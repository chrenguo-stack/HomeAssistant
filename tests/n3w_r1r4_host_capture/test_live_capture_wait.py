from __future__ import annotations

import threading
import time
from pathlib import Path

from experiments.n3w_r1r4_live_capture_wait import wait_for_operator_confirmation
from experiments.n3w_r1r4_host_capture_orchestrator import DualCapture, RoleBinding


def test_operator_wait_keeps_reader_bytes_and_starts_only_after_confirmation(tmp_path: Path) -> None:
    capture = DualCapture(
        tmp_path / "capture",
        [RoleBinding("CONTROL", "control-id"), RoleBinding("DUT", "dut-id")],
    )
    capture.mark_reader_ready("CONTROL", "control-id")
    capture.mark_reader_ready("DUT", "dut-id")
    assert capture.begin_host_capture()
    confirmation = tmp_path / "operator.confirmed"

    def feed_before_confirmation() -> None:
        time.sleep(0.02)
        capture.feed("CONTROL", b"ESP-ROM: boot\n")
        capture.feed("CONTROL", b"R1R4_CAPTURE_HEARTBEAT role=CONTROL\n")
        confirmation.touch()

    producer = threading.Thread(target=feed_before_confirmation)
    producer.start()
    assert wait_for_operator_confirmation(capture, confirmation, timeout_s=1.0, poll_s=0.005)
    producer.join()
    assert capture.experiment_started is False
    assert b"R1R4_CAPTURE_HEARTBEAT" in (tmp_path / "capture/control.raw").read_bytes()
    assert any(event.kind == "operator_wait_started" for event in capture.events)
    assert any(event.kind == "operator_confirmed" for event in capture.events)


def test_operator_wait_times_out_without_starting_experiment(tmp_path: Path) -> None:
    capture = DualCapture(
        tmp_path / "capture",
        [RoleBinding("CONTROL", "control-id"), RoleBinding("DUT", "dut-id")],
    )
    capture.mark_reader_ready("CONTROL", "control-id")
    capture.mark_reader_ready("DUT", "dut-id")
    assert capture.begin_host_capture()
    assert not wait_for_operator_confirmation(
        capture, tmp_path / "missing.confirmed", timeout_s=0.01, poll_s=0.001
    )
    assert capture.experiment_started is False
    assert any(event.kind == "operator_confirmation_timeout" for event in capture.events)
