from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"


def text(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def test_gate_c_uses_existing_direct_recovery_state_machine() -> None:
    runtime = text("n3w_simple_product_runtime.cpp")
    component = text("n3w_simple_product_component_broker_relocation.cpp")
    header = text("n3w_simple_product_component.h")

    assert "on_direct_recovery_probe_tick" in runtime
    assert "on_direct_recovery_commit_result" in runtime
    assert "DirectRecoveryPhase::MQTT_RECOVERY" in component
    assert "RadioOwnership::DIRECT_PROBE" in component
    assert "kHealthyRelayDirectRecoveryAbsoluteMs = 30000" in header
    assert "kNoRelayDirectRecoveryAbsoluteMs = 120000" in header
    assert "kDirectRecoveryMqttBudgetMs = 25000" in header
    assert "kDirectRecoveryConfirmBudgetMs = 5000" in header


def test_gate_c_discovery_is_nonblocking_and_bounded() -> None:
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
    assert "broker_relocation_discovery_can_start" in component
    assert "direct_recovery_attempt_.phase_deadline_ms()" in component
    assert "direct_recovery_attempt_.absolute_deadline_ms()" in component
    assert "now < last_broker_discovery_started_ms_" in component


def test_gate_c_preserves_identity_and_durable_broker_state() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")

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


def test_gate_c_candidate_is_promoted_only_after_direct_commit() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")

    commit = component.index("on_direct_recovery_commit_result")
    promote = component.index(
        "stable_runtime_broker_host_ = pending_broker_candidate_host_", commit
    )
    assert promote > commit
    assert "broker_candidate_verified_" in component[commit:promote]
    assert "rollback_broker_candidate_();" in component[commit:promote]


def test_gate_c_candidate_attempt_fences_then_requests_bounded_cancel_and_reconnect() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")

    retarget = component.index("bool SimpleProductComponent::retarget_runtime_broker_")
    rollback = component.index("void SimpleProductComponent::rollback_broker_candidate_", retarget)
    block = component[retarget:rollback]
    switched = block.index("n3w_runtime_retarget_server")
    fenced = block.index("n3w_runtime_fence_old_events", switched)
    disconnect = block.index("n3w_runtime_request_disconnect", fenced)
    reconnect = block.index("n3w_runtime_request_reconnect", disconnect)
    assert switched < fenced < disconnect < reconnect
    assert "disconnect_requested || reconnect_requested" in block
    assert "n3w_runtime_stop_and_clear_events" not in block
    assert "n3w_runtime_start" not in block


def test_gate_c_candidate_retries_reconnect_until_candidate_deadline() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")

    advance = component.index("void SimpleProductComponent::advance_broker_relocation_")
    probe = component.index("void SimpleProductComponent::on_direct_recovery_probe_tick", advance)
    block = component[advance:probe]
    active = block.index("if (broker_candidate_active_)")
    retry = block.index("n3w_runtime_request_reconnect", active)
    timeout = block.index("now >= broker_candidate_deadline_ms_", retry)
    assert active < retry < timeout


def test_gate_c_candidate_timeout_can_advance_to_second_candidate() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")

    advance = component.index("void SimpleProductComponent::advance_broker_relocation_")
    probe = component.index("void SimpleProductComponent::on_direct_recovery_probe_tick", advance)
    block = component[advance:probe]
    timeout = block.index("now >= broker_candidate_deadline_ms_")
    cleared = block.index("pending_broker_candidate_host_.clear();", timeout)
    next_candidate = block.index("start_next_broker_candidate_()", cleared)
    rollback = block.index("rollback_broker_candidate_();", next_candidate)
    assert timeout < cleared < next_candidate < rollback


def test_gate_c_rollback_restores_stable_target_without_blocking_stop() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")

    rollback = component.index("void SimpleProductComponent::rollback_broker_candidate_")
    end = component.index("bool SimpleProductComponent::start_broker_discovery_", rollback)
    block = component[rollback:end]
    restored = block.index("stable_runtime_broker_host_")
    switched = block.index("n3w_runtime_retarget_server", restored)
    fenced = block.index("n3w_runtime_fence_old_events", switched)
    disconnect = block.index("n3w_runtime_request_disconnect", fenced)
    reconnect = block.index("n3w_runtime_request_reconnect", disconnect)
    assert restored < switched < fenced < disconnect < reconnect
    assert "esp_mqtt_client_stop" not in block


def test_gate_c_rejects_candidate_if_wifi_network_changed_after_discovery() -> None:
    component = text("n3w_simple_product_component_broker_relocation.cpp")

    start = component.index("bool SimpleProductComponent::start_next_broker_candidate_")
    end = component.index("void SimpleProductComponent::advance_broker_relocation_", start)
    block = component[start:end]
    assert "current_wifi_ipv4_(&current_ipv4, &current_mask)" in block
    assert "current_ipv4 != broker_discovery_local_ipv4_" in block
    assert "current_mask != broker_discovery_subnet_mask_" in block
    assert "network changed after discovery" in block


def test_gate_c_mqtt_overlay_filters_old_generation_without_blocking_stop() -> None:
    patch = text("n3w_mqtt_retarget_barrier_patch.py.script")
    tls_patch = text("n3w_tls_server_name_patch.py.script")
    component_init = text("__init__.py")

    tls_pos = component_init.index("n3w_tls_server_name_patch.py.script")
    barrier_pos = component_init.index("n3w_mqtt_retarget_barrier_patch.py.script")
    assert tls_pos < barrier_pos
    assert "EXPECTED_MQTT_BACKEND_ESP32_CPP_BLOB" in patch
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
    assert "CLIENT_BARRIER_NEW" in tls_patch
    assert "BACKEND_BARRIER_EVENT_NEW" in tls_patch
    assert "BACKEND_BARRIER_METHOD_NEW" in tls_patch
    assert "BACKEND_BARRIER_STORAGE_NEW" in tls_patch


def test_gate_c_filter_rejects_self_and_unbounded_ttl() -> None:
    policy = text("n3w_manager_discovery_policy.cpp")
    header = text("n3w_manager_discovery.h")

    assert "advertised == local" in policy
    assert "candidate.ttl_s == 0U" in policy
    assert "candidate.ttl_s > kManagerDiscoveryMaxCandidateTtlSeconds" in policy
    assert "kManagerDiscoveryMaxCandidateTtlSeconds = 120" in header
