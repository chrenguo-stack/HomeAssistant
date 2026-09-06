#!/usr/bin/env python3
"""Live R1R4 capture wrapper with an explicit human-operation barrier.

The serial reader is started before the barrier and keeps persisting raw bytes
while the operator performs the requested reset.  The fixed 60-second window
starts only after the one-shot confirmation file appears.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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


def wait_for_operator_confirmation(
    capture: DualCapture,
    confirmation_file: Path,
    *,
    timeout_s: float = 300.0,
    poll_s: float = 0.05,
    clock=time.monotonic,
    sleeper=time.sleep,
) -> bool:
    """Wait without stopping readers or starting the bounded experiment clock."""
    if confirmation_file.exists():
        capture._emit("operator_confirmation_rejected", None, {"reason": "file_preexisting"})
        return False
    started = clock()
    capture._emit(
        "operator_wait_started",
        None,
        {"confirmation_file": str(confirmation_file), "timeout_s": timeout_s},
    )
    while clock() - started < timeout_s:
        if confirmation_file.exists():
            capture._emit("operator_confirmed", None, {"confirmation_file": str(confirmation_file)})
            return True
        sleeper(poll_s)
    capture._emit(
        "operator_confirmation_timeout",
        None,
        {"confirmation_file": str(confirmation_file), "timeout_s": timeout_s},
    )
    return False


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
    exit_code = 2
    try:
        print("MODE=LIVE_SERIAL DTR=false RTS=false WRITE_TO_DEVICE=false", flush=True)
        ready = backend.open_all() and backend.start_reader_loop() and capture.begin_host_capture()
        if not ready:
            capture._emit("host_start_failed", None, {})
        else:
            print(
                "HOST_COLLECTOR_READY=true; reader loop is running; "
                "waiting for operator confirmation; 60-second window not started",
                flush=True,
            )
            print(
                f"OPERATOR_ACTION_REQUIRED=perform approved reset; then create {args.operator_confirm_file}",
                flush=True,
            )
            if wait_for_operator_confirmation(
                capture,
                args.operator_confirm_file,
                timeout_s=args.operator_timeout_s,
            ):
                capture.begin_experiment()
                print(
                    f"OPERATOR_CONFIRMED=true; FIXED_CAPTURE_WINDOW_S={LIVE_CAPTURE_DURATION_S:g}",
                    flush=True,
                )
                deadline = time.monotonic() + LIVE_CAPTURE_DURATION_S
                while time.monotonic() < deadline and not all(
                    state.summary_seen for state in capture.states.values()
                ):
                    capture.tick()
                    time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
                exit_code = 0
            else:
                capture._emit("experiment_not_started", None, {"reason": "operator_confirmation_missing"})
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
    print(
        json.dumps(
            {key: manifest[key] for key in ("capture_completeness", "capture_valid", "observed_lifecycle_results")},
            sort_keys=True,
        )
    )
    return exit_code if exit_code != 0 else (0 if manifest["capture_valid"] is True else 1)


if __name__ == "__main__":
    raise SystemExit(main())
