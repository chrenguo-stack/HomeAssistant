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
    "U3_PERMISSION_REPAIR_TO_U4_R5_20261111_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_u3_permission_recovery_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_r5_manifest_is_fail_closed_and_exact_scope() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["schema"] == "gh.n3w-t1-kf147-u3-permission-recovery-manifest/1"
    assert doc["gate_id"] == GATE
    assert doc["authorization_id"] == GATE
    assert doc["confirmation"] == "EXECUTE KF147 U3 PERMISSION REPAIR TO U4 R5: YES"
    assert doc["state_root"].endswith("kf147-u3-permission-recovery-r5-20261111-01")
    assert doc["live_execution_authorized"] is False
    assert doc["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    contract = doc["execution_contract"]
    assert contract["predecessor_r4_terminal_failure_required"] is True
    assert contract["usb_update_dir_permission_repair_only"] is True
    assert contract["usb_update_dir_expected_mode_before"] == "0770"
    assert contract["usb_update_dir_expected_mode_after"] == "0700"
    assert contract["usb_wipe"] is False
    assert contract["usb_partition"] is False
    assert contract["usb_format"] is False
    assert contract["destructive_confirmation_replay"] is False
    assert contract["u5_plus"] is False
    assert contract["merge"] is False


def test_recovery_is_exact_existing_u3_to_u4_only() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = doc["expected_live_entry"]
    assert live["transaction_id_sha256"] == (
        "ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738"
    )
    assert live["usb_filesystem_uuid"] == "967cf065-abe5-49ee-8499-7c3f50d2c48f"
    assert live["usb_candidate_public_fingerprint"] == (
        "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
    )
    assert live["target_archive_size_bytes"] == 835309535
    assert live["target_archive_sha256"] == (
        "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
    )


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-u3-permission-recovery>", "exec")
    assert module.GATE_ID == GATE
    assert module.CONFIRMATION == "EXECUTE KF147 U3 PERMISSION REPAIR TO U4 R5: YES"


def test_remote_recovery_has_no_reformat_repartition_or_destructive_replay() -> None:
    source = load_executor().REMOTE_SCRIPT
    forbidden = (
        '"wipefs"',
        '"sfdisk"',
        '"mkfs.ext4"',
        '"CONFIRM_USB_ERASE"',
        '"PREPARE"',
        "confirm_and_prepare",
        "authorize_destructive_format",
        'run(["umount"',
    )
    for token in forbidden:
        assert token not in source
    assert 'run(["systemctl", "restart", SERVICE]' in source
    assert "U3_TARGET_DOWNLOADING_VERIFYING" in source
    assert "U4_READY_TO_INSTALL" in source


def test_preflight_requires_terminal_r4_timeout_before_successor() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert "R4_FAILURE_PATH" in source
    assert '"Stop:u3_recovery_timeout"' in source
    assert "r4_terminal_failure_not_confirmed" in source
    first = source.index("r4_failure = read_json(")
    media = source.index("media = bound_partition(tx, live)")
    assert first < media


def test_preflight_binds_exact_live_permission_defect() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'update_dir["mode"] != 0o770' in source
    assert 'update_dir["uid"] != 0' in source
    assert 'update_dir["gid"] != 999' in source
    assert "usb_update_directory_precondition_drift" in source
    assert 'transaction_dir["mode"] != 0o700' in source
    assert "usb_target_directory_unexpectedly_present" in source
    assert "bound_partition_exact_mount_missing" in source


def test_authorization_claim_precedes_only_allowed_live_permission_repair() -> None:
    source = load_executor().REMOTE_SCRIPT
    claim = source.index('state_root / "authorization_claim.json"')
    postclaim = source.index("postclaim = validate_preflight(plan)")
    chmod = source.index("os.fchmod(descriptor, 0o700)")
    restart = source.index('run(["systemctl", "restart", SERVICE]')
    assert claim < postclaim < chmod < restart


def test_permission_repair_is_exact_0770_to_0700_and_fsynced() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'stat.S_IMODE(metadata.st_mode) != 0o770' in source
    assert "os.fchmod(descriptor, 0o700)" in source
    assert "os.fsync(descriptor)" in source
    assert 'repaired["mode"] != 0o700' in source
    assert '"before_mode": "0770"' in source
    assert '"after_mode": "0700"' in source


def test_success_requires_exact_u4_archive_and_container_continuity() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'tx.get("phase") != U4' in source
    assert 'tx.get("target_artifact_verified") is not True' in source
    assert 'target.stat().st_size != live["target_archive_size_bytes"]' in source
    assert 'sha_file(target) != live["target_archive_sha256"]' in source
    assert '"post_recovery_container_drift:" + key' in source
    assert '"u5_plus": False' in source


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
