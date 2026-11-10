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
    "U3_BOUND_MEDIA_RECOVERY_TO_U4_20261110_01"
)
CONFIRMATION = "EXECUTE KF147 U3 BOUND MEDIA RECOVERY TO U4: YES"

REMOTE_SCRIPT = r"""
import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
PREPARE_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-prepare.json")
SERVICE = "n3w-t1-ha-ota.service"
STATE_ROOT_PARENT = Path("/var/lib/n3w-t1-core-updater")
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
        raise Stop(
            "command_failed:"
            + Path(argv[0]).name
            + ":"
            + str(result.returncode)
        )
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


def read_json(path, schema):
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
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise Stop("state_schema_invalid:" + path.name)
    return doc


def durable_json(path, value):
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(fd, "wb", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


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

    raw_parent = run(
        ["lsblk", "--noheadings", "--paths", "--output", "PKNAME", partition],
        timeout=30,
    ).stdout.strip()
    if not raw_parent.startswith("/dev/"):
        raise Stop("bound_parent_invalid")

    doc = lsblk_doc()
    disks = [
        item
        for item in doc["blockdevices"]
        if isinstance(item, dict)
        and item.get("type") == "disk"
        and item.get("path") == raw_parent
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

    part_nodes = [
        item for item in flatten([disk]) if item.get("path") == partition
    ]
    if len(part_nodes) != 1:
        raise Stop("bound_partition_inventory_invalid")
    mounted = [
        item
        for item in (part_nodes[0].get("mountpoints") or [])
        if isinstance(item, str) and item.startswith("/")
    ]
    return {
        "partition": partition,
        "parent": raw_parent,
        "uuid": uuid.lower(),
        "current_partition_mountpoints": mounted,
    }


def mount_view(target):
    result = run(
        ["findmnt", "--noheadings", "--output", "SOURCE,TARGET", "--target", target],
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        return None
    line = result.stdout.strip()
    if not line:
        return None
    fields = line.split()
    if len(fields) < 2:
        raise Stop("runtime_mount_view_invalid")
    return {"source": fields[0], "target": fields[-1]}


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


def validate_preflight(plan):
    live = plan["live"]
    tx = read_json(TX_PATH, TX_SCHEMA)
    prep = read_json(PREPARE_PATH, PREPARE_SCHEMA)
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

    media = bound_partition(tx, live)
    if media["current_partition_mountpoints"]:
        raise Stop("bound_partition_mounted_unexpectedly")

    mount_target = (
        "/run/n3w-t1-ota/media/"
        + live["transaction_id_sha256"][:16]
    )
    mounted = mount_view(mount_target)
    if mounted is not None:
        if mounted["target"] != mount_target:
            raise Stop("runtime_mount_target_drift")
        if mounted["source"] == media["partition"]:
            raise Stop("current_bound_partition_already_mounted")
        live_paths = {
            item.get("path")
            for item in flatten(lsblk_doc()["blockdevices"])
            if isinstance(item.get("path"), str)
        }
        if mounted["source"] in live_paths:
            raise Stop("runtime_mount_source_still_live")

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

    return {
        "transaction_sha256": sha_file(TX_PATH),
        "prepare_sha256": sha_file(PREPARE_PATH),
        "phase": tx["phase"],
        "media": media,
        "mount_target": mount_target,
        "stale_mount": mounted,
        "service": service,
        "containers": containers,
    }


def target_view(plan):
    live = plan["live"]
    tx = read_json(TX_PATH, TX_SCHEMA)
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
    target_mount = run(
        ["findmnt", "--noheadings", "--output", "TARGET", "--source", partition],
        timeout=30,
    ).stdout.strip()
    expected_mount = "/run/n3w-t1-ota/media/" + live["transaction_id_sha256"][:16]
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


def execute(plan, authorization, confirmation, mode):
    pre = validate_preflight(plan)
    if mode == "preflight":
        return {
            "schema": "gh.n3w-t1-kf147-u3-bound-media-recovery/1",
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
    if (
        authorization != plan["authorization_id"]
        or confirmation != plan["confirmation"]
    ):
        raise Stop("recovery_authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("recovery_authorization_state_root_exists")
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
        "schema": "gh.n3w-t1-kf147-u3-bound-media-recovery/1",
        "status": "STOP",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "stale_mount_unmounted": False,
        "service_restarted": False,
        "u4_ready": False,
        "u5_plus": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "manual_recovery_required": True,
        "first_failed_operation": None,
    }

    try:
        postclaim = validate_preflight(plan)
        durable_json(state_root / "postclaim.json", postclaim)

        stale = postclaim.get("stale_mount")
        if stale is not None:
            run(["umount", postclaim["mount_target"]], timeout=45)
            result["stale_mount_unmounted"] = True
            if mount_view(postclaim["mount_target"]) is not None:
                raise Stop("stale_runtime_mount_persisted")

        run(["systemctl", "restart", SERVICE], timeout=60)
        result["service_restarted"] = True

        deadline = time.monotonic() + plan["poll_timeout_seconds"]
        last = None
        while time.monotonic() < deadline:
            tx = read_json(TX_PATH, TX_SCHEMA)
            service = systemd_state()
            last = {
                "transaction_phase": tx.get("phase"),
                "transaction_status": tx.get("status"),
                "service": service,
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
                durable_json(state_root / "post.json", post)
                result.update(
                    {
                        "status": "PASS",
                        "u4_ready": True,
                        "manual_recovery_required": False,
                        "target_artifact_verified": True,
                        "containers_preserved": True,
                        "post": post,
                    }
                )
                durable_json(state_root / "result.json", result)
                return result
            if tx.get("phase") != U3 or tx.get("status") != "ACTIVE":
                raise Stop("unexpected_recovery_transaction_state")
            if service.get("ActiveState") != "active":
                raise Stop("ha_ota_service_not_active_after_restart")
            time.sleep(2)

        result["last_observed"] = last
        raise Stop("u3_recovery_timeout")
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        try:
            durable_json(state_root / "failure.json", result)
        except Exception:
            pass
        return result


def main():
    if len(sys.argv) != 5:
        print(json.dumps({"status": "STOP", "reason": "arguments_invalid"}))
        return 2
    try:
        plan = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
            "U3_BOUND_MEDIA_RECOVERY_TO_U4_20261110_01"
        ):
            raise Stop("gate_id_invalid")
        result = execute(plan, sys.argv[2], sys.argv[3], sys.argv[4])
    except Exception as error:
        result = {
            "status": "STOP",
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
    return run(["git", "-C", str(REPO_ROOT), *args], timeout=30).stdout.strip()


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
        != "gh.n3w-t1-kf147-u3-bound-media-recovery-manifest/1"
        or manifest.get("gate_id") != GATE_ID
        or manifest.get("authorization_id") != GATE_ID
        or manifest.get("confirmation") != CONFIRMATION
    ):
        raise Stop("manifest_contract_invalid")
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
        "n3w_t1_ssh_transport_kf147_u3_recovery",
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


def remote_call(transport: Any, plan: dict[str, Any], authorization: str, confirmation: str, mode: str):
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
        "schema": "gh.n3w-t1-kf147-u3-bound-media-recovery-local-result/1",
        "status": "STOP",
        "gate_id": GATE_ID,
        "t1_access": False,
        "read_only_preflight": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "usb_reformat": False,
        "destructive_confirmation_replay": False,
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
            "authorization_id": manifest["authorization_id"],
            "confirmation": manifest["confirmation"],
            "live_execution_authorized": manifest["live_execution_authorized"],
            "authorization_state": manifest["authorization_state"],
            "state_root": manifest["state_root"],
            "poll_timeout_seconds": manifest["poll_timeout_seconds"],
            "live": manifest["expected_live_entry"],
            "containers": manifest["expected_containers"],
        }
        mode = "preflight" if args.preflight_only else "execute"
        authorization = "" if args.preflight_only else args.authorization_id
        confirmation = "" if args.preflight_only else args.confirm
        returncode, remote = remote_call(
            transport, plan, authorization, confirmation, mode
        )
        write_private(evidence_root / "result.json", remote)
        result["remote_returncode"] = returncode
        if returncode != 0 or remote.get("status") != "PASS":
            result["first_failed_operation"] = (
                remote.get("reason")
                or remote.get("first_failed_operation")
                or "remote_recovery_stop"
            )
            result["authorization_claimed"] = bool(
                remote.get("authorization_claimed")
            )
            result["authorization_consumed"] = bool(
                remote.get("authorization_consumed")
            )
            return result

        result.update(remote)
        result["t1_access"] = True
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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight-only", action="store_true")
    group.add_argument("--execute", action="store_true")
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
