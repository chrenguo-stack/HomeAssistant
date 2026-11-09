from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "tools/execution_packages/n3w/r7a/kf147_manager_v3_live_apply"
MANIFEST = PACKAGE / "manifest.json"
LOCAL = PACKAGE / "executor.py"
REMOTE = PACKAGE / "remote_apply.py"
WORKFLOW = ROOT / ".github/workflows/n3w-kf147-manager-v3-live-package-ci.yml"

GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_20261109_01"
)


def test_manifest_is_fail_closed_until_exact_package_binding() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["schema"] == "gh.n3w-t1-kf147-manager-v3-live-executor/1"
    assert doc["gate_id"] == GATE
    assert doc["authorization_id"] == GATE
    assert doc["live_execution_authorized"] is False
    assert doc["package_authority"] == {
        "workflow_run_id": None,
        "artifact_id": None,
        "artifact_name": None,
        "artifact_digest": None,
    }


def test_execution_contract_preserves_u1_and_forbids_usb_mutation() -> None:
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = doc["execution_contract"]
    assert contract["manager_image_mutation"] is True
    assert contract["application_owner_restart_required"] is True
    assert contract["homeassistant_image_mutation"] is False
    assert contract["homeassistant_container_recreate"] is False
    assert contract["broker_mutation"] is False
    assert contract["host_policy_mutation"] is False
    assert contract["host_source_mutation"] is False
    assert contract["u1_transaction_reset"] is False
    assert contract["prepare_replay"] is False
    assert contract["confirm_usb_erase"] is False
    assert contract["usb_mutation"] is False
    assert contract["u2_plus"] is False
    assert contract["automatic_retry"] is False
    assert contract["remote_local_rollback"] is True
    assert contract["merge"] is False


def test_remote_executor_has_no_destructive_usb_commands_or_prepare_submission() -> None:
    source = REMOTE.read_text(encoding="utf-8")
    for forbidden in (
        '"wipefs"',
        '"mkfs',
        '"fdisk"',
        '"sfdisk"',
        '"parted"',
        "CONFIRM_USB_ERASE",
        'action="PREPARE"',
        '"PREPARE"',
    ):
        assert forbidden not in source
    assert '"lsblk"' in source
    assert "U1_PREPARE_REQUESTED" in source
    assert "confirmation_consumed" in source
    assert "capacity_snapshot_present" in source


def test_remote_executor_rolls_back_from_owner_quiesce_boundary() -> None:
    source = REMOTE.read_text(encoding="utf-8")
    assert "rollback_needed = True" in source
    assert 'run(["systemctl", "stop", SERVICES_UNIT]' in source
    assert "if rollback_needed:" in source
    assert "rollback(pre, snapshot_env)" in source
    assert 'run(["systemctl", "start", SERVICES_UNIT]' in source


def test_remote_executor_binds_exact_predecessor_and_target() -> None:
    source = REMOTE.read_text(encoding="utf-8")
    assert "local/greenhouse-manager:fresh-7807271e4c48" in source
    assert "local/greenhouse-manager:fresh-44e7d7472714" in source
    assert "sha256:fd5104d610645347fe47137dbb24121851fa8a48530df3e3c905704607c5e3d4" in source
    assert "9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5" in source
    assert "32017047552" in source
    assert "835309535" in source
    assert "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973" in source


def test_local_launcher_uses_single_password_controlmaster_transport() -> None:
    source = LOCAL.read_text(encoding="utf-8")
    assert "n3w_t1_ssh_transport.py" in source
    assert "transport.start_epoch()" in source
    assert "transport.scp_to(" in source
    assert "transport.close_epoch()" in source
    assert "5bc28b30e696bd3d0f5ae4c98fd81b8f8679aaa7" in source


def test_workflow_builds_manager_only_slice_from_frozen_exact_artifact() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "UPSTREAM_ARTIFACT_ID: \"13673322402\"" in source
    assert "SOURCE_HEAD: 44e7d74727147975de88e85c4b18ba3f7493fd76" in source
    assert "MANAGER_TAR_SHA256: 9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5" in source
    assert "greenhouse-manager-arm64.tar" in source
    assert "homeassistant-arm64.tar" not in "\n".join(
        line for line in source.splitlines()
        if "cp " in line and "$RUNNER_TEMP/package" in line
    )
