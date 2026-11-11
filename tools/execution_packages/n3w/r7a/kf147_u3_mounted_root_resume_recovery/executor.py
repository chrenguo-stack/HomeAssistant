#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
SSH_TRANSPORT_PATH = REPO_ROOT / "tools/n3w_t1_ssh_transport.py"
TARGET_SOURCE_PATH = REPO_ROOT / "tools/n3w_t1_core_updater_ha_prepare_host.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U3_MOUNTED_ROOT_RESUME_TO_U4_R6_20261111_01"
)
CONFIRMATION = "EXECUTE KF147 U3 MOUNTED ROOT RESUME TO U4 R6: YES"
TARGET_RELATIVE = "tools/n3w_t1_core_updater_ha_prepare_host.py"

REMOTE_SCRIPT = r'''
import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
PREPARE_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-prepare.json")
SERVICE = "n3w-t1-ha-ota.service"
SOCKET_PATH = Path("/run/n3w-t1-ota/ha-ota.sock")
R5_ROOT = Path("/var/lib/n3w-t1-core-updater/kf147-u3-permission-recovery-r5-20261111-01")
TX_SCHEMA = "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
PREPARE_SCHEMA = "gh.n3w-t1-ha-usb-prepare-state/1"
U3 = "U3_TARGET_DOWNLOADING_VERIFYING"
U4 = "U4_READY_TO_INSTALL"


class Stop(RuntimeError):
    pass


def run(argv, *, timeout=60, check=True):
    result = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        raise Stop("command_failed:" + Path(argv[0]).name + ":" + str(result.returncode))
    return result


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def read_private_object(path, schema=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("state_file_invalid:" + path.name)
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise Stop("state_file_metadata_invalid:" + path.name)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("state_json_invalid:" + path.name) from error
    if not isinstance(doc, dict) or (schema is not None and doc.get("schema") != schema):
        raise Stop("state_schema_invalid:" + path.name)
    return doc


def fsync_dir(path):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_json(path, value):
    path = Path(path)
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "wb", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_dir(path.parent)


def parse_properties(text):
    result = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def systemd_state():
    return parse_properties(
        run(
            [
                "systemctl",
                "show",
                SERVICE,
                "--property=ActiveState",
                "--property=SubState",
                "--property=MainPID",
                "--property=NRestarts",
                "--property=Result",
                "--property=ExecMainStartTimestamp",
            ],
            timeout=30,
        ).stdout
    )


def wait_service_active():
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        state = systemd_state()
        if (
            state.get("ActiveState") == "active"
            and state.get("SubState") == "running"
            and SOCKET_PATH.exists()
        ):
            return state
        time.sleep(1.0)
    raise Stop("ha_ota_service_not_active")


def lsblk_doc():
    raw = run(
        [
            "lsblk",
            "--json",
            "--bytes",
            "--paths",
            "--output",
            "NAME,PATH,TYPE,RM,RO,SIZE,MODEL,SERIAL,WWN,TRAN,MOUNTPOINTS,PKNAME",
        ],
        timeout=45,
    ).stdout
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as error:
        raise Stop("lsblk_json_invalid") from error
    if not isinstance(doc, dict) or not isinstance(doc.get("blockdevices"), list):
        raise Stop("lsblk_shape_invalid")
    return doc


def flatten(nodes):
    result = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        result.append(node)
        children = node.get("children")
        if isinstance(children, list):
            result.extend(flatten(children))
    return result


def stable_fingerprint(node):
    serial = node.get("serial")
    serial = serial.strip() if isinstance(serial, str) and serial.strip() else None
    wwn = node.get("wwn")
    wwn = wwn.strip() if isinstance(wwn, str) and wwn.strip() else None
    if serial is None and wwn is None:
        raise Stop("usb_stable_identity_unavailable")
    identity = {
        "serial": serial,
        "wwn": wwn,
        "model": str(node.get("model") or "").strip(),
        "size": node.get("size"),
        "transport": str(node.get("tran") or "").strip().lower(),
    }
    return sha256_bytes(canonical(identity))


def bound_partition(tx, live):
    uuid = tx.get("usb_filesystem_uuid")
    if not isinstance(uuid, str) or not uuid:
        raise Stop("usb_filesystem_uuid_missing")
    resolved = run(["blkid", "-U", uuid.lower()], timeout=30, check=False)
    if resolved.returncode != 0:
        raise Stop("bound_partition_unavailable")
    partition = resolved.stdout.strip()
    if not partition.startswith("/dev/"):
        raise Stop("bound_partition_invalid")
    parent = run(
        ["lsblk", "--noheadings", "--paths", "--output", "PKNAME", partition],
        timeout=30,
    ).stdout.strip()
    if not parent.startswith("/dev/"):
        raise Stop("bound_parent_invalid")
    doc = lsblk_doc()
    disks = [
        item
        for item in doc["blockdevices"]
        if isinstance(item, dict)
        and item.get("type") == "disk"
        and item.get("path") == parent
    ]
    if len(disks) != 1:
        raise Stop("bound_parent_ambiguous")
    disk = disks[0]
    if (
        str(disk.get("tran") or "").strip().lower() != "usb"
        or disk.get("rm") not in (True, 1, "1")
        or disk.get("ro") in (True, 1, "1")
        or str(disk.get("model") or "").strip() != live["usb_candidate_model"]
        or int(disk.get("size") or 0) != live["usb_candidate_capacity_bytes"]
        or stable_fingerprint(disk) != live["usb_candidate_public_fingerprint"]
    ):
        raise Stop("bound_usb_identity_mismatch")
    partition_nodes = [
        item for item in flatten([disk]) if item.get("path") == partition
    ]
    if len(partition_nodes) != 1:
        raise Stop("bound_partition_inventory_invalid")
    mounted = [
        item
        for item in (partition_nodes[0].get("mountpoints") or [])
        if isinstance(item, str) and item.startswith("/")
    ]
    return {
        "partition": partition,
        "parent": parent,
        "uuid": uuid.lower(),
        "current_partition_mountpoints": mounted,
    }


def mount_view(target):
    result = run(
        ["findmnt", "--noheadings", "--output", "SOURCE,TARGET", "--mountpoint", target],
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        return None
    fields = result.stdout.strip().split()
    if len(fields) < 2:
        raise Stop("runtime_mount_view_invalid")
    return {"source": fields[0], "target": fields[-1]}


def directory_view(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise Stop("required_directory_invalid:" + str(path))
    metadata = path.stat()
    return {
        "path": str(path),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "mode": stat.S_IMODE(metadata.st_mode),
    }


def container_view(image):
    ids = [
        line.strip()
        for line in run(
            ["docker", "ps", "-a", "--filter", "ancestor=" + image, "--format", "{{.ID}}"],
            timeout=45,
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(ids) != 1:
        raise Stop("container_cardinality_invalid:" + image)
    docs = json.loads(run(["docker", "inspect", ids[0]], timeout=45).stdout)
    if not isinstance(docs, list) or len(docs) != 1:
        raise Stop("container_inspect_invalid:" + image)
    item = docs[0]
    state = item.get("State") if isinstance(item.get("State"), dict) else {}
    return {
        "container_id": item.get("Id"),
        "runtime_image_id": item.get("Image"),
        "status": state.get("Status"),
        "restart_count": item.get("RestartCount"),
    }


def ipc_status(manager_id):
    probe = r"""import json,socket
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(5)
s.connect("/run/n3w/t1-ota/ha-ota.sock")
s.sendall(json.dumps({"schema":"gh.n3w-t1-ha-ota-ipc-request/1","operation":"status"},separators=(",",":")).encode()+b"\n")
s.shutdown(socket.SHUT_WR)
data=bytearray()
while len(data) <= 8192:
    block=s.recv(1024)
    if not block: break
    data.extend(block)
    if b"\n" in data: break
print(bytes(data).split(b"\n",1)[0].decode())"""
    raw = run(
        ["docker", "exec", "-u", "999:999", manager_id, "python3", "-c", probe],
        timeout=30,
    ).stdout.strip()
    try:
        response = json.loads(raw)
    except json.JSONDecodeError as error:
        raise Stop("ipc_status_invalid") from error
    if not isinstance(response, dict) or response.get("accepted") is not True:
        raise Stop("ipc_status_rejected")
    return response


def predecessor_view():
    claim = read_private_object(R5_ROOT / "authorization_claim.json")
    repair = read_private_object(R5_ROOT / "permission_repair.json")
    failure = read_private_object(
        R5_ROOT / "failure.json",
        "gh.n3w-t1-kf147-u3-permission-recovery/1",
    )
    if (
        claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or repair.get("before_mode") != "0770"
        or repair.get("after_mode") != "0700"
        or failure.get("status") != "STOP"
        or failure.get("authorization_claimed") is not True
        or failure.get("authorization_consumed") is not True
        or failure.get("replay_permitted") is not False
        or failure.get("usb_update_dir_permission_repaired") is not True
        or failure.get("service_restarted") is not True
        or failure.get("u4_ready") is not False
        or failure.get("first_failed_operation") != "Stop:u3_permission_recovery_timeout"
    ):
        raise Stop("r5_terminal_failure_not_confirmed")
    return {
        "authorization_claim_sha256": sha_file(R5_ROOT / "authorization_claim.json"),
        "permission_repair_sha256": sha_file(R5_ROOT / "permission_repair.json"),
        "failure_sha256": sha_file(R5_ROOT / "failure.json"),
    }


def validate_preflight(plan):
    live = plan["live"]
    tx = read_private_object(TX_PATH, TX_SCHEMA)
    prep = read_private_object(PREPARE_PATH, PREPARE_SCHEMA)
    if (
        tx.get("phase") != U3
        or tx.get("status") != "ACTIVE"
        or tx.get("transaction_id_sha256") != live["transaction_id_sha256"]
        or tx.get("target_manifest_identity", {}).get("release_identity")
        != live["release_identity"]
        or tx.get("target_archive_sha256") != live["target_archive_sha256"]
        or tx.get("target_archive_size") != live["target_archive_size_bytes"]
        or tx.get("usb_device_identity_public_fingerprint")
        != live["usb_candidate_public_fingerprint"]
        or tx.get("usb_filesystem_uuid") != live["usb_filesystem_uuid"]
        or tx.get("usb_capacity_verified") is not True
        or tx.get("target_artifact_verified") is not False
    ):
        raise Stop("u3_transaction_binding_drift")
    if (
        prep.get("transaction_id_sha256") != live["transaction_id_sha256"]
        or prep.get("release_identity") != live["release_identity"]
        or prep.get("confirmation_consumed") is not True
        or prep.get("confirmation_required") is not False
    ):
        raise Stop("u3_prepare_binding_drift")

    predecessor = predecessor_view()
    media = bound_partition(tx, live)
    mount_target = "/run/n3w-t1-ota/media/" + live["transaction_id_sha256"][:16]
    if media["current_partition_mountpoints"] != [mount_target]:
        raise Stop("bound_partition_mount_drift")
    mounted = mount_view(mount_target)
    if (
        mounted is None
        or mounted["source"] != media["partition"]
        or mounted["target"] != mount_target
    ):
        raise Stop("bound_partition_exact_mount_missing")

    mount_root = directory_view(mount_target)
    update_dir = directory_view(Path(mount_target) / "n3w-update")
    transaction_dir = directory_view(Path(mount_target) / "n3w-update" / "transaction")
    if (
        mount_root["uid"] != 0
        or mount_root["gid"] != 0
        or mount_root["mode"] != 0o755
    ):
        raise Stop("mounted_filesystem_root_drift")
    if (
        update_dir["uid"] != 0
        or update_dir["gid"] != 999
        or update_dir["mode"] != 0o700
    ):
        raise Stop("usb_update_directory_precondition_drift")
    if (
        transaction_dir["uid"] != 0
        or transaction_dir["gid"] != 999
        or transaction_dir["mode"] != 0o700
    ):
        raise Stop("usb_transaction_directory_precondition_drift")
    target_dir = Path(mount_target) / "n3w-update" / "target"
    if target_dir.exists() or target_dir.is_symlink():
        raise Stop("usb_target_directory_unexpectedly_present")

    require_regular(plan["remote_target"], 0o644)
    source_sha256 = sha_file(plan["remote_target"])
    if source_sha256 != plan["predecessor_source_sha256"]:
        raise Stop("installed_prepare_host_source_drift")

    service = systemd_state()
    if service.get("ActiveState") != "active" or service.get("SubState") != "running":
        raise Stop("ha_ota_service_not_running")
    containers = {
        "manager": container_view(live["manager_image"]),
        "homeassistant": container_view(live["homeassistant_image"]),
        "broker": container_view(live["broker_image"]),
    }
    for key, expected in plan["containers"].items():
        observed = containers[key]
        if (
            observed["container_id"] != expected["container_id"]
            or observed["runtime_image_id"] != expected["runtime_image_id"]
            or observed["restart_count"] != expected["restart_count"]
            or observed["status"] != "running"
        ):
            raise Stop("container_continuity_drift:" + key)
    ipc = ipc_status(containers["manager"]["container_id"])
    if (
        ipc.get("phase") != "ERROR"
        or ipc.get("error_code") != "usb_runtime_directory_metadata_invalid"
    ):
        raise Stop("r5_runtime_error_state_drift")
    return {
        "transaction_sha256": sha_file(TX_PATH),
        "prepare_sha256": sha_file(PREPARE_PATH),
        "phase": tx["phase"],
        "media": media,
        "mount_target": mount_target,
        "mount": mounted,
        "mount_root": mount_root,
        "update_dir": update_dir,
        "transaction_dir": transaction_dir,
        "target_dir_present": False,
        "installed_prepare_host_sha256": source_sha256,
        "service": service,
        "containers": containers,
        "ipc": ipc,
        "r5": predecessor,
    }


def atomic_install(source, target):
    source = Path(source)
    target = Path(target)
    require_regular(source, 0o600)
    if target.is_symlink() or not target.is_file():
        raise Stop("target_source_invalid")
    temporary = target.parent / (".n3w-kf147-r6." + target.name + "." + str(os.getpid()))
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        with source.open("rb") as input_stream, os.fdopen(descriptor, "wb", closefd=False) as output:
            shutil.copyfileobj(input_stream, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        os.fchmod(descriptor, 0o644)
        os.fchown(descriptor, 0, 0)
    finally:
        os.close(descriptor)
    os.replace(temporary, target)
    fsync_dir(target.parent)


def target_view(plan):
    live = plan["live"]
    tx = read_private_object(TX_PATH, TX_SCHEMA)
    if (
        tx.get("phase") != U4
        or tx.get("status") != "ACTIVE"
        or tx.get("target_artifact_verified") is not True
        or tx.get("usb_capacity_verified") is not True
        or tx.get("transaction_id_sha256") != live["transaction_id_sha256"]
        or tx.get("usb_filesystem_uuid") != live["usb_filesystem_uuid"]
    ):
        raise Stop("u4_transaction_invalid")
    partition = run(
        ["blkid", "-U", live["usb_filesystem_uuid"]],
        timeout=30,
    ).stdout.strip()
    if not partition.startswith("/dev/"):
        raise Stop("u4_partition_invalid")
    expected_mount = "/run/n3w-t1-ota/media/" + live["transaction_id_sha256"][:16]
    target_mount = run(
        ["findmnt", "--noheadings", "--output", "TARGET", "--source", partition],
        timeout=30,
    ).stdout.strip()
    if target_mount != expected_mount:
        raise Stop("u4_mount_binding_invalid")
    target = Path(expected_mount) / "n3w-update" / "target" / "homeassistant-arm64.tar.gz"
    if target.is_symlink() or not target.is_file():
        raise Stop("u4_target_archive_missing")
    if target.stat().st_size != live["target_archive_size_bytes"]:
        raise Stop("u4_target_size_mismatch")
    if sha_file(target) != live["target_archive_sha256"]:
        raise Stop("u4_target_sha_mismatch")
    return {
        "phase": tx["phase"],
        "transaction_sha256": sha_file(TX_PATH),
        "partition": partition,
        "mount_target": expected_mount,
        "target_path": str(target),
        "target_size_bytes": target.stat().st_size,
        "target_sha256": live["target_archive_sha256"],
    }


def rollback_pre_activation(plan, backup):
    result = {"attempted": True, "status": "FAIL"}
    try:
        atomic_install(backup, plan["remote_target"])
        run(["systemctl", "restart", SERVICE], timeout=60)
        wait_service_active()
        if sha_file(plan["remote_target"]) != plan["predecessor_source_sha256"]:
            raise Stop("rollback_source_sha256_mismatch")
        result["status"] = "PASS"
    except Exception as error:
        result["error"] = type(error).__name__ + ":" + str(error)[:240]
    return result


def execute(plan, authorization, confirmation, mode):
    pre = validate_preflight(plan)
    if mode == "preflight":
        return {
            "schema": "gh.n3w-t1-kf147-u3-mounted-root-resume-recovery/1",
            "status": "PASS",
            "read_only": True,
            "recovery_eligible": True,
            "live_execution_authorized": plan.get("live_execution_authorized") is True,
            "preflight": pre,
        }
    if (
        plan.get("live_execution_authorized") is not True
        or plan.get("authorization_state") != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("recovery_live_execution_not_authorized")
    if authorization != plan["authorization_id"] or confirmation != plan["confirmation"]:
        raise Stop("recovery_authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("recovery_authorization_state_root_exists")
    stage_root = Path(plan["remote_staging_root"])
    staged = stage_root / "n3w_t1_core_updater_ha_prepare_host.py"
    require_regular(staged, 0o600)
    if sha_file(staged) != plan["target_source_sha256"]:
        raise Stop("staged_prepare_host_sha256_mismatch")
    backup = stage_root / ".preclaim-backup.py"
    if backup.exists() or backup.is_symlink():
        raise Stop("preclaim_backup_residue")
    shutil.copyfile(plan["remote_target"], backup)
    os.chmod(backup, 0o600)
    os.chown(backup, 0, 0)
    with backup.open("rb") as stream:
        os.fsync(stream.fileno())
    fsync_dir(stage_root)
    if sha_file(backup) != plan["predecessor_source_sha256"]:
        raise Stop("preclaim_backup_sha256_mismatch")

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
            "transaction_id_sha256": plan["live"]["transaction_id_sha256"],
            "usb_filesystem_uuid": plan["live"]["usb_filesystem_uuid"],
        },
    )
    result = {
        "schema": "gh.n3w-t1-kf147-u3-mounted-root-resume-recovery/1",
        "status": "STOP",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "host_source_mutation": False,
        "source_activated": False,
        "service_restarted": False,
        "u4_ready": False,
        "u5_plus": False,
        "usb_mutation": False,
        "usb_target_write": False,
        "usb_reformat": False,
        "usb_repartition": False,
        "destructive_confirmation_replay": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "rollback": None,
        "first_failed_operation": None,
    }
    try:
        postclaim = validate_preflight(plan)
        durable_json(state_root / "postclaim.json", postclaim)
        atomic_install(staged, plan["remote_target"])
        result["host_source_mutation"] = True
        if sha_file(plan["remote_target"]) != plan["target_source_sha256"]:
            raise Stop("installed_prepare_host_sha256_mismatch")
        run(["systemctl", "restart", SERVICE], timeout=60)
        result["service_restarted"] = True
        service = wait_service_active()
        result["source_activated"] = True
        result["usb_mutation"] = True
        result["usb_target_write"] = True
        durable_json(
            state_root / "activation.json",
            {
                "installed_prepare_host_sha256": plan["target_source_sha256"],
                "service": service,
                "source_activated": True,
            },
        )

        deadline = time.monotonic() + plan["poll_timeout_seconds"]
        last = None
        while time.monotonic() < deadline:
            tx = read_private_object(TX_PATH, TX_SCHEMA)
            service = systemd_state()
            target_dir = Path(pre["mount_target"]) / "n3w-update" / "target"
            target_files = []
            if target_dir.is_dir() and not target_dir.is_symlink():
                try:
                    for item in target_dir.iterdir():
                        try:
                            if item.is_file() and not item.is_symlink():
                                target_files.append(
                                    {"name": item.name, "size": item.stat().st_size}
                                )
                        except OSError:
                            continue
                    target_files.sort(key=lambda item: item["name"])
                except OSError:
                    target_files = []
            ipc = ipc_status(pre["containers"]["manager"]["container_id"])
            last = {
                "transaction_phase": tx.get("phase"),
                "transaction_status": tx.get("status"),
                "service": service,
                "target_files": target_files,
                "ipc": ipc,
            }
            if tx.get("phase") == U4:
                post = target_view(plan)
                containers = {
                    "manager": container_view(plan["live"]["manager_image"]),
                    "homeassistant": container_view(plan["live"]["homeassistant_image"]),
                    "broker": container_view(plan["live"]["broker_image"]),
                }
                for key, expected in plan["containers"].items():
                    observed = containers[key]
                    if (
                        observed["container_id"] != expected["container_id"]
                        or observed["runtime_image_id"] != expected["runtime_image_id"]
                        or observed["restart_count"] != expected["restart_count"]
                        or observed["status"] != "running"
                    ):
                        raise Stop("post_recovery_container_drift:" + key)
                post["containers"] = containers
                post["installed_prepare_host_sha256"] = sha_file(plan["remote_target"])
                if post["installed_prepare_host_sha256"] != plan["target_source_sha256"]:
                    raise Stop("u4_prepare_host_source_drift")
                durable_json(state_root / "post.json", post)
                result.update(
                    {
                        "status": "PASS",
                        "u4_ready": True,
                        "target_artifact_verified": True,
                        "containers_preserved": True,
                        "post": post,
                    }
                )
                durable_json(state_root / "result.json", result)
                shutil.rmtree(stage_root)
                return result
            if tx.get("phase") != U3 or tx.get("status") != "ACTIVE":
                raise Stop("unexpected_recovery_transaction_state")
            if service.get("ActiveState") != "active":
                raise Stop("ha_ota_service_not_active_after_restart")
            if ipc.get("phase") == "ERROR":
                raise Stop("u3_resume_error:" + str(ipc.get("error_code")))
            if sha_file(plan["remote_target"]) != plan["target_source_sha256"]:
                raise Stop("activated_prepare_host_source_drift")
            time.sleep(2)
        result["last_observed"] = last
        raise Stop("u3_mounted_root_resume_timeout")
    except Exception as error:
        result["first_failed_operation"] = type(error).__name__ + ":" + str(error)[:240]
        if not result["source_activated"]:
            result["rollback"] = rollback_pre_activation(plan, backup)
        durable_json(state_root / "failure.json", result)
        return result


def main():
    if len(sys.argv) != 5:
        print(json.dumps({"status": "STOP", "reason": "arguments_invalid"}))
        return 2
    try:
        plan = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
            "U3_MOUNTED_ROOT_RESUME_TO_U4_R6_20261111_01"
        ):
            raise Stop("gate_id_invalid")
        result = execute(plan, sys.argv[2], sys.argv[3], sys.argv[4])
    except Exception as error:
        result = {"status": "STOP", "reason": type(error).__name__ + ":" + str(error)[:240]}
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


raise SystemExit(main())
'''


class Stop(RuntimeError):
    pass


def run(argv: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
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
        raise Stop(f"local_command_failed:{Path(argv[0]).name}:{completed.returncode}")
    return completed


def git_text(*args: str) -> str:
    return run(["git", "-C", str(REPO_ROOT), *args], timeout=30).stdout.strip()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("manifest_invalid") from error
    if not isinstance(value, dict):
        raise Stop("manifest_invalid")
    return value


def validate_local(expected_commit: str, *, require_live: bool) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    manifest = read_manifest()
    if (
        manifest.get("schema")
        != "gh.n3w-t1-kf147-u3-mounted-root-resume-recovery-manifest/1"
        or manifest.get("gate_id") != GATE_ID
        or manifest.get("authorization_id") != GATE_ID
        or manifest.get("confirmation") != CONFIRMATION
    ):
        raise Stop("manifest_contract_invalid")
    authority = manifest.get("package_source_authority")
    expected_paths = {
        "tools/execution_packages/n3w/r7a/kf147_u3_mounted_root_resume_recovery/executor.py",
        TARGET_RELATIVE,
        "tools/n3w_t1_ssh_transport.py",
    }
    if not isinstance(authority, dict) or set(authority) != expected_paths:
        raise Stop("package_source_authority_invalid")
    for relative, blob in authority.items():
        if (
            not isinstance(blob, str)
            or re.fullmatch(r"[0-9a-f]{40}", blob) is None
            or git_text("rev-parse", f"HEAD:{relative}") != blob
        ):
            raise Stop("package_source_authority_drift:" + relative)
    predecessor = manifest.get("predecessor_source_authority", {})
    predecessor_head = predecessor.get("source_head")
    predecessor_blob = predecessor.get("prepare_host_blob")
    if (
        re.fullmatch(r"[0-9a-f]{40}", str(predecessor_head)) is None
        or re.fullmatch(r"[0-9a-f]{40}", str(predecessor_blob)) is None
        or git_text("rev-parse", f"{predecessor_head}:{TARGET_RELATIVE}")
        != predecessor_blob
    ):
        raise Stop("predecessor_source_authority_drift")
    if sha_file(TARGET_SOURCE_PATH) != manifest.get("target_prepare_host_sha256"):
        raise Stop("target_prepare_host_sha256_drift")
    if require_live:
        if (
            manifest.get("live_execution_authorized") is not True
            or manifest.get("authorization_state")
            != {
                "granted": True,
                "claimed": False,
                "consumed": False,
                "replay_permitted": False,
            }
        ):
            raise Stop("live_execution_not_authorized")
    return manifest


def load_transport() -> type:
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_ssh_transport_kf147_u3_mounted_root_resume",
        SSH_TRANSPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport


def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise Stop("evidence_root_invalid")
        os.chmod(root, 0o700)
    else:
        root.mkdir(parents=True, mode=0o700)
    metadata = root.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise Stop("evidence_root_metadata_invalid")
    return root


def write_private(path: Path, value: Any) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "wb", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def build_plan(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate_id": GATE_ID,
        "authorization_id": manifest["authorization_id"],
        "confirmation": manifest["confirmation"],
        "live_execution_authorized": manifest["live_execution_authorized"],
        "authorization_state": manifest["authorization_state"],
        "state_root": manifest["state_root"],
        "remote_staging_root": manifest["remote_staging_root"],
        "remote_target": manifest["remote_target"],
        "predecessor_source_sha256": manifest["predecessor_source_authority"]["prepare_host_sha256"],
        "target_source_sha256": manifest["target_prepare_host_sha256"],
        "poll_timeout_seconds": manifest["poll_timeout_seconds"],
        "live": manifest["expected_live_entry"],
        "containers": manifest["expected_containers"],
    }


def remote_call(
    transport: Any,
    plan: dict[str, Any],
    authorization: str,
    confirmation: str,
    mode: str,
) -> tuple[int, dict[str, Any]]:
    payload = base64.b64encode(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    completed = transport.run_remote(
        ["python3", "-c", REMOTE_SCRIPT, payload, authorization, confirmation, mode],
        timeout=plan["poll_timeout_seconds"] + 180,
        check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Stop("remote_result_json_invalid") from error
    if not isinstance(result, dict):
        raise Stop("remote_result_shape_invalid")
    return completed.returncode, result


def execute(args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "gh.n3w-t1-kf147-u3-mounted-root-resume-local-result/1",
        "status": "STOP",
        "gate_id": GATE_ID,
        "t1_access": False,
        "read_only_preflight": True,
        "remote_staging": False,
        "live_apply_invoked": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "usb_mutation": False,
        "usb_reformat": False,
        "usb_repartition": False,
        "destructive_confirmation_replay": False,
        "u5_plus": False,
        "board_access": False,
        "merge": False,
        "first_failed_operation": None,
    }
    transport = None
    try:
        manifest = validate_local(
            args.expected_package_commit,
            require_live=not args.preflight_only,
        )
        plan = build_plan(manifest)
        evidence_root = prepare_evidence_root(args.evidence_root)
        transport_type = load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        returncode, remote = remote_call(transport, plan, "", "", "preflight")
        write_private(evidence_root / "preflight.json", remote)
        if returncode != 0 or remote.get("status") != "PASS":
            result["first_failed_operation"] = remote.get("reason") or "preflight_stop"
            result["remote_returncode"] = returncode
            return result
        if args.preflight_only:
            result.update(remote)
            result["t1_access"] = True
            return result

        if args.authorization_id != GATE_ID or args.confirm != CONFIRMATION:
            raise Stop("authorization_or_confirmation_invalid")
        remote_root = manifest["remote_staging_root"]
        if transport.run_remote(["test", "-e", remote_root], timeout=30, check=False).returncode == 0:
            raise Stop("remote_staging_already_exists")
        transport.run_remote(
            ["install", "-d", "-m", "0700", "-o", "root", "-g", "root", remote_root],
            timeout=60,
        )
        remote_source = remote_root + "/n3w_t1_core_updater_ha_prepare_host.py"
        transport.scp_to(TARGET_SOURCE_PATH, remote_source, timeout=180)
        transport.run_remote(
            ["chmod", "0600", remote_source],
            timeout=30,
        )
        result["remote_staging"] = True
        result["live_apply_invoked"] = True
        returncode, remote = remote_call(
            transport,
            plan,
            args.authorization_id,
            args.confirm,
            "execute",
        )
        write_private(evidence_root / "result.json", remote)
        result["remote_returncode"] = returncode
        result["authorization_claimed"] = bool(remote.get("authorization_claimed"))
        result["authorization_consumed"] = bool(remote.get("authorization_consumed"))
        result["host_source_mutation"] = bool(remote.get("host_source_mutation"))
        result["source_activated"] = bool(remote.get("source_activated"))
        result["service_restarted"] = bool(remote.get("service_restarted"))
        result["usb_mutation"] = bool(remote.get("usb_mutation"))
        result["usb_target_write"] = bool(remote.get("usb_target_write"))
        if returncode != 0 or remote.get("status") != "PASS":
            result["first_failed_operation"] = (
                remote.get("first_failed_operation")
                or remote.get("reason")
                or "remote_recovery_stop"
            )
            result["rollback"] = remote.get("rollback")
            return result
        result.update(remote)
        result["t1_access"] = True
        return result
    except Exception as error:
        result["first_failed_operation"] = type(error).__name__ + ":" + str(error)[:240]
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
    if re.fullmatch(r"[A-Za-z0-9._-]{1,160}", args.execution_id) is None:
        print(json.dumps({"status": "STOP", "reason": "execution_id_invalid"}))
        return 2
    if args.execute and (
        args.authorization_id != GATE_ID or args.confirm != CONFIRMATION
    ):
        print(json.dumps({"status": "STOP", "reason": "authorization_invalid"}))
        return 2
    result = execute(args)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
