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


def test_gate_c_filter_rejects_self_and_unbounded_ttl() -> None:
    policy = text("n3w_manager_discovery_policy.cpp")
    header = text("n3w_manager_discovery.h")

    assert "advertised == local" in policy
    assert "candidate.ttl_s == 0U" in policy
    assert "candidate.ttl_s > kManagerDiscoveryMaxCandidateTtlSeconds" in policy
    assert "kManagerDiscoveryMaxCandidateTtlSeconds = 120" in header
