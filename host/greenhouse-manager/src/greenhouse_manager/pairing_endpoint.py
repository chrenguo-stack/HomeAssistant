from __future__ import annotations

import hashlib
import hmac
import json
import re
import socket
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

from .pairing_discovery import is_local_source
from .pairing_service import (
    PairingConflict as CorePairingConflict,
    PairingError as CorePairingError,
    PairingExpired as CorePairingExpired,
    PairingProofRejected as CorePairingProofRejected,
    PairingProvisioningError as CorePairingProvisioningError,
    PairingRollbackError as CorePairingRollbackError,
)
from .pairing_secure_transport import (
    SecureEnvelope,
    SecureEnvelopeRejected,
    SecurePairingConflict,
    SecurePairingError,
    SecurePairingKeyRejected,
    SecurePairingOffer,
    SecurePairingProofRejected,
    SecurePairingRollbackError,
    SecurePairingSnapshot,
    decode_base64url_32,
    encode_base64url,
)

MAX_REQUEST_BYTES = 16 * 1024
MAX_ACTIVE_REQUESTS = 16
REQUEST_TIMEOUT_S = 5.0
_SESSION_PATH = re.compile(
    r"^/v1/pairing/sessions/([0-9a-fA-F-]{36})/(establish|credentials|ack|abort|status)$"
)


class PairingEndpointError(RuntimeError):
    pass


class PairingNotFound(PairingEndpointError):
    pass


class PairingRequestRejected(PairingEndpointError):
    pass


class PairingRequestRateLimited(PairingEndpointError):
    pass


class PairingCoordinatorLike(Protocol):
    def open_session(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        pairing_secret: str,
        now: datetime | None = None,
    ) -> SecurePairingOffer: ...

    def establish_channel(
        self,
        session_id: str,
        *,
        node_nonce: str,
        node_public_key: str,
        proof: str,
        now: datetime | None = None,
    ) -> SecurePairingSnapshot: ...

    def issue_encrypted_credentials(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> SecureEnvelope: ...

    def acknowledge_encrypted_delivery(
        self,
        session_id: str,
        envelope: SecureEnvelope | Mapping[str, Any],
        *,
        now: datetime | None = None,
    ) -> SecurePairingSnapshot: ...

    def abort(self, session_id: str) -> SecurePairingSnapshot: ...

    def status(
        self,
        session_id: str,
        *,
        now: datetime | None = None,
    ) -> SecurePairingSnapshot: ...


@dataclass(frozen=True, slots=True)
class PairingHTTPResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(slots=True)
class _RegisteredOffer:
    offer: SecurePairingOffer
    claim_proof: bytearray
    claimed_by: str | None = None


def build_claim_proof(
    *,
    pairing_secret: str,
    hardware_id: str,
    pairing_id: str,
) -> str:
    secret = decode_base64url_32(
        pairing_secret,
        field_name="pairing_secret",
    )
    try:
        transcript = "\n".join(
            (
                "gh.pair.claim/1",
                hardware_id,
                pairing_id,
            )
        ).encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("claim identifiers must be ASCII") from error
    return encode_base64url(
        hmac.new(secret, transcript, hashlib.sha256).digest()
    )


class PendingOfferRegistry:
    """Local-UI-only QR import boundary plus node-facing one-time claim."""

    def __init__(self, coordinator: PairingCoordinatorLike) -> None:
        self.coordinator = coordinator
        self._lock = threading.RLock()
        self._by_pairing: dict[tuple[str, str], _RegisteredOffer] = {}
        self._by_session: dict[str, _RegisteredOffer] = {}

    def import_scanned_pairing(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        pairing_secret: str,
        now: datetime | None = None,
    ) -> SecurePairingOffer:
        """Called only by the trusted local UI after the user scans the node QR."""

        claim_proof = decode_base64url_32(
            build_claim_proof(
                pairing_secret=pairing_secret,
                hardware_id=hardware_id,
                pairing_id=pairing_id,
            ),
            field_name="claim_proof",
        )
        offer = self.coordinator.open_session(
            hardware_id,
            pairing_id,
            pairing_secret=pairing_secret,
            now=now,
        )
        registered = _RegisteredOffer(
            offer=offer,
            claim_proof=bytearray(claim_proof),
        )
        key = (hardware_id, pairing_id)
        with self._lock:
            if key in self._by_pairing or offer.session_id in self._by_session:
                try:
                    self.coordinator.abort(offer.session_id)
                finally:
                    raise SecurePairingConflict("pairing offer is already registered")
            self._by_pairing[key] = registered
            self._by_session[offer.session_id] = registered
        return offer

    def claim(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        client_ip: str,
        claim_proof: str,
        now: datetime | None = None,
    ) -> SecurePairingOffer:
        key = (hardware_id, pairing_id)
        with self._lock:
            try:
                registered = self._by_pairing[key]
            except KeyError as error:
                raise PairingNotFound("pairing offer is unavailable") from error
            try:
                supplied = decode_base64url_32(
                    claim_proof,
                    field_name="claim_proof",
                )
            except ValueError as error:
                raise SecurePairingProofRejected("claim proof rejected") from error
            if not hmac.compare_digest(
                supplied,
                bytes(registered.claim_proof),
            ):
                raise SecurePairingProofRejected("claim proof rejected")
            snapshot = self.coordinator.status(
                registered.offer.session_id,
                now=now,
            )
            if snapshot.state.value in {"failed", "expired", "consumed"}:
                self.release_terminal(registered.offer.session_id)
                raise PairingNotFound("pairing offer is unavailable")
            if registered.claimed_by is None:
                registered.claimed_by = client_ip
            elif registered.claimed_by != client_ip:
                raise SecurePairingConflict("pairing offer is already claimed")
            return registered.offer

    def require_session(self, session_id: str, *, client_ip: str) -> SecurePairingOffer:
        with self._lock:
            try:
                registered = self._by_session[session_id]
            except KeyError as error:
                raise PairingNotFound("pairing session is unavailable") from error
            if registered.claimed_by != client_ip:
                raise PairingNotFound("pairing session is unavailable")
            return registered.offer

    def release_terminal(self, session_id: str) -> None:
        with self._lock:
            registered = self._by_session.pop(session_id, None)
            if registered is None:
                return
            self._by_pairing.pop(
                (registered.offer.hardware_id, registered.offer.pairing_id),
                None,
            )
            for index in range(len(registered.claim_proof)):
                registered.claim_proof[index] = 0
            registered.claim_proof.clear()


class FixedWindowRateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit < 1 or window_s <= 0:
            raise ValueError("rate limit and window must be positive")
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._lock = threading.RLock()
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        cutoff = now - self.window_s
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


def _strict_json(body: bytes) -> Mapping[str, Any]:
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PairingRequestRejected("request body is invalid JSON") from error
    if not isinstance(document, dict):
        raise PairingRequestRejected("request body must be a JSON object")
    return document


def _require_exact_fields(document: Mapping[str, Any], fields: set[str]) -> None:
    if set(document) != fields:
        raise PairingRequestRejected("request fields are invalid")


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _offer_document(offer: SecurePairingOffer) -> dict[str, Any]:
    return {
        "schema": offer.schema,
        "session_id": offer.session_id,
        "hardware_id": offer.hardware_id,
        "pairing_id": offer.pairing_id,
        "manager_nonce": offer.manager_nonce,
        "manager_public_key": offer.manager_public_key,
        "cipher_suite": offer.cipher_suite,
        "expires_at": _iso(offer.expires_at),
        "max_proof_attempts": offer.max_proof_attempts,
    }


def _snapshot_document(snapshot: SecurePairingSnapshot) -> dict[str, Any]:
    return {
        "schema": "gh.pair.secure-status/1",
        "session_id": snapshot.session_id,
        "state": snapshot.state.value,
        "expires_at": _iso(snapshot.expires_at),
        "proof_attempts": snapshot.proof_attempts,
        "credential_generation": snapshot.credential_generation,
    }


def _json_response(
    status: int,
    document: Mapping[str, Any],
    *,
    request_id: str,
) -> PairingHTTPResponse:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return PairingHTTPResponse(
        status=status,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Request-ID": request_id,
            "Connection": "close",
        },
        body=payload,
    )


class PairingEndpointApp:
    def __init__(
        self,
        registry: PendingOfferRegistry,
        *,
        rate_limiter: FixedWindowRateLimiter | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.registry = registry
        self.coordinator = registry.coordinator
        self.rate_limiter = rate_limiter or FixedWindowRateLimiter(
            limit=30,
            window_s=60,
        )
        self.clock = clock

    def handle(
        self,
        *,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: bytes,
        client_ip: str,
    ) -> PairingHTTPResponse:
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        request_id = normalized_headers.get("x-request-id", "")
        try:
            request_id = (
                str(uuid.UUID(request_id))
                if request_id
                else str(uuid.uuid4())
            )
        except ValueError:
            request_id = str(uuid.uuid4())

        try:
            if not is_local_source(client_ip):
                raise PairingRequestRejected(
                    "request source is outside the local network"
                )
            if not self.rate_limiter.allow(client_ip):
                raise PairingRequestRateLimited("request rate limit exceeded")
            if len(body) > MAX_REQUEST_BYTES:
                return self._error(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "request_too_large",
                    request_id,
                )
            if method not in {"GET", "POST"}:
                return self._error(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    "method_not_allowed",
                    request_id,
                )
            if method == "POST":
                content_type = (
                    normalized_headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if content_type != "application/json":
                    return self._error(
                        HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                        "json_required",
                        request_id,
                    )
            return self._dispatch(method, path, body, client_ip, request_id)
        except PairingRequestRateLimited:
            return self._error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "rate_limited",
                request_id,
            )
        except PairingNotFound:
            return self._error(HTTPStatus.NOT_FOUND, "not_found", request_id)
        except PairingRequestRejected:
            return self._error(
                HTTPStatus.BAD_REQUEST,
                "invalid_request",
                request_id,
            )
        except (SecurePairingProofRejected, CorePairingProofRejected):
            return self._error(
                HTTPStatus.FORBIDDEN,
                "proof_rejected",
                request_id,
            )
        except (SecurePairingKeyRejected, SecureEnvelopeRejected):
            return self._error(
                HTTPStatus.BAD_REQUEST,
                "secure_message_rejected",
                request_id,
            )
        except (
            SecurePairingConflict,
            CorePairingConflict,
            CorePairingExpired,
        ):
            return self._error(
                HTTPStatus.CONFLICT,
                "pairing_conflict",
                request_id,
            )
        except (
            SecurePairingRollbackError,
            CorePairingRollbackError,
            CorePairingProvisioningError,
        ):
            return self._error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "rollback_failed",
                request_id,
            )
        except (SecurePairingError, CorePairingError):
            return self._error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "pairing_failed",
                request_id,
            )
        except Exception:
            return self._error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
                request_id,
            )

    def _dispatch(
        self,
        method: str,
        path: str,
        body: bytes,
        client_ip: str,
        request_id: str,
    ) -> PairingHTTPResponse:
        if method == "GET" and path == "/healthz":
            return _json_response(
                HTTPStatus.OK,
                {"schema": "gh.pair.health/1", "status": "ok"},
                request_id=request_id,
            )
        if method == "POST" and path == "/v1/pairing/claim":
            document = _strict_json(body)
            _require_exact_fields(
                document,
                {"schema", "hardware_id", "pairing_id", "claim_proof"},
            )
            if document["schema"] != "gh.pair.claim/1":
                raise PairingRequestRejected("claim schema is invalid")
            hardware_id = document["hardware_id"]
            pairing_id = document["pairing_id"]
            claim_proof = document["claim_proof"]
            if any(
                not isinstance(value, str)
                for value in (hardware_id, pairing_id, claim_proof)
            ):
                raise PairingRequestRejected("claim values are invalid")
            offer = self.registry.claim(
                hardware_id,
                pairing_id,
                client_ip=client_ip,
                claim_proof=claim_proof,
                now=self.clock(),
            )
            return _json_response(
                HTTPStatus.OK,
                _offer_document(offer),
                request_id=request_id,
            )

        match = _SESSION_PATH.fullmatch(path)
        if match is None:
            raise PairingNotFound("route is unavailable")
        session_id, action = match.groups()
        try:
            uuid.UUID(session_id)
        except ValueError as error:
            raise PairingNotFound("pairing session is unavailable") from error
        self.registry.require_session(session_id, client_ip=client_ip)
        now = self.clock()

        if method == "GET" and action == "status":
            snapshot = self.coordinator.status(session_id, now=now)
            response = _json_response(
                HTTPStatus.OK,
                _snapshot_document(snapshot),
                request_id=request_id,
            )
            if snapshot.state.value in {"failed", "expired", "consumed"}:
                self.registry.release_terminal(session_id)
            return response
        if method != "POST" or action == "status":
            return self._error(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "method_not_allowed",
                request_id,
            )

        document = _strict_json(body)
        if action == "establish":
            _require_exact_fields(
                document,
                {"schema", "node_nonce", "node_public_key", "proof"},
            )
            if document["schema"] != "gh.pair.establish/1":
                raise PairingRequestRejected("establish schema is invalid")
            values = (
                document["node_nonce"],
                document["node_public_key"],
                document["proof"],
            )
            if any(not isinstance(value, str) for value in values):
                raise PairingRequestRejected("establish values are invalid")
            snapshot = self.coordinator.establish_channel(
                session_id,
                node_nonce=values[0],
                node_public_key=values[1],
                proof=values[2],
                now=now,
            )
            return _json_response(
                HTTPStatus.OK,
                _snapshot_document(snapshot),
                request_id=request_id,
            )
        if action == "credentials":
            _require_exact_fields(document, {"schema"})
            if document["schema"] != "gh.pair.credentials-request/1":
                raise PairingRequestRejected(
                    "credentials request schema is invalid"
                )
            envelope = self.coordinator.issue_encrypted_credentials(
                session_id,
                now=now,
            )
            return _json_response(
                HTTPStatus.OK,
                envelope.to_document(),
                request_id=request_id,
            )
        if action == "ack":
            snapshot = self.coordinator.acknowledge_encrypted_delivery(
                session_id,
                document,
                now=now,
            )
            response = _json_response(
                HTTPStatus.OK,
                _snapshot_document(snapshot),
                request_id=request_id,
            )
            self.registry.release_terminal(session_id)
            return response
        if action == "abort":
            _require_exact_fields(document, {"schema"})
            if document["schema"] != "gh.pair.abort/1":
                raise PairingRequestRejected("abort schema is invalid")
            snapshot = self.coordinator.abort(session_id)
            response = _json_response(
                HTTPStatus.OK,
                _snapshot_document(snapshot),
                request_id=request_id,
            )
            self.registry.release_terminal(session_id)
            return response
        raise PairingNotFound("route is unavailable")

    @staticmethod
    def _error(
        status: int,
        code: str,
        request_id: str,
    ) -> PairingHTTPResponse:
        return _json_response(
            status,
            {"schema": "gh.pair.error/1", "error": code},
            request_id=request_id,
        )


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        app: PairingEndpointApp,
        max_active_requests: int = MAX_ACTIVE_REQUESTS,
    ) -> None:
        if max_active_requests < 1:
            raise ValueError("max_active_requests must be positive")
        self.app = app
        self._slots = threading.BoundedSemaphore(max_active_requests)
        super().__init__(server_address, handler_class)

    def process_request(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(
                    b"HTTP/1.1 503 Service Unavailable\r\n"
                    b"Content-Length: 0\r\n"
                    b"Connection: close\r\n\r\n"
                )
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class PairingRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "GreenhousePairing/1"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(REQUEST_TIMEOUT_S)

    def do_GET(self) -> None:
        self._handle_request()

    def do_POST(self) -> None:
        self._handle_request()

    def do_PUT(self) -> None:
        self._handle_request()

    def do_DELETE(self) -> None:
        self._handle_request()

    def _handle_request(self) -> None:
        server = self.server
        if not isinstance(server, BoundedThreadingHTTPServer):
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        transfer_encoding = self.headers.get("Transfer-Encoding")
        if transfer_encoding:
            response = server.app._error(
                HTTPStatus.BAD_REQUEST,
                "chunked_encoding_not_supported",
                self.headers.get("X-Request-ID", "invalid"),
            )
            self._write(response)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = -1
        if content_length < 0:
            response = server.app._error(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_length",
                self.headers.get("X-Request-ID", "invalid"),
            )
            self._write(response)
            return
        if content_length > MAX_REQUEST_BYTES:
            response = server.app._error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "request_too_large",
                self.headers.get("X-Request-ID", "invalid"),
            )
            self._write(response)
            return
        body = self.rfile.read(content_length) if content_length else b""
        response = server.app.handle(
            method=self.command,
            path=self.path,
            headers={key: value for key, value in self.headers.items()},
            body=body,
            client_ip=self.client_address[0],
        )
        self._write(response)

    def _write(self, response: PairingHTTPResponse) -> None:
        self.send_response(response.status)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        if response.body:
            self.wfile.write(response.body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def make_pairing_http_server(
    bind: tuple[str, int],
    *,
    app: PairingEndpointApp,
    max_active_requests: int = MAX_ACTIVE_REQUESTS,
) -> BoundedThreadingHTTPServer:
    return BoundedThreadingHTTPServer(
        bind,
        PairingRequestHandler,
        app=app,
        max_active_requests=max_active_requests,
    )
