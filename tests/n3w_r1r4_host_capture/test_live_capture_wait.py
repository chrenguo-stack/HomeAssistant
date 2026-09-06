from __future__ import annotations

import threading
import time
from pathlib import Path

from experiments.n3w_r1r4_live_capture_wait import (
    OperatorWaitResult,
    run_live_capture,
    wait_for_operator_confirmation,
)
from experiments.n3w_r1r4_host_capture_orchestrator import DualCapture, RoleBinding


class VirtualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def ns(self) -> int:
        return int(self.now * 1_000_000_000)


class FakeBackend:
    def __init__(self, capture: DualCapture) -> None:
        self.capture = capture
        self.stopped = False
        self.closed = False

    def open_all(self) -> bool:
        return (
            self.capture.mark_reader_ready("CONTROL", "control-id")
            and self.capture.mark_reader_ready("DUT", "dut-id")
        )

    def start_reader_loop(self) -> bool:
        return True

    def stop_reader_loop(self) -> None:
        self.stopped = True

    def close_all(self) -> None:
        self.closed = True


def summary_line(role: str) -> bytes:
    if role == "CONTROL":
        return (
            b"R1R3_SUMMARY role=CONTROL baseline=PASS probe_tx_api=PASS "
            b"switch_tx_api=PASS switch_tx_request_op_id=55 switch_tx_driver_op_id=1 "
            b"switch_tx_completion=PASS switch_tx_status=TX_DURATION_COMPLETED "
            b"control_home_channel_api=PASS control_home_channel=1 control_ap_sta_link=true "
            b"control_home_return=PASS home_ack_api=NOT_APPLICABLE "
            b"home_ack_send_callback=NOT_APPLICABLE home_ack_received=PASS home_ack=PASS\n"
        )
    return (
        b"R1R3_SUMMARY role=DUT baseline=PASS roc_req=PASS "
        b"roc_request_input_op_id=0 roc_driver_op_id=1 roc_natural_complete=false "
        b"roc_cancel_api=PASS roc_cancel_complete=PASS roc_completion_status=WIFI_ROC_FAIL "
        b"roc_termination_observed=true roc_termination_wait=PASS roc_active=false "
        b"probe_rx=PASS home_recovery=PASS home_channel_api=PASS home_channel=1 "
        b"home_sta_link=true home_ack_tx=PASS home_ack_api=PASS "
        b"home_ack_send_callback=PASS home_ack_received=NOT_APPLICABLE disconnect_count=0\n"
    )


def lifecycle_lines(role: str) -> bytes:
    return (
        f"R1R4_CAPTURE_HEARTBEAT role={role}\n"
        f"R1R4_LIFECYCLE_GATE_OPEN role={role}\n"
    ).encode()


def make_live_capture(tmp_path: Path, clock: VirtualClock) -> tuple[DualCapture, FakeBackend]:
    capture = DualCapture(
        tmp_path / "capture",
        [RoleBinding("CONTROL", "control-id"), RoleBinding("DUT", "dut-id")],
        clock_ns=clock.ns,
    )
    return capture, FakeBackend(capture)


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


def test_both_summaries_before_confirmation_end_wait_without_second_window(tmp_path: Path) -> None:
    capture = DualCapture(
        tmp_path / "capture",
        [RoleBinding("CONTROL", "control-id"), RoleBinding("DUT", "dut-id")],
    )
    capture.mark_reader_ready("CONTROL", "control-id")
    capture.mark_reader_ready("DUT", "dut-id")
    assert capture.begin_host_capture()
    confirmation = tmp_path / "operator.confirmed"

    def feed_completed_run() -> None:
        time.sleep(0.02)
        capture.feed("DUT", b"R1R4_LIFECYCLE_GATE_OPEN role=DUT\n")
        capture.feed("CONTROL", b"R1R4_LIFECYCLE_GATE_OPEN control_capture_armed=true\n")
        capture.feed("DUT", b"R1R3_SUMMARY role=DUT baseline=PASS\n")
        capture.feed("CONTROL", b"R1R3_SUMMARY role=CONTROL baseline=PASS\n")

    producer = threading.Thread(target=feed_completed_run)
    producer.start()
    result = wait_for_operator_confirmation(capture, confirmation, timeout_s=1.0, poll_s=0.005)
    producer.join()

    assert result is OperatorWaitResult.COMPLETED_BEFORE_CONFIRMATION
    assert capture.experiment_started is False
    assert not confirmation.exists()
    assert any(event.kind == "experiment_started_before_confirmation" for event in capture.events)
    assert any(event.kind == "capture_completed_before_operator_confirmation" for event in capture.events)
    assert not any(event.kind == "experiment_started" for event in capture.events)


def test_confirmation_after_early_lifecycle_gate_does_not_start_second_window(tmp_path: Path) -> None:
    capture = DualCapture(
        tmp_path / "capture",
        [RoleBinding("CONTROL", "control-id"), RoleBinding("DUT", "dut-id")],
    )
    capture.mark_reader_ready("CONTROL", "control-id")
    capture.mark_reader_ready("DUT", "dut-id")
    assert capture.begin_host_capture()
    confirmation = tmp_path / "operator.confirmed"

    def feed_early_start() -> None:
        time.sleep(0.02)
        capture.feed("DUT", b"R1R4_LIFECYCLE_GATE_OPEN role=DUT\n")
        capture.feed("CONTROL", b"R1R4_LIFECYCLE_GATE_OPEN control_capture_armed=true\n")
        time.sleep(0.02)
        confirmation.touch()

    producer = threading.Thread(target=feed_early_start)
    producer.start()
    result = wait_for_operator_confirmation(capture, confirmation, timeout_s=1.0, poll_s=0.005)
    producer.join()

    assert result is OperatorWaitResult.ALREADY_STARTED_BEFORE_CONFIRMATION
    assert capture.experiment_started is False
    assert any(event.kind == "operator_confirmation_after_early_start" for event in capture.events)
    assert not any(event.kind == "experiment_started" for event in capture.events)


def test_main_flow_gate_then_confirmation_keeps_one_window_and_completes(tmp_path: Path) -> None:
    clock = VirtualClock()
    capture, backend = make_live_capture(tmp_path, clock)
    confirmation = tmp_path / "operator.confirmed"
    steps = {"count": 0}

    def sleeper(seconds: float) -> None:
        clock.now += seconds
        steps["count"] += 1
        if steps["count"] == 1:
            capture.feed("CONTROL", lifecycle_lines("CONTROL"))
            capture.feed("DUT", lifecycle_lines("DUT"))
        elif steps["count"] == 2:
            confirmation.touch()
        elif steps["count"] == 3:
            capture.feed("CONTROL", summary_line("CONTROL"))
            capture.feed("DUT", summary_line("DUT"))

    output: list[str] = []
    exit_code, manifest = run_live_capture(
        capture,
        backend,
        confirmation,
        operator_timeout_s=10.0,
        duration_s=60.0,
        poll_s=0.05,
        clock=clock,
        sleeper=sleeper,
        output=output.append,
    )

    assert exit_code == 0
    assert manifest["capture_valid"] is True
    assert backend.stopped and backend.closed
    assert any("实验已启动，请勿再次复位" in message for message in output)
    assert any(event.kind == "capture_window_started_at_lifecycle_gate" for event in capture.events)
    assert any(event.kind == "operator_confirmation_after_early_start" for event in capture.events)
    assert not any(event.kind == "experiment_started" for event in capture.events)
    assert not any(event.kind == "experiment_not_started" for event in capture.events)


def test_main_flow_gate_without_confirmation_has_bounded_deadline(tmp_path: Path) -> None:
    clock = VirtualClock()
    capture, backend = make_live_capture(tmp_path, clock)
    confirmation = tmp_path / "operator.confirmed"
    fed_gate = {"done": False}

    def sleeper(seconds: float) -> None:
        clock.now += seconds
        if not fed_gate["done"]:
            fed_gate["done"] = True
            capture.feed("CONTROL", lifecycle_lines("CONTROL"))
            capture.feed("DUT", lifecycle_lines("DUT"))

    exit_code, manifest = run_live_capture(
        capture,
        backend,
        confirmation,
        operator_timeout_s=300.0,
        duration_s=60.0,
        poll_s=60.0,
        clock=clock,
        sleeper=sleeper,
        output=lambda _message: None,
    )

    assert exit_code == 1
    assert manifest["capture_valid"] is False
    assert any(event.kind == "capture_window_timeout" for event in capture.events)
    assert not any(event.kind == "experiment_not_started" for event in capture.events)
    assert backend.stopped and backend.closed


def test_main_flow_complete_before_confirmation_returns_capture_valid_exit_zero(tmp_path: Path) -> None:
    clock = VirtualClock()
    capture, backend = make_live_capture(tmp_path, clock)
    confirmation = tmp_path / "operator.confirmed"
    fed = {"done": False}

    def sleeper(seconds: float) -> None:
        clock.now += seconds
        if not fed["done"]:
            fed["done"] = True
            capture.feed("CONTROL", lifecycle_lines("CONTROL") + summary_line("CONTROL"))
            capture.feed("DUT", lifecycle_lines("DUT") + summary_line("DUT"))

    exit_code, manifest = run_live_capture(
        capture,
        backend,
        confirmation,
        operator_timeout_s=30.0,
        clock=clock,
        sleeper=sleeper,
        output=lambda _message: None,
    )

    assert exit_code == 0
    assert manifest["capture_valid"] is True
    assert any(event.kind == "capture_completed_before_operator_confirmation" for event in capture.events)
    assert not any(event.kind == "experiment_not_started" for event in capture.events)


def test_main_flow_preexisting_confirmation_is_rejected_but_capture_can_complete(tmp_path: Path) -> None:
    clock = VirtualClock()
    capture, backend = make_live_capture(tmp_path, clock)
    confirmation = tmp_path / "operator.confirmed"
    confirmation.touch()
    fed = {"done": False}

    def sleeper(seconds: float) -> None:
        clock.now += seconds
        if not fed["done"]:
            fed["done"] = True
            capture.feed("CONTROL", lifecycle_lines("CONTROL") + summary_line("CONTROL"))
            capture.feed("DUT", lifecycle_lines("DUT") + summary_line("DUT"))

    exit_code, manifest = run_live_capture(
        capture,
        backend,
        confirmation,
        operator_timeout_s=30.0,
        clock=clock,
        sleeper=sleeper,
        output=lambda _message: None,
    )

    assert exit_code == 0
    assert manifest["capture_valid"] is True
    assert any(event.kind == "operator_confirmation_rejected" for event in capture.events)
    assert not any(event.kind == "operator_confirmed" for event in capture.events)


def test_main_flow_fatal_capture_stops_and_preserves_invalid_evidence(tmp_path: Path) -> None:
    clock = VirtualClock()
    capture, backend = make_live_capture(tmp_path, clock)
    confirmation = tmp_path / "operator.confirmed"
    steps = {"count": 0}

    def sleeper(seconds: float) -> None:
        clock.now += seconds
        steps["count"] += 1
        if steps["count"] == 1:
            capture.feed("CONTROL", lifecycle_lines("CONTROL"))
            capture.feed("DUT", lifecycle_lines("DUT"))
        elif steps["count"] == 2:
            capture.update_port_state("CONTROL", False)

    exit_code, manifest = run_live_capture(
        capture,
        backend,
        confirmation,
        operator_timeout_s=30.0,
        duration_s=60.0,
        poll_s=0.05,
        clock=clock,
        sleeper=sleeper,
        output=lambda _message: None,
    )

    assert exit_code == 1
    assert manifest["capture_valid"] is False
    assert any(event.kind == "capture_terminal_fatal" for event in capture.events)
    assert any(event.kind == "capture_interrupted" for event in capture.events)
    assert backend.stopped and backend.closed
