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

    assert "PHASE4_PAIRING_QR_PAYLOAD=%s" in config
    assert "pairing_qr_payload()" in config
    assert "runtime_ready()" in config
    assert "send_telemetry_json" in config
    assert "PHASE4_LAB_TELEMETRY" in config
    assert "phase4_lab" in config
    assert "uptime_ms" in config
    assert "cap_hash" in config
    assert "measurements" in config
    assert "quality" in config
    assert "power" in config
    assert "std::array<uint8_t, 8> random_boot" in config
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
