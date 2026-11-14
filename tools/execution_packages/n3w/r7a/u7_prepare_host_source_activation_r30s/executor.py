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
TARGET = ROOT / "tools" / "n3w_t1_core_updater_ha_prepare_host.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U7_PREPARE_HOST_SOURCE_ACTIVATION_R30S_20261115_01"
)
CONFIRMATION = "EXECUTE U7 R30S PREPARE HOST SOURCE ACTIVATION: YES"


class Stop(RuntimeError):
    pass


def load_base():
    spec = importlib.util.spec_from_file_location("n3w_r30s_base", BASE_EXECUTOR)
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
R29 = Path(
    "/var/lib/n3w-t1-core-updater/u7-r29-source-activation-20261114-01"
)
TARGET = Path("/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_prepare_host.py")
TOOLS_ROOT = Path("/opt/HomeAssistant/tools")
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
        raise Stop("required_file_invalid:" + path.name)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha1(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + path.name)
    digest = hashlib.sha1()
    digest.update(
        ("blob " + str(path.stat().st_size) + "\0").encode("ascii")
    )
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + path.name)
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise Stop("required_file_metadata_invalid:" + path.name)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("required_json_invalid:" + path.name) from error
    if not isinstance(value, dict):
        raise Stop("required_object_invalid:" + path.name)
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


def durable_json_once(path, value):
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
        raise Stop("staged_source_invalid")
    descriptor, raw = tempfile.mkstemp(
        prefix="." + destination.name + ".",
        dir=destination.parent,
    )
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, 0o644)
        with os.fdopen(descriptor, "wb", closefd=True) as output:
            with source.open("rb") as input_stream:
                shutil.copyfileobj(input_stream, output)
            output.flush()
            os.fsync(output.fileno())
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
    return {"units": units, "containers": containers}


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
        raise Stop("r30s_u6_transaction_invalid")
    return transaction


def verify_r26(plan):
    claim = read_object(R26 / "authorization_claim.json")
    success = read_object(R26 / "success.json")
    post = success.get("post")
    if (
        claim.get("authorization_id") != plan["r26_gate_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or success.get("status") != "U6_R26_PREDECESSOR_RECOVERY_PASS"
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or not isinstance(post, dict)
        or post.get("transaction_sha256") != plan["transaction_sha256"]
    ):
        raise Stop("r26_authority_invalid")


def verify_r29(plan):
    claim = read_object(R29 / "authorization_claim.json")
    success = read_object(R29 / "success.json")
    post = success.get("post")
    if (
        claim.get("authorization_id") != plan["r29_gate_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or success.get("status") != "U7_R29_SOURCE_ACTIVATION_PASS"
        or success.get("authorization_claimed") is not True
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or success.get("source_activated") is not True
        or success.get("activated_source_file_count") != 7
        or not isinstance(post, dict)
        or post.get("transaction_sha256") != plan["transaction_sha256"]
    ):
        raise Stop("r29_authority_invalid")


def verify_sources(plan, *, target=False):
    observed = {}
    expected_target = (
        plan["target_sha256"]
        if target
        else plan["predecessor_sha256"]
    )
    digest = sha_file(TARGET)
    if digest != expected_target:
        raise Stop("prepare_host_source_drift")
    observed[TARGET.name] = {
        "sha256": digest,
        "git_blob_sha1": git_blob_sha1(TARGET),
    }
    for raw_path, expected in plan["unchanged_source_sha256"].items():
        path = Path(raw_path)
        current = sha_file(path)
        if current != expected:
            raise Stop("unchanged_source_drift:" + path.name)
        observed[path.name] = {"sha256": current}
    return observed


def installed_capability(expected):
    script = (
        "import sys;"
        "sys.path.insert(0,'/opt/HomeAssistant/tools');"
        "import n3w_t1_core_updater_ha_prepare_host as m;"
        "print('YES' if hasattr(m.SubprocessPrepareBackend,"
        "'backup_capacity_revalidation') else 'NO')"
    )
    completed = run(
        ["python3", "-B", "-c", script],
        timeout=90,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0:
        raise Stop("installed_prepare_host_import_failed")
    value = completed.stdout.strip()
    if value != expected:
        raise Stop("prepare_host_capability_state_invalid")
    return value


def staged_import_preflight(plan):
    stage = Path(plan["remote_staging_root"])
    staged = stage / TARGET.name
    if sha_file(staged) != plan["target_sha256"]:
        raise Stop("staged_prepare_host_sha_invalid")
    script = (
        "import sys;"
        "sys.path.insert(0,sys.argv[1]);"
        "sys.path.insert(1,'/opt/HomeAssistant/tools');"
        "import n3w_t1_core_updater_ha_prepare_host as m;"
        "assert hasattr(m.SubprocessPrepareBackend,"
        "'backup_capacity_revalidation');"
        "print('PASS')"
    )
    completed = run(
        ["python3", "-B", "-c", script, str(stage)],
        timeout=90,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0 or completed.stdout.strip() != "PASS":
        raise Stop("staged_prepare_host_import_failed")
    return True


def verify_prestate(plan):
    verify_transaction(plan)
    verify_r26(plan)
    verify_r29(plan)
    sources = verify_sources(plan, target=False)
    capability = installed_capability("NO")
    runtime = verify_runtime(plan)
    return {
        "transaction_sha256": sha_file(TX),
        "sources": sources,
        "installed_u7_capacity_method": capability,
        "runtime": runtime,
        "r26_consumed_no_replay": True,
        "r29_consumed_no_replay": True,
    }


def rollback(plan, backup_path):
    result = {"attempted": True, "status": "STOP", "errors": []}
    try:
        atomic_install(backup_path, TARGET)
        verify_sources(plan, target=False)
        installed_capability("NO")
        verify_runtime(plan)
        result["status"] = "PASS"
    except Exception as error:
        result["errors"].append(
            type(error).__name__ + ":" + str(error)[:180]
        )
    return result


def read_status(plan):
    state_root = Path(plan["state_root"])
    if not state_root.exists():
        return {
            "schema": "gh.n3w-t1-u7-r30s-status/1",
            "status": "NOT_STARTED",
            "terminal": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
        }
    if state_root.is_symlink() or not state_root.is_dir():
        raise Stop("r30s_state_root_invalid")
    for name in ("success.json", "failure.json"):
        path = state_root / name
        if path.exists():
            value = read_object(path)
            value["terminal"] = True
            value["reconciled_from_ledger"] = True
            return value
    claim_path = state_root / "authorization_claim.json"
    claim = read_object(claim_path) if claim_path.exists() else None
    return {
        "schema": "gh.n3w-t1-u7-r30s-status/1",
        "status": "RUNNING_OR_INTERRUPTED",
        "terminal": False,
        "authorization_claimed": bool(
            claim and claim.get("claimed") is True
        ),
        "authorization_consumed": bool(
            claim and claim.get("consumed") is True
        ),
        "replay_permitted": False,
    }


def execute(plan, authorization_id, confirmation):
    result = {
        "schema": "gh.n3w-t1-u7-r30s-source-activation/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "source_activated": False,
        "activated_source_file_count": 0,
        "host_source_mutation": False,
        "service_stop": False,
        "service_restart": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u7_transition": False,
        "u8_plus": False,
        "rollback_required": False,
        "rollback": None,
    }
    if (
        authorization_id != plan["authorization_id"]
        or confirmation != plan["confirmation"]
        or plan.get("live_execution_authorized") is not True
        or plan.get("authorization_state") != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("authorization_invalid")

    state_root = Path(plan["state_root"])
    stage_root = Path(plan["remote_staging_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("r30s_state_root_residue")
    if stage_root.is_symlink() or not stage_root.is_dir():
        raise Stop("r30s_staging_root_invalid")

    pre = verify_prestate(plan)
    staged_import_preflight(plan)

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    backup_path = state_root / "preclaim-prepare-host.py"
    shutil.copyfile(TARGET, backup_path)
    os.chmod(backup_path, 0o600)
    os.chown(backup_path, 0, 0)
    if sha_file(backup_path) != plan["predecessor_sha256"]:
        raise Stop("preclaim_backup_sha_invalid")
    durable_json_once(
        state_root / "preclaim.json",
        {
            "schema": "gh.n3w-t1-u7-r30s-preclaim/1",
            "prepare_host_sha256": sha_file(backup_path),
            "transaction_sha256": pre["transaction_sha256"],
        },
    )
    durable_json_once(
        state_root / "authorization_claim.json",
        {
            "schema": "gh.n3w-t1-u7-r30s-authorization-claim/1",
            "gate_id": plan["gate_id"],
            "authorization_id": authorization_id,
            "execution_id": plan["execution_id"],
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
        },
    )
    result.update(
        authorization_claimed=True,
        authorization_consumed=True,
        replay_permitted=False,
    )

    try:
        atomic_install(stage_root / TARGET.name, TARGET)
        result["host_source_mutation"] = True
        verify_sources(plan, target=True)
        installed_capability("YES")
        if sha_file(TX) != plan["transaction_sha256"]:
            raise Stop("transaction_mutated_during_source_activation")
        post_runtime = verify_runtime(plan)
        result.update(
            status="U7_R30S_PREPARE_HOST_SOURCE_ACTIVATION_PASS",
            source_activated=True,
            activated_source_file_count=1,
            transaction_sha256=sha_file(TX),
            post_runtime=post_runtime,
        )
        durable_json_once(state_root / "success.json", result)
        try:
            shutil.rmtree(stage_root)
        except Exception as cleanup_error:
            result["completed_remote_status"] = result["status"]
            result["status"] = "STOP_POSTSUCCESS_CLEANUP"
            result["postsuccess_cleanup_error"] = (
                type(cleanup_error).__name__
                + ":"
                + str(cleanup_error)[:180]
            )
        return result
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        result["rollback_required"] = bool(result["host_source_mutation"])
        if result["rollback_required"]:
            result["rollback"] = rollback(plan, backup_path)
        try:
            durable_json_once(state_root / "failure.json", result)
        except Exception:
            pass
        return result


def main():
    try:
        mode = sys.argv[1]
        plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U7_PREPARE_HOST_SOURCE_ACTIVATION_R30S_20261115_01"
        ):
            raise Stop("gate_id_invalid")

        if mode == "preflight":
            if (
                Path(plan["state_root"]).exists()
                or Path(plan["state_root"]).is_symlink()
            ):
                raise Stop("r30s_state_root_residue")
            if (
                Path(plan["remote_staging_root"]).exists()
                or Path(plan["remote_staging_root"]).is_symlink()
            ):
                raise Stop("r30s_staging_root_residue")
            result = {
                "schema": "gh.n3w-t1-u7-r30s-preflight/1",
                "status": "PASS",
                "read_only": True,
                "source_activation_eligible": True,
                "live_execution_authorized": (
                    plan.get("live_execution_authorized") is True
                ),
                "preflight": verify_prestate(plan),
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
            }
        elif mode == "execute":
            result = execute(plan, sys.argv[3], sys.argv[4])
        elif mode == "status":
            result = read_status(plan)
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
        if result.get("status")
        in {
            "PASS",
            "U7_R30S_PREPARE_HOST_SOURCE_ACTIVATION_PASS",
        }
        else 2
    )


raise SystemExit(main())
'''


def git_text(*args: str) -> str:
    return load_base().git_text(*args)


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
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    try:
        result = json.loads(lines[-1]) if lines else {}
    except Exception:
        result = {}
    if not isinstance(result, dict) or not result:
        result = {"status": "STOP", "reason": "remote_result_invalid"}
    return completed, result


def reconcile_after_invoke(transport, plan, evidence, base):
    try:
        completed, status = remote_mode(
            transport,
            "status",
            plan,
            timeout=90,
        )
        base.write_remote_evidence(
            evidence,
            "status_reconcile_remote",
            completed,
        )
        base.write_private_json(evidence / "status_reconcile.json", status)
        return completed, status
    except Exception as error:
        return None, {
            "status": "STOP_UNKNOWN",
            "terminal": False,
            "reason": "status_reconciliation_failed:"
            + type(error).__name__
            + ":"
            + str(error)[:180],
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_permitted": False,
        }


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
        "schema": "gh.n3w-t1-u7-r30s-local-result/1",
        "status": "STOP",
        "read_only_preflight": bool(args.preflight_only),
        "t1_access": False,
        "remote_staging": False,
        "remote_execute_invoked": False,
        "remote_execute_result_observed": False,
        "status_reconciliation_attempted": False,
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
                "predecessor_sha256": manifest["predecessor_sha256"],
                "target_sha256": manifest["target_sha256"],
                "unchanged_source_sha256": (
                    manifest["unchanged_source_sha256"]
                ),
                "execution_id": args.execution_id,
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
            timeout=300,
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
                "r30s_preflight_failed:"
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
            transport.scp_to(
                TARGET,
                stage + "/" + TARGET.name,
                timeout=180,
            )
            transport.run_remote(
                ["chmod", "0600", stage + "/" + TARGET.name],
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
                result["remote_returncode"] = execute_transport.returncode
                if remote.get("reason") == "remote_result_invalid":
                    raise Stop("remote_execute_result_invalid")
                result.update(remote)
                result["remote_execute_result_observed"] = True
                base.write_remote_evidence(
                    evidence,
                    "execute_remote",
                    execute_transport,
                )
            except Exception as invoke_error:
                result["status_reconciliation_attempted"] = True
                status_transport, status = reconcile_after_invoke(
                    transport,
                    plan,
                    evidence,
                    base,
                )
                if status.get("terminal") is True:
                    result.update(status)
                    result["remote_execute_result_observed"] = True
                    if status_transport is not None:
                        result["remote_returncode"] = (
                            status_transport.returncode
                        )
                else:
                    result.update(
                        status="STOP_UNKNOWN",
                        reason="postinvoke_unknown:"
                        + type(invoke_error).__name__
                        + ":"
                        + str(invoke_error)[:180],
                        authorization_claimed=True,
                        authorization_consumed=True,
                        replay_permitted=False,
                        remote_execute_result_observed=False,
                    )

            result["t1_access"] = True
            return_code = (
                0
                if result.get("status")
                == "U7_R30S_PREPARE_HOST_SOURCE_ACTIVATION_PASS"
                else 2
            )
    except Exception as error:
        if result.get("remote_execute_invoked"):
            result.update(
                status="STOP_UNKNOWN",
                authorization_claimed=True,
                authorization_consumed=True,
                replay_permitted=False,
            )
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
        try:
            if "evidence" in locals():
                base.write_private_json(evidence / "result.json", result)
        except Exception:
            if result.get("remote_execute_invoked"):
                result["authorization_claimed"] = True
                result["authorization_consumed"] = True
                result["replay_permitted"] = False
            return_code = 2

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
