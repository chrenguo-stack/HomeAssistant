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
READONLY_EXECUTOR_PATH = (
    REPO_ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "kf147_usb_u2_readonly_baseline"
    / "executor.py"
)

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_"
    "USB_CONFIRMATION_U1_U4_DESTRUCTIVE_PREPARE_20261110_01"
)
CONFIRMATION = (
    "EXECUTE KF147 USB CONFIRMATION U1 TO U4 DESTRUCTIVE PREPARE: YES"
)

REMOTE_EXECUTE_SCRIPT = r"""
import base64
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
PREPARE_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-prepare.json")
TX_SCHEMA = "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
PREPARE_SCHEMA = "gh.n3w-t1-ha-usb-prepare-state/1"
IPC_SCHEMA = "gh.n3w-t1-ha-ota-ipc-request/1"
IPC_RESPONSE_V3 = "gh.n3w-t1-ha-ota-ipc-response/3"
U1 = "U1_PREPARE_REQUESTED"
U2 = "U2_USB_QUALIFIED_FORMATTED_BOUND"
U3 = "U3_TARGET_DOWNLOADING_VERIFYING"
U4 = "U4_TARGET_READY"
USB_FLOOR_BYTES = 14 * 1024**3


class Stop(RuntimeError):
    pass


def run(argv, *, check=True, timeout=120):
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


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
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


def durable_json(path, value):
    path = Path(path)
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
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
    fsync_dir(path.parent)


def require_private_regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("file_invalid:" + str(path))
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise Stop("file_metadata_invalid:" + str(path))


def read_json(path, schema):
    path = Path(path)
    require_private_regular(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("json_invalid:" + path.name) from error
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise Stop("json_schema_invalid:" + path.name)
    return value


def docker_one(image, expected_image_id, expected_restart_count):
    ids = [
        line.strip()
        for line in run(
            [
                "docker",
                "ps",
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
        raise Stop("container_cardinality_invalid:" + image + ":" + str(len(ids)))
    try:
        documents = json.loads(run(["docker", "inspect", ids[0]], timeout=45).stdout)
    except json.JSONDecodeError as error:
        raise Stop("container_inspect_invalid:" + image) from error
    if not isinstance(documents, list) or len(documents) != 1:
        raise Stop("container_inspect_invalid:" + image)
    item = documents[0]
    if (
        not isinstance(item, dict)
        or item.get("Config", {}).get("Image") != image
        or item.get("Image") != expected_image_id
        or item.get("State", {}).get("Status") != "running"
        or item.get("RestartCount") != expected_restart_count
    ):
        raise Stop("container_state_invalid:" + image)
    return item


def containers(plan):
    live = plan["live"]
    return {
        "manager": docker_one(
            live["manager_image"],
            live["manager_runtime_image_id"],
            live["manager_restart_count"],
        ),
        "homeassistant": docker_one(
            live["homeassistant_image"],
            live["homeassistant_runtime_image_id"],
            live["homeassistant_restart_count"],
        ),
        "broker": docker_one(
            live["broker_image"],
            live["broker_runtime_image_id"],
            live["broker_restart_count"],
        ),
    }


def critical(plan):
    live = plan["live"]
    tx = read_json(TX_PATH, TX_SCHEMA)
    tx_sha = sha_file(TX_PATH)
    if tx_sha != live["u1_transaction_sha256"]:
        raise Stop("u1_transaction_sha_drift")
    if (
        tx.get("transaction_id_sha256") != live["transaction_id_sha256"]
        or tx.get("phase") != U1
        or tx.get("status") != "ACTIVE"
        or tx.get("authorization_claimed") is not False
        or tx.get("authorization_consumed") is not False
    ):
        raise Stop("u1_transaction_semantics_drift")
    target_identity = tx.get("target_manifest_identity")
    if not isinstance(target_identity, dict):
        raise Stop("u1_target_manifest_identity_invalid")
    if (
        target_identity.get("release_identity") != live["release_identity"]
        or tx.get("current_image_ref") != live["current_image_ref"]
        or tx.get("target_image_ref") != live["target_image_ref"]
        or tx.get("target_archive_sha256") != live["target_archive_sha256"]
        or tx.get("target_archive_size") != live["target_archive_size_bytes"]
    ):
        raise Stop("u1_release_or_target_drift")

    prep = read_json(PREPARE_PATH, PREPARE_SCHEMA)
    if (
        prep.get("transaction_id_sha256") != live["transaction_id_sha256"]
        or prep.get("release_identity") != live["release_identity"]
        or prep.get("baseline_public_fingerprints")
        != live["baseline_public_fingerprints"]
        or prep.get("confirmation_required") is not True
        or prep.get("confirmation_consumed") is not False
    ):
        raise Stop("prepare_binding_drift")
    candidate = prep.get("candidate")
    expected_candidate = {
        "public_fingerprint": live["usb_candidate_public_fingerprint"],
        "display_model": live["usb_candidate_model"],
        "display_capacity_bytes": live["usb_candidate_capacity_bytes"],
    }
    if candidate != expected_candidate:
        raise Stop("prepare_candidate_drift")
    if (
        live["usb_candidate_public_fingerprint"]
        in prep["baseline_public_fingerprints"]
    ):
        raise Stop("prepare_candidate_not_fresh")

    snapshot = prep.get("capacity_snapshot")
    if not isinstance(snapshot, dict):
        raise Stop("capacity_snapshot_missing")
    expected_capacity = {
        "capacity_policy_schema": live["capacity_policy_schema"],
        "target_artifact_bytes": live["target_archive_size_bytes"],
        "predecessor_recovery_budget_bytes": live[
            "predecessor_recovery_budget_bytes"
        ],
        "usb_required_bytes": live["usb_required_bytes"],
        "recommended_nominal_usb_gb": live["recommended_nominal_usb_gb"],
    }
    for key, expected in expected_capacity.items():
        if snapshot.get(key) != expected:
            raise Stop("capacity_snapshot_drift:" + key)
    if live["usb_candidate_capacity_bytes"] < max(
        USB_FLOOR_BYTES,
        snapshot["usb_required_bytes"],
    ):
        raise Stop("candidate_capacity_not_plausible")
    return {
        "tx_sha256": tx_sha,
        "prepare_sha256": sha_file(PREPARE_PATH),
        "transaction_id_sha256": tx["transaction_id_sha256"],
        "release_identity": live["release_identity"],
        "candidate": expected_candidate,
        "capacity_snapshot": snapshot,
    }


def ipc(container_id, request):
    payload = base64.b64encode(
        json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    ).decode("ascii")
    probe = (
        "import base64,json,socket,sys\n"
        "p='/run/n3w/t1-ota/ha-ota.sock'\n"
        "q=base64.b64decode(sys.argv[1])\n"
        "s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);"
        "s.settimeout(10);s.connect(p);s.sendall(q);s.shutdown(socket.SHUT_WR)\n"
        "d=bytearray()\n"
        "while len(d)<=8192:\n"
        " b=s.recv(1024)\n"
        " if not b: break\n"
        " d.extend(b)\n"
        " if b'\\n' in d: break\n"
        "s.close();print(bytes(d).split(b'\\n',1)[0].decode())\n"
    )
    raw = run(
        [
            "docker",
            "exec",
            "-u",
            "999:999",
            container_id,
            "python3",
            "-c",
            probe,
            payload,
        ],
        timeout=45,
    ).stdout.strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise Stop("manager_ipc_json_invalid") from error
    if not isinstance(value, dict):
        raise Stop("manager_ipc_shape_invalid")
    return value


def require_status_ready(status, plan):
    live = plan["live"]
    candidate = status.get("usb_candidate")
    if (
        status.get("schema") != IPC_RESPONSE_V3
        or status.get("accepted") is not True
        or status.get("phase") != "USB_REQUIRED_CONFIRMATION"
        or status.get("usb_confirmation_required") is not True
        or status.get("usb_capacity_check_state")
        != "CANDIDATE_READY_FOR_CONFIRMATION"
        or status.get("user_message_code_or_null") != "USB_CONFIRM_ERASE"
        or status.get("usb_required_bytes_or_null") != live["usb_required_bytes"]
        or status.get("usb_recommended_nominal_gb_or_null")
        != live["recommended_nominal_usb_gb"]
        or not isinstance(candidate, dict)
        or candidate.get("public_fingerprint")
        != live["usb_candidate_public_fingerprint"]
        or candidate.get("display_model") != live["usb_candidate_model"]
        or candidate.get("display_capacity_bytes")
        != live["usb_candidate_capacity_bytes"]
    ):
        raise Stop("manager_ipc_not_ready_for_confirmation")


def post_u4(plan, pre_containers):
    live = plan["live"]
    tx = read_json(TX_PATH, TX_SCHEMA)
    if (
        tx.get("transaction_id_sha256") != live["transaction_id_sha256"]
        or tx.get("phase") != U4
        or tx.get("status") != "ACTIVE"
        or tx.get("target_artifact_verified") is not True
        or tx.get("usb_capacity_verified") is not True
        or tx.get("usb_device_identity_public_fingerprint")
        != live["usb_candidate_public_fingerprint"]
        or tx.get("authorization_claimed") is not False
        or tx.get("authorization_consumed") is not False
    ):
        raise Stop("u4_transaction_validation_failed")
    filesystem_uuid = tx.get("usb_filesystem_uuid")
    if (
        not isinstance(filesystem_uuid, str)
        or not 8 <= len(filesystem_uuid) <= 64
    ):
        raise Stop("u4_filesystem_uuid_invalid")
    measured = tx.get("usb_measured_usable_bytes")
    if type(measured) is not int or measured < USB_FLOOR_BYTES:
        raise Stop("u4_measured_capacity_invalid")

    prep = read_json(PREPARE_PATH, PREPARE_SCHEMA)
    if (
        prep.get("transaction_id_sha256") != live["transaction_id_sha256"]
        or prep.get("release_identity") != live["release_identity"]
        or prep.get("confirmation_required") is not False
        or prep.get("confirmation_consumed") is not True
    ):
        raise Stop("u4_prepare_confirmation_state_invalid")

    current_containers = containers(plan)
    for key in ("manager", "homeassistant", "broker"):
        if current_containers[key].get("Id") != pre_containers[key].get("Id"):
            raise Stop("container_continuity_failed:" + key)

    status = ipc(
        pre_containers["manager"]["Id"],
        {"schema": IPC_SCHEMA, "operation": "status"},
    )
    if (
        status.get("schema") != IPC_RESPONSE_V3
        or status.get("accepted") is not True
        or status.get("phase") != "READY_TO_INSTALL"
        or status.get("error_code") is not None
    ):
        raise Stop("u4_ipc_projection_invalid")

    partition = run(
        ["blkid", "-U", filesystem_uuid],
        timeout=30,
    ).stdout.strip()
    if not partition.startswith("/dev/"):
        raise Stop("u4_partition_unresolved")
    mount_path = run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "TARGET",
            "--source",
            partition,
        ],
        timeout=30,
    ).stdout.strip()
    if not mount_path.startswith("/"):
        raise Stop("u4_mount_unresolved")
    target = (
        Path(mount_path)
        / "n3w-update"
        / "target"
        / "homeassistant-arm64.tar.gz"
    )
    if target.is_symlink() or not target.is_file():
        raise Stop("u4_target_artifact_missing")
    if target.stat().st_size != live["target_archive_size_bytes"]:
        raise Stop("u4_target_artifact_size_drift")
    if sha_file(target) != live["target_archive_sha256"]:
        raise Stop("u4_target_artifact_sha_drift")

    return {
        "transaction_sha256": sha_file(TX_PATH),
        "prepare_sha256": sha_file(PREPARE_PATH),
        "phase": tx["phase"],
        "target_artifact_verified": True,
        "usb_capacity_verified": True,
        "usb_device_identity_public_fingerprint": tx[
            "usb_device_identity_public_fingerprint"
        ],
        "usb_filesystem_uuid": filesystem_uuid,
        "usb_measured_usable_bytes": measured,
        "target_artifact_path": str(target),
        "target_archive_sha256": live["target_archive_sha256"],
        "target_archive_size_bytes": live["target_archive_size_bytes"],
        "manager_ipc": status,
        "containers_preserved": True,
        "prepare_confirmation_consumed": True,
    }


def execute(plan, authorization, confirmation):
    if (
        plan.get("live_execution_authorized") is not True
        or plan.get("authorization_state") != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("live_execution_not_authorized")
    if (
        authorization != plan["authorization_id"]
        or confirmation != plan["confirmation"]
    ):
        raise Stop("authorization_or_confirmation_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("authorization_state_root_exists")

    pre = critical(plan)
    pre_containers = containers(plan)
    manager_id = pre_containers["manager"]["Id"]
    status = ipc(
        manager_id,
        {"schema": IPC_SCHEMA, "operation": "status"},
    )
    require_status_ready(status, plan)

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
            "release_identity": plan["live"]["release_identity"],
            "usb_candidate_public_fingerprint": plan["live"][
                "usb_candidate_public_fingerprint"
            ],
        },
    )

    result = {
        "schema": "gh.n3w-t1-kf147-usb-confirm-u1-u4-result/1",
        "status": "STOP",
        "authorization_id": plan["authorization_id"],
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "destructive_submit_accepted": False,
        "usb_mutation_possible": False,
        "u2_plus": False,
        "u4_ready": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "automatic_retry": False,
        "rollback_attempted": False,
        "manual_recovery_required": False,
        "first_failed_operation": None,
    }

    try:
        postclaim = critical(plan)
        status = ipc(
            manager_id,
            {"schema": IPC_SCHEMA, "operation": "status"},
        )
        require_status_ready(status, plan)
        durable_json(state_root / "postclaim.json", postclaim)

        submit = ipc(
            manager_id,
            {
                "schema": IPC_SCHEMA,
                "operation": "submit",
                "action": "CONFIRM_USB_ERASE",
                "target_release_id": plan["live"]["release_identity"],
            },
        )
        durable_json(state_root / "dispatch.json", submit)
        if (
            submit.get("schema") != IPC_RESPONSE_V3
            or submit.get("accepted") is not True
            or submit.get("code") != "accepted"
            or submit.get("phase") != "TARGET_DOWNLOADING_VERIFYING"
        ):
            raise Stop("destructive_submit_rejected")
        result["destructive_submit_accepted"] = True
        result["usb_mutation_possible"] = True

        deadline = time.monotonic() + plan["poll_timeout_seconds"]
        last = None
        while time.monotonic() < deadline:
            tx = read_json(TX_PATH, TX_SCHEMA)
            phase = tx.get("phase")
            status = ipc(
                manager_id,
                {"schema": IPC_SCHEMA, "operation": "status"},
            )
            last = {
                "transaction_phase": phase,
                "transaction_status": tx.get("status"),
                "ipc_phase": status.get("phase"),
                "ipc_error_code": status.get("error_code"),
            }
            if phase == U4:
                post = post_u4(plan, pre_containers)
                durable_json(state_root / "post.json", post)
                result.update(
                    {
                        "status": "PASS",
                        "usb_mutation_possible": True,
                        "u2_plus": True,
                        "u4_ready": True,
                        "target_artifact_verified": True,
                        "containers_preserved": True,
                        "manual_recovery_required": False,
                        "post": post,
                    }
                )
                durable_json(state_root / "result.json", result)
                return result
            if phase not in {U1, U2, U3}:
                raise Stop("unexpected_transaction_phase:" + str(phase))
            if status.get("phase") == "ERROR":
                raise Stop(
                    "prepare_worker_error:"
                    + str(status.get("error_code") or "unknown")
                )
            time.sleep(2.0)

        result["last_observed"] = last
        raise Stop("u4_wait_timeout")
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        result["manual_recovery_required"] = bool(
            result["authorization_consumed"]
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
            "USB_CONFIRMATION_U1_U4_DESTRUCTIVE_PREPARE_20261110_01"
        ):
            raise Stop("gate_id_invalid")
        result = execute(plan, sys.argv[2], sys.argv[3])
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


def run(
    argv: list[str],
    *,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
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


def load_readonly_executor() -> Any:
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_kf147_usb_u2_readonly_baseline_executor_inherited",
        READONLY_EXECUTOR_PATH,
    )
    if spec is None or spec.loader is None:
        raise Stop("readonly_executor_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_local(expected_commit: str) -> tuple[dict[str, Any], Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text(
        "status",
        "--porcelain",
        "--untracked-files=no",
    ):
        raise Stop("tracked_worktree_dirty")

    manifest = read_manifest()
    if (
        manifest.get("schema")
        != "gh.n3w-t1-kf147-usb-confirm-u1-u4-successor/1"
        or manifest.get("gate_id") != GATE_ID
        or manifest.get("authorization_id") != GATE_ID
        or manifest.get("confirmation") != CONFIRMATION
    ):
        raise Stop("manifest_contract_invalid")

    package_authority = manifest.get("package_source_authority")
    if not isinstance(package_authority, dict):
        raise Stop("package_source_authority_invalid")
    for relative, blob in package_authority.items():
        if (
            not isinstance(relative, str)
            or not isinstance(blob, str)
            or re.fullmatch(r"[0-9a-f]{40}", blob) is None
            or git_text("rev-parse", f"HEAD:{relative}") != blob
        ):
            raise Stop("package_source_authority_drift:" + str(relative))

    readonly = load_readonly_executor()
    readonly.validate_local(expected_commit)
    inherited = manifest.get("inherited_readonly_authority")
    if not isinstance(inherited, dict):
        raise Stop("inherited_readonly_authority_invalid")
    for relative, blob in inherited.items():
        if git_text("rev-parse", f"HEAD:{relative}") != blob:
            raise Stop("inherited_readonly_authority_drift:" + relative)
    return manifest, readonly


def validate_baseline(
    baseline: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    live = manifest["expected_live_entry"]
    if (
        baseline.get("status") != "PASS"
        or baseline.get("read_only") is not True
        or baseline.get("mutation") is not False
        or baseline.get("transaction_phase") != "U1_PREPARE_REQUESTED"
        or baseline.get("transaction_status") != "ACTIVE"
        or baseline.get("u1_transaction_sha256")
        != live["u1_transaction_sha256"]
        or baseline.get("transaction_id_sha256")
        != live["transaction_id_sha256"]
        or baseline.get("release_identity") != live["release_identity"]
        or baseline.get("prepare_release_identity")
        != live["release_identity"]
        or baseline.get("baseline_public_fingerprints")
        != live["baseline_public_fingerprints"]
        or baseline.get("candidate_fresh_relative_to_u1_baseline")
        is not True
        or baseline.get("usb_confirmation_required") is not True
        or baseline.get("usb_confirmation_consumed") is not False
    ):
        raise Stop("inherited_baseline_semantics_drift")

    candidate = baseline.get("usb_candidate")
    expected_candidate = {
        "public_fingerprint": live["usb_candidate_public_fingerprint"],
        "display_model": live["usb_candidate_model"],
        "display_capacity_bytes": live["usb_candidate_capacity_bytes"],
    }
    if candidate != expected_candidate:
        raise Stop("inherited_candidate_drift")
    physical = baseline.get("physical_usb_candidate")
    if (
        not isinstance(physical, dict)
        or physical.get("public_fingerprint")
        != live["usb_candidate_public_fingerprint"]
        or physical.get("display_model") != live["usb_candidate_model"]
        or physical.get("display_capacity_bytes")
        != live["usb_candidate_capacity_bytes"]
        or physical.get("removable") is not True
        or physical.get("mass_storage") is not True
        or physical.get("read_only") is not False
        or physical.get("is_root_device") is not False
        or physical.get("backs_production_mount") is not False
    ):
        raise Stop("inherited_physical_usb_drift")

    snapshot = baseline.get("capacity_snapshot")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("capacity_policy_schema")
        != live["capacity_policy_schema"]
        or snapshot.get("target_artifact_bytes")
        != live["target_archive_size_bytes"]
        or snapshot.get("predecessor_recovery_budget_bytes")
        != live["predecessor_recovery_budget_bytes"]
        or snapshot.get("usb_required_bytes") != live["usb_required_bytes"]
        or snapshot.get("recommended_nominal_usb_gb")
        != live["recommended_nominal_usb_gb"]
    ):
        raise Stop("inherited_capacity_snapshot_drift")

    for label in ("manager", "homeassistant", "broker"):
        view = baseline.get(label)
        if (
            not isinstance(view, dict)
            or view.get("status") != "running"
            or view.get("restart_count") != live[f"{label}_restart_count"]
        ):
            raise Stop("inherited_container_continuity_drift:" + label)


def build_plan(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate_id": GATE_ID,
        "authorization_id": manifest["authorization_id"],
        "confirmation": manifest["confirmation"],
        "live_execution_authorized": manifest["live_execution_authorized"],
        "authorization_state": manifest["authorization_state"],
        "state_root": manifest["state_root"],
        "poll_timeout_seconds": manifest["poll_timeout_seconds"],
        "live": manifest["expected_live_entry"],
    }


def check_state_root_absent(transport: Any, state_root: str) -> None:
    observed = transport.run_remote(
        ["test", "-e", state_root],
        check=False,
        timeout=30,
    )
    if observed.returncode == 0:
        raise Stop("authorization_state_root_exists")
    if observed.returncode != 1:
        raise Stop("authorization_state_root_probe_failed")


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


def run_remote_execute(
    transport: Any,
    plan: dict[str, Any],
    authorization: str,
    confirmation: str,
) -> tuple[int, dict[str, Any]]:
    payload = base64.b64encode(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    completed = transport.run_remote(
        [
            "python3",
            "-c",
            REMOTE_EXECUTE_SCRIPT,
            payload,
            authorization,
            confirmation,
            "execute",
        ],
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
        "schema": "gh.n3w-t1-kf147-usb-confirm-u1-u4-local-result/1",
        "status": "STOP",
        "gate_id": GATE_ID,
        "t1_access": False,
        "read_only_preflight": False,
        "live_execute_invoked": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "usb_mutation": False,
        "u2_plus": False,
        "u4_ready": False,
        "homeassistant_mutation": False,
        "manager_mutation": False,
        "broker_mutation": False,
        "board_access": False,
        "merge": False,
        "first_failed_operation": None,
    }
    transport = None
    try:
        manifest, readonly = validate_local(args.expected_package_commit)
        evidence_root = prepare_evidence_root(args.evidence_root)
        transport_type = readonly.load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        readonly_manifest = readonly.read_manifest()
        readonly_plan = readonly.build_plan(readonly_manifest)
        remote_returncode, baseline = readonly.run_remote(
            transport,
            readonly_plan,
        )
        write_private(evidence_root / "fresh-preflight.json", baseline)
        if remote_returncode != 0 or baseline.get("status") != "PASS":
            result["first_failed_operation"] = (
                baseline.get("reason") or "fresh_preflight_failed"
            )
            return result
        validate_baseline(baseline, manifest)
        check_state_root_absent(transport, manifest["state_root"])
        result["read_only_preflight"] = True

        if args.preflight_only:
            result.update(
                {
                    "status": "PASS",
                    "authorization_eligible": True,
                    "live_execution_authorized": bool(
                        manifest["live_execution_authorized"]
                    ),
                    "explicit_user_authorization_required": True,
                    "destructive_execution_ready": False,
                    "baseline": baseline,
                }
            )
            return result

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
            result["first_failed_operation"] = (
                "live_execution_not_authorized"
            )
            return result
        if (
            args.authorization_id != GATE_ID
            or args.confirm != CONFIRMATION
        ):
            result["first_failed_operation"] = (
                "authorization_or_confirmation_invalid"
            )
            return result

        result["live_execute_invoked"] = True
        plan = build_plan(manifest)
        remote_returncode, remote_result = run_remote_execute(
            transport,
            plan,
            args.authorization_id,
            args.confirm,
        )
        write_private(evidence_root / "remote-result.json", remote_result)
        result["remote_returncode"] = remote_returncode
        result["authorization_claimed"] = bool(
            remote_result.get("authorization_claimed")
        )
        result["authorization_consumed"] = bool(
            remote_result.get("authorization_consumed")
        )
        result["usb_mutation"] = bool(
            remote_result.get("usb_mutation_possible")
        )
        result["u2_plus"] = bool(remote_result.get("u2_plus"))
        result["u4_ready"] = bool(remote_result.get("u4_ready"))
        if remote_returncode != 0 or remote_result.get("status") != "PASS":
            result["first_failed_operation"] = (
                remote_result.get("first_failed_operation")
                or remote_result.get("reason")
                or "remote_execute_failed"
            )
            result["manual_recovery_required"] = bool(
                remote_result.get("manual_recovery_required")
            )
            return result
        result.update(remote_result)
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
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--authorization-id")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    if args.preflight_only == args.execute:
        print(json.dumps({"status": "STOP", "reason": "mode_invalid"}))
        return 2
    if re.fullmatch(
        r"[A-Za-z0-9._-]{1,160}",
        args.execution_id,
    ) is None:
        print(
            json.dumps(
                {"status": "STOP", "reason": "execution_id_invalid"}
            )
        )
        return 2

    result = execute(args)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
