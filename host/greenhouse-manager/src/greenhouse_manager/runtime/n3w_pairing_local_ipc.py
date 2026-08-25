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
REPAIR_SCHEMA = "gh.pair.repair-authorize/1"
REPAIR_RESPONSE_SCHEMA = "gh.pair.repair-authorize-result/1"
MAX_REQUEST_BYTES = 4096
MAX_RESPONSE_BYTES = 4096
SOCKET_TIMEOUT_S = 2.0


class SetupSecretImporter(Protocol):
    def import_setup_secret(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        setup_secret: bytes,
    ) -> None: ...

    def authorize_repair(
        self,
        hardware_id: str,
        pairing_id: str,
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


def _response(
    *,
    accepted: bool,
    code: str,
    schema: str = RESPONSE_SCHEMA,
) -> bytes:
    return (
        json.dumps(
            {
                "accepted": accepted,
                "code": code,
                "schema": schema,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )



def _wipe_buffer(value: bytearray) -> None:
    if value:
        value[:] = b"\0" * len(value)
        value.clear()


def _read_frame(
    connection: socket.socket,
    *,
    max_bytes: int,
    timeout_code: str,
    too_large_code: str,
    invalid_code: str,
) -> bytearray:
    """Read exactly one bounded newline-or-EOF frame.

    A newline identifies the logical end of the frame, but the reader
    continues through EOF so a second frame cannot hide in a later stream
    segment. Only whitespace is permitted after the first newline.
    """

    payload = bytearray()
    frame_end: int | None = None

    try:
        while len(payload) <= max_bytes:
            try:
                block = connection.recv(
                    min(
                        1024,
                        max_bytes + 1 - len(payload),
                    )
                )
            except TimeoutError as error:
                raise PairingLocalIpcError(
                    timeout_code
                ) from error
            except OSError as error:
                raise PairingLocalIpcError(
                    invalid_code
                ) from error

            if not block:
                break

            payload.extend(block)

            if len(payload) > max_bytes:
                raise PairingLocalIpcError(
                    too_large_code
                )

            if frame_end is None:
                newline = payload.find(b"\n")

                if newline >= 0:
                    frame_end = newline

            if frame_end is not None:
                trailing = payload[
                    frame_end + 1:
                ]

                if bytes(trailing).strip():
                    raise PairingLocalIpcError(
                        invalid_code
                    )

        if len(payload) > max_bytes:
            raise PairingLocalIpcError(
                too_large_code
            )

        if not payload:
            raise PairingLocalIpcError(
                invalid_code
            )

        if frame_end is not None:
            del payload[frame_end:]

        if not payload:
            raise PairingLocalIpcError(
                invalid_code
            )

        return payload

    except Exception:
        _wipe_buffer(payload)
        raise

def _decode_response(
    payload: bytearray,
    *,
    response_schema: str,
) -> dict[str, object]:
    try:
        document = json.loads(
            bytes(payload).decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise PairingLocalIpcError(
            "response_invalid"
        ) from error

    if (
        not isinstance(document, dict)
        or set(document)
        != {
            "accepted",
            "code",
            "schema",
        }
        or document.get("schema")
        != response_schema
        or not isinstance(
            document.get("accepted"),
            bool,
        )
        or not isinstance(
            document.get("code"),
            str,
        )
        or not document["code"]
    ):
        raise PairingLocalIpcError(
            "response_invalid"
        )

    return document


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
        response_schema = RESPONSE_SCHEMA
        try:
            payload = _read_frame(
                connection,
                max_bytes=MAX_REQUEST_BYTES,
                timeout_code="request_timeout",
                too_large_code="request_too_large",
                invalid_code="request_frame_invalid",
            )

            try:
                document = json.loads(
                    bytes(payload).decode("utf-8")
                )
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
            ) as error:
                raise PairingLocalIpcError(
                    "request_json_invalid"
                ) from error

            if not isinstance(document, dict):
                raise PairingLocalIpcError("request_fields_invalid")

            schema = document.get("schema")

            if schema == REPAIR_SCHEMA:
                response_schema = REPAIR_RESPONSE_SCHEMA

            if schema == SCHEMA:
                if set(document) != {
                    "schema",
                    "hardware_id",
                    "pairing_id",
                    "setup_secret",
                }:
                    raise PairingLocalIpcError("request_fields_invalid")
                hardware_id = document["hardware_id"]
                pairing_id = document["pairing_id"]
                if (
                    not isinstance(hardware_id, str)
                    or not isinstance(pairing_id, str)
                ):
                    raise PairingLocalIpcError(
                        "request_identity_invalid"
                    )
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
                return _response(
                    accepted=True,
                    code="accepted",
                )

            if schema == REPAIR_SCHEMA:
                if set(document) != {
                    "schema",
                    "hardware_id",
                    "pairing_id",
                }:
                    raise PairingLocalIpcError(
                        "request_fields_invalid"
                    )
                hardware_id = document["hardware_id"]
                pairing_id = document["pairing_id"]
                if (
                    not isinstance(hardware_id, str)
                    or not isinstance(pairing_id, str)
                ):
                    raise PairingLocalIpcError(
                        "request_identity_invalid"
                    )
                self.coordinator.authorize_repair(
                    hardware_id,
                    pairing_id,
                )
                return _response(
                    accepted=True,
                    code="repair_authorized",
                    schema=REPAIR_RESPONSE_SCHEMA,
                )

            raise PairingLocalIpcError("request_schema_invalid")
        except Exception as error:
            code = (
                str(error)
                if isinstance(
                    error,
                    PairingLocalIpcError,
                )
                else "rejected"
            )
            return _response(
                accepted=False,
                code=code,
                schema=response_schema,
            )
        finally:
            _wipe_buffer(payload)


def _request_over_socket(
    path: str | Path,
    document: dict[str, object],
    *,
    response_schema: str,
    timeout_s: float = SOCKET_TIMEOUT_S,
) -> dict[str, object]:
    if timeout_s <= 0:
        raise PairingLocalIpcError(
            "socket_timeout_invalid"
        )

    request = bytearray(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )

    response = bytearray()

    try:
        if len(request) > MAX_REQUEST_BYTES:
            raise PairingLocalIpcError(
                "request_too_large"
            )

        with socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        ) as client:
            client.settimeout(timeout_s)

            try:
                client.connect(
                    str(Path(path).expanduser())
                )
                client.sendall(
                    bytes(request)
                )
                client.shutdown(
                    socket.SHUT_WR
                )
            except TimeoutError as error:
                raise PairingLocalIpcError(
                    "ipc_timeout"
                ) from error
            except OSError as error:
                raise PairingLocalIpcError(
                    "ipc_unavailable"
                ) from error

            response = _read_frame(
                client,
                max_bytes=MAX_RESPONSE_BYTES,
                timeout_code="response_timeout",
                too_large_code="response_too_large",
                invalid_code="response_frame_invalid",
            )

        return _decode_response(
            response,
            response_schema=response_schema,
        )

    finally:
        _wipe_buffer(request)
        _wipe_buffer(response)

def import_setup_secret_over_socket(
    path: str | Path,
    *,
    hardware_id: str,
    pairing_id: str,
    setup_secret: str,
) -> dict[str, object]:
    return _request_over_socket(
        path,
        {
            "schema": SCHEMA,
            "hardware_id": hardware_id,
            "pairing_id": pairing_id,
            "setup_secret": setup_secret,
        },
        response_schema=RESPONSE_SCHEMA,
    )


def authorize_repair_over_socket(
    path: str | Path,
    *,
    hardware_id: str,
    pairing_id: str,
) -> dict[str, object]:
    return _request_over_socket(
        path,
        {
            "schema": REPAIR_SCHEMA,
            "hardware_id": hardware_id,
            "pairing_id": pairing_id,
        },
        response_schema=REPAIR_RESPONSE_SCHEMA,
    )
