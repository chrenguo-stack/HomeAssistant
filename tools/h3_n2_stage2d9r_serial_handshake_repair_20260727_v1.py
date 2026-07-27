#!/usr/bin/env python3
"""Source-only Stage2D9R serial handshake repair helpers.

This module does not authorize or start a physical execution. It supplies the
reviewable host-side mechanism that a future exact D2 package must bind:

* establish a continuous serial capture before the isolated Broker starts;
* retain a redacted transcript on every timeout or terminal result;
* separate PREPARE/VERIFY ready and result timeout codes;
* preserve the existing one-shot authorization and executor boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Iterable

SOURCE_STATE = "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_PACKAGE"
READY_TIMEOUT_CODES = {
    b"stage2d9r_command_ready=PREPARE": "PREPARE_READY_MARKER_TIMEOUT",
    b"stage2d9r_command_ready=VERIFY": "VERIFY_READY_MARKER_TIMEOUT",
}
RESULT_TIMEOUT_CODES = {
    b"stage2d9r_command_ready=PREPARE": "PREPARE_RESULT_TIMEOUT",
    b"stage2d9r_command_ready=VERIFY": "VERIFY_RESULT_TIMEOUT",
}
RESULT_MARKERS = {
    b"stage2d9r_command_ready=PREPARE": b"stage2d9r_prepare=pass",
    b"stage2d9r_command_ready=VERIFY": b"stage2d9r_verify=pass",
}
DEVICE_FAILURE_MARKER = b"stage2d9r_executor=fail"
# Only redact an executable command line that starts with the command schema.
# Diagnostic lines such as `expected_schema=GH2D9R_PREPARE_V1` remain visible.
_COMMAND_LINE = re.compile(
    rb"(?m)^[ \t]*(?:GH2D9R_PREPARE_V1|GH2D9R_VERIFY_V1)[^\r\n]*(?:\r?\n|$)"
)


class HandshakeRepairError(RuntimeError):
    pass


def redact_transcript(raw: bytes) -> bytes:
    """Remove executable command material while preserving boot diagnostics."""

    def replacement(match: re.Match[bytes]) -> bytes:
        line = match.group(0)
        schema = (
            b"GH2D9R_PREPARE_V1"
            if b"GH2D9R_PREPARE_V1" in line
            else b"GH2D9R_VERIFY_V1"
        )
        newline = b"\n" if line.endswith(b"\n") else b""
        return schema + b" [REDACTED_COMMAND_MATERIAL]" + newline

    return _COMMAND_LINE.sub(replacement, raw)


class SerialCaptureSession:
    """Continuously captures a single serial device into an in-memory transcript."""

    def __init__(
        self,
        device: str,
        baud: int,
        *,
        serial_factory: Callable[..., Any],
    ) -> None:
        self.device = device
        self.baud = baud
        self._serial_factory = serial_factory
        self._handle: Any | None = None
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._reader_error: str | None = None

    def open(self) -> None:
        if self._handle is not None:
            raise HandshakeRepairError("SERIAL_CAPTURE_ALREADY_OPEN")
        self._handle = self._serial_factory(
            self.device,
            self.baud,
            timeout=0.1,
            write_timeout=2,
        )
        self._thread = threading.Thread(
            target=self._reader,
            name="stage2d9r-serial-capture",
            daemon=True,
        )
        self._thread.start()

    def _reader(self) -> None:
        assert self._handle is not None
        while not self._stop.is_set():
            try:
                chunk = self._handle.read(4096)
            except Exception as exc:  # pragma: no cover - device-specific detail
                self._reader_error = type(exc).__name__
                return
            if chunk:
                with self._lock:
                    self._buffer.extend(chunk)

    def snapshot(self) -> bytes:
        with self._lock:
            return bytes(self._buffer)

    def wait_for_any(
        self,
        markers: Iterable[bytes],
        timeout: float,
    ) -> tuple[bytes | None, bytes]:
        expected = tuple(markers)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            captured = self.snapshot()
            for marker in expected:
                if marker in captured:
                    return marker, captured
            if self._reader_error is not None:
                raise HandshakeRepairError(
                    f"SERIAL_CAPTURE_READER_FAILED:{self._reader_error}"
                )
            time.sleep(0.01)
        return None, self.snapshot()

    def write(self, value: bytes) -> None:
        if self._handle is None:
            raise HandshakeRepairError("SERIAL_CAPTURE_NOT_OPEN")
        self._handle.write(value)
        self._handle.flush()

    def persist_redacted(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(redact_transcript(self.snapshot()))
        path.chmod(0o600)

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._handle is not None:
            self._handle.close()
        self._handle = None
        self._thread = None


@dataclass
class RepairedHandshakeController:
    """Installs the repaired serial/Broker ordering around a frozen executor."""

    module: Any
    serial_factory: Callable[..., Any]

    def __post_init__(self) -> None:
        self.selected: Any | None = None
        self.session: SerialCaptureSession | None = None
        self._select_serial = self.module.select_serial
        self._start_broker = self.module.start_broker
        self._stop_broker = self.module.stop_broker

    def install(self) -> None:
        self.module.select_serial = self.select_serial
        self.module.start_broker = self.start_broker
        self.module.stop_broker = self.stop_broker
        self.module.wait_serial_line = self.wait_serial_line

    def select_serial(self, authorization: dict[str, Any]) -> Any:
        selected = self._select_serial(authorization)
        self.selected = selected
        return selected

    def _open_session(self, *, replace: bool) -> None:
        if self.selected is None:
            raise self.module.ExecutionError("SERIAL_SELECTION_NOT_AVAILABLE")
        if self.session is not None:
            if not replace:
                return
            self.session.close()
        self.session = SerialCaptureSession(
            self.selected.device,
            self.module.SERIAL_BAUD,
            serial_factory=self.serial_factory,
        )
        self.session.open()

    def start_broker(self, mosquitto_path: Path, private_root: Path, log_path: Path):
        # This ordering is the core repair: capture is live before Broker startup.
        self._open_session(replace=True)
        return self._start_broker(mosquitto_path, private_root, log_path)

    def stop_broker(self, process: Any | None) -> None:
        try:
            self._stop_broker(process)
        finally:
            if self.session is not None:
                self.session.close()
                self.session = None

    def wait_serial_line(
        self,
        device: str,
        expected: bytes,
        timeout: float,
        command: bytes | None,
        log_path: Path,
    ) -> bytes:
        if expected not in READY_TIMEOUT_CODES:
            raise self.module.ExecutionError("SERIAL_EXPECTED_MARKER_UNSUPPORTED")

        # PREPARE uses the capture opened before Broker startup. After the device
        # restarts, VERIFY gets a fresh capture bound to the re-selected device.
        if expected.endswith(b"VERIFY"):
            self._open_session(replace=True)
        elif self.session is None:
            self._open_session(replace=False)
        assert self.session is not None
        if self.session.device != device:
            raise self.module.ExecutionError("SERIAL_CAPTURE_DEVICE_MISMATCH")

        try:
            marker, captured = self.session.wait_for_any(
                (expected, DEVICE_FAILURE_MARKER), timeout
            )
            if marker == DEVICE_FAILURE_MARKER:
                raise self.module.ExecutionError("DEVICE_EXECUTOR_FAILED")
            if marker is None:
                raise self.module.ExecutionError(READY_TIMEOUT_CODES[expected])
            if command is None:
                return captured

            self.session.write(command)
            result_marker = RESULT_MARKERS[expected]
            marker, captured = self.session.wait_for_any(
                (result_marker, DEVICE_FAILURE_MARKER),
                self.module.SERIAL_PASS_TIMEOUT_S,
            )
            if marker == DEVICE_FAILURE_MARKER:
                raise self.module.ExecutionError("DEVICE_EXECUTOR_FAILED")
            if marker is None:
                raise self.module.ExecutionError(RESULT_TIMEOUT_CODES[expected])
            return captured
        finally:
            # Evidence is retained even when the ready/result wait times out.
            self.session.persist_redacted(log_path)


def install_repaired_handshake(
    module: Any,
    *,
    serial_factory: Callable[..., Any] | None = None,
) -> RepairedHandshakeController:
    if serial_factory is None:
        try:
            import serial  # type: ignore
        except ImportError as exc:  # pragma: no cover - host dependency
            raise HandshakeRepairError("PYSERIAL_UNAVAILABLE") from exc
        serial_factory = serial.Serial
    controller = RepairedHandshakeController(module, serial_factory)
    controller.install()
    return controller


def main() -> int:
    import json

    print(
        json.dumps(
            {
                "status": SOURCE_STATE,
                "authorization_created": False,
                "authorization_claimed": False,
                "authorization_consumed": False,
                "board_operation": False,
                "serial_operation": False,
                "flash_operation": False,
                "network_operation": False,
                "broker_started": False,
                "prepare_executed": False,
                "verify_executed": False,
                "replay_permitted": False,
                "automatic_retry_permitted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
