#!/usr/bin/env python3
"""Source-only repair for Stage2D9R USB Serial/JTAG command delivery.

The module is inert on import and has no CLI that can enumerate USB, open a
serial device, or execute a physical request.  A future, separately authorized
wrapper must explicitly install the repaired write method on its capture
session class.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import time
from typing import Any, Callable

SOURCE_STATE = "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_EXECUTION_BINDING"
ROOT_CAUSE_CODE = "USB_SERIAL_JTAG_RX_BURST_OVERRUN_AFTER_NONBLOCKING_REPAIR"
USB_SERIAL_JTAG_DEFAULT_RX_BYTES = 256
FIRMWARE_READ_BYTES_PER_LOOP = 128
MIN_CA_PEM_BYTES = 256
MAX_COMMAND_LINE_BYTES = 8192
COMMAND_TERMINATOR_BYTES = 1
MAX_COMMAND_BYTES = MAX_COMMAND_LINE_BYTES + COMMAND_TERMINATOR_BYTES
PACED_CHUNK_BYTES = 64
INTER_CHUNK_DELAY_SECONDS = 0.100
PREPARE_SCHEMA = b"GH2D9R_PREPARE_V1 "
VERIFY_SCHEMA = b"GH2D9R_VERIFY_V1 "


class TransportRepairError(RuntimeError):
    """Stable fail-closed transport error."""


@dataclass(frozen=True)
class DeliveryEvidence:
    schema: str
    command_schema: str
    command_sha256: str
    command_bytes: int
    chunk_bytes: int
    chunk_count: int
    inter_chunk_delay_ms: int
    exact_write_confirmed: bool
    flush_count: int
    raw_command_included: bool
    transport_layer_authorizes_physical_operation: bool

    def public(self) -> dict[str, object]:
        return asdict(self)


def _command_schema(value: bytes) -> str:
    if value.startswith(PREPARE_SCHEMA):
        return "GH2D9R_PREPARE_V1"
    if value.startswith(VERIFY_SCHEMA):
        return "GH2D9R_VERIFY_V1"
    raise TransportRepairError("COMMAND_SCHEMA_UNSUPPORTED")


def validate_command(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise TransportRepairError("COMMAND_TYPE_INVALID")
    if not value or len(value) > MAX_COMMAND_BYTES:
        raise TransportRepairError("COMMAND_LENGTH_INVALID")
    if value.count(b"\n") != 1 or not value.endswith(b"\n"):
        raise TransportRepairError("COMMAND_FRAMING_INVALID")
    return _command_schema(value)


def write_command_paced(
    handle: Any,
    value: bytes,
    *,
    sleep: Callable[[float], None] = time.sleep,
    chunk_bytes: int = PACED_CHUNK_BYTES,
    inter_chunk_delay_seconds: float = INTER_CHUNK_DELAY_SECONDS,
) -> DeliveryEvidence:
    """Write one already-bound command exactly once in bounded paced chunks."""
    command_schema = validate_command(value)
    if (
        not isinstance(chunk_bytes, int)
        or chunk_bytes <= 0
        or chunk_bytes > PACED_CHUNK_BYTES
    ):
        raise TransportRepairError("CHUNK_SIZE_INVALID")
    if (
        not isinstance(inter_chunk_delay_seconds, (int, float))
        or inter_chunk_delay_seconds < INTER_CHUNK_DELAY_SECONDS
        or inter_chunk_delay_seconds > 1.0
    ):
        raise TransportRepairError("INTER_CHUNK_DELAY_INVALID")
    if handle is None or not callable(getattr(handle, "write", None)):
        raise TransportRepairError("SERIAL_HANDLE_INVALID")
    if not callable(getattr(handle, "flush", None)):
        raise TransportRepairError("SERIAL_FLUSH_UNAVAILABLE")

    chunks = [
        value[offset : offset + chunk_bytes]
        for offset in range(0, len(value), chunk_bytes)
    ]
    flush_count = 0
    for index, chunk in enumerate(chunks):
        written = handle.write(chunk)
        if not isinstance(written, int) or written != len(chunk):
            raise TransportRepairError("SERIAL_COMMAND_SHORT_WRITE")
        handle.flush()
        flush_count += 1
        if index + 1 < len(chunks):
            sleep(float(inter_chunk_delay_seconds))

    return DeliveryEvidence(
        schema="gh.h3.n2.stage2d9r-g3r-command-delivery-evidence/1",
        command_schema=command_schema,
        command_sha256=hashlib.sha256(value).hexdigest(),
        command_bytes=len(value),
        chunk_bytes=chunk_bytes,
        chunk_count=len(chunks),
        inter_chunk_delay_ms=int(inter_chunk_delay_seconds * 1000),
        exact_write_confirmed=True,
        flush_count=flush_count,
        raw_command_included=False,
        transport_layer_authorizes_physical_operation=False,
    )


def install_on_session_class(
    session_class: type[Any],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[..., Any]:
    """Install the repair explicitly and return the previous method.

    The future execution-binding layer owns this call and must persist
    ``_stage2d9r_transport_delivery_evidence`` after every command attempt.
    """
    original = getattr(session_class, "write", None)
    if not callable(original):
        raise TransportRepairError("SESSION_WRITE_METHOD_MISSING")
    if getattr(session_class, "_stage2d9r_paced_transport_v1", False):
        raise TransportRepairError("TRANSPORT_REPAIR_ALREADY_INSTALLED")

    def write(self: Any, value: bytes) -> None:
        handle = getattr(self, "_handle", None)
        if handle is None:
            raise TransportRepairError("SERIAL_CAPTURE_NOT_OPEN")
        evidence = write_command_paced(handle, value, sleep=sleep)
        setattr(
            self,
            "_stage2d9r_transport_delivery_evidence",
            evidence.public(),
        )

    session_class.write = write
    session_class._stage2d9r_paced_transport_v1 = True
    return original


def source_status() -> dict[str, object]:
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-prepare-transport-pacing-repair/1",
        "status": SOURCE_STATE,
        "root_cause_code": ROOT_CAUSE_CODE,
        "usb_serial_jtag_default_rx_bytes": USB_SERIAL_JTAG_DEFAULT_RX_BYTES,
        "firmware_read_bytes_per_loop": FIRMWARE_READ_BYTES_PER_LOOP,
        "paced_chunk_bytes": PACED_CHUNK_BYTES,
        "inter_chunk_delay_ms": int(INTER_CHUNK_DELAY_SECONDS * 1000),
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
    }


def main() -> int:
    print(json.dumps(source_status(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
