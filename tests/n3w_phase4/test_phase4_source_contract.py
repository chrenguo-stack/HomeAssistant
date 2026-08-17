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


def test_generic_phase4_target_is_role_neutral_and_source_only() -> None:
    config = text(LAB / "generic.yml")
    assert "greenhouse_n3w_core:" in config
    assert "phase4_source_harness: true" in config
    assert "wifi:" not in config
    assert "mqtt:" not in config
    forbidden = (
        "node_id:",
        "system_id:",
        "setup_secret",
        "system_peer_key",
        "peer_mac",
        "gateway_id",
        "!secret",
    )
    assert not any(value in config.lower() for value in forbidden)


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
    assert "activate_radio(" not in component


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
