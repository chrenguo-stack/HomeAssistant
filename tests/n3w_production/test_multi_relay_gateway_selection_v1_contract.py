from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_core"
TARGET = ROOT / "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_body(source: str, signature: str, next_signature: str) -> str:
    start = source.index(signature)
    end = source.index(next_signature, start)
    return source[start:end]


def test_candidate_window_and_rssi_policy_are_frozen() -> None:
    header = text(CORE / "n3w_simple_product_runtime.h")
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    assert "uint32_t candidate_window_ms{6500};" in header
    assert "int64_t rssi_sum{0};" in header
    assert "uint32_t rssi_sample_count{0};" in header
    assert "bool attempted{false};" in header
    assert "gateway_selection_epoch_" in header

    assert "epoch.deadline_ms = now + policy_.candidate_window_ms;" in source
    assert "same_node->rssi_sum += rssi_dbm;" in source
    assert "++same_node->rssi_sample_count;" in source
    assert "same_node->rssi_sum = rssi_dbm;" in source
    assert "same_node->rssi_sample_count = 1;" in source


def test_strongest_anchored_band_and_stable_hash_contract() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    assert 'constexpr char kGatewaySelectionHashDomain[] = "N3W-GWSEL-V1";' in source
    assert "append_u16be(child_node_id.size());" in source
    assert "append_u16be(relay_node_id.size());" in source
    assert "MBEDTLS_MD_SHA256" in source
    assert "3LL * static_cast<int64_t>(anchor.rssi_sample_count)" in source
    assert "difference > band_limit" in source
    assert "std::lexicographical_compare(" in source
    assert "digest == best_digest &&" in source
    assert "candidate.relay_node_id < candidates[best].relay_node_id" in source


def test_candidate_identity_binding_and_channel_refresh_are_bounded() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    assert "find_gateway_candidate_by_node_(packet.relay_node_id)" in source
    assert "find_gateway_candidate_by_mac_(source)" in source
    assert "same_node->mac != source" in source
    assert "same_mac->relay_node_id != packet.relay_node_id" in source
    assert "same_node->channel != channel" in source
    assert "same_node->rssi_sum = rssi_dbm;" in source


def test_challenge_timeout_fallback_is_candidate_specific() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")
    tick = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::tick()",
        "SimpleProductError SimpleProductRuntime::note_direct_result",
    )

    assert "candidate->attempted = true;" in tick
    assert "pending_challenge_.reset();" in tick
    assert "attempt_next_gateway_candidate_()" in tick
    assert "now >= gateway_selection_epoch_->deadline_ms" in tick


def test_local_challenge_and_accept_failures_do_not_blindly_fall_through() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    attempt = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::attempt_next_gateway_candidate_()",
        "SimpleProductError SimpleProductRuntime::start_challenge_for_candidate_",
    )
    assert "clear_gateway_selection_();" in attempt

    accept = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::handle_accept_(",
        "SimpleProductError SimpleProductRuntime::handle_compact_(",
    )
    assert "pending_challenge_.reset();" in accept
    assert accept.count("clear_gateway_selection_();") >= 4
    assert "(void) port_->remove_peer(source);" in accept


def test_invalid_accept_keeps_pending_until_timeout() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")
    accept = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::handle_accept_(",
        "SimpleProductError SimpleProductRuntime::handle_compact_(",
    )

    mismatch = accept.index(
        "if (source != pending.relay_mac || channel != pending.channel ||"
    )
    verify = accept.index("verify_simple_peer_accept(", mismatch)
    first_pending_reset = accept.index("pending_challenge_.reset();", verify)
    assert mismatch < verify < first_pending_reset


def test_rssi_survives_driver_metadata_ring_and_runtime_boundary() -> None:
    header = text(CORE / "n3w_simple_product_component.h")
    source = text(CORE / "n3w_simple_product_component.cpp")

    assert "int16_t rssi_dbm{-127};" in header
    assert "slot.rssi_dbm = metadata.rssi_dbm;" in source
    assert "slot.channel," in source
    assert "slot.rssi_dbm);" in source


def test_direct_recovery_is_deferred_for_entire_selection_transaction() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")

    recovery = function_body(
        source,
        "void SimpleProductComponent::advance_recovery_()",
        "bool SimpleProductComponent::claim_relay_radio_()",
    )
    assert "if (runtime_.gateway_selection_busy()) return;" in recovery

    probe = function_body(
        source,
        "bool SimpleProductComponent::begin_direct_probe_(",
        "bool SimpleProductComponent::prepare_direct_probe_radio_()",
    )
    assert "runtime_.gateway_selection_busy()" in probe
    assert "runtime_.challenge_pending()" not in probe


def test_no_proactive_roaming_or_dynamic_load_balancing_is_introduced() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    discovery = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::handle_discovery_(",
        "void SimpleProductRuntime::clear_gateway_selection_()",
    )
    assert "path_.state() != LocalPathState::DISCOVERY" in discovery

    relay_result = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::note_relay_delivery_result(",
        "SimpleProductError SimpleProductRuntime::rebind_radio_state()",
    )
    assert "path_.note_relay_result(success)" in relay_result
    assert "leave_relay_for_discovery_()" in relay_result

    assert "active_relay_->" not in source[source.index(
        "SimpleProductError SimpleProductRuntime::select_next_gateway_candidate_"
    ):source.index(
        "SimpleProductError SimpleProductRuntime::attempt_next_gateway_candidate_"
    )]


def test_option_b_single_attempt_queue_contract_is_preserved() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")
    header = text(CORE / "n3w_simple_product_component.h")

    assert "Option B: the queue owns telemetry only while it has not yet received a" in source
    assert "PendingTelemetryState::RELAY_IN_FLIGHT" in source
    assert "telemetry Relay single attempt in-flight" in source
    assert "telemetry single attempt failed; not resending" in source
    assert "Do not convert MAC failure into application resend." in source
    assert "uint32_t submit_count{0};" in header


def test_product_target_still_compiles_the_independent_product_core() -> None:
    target = text(TARGET)
    assert "f1_0_rc2_n3w_target" not in target.lower() or "packages:" in target
    assert "greenhouse_n3w_product_core" in target
    assert "n3w_product_transport.yml" in target
    assert "n3w_product_telemetry.yml" in target


def test_source_scope_does_not_claim_real_sensor_physical_acceptance() -> None:
    # This source-repair gate is a communication/runtime gate. The current
    # physical communication tests have not yet injected live sensor payloads,
    # so this contract deliberately proves transport/selection wiring only.
    source = text(CORE / "n3w_simple_product_runtime.cpp")
    assert "send_telemetry(" in source
    assert "gateway_selection" in source


def test_r2_candidate_capacity_and_transaction_budget_are_frozen() -> None:
    header = text(CORE / "n3w_simple_product_runtime.h")
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    assert "uint32_t gateway_selection_transaction_max_ms{30000};" in header
    assert "std::size_t max_gateway_candidates{8};" in header
    assert "uint64_t transaction_deadline_ms{0};" in header
    assert "CANDIDATE_CAPACITY = 10" in header

    assert "epoch.candidates.reserve(policy_.max_gateway_candidates);" in source
    assert "epoch.transaction_deadline_ms =" in source
    assert "now + policy_.gateway_selection_transaction_max_ms;" in source
    assert (
        "gateway_selection_epoch_->candidates.size() >=\n"
        "            policy_.max_gateway_candidates"
    ) in source
    assert "DiscoveryRejectReason::CANDIDATE_CAPACITY" in source


def test_r2_whole_transaction_deadline_precedes_candidate_timeout_fallback() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")
    tick = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::tick()",
        "SimpleProductError SimpleProductRuntime::note_direct_result",
    )

    transaction_check = tick.index(
        "now >= gateway_selection_epoch_->transaction_deadline_ms"
    )
    pending_timeout = tick.index("now >= pending_challenge_->expires_at_ms")
    assert transaction_check < pending_timeout
    assert "start_full_scan_(now, false)" in tick
    assert "begin_discovery_()" in tick

    attempt = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::attempt_next_gateway_candidate_()",
        "SimpleProductError SimpleProductRuntime::start_challenge_for_candidate_",
    )
    assert "transaction_deadline_ms" in attempt
    assert "start_full_scan_(clock_->now_ms(), false)" in attempt
    assert "begin_discovery_()" in attempt


def test_r2_accept_deadline_is_checked_before_crypto_or_radio_side_effects() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")
    accept = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::handle_accept_(",
        "SimpleProductError SimpleProductRuntime::handle_compact_(",
    )

    pending_expiry = accept.index("now >= pending.expires_at_ms")
    transaction_expiry = accept.index(
        "now >= gateway_selection_epoch_->transaction_deadline_ms"
    )
    verify = accept.index("verify_simple_peer_accept(")
    set_channel = accept.index("port_->set_radio_channel(channel)")
    install_peer = accept.index("port_->install_encrypted_peer(")

    assert pending_expiry < verify
    assert transaction_expiry < verify
    assert verify < set_channel < install_peer
    assert (
        "return SimpleProductError::PACKET_REJECTED;" in
        accept[pending_expiry:verify]
    )


def test_r2_local_fault_classification_is_narrow_and_component_consumes_it() -> None:
    runtime_source = text(CORE / "n3w_simple_product_runtime.cpp")
    component_header = text(CORE / "n3w_simple_product_component.h")
    component_source = text(CORE / "n3w_simple_product_component.cpp")

    helper = function_body(
        runtime_source,
        "bool gateway_selection_local_fault_requires_restore(",
        "SimpleProductRuntime::SimpleProductRuntime(",
    )
    assert "!selection_busy_before || selection_busy_after" in helper
    assert "SimpleProductError::RADIO_FAILED" in helper
    assert "SimpleProductError::CRYPTO_FAILED" in helper
    assert "SimpleProductError::STATE_REJECTED" in helper
    assert "SimpleProductError::PACKET_REJECTED" not in helper

    assert "GATEWAY_SELECTION_LOCAL_FAULT" in component_header
    assert "bool drain_radio_();" in component_header
    assert "bool consume_gateway_selection_runtime_result_(" in component_header

    loop = function_body(
        component_source,
        "void SimpleProductComponent::loop()",
        "TelemetrySubmitDisposition SimpleProductComponent::submit_telemetry_json(",
    )
    assert "if (drain_radio_()) return;" in loop
    assert "selection_busy_before_tick" in loop
    assert "consume_gateway_selection_runtime_result_(" in loop

    drain = function_body(
        component_source,
        "bool SimpleProductComponent::drain_radio_()",
        "void SimpleProductComponent::clear_rx_ring_()",
    )
    assert "selection_busy_before" in drain
    assert "consume_gateway_selection_runtime_result_(" in drain
    assert "return true;" in drain

    consume = function_body(
        component_source,
        "bool SimpleProductComponent::consume_gateway_selection_runtime_result_(",
        "void SimpleProductComponent::on_espnow_receive(",
    )
    assert "gateway_selection_local_fault_requires_restore(" in consume
    assert "RadioOwnership::RELAY_ESPNOW" in consume
    assert "LocalPathState::DISCOVERY" in consume
    shutdown = consume.index("radio_.shutdown()")
    clear_rx = consume.index("clear_rx_ring_()", shutdown)
    begin_restore = consume.index("begin_relay_restore_(", clear_rx)
    assert shutdown < clear_rx < begin_restore
    assert "RelayRestoreCause::GATEWAY_SELECTION_LOCAL_FAULT" in consume


def test_r2_local_fault_restore_drops_stale_rx_after_quiesce() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")
    restore = function_body(
        source,
        "void SimpleProductComponent::advance_relay_restore_()",
        "bool SimpleProductComponent::enqueue_telemetry_(",
    )

    clear_tx = restore.index("clear_tx_completion_ring_();")
    local_fault = restore.index(
        "RelayRestoreCause::GATEWAY_SELECTION_LOCAL_FAULT"
    )
    clear_rx = restore.index("clear_rx_ring_();", local_fault)
    restore_radio = restore.index("restore_relay_radio_()", clear_rx)

    assert clear_tx < local_fault < clear_rx < restore_radio


def test_r2_scan_failure_remains_visible_to_component_restore() -> None:
    runtime_header = text(CORE / "n3w_simple_product_runtime.h")
    runtime_source = text(CORE / "n3w_simple_product_runtime.cpp")
    component_source = text(CORE / "n3w_simple_product_component.cpp")

    assert "bool discovery_radio_ready() const" in runtime_header
    scan = function_body(
        runtime_source,
        "SimpleProductError SimpleProductRuntime::set_scan_channel_(",
        "SimpleProductError SimpleProductRuntime::start_fast_scan_(",
    )
    assert "discovery_radio_ready_ = false;" in scan
    assert "return SimpleProductError::RADIO_FAILED;" in scan
    assert "discovery_radio_ready_ = true;" in scan

    consume = function_body(
        component_source,
        "bool SimpleProductComponent::consume_gateway_selection_runtime_result_(",
        "void SimpleProductComponent::on_espnow_receive(",
    )
    assert "result == SimpleProductError::RADIO_FAILED" in consume
    assert "!runtime_.discovery_radio_ready()" in consume
    assert "begin_relay_restore_(" in consume


def test_r2_fast_exhaustion_falls_back_before_full_exhaustion_realigns() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")
    attempt = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::attempt_next_gateway_candidate_()",
        "SimpleProductError SimpleProductRuntime::start_challenge_for_candidate_",
    )

    assert (
        "candidate_index >= gateway_selection_epoch_->candidates.size()" in attempt
    )
    assert "full_collection" in attempt
    assert "start_full_scan_(clock_->now_ms(), false)" in attempt
    assert "begin_discovery_()" in attempt

    begin = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::begin_discovery_()",
        "SimpleProductError SimpleProductRuntime::refresh_legal_channels_()",
    )
    assert "clear_gateway_selection_();" in begin
    assert "refresh_legal_channels_()" in begin
    assert "scan_.configure_ordered(hints)" in begin
    assert "set_scan_channel_(" in begin
