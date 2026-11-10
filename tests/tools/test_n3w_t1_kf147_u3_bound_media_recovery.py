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
    / "kf147_u3_bound_media_recovery"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U3_BOUND_MEDIA_RECOVERY_TO_U4_R4_20261111_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_u3_bound_media_recovery_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_successor_r4_manifest_binds_fresh_explicit_authorization() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["gate_id"] == GATE
    assert doc["authorization_id"] == GATE
    assert doc["confirmation"] == "EXECUTE KF147 U3 BOUND MEDIA RECOVERY TO U4 R4: YES"
    assert doc["state_root"].endswith("kf147-u3-bound-media-recovery-r4-20261111-01")
    assert doc["live_execution_authorized"] is True
    assert doc["authorization_state"] == {
        "granted": True,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }


def test_recovery_is_exact_existing_u3_to_u4_only() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = doc["expected_live_entry"]
    contract = doc["execution_contract"]
    assert live["transaction_id_sha256"] == (
        "ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738"
    )
    assert live["usb_filesystem_uuid"] == (
        "967cf065-abe5-49ee-8499-7c3f50d2c48f"
    )
    assert live["usb_candidate_public_fingerprint"] == (
        "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
    )
    assert contract["usb_wipe"] is False
    assert contract["usb_partition"] is False
    assert contract["usb_format"] is False
    assert contract["destructive_confirmation_replay"] is False
    assert contract["success_phase"] == "U4_READY_TO_INSTALL"
    assert contract["u5_plus"] is False


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-u3-bound-media-recovery>", "exec")
    assert module.GATE_ID == GATE


def test_remote_recovery_has_no_reformat_or_confirmation_replay_path() -> None:
    source = load_executor().REMOTE_SCRIPT
    forbidden = (
        '"wipefs"',
        '"sfdisk"',
        '"mkfs.ext4"',
        '"CONFIRM_USB_ERASE"',
        '"PREPARE"',
        "confirm_and_prepare",
        "authorize_destructive_format",
    )
    for token in forbidden:
        assert token not in source
    assert '"umount"' in source
    assert '["systemctl", "restart", SERVICE]' in source
    assert "U3_TARGET_DOWNLOADING_VERIFYING" in source
    assert "U4_READY_TO_INSTALL" in source


def test_authorization_claim_precedes_mount_cleanup_and_service_restart() -> None:
    source = load_executor().REMOTE_SCRIPT
    claim = source.index('durable_json(\n        state_root / "authorization_claim.json"')
    cleanup = source.index('run(["umount", postclaim["mount_target"]]')
    restart = source.index('run(["systemctl", "restart", SERVICE]')
    assert claim < cleanup < restart


def test_recovery_revalidates_same_u3_after_claim() -> None:
    source = load_executor().REMOTE_SCRIPT
    first = source.index("pre = validate_preflight(plan)")
    claim = source.index('state_root / "authorization_claim.json"')
    second = source.index("postclaim = validate_preflight(plan)")
    cleanup = source.index('run(["umount", postclaim["mount_target"]]')
    assert first < claim < second < cleanup


def test_success_requires_exact_u4_archive_and_container_continuity() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'tx.get("phase") != U4' in source
    assert 'tx.get("target_artifact_verified") is not True' in source
    assert 'target.stat().st_size != live["target_archive_size_bytes"]' in source
    assert 'sha_file(target) != live["target_archive_sha256"]' in source
    assert '"post_recovery_container_drift:" + key' in source
    assert '"u5_plus": False' in source


def test_preflight_rejects_current_bound_partition_mounted_or_live_stale_source() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert "bound_partition_mounted_unexpectedly" in source
    assert "current_bound_partition_already_mounted" in source
    assert "runtime_mount_source_still_live" in source
    assert "bound_usb_identity_mismatch" in source


def test_lsblk_json_requests_name_column_for_children_tree() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert '"NAME,PATH,TYPE,RM,RO,SIZE,MODEL,SERIAL,WWN,TRAN,MOUNTPOINTS,PKNAME"' in source

def test_mount_view_uses_exact_mountpoint_semantics() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert '["findmnt", "--noheadings", "--output", "SOURCE,TARGET", "--mountpoint", target]' in source
    assert '["findmnt", "--noheadings", "--output", "SOURCE,TARGET", "--target", target]' not in source


def test_usb_transaction_metadata_creates_private_update_parent_first() -> None:
    source = (
        ROOT / "tools" / "n3w_t1_core_updater_ha_prepare_host.py"
    ).read_text(encoding="utf-8")
    update_dir = source.index(
        'update_dir = Path(media.mount_path) / "n3w-update"'
    )
    update_check = source.index(
        "_require_private_directory(update_dir, create=True)",
        update_dir,
    )
    transaction_dir = source.index(
        'transaction_dir = update_dir / "transaction"',
        update_check,
    )
    transaction_check = source.index(
        "_require_private_directory(transaction_dir, create=True)",
        transaction_dir,
    )
    assert update_dir < update_check < transaction_dir < transaction_check


def test_remote_python_c_argument_contract_matches_remote_call() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    assert "import base64" in source
    assert "if len(sys.argv) != 5:" in source
    assert "execute(plan, sys.argv[2], sys.argv[3], sys.argv[4])" in source
    local_source = EXECUTOR.read_text(encoding="utf-8")
    assert (
        '["python3", "-c", REMOTE_SCRIPT, payload, authorization, confirmation, mode]'
        in local_source
    )
