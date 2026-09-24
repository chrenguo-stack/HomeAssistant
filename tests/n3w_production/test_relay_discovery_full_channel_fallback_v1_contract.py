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
    assert "uint32_t full_handshake_max_ms{24000};" in header
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
