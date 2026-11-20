#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import re
import subprocess
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
    "U8_RECOVERY_ADMISSION_R33_20261115_01"
)
CONFIRMATION = "EXECUTE U8 R33 RECOVERY ADMISSION: YES"
MANIFEST_SCHEMA = "gh.n3w-t1-u8-r33-recovery-admission-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u8-r33-local-result/1"
PREFLIGHT_TIMEOUT_SECONDS = 1200
PREFLIGHT_REMOTE_PROCESS_TIMEOUT_SECONDS = 1170
EXECUTE_TIMEOUT_SECONDS = 1500


class Stop(RuntimeError):
    pass


def load_base():
    spec = importlib.util.spec_from_file_location("n3w_r33_base", BASE_EXECUTOR)
    if spec is None or spec.loader is None:
        raise Stop("base_executor_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REMOTE_SCRIPT = r'''
import base64
import dataclasses
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TX = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
R32 = Path(
    "/var/lib/n3w-t1-core-updater/"
    "u7-r32-repaired-ha-quiesce-backup-20261115-01"
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
    descriptor, raw = tempfile.mkstemp(
        prefix="." + path.name + ".",
        dir=path.parent,
    )
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
        if (
            value.get("ActiveState") not in {"inactive", "failed"}
            or value.get("MainPID") != "0"
            or value.get("NRestarts") != "0"
        ):
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
        or result["container_id"] != expected["container_id"]
        or result["restart_count"] != 0
    ):
        raise Stop("container_identity_drift:" + expected["image"])
    return result


def verify_quiesced_runtime(plan):
    units = {
        "host": require_unit(HOST_UNIT, active=True),
        "services_owner": require_unit(SERVICES_UNIT, active=False),
        "broker_owner": require_unit(BROKER_UNIT, active=True),
    }
    containers = {
        name: docker_snapshot(expected)
        for name, expected in plan["containers"].items()
    }
    if containers["broker"].get("status") != "running":
        raise Stop("broker_not_running_u8_prestate")
    if containers["manager"].get("status") == "running":
        raise Stop("manager_not_quiesced_u8_prestate")
    if containers["homeassistant"].get("status") == "running":
        raise Stop("homeassistant_not_quiesced_u8_prestate")
    return {"units": units, "containers": containers}


def verify_predecessor_internal_image(plan):
    completed = run(
        ["docker", "image", "inspect", plan["predecessor_image"]],
        timeout=45,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("predecessor_internal_image_missing")
    try:
        documents = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Stop("predecessor_internal_image_invalid") from error
    if not isinstance(documents, list) or len(documents) != 1:
        raise Stop("predecessor_internal_image_invalid")
    if documents[0].get("Id") != plan["predecessor_runtime_image_id"]:
        raise Stop("predecessor_internal_image_drift")
    return {
        "image_ref": plan["predecessor_image"],
        "image_id": plan["predecessor_runtime_image_id"],
        "present": True,
    }


def verify_target_internal_image_absent(plan):
    completed = run(
        ["docker", "image", "inspect", plan["target_image"]],
        timeout=45,
        check=False,
    )
    if completed.returncode == 0:
        raise Stop("target_internal_image_unexpectedly_present")
    return {"image_ref": plan["target_image"], "present": False}


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
        transaction.get("phase")
        != "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or sha_file(TX) != plan["transaction_sha256"]
        or transaction.get("target_image_ref") != plan["target_image"]
        or transaction.get("current_image_ref") != plan["predecessor_image"]
        or transaction.get("target_archive_sha256")
        != plan["target_archive_sha256"]
        or transaction.get("target_archive_size")
        != plan["target_archive_size_bytes"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not True
        or transaction.get("predecessor_recovery_identity")
        != plan["predecessor_identity"]
        or transaction.get("ha_data_backup_verified") is not True
        or transaction.get("ha_data_backup_identity")
        != plan["backup_identity"]
        or transaction.get("recovery_content_manifest_sha256") is not None
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
    ):
        raise Stop("u8_r33_u7_transaction_invalid")
    return transaction


def verify_r32(plan):
    claim = read_object(R32 / "authorization_claim.json")
    success = read_object(R32 / "success.json")
    if (
        claim.get("authorization_id") != plan["r32_gate_id"]
        or claim.get("execution_id") != plan["r32_execution_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or success.get("status")
        != "U7_R32_REPAIRED_HA_QUIESCE_DATA_BACKUP_PASS"
        or success.get("authorization_claimed") is not True
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or success.get("backup_verified") is not True
        or success.get("backup") != plan["backup_identity"]
        or success.get("transaction_phase")
        != "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
        or success.get("transaction_sha256") != plan["transaction_sha256"]
        or success.get("u8_plus") is not False
        or success.get("rollback_required") is not False
        or success.get("recovery_attempted") is not False
    ):
        raise Stop("r32_authority_invalid")
    return True


def import_product():
    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_backup import (
        ProtectedHaDataBackupProvider,
        backup_record_from_document,
    )
    from n3w_t1_core_updater_ha_capacity import (
        validate_recovery_admission_capacity,
    )
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_recovery import (
        image_recovery_record_from_document,
    )
    from n3w_t1_core_updater_ha_usb import record_recovery_admission
    from n3w_t1_core_updater_ha_usb_media import assess_capacity
    from n3w_t1_core_updater_ha_usb_state import (
        HaUsbStateStore,
        validate_transaction_document,
    )

    return {
        "ProtectedHaDataBackupProvider": ProtectedHaDataBackupProvider,
        "backup_record_from_document": backup_record_from_document,
        "validate_recovery_admission_capacity": (
            validate_recovery_admission_capacity
        ),
        "SubprocessPrepareBackend": SubprocessPrepareBackend,
        "image_recovery_record_from_document": (
            image_recovery_record_from_document
        ),
        "record_recovery_admission": record_recovery_admission,
        "assess_capacity": assess_capacity,
        "HaUsbStateStore": HaUsbStateStore,
        "validate_transaction_document": validate_transaction_document,
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
        raise Stop("u8_media_not_already_mounted")
    fields = completed.stdout.strip().split(None, 3)
    if len(fields) != 4:
        raise Stop("u8_media_mount_probe_invalid")
    source, target, fstype, options = fields
    option_set = set(options.split(","))
    if (
        not source.startswith("/dev/")
        or target != mount_path
        or fstype != "ext4"
        or "rw" not in option_set
        or not {"nodev", "nosuid", "noexec"}.issubset(option_set)
    ):
        raise Stop("u8_media_mount_not_live_eligible")
    return {
        "source_kind": "block_device",
        "target": mount_path,
        "fstype": fstype,
        "rw": True,
        "nodev": True,
        "nosuid": True,
        "noexec": True,
    }


def verify_archive_continuity(path, expected_sha256, expected_size):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("u8_archive_continuity_file_invalid:" + path.name)
    if (
        not isinstance(expected_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        or type(expected_size) is not int
        or expected_size <= 0
    ):
        raise Stop("u8_archive_continuity_authority_invalid:" + path.name)
    if path.stat().st_size != expected_size:
        raise Stop("u8_archive_continuity_size_mismatch:" + path.name)
    observed_sha256 = sha_file(path)
    if observed_sha256 != expected_sha256:
        raise Stop("u8_archive_continuity_sha256_mismatch:" + path.name)
    return {
        "sha256": observed_sha256,
        "size_bytes": expected_size,
    }


def build_admission_inputs(plan, transaction, *, write_required):
    product = import_product()
    backend = product["SubprocessPrepareBackend"]()
    media = backend.resolve_transaction_media(
        transaction,
        write_required=write_required,
    )
    if media is None or media.mount_path != plan["mount_target"]:
        raise Stop("u8_media_resolution_invalid")

    target = product["image_recovery_record_from_document"](
        transaction.get("target_artifact_identity"),
        expected_kind="target",
        expected_image_ref=transaction["target_image_ref"],
        expected_archive_sha256=transaction["target_archive_sha256"],
    )
    if (
        target.public() != transaction.get("target_artifact_identity")
        or target.archive_size_bytes != transaction["target_archive_size"]
    ):
        raise Stop("u8_target_identity_drift")

    predecessor = product["image_recovery_record_from_document"](
        transaction.get("predecessor_recovery_identity"),
        expected_kind="predecessor",
        expected_image_ref=transaction["current_image_ref"],
        expected_archive_sha256=plan["predecessor_identity"]["archive_sha256"],
    )
    if predecessor.public() != plan["predecessor_identity"]:
        raise Stop("u8_predecessor_identity_drift")

    backup = product["backup_record_from_document"](
        transaction.get("ha_data_backup_identity")
    )
    if backup.public() != plan["backup_identity"]:
        raise Stop("u8_backup_identity_drift")

    capacity_report = product["assess_capacity"](
        transaction["usb_measured_usable_bytes"],
        backend.capacity_inputs(transaction),
    )
    if capacity_report.capacity_pass is not True:
        raise Stop("u8_media_capacity_not_verified")

    recovery_capacity = backend.recovery_admission_capacity(
        transaction,
        media,
        target=target,
        predecessor=predecessor,
        backup=backup,
    )
    product["validate_recovery_admission_capacity"](
        recovery_capacity,
        target_archive_bytes=target.archive_size_bytes,
        predecessor_archive_bytes=predecessor.archive_size_bytes,
        ha_backup_archive_bytes=backup.archive_size_bytes,
    )

    return (
        product,
        backend,
        media,
        target,
        predecessor,
        backup,
        capacity_report,
        recovery_capacity,
    )


def verify_media_and_recovery_inputs(plan, transaction):
    mount = require_existing_rw_mount(plan)
    (
        product,
        _backend,
        media,
        target,
        predecessor,
        backup,
        capacity_report,
        recovery_capacity,
    ) = build_admission_inputs(plan, transaction, write_required=False)

    mount_path = Path(media.mount_path)
    target_continuity = verify_archive_continuity(
        mount_path / "n3w-update" / "target" / "homeassistant-arm64.tar.gz",
        target.archive_sha256,
        target.archive_size_bytes,
    )
    predecessor_continuity = verify_archive_continuity(
        mount_path
        / "n3w-update"
        / "predecessor"
        / "homeassistant-predecessor.tar.gz",
        predecessor.archive_sha256,
        predecessor.archive_size_bytes,
    )

    provider = product["ProtectedHaDataBackupProvider"]()
    verified_backup = provider.verify_backup(
        backup,
        transaction_id_sha256=transaction["transaction_id_sha256"],
        destination_root=mount_path / "n3w-update" / "ha-data",
    )
    if verified_backup.public() != plan["backup_identity"]:
        raise Stop("u8_backup_verification_identity_drift")

    return {
        "mount": mount,
        "target_archive_continuity": target_continuity,
        "predecessor_archive_continuity": predecessor_continuity,
        "backup_verified": True,
        "backup_identity": verified_backup.public(),
        "initial_capacity_pass": capacity_report.capacity_pass,
        "recovery_capacity": dataclasses.asdict(recovery_capacity),
        "portable_identity_authority_reused": True,
    }


def verify_prestate(plan):
    source_hashes = verify_source_hashes(plan)
    transaction = verify_transaction(plan)
    verify_r32(plan)
    runtime = verify_quiesced_runtime(plan)
    predecessor_image = verify_predecessor_internal_image(plan)
    target_image = verify_target_internal_image_absent(plan)
    media = verify_media_and_recovery_inputs(plan, transaction)
    return {
        "transaction_sha256": sha_file(TX),
        "source_hash_count": len(source_hashes),
        "r32_consumed_no_replay": True,
        "runtime": runtime,
        "predecessor_internal_image": predecessor_image,
        "target_internal_image": target_image,
        "media": media,
        "production_prestate_exact": True,
    }


def mirror_documents(plan):
    mirror = Path(plan["mount_target"]) / "n3w-update" / "transaction"
    return (
        read_object(mirror / "manifest.json"),
        read_object(mirror / "phase.json"),
        read_object(mirror / "content-authority.json"),
    )


def verify_terminal_u8_state(plan):
    transaction = read_object(TX)
    recovery_manifest = transaction.get("recovery_content_manifest_sha256")
    if (
        transaction.get("phase") != "U8_RECOVERY_ADMISSION_COMPLETE"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not True
        or transaction.get("ha_data_backup_verified") is not True
        or transaction.get("production_prestate_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
        or not isinstance(recovery_manifest, str)
        or re.fullmatch(r"[0-9a-f]{64}", recovery_manifest) is None
    ):
        raise Stop("r33_terminal_transaction_mismatch")

    product = import_product()
    product["validate_transaction_document"](transaction)
    require_existing_rw_mount(plan)
    manifest, phase, authority = mirror_documents(plan)
    if (
        manifest.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or manifest.get("usb_filesystem_uuid")
        != transaction.get("usb_filesystem_uuid")
        or manifest.get("usb_device_identity_public_fingerprint")
        != transaction.get("usb_device_identity_public_fingerprint")
        or phase.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or phase.get("phase") != "U8_RECOVERY_ADMISSION_COMPLETE"
        or phase.get("target_artifact_verified") is not True
        or phase.get("usb_capacity_verified") is not True
        or authority.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or authority.get("target_artifact_identity")
        != transaction.get("target_artifact_identity")
        or authority.get("predecessor_recovery_identity")
        != transaction.get("predecessor_recovery_identity")
        or authority.get("ha_data_backup_identity")
        != transaction.get("ha_data_backup_identity")
        or authority.get("recovery_content_manifest_sha256")
        != recovery_manifest
    ):
        raise Stop("r33_terminal_usb_mirror_mismatch")
    runtime = verify_quiesced_runtime(plan)
    verify_predecessor_internal_image(plan)
    verify_target_internal_image_absent(plan)
    return {
        "transaction_exact": True,
        "transaction_sha256": sha_file(TX),
        "transaction_phase": transaction["phase"],
        "recovery_content_manifest_sha256": recovery_manifest,
        "usb_mirror_exact": True,
        "runtime_quiesced": True,
        "broker_continuity": True,
        "predecessor_internal_image_preserved": True,
        "target_internal_image_absent": True,
    }


def read_terminal_status(plan):
    state_root = Path(plan["state_root"])
    if not state_root.exists():
        return {
            "schema": "gh.n3w-t1-u8-r33-status/1",
            "status": "NOT_STARTED",
            "terminal": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
        }
    if state_root.is_symlink() or not state_root.is_dir():
        raise Stop("r33_state_root_invalid")
    success_path = state_root / "success.json"
    failure_path = state_root / "failure.json"
    claim_path = state_root / "authorization_claim.json"
    progress_path = state_root / "progress.json"
    claim = read_object(claim_path) if claim_path.exists() else None
    if success_path.exists():
        value = read_object(success_path)
        value["terminal_reconciliation"] = verify_terminal_u8_state(plan)
        value["terminal"] = True
        value["reconciled_from_ledger"] = True
        return value
    if failure_path.exists():
        value = read_object(failure_path)
        value["terminal"] = True
        value["reconciled_from_ledger"] = True
        return value
    if claim is not None:
        try:
            terminal = verify_terminal_u8_state(plan)
            return {
                "schema": "gh.n3w-t1-u8-r33-status/1",
                "status": "U8_R33_RECOVERY_ADMISSION_PASS_RECONCILED",
                "terminal": True,
                "authorization_claimed": True,
                "authorization_consumed": True,
                "replay_permitted": False,
                "reconciled_from_durable_u8": True,
                "terminal_reconciliation": terminal,
            }
        except Exception:
            pass
    progress = read_object(progress_path) if progress_path.exists() else None
    transaction = read_object(TX)
    return {
        "schema": "gh.n3w-t1-u8-r33-status/1",
        "status": "RUNNING_OR_INTERRUPTED",
        "terminal": False,
        "authorization_claimed": bool(
            claim and claim.get("claimed") is True
        ),
        "authorization_consumed": bool(
            claim and claim.get("consumed") is True
        ),
        "replay_permitted": False,
        "progress": progress,
        "transaction_phase": transaction.get("phase"),
    }


def execute(plan, authorization_id, confirmation):
    result = {
        "schema": "gh.n3w-t1-u8-r33-recovery-admission/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "service_stop": False,
        "service_restart": False,
        "ha_quiesced": True,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u8_transition": False,
        "u9_plus": False,
        "destructive_cutover": False,
        "predecessor_image_delete": False,
        "target_image_load": False,
        "rollback_required": False,
    }
    if (
        authorization_id != plan["authorization_id"]
        or confirmation != plan["confirmation"]
        or plan.get("live_execution_authorized") is not True
        or plan.get("authorization_state")
        != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("r33_state_root_residue")

    pre = verify_prestate(plan)

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    claim = {
        "schema": "gh.n3w-t1-u8-r33-authorization-claim/1",
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

    def progress(phase, value=0):
        if (
            not isinstance(phase, str)
            or re.fullmatch(r"[a-z0-9_]{1,64}", phase) is None
            or type(value) is not int
            or value < 0
        ):
            raise Stop("u8_progress_invalid")
        durable_json_replace(
            state_root / "progress.json",
            {
                "schema": "gh.n3w-t1-u8-r33-progress/1",
                "phase": phase,
                "value": value,
                "updated_at_unix": int(time.time()),
            },
        )

    try:
        progress("executor_claimed")
        product = import_product()
        store = product["HaUsbStateStore"]()
        backend = product["SubprocessPrepareBackend"]()
        with store.lock():
            current = store.read()
            if current is None:
                raise Stop("u8_transaction_missing")
            current = product["validate_transaction_document"](current)
            if sha_file(TX) != plan["transaction_sha256"]:
                raise Stop("u8_transaction_drift_after_claim")
            (
                _product,
                _backend,
                media,
                target,
                predecessor,
                backup,
                capacity_report,
                recovery_capacity,
            ) = build_admission_inputs(
                plan,
                current,
                write_required=True,
            )
            progress("recovery_admission_revalidate")
            admitted = product["record_recovery_admission"](
                current,
                target=target,
                predecessor=predecessor,
                backup=backup,
                capacity_report=capacity_report,
                recovery_capacity=recovery_capacity,
                production_prestate_exact=True,
            )
            progress("recovery_admission_usb_sync")
            backend.sync_transaction_metadata(admitted, media)
            progress("recovery_admission_host_sync")
            store.write(admitted)

        terminal = verify_terminal_u8_state(plan)
        result.update(
            status="U8_R33_RECOVERY_ADMISSION_PASS",
            transaction_mutation=True,
            usb_mutation=True,
            u8_transition=True,
            u9_plus=False,
            transaction_phase=terminal["transaction_phase"],
            transaction_sha256=terminal["transaction_sha256"],
            recovery_content_manifest_sha256=(
                terminal["recovery_content_manifest_sha256"]
            ),
            pre=pre,
            post=terminal,
        )
        progress("executor_success")
        durable_json_once(state_root / "success.json", result)
        return result
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        try:
            result["transaction_mutation"] = (
                sha_file(TX) != plan["transaction_sha256"]
            )
            current = read_object(TX)
            result["transaction_phase"] = current.get("phase")
            result["u8_transition"] = (
                current.get("phase") == "U8_RECOVERY_ADMISSION_COMPLETE"
            )
        except Exception:
            pass
        try:
            _manifest, phase, _authority = mirror_documents(plan)
            result["usb_mutation"] = (
                phase.get("phase") == "U8_RECOVERY_ADMISSION_COMPLETE"
            )
        except Exception:
            pass
        try:
            result["postclaim_terminal_probe"] = verify_terminal_u8_state(plan)
            result["status"] = "STOP_POSTSUCCESS_LOCAL"
        except Exception as reconcile_error:
            result["status"] = "STOP_POSTCLAIM"
            result["reconciliation_error"] = (
                type(reconcile_error).__name__
                + ":"
                + str(reconcile_error)[:180]
            )
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
            "U8_RECOVERY_ADMISSION_R33_20261115_01"
        ):
            raise Stop("gate_id_invalid")

        if mode == "preflight":
            state_root = Path(plan["state_root"])
            if state_root.exists() or state_root.is_symlink():
                raise Stop("r33_state_root_residue")
            result = {
                "schema": "gh.n3w-t1-u8-r33-preflight/1",
                "status": "PASS",
                "read_only": True,
                "u8_live_eligible": True,
                "live_execution_authorized": (
                    plan.get("live_execution_authorized") is True
                ),
                "preflight": verify_prestate(plan),
                "authorization_claimed": False,
                "authorization_consumed": False,
                "replay_permitted": False,
                "service_stop": False,
                "service_restart": False,
                "transaction_mutation": False,
                "usb_mutation": False,
                "u8_transition": False,
                "u9_plus": False,
                "destructive_cutover": False,
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
        in {
            "PASS",
            "U8_R33_RECOVERY_ADMISSION_PASS",
            "U8_R33_RECOVERY_ADMISSION_PASS_RECONCILED",
        }
        else 2
    )


raise SystemExit(main())
'''


def git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("git_command_failed:" + args[0])
    return completed.stdout.strip()


def read_manifest(expected_commit: str, *, execute: bool) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")

    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        document.get("schema") != MANIFEST_SCHEMA
        or document.get("gate_id") != GATE_ID
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


def remote_mode(
    transport,
    mode,
    plan,
    *extra,
    timeout=300,
    remote_process_timeout=None,
):
    payload = base64.b64encode(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    argv = ["python3", "-B", "-c", REMOTE_SCRIPT, mode, payload, *extra]
    if remote_process_timeout is not None:
        argv = [
            "timeout",
            "--signal=TERM",
            "--kill-after=15s",
            str(remote_process_timeout),
            *argv,
        ]
    completed = transport.run_remote(
        argv,
        timeout=timeout,
        check=False,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    try:
        result = json.loads(lines[-1]) if lines else {}
    except Exception:
        result = {}
    if not isinstance(result, dict) or not result:
        if completed.returncode in {124, 137}:
            result = {"status": "STOP", "reason": "remote_process_timeout"}
        else:
            result = {"status": "STOP", "reason": "remote_result_invalid"}
    return completed, result


def reconcile_after_invoke(transport, plan, evidence, base):
    try:
        status_transport, status = remote_mode(
            transport,
            "status",
            plan,
            timeout=180,
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
            "reason": (
                "status_reconciliation_failed:"
                + type(error).__name__
                + ":"
                + str(error)[:180]
            ),
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
        "schema": LOCAL_RESULT_SCHEMA,
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
        "transaction_mutation": False,
        "usb_mutation": False,
        "u8_transition": False,
        "u9_plus": False,
        "destructive_cutover": False,
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

        if args.preflight_only:
            pre_transport, preflight = remote_mode(
                transport,
                "preflight",
                plan,
                timeout=PREFLIGHT_TIMEOUT_SECONDS,
                remote_process_timeout=PREFLIGHT_REMOTE_PROCESS_TIMEOUT_SECONDS,
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
                    "r33_preflight_failed:"
                    + str(preflight.get("reason"))
                )
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
                    timeout=EXECUTE_TIMEOUT_SECONDS,
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
                base.write_private_json(evidence / "execute.json", remote)
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
                    )

            if result.get("status") in {
                "U8_R33_RECOVERY_ADMISSION_PASS",
                "U8_R33_RECOVERY_ADMISSION_PASS_RECONCILED",
            }:
                return_code = 0
            else:
                return_code = 2
    except Exception as error:
        result.update(
            status="STOP",
            reason=type(error).__name__ + ":" + str(error)[:300],
        )
        return_code = 2
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
                    + str(cleanup_error)[:180]
                )
                if return_code == 0:
                    result["completed_remote_status"] = result.get("status")
                    result["status"] = "STOP_POSTSUCCESS_LOCAL"
                    return_code = 2
        try:
            if "evidence" in locals():
                base.write_private_json(evidence / "local_result.json", result)
        except Exception:
            if return_code == 0:
                result["completed_remote_status"] = result.get("status")
                result["status"] = "STOP_POSTSUCCESS_LOCAL"
                return_code = 2

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
