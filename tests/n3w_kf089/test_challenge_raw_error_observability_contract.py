from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DRIVER_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_espnow_driver.h"
DRIVER_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_espnow_driver.cpp"
RUNTIME_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.h"
RUNTIME_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_runtime.cpp"
COMPONENT_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.h"
DIAG_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_lab_diagnostics.h"
DIAG_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_lab_diagnostics.cpp"
GENERIC = ROOT / "firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"
RADIO_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.h"


def test_challenge_submit_raw_error_observability_contract():
    driver_h = DRIVER_H.read_text(encoding="utf-8")
    driver_cpp = DRIVER_CPP.read_text(encoding="utf-8")
    runtime_h = RUNTIME_H.read_text(encoding="utf-8")
    runtime_cpp = RUNTIME_CPP.read_text(encoding="utf-8")
    component_h = COMPONENT_H.read_text(encoding="utf-8")
    diag_h = DIAG_H.read_text(encoding="utf-8")
    diag_cpp = DIAG_CPP.read_text(encoding="utf-8")
    generic = GENERIC.read_text(encoding="utf-8")

    assert "DriverError last_broadcast_send_error() const" in driver_h
    assert "int32_t last_broadcast_send_error_raw() const" in driver_h
    assert "last_broadcast_send_error_{DriverError::NONE}" in driver_h
    assert "last_broadcast_send_error_raw_{0}" in driver_h

    assert "const esp_err_t send_result =" in driver_cpp
    assert "esp_now_send(kEspNowBroadcastMac.data(), data, size)" in driver_cpp
    assert (
        "last_broadcast_send_error_raw_ = "
        "static_cast<int32_t>(send_result);"
    ) in driver_cpp
    assert "send_result == ESP_OK ? DriverError::NONE : DriverError::SEND_FAILED" in driver_cpp

    assert "last_broadcast_send_error_code() const" in runtime_h
    assert "last_broadcast_send_error_raw() const" in runtime_h
    assert "on_challenge_submit_result(" in runtime_h

    assert "const SimpleRuntimeError encode_result =" in runtime_cpp
    assert "challenge_driver_error = port_->last_broadcast_send_error_code();" in runtime_cpp
    assert "challenge_raw_error = port_->last_broadcast_send_error_raw();" in runtime_cpp
    assert "diagnostic_sink_->on_challenge_submit_result(" in runtime_cpp

    assert "last_broadcast_send_error_code() const override" in component_h
    assert "radio_.last_broadcast_send_error()" in component_h
    assert "radio_.last_broadcast_send_error_raw()" in component_h

    assert "challenge_submit_failure_count{0}" in diag_h
    assert "challenge_submit_first_driver_error{0}" in diag_h
    assert "challenge_submit_last_driver_error{0}" in diag_h
    assert "challenge_submit_first_error_raw{0}" in diag_h
    assert "challenge_submit_last_error_raw{0}" in diag_h
    assert "N3wLabDiagnostics::on_challenge_submit_result(" in diag_cpp

    for token in (
        "challenge_submit_failure_count",
        "challenge_submit_first_driver_error",
        "challenge_submit_last_driver_error",
        "challenge_submit_first_error_raw",
        "challenge_submit_last_error_raw",
    ):
        assert f'\\"{token}\\":' in generic


def test_raw_error_observability_does_not_change_persisted_diag_schema():
    diag_h = DIAG_H.read_text(encoding="utf-8")

    assert "static constexpr uint16_t kSchemaVersion = 5U;" in diag_h

    snapshot_tail = diag_h.split("struct Snapshot {", 1)[1]
    latency_tail = diag_h.split("struct LatencySnapshot {", 1)[1]

    assert "\n  };" in snapshot_tail
    assert "\n  };" in latency_tail

    snapshot_block = snapshot_tail.split("\n  };", 1)[0]
    latency_block = latency_tail.split("\n  };", 1)[0]

    assert "challenge_submit_" not in snapshot_block
    assert "challenge_submit_failure_count" in latency_block
    assert "challenge_submit_first_error_raw" in latency_block
    assert "challenge_submit_last_error_raw" in latency_block


def test_failover_policy_is_unchanged():
    radio_h = RADIO_H.read_text(encoding="utf-8")
    runtime_h = RUNTIME_H.read_text(encoding="utf-8")

    assert "direct_failures_to_discovery{3}" in radio_h
    assert "direct_recoveries_to_direct{2}" in radio_h
    assert "relay_failures_to_discovery{2}" in radio_h

    assert "std::vector<uint8_t> allowed_channels{1, 6, 11};" in runtime_h
    assert "uint32_t scan_dwell_ms{250};" in runtime_h
    assert "uint32_t challenge_timeout_ms{1500};" in runtime_h
    assert "uint32_t relay_advertisement_interval_ms{2000};" in runtime_h
