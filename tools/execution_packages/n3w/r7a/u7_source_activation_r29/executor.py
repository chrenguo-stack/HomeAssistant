#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
BASE_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u6_source_activation_r25"
    / "executor.py"
)

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U7_SOURCE_ACTIVATION_R29_20261114_01"
)
CONFIRMATION = "EXECUTE U7 R29 SOURCE ACTIVATION: YES"

TARGETS = {
    "backup": ROOT / "tools" / "n3w_t1_core_updater_ha_backup.py",
    "usb": ROOT / "tools" / "n3w_t1_core_updater_ha_usb.py",
    "install": ROOT / "tools" / "n3w_t1_core_updater_ha_install.py",
    "capacity": ROOT / "tools" / "n3w_t1_core_updater_ha_capacity.py",
    "host": ROOT / "tools" / "n3w_t1_core_updater_host.py",
    "common": ROOT / "tools" / "n3w_t1_core_updater_common.py",
    "v2_state": ROOT / "tools" / "n3w_t1_core_updater_v2_state.py",
}

REMOTE_NAMES = {
    "backup": "n3w_t1_core_updater_ha_backup.py",
    "usb": "n3w_t1_core_updater_ha_usb.py",
    "install": "n3w_t1_core_updater_ha_install.py",
    "capacity": "n3w_t1_core_updater_ha_capacity.py",
    "host": "n3w_t1_core_updater_host.py",
    "common": "n3w_t1_core_updater_common.py",
    "v2_state": "n3w_t1_core_updater_v2_state.py",
}


class Stop(RuntimeError):
    pass


def load_base():
    spec = importlib.util.spec_from_file_location("n3w_r29_base", BASE_EXECUTOR)
    if spec is None or spec.loader is None:
        raise Stop("base_executor_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REMOTE_SCRIPT = r'''
import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

TX = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
R26 = Path(
    "/var/lib/n3w-t1-core-updater/u6-r26-predecessor-recovery-20261114-01"
)
HOST_UNIT = "n3w-t1-ha-ota.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"


class Stop(RuntimeError):
    pass


def run(argv, *, timeout=60, check=True, env=None):
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
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


def git_blob_sha1(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + str(path))
    metadata = path.stat()
    digest = hashlib.sha1()
    digest.update(("blob " + str(metadata.st_size) + "\0").encode("ascii"))
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


def fsync_dir(path):
    descriptor = os.open(
        str(path),
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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


def atomic_install(source, destination):
    source = Path(source)
    destination = Path(destination)
    if source.is_symlink() or not source.is_file():
        raise Stop("staged_source_invalid:" + source.name)
    descriptor, raw = tempfile.mkstemp(
        prefix="." + destination.name + ".",
        dir=destination.parent,
    )
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, 0o644)
        with os.fdopen(descriptor, "wb", closefd=True) as out:
            with source.open("rb") as inp:
                shutil.copyfileobj(inp, out)
            out.flush()
            os.fsync(out.fileno())
        os.chown(temporary, 0, 0)
        os.replace(temporary, destination)
        fsync_dir(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


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


def docker_view(expected):
    ids = [
        value.strip()
        for value in run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "ancestor=" + expected["image"],
                "--format",
                "{{.ID}}",
            ],
            timeout=45,
        ).stdout.splitlines()
        if value.strip()
    ]
    if len(ids) != 1:
        raise Stop("container_cardinality_invalid:" + expected["image"])
    documents = json.loads(
        run(["docker", "inspect", ids[0]], timeout=45).stdout
    )
    if not isinstance(documents, list) or len(documents) != 1:
        raise Stop("container_inspect_invalid:" + expected["image"])
    item = documents[0]
    state = item.get("State") if isinstance(item.get("State"), dict) else {}
    config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
    result = {
        "container_id": item.get("Id"),
        "runtime_image_id": item.get("Image"),
        "configured_image_ref": config.get("Image"),
        "status": state.get("Status"),
        "restart_count": item.get("RestartCount"),
    }
    if (
        result["runtime_image_id"] != expected["runtime_image_id"]
        or result["configured_image_ref"] != expected["image"]
        or result["status"] != "running"
        or result["restart_count"] != 0
    ):
        raise Stop("container_runtime_drift:" + expected["image"])
    return result


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
        or value.get("phase") != "PREDECESSOR_RECOVERY_PREPARING"
        or value.get("error_code") is not None
        or value.get("installed_version") != "2026.10.0"
    ):
        raise Stop("ipc_not_u6_ready")
    return value


def verify_transaction(plan):
    transaction = read_object(TX)
    if (
        transaction.get("phase") != "U6_PREDECESSOR_RECOVERY_PREPARING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or sha_file(TX) != plan["transaction_sha256"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not False
        or transaction.get("predecessor_recovery_identity") is not None
        or transaction.get("ha_data_backup_verified") is not False
        or transaction.get("ha_data_backup_identity") is not None
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
    ):
        raise Stop("u7_u6_transaction_invalid")
    return transaction


def verify_r26(plan):
    claim = read_object(R26 / "authorization_claim.json")
    success = read_object(R26 / "success.json")
    if (
        claim.get("authorization_id") != plan["r26_gate_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
    ):
        raise Stop("r26_claim_invalid")
    post = success.get("post")
    if (
        success.get("status") != "U6_R26_PREDECESSOR_RECOVERY_PASS"
        or success.get("authorization_claimed") is not True
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or success.get("u6_transition") is not True
        or success.get("u7_plus") is not False
        or not isinstance(post, dict)
        or post.get("transaction_phase")
        != "U6_PREDECESSOR_RECOVERY_PREPARING"
        or post.get("transaction_sha256") != plan["transaction_sha256"]
        or post.get("predecessor") != plan["predecessor_identity"]
    ):
        raise Stop("r26_success_invalid")
    return {
        "claim_consumed_no_replay": True,
        "predecessor_authority_exact": True,
    }


def optional_source_state(path, allowed_blobs):
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        if "ABSENT" not in allowed_blobs:
            raise Stop("required_source_absent:" + path.name)
        return {"state": "ABSENT", "git_blob_sha1": None}
    if path.is_symlink() or not path.is_file():
        raise Stop("source_path_invalid:" + path.name)
    observed = git_blob_sha1(path)
    if observed not in allowed_blobs:
        raise Stop("source_blob_drift:" + path.name)
    return {"state": "PRESENT", "git_blob_sha1": observed}


def verify_sources(plan, *, target_sources):
    observed = {}
    for path, expected in plan["unchanged_source_sha256"].items():
        digest = sha_file(path)
        if digest != expected:
            raise Stop("unchanged_u6_source_drift:" + Path(path).name)
        observed[path] = {"state": "PRESENT", "sha256": digest}

    for key, path in plan["remote_paths"].items():
        source = Path(path)
        if target_sources:
            digest = sha_file(source)
            if digest != plan["target_sha256"][key]:
                raise Stop("target_source_drift:" + key)
            observed[path] = {
                "state": "PRESENT",
                "sha256": digest,
                "git_blob_sha1": git_blob_sha1(source),
            }
            continue

        if key in plan["fixed_predecessor_sha256"]:
            expected = plan["fixed_predecessor_sha256"][key]
            if expected is None:
                if source.exists() or source.is_symlink():
                    raise Stop("pre_u7_source_not_absent:" + key)
                observed[path] = {"state": "ABSENT"}
            else:
                digest = sha_file(source)
                if digest != expected:
                    raise Stop("fixed_predecessor_drift:" + key)
                observed[path] = {
                    "state": "PRESENT",
                    "sha256": digest,
                    "git_blob_sha1": git_blob_sha1(source),
                }
            continue

        allowed = plan["dynamic_predecessor_git_blobs"][key]
        observed[path] = optional_source_state(path, allowed)
    return observed


def verify_runtime(plan):
    units = {
        "host": service_state(HOST_UNIT),
        "services_owner": service_state(SERVICES_UNIT),
        "broker_owner": service_state(BROKER_UNIT),
    }
    for name, value in units.items():
        if (
            value.get("returncode") != 0
            or value.get("ActiveState") != "active"
            or value.get("SubState") != "running"
            or value.get("Result") != "success"
            or value.get("NRestarts") != "0"
        ):
            raise Stop("unit_not_healthy:" + name)

    containers = {
        name: docker_view(expected)
        for name, expected in plan["containers"].items()
    }
    ipc = ipc_status(containers["manager"]["container_id"])
    return {"units": units, "containers": containers, "ipc": ipc}


def verify_prestate(plan, *, target_sources):
    verify_transaction(plan)
    r26 = verify_r26(plan)
    sources = verify_sources(plan, target_sources=target_sources)
    runtime = verify_runtime(plan)
    return {
        "transaction_sha256": sha_file(TX),
        "r26": r26,
        "sources": sources,
        **runtime,
    }


def sanitize_import_error(stage_root, error_text):
    value = (error_text or "").strip()
    value = value.replace(str(stage_root), "<stage>")
    value = value.replace("/opt/HomeAssistant/tools", "<tools>")
    value = value.replace("\n", " ")
    if len(value) > 240:
        value = value[-240:]
    return value


def staged_import_preflight(plan):
    stage = Path(plan["remote_staging_root"])
    script = (
        "import sys;"
        "sys.path.insert(0,'/opt/HomeAssistant/tools');"
        "sys.path.insert(0,sys.argv[1]);"
        "mods=sys.argv[2:];"
        "import importlib;"
        "[importlib.import_module(m) for m in mods];"
        "print('PASS')"
    )
    modules = [
        "n3w_t1_core_updater_ha_backup",
        "n3w_t1_core_updater_ha_capacity",
        "n3w_t1_core_updater_ha_usb",
        "n3w_t1_core_updater_ha_install",
        "n3w_t1_core_updater_host",
        "n3w_t1_core_updater_common",
        "n3w_t1_core_updater_v2_state",
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = run(
        ["python3", "-B", "-c", script, str(stage), *modules],
        timeout=90,
        check=False,
        env=environment,
    )
    if completed.returncode != 0 or completed.stdout.strip() != "PASS":
        detail = sanitize_import_error(stage, completed.stderr)
        raise Stop(
            "staged_import_failed:"
            + str(completed.returncode)
            + ":"
            + detail
        )
    return {"status": "PASS", "modules": modules}


def installed_import_validation():
    script = (
        "import sys;"
        "sys.path.insert(0,'/opt/HomeAssistant/tools');"
        "import n3w_t1_core_updater_ha_backup;"
        "import n3w_t1_core_updater_ha_capacity;"
        "import n3w_t1_core_updater_ha_usb;"
        "import n3w_t1_core_updater_ha_install;"
        "import n3w_t1_core_updater_host;"
        "import n3w_t1_core_updater_common;"
        "import n3w_t1_core_updater_v2_state;"
        "print('PASS')"
    )
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = run(
        ["python3", "-B", "-c", script],
        timeout=90,
        check=False,
        env=environment,
    )
    if completed.returncode != 0 or completed.stdout.strip() != "PASS":
        detail = sanitize_import_error(
            Path("/opt/HomeAssistant/tools"),
            completed.stderr,
        )
        raise Stop(
            "installed_import_failed:"
            + str(completed.returncode)
            + ":"
            + detail
        )


def copy_preclaim_backups(plan, pre, backup_root):
    backup_root.mkdir(mode=0o700)
    os.chown(backup_root, 0, 0)
    recorded = {}
    for key, path in plan["remote_paths"].items():
        state = pre["sources"][path]
        if state.get("state") == "ABSENT":
            recorded[key] = {"state": "ABSENT"}
            continue
        source = Path(path)
        backup = backup_root / plan["remote_names"][key]
        shutil.copyfile(source, backup)
        os.chmod(backup, 0o600)
        os.chown(backup, 0, 0)
        recorded[key] = {
            "state": "PRESENT",
            "sha256": sha_file(backup),
            "git_blob_sha1": git_blob_sha1(backup),
        }
        if state.get("sha256") is not None:
            if recorded[key]["sha256"] != state["sha256"]:
                raise Stop("preclaim_backup_sha_drift:" + key)
        if state.get("git_blob_sha1") is not None:
            if recorded[key]["git_blob_sha1"] != state["git_blob_sha1"]:
                raise Stop("preclaim_backup_blob_drift:" + key)
    return recorded


def rollback(plan, pre, backup_root):
    result = {"attempted": True, "status": "STOP", "errors": []}
    try:
        for key, path in plan["remote_paths"].items():
            destination = Path(path)
            state = pre["sources"][path]
            if state.get("state") == "ABSENT":
                if destination.exists() or destination.is_symlink():
                    if destination.is_symlink() or not destination.is_file():
                        raise Stop("rollback_path_invalid:" + key)
                    destination.unlink()
                    fsync_dir(destination.parent)
                continue
            backup = backup_root / plan["remote_names"][key]
            atomic_install(backup, destination)
        post = verify_prestate(plan, target_sources=False)
        if post["sources"] != pre["sources"]:
            raise Stop("rollback_source_prestate_mismatch")
        result["post"] = post
        result["status"] = "PASS"
    except Exception as error:
        result["errors"].append(
            type(error).__name__ + ":" + str(error)[:240]
        )
    return result


def runtime_continuity(before, after):
    for name in ("host", "services_owner", "broker_owner"):
        if after["units"][name]["MainPID"] != before["units"][name]["MainPID"]:
            raise Stop("unit_pid_drift:" + name)
    for name in ("manager", "homeassistant", "broker"):
        if (
            after["containers"][name]["container_id"]
            != before["containers"][name]["container_id"]
            or after["containers"][name]["restart_count"]
            != before["containers"][name]["restart_count"]
        ):
            raise Stop("container_runtime_drift_after_activation:" + name)


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
        raise Stop("r29_not_authorized")
    if (
        authorization != plan["authorization_id"]
        or confirmation != plan["confirmation"]
    ):
        raise Stop("r29_authorization_invalid")

    state_root = Path(plan["state_root"])
    stage_root = Path(plan["remote_staging_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("r29_state_root_exists")
    if (
        stage_root.is_symlink()
        or not stage_root.is_dir()
        or stage_root.stat().st_uid != 0
        or stat.S_IMODE(stage_root.stat().st_mode) != 0o700
    ):
        raise Stop("r29_staging_root_invalid")

    for key, expected in plan["target_sha256"].items():
        staged = stage_root / plan["remote_names"][key]
        if (
            staged.is_symlink()
            or not staged.is_file()
            or sha_file(staged) != expected
        ):
            raise Stop("r29_staged_source_invalid:" + key)

    pre = verify_prestate(plan, target_sources=False)
    try:
        staged_import = staged_import_preflight(plan)
        backup_root = stage_root / ".preclaim-backup"
        source_backup = copy_preclaim_backups(
            plan,
            pre,
            backup_root,
        )
    except Exception as preclaim_error:
        try:
            shutil.rmtree(stage_root)
        except Exception as cleanup_error:
            raise Stop(
                "preclaim_failure_cleanup_failed:"
                + type(preclaim_error).__name__
                + ":"
                + str(preclaim_error)[:160]
            ) from cleanup_error
        raise

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    fsync_dir(state_root.parent)
    durable_json(state_root / "preflight.json", pre)
    durable_json(state_root / "staged_import.json", staged_import)
    durable_json(state_root / "source_prestate.json", source_backup)

    result = {
        "schema": "gh.n3w-t1-u7-r29-source-activation/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "authorization_claim_persistence_unknown": False,
        "host_source_mutation": False,
        "activated_source_file_count": 0,
        "service_stop": False,
        "service_restart": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u7_transition": False,
        "u8_plus": False,
        "rollback_required": False,
        "rollback": None,
        "board_access": False,
        "merge": False,
    }

    claim = {
        "authorization_id": plan["authorization_id"],
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
    }
    try:
        durable_json(state_root / "authorization_claim.json", claim)
    except Exception as error:
        result.update(
            status="STOP_UNKNOWN",
            reason=(
                "authorization_claim_persistence_unknown:"
                + type(error).__name__
                + ":"
                + str(error)[:180]
            ),
            authorization_claimed=True,
            authorization_consumed=True,
            replay_permitted=False,
            authorization_claim_persistence_unknown=True,
        )
        return result

    result.update(
        authorization_claimed=True,
        authorization_consumed=True,
        replay_permitted=False,
    )

    try:
        postclaim = verify_prestate(plan, target_sources=False)
        if postclaim["sources"] != pre["sources"]:
            raise Stop("postclaim_source_drift")
        if postclaim["transaction_sha256"] != pre["transaction_sha256"]:
            raise Stop("postclaim_transaction_drift")
        runtime_continuity(pre, postclaim)

        result["host_source_mutation"] = True
        for key, destination in plan["remote_paths"].items():
            atomic_install(
                stage_root / plan["remote_names"][key],
                destination,
            )
            result["activated_source_file_count"] += 1

        installed_import_validation()
        post = verify_prestate(plan, target_sources=True)
        if post["transaction_sha256"] != pre["transaction_sha256"]:
            raise Stop("u6_transaction_drift_after_activation")
        runtime_continuity(pre, post)

        result.update(
            status="U7_R29_SOURCE_ACTIVATION_PASS",
            source_activated=True,
            u6_preserved=True,
            staged_import_validation=True,
            installed_import_validation=True,
            post=post,
        )
        durable_json(state_root / "success.json", result)
        try:
            shutil.rmtree(stage_root)
        except Exception as cleanup_error:
            result["completed_remote_status"] = result["status"]
            result["status"] = "STOP_POSTSUCCESS_CLEANUP"
            result["postsuccess_cleanup_error"] = (
                type(cleanup_error).__name__
                + ":"
                + str(cleanup_error)[:240]
            )
            result["rollback_required"] = False
        return result
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        result["rollback_required"] = bool(result["host_source_mutation"])
        if result["rollback_required"]:
            result["rollback"] = rollback(plan, pre, backup_root)
        try:
            durable_json(state_root / "failure.json", result)
        except Exception:
            pass
        return result


def main():
    try:
        mode = sys.argv[1]
        plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U7_SOURCE_ACTIVATION_R29_20261114_01"
        ):
            raise Stop("gate_id_invalid")

        if mode == "preflight":
            if (
                Path(plan["state_root"]).exists()
                or Path(plan["state_root"]).is_symlink()
            ):
                raise Stop("r29_state_root_residue")
            if (
                Path(plan["remote_staging_root"]).exists()
                or Path(plan["remote_staging_root"]).is_symlink()
            ):
                raise Stop("r29_staging_root_residue")
            result = {
                "schema": "gh.n3w-t1-u7-r29-source-activation-preflight/1",
                "status": "PASS",
                "read_only": True,
                "source_activation_eligible": True,
                "live_execution_authorized": (
                    plan.get("live_execution_authorized") is True
                ),
                "preflight": verify_prestate(
                    plan,
                    target_sources=False,
                ),
                "host_source_mutation": False,
                "service_stop": False,
                "service_restart": False,
                "transaction_mutation": False,
                "usb_mutation": False,
                "u7_transition": False,
                "u8_plus": False,
            }
        elif mode == "execute":
            result = execute(plan, sys.argv[3], sys.argv[4])
        else:
            raise Stop("mode_invalid")
    except Exception as error:
        result = {
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
        }

    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status") in {
            "PASS",
            "U7_R29_SOURCE_ACTIVATION_PASS",
        }
        else 2
    )


raise SystemExit(main())
'''


def git_text(*args: str) -> str:
    return load_base().git_text(*args)


def sha_file(path: Path) -> str:
    return load_base().sha_file(path)


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

    expected_state = {
        "granted": bool(execute),
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    if (
        document.get("authorization_state") != expected_state
        or document.get("live_execution_authorized") is not execute
    ):
        raise Stop("manifest_authorization_state_invalid")

    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


def remote_mode(transport, mode, plan, *extra, timeout=300):
    payload = base64.b64encode(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    completed = transport.run_remote(
        ["python3", "-B", "-c", REMOTE_SCRIPT, mode, payload, *extra],
        timeout=timeout,
        check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except Exception:
        result = {"status": "STOP", "reason": "remote_result_invalid"}
    return completed, result


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
        "schema": "gh.n3w-t1-u7-r29-source-activation-local-result/1",
        "status": "STOP",
        "read_only_preflight": bool(args.preflight_only),
        "t1_access": False,
        "remote_staging": False,
        "remote_execute_invoked": False,
        "remote_execute_result_observed": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "host_source_mutation": False,
        "service_stop": False,
        "service_restart": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u7_transition": False,
        "u8_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    base = load_base()

    try:
        manifest = read_manifest(
            args.expected_package_commit,
            execute=bool(args.execute),
        )
        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_live_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "authorization_id": manifest["authorization_id"],
                "confirmation": manifest["confirmation"],
                "live_execution_authorized": (
                    manifest["live_execution_authorized"]
                ),
                "authorization_state": manifest["authorization_state"],
                "state_root": manifest["state_root"],
                "remote_staging_root": manifest["remote_staging_root"],
                "remote_paths": manifest["remote_paths"],
                "remote_names": REMOTE_NAMES,
                "fixed_predecessor_sha256": (
                    manifest["fixed_predecessor_sha256"]
                ),
                "dynamic_predecessor_git_blobs": (
                    manifest["dynamic_predecessor_git_blobs"]
                ),
                "unchanged_source_sha256": (
                    manifest["unchanged_source_sha256"]
                ),
                "target_sha256": {
                    key: sha_file(path)
                    for key, path in TARGETS.items()
                },
            }
        )

        transport_type = base.load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        pre_transport, preflight = remote_mode(
            transport,
            "preflight",
            plan,
            timeout=240,
        )
        base.write_remote_evidence(
            evidence,
            "preflight_remote",
            pre_transport,
        )
        base.write_private_json(evidence / "preflight.json", preflight)
        if (
            pre_transport.returncode != 0
            or preflight.get("status") != "PASS"
        ):
            raise Stop(
                "r29_preflight_failed:"
                + str(preflight.get("reason"))
            )

        if args.preflight_only:
            result.update(preflight)
            result["t1_access"] = True
            return_code = 0
        else:
            if (
                args.authorization_id != GATE_ID
                or args.confirm != CONFIRMATION
            ):
                raise Stop("authorization_invalid")

            stage = manifest["remote_staging_root"]
            transport.run_remote(
                ["install", "-d", "-m", "0700", stage],
                timeout=30,
            )
            for key, source in TARGETS.items():
                transport.scp_to(
                    source,
                    stage + "/" + REMOTE_NAMES[key],
                    timeout=180,
                )
            transport.run_remote(
                [
                    "chmod",
                    "0600",
                    *[
                        stage + "/" + REMOTE_NAMES[key]
                        for key in TARGETS
                    ],
                ],
                timeout=30,
            )
            result["remote_staging"] = True
            result["remote_execute_invoked"] = True

            try:
                execute_transport, remote = remote_mode(
                    transport,
                    "execute",
                    plan,
                    args.authorization_id,
                    args.confirm,
                    timeout=600,
                )
            except Exception:
                result.update(
                    status="STOP_UNKNOWN",
                    authorization_claimed=True,
                    authorization_consumed=True,
                    replay_permitted=False,
                    remote_execute_result_observed=False,
                )
                raise

            result["remote_returncode"] = execute_transport.returncode
            if not all(
                key in remote
                for key in (
                    "authorization_claimed",
                    "authorization_consumed",
                    "replay_permitted",
                )
            ):
                result.update(
                    status="STOP_UNKNOWN",
                    reason="remote_execute_claim_state_unknown",
                    authorization_claimed=True,
                    authorization_consumed=True,
                    replay_permitted=False,
                    remote_execute_result_observed=False,
                )
            else:
                result.update(remote)
                result["remote_execute_result_observed"] = True

            result["t1_access"] = True
            base.write_remote_evidence(
                evidence,
                "execute_remote",
                execute_transport,
            )
            return_code = (
                0
                if (
                    execute_transport.returncode == 0
                    and result.get("status")
                    == "U7_R29_SOURCE_ACTIVATION_PASS"
                )
                else 2
            )
    except Exception as error:
        if result.get("status") in {
            "PASS",
            "U7_R29_SOURCE_ACTIVATION_PASS",
        }:
            result["completed_remote_status"] = result["status"]
            result["status"] = "STOP_POSTSUCCESS_LOCAL"
        result["reason"] = type(error).__name__ + ":" + str(error)[:300]
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception as cleanup_error:
                result["ssh_master_cleanup"] = False
                result["ssh_master_cleanup_error"] = (
                    type(cleanup_error).__name__
                    + ":"
                    + str(cleanup_error)[:240]
                )
                return_code = 2

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
