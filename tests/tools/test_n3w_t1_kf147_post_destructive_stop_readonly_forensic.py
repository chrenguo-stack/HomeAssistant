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
    / "kf147_post_destructive_stop_readonly_forensic"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "POST_DESTRUCTIVE_STOP_READONLY_FORENSIC_20261110_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_post_destructive_stop_readonly_forensic_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_readonly_and_predecessor_authorization_is_consumed() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["schema"] == (
        "gh.n3w-t1-kf147-post-destructive-stop-readonly-forensic/1"
    )
    assert doc["gate_id"] == GATE
    assert doc["mode"] == "READ_ONLY_FORENSIC"
    assert doc["predecessor_execution_head"] == (
        "ff6370c3b9e46e1ddf20409915e1b10dabb6e286"
    )
    assert doc["predecessor_result"] == {
        "status": "STOP",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "first_failed_operation": (
            "Stop:prepare_worker_error:ha_usb_prepare_worker_inactive"
        ),
    }
    assert doc["execution_contract"] == {
        "read_only": True,
        "remote_write": False,
        "service_restart": False,
        "docker_mutation": False,
        "usb_mutation": False,
        "authorization_replay": False,
        "u5_plus": False,
        "board_access": False,
        "merge": False,
    }


def test_executor_and_remote_probe_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-post-stop-forensic>", "exec")
    assert module.GATE_ID == GATE


def test_remote_probe_has_no_mutation_or_authorization_replay_path() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    forbidden = (
        '"wipefs"',
        '"sfdisk"',
        '"mkfs.ext4"',
        '"mount"',
        '"umount"',
        '["systemctl", "start"',
        '["systemctl", "stop"',
        '["systemctl", "restart"',
        '"docker load"',
        '"docker rm"',
        '"CONFIRM_USB_ERASE"',
        '"PREPARE"',
        "resume_prepare",
        "confirm_and_prepare",
    )
    for token in forbidden:
        assert token not in source
    assert '"systemctl",' in source
    assert '"show",' in source
    assert '"lsblk",' in source
    assert '"findmnt",' in source
    assert '"blkid",' in source


def test_forensic_classifies_all_relevant_durable_boundaries() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    assert 'state = "DURABLE_U4"' in source
    assert 'state = "DURABLE_U3"' in source
    assert 'state = "DURABLE_U2"' in source
    assert 'state = "POST_CONFIRM_PRE_U2"' in source
    assert '"same_authorization_replay_permitted": False' in source


def test_forensic_reads_execution_one_shot_evidence_without_writing_it() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    assert (
        "/var/lib/n3w-t1-core-updater/"
        "kf147-usb-confirm-u1-u4-20261110-01"
    ) in source
    for name in (
        "preflight.json",
        "authorization_claim.json",
        "postclaim.json",
        "dispatch.json",
        "post.json",
        "failure.json",
        "result.json",
    ):
        assert f'"{name}"' in source
    assert "durable_json" not in source
    assert "os.replace" not in source


def test_forensic_can_verify_target_archive_only_when_already_mounted() -> None:
    module = load_executor()
    source = module.REMOTE_SCRIPT
    assert "filesystem_uuid_not_uniquely_visible" in source
    assert "bound_filesystem_not_uniquely_mounted" in source
    assert "target_archive_not_present" in source
    assert "homeassistant-arm64.tar.gz" in source
    assert "sha_file(target)" in source


def test_manifest_binds_expected_failed_execution_identity() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = doc["expected_live_entry"]
    assert live["transaction_id_sha256"] == (
        "ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738"
    )
    assert live["release_identity"] == "homeassistant-2026.10.4"
    assert live["usb_candidate_public_fingerprint"] == (
        "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
    )
    assert live["target_archive_sha256"] == (
        "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
    )
    assert live["target_archive_size_bytes"] == 835309535
