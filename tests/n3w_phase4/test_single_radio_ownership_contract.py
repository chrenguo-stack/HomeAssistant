from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"


def text(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def test_driver_starts_and_stops_only_the_standalone_wifi_session() -> None:
    header = text("n3w_espnow_driver.h")
    source = text("n3w_espnow_driver.cpp")

    assert "initialize_standalone" in header
    assert "wifi_initialized_by_driver_" in header
    assert "wifi_started_by_driver_" in header
    assert "start_wifi_(bool start_standalone_wifi)" in source
    assert "esp_wifi_set_mode(WIFI_MODE_STA)" in source
    assert "esp_wifi_start()" in source
    assert "if (wifi_started_by_driver_)" in source
    assert "if (wifi_initialized_by_driver_)" in source


def test_relay_mode_disables_sta_reconnect_before_channel_mutation() -> None:
    source = text("n3w_simple_product_component.cpp")
    header = text("n3w_simple_product_component.h")

    claim_start = source.index("bool SimpleProductComponent::claim_relay_radio_()")
    claim_end = source.index("bool SimpleProductComponent::begin_direct_probe_()")
    claim = source[claim_start:claim_end]
    disable = claim.index("global_wifi_component->disable()")
    standalone = claim.index("radio_.initialize_standalone", disable)
    ownership = claim.index("RadioOwnership::RELAY_ESPNOW", standalone)
    assert disable < standalone < ownership

    channel_start = source.index(
        "bool SimpleProductComponent::set_radio_channel(uint8_t channel)"
    )
    channel_end = source.index(
        "bool SimpleProductComponent::broadcast_control", channel_start
    )
    channel = source[channel_start:channel_end]
    claim_gate = channel.index("claim_relay_radio_()")
    mutate = channel.index("radio_.set_channel(channel)", claim_gate)
    assert claim_gate < mutate

    assert "enum class RadioOwnership" in header
    assert "DIRECT_WIFI" in header
    assert "RELAY_ESPNOW" in header
    assert "DIRECT_PROBE" in header


def test_discovery_claims_relay_radio_even_while_sta_remains_associated() -> None:
    source = text("n3w_simple_product_component.cpp")
    channel_start = source.index(
        "bool SimpleProductComponent::set_radio_channel(uint8_t channel)"
    )
    channel_end = source.index(
        "bool SimpleProductComponent::broadcast_control", channel_start
    )
    channel = source[channel_start:channel_end]

    discovery_gate = channel.index(
        "runtime_.path_state() != LocalPathState::DIRECT"
    )
    forced_claim = channel.index("!claim_relay_radio_()", discovery_gate)
    associated_sta_gate = channel.index("wifi_connected())", forced_claim)
    assert discovery_gate < forced_claim < associated_sta_gate


def test_direct_probe_pauses_relay_submissions_and_rebinds_on_failure() -> None:
    source = text("n3w_simple_product_component.cpp")
    runtime = text("n3w_simple_product_runtime.cpp")

    loop_start = source.index("void SimpleProductComponent::loop()")
    loop_end = source.index("bool SimpleProductComponent::send_telemetry_json(", loop_start)
    loop = source[loop_start:loop_end]
    probe_gate = loop.index(
        "if (radio_ownership_ == RadioOwnership::DIRECT_PROBE)"
    )
    recovery = loop.index("advance_recovery_();", probe_gate)
    probe_return = loop.index("return;", recovery)
    runtime_tick = loop.index("runtime_.tick()", probe_return)
    assert probe_gate < recovery < probe_return < runtime_tick

    telemetry_start = source.index("bool SimpleProductComponent::send_telemetry_json(")
    telemetry_end = source.index(
        "bool SimpleProductComponent::read_local_mac_()", telemetry_start
    )
    telemetry = source[telemetry_start:telemetry_end]
    assert "RadioOwnership::DIRECT_PROBE" in telemetry
    assert "runtime_.challenge_pending()" in source

    channel_start = source.index(
        "bool SimpleProductComponent::set_radio_channel(uint8_t channel)"
    )
    channel_end = source.index(
        "bool SimpleProductComponent::broadcast_control", channel_start
    )
    channel = source[channel_start:channel_end]
    assert "RadioOwnership::DIRECT_PROBE &&\n      !wifi_connected()" in channel
    assert "radio_ownership_ == RadioOwnership::DIRECT_PROBE) &&\n      wifi_connected()" in channel

    restore_start = source.index("bool SimpleProductComponent::restore_relay_radio_()")
    restore_end = source.index(
        "void SimpleProductComponent::drain_send_completions_()", restore_start
    )
    restore = source[restore_start:restore_end]
    assert restore.index("global_wifi_component->disable()") < restore.index(
        "radio_.initialize_standalone"
    )
    assert "runtime_.rebind_radio_state()" in restore

    rebind_start = runtime.index(
        "SimpleProductError SimpleProductRuntime::rebind_radio_state()"
    )
    rebind_end = runtime.index(
        "bool SimpleProductRuntime::update_direct_channel_hint", rebind_start
    )
    rebind = runtime[rebind_start:rebind_end]
    assert "port_->set_radio_channel(channel)" in rebind
    assert "port_->install_encrypted_peer(" in rebind


def test_challenge_uses_fixed_owned_channel_and_pending_accept_window() -> None:
    runtime = text("n3w_simple_product_runtime.cpp")
    start = runtime.index("SimpleProductError SimpleProductRuntime::handle_discovery_(")
    end = runtime.index(
        "SimpleProductError SimpleProductRuntime::handle_challenge_(", start
    )
    challenge = runtime[start:end]

    channel_fix = challenge.index("port_->set_radio_channel(channel)")
    normal_send = challenge.index(
        "port_->broadcast_control(encoded.data(), encoded.size())", channel_fix
    )
    pending = challenge.index("pending_challenge_ = std::move(pending)", normal_send)

    assert channel_fix < normal_send < pending
    assert "broadcast_control_on_channel" not in challenge
    assert "2ULL * policy_.challenge_timeout_ms" in challenge
    assert "owns and holds this channel" in challenge


def test_direct_failback_commits_only_after_concrete_radio_restore() -> None:
    runtime = text("n3w_simple_product_runtime.cpp")

    note_start = runtime.index(
        "SimpleProductError SimpleProductRuntime::note_direct_recovery_probe"
    )
    note_end = runtime.index(
        "SimpleProductError SimpleProductRuntime::note_relay_delivery_result",
        note_start,
    )
    note = runtime[note_start:note_end]

    readiness = note.index("path_.direct_recovery_would_commit_on_success()")
    restore = note.index("restore_direct_()", readiness)
    reset_hysteresis = note.index(
        "path_.note_direct_recovery_probe(false)", restore
    )
    logical_commit = note.index(
        "path_.note_direct_recovery_probe(success)", reset_hysteresis
    )
    assert readiness < restore < reset_hysteresis < logical_commit

    restore_start = runtime.index("SimpleProductError SimpleProductRuntime::restore_direct_()")
    restore_end = runtime.index(
        "SimpleProductError SimpleProductRuntime::handle_discovery_(", restore_start
    )
    restore_body = runtime[restore_start:restore_end]

    radio_first = restore_body.index("port_->set_radio_channel(direct_channel_)")
    pending_reset = restore_body.index("pending_challenge_.reset()", radio_first)
    relay_remove = restore_body.index("port_->remove_peer", pending_reset)
    assert radio_first < pending_reset < relay_remove


def test_accept_fixes_relay_channel_before_peer_and_state_commit() -> None:
    runtime = text("n3w_simple_product_runtime.cpp")
    start = runtime.index("SimpleProductError SimpleProductRuntime::handle_accept_(")
    end = runtime.index(
        "SimpleProductError SimpleProductRuntime::handle_compact_(", start
    )
    accept = runtime[start:end]

    channel_fix = accept.index("port_->set_radio_channel(channel)")
    peer_bind = accept.index("port_->install_encrypted_peer(", channel_fix)
    state_commit = accept.index("path_.note_authenticated_relay_ready(true)", peer_bind)
    active_bind = accept.index("active_relay_ = std::move(relay)", state_commit)
    assert channel_fix < peer_bind < state_commit < active_bind
