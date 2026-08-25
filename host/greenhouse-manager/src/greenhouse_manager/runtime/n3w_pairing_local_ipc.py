from __future__ import annotations

import base64
import json
import os
import socket
import stat
import threading
from pathlib import Path
from typing import Protocol

SCHEMA = "gh.pair.setup-secret-import/1"
RESPONSE_SCHEMA = "gh.pair.setup-secret-import-result/1"
MAX_REQUEST_BYTES = 4096


class SetupSecretImporter(Protocol):
    def import_setup_secret(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        setup_secret: bytes,
    ) -> None: ...


class PairingLocalIpcError(RuntimeError):
    pass


def _has_symlink(path: Path) -> bool:
    current = path
    while current != current.parent:
        if current.is_symlink():
            return True
        current = current.parent
    return current.is_symlink()


def _decode_secret(value: object) -> bytearray:
    if not isinstance(value, str) or not value or not value.isascii():
        raise PairingLocalIpcError("setup_secret_encoding_invalid")
    try:
        decoded = bytearray(
            base64.urlsafe_b64decode(value + "=" * ((4 - len(value) % 4) % 4))
        )
    except (TypeError, ValueError) as error:
        raise PairingLocalIpcError("setup_secret_encoding_invalid") from error
    if len(decoded) != 32:
        raise PairingLocalIpcError("setup_secret_length_invalid")
    return decoded


def _response(*, accepted: bool, code: str) -> bytes:
    return (
        json.dumps(
            {
                "accepted": accepted,
                "code": code,
                "schema": RESPONSE_SCHEMA,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


class ManagerOwnedPairingSocket:
    """Manager-owned, local-only Setup Secret import endpoint."""

    def __init__(
        self,
        coordinator: SetupSecretImporter,
        path: str | Path,
        *,
        mode: int = 0o600,
    ) -> None:
        self.coordinator = coordinator
        self.path = Path(path).expanduser()
        self.mode = mode
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._validate_path()

    def _validate_path(self) -> None:
        if not self.path.is_absolute() or _has_symlink(self.path.parent):
            raise PairingLocalIpcError("pairing_socket_path_invalid")
        if self.mode & 0o077:
            raise PairingLocalIpcError("pairing_socket_mode_invalid")
        parent = self.path.parent
        if not parent.is_dir():
            raise PairingLocalIpcError("pairing_socket_parent_missing")
        info = parent.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o022:
            raise PairingLocalIpcError("pairing_socket_parent_unsafe")
        if self.path.exists() or self.path.is_symlink():
            raise PairingLocalIpcError("pairing_socket_path_exists")

    @property
    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_alive:
            return
        self._validate_path()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.path))
            os.chmod(self.path, self.mode)
            listener.listen(8)
            listener.settimeout(0.25)
        except Exception:
            listener.close()
            self.path.unlink(missing_ok=True)
            raise
        self._socket = listener
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._serve,
            name="n3w-pairing-local-ipc",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        listener = self._socket
        if listener is not None:
            listener.close()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout_s)
        if thread is not None and thread.is_alive():
            raise PairingLocalIpcError("pairing_socket_stop_timeout")
        self._socket = None
        self.path.unlink(missing_ok=True)

    def _serve(self) -> None:
        while not self._stop.is_set():
            listener = self._socket
            if listener is None:
                return
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                if self._stop.is_set():
                    return
                raise
            with connection:
                connection.settimeout(2.0)
                connection.sendall(self._handle(connection))

    def _handle(self, connection: socket.socket) -> bytes:
        payload = bytearray()
        try:
            while len(payload) <= MAX_REQUEST_BYTES:
                block = connection.recv(min(1024, MAX_REQUEST_BYTES + 1 - len(payload)))
                if not block:
                    break
                payload.extend(block)
                if b"\n" in block:
                    break
            if len(payload) > MAX_REQUEST_BYTES:
                raise PairingLocalIpcError("request_too_large")
            document = json.loads(bytes(payload).decode("utf-8"))
            if not isinstance(document, dict) or set(document) != {
                "schema",
                "hardware_id",
                "pairing_id",
                "setup_secret",
            }:
                raise PairingLocalIpcError("request_fields_invalid")
            if document["schema"] != SCHEMA:
                raise PairingLocalIpcError("request_schema_invalid")
            hardware_id = document["hardware_id"]
            pairing_id = document["pairing_id"]
            if not isinstance(hardware_id, str) or not isinstance(pairing_id, str):
                raise PairingLocalIpcError("request_identity_invalid")
            secret = _decode_secret(document["setup_secret"])
            try:
                self.coordinator.import_setup_secret(
                    hardware_id,
                    pairing_id,
                    setup_secret=bytes(secret),
                )
            finally:
                secret[:] = b"\0" * len(secret)
                secret.clear()
            return _response(accepted=True, code="accepted")
        except Exception as error:
            code = str(error) if isinstance(error, PairingLocalIpcError) else "rejected"
            return _response(accepted=False, code=code)
        finally:
            payload[:] = b"\0" * len(payload)
            payload.clear()


def import_setup_secret_over_socket(
    path: str | Path,
    *,
    hardware_id: str,
    pairing_id: str,
    setup_secret: str,
) -> dict[str, object]:
    request = json.dumps(
        {
            "schema": SCHEMA,
            "hardware_id": hardware_id,
            "pairing_id": pairing_id,
            "setup_secret": setup_secret,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    if len(request) > MAX_REQUEST_BYTES:
        raise PairingLocalIpcError("request_too_large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(Path(path).expanduser()))
        client.sendall(request)
        response = client.recv(MAX_REQUEST_BYTES + 1)
    document = json.loads(response.decode("utf-8"))
    if not isinstance(document, dict) or document.get("schema") != RESPONSE_SCHEMA:
        raise PairingLocalIpcError("response_invalid")
    return document
