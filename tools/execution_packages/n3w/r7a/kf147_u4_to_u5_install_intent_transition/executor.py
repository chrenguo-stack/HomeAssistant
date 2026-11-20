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
GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "U4_TO_U5_INSTALL_INTENT_TRANSITION_R9_20261111_01"
)
CONFIRMATION = "EXECUTE KF147 U4 TO U5 INSTALL INTENT TRANSITION R9: YES"


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
R6_ROOT = Path(
    "/var/lib/n3w-t1-core-updater/"
    "kf147-u3-mounted-root-resume-r6-20261111-01"
)
SERVICE = "n3w-t1-ha-ota.service"


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


def git_blob_sha1(path):
    payload = Path(path).read_bytes()
    digest = hashlib.sha1()
    digest.update(b"blob " + str(len(payload)).encode("ascii") + b"\0")
    digest.update(payload)
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


def verify_bound_media(plan, transaction, service):
    expected_uuid = plan["usb_filesystem_uuid"].lower()
    expected_fingerprint = plan["usb_public_fingerprint"]
    if transaction.get("usb_device_identity_public_fingerprint") != expected_fingerprint:
        raise Stop("u4_usb_fingerprint_drift")

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

    main_pid = service.get("MainPID")
    if not isinstance(main_pid, str) or not main_pid.isdigit() or int(main_pid) <= 0:
        raise Stop("ota_service_pid_invalid")
    preflight_namespace = _mount_namespace(None)
    service_namespace = _mount_namespace(int(main_pid))
    if preflight_namespace != service_namespace:
        raise Stop("usb_mount_namespace_mismatch")

    mount_options = {
        item.strip()
        for item in mount_options_raw.split(",")
        if item.strip()
    }
    required_options = set(plan["mount_required_options"])
    forbidden_options = set(plan["mount_forbidden_options"])
    if (
        not required_options.issubset(mount_options)
        or mount_options.intersection(forbidden_options)
    ):
        raise Stop("usb_mount_not_u5_writable:" + ",".join(sorted(mount_options)))

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


def service_state():
    completed = run(
        [
            "systemctl", "show", SERVICE,
            "-p", "ActiveState", "-p", "SubState", "-p", "MainPID",
            "-p", "NRestarts", "-p", "Result", "-p", "ExecMainStartTimestamp",
        ],
        timeout=30,
    )
    result = {}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


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


def ipc_request(manager_id, document):
    probe = r"""import json,socket,sys
request=json.loads(sys.argv[1])
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(5)
s.connect("/run/n3w/t1-ota/ha-ota.sock")
s.sendall(json.dumps(request,sort_keys=True,separators=(",",":")).encode()+b"\n")
s.shutdown(socket.SHUT_WR)
payload=s.recv(8192).decode().strip()
print(payload)"""
    completed = run(
        [
            "docker", "exec", "-u", "999:999", manager_id,
            "python3", "-c", probe,
            json.dumps(document, sort_keys=True, separators=(",", ":")),
        ],
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("ipc_request_unavailable:" + str(completed.returncode))
    try:
        value = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as error:
        raise Stop("ipc_response_invalid") from error
    if not isinstance(value, dict) or value.get("accepted") is not True:
        raise Stop("ipc_request_rejected:" + str(value.get("code") if isinstance(value, dict) else "invalid"))
    return value


def ipc_status(manager_id):
    return ipc_request(
        manager_id,
        {"schema": "gh.n3w-t1-ha-ota-ipc-request/1", "operation": "status"},
    )


def ipc_install(manager_id, release_id):
    return ipc_request(
        manager_id,
        {
            "schema": "gh.n3w-t1-ha-ota-ipc-request/1",
            "operation": "submit",
            "action": "INSTALL",
            "target_release_id": release_id,
        },
    )


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


def validate_installed_sources(plan):
    sha256_view = {}
    for path, expected in plan["installed_predecessor_sha256"].items():
        observed = sha_file(path)
        if observed != expected:
            raise Stop("installed_source_drift:" + Path(path).name)
        sha256_view[path] = observed

    blob_view = {}
    for path, expected in plan["installed_runtime_git_blob_sha1"].items():
        observed = git_blob_sha1(path)
        if observed != expected:
            raise Stop("installed_runtime_source_drift:" + Path(path).name)
        blob_view[path] = observed
    return sha256_view, blob_view


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


def validate_u4(plan):
    source_hashes, runtime_blobs = validate_installed_sources(plan)

    claim = read_object(R6_ROOT / "authorization_claim.json")
    activation = read_object(R6_ROOT / "activation.json")
    failure = read_object(R6_ROOT / "failure.json")
    if (
        claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or activation.get("source_activated") is not True
        or failure.get("status") != "STOP"
        or failure.get("authorization_consumed") is not True
        or failure.get("replay_permitted") is not False
    ):
        raise Stop("r6_terminal_state_invalid")

    transaction = read_object(TX_PATH)
    if (
        transaction.get("phase") != "U4_READY_TO_INSTALL"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("transaction_id_sha256") != plan["transaction_id_sha256"]
        or transaction.get("usb_filesystem_uuid") != plan["usb_filesystem_uuid"]
    ):
        raise Stop("u4_transaction_invalid")
    transaction_sha256 = sha_file(TX_PATH)
    if transaction_sha256 != plan["transaction_sha256"]:
        raise Stop("u4_transaction_sha256_drift")

    service = service_state()
    if service.get("ActiveState") != "active" or service.get("SubState") != "running":
        raise Stop("ota_service_not_running")
    media_binding = verify_bound_media(plan, transaction, service)
    mount_target = media_binding["mount_target"]
    target = Path(mount_target) / "n3w-update" / "target" / "homeassistant-arm64.tar.gz"
    if target.is_symlink() or not target.is_file():
        raise Stop("target_archive_missing")
    if target.stat().st_size != plan["target_size_bytes"]:
        raise Stop("target_archive_size_drift")
    if sha_file(target) != plan["target_sha256"]:
        raise Stop("target_archive_sha256_drift")

    containers = {
        key: container_view(value["image"])
        for key, value in plan["containers"].items()
    }
    for key, expected in plan["containers"].items():
        observed = containers[key]
        if (
            observed["container_id"] != expected["container_id"]
            or observed["runtime_image_id"] != expected["runtime_image_id"]
            or observed["restart_count"] != 0
            or observed["status"] != "running"
        ):
            raise Stop("container_drift:" + key)
    ipc = ipc_status(containers["manager"]["container_id"])
    if (
        ipc.get("phase") != "READY_TO_INSTALL"
        or ipc.get("error_code") is not None
        or ipc.get("installed_version") != "2026.10.0"
    ):
        raise Stop("ipc_not_ready_to_install")
    usb_transaction_metadata = usb_transaction_metadata_view(
        plan,
        transaction,
        "U4_READY_TO_INSTALL",
    )
    return {
        "transaction": transaction,
        "transaction_sha256": transaction_sha256,
        "installed_source_sha256": source_hashes,
        "installed_runtime_git_blob_sha1": runtime_blobs,
        "service": service,
        "usb_binding": media_binding,
        "usb_transaction_metadata": usb_transaction_metadata,
        "target_sha256": plan["target_sha256"],
        "target_size_bytes": target.stat().st_size,
        "containers": containers,
        "ipc": ipc,
    }


def validate_u5(plan, baseline):
    source_hashes, runtime_blobs = validate_installed_sources(plan)

    transaction = read_object(TX_PATH)
    if (
        transaction.get("phase") != "U5_INSTALL_REQUESTED_REVALIDATING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("transaction_id_sha256") != plan["transaction_id_sha256"]
        or transaction.get("usb_filesystem_uuid") != plan["usb_filesystem_uuid"]
    ):
        raise Stop("u5_transaction_invalid")
    transaction_sha256 = sha_file(TX_PATH)
    if transaction_sha256 == baseline["transaction_sha256"]:
        raise Stop("u5_transaction_not_changed")

    service = service_state()
    if service != baseline["service"]:
        raise Stop("service_changed")
    media_binding = verify_bound_media(plan, transaction, service)
    if media_binding != baseline["usb_binding"]:
        raise Stop("usb_binding_changed")

    target = Path(media_binding["mount_target"]) / "n3w-update" / "target" / "homeassistant-arm64.tar.gz"
    if target.is_symlink() or not target.is_file():
        raise Stop("target_archive_missing")
    if target.stat().st_size != plan["target_size_bytes"] or sha_file(target) != plan["target_sha256"]:
        raise Stop("target_archive_drift")

    containers = {
        key: container_view(value["image"])
        for key, value in plan["containers"].items()
    }
    if containers != baseline["containers"]:
        raise Stop("container_changed")

    ipc = ipc_status(containers["manager"]["container_id"])
    if (
        ipc.get("phase") != "INSTALL_REQUESTED_REVALIDATING"
        or ipc.get("error_code") is not None
        or ipc.get("installed_version") != "2026.10.0"
    ):
        raise Stop("ipc_not_u5")
    usb_transaction_metadata = usb_transaction_metadata_view(
        plan,
        transaction,
        "U5_INSTALL_REQUESTED_REVALIDATING",
    )
    before_usb = baseline["usb_transaction_metadata"]
    if (
        usb_transaction_metadata["manifest_sha256"] != before_usb["manifest_sha256"]
        or usb_transaction_metadata["checksums_sha256"] != before_usb["checksums_sha256"]
        or usb_transaction_metadata["phase_sha256"] == before_usb["phase_sha256"]
    ):
        raise Stop("usb_transaction_metadata_transition_invalid")
    return {
        "transaction_phase": transaction["phase"],
        "transaction_sha256": transaction_sha256,
        "installed_source_sha256": source_hashes,
        "installed_runtime_git_blob_sha1": runtime_blobs,
        "service": service,
        "usb_binding": media_binding,
        "usb_transaction_metadata": usb_transaction_metadata,
        "target_sha256": plan["target_sha256"],
        "target_size_bytes": target.stat().st_size,
        "containers": containers,
        "ipc": ipc,
    }


def execute(plan):
    baseline = validate_u4(plan)
    if plan.get("mode") == "preflight":
        return {
            "schema": "gh.n3w-t1-kf147-u4-u5-install-intent-transition/1",
            "status": "PASS",
            "read_only": True,
            "u5_transition_eligible": True,
            "live_execution_authorized": plan.get("live_execution_authorized") is True,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "usb_transaction_metadata_mutation": False,
            "host_source_mutation": False,
            "service_restart": False,
            "homeassistant_mutation": False,
            "manager_mutation": False,
            "broker_mutation": False,
            "u5_transition": False,
            "u6_plus": False,
            "preflight": baseline,
            "board_access": False,
            "merge": False,
        }
    if plan.get("mode") != "execute":
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
        raise Stop("u5_transition_live_execution_not_authorized")
    if (
        plan.get("authorization") != plan.get("authorization_id")
        or plan.get("confirmation") != plan.get("expected_confirmation")
    ):
        raise Stop("u5_transition_authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("u5_transition_authorization_state_root_exists")
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
            "target_release_id": plan["target_release_id"],
        },
    )

    result = {
        "schema": "gh.n3w-t1-kf147-u4-u5-install-intent-transition/1",
        "status": "STOP",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "transaction_mutation": False,
        "host_state_mutation": True,
        "host_source_mutation": False,
        "usb_mutation": False,
        "usb_transaction_metadata_mutation": False,
        "split_state_detected": False,
        "service_restart": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "u5_transition": False,
        "u6_plus": False,
        "board_access": False,
        "merge": False,
    }
    try:
        postclaim = validate_u4(plan)
        durable_json(state_root / "postclaim.json", postclaim)
        install_response = ipc_install(
            postclaim["containers"]["manager"]["container_id"],
            plan["target_release_id"],
        )
        result["transaction_mutation"] = True
        result["usb_mutation"] = True
        result["usb_transaction_metadata_mutation"] = True
        result["u5_transition"] = True
        durable_json(state_root / "install_response.json", install_response)

        post = validate_u5(plan, baseline)
        result.update(
            status="U5_INSTALL_INTENT_TRANSITION_PASS",
            post=post,
        )
        durable_json(state_root / "result.json", result)
        return result
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
        host_phase = None
        usb_phase = None
        try:
            transaction = read_object(TX_PATH)
            host_phase = transaction.get("phase")
            result["observed_transaction_phase"] = host_phase
            result["u5_transition"] = host_phase == "U5_INSTALL_REQUESTED_REVALIDATING"
            result["u6_plus"] = host_phase not in {
                "U4_READY_TO_INSTALL",
                "U5_INSTALL_REQUESTED_REVALIDATING",
            }
            result["transaction_mutation"] = result["u5_transition"] or result["u6_plus"]
        except Exception:
            pass
        try:
            usb_phase = usb_transaction_phase_observed(plan)
            result["observed_usb_transaction_phase"] = usb_phase
            result["usb_mutation"] = usb_phase != "U4_READY_TO_INSTALL"
            result["usb_transaction_metadata_mutation"] = result["usb_mutation"]
        except Exception:
            pass
        if host_phase is not None and usb_phase is not None:
            result["split_state_detected"] = host_phase != usb_phase
        try:
            durable_json(state_root / "failure.json", result)
        except Exception:
            pass
        return result


def main():
    result = {
        "schema": "gh.n3w-t1-kf147-u4-u5-install-intent-transition/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "transaction_mutation": False,
        "host_state_mutation": False,
        "host_source_mutation": False,
        "usb_mutation": False,
        "service_restart": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "u5_transition": False,
        "u6_plus": False,
        "board_access": False,
        "merge": False,
    }
    try:
        plan = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
            "U4_TO_U5_INSTALL_INTENT_TRANSITION_R9_20261111_01"
        ):
            raise Stop("gate_id_invalid")
        result = execute(plan)
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {
        "PASS",
        "U5_INSTALL_INTENT_TRANSITION_PASS",
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
    runtime_blobs = document["expected_live_entry"]["installed_runtime_git_blob_sha1"]
    prefix = "/opt/HomeAssistant/"
    for installed, expected_blob in runtime_blobs.items():
        if not installed.startswith(prefix):
            raise Stop("installed_runtime_source_path_invalid")
        relative = installed[len(prefix):]
        if git_text("rev-parse", "HEAD:" + relative) != expected_blob:
            raise Stop("installed_runtime_source_authority_drift:" + relative)
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
    spec = importlib.util.spec_from_file_location("n3w_u5_install_intent_transition_transport", SSH_TRANSPORT_PATH)
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
        "schema": "gh.n3w-t1-kf147-u4-u5-install-intent-transition-local-result/1",
        "status": "STOP",
        "read_only_preflight": bool(args.preflight_only),
        "t1_access": False,
        "live_execution_authorized": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "remote_staging": False,
        "host_state_mutation": False,
        "host_source_mutation": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "usb_transaction_metadata_mutation": False,
        "split_state_detected": False,
        "service_restart": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "u5_transition": False,
        "u6_plus": False,
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
        write_private(evidence_root / "remote_stdout.json", {"stdout": completed.stdout})
        write_private(evidence_root / "remote_stderr.json", {"stderr": completed.stderr})
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
            "U5_INSTALL_INTENT_TRANSITION_PASS",
        }:
            result["reason"] = remote.get("reason") or "remote_u5_transition_stop"
            for key in (
                "authorization_claimed",
                "authorization_consumed",
                "transaction_mutation",
                "host_state_mutation",
                "host_source_mutation",
                "usb_mutation",
                "usb_transaction_metadata_mutation",
                "split_state_detected",
                "service_restart",
                "homeassistant_mutation",
                "manager_mutation",
                "broker_mutation",
                "u5_transition",
                "u6_plus",
                "board_access",
                "merge",
            ):
                if key in remote:
                    result[key] = remote[key]
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
