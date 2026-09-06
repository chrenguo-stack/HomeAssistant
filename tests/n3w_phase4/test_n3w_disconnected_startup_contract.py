from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"


def text(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def function_body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_runtime_start_no_longer_requires_live_wifi_association() -> None:
    source = text("n3w_simple_product_component.cpp")
    header = text("n3w_simple_product_component.h")
    body = function_body(
        source,
        "bool SimpleProductComponent::start_runtime_if_ready_()",
        "void SimpleProductComponent::advance_pairing_()",
    )

    assert "!runtime_state_loaded_ || !mqtt_configured_ || !wifi_connected()" not in body
    assert "if (!runtime_state_loaded_ || !mqtt_configured_)" in body
    assert "const bool direct_available = wifi_connected();" in body
    assert "SimpleProductStartMode::DISCOVERY" in body
    assert "SimpleProductStartMode::DIRECT" in body
    assert "kInitialDirectGraceMs = 15000" in header
    assert "runtime_start_grace_started_" in header
    assert "runtime_start_grace_started_ms_" in header


def test_runtime_has_explicit_discovery_start_semantics() -> None:
    header = text("n3w_simple_product_runtime.h")
    source = text("n3w_simple_product_runtime.cpp")
    radio_header = text("n3w_radio.h")
    radio_source = text("n3w_radio.cpp")

    assert "enum class SimpleProductStartMode" in header
    assert "DIRECT = 0" in header
    assert "DISCOVERY" in header
    assert "SimpleProductStartMode start_mode" in header
    assert "direct_channel == 0 || valid_radio_channel(direct_channel)" in source
    assert "path_.reset(initial_path)" in source
    assert "RadioError reset(LocalPathState initial_state" in radio_header
    assert "RadioError LocalPathController::reset(LocalPathState initial_state)" in radio_source

    start_body = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::start(",
        "void SimpleProductRuntime::stop()",
    )
    assert "LocalPathState::DIRECT : LocalPathState::DISCOVERY" in start_body
    assert "const uint8_t channel = scan_.current();" in start_body
    assert "next_scan_switch_ms_ = now + policy_.scan_dwell_ms;" in start_body


def test_disconnected_channel_scan_rebinds_broadcast_peer_without_mutating_connected_sta() -> None:
    source = text("n3w_simple_product_component.cpp")
    body = function_body(
        source,
        "bool SimpleProductComponent::set_radio_channel(uint8_t channel)",
        "bool SimpleProductComponent::broadcast_control",
    )

    wifi_gate = body.index("if (wifi_connected())")
    same_channel = body.index("return current_channel == channel", wifi_gate)
    driver_switch = body.index("radio_.set_channel(channel)", same_channel)
    broadcast_rebind = body.index("radio_.prepare_broadcast_peer(channel)", driver_switch)
    assert wifi_gate < same_channel < driver_switch < broadcast_rebind


def test_failed_discovery_channel_switch_has_bounded_retry_deadline() -> None:
    source = text("n3w_simple_product_runtime.cpp")
    body = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::maybe_advance_scan_(uint64_t now_ms)",
        "SimpleProductRelayPeer *SimpleProductRuntime::find_relay_child_",
    )

    deadline = body.index("next_scan_switch_ms_ = now_ms + policy_.scan_dwell_ms;")
    advance = body.index("scan_.advance()")
    switch = body.index("port_->set_radio_channel(channel)")
    assert deadline < advance < switch


def test_direct_recovery_rebinds_broadcast_peer_to_recovered_home_channel() -> None:
    source = text("n3w_simple_product_component.cpp")
    body = function_body(
        source,
        "void SimpleProductComponent::advance_recovery_()",
        "void SimpleProductComponent::drain_radio_()",
    )

    observe = body.index("esp_wifi_get_channel")
    rebind = body.index("radio_.prepare_broadcast_peer(channel)", observe)
    update_hint = body.index("runtime_.update_direct_channel_hint(channel)", rebind)
    recovery = body.index("runtime_.note_direct_recovery_probe(direct_ready)", update_hint)
    assert observe < rebind < update_hint < recovery
