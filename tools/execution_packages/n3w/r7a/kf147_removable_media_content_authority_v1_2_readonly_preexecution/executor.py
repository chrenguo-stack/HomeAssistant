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
    "REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_READONLY_PREEXECUTION_20261112_01"
)


class Stop(RuntimeError):
    pass


REMOTE_SCRIPT = r"""
import base64
import hashlib
import json
import socket
import stat
import subprocess
import sys
from pathlib import Path


class Stop(RuntimeError):
    pass


TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
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


def read_object(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + str(path))
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise Stop("required_file_metadata_invalid:" + str(path))
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Stop("required_object_invalid:" + str(path)) from error
    if not isinstance(value, dict):
        raise Stop("required_object_invalid:" + str(path))
    return value


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
    completed = run(argv, timeout=30, check=False)
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
        partition_path = partition["path"]

        mounted = tuple(
            point
            for item in descendants
            for point in _mountpoints(item)
        )
        if mounted:
            if set(mounted) != {expected_runtime_mount}:
                continue
            mount_state = "UPDATER_RUNTIME_MOUNTED"
        else:
            mount_state = "UNMOUNTED"

        fs = run(
            ["blkid", "-s", "TYPE", "-o", "value", partition_path],
            timeout=30,
            check=False,
        )
        label = run(
            ["blkid", "-s", "LABEL", "-o", "value", partition_path],
            timeout=30,
            check=False,
        )
        if (
            fs.returncode != 0
            or label.returncode != 0
            or fs.stdout.strip() != "ext4"
            or label.stdout.strip() != "N3W-UPDATE"
        ):
            continue

        size = partition.get("size")
        if type(size) is not int or size <= 0:
            raise Stop("usb_partition_size_invalid")

        matches.append(
            {
                "parent": path,
                "partition": partition_path,
                "partition_major_minor": str(
                    partition.get("maj:min") or ""
                ).strip(),
                "model": str(disk.get("model") or "").strip(),
                "size_bytes": size,
                "filesystem_type": "ext4",
                "filesystem_label": "N3W-UPDATE",
                "mount_state": mount_state,
                "expected_runtime_mount": expected_runtime_mount,
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


def service_state():
    completed = run(
        [
            "systemctl",
            "show",
            SERVICE,
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
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "ancestor=" + image,
                "--format",
                "{{.ID}}",
            ],
            timeout=45,
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(ids) != 1:
        raise Stop("container_cardinality_invalid:" + image)
    documents = json.loads(
        run(["docker", "inspect", ids[0]], timeout=45).stdout
    )
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
            manager_id,
            "python3",
            "-c",
            probe,
        ],
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


def main():
    result = {
        "schema": "gh.n3w-t1-kf147-removable-media-content-authority-v1-2-readonly-preexecution/1",
        "status": "STOP",
        "read_only": True,
        "source_activation_preflight_eligible": False,
        "physical_media_identity_authority": False,
        "live_execution_authorized": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "remote_staging": False,
        "mount_attempted": False,
        "umount_attempted": False,
        "host_source_mutation": False,
        "host_state_mutation": False,
        "usb_mutation": False,
        "transaction_mutation": False,
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
            "REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_READONLY_PREEXECUTION_20261112_01"
        ):
            raise Stop("gate_id_invalid")

        transaction = read_object(TX_PATH)
        if (
            transaction.get("schema")
            != "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
            or transaction.get("phase") != "U4_READY_TO_INSTALL"
            or transaction.get("status") != "ACTIVE"
            or transaction.get("target_artifact_verified") is not True
            or transaction.get("usb_capacity_verified") is not True
            or transaction.get("authorization_claimed") is not False
            or transaction.get("authorization_consumed") is not False
            or transaction.get("transaction_id_sha256")
            != plan["transaction_id_sha256"]
        ):
            raise Stop("legacy_u4_transaction_invalid")
        transaction_sha256 = sha_file(TX_PATH)
        if transaction_sha256 != plan["transaction_sha256"]:
            raise Stop("legacy_u4_transaction_sha256_drift")

        for field in (
            "target_artifact_identity",
            "predecessor_recovery_identity",
            "ha_data_backup_identity",
            "recovery_content_manifest_sha256",
        ):
            if transaction.get(field) is not None:
                raise Stop("legacy_u4_already_extended:" + field)

        source_hashes = {}
        for path in plan["installed_source_paths"]:
            source_hashes[path] = sha_file(path)
        for path, expected in plan["known_installed_source_sha256"].items():
            if source_hashes.get(path) != expected:
                raise Stop("installed_source_drift:" + Path(path).name)

        service = service_state()
        if (
            service.get("ActiveState") != "active"
            or service.get("SubState") != "running"
            or service.get("NRestarts") != "0"
            or service.get("Result") != "success"
        ):
            raise Stop("ota_service_not_healthy")

        containers = {
            key: container_view(value["image"])
            for key, value in plan["containers"].items()
        }
        for key, expected in plan["containers"].items():
            observed = containers[key]
            if (
                observed["runtime_image_id"]
                != expected["runtime_image_id"]
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

        media = safe_compatible_media(transaction)

        result.update(
            {
                "status": "PASS",
                "source_activation_preflight_eligible": True,
                "legacy_u4_compatible": True,
                "transaction_phase": transaction["phase"],
                "transaction_sha256": transaction_sha256,
                "installed_source_sha256": source_hashes,
                "service": service,
                "containers": containers,
                "ipc": ipc,
                "compatible_media": media,
            }
        )
        return_code = 0
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
        return_code = 2
    print(json.dumps(result, sort_keys=True))
    return return_code


raise SystemExit(main())
"""


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


def read_manifest(expected_commit: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        document.get("gate_id") != GATE_ID
        or document.get("live_execution_authorized") is not False
        or document.get("authorization_state")
        != {
            "granted": False,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("manifest_contract_invalid")
    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
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
        "n3w_v1_2_readonly_preexecution_transport",
        SSH_TRANSPORT_PATH,
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
    parser.add_argument("--preflight-only", action="store_true", required=True)
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema": "gh.n3w-t1-kf147-removable-media-content-authority-v1-2-readonly-preexecution-local-result/1",
        "status": "STOP",
        "read_only_preflight": True,
        "t1_access": False,
        "live_execution_authorized": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "remote_staging": False,
        "mount_attempted": False,
        "umount_attempted": False,
        "host_source_mutation": False,
        "host_state_mutation": False,
        "usb_mutation": False,
        "transaction_mutation": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "u5_transition": False,
        "u6_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    try:
        if args.execution_id != GATE_ID:
            raise Stop("execution_id_invalid")
        manifest = read_manifest(args.expected_package_commit)
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
        plan["gate_id"] = GATE_ID
        payload = base64.b64encode(
            json.dumps(
                plan,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii")
        completed = transport.run_remote(
            ["python3", "-c", REMOTE_SCRIPT, payload],
            timeout=900,
            check=False,
        )
        try:
            remote = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise Stop("remote_result_json_invalid") from error
        write_private(evidence_root / "preflight.json", remote)
        result["remote_returncode"] = completed.returncode
        if completed.returncode != 0 or remote.get("status") != "PASS":
            result["reason"] = (
                remote.get("reason") or "remote_preflight_stop"
            )
            return_code = 2
        else:
            result.update(remote)
            result["t1_access"] = True
            return_code = 0
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
        return_code = 2
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception:
                result["ssh_master_cleanup"] = False

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
