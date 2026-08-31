from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
LAB = ROOT / "firmware/esphome_rc/board_lab/n3w_phase4_physical"
MANAGER = ROOT / "host/greenhouse-manager/src/greenhouse_manager/runtime"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_concrete_driver_accepts_new_single_frame_budget_without_rewriting_legacy_contract() -> None:
    driver_header = text(CORE / "n3w_espnow_driver.h")
    driver_source = text(CORE / "n3w_espnow_driver.cpp")
    radio_header = text(CORE / "n3w_radio.h")
    compact_header = text(CORE / "n3w_compact_telemetry.h")

    assert "kEspNowPhysicalDatagramLimit = 1470" in driver_header
    assert "kEspNowV2PayloadLimit = 1470" in compact_header
    assert "kCompactTelemetryMaxWireBytes" in compact_header
    assert "size > kEspNowPhysicalDatagramLimit" in driver_source
    assert "kEspNowDatagramLimit = 240" in radio_header
    assert "kDataFragmentPayloadBytes = 180" in radio_header


def test_simplified_runtime_reuses_connected_sta_channel_without_init_thrash() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")
    header = text(CORE / "n3w_simple_product_component.h")
    start = source.index("bool SimpleProductComponent::start_runtime_if_ready_()")
    end = source.index("void SimpleProductComponent::advance_pairing_()", start)
    body = source[start:end]

    retry_gate = body.index(
        "now - last_radio_attempt_ms_ < kRadioRetryIntervalMs"
    )
    current_channel = body.index("esp_wifi_get_channel")
    initialize = body.index("radio_.initialize")
    broadcast_peer = body.index("radio_.prepare_broadcast_peer")

    assert retry_gate < current_channel < initialize < broadcast_peer
    assert "radio_.set_channel" not in body
    assert "ESP-NOW initialization failed error=%u" in body
    assert "ESP-NOW broadcast peer configuration failed error=%u" in body
    assert "Simplified N3-W runtime start failed error=%u" in body
    assert "bool radio_attempted_{false};" in header
    assert "uint64_t last_radio_attempt_ms_{0};" in header


def test_simplified_port_never_mutates_an_associated_sta_channel() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")
    runtime = text(CORE / "n3w_simple_product_runtime.cpp")

    start = source.index("bool SimpleProductComponent::set_radio_channel(uint8_t channel)")
    end = source.index("bool SimpleProductComponent::broadcast_control", start)
    body = source[start:end]

    wifi_gate = body.index("if (wifi_connected())")
    observe_channel = body.index("esp_wifi_get_channel", wifi_gate)
    same_channel_success = body.index("return current_channel == channel", observe_channel)
    driver_mutation = body.index("return radio_.set_channel(channel)", same_channel_success)

    assert wifi_gate < observe_channel < same_channel_success < driver_mutation
    assert body.count("radio_.set_channel(channel)") == 1
    assert body.count("esp_wifi_get_channel") == 1

    runtime_start = runtime.index("SimpleProductError SimpleProductRuntime::start(")
    runtime_stop = runtime.index("void SimpleProductRuntime::stop()", runtime_start)
    runtime_body = runtime[runtime_start:runtime_stop]

    # Runtime start intentionally keeps the generic port contract. The concrete
    # ESP32 product adapter must make an idempotent request for the already-owned
    # STA channel a no-op, so this indirect path can no longer reach
    # esp_wifi_set_channel() while associated.
    assert "port_->set_radio_channel(direct_channel_)" in runtime_body


def test_generic_phase4_target_is_role_neutral_and_first_use_ready() -> None:
    config = text(LAB / "generic.yml")
    lowered = config.lower()
    assert "greenhouse_n3w_core:" in config
    assert "id: n3w_phase4_core" in config
    assert "phase4_source_harness: true" in config
    assert "phase4_product_runtime: true" in config
    assert "wifi:" in config
    assert "captive_portal:" in config
    assert "mqtt:" in config
    assert "enable_on_boot: false" in config
    assert "broker: 127.0.0.1" in config
    assert 'ssid: "Greenhouse N3-W Setup"' in config
    forbidden = (
        "node_id:",
        "system_id:",
        "setup_secret",
        "system_peer_key",
        "peer_mac",
        "gateway_id",
        "mqtt_username",
        "mqtt_password",
        "!secret",
    )
    assert not any(value in lowered for value in forbidden)


def test_phase4_lab_target_exposes_private_pairing_pop_and_synthetic_telemetry() -> None:
    config = text(LAB / "generic.yml")
    component = text(CORE / "n3w_simple_product_component.h")
    core = text(CORE / "greenhouse_n3w_core.h")

    assert "PHASE4_PAIRING_QR_PAYLOAD=%s" in config
    assert "pairing_qr_payload()" in config
    assert "runtime_ready()" in config
    assert "take_telemetry_identity" in config
    assert "send_telemetry_json" in config
    assert "PHASE4_LAB_TELEMETRY" in config
    assert "phase4_lab" in config
    assert "uptime_ms" in config
    assert "cap_hash" in config
    assert "measurements" in config
    assert "quality" in config
    assert "power" in config
    assert "std::array<uint8_t, 8> random_boot" not in config
    assert "static uint32_t seq" not in config
    assert "NvsBootSessionStore boot_session_store_{};" in core
    assert "BootSessionManager boot_session_manager_{};" in core
    assert "provision_recovery_floor" in core
    assert "fresh_identity_candidate_" in core
    assert "id(n3w_phase4_core).node_id()" in config
    assert "const std::string &node_id() const { return peer_state_.node_id; }" in component

    # Physical-lab stimulus remains role neutral and derives all identities at runtime.
    for forbidden in (
        "node_child",
        "node_relay",
        "gh-system-01",
    ):
        assert forbidden not in config.lower()


def test_source_harness_binds_real_adapters_without_executing_them() -> None:
    header = text(CORE / "n3w_phase4_physical_harness.h")
    source = text(CORE / "n3w_phase4_physical_harness.cpp")
    component = text(CORE / "greenhouse_n3w_core.h")

    for symbol in (
        "EspNowDriver",
        "LocalPathController",
        "NvsSetupSecretStore",
        "NvsProvisionedPeerStoreV2",
        "send_compact_unicast",
        "install_authenticated_peer",
    ):
        assert symbol in header
    assert "prepare_source_only" in source
    assert "phase4_harness_.prepare_source_only()" in component
    assert "SimpleProductComponent::setup()" in component
    assert "set_phase4_product_runtime_enabled" in component


def test_simplified_product_runtime_excludes_legacy_path_and_finite_grants() -> None:
    scope = "\n".join(
        text(CORE / name)
        for name in (
            "n3w_simple_product_runtime.h",
            "n3w_simple_product_runtime.cpp",
            "n3w_simple_product_component.h",
            "n3w_simple_product_component.cpp",
            "n3w_simple_pairing_client.h",
            "n3w_simple_pairing_client.cpp",
        )
    )
    required = (
        "SimpleProductRuntime",
        "NvsSetupSecretStore",
        "NvsProvisionedPeerStoreV2",
        "NvsProvisionedBrokerStoreV2",
        "PendingPairingAckV2",
        "send_encrypted_peer",
        "note_direct_recovery_probe",
    )
    assert all(value in scope for value in required)
    forbidden = (
        "n3w_runtime_wiring",
        "PeerAuthorizationV2",
        "peer_grant",
        "grant_ttl",
        "PATH_COMMAND",
        "ChildRelayCache",
        "DATA_FRAGMENT",
        "RECEIPT_ACK",
        "RESEND",
        "REORDER",
        "X25519",
    )
    assert not any(value in scope for value in forbidden)


def test_manager_phase4_harness_uses_only_simplified_ingress_and_auto_id() -> None:
    source = text(MANAGER / "n3w_phase4_isolated_harness.py")
    required = (
        "AutomaticNodeIdApprover",
        "N3wCanonicalIngressCoordinator",
        "CompactRelayIngressCore",
        "N3wMultiIngressRouter",
    )
    assert all(value in source for value in required)
    forbidden = (
        "n3w_runtime_wiring",
        "peer_grant",
        "grant_ttl",
        "PATH_COMMAND",
        "ChildRelayCache",
        "DATA_FRAGMENT",
        "RECEIPT_ACK",
        "RESEND",
        "REORDER",
    )
    assert not any(value in source for value in forbidden)


def test_simplified_manager_network_entrypoints_remain_opt_in() -> None:
    mqtt_service = text(MANAGER / "n3w_simplified_isolated_mqtt_service.py")
    pairing_runtime = text(MANAGER / "n3w_simplified_pairing_runtime.py")
    normal_app = text(MANAGER / "app.py")

    assert "replace(settings, n3w_runtime_enabled=False)" in mqtt_service
    assert "N3wMultiIngressRouter" not in normal_app
    assert "SimplifiedPairingRuntime" not in normal_app
    assert "assemble_simplified_pairing_runtime" in pairing_runtime

def test_tls_server_name_repair_separates_tcp_target_from_tls_identity() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")
    start = source.index("bool SimpleProductComponent::configure_mqtt_()")
    end = source.index("bool SimpleProductComponent::derive_pmk_", start)
    body = source[start:end]

    tcp_target = body.index(
        "set_broker_address(broker_state_.broker_host)"
    )
    tls_identity = body.index(
        "set_tls_server_name(\n"
        "      broker_state_.broker_tls_server_name)"
    )
    ca_binding = body.index(
        "set_ca_certificate(broker_state_.ca_pem.c_str())"
    )
    enable = body.index("enable();", ca_binding)

    assert tcp_target < tls_identity < ca_binding < enable
    assert (
        "set_broker_address(broker_state_.broker_tls_server_name)"
        not in body
    )
    assert "set_skip_cert_cn_check(true)" not in body


def test_tls_server_name_patch_carrier_is_exact_generated_source_overlay() -> None:
    init_candidates = list(CORE.glob("??init??.py"))
    assert len(init_candidates) == 1
    component_init = text(init_candidates[0])
    patch = text(CORE / "n3w_tls_server_name_patch.py.script")

    assert "add_extra_script(" in component_init
    assert '"pre",' in component_init
    assert '"n3w_tls_server_name_patch.py",' in component_init
    assert '"n3w_tls_server_name_patch.py.script"' in component_init

    assert 'EXPECTED_ESPHOME_VERSION = "2026.4.3"' in patch
    assert "14473f737a0739f043b154dd1ea3e55012ca2096" in patch
    assert "58d1b29b3258a1fcae99b23f67c99a728ea0992c" in patch

    assert 'TARGET_NAMES = (' in patch
    assert '"mqtt_client.h",' in patch
    assert '"mqtt_backend_esp32.h",' in patch
    assert '"mqtt_backend_esp32.cpp"' not in patch

    assert 'env.subst("$PROJECT_SRC_DIR")' in patch
    assert '"esphome" / "components" / "mqtt"' in patch
    assert "broker.verification.common_name" in patch
    assert "tls_server_name_" in patch

    assert "skip_cert_common_name_check = true" not in patch
    assert "site-packages" not in patch.lower()
    assert "requests." not in patch
    assert "urllib" not in patch
