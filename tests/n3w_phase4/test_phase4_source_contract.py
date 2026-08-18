from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
LAB = ROOT / "firmware/esphome_rc/board_lab/n3w_phase4_physical"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_concrete_driver_accepts_new_single_frame_budget_without_rewriting_legacy_contract() -> None:
    radio_header = text(CORE / "n3w_radio.h")
    assert "kEspNowSingleFramePayloadBytes = 220" in radio_header
    assert "kEspNowPhysicalDatagramLimit = 250" in radio_header
    assert "kDataFragmentPayloadBytes = 180" in radio_header


def test_simplified_runtime_reuses_connected_sta_channel_without_init_thrash() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")
    header = text(CORE / "n3w_simple_product_component.h")
    start = source.index("bool SimpleProductComponent::start_runtime_if_ready_()")
    end = source.index("void SimpleProductComponent::advance_pairing_()", start)
    body = source[start:end]

    retry_gate = body.index(
        "now - last_radio_attempt_ms_ < kRadioRetryIntervalMs"
    )
    current_channel = body.index("esp_wifi_get_channel")
    initialize = body.index("radio_.initialize")
    broadcast_peer = body.index("radio_.prepare_broadcast_peer")

    assert retry_gate < current_channel < initialize < broadcast_peer
    assert "radio_.set_channel" not in body
    assert "ESP-NOW initialization failed error=%u" in body
    assert "ESP-NOW broadcast peer configuration failed error=%u" in body
    assert "Simplified N3-W runtime start failed error=%u" in body
    assert "bool radio_attempted_{false};" in header
    assert "uint64_t last_radio_attempt_ms_{0};" in header


def test_simplified_port_never_mutates_an_associated_sta_channel() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")
    runtime = text(CORE / "n3w_simple_product_runtime.cpp")

    start = source.index("bool SimpleProductComponent::set_radio_channel(uint8_t channel)")
    end = source.index("bool SimpleProductComponent::broadcast_control", start)
    body = source[start:end]

    wifi_gate = body.index("if (wifi_connected())")
    observe_channel = body.index("esp_wifi_get_channel", wifi_gate)
    same_channel_success = body.index("return current_channel == channel", observe_channel)
    driver_mutation = body.index("return radio_.set_channel(channel)", same_channel_success)

    assert wifi_gate < observe_channel < same_channel_success < driver_mutation
    assert body.count("radio_.set_channel(channel)") == 1
    assert body.count("esp_wifi_get_channel") == 1

    runtime_start = runtime.index("SimpleProductError SimpleProductRuntime::start(")
    runtime_stop = runtime.index("void SimpleProductRuntime::stop()", runtime_start)
    runtime_body = runtime[runtime_start:runtime_stop]

    # Runtime start intentionally keeps the generic port contract. The concrete
    # ESP32 product adapter must make an idempotent request for the already-owned
    # STA channel a no-op, so this indirect path can no longer reach
    # esp_wifi_set_channel() while associated.
    assert "port_->set_radio_channel(direct_channel_)" in runtime_body


def test_generic_phase4_target_is_role_neutral_and_first_use_ready() -> None:
    config = text(LAB / "generic.yml")
    lowered = config.lower()

    assert "role:" not in lowered
    assert "node_id:" not in lowered
    assert "gateway_id:" not in lowered
    assert "peer_mac:" not in lowered
    assert "manager_host:" not in lowered
    assert "mqtt_username:" not in lowered
    assert "mqtt_password:" not in lowered
    assert "activation_enabled: true" in lowered
