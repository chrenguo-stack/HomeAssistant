from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "kf147_usb_u2_readonly_baseline"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "USB_CONFIRMATION_U2_FRESH_READONLY_BASELINE_20261110_01"
)

EXPECTED_LIVE = {
    "manager_image": "local/greenhouse-manager:fresh-44e7d7472714",
    "manager_runtime_image_id": (
        "sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2"
    ),
    "homeassistant_image": "local/n3w-homeassistant:2026.10.0-0c73235a",
    "homeassistant_runtime_image_id": (
        "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"
    ),
    "broker_image": "local/n3w-mosquitto:2.1.2-3184566d",
    "broker_runtime_image_id": (
        "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563"
    ),
    "u1_transaction_sha256": (
        "6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49"
    ),
    "usb_candidate_public_fingerprint": (
        "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
    ),
    "usb_candidate_model": "Extreme",
    "usb_candidate_capacity_bytes": 32017047552,
    "confirmation_required": True,
    "confirmation_consumed": False,
    "capacity_snapshot_present": True,
    "host_service_active": True,
    "services_owner_active": True,
}


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_usb_u2_readonly_baseline_executor_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_strictly_read_only_and_binds_last_proven_live_state() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["schema"] == "gh.n3w-t1-kf147-usb-u2-readonly-baseline/1"
    assert doc["gate_id"] == GATE
    assert doc["mode"] == "READ_ONLY"
    assert doc["live_execution_authorized"] is False
    assert doc["expected_live_entry"] == EXPECTED_LIVE
    assert doc["stop_boundary"] == (
        "STOP_AFTER_FRESH_READONLY_BASELINE_BEFORE_DESTRUCTIVE_AUTHORIZATION"
    )

    contract = doc["execution_contract"]
    assert contract == {
        "read_only": True,
        "remote_write": False,
        "service_restart": False,
        "docker_mutation": False,
        "host_source_mutation": False,
        "prepare_replay": False,
        "confirm_usb_erase": False,
        "usb_mutation": False,
        "u2_plus": False,
        "board_access": False,
        "merge": False,
    }


def test_package_authority_binds_executor_and_hardened_ssh_transport() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(doc["package_source_authority"]) == {
        "tools/execution_packages/n3w/r7a/"
        "kf147_usb_u2_readonly_baseline/executor.py",
        "tools/n3w_t1_ssh_transport.py",
    }
    for blob in doc["package_source_authority"].values():
        assert len(blob) == 40
        int(blob, 16)


def test_remote_authority_covers_stage_b_host_policy_and_runtime_wiring() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    authority = doc["remote_source_authority"]
    required = {
        "tools/n3w_t1_core_updater_ha_capacity.py",
        "tools/n3w_t1_core_updater_ha_ipc.py",
        "tools/n3w_t1_core_updater_ha_prepare.py",
        "tools/n3w_t1_core_updater_ha_prepare_host.py",
        "tools/n3w_t1_core_updater_ha_recovery_encoding.py",
        "tools/n3w_t1_core_updater_ha_usb.py",
        "tools/n3w_t1_core_updater_ha_daemon.py",
        "tools/n3w_t1_core_updater_ha_usb_state.py",
        "tools/n3w_t1_core_updater_ha_usb_media.py",
        "tools/n3w_t1_core_updater_v2_common.py",
        "infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json",
        "infra/n3w-t1/upgrades/homeassistant-2026.10.4-approved.json",
        "infra/n3w-t1/production/docker-compose.ha-ota.yml",
        "infra/n3w-t1/systemd/n3w-t1-ha-ota.service",
        "infra/n3w-t1/systemd/n3wfc4-services-activation.ha-ota.conf",
    }
    assert set(authority) == required
    for item in authority.values():
        assert set(item) == {"blob", "remote_path"}
        assert len(item["blob"]) == 40
        int(item["blob"], 16)
        assert item["remote_path"].startswith("/")


def test_remote_script_compiles_and_contains_no_destructive_usb_or_service_actions() -> None:
    module = load_executor()
    compile(module.REMOTE_SCRIPT, "<kf147-usb-u2-readonly>", "exec")
    source = module.REMOTE_SCRIPT
    forbidden = (
        "wipefs",
        "sfdisk",
        "mkfs.",
        "parted",
        "docker load",
        "docker rm",
        '["systemctl", "stop"',
        '["systemctl", "start"',
        '["systemctl", "restart"',
        "CONFIRM_USB_ERASE",
        "T1_HOMEASSISTANT_USB_FORMAT_ALL_DATA",
    )
    for token in forbidden:
        assert token not in source


def test_remote_script_revalidates_u1_candidate_capacity_and_ipc_v3() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    assert '"U1_PREPARE_REQUESTED"' in source
    assert '"ACTIVE"' in source
    assert '"confirmation_required"' in source
    assert '"confirmation_consumed"' in source
    assert '"usb_required_bytes"' in source
    assert '"recommended_nominal_usb_gb"' in source
    assert '"CANDIDATE_READY_FOR_CONFIRMATION"' in source
    assert '"USB_REQUIRED_CONFIRMATION"' in source
    assert '"USB_CONFIRM_ERASE"' in source
    assert "usb_physical_candidate_drift:" in source
    assert "remote_authority_drift:" in source


def test_executor_result_cannot_claim_destructive_readiness() -> None:
    module = load_executor()
    source = EXECUTOR.read_text(encoding="utf-8")
    assert '"destructive_execution_ready": False' in source
    assert '"usb_mutation": False' in source
    assert '"u2_plus": False' in source
    assert '"remote_write": False' in source
    assert '"service_restart": False' in source
    assert '"docker_mutation": False' in source
    assert module.GATE_ID == GATE
