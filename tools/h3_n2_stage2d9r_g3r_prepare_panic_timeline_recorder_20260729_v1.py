#!/usr/bin/env python3
"""Realtime serial timeline and normalized reset/panic evidence for Stage2D9R.

Source-only helper. It does not enumerate USB, open a board, authorize, or execute a
physical request by itself. A future exact D2 wrapper supplies the serial factory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Any, Callable, Iterable

import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1 as legacy
import h3_n2_stage2d9r_serial_handshake_repair_20260727_v1 as serial_repair

SOURCE_STATE = "SOURCE_ONLY_REALTIME_PANIC_TIMELINE_REQUIRES_NEW_EXACT_D2_PACKAGE"
POLICY_VERSION = 2
REALTIME_SERIAL_FILE = "prepare-serial.realtime.redacted.jsonl"
RESET_SIGNATURE_FILE = "prepare-reset-signatures.json"
REALTIME_TIMELINE_FILE = "prepare-timeline.realtime.json"
MANIFEST_FILE = "prepare-panic-evidence-manifest.json"

_RESET_START_RE = re.compile(r"(?:^|\s)(?:ESP-ROM:|rst:|Guru Meditation Error:|panic(?:'ed)?)", re.I)
_RESET_REASON_RE = re.compile(r"\brst:\s*([^,\r\n]+(?:\([^)]*\))?)", re.I)
_PANIC_CLASS_RE = re.compile(r"(?:Guru Meditation Error:\s*|panic(?:'ed)?\s*[:=]?\s*)([^\r\n]+)", re.I)
_CORE_RE = re.compile(r"\bCore\s+(\d+)\b", re.I)
_ADDRESS_PATTERNS = {
    "mepc": re.compile(r"\bMEPC\s*[:=]\s*(0x[0-9a-fA-F]+)", re.I),
    "ra": re.compile(r"(?:^|\s)RA\s*[:=]\s*(0x[0-9a-fA-F]+)", re.I),
    "saved_pc": re.compile(r"\bSaved PC\s*[:=]\s*(0x[0-9a-fA-F]+)", re.I),
}
_BACKTRACE_RE = re.compile(r"\b(?:Backtrace|Stack memory)\b", re.I)
_REBOOT_RE = re.compile(r"\bRebooting\.\.\.", re.I)
_SAFE_MARKERS = {
    "stage2d9r_command_ready=PREPARE",
    "stage2d9r_command_ready=VERIFY",
    "stage2d9r_prepare=pass",
    "stage2d9r_verify=pass",
    "stage2d9r_executor=fail",
}
_POST_COMMAND_PHASES = {"post_command", "late_window", "result"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


@dataclass(frozen=True)
class TimedLine:
    at: str
    monotonic_ns: int
    phase: str
    redacted: str
    event: dict[str, Any]

    def public_event(self) -> dict[str, Any]:
        value = dict(self.event)
        value["monotonic_ns"] = self.monotonic_ns
        return value


@dataclass
class RealtimeSerialCaptureSession:
    device: str
    baud: int
    serial_factory: Callable[..., Any]
    _handle: Any | None = field(default=None, init=False)
    _buffer: bytearray = field(default_factory=bytearray, init=False)
    _pending: bytearray = field(default_factory=bytearray, init=False)
    _lines: list[TimedLine] = field(default_factory=list, init=False)
    _phase_markers: list[dict[str, Any]] = field(default_factory=list, init=False)
    _phase: str = field(default="startup", init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _stop: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _reader_error: str | None = field(default=None, init=False)
    _last_at: str | None = field(default=None, init=False)
    _last_monotonic_ns: int | None = field(default=None, init=False)

    def open(self) -> None:
        if self._handle is not None:
            raise serial_repair.HandshakeRepairError("SERIAL_CAPTURE_ALREADY_OPEN")
        self._handle = self.serial_factory(
            self.device,
            self.baud,
            timeout=0.1,
            write_timeout=2,
        )
        self._thread = threading.Thread(
            target=self._reader,
            name="stage2d9r-realtime-panic-capture",
            daemon=True,
        )
        self._thread.start()

    def mark_phase(self, phase: str) -> dict[str, Any]:
        at = utc_now()
        monotonic_ns = time.monotonic_ns()
        with self._lock:
            self._phase = phase
            marker = {"at": at, "monotonic_ns": monotonic_ns, "kind": "CAPTURE_PHASE", "phase": phase}
            self._phase_markers.append(marker)
        return marker

    def _reader(self) -> None:
        assert self._handle is not None
        while not self._stop.is_set():
            try:
                chunk = self._handle.read(4096)
            except Exception as exc:  # pragma: no cover - device-specific detail
                self._reader_error = type(exc).__name__
                return
            if chunk:
                self.ingest(chunk)

    def ingest(
        self,
        chunk: bytes,
        *,
        at: str | None = None,
        monotonic_ns: int | None = None,
        phase: str | None = None,
    ) -> None:
        """Record bytes at receipt time. `phase` exists for deterministic tests."""
        if not isinstance(chunk, (bytes, bytearray)):
            raise TypeError("SERIAL_CHUNK_TYPE_INVALID")
        observed_at = at or utc_now()
        observed_monotonic = monotonic_ns if monotonic_ns is not None else time.monotonic_ns()
        with self._lock:
            if phase is not None:
                self._phase = phase
            active_phase = self._phase
            self._buffer.extend(chunk)
            self._pending.extend(chunk)
            self._last_at = observed_at
            self._last_monotonic_ns = observed_monotonic
            while True:
                newline = self._pending.find(b"\n")
                if newline < 0:
                    break
                raw = bytes(self._pending[: newline + 1])
                del self._pending[: newline + 1]
                self._append_line(raw, observed_at, observed_monotonic, active_phase)

    def _append_line(self, raw: bytes, at: str, monotonic_ns: int, phase: str) -> None:
        text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        redacted = legacy.redact_text(text)
        event = legacy.serial_event(text, at=at, phase=phase)
        self._lines.append(TimedLine(at, monotonic_ns, phase, redacted, event))

    def _flush_partial(self) -> None:
        with self._lock:
            if not self._pending:
                return
            raw = bytes(self._pending)
            self._pending.clear()
            self._append_line(
                raw,
                self._last_at or utc_now(),
                self._last_monotonic_ns if self._last_monotonic_ns is not None else time.monotonic_ns(),
                self._phase,
            )

    def snapshot(self) -> bytes:
        with self._lock:
            return bytes(self._buffer)

    def line_events(self) -> list[dict[str, Any]]:
        self._flush_partial()
        with self._lock:
            return [line.public_event() for line in self._lines]

    def phase_markers(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(value) for value in self._phase_markers]

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
                raise serial_repair.HandshakeRepairError(
                    f"SERIAL_CAPTURE_READER_FAILED:{self._reader_error}"
                )
            time.sleep(0.01)
        return None, self.snapshot()

    def write(self, value: bytes) -> None:
        if self._handle is None:
            raise serial_repair.HandshakeRepairError("SERIAL_CAPTURE_NOT_OPEN")
        self._handle.write(value)
        self._handle.flush()

    def persist_redacted(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write(path, serial_repair.redact_transcript(self.snapshot()))

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._flush_partial()
        if self._handle is not None:
            self._handle.close()
        self._handle = None
        self._thread = None

    def reset_signatures(self) -> list[dict[str, Any]]:
        self._flush_partial()
        with self._lock:
            lines = list(self._lines)
        cycles: list[list[TimedLine]] = []
        active: list[TimedLine] = []
        for line in lines:
            text = line.redacted
            starts = _RESET_START_RE.search(text) is not None
            if starts and active and any(_REBOOT_RE.search(item.redacted) for item in active):
                cycles.append(active)
                active = []
            if starts and not active:
                active = [line]
            elif active:
                active.append(line)
            if active and _REBOOT_RE.search(text):
                cycles.append(active)
                active = []
        if active:
            cycles.append(active)

        signatures: list[dict[str, Any]] = []
        for index, cycle in enumerate(cycles, start=1):
            text = "\n".join(item.redacted for item in cycle)
            reset_reason_match = _RESET_REASON_RE.search(text)
            panic_match = _PANIC_CLASS_RE.search(text)
            core_match = _CORE_RE.search(text)
            addresses: dict[str, str | None] = {}
            for key, pattern in _ADDRESS_PATTERNS.items():
                match = pattern.search(text)
                addresses[key] = match.group(1).lower() if match else None
            backtrace_hashes = [
                legacy.sha256_text(item.redacted)
                for item in cycle
                if _BACKTRACE_RE.search(item.redacted)
            ]
            phases = [item.phase for item in cycle]
            normalized = {
                "reset_reason": reset_reason_match.group(1).strip() if reset_reason_match else None,
                "panic_class": panic_match.group(1).strip() if panic_match else None,
                "core": int(core_match.group(1)) if core_match else None,
                **addresses,
                "backtrace_or_stack_sha256": backtrace_hashes,
                "reboot_marker_observed": any(_REBOOT_RE.search(item.redacted) for item in cycle),
            }
            signatures.append({
                "cycle_index": index,
                "first_at": cycle[0].at,
                "last_at": cycle[-1].at,
                "first_monotonic_ns": cycle[0].monotonic_ns,
                "last_monotonic_ns": cycle[-1].monotonic_ns,
                "first_phase": cycle[0].phase,
                "last_phase": cycle[-1].phase,
                "post_command": any(phase in _POST_COMMAND_PHASES for phase in phases),
                "line_count": len(cycle),
                **normalized,
                "signature_sha256": canonical_sha256(normalized),
            })
        return signatures

    def unrecognized_result_after_command(self) -> bool:
        self._flush_partial()
        with self._lock:
            lines = list(self._lines)
        for line in lines:
            if line.phase not in _POST_COMMAND_PHASES:
                continue
            marker = line.event.get("marker")
            if isinstance(marker, str) and marker.startswith("stage2d9r_") and marker not in _SAFE_MARKERS:
                return True
        return False

    def persist_evidence(
        self,
        root: Path,
        *,
        controller_timeline: list[dict[str, Any]],
        classification: str,
        terminal: bool,
    ) -> dict[str, Any]:
        lines = self.line_events()
        signatures = self.reset_signatures()
        serial_bytes = b"".join(canonical_bytes(value) + b"\n" for value in lines)
        signatures_value = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-reset-signatures/1",
            "policy_version": POLICY_VERSION,
            "reset_loop_count": len(signatures),
            "first_reset_at": signatures[0]["first_at"] if signatures else None,
            "last_reset_at": signatures[-1]["last_at"] if signatures else None,
            "signatures": signatures,
        }
        signatures_bytes = canonical_bytes(signatures_value) + b"\n"
        timeline_value = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-realtime-timeline/1",
            "policy_version": POLICY_VERSION,
            "classification": classification,
            "terminal": terminal,
            "phase_markers": self.phase_markers(),
            "controller_events": controller_timeline,
            "reset_cycle_count": len(signatures),
        }
        timeline_bytes = canonical_bytes(timeline_value) + b"\n"
        atomic_write(root / REALTIME_SERIAL_FILE, serial_bytes)
        atomic_write(root / RESET_SIGNATURE_FILE, signatures_bytes)
        atomic_write(root / REALTIME_TIMELINE_FILE, timeline_bytes)
        manifest = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-panic-evidence-manifest/1",
            "policy_version": POLICY_VERSION,
            "classification": classification,
            "terminal": terminal,
            "realtime_serial_sha256": sha256_bytes(serial_bytes),
            "reset_signatures_sha256": sha256_bytes(signatures_bytes),
            "realtime_timeline_sha256": sha256_bytes(timeline_bytes),
            "reset_loop_count": len(signatures),
            "post_command_reset_count": sum(1 for value in signatures if value["post_command"]),
            "first_reset_at": signatures[0]["first_at"] if signatures else None,
            "last_reset_at": signatures[-1]["last_at"] if signatures else None,
            "raw_private_values_included": False,
            "real_board_evidence_in_public_artifact": False,
        }
        manifest_bytes = canonical_bytes(manifest) + b"\n"
        atomic_write(root / MANIFEST_FILE, manifest_bytes)
        manifest["manifest_file_sha256"] = sha256_bytes(manifest_bytes)
        return manifest


def main() -> int:
    print(json.dumps({
        "status": SOURCE_STATE,
        "policy_version": POLICY_VERSION,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "flash_operation": False,
        "network_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
