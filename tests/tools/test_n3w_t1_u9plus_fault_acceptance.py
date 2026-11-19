from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_p3_u1_u4_recovery" / "u9plus_fault_acceptance.py"
)
MANIFEST = SCRIPT.with_name("u9plus_fault_acceptance_manifest.json")


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_source_compiles_and_binds_current_consumed_u9() -> None:
    text = source()
    compile(text, str(SCRIPT), "exec")
    value = manifest()
    assert value["current_u9"]["transaction_sha256"] == (
        "2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b"
    )
    assert value["current_u9"]["authorization_consumed"] is True
    assert value["current_u9"]["replay_permitted"] is False


def test_gate_authorizes_only_phase_a_u10_and_recovery() -> None:
    value = manifest()
    assert value["live_execution_authorized"] is True
    assert value["destructive_u10_authorized"] is True
    assert value["candidate_daemon_override_authorized"] is True
    assert value["product_u9_reclaim_authorized"] is False
    assert value["product_u9_replay_authorized"] is False
    assert value["target_image_load_authorized"] is False
    assert value["u11_plus_authorized"] is False
    assert value["merge"] is False


def test_source_has_no_target_install_or_u11_transition() -> None:
    text = source()
    assert "HaUsbU11TargetInstallController" not in text
    assert "record_target_accepted" not in text
    assert "record_commit" not in text
    assert '["docker", "load"' not in text
    assert "u11_plus=False" in text or '"u11_plus": False' in text


def test_u10_syncs_bound_usb_before_host_transaction() -> None:
    text = source()
    sync = text.index("backend.sync_transaction_metadata(u10, media)")
    write = text.index("store.write(u10)", sync)
    assert sync < write
    assert "record_predecessor_capacity_released(" in text
    assert "claim_live_authorization(" not in text


def test_candidate_daemon_is_temporary_override_without_product_source_overwrite() -> None:
    text = source()
    assert "90-u9plus-fault-acceptance.conf" in text
    assert "ExecStart=" in text
    assert "daemon-reload" in text
    assert "ota_daemon_restarted_during_override_install" in text
    assert "shutil.copy" not in text
    assert "os.replace(CANDIDATE_DIR" not in text
    assert "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_daemon.py" in text


def test_physical_fault_checkpoints_are_required() -> None:
    text = source()
    assert "POWER_OFF_T1_THEN_REMOVE_BOUND_USB_THEN_POWER_ON" in text
    assert "RECOVERY_MEDIA_REQUIRED" in text
    assert "POWER_OFF_T1_THEN_REINSERT_SAME_BOUND_USB_THEN_POWER_ON" in text
    assert "second_power_cycle_not_observed" in text
    assert 'tx.get("rollback_origin_phase") == U10' in text


def test_phase_a_does_not_claim_customer_downtime_sla() -> None:
    text = source()
    assert '"customer_downtime_sla_proven": False' in text
    assert "lab_u10_to_recovered_seconds_includes_operator_hold" in text
    assert "automatic_recovery_seconds_from_second_boot" in text


def test_recovery_requires_kf140_safe_candidate_sources() -> None:
    text = source()
    assert "n3w_t1_core_updater_ha_u13b_host.py" in text
    assert "n3w_t1_core_updater_ha_u13b_auto.py" in text
    assert "n3w_t1_core_updater_ha_ipc.py" in text
    assert "candidate_source_blob_drift" in text


def test_missing_media_observation_is_read_only_and_stays_u10() -> None:
    text = source()
    start = text.index("def observe_missing(")
    end = text.index("def verify_recovered(", start)
    block = text[start:end]
    assert 'tx.get("phase") == U10' in block
    assert '"RECOVERY_MEDIA_REQUIRED"' in block
    assert "docker\", \"rm" not in block
    assert "store.write(" not in block


def test_terminal_recovery_requires_u13b_from_u10_and_no_target() -> None:
    text = source()
    start = text.index("def verify_recovered(")
    end = text.index("def remote_main(", start)
    block = text[start:end]
    assert 'tx.get("phase") == U13B' in block
    assert 'tx.get("rollback_origin_phase") == U10' in block
    assert 'tx.get("rollback_ha_data_restored") is True' in block
    assert 'tx.get("rollback_health_verified") is True' in block
    assert "target_image_present_after_rollback" in block


def test_bootstrap_dependency_order_prevents_remote_import_failure() -> None:
    text = source()
    start = text.index("def bootstrap_for_remote():")
    end = text.index("def source_check(", start)
    block = text[start:end]
    ordered = [
        '("u6_recovery", u6_recovery)',
        '("check_ha_backup", check_ha_backup)',
        '("ha_backup", ha_backup)',
        '("recovery_admission", u8)',
        '("u9_live_authorization", u9)',
        '("u10_preflight", u10_preflight)',
    ]
    positions = [block.index(item) for item in ordered]
    assert positions == sorted(positions)


def test_remote_stdout_empty_preserves_stderr_diagnostic() -> None:
    text = source()
    assert 'completed.stderr.strip().replace("\\n", " ")[:600]' in text
    assert '"remote_stdout_empty" + (":" + stderr if stderr else "")' in text
