from __future__ import annotations

import hashlib
import json
import re
import ssl
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol

from .n3w_trusted_product_lan import (
    TrustedProductLanState,
    load_trusted_product_lan,
)
from .pairing_discovery import SlidingWindowRateLimiter
from .pairing_secure_transport import decode_base64url_32

CONFIRM_SCHEMA = "gh.registration.confirm/1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HARDWARE_ID = re.compile(r"^ghw-[a-z0-9]+-[0-9a-f]{12}$")


class RegistrationBootstrapRejected(RuntimeError):
    pass


class RegistrationTransactionService(Protocol):
    def start(
        self,
        request: dict[str, str],
        *,
        source_ip: str,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class BootstrapSkeletonResult:
    status: str
    reason: str | None = None
    transaction_started: bool = False
    manager_id: str | None = None
    system_id: str | None = None
    pairing_host: str | None = None
    pairing_port: int | None = None
    pairing_path: str | None = None
    expires_in_seconds: int | None = None

    def to_document(self) -> dict[str, Any]:
        if self.transaction_started:
            return {
                "schema": "gh.registration.confirm-result/1",
                "accepted": True,
                "status": "accepted",
                "manager_id": self.manager_id,
                "system_id": self.system_id,
                "pairing_host": self.pairing_host,
                "pairing_port": self.pairing_port,
                "pairing_path": self.pairing_path,
                "expires_in_seconds": self.expires_in_seconds,
            }
        return {
            "schema": "gh.registration.confirm-result/1",
            "accepted": False,
            "status": self.status,
            "reason": self.reason,
        }


_REQUIRED_FIELDS = {
    "schema",
    "manager_id",
    "system_id",
    "hardware_id",
    "pairing_id",
    "setup_secret",
}


def validate_bootstrap_source(
    source_ip: str,
    *,
    state_loader: Callable[[], TrustedProductLanState] = load_trusted_product_lan,
) -> None:
    state = state_loader()
    if not state.available:
        raise RegistrationBootstrapRejected("trusted_product_lan_unavailable")
    if not state.authorizes(source_ip):
        raise RegistrationBootstrapRejected("source_not_trusted_product_lan")


def validate_confirm_document(document: Any) -> dict[str, str]:
    if not isinstance(document, dict) or set(document) != _REQUIRED_FIELDS:
        raise RegistrationBootstrapRejected("identity_invalid")
    if document.get("schema") != CONFIRM_SCHEMA:
        raise RegistrationBootstrapRejected("identity_invalid")
    manager_id = document.get("manager_id")
    system_id = document.get("system_id")
    hardware_id = document.get("hardware_id")
    pairing_id = document.get("pairing_id")
    setup_secret = document.get("setup_secret")
    if (
        not isinstance(manager_id, str)
        or _SAFE_ID.fullmatch(manager_id) is None
        or not isinstance(system_id, str)
        or _SAFE_ID.fullmatch(system_id) is None
        or not isinstance(hardware_id, str)
        or _HARDWARE_ID.fullmatch(hardware_id) is None
        or not isinstance(pairing_id, str)
        or not isinstance(setup_secret, str)
    ):
        raise RegistrationBootstrapRejected("identity_invalid")
    try:
        parsed_pairing = uuid.UUID(pairing_id)
        decode_base64url_32(
            setup_secret,
            field_name="setup_secret",
        )
    except ValueError as error:
        raise RegistrationBootstrapRejected("identity_invalid") from error
    if str(parsed_pairing) != pairing_id:
        raise RegistrationBootstrapRejected("identity_invalid")
    return {
        "manager_id": manager_id,
        "system_id": system_id,
        "hardware_id": hardware_id,
        "pairing_id": pairing_id,
        "setup_secret": setup_secret,
    }


def evaluate_confirm_skeleton(
    document: Any,
    *,
    source_ip: str,
    expected_manager_id: str,
    expected_system_id: str,
    state_loader: Callable[[], TrustedProductLanState] = load_trusted_product_lan,
) -> BootstrapSkeletonResult:
    validate_bootstrap_source(source_ip, state_loader=state_loader)
    request = validate_confirm_document(document)
    if request["manager_id"] != expected_manager_id:
        raise RegistrationBootstrapRejected("manager_mismatch")
    if request["system_id"] != expected_system_id:
        raise RegistrationBootstrapRejected("system_mismatch")
    return BootstrapSkeletonResult(
        status="unavailable",
        reason="first_registration_transaction_not_implemented",
    )


MAX_CONFIRM_BODY_BYTES = 2048
CONFIRM_PATH = "/v1/registration/confirm"


def bootstrap_certificate_sha256(path: str | Path) -> str:
    certificate_path = Path(path)
    if (
        not certificate_path.is_absolute()
        or certificate_path.is_symlink()
        or not certificate_path.is_file()
    ):
        raise ValueError("registration bootstrap certificate path invalid")
    pem = certificate_path.read_text(encoding="utf-8")
    try:
        der = ssl.PEM_cert_to_DER_cert(pem)
    except ValueError as error:
        raise ValueError("registration bootstrap certificate invalid") from error
    return hashlib.sha256(der).hexdigest()


class RegistrationBootstrapApp:
    def __init__(
        self,
        *,
        manager_id: str,
        system_id: str,
        state_loader: Callable[[], TrustedProductLanState] = load_trusted_product_lan,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        transaction_service: RegistrationTransactionService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.manager_id = manager_id
        self.system_id = system_id
        self.state_loader = state_loader
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
            limit=12,
            window_s=60,
        )
        self.transaction_service = transaction_service
        self.clock = clock

    def authorize_source(self, source_ip: str) -> None:
        validate_bootstrap_source(source_ip, state_loader=self.state_loader)
        if not self.rate_limiter.allow(source_ip):
            raise RegistrationBootstrapRejected("registration_rate_limited")

    def handle_confirm(
        self,
        document: Any,
        *,
        source_ip: str,
        source_already_authorized: bool = False,
    ) -> BootstrapSkeletonResult:
        if not source_already_authorized:
            self.authorize_source(source_ip)
        validate_bootstrap_source(
            source_ip,
            state_loader=self.state_loader,
        )
        request = validate_confirm_document(document)
        if request["manager_id"] != self.manager_id:
            raise RegistrationBootstrapRejected("manager_mismatch")
        if request["system_id"] != self.system_id:
            raise RegistrationBootstrapRejected("system_mismatch")
        service = self.transaction_service
        if service is None:
            return BootstrapSkeletonResult(
                status="unavailable",
                reason="first_registration_transaction_not_implemented",
            )
        try:
            started = service.start(
                request,
                source_ip=source_ip,
            )
        except RuntimeError as error:
            raise RegistrationBootstrapRejected(str(error)) from error
        observed_at = (
            self.clock()
            if self.clock is not None
            else datetime.now(UTC)
        )
        return BootstrapSkeletonResult(
            status="accepted",
            transaction_started=True,
            manager_id=started.manager_id,
            system_id=started.system_id,
            pairing_host=started.pairing_host,
            pairing_port=started.pairing_port,
            pairing_path=started.pairing_path,
            expires_in_seconds=started.expires_in_seconds(
                now=observed_at,
            ),
        )


class RegistrationBootstrapHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        app: RegistrationBootstrapApp,
    ) -> None:
        self.app = app
        super().__init__(server_address, _RegistrationBootstrapHandler)


class _RegistrationBootstrapHandler(BaseHTTPRequestHandler):
    server: RegistrationBootstrapHTTPServer

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _write_json(self, status: HTTPStatus, document: dict[str, Any]) -> None:
        payload = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        if self.path != CONFIRM_PATH:
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {
                    "schema": "gh.registration.confirm-result/1",
                    "accepted": False,
                    "status": "rejected",
                    "reason": "path_not_found",
                },
            )
            return

        source_ip = self.client_address[0]
        try:
            self.server.app.authorize_source(source_ip)
        except RegistrationBootstrapRejected as error:
            status = (
                HTTPStatus.SERVICE_UNAVAILABLE
                if str(error) == "trusted_product_lan_unavailable"
                else HTTPStatus.FORBIDDEN
            )
            self._write_json(
                status,
                {
                    "schema": "gh.registration.confirm-result/1",
                    "accepted": False,
                    "status": "rejected",
                    "reason": str(error),
                },
            )
            return

        content_type = self.headers.get("Content-Type", "")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if (
            content_type.split(";", 1)[0].strip().lower() != "application/json"
            or not 1 <= length <= MAX_CONFIRM_BODY_BYTES
        ):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "schema": "gh.registration.confirm-result/1",
                    "accepted": False,
                    "status": "rejected",
                    "reason": "request_invalid",
                },
            )
            return

        try:
            body = self.rfile.read(length)
            document = json.loads(body.decode("utf-8"))
            result = self.server.app.handle_confirm(
                document,
                source_ip=source_ip,
                source_already_authorized=True,
            )
        except (UnicodeError, json.JSONDecodeError):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "schema": "gh.registration.confirm-result/1",
                    "accepted": False,
                    "status": "rejected",
                    "reason": "request_invalid",
                },
            )
            return
        except RegistrationBootstrapRejected as error:
            reason = str(error)
            status = (
                HTTPStatus.CONFLICT
                if reason in {
                    "manager_mismatch",
                    "system_mismatch",
                    "registration_busy",
                    "replay_detected",
                    "expired",
                }
                else HTTPStatus.SERVICE_UNAVAILABLE
                if reason == "bootstrap_unavailable"
                else HTTPStatus.BAD_REQUEST
            )
            self._write_json(
                status,
                {
                    "schema": "gh.registration.confirm-result/1",
                    "accepted": False,
                    "status": "rejected",
                    "reason": reason,
                },
            )
            return

        self._write_json(
            HTTPStatus.OK
            if result.transaction_started
            else HTTPStatus.SERVICE_UNAVAILABLE,
            result.to_document(),
        )


def make_registration_bootstrap_tls_server(
    server_address: tuple[str, int],
    *,
    app: RegistrationBootstrapApp,
    certificate_file: str | Path,
    private_key_file: str | Path,
) -> RegistrationBootstrapHTTPServer:
    certificate_path = Path(certificate_file)
    private_key_path = Path(private_key_file)
    for path in (certificate_path, private_key_path):
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise ValueError("registration bootstrap TLS path invalid")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(
        certfile=str(certificate_path),
        keyfile=str(private_key_path),
    )
    server = RegistrationBootstrapHTTPServer(server_address, app=app)
    try:
        server.socket = context.wrap_socket(server.socket, server_side=True)
    except Exception:
        server.server_close()
        raise
    return server
