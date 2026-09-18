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
    assert "RELAY_RESTORE" in header


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


def test_recovery_probe_checks_ap_presence_and_buffers_business_telemetry() -> None:
    source = text("n3w_simple_product_component.cpp")
    header = text("n3w_simple_product_component.h")

    advance_start = source.index("void SimpleProductComponent::advance_recovery_()")
    advance_end = source.index(
        "bool SimpleProductComponent::claim_relay_radio_()", advance_start
    )
    advance = source[advance_start:advance_end]
    presence = advance.index("probe_direct_ap_presence_()")
    full_verify = advance.index("begin_direct_probe_()", presence)
    assert presence < full_verify
    assert "schedule_recovery_probe_(true)" in advance

    probe_start = source.index(
        "SimpleProductComponent::probe_direct_ap_presence_()"
    )
    probe_end = source.index(
        "void SimpleProductComponent::schedule_recovery_probe_", probe_start
    )
    probe = source[probe_start:probe_end]
    scan = probe.index("esp_wifi_scan_start(&scan, true)")
    restore = probe.index("radio_.set_channel(relay_channel)", scan)
    assert scan < restore
    assert "WIFI_SCAN_TYPE_PASSIVE" in probe
    assert "kDirectPresenceProbePassiveMs" in probe

    telemetry_start = source.index("bool SimpleProductComponent::send_telemetry_json(")
    telemetry_end = source.index(
        "bool SimpleProductComponent::read_local_mac_()", telemetry_start
    )
    telemetry = source[telemetry_start:telemetry_end]
    assert "enqueue_telemetry_" in telemetry
    assert "!telemetry_queue_.empty()" in telemetry
    assert "return false;" not in telemetry

    flush_start = source.index("void SimpleProductComponent::flush_telemetry_queue_()")
    flush_end = source.index("bool SimpleProductComponent::restore_relay_radio_()", flush_start)
    flush = source[flush_start:flush_end]
    assert "telemetry_queue_.front()" in flush
    assert "telemetry_queue_.pop_front()" in flush
    assert "kTelemetryQueueCapacity = 8" in header
    assert "kRecoveryProbeBackoffMaxMs = 600000" in header


def test_relay_restore_failure_is_rate_limited_and_transactional() -> None:
    source = text("n3w_simple_product_component.cpp")
    runtime = text("n3w_simple_product_runtime.cpp")

    retry_start = source.index("void SimpleProductComponent::advance_relay_restore_()")
    retry_end = source.index(
        "bool SimpleProductComponent::enqueue_telemetry_", retry_start
    )
    retry = source[retry_start:retry_end]
    assert "next_relay_restore_attempt_ms_" in retry
    assert "kRelayRestoreRetryFastMs" in retry
    assert "kRelayRestoreRetrySlowMs" in retry

    restore_start = source.index("bool SimpleProductComponent::restore_relay_radio_()")
    restore_end = source.index(
        "void SimpleProductComponent::drain_send_completions_()", restore_start
    )
    restore = source[restore_start:restore_end]
    initialize = restore.index("radio_.initialize_standalone")
    rebind = restore.index("runtime_.rebind_radio_state()", initialize)
    ownership = restore.index("RadioOwnership::RELAY_ESPNOW", rebind)
    assert initialize < rebind < ownership

    rebind_start = runtime.index(
        "SimpleProductError SimpleProductRuntime::rebind_radio_state()"
    )
    rebind_end = runtime.index(
        "bool SimpleProductRuntime::update_direct_channel_hint", rebind_start
    )
    rebind_body = runtime[rebind_start:rebind_end]
    assert "port_->set_radio_channel(channel)" in rebind_body
    assert "port_->install_encrypted_peer(" in rebind_body


def test_channel_commit_requires_readback_and_unknown_is_not_faked() -> None:
    driver = text("n3w_espnow_driver.cpp")
    diagnostics = text("n3w_lab_diagnostics.cpp")

    set_start = driver.index("DriverError EspNowDriver::set_channel(uint8_t channel)")
    set_end = driver.index("DriverError EspNowDriver::prepare_broadcast_peer", set_start)
    set_body = driver[set_start:set_end]
    set_call = set_body.index("esp_wifi_set_channel")
    get_call = set_body.index("esp_wifi_get_channel", set_call)
    mismatch = set_body.index("observed != channel", get_call)
    success = set_body.index("return DriverError::NONE", mismatch)
    assert set_call < get_call < mismatch < success

    assert "snapshot_.current_channel = observed;" in diagnostics
    assert "observed != 0U ? observed : requested" not in diagnostics


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
