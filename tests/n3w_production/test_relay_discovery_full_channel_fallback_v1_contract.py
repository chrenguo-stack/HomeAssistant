from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_core"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_body(source: str, signature: str, next_signature: str) -> str:
    start = source.index(signature)
    end = source.index(next_signature, start)
    return source[start:end]


def test_layered_discovery_policy_is_frozen() -> None:
    header = text(CORE / "n3w_simple_product_runtime.h")

    assert "std::vector<uint8_t> allowed_channels{1, 6, 11};" in header
    assert "uint32_t scan_dwell_ms{250};" in header
    assert "uint32_t fast_search_budget_ms{6500};" in header
    assert "uint32_t candidate_window_ms{6500};" in header
    assert "uint32_t gateway_selection_transaction_max_ms{30000};" in header
    assert "uint32_t full_scan_dwell_ms{2250};" in header
    assert "uint32_t full_scan_schedule_margin_ms{2000};" in header
    assert "uint32_t full_handshake_max_ms{26000};" in header
    assert "uint32_t full_scan_total_max_ms{60000};" in header
    assert "HINT" in header
    assert "FAST" in header
    assert "FULL" in header


def test_full_scan_uses_current_complete_legal_domain() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    full = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::start_full_scan_(",
        "SimpleProductError SimpleProductRuntime::finish_full_scan_(",
    )

    refresh = full.index("refresh_legal_channels_()")
    configure = full.index("scan_.configure_ordered(legal_channels_)")
    set_channel = full.index("set_scan_channel_(")
    assert refresh < configure < set_channel
    assert "policy_.full_scan_dwell_ms" in full
    assert "legal_channels_.size()" in full
    assert "policy_.full_scan_schedule_margin_ms" in full
    assert "policy_.full_scan_total_max_ms" in full
    assert "allowed_channels" not in full


def test_full_scan_is_bounded_and_does_not_freeze_on_first_candidate() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    discovery = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::handle_discovery_(",
        "void SimpleProductRuntime::clear_gateway_selection_()",
    )
    full_finish = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::finish_full_scan_(",
        "SimpleProductError SimpleProductRuntime::leave_relay_for_discovery_()",
    )
    advance = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::maybe_advance_scan_(",
        "uint8_t SimpleProductRuntime::working_channel() const",
    )

    assert "discovery_scan_stage_ == DiscoveryScanStage::FULL" in discovery
    assert "return SimpleProductError::NONE;" in discovery
    assert "gateway_selection_epoch_->frozen = true;" in full_finish
    assert "policy_.full_handshake_max_ms" in full_finish
    assert "std::min(full_scan_total_deadline_ms_, handshake_deadline)" in full_finish
    assert "scan_.advance_bounded()" in advance
    assert "finish_full_scan_(now_ms)" in advance
    assert "now_ms >= full_scan_hard_deadline_ms_" in advance


def test_hint_is_priority_only_and_full_scan_revisits_it() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    begin = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::begin_discovery_()",
        "SimpleProductError SimpleProductRuntime::refresh_legal_channels_()",
    )
    full = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::start_full_scan_(",
        "SimpleProductError SimpleProductRuntime::finish_full_scan_(",
    )

    assert "append_hint(direct_channel_);" in begin
    assert "append_hint(cached_gateway_channel_);" in begin
    assert "scan_.configure_ordered(hints)" in begin
    assert "scan_.configure_ordered(legal_channels_)" in full


def test_gateway_channel_cache_is_ram_only_and_authenticated() -> None:
    header = text(CORE / "n3w_simple_product_runtime.h")
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    accept = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::handle_accept_(",
        "SimpleProductError SimpleProductRuntime::handle_compact_(",
    )
    set_channel = accept.index("port_->set_radio_channel(channel)")
    install_peer = accept.index("port_->install_encrypted_peer(")
    path_commit = accept.index("path_.note_authenticated_relay_ready(true)")
    active = accept.index("active_relay_ = std::move(relay)")
    cache = accept.index("cached_gateway_channel_ = channel")
    assert set_channel < install_peer < path_commit < active < cache

    stop = function_body(
        source,
        "void SimpleProductRuntime::stop()",
        "SimpleProductError SimpleProductRuntime::tick()",
    )
    assert "cached_gateway_channel_ = 0;" in stop
    assert "cached_gateway_channel_" in header
    assert "Nvs" not in header[header.index("cached_gateway_channel_") - 120:
                               header.index("cached_gateway_channel_") + 120]


def test_regulatory_domain_comes_from_current_esp_idf_country() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")

    read_country = function_body(
        source,
        "bool SimpleProductComponent::read_current_legal_channels_(",
        "bool SimpleProductComponent::current_legal_channels(",
    )
    assert "esp_wifi_get_country(&country)" in read_country
    assert "country.schan" in read_country
    assert "country.nchan" in read_country
    assert "last > 14U" in read_country
    assert "esp_wifi_set_country" not in source

    set_channel = function_body(
        source,
        "bool SimpleProductComponent::set_radio_channel(uint8_t channel)",
        "bool SimpleProductComponent::broadcast_control(",
    )
    assert "current_country_allows_channel_(channel)" in set_channel


def test_full_discovery_is_busy_before_first_candidate() -> None:
    header = text(CORE / "n3w_simple_product_runtime.h")
    component = text(CORE / "n3w_simple_product_component.cpp")

    busy_start = header.index("bool gateway_selection_busy() const")
    busy_end = header.index("std::size_t relay_child_count()", busy_start)
    busy = header[busy_start:busy_end]
    assert "full_scan_in_progress_" in busy

    recovery = function_body(
        component,
        "void SimpleProductComponent::advance_recovery_()",
        "bool SimpleProductComponent::claim_relay_radio_()",
    )
    assert "if (runtime_.gateway_selection_busy()) return;" in recovery


def test_discovery_fault_before_first_candidate_enters_bounded_restore() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")

    consume = function_body(
        source,
        "bool SimpleProductComponent::consume_gateway_selection_runtime_result_(",
        "void SimpleProductComponent::on_espnow_receive(",
    )
    assert "result == SimpleProductError::RADIO_FAILED" in consume
    assert "runtime_.path_state() == LocalPathState::DISCOVERY" in consume
    assert "!runtime_.discovery_radio_ready()" in consume
    shutdown = consume.index("radio_.shutdown()")
    clear_rx = consume.index("clear_rx_ring_()", shutdown)
    restore = consume.index("begin_relay_restore_(", clear_rx)
    assert shutdown < clear_rx < restore


def test_direct_failback_and_relay_activation_order_are_preserved() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    accept = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::handle_accept_(",
        "SimpleProductError SimpleProductRuntime::handle_compact_(",
    )
    assert (
        accept.index("port_->set_radio_channel(channel)") <
        accept.index("port_->install_encrypted_peer(") <
        accept.index("path_.note_authenticated_relay_ready(true)")
    )

    restore = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::restore_direct_()",
        "SimpleProductError SimpleProductRuntime::handle_discovery_(",
    )
    assert restore.index("port_->set_radio_channel(direct_channel_)") < restore.index(
        "active_relay_.reset()"
    )


def test_full_scan_does_not_add_proactive_roaming() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    discovery = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::handle_discovery_(",
        "void SimpleProductRuntime::clear_gateway_selection_()",
    )
    assert "path_.state() != LocalPathState::DISCOVERY" in discovery


def test_product_single_radio_ownership_is_preserved() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")

    claim = function_body(
        source,
        "bool SimpleProductComponent::claim_relay_radio_()",
        "bool SimpleProductComponent::begin_direct_probe_(",
    )
    shutdown = claim.index("radio_.shutdown()")
    disable = claim.index("wifi::global_wifi_component->disable()", shutdown)
    standalone = claim.index("radio_.initialize_standalone(this, pmk)", disable)
    ownership = claim.index(
        "radio_ownership_ = RadioOwnership::RELAY_ESPNOW", standalone
    )
    assert shutdown < disable < standalone < ownership

    set_channel = function_body(
        source,
        "bool SimpleProductComponent::set_radio_channel(uint8_t channel)",
        "bool SimpleProductComponent::broadcast_control(",
    )
    assert "wifi_connected())" in set_channel
    assert "return current_channel == channel;" in set_channel
    assert "runtime_.path_state() != LocalPathState::DIRECT" in set_channel
    assert "claim_relay_radio_()" in set_channel


def test_product_disconnected_start_enters_owned_standalone_discovery() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")

    start = function_body(
        source,
        "bool SimpleProductComponent::start_runtime_if_ready_()",
        "void SimpleProductComponent::advance_pairing_()",
    )
    assert "SimpleProductStartMode::DISCOVERY" in start
    disable = start.index("wifi::global_wifi_component->disable()")
    standalone = start.index("radio_.initialize_standalone(this, pmk)", disable)
    relay_owner = start.index(
        "radio_ownership_ = RadioOwnership::RELAY_ESPNOW", standalone
    )
    runtime_start = start.index("runtime_.start(", relay_owner)
    assert disable < standalone < relay_owner < runtime_start


def test_scan_dwell_starts_after_channel_set_completes() -> None:
    source = text(CORE / "n3w_simple_product_runtime.cpp")

    scan = function_body(
        source,
        "SimpleProductError SimpleProductRuntime::set_scan_channel_(",
        "SimpleProductError SimpleProductRuntime::start_fast_scan_(",
    )
    set_channel = scan.index("port_->set_radio_channel(channel)")
    ready_clock = scan.index("const uint64_t ready_ms = clock_->now_ms()", set_channel)
    dwell_deadline = scan.index("next_scan_switch_ms_ = ready_ms + dwell_ms", ready_clock)
    assert set_channel < ready_clock < dwell_deadline
    assert "next_scan_switch_ms_ = now_ms + dwell_ms" not in scan


def test_discovery_restore_restarts_scan_state_instead_of_rebinding_stale_full() -> None:
    runtime = text(CORE / "n3w_simple_product_runtime.cpp")
    component = text(CORE / "n3w_simple_product_component.cpp")

    reset = function_body(
        runtime,
        "SimpleProductError SimpleProductRuntime::reset_to_discovery_after_radio_fault()",
        "SimpleProductError SimpleProductRuntime::restart_discovery_after_radio_fault()",
    )
    assert "full_scan_in_progress_ = false;" in reset
    assert "discovery_radio_ready_ = false;" in reset
    assert "legal_channels_.clear();" in reset
    assert "begin_discovery_()" not in reset

    restart = function_body(
        runtime,
        "SimpleProductError SimpleProductRuntime::restart_discovery_after_radio_fault()",
        "bool SimpleProductRuntime::update_direct_channel_hint",
    )
    assert "reset_to_discovery_after_radio_fault()" in restart
    assert "return begin_discovery_();" in restart

    restore = function_body(
        component,
        "bool SimpleProductComponent::restore_relay_radio_()",
        "void SimpleProductComponent::drain_send_completions_()",
    )
    cause = restore.index("RelayRestoreCause::GATEWAY_SELECTION_LOCAL_FAULT")
    restart_call = restore.index("runtime_.restart_discovery_after_radio_fault()", cause)
    rebind_call = restore.index("runtime_.rebind_radio_state()", restart_call)
    assert cause < restart_call < rebind_call


def test_failed_discovery_restart_consumes_existing_restore_budget() -> None:
    component = text(CORE / "n3w_simple_product_component.cpp")

    restore_loop = function_body(
        component,
        "void SimpleProductComponent::advance_relay_restore_()",
        "bool SimpleProductComponent::enqueue_telemetry_(",
    )
    restore_attempt = restore_loop.index("if (restore_relay_radio_())")
    success_clear = restore_loop.index("relay_restore_budget_.clear();", restore_attempt)
    failure_note = restore_loop.index("relay_restore_budget_.note_failure();", success_clear)
    exhausted = restore_loop.index("relay_restore_budget_.exhausted(now)", failure_note)
    assert restore_attempt < success_clear < failure_note < exhausted
    assert "begin_relay_restore_(" not in restore_loop[failure_note:exhausted]

    exit_path = function_body(
        component,
        "void SimpleProductComponent::exit_relay_restore_failure_(uint64_t now)",
        "void SimpleProductComponent::advance_relay_restore_()",
    )
    assert "runtime_.reset_to_discovery_after_radio_fault()" in exit_path
    assert "runtime_.restart_discovery_after_radio_fault()" not in exit_path


def test_full_budget_leaves_scheduler_margin_for_eight_candidates() -> None:
    header = text(CORE / "n3w_simple_product_runtime.h")

    assert "uint32_t full_scan_dwell_ms{2250};" in header
    assert "uint32_t full_scan_schedule_margin_ms{2000};" in header
    assert "uint32_t full_handshake_max_ms{26000};" in header
    assert "uint32_t full_scan_total_max_ms{60000};" in header

    assert 14 * 2250 + 2000 + 26000 == 59500
    assert 59500 < 60000


def test_stale_discovery_plan_is_marked_and_cannot_be_rebound() -> None:
    header = text(CORE / "n3w_simple_product_runtime.h")
    runtime = text(CORE / "n3w_simple_product_runtime.cpp")
    component = text(CORE / "n3w_simple_product_component.cpp")

    assert "bool discovery_restart_required() const" in header
    assert "bool discovery_restart_required_{false};" in header

    reset = function_body(
        runtime,
        "SimpleProductError SimpleProductRuntime::reset_to_discovery_after_radio_fault()",
        "SimpleProductError SimpleProductRuntime::restart_discovery_after_radio_fault()",
    )
    assert "discovery_restart_required_ = true;" in reset

    rebind = function_body(
        runtime,
        "SimpleProductError SimpleProductRuntime::rebind_radio_state()",
        "SimpleProductError SimpleProductRuntime::reset_to_discovery_after_radio_fault()",
    )
    guard = rebind.index("if (discovery_restart_required_)")
    failure = rebind.index("return SimpleProductError::RADIO_FAILED;", guard)
    stale_channel = rebind.index("scan_.current()", failure)
    assert guard < failure < stale_channel

    begin = function_body(
        runtime,
        "SimpleProductError SimpleProductRuntime::begin_discovery_()",
        "SimpleProductError SimpleProductRuntime::refresh_legal_channels_()",
    )
    assert begin.index("discovery_restart_required_ = true;") < begin.index(
        "refresh_legal_channels_()"
    )
    assert "discovery_restart_required_ = false;" in begin

    restore = function_body(
        component,
        "bool SimpleProductComponent::restore_relay_radio_()",
        "void SimpleProductComponent::drain_send_completions_()",
    )
    assert "discovery_restore_requires_restart(" in restore
    assert "runtime_.path_state()" in restore
    assert "runtime_.discovery_restart_required()" in restore
    assert "RelayRestoreCause::GATEWAY_SELECTION_LOCAL_FAULT" in restore
    assert "runtime_.restart_discovery_after_radio_fault()" in restore
    assert "runtime_.rebind_radio_state()" in restore


def test_logical_reset_then_direct_failure_routes_back_to_fresh_discovery() -> None:
    runtime = text(CORE / "n3w_simple_product_runtime.cpp")
    component = text(CORE / "n3w_simple_product_component.cpp")

    policy = function_body(
        runtime,
        "bool discovery_restore_requires_restart(",
        "SimpleProductRuntime::SimpleProductRuntime(",
    )
    assert "path_state == LocalPathState::DISCOVERY" in policy
    assert "discovery_restart_required || gateway_selection_local_fault" in policy

    exit_path = function_body(
        component,
        "void SimpleProductComponent::exit_relay_restore_failure_(uint64_t now)",
        "void SimpleProductComponent::advance_relay_restore_()",
    )
    reset = exit_path.index("runtime_.reset_to_discovery_after_radio_fault()")
    direct = exit_path.index("begin_direct_probe_after_restore_exit_(now)", reset)
    assert reset < direct
    assert "runtime_.restart_discovery_after_radio_fault()" not in exit_path

    recovery = function_body(
        component,
        "void SimpleProductComponent::advance_recovery_()",
        "bool SimpleProductComponent::claim_relay_radio_()",
    )
    assert "begin_relay_restore_(RelayRestoreCause::FULL_DIRECT_VERIFY)" in recovery

    restore = function_body(
        component,
        "bool SimpleProductComponent::restore_relay_radio_()",
        "void SimpleProductComponent::drain_send_completions_()",
    )
    route = restore.index("discovery_restore_requires_restart(")
    restart = restore.index("runtime_.restart_discovery_after_radio_fault()", route)
    assert route < restart
