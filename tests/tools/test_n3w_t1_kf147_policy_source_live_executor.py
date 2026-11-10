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

EXPECTED_UNCHANGED = {
    "tools/n3w_t1_core_updater_ha_daemon.py",
    "tools/n3w_t1_core_updater_ha_usb_state.py",
    "tools/n3w_t1_core_updater_ha_usb_media.py",
    "tools/n3w_t1_core_updater_ha_backup.py",
    "tools/n3w_t1_core_updater_ha_recovery.py",
    "tools/n3w_t1_core_updater_v2_common.py",
    "tools/n3w_t1_core_updater_v2_state.py",
    "tools/n3w_t1_core_updater_common.py",
    "tools/n3w_t1_portable_image_identity.py",
    "infra/n3w-t1/production/docker-compose.ha-ota.yml",
    "infra/n3w-t1/systemd/n3w-t1-ha-ota.service",
    "infra/n3w-t1/systemd/n3wfc4-services-activation.ha-ota.conf",
    "infra/n3w-t1/upgrades/homeassistant-2026.10.4-approved.json",
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
    assert doc["predecessor_source_authority"]["source_head"] == (
        "70aaa4070641dd73c1a97738e6332be31403d45e"
    )
    assert set(doc["unchanged_live_authority"]) == EXPECTED_UNCHANGED
    assert EXPECTED_TARGETS.isdisjoint(EXPECTED_UNCHANGED)
    for authority in doc["unchanged_live_authority"].values():
        assert set(authority) == {"blob", "remote_path"}
        assert authority["remote_path"].startswith("/")

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


def test_unchanged_a1r_dependencies_are_read_only_preflight_inputs() -> None:
    module = load_executor()
    assert set(module.TARGETS).isdisjoint(EXPECTED_UNCHANGED)
    source = module.REMOTE_SCRIPT
    assert "def dependency_prestate(plan):" in source
    assert 'raise Stop("unchanged_dependency_drift:" + item["repo_path"])' in source
    assert '"dependencies": dependencies' in source


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
    rollback_start = source.index("def rollback(plan, backup_dir, pre):")
    rollback_stop = source.index('run(["systemctl", "stop", HOST_UNIT]', rollback_start)
    restore_loop = source.index('for item in plan["files"]:', rollback_stop)
    prepare_restore = source.index(
        'prepare_backup = Path(backup_dir) / "homeassistant-usb-prepare.json"',
        restore_loop,
    )
    restart = source.index('run(["systemctl", "start", HOST_UNIT]', prepare_restore)
    assert rollback_start < rollback_stop < restore_loop < prepare_restore < restart
    assert "wait_host_inactive()" in source[rollback_stop:restore_loop]
    assert "os.replace(temp, PREPARE_PATH)" in source
    assert "post = baseline(plan, require_snapshot=False)" in source
    assert 'result["status"] = "PASS"' in source


def test_preflight_binds_manager_ota_env_and_readonly_runtime_mount() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    assert 'require_manager_ota_wiring(manager)' in source
    assert '"GH_N3W_T1_OTA_ENABLED": "true"' in source
    assert '"GH_N3W_T1_OTA_INSTALLED_VERSION": "2026.10.0"' in source
    assert '"GH_N3W_T1_OTA_MANIFEST_PATH": "/run/n3w/t1-ota/approved-homeassistant.json"' in source
    assert '"GH_N3W_T1_OTA_SOCKET_PATH": "/run/n3w/t1-ota/ha-ota.sock"' in source
    assert 'item.get("Destination") == "/run/n3w/t1-ota"' in source
    assert 'matches[0].get("Source") != "/run/n3w-t1-ota"' in source
    assert 'matches[0].get("RW") is not False' in source


def test_manager_ipc_probe_uses_container_socket_path() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    probe_start = source.index("def manager_ipc_probe")
    probe_end = source.index("\ndef target_files", probe_start)
    probe = source[probe_start:probe_end]
    assert 'path = "/run/n3w/t1-ota/ha-ota.sock"' in probe
    assert 'path = "/run/n3w-t1-ota/ha-ota.sock"' not in probe


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
