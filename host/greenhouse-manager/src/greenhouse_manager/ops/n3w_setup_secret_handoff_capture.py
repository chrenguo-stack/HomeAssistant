"""Capture one N3-W setup-secret handoff without exposing secret material."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

PAIRING_PAYLOAD = re.compile(
    rb"GHN3W2:([A-Za-z0-9._-]+):([A-Za-z0-9._-]+):([A-Za-z0-9_-]+)"
)
MAX_CAPTURE_BYTES = 64 * 1024


class SerialPort(Protocol):
    def __enter__(self) -> SerialPort: ...

    def __exit__(self, *args: object) -> None: ...

    def read(self, size: int) -> bytes: ...


SerialFactory = Callable[..., SerialPort]


class CaptureError(RuntimeError):
    """A fail-closed capture error with a secret-safe public message."""


def _sha256(value: str | bytes) -> str:
    payload = value.encode("ascii") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def _decode_payload(
    raw: bytes,
    *,
    expected_hardware_id: str,
    expected_pairing_id_sha256: str,
) -> tuple[str, str, str]:
    match = PAIRING_PAYLOAD.search(raw)
    if match is None:
        raise CaptureError("PRIVATE_PAIRING_PAYLOAD_NOT_OBSERVED")

    hardware_id, pairing_id, setup_secret = (
        value.decode("ascii") for value in match.groups()
    )
    if hardware_id != expected_hardware_id:
        raise CaptureError("HARDWARE_ID_BINDING_MISMATCH")
    if _sha256(pairing_id) != expected_pairing_id_sha256:
        raise CaptureError("PAIRING_ID_BINDING_MISMATCH")
    if len(setup_secret) != 43:
        raise CaptureError("SETUP_SECRET_ENCODING_INVALID")
    try:
        decoded_secret = base64.urlsafe_b64decode(setup_secret + "=")
    except ValueError as error:
        raise CaptureError("SETUP_SECRET_ENCODING_INVALID") from error
    if len(decoded_secret) != 32:
        raise CaptureError("SETUP_SECRET_LENGTH_INVALID")
    return hardware_id, pairing_id, setup_secret


def _private_output_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise CaptureError("OUTPUT_PATH_MUST_BE_ABSOLUTE")
    if path.exists() or path.is_symlink():
        raise CaptureError("OUTPUT_ALREADY_EXISTS")
    parent = path.parent.resolve(strict=True)
    parent_stat = parent.stat()
    parent_mode = stat.S_IMODE(parent_stat.st_mode)
    if parent_mode & 0o077:
        raise CaptureError("OUTPUT_PARENT_NOT_PRIVATE")
    if parent_stat.st_uid != os.geteuid():
        raise CaptureError("OUTPUT_PARENT_OWNER_MISMATCH")
    return parent / path.name


def _capture_bytes(
    serial_factory: SerialFactory,
    *,
    port: str,
    baud: int,
    timeout_seconds: float,
) -> bytes:
    deadline = time.monotonic() + timeout_seconds
    buffer = bytearray()
    with serial_factory(port, baud, timeout=0.5) as device:
        while time.monotonic() < deadline:
            chunk = device.read(4096)
            if not chunk:
                continue
            buffer.extend(chunk)
            if len(buffer) > MAX_CAPTURE_BYTES:
                del buffer[:-MAX_CAPTURE_BYTES]
            if PAIRING_PAYLOAD.search(buffer):
                return bytes(buffer)
    raise CaptureError("PRIVATE_PAIRING_PAYLOAD_NOT_OBSERVED")


def _serialize_handoff(hardware_id: str, pairing_id: str, setup_secret: str) -> bytes:
    document = {
        "schema": "gh.pair.setup-secret-import/1",
        "hardware_id": hardware_id,
        "pairing_id": pairing_id,
        "setup_secret": setup_secret,
    }
    return json.dumps(document, separators=(",", ":")).encode("utf-8") + b"\n"


def _write_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture a board-bound N3-W Setup Secret into a private handoff file"
    )
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-hardware-id", required=True)
    parser.add_argument("--expected-pairing-id-sha256", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    return parser


def _default_serial_factory() -> SerialFactory:
    try:
        import serial
    except ImportError as error:
        raise CaptureError("PYSERIAL_DEPENDENCY_UNAVAILABLE") from error
    return serial.Serial


def main(
    argv: Sequence[str] | None = None,
    *,
    serial_factory: SerialFactory | None = None,
) -> int:
    args = _parser().parse_args(argv)
    try:
        if not re.fullmatch(r"[0-9a-f]{64}", args.expected_pairing_id_sha256):
            raise CaptureError("EXPECTED_PAIRING_ID_SHA256_INVALID")
        if args.timeout_seconds <= 0 or args.baud <= 0:
            raise CaptureError("SERIAL_PARAMETERS_INVALID")
        output = _private_output_path(args.output)
        captured = _capture_bytes(
            serial_factory or _default_serial_factory(),
            port=args.port,
            baud=args.baud,
            timeout_seconds=args.timeout_seconds,
        )
        hardware_id, pairing_id, setup_secret = _decode_payload(
            captured,
            expected_hardware_id=args.expected_hardware_id,
            expected_pairing_id_sha256=args.expected_pairing_id_sha256,
        )
        payload = _serialize_handoff(hardware_id, pairing_id, setup_secret)
        _write_exclusive(output, payload)
    except (CaptureError, FileExistsError, OSError) as error:
        message = str(error) if isinstance(error, CaptureError) else "PRIVATE_HANDOFF_WRITE_FAILED"
        print(f"CAPTURE_RESULT=FAIL:{message}")
        print("SECRET_VALUE_EXPOSED=false")
        return 1

    print("PRIVATE_PAIRING_PAYLOAD=CAPTURED")
    print(f"HARDWARE_ID_SHA256={_sha256(hardware_id)}")
    print(f"PAIRING_ID_SHA256={_sha256(pairing_id)}")
    print(f"SETUP_SECRET_LENGTH={len(setup_secret)}")
    print(f"PRIVATE_HANDOFF_SHA256={_sha256(payload)}")
    print("SECRET_VALUE_EXPOSED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
