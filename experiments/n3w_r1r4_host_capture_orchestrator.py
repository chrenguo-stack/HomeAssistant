#!/usr/bin/env python3
"""Host-only R1R4 dual-console capture state machine.

The serial dependency is lazy: simulation/replay mode uses no serial package,
while explicit live mode uses the bounded :class:`SerialBackend`. Collector
readiness is an explicit reader/binding event, not the existence of a log file
or a live process. Device lifecycle gates are observed evidence of experiment
start, never the pre-start barrier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Literal

Role = Literal["CONTROL", "DUT"]
ROLES: tuple[Role, Role] = ("CONTROL", "DUT")
LIVE_CAPTURE_DURATION_S = 60.0


@dataclass(frozen=True)
class RoleBinding:
    role: Role
    device_id: str


REAL_SUMMARY_FIELDS: dict[Role, tuple[str, ...]] = {
    "CONTROL": (
        "baseline",
        "probe_tx_api",
        "switch_tx_api",
        "switch_tx_request_op_id",
        "switch_tx_driver_op_id",
        "switch_tx_completion",
        "switch_tx_status",
        "control_home_channel_api",
        "control_home_channel",
        "control_ap_sta_link",
        "control_home_return",
        "home_ack_api",
        "home_ack_send_callback",
        "home_ack_received",
        "home_ack",
    ),
    "DUT": (
        "baseline",
        "roc_req",
        "roc_request_input_op_id",
        "roc_driver_op_id",
        "roc_natural_complete",
        "roc_cancel_api",
        "roc_cancel_complete",
        "roc_termination_observed",
        "roc_termination_wait",
        "roc_active",
        "roc_completion_status",
        "probe_rx",
        "home_recovery",
        "home_channel_api",
        "home_channel",
        "home_sta_link",
        "home_ack_tx",
        "home_ack_api",
        "home_ack_send_callback",
        "home_ack_received",
        "disconnect_count",
    ),
}
_TOKEN_RE = re.compile(r"([A-Za-z0-9_]+)=([^\s,]+)")
_BOOT_MARKERS = ("ESP-ROM:", "rst:0x", "boot:0x", "cpu_start: Starting scheduler", "app_init()")


@dataclass
class OperationEventTracker:
    """Host-side model for the bounded async operation evidence contract."""

    kind: str
    expected_op_id: int
    queue_overflow: bool = False
    ignored_events: int = 0
    tx_done: bool = False
    tx_duration_complete: bool = False
    tx_failed: bool = False
    tx_cancelled: bool = False
    roc_natural_complete: bool = False
    roc_cancel_complete: bool = False
    terminal_status: str = "UNKNOWN"

    def observe(self, kind: str, op_id: int, status: str) -> bool:
        if self.queue_overflow or kind != self.kind or op_id != self.expected_op_id:
            self.ignored_events += 1
            return False
        if kind == "ACTION_TX":
            if status == "TX_DONE":
                self.tx_done = True
            elif status == "TX_DURATION_COMPLETED":
                self.tx_duration_complete = True
                self.terminal_status = status
            elif status == "TX_FAILED":
                self.tx_failed = True
                self.terminal_status = status
            elif status == "TX_OP_CANCELLED":
                self.tx_cancelled = True
                self.terminal_status = status
            return True
        if kind == "ROC_DONE":
            self.terminal_status = status
            if status == "WIFI_ROC_DONE":
                self.roc_natural_complete = True
            elif status == "WIFI_ROC_FAIL":
                self.roc_cancel_complete = True
            return True
        self.ignored_events += 1
        return False

    def completion_pass(self) -> bool:
        if self.queue_overflow:
            return False
        if self.kind == "ACTION_TX":
            return self.tx_duration_complete and not self.tx_failed and not self.tx_cancelled
        if self.kind == "ROC_DONE":
            return self.roc_natural_complete or self.roc_cancel_complete
        return False


def operation_summary_consistent(role: Role, fields: dict[str, str]) -> bool:
    """Reject summaries that claim async success without its required evidence."""
    if role == "CONTROL":
        if fields.get("switch_tx_completion") == "PASS":
            if fields.get("switch_tx_status") != "TX_DURATION_COMPLETED":
                return False
            if fields.get("switch_tx_api") != "PASS":
                return False
        if fields.get("control_home_return") == "PASS":
            if fields.get("control_home_channel_api") != "PASS":
                return False
            if fields.get("control_home_channel") != "1":
                return False
            if fields.get("control_ap_sta_link") != "true":
                return False
        return True
    if fields.get("roc_cancel_complete") == "PASS":
        if fields.get("roc_cancel_api") != "PASS":
            return False
        if fields.get("roc_completion_status") != "WIFI_ROC_FAIL":
            return False
        if fields.get("roc_natural_complete") == "true":
            return False
    if fields.get("roc_req") == "PASS":
        termination_ok = (
            fields.get("roc_termination_observed") == "true"
            and fields.get("roc_termination_wait") == "PASS"
            and fields.get("roc_active") == "false"
        )
        if not termination_ok:
            if fields.get("roc_active") != "true":
                return False
            if fields.get("home_recovery") != "NOT_EXECUTED":
                return False
            if fields.get("home_ack_tx") != "NOT_EXECUTED":
                return False
    if fields.get("roc_termination_wait") == "PASS" and fields.get("roc_active") != "false":
        return False
    if fields.get("home_ack_tx") == "PASS" and fields.get("home_recovery") != "PASS":
        return False
    return True


@dataclass(frozen=True)
class HostEvent:
    kind: str
    role: Role | None
    monotonic_ns: int
    wall_time: str
    details: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "role": self.role,
            "monotonic_ns": self.monotonic_ns,
            "wall_time": self.wall_time,
            "details": self.details,
        }


@dataclass
class RoleState:
    binding: RoleBinding
    raw_path: Path
    events_path: Path
    raw_bytes: int = 0
    data_seen: bool = False
    reader_ready: bool = False
    connected: bool = False
    identity_valid: bool = False
    heartbeat_seen: bool = False
    lifecycle_gate_seen: bool = False
    summary_seen: bool = False
    summary_fields: dict[str, str] = field(default_factory=dict)
    evidence_order: list[str] = field(default_factory=list)
    role_mismatch: bool = False
    disconnected: bool = False
    reconnect_count: int = 0
    boot_marker_count: int = 0
    device_reboot_detected: bool = False
    capture_interrupted: bool = False
    line_buffer: bytes = b""


class DualCapture:
    """Bounded, host-timestamped capture for one CONTROL and one DUT."""

    def __init__(
        self,
        output_dir: Path,
        bindings: Iterable[RoleBinding],
        *,
        heartbeat_timeout_s: float = 8.0,
        summary_timeout_s: float = 45.0,
        clock_ns: Callable[[], int] | None = None,
        wall_clock: Callable[[], datetime] | None = None,
    ) -> None:
        binding_map = {binding.role: binding for binding in bindings}
        if set(binding_map) != set(ROLES):
            raise ValueError("exactly one CONTROL and one DUT binding are required")
        if any(not binding.device_id for binding in binding_map.values()):
            raise ValueError("device bindings must be non-empty")
        if len({binding.device_id for binding in binding_map.values()}) != len(ROLES):
            raise ValueError("CONTROL and DUT device bindings must be unique")
        self.output_dir = output_dir
        if output_dir.exists() and any(output_dir.iterdir()):
            raise ValueError(f"output directory must be new and empty: {output_dir}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.summary_timeout_s = summary_timeout_s
        self._clock_ns = clock_ns or time.monotonic_ns
        self._wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self._event_lock = threading.RLock()
        self.events: list[HostEvent] = []
        self.host_events_path = output_dir / "host.events.jsonl"
        self.host_events_path.touch(exist_ok=True)
        self.host_started = False
        self.experiment_started = False
        self.finalized = False
        self._start_ns: int | None = None
        self._states: dict[Role, RoleState] = {}
        for role in ROLES:
            state = RoleState(
                binding=binding_map[role],
                raw_path=output_dir / f"{role.lower()}.raw",
                events_path=output_dir / f"{role.lower()}.events.jsonl",
            )
            state.raw_path.touch(exist_ok=True)
            state.events_path.touch(exist_ok=True)
            self._states[role] = state
        self._emit("host_capture_prepared", None, {"roles": list(ROLES)})

    @property
    def states(self) -> dict[Role, RoleState]:
        return self._states

    def _emit(
        self,
        kind: str,
        role: Role | None,
        details: dict[str, object] | None = None,
        *,
        now_ns: int | None = None,
    ) -> HostEvent:
        with self._event_lock:
            event = HostEvent(
                kind=kind,
                role=role,
                monotonic_ns=self._clock_ns() if now_ns is None else now_ns,
                wall_time=self._wall_clock().isoformat(),
                details=details or {},
            )
            self.events.append(event)
            serialized = json.dumps(event.as_dict(), sort_keys=True) + "\n"
            with self.host_events_path.open("a", encoding="utf-8") as stream:
                stream.write(serialized)
                stream.flush()
            if role is not None:
                with self._states[role].events_path.open("a", encoding="utf-8") as stream:
                    stream.write(serialized)
                    stream.flush()
            return event

    def mark_reader_ready(self, role: Role, device_id: str, *, now_ns: int | None = None) -> bool:
        """Record that a bound reader is actually ready to receive bytes."""
        state = self._states[role]
        if device_id != state.binding.device_id:
            self._emit(
                "port_identity_mismatch",
                role,
                {"expected_device_id": state.binding.device_id, "observed_device_id": device_id},
                now_ns=now_ns,
            )
            state.identity_valid = False
            return False
        state.reader_ready = True
        state.connected = True
        state.identity_valid = True
        self._emit("collector_ready", role, {"device_id": device_id}, now_ns=now_ns)
        return True

    def update_port_state(
        self,
        role: Role,
        connected: bool,
        device_id: str | None = None,
        *,
        now_ns: int | None = None,
    ) -> bool:
        state = self._states[role]
        if device_id is not None and device_id != state.binding.device_id:
            self._emit(
                "port_identity_mismatch",
                role,
                {"expected_device_id": state.binding.device_id, "observed_device_id": device_id},
                now_ns=now_ns,
            )
            state.identity_valid = False
            return False
        if connected:
            state.connected = True
            if state.disconnected:
                state.reconnect_count += 1
                self._emit("port_reconnected", role, {"reconnect_count": state.reconnect_count}, now_ns=now_ns)
            state.disconnected = False
            return True
        state.connected = False
        state.disconnected = True
        # Bytes received after HOST_COLLECTOR_READY are already evidence. A
        # disconnect after reader readiness must not be hidden merely because
        # the bounded capture window has not completed yet.
        if self.host_started and state.data_seen:
            state.capture_interrupted = True
            self._emit(
                "capture_interrupted",
                role,
                {"reason": "port_disconnected", "experiment_started": self.experiment_started},
                now_ns=now_ns,
            )
        self._emit("port_disconnected", role, {}, now_ns=now_ns)
        return True

    def ready_barrier(self) -> bool:
        """Return true only after both bound reader loops reported readiness."""
        return all(state.reader_ready and state.identity_valid and state.connected for state in self._states.values())

    def begin_host_capture(self, *, now_ns: int | None = None) -> bool:
        if not self.ready_barrier():
            self._emit("prestart_barrier_blocked", None, {"reason": "both_bound_readers_not_ready"}, now_ns=now_ns)
            return False
        self.host_started = True
        self._emit("host_capture_started", None, {}, now_ns=now_ns)
        return True

    def begin_experiment(self, *, now_ns: int | None = None) -> bool:
        """Mark the device experiment start after the host reader barrier."""
        if not self.host_started or not self.ready_barrier():
            self._emit("experiment_start_blocked", None, {"reason": "host_capture_not_ready"}, now_ns=now_ns)
            return False
        self.experiment_started = True
        self._start_ns = self._clock_ns() if now_ns is None else now_ns
        missing = [role for role, state in self._states.items() if not state.heartbeat_seen]
        self._emit(
            "experiment_started",
            None,
            {"startup_heartbeat_missing": missing},
            now_ns=now_ns,
        )
        return True

    def feed(self, role: Role, data: bytes, *, now_ns: int | None = None) -> int:
        """Persist raw bytes and parse complete UTF-8 log lines."""
        state = self._states[role]
        if not state.connected or not state.identity_valid:
            self._emit("bytes_rejected_not_bound", role, {"byte_count": len(data)}, now_ns=now_ns)
            return 0
        if data:
            with state.raw_path.open("ab") as stream:
                stream.write(data)
                stream.flush()
            state.raw_bytes += len(data)
            state.data_seen = True
            self._emit("bytes_received", role, {"byte_count": len(data)}, now_ns=now_ns)
        state.line_buffer += data
        lines = state.line_buffer.split(b"\n")
        state.line_buffer = lines.pop()
        for raw_line in lines:
            self._observe_line(role, raw_line.rstrip(b"\r"), now_ns=now_ns)
        return len(data)

    @staticmethod
    def _tokens(text: str) -> dict[str, str]:
        return {key: value for key, value in _TOKEN_RE.findall(text)}

    def _role_is_valid(self, role: Role, text: str, *, require_explicit: bool, now_ns: int | None) -> bool:
        declared = self._tokens(text).get("role")
        if declared is None:
            if require_explicit:
                self._states[role].role_mismatch = True
                self._emit("role_missing", role, {"line": text}, now_ns=now_ns)
                return False
            return True
        if declared != role:
            self._states[role].role_mismatch = True
            self._emit(
                "role_mismatch",
                role,
                {"expected_role": role, "declared_role": declared, "line": text},
                now_ns=now_ns,
            )
            return False
        return True

    def _record_order(self, role: Role, evidence: str) -> None:
        if evidence not in self._states[role].evidence_order:
            self._states[role].evidence_order.append(evidence)

    def _observe_line(self, role: Role, line: bytes, *, now_ns: int | None) -> None:
        text = line.decode("utf-8", errors="replace")
        state = self._states[role]
        if any(marker in text for marker in _BOOT_MARKERS):
            if state.heartbeat_seen:
                state.device_reboot_detected = True
                self._emit(
                    "device_reboot_detected",
                    role,
                    {"boot_marker_count": state.boot_marker_count, "line": text},
                    now_ns=now_ns,
                )
            state.boot_marker_count += 1
            self._emit("boot_evidence_observed", role, {"boot_marker_count": state.boot_marker_count}, now_ns=now_ns)
        if "R1R4_CAPTURE_HEARTBEAT" in text:
            if self._role_is_valid(role, text, require_explicit=True, now_ns=now_ns):
                state.heartbeat_seen = True
                self._record_order(role, "heartbeat")
                self._emit("heartbeat_received", role, {"line": text}, now_ns=now_ns)
        if "R1R4_LIFECYCLE_GATE_OPEN" in text:
            if self._role_is_valid(role, text, require_explicit=False, now_ns=now_ns):
                state.lifecycle_gate_seen = True
                self._record_order(role, "lifecycle_gate")
                details = {
                    "line": text,
                    "host_barrier_seen": self.host_started,
                    "role_explicit": "role=" in text,
                }
                self._emit("experiment_start_observed", role, details, now_ns=now_ns)
                if not self.host_started:
                    self._emit("lifecycle_gate_before_host_start", role, details, now_ns=now_ns)
        if "R1R3_SUMMARY" in text:
            if self._role_is_valid(role, text, require_explicit=True, now_ns=now_ns):
                fields = self._tokens(text)
                state.summary_seen = True
                state.summary_fields = {key: value for key, value in fields.items() if key != "role"}
                self._record_order(role, "summary")
                self._emit("summary_received", role, {"line": text, "fields": state.summary_fields}, now_ns=now_ns)
                self._emit("experiment_end_observed", role, {"summary_seen": True}, now_ns=now_ns)

    def tick(self, *, now_ns: int | None = None) -> None:
        """Emit bounded timeout evidence without treating it as experiment PASS."""
        now = self._clock_ns() if now_ns is None else now_ns
        for role, state in self._states.items():
            if self.host_started and not state.data_seen:
                anchor = self.events[0].monotonic_ns
                if now - anchor >= int(self.heartbeat_timeout_s * 1_000_000_000):
                    if not any(e.kind == "log_missing" and e.role == role for e in self.events):
                        self._emit("log_missing", role, {"reason": "no_bytes_received"}, now_ns=now)
            if self.experiment_started and not state.summary_seen and self._start_ns is not None:
                if now - self._start_ns >= int(self.summary_timeout_s * 1_000_000_000):
                    if not any(e.kind == "summary_missing" and e.role == role for e in self.events):
                        self._emit("summary_missing", role, {}, now_ns=now)

    def finalize(self, *, now_ns: int | None = None) -> dict[str, object]:
        for role, state in self._states.items():
            if state.line_buffer:
                self._observe_line(role, state.line_buffer.rstrip(b"\r"), now_ns=now_ns)
                state.line_buffer = b""
        self.tick(now_ns=now_ns)
        self.finalized = True
        states = self._states
        summaries_complete = all(state.summary_seen for state in states.values())
        required_order = ("heartbeat", "lifecycle_gate", "summary")
        ordered = all(
            tuple(state.evidence_order[: len(required_order)]) == required_order
            for state in states.values()
        )
        required_evidence = all(
            state.heartbeat_seen and state.lifecycle_gate_seen and state.summary_seen
            for state in states.values()
        )
        summary_fields_complete = all(
            set(REAL_SUMMARY_FIELDS[role]).issubset(states[role].summary_fields)
            for role in ROLES
        )
        operation_summary_valid = {
            role: operation_summary_consistent(role, states[role].summary_fields)
            for role in ROLES
        }
        fatal_capture_events = {
            "log_missing",
            "summary_missing",
            "port_identity_mismatch",
            "role_missing",
            "role_mismatch",
            "lifecycle_gate_before_host_start",
            "device_reboot_detected",
            "capture_interrupted",
        }
        capture_valid = required_evidence and summary_fields_complete and all(operation_summary_valid.values()) and ordered and not any(
            event.kind in fatal_capture_events for event in self.events
        )
        capture_completeness = "COMPLETE" if capture_valid else "INCOMPLETE"
        manifest = {
            "collector_ready": {role: states[role].reader_ready and states[role].identity_valid for role in ROLES},
            "data_seen": {role: states[role].data_seen for role in ROLES},
            "heartbeat_seen": {role: states[role].heartbeat_seen for role in ROLES},
            "lifecycle_gate_seen": {role: states[role].lifecycle_gate_seen for role in ROLES},
            "summary_seen": {role: states[role].summary_seen for role in ROLES},
            "summaries_complete": summaries_complete,
            "evidence_order": {role: states[role].evidence_order for role in ROLES},
            "observed_lifecycle_results": {
                role: dict(states[role].summary_fields)
                for role in ROLES
            },
            "summary_fields_complete": summary_fields_complete,
            "operation_summary_valid": operation_summary_valid,
            "capture_completeness": capture_completeness,
            "capture_valid": capture_valid,
            "product_experiment_result": "REQUIRES_RAW_LOG_REVIEW",
            "boot_marker_count": {role: states[role].boot_marker_count for role in ROLES},
            "device_reboot_detected": {role: states[role].device_reboot_detected for role in ROLES},
            "capture_interrupted": {role: states[role].capture_interrupted for role in ROLES},
            "raw_sha256": {role: _sha256(states[role].raw_path) for role in ROLES},
            "events": [event.as_dict() for event in self.events],
        }
        with (self.output_dir / "capture-manifest.json").open("w", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
        return manifest


def discover_serial_identity(port: str) -> str:
    """Return a stable, human-bound USB descriptor without opening the port."""
    try:
        from serial.tools import list_ports  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only in live envs
        raise RuntimeError("live mode requires pyserial; replay mode does not") from exc
    matches = [info for info in list_ports.comports() if info.device == port]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one USB descriptor for {port!r}, found {len(matches)}")
    info = matches[0]
    parts = {
        "device": info.device,
        "serial": info.serial_number or "",
        "vid": "" if info.vid is None else f"{info.vid:04x}",
        "pid": "" if info.pid is None else f"{info.pid:04x}",
        "location": info.location or "",
        "product": info.product or "",
    }
    if not any(parts[key] for key in ("serial", "location", "product")):
        raise RuntimeError(f"USB descriptor for {port!r} has no stable identity fields")
    return "|".join(f"{key}={value}" for key, value in parts.items())


def _default_serial_factory(port: str, **kwargs: object) -> object:
    try:
        import serial  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only in live envs
        raise RuntimeError("live mode requires pyserial; replay mode does not") from exc
    # Open with modem-control lines already low. This avoids the common
    # pyserial DTR/RTS edge that can reset an ESP board during handoff.
    connection = serial.Serial(port=None, **kwargs)
    connection.dtr = False
    connection.rts = False
    connection.port = port
    connection.open()
    return connection


class SerialBackend:
    """Minimal live reader adapter; never writes bytes to a device."""

    def __init__(
        self,
        capture: DualCapture,
        ports: dict[Role, str],
        *,
        serial_factory: Callable[..., object] | None = None,
        identity_lookup: Callable[[str], str] = discover_serial_identity,
        reconnect_timeout_s: float = 10.0,
        max_reconnect_attempts: int = 3,
        read_size: int = 4096,
        clock_ns: Callable[[], int] | None = None,
    ) -> None:
        if set(ports) != set(ROLES) or len(set(ports.values())) != len(ROLES):
            raise ValueError("CONTROL and DUT ports must be present and unique")
        self.capture = capture
        self.ports = ports
        self.serial_factory = serial_factory or _default_serial_factory
        self.identity_lookup = identity_lookup
        self.reconnect_timeout_s = reconnect_timeout_s
        if max_reconnect_attempts < 1:
            raise ValueError("max_reconnect_attempts must be positive")
        self.max_reconnect_attempts = max_reconnect_attempts
        self.read_size = read_size
        self._clock_ns = clock_ns or time.monotonic_ns
        self._connections: dict[Role, object] = {}
        self._retry_after_ns: dict[Role, int] = {}
        self._reconnect_attempts: dict[Role, int] = {role: 0 for role in ROLES}
        self._stop_event = threading.Event()
        self._loop_started = threading.Event()
        self._reader_thread: threading.Thread | None = None

    def _open_role(self, role: Role, *, initial: bool) -> bool:
        port = self.ports[role]
        if not initial:
            if self._reconnect_attempts[role] >= self.max_reconnect_attempts:
                self.capture._emit(
                    "reconnect_exhausted",
                    role,
                    {"max_reconnect_attempts": self.max_reconnect_attempts},
                )
                return False
            self._reconnect_attempts[role] += 1
        try:
            observed_id = self.identity_lookup(port)
        except Exception as exc:
            self.capture._emit("port_identity_probe_failed", role, {"error": type(exc).__name__})
            self._retry_after_ns[role] = self._clock_ns() + int(self.reconnect_timeout_s * 1_000_000_000)
            return False
        expected_id = self.capture.states[role].binding.device_id
        if observed_id != expected_id:
            self.capture.update_port_state(role, False, observed_id)
            self.capture._emit(
                "port_identity_mismatch",
                role,
                {"expected_device_id": expected_id, "observed_device_id": observed_id},
            )
            return False
        try:
            connection = self.serial_factory(
                port,
                baudrate=115200,
                timeout=0.2,
                write_timeout=0.2,
                dsrdtr=False,
                rtscts=False,
            )
        except Exception as exc:
            self.capture._emit("port_open_failed", role, {"error": type(exc).__name__, "initial": initial})
            self._retry_after_ns[role] = self._clock_ns() + int(self.reconnect_timeout_s * 1_000_000_000)
            return False
        self._connections[role] = connection
        if initial:
            self.capture.mark_reader_ready(role, observed_id)
        else:
            self._reconnect_attempts[role] = 0
            self.capture.update_port_state(role, True, observed_id)
        return True

    def open_all(self) -> bool:
        opened: list[Role] = []
        for role in ROLES:
            if not self._open_role(role, initial=True):
                self.close_all()
                return False
            opened.append(role)
        return len(opened) == len(ROLES)

    def start_reader_loop(self) -> bool:
        """Start polling before the host-ready barrier is announced."""
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return True
        self._stop_event.clear()
        self._loop_started.clear()

        def run() -> None:
            self._loop_started.set()
            self.capture._emit("reader_loop_running", None, {"roles": list(ROLES)})
            try:
                while not self._stop_event.is_set():
                    self.poll_once()
                    time.sleep(0.02)
            except BaseException as exc:  # preserve evidence before main shutdown
                self.capture._emit("reader_loop_exception", None, {"error": type(exc).__name__})

        self._reader_thread = threading.Thread(target=run, name="r1r4-reader", daemon=True)
        self._reader_thread.start()
        return self._loop_started.wait(timeout=1.0)

    def stop_reader_loop(self) -> None:
        self._stop_event.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=1.0)
        self._reader_thread = None

    def poll_once(self) -> None:
        now = self._clock_ns()
        for role in ROLES:
            connection = self._connections.get(role)
            if connection is None:
                if now >= self._retry_after_ns.get(role, now):
                    self._open_role(role, initial=False)
                continue
            try:
                data = connection.read(self.read_size)  # type: ignore[attr-defined]
            except Exception as exc:
                self.capture.update_port_state(role, False)
                self.capture._emit("reader_error", role, {"error": type(exc).__name__})
                try:
                    connection.close()  # type: ignore[attr-defined]
                finally:
                    self._connections.pop(role, None)
                    self._retry_after_ns[role] = now + int(self.reconnect_timeout_s * 1_000_000_000)
                continue
            if data:
                self.capture.feed(role, bytes(data), now_ns=now)

    def close_all(self) -> None:
        for connection in self._connections.values():
            try:
                connection.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        self._connections.clear()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _feed_file(capture: DualCapture, role: Role, path: Path) -> None:
    if path.exists():
        capture.feed(role, path.read_bytes())


def _run_live_capture_window(
    capture: DualCapture,
    *,
    duration_s: float = LIVE_CAPTURE_DURATION_S,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    """Run the bounded live window without an operator-input barrier."""
    capture.begin_experiment()
    deadline = clock() + duration_s
    while clock() < deadline and not all(state.summary_seen for state in capture.states.values()):
        capture.tick()
        sleeper(min(0.02, max(0.0, deadline - clock())))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--control-input", type=Path)
    parser.add_argument("--dut-input", type=Path)
    parser.add_argument("--control-device", required=True)
    parser.add_argument("--dut-device", required=True)
    parser.add_argument("--control-port")
    parser.add_argument("--dut-port")
    args = parser.parse_args()
    capture = DualCapture(
        args.output_dir,
        [RoleBinding("CONTROL", args.control_device), RoleBinding("DUT", args.dut_device)],
    )
    if args.mode == "replay":
        # Reader binding/readiness is established before any simulated device
        # bytes arrive, mirroring the required physical start barrier.
        capture.mark_reader_ready("CONTROL", args.control_device)
        capture.mark_reader_ready("DUT", args.dut_device)
        if not capture.begin_host_capture():
            capture.finalize()
            return 2
        capture.begin_experiment()
        if args.control_input is not None:
            _feed_file(capture, "CONTROL", args.control_input)
        if args.dut_input is not None:
            _feed_file(capture, "DUT", args.dut_input)
        manifest = capture.finalize()
        print(json.dumps({key: manifest[key] for key in ("capture_completeness", "capture_valid", "observed_lifecycle_results")}, sort_keys=True))
        return 0 if manifest["capture_valid"] is True else 1

    if not args.control_port or not args.dut_port:
        parser.error("--mode live requires --control-port and --dut-port")
    backend = SerialBackend(capture, {"CONTROL": args.control_port, "DUT": args.dut_port})
    exit_code = 2
    try:
        print("MODE=LIVE_SERIAL DTR=false RTS=false WRITE_TO_DEVICE=false")
        ready = backend.open_all() and backend.start_reader_loop() and capture.begin_host_capture()
        if not ready:
            capture._emit("host_start_failed", None, {})
        else:
            print(
                "HOST_COLLECTOR_READY=true; reader loop is running; "
                "fixed 60-second capture window started; no operator input required"
            )
            _run_live_capture_window(capture)
            exit_code = 0
    except KeyboardInterrupt:
        capture._emit("host_interrupted", None, {})
        exit_code = 130
    except BaseException as exc:
        capture._emit("host_orchestrator_exception", None, {"error": type(exc).__name__})
        exit_code = 1
    finally:
        backend.stop_reader_loop()
        backend.close_all()
        manifest = capture.finalize()
    print(json.dumps({key: manifest[key] for key in ("capture_completeness", "capture_valid", "observed_lifecycle_results")}, sort_keys=True))
    return exit_code if exit_code != 0 else (0 if manifest["capture_valid"] is True else 1)


if __name__ == "__main__":
    raise SystemExit(main())
