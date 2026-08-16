from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
LAB = ROOT / "firmware/esphome_rc/board_lab/n3w_phase3_simple"

PRODUCTION_FILES = (
    CORE / "n3w_simple_crypto.h",
    CORE / "n3w_simple_crypto.cpp",
    CORE / "n3w_compact_telemetry.h",
    CORE / "n3w_compact_telemetry.cpp",
    CORE / "n3w_simple_runtime.h",
    CORE / "n3w_simple_runtime.cpp",
    CORE / "n3w_esp32_simple_nvs.h",
    CORE / "n3w_esp32_simple_nvs.cpp",
)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_compact_frame_is_single_datagram_and_gateway_independent() -> None:
    header = text(CORE / "n3w_compact_telemetry.h")
    source = text(CORE / "n3w_compact_telemetry.cpp")
    assert "kEspNowV2PayloadLimit = 1470" in header
    assert "kCompactTelemetryHeaderBytes = 48" in header
    assert "kMaxCiphertextBytes" in header
    assert "fragment_index" not in source
    assert "fragment_count" not in source
    assert "ReceiptAck" not in source
    assert "gateway_id" not in source
    assert '"gh.relay/2"' in source


def test_setup_secret_is_device_generated_and_not_factory_baked() -> None:
    nvs = text(CORE / "n3w_esp32_simple_nvs.cpp")
    assert "esp_fill_random(record.secret" in nvs
    assert "NvsSetupSecretStore::load_or_create" in nvs
    assert "NvsSetupSecretStore::erase" in nvs
    for path in PRODUCTION_FILES:
        value = text(path)
        assert not re.search(r'(?i)\b[0-9a-f]{64}\b', value), path


def test_peer_trust_has_no_manager_grant_or_static_peer_binding() -> None:
    combined = "\n".join(text(path) for path in PRODUCTION_FILES)
    forbidden = (
        "authorization_id",
        "grant_ttl",
        "peer_grant",
        "request_peer_authorization",
        "manager_eligibility",
        "PATH_COMMAND",
    )
    assert not any(value in combined for value in forbidden)
    assert "derive_pair_lmk_v2" in combined
    assert "build_peer_proof_v2" in combined
    assert "peer_trust_generation" in combined


def test_compile_targets_are_role_neutral_generic_firmware() -> None:
    child = text(LAB / "child.yml")
    relay = text(LAB / "relay.yml")
    for value in (child, relay):
        assert "greenhouse_n3w_core:" in value
        assert "peer_mac" not in value
        assert "system_peer_key" not in value
        assert "setup_secret" not in value
        assert "node_id:" not in value
        assert "gateway_id" not in value
        assert "!secret" not in value
    normalized_child = child.replace("gh-n3w-phase3-child", "gh-n3w-phase3-role")
    normalized_relay = relay.replace("gh-n3w-phase3-relay", "gh-n3w-phase3-role")
    assert normalized_child == normalized_relay
