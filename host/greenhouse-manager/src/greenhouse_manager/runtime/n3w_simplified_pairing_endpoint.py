from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from .pairing_discovery import is_local_source
from .pairing_endpoint import (
    FixedWindowRateLimiter,
    PairingHTTPResponse,
)
from .n3w_simplified_pairing import (
    SimplifiedPairingConflict,
    SimplifiedPairingCoordinator,
    SimplifiedPairingError,
    SimplifiedPairingRejected,
)

_SESSION_PATH = re.compile(
    r"^/v2/pairing/sessions/([0-9a-fA-F-]{36})/(establish|ack|abort|status)$"
)
_MAX_REQUEST_BYTES = 16 * 1024


def _response(status: int, document: Mapping[str, Any], request_id: str) -> PairingHTTPResponse:
    body = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return PairingHTTPResponse(
        status=status,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Request-ID": request_id,
            "Connection": "close",
        },
        body=body,
    )


def _strict_json(body: bytes) -> Mapping[str, Any]:
    try:
        document = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SimplifiedPairingRejected("request_json_invalid") from error
    if not isinstance(document, dict):
        raise SimplifiedPairingRejected("request_json_invalid")
    return document


def _exact(document: Mapping[str, Any], fields: set[str]) -> None:
    if set(document) != fields:
        raise SimplifiedPairingRejected("request_fields_invalid")


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class SimplifiedPairingEndpointApp:
    """Local-only HTTP adapter for Phase 4 Setup-Secret pairing."""

    def __init__(
        self,
        coordinator: SimplifiedPairingCoordinator,
        *,
        rate_limiter: FixedWindowRateLimiter | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.coordinator = coordinator
        self.registry = coordinator.registry
        self.rate_limiter = rate_limiter or FixedWindowRateLimiter(limit=30, window_s=60)
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
        request_id = headers.get("X-Request-ID") or headers.get("x-request-id") or str(uuid.uuid4())
        try:
            request_id = str(uuid.UUID(request_id))
        except ValueError:
            request_id = str(uuid.uuid4())
        try:
            if not is_local_source(client_ip):
                raise SimplifiedPairingRejected("source_not_local")
            if not self.rate_limiter.allow(client_ip):
                return self._error(HTTPStatus.TOO_MANY_REQUESTS, "rate_limited", request_id)
            if len(body) > _MAX_REQUEST_BYTES:
                return self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request_too_large", request_id)
            if method not in {"GET", "POST"}:
                return self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", request_id)
            return self._dispatch(method, path, body, request_id)
        except SimplifiedPairingRejected as error:
            return self._error(HTTPStatus.FORBIDDEN, str(error), request_id)
        except SimplifiedPairingConflict as error:
            return self._error(HTTPStatus.CONFLICT, str(error), request_id)
        except KeyError:
            return self._error(HTTPStatus.NOT_FOUND, "registration_not_found", request_id)
        except SimplifiedPairingError:
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "pairing_failed", request_id)
        except (TypeError, ValueError):
            return self._error(HTTPStatus.BAD_REQUEST, "invalid_request", request_id)

    def _dispatch(
        self,
        method: str,
        path: str,
        body: bytes,
        request_id: str,
    ) -> PairingHTTPResponse:
        if method == "GET" and path == "/healthz":
            return _response(
                HTTPStatus.OK,
                {"schema": "gh.pair.simple-health/1", "status": "ok"},
                request_id,
            )
        if method == "POST" and path == "/v2/pairing/hello":
            document = _strict_json(body)
            result = self.registry.observe_hello(document, now=self.clock())
            return _response(
                HTTPStatus.OK,
                {
                    "schema": "gh.pair.simple-hello-result/1",
                    "status": result.state.value,
                    "hardware_id": result.hardware_id,
                    "pairing_id": result.pairing_id,
                },
                request_id,
            )
        if method == "POST" and path == "/v2/pairing/begin":
            document = _strict_json(body)
            _exact(document, {"schema", "hardware_id", "pairing_id", "node_nonce"})
            if document["schema"] != "gh.pair.simple-begin/1":
                raise SimplifiedPairingRejected("schema_invalid")
            values = (document["hardware_id"], document["pairing_id"], document["node_nonce"])
            if any(not isinstance(value, str) for value in values):
                raise SimplifiedPairingRejected("request_fields_invalid")
            offer = self.coordinator.begin(
                values[0], values[1], node_nonce=values[2], now=self.clock()
            )
            return _response(
                HTTPStatus.OK,
                {
                    "schema": offer.schema,
                    "session_id": offer.session_id,
                    "hardware_id": offer.hardware_id,
                    "pairing_id": offer.pairing_id,
                    "manager_id": offer.manager_id,
                    "manager_nonce": offer.manager_nonce,
                    "manager_proof": offer.manager_proof,
                    "expires_at": _iso(offer.expires_at),
                },
                request_id,
            )

        match = _SESSION_PATH.fullmatch(path)
        if match is None:
            return self._error(HTTPStatus.NOT_FOUND, "not_found", request_id)
        session_id, action = match.groups()
        try:
            uuid.UUID(session_id)
        except ValueError:
            return self._error(HTTPStatus.NOT_FOUND, "not_found", request_id)
        now = self.clock()
        if method == "GET" and action == "status":
            snapshot = self.coordinator.status(session_id, now=now)
            return _response(
                HTTPStatus.OK,
                {
                    "schema": "gh.pair.simple-status/1",
                    "session_id": snapshot.session_id,
                    "state": snapshot.state.value,
                    "node_id": snapshot.node_id,
                    "expires_at": _iso(snapshot.expires_at),
                },
                request_id,
            )
        if method != "POST" or action == "status":
            return self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", request_id)
        document = _strict_json(body)
        if action == "establish":
            _exact(document, {"schema", "node_proof"})
            if document["schema"] != "gh.pair.simple-establish/1" or not isinstance(document["node_proof"], str):
                raise SimplifiedPairingRejected("schema_invalid")
            encrypted = self.coordinator.establish(
                session_id,
                node_proof=document["node_proof"],
                now=now,
            )
            return _response(
                HTTPStatus.OK,
                {
                    "schema": encrypted.schema,
                    "session_id": encrypted.session_id,
                    "node_id": encrypted.node_id,
                    "nonce": encrypted.nonce,
                    "ciphertext": encrypted.ciphertext,
                    "delivery_digest": encrypted.delivery_digest,
                },
                request_id,
            )
        if action == "ack":
            _exact(document, {"schema", "delivery_digest"})
            if document["schema"] != "gh.pair.simple-ack/1" or not isinstance(document["delivery_digest"], str):
                raise SimplifiedPairingRejected("schema_invalid")
            snapshot = self.coordinator.acknowledge(
                session_id,
                delivery_digest=document["delivery_digest"],
                now=now,
            )
            return _response(
                HTTPStatus.OK,
                {
                    "schema": "gh.pair.simple-status/1",
                    "session_id": snapshot.session_id,
                    "state": snapshot.state.value,
                    "node_id": snapshot.node_id,
                    "expires_at": _iso(snapshot.expires_at),
                },
                request_id,
            )
        if action == "abort":
            _exact(document, {"schema"})
            if document["schema"] != "gh.pair.simple-abort/1":
                raise SimplifiedPairingRejected("schema_invalid")
            snapshot = self.coordinator.abort(session_id)
            return _response(
                HTTPStatus.OK,
                {
                    "schema": "gh.pair.simple-status/1",
                    "session_id": snapshot.session_id,
                    "state": snapshot.state.value,
                    "node_id": snapshot.node_id,
                    "expires_at": _iso(snapshot.expires_at),
                },
                request_id,
            )
        return self._error(HTTPStatus.NOT_FOUND, "not_found", request_id)

    @staticmethod
    def _error(status: int, code: str, request_id: str) -> PairingHTTPResponse:
        return _response(
            status,
            {"schema": "gh.pair.simple-error/1", "error": code},
            request_id,
        )
