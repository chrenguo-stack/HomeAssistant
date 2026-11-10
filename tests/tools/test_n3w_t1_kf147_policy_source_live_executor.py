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
    / "kf147_policy_source_live_repair"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "KF147_STAGE_B_POLICY_SOURCE_REPAIR_R2_20261110_01"
)

EXPECTED_TARGETS = {
    "tools/n3w_t1_core_updater_ha_capacity.py",
    "tools/n3w_t1_core_updater_ha_ipc.py",
    "tools/n3w_t1_core_updater_ha_prepare.py",
    "tools/n3w_t1_core_updater_ha_prepare_host.py",
    "tools/n3w_t1_core_updater_ha_recovery_encoding.py",
    "tools/n3w_t1_core_updater_ha_usb.py",
    "infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json",
}


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_policy_source_live_executor_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_fail_closed_and_scope_is_minimal() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["schema"] == "gh.n3w-t1-kf147-policy-source-live-repair/1"
    assert doc["gate_id"] == GATE
    assert doc["authorization_id"] == GATE
    assert doc["live_execution_authorized"] is False
    assert doc["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert set(doc["source_authority"]) == EXPECTED_TARGETS | {
        "tools/n3w_t1_ssh_transport.py"
    }
    assert set(doc["predecessor_source_authority"]["files"]) == EXPECTED_TARGETS

    contract = doc["execution_contract"]
    assert contract["exact_seven_file_delta_only"] is True
    assert contract["host_source_mutation"] is True
    assert contract["host_release_policy_install"] is True
    assert contract["host_daemon_restart_only"] is True
    assert contract["services_owner_restart"] is False
    assert contract["manager_mutation"] is False
    assert contract["homeassistant_mutation"] is False
    assert contract["broker_mutation"] is False
    assert contract["prepare_replay"] is False
    assert contract["confirm_usb_erase"] is False
    assert contract["usb_mutation"] is False
    assert contract["u2_plus"] is False
    assert contract["automatic_retry"] is False
    assert contract["automatic_host_source_rollback"] is True
    assert contract["board_access"] is False
    assert contract["merge"] is False


def test_executor_target_set_matches_manifest_and_does_not_replace_wiring() -> None:
    module = load_executor()
    assert set(module.TARGETS) == EXPECTED_TARGETS
    remote_targets = set(module.TARGETS.values())
    assert "/etc/systemd/system/n3w-t1-ha-ota.service" not in remote_targets
    assert not any("docker-compose" in path for path in remote_targets)
    assert not any("services-activation" in path for path in remote_targets)


def test_remote_script_compiles_and_restarts_only_host_daemon() -> None:
    module = load_executor()
    compile(module.REMOTE_SCRIPT, "<kf147-stage-b-remote>", "exec")
    source = module.REMOTE_SCRIPT
    assert 'run(["systemctl", "stop", HOST_UNIT]' in source
    assert 'run(["systemctl", "start", HOST_UNIT]' in source
    assert 'run(["systemctl", "restart", SERVICES_UNIT]' not in source
    assert 'run(["systemctl", "stop", SERVICES_UNIT]' not in source
    assert 'run(["systemctl", "start", SERVICES_UNIT]' not in source
    assert '"wipefs"' not in source
    assert '"mkfs"' not in source
    assert '"parted"' not in source
    assert '"mount"' not in source
    assert "CONFIRM_USB_ERASE" not in source


def test_source_backup_precedes_claim_and_prepare_snapshot_is_frozen_after_claim() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    source_backup = source.index('backup_dir = stage_root / ".preclaim-backup"')
    state = source.index("state_root.mkdir(mode=0o700)")
    claim = source.index('state_root / "authorization_claim.json"')
    stop = source.index('run(["systemctl", "stop", HOST_UNIT]')
    prepare_backup = source.index('prepare_backup = backup_dir / "homeassistant-usb-prepare.json"')
    verify = source.index('raise Stop("prepare_backup_sha256_mismatch")')
    install = source.index('atomic_install(item["staged_path"], item["remote_path"])')
    assert source_backup < state < claim < stop < prepare_backup < verify < install


def test_rollback_restores_prepare_state_and_predecessor_source() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    assert 'prepare_backup = Path(backup_dir) / "homeassistant-usb-prepare.json"' in source
    assert "os.replace(temp, PREPARE_PATH)" in source
    assert "post = baseline(plan, require_snapshot=False)" in source
    assert 'result["status"] = "PASS"' in source


def test_post_validation_requires_v3_capacity_and_candidate_continuity() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    assert 'response.get("schema") != IPC_RESPONSE_V3' in source
    assert 'response.get("usb_required_bytes_or_null")' in source
    assert 'response.get("usb_recommended_nominal_gb_or_null")' in source
    assert 'candidate.get("public_fingerprint")' in source
    assert "wait_snapshot(plan)" in source
    assert "container_continuity_failed" in source


def test_expected_live_entry_binds_r2_manager_and_existing_u1_candidate() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = doc["expected_live_entry"]
    assert live["manager_image"] == "local/greenhouse-manager:fresh-44e7d7472714"
    assert live["manager_runtime_image_id"] == (
        "sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2"
    )
    assert live["manager_ipc_v3_support"] is True
    assert live["u1_transaction_sha256"] == (
        "6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49"
    )
    assert live["usb_candidate_public_fingerprint"] == (
        "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
    )
    assert live["usb_candidate_model"] == "Extreme"
    assert live["usb_candidate_capacity_bytes"] == 32017047552
    assert live["confirmation_required"] is True
    assert live["confirmation_consumed"] is False
    assert live["capacity_snapshot_present"] is False
