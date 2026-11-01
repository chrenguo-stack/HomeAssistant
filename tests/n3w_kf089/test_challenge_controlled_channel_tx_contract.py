from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"

DRIVER_H = CORE / "n3w_espnow_driver.h"
DRIVER_CPP = CORE / "n3w_espnow_driver.cpp"
RUNTIME_H = CORE / "n3w_simple_product_runtime.h"
RUNTIME_CPP = CORE / "n3w_simple_product_runtime.cpp"
COMPONENT_H = CORE / "n3w_simple_product_component.h"
RADIO_H = CORE / "n3w_radio.h"


def test_challenge_uses_owned_fixed_channel_tx():
    driver_h = DRIVER_H.read_text(encoding="utf-8")
    driver_cpp = DRIVER_CPP.read_text(encoding="utf-8")
    runtime_h = RUNTIME_H.read_text(encoding="utf-8")
    runtime_cpp = RUNTIME_CPP.read_text(encoding="utf-8")
    component_h = COMPONENT_H.read_text(encoding="utf-8")

    # Keep the lower-level controlled-channel primitive available for bounded
    # diagnostics/legacy callers, but the active PR424 challenge path must not
    # start another temporary off-channel operation once Relay owns the radio.
    assert "DriverError send_broadcast_on_channel(" in driver_h
    assert "virtual bool broadcast_control_on_channel(" in runtime_h
    assert "bool broadcast_control_on_channel(" in component_h
    assert "radio_.send_broadcast_on_channel(" in component_h
    assert "esp_now_switch_channel_tx(config)" in driver_cpp
    assert "config->op_id =" not in driver_cpp

    start = runtime_cpp.index(
        "SimpleProductError SimpleProductRuntime::handle_discovery_("
    )
    end = runtime_cpp.index(
        "SimpleProductError SimpleProductRuntime::handle_challenge_(",
        start,
    )
    challenge_path = runtime_cpp[start:end]

    channel_fix = challenge_path.index("port_->set_radio_channel(channel)")
    normal_send = challenge_path.index(
        "port_->broadcast_control(encoded.data(), encoded.size())", channel_fix
    )
    failure = challenge_path.index("if (!challenge_sent)", normal_send)
    pending = challenge_path.index("pending_challenge_ = std::move(pending)", failure)

    assert channel_fix < normal_send < failure < pending
    assert "broadcast_control_on_channel" not in challenge_path
    assert "2ULL * policy_.challenge_timeout_ms" in challenge_path


def test_relay_advertisement_stays_on_normal_broadcast_path():
    runtime_cpp = RUNTIME_CPP.read_text(encoding="utf-8")

    start = runtime_cpp.index(
        "SimpleProductError SimpleProductRuntime::maybe_advertise_relay_("
    )
    end = runtime_cpp.index(
        "SimpleProductError SimpleProductRuntime::maybe_advance_scan_(",
        start,
    )
    advertisement = runtime_cpp[start:end]

    assert "port_->broadcast_control(encoded.data(), encoded.size())" in advertisement
    assert "broadcast_control_on_channel" not in advertisement


def test_failover_policy_remains_unchanged():
    radio_h = RADIO_H.read_text(encoding="utf-8")
    runtime_h = RUNTIME_H.read_text(encoding="utf-8")

    assert "direct_failures_to_discovery{3}" in radio_h
    assert "direct_recoveries_to_direct{2}" in radio_h
    assert "relay_failures_to_discovery{2}" in radio_h

    assert "std::vector<uint8_t> allowed_channels{1, 6, 11};" in runtime_h
    assert "uint32_t scan_dwell_ms{250};" in runtime_h
    assert "uint32_t challenge_timeout_ms{1500};" in runtime_h
    assert "uint32_t relay_advertisement_interval_ms{2000};" in runtime_h


def test_existing_raw_error_surface_is_preserved():
    driver_h = DRIVER_H.read_text(encoding="utf-8")
    driver_cpp = DRIVER_CPP.read_text(encoding="utf-8")

    assert "last_broadcast_send_error() const" in driver_h
    assert "last_broadcast_send_error_raw() const" in driver_h
    assert "last_broadcast_send_error_raw_ = static_cast<int32_t>(send_result);" in driver_cpp
    assert "send_result == ESP_OK ? DriverError::NONE : DriverError::SEND_FAILED" in driver_cpp
