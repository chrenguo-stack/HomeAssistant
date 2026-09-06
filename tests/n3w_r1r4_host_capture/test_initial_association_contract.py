from __future__ import annotations

from pathlib import Path


SOURCE = (
    Path(__file__).parents[2]
    / "diagnostics"
    / "n3w_r1r4_usb_console_evidence"
    / "main"
    / "r1r4_usb_console_evidence_main.c"
).read_text(encoding="utf-8")


def test_initial_association_retry_is_bounded_and_observable() -> None:
    assert "R1R3_INITIAL_ASSOC_MAX_ATTEMPTS 3" in SOURCE
    assert "R1R3_INITIAL_ASSOC_TIMEOUT_MS 15000" in SOURCE
    assert "R1R3_INITIAL_ASSOC_ATTEMPT_WAIT_MS 5000" in SOURCE
    assert "R1R3_STAGE_ATTEMPT stage=INITIAL_ASSOCIATION" in SOURCE
    assert "api_result=%s disconnect_reason=%u" in SOURCE
    assert "R1R3_STAGE_TIMEOUT stage=INITIAL_ASSOCIATION" in SOURCE


def test_initial_association_success_stops_before_baseline_and_roc() -> None:
    helper = SOURCE[SOURCE.index("static bool wait_initial_association"):]
    success = helper.index("R1R3_STAGE_RESULT stage=INITIAL_ASSOCIATION result=PASS")
    return_stmt = helper.index("return true;", success)
    next_attempt = helper.find("s_initial_assoc_attempts++", success + 1)
    assert next_attempt == -1 or next_attempt > return_stmt
    assert "R1R3_STAGE_RESULT stage=BASELINE result=PASS" in SOURCE
    assert "R1R3_STAGE_RESULT stage=OFFCHANNEL result=EXECUTED" in SOURCE


def test_initial_association_exhaustion_marks_later_stages_not_executed() -> None:
    timeout = SOURCE.index("R1R3_STAGE_TIMEOUT stage=INITIAL_ASSOCIATION")
    tail = SOURCE[timeout:]
    assert "R1R3_STAGE_NOT_EXECUTED stage=BASELINE reason=INITIAL_ASSOCIATION_TIMEOUT" in tail
    assert "R1R3_STAGE_NOT_EXECUTED stage=OFFCHANNEL reason=BASELINE_NOT_REACHED" in tail
    assert "R1R3_STAGE_TIMEOUT stage=BASELINE" in SOURCE
    assert "R1R3_STAGE_NOT_EXECUTED stage=OFFCHANNEL reason=BASELINE_TIMEOUT" in SOURCE
    assert "R1R3_OFFCHANNEL_START_TIMEOUT_MS 15000" in SOURCE
    assert "R1R3_STAGE_TIMEOUT stage=OFFCHANNEL" in SOURCE


def test_offchannel_contract_parameters_are_unchanged() -> None:
    for token in (
        "#define R1R3_HOME_CHANNEL 1",
        "#define R1R3_TARGET_CHANNEL 6",
        "#define R1R3_ROC_WAIT_MS 3000",
        "esp_now_remain_on_channel(&cfg)",
        "esp_now_switch_channel_tx(cfg)",
        "WIFI_ROC_REQ",
        "WIFI_ROC_CANCEL",
        "request_op_id",
        "driver_op_id",
        "WIFI_EVENT_ACTION_TX_STATUS",
        "WIFI_EVENT_ROC_DONE",
    ):
        assert token in SOURCE
    assert "R1R3_ROC_OP_ID" not in SOURCE


def test_driver_operation_id_is_saved_and_reused_for_cancel() -> None:
    assert "roc_request(\n        R1R3_TARGET_CHANNEL, request_op_id, &s_roc_driver_op_id)" in SOURCE
    assert "roc_cancel(R1R3_TARGET_CHANNEL, s_roc_driver_op_id)" in SOURCE
    assert "cancel_request_driver_op_id" in SOURCE
    assert "WIFI_EVENT_ACTION_TX_STATUS" in SOURCE
    assert "WIFI_EVENT_ROC_DONE" in SOURCE
    assert "R1R4_OPERATION_TIMEOUT" in SOURCE
    assert "R1R4_OP_EVENT_QUEUE_OVERFLOW" in SOURCE


def test_control_home_return_uses_actual_channel_not_event_channel() -> None:
    assert "R1R4_HOME_CHANNEL_CHECK" in SOURCE
    assert "control_home_channel" in SOURCE
    assert "control_home_return" in SOURCE
    assert "control_home_channel=6" not in SOURCE


def test_dut_completion_is_shared_with_minimal_c_decision_harness() -> None:
    state_header = (
        Path(__file__).parents[2]
        / "diagnostics"
        / "n3w_r1r4_usb_console_evidence"
        / "main"
        / "r1r4_operation_state.h"
    ).read_text(encoding="utf-8")
    for token in (
        "r1r4_termination_trusted",
        "r1r4_should_clear_roc_active",
        "r1r4_should_continue_home_recovery",
        "r1r4_should_send_home_ack",
        "ROC_TERMINATION_UNCONFIRMED",
        "home_recovery=NOT_EXECUTED",
        "home_ack_tx=NOT_EXECUTED",
    ):
        assert token in state_header or token in SOURCE
