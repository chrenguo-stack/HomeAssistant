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
import tempfile
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
SSH_TRANSPORT_PATH = REPO_ROOT / "tools/n3w_t1_ssh_transport.py"

GATE_ID = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_STAGE_B_POLICY_SOURCE_REPAIR_R2_20261110_01"
CONFIRMATION = "EXECUTE KF147 STAGE B POLICY SOURCE REPAIR R2: YES"
PREDECESSOR_SOURCE_HEAD = "70aaa4070641dd73c1a97738e6332be31403d45e"
REMOTE_DIR = "/var/tmp/n3w-kf147-stage-b-policy-source-r2-20261110-01"
STATE_ROOT = "/var/lib/n3w-t1-core-updater/kf147-stage-b-policy-source-r2-20261110-01"

TARGETS = {
    "tools/n3w_t1_core_updater_ha_capacity.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_capacity.py",
    "tools/n3w_t1_core_updater_ha_ipc.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_ipc.py",
    "tools/n3w_t1_core_updater_ha_prepare.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare.py",
    "tools/n3w_t1_core_updater_ha_prepare_host.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py",
    "tools/n3w_t1_core_updater_ha_recovery_encoding.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_recovery_encoding.py",
    "tools/n3w_t1_core_updater_ha_usb.py":
        "/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_usb.py",
    "infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json":
        "/etc/n3w-t1-ota/homeassistant-release-source.json",
}

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
directory = os.open(os.path.dirname(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
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
TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
PREPARE_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-prepare.json")
SOCKET_PATH = "/run/n3w-t1-ota/ha-ota.sock"
TX_SCHEMA = "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
PREPARE_SCHEMA = "gh.n3w-t1-ha-usb-prepare-state/1"
IPC_REQUEST_SCHEMA = "gh.n3w-t1-ha-ota-ipc-request/1"
IPC_RESPONSE_V3 = "gh.n3w-t1-ha-ota-ipc-response/3"


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


def require_regular(path, mode):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise Stop("file_invalid:" + path)
    meta = p.stat()
    if meta.st_uid != 0 or meta.st_gid != 0 or stat.S_IMODE(meta.st_mode) != mode:
        raise Stop("file_metadata_invalid:" + path)


def read_private_json(path, schema):
    require_regular(str(path), 0o600)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("json_invalid:" + path.name) from error
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise Stop("json_schema_invalid:" + path.name)
    return doc


def docker_one(image):
    ids = [
        line.strip()
        for line in run(
            ["docker", "ps", "--filter", "ancestor=" + image, "--format", "{{.ID}}"],
            timeout=60,
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(ids) != 1:
        raise Stop("container_cardinality_invalid:" + image + ":" + str(len(ids)))
    try:
        doc = json.loads(run(["docker", "inspect", ids[0]], timeout=60).stdout)
    except json.JSONDecodeError as error:
        raise Stop("container_inspect_invalid:" + image) from error
    if not isinstance(doc, list) or len(doc) != 1 or not isinstance(doc[0], dict):
        raise Stop("container_inspect_invalid:" + image)
    item = doc[0]
    if item.get("Config", {}).get("Image") != image or item.get("State", {}).get("Status") != "running":
        raise Stop("container_state_invalid:" + image)
    return item


def prepare_view(plan, *, require_snapshot):
    tx = read_private_json(TX_PATH, TX_SCHEMA)
    if sha_file(TX_PATH) != plan["live"]["u1_transaction_sha256"]:
        raise Stop("u1_transaction_sha_drift")
    if (
        tx.get("phase") != "U1_PREPARE_REQUESTED"
        or tx.get("status") != "ACTIVE"
        or tx.get("authorization_claimed") is not False
        or tx.get("authorization_consumed") is not False
    ):
        raise Stop("u1_transaction_semantics_drift")

    prep = read_private_json(PREPARE_PATH, PREPARE_SCHEMA)
    candidate = prep.get("candidate")
    if not isinstance(candidate, dict):
        raise Stop("prepare_candidate_missing")
    if (
        candidate.get("public_fingerprint")
        != plan["live"]["usb_candidate_public_fingerprint"]
        or candidate.get("display_model") != plan["live"]["usb_candidate_model"]
        or candidate.get("display_capacity_bytes")
        != plan["live"]["usb_candidate_capacity_bytes"]
        or prep.get("confirmation_required") is not True
        or prep.get("confirmation_consumed") is not False
    ):
        raise Stop("prepare_candidate_drift")
    snapshot = prep.get("capacity_snapshot")
    if require_snapshot and not isinstance(snapshot, dict):
        raise Stop("capacity_snapshot_missing")
    if not require_snapshot and snapshot is not None:
        raise Stop("capacity_snapshot_unexpected")
    if isinstance(snapshot, dict):
        required = snapshot.get("usb_required_bytes")
        recommended = snapshot.get("recommended_nominal_usb_gb")
        if (
            type(required) is not int
            or required <= 0
            or type(recommended) is not int
            or recommended <= 0
        ):
            raise Stop("capacity_snapshot_invalid")
    return {
        "transaction": tx,
        "prepare": prep,
        "transaction_sha256": sha_file(TX_PATH),
        "prepare_sha256": sha_file(PREPARE_PATH),
    }


def file_prestate(plan):
    observed = {}
    for item in plan["files"]:
        path = Path(item["remote_path"])
        expected = item["pre_sha256"]
        if expected is None:
            if path.exists() or path.is_symlink():
                raise Stop("predecessor_absent_file_present:" + str(path))
            observed[item["repo_path"]] = None
            continue
        require_regular(str(path), 0o644)
        value = sha_file(path)
        if value != expected:
            raise Stop("predecessor_file_drift:" + item["repo_path"])
        observed[item["repo_path"]] = value
    return observed


def dependency_prestate(plan):
    observed = {}
    for item in plan["dependencies"]:
        path = item["remote_path"]
        require_regular(path, 0o644)
        value = sha_file(path)
        if value != item["sha256"]:
            raise Stop("unchanged_dependency_drift:" + item["repo_path"])
        observed[item["repo_path"]] = value
    return observed


def baseline(plan, *, require_snapshot):
    system_state = run(["systemctl", "is-system-running"], check=False, timeout=30).stdout.strip()
    if system_state not in {"running", "degraded"}:
        raise Stop("system_state_invalid:" + system_state)
    for unit in (SERVICES_UNIT, HOST_UNIT):
        if run(["systemctl", "is-active", unit], check=False, timeout=30).stdout.strip() != "active":
            raise Stop("required_unit_inactive:" + unit)

    manager = docker_one(plan["live"]["manager_image"])
    homeassistant = docker_one(plan["live"]["homeassistant_image"])
    broker = docker_one(plan["live"]["broker_image"])
    expected_ids = (
        (manager, plan["live"]["manager_runtime_image_id"], "manager"),
        (homeassistant, plan["live"]["homeassistant_runtime_image_id"], "homeassistant"),
        (broker, plan["live"]["broker_runtime_image_id"], "broker"),
    )
    for doc, expected, label in expected_ids:
        if doc.get("Image") != expected:
            raise Stop(label + "_runtime_image_drift")

    state = prepare_view(plan, require_snapshot=require_snapshot)
    files = file_prestate(plan) if not require_snapshot else None
    dependencies = dependency_prestate(plan)
    return {
        "system_state": system_state,
        "manager_container_id": manager.get("Id"),
        "homeassistant_container_id": homeassistant.get("Id"),
        "broker_container_id": broker.get("Id"),
        "transaction_sha256": state["transaction_sha256"],
        "prepare_sha256": state["prepare_sha256"],
        "files": files,
        "dependencies": dependencies,
    }


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_json(path, value):
    path = Path(path)
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb", closefd=True) as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_dir(path.parent)


def atomic_install(source, target):
    source = Path(source)
    target = Path(target)
    if source.is_symlink() or not source.is_file():
        raise Stop("staged_source_invalid:" + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.is_symlink():
        raise Stop("target_symlink:" + str(target))
    temp = target.parent / (".n3w-kf147." + target.name + "." + str(os.getpid()))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temp, flags, 0o644)
    try:
        with source.open("rb") as inp, os.fdopen(fd, "wb", closefd=False) as out:
            shutil.copyfileobj(inp, out, length=1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        os.fchmod(fd, 0o644)
        os.fchown(fd, 0, 0)
    finally:
        os.close(fd)
    os.replace(temp, target)
    fsync_dir(target.parent)


def wait_host_active():
    deadline = time.monotonic() + 45.0
    while time.monotonic() < deadline:
        active = run(["systemctl", "is-active", HOST_UNIT], check=False, timeout=30).stdout.strip()
        if active == "active" and Path(SOCKET_PATH).exists():
            return
        time.sleep(1.0)
    raise Stop("host_service_not_active")


def wait_host_inactive():
    deadline = time.monotonic() + 45.0
    while time.monotonic() < deadline:
        active = run(["systemctl", "is-active", HOST_UNIT], check=False, timeout=30).stdout.strip()
        if active in {"inactive", "failed"} and not Path(SOCKET_PATH).exists():
            return
        time.sleep(1.0)
    raise Stop("host_service_not_inactive")


def wait_snapshot(plan):
    deadline = time.monotonic() + 30.0
    last = None
    while time.monotonic() < deadline:
        try:
            last = prepare_view(plan, require_snapshot=True)
            return last
        except Stop as error:
            if str(error) != "capacity_snapshot_missing":
                raise
        time.sleep(1.0)
    raise Stop("capacity_snapshot_timeout")


def manager_ipc_probe(container_id, plan):
    probe = r"""
import json
import socket

path = "/run/n3w-t1-ota/ha-ota.sock"
request = (
    json.dumps(
        {"schema": "gh.n3w-t1-ha-ota-ipc-request/1", "operation": "status"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    + b"\n"
)
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.settimeout(5.0)
    client.connect(path)
    client.sendall(request)
    client.shutdown(socket.SHUT_WR)
    payload = bytearray()
    while len(payload) <= 8192:
        block = client.recv(1024)
        if not block:
            break
        payload.extend(block)
        if b"\n" in payload:
            break
print(bytes(payload).split(b"\n", 1)[0].decode("utf-8"))
"""
    raw = run(
        ["docker", "exec", "-u", "999:999", container_id, "python3", "-c", probe],
        timeout=30,
    ).stdout.strip()
    try:
        response = json.loads(raw)
    except json.JSONDecodeError as error:
        raise Stop("manager_ipc_v3_json_invalid") from error
    candidate = response.get("usb_candidate")
    if (
        response.get("schema") != IPC_RESPONSE_V3
        or response.get("accepted") is not True
        or not isinstance(candidate, dict)
        or candidate.get("public_fingerprint")
        != plan["live"]["usb_candidate_public_fingerprint"]
        or response.get("usb_confirmation_required") is not True
        or type(response.get("usb_required_bytes_or_null")) is not int
        or response["usb_required_bytes_or_null"] <= 0
        or type(response.get("usb_recommended_nominal_gb_or_null")) is not int
        or response["usb_recommended_nominal_gb_or_null"] <= 0
    ):
        raise Stop("manager_ipc_v3_validation_failed")
    return response


def target_files(plan):
    values = {}
    for item in plan["files"]:
        path = item["remote_path"]
        require_regular(path, 0o644)
        observed = sha_file(path)
        if observed != item["target_sha256"]:
            raise Stop("target_file_drift:" + item["repo_path"])
        values[item["repo_path"]] = observed
    return values


def rollback(plan, backup_dir, pre):
    result = {"attempted": True, "status": "FAIL"}
    try:
        run(["systemctl", "stop", HOST_UNIT], timeout=90)
        wait_host_inactive()
        for item in plan["files"]:
            target = Path(item["remote_path"])
            backup = Path(backup_dir) / item["stage_name"]
            if item["pre_sha256"] is None:
                if target.exists() or target.is_symlink():
                    if target.is_symlink() or not target.is_file():
                        raise Stop("rollback_target_invalid:" + str(target))
                    target.unlink()
                    fsync_dir(target.parent)
            else:
                if not backup.is_file() or backup.is_symlink():
                    raise Stop("rollback_backup_missing:" + item["repo_path"])
                atomic_install(backup, target)

        prepare_backup = Path(backup_dir) / "homeassistant-usb-prepare.json"
        if prepare_backup.exists():
            if prepare_backup.is_symlink() or not prepare_backup.is_file():
                raise Stop("rollback_prepare_backup_invalid")
            temp = PREPARE_PATH.parent / (".n3w-kf147.rollback.prepare." + str(os.getpid()))
            shutil.copyfile(prepare_backup, temp)
            os.chmod(temp, 0o600)
            os.chown(temp, 0, 0)
            with open(temp, "rb") as stream:
                os.fsync(stream.fileno())
            os.replace(temp, PREPARE_PATH)
            fsync_dir(PREPARE_PATH.parent)

        run(["systemctl", "start", HOST_UNIT], timeout=90)
        wait_host_active()
        post = baseline(plan, require_snapshot=False)
        if (
            post["manager_container_id"] != pre["manager_container_id"]
            or post["homeassistant_container_id"] != pre["homeassistant_container_id"]
            or post["broker_container_id"] != pre["broker_container_id"]
        ):
            raise Stop("rollback_container_continuity_failed")
        result["status"] = "PASS"
    except Exception as error:
        result["error"] = type(error).__name__ + ":" + str(error)[:240]
    return result


def execute(plan, authorization, confirmation):
    if authorization != plan["gate_id"] or confirmation != plan["confirmation"]:
        raise Stop("authorization_or_confirmation_invalid")
    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("authorization_state_root_exists")

    pre = baseline(plan, require_snapshot=False)
    stage_root = Path(plan["remote_dir"])
    if not stage_root.is_dir() or stage_root.is_symlink():
        raise Stop("staging_root_invalid")
    for item in plan["files"]:
        staged = Path(item["staged_path"])
        require_regular(str(staged), 0o600)
        if sha_file(staged) != item["target_sha256"]:
            raise Stop("staged_sha256_mismatch:" + item["repo_path"])

    backup_dir = stage_root / ".preclaim-backup"
    if backup_dir.exists() or backup_dir.is_symlink():
        raise Stop("preclaim_backup_residue")
    backup_dir.mkdir(mode=0o700)
    os.chown(backup_dir, 0, 0)

    for item in plan["files"]:
        if item["pre_sha256"] is not None:
            source = Path(item["remote_path"])
            backup = backup_dir / item["stage_name"]
            shutil.copyfile(source, backup)
            os.chmod(backup, 0o600)
            os.chown(backup, 0, 0)
            if sha_file(backup) != item["pre_sha256"]:
                raise Stop("backup_sha256_mismatch:" + item["repo_path"])
    fsync_dir(backup_dir)

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    durable_json(state_root / "preflight.json", pre)
    durable_json(
        state_root / "authorization_claim.json",
        {
            "authorization_id": plan["gate_id"],
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
        },
    )

    result = {
        "schema": "gh.n3w-t1-kf147-policy-source-live-repair-result/1",
        "status": "STOP",
        "authorization_id": plan["gate_id"],
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "host_source_mutation": False,
        "host_daemon_restart": False,
        "manager_mutation": False,
        "homeassistant_mutation": False,
        "broker_mutation": False,
        "usb_mutation": False,
        "u2_plus": False,
        "rollback_required": False,
        "rollback": None,
        "first_failed_operation": None,
    }

    try:
        run(["systemctl", "stop", HOST_UNIT], timeout=90)
        result["host_daemon_stopped"] = True
        wait_host_inactive()

        frozen = prepare_view(plan, require_snapshot=False)
        if frozen["transaction_sha256"] != pre["transaction_sha256"]:
            raise Stop("u1_transaction_drift_after_claim")
        prepare_backup = backup_dir / "homeassistant-usb-prepare.json"
        shutil.copyfile(PREPARE_PATH, prepare_backup)
        os.chmod(prepare_backup, 0o600)
        os.chown(prepare_backup, 0, 0)
        if sha_file(prepare_backup) != frozen["prepare_sha256"]:
            raise Stop("prepare_backup_sha256_mismatch")
        fsync_dir(backup_dir)

        for item in plan["files"]:
            atomic_install(item["staged_path"], item["remote_path"])
        result["host_source_mutation"] = True

        run(["systemctl", "start", HOST_UNIT], timeout=90)
        result["host_daemon_restart"] = True
        wait_host_active()
        wait_snapshot(plan)

        post_base = baseline(plan, require_snapshot=True)
        if (
            post_base["manager_container_id"] != pre["manager_container_id"]
            or post_base["homeassistant_container_id"] != pre["homeassistant_container_id"]
            or post_base["broker_container_id"] != pre["broker_container_id"]
        ):
            raise Stop("container_continuity_failed")
        files = target_files(plan)
        ipc = manager_ipc_probe(pre["manager_container_id"], plan)

        post = {
            "containers_preserved": True,
            "transaction_sha256": post_base["transaction_sha256"],
            "target_files": files,
            "manager_ipc": ipc,
            "capacity_snapshot_present": True,
            "candidate_preserved": True,
        }
        durable_json(state_root / "post.json", post)
        shutil.rmtree(stage_root)
        result.update(
            {
                "status": "PASS",
                "manager_ipc_v3_support": True,
                "capacity_snapshot_present": True,
                "prepare_candidate_preserved": True,
                "u1_transaction_preserved": True,
                "rollback_required": False,
            }
        )
        return result
    except Exception as error:
        result["first_failed_operation"] = type(error).__name__ + ":" + str(error)[:240]
        result["rollback_required"] = True
        result["rollback"] = rollback(plan, backup_dir, pre)
        durable_json(state_root / "failure.json", result)
        return result


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"status": "STOP", "reason": "arguments_missing"}))
        return 2
    mode = sys.argv[1]
    try:
        plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
        if mode == "preflight":
            result = baseline(plan, require_snapshot=False)
            result.update(
                {
                    "schema": "gh.n3w-t1-kf147-policy-source-preflight/1",
                    "status": "PASS",
                    "mutation": False,
                }
            )
        elif mode == "execute":
            if len(sys.argv) != 5:
                raise Stop("execution_arguments_missing")
            result = execute(plan, sys.argv[3], sys.argv[4])
        else:
            raise Stop("mode_invalid")
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
        raise Stop(f"local_command_failed:{Path(argv[0]).name}:{completed.returncode}")
    return completed


def git_text(*args: str) -> str:
    return run(["git", "-C", str(REPO_ROOT), *args], timeout=30).stdout.strip()


def git_bytes(*args: str, check: bool = True) -> bytes:
    completed = run(
        ["git", "-C", str(REPO_ROOT), *args],
        timeout=60,
        check=check,
        binary=True,
    )
    return completed.stdout


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stop("manifest_invalid")
    return value


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
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(fd, "wb", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def validate_local(expected_commit: str, *, require_live: bool) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")

    manifest = read_manifest()
    if (
        manifest.get("schema") != "gh.n3w-t1-kf147-policy-source-live-repair/1"
        or manifest.get("gate_id") != GATE_ID
        or manifest.get("authorization_id") != GATE_ID
        or manifest.get("confirmation") != CONFIRMATION
    ):
        raise Stop("manifest_contract_invalid")
    if manifest.get("predecessor_source_authority", {}).get("source_head") != PREDECESSOR_SOURCE_HEAD:
        raise Stop("predecessor_source_head_invalid")
    if set(manifest.get("source_authority", {})) != set(TARGETS) | {
        "tools/n3w_t1_ssh_transport.py"
    }:
        raise Stop("source_authority_shape_invalid")
    for relative, blob in manifest["source_authority"].items():
        if git_text("rev-parse", f"HEAD:{relative}") != blob:
            raise Stop(f"source_authority_drift:{relative}")

    dependencies = manifest.get("unchanged_live_authority")
    if not isinstance(dependencies, dict) or not dependencies:
        raise Stop("unchanged_live_authority_invalid")
    for relative, authority in dependencies.items():
        if (
            not isinstance(authority, dict)
            or set(authority) != {"blob", "remote_path"}
            or not isinstance(authority.get("blob"), str)
            or re.fullmatch(r"[0-9a-f]{40}", authority["blob"]) is None
            or not isinstance(authority.get("remote_path"), str)
            or not authority["remote_path"].startswith("/")
        ):
            raise Stop(f"unchanged_live_authority_invalid:{relative}")
        if git_text("rev-parse", f"HEAD:{relative}") != authority["blob"]:
            raise Stop(f"unchanged_source_authority_drift:{relative}")
    if require_live:
        auth = manifest.get("authorization_state", {})
        if not (
            manifest.get("live_execution_authorized") is True
            and auth.get("granted") is True
            and auth.get("claimed") is False
            and auth.get("consumed") is False
            and auth.get("replay_permitted") is False
        ):
            raise Stop("live_execution_not_authorized")
    return manifest


def build_plan(manifest: dict[str, Any]) -> dict[str, Any]:
    predecessor = manifest["predecessor_source_authority"]["files"]
    files = []
    for index, relative in enumerate(TARGETS):
        target_path = REPO_ROOT / relative
        if target_path.is_symlink() or not target_path.is_file():
            raise Stop(f"target_source_invalid:{relative}")
        target_sha = sha_file(target_path)
        predecessor_blob = predecessor[relative]
        if predecessor_blob is None:
            exists = run(
                [
                    "git",
                    "-C",
                    str(REPO_ROOT),
                    "cat-file",
                    "-e",
                    f"{PREDECESSOR_SOURCE_HEAD}:{relative}",
                ],
                timeout=30,
                check=False,
            ).returncode == 0
            if exists:
                raise Stop(f"predecessor_absence_drift:{relative}")
            pre_sha = None
        else:
            if git_text("rev-parse", f"{PREDECESSOR_SOURCE_HEAD}:{relative}") != predecessor_blob:
                raise Stop(f"predecessor_blob_drift:{relative}")
            pre_sha = sha_bytes(git_bytes("show", f"{PREDECESSOR_SOURCE_HEAD}:{relative}"))
        stage_name = f"{index:02d}-" + relative.replace("/", "__")
        files.append(
            {
                "repo_path": relative,
                "remote_path": TARGETS[relative],
                "stage_name": stage_name,
                "staged_path": f"{REMOTE_DIR}/{stage_name}",
                "pre_sha256": pre_sha,
                "target_sha256": target_sha,
            }
        )
    dependencies = []
    for relative, authority in manifest["unchanged_live_authority"].items():
        source = REPO_ROOT / relative
        if source.is_symlink() or not source.is_file():
            raise Stop(f"unchanged_source_invalid:{relative}")
        if git_text("rev-parse", f"HEAD:{relative}") != authority["blob"]:
            raise Stop(f"unchanged_source_blob_drift:{relative}")
        dependencies.append(
            {
                "repo_path": relative,
                "remote_path": authority["remote_path"],
                "sha256": sha_file(source),
            }
        )
    return {
        "gate_id": GATE_ID,
        "confirmation": CONFIRMATION,
        "remote_dir": REMOTE_DIR,
        "state_root": STATE_ROOT,
        "live": manifest["expected_live_entry"],
        "files": files,
        "dependencies": dependencies,
    }


def load_transport() -> type:
    manifest = read_manifest()
    expected = manifest["source_authority"]["tools/n3w_t1_ssh_transport.py"]
    if git_text("hash-object", str(SSH_TRANSPORT_PATH)) != expected:
        raise Stop("ssh_transport_binding_invalid")
    spec = importlib.util.spec_from_file_location(
        "n3w_t1_ssh_transport",
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


def stream_file(source: Path, transport: Any, remote_path: str, *, timeout: int = 180) -> None:
    if source.is_symlink() or not source.is_file():
        raise Stop("stream_source_invalid")
    command = shlex.join(("python3", "-c", REMOTE_STREAM_WRITE, remote_path))
    with source.open("rb") as stream:
        completed = subprocess.run(
            child_ssh_argv(transport, command),
            stdin=stream,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    if completed.returncode != 0:
        raise Stop(f"command_failed:ssh-stream:{completed.returncode}")


def run_remote_mode(
    transport: Any,
    mode: str,
    plan: dict[str, Any],
    *,
    authorization: str | None = None,
    confirmation: str | None = None,
    timeout: int = 180,
) -> tuple[int, dict[str, Any]]:
    payload = base64.b64encode(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    argv = ["python3", "-c", REMOTE_SCRIPT, mode, payload]
    if mode == "execute":
        argv.extend([authorization or "", confirmation or ""])
    completed = transport.run_remote(argv, timeout=timeout, check=False)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise Stop("remote_result_json_invalid") from error
    if not isinstance(result, dict):
        raise Stop("remote_result_shape_invalid")
    return completed.returncode, result


def execute(args: argparse.Namespace) -> dict[str, Any]:
    manifest = validate_local(args.expected_package_commit, require_live=not args.preflight_only)
    plan = build_plan(manifest)
    root = prepare_evidence_root(args.evidence_root)
    result: dict[str, Any] = {
        "schema": "gh.n3w-t1-kf147-policy-source-local-result/1",
        "status": "STOP",
        "authorization_id": GATE_ID,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "t1_access": False,
        "remote_staging": False,
        "live_apply_invoked": False,
        "usb_mutation": False,
        "u2_plus": False,
        "merge": False,
        "first_failed_operation": None,
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

        rc, preflight = run_remote_mode(
            transport,
            "preflight",
            plan,
            timeout=180,
        )
        write_private(root / "preflight.json", preflight)
        if rc != 0 or preflight.get("status") != "PASS":
            result["first_failed_operation"] = preflight.get("reason") or "preflight_stop"
            return result

        if args.preflight_only:
            result.update({"status": "PASS", "read_only": True})
            return result

        if args.authorization_id != GATE_ID or args.confirm != CONFIRMATION:
            raise Stop("authorization_or_confirmation_invalid")
        if (
            transport.run_remote(
                ["test", "-e", REMOTE_DIR],
                check=False,
                timeout=30,
            ).returncode
            == 0
        ):
            raise Stop("remote_staging_already_exists")
        transport.run_remote(
            ["install", "-d", "-m", "0700", "-o", "root", "-g", "root", REMOTE_DIR],
            timeout=60,
        )
        for item in plan["files"]:
            stream_file(
                REPO_ROOT / item["repo_path"],
                transport,
                item["staged_path"],
            )
        result["remote_staging"] = True

        result["live_apply_invoked"] = True
        rc, remote_result = run_remote_mode(
            transport,
            "execute",
            plan,
            authorization=args.authorization_id,
            confirmation=args.confirm,
            timeout=300,
        )
        write_private(root / "remote_result.json", remote_result)
        result["authorization_claimed"] = bool(
            remote_result.get("authorization_claimed")
        )
        result["authorization_consumed"] = bool(
            remote_result.get("authorization_consumed")
        )
        result["remote_returncode"] = rc
        if rc != 0 or remote_result.get("status") != "PASS":
            result["first_failed_operation"] = (
                remote_result.get("first_failed_operation")
                or remote_result.get("reason")
                or "remote_apply_failed"
            )
            result["rollback_required"] = remote_result.get("rollback_required")
            result["rollback"] = remote_result.get("rollback")
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
    parser.add_argument("--expected-package-commit")
    parser.add_argument("--authorization-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

    required = (
        args.expected_package_commit,
        args.execution_id,
        args.evidence_root,
        args.t1_ssh_target,
        args.known_hosts,
        args.expected_host_key_sha256,
    )
    if any(value is None for value in required):
        print(json.dumps({"status": "STOP", "reason": "execution_arguments_missing"}))
        return 2
    if args.preflight_only == args.execute:
        print(json.dumps({"status": "STOP", "reason": "mode_invalid"}))
        return 2
    if args.execute and (
        args.authorization_id != GATE_ID or args.confirm != CONFIRMATION
    ):
        print(json.dumps({"status": "STOP", "reason": "authorization_or_confirmation_invalid"}))
        return 2

    result = execute(args)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
