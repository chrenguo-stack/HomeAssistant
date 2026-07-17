from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPONENT = ROOT / "firmware/esphome_rc/components/greenhouse_mqtt_auth"
CPP = COMPONENT / "greenhouse_mqtt_auth.cpp"
HEADER = COMPONENT / "greenhouse_mqtt_auth.h"
PYTHON = COMPONENT / "__init__.py"
YAML = ROOT / "firmware/esphome_rc/tests/greenhouse_mqtt_auth_compile.yml"
WORKFLOW = ROOT / ".github/workflows/m2-esphome-node-auth-adapter-ci.yml"
CONTRACT = ROOT / "protocols/pairing/gh-node-esphome-mqtt-boot-profile-adapter-v1.md"


def test_adapter_files_are_present() -> None:
    for path in (CPP, HEADER, PYTHON, YAML, WORKFLOW, CONTRACT):
        assert path.is_file(), path


def test_profile_is_applied_before_mqtt_setup() -> None:
    source = CPP.read_text(encoding="utf-8")

    assert "setup_priority::DATA" in source
    assert "set_username" in source
    assert "set_password" in source
    assert "set_client_id" in source
    assert "apply_boot_profile_" in source


def test_adapter_does_not_claim_runtime_credential_switching() -> None:
    source = CPP.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")

    assert "mqtt_client_->disable()" not in source
    assert "mqtt_client_->enable()" not in source
    assert "switch_to_candidate_" not in header
    assert "switch_to_anonymous_" not in header
    assert "App.safe_reboot()" in source


def test_persisted_state_contains_no_secret_material() -> None:
    header = HEADER.read_text(encoding="utf-8")
    state = header.split("struct PersistedState", 1)[1].split("};", 1)[0]

    assert "std::string" not in state
    assert "password" not in state.lower()
    assert "username" not in state.lower()
    assert "client_id" not in state.lower()
    assert "ESPPreferenceObject" in header


def test_esp_idf_disconnect_is_treated_as_generic() -> None:
    source = CPP.read_text(encoding="utf-8")
    contract = CONTRACT.read_text(encoding="utf-8")

    assert "generic_candidate_connection_failure" in source
    assert "never claim an authentication-specific reason" in source
    assert "认证拒绝原因不可精确归因" in contract
    assert "is_authentication_failure_" not in source


def test_compile_target_is_non_production_and_secret_indirect() -> None:
    config = YAML.read_text(encoding="utf-8")

    assert "broker: 192.0.2.10" in config
    assert "candidate_password: !secret mqtt_candidate_password" in config
    assert "candidate_client_id: ci-node" in config
    assert "anonymous_client_id: ci-node-anon" in config
    assert "gh-n1-a9f2f8" not in config


def test_workflow_pins_esphome_and_scans_logs() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'esphome==2026.4.3' in workflow
    assert "esphome config greenhouse_mqtt_auth_compile.yml" in workflow
    assert "esphome compile greenhouse_mqtt_auth_compile.yml" in workflow
    assert "ephemeral secret appeared in ESPHome output" in workflow
    assert "if: always()" in workflow


def test_contract_preserves_all_production_safety_boundaries() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    for statement in (
        "anonymous 必须继续开启",
        "不访问 Home Assistant `.storage`",
        "不生成或下发生产节点凭据",
        "不升级生产节点固件",
        "不修改生产 T1",
        "ready_for_live_apply=false",
        "ready_for_anonymous_closure=false",
    ):
        assert statement in contract
