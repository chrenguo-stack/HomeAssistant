#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
BASE_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u6_source_activation_r25"
    / "executor.py"
)

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U7_HA_QUIESCE_DATA_BACKUP_R30_20261115_01"
)
CONFIRMATION = "EXECUTE U7 R30 HA QUIESCE DATA BACKUP: YES"


class Stop(RuntimeError):
    pass


def load_base():
    spec = importlib.util.spec_from_file_location("n3w_r30_base", BASE_EXECUTOR)
    if spec is None or spec.loader is None:
        raise Stop("base_executor_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REMOTE_SCRIPT = r'''
import base64
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TX = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
R26 = Path(
    "/var/lib/n3w-t1-core-updater/u6-r26-predecessor-recovery-20261114-01"
)
R29 = Path(
    "/var/lib/n3w-t1-core-updater/u7-r29-source-activation-20261114-01"
)
R30S = Path(
    "/var/lib/n3w-t1-core-updater/u7-r30s-prepare-host-source-activation-20261115-01"
)
HOST_UNIT = "n3w-t1-ha-ota.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
TOOLS_ROOT = Path("/opt/HomeAssistant/tools")


class Stop(RuntimeError):
    pass


def run(argv, *, timeout=60, check=True):
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        raise Stop(
            "command_failed:"
            + Path(argv[0]).name
            + ":"
            + str(completed.returncode)
        )
    return completed


def sha_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + path.name)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + path.name)
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise Stop("required_file_metadata_invalid:" + path.name)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("required_json_invalid:" + path.name) from error
    if not isinstance(value, dict):
        raise Stop("required_object_invalid:" + path.name)
    return value


def fsync_dir(path):
    descriptor = os.open(
        str(path),
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_json_once(path, value):
    path = Path(path)
    payload = (
        json.dumps(value, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    fsync_dir(path.parent)


def durable_json_replace(path, value):
    path = Path(path)
    payload = (
        json.dumps(value, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    descriptor, raw = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def service_state(unit):
    completed = run(
        [
            "systemctl",
            "show",
            unit,
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "MainPID",
            "-p",
            "NRestarts",
            "-p",
            "Result",
        ],
        timeout=30,
        check=False,
    )
    result = {"returncode": completed.returncode}
    if completed.returncode == 0:
        for line in completed.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key] = value
    return result


def require_unit(unit, *, active):
    value = service_state(unit)
    if value.get("returncode") != 0:
        raise Stop("unit_probe_failed:" + unit)
    if active:
        if (
            value.get("ActiveState") != "active"
            or value.get("SubState") != "running"
            or value.get("Result") != "success"
            or value.get("NRestarts") != "0"
        ):
            raise Stop("unit_not_healthy:" + unit)
    else:
        if value.get("ActiveState") not in {"inactive", "failed"}:
            raise Stop("unit_not_quiesced:" + unit)
    return value


def docker_snapshot(expected):
    ids = [
        value.strip()
        for value in run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "ancestor=" + expected["image"],
                "--format",
                "{{.ID}}",
            ],
            timeout=45,
        ).stdout.splitlines()
        if value.strip()
    ]
    if len(ids) != 1:
        raise Stop("container_cardinality_invalid:" + expected["image"])
    documents = json.loads(
        run(["docker", "inspect", ids[0]], timeout=45).stdout
    )
    if not isinstance(documents, list) or len(documents) != 1:
        raise Stop("container_inspect_invalid:" + expected["image"])
    item = documents[0]
    state = item.get("State") if isinstance(item.get("State"), dict) else {}
    config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
    result = {
        "container_id": item.get("Id"),
        "runtime_image_id": item.get("Image"),
        "configured_image_ref": config.get("Image"),
        "status": state.get("Status"),
        "restart_count": item.get("RestartCount"),
    }
    if (
        result["runtime_image_id"] != expected["runtime_image_id"]
        or result["configured_image_ref"] != expected["image"]
        or result["restart_count"] != 0
    ):
        raise Stop("container_identity_drift:" + expected["image"])
    return result


def verify_running_runtime(plan):
    units = {
        "host": require_unit(HOST_UNIT, active=True),
        "services_owner": require_unit(SERVICES_UNIT, active=True),
        "broker_owner": require_unit(BROKER_UNIT, active=True),
    }
    containers = {
        name: docker_snapshot(expected)
        for name, expected in plan["containers"].items()
    }
    for name, value in containers.items():
        if value.get("status") != "running":
            raise Stop("container_not_running:" + name)
    return {"units": units, "containers": containers}


def verify_quiesced_runtime(plan, baseline):
    units = {
        "host": require_unit(HOST_UNIT, active=True),
        "services_owner": require_unit(SERVICES_UNIT, active=False),
        "broker_owner": require_unit(BROKER_UNIT, active=True),
    }
    if units["services_owner"].get("ActiveState") != "inactive":
        raise Stop("services_owner_not_inactive_post_u7")
    containers = {
        name: docker_snapshot(expected)
        for name, expected in plan["containers"].items()
    }
    if containers["broker"].get("status") != "running":
        raise Stop("broker_not_running_post_u7")
    if containers["manager"].get("status") == "running":
        raise Stop("manager_not_quiesced_post_u7")
    if containers["homeassistant"].get("status") == "running":
        raise Stop("homeassistant_not_quiesced_post_u7")
    for name in ("broker", "manager", "homeassistant"):
        if (
            containers[name]["container_id"]
            != baseline["containers"][name]["container_id"]
        ):
            raise Stop("container_id_drift_post_u7:" + name)
    return {"units": units, "containers": containers}


def verify_source_hashes(plan):
    observed = {}
    for raw_path, expected in plan["installed_source_sha256"].items():
        path = Path(raw_path)
        digest = sha_file(path)
        if digest != expected:
            raise Stop("installed_source_drift:" + path.name)
        observed[path.name] = digest
    return observed


def verify_transaction(plan):
    transaction = read_object(TX)
    if (
        transaction.get("phase") != "U6_PREDECESSOR_RECOVERY_PREPARING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or sha_file(TX) != plan["transaction_sha256"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not False
        or transaction.get("predecessor_recovery_identity") is not None
        or transaction.get("ha_data_backup_verified") is not False
        or transaction.get("ha_data_backup_identity") is not None
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
    ):
        raise Stop("u7_r30_u6_transaction_invalid")
    return transaction


def verify_r26(plan):
    claim = read_object(R26 / "authorization_claim.json")
    success = read_object(R26 / "success.json")
    post = success.get("post")
    if (
        claim.get("authorization_id") != plan["r26_gate_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or success.get("status") != "U6_R26_PREDECESSOR_RECOVERY_PASS"
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or not isinstance(post, dict)
        or post.get("transaction_sha256") != plan["transaction_sha256"]
        or post.get("predecessor") != plan["predecessor_identity"]
    ):
        raise Stop("r26_authority_invalid")
    return True


def verify_r29(plan):
    claim = read_object(R29 / "authorization_claim.json")
    success = read_object(R29 / "success.json")
    post = success.get("post")
    if (
        claim.get("authorization_id") != plan["r29_gate_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or success.get("status") != "U7_R29_SOURCE_ACTIVATION_PASS"
        or success.get("authorization_claimed") is not True
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or success.get("source_activated") is not True
        or success.get("activated_source_file_count") != 7
        or not isinstance(post, dict)
        or post.get("transaction_sha256") != plan["transaction_sha256"]
    ):
        raise Stop("r29_authority_invalid")
    return True


def verify_r30s(plan):
    claim = read_object(R30S / "authorization_claim.json")
    success = read_object(R30S / "success.json")
    if (
        claim.get("authorization_id") != plan["r30s_gate_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or success.get("status")
        != "U7_R30S_PREPARE_HOST_SOURCE_ACTIVATION_PASS"
        or success.get("authorization_claimed") is not True
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or success.get("source_activated") is not True
        or success.get("activated_source_file_count") != 1
        or success.get("transaction_sha256")
        != plan["transaction_sha256"]
    ):
        raise Stop("r30s_authority_invalid")
    stage = Path(
        "/var/lib/n3w-t1-core-updater/staging/"
        "u7-r30s-prepare-host-source-activation-20261115-01"
    )
    if stage.exists() or stage.is_symlink():
        raise Stop("r30s_staging_residue")
    return True


def import_product():
    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_backup import ProtectedHaDataBackupProvider
    from n3w_t1_core_updater_ha_capacity import validate_backup_revalidation
    from n3w_t1_core_updater_ha_install import HaUsbU7BackupController
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_recovery import validate_image_recovery_record
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
    from n3w_t1_core_updater_host import LocalHost

    return {
        "ProtectedHaDataBackupProvider": ProtectedHaDataBackupProvider,
        "validate_backup_revalidation": validate_backup_revalidation,
        "HaUsbU7BackupController": HaUsbU7BackupController,
        "SubprocessPrepareBackend": SubprocessPrepareBackend,
        "validate_image_recovery_record": validate_image_recovery_record,
        "HaUsbStateStore": HaUsbStateStore,
        "LocalHost": LocalHost,
    }


def require_existing_rw_mount(plan):
    mount_path = plan["mount_target"]
    completed = run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE,TARGET,FSTYPE,OPTIONS",
            "--target",
            mount_path,
        ],
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("u7_media_not_already_mounted")
    fields = completed.stdout.strip().split(None, 3)
    if len(fields) != 4:
        raise Stop("u7_media_mount_probe_invalid")
    source, target, fstype, options = fields
    if (
        not source.startswith("/dev/")
        or target != mount_path
        or fstype != "ext4"
        or "rw" not in set(options.split(","))
    ):
        raise Stop("u7_media_mount_not_live_eligible")
    return {
        "source_kind": "block_device",
        "target": mount_path,
        "fstype": fstype,
        "rw": True,
    }


def verify_media_and_backup_inputs(plan, transaction):
    require_existing_rw_mount(plan)
    product = import_product()
    backend = product["SubprocessPrepareBackend"]()
    media = backend.resolve_transaction_media(
        transaction,
        write_required=False,
    )
    if media is None or media.mount_path != plan["mount_target"]:
        raise Stop("u7_media_resolution_invalid")

    target = product["validate_image_recovery_record"](
        backend.verify_prepared_target(
            transaction=transaction,
            media=media,
        ),
        expected_kind="target",
        expected_image_ref=transaction["target_image_ref"],
        expected_archive_sha256=transaction["target_archive_sha256"],
    )
    if target.public() != transaction.get("target_artifact_identity"):
        raise Stop("u7_target_identity_drift")

    predecessor = product["validate_image_recovery_record"](
        backend.verify_prepared_predecessor(
            transaction=transaction,
            media=media,
        ),
        expected_kind="predecessor",
        expected_image_ref=transaction["current_image_ref"],
    )
    if predecessor.public() != plan["predecessor_identity"]:
        raise Stop("u7_predecessor_identity_drift")

    capacity = backend.backup_capacity_revalidation(
        transaction,
        media,
        predecessor=predecessor,
    )
    product["validate_backup_revalidation"](
        capacity,
        expected_target_artifact_bytes=transaction["target_archive_size"],
        expected_predecessor_archive_bytes=predecessor.archive_size_bytes,
    )

    provider = product["ProtectedHaDataBackupProvider"]()
    provider._validate_source_tree()
    provider._verify_sqlite()
    root_key = provider._root_key()
    if len(root_key) != 32:
        raise Stop("u7_backup_root_key_invalid")
    del root_key
    if shutil.which("openssl") is None or shutil.which("tar") is None:
        raise Stop("u7_backup_host_tool_unavailable")

    return {
        "media_mounted": True,
        "target_exact": True,
        "predecessor_exact": True,
        "backup_capacity_verified": True,
        "ha_source_supported": True,
        "sqlite_quick_check": True,
        "root_key_available": True,
        "crypto_tools_available": True,
    }


def verify_prestate(plan):
    source_hashes = verify_source_hashes(plan)
    transaction = verify_transaction(plan)
    verify_r26(plan)
    verify_r29(plan)
    verify_r30s(plan)
    runtime = verify_running_runtime(plan)
    media = verify_media_and_backup_inputs(plan, transaction)
    return {
        "transaction_sha256": sha_file(TX),
        "source_hash_count": len(source_hashes),
        "r26_consumed_no_replay": True,
        "r29_consumed_no_replay": True,
        "r30s_consumed_no_replay": True,
        "runtime": runtime,
        "media": media,
    }


def verify_terminal_u7_state(plan, success):
    transaction = read_object(TX)
    if (
        success.get("status") != "U7_R30_HA_QUIESCE_DATA_BACKUP_PASS"
        or transaction.get("phase")
        != "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
        or transaction.get("ha_data_backup_verified") is not True
        or not isinstance(transaction.get("ha_data_backup_identity"), dict)
        or success.get("backup") != transaction.get("ha_data_backup_identity")
        or sha_file(TX) != success.get("transaction_sha256")
    ):
        raise Stop("r30_terminal_transaction_mismatch")

    require_existing_rw_mount(plan)
    mirror = Path(plan["mount_target"]) / "n3w-update" / "transaction"
    manifest = read_object(mirror / "manifest.json")
    phase = read_object(mirror / "phase.json")
    authority = read_object(mirror / "content-authority.json")
    if (
        manifest.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or manifest.get("usb_filesystem_uuid")
        != transaction.get("usb_filesystem_uuid")
        or manifest.get("usb_device_identity_public_fingerprint")
        != transaction.get("usb_device_identity_public_fingerprint")
        or manifest.get("target_archive_sha256")
        != transaction.get("target_archive_sha256")
        or manifest.get("target_archive_size_bytes")
        != transaction.get("target_archive_size")
        or phase.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or phase.get("phase")
        != "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
        or authority.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or authority.get("ha_data_backup_identity")
        != transaction.get("ha_data_backup_identity")
    ):
        raise Stop("r30_terminal_usb_mirror_mismatch")

    pre = success.get("pre")
    if not isinstance(pre, dict) or not isinstance(pre.get("runtime"), dict):
        raise Stop("r30_terminal_runtime_baseline_missing")
    verify_quiesced_runtime(plan, pre["runtime"])
    return {
        "transaction_exact": True,
        "usb_mount_present": True,
        "usb_mirror_exact": True,
        "backup_identity_exact": True,
        "runtime_quiesced": True,
        "broker_continuity": True,
    }


def read_terminal_status(plan):
    state_root = Path(plan["state_root"])
    if not state_root.exists():
        return {
            "schema": "gh.n3w-t1-u7-r30-status/1",
            "status": "NOT_STARTED",
            "terminal": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
        }
    if state_root.is_symlink() or not state_root.is_dir():
        raise Stop("r30_state_root_invalid")
    success_path = state_root / "success.json"
    failure_path = state_root / "failure.json"
    claim_path = state_root / "authorization_claim.json"
    progress_path = state_root / "progress.json"
    claim = read_object(claim_path) if claim_path.exists() else None
    if success_path.exists():
        value = read_object(success_path)
        value["terminal_reconciliation"] = verify_terminal_u7_state(
            plan,
            value,
        )
        value["terminal"] = True
        value["reconciled_from_ledger"] = True
        return value
    if failure_path.exists():
        value = read_object(failure_path)
        value["terminal"] = True
        value["reconciled_from_ledger"] = True
        return value
    progress = read_object(progress_path) if progress_path.exists() else None
    transaction = read_object(TX)
    return {
        "schema": "gh.n3w-t1-u7-r30-status/1",
        "status": "RUNNING_OR_INTERRUPTED",
        "terminal": False,
        "authorization_claimed": bool(claim and claim.get("claimed") is True),
        "authorization_consumed": bool(claim and claim.get("consumed") is True),
        "replay_permitted": False,
        "progress": progress,
        "transaction_phase": transaction.get("phase"),
        "ha_data_backup_verified": transaction.get("ha_data_backup_verified"),
    }


def execute(plan, authorization_id, confirmation):
    result = {
        "schema": "gh.n3w-t1-u7-r30-ha-quiesce-backup/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "service_stop": False,
        "service_restart": False,
        "ha_quiesced": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u7_transition": False,
        "u8_plus": False,
        "backup_verified": False,
        "recovery_attempted": False,
        "recovery_pass": None,
        "rollback_required": False,
    }
    if (
        authorization_id != plan["authorization_id"]
        or confirmation != plan["confirmation"]
        or plan.get("live_execution_authorized") is not True
        or plan.get("authorization_state") != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("r30_state_root_residue")

    pre = verify_prestate(plan)
    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    claim = {
        "schema": "gh.n3w-t1-u7-r30-authorization-claim/1",
        "gate_id": plan["gate_id"],
        "authorization_id": authorization_id,
        "execution_id": plan["execution_id"],
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
    }
    durable_json_once(state_root / "authorization_claim.json", claim)
    result.update(
        authorization_claimed=True,
        authorization_consumed=True,
        replay_permitted=False,
    )

    allowed_progress = re.compile(r"^[a-z0-9_]{1,64}$")

    def progress(phase, value=0):
        if (
            not isinstance(phase, str)
            or allowed_progress.fullmatch(phase) is None
            or type(value) is not int
            or value < 0
        ):
            raise Stop("u7_progress_invalid")
        durable_json_replace(
            state_root / "progress.json",
            {
                "schema": "gh.n3w-t1-u7-r30-progress/1",
                "phase": phase,
                "value": value,
                "updated_at_unix": int(time.time()),
            },
        )

    product = import_product()

    class RuntimeTracker:
        def __init__(self):
            self.inner = product["LocalHost"]()
            self.quiesce_invoked = False
            self.resume_invoked = False
            self.resume_succeeded = None

        def quiesce_homeassistant_for_backup(self):
            self.quiesce_invoked = True
            return self.inner.quiesce_homeassistant_for_backup()

        def resume_homeassistant_after_backup_failure(self):
            self.resume_invoked = True
            try:
                value = self.inner.resume_homeassistant_after_backup_failure()
            except Exception:
                self.resume_succeeded = False
                raise
            self.resume_succeeded = True
            return value

    runtime = RuntimeTracker()
    try:
        progress("executor_claimed")
        store = product["HaUsbStateStore"]()
        backend = product["SubprocessPrepareBackend"]()
        provider = product["ProtectedHaDataBackupProvider"](progress=progress)
        controller = product["HaUsbU7BackupController"](
            transaction_store=store,
            backend=backend,
            runtime_owner=runtime,
            backup_provider=provider,
            progress=progress,
        )
        with store.lock():
            prepared = controller.prepare_or_resume()

        post = read_object(TX)
        if (
            prepared.transaction.get("phase")
            != "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
            or post.get("phase")
            != "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
            or post.get("ha_data_backup_verified") is not True
            or not isinstance(post.get("ha_data_backup_identity"), dict)
            or post.get("authorization_claimed") is not False
            or post.get("authorization_consumed") is not False
            or post.get("authorization_id_sha256") is not None
            or prepared.services_left_quiesced is not True
        ):
            raise Stop("u7_r30_post_transaction_invalid")
        if prepared.backup.public() != post["ha_data_backup_identity"]:
            raise Stop("u7_r30_backup_identity_drift")

        post_runtime = verify_quiesced_runtime(plan, pre["runtime"])
        result.update(
            status="U7_R30_HA_QUIESCE_DATA_BACKUP_PASS",
            service_stop=True,
            service_restart=False,
            ha_quiesced=True,
            transaction_mutation=True,
            usb_mutation=True,
            u7_transition=True,
            u8_plus=False,
            backup_verified=True,
            transaction_sha256=sha_file(TX),
            transaction_phase=post["phase"],
            backup=prepared.backup.public(),
            pre=pre,
            post_runtime=post_runtime,
        )
        progress("executor_success", prepared.backup.archive_size_bytes)
        durable_json_once(state_root / "success.json", result)
        return result
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        result["transaction_mutation"] = sha_file(TX) != plan["transaction_sha256"]
        try:
            current = read_object(TX)
            result["transaction_phase"] = current.get("phase")
            result["ha_quiesced"] = (
                current.get("phase")
                == "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
            )
            result["u7_transition"] = result["ha_quiesced"]
            result["backup_verified"] = (
                current.get("ha_data_backup_verified") is True
            )
        except Exception:
            pass
        result["service_stop"] = runtime.quiesce_invoked
        result["usb_mutation"] = bool(result["transaction_mutation"])
        if runtime.resume_invoked:
            result["recovery_attempted"] = True
            result["service_restart"] = True
            try:
                verify_running_runtime(plan)
                result["recovery_pass"] = True
                result["status"] = "STOP_RECOVERED"
            except Exception as recovery_error:
                result["recovery_pass"] = False
                result["status"] = "STOP_RECOVERY_FAILED"
                result["recovery_error"] = (
                    type(recovery_error).__name__
                    + ":"
                    + str(recovery_error)[:180]
                )
        elif runtime.quiesce_invoked:
            result["recovery_attempted"] = True
            try:
                runtime.resume_homeassistant_after_backup_failure()
                verify_running_runtime(plan)
                result["recovery_pass"] = True
                result["service_restart"] = True
                result["status"] = "STOP_RECOVERED"
            except Exception as recovery_error:
                result["recovery_pass"] = False
                result["service_restart"] = runtime.resume_invoked
                result["status"] = "STOP_RECOVERY_FAILED"
                result["recovery_error"] = (
                    type(recovery_error).__name__
                    + ":"
                    + str(recovery_error)[:180]
                )
        else:
            result["recovery_attempted"] = False
            result["recovery_pass"] = None
            result["service_restart"] = False
            result["status"] = "STOP_PREQUIESCE"
        try:
            progress("executor_failure")
        except Exception:
            pass
        try:
            durable_json_once(state_root / "failure.json", result)
        except Exception:
            pass
        return result


def main():
    try:
        mode = sys.argv[1]
        plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U7_HA_QUIESCE_DATA_BACKUP_R30_20261115_01"
        ):
            raise Stop("gate_id_invalid")

        if mode == "preflight":
            if (
                Path(plan["state_root"]).exists()
                or Path(plan["state_root"]).is_symlink()
            ):
                raise Stop("r30_state_root_residue")
            result = {
                "schema": "gh.n3w-t1-u7-r30-preflight/1",
                "status": "PASS",
                "read_only": True,
                "u7_live_eligible": True,
                "live_execution_authorized": (
                    plan.get("live_execution_authorized") is True
                ),
                "preflight": verify_prestate(plan),
                "authorization_claimed": False,
                "authorization_consumed": False,
                "replay_permitted": False,
                "service_stop": False,
                "service_restart": False,
                "ha_quiesced": False,
                "transaction_mutation": False,
                "usb_mutation": False,
                "u7_transition": False,
                "u8_plus": False,
            }
        elif mode == "execute":
            result = execute(plan, sys.argv[3], sys.argv[4])
        elif mode == "status":
            result = read_terminal_status(plan)
        else:
            raise Stop("mode_invalid")
    except Exception as error:
        result = {
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
        }

    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status")
        in {"PASS", "U7_R30_HA_QUIESCE_DATA_BACKUP_PASS"}
        else 2
    )


raise SystemExit(main())
'''


def git_text(*args: str) -> str:
    return load_base().git_text(*args)


def read_manifest(expected_commit: str, *, execute: bool) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")

    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        document.get("gate_id") != GATE_ID
        or document.get("authorization_id") != GATE_ID
        or document.get("confirmation") != CONFIRMATION
    ):
        raise Stop("manifest_gate_invalid")

    expected_state = {
        "granted": bool(execute),
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    if (
        document.get("authorization_state") != expected_state
        or document.get("live_execution_authorized") is not execute
    ):
        raise Stop("manifest_authorization_state_invalid")

    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


def remote_mode(transport, mode, plan, *extra, timeout=300):
    payload = base64.b64encode(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    completed = transport.run_remote(
        ["python3", "-B", "-c", REMOTE_SCRIPT, mode, payload, *extra],
        timeout=timeout,
        check=False,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    try:
        result = json.loads(lines[-1]) if lines else {}
    except Exception:
        result = {}
    if not isinstance(result, dict) or not result:
        result = {"status": "STOP", "reason": "remote_result_invalid"}
    return completed, result


def reconcile_after_invoke(transport, plan, evidence, base):
    try:
        status_transport, status = remote_mode(
            transport,
            "status",
            plan,
            timeout=120,
        )
        base.write_remote_evidence(
            evidence,
            "status_reconcile_remote",
            status_transport,
        )
        base.write_private_json(evidence / "status_reconcile.json", status)
        return status_transport, status
    except Exception as error:
        return None, {
            "status": "STOP_UNKNOWN",
            "reason": "status_reconciliation_failed:"
            + type(error).__name__
            + ":"
            + str(error)[:180],
            "terminal": False,
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_permitted": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight-only", action="store_true")
    group.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-id", default="")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema": "gh.n3w-t1-u7-r30-local-result/1",
        "status": "STOP",
        "read_only_preflight": bool(args.preflight_only),
        "t1_access": False,
        "remote_execute_invoked": False,
        "remote_execute_result_observed": False,
        "status_reconciliation_attempted": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "service_stop": False,
        "service_restart": False,
        "ha_quiesced": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u7_transition": False,
        "u8_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    base = load_base()

    try:
        manifest = read_manifest(
            args.expected_package_commit,
            execute=bool(args.execute),
        )
        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_live_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "authorization_id": manifest["authorization_id"],
                "confirmation": manifest["confirmation"],
                "live_execution_authorized": (
                    manifest["live_execution_authorized"]
                ),
                "authorization_state": manifest["authorization_state"],
                "state_root": manifest["state_root"],
                "mount_target": manifest["mount_target"],
                "installed_source_sha256": (
                    manifest["installed_source_sha256"]
                ),
                "execution_id": args.execution_id,
            }
        )

        transport_type = base.load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        pre_transport, preflight = remote_mode(
            transport,
            "preflight",
            plan,
            timeout=420,
        )
        base.write_remote_evidence(
            evidence,
            "preflight_remote",
            pre_transport,
        )
        base.write_private_json(evidence / "preflight.json", preflight)
        if (
            pre_transport.returncode != 0
            or preflight.get("status") != "PASS"
        ):
            raise Stop(
                "r30_preflight_failed:"
                + str(preflight.get("reason"))
            )

        if args.preflight_only:
            result.update(preflight)
            result["t1_access"] = True
            return_code = 0
        else:
            if (
                args.authorization_id != GATE_ID
                or args.confirm != CONFIRMATION
            ):
                raise Stop("authorization_invalid")
            result["remote_execute_invoked"] = True
            try:
                execute_transport, remote = remote_mode(
                    transport,
                    "execute",
                    plan,
                    args.authorization_id,
                    args.confirm,
                    timeout=2400,
                )
                result["remote_returncode"] = execute_transport.returncode
                if remote.get("reason") == "remote_result_invalid":
                    raise Stop("remote_execute_result_invalid")
                result.update(remote)
                result["remote_execute_result_observed"] = True
                base.write_remote_evidence(
                    evidence,
                    "execute_remote",
                    execute_transport,
                )
            except Exception as invoke_error:
                result["status_reconciliation_attempted"] = True
                status_transport, status = reconcile_after_invoke(
                    transport,
                    plan,
                    evidence,
                    base,
                )
                if status.get("terminal") is True:
                    result.update(status)
                    result["remote_execute_result_observed"] = True
                    if status_transport is not None:
                        result["remote_returncode"] = (
                            status_transport.returncode
                        )
                else:
                    result.update(
                        status="STOP_UNKNOWN",
                        reason=(
                            "postinvoke_unknown:"
                            + type(invoke_error).__name__
                            + ":"
                            + str(invoke_error)[:180]
                        ),
                        authorization_claimed=True,
                        authorization_consumed=True,
                        replay_permitted=False,
                        remote_execute_result_observed=False,
                    )

            result["t1_access"] = True
            return_code = (
                0
                if result.get("status")
                == "U7_R30_HA_QUIESCE_DATA_BACKUP_PASS"
                else 2
            )
    except Exception as error:
        if result.get("remote_execute_invoked"):
            result.update(
                status="STOP_UNKNOWN",
                authorization_claimed=True,
                authorization_consumed=True,
                replay_permitted=False,
            )
        result["reason"] = type(error).__name__ + ":" + str(error)[:300]
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception as cleanup_error:
                result["ssh_master_cleanup"] = False
                result["ssh_master_cleanup_error"] = (
                    type(cleanup_error).__name__
                    + ":"
                    + str(cleanup_error)[:240]
                )
                return_code = 2

        try:
            if "evidence" in locals():
                base.write_private_json(evidence / "result.json", result)
        except Exception as evidence_error:
            if result.get("status") in {
                "PASS",
                "U7_R30_HA_QUIESCE_DATA_BACKUP_PASS",
            }:
                result["completed_remote_status"] = result["status"]
                result["status"] = "STOP_POSTSUCCESS_LOCAL"
            if result.get("remote_execute_invoked"):
                result["authorization_claimed"] = True
                result["authorization_consumed"] = True
                result["replay_permitted"] = False
            result["local_evidence_error"] = (
                type(evidence_error).__name__
                + ":"
                + str(evidence_error)[:180]
            )
            return_code = 2

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
