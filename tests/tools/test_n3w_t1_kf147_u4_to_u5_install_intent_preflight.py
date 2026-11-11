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
    / "kf147_u4_to_u5_install_intent_preflight"
)
EXECUTOR = PACKAGE / "executor.py"
MANIFEST = PACKAGE / "manifest.json"
GATE = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U4_TO_U5_INSTALL_INTENT_R7_PREFLIGHT_20261111_01"
)


def load_executor():
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_u4_u5_install_intent_preflight_test",
        EXECUTOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_is_read_only_ungranted_u5_preflight() -> None:
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
    assert contract["read_only_preflight"] is True
    assert contract["source_deployment"] is False
    assert contract["service_restart"] is False
    assert contract["transaction_mutation"] is False
    assert contract["usb_mutation"] is False
    assert contract["homeassistant_mutation"] is False
    assert contract["u5_transition"] is False
    assert contract["u6_plus"] is False


def test_manifest_binds_exact_u4_live_entry_and_sources() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = document["expected_live_entry"]
    assert live["transaction_sha256"] == (
        "dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259"
    )
    assert "usb_partition" not in live
    assert live["usb_public_fingerprint"] == (
        "e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93"
    )
    assert live["usb_filesystem_type"] == "ext4"
    assert live["usb_filesystem_label"] == "N3W-UPDATE"
    assert live["mount_required_options"] == ["rw", "nodev", "nosuid", "noexec"]
    assert live["mount_forbidden_options"] == ["ro", "noload", "norecovery"]
    assert live["target_size_bytes"] == 835309535
    assert live["target_sha256"] == (
        "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
    )
    assert live["installed_predecessor_sha256"] == {
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare.py": (
            "9139dc652eb992963c21d4fda171eef2bf685e1bbe0cbcea2319244c7e963475"
        ),
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py": (
            "a11089ef57cf68c40a648c85ac7e7569a281f7fad13f75a09c0a3b04bad80ecf"
        ),
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_ipc.py": (
            "3aca46350c2fce9818dbc635f5343f01b06ff80081d93205ce7d28fc4ca2f771"
        ),
    }


def test_executor_and_remote_script_compile() -> None:
    module = load_executor()
    compile(EXECUTOR.read_text(encoding="utf-8"), str(EXECUTOR), "exec")
    compile(module.REMOTE_SCRIPT, "<kf147-u4-u5-preflight>", "exec")
    assert module.GATE_ID == GATE


def test_remote_script_decodes_plan_without_name_error() -> None:
    module = load_executor()
    payload = base64.b64encode(json.dumps({"gate_id": GATE}).encode()).decode()
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


def test_remote_preflight_is_read_only_and_requires_exact_u4() -> None:
    source = load_executor().REMOTE_SCRIPT
    assert 'transaction.get("phase") != "U4_READY_TO_INSTALL"' in source
    assert 'transaction.get("authorization_claimed") is not False' in source
    assert 'transaction.get("authorization_consumed") is not False' in source
    assert 'ipc.get("phase") != "READY_TO_INSTALL"' in source
    assert 'sha_file(target) != plan["target_sha256"]' in source
    forbidden = (
        'run(["systemctl", "restart"',
        'run(["docker", "stop"',
        'run(["docker", "rm"',
        'run(["docker", "load"',
        "scp_to(",
        "request_install(",
        "os.replace(",
    )
    for token in forbidden:
        assert token not in source


def test_product_u5_intent_stops_before_u6_and_u9_claim() -> None:
    prepare = (ROOT / "tools" / "n3w_t1_core_updater_ha_prepare.py").read_text(
        encoding="utf-8"
    )
    ipc = (ROOT / "tools" / "n3w_t1_core_updater_ha_ipc.py").read_text(
        encoding="utf-8"
    )
    assert "def revalidate_and_request_install" in prepare
    assert "self.backend.verify_prepared_target" in prepare
    assert "self.backend.sync_transaction_metadata(u5, media)" in prepare
    assert "u5 = request_install(transaction)" in prepare
    assert 'action not in {"PREPARE", "CONFIRM_USB_ERASE", "INSTALL"}' in ipc
    assert "self.prepare_controller.revalidate_and_request_install()" in ipc
    assert 'transition(transaction, "U6_' not in prepare


def test_target_binding_workflow_covers_u5_preflight() -> None:
    workflow = (
        ROOT
        / ".github"
        / "workflows"
        / "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
    ).read_text(encoding="utf-8")
    package_glob = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u4_to_u5_install_intent_preflight/**"
    )
    executor_path = (
        "tools/execution_packages/n3w/r7a/"
        "kf147_u4_to_u5_install_intent_preflight/executor.py"
    )
    test_path = "tests/tools/test_n3w_t1_kf147_u4_to_u5_install_intent_preflight.py"
    assert workflow.count(package_glob) == 1
    assert workflow.count(executor_path) == 1
    assert workflow.count(test_path) == 2


def load_remote_namespace() -> dict[str, object]:
    source = load_executor().REMOTE_SCRIPT
    trailer = "\n\nraise SystemExit(main())\n"
    assert source.endswith(trailer)
    namespace: dict[str, object] = {}
    exec(source[: -len(trailer)], namespace)
    return namespace


def remote_media_fixture(namespace: dict[str, object]):
    mount_target = "/run/n3w-t1-ota/media/ca89774eb4254d0f"
    partition = "/dev/sda1"
    parent = "/dev/sda"
    disk = {
        "name": "sda",
        "path": parent,
        "type": "disk",
        "rm": 1,
        "ro": 0,
        "size": 32000000000,
        "model": "Extreme",
        "serial": "TEST-SERIAL-001",
        "wwn": None,
        "tran": "usb",
        "mountpoints": [None],
        "maj:min": "8:16",
        "children": [
            {
                "name": "sda1",
                "path": partition,
                "type": "part",
                "rm": 1,
                "ro": 0,
                "size": 31900000000,
                "model": None,
                "serial": None,
                "wwn": None,
                "tran": None,
                "mountpoints": [mount_target],
                "maj:min": "8:17",
            }
        ],
    }
    fingerprint = namespace["_stable_fingerprint"](disk)
    state = {
        "uuid_devices": [partition],
        "source_targets": [mount_target],
        "root_major_minor": "179:2",
        "filesystem_type": "ext4",
        "filesystem_label": "N3W-UPDATE",
        "mount_source": partition,
        "mount_target": mount_target,
        "mount_type": "ext4",
        "mount_options": "rw,nodev,nosuid,noexec,relatime",
        "mount_major_minor": "8:17",
        "partition_major_minor": "8:17",
        "preflight_namespace": "mnt:[4026531840]",
        "service_namespace": "mnt:[4026531840]",
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
        if argv[:2] == ["blkid", "-t"]:
            return completed(0, "\n".join(state["uuid_devices"]) + "\n")
        if argv == [
            "lsblk",
            "--noheadings",
            "--paths",
            "--output",
            "PKNAME",
            partition,
        ]:
            return completed(0, parent + "\n")
        if argv and argv[0] == "lsblk" and "--json" in argv:
            return completed(0, json.dumps({"blockdevices": [disk]}))
        if argv == ["findmnt", "--noheadings", "--output", "MAJ:MIN", "/"]:
            return completed(0, state["root_major_minor"] + "\n")
        if argv == ["blkid", "-s", "TYPE", "-o", "value", partition]:
            return completed(0, state["filesystem_type"] + "\n")
        if argv == ["blkid", "-s", "LABEL", "-o", "value", partition]:
            return completed(0, state["filesystem_label"] + "\n")
        if argv == [
            "findmnt",
            "--noheadings",
            "--output",
            "TARGET",
            "--source",
            partition,
        ]:
            targets = state["source_targets"]
            if targets is None:
                return completed(1, "")
            return completed(0, "\n".join(targets) + "\n")
        mount_fields = {
            "SOURCE": state["mount_source"],
            "TARGET": state["mount_target"],
            "FSTYPE": state["mount_type"],
            "OPTIONS": state["mount_options"],
            "MAJ:MIN": state["mount_major_minor"],
        }
        for field, value in mount_fields.items():
            if argv == [
                "findmnt",
                "--noheadings",
                "--mountpoint",
                mount_target,
                "--output",
                field,
            ]:
                return completed(0, value + "\n")
        if argv == [
            "lsblk",
            "--noheadings",
            "--output",
            "MAJ:MIN",
            partition,
        ]:
            return completed(0, state["partition_major_minor"] + "\n")
        raise AssertionError("unexpected command: " + repr(argv))

    namespace["run"] = fake_run
    namespace["_mount_namespace"] = (
        lambda pid: state["preflight_namespace"]
        if pid is None
        else state["service_namespace"]
    )
    plan = {
        "usb_filesystem_uuid": "967cf065-abe5-49ee-8499-7c3f50d2c48f",
        "usb_public_fingerprint": fingerprint,
        "usb_filesystem_type": "ext4",
        "usb_filesystem_label": "N3W-UPDATE",
        "mount_target": mount_target,
        "mount_required_options": ["rw", "nodev", "nosuid", "noexec"],
        "mount_forbidden_options": ["ro", "noload", "norecovery"],
    }
    transaction = {
        "usb_device_identity_public_fingerprint": fingerprint,
    }
    service = {"MainPID": "123"}
    return plan, transaction, service, disk, state


def assert_remote_stop(namespace, expected_reason, callback) -> None:
    stop_type = namespace["Stop"]
    try:
        callback()
    except stop_type as error:
        assert str(error).startswith(expected_reason)
    else:
        raise AssertionError("expected remote Stop: " + expected_reason)


def test_dynamic_usb_binding_accepts_same_usb_after_sdb_to_sda_renumbering() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, _disk, _state = remote_media_fixture(namespace)
    binding = namespace["verify_bound_media"](plan, transaction, service)
    assert "usb_partition" not in plan
    assert binding["partition"] == "/dev/sda1"
    assert binding["public_fingerprint"] == plan["usb_public_fingerprint"]
    assert binding["mount_target"] == plan["mount_target"]


def test_dynamic_usb_binding_rejects_wrong_usb_fingerprint() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, disk, _state = remote_media_fixture(namespace)
    disk["serial"] = "OTHER-USB"
    assert_remote_stop(
        namespace,
        "usb_public_fingerprint_mismatch",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )


def test_dynamic_usb_binding_rejects_duplicate_filesystem_uuid() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, _disk, state = remote_media_fixture(namespace)
    state["uuid_devices"] = ["/dev/sda1", "/dev/sdb1"]
    assert_remote_stop(
        namespace,
        "usb_filesystem_uuid_cardinality_invalid",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )


def test_dynamic_usb_binding_rejects_invalid_device_properties() -> None:
    for field, value in (("tran", "sata"), ("rm", 0), ("ro", 1)):
        namespace = load_remote_namespace()
        plan, transaction, service, disk, _state = remote_media_fixture(namespace)
        disk[field] = value
        assert_remote_stop(
            namespace,
            "usb_bound_device_properties_invalid",
            lambda: namespace["verify_bound_media"](plan, transaction, service),
        )


def test_dynamic_usb_binding_rejects_root_disk() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, _disk, state = remote_media_fixture(namespace)
    state["root_major_minor"] = "8:17"
    assert_remote_stop(
        namespace,
        "usb_bound_device_is_root",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )


def test_dynamic_usb_binding_rejects_non_ext4_filesystem() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, _disk, state = remote_media_fixture(namespace)
    state["filesystem_type"] = "xfs"
    assert_remote_stop(
        namespace,
        "usb_bound_filesystem_contract_invalid",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )


def test_dynamic_usb_binding_rejects_unmounted_or_mounted_elsewhere() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, _disk, state = remote_media_fixture(namespace)
    state["source_targets"] = None
    assert_remote_stop(
        namespace,
        "usb_mount_missing",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )

    namespace = load_remote_namespace()
    plan, transaction, service, _disk, state = remote_media_fixture(namespace)
    state["source_targets"] = ["/mnt/other"]
    assert_remote_stop(
        namespace,
        "usb_bound_partition_mounted_elsewhere",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )


def test_dynamic_usb_binding_rejects_wrong_mount_source() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, _disk, state = remote_media_fixture(namespace)
    state["mount_major_minor"] = "8:99"
    assert_remote_stop(
        namespace,
        "usb_mount_source_mismatch",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )


def test_dynamic_usb_binding_rejects_mount_namespace_mismatch() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, _disk, state = remote_media_fixture(namespace)
    state["service_namespace"] = "mnt:[4026531999]"
    assert_remote_stop(
        namespace,
        "usb_mount_namespace_mismatch",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )


def test_read_only_no_journal_replay_mount_is_not_u5_writable() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, _disk, state = remote_media_fixture(namespace)
    state["mount_options"] = "ro,noload,nodev,nosuid,noexec"
    assert_remote_stop(
        namespace,
        "usb_mount_not_u5_writable",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )


def test_rw_norecovery_mount_is_not_u5_writable() -> None:
    namespace = load_remote_namespace()
    plan, transaction, service, _disk, state = remote_media_fixture(namespace)
    state["mount_options"] = "rw,norecovery,nodev,nosuid,noexec"
    assert_remote_stop(
        namespace,
        "usb_mount_not_u5_writable",
        lambda: namespace["verify_bound_media"](plan, transaction, service),
    )


def test_executor_has_no_fixed_sdx_partition_authority() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")
    assert 'plan["usb_partition"]' not in source
    assert '"usb_partition": "/dev/' not in MANIFEST.read_text(encoding="utf-8")
