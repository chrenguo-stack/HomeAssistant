from __future__ import annotations

import importlib.util
import json
import tarfile
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "docs/decisions/n3w-p5-two-board-isolated-e2e-prep-stage-entry.json"
PLAN = ROOT / "docs/decisions/n3w-p5-two-board-isolated-e2e-execution-plan.json"
PRIVATE_SCHEMA = (
    ROOT / "protocols/transport/schemas/gh.n3w-p5-private-input-1.schema.json"
)
EVIDENCE_SCHEMA = ROOT / "protocols/transport/schemas/gh.n3w-p5-evidence-1.schema.json"
CHILD = ROOT / "firmware/esphome_rc/board_lab/n3w_p5_two_board/child.yml"
RELAY = ROOT / "firmware/esphome_rc/board_lab/n3w_p5_two_board/relay.yml"
P5_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.cpp"
COMPOSE = ROOT / "infra/compose/n3w-p5-two-board-isolated/docker-compose.yml"
BUILDER = ROOT / "tools/n3w_p5/build_execution_template.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("n3w_p5_builder", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_entry_freezes_exact_preparation_boundary() -> None:
    doc = json.loads(STAGE.read_text(encoding="utf-8"))
    assert doc["base_sha"] == "8a57243fce0d347ebb20108f4ec5a2d5d4267486"
    assert doc["preserved_pr"] == 276
    assert doc["preserved_pr_head"] == "239ea594c643d4990d449187f8b0cabae619e3d7"
    assert doc["p4b_dependency"]["merged_pr"] == 291
    assert doc["mode"] == "PREPARATION_ONLY_NO_PHYSICAL_EXECUTION"
    assert doc["roles"]["child"]["holds_application_key"] is True
    assert doc["roles"]["relay"]["holds_application_key"] is False
    assert doc["contract"]["mesh"] is False
    assert doc["contract"]["multihop"] is False
    assert all(value is False for value in doc["safety_boundary"].values())
    assert doc["next_gate_status"].startswith("NOT_APPROVED")


def test_private_and_evidence_schemas_are_valid_and_secret_free_by_contract() -> None:
    private_schema = json.loads(PRIVATE_SCHEMA.read_text(encoding="utf-8"))
    evidence_schema = json.loads(EVIDENCE_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(private_schema)
    Draft202012Validator.check_schema(evidence_schema)
    candidate = {
        "schema": "gh.n3w-p5-private-input/1",
        "authorization_id": "D1-N3W-P5-PHYSICAL-TEST-ONLY",
        "repository_sha": "1" * 40,
        "system_id": "n3wp5lab",
        "node_id": "n3wp5_child01",
        "gateway_id": "n3wp5_relay01",
        "child_mac": "02:00:00:00:00:01",
        "relay_mac": "02:00:00:00:00:02",
        "wifi_channel": 6,
        "session_floor": 1000,
        "wifi": {"ssid": "p5-lab", "password": "x" * 16},
        "mqtt": {
            "host": "192.0.2.2",
            "port": 18883,
            "child_username": "p5child",
            "child_password": "a" * 20,
            "relay_username": "p5relay",
            "relay_password": "b" * 20,
            "manager_username": "manager",
            "manager_password": "c" * 20,
            "ha_username": "homeassistant",
            "ha_password": "d" * 20,
        },
        "keys": {
            "pmk_hex": "01" * 16,
            "lmk_hex": "02" * 16,
            "application_epoch_1_hex": "03" * 32,
            "application_epoch_2_hex": "04" * 32,
        },
    }
    Draft202012Validator(private_schema).validate(candidate)
    assert evidence_schema["properties"]["secret_values_included"]["const"] is False


def test_two_firmware_roles_are_compile_only_and_relay_has_no_application_key() -> None:
    child = CHILD.read_text(encoding="utf-8")
    relay = RELAY.read_text(encoding="utf-8")
    assert "role: child" in child
    assert "role: relay" in relay
    assert "execution_enabled: false" in child
    assert "execution_enabled: false" in relay
    assert "app_key_epoch1_hex" in child
    assert "app_key_epoch2_hex" in child
    assert "app_key_epoch1_hex" not in relay
    assert "app_key_epoch2_hex" not in relay
    for text in (child, relay):
        assert "esp32-c6-devkitm-1" in text
        assert "variant: ESP32C6" in text
        assert "flash_size: 8MB" in text
        assert "type: esp-idf" in text
        assert "greenhouse_n3w_core" in text
        assert "greenhouse_n3w_p5_lab" in text


def test_lab_runtime_reuses_p4a_p4b_and_keeps_relay_ciphertext_only() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    for token in (
        "BootSessionManager",
        "build_relay_frame",
        "fragment_relay_frame",
        "RelayIngressController",
        "encode_authenticated_probe",
        "decode_authenticated_probe",
        "ACCEPTED_FOR_FORWARDING",
        "global_mqtt_client->publish",
        "PATH DIRECT",
        "PATH RELAY",
        "KEY 1",
        "KEY 2",
        "RESEND",
        "REORDER",
    ):
        assert token in source
    assert "aes256gcm_decrypt" not in source
    assert "homeassistant/" not in source


def test_isolated_compose_is_nonproduction_and_n3w_enabled_only_inside_lab() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "GH_SYSTEM_ID: n3wp5lab" in text
    assert 'GH_N3W_RUNTIME_ENABLED: "true"' in text
    assert "18883" in text
    assert "allow_anonymous" not in text
    for forbidden in (
        "/opt/greenhouse",
        "production",
        "192.168.68.",
        "GH_SYSTEM_ID: greenhouse",
    ):
        assert forbidden not in text


def test_execution_plan_contains_full_p5_matrix_and_terminal_policy() -> None:
    doc = json.loads(PLAN.read_text(encoding="utf-8"))
    names = {item["name"] for item in doc["matrix"]}
    assert {
        "direct_to_relay",
        "relay_to_direct",
        "duplicate",
        "reorder",
        "late_old_frame",
        "child_restart",
        "relay_restart",
        "manager_restart",
        "authorization_revoke",
        "key_rotation",
        "broker_outage",
        "identity_continuity",
    } <= names
    assert doc["physical_execution_authorized"] is False
    assert "no_replay" in doc["terminal_attempt_policy"]


def test_public_execution_template_is_deterministic_and_contains_no_authorization(
    tmp_path: Path,
) -> None:
    builder = _load_builder()
    first = tmp_path / "first.tar"
    second = tmp_path / "second.tar"
    one = builder.build(first)
    two = builder.build(second)
    assert one["sha256"] == two["sha256"]
    assert one["physical_authorization_included"] is False
    assert one["secret_values_included"] is False
    with tarfile.open(first, "r") as archive:
        names = archive.getnames()
        assert "PUBLIC_TEMPLATE_BINDING.json" in names
        assert "SHA256SUMS" in names
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
        binding = json.load(archive.extractfile("PUBLIC_TEMPLATE_BINDING.json"))
    assert binding["physical_authorization_included"] is False
    assert binding["board_mac_binding_included"] is False
    assert binding["secret_values_included"] is False
