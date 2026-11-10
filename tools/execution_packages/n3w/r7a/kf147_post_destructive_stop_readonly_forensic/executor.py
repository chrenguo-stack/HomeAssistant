#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
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

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "POST_DESTRUCTIVE_STOP_READONLY_FORENSIC_20261110_01"
)

REMOTE_SCRIPT = r"""
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
PREPARE_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-prepare.json")
EXECUTION_STATE_ROOT = Path(
    "/var/lib/n3w-t1-core-updater/kf147-usb-confirm-u1-u4-20261110-01"
)
HOST_UNIT = "n3w-t1-ha-ota.service"

TX_SCHEMA = "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
PREPARE_SCHEMA = "gh.n3w-t1-ha-usb-prepare-state/1"

U1 = "U1_PREPARE_REQUESTED"
U2 = "U2_USB_QUALIFIED_FORMATTED_BOUND"
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
        raise Stop(
            "command_failed:"
            + Path(argv[0]).name
            + ":"
            + str(result.returncode)
        )
    return result


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_private_json(path, expected_schema=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("file_invalid:" + str(path))
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise Stop("file_metadata_invalid:" + str(path))
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("json_invalid:" + path.name) from error
    if not isinstance(value, dict):
        raise Stop("json_shape_invalid:" + path.name)
    if expected_schema is not None and value.get("schema") != expected_schema:
        raise Stop("json_schema_invalid:" + path.name)
    return value


def optional_private_json(path):
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        return None
    value = read_private_json(path)
    return {
        "sha256": sha_file(path),
        "document": value,
    }


def parse_properties(text):
    result = {}
    for line in text.splitlines():
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
        return {
            "image": image,
            "cardinality": len(ids),
            "container_id": ids[0] if len(ids) == 1 else None,
        }
    try:
        docs = json.loads(
            run(["docker", "inspect", ids[0]], timeout=45).stdout
        )
    except Exception:
        return {
            "image": image,
            "cardinality": 1,
            "container_id": ids[0],
            "inspect_valid": False,
        }
    if not isinstance(docs, list) or len(docs) != 1 or not isinstance(docs[0], dict):
        return {
            "image": image,
            "cardinality": 1,
            "container_id": ids[0],
            "inspect_valid": False,
        }
    item = docs[0]
    state = item.get("State") if isinstance(item.get("State"), dict) else {}
    return {
        "image": image,
        "cardinality": 1,
        "container_id": item.get("Id"),
        "runtime_image_id": item.get("Image"),
        "status": state.get("Status"),
        "started_at": state.get("StartedAt"),
        "restart_count": item.get("RestartCount"),
    }


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


def blkid_export(path):
    result = run(["blkid", "-o", "export", path], check=False, timeout=30)
    if result.returncode != 0:
        return None
    return parse_properties(result.stdout)


def target_artifact_view(tx, lsblk_doc):
    filesystem_uuid = tx.get("usb_filesystem_uuid")
    if not isinstance(filesystem_uuid, str) or not filesystem_uuid:
        return {"available": False, "reason": "filesystem_uuid_missing"}

    nodes = flatten(lsblk_doc.get("blockdevices") or [])
    matching = [
        node
        for node in nodes
        if str(node.get("uuid") or "").lower() == filesystem_uuid.lower()
    ]
    if len(matching) != 1:
        return {
            "available": False,
            "reason": "filesystem_uuid_not_uniquely_visible",
            "matching_nodes": len(matching),
        }
    node = matching[0]
    mountpoints = node.get("mountpoints")
    if not isinstance(mountpoints, list):
        mountpoints = []
    mounted = [
        item for item in mountpoints if isinstance(item, str) and item.startswith("/")
    ]
    if len(mounted) != 1:
        return {
            "available": False,
            "reason": "bound_filesystem_not_uniquely_mounted",
            "device_path": node.get("path"),
            "mountpoints": mounted,
        }
    target = (
        Path(mounted[0])
        / "n3w-update"
        / "target"
        / "homeassistant-arm64.tar.gz"
    )
    if target.is_symlink() or not target.is_file():
        return {
            "available": False,
            "reason": "target_archive_not_present",
            "device_path": node.get("path"),
            "mountpoint": mounted[0],
        }
    return {
        "available": True,
        "device_path": node.get("path"),
        "mountpoint": mounted[0],
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "sha256": sha_file(target),
    }


def classify(tx, prep, lsblk_doc):
    phase = tx.get("phase")
    confirmation_consumed = prep.get("confirmation_consumed")
    nodes = flatten(lsblk_doc.get("blockdevices") or [])
    formatted = [
        {
            "path": node.get("path"),
            "type": node.get("type"),
            "fstype": node.get("fstype"),
            "label": node.get("label"),
            "uuid": node.get("uuid"),
            "mountpoints": node.get("mountpoints"),
        }
        for node in nodes
        if (
            node.get("fstype") == "ext4"
            and node.get("label") == "N3W-UPDATE"
        )
    ]
    if phase == U4:
        state = "DURABLE_U4"
    elif phase == U3:
        state = "DURABLE_U3"
    elif phase == U2:
        state = "DURABLE_U2"
    elif phase == U1 and confirmation_consumed is True:
        state = "POST_CONFIRM_PRE_U2"
    elif phase == U1:
        state = "U1_NOT_CONSUMED"
    else:
        state = "UNEXPECTED_PHASE"

    destructive_effect = phase in {U2, U3, U4} or bool(formatted)
    return {
        "durable_state": state,
        "destructive_effect_observed": destructive_effect,
        "formatted_n3w_update_filesystems": formatted,
        "same_authorization_replay_permitted": False,
    }


def main():
    try:
        plan = json.loads(
            __import__("base64").b64decode(sys.argv[1]).decode("utf-8")
        )
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
            "POST_DESTRUCTIVE_STOP_READONLY_FORENSIC_20261110_01"
        ):
            raise Stop("gate_id_invalid")

        tx = read_private_json(TX_PATH, TX_SCHEMA)
        prep = read_private_json(PREPARE_PATH, PREPARE_SCHEMA)

        service = parse_properties(
            run(
                [
                    "systemctl",
                    "show",
                    HOST_UNIT,
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

        lsblk_raw = run(
            [
                "lsblk",
                "--json",
                "--bytes",
                "--paths",
                "--output",
                "NAME,PATH,TYPE,SIZE,MODEL,RM,RO,TRAN,FSTYPE,LABEL,UUID,MOUNTPOINTS,PKNAME",
            ],
            timeout=45,
        ).stdout
        try:
            lsblk_doc = json.loads(lsblk_raw)
        except json.JSONDecodeError as error:
            raise Stop("lsblk_json_invalid") from error
        if not isinstance(lsblk_doc, dict):
            raise Stop("lsblk_shape_invalid")

        findmnt_result = run(
            [
                "findmnt",
                "--json",
                "--output",
                "SOURCE,TARGET,FSTYPE,OPTIONS",
            ],
            check=False,
            timeout=30,
        )
        try:
            findmnt_doc = (
                json.loads(findmnt_result.stdout)
                if findmnt_result.returncode == 0 and findmnt_result.stdout.strip()
                else None
            )
        except json.JSONDecodeError:
            findmnt_doc = None

        execution_state = {
            name: optional_private_json(EXECUTION_STATE_ROOT / name)
            for name in (
                "preflight.json",
                "authorization_claim.json",
                "postclaim.json",
                "dispatch.json",
                "post.json",
                "failure.json",
                "result.json",
            )
        }

        result = {
            "schema": "gh.n3w-t1-kf147-post-destructive-stop-readonly-forensic/1",
            "status": "PASS",
            "read_only": True,
            "mutation": False,
            "usb_mutation": False,
            "service_restart": False,
            "docker_mutation": False,
            "authorization_replay": False,
            "transaction_sha256": sha_file(TX_PATH),
            "transaction": tx,
            "prepare_sha256": sha_file(PREPARE_PATH),
            "prepare": prep,
            "execution_state": execution_state,
            "host_service": service,
            "containers": {
                "manager": container_view(plan["live"]["manager_image"]),
                "homeassistant": container_view(plan["live"]["homeassistant_image"]),
                "broker": container_view(plan["live"]["broker_image"]),
            },
            "lsblk": lsblk_doc,
            "findmnt": findmnt_doc,
            "sda_blkid": blkid_export("/dev/sda"),
            "sda1_blkid": blkid_export("/dev/sda1"),
        }
        result["classification"] = classify(tx, prep, lsblk_doc)
        result["target_artifact"] = target_artifact_view(tx, lsblk_doc)
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-kf147-post-destructive-stop-readonly-forensic/1",
            "status": "STOP",
            "read_only": True,
            "mutation": False,
            "usb_mutation": False,
            "service_restart": False,
            "docker_mutation": False,
            "authorization_replay": False,
            "reason": type(error).__name__ + ":" + str(error)[:240],
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


raise SystemExit(main())
"""


class Stop(RuntimeError):
    pass


def run(argv: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop(
            f"local_command_failed:{Path(argv[0]).name}:{completed.returncode}"
        )
    return completed


def git_text(*args: str) -> str:
    return run(
        ["git", "-C", str(REPO_ROOT), *args],
        timeout=30,
    ).stdout.strip()


def read_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("manifest_invalid") from error
    if not isinstance(value, dict):
        raise Stop("manifest_invalid")
    return value


def validate_local(expected_commit: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")

    manifest = read_manifest()
    if (
        manifest.get("schema")
        != "gh.n3w-t1-kf147-post-destructive-stop-readonly-forensic/1"
        or manifest.get("gate_id") != GATE_ID
        or manifest.get("mode") != "READ_ONLY_FORENSIC"
        or manifest.get("predecessor_execution_head")
        != "ff6370c3b9e46e1ddf20409915e1b10dabb6e286"
    ):
        raise Stop("manifest_contract_invalid")

    contract = manifest.get("execution_contract")
    if not isinstance(contract, dict) or contract.get("read_only") is not True:
        raise Stop("manifest_execution_contract_invalid")
    for key in (
        "remote_write",
        "service_restart",
        "docker_mutation",
        "usb_mutation",
        "authorization_replay",
        "u5_plus",
        "board_access",
        "merge",
    ):
        if contract.get(key) is not False:
            raise Stop("manifest_mutation_contract_invalid:" + key)

    authority = manifest.get("package_source_authority")
    if not isinstance(authority, dict):
        raise Stop("package_source_authority_invalid")
    for relative, blob in authority.items():
        if (
            not isinstance(relative, str)
            or not isinstance(blob, str)
            or re.fullmatch(r"[0-9a-f]{40}", blob) is None
            or git_text("rev-parse", f"HEAD:{relative}") != blob
        ):
            raise Stop("package_source_authority_drift:" + str(relative))
    return manifest


def load_transport() -> type:
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_ssh_transport_kf147_forensic",
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


def execute(args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "gh.n3w-t1-kf147-post-destructive-stop-local-result/1",
        "status": "STOP",
        "gate_id": GATE_ID,
        "t1_access": False,
        "read_only": True,
        "remote_write": False,
        "service_restart": False,
        "docker_mutation": False,
        "usb_mutation": False,
        "authorization_replay": False,
        "u5_plus": False,
        "board_access": False,
        "merge": False,
        "first_failed_operation": None,
    }
    transport = None
    try:
        manifest = validate_local(args.expected_package_commit)
        evidence_root = prepare_evidence_root(args.evidence_root)

        transport_type = load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        plan = {
            "gate_id": GATE_ID,
            "live": manifest["expected_live_entry"],
        }
        payload = base64.b64encode(
            json.dumps(
                plan,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii")
        completed = transport.run_remote(
            ["python3", "-c", REMOTE_SCRIPT, payload],
            timeout=300,
            check=False,
        )
        try:
            forensic = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise Stop("remote_result_json_invalid") from error
        if not isinstance(forensic, dict):
            raise Stop("remote_result_shape_invalid")

        write_private(evidence_root / "forensic.json", forensic)
        result["remote_returncode"] = completed.returncode
        if completed.returncode != 0 or forensic.get("status") != "PASS":
            result["first_failed_operation"] = (
                forensic.get("reason") or "remote_forensic_stop"
            )
            return result

        result.update(
            {
                "status": "PASS",
                "forensic": forensic,
            }
        )
        return result
    except Exception as error:
        result["first_failed_operation"] = (
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
    args = parser.parse_args()

    if re.fullmatch(r"[A-Za-z0-9._-]{1,160}", args.execution_id) is None:
        print(json.dumps({"status": "STOP", "reason": "execution_id_invalid"}))
        return 2

    result = execute(args)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
