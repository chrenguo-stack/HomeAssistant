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
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U6_PREDECESSOR_RECOVERY_READONLY_PREFLIGHT_R24_20261114_01"
)


class Stop(RuntimeError):
    pass


REMOTE_SCRIPT = r'''
import base64
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path


TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
R23_ROOT = Path(
    "/var/lib/n3w-t1-core-updater/"
    "kf153-r23-u5-ipc-source-activation-20261113-01"
)
HOST_UNIT = "n3w-t1-ha-ota.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
HOMEASSISTANT_CONTAINER = "n3wfc4-homeassistant-1"


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
        raise Stop("required_file_invalid:" + str(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
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
    except Exception as error:
        raise Stop("required_json_invalid:" + str(path)) from error
    if not isinstance(value, dict):
        raise Stop("required_object_invalid:" + str(path))
    return value


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


def require_healthy_unit(unit, name):
    observed = service_state(unit)
    if (
        observed.get("returncode") != 0
        or observed.get("ActiveState") != "active"
        or observed.get("SubState") != "running"
        or observed.get("Result") != "success"
        or observed.get("NRestarts") != "0"
    ):
        raise Stop("unit_not_healthy:" + name)
    return observed


def docker_view(image):
    ids = [
        value.strip()
        for value in run(
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
        if value.strip()
    ]
    if len(ids) != 1:
        raise Stop("container_cardinality_invalid:" + image)
    documents = json.loads(run(["docker", "inspect", ids[0]], timeout=45).stdout)
    if not isinstance(documents, list) or len(documents) != 1:
        raise Stop("container_inspect_invalid:" + image)
    item = documents[0]
    state = item.get("State") if isinstance(item.get("State"), dict) else {}
    config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
    return {
        "container_id": item.get("Id"),
        "runtime_image_id": item.get("Image"),
        "configured_image_ref": config.get("Image"),
        "status": state.get("Status"),
        "restart_count": item.get("RestartCount"),
    }


def exact_homeassistant_container():
    completed = run(
        ["docker", "inspect", "--type", "container", HOMEASSISTANT_CONTAINER],
        timeout=45,
    )
    documents = json.loads(completed.stdout)
    if not isinstance(documents, list) or len(documents) != 1:
        raise Stop("homeassistant_container_inspect_invalid")
    item = documents[0]
    state = item.get("State") if isinstance(item.get("State"), dict) else {}
    config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
    return {
        "container_id": item.get("Id"),
        "runtime_image_id": item.get("Image"),
        "configured_image_ref": config.get("Image"),
        "status": state.get("Status"),
        "restart_count": item.get("RestartCount"),
    }


def flatten_blocks(nodes):
    result = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        result.append(node)
        children = node.get("children")
        if isinstance(children, list):
            result.extend(flatten_blocks(children))
    return result


def boolish(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def lsblk_tree():
    completed = run(
        [
            "lsblk",
            "--json",
            "--bytes",
            "--paths",
            "--tree",
            "--output",
            "PATH,TYPE,RM,RO,SIZE,MODEL,SERIAL,WWN,TRAN,MOUNTPOINTS,MAJ:MIN",
        ],
        timeout=30,
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Stop("usb_inventory_invalid") from error
    blocks = value.get("blockdevices")
    if not isinstance(blocks, list):
        raise Stop("usb_inventory_invalid")
    return [item for item in blocks if isinstance(item, dict)]


def mountpoints(node):
    raw = node.get("mountpoints")
    if isinstance(raw, list):
        return tuple(
            str(item).strip()
            for item in raw
            if isinstance(item, str) and item.strip()
        )
    raw = node.get("mountpoint")
    if isinstance(raw, str) and raw.strip():
        return (raw.strip(),)
    return ()


def command_value(argv, reason):
    completed = run(argv, timeout=30, check=False)
    if completed.returncode != 0:
        raise Stop(reason)
    value = completed.stdout.strip()
    if not value:
        raise Stop(reason)
    return value


def resolve_content_authority_media(plan):
    root_major_minor = command_value(
        ["findmnt", "--noheadings", "--output", "MAJ:MIN", "/"],
        "root_device_unresolved",
    )
    expected_target = plan["mount_target"]
    matches = []

    for disk in lsblk_tree():
        if disk.get("type") != "disk":
            continue
        if (
            str(disk.get("tran") or "").strip().lower() != "usb"
            or not boolish(disk.get("rm"))
            or boolish(disk.get("ro"))
        ):
            continue
        descendants = flatten_blocks([disk])
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
        ]
        if len(partitions) != 1:
            continue
        partition = str(partitions[0]["path"])
        filesystem_type = run(
            ["blkid", "-s", "TYPE", "-o", "value", partition],
            timeout=30,
            check=False,
        )
        filesystem_label = run(
            ["blkid", "-s", "LABEL", "-o", "value", partition],
            timeout=30,
            check=False,
        )
        if (
            filesystem_type.returncode != 0
            or filesystem_label.returncode != 0
            or filesystem_type.stdout.strip() != "ext4"
            or filesystem_label.stdout.strip() != "N3W-UPDATE"
        ):
            continue
        targets = {
            point
            for item in descendants
            for point in mountpoints(item)
        }
        if targets != {expected_target}:
            continue
        matches.append((disk, partition))

    if len(matches) != 1:
        raise Stop("content_authority_media_cardinality_invalid")

    disk, partition = matches[0]
    mount_source = command_value(
        [
            "findmnt",
            "--noheadings",
            "--mountpoint",
            expected_target,
            "--output",
            "SOURCE",
        ],
        "usb_mount_missing",
    )
    mount_type = command_value(
        [
            "findmnt",
            "--noheadings",
            "--mountpoint",
            expected_target,
            "--output",
            "FSTYPE",
        ],
        "usb_mount_missing",
    )
    options_raw = command_value(
        [
            "findmnt",
            "--noheadings",
            "--mountpoint",
            expected_target,
            "--output",
            "OPTIONS",
        ],
        "usb_mount_missing",
    )
    options = {
        item.strip()
        for item in options_raw.split(",")
        if item.strip()
    }
    if mount_type != "ext4":
        raise Stop("usb_mount_filesystem_invalid")
    if not {"rw", "nodev", "nosuid", "noexec"}.issubset(options):
        raise Stop("usb_mount_options_invalid")
    if {"ro", "noload", "norecovery"}.intersection(options):
        raise Stop("usb_mount_options_invalid")

    uuid_probe = run(
        ["blkid", "-s", "UUID", "-o", "value", partition],
        timeout=30,
        check=False,
    )
    current_uuid = (
        uuid_probe.stdout.strip().lower()
        if uuid_probe.returncode == 0
        else None
    )
    return {
        "partition": partition,
        "parent": disk.get("path"),
        "mount_source": mount_source,
        "mount_target": expected_target,
        "filesystem_type": mount_type,
        "filesystem_uuid_observed": current_uuid,
        "physical_identity_used_as_business_authority": False,
        "mount_options": sorted(options),
    }


def verify_transaction(plan):
    transaction = read_object(TX_PATH)
    if (
        transaction.get("phase") != "U5_INSTALL_REQUESTED_REVALIDATING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
    ):
        raise Stop("u5_transaction_invalid")
    if transaction.get("current_image_ref") != plan["current_image_ref"]:
        raise Stop("predecessor_image_ref_drift")
    current_identity = transaction.get("current_image_identity")
    if (
        not isinstance(current_identity, dict)
        or current_identity.get("runtime_image_id")
        != plan["current_runtime_image_id"]
        or current_identity.get("platform") != "linux/arm64"
    ):
        raise Stop("predecessor_transaction_identity_drift")
    target_identity = transaction.get("target_artifact_identity")
    if not isinstance(target_identity, dict):
        raise Stop("target_artifact_identity_missing")
    digest = sha_file(TX_PATH)
    if digest != plan["transaction_sha256"]:
        raise Stop("u5_transaction_sha256_drift")
    return transaction, digest


def verify_usb_content(plan, transaction, media):
    root = Path(media["mount_target"]) / "n3w-update"
    target = root / "target" / "homeassistant-arm64.tar.gz"
    if target.is_symlink() or not target.is_file():
        raise Stop("target_archive_missing")
    if target.stat().st_size != plan["target_size_bytes"]:
        raise Stop("target_archive_size_drift")
    if sha_file(target) != plan["target_sha256"]:
        raise Stop("target_archive_sha256_drift")

    tx_root = root / "transaction"
    manifest = read_object(tx_root / "manifest.json")
    phase = read_object(tx_root / "phase.json")
    content = read_object(tx_root / "content-authority.json")
    if (
        manifest.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or phase.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or phase.get("phase") != transaction["phase"]
        or content.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or content.get("target_artifact_identity")
        != transaction.get("target_artifact_identity")
        or content.get("predecessor_recovery_identity") is not None
        or content.get("ha_data_backup_identity") is not None
        or content.get("recovery_content_manifest_sha256") is not None
    ):
        raise Stop("usb_content_authority_drift")

    predecessor_dir = root / "predecessor"
    predecessor_entries = []
    if predecessor_dir.exists() or predecessor_dir.is_symlink():
        if predecessor_dir.is_symlink() or not predecessor_dir.is_dir():
            raise Stop("unexpected_u6_predecessor_path")
        predecessor_entries = sorted(item.name for item in predecessor_dir.iterdir())
        if predecessor_entries:
            raise Stop("unexpected_u6_predecessor_residue")

    return {
        "target_size_bytes": target.stat().st_size,
        "target_sha256": plan["target_sha256"],
        "transaction_phase": phase.get("phase"),
        "target_identity_exact": True,
        "predecessor_recovery_identity": None,
        "ha_data_backup_identity": None,
        "predecessor_directory_entries": predecessor_entries,
    }


def verify_r23_terminal(plan):
    claim = read_object(R23_ROOT / "authorization_claim.json")
    if (
        claim.get("authorization_id") != plan["r23_gate_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
    ):
        raise Stop("r23_authorization_claim_invalid")
    if (R23_ROOT / "failure.json").exists():
        raise Stop("r23_failure_residue_present")
    if (R23_ROOT / "postsuccess_cleanup_failure.json").exists():
        raise Stop("r23_postsuccess_cleanup_failure_present")
    return {
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
    }


def verify_sources(plan):
    observed = {}
    for path, expected in plan["installed_source_sha256"].items():
        digest = sha_file(path)
        if digest != expected:
            raise Stop("installed_source_drift:" + Path(path).name)
        observed[path] = digest
    install_path = Path(
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_install.py"
    )
    if install_path.exists() or install_path.is_symlink():
        raise Stop("u6_install_source_unexpectedly_present")
    return observed


def ipc_status(manager_id):
    probe = r"""import json,socket
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(10)
s.connect("/run/n3w/t1-ota/ha-ota.sock")
s.sendall(json.dumps({"schema":"gh.n3w-t1-ha-ota-ipc-request/1","operation":"status"},sort_keys=True,separators=(",",":")).encode()+b"\n")
s.shutdown(socket.SHUT_WR)
print(s.recv(8192).decode().strip())"""
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
        raise Stop("ipc_status_unavailable:" + str(completed.returncode))
    try:
        value = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as error:
        raise Stop("ipc_status_invalid") from error
    if (
        not isinstance(value, dict)
        or value.get("accepted") is not True
        or value.get("phase") != "INSTALL_REQUESTED_REVALIDATING"
        or value.get("error_code") is not None
        or value.get("installed_version") != "2026.10.0"
    ):
        raise Stop("ipc_not_u5_ready")
    return value


def main():
    try:
        plan = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U6_PREDECESSOR_RECOVERY_READONLY_PREFLIGHT_R24_20261114_01"
        ):
            raise Stop("gate_id_invalid")

        r23 = verify_r23_terminal(plan)
        transaction, transaction_sha256 = verify_transaction(plan)
        sources = verify_sources(plan)

        units = {
            "host": require_healthy_unit(HOST_UNIT, "host"),
            "services_owner": require_healthy_unit(
                SERVICES_UNIT,
                "services_owner",
            ),
            "broker_owner": require_healthy_unit(
                BROKER_UNIT,
                "broker_owner",
            ),
        }
        media = resolve_content_authority_media(plan)
        content = verify_usb_content(plan, transaction, media)

        containers = {}
        for name, expected in plan["containers"].items():
            observed = docker_view(expected["image"])
            if (
                observed["runtime_image_id"]
                != expected["runtime_image_id"]
                or observed["status"] != "running"
                or observed["restart_count"] != 0
            ):
                raise Stop("container_drift:" + name)
            containers[name] = observed

        exact_ha = exact_homeassistant_container()
        if (
            exact_ha["runtime_image_id"]
            != plan["current_runtime_image_id"]
            or exact_ha["configured_image_ref"]
            != plan["current_image_ref"]
            or exact_ha["status"] != "running"
            or exact_ha["restart_count"] != 0
            or exact_ha["container_id"]
            != containers["homeassistant"]["container_id"]
        ):
            raise Stop("homeassistant_predecessor_runtime_drift")

        ipc = ipc_status(containers["manager"]["container_id"])

        result = {
            "schema": "gh.n3w-t1-u6-predecessor-recovery-readonly-preflight/1",
            "status": "PASS",
            "read_only": True,
            "u6_readonly_preflight_pass": True,
            "u6_source_activation_eligible": True,
            "u6_live_transition_eligible": False,
            "live_execution_authorized": False,
            "r23_terminal": r23,
            "transaction_phase": transaction["phase"],
            "transaction_sha256": transaction_sha256,
            "installed_source_sha256": sources,
            "units": units,
            "media": media,
            "content_authority": content,
            "containers": containers,
            "homeassistant_predecessor": exact_ha,
            "ipc": ipc,
            "physical_identity_used_as_business_authority": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "source_deployment": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "usb_transaction_metadata_mutation": False,
            "service_restart": False,
            "homeassistant_mutation": False,
            "manager_mutation": False,
            "broker_mutation": False,
            "u6_transition": False,
            "u7_plus": False,
            "board_access": False,
            "merge": False,
        }
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-u6-predecessor-recovery-readonly-preflight/1",
            "status": "STOP",
            "read_only": True,
            "reason": type(error).__name__ + ":" + str(error)[:240],
            "u6_readonly_preflight_pass": False,
            "u6_source_activation_eligible": False,
            "u6_live_transition_eligible": False,
            "live_execution_authorized": False,
            "physical_identity_used_as_business_authority": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "source_deployment": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "usb_transaction_metadata_mutation": False,
            "service_restart": False,
            "u6_transition": False,
            "u7_plus": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


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
        "n3w_u6_r24_transport",
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
        "schema": "gh.n3w-t1-u6-predecessor-recovery-readonly-preflight-local/1",
        "status": "STOP",
        "read_only_preflight": True,
        "t1_access": False,
        "live_execution_authorized": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "remote_staging": False,
        "source_deployment": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_restart": False,
        "u6_transition": False,
        "u7_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    try:
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
                remote.get("reason")
                if isinstance(remote, dict)
                else "remote_preflight_stop"
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
