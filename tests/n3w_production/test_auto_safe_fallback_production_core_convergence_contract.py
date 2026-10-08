from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_core"
TARGET = ROOT / "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml"
TRANSPORT = ROOT / "firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml"


def text(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def test_production_target_uses_product_core() -> None:
    target = TARGET.read_text(encoding="utf-8")
    transport = TRANSPORT.read_text(encoding="utf-8")
    assert "greenhouse_n3w_product_core" in target
    assert "packages/n3w_product_transport.yml" in target
    assert "greenhouse_n3w_product_core:" in transport
    assert "product_runtime: true" in transport


def test_production_core_has_auto_fallback_support_files() -> None:
    for name in (
        "n3w_broker_relocation_policy.cpp",
        "n3w_broker_relocation_policy.h",
        "n3w_esp32_manager_discovery.cpp",
        "n3w_esp32_manager_discovery.h",
        "n3w_esp32_manager_discovery_session.cpp",
        "n3w_esp32_manager_discovery_session.h",
        "n3w_manager_discovery.cpp",
        "n3w_manager_discovery.h",
        "n3w_manager_discovery_policy.cpp",
        "n3w_mqtt_retarget_barrier_patch.py.script",
        "n3w_simple_product_component_broker_relocation.cpp",
    ):
        assert (CORE / name).is_file(), name


def test_production_gate_c_uses_existing_direct_recovery_state_machine() -> None:
    runtime = text("n3w_simple_product_runtime.cpp")
    component = text("n3w_simple_product_component_broker_relocation.cpp")
    header = text("n3w_simple_product_component.h")
    policy = text("n3w_direct_recovery_policy.h")

    assert "on_direct_recovery_probe_tick" in runtime
    assert "on_direct_recovery_commit_result" in runtime
    assert "DirectRecoveryPhase::MQTT_RECOVERY" in component
    assert "RadioOwnership::DIRECT_PROBE" in component
    assert "kHealthyRelayDirectRecoveryAbsoluteMs = 30000" in header
    assert "kNoRelayDirectRecoveryAbsoluteMs = 120000" in header
    assert "kDirectRecoveryMqttBudgetMs = 25000" in header
    assert "kDirectRecoveryConfirmBudgetMs = 5000" in header
    assert "phase_deadline_ms() const" in policy
    assert "absolute_deadline_ms() const" in policy


def test_direct_mqtt_relocation_trigger_is_business_cadence_independent() -> None:
    product = text("greenhouse_n3w_product_core.h")
    telemetry = (
        ROOT
        / "firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml"
    ).read_text(encoding="utf-8")

    loop_start = product.index("void loop() override")
    loop_end = product.index("bool provision_boot_session_repair_recovery", loop_start)
    loop_block = product[loop_start:loop_end]
    assert "SimpleProductComponent::loop();" in loop_block
    assert "advance_direct_mqtt_broker_relocation_();" in loop_block

    helper_start = product.index("void advance_direct_mqtt_broker_relocation_()")
    helper_end = product.index(
        "static StartupIdentityRecordState startup_identity_record_state_(",
        helper_start,
    )
    helper = product[helper_start:helper_end]
    assert "runtime_.path_state() == LocalPathState::DIRECT" in helper
    assert "direct_wifi_connected_()" in helper
    assert "direct_mqtt_connected_()" in helper
    assert "broker_relocation_trigger_due(direct_mqtt_failure_started_ms_, now)" in helper
    assert "kBrokerRelocationDiscoveryMinIntervalMs" in helper
    assert "start_broker_discovery_()" in helper
    assert "start_next_direct_broker_candidate_()" in helper
    assert "direct_recovery_attempt_.phase() != DirectRecoveryPhase::IDLE" in helper
    assert "runtime_.note_direct_result" not in helper
    assert "submit_telemetry_json" not in helper
    assert "n3w_telemetry_interval" not in helper
    assert "interval: ${n3w_telemetry_interval}" in telemetry


def test_direct_mqtt_relocation_candidate_window_is_bounded() -> None:
    product = text("greenhouse_n3w_product_core.h")
    helper_start = product.index("bool start_next_direct_broker_candidate_()")
    helper_end = product.index("void advance_direct_mqtt_broker_relocation_()", helper_start)
    helper = product[helper_start:helper_end]
    assert "kBrokerRelocationCandidateBudgetMs" in helper
    assert "kBrokerRelocationCleanupReserveMs" in helper
    assert "broker_relocation_candidate_deadline" in helper
    assert "broker_discovery_completed_ms_" in helper
    assert "current_wifi_ipv4_(&current_ipv4, &current_mask)" in helper
    assert "current_ipv4 != broker_discovery_local_ipv4_" in helper
    assert "current_mask != broker_discovery_subnet_mask_" in helper
    assert "target.ttl_s == 0U" in helper
    assert "retarget_runtime_broker_(target.host, true)" in helper


def test_direct_mqtt_relocation_setup_failure_rolls_back_fail_closed() -> None:
    product = text("greenhouse_n3w_product_core.h")

    reset_start = product.index("void reset_direct_broker_relocation_(bool rollback)")
    reset_end = product.index("bool start_next_direct_broker_candidate_()", reset_start)
    reset = product[reset_start:reset_end]
    assert "if (rollback)" in reset
    assert "rollback_broker_candidate_();" in reset
    assert "rollback && broker_candidate_active_" not in reset

    candidate_start = product.index("bool start_next_direct_broker_candidate_()")
    candidate_end = product.index("void advance_direct_mqtt_broker_relocation_()", candidate_start)
    candidate = product[candidate_start:candidate_end]
    retarget = candidate.index("retarget_runtime_broker_(target.host, true)")
    rollback = candidate.index("rollback_broker_candidate_();", retarget)
    failed = candidate.index("stable Broker restored", rollback)
    assert retarget < rollback < failed


def test_production_discovery_is_nonblocking_and_bounded() -> None:
    session = text("n3w_esp32_manager_discovery_session.cpp")
    policy = text("n3w_broker_relocation_policy.h")
    component = text("n3w_simple_product_component_broker_relocation.cpp")

    assert "MSG_DONTWAIT" in session
    assert "kDiscoveryPollDatagramLimit = 2" in session
    assert "kDiscoveryCollectWindowMs = 1000" in session
    assert "kManagerDiscoveryMaxParsedDatagrams" in session
    assert "kBrokerRelocationMqttFailureTriggerMs = 10000" in policy
    assert "kBrokerRelocationCandidateBudgetMs = 6000" in policy
    assert "kBrokerRelocationCleanupReserveMs = 2000" in policy
    assert "kBrokerRelocationDiscoveryMinIntervalMs = 60000" in policy
    assert "direct_recovery_attempt_.phase_deadline_ms()" in component
    assert "direct_recovery_attempt_.absolute_deadline_ms()" in component


def test_production_relocation_preserves_identity_and_durable_state() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")
    product = text("greenhouse_n3w_product_core.h")

    assert "broker_state_.broker_port" in component
    assert "peer_state_.system_id" in component
    assert "stable_runtime_broker_host_" in component
    assert "pending_broker_candidate_host_" in component
    assert "SimplePairingClient::run_once" not in component
    for forbidden in (
        "set_ca_certificate",
        "set_tls_server_name",
        "set_username",
        "set_password",
        "set_client_id",
        ".save(",
        "broker_store_.save(",
        "broker_store_.erase(",
        "peer_store_.save(",
        "peer_store_.erase(",
        "NvsProvisionedBrokerStoreV2",
    ):
        assert forbidden not in component

    direct_start = product.index("bool start_next_direct_broker_candidate_()")
    direct_end = product.index(
        "static StartupIdentityRecordState startup_identity_record_state_(",
        direct_start,
    )
    direct = product[direct_start:direct_end]
    for forbidden in (
        "set_ca_certificate",
        "set_tls_server_name",
        "set_username",
        "set_password",
        "set_client_id",
        "broker_store_.save(",
        "broker_store_.erase(",
        "peer_store_.save(",
        "peer_store_.erase(",
    ):
        assert forbidden not in direct


def test_production_candidate_commit_and_rollback_are_fail_closed() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")

    commit = component.index("on_direct_recovery_commit_result")
    promote = component.index(
        "stable_runtime_broker_host_ = pending_broker_candidate_host_", commit
    )
    assert promote > commit
    assert "broker_candidate_verified_" in component[commit:promote]
    assert "rollback_broker_candidate_();" in component[commit:promote]

    retarget = component.index("bool SimpleProductComponent::retarget_runtime_broker_")
    rollback = component.index("void SimpleProductComponent::rollback_broker_candidate_", retarget)
    block = component[retarget:rollback]
    switched = block.index("n3w_runtime_retarget_server")
    fenced = block.index("n3w_runtime_fence_old_events", switched)
    disconnect = block.index("n3w_runtime_request_disconnect", fenced)
    reconnect = block.index("n3w_runtime_request_reconnect", disconnect)
    assert switched < fenced < disconnect < reconnect
    assert "esp_mqtt_client_stop" not in block
    assert "portMAX_DELAY" not in block


def test_production_candidate_retries_and_network_generation_are_bounded() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")

    advance = component.index("void SimpleProductComponent::advance_broker_relocation_")
    probe = component.index("void SimpleProductComponent::on_direct_recovery_probe_tick", advance)
    block = component[advance:probe]
    active = block.index("if (broker_candidate_active_)")
    retry = block.index("n3w_runtime_request_reconnect", active)
    timeout = block.index("now >= broker_candidate_deadline_ms_", retry)
    assert active < retry < timeout

    start = component.index("bool SimpleProductComponent::start_next_broker_candidate_")
    end = component.index("void SimpleProductComponent::advance_broker_relocation_", start)
    candidate = component[start:end]
    assert "current_wifi_ipv4_(&current_ipv4, &current_mask)" in candidate
    assert "current_ipv4 != broker_discovery_local_ipv4_" in candidate
    assert "current_mask != broker_discovery_subnet_mask_" in candidate
    assert "network changed after discovery" in candidate


def test_production_mqtt_overlay_is_composed_and_nonblocking() -> None:
    patch = text("n3w_mqtt_retarget_barrier_patch.py.script")
    tls_patch = text("n3w_tls_server_name_patch.py.script")
    component_init = text("__init__.py")

    tls_pos = component_init.index("n3w_tls_server_name_patch.py.script")
    barrier_pos = component_init.index("n3w_mqtt_retarget_barrier_patch.py.script")
    assert tls_pos < barrier_pos
    assert "connection_generation_" in patch
    assert "minimum_event_generation_" in patch
    assert "MQTT_EVENT_BEFORE_CONNECT" in patch
    assert "event->generation >= minimum_generation" in patch
    assert "n3w_runtime_fence_old_events" in patch
    assert "this->state_ = MQTT_CLIENT_CONNECTING" in patch
    assert "this->connect_begin_ = millis()" in patch
    assert "esp_mqtt_client_stop" not in patch
    assert "portMAX_DELAY" not in patch
    assert "already = all(text.count(new) == 1 for _, new in replacements)" in patch
    assert "old not in text" not in patch
    assert "reverse_replacements" in tls_patch
    assert "composed_replacements" in tls_patch
    assert 'return "ALREADY_COMPOSED"' in tls_patch


def test_production_pairing_remains_separate_from_recovery() -> None:
    pairing = text("n3w_simple_pairing_client.cpp")
    pairing_header = text("n3w_simple_pairing_client.h")

    assert "build_simple_discovery_query" in pairing
    assert "parse_simple_discovery_response" in pairing
    assert "ALREADY_PROVISIONED" in pairing
    assert "SimpleManagerCandidateV2" in pairing_header
    assert "n3w_manager_discovery.h" in pairing_header
    assert "n3w_simple_product_component_broker_relocation" not in pairing


def test_production_filter_rejects_self_and_unbounded_ttl() -> None:
    policy = text("n3w_manager_discovery_policy.cpp")
    header = text("n3w_manager_discovery.h")

    assert "advertised == local" in policy
    assert "candidate.ttl_s == 0U" in policy
    assert "candidate.ttl_s > kManagerDiscoveryMaxCandidateTtlSeconds" in policy
    assert "kManagerDiscoveryMaxCandidateTtlSeconds = 120" in header


def test_pr474_full_channel_and_gateway_selection_contracts_remain_present() -> None:
    runtime_header = text("n3w_simple_product_runtime.h")
    runtime = text("n3w_simple_product_runtime.cpp")
    component = text("n3w_simple_product_component.h")

    for token in (
        "current_legal_channels",
        "DiscoveryScanStage",
        "gateway_selection_busy",
        "discovery_restart_required",
    ):
        assert token in runtime_header
    for token in (
        "start_full_scan_",
        "gateway_selection_local_fault_requires_restore",
        "restart_discovery_after_radio_fault",
        "discovery_restore_requires_restart",
    ):
        assert token in runtime
    for token in (
        "GATEWAY_SELECTION_LOCAL_FAULT",
        "clear_rx_ring_",
        "read_current_legal_channels_",
        "current_country_allows_channel_",
    ):
        assert token in component
