#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import shlex
import stat
import subprocess
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
SSH_TRANSPORT_PATH = ROOT / "tools/n3w_t1_ssh_transport.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "KF152_DEPENDENCY_SAFE_SOURCE_ACTIVATION_R17_20261113_01"
)
CONFIRMATION = (
    "EXECUTE KF152 DEPENDENCY SAFE SOURCE ACTIVATION R17: YES"
)

REMOTE_STREAM_WRITE = r"""
import os
import sys

path = sys.argv[1]
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
fd = os.open(path, flags, 0o600)
with os.fdopen(fd, "wb", closefd=True) as output:
    while True:
        block = sys.stdin.buffer.read(1024 * 1024)
        if not block:
            break
        output.write(block)
    output.flush()
    os.fsync(output.fileno())
directory = os.open(
    os.path.dirname(path),
    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
)
try:
    os.fsync(directory)
finally:
    os.close(directory)
"""

REMOTE_SCRIPT = r"""
import base64
import hashlib
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

HOST_UNIT = "n3w-t1-ha-ota.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
TX_SCHEMA = "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"


class Stop(RuntimeError):
    pass


def run(argv, *, check=True, timeout=120):
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
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha1(path):
    payload = Path(path).read_bytes()
    digest = hashlib.sha1()
    digest.update(
        b"blob "
        + str(len(payload)).encode("ascii")
        + b"\0"
    )
    digest.update(payload)
    return digest.hexdigest()


def fsync_dir(path):
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def require_regular(path, mode):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("file_invalid:" + str(path))
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise Stop("file_metadata_invalid:" + str(path))


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("json_file_invalid:" + path.name)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("json_invalid:" + path.name) from error
    if not isinstance(value, dict):
        raise Stop("json_shape_invalid:" + path.name)
    return value


def durable_json(path, value):
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


def atomic_install(source, target):
    source = Path(source)
    target = Path(target)
    require_regular(source, 0o600)
    if target.is_symlink() or not target.is_file():
        raise Stop("target_file_invalid:" + str(target))
    temp = target.parent / (
        ".n3w-kf147-v12." + target.name + "." + str(os.getpid())
    )
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(temp, flags, 0o644)
    try:
        with source.open("rb") as inp, os.fdopen(
            descriptor,
            "wb",
            closefd=False,
        ) as out:
            shutil.copyfileobj(inp, out, length=1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        os.fchmod(descriptor, 0o644)
        os.fchown(descriptor, 0, 0)
    finally:
        os.close(descriptor)
    os.replace(temp, target)
    fsync_dir(target.parent)


def _boolish(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def _mountpoints(node):
    raw = node.get("mountpoints")
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise Stop("usb_mountpoints_invalid")
    return tuple(
        item.strip()
        for item in raw
        if isinstance(item, str) and item.strip()
    )


def _flatten_blocks(nodes):
    flattened = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        flattened.append(node)
        children = node.get("children")
        if isinstance(children, list):
            flattened.extend(_flatten_blocks(children))
    return flattened


def _lsblk_tree():
    completed = run(
        [
            "lsblk",
            "--json",
            "--bytes",
            "--paths",
            "--tree",
            "--output",
            "NAME,PATH,TYPE,RM,RO,SIZE,MODEL,SERIAL,WWN,TRAN,"
            "MOUNTPOINTS,MAJ:MIN",
        ],
        timeout=30,
    )
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Stop("usb_inventory_invalid") from error
    blocks = document.get("blockdevices")
    if not isinstance(blocks, list):
        raise Stop("usb_inventory_invalid")
    return [node for node in blocks if isinstance(node, dict)]


def _single_output(argv, reason):
    completed = run(argv, check=False, timeout=30)
    if completed.returncode != 0:
        raise Stop(reason)
    value = completed.stdout.strip()
    if not value:
        raise Stop(reason)
    return value


def safe_compatible_media(transaction):
    transaction_id = transaction.get("transaction_id_sha256")
    if not isinstance(transaction_id, str) or len(transaction_id) != 64:
        raise Stop("transaction_id_invalid")
    expected_runtime_mount = (
        "/run/n3w-t1-ota/media/" + transaction_id[:16]
    )
    root_major_minor = _single_output(
        ["findmnt", "--noheadings", "--output", "MAJ:MIN", "/"],
        "root_device_unresolved",
    )
    matches = []
    for disk in _lsblk_tree():
        if disk.get("type") != "disk":
            continue
        path = disk.get("path")
        if not isinstance(path, str) or not path.startswith("/dev/"):
            continue
        if (
            str(disk.get("tran") or "").strip().lower() != "usb"
            or not _boolish(disk.get("rm"))
            or _boolish(disk.get("ro"))
        ):
            continue
        descendants = _flatten_blocks([disk])
        major_minors = {
            str(item.get("maj:min") or "").strip()
            for item in descendants
        }
        if root_major_minor in major_minors:
            continue
        partitions = [
            item
            for item in descendants
            if item.get("type") == "part"
            and isinstance(item.get("path"), str)
            and item["path"].startswith("/dev/")
        ]
        if len(partitions) != 1:
            continue
        partition = partitions[0]
        mounted = tuple(
            point
            for item in descendants
            for point in _mountpoints(item)
        )
        if mounted and set(mounted) != {expected_runtime_mount}:
            continue
        fs = run(
            ["blkid", "-s", "TYPE", "-o", "value", partition["path"]],
            check=False,
            timeout=30,
        )
        label = run(
            ["blkid", "-s", "LABEL", "-o", "value", partition["path"]],
            check=False,
            timeout=30,
        )
        if (
            fs.returncode != 0
            or label.returncode != 0
            or fs.stdout.strip() != "ext4"
            or label.stdout.strip() != "N3W-UPDATE"
        ):
            continue
        matches.append(
            {
                "parent": path,
                "partition": partition["path"],
                "partition_major_minor": str(
                    partition.get("maj:min") or ""
                ).strip(),
                "mount_state": (
                    "UPDATER_RUNTIME_MOUNTED"
                    if mounted
                    else "UNMOUNTED"
                ),
                "filesystem_type": "ext4",
                "filesystem_label": "N3W-UPDATE",
                "serial_present": bool(
                    isinstance(disk.get("serial"), str)
                    and disk["serial"].strip()
                ),
                "wwn_present": bool(
                    isinstance(disk.get("wwn"), str)
                    and disk["wwn"].strip()
                ),
            }
        )
    if not matches:
        raise Stop("compatible_product_media_required")
    if len(matches) != 1:
        raise Stop("usb_multiple_eligible_devices")
    return matches[0]


def docker_view(image):
    ids = [
        line.strip()
        for line in run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "ancestor=" + image,
                "--format",
                "{{.ID}}",
            ],
            timeout=60,
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(ids) != 1:
        raise Stop("container_cardinality_invalid:" + image)
    try:
        document = json.loads(
            run(["docker", "inspect", ids[0]], timeout=60).stdout
        )
    except json.JSONDecodeError as error:
        raise Stop("container_inspect_invalid:" + image) from error
    if not isinstance(document, list) or len(document) != 1:
        raise Stop("container_inspect_invalid:" + image)
    item = document[0]
    state = (
        item.get("State")
        if isinstance(item.get("State"), dict)
        else {}
    )
    return {
        "runtime_image_id": item.get("Image"),
        "restart_count": item.get("RestartCount"),
        "status": state.get("Status"),
        "exit_code": state.get("ExitCode"),
    }


def service_state(unit):
    keys = ["ActiveState", "SubState", "Result", "NRestarts"]
    result = {}
    for key in keys:
        result[key] = run(
            ["systemctl", "show", unit, "-p", key, "--value"],
            check=False,
            timeout=30,
        ).stdout.strip()
    return result


def wait_unit(unit, desired, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        value = run(
            ["systemctl", "is-active", unit],
            check=False,
            timeout=30,
        ).stdout.strip()
        if desired == "active" and value == "active":
            return
        if desired == "inactive" and value in {"inactive", "failed"}:
            return
        time.sleep(1)
    raise Stop("unit_state_timeout:" + unit + ":" + desired)


def ipc_status(manager_image):
    ids = [
        line.strip()
        for line in run(
            [
                "docker",
                "ps",
                "--filter",
                "ancestor=" + manager_image,
                "--format",
                "{{.ID}}",
            ],
            timeout=45,
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(ids) != 1:
        raise Stop("manager_container_cardinality_invalid")
    probe = r'''import json,socket
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(5)
s.connect("/run/n3w/t1-ota/ha-ota.sock")
s.sendall(json.dumps({"schema":"gh.n3w-t1-ha-ota-ipc-request/1","operation":"status"},separators=(",",":")).encode()+b"\n")
s.shutdown(socket.SHUT_WR)
print(s.recv(8192).decode().strip())'''
    completed = run(
        [
            "docker",
            "exec",
            "-u",
            "999:999",
            ids[0],
            "python3",
            "-c",
            probe,
        ],
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise Stop("ipc_status_unavailable:" + str(completed.returncode))
    try:
        value = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as error:
        raise Stop("ipc_status_invalid") from error
    if (
        not isinstance(value, dict)
        or value.get("accepted") is not True
        or value.get("code") != "status"
    ):
        raise Stop("ipc_status_rejected")
    return value


def verify_transaction(plan):
    transaction = read_json(TX_PATH)
    if (
        transaction.get("schema") != TX_SCHEMA
        or transaction.get("phase") != "U4_READY_TO_INSTALL"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
    ):
        raise Stop("legacy_u4_transaction_invalid")
    for field in (
        "target_artifact_identity",
        "predecessor_recovery_identity",
        "ha_data_backup_identity",
        "recovery_content_manifest_sha256",
    ):
        if transaction.get(field) is not None:
            raise Stop("legacy_u4_already_extended:" + field)
    digest = sha_file(TX_PATH)
    if digest != plan["transaction_sha256"]:
        raise Stop("legacy_u4_transaction_sha256_drift")
    return transaction, digest


def verify_source_set(plan, *, target):
    observed = {}
    key = "target_sha256" if target else "predecessor_sha256"
    for item in plan["source_files"]:
        path = item["remote_path"]
        require_regular(path, 0o644)
        digest = sha_file(path)
        if digest != item[key]:
            raise Stop(
                ("target" if target else "predecessor")
                + "_source_drift:"
                + item["repo_path"]
            )
        observed[path] = digest
    for path, expected in plan["runtime_git_blob_sha1"].items():
        require_regular(path, 0o644)
        if git_blob_sha1(path) != expected:
            raise Stop("runtime_dependency_drift:" + Path(path).name)
    return observed


def verify_containers(plan):
    result = {}
    for name, expected in plan["containers"].items():
        observed = docker_view(expected["image"])
        if (
            observed["runtime_image_id"] != expected["runtime_image_id"]
            or observed["restart_count"] != 0
        ):
            raise Stop("container_drift:" + name)
        if observed["status"] != "running":
            raise Stop("container_not_ready:" + name)
        result[name] = observed
    return result


def verify_r16_terminal_residue(plan):
    state_root = Path(plan["r16_terminal_state_root"])
    stage_root = Path(plan["r16_terminal_stage_root"])
    if state_root.is_symlink() or not state_root.is_dir():
        raise Stop("r16_terminal_state_root_invalid")
    if stage_root.is_symlink() or not stage_root.is_dir():
        raise Stop("r16_terminal_stage_root_invalid")
    claim = read_json(state_root / "authorization_claim.json")
    failure = read_json(state_root / "failure.json")
    if claim != {
        "authorization_id": (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "KF151_USB_MEDIA_RESOLVER_SOURCE_ACTIVATION_R16_20261113_01"
        ),
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
    }:
        raise Stop("r16_terminal_claim_invalid")
    if (
        failure.get("status") != "STOP"
        or failure.get("first_failed_operation") != "Stop:services_owner_not_active"
        or failure.get("authorization_claimed") is not True
        or failure.get("authorization_consumed") is not True
        or failure.get("transaction_mutation") is not False
        or failure.get("usb_mutation") is not False
        or failure.get("u5_transition") is not False
        or failure.get("u6_plus") is not False
        or not isinstance(failure.get("rollback"), dict)
        or failure["rollback"].get("status") != "STOP"
    ):
        raise Stop("r16_terminal_failure_invalid")
    active = [item for item in plan["source_files"] if item.get("activate") is True]
    if len(active) != 1:
        raise Stop("r17_activation_scope_invalid")
    item = active[0]
    staged = stage_root / item["stage_name"]
    backup = stage_root / ".preclaim-backup" / item["stage_name"]
    require_regular(staged, 0o600)
    require_regular(backup, 0o600)
    if sha_file(staged) != item["target_sha256"]:
        raise Stop("r16_staged_target_drift")
    if sha_file(backup) != item["predecessor_sha256"]:
        raise Stop("r16_backup_predecessor_drift")
    return {
        "claim_consumed": True,
        "failure": "services_owner_not_active",
        "staged_target_sha256": sha_file(staged),
        "backup_predecessor_sha256": sha_file(backup),
    }


def failed_prestate(plan):
    transaction, transaction_sha = verify_transaction(plan)
    sources = verify_source_set(plan, target=False)
    residue = verify_r16_terminal_residue(plan)
    host = service_state(HOST_UNIT)
    services = service_state(SERVICES_UNIT)
    broker_owner = service_state(BROKER_UNIT)
    if (
        host.get("ActiveState") != "active"
        or host.get("SubState") != "running"
        or host.get("Result") != "success"
        or host.get("NRestarts") != "0"
    ):
        raise Stop("r17_host_prestate_invalid")
    if (
        services.get("ActiveState") != "failed"
        or services.get("SubState") != "failed"
        or services.get("Result") != "exit-code"
        or services.get("NRestarts") != "0"
    ):
        raise Stop("r17_services_owner_prestate_invalid")
    if (
        broker_owner.get("ActiveState") != "active"
        or broker_owner.get("SubState") != "running"
        or broker_owner.get("Result") != "success"
        or broker_owner.get("NRestarts") != "0"
    ):
        raise Stop("r17_broker_owner_prestate_invalid")
    expected_status = {
        "manager": ("exited", 137),
        "homeassistant": ("exited", 137),
        "broker": ("running", 0),
    }
    containers = {}
    for name, expected in plan["containers"].items():
        observed = docker_view(expected["image"])
        status, exit_code = expected_status[name]
        if (
            observed["runtime_image_id"] != expected["runtime_image_id"]
            or observed["restart_count"] != 0
            or observed["status"] != status
            or observed["exit_code"] != exit_code
        ):
            raise Stop("r17_container_prestate_invalid:" + name)
        containers[name] = observed
    media = safe_compatible_media(transaction)
    if media.get("mount_state") != "UNMOUNTED":
        raise Stop("r17_usb_prestate_must_be_unmounted")
    return {
        "transaction_phase": transaction["phase"],
        "transaction_sha256": transaction_sha,
        "sources": sources,
        "service": host,
        "services_owner": services,
        "broker_owner": broker_owner,
        "containers": containers,
        "compatible_media": media,
        "r16_terminal": residue,
    }


def baseline(plan, *, target_sources):
    transaction, transaction_sha = verify_transaction(plan)
    sources = verify_source_set(plan, target=target_sources)
    host = service_state(HOST_UNIT)
    services = service_state(SERVICES_UNIT)
    broker_owner = service_state(BROKER_UNIT)
    if (
        host.get("ActiveState") != "active"
        or host.get("SubState") != "running"
        or host.get("Result") != "success"
        or host.get("NRestarts") != "0"
    ):
        raise Stop("host_service_not_healthy")
    if (
        services.get("ActiveState") != "active"
        or services.get("SubState") != "running"
        or services.get("Result") != "success"
        or services.get("NRestarts") != "0"
    ):
        raise Stop("services_owner_not_active")
    if (
        broker_owner.get("ActiveState") != "active"
        or broker_owner.get("SubState") != "running"
        or broker_owner.get("Result") != "success"
        or broker_owner.get("NRestarts") != "0"
    ):
        raise Stop("broker_owner_not_healthy")
    containers = verify_containers(plan)
    ipc = ipc_status(plan["containers"]["manager"]["image"])
    if (
        ipc.get("phase") != "READY_TO_INSTALL"
        or ipc.get("error_code") is not None
        or ipc.get("installed_version") != "2026.10.0"
    ):
        raise Stop("ipc_not_ready_to_install")
    media = safe_compatible_media(transaction)
    return {
        "transaction_phase": transaction["phase"],
        "transaction_sha256": transaction_sha,
        "sources": sources,
        "service": host,
        "services_owner": services,
        "broker_owner": broker_owner,
        "containers": containers,
        "ipc": ipc,
        "compatible_media": media,
    }


def wait_runtime_baseline(
    plan,
    *,
    target_sources,
    timeout_seconds=120,
):
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
    ):
        raise Stop("runtime_readiness_timeout_invalid")
    transient_prefixes = (
        "container_cardinality_invalid:",
        "container_not_ready:",
        "manager_container_cardinality_invalid",
        "ipc_status_unavailable:",
        "ipc_not_ready_to_install",
        "services_owner_not_active",
    )
    deadline = time.monotonic() + timeout_seconds
    last_reason = "runtime_not_ready"
    while time.monotonic() < deadline:
        try:
            return baseline(plan, target_sources=target_sources)
        except Stop as error:
            reason = str(error)
            if not reason.startswith(transient_prefixes):
                raise
            last_reason = reason
            time.sleep(2)
    raise Stop("runtime_readiness_timeout:" + last_reason[:180])


def rollback(plan, backup_dir):
    result = {
        "attempted": True,
        "status": "STOP",
        "errors": [],
        "services_owner_restart": False,
        "host_daemon_restart": False,
    }
    try:
        run(["systemctl", "stop", SERVICES_UNIT], check=False, timeout=150)
        wait_unit(SERVICES_UNIT, "inactive", 90)
        run(["systemctl", "stop", HOST_UNIT], check=False, timeout=90)
        wait_unit(HOST_UNIT, "inactive", 60)
        for item in plan["source_files"]:
            if not item.get("activate", False):
                continue
            backup = Path(backup_dir) / item["stage_name"]
            if backup.is_symlink() or not backup.is_file():
                raise Stop("rollback_backup_missing:" + item["repo_path"])
            atomic_install(backup, item["remote_path"])
        verify_source_set(plan, target=False)
        run(["systemctl", "start", HOST_UNIT], timeout=90)
        wait_unit(HOST_UNIT, "active", 60)
        result["host_daemon_restart"] = True
        run(["systemctl", "start", SERVICES_UNIT], timeout=180)
        wait_unit(SERVICES_UNIT, "active", 120)
        result["services_owner_restart"] = True
        result["post"] = wait_runtime_baseline(
            plan,
            target_sources=False,
            timeout_seconds=180,
        )
        result["status"] = "PASS"
    except Exception as error:
        result["errors"].append(type(error).__name__ + ":" + str(error)[:240])
    return result

def execute(plan, authorization, confirmation):
    if (
        plan.get("live_execution_authorized") is not True
        or plan.get("authorization_state")
        != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("kf152_r17_not_authorized")
    if authorization != plan["authorization_id"] or confirmation != plan["confirmation"]:
        raise Stop("kf152_r17_authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("r17_state_root_exists")
    stage_root = Path(plan["remote_staging_root"])
    if stage_root.is_symlink() or not stage_root.is_dir():
        raise Stop("r17_staging_root_invalid")
    for item in plan["source_files"]:
        if not item.get("activate", False):
            continue
        staged = stage_root / item["stage_name"]
        require_regular(staged, 0o600)
        if sha_file(staged) != item["target_sha256"]:
            raise Stop("staged_source_drift:" + item["repo_path"])

    pre = failed_prestate(plan)
    backup_dir = stage_root / ".preclaim-backup"
    if backup_dir.exists() or backup_dir.is_symlink():
        raise Stop("r17_backup_residue")
    backup_dir.mkdir(mode=0o700)
    os.chown(backup_dir, 0, 0)
    for item in plan["source_files"]:
        if not item.get("activate", False):
            continue
        source = Path(item["remote_path"])
        backup = backup_dir / item["stage_name"]
        shutil.copyfile(source, backup)
        os.chmod(backup, 0o600)
        os.chown(backup, 0, 0)
        if sha_file(backup) != item["predecessor_sha256"]:
            raise Stop("backup_source_drift:" + item["repo_path"])
    fsync_dir(backup_dir)

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    durable_json(state_root / "preflight.json", pre)
    durable_json(
        state_root / "authorization_claim.json",
        {
            "authorization_id": plan["authorization_id"],
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
        },
    )

    result = {
        "schema": "gh.n3w-t1-kf152-r17-dependency-safe-source-activation/1",
        "status": "STOP",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "host_source_mutation": False,
        "lifecycle_mutation_started": False,
        "host_daemon_restart": False,
        "services_owner_restart": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u5_transition": False,
        "u6_plus": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "rollback_required": False,
        "rollback": None,
        "board_access": False,
        "merge": False,
    }
    try:
        postclaim = failed_prestate(plan)
        if postclaim["transaction_sha256"] != pre["transaction_sha256"]:
            raise Stop("postclaim_transaction_drift")
        durable_json(state_root / "postclaim.json", postclaim)

        result["lifecycle_mutation_started"] = True
        run(["systemctl", "stop", SERVICES_UNIT], check=False, timeout=150)
        wait_unit(SERVICES_UNIT, "inactive", 90)
        run(["systemctl", "stop", HOST_UNIT], check=False, timeout=90)
        wait_unit(HOST_UNIT, "inactive", 60)

        _transaction, stopped_sha = verify_transaction(plan)
        if stopped_sha != pre["transaction_sha256"]:
            raise Stop("transaction_drift_after_stop")

        result["host_source_mutation"] = True
        for item in plan["source_files"]:
            if not item.get("activate", False):
                continue
            atomic_install(stage_root / item["stage_name"], item["remote_path"])
        verify_source_set(plan, target=True)

        run(["systemctl", "start", HOST_UNIT], timeout=90)
        wait_unit(HOST_UNIT, "active", 60)
        result["host_daemon_restart"] = True

        run(["systemctl", "start", SERVICES_UNIT], timeout=180)
        wait_unit(SERVICES_UNIT, "active", 120)
        result["services_owner_restart"] = True

        post = wait_runtime_baseline(plan, target_sources=True, timeout_seconds=180)
        if post["transaction_sha256"] != pre["transaction_sha256"]:
            raise Stop("u4_postactivation_transaction_drift")

        durable_json(state_root / "post.json", post)
        result.update(
            status="KF152_R17_RECOVERY_ACTIVATION_PASS",
            source_activated=True,
            services_recovered=True,
            u4_preserved=True,
            post=post,
        )
        durable_json(state_root / "result.json", result)
        shutil.rmtree(stage_root)
        return result
    except Exception as error:
        result["first_failed_operation"] = type(error).__name__ + ":" + str(error)[:240]
        result["rollback_required"] = bool(
            result["lifecycle_mutation_started"] or result["host_source_mutation"]
        )
        if result["rollback_required"]:
            result["rollback"] = rollback(plan, backup_dir)
        try:
            durable_json(state_root / "failure.json", result)
        except Exception:
            pass
        return result

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"status": "STOP", "reason": "arguments_missing"}))
        return 2
    mode = sys.argv[1]
    try:
        plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "KF152_DEPENDENCY_SAFE_SOURCE_ACTIVATION_R17_20261113_01"
        ):
            raise Stop("gate_id_invalid")
        if mode == "preflight":
            pre = failed_prestate(plan)
            result = {
                "schema": "gh.n3w-t1-kf152-r17-dependency-safe-source-activation-preflight/1",
                "status": "PASS",
                "read_only": True,
                "recovery_activation_eligible": True,
                "live_execution_authorized": (
                    plan.get("live_execution_authorized") is True
                ),
                "preflight": pre,
                "transaction_mutation": False,
                "usb_mutation": False,
                "u5_transition": False,
                "u6_plus": False,
            }
        elif mode == "execute":
            if len(sys.argv) != 5:
                raise Stop("execute_arguments_invalid")
            result = execute(plan, sys.argv[3], sys.argv[4])
        else:
            raise Stop("mode_invalid")
    except Exception as error:
        result = {
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:240],
        }
    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status")
        in {"PASS", "KF152_R17_RECOVERY_ACTIVATION_PASS"}
        else 2
    )


raise SystemExit(main())
"""


class Stop(RuntimeError):
    pass


def run(
    argv: list[str],
    *,
    timeout: int = 120,
    check: bool = True,
    binary: bool = False,
) -> subprocess.CompletedProcess[Any]:
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=not binary,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        raise Stop(
            f"local_command_failed:{Path(argv[0]).name}:{completed.returncode}"
        )
    return completed


def git_text(*args: str) -> str:
    return run(
        ["git", "-C", str(ROOT), *args],
        timeout=60,
    ).stdout.strip()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
    expected_state = (
        {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
        if execute
        else {
            "granted": False,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    )
    if document.get("authorization_state") != expected_state:
        raise Stop("manifest_authorization_state_invalid")
    if execute and document.get("live_execution_authorized") is not True:
        raise Stop("live_execution_not_authorized")
    if not execute and document.get("live_execution_authorized") is not False:
        raise Stop("preflight_manifest_must_be_ungranted")
    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    activated = []
    for item in document["source_files"]:
        relative = item["repo_path"]
        if git_text("rev-parse", "HEAD:" + relative) != item["target_blob"]:
            raise Stop("target_source_blob_drift:" + relative)
        if sha_file(ROOT / relative) != item["target_sha256"]:
            raise Stop("target_source_sha256_drift:" + relative)
        if item.get("activate") is True:
            activated.append(relative)
        elif item.get("activate") is not False:
            raise Stop("source_activation_flag_invalid:" + relative)
    if activated != ["tools/n3w_t1_core_updater_ha_prepare_host.py"]:
        raise Stop("source_activation_scope_invalid")
    return document


def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise Stop("evidence_root_invalid")
        os.chmod(root, 0o700)
    else:
        root.mkdir(parents=True, mode=0o700)
    metadata = root.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise Stop("evidence_root_metadata_invalid")
    return root


def write_private(path: Path, value: Any) -> None:
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
    with os.fdopen(descriptor, "wb", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def load_transport() -> type:
    spec = importlib.util.spec_from_file_location(
        "n3w_kf152_r17_source_activation_transport",
        SSH_TRANSPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport


def child_ssh_argv(transport: Any, command: str) -> tuple[str, ...]:
    transport.assert_master()
    return (
        "ssh",
        "-F",
        "/dev/null",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={transport.known_hosts}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "HashKnownHosts=no",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "IdentityAgent=none",
        "-o",
        "ControlMaster=no",
        "-o",
        "ControlPersist=no",
        "-o",
        f"ControlPath={transport.control_path}",
        "-o",
        "BatchMode=yes",
        "-o",
        "PubkeyAuthentication=no",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "KbdInteractiveAuthentication=no",
        "-o",
        "PreferredAuthentications=none",
        "-o",
        "ProxyCommand=/usr/bin/false",
        transport.target,
        command,
    )


def stream_file(source: Path, transport: Any, remote_path: str) -> None:
    if source.is_symlink() or not source.is_file():
        raise Stop("stream_source_invalid")
    command = shlex.join(
        ("python3", "-c", REMOTE_STREAM_WRITE, remote_path)
    )
    with source.open("rb") as stream:
        completed = subprocess.run(
            child_ssh_argv(transport, command),
            stdin=stream,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            check=False,
        )
    if completed.returncode != 0:
        raise Stop("ssh_stream_failed:" + str(completed.returncode))


def remote_mode(
    transport: Any,
    mode: str,
    plan: dict[str, Any],
    *,
    authorization: str = "",
    confirmation: str = "",
    timeout: int = 300,
) -> tuple[int, dict[str, Any], str]:
    payload = base64.b64encode(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    argv = ["python3", "-c", REMOTE_SCRIPT, mode, payload]
    if mode == "execute":
        argv.extend([authorization, confirmation])
    completed = transport.run_remote(
        argv,
        timeout=timeout,
        check=False,
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Stop("remote_result_json_invalid") from error
    if not isinstance(value, dict):
        raise Stop("remote_result_shape_invalid")
    return completed.returncode, value, completed.stderr


def execute(args: argparse.Namespace) -> dict[str, Any]:
    manifest = read_manifest(
        args.expected_package_commit,
        execute=args.execute,
    )
    plan = dict(manifest["expected_live_entry"])
    plan.update(
        {
            "gate_id": GATE_ID,
            "authorization_id": manifest["authorization_id"],
            "confirmation": manifest["confirmation"],
            "live_execution_authorized": manifest[
                "live_execution_authorized"
            ],
            "authorization_state": manifest["authorization_state"],
            "state_root": manifest["state_root"],
            "remote_staging_root": manifest["remote_staging_root"],
            "source_files": manifest["source_files"],
            "runtime_git_blob_sha1": manifest[
                "runtime_git_blob_sha1"
            ],
            "r16_terminal_state_root": manifest[
                "r16_terminal_state_root"
            ],
            "r16_terminal_stage_root": manifest[
                "r16_terminal_stage_root"
            ],
        }
    )
    evidence = prepare_evidence_root(args.evidence_root)
    result: dict[str, Any] = {
        "schema": "gh.n3w-t1-kf152-r17-dependency-safe-source-activation-local-result/1",
        "status": "STOP",
        "read_only_preflight": bool(args.preflight_only),
        "t1_access": False,
        "remote_staging": False,
        "live_execution_authorized": bool(args.execute),
        "authorization_claimed": False,
        "authorization_consumed": False,
        "host_source_mutation": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u5_transition": False,
        "u6_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    try:
        transport_type = load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        rc, pre, stderr = remote_mode(
            transport,
            "preflight",
            plan,
            timeout=240,
        )
        write_private(evidence / "preflight.json", pre)
        write_private(
            evidence / "preflight_transport.json",
            {"returncode": rc, "stderr": stderr},
        )
        if rc != 0 or pre.get("status") != "PASS":
            result["reason"] = pre.get("reason") or "preflight_stop"
            return result
        if args.preflight_only:
            result.update(pre)
            result["t1_access"] = True
            return result

        if (
            args.authorization_id != GATE_ID
            or args.confirm != CONFIRMATION
        ):
            raise Stop("authorization_or_confirmation_invalid")

        remote_root = manifest["remote_staging_root"]
        if (
            transport.run_remote(
                ["test", "-e", remote_root],
                check=False,
                timeout=30,
            ).returncode
            == 0
        ):
            raise Stop("remote_staging_already_exists")
        transport.run_remote(
            [
                "install",
                "-d",
                "-m",
                "0700",
                "-o",
                "root",
                "-g",
                "root",
                remote_root,
            ],
            timeout=60,
        )
        for item in manifest["source_files"]:
            if not item.get("activate", False):
                continue
            stream_file(
                ROOT / item["repo_path"],
                transport,
                remote_root + "/" + item["stage_name"],
            )
        result["remote_staging"] = True

        rc, remote, stderr = remote_mode(
            transport,
            "execute",
            plan,
            authorization=args.authorization_id,
            confirmation=args.confirm,
            timeout=600,
        )
        write_private(evidence / "result.json", remote)
        write_private(
            evidence / "remote_transport.json",
            {"returncode": rc, "stderr": stderr},
        )
        for key in (
            "authorization_claimed",
            "authorization_consumed",
            "host_source_mutation",
            "host_daemon_restart",
            "services_owner_restart",
            "transaction_mutation",
            "usb_mutation",
            "u5_transition",
            "u6_plus",
            "homeassistant_mutation",
            "manager_mutation",
            "broker_mutation",
            "rollback_required",
            "rollback",
            "board_access",
            "merge",
        ):
            if key in remote:
                result[key] = remote[key]
        result["remote_returncode"] = rc
        if (
            rc != 0
            or remote.get("status")
            != "KF152_R17_RECOVERY_ACTIVATION_PASS"
        ):
            result["reason"] = (
                remote.get("first_failed_operation")
                or remote.get("reason")
                or "remote_execute_stop"
            )
            return result
        result.update(remote)
        result["t1_access"] = True
        return result
    except Exception as error:
        result["reason"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        return result
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception:
                result["ssh_master_cleanup"] = False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-id", default="")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.execution_id != GATE_ID:
        print(
            json.dumps(
                {"status": "STOP", "reason": "execution_id_invalid"}
            )
        )
        return 2
    result = execute(args)
    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status")
        in {"PASS", "KF152_R17_RECOVERY_ACTIVATION_PASS"}
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
