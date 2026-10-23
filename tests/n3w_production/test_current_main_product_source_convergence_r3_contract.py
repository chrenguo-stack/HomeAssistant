from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
TARGET = ROOT / "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml"


def text(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_current_active_core_owns_r3_broker_fallback() -> None:
    for name in (
        "n3w_broker_relocation_policy.cpp",
        "n3w_broker_relocation_policy.h",
        "n3w_manager_discovery.cpp",
        "n3w_manager_discovery.h",
        "n3w_manager_discovery_policy.cpp",
        "n3w_esp32_manager_discovery.cpp",
        "n3w_esp32_manager_discovery.h",
        "n3w_esp32_manager_discovery_session.cpp",
        "n3w_esp32_manager_discovery_session.h",
        "n3w_mqtt_retarget_barrier_patch.py.script",
        "n3w_simple_product_component_broker_relocation.cpp",
    ):
        assert (CORE / name).is_file(), name
    target = TARGET.read_text(encoding="utf-8")
    assert "greenhouse_n3w_core" in target
    assert "greenhouse_n3w_product_core" not in target


def test_direct_mqtt_trigger_is_loop_driven_not_telemetry_driven() -> None:
    component = text("n3w_simple_product_component.cpp")
    relocation = text("n3w_simple_product_component_broker_relocation.cpp")
    helper = block(
        relocation,
        "void SimpleProductComponent::advance_direct_mqtt_broker_relocation_()",
        "}  // namespace esphome::greenhouse_n3w_core",
    )
    assert "advance_direct_mqtt_broker_relocation_();" in component
    assert "runtime_.path_state() == LocalPathState::DIRECT" in helper
    assert "broker_wifi_connected()" in helper
    assert "broker_mqtt_connected()" in helper
    assert "broker_relocation_trigger_due(direct_mqtt_failure_started_ms_, now)" in helper
    assert "kBrokerRelocationDiscoveryMinIntervalMs" in helper
    assert "start_broker_discovery_()" in helper
    assert "start_next_direct_broker_candidate_()" in helper
    assert "direct_recovery_attempt_.phase() != DirectRecoveryPhase::IDLE" in helper
    assert "runtime_.note_direct_result" not in helper
    assert "submit_telemetry_json" not in helper


def test_existing_direct_recovery_state_machine_is_extended_not_duplicated() -> None:
    runtime = text("n3w_simple_product_runtime.cpp")
    runtime_header = text("n3w_simple_product_runtime.h")
    component_header = text("n3w_simple_product_component.h")
    relocation = text("n3w_simple_product_component_broker_relocation.cpp")
    policy = text("n3w_direct_recovery_policy.h")
    assert "on_direct_recovery_probe_tick" in runtime
    assert "on_direct_recovery_commit_result" in runtime
    assert "on_direct_recovery_probe_tick" in runtime_header
    assert "on_direct_recovery_commit_result" in runtime_header
    assert "DirectRecoveryAttempt direct_recovery_attempt_" in component_header
    assert "DirectRecoveryPhase::MQTT_RECOVERY" in relocation
    assert "phase_deadline_ms() const" in policy
    assert "absolute_deadline_ms() const" in policy
    assert "DirectBrokerRecoveryPhase" not in relocation
    assert "BrokerRecoveryStateMachine" not in relocation


def test_relocation_is_ram_only_and_preserves_identity_and_credentials() -> None:
    relocation = text("n3w_simple_product_component_broker_relocation.cpp")
    assert "n3w_runtime_retarget_server" in relocation
    assert "broker_state_.broker_port" in relocation
    assert "peer_state_.system_id" in relocation
    assert "stable_runtime_broker_host_" in relocation
    assert "pending_broker_candidate_host_" in relocation
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
        "SimplePairingClient::run_once",
    ):
        assert forbidden not in relocation


def test_candidate_failure_rolls_back_and_success_is_boot_local() -> None:
    relocation = text("n3w_simple_product_component_broker_relocation.cpp")
    retarget = relocation.index("bool SimpleProductComponent::retarget_runtime_broker_")
    rollback = relocation.index("void SimpleProductComponent::rollback_broker_candidate_", retarget)
    retarget_block = relocation[retarget:rollback]
    switched = retarget_block.index("n3w_runtime_retarget_server")
    fenced = retarget_block.index("n3w_runtime_fence_old_events", switched)
    disconnect = retarget_block.index("n3w_runtime_request_disconnect", fenced)
    reconnect = retarget_block.index("n3w_runtime_request_reconnect", disconnect)
    assert switched < fenced < disconnect < reconnect
    assert "esp_mqtt_client_stop" not in retarget_block
    assert "portMAX_DELAY" not in retarget_block
    direct = block(
        relocation,
        "void SimpleProductComponent::advance_direct_mqtt_broker_relocation_()",
        "}  // namespace esphome::greenhouse_n3w_core",
    )
    assert "rollback_broker_candidate_();" in direct
    assert "stable_runtime_broker_host_ = pending_broker_candidate_host_" in direct
    assert "broker_store_" not in direct
    assert "peer_store_" not in direct


    rollback_body = block(
        relocation,
        "void SimpleProductComponent::rollback_broker_candidate_()",
        "bool SimpleProductComponent::start_broker_discovery_()",
    )
    assert "if (!restored)" in rollback_body
    assert "request_safe_reboot_(" in rollback_body


def test_discovery_and_candidate_windows_are_bounded() -> None:
    policy = text("n3w_broker_relocation_policy.h")
    session = text("n3w_esp32_manager_discovery_session.cpp")
    relocation = text("n3w_simple_product_component_broker_relocation.cpp")
    assert "kBrokerRelocationMqttFailureTriggerMs = 10000" in policy
    assert "kBrokerRelocationDiscoveryBudgetMs = 1000" in policy
    assert "kBrokerRelocationCandidateBudgetMs = 6000" in policy
    assert "kBrokerRelocationCleanupReserveMs = 2000" in policy
    assert "kBrokerRelocationDiscoveryMinIntervalMs = 60000" in policy
    assert "MSG_DONTWAIT" in session
    assert "kDiscoveryPollDatagramLimit = 2" in session
    assert "kDiscoveryCollectWindowMs = 1000" in session
    assert "current_wifi_ipv4_(&current_ipv4, &current_mask)" in relocation
    assert "current_ipv4 != broker_discovery_local_ipv4_" in relocation
    assert "current_mask != broker_discovery_subnet_mask_" in relocation
    assert "target.ttl_s == 0U" in relocation


def test_discovery_filter_is_same_system_same_subnet_and_source_bound() -> None:
    policy = text("n3w_manager_discovery_policy.cpp")
    header = text("n3w_manager_discovery.h")
    assert "candidate.system_id != context.expected_system_id" in policy
    assert "advertised == local" in policy
    assert "advertised != source" in policy
    assert "(advertised & mask) != (local & mask)" in policy
    assert "candidate.ttl_s == 0U" in policy
    assert "candidate.ttl_s > kManagerDiscoveryMaxCandidateTtlSeconds" in policy
    assert "kManagerDiscoveryMaxCandidateTtlSeconds = 120" in header


def test_mqtt_runtime_retarget_overlay_is_composed_and_nonblocking() -> None:
    init = text("__init__.py")
    tls = text("n3w_tls_server_name_patch.py.script")
    barrier = text("n3w_mqtt_retarget_barrier_patch.py.script")
    assert init.index("n3w_tls_server_name_patch.py.script") < init.index(
        "n3w_mqtt_retarget_barrier_patch.py.script"
    )
    assert "n3w_runtime_retarget_server" in tls
    assert "n3w_runtime_request_disconnect" in tls
    assert "n3w_runtime_request_reconnect" in tls
    assert "connection_generation_" in barrier
    assert "minimum_event_generation_" in barrier
    assert "MQTT_EVENT_BEFORE_CONNECT" in barrier
    assert "event->generation >= minimum_generation" in barrier
    assert "n3w_runtime_fence_old_events" in barrier
    assert "esp_mqtt_client_stop" not in barrier
    assert "portMAX_DELAY" not in barrier


def test_pairing_reuses_shared_discovery_without_losing_current_fields() -> None:
    pairing_header = text("n3w_simple_pairing_client.h")
    pairing = text("n3w_simple_pairing_client.cpp")
    assert '#include "n3w_manager_discovery.h"' in pairing_header
    assert "build_simple_discovery_query" in pairing
    assert "parse_simple_discovery_response" in pairing
    assert "struct SimpleManagerCandidateV2" not in pairing_header
    assert "firmware_version_" in pairing
    assert "pairing_handoff_ready_" in pairing
