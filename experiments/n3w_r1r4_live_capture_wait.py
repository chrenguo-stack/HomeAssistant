#!/usr/bin/env python3
"""Live R1R4 capture wrapper with a non-blocking operator acknowledgement.

The serial reader starts before any operator action and keeps persisting raw
bytes.  The first observed lifecycle gate is the experiment start evidence and
starts one fixed 60-second capture window.  A later operator confirmation is
recorded only; it never starts or extends another window.
"""

from __future__ import annotations

import argparse
import json
import time
from enum import Enum
from pathlib import Path

try:
    from .n3w_r1r4_host_capture_orchestrator import (
        LIVE_CAPTURE_DURATION_S,
        DualCapture,
        RoleBinding,
        SerialBackend,
    )
except ImportError:  # direct ``python experiments/n3w_r1r4_live_capture_wait.py``
    from n3w_r1r4_host_capture_orchestrator import (
        LIVE_CAPTURE_DURATION_S,
        DualCapture,
        RoleBinding,
        SerialBackend,
    )


class OperatorWaitResult(str, Enum):
    """Outcome of the operator barrier, preserving a boolean-compatible API."""

    CONFIRMED = "confirmed"
    COMPLETED_BEFORE_CONFIRMATION = "completed_before_confirmation"
    ALREADY_STARTED_BEFORE_CONFIRMATION = "already_started_before_confirmation"
    FATAL_BEFORE_CONFIRMATION = "fatal_before_confirmation"
    TIMEOUT = "timeout"

    def __bool__(self) -> bool:
        return self is OperatorWaitResult.CONFIRMED


_FATAL_WAIT_EVENTS = frozenset(
    {
        "capture_interrupted",
        "device_reboot_detected",
        "log_missing",
        "port_identity_mismatch",
        "reader_error",
        "reader_loop_exception",
        "role_missing",
        "role_mismatch",
    }
)


def _fatal_wait_events(capture: DualCapture) -> list[str]:
    return [event.kind for event in capture.events if event.kind in _FATAL_WAIT_EVENTS]


def run_live_capture(
    capture: DualCapture,
    backend: object,
    confirmation_file: Path,
    *,
    operator_timeout_s: float = 300.0,
    duration_s: float = LIVE_CAPTURE_DURATION_S,
    poll_s: float = 0.05,
    clock=time.monotonic,
    sleeper=time.sleep,
    output=print,
) -> tuple[int, dict[str, object]]:
    """Run the complete live orchestration with injectable time/backend.

    The operator confirmation is an acknowledgement side channel.  The
    lifecycle gate is the only host timestamp that starts the bounded window;
    no synthetic ``experiment_started`` event is emitted here.
    """
    exit_code = 2
    manifest: dict[str, object]
    try:
        ready = backend.open_all() and backend.start_reader_loop() and capture.begin_host_capture()
        if not ready:
            capture._emit("host_start_failed", None, {})
        else:
            output(
                "HOST_COLLECTOR_READY=true; reader loop is running; "
                "waiting for lifecycle gate and operator acknowledgement"
            )
            output(
                f"OPERATOR_ACTION_REQUIRED=perform approved reset; then create {confirmation_file}"
            )
            capture._emit(
                "operator_wait_started",
                None,
                {"confirmation_file": str(confirmation_file), "timeout_s": operator_timeout_s},
            )
            wait_deadline = clock() + operator_timeout_s
            capture_deadline: float | None = None
            observed_gate_roles: set[str] = set()
            confirmation_seen = False
            confirmation_rejected = confirmation_file.exists()
            if confirmation_rejected:
                capture._emit("operator_confirmation_rejected", None, {"reason": "file_preexisting"})
            observed_fatal_events = 0
            terminal_reason: str | None = None

            while True:
                capture.tick()
                fatal_events = _fatal_wait_events(capture)
                if len(fatal_events) > observed_fatal_events:
                    capture._emit(
                        "capture_terminal_fatal",
                        None,
                        {"kinds": sorted(set(fatal_events))},
                    )
                    terminal_reason = "fatal_capture_event"
                    exit_code = 1
                    break
                observed_fatal_events = len(fatal_events)

                for role, state in capture.states.items():
                    if state.lifecycle_gate_seen and role not in observed_gate_roles:
                        observed_gate_roles.add(role)
                        if capture_deadline is None:
                            gate_time = clock()
                            capture_deadline = gate_time + duration_s
                            capture._emit(
                                "capture_window_started_at_lifecycle_gate",
                                role,
                                {
                                    "host_monotonic_s": gate_time,
                                    "duration_s": duration_s,
                                },
                            )
                            output("实验已启动，请勿再次复位")

                if not confirmation_seen and not confirmation_rejected and confirmation_file.exists():
                    confirmation_seen = True
                    capture._emit("operator_confirmed", None, {"confirmation_file": str(confirmation_file)})
                    if capture_deadline is not None:
                        capture._emit(
                            "operator_confirmation_after_early_start",
                            None,
                            {"roles": sorted(observed_gate_roles)},
                        )
                    else:
                        capture._emit("operator_confirmation_waiting_for_lifecycle_gate", None, {})
                if all(state.summary_seen for state in capture.states.values()):
                    capture._emit(
                        "capture_completed_before_operator_confirmation"
                        if not confirmation_seen
                        else "capture_completed",
                        None,
                        {"roles": list(capture.states)},
                    )
                    terminal_reason = "summaries_complete"
                    break

                now = clock()
                if capture_deadline is not None:
                    if now >= capture_deadline:
                        capture._emit(
                            "capture_window_timeout",
                            None,
                            {"deadline_monotonic_s": capture_deadline},
                        )
                        terminal_reason = "capture_deadline"
                        exit_code = 1
                        break
                    sleep_for = min(poll_s, max(0.0, capture_deadline - now))
                else:
                    if now >= wait_deadline:
                        capture._emit(
                            "lifecycle_gate_timeout",
                            None,
                            {"timeout_s": operator_timeout_s},
                        )
                        terminal_reason = "lifecycle_gate_timeout"
                        exit_code = 1
                        break
                    sleep_for = min(poll_s, max(0.0, wait_deadline - now))
                sleeper(sleep_for)

            capture._emit("capture_terminal", None, {"reason": terminal_reason})
            if exit_code == 2:
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
    if exit_code == 0 and manifest["capture_valid"] is not True:
        exit_code = 1
    return exit_code, manifest


def wait_for_operator_confirmation(
    capture: DualCapture,
    confirmation_file: Path,
    *,
    timeout_s: float = 300.0,
    poll_s: float = 0.05,
    clock=time.monotonic,
    sleeper=time.sleep,
) -> OperatorWaitResult:
    """Wait while preserving evidence already arriving from the devices.

    The firmware can start and finish independently of this host-side barrier.
    Summary completion or a fatal capture event therefore ends the wait without
    creating a second host experiment window.
    """
    if confirmation_file.exists():
        capture._emit("operator_confirmation_rejected", None, {"reason": "file_preexisting"})
        return OperatorWaitResult.TIMEOUT
    started = clock()
    capture._emit(
        "operator_wait_started",
        None,
        {"confirmation_file": str(confirmation_file), "timeout_s": timeout_s},
    )
    observed_started_roles: set[str] = set()
    observed_fatal_events = 0
    while clock() - started < timeout_s:
        capture.tick()
        for role, state in capture.states.items():
            if state.lifecycle_gate_seen and role not in observed_started_roles:
                observed_started_roles.add(role)
                capture._emit(
                    "experiment_started_before_confirmation",
                    role,
                    {"reason": "lifecycle_gate_observed_during_operator_wait"},
                )
        fatal_events = [event for event in capture.events if event.kind in _FATAL_WAIT_EVENTS]
        if len(fatal_events) > observed_fatal_events:
            capture._emit(
                "operator_wait_fatal_error",
                None,
                {"kinds": sorted({event.kind for event in fatal_events})},
            )
            return OperatorWaitResult.FATAL_BEFORE_CONFIRMATION
        observed_fatal_events = len(fatal_events)
        if all(state.summary_seen for state in capture.states.values()):
            capture._emit(
                "capture_completed_before_operator_confirmation",
                None,
                {"roles": list(capture.states)},
            )
            return OperatorWaitResult.COMPLETED_BEFORE_CONFIRMATION
        if confirmation_file.exists():
            capture._emit("operator_confirmed", None, {"confirmation_file": str(confirmation_file)})
            if observed_started_roles:
                capture._emit(
                    "operator_confirmation_after_early_start",
                    None,
                    {"roles": sorted(observed_started_roles)},
                )
                return OperatorWaitResult.ALREADY_STARTED_BEFORE_CONFIRMATION
            return OperatorWaitResult.CONFIRMED
        sleeper(poll_s)
    capture._emit(
        "operator_confirmation_timeout",
        None,
        {"confirmation_file": str(confirmation_file), "timeout_s": timeout_s},
    )
    return OperatorWaitResult.TIMEOUT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--control-device", required=True)
    parser.add_argument("--dut-device", required=True)
    parser.add_argument("--control-port", required=True)
    parser.add_argument("--dut-port", required=True)
    parser.add_argument("--operator-confirm-file", type=Path, required=True)
    parser.add_argument("--operator-timeout-s", type=float, default=300.0)
    args = parser.parse_args()

    capture = DualCapture(
        args.output_dir,
        [RoleBinding("CONTROL", args.control_device), RoleBinding("DUT", args.dut_device)],
    )
    backend = SerialBackend(
        capture,
        {"CONTROL": args.control_port, "DUT": args.dut_port},
    )
    print("MODE=LIVE_SERIAL DTR=false RTS=false WRITE_TO_DEVICE=false", flush=True)
    exit_code, manifest = run_live_capture(
        capture,
        backend,
        args.operator_confirm_file,
        operator_timeout_s=args.operator_timeout_s,
        output=lambda message: print(message, flush=True),
    )
    print(
        json.dumps(
            {key: manifest[key] for key in ("capture_completeness", "capture_valid", "observed_lifecycle_results")},
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
