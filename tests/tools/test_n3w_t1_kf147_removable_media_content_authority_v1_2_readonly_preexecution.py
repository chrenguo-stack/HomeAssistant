from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "kf147_removable_media_content_authority_v1_2_readonly_preexecution"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
)
GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_READONLY_PREEXECUTION_20261112_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_v1_2_readonly_preexecution_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_remote_namespace():
    source = load_executor().REMOTE_SCRIPT
    trailer = "\n\nraise SystemExit(main())\n"
    assert source.endswith(trailer)
    namespace = {}
    exec(source[: -len(trailer)], namespace)
    return namespace


def test_manifest_is_read_only_and_has_no_physical_identity_authority() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert document["gate_id"] == GATE
    assert document["live_execution_authorized"] is False
    assert document["authorization_state"] == {
        "granted": False,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    contract = document["execution_contract"]
    assert contract["preflight_read_only"] is True
    assert contract["remote_staging"] is False
    assert contract["source_deployment"] is False
    assert contract["service_restart"] is False
    assert contract["mount"] is False
    assert contract["umount"] is False
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["usb_filesystem_write"] is False
    assert contract["u5_transition"] is False
    assert contract["u6_plus"] is False
    assert contract["physical_usb_identity_continuity_required"] is False
    live = document["expected_live_entry"]
    assert "usb_filesystem_uuid" not in live
    assert "usb_public_fingerprint" not in live


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<v1-2-readonly-preexecution>", "exec")
    assert module.GATE_ID == GATE


def test_remote_probe_is_strictly_nonmutating() -> None:
    source = load_executor().REMOTE_SCRIPT
    forbidden = (
        'run(["mount"',
        'run(["umount"',
        'run(["systemctl", "restart"',
        'run(["docker", "stop"',
        'run(["docker", "rm"',
        'run(["docker", "load"',
        "request_install(",
        "os.replace(",
        "write_text(",
        "write_bytes(",
        "mkdir(",
        "unlink(",
        "rmtree(",
    )
    for token in forbidden:
        assert token not in source
    assert 'transaction.get("usb_filesystem_uuid")' not in source
    assert (
        'transaction.get("usb_device_identity_public_fingerprint")'
        not in source
    )


def test_remote_requires_exact_legacy_u4_and_unextended_identity_state() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert '"U4_READY_TO_INSTALL"' in source
    assert '"authorization_claimed") is not False' in source
    assert '"authorization_consumed") is not False' in source
    assert '"target_artifact_identity"' in source
    assert '"predecessor_recovery_identity"' in source
    assert '"ha_data_backup_identity"' in source
    assert '"recovery_content_manifest_sha256"' in source
    assert '"READY_TO_INSTALL"' in source


def test_anonymous_unmounted_n3w_update_media_is_eligible() -> None:
    namespace = load_remote_namespace()
    transaction_id = "c" * 64
    parent = "/dev/sda"
    partition = "/dev/sda1"
    disk = {
        "path": parent,
        "type": "disk",
        "rm": 1,
        "ro": 0,
        "size": 32000000000,
        "model": "Anonymous USB",
        "serial": None,
        "wwn": None,
        "tran": "usb",
        "mountpoints": [None],
        "maj:min": "8:0",
        "children": [
            {
                "path": partition,
                "type": "part",
                "rm": 1,
                "ro": 0,
                "size": 31900000000,
                "mountpoints": [None],
                "maj:min": "8:1",
            }
        ],
    }

    def completed(returncode: int, stdout: str):
        return types.SimpleNamespace(
            returncode=returncode,
            stdout=stdout,
            stderr="",
        )

    def fake_run(argv, *, timeout=60, check=True):
        del timeout, check
        argv = list(argv)
        if argv == [
            "findmnt",
            "--noheadings",
            "--output",
            "MAJ:MIN",
            "/",
        ]:
            return completed(0, "179:2\n")
        if argv and argv[0] == "lsblk":
            return completed(
                0,
                json.dumps({"blockdevices": [disk]}),
            )
        if argv == [
            "blkid",
            "-s",
            "TYPE",
            "-o",
            "value",
            partition,
        ]:
            return completed(0, "ext4\n")
        if argv == [
            "blkid",
            "-s",
            "LABEL",
            "-o",
            "value",
            partition,
        ]:
            return completed(0, "N3W-UPDATE\n")
        raise AssertionError(argv)

    namespace["run"] = fake_run
    media = namespace["safe_compatible_media"](
        {"transaction_id_sha256": transaction_id}
    )
    assert media["parent"] == "/dev/sda"
    assert media["partition"] == "/dev/sda1"
    assert media["mount_state"] == "UNMOUNTED"
    assert media["serial_present"] is False
    assert media["wwn_present"] is False


def test_multiple_compatible_media_fail_closed() -> None:
    namespace = load_remote_namespace()
    transaction_id = "d" * 64
    disks = []
    for index in (0, 16):
        parent = "/dev/sd" + ("a" if index == 0 else "b")
        partition = parent + "1"
        disks.append(
            {
                "path": parent,
                "type": "disk",
                "rm": 1,
                "ro": 0,
                "size": 32000000000,
                "model": "USB",
                "serial": None,
                "wwn": None,
                "tran": "usb",
                "mountpoints": [None],
                "maj:min": f"8:{index}",
                "children": [
                    {
                        "path": partition,
                        "type": "part",
                        "rm": 1,
                        "ro": 0,
                        "size": 31900000000,
                        "mountpoints": [None],
                        "maj:min": f"8:{index + 1}",
                    }
                ],
            }
        )

    def completed(returncode: int, stdout: str):
        return types.SimpleNamespace(
            returncode=returncode,
            stdout=stdout,
            stderr="",
        )

    def fake_run(argv, *, timeout=60, check=True):
        del timeout, check
        argv = list(argv)
        if argv == [
            "findmnt",
            "--noheadings",
            "--output",
            "MAJ:MIN",
            "/",
        ]:
            return completed(0, "179:2\n")
        if argv and argv[0] == "lsblk":
            return completed(
                0,
                json.dumps({"blockdevices": disks}),
            )
        if argv[:5] == ["blkid", "-s", "TYPE", "-o", "value"]:
            return completed(0, "ext4\n")
        if argv[:5] == ["blkid", "-s", "LABEL", "-o", "value"]:
            return completed(0, "N3W-UPDATE\n")
        raise AssertionError(argv)

    namespace["run"] = fake_run
    stop_type = namespace["Stop"]
    try:
        namespace["safe_compatible_media"](
            {"transaction_id_sha256": transaction_id}
        )
    except stop_type as error:
        assert str(error) == "usb_multiple_eligible_devices"
    else:
        raise AssertionError("multiple compatible USB devices must fail closed")


def test_remote_script_decodes_plan_without_name_error() -> None:
    module = load_executor()
    payload = base64.b64encode(
        json.dumps({"gate_id": GATE}).encode()
    ).decode()
    completed = subprocess.run(
        [sys.executable, "-c", module.REMOTE_SCRIPT, payload],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert result["status"] == "STOP"
    assert not result["reason"].startswith("NameError:")


def test_target_binding_workflow_covers_v1_2_readonly_package() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_removable_media_content_authority_v1_2_readonly_preexecution/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_removable_media_content_authority_v1_2_"
        "readonly_preexecution/executor.py"
    )
    test_path = (
        "tests/tools/"
        "test_n3w_t1_kf147_removable_media_content_authority_v1_2_"
        "readonly_preexecution.py"
    )
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2
