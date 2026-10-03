from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"


def text(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def test_gate_b_discovery_is_independent_from_pairing_state_machine() -> None:
    header = text("n3w_manager_discovery.h")
    discovery = text("n3w_manager_discovery.cpp")
    pairing = text("n3w_simple_pairing_client.cpp")

    assert "class SimpleManagerDiscovery" in header
    assert "class SimpleManagerDiscoveryNetwork" in header
    assert "class SimpleManagerDiscoveryRandom" in header
    assert "SimplePairingClient" not in header
    assert "SimpleManagerDiscovery::discover" in discovery

    run_start = pairing.index("SimplePairingClient::run_once")
    run_end = pairing.index("SimplePairingClient::resume_pending_ack", run_start)
    run_once = pairing[run_start:run_end]
    assert "if (provisioned_) return SimplePairingClientError::ALREADY_PROVISIONED;" in run_once


def test_gate_b_each_discovery_round_generates_fresh_request_material() -> None:
    discovery = text("n3w_manager_discovery.cpp")
    pairing = text("n3w_simple_pairing_client.cpp")

    session_start = discovery.index("SimpleManagerDiscovery::discover")
    session_end = discovery.index("bool build_simple_discovery_query", session_start)
    session = discovery[session_start:session_end]
    assert "std::array<uint8_t, 16> request_random{};" in session
    assert "std::array<uint8_t, 32> nonce_random{};" in session
    assert "fill_(request_random.data(), request_random.size())" in session
    assert "fill_(nonce_random.data(), nonce_random.size())" in session
    assert "build_simple_discovery_query(" in session

    pairing_start = pairing.index("SimplePairingClient::discover_")
    pairing_end = pairing.index("SimplePairingClient::send_hello_", pairing_start)
    pairing_discovery = pairing[pairing_start:pairing_end]
    assert "fill_(request_random.data(), request_random.size())" in pairing_discovery
    assert "fill_(nonce.data(), nonce.size())" in pairing_discovery
    assert "build_simple_discovery_query(" in pairing_discovery
    assert "parse_simple_discovery_response(" in pairing_discovery


def test_gate_b_discovery_protocol_correlates_request_id_and_nonce() -> None:
    discovery = text("n3w_manager_discovery.cpp")

    assert 'root["schema"] = "gh.discovery.query/1";' in discovery
    assert 'root["request_id"] = *request_id;' in discovery
    assert 'root["nonce"] = *nonce_text;' in discovery
    assert 'std::string(root["schema"] | "") != "gh.discovery.response/1"' in discovery
    assert 'std::string(root["request_id"] | "") != request_id' in discovery
    assert 'std::string(root["nonce"] | "") != nonce_text' in discovery


def test_gate_b_bounded_candidate_contract_is_frozen() -> None:
    header = text("n3w_manager_discovery.h")
    policy = text("n3w_manager_discovery_policy.cpp")
    discovery = text("n3w_manager_discovery.cpp")

    assert "kManagerDiscoveryMaxParsedDatagrams = 8" in header
    assert "kManagerDiscoveryMaxRetainedCandidates = 3" in header
    assert "kManagerDiscoveryMaxAttemptCandidates = 2" in header
    assert "kManagerDiscoveryMaxParsedDatagrams" in discovery
    assert "kManagerDiscoveryMaxRetainedCandidates" in policy
    assert "kManagerDiscoveryMaxAttemptCandidates" in policy


def test_gate_b_filters_system_subnet_unicast_and_source_binding() -> None:
    policy = text("n3w_manager_discovery_policy.cpp")

    assert "candidate.system_id != context.expected_system_id" in policy
    assert "!valid_unicast_ipv4(advertised)" in policy
    assert "advertised != source" in policy
    assert "(advertised & mask) != (local & mask)" in policy
    assert "advertised == network || advertised == broadcast" in policy


def test_gate_b_broker_target_uses_only_durable_port() -> None:
    policy = text("n3w_manager_discovery_policy.cpp")

    start = policy.index("make_simple_broker_recovery_targets")
    block = policy[start:]
    assert "durable_broker_port" in block
    assert "candidates[index].host" in block
    assert "candidates[index].port" not in block


def test_gate_b_discovery_has_no_trust_identity_or_nvs_mutation() -> None:
    combined = "\n".join(
        [
            text("n3w_manager_discovery.h"),
            text("n3w_manager_discovery.cpp"),
            text("n3w_manager_discovery_policy.cpp"),
        ]
    )

    forbidden = [
        "ca_pem",
        "broker_tls_server_name",
        "mqtt_username",
        "mqtt_password",
        "mqtt_client_id",
        "peer_trust_generation",
        "system_peer_key",
        "n3w_application_key",
        "Nvs",
        ".save(",
        ".erase(",
    ]
    for token in forbidden:
        assert token not in combined
