from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path


MODULE_PATH = Path(__file__).parents[2] / "experiments" / "n3w_r1r4_host_capture_orchestrator.py"
SPEC = importlib.util.spec_from_file_location("r1r4_capture", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules["r1r4_capture"] = module
SPEC.loader.exec_module(module)

DualCapture = module.DualCapture
RoleBinding = module.RoleBinding
SerialBackend = module.SerialBackend
run_live_capture_window = module._run_live_capture_window


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000_000

    def __call__(self) -> int:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += int(seconds * 1_000_000_000)


def make_capture(tmp_path: Path, clock: Clock) -> object:
    return DualCapture(
        tmp_path,
        [RoleBinding("CONTROL", "control-usb"), RoleBinding("DUT", "dut-usb")],
        heartbeat_timeout_s=2,
        summary_timeout_s=5,
        clock_ns=clock,
    )


def ready(capture: object) -> None:
    assert capture.mark_reader_ready("CONTROL", "control-usb")
    assert capture.mark_reader_ready("DUT", "dut-usb")
    assert capture.begin_host_capture()
    assert capture.begin_experiment()


def line(role: str, *, result: str = "PASS") -> bytes:
    if role == "CONTROL":
        summary = f"R1R3_SUMMARY role=CONTROL baseline={result} probe_tx_api={result} home_ack={result}"
    else:
        summary = (
            f"R1R3_SUMMARY role=DUT baseline={result} roc_req={result} probe_rx={result} "
            f"roc_cancel={result} home_recovery={result} home_ack_tx={result} disconnect_count=0"
        )
    return (
        f"R1R4_CAPTURE_HEARTBEAT role={role}\n"
        f"R1R4_LIFECYCLE_GATE_OPEN role={role}\n"
        f"{summary}\n"
    ).encode()


def test_normal_two_board_run_separates_summary_from_pass(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    ready(capture)
    capture.feed("CONTROL", line("CONTROL"))
    capture.feed("DUT", line("DUT"))
    manifest = capture.finalize()

    assert manifest["collector_ready"] == {"CONTROL": True, "DUT": True}
    assert manifest["summary_seen"] == {"CONTROL": True, "DUT": True}
    assert manifest["summaries_complete"] is True
    assert manifest["capture_completeness"] == "COMPLETE"
    assert manifest["capture_valid"] is True
    assert "experiment_pass" not in manifest
    assert manifest["observed_lifecycle_results"]["CONTROL"] == {
        "baseline": "PASS", "probe_tx_api": "PASS", "home_ack": "PASS"
    }
    assert (tmp_path / "control.raw").read_bytes()
    assert (tmp_path / "dut.raw").read_bytes()
    assert (tmp_path / "host.events.jsonl").read_text(encoding="utf-8")
    assert any(event.kind == "experiment_start_observed" for event in capture.events)


def test_summary_without_explicit_pass_is_not_product_pass(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    ready(capture)
    capture.feed("CONTROL", b"R1R3_SUMMARY role=CONTROL baseline=PASS probe_tx_api=FAIL home_ack=FAIL\n")
    capture.feed("DUT", b"R1R3_SUMMARY role=DUT baseline=PASS roc_req=FAIL probe_rx=FAIL roc_cancel=FAIL home_recovery=FAIL home_ack_tx=FAIL disconnect_count=4\n")
    manifest = capture.finalize()

    assert manifest["summaries_complete"] is True
    assert manifest["capture_completeness"] == "INCOMPLETE"
    assert manifest["capture_valid"] is False
    assert manifest["observed_lifecycle_results"]["DUT"]["disconnect_count"] == "4"


def test_complete_capture_preserves_failed_lifecycle_fields_without_verdict(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    ready(capture)
    capture.feed("CONTROL", line("CONTROL", result="FAIL"))
    capture.feed("DUT", line("DUT", result="FAIL"))
    manifest = capture.finalize()

    assert manifest["capture_completeness"] == "COMPLETE"
    assert manifest["capture_valid"] is True
    assert manifest["product_experiment_result"] == "REQUIRES_RAW_LOG_REVIEW"
    assert manifest["observed_lifecycle_results"]["CONTROL"]["home_ack"] == "FAIL"
    assert manifest["observed_lifecycle_results"]["DUT"]["probe_rx"] == "FAIL"


def test_single_endpoint_no_data_records_log_missing(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    ready(capture)
    capture.feed("CONTROL", line("CONTROL"))
    clock.advance(3)
    manifest = capture.finalize(now_ns=clock.now)

    assert manifest["data_seen"] == {"CONTROL": True, "DUT": False}
    assert any(event.kind == "log_missing" and event.role == "DUT" for event in capture.events)
    assert manifest["capture_valid"] is False


def test_startup_heartbeat_missing_is_not_hidden_by_lifecycle_gate(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    ready(capture)
    capture.feed("CONTROL", b"R1R4_LIFECYCLE_GATE_OPEN role=CONTROL\n")
    capture.feed("DUT", b"R1R4_CAPTURE_HEARTBEAT role=DUT\n")
    manifest = capture.finalize()

    assert any(event.kind == "experiment_start_observed" for event in capture.events)
    assert any(
        event.kind == "experiment_started"
        and event.details["startup_heartbeat_missing"] == ["CONTROL", "DUT"]
        for event in capture.events
    )
    assert manifest["summaries_complete"] is False


def test_disconnect_reconnect_is_recorded_and_missing_summary_is_separate(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    ready(capture)
    capture.feed("CONTROL", line("CONTROL"))
    capture.update_port_state("DUT", False)
    capture.update_port_state("DUT", True, "dut-usb")
    clock.advance(6)
    manifest = capture.finalize(now_ns=clock.now)

    assert any(event.kind == "port_disconnected" and event.role == "DUT" for event in capture.events)
    assert any(event.kind == "port_reconnected" and event.role == "DUT" for event in capture.events)
    assert any(event.kind == "summary_missing" and event.role == "DUT" for event in capture.events)
    assert manifest["summaries_complete"] is False
    assert manifest["capture_completeness"] == "INCOMPLETE"


def test_lifecycle_gate_cannot_be_used_as_prestart_barrier(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    capture.mark_reader_ready("CONTROL", "control-usb")
    capture.mark_reader_ready("DUT", "dut-usb")
    capture.feed("CONTROL", b"R1R4_LIFECYCLE_GATE_OPEN role=CONTROL\n")

    assert not capture.host_started
    assert any(event.kind == "lifecycle_gate_before_host_start" for event in capture.events)
    assert not capture.begin_experiment()


def test_duplicate_binding_and_nonempty_output_are_rejected(tmp_path: Path) -> None:
    try:
        DualCapture(tmp_path / "duplicate", [RoleBinding("CONTROL", "same"), RoleBinding("DUT", "same")])
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate device binding accepted")
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "old.raw").write_bytes(b"old")
    try:
        DualCapture(occupied, [RoleBinding("CONTROL", "c"), RoleBinding("DUT", "d")])
    except ValueError as exc:
        assert "new and empty" in str(exc)
    else:
        raise AssertionError("non-empty output directory accepted")


def test_role_swap_is_rejected_and_capture_is_incomplete(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    ready(capture)
    capture.feed("CONTROL", b"R1R4_CAPTURE_HEARTBEAT role=DUT\n")
    manifest = capture.finalize()

    assert any(event.kind == "role_mismatch" for event in capture.events)
    assert manifest["capture_valid"] is False


class FakeSerial:
    def __init__(self, chunks: list[bytes] | None = None, failures: int = 0) -> None:
        self.chunks = list(chunks or [])
        self.failures = failures
        self.closed = False

    def read(self, size: int) -> bytes:
        del size
        if self.chunks:
            return self.chunks.pop(0)
        if self.failures:
            self.failures -= 1
            raise OSError("simulated disconnect")
        return b""

    def close(self) -> None:
        self.closed = True


def test_serial_backend_uses_non_toggling_lines_and_reconnects(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    created: list[dict[str, object]] = []
    connections = {
        "control-port": [FakeSerial([line("CONTROL")])],
        "dut-port": [FakeSerial([b"ESP-ROM: initial\n"], failures=1), FakeSerial([b"ESP-ROM: rebooted\n"])],
    }

    def factory(port: str, **kwargs: object) -> FakeSerial:
        created.append({"port": port, **kwargs})
        return connections[port].pop(0)

    backend = SerialBackend(
        capture,
        {"CONTROL": "control-port", "DUT": "dut-port"},
        serial_factory=factory,
        identity_lookup=lambda port: {"control-port": "control-usb", "dut-port": "dut-usb"}[port],
        reconnect_timeout_s=0,
        clock_ns=clock,
    )
    assert backend.open_all()
    assert capture.begin_host_capture()
    assert capture.begin_experiment()
    backend.poll_once()
    backend.poll_once()
    backend.poll_once()
    backend.poll_once()
    manifest = capture.finalize()

    assert all(item["dsrdtr"] is False and item["rtscts"] is False for item in created)
    assert any(event.kind == "port_disconnected" and event.role == "DUT" for event in capture.events)
    assert any(event.kind == "port_reconnected" and event.role == "DUT" for event in capture.events)
    assert any(event.kind == "capture_interrupted" and event.role == "DUT" for event in capture.events)
    assert manifest["capture_valid"] is False
    backend.close_all()


def test_live_window_runs_without_operator_input_and_is_bounded(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    capture.mark_reader_ready("CONTROL", "control-usb")
    capture.mark_reader_ready("DUT", "dut-usb")
    assert capture.begin_host_capture()
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.advance(max(seconds, 0.001))

    run_live_capture_window(capture, duration_s=0.05, clock=lambda: clock.now / 1_000_000_000, sleeper=sleep)
    manifest = capture.finalize(now_ns=clock.now)

    assert capture.experiment_started is True
    assert sleeps
    assert any(event.kind == "experiment_started" for event in capture.events)
    assert manifest["capture_valid"] is False


def test_live_cli_has_no_enter_gate_and_keeps_sixty_second_window() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "LIVE_CAPTURE_DURATION_S = 60.0" in source
    assert "_wait_for_operator_confirmation" not in source
    assert "operator-timeout-s" not in source
    assert "fixed 60-second capture window started; no operator input required" in source


def test_multiple_initial_boot_lines_are_allowed_before_heartbeat(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    ready(capture)
    capture.feed(
        "CONTROL",
        b"ESP-ROM: first\nrst:0x1\n" + line("CONTROL"),
    )
    capture.feed("DUT", line("DUT"))
    manifest = capture.finalize()

    assert manifest["boot_marker_count"]["CONTROL"] == 2
    assert manifest["device_reboot_detected"]["CONTROL"] is False
    assert manifest["capture_valid"] is True


def test_reader_loop_writes_raw_during_operator_confirmation_window(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    connections = {"control-port": FakeSerial([b"R1R4_CAPTURE_HEARTBEAT role=CONTROL\n"]), "dut-port": FakeSerial()}

    backend = SerialBackend(
        capture,
        {"CONTROL": "control-port", "DUT": "dut-port"},
        serial_factory=lambda port, **kwargs: connections[port],
        identity_lookup=lambda port: {"control-port": "control-usb", "dut-port": "dut-usb"}[port],
        clock_ns=clock,
    )
    assert backend.open_all()
    assert backend.start_reader_loop()
    assert capture.begin_host_capture()
    time.sleep(0.06)
    assert (tmp_path / "control.raw").read_bytes()
    assert not capture.experiment_started
    backend.stop_reader_loop()
    backend.close_all()
    capture.finalize()


def test_disconnect_after_prestart_bytes_before_enter_invalidates_capture(tmp_path: Path) -> None:
    clock = Clock()
    capture = make_capture(tmp_path, clock)
    capture.mark_reader_ready("CONTROL", "control-usb")
    capture.mark_reader_ready("DUT", "dut-usb")
    assert capture.begin_host_capture()
    capture.feed("CONTROL", b"R1R4_CAPTURE_HEARTBEAT role=CONTROL\n")
    capture.update_port_state("CONTROL", False)
    capture.update_port_state("CONTROL", True, "control-usb")
    assert capture.begin_experiment()
    capture.feed("CONTROL", b"R1R4_LIFECYCLE_GATE_OPEN control_capture_armed=true dut_capture_ready=true\n")
    capture.feed("CONTROL", b"R1R3_SUMMARY role=CONTROL baseline=PASS probe_tx_api=PASS home_ack=PASS\n")
    capture.feed("DUT", line("DUT"))
    manifest = capture.finalize()

    assert any(event.kind == "capture_interrupted" and event.role == "CONTROL" for event in capture.events)
    assert manifest["capture_interrupted"]["CONTROL"] is True
    assert manifest["capture_valid"] is False
