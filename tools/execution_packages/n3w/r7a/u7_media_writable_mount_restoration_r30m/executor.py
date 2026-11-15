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

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
SSH_TRANSPORT_PATH = ROOT / "tools" / "n3w_t1_ssh_transport.py"
GATE_ID = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U7_MEDIA_WRITABLE_MOUNT_RESTORATION_R30M_20261115_01"
CONFIRMATION = "EXECUTE U7 R30M WRITABLE MOUNT RESTORATION: YES"

class Stop(RuntimeError):
    pass

REMOTE_SCRIPT = r'''
import base64
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path


class Stop(RuntimeError):
    pass


TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
SERVICE = "n3w-t1-ha-ota.service"
HOST_UNIT = "n3w-t1-ha-ota.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
R26 = Path("/var/lib/n3w-t1-core-updater/u6-r26-predecessor-recovery-20261114-01")
R29 = Path("/var/lib/n3w-t1-core-updater/u7-r29-source-activation-20261114-01")
R30S = Path("/var/lib/n3w-t1-core-updater/u7-r30s-prepare-host-source-activation-20261115-01")


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
        raise Stop("command_failed:" + Path(argv[0]).name + ":" + str(completed.returncode))
    return completed


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()



def _boolish(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


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


def _stable_fingerprint(node):
    serial = (
        node["serial"].strip()
        if isinstance(node.get("serial"), str) and node["serial"].strip()
        else None
    )
    wwn = (
        node["wwn"].strip()
        if isinstance(node.get("wwn"), str) and node["wwn"].strip()
        else None
    )
    if serial is None and wwn is None:
        raise Stop("usb_stable_identity_unavailable")
    identity = {
        "serial": serial,
        "wwn": wwn,
        "model": str(node.get("model") or "").strip(),
        "size": node.get("size"),
        "transport": str(node.get("tran") or "").strip().lower(),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _lsblk_tree():
    completed = run(
        [
            "lsblk",
            "--json",
            "--bytes",
            "--paths",
            "--tree",
            "--output",
            "NAME,PATH,TYPE,RM,RO,SIZE,MODEL,SERIAL,WWN,TRAN,MOUNTPOINTS,MAJ:MIN",
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


def _mount_namespace(pid):
    path = "/proc/self/ns/mnt" if pid is None else "/proc/" + str(pid) + "/ns/mnt"
    try:
        value = os.readlink(path)
    except OSError as error:
        raise Stop("mount_namespace_unavailable") from error
    if not value:
        raise Stop("mount_namespace_unavailable")
    return value


def _single_output(argv, reason, *, timeout=30):
    completed = run(argv, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise Stop(reason)
    value = completed.stdout.strip()
    if not value:
        raise Stop(reason)
    return value


def verify_bound_media(
    plan,
    transaction,
    service,
    expected_mode,
    require_service_namespace=True,
):
    expected_uuid = plan["usb_filesystem_uuid"].lower()
    expected_fingerprint = plan["usb_public_fingerprint"]
    if transaction.get("usb_device_identity_public_fingerprint") != expected_fingerprint:
        raise Stop("u6_usb_fingerprint_drift")
    if transaction.get("usb_filesystem_uuid") != expected_uuid:
        raise Stop("u6_usb_filesystem_uuid_drift")

    uuid_matches = [
        line.strip()
        for line in _single_output(
            ["blkid", "-t", "UUID=" + expected_uuid, "-o", "device"],
            "usb_filesystem_uuid_unavailable",
        ).splitlines()
        if line.strip()
    ]
    if len(uuid_matches) != 1:
        raise Stop("usb_filesystem_uuid_cardinality_invalid")
    partition = uuid_matches[0]
    if not partition.startswith("/dev/"):
        raise Stop("usb_bound_partition_invalid")

    parent = _single_output(
        ["lsblk", "--noheadings", "--paths", "--output", "PKNAME", partition],
        "usb_bound_parent_invalid",
    )
    if not parent.startswith("/dev/"):
        raise Stop("usb_bound_parent_invalid")

    disks = [
        item
        for item in _lsblk_tree()
        if item.get("type") == "disk" and item.get("path") == parent
    ]
    if len(disks) != 1:
        raise Stop("usb_bound_parent_ambiguous")
    disk = disks[0]
    if (
        str(disk.get("tran") or "").strip().lower() != "usb"
        or not _boolish(disk.get("rm"))
        or _boolish(disk.get("ro"))
    ):
        raise Stop("usb_bound_device_properties_invalid")
    observed_fingerprint = _stable_fingerprint(disk)
    if observed_fingerprint != expected_fingerprint:
        raise Stop("usb_public_fingerprint_mismatch")

    root_major_minor = _single_output(
        ["findmnt", "--noheadings", "--output", "MAJ:MIN", "/"],
        "usb_root_device_unresolved",
    )
    major_minors = {
        str(item.get("maj:min") or "").strip()
        for item in _flatten_blocks([disk])
    }
    if root_major_minor in major_minors:
        raise Stop("usb_bound_device_is_root")

    filesystem_type = _single_output(
        ["blkid", "-s", "TYPE", "-o", "value", partition],
        "usb_filesystem_type_unavailable",
    )
    filesystem_label = _single_output(
        ["blkid", "-s", "LABEL", "-o", "value", partition],
        "usb_filesystem_label_unavailable",
    )
    if (
        filesystem_type != plan["usb_filesystem_type"]
        or filesystem_label != plan["usb_filesystem_label"]
    ):
        raise Stop("usb_bound_filesystem_contract_invalid")

    expected_target = plan["mount_target"]
    source_targets = [
        line.strip()
        for line in _single_output(
            ["findmnt", "--noheadings", "--output", "TARGET", "--source", partition],
            "usb_mount_missing",
        ).splitlines()
        if line.strip()
    ]
    if len(source_targets) != 1:
        raise Stop("usb_mount_cardinality_invalid")
    if source_targets[0] != expected_target:
        raise Stop("usb_bound_partition_mounted_elsewhere")

    mount_source = _single_output(
        ["findmnt", "--noheadings", "--mountpoint", expected_target, "--output", "SOURCE"],
        "usb_mount_missing",
    )
    mount_target = _single_output(
        ["findmnt", "--noheadings", "--mountpoint", expected_target, "--output", "TARGET"],
        "usb_mount_missing",
    )
    mount_type = _single_output(
        ["findmnt", "--noheadings", "--mountpoint", expected_target, "--output", "FSTYPE"],
        "usb_mount_missing",
    )
    mount_options_raw = _single_output(
        ["findmnt", "--noheadings", "--mountpoint", expected_target, "--output", "OPTIONS"],
        "usb_mount_missing",
    )
    mount_major_minor = _single_output(
        ["findmnt", "--noheadings", "--mountpoint", expected_target, "--output", "MAJ:MIN"],
        "usb_mount_missing",
    )
    partition_major_minor = _single_output(
        ["lsblk", "--noheadings", "--output", "MAJ:MIN", partition],
        "usb_partition_major_minor_unavailable",
    )
    if mount_target != expected_target:
        raise Stop("usb_mount_target_drift")
    if mount_type != plan["usb_filesystem_type"]:
        raise Stop("usb_mount_filesystem_drift")
    if mount_major_minor != partition_major_minor:
        raise Stop("usb_mount_source_mismatch")

    preflight_namespace = _mount_namespace(None)
    service_namespace = None
    if require_service_namespace:
        if not isinstance(service, dict):
            raise Stop("ota_service_state_invalid")
        main_pid = service.get("MainPID")
        if not isinstance(main_pid, str) or not main_pid.isdigit() or int(main_pid) <= 0:
            raise Stop("ota_service_pid_invalid")
        service_namespace = _mount_namespace(int(main_pid))
        if preflight_namespace != service_namespace:
            raise Stop("usb_mount_namespace_mismatch")

    mount_options = {
        item.strip()
        for item in mount_options_raw.split(",")
        if item.strip()
    }
    if expected_mode == "recovery":
        required_options = set(plan["recovery_mount_required_options"])
        forbidden_options = set(plan["recovery_mount_forbidden_options"])
        if (
            not required_options.issubset(mount_options)
            or mount_options.intersection(forbidden_options)
        ):
            raise Stop("usb_recovery_mount_contract_invalid:" + ",".join(sorted(mount_options)))
        if not ({"noload", "norecovery"} & mount_options):
            raise Stop("usb_recovery_journal_suppression_missing")
    elif expected_mode == "writable":
        required_options = set(plan["writable_mount_required_options"])
        forbidden_options = set(plan["writable_mount_forbidden_options"])
        if (
            not required_options.issubset(mount_options)
            or mount_options.intersection(forbidden_options)
        ):
            raise Stop("usb_writable_mount_contract_invalid:" + ",".join(sorted(mount_options)))
    else:
        raise Stop("usb_mount_expected_mode_invalid")

    return {
        "partition": partition,
        "parent": parent,
        "public_fingerprint": observed_fingerprint,
        "filesystem_uuid": expected_uuid,
        "filesystem_type": filesystem_type,
        "filesystem_label": filesystem_label,
        "mount_source": mount_source,
        "mount_target": mount_target,
        "mount_major_minor": mount_major_minor,
        "mount_options": sorted(mount_options),
        "preflight_mount_namespace": preflight_namespace,
        "service_mount_namespace": service_namespace,
    }


def read_object(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + str(path))
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise Stop("required_file_metadata_invalid:" + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stop("required_object_invalid:" + str(path))
    return value


def unit_state(unit):
    completed = run(
        [
            "systemctl", "show", unit,
            "-p", "ActiveState", "-p", "SubState", "-p", "MainPID",
            "-p", "NRestarts", "-p", "Result",
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


def require_unit(unit):
    value = unit_state(unit)
    if (
        value.get("returncode") != 0
        or value.get("ActiveState") != "active"
        or value.get("SubState") != "running"
        or value.get("Result") != "success"
        or value.get("NRestarts") != "0"
    ):
        raise Stop("unit_not_healthy:" + unit)
    return value


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
    documents = json.loads(run(["docker", "inspect", ids[0]], timeout=45).stdout)
    if not isinstance(documents, list) or len(documents) != 1:
        raise Stop("container_inspect_invalid:" + image)
    item = documents[0]
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
print(s.recv(8192).decode().strip())"""
    completed = run(
        ["docker", "exec", "-u", "999:999", manager_id, "python3", "-c", probe],
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("ipc_probe_unavailable:" + str(completed.returncode))
    try:
        value = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as error:
        raise Stop("ipc_status_invalid") from error
    if not isinstance(value, dict) or value.get("accepted") is not True:
        raise Stop("ipc_status_rejected")
    return value



def verify_unmounted_media(plan, transaction):
    expected_uuid = plan["usb_filesystem_uuid"].lower()
    expected_fingerprint = plan["usb_public_fingerprint"]
    if transaction.get("usb_device_identity_public_fingerprint") != expected_fingerprint:
        raise Stop("u4_usb_fingerprint_drift")

    completed = run(
        ["blkid", "-t", "UUID=" + expected_uuid, "-o", "device"],
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("usb_filesystem_uuid_unavailable")
    matches = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(matches) != 1:
        raise Stop("usb_filesystem_uuid_cardinality_invalid")
    partition = matches[0]
    parent = _single_output(
        ["lsblk", "--noheadings", "--paths", "--output", "PKNAME", partition],
        "usb_bound_parent_invalid",
    )
    disks = [
        item
        for item in _lsblk_tree()
        if item.get("type") == "disk" and item.get("path") == parent
    ]
    if len(disks) != 1:
        raise Stop("usb_bound_parent_ambiguous")
    disk = disks[0]
    if (
        str(disk.get("tran") or "").strip().lower() != "usb"
        or not _boolish(disk.get("rm"))
        or _boolish(disk.get("ro"))
        or _stable_fingerprint(disk) != expected_fingerprint
    ):
        raise Stop("usb_bound_device_identity_mismatch")

    root_major_minor = _single_output(
        ["findmnt", "--noheadings", "--output", "MAJ:MIN", "/"],
        "usb_root_device_unresolved",
    )
    if root_major_minor in {
        str(item.get("maj:min") or "").strip()
        for item in _flatten_blocks([disk])
    }:
        raise Stop("usb_bound_device_is_root")

    filesystem_type = _single_output(
        ["blkid", "-s", "TYPE", "-o", "value", partition],
        "usb_filesystem_type_unavailable",
    )
    filesystem_label = _single_output(
        ["blkid", "-s", "LABEL", "-o", "value", partition],
        "usb_filesystem_label_unavailable",
    )
    if (
        filesystem_type != plan["usb_filesystem_type"]
        or filesystem_label != plan["usb_filesystem_label"]
    ):
        raise Stop("usb_bound_filesystem_contract_invalid")

    mounted_descendants = []
    for item in _flatten_blocks([disk]):
        mountpoints = item.get("mountpoints")
        if isinstance(mountpoints, list):
            mounted_descendants.extend(
                point.strip()
                for point in mountpoints
                if isinstance(point, str) and point.strip()
            )
        else:
            legacy_mountpoint = item.get("mountpoint")
            if isinstance(legacy_mountpoint, str) and legacy_mountpoint.strip():
                mounted_descendants.append(legacy_mountpoint.strip())
    if mounted_descendants:
        raise Stop(
            "usb_disk_descendant_still_mounted:"
            + ",".join(sorted(set(mounted_descendants)))
        )

    mounted = run(
        ["findmnt", "--noheadings", "--output", "TARGET", "--source", partition],
        timeout=30,
        check=False,
    )
    if mounted.returncode == 0 and mounted.stdout.strip():
        raise Stop("usb_still_mounted_after_unmount")
    occupied = run(
        ["findmnt", "--noheadings", "--mountpoint", plan["mount_target"], "--output", "SOURCE"],
        timeout=30,
        check=False,
    )
    if occupied.returncode == 0 and occupied.stdout.strip():
        raise Stop("usb_mount_target_still_occupied")
    partition_major_minor = _single_output(
        ["lsblk", "--noheadings", "--output", "MAJ:MIN", partition],
        "usb_partition_major_minor_unavailable",
    )
    fs_report = run(["tune2fs", "-l", partition], timeout=30, check=False)
    if fs_report.returncode != 0:
        raise Stop("usb_filesystem_state_unavailable")
    fs_state = ""
    for line in fs_report.stdout.splitlines():
        if line.startswith("Filesystem state:"):
            fs_state = line.split(":", 1)[1].strip()
            break
    if fs_state != "clean":
        raise Stop("usb_filesystem_not_clean:" + fs_state)
    return {
        "partition": partition,
        "parent": parent,
        "partition_major_minor": partition_major_minor,
        "public_fingerprint": expected_fingerprint,
        "filesystem_state": fs_state,
    }


def verify_target(plan):
    target = Path(plan["mount_target"]) / "n3w-update" / "target" / "homeassistant-arm64.tar.gz"
    for item in (target, target.parent, target.parent.parent):
        if item.is_symlink():
            raise Stop("target_archive_symlink")
    if not target.is_file():
        raise Stop("target_archive_missing")
    if target.stat().st_size != plan["target_size_bytes"]:
        raise Stop("target_archive_size_drift")
    if sha_file(target) != plan["target_sha256"]:
        raise Stop("target_archive_sha256_drift")
    return {
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "sha256": plan["target_sha256"],
    }


def verify_predecessor(plan):
    predecessor = (
        Path(plan["mount_target"])
        / "n3w-update"
        / "predecessor"
        / "homeassistant-predecessor.tar.gz"
    )
    for item in (predecessor, predecessor.parent, predecessor.parent.parent):
        if item.is_symlink():
            raise Stop("predecessor_archive_symlink")
    if not predecessor.is_file():
        raise Stop("predecessor_archive_missing")
    if predecessor.stat().st_size != plan["predecessor_size_bytes"]:
        raise Stop("predecessor_archive_size_drift")
    if sha_file(predecessor) != plan["predecessor_sha256"]:
        raise Stop("predecessor_archive_sha256_drift")
    return {
        "path": str(predecessor),
        "size_bytes": predecessor.stat().st_size,
        "sha256": plan["predecessor_sha256"],
    }


def _usb_metadata_object(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("usb_transaction_metadata_invalid:" + path.name)
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise Stop("usb_transaction_metadata_metadata_invalid:" + path.name)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("usb_transaction_metadata_json_invalid:" + path.name) from error
    if not isinstance(value, dict):
        raise Stop("usb_transaction_metadata_shape_invalid:" + path.name)
    return value


def usb_transaction_phase_observed(plan):
    phase_path = (
        Path(plan["mount_target"]) / "n3w-update" / "transaction" / "phase.json"
    )
    value = _usb_metadata_object(phase_path)
    if (
        value.get("schema") != "gh.n3w-t1-ha-usb-transaction-phase/1"
        or value.get("transaction_id_sha256") != plan["transaction_id_sha256"]
    ):
        raise Stop("usb_transaction_phase_binding_invalid")
    return value.get("phase")


def usb_transaction_metadata_view(plan, transaction, expected_phase):
    root = Path(plan["mount_target"]) / "n3w-update" / "transaction"
    manifest_path = root / "manifest.json"
    phase_path = root / "phase.json"
    checksums_path = root / "checksums.json"
    manifest = _usb_metadata_object(manifest_path)
    phase = _usb_metadata_object(phase_path)
    checksums = _usb_metadata_object(checksums_path)

    release = transaction.get("target_manifest_identity")
    release_identity = (
        release.get("release_identity")
        if isinstance(release, dict)
        else None
    )
    if manifest != {
        "schema": "gh.n3w-t1-ha-usb-transaction-manifest/1",
        "transaction_id_sha256": plan["transaction_id_sha256"],
        "release_identity": release_identity,
        "target_image_ref": transaction.get("target_image_ref"),
        "target_archive_sha256": plan["target_sha256"],
        "target_archive_size_bytes": plan["target_size_bytes"],
        "usb_filesystem_uuid": plan["usb_filesystem_uuid"],
        "usb_device_identity_public_fingerprint": plan["usb_public_fingerprint"],
    }:
        raise Stop("usb_transaction_manifest_drift")
    if phase != {
        "schema": "gh.n3w-t1-ha-usb-transaction-phase/1",
        "transaction_id_sha256": plan["transaction_id_sha256"],
        "phase": expected_phase,
        "target_artifact_verified": True,
        "usb_capacity_verified": True,
    }:
        raise Stop("usb_transaction_phase_drift")
    if checksums != {
        "schema": "gh.n3w-t1-ha-usb-checksums/1",
        "target_archive_sha256": plan["target_sha256"],
        "target_archive_size_bytes": plan["target_size_bytes"],
    }:
        raise Stop("usb_transaction_checksums_drift")
    return {
        "phase": expected_phase,
        "manifest_sha256": sha_file(manifest_path),
        "phase_sha256": sha_file(phase_path),
        "checksums_sha256": sha_file(checksums_path),
    }



def runtime_view(plan):
    units = {
        "host": require_unit(HOST_UNIT),
        "services_owner": require_unit(SERVICES_UNIT),
        "broker_owner": require_unit(BROKER_UNIT),
    }
    containers = {
        key: container_view(value["image"])
        for key, value in plan["containers"].items()
    }
    for key, expected in plan["containers"].items():
        observed = containers[key]
        if (
            observed["runtime_image_id"] != expected["runtime_image_id"]
            or observed["restart_count"] != 0
            or observed["status"] != "running"
        ):
            raise Stop("container_drift:" + key)
    return {"service": units["host"], "units": units, "containers": containers}


def validate_transaction(plan):
    r26_claim = read_object(R26 / "authorization_claim.json")
    r26_success = read_object(R26 / "success.json")
    r26_post = r26_success.get("post")
    if (
        r26_claim.get("authorization_id") != plan["r26_gate_id"]
        or r26_claim.get("claimed") is not True
        or r26_claim.get("consumed") is not True
        or r26_claim.get("replay_permitted") is not False
        or r26_success.get("status") != "U6_R26_PREDECESSOR_RECOVERY_PASS"
        or r26_success.get("authorization_consumed") is not True
        or r26_success.get("replay_permitted") is not False
        or not isinstance(r26_post, dict)
        or r26_post.get("transaction_sha256") != plan["transaction_sha256"]
        or r26_post.get("predecessor") != plan["predecessor_identity"]
    ):
        raise Stop("r26_authority_invalid")

    r29_claim = read_object(R29 / "authorization_claim.json")
    r29_success = read_object(R29 / "success.json")
    r29_post = r29_success.get("post")
    if (
        r29_claim.get("authorization_id") != plan["r29_gate_id"]
        or r29_claim.get("claimed") is not True
        or r29_claim.get("consumed") is not True
        or r29_claim.get("replay_permitted") is not False
        or r29_success.get("status") != "U7_R29_SOURCE_ACTIVATION_PASS"
        or r29_success.get("authorization_claimed") is not True
        or r29_success.get("authorization_consumed") is not True
        or r29_success.get("replay_permitted") is not False
        or r29_success.get("source_activated") is not True
        or r29_success.get("activated_source_file_count") != 7
        or not isinstance(r29_post, dict)
        or r29_post.get("transaction_sha256") != plan["transaction_sha256"]
    ):
        raise Stop("r29_authority_invalid")

    r30s_claim = read_object(R30S / "authorization_claim.json")
    r30s_success = read_object(R30S / "success.json")
    if (
        r30s_claim.get("authorization_id") != plan["r30s_gate_id"]
        or r30s_claim.get("claimed") is not True
        or r30s_claim.get("consumed") is not True
        or r30s_claim.get("replay_permitted") is not False
        or r30s_success.get("status") != "U7_R30S_PREPARE_HOST_SOURCE_ACTIVATION_PASS"
        or r30s_success.get("authorization_claimed") is not True
        or r30s_success.get("authorization_consumed") is not True
        or r30s_success.get("replay_permitted") is not False
        or r30s_success.get("source_activated") is not True
        or r30s_success.get("activated_source_file_count") != 1
        or r30s_success.get("transaction_sha256") != plan["transaction_sha256"]
    ):
        raise Stop("r30s_authority_invalid")

    transaction = read_object(TX_PATH)
    if (
        transaction.get("phase") != "U6_PREDECESSOR_RECOVERY_PREPARING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not False
        or transaction.get("predecessor_recovery_identity") is not None
        or transaction.get("ha_data_backup_verified") is not False
        or transaction.get("ha_data_backup_identity") is not None
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
        or transaction.get("transaction_id_sha256") != plan["transaction_id_sha256"]
        or transaction.get("usb_filesystem_uuid") != plan["usb_filesystem_uuid"]
        or transaction.get("usb_device_identity_public_fingerprint") != plan["usb_public_fingerprint"]
    ):
        raise Stop("u6_transaction_invalid")
    observed_sha = sha_file(TX_PATH)
    if observed_sha != plan["transaction_sha256"]:
        raise Stop("u6_transaction_sha256_drift")
    return transaction, observed_sha


def validate_sources(plan):
def validate_sources(plan):
    observed = {}
    for path, expected in plan["installed_source_sha256"].items():
        value = sha_file(path)
        if value != expected:
            raise Stop("installed_source_drift:" + Path(path).name)
        observed[path] = value
    return observed


def prepare_mount_target(plan):
    runtime_root = Path("/run/n3w-t1-ota")
    media_root = runtime_root / "media"
    target = Path(plan["mount_target"])
    if target.parent != media_root or target.name != plan["transaction_id_sha256"][:16]:
        raise Stop("mount_target_contract_invalid")
    if runtime_root.is_symlink() or not runtime_root.is_dir():
        raise Stop("runtime_root_invalid")
    root_meta = runtime_root.stat()
    if root_meta.st_uid != 0 or stat.S_IMODE(root_meta.st_mode) & 0o027:
        raise Stop("runtime_root_metadata_invalid")

    created = []
    for path in (media_root, target):
        if path.is_symlink():
            raise Stop("runtime_mount_directory_invalid:" + path.name)
        if not path.exists():
            path.mkdir(mode=0o700)
            created.append(str(path))
        if not path.is_dir():
            raise Stop("runtime_mount_directory_invalid:" + path.name)
        metadata = path.stat()
        if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise Stop("runtime_mount_directory_metadata_invalid:" + path.name)
    return {"target": str(target), "created": created}


def cleanup_created_directories(created):
    for raw in reversed(created):
        path = Path(raw)
        try:
            path.rmdir()
        except OSError:
            pass


def validate_preflight(plan):
    source_hashes = validate_sources(plan)
    transaction, transaction_sha256 = validate_transaction(plan)
    runtime = runtime_view(plan)
    unmounted = verify_unmounted_media(plan, transaction)
    return {
        "transaction_sha256": transaction_sha256,
        "transaction_phase": transaction["phase"],
        "installed_source_sha256": source_hashes,
        "runtime": runtime,
        "usb_unmounted": unmounted,
        "target_expected_sha256": plan["target_sha256"],
        "target_expected_size_bytes": plan["target_size_bytes"],
        "predecessor_expected_sha256": plan["predecessor_sha256"],
        "predecessor_expected_size_bytes": plan["predecessor_size_bytes"],
    }


def validate_post_writable(plan, baseline):
    source_hashes = validate_sources(plan)
    transaction, transaction_sha256 = validate_transaction(plan)
    runtime = runtime_view(plan)
    media = verify_bound_media(plan, transaction, runtime["service"], "writable")
    target = verify_target(plan)
    predecessor = verify_predecessor(plan)
    if transaction_sha256 != baseline["transaction_sha256"]:
        raise Stop("transaction_changed")
    if source_hashes != baseline["installed_source_sha256"]:
        raise Stop("installed_source_changed")
    if runtime != baseline["runtime"]:
        raise Stop("runtime_changed")
    return {
        "transaction_sha256": transaction_sha256,
        "transaction_phase": transaction["phase"],
        "installed_source_sha256": source_hashes,
        "runtime": runtime,
        "usb_binding": media,
        "target": target,
        "predecessor": predecessor,
    }

def durable_json(path, value):
def durable_json(path, value):
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(str(Path(path).parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def rollback_to_unmounted(plan, transaction, created):
    target = plan["mount_target"]
    mounted = run(
        ["findmnt", "--noheadings", "--mountpoint", target, "--output", "SOURCE"],
        timeout=30,
        check=False,
    )
    if mounted.returncode == 0 and mounted.stdout.strip():
        run(["umount", target], timeout=60)
    identity = verify_unmounted_media(plan, transaction)
    cleanup_created_directories(created)
    transaction_sha256 = sha_file(TX_PATH)
    if transaction_sha256 != plan["transaction_sha256"]:
        raise Stop("rollback_transaction_changed")
    return {
        "usb_unmounted": identity,
        "transaction_sha256": transaction_sha256,
    }

def execute(plan):
    mode = plan.get("mode")
    baseline = validate_preflight(plan)
    if mode == "preflight":
        return {
            "schema": "gh.n3w-t1-u7-r30m-writable-mount-restoration/1",
            "status": "PASS",
            "read_only": True,
            "restoration_eligible": True,
            "live_execution_authorized": plan.get("live_execution_authorized") is True,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "runtime_directory_creation_attempted": False,
            "writable_mount_attempted": False,
            "writable_mount_restored": False,
            "host_state_mutation": False,
            "usb_mutation": False,
            "transaction_mutation": False,
            "u7_transition": False,
            "u8_plus": False,
            "preflight": baseline,
        }
    if mode != "execute":
        raise Stop("execution_mode_invalid")
    if (
        plan.get("live_execution_authorized") is not True
        or plan.get("authorization_state") != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("restoration_live_execution_not_authorized")
    if (
        plan.get("authorization") != plan.get("authorization_id")
        or plan.get("confirmation") != plan.get("expected_confirmation")
    ):
        raise Stop("restoration_authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("restoration_authorization_state_root_exists")
    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    durable_json(state_root / "preflight.json", baseline)
    durable_json(
        state_root / "authorization_claim.json",
        {
            "authorization_id": plan["authorization_id"],
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
            "transaction_id_sha256": plan["transaction_id_sha256"],
            "usb_filesystem_uuid": plan["usb_filesystem_uuid"],
        },
    )

    result = {
        "schema": "gh.n3w-t1-u7-r30m-writable-mount-restoration/1",
        "status": "STOP",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "runtime_directory_creation_attempted": False,
        "runtime_directories_created": 0,
        "writable_mount_attempted": False,
        "writable_mount_restored": False,
        "rollback_attempted": False,
        "rollback_succeeded": False,
        "host_state_mutation": True,
        "host_source_mutation": False,
        "usb_mutation": False,
        "transaction_mutation": False,
        "service_restart": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "u7_transition": False,
        "u8_plus": False,
        "board_access": False,
        "merge": False,
    }
    created = []
    try:
        postclaim = validate_preflight(plan)
        durable_json(state_root / "postclaim.json", postclaim)
        result["runtime_directory_creation_attempted"] = True
        directory_state = prepare_mount_target(plan)
        created = directory_state["created"]
        result["runtime_directories_created"] = len(created)

        result["writable_mount_attempted"] = True
        result["usb_mutation"] = True
        run(
            [
                "mount",
                "-t",
                "ext4",
                "-o",
                "rw,nodev,nosuid,noexec",
                postclaim["usb_unmounted"]["partition"],
                directory_state["target"],
            ],
            timeout=60,
        )
        result["writable_mount_restored"] = True

        post = validate_post_writable(plan, baseline)
        result.update(
            status="U7_R30M_WRITABLE_MOUNT_RESTORATION_PASS",
            post=post,
            rollback_attempted=False,
            rollback_succeeded=False,
        )
        durable_json(state_root / "result.json", result)
        return result
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
        if result["writable_mount_attempted"]:
            result["rollback_attempted"] = True
            try:
                transaction, _ = validate_transaction(plan)
                rollback = rollback_to_unmounted(plan, transaction, created)
                result["rollback_succeeded"] = True
                result["rollback"] = rollback
            except Exception as rollback_error:
                result["rollback_succeeded"] = False
                result["rollback_reason"] = (
                    type(rollback_error).__name__ + ":" + str(rollback_error)[:240]
                )
        try:
            durable_json(state_root / "failure.json", result)
        except Exception:
            pass
        return result

def main():
    result = {
        "schema": "gh.n3w-t1-u7-r30m-writable-mount-restoration/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "usb_mutation": False,
        "host_state_mutation": False,
        "host_source_mutation": False,
        "service_restart": False,
        "u7_transition": False,
        "u8_plus": False,
        "board_access": False,
        "merge": False,
    }
    try:
        plan = json.loads(base64.b64decode(sys.argv[1]))
        result = execute(plan)
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {
        "PASS",
        "U7_R30M_WRITABLE_MOUNT_RESTORATION_PASS",
    } else 2


raise SystemExit(main())
'''

def git_text(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("local_git_failed")
    return completed.stdout.strip()

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
        {"granted": True, "claimed": False, "consumed": False, "replay_permitted": False}
        if execute
        else {"granted": False, "claimed": False, "consumed": False, "replay_permitted": False}
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
    for relative, expected_sha in document["target_source_sha256"].items():
        if sha_file(ROOT / relative) != expected_sha:
            raise Stop("target_source_sha256_drift:" + relative)
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

def load_transport() -> type:
    spec = importlib.util.spec_from_file_location(
        "n3w_r12_post_reboot_mount_transport", SSH_TRANSPORT_PATH
    )
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport

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
        "schema": "gh.n3w-t1-kf147-u7-r30m-writable-mount-restoration-local-result/1",
        "status": "STOP",
        "read_only_preflight": bool(args.preflight_only),
        "t1_access": False,
        "live_execution_authorized": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "remote_staging": False,
        "host_state_mutation": False,
        "host_source_mutation": False,
        "usb_mutation": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "u7_transition": False,
        "u8_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    try:
        if re.fullmatch(r"[A-Za-z0-9._-]{1,160}", args.execution_id) is None:
            raise Stop("execution_id_invalid")
        if args.execute and (
            args.authorization_id != GATE_ID or args.confirm != CONFIRMATION
        ):
            raise Stop("authorization_invalid")
        manifest = read_manifest(
            args.expected_package_commit,
            execute=bool(args.execute),
        )
        evidence_root = prepare_evidence_root(args.evidence_root)
        transport_type = load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        plan = dict(manifest["expected_live_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "authorization_id": manifest["authorization_id"],
                "expected_confirmation": manifest["confirmation"],
                "live_execution_authorized": manifest["live_execution_authorized"],
                "authorization_state": manifest["authorization_state"],
                "state_root": manifest["state_root"],
                "mode": "preflight" if args.preflight_only else "execute",
                "authorization": "" if args.preflight_only else args.authorization_id,
                "confirmation": "" if args.preflight_only else args.confirm,
            }
        )
        payload = base64.b64encode(
            json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        completed = transport.run_remote(
            ["python3", "-c", REMOTE_SCRIPT, payload],
            timeout=900,
            check=False,
        )
        result["remote_returncode"] = completed.returncode
        write_private(
            evidence_root / "remote_transport.json",
            {
                "returncode": completed.returncode,
                "stdout_length": len(completed.stdout),
                "stderr_length": len(completed.stderr),
            },
        )
        write_private(
            evidence_root / "remote_stdout.json",
            {"stdout": completed.stdout},
        )
        write_private(
            evidence_root / "remote_stderr.json",
            {"stderr": completed.stderr},
        )
        try:
            remote = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise Stop(
                "remote_result_json_invalid:"
                + str(completed.returncode)
                + ":stdout_len="
                + str(len(completed.stdout))
                + ":stderr_len="
                + str(len(completed.stderr))
            ) from error
        write_private(evidence_root / "result.json", remote)
        if completed.returncode != 0 or remote.get("status") not in {
            "PASS",
            "U7_R30M_WRITABLE_MOUNT_RESTORATION_PASS",
        }:
            result["reason"] = remote.get("reason") or "remote_restoration_stop"
            result["authorization_claimed"] = bool(remote.get("authorization_claimed"))
            result["authorization_consumed"] = bool(remote.get("authorization_consumed"))
            result["usb_mutation"] = bool(remote.get("usb_mutation"))
            result["host_state_mutation"] = bool(remote.get("host_state_mutation"))
        else:
            result.update(remote)
            result["t1_access"] = True
            result["live_execution_authorized"] = bool(args.execute)
            return_code = 0
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception:
                result["ssh_master_cleanup"] = False
                return_code = 2
    print(json.dumps(result, sort_keys=True))
    return return_code

if __name__ == "__main__":
    raise SystemExit(main())
