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
