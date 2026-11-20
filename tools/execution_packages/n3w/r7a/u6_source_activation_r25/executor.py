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
TARGET_PREPARE_HOST = ROOT / "tools" / "n3w_t1_core_updater_ha_prepare_host.py"
TARGET_INSTALL = ROOT / "tools" / "n3w_t1_core_updater_ha_install.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U6_SOURCE_ACTIVATION_R25_20261114_01"
)
CONFIRMATION = "EXECUTE U6 R25 SOURCE ACTIVATION: YES"


class Stop(RuntimeError):
    pass


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

TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
R23_ROOT = Path(
    "/var/lib/n3w-t1-core-updater/"
    "kf153-r23-u5-ipc-source-activation-20261113-01"
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


def verify_prestate(plan, *, target_sources):
    transaction = read_object(TX_PATH)
    if (
        transaction.get("phase") != "U5_INSTALL_REQUESTED_REVALIDATING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
    ):
        raise Stop("u5_transaction_invalid")
    tx_sha = sha_file(TX_PATH)
    if tx_sha != plan["transaction_sha256"]:
        raise Stop("u5_transaction_sha256_drift")

    claim = read_object(R23_ROOT / "authorization_claim.json")
    if (
        claim.get("authorization_id") != plan["r23_gate_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
    ):
        raise Stop("r23_claim_invalid")

    sources = {}
    for path, predecessor in plan["installed_source_sha256"].items():
        if path == plan["prepare_host_remote_path"] and target_sources:
            expected = plan["target_prepare_host_sha256"]
        else:
            expected = predecessor
        observed = sha_file(path)
        if observed != expected:
            raise Stop("installed_source_drift:" + Path(path).name)
        sources[path] = observed

    install_path = Path(plan["install_remote_path"])
    if target_sources:
        if (
            install_path.is_symlink()
            or not install_path.is_file()
            or sha_file(install_path) != plan["target_install_sha256"]
        ):
            raise Stop("install_source_target_invalid")
        sources[str(install_path)] = plan["target_install_sha256"]
    else:
        if install_path.exists() or install_path.is_symlink():
            raise Stop("install_source_predecessor_not_absent")

    units = {
        "host": service_state(HOST_UNIT),
        "services_owner": service_state(SERVICES_UNIT),
        "broker_owner": service_state(BROKER_UNIT),
    }
    for name, observed in units.items():
        if (
            observed.get("returncode") != 0
            or observed.get("ActiveState") != "active"
            or observed.get("SubState") != "running"
            or observed.get("Result") != "success"
            or observed.get("NRestarts") != "0"
        ):
            raise Stop("unit_not_healthy:" + name)

    containers = {}
    for name, expected in plan["containers"].items():
        observed = docker_view(expected["image"])
        if (
            observed["runtime_image_id"] != expected["runtime_image_id"]
            or observed["status"] != "running"
            or observed["restart_count"] != 0
        ):
            raise Stop("container_drift:" + name)
        containers[name] = observed

    ipc = ipc_status(containers["manager"]["container_id"])
    return {
        "transaction_phase": transaction["phase"],
        "transaction_sha256": tx_sha,
        "sources": sources,
        "units": units,
        "containers": containers,
        "ipc": ipc,
    }


def verify_importable(plan):
    script = (
        "import sys;"
        "sys.path.insert(0,'/opt/HomeAssistant/tools');"
        "import n3w_t1_core_updater_ha_prepare_host;"
        "import n3w_t1_core_updater_ha_install;"
        "print('PASS')"
    )
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = run(
        ["python3", "-B", "-c", script],
        timeout=60,
        check=False,
        env=environment,
    )
    if completed.returncode != 0 or completed.stdout.strip() != "PASS":
        raise Stop("activated_source_import_failed")


def rollback(plan, backup_dir):
    result = {"attempted": True, "status": "STOP", "errors": []}
    try:
        old_prepare = Path(backup_dir) / "prepare_host.py"
        atomic_install(old_prepare, plan["prepare_host_remote_path"])
        install_path = Path(plan["install_remote_path"])
        if install_path.exists() or install_path.is_symlink():
            if install_path.is_symlink() or not install_path.is_file():
                raise Stop("rollback_install_path_invalid")
            install_path.unlink()
            fsync_dir(install_path.parent)
        result["post"] = verify_prestate(plan, target_sources=False)
        result["status"] = "PASS"
    except Exception as error:
        result["errors"].append(
            type(error).__name__ + ":" + str(error)[:240]
        )
    return result


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
        raise Stop("r25_not_authorized")
    if (
        authorization != plan["authorization_id"]
        or confirmation != plan["confirmation"]
    ):
        raise Stop("r25_authorization_invalid")

    state_root = Path(plan["state_root"])
    stage_root = Path(plan["remote_staging_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("r25_state_root_exists")

    staged_prepare = stage_root / "prepare_host.py"
    staged_install = stage_root / "install.py"
    if (
        staged_prepare.is_symlink()
        or not staged_prepare.is_file()
        or sha_file(staged_prepare) != plan["target_prepare_host_sha256"]
        or staged_install.is_symlink()
        or not staged_install.is_file()
        or sha_file(staged_install) != plan["target_install_sha256"]
    ):
        raise Stop("r25_staged_source_invalid")

    pre = verify_prestate(plan, target_sources=False)
    backup_dir = stage_root / ".preclaim-backup"
    backup_dir.mkdir(mode=0o700)
    os.chown(backup_dir, 0, 0)
    old_prepare = backup_dir / "prepare_host.py"
    shutil.copyfile(plan["prepare_host_remote_path"], old_prepare)
    os.chmod(old_prepare, 0o600)
    os.chown(old_prepare, 0, 0)
    if (
        sha_file(old_prepare)
        != plan["installed_source_sha256"][plan["prepare_host_remote_path"]]
    ):
        raise Stop("r25_backup_drift")

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    fsync_dir(state_root.parent)
    durable_json(state_root / "preflight.json", pre)

    result = {
        "schema": "gh.n3w-t1-u6-r25-source-activation/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "authorization_claim_persistence_unknown": False,
        "host_source_mutation": False,
        "service_restart": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "usb_transaction_metadata_mutation": False,
        "u6_transition": False,
        "u7_plus": False,
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
        if postclaim["transaction_sha256"] != pre["transaction_sha256"]:
            raise Stop("postclaim_transaction_drift")
        if (
            postclaim["units"]["host"]["MainPID"]
            != pre["units"]["host"]["MainPID"]
        ):
            raise Stop("host_pid_drift_before_activation")

        atomic_install(
            staged_prepare,
            plan["prepare_host_remote_path"],
        )
        result["host_source_mutation"] = True
        atomic_install(
            staged_install,
            plan["install_remote_path"],
        )

        verify_importable(plan)
        post = verify_prestate(plan, target_sources=True)
        if post["transaction_sha256"] != pre["transaction_sha256"]:
            raise Stop("u5_transaction_drift_after_activation")
        for name in ("host", "services_owner", "broker_owner"):
            if post["units"][name]["MainPID"] != pre["units"][name]["MainPID"]:
                raise Stop("unit_pid_drift_after_activation:" + name)

        result.update(
            status="U6_R25_SOURCE_ACTIVATION_PASS",
            source_activated=True,
            u5_preserved=True,
            import_validation=True,
            post=post,
        )
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
            try:
                durable_json(
                    state_root / "postsuccess_cleanup_failure.json",
                    result,
                )
            except Exception:
                pass
        return result
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        result["rollback_required"] = bool(result["host_source_mutation"])
        if result["rollback_required"]:
            result["rollback"] = rollback(plan, backup_dir)
        try:
            durable_json(state_root / "failure.json", result)
        except Exception:
            pass
        return result


def main():
    mode = sys.argv[1]
    plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
    try:
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U6_SOURCE_ACTIVATION_R25_20261114_01"
        ):
            raise Stop("gate_id_invalid")

        if mode == "preflight":
            if (
                Path(plan["state_root"]).exists()
                or Path(plan["state_root"]).is_symlink()
            ):
                raise Stop("r25_state_root_residue")
            if (
                Path(plan["remote_staging_root"]).exists()
                or Path(plan["remote_staging_root"]).is_symlink()
            ):
                raise Stop("r25_staging_root_residue")
            pre = verify_prestate(plan, target_sources=False)
            result = {
                "schema": "gh.n3w-t1-u6-r25-source-activation-preflight/1",
                "status": "PASS",
                "read_only": True,
                "source_activation_eligible": True,
                "live_execution_authorized": (
                    plan.get("live_execution_authorized") is True
                ),
                "preflight": pre,
                "host_source_mutation": False,
                "service_restart": False,
                "transaction_mutation": False,
                "usb_mutation": False,
                "u6_transition": False,
                "u7_plus": False,
            }
        elif mode == "execute":
            result = execute(plan, sys.argv[3], sys.argv[4])
        else:
            raise Stop("mode_invalid")
    except Exception as error:
        result = {
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:240],
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
        }

    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status") in {
            "PASS",
            "U6_R25_SOURCE_ACTIVATION_PASS",
        }
        else 2
    )


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
        {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
        if execute
        else {
            "granted": False,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    )
    if document.get("authorization_state") != expected_state:
        raise Stop("manifest_authorization_state_invalid")
    if document.get("live_execution_authorized") is not execute:
        raise Stop("manifest_execution_authority_invalid")

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


def write_private_json(path: Path, value: Any) -> None:
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


def write_private_text(path: Path, value: str) -> None:
    payload = value.encode("utf-8")
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


def write_remote_evidence(evidence: Path, prefix: str, completed) -> None:
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    write_private_json(
        evidence / (prefix + "_transport.json"),
        {
            "returncode": completed.returncode,
            "stdout_length": len(stdout),
            "stderr_length": len(stderr),
            "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        },
    )
    write_private_text(evidence / (prefix + "_stdout.txt"), stdout)
    write_private_text(evidence / (prefix + "_stderr.txt"), stderr)


def load_transport():
    spec = importlib.util.spec_from_file_location(
        "n3w_r25_transport",
        SSH_TRANSPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport


def remote_mode(transport, mode, plan, *extra, timeout=300):
    payload = base64.b64encode(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    completed = transport.run_remote(
        ["python3", "-c", REMOTE_SCRIPT, mode, payload, *extra],
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
        "schema": "gh.n3w-t1-u6-r25-source-activation-local-result/1",
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
        "service_restart": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u6_transition": False,
        "u7_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    try:
        manifest = read_manifest(
            args.expected_package_commit,
            execute=bool(args.execute),
        )
        evidence = prepare_evidence_root(args.evidence_root)
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
                "prepare_host_remote_path": (
                    manifest["prepare_host_remote_path"]
                ),
                "install_remote_path": manifest["install_remote_path"],
                "target_prepare_host_sha256": sha_file(
                    TARGET_PREPARE_HOST
                ),
                "target_install_sha256": sha_file(TARGET_INSTALL),
            }
        )

        transport_type = load_transport()
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
        write_remote_evidence(
            evidence,
            "preflight_remote",
            pre_transport,
        )
        write_private_json(evidence / "preflight.json", preflight)
        if (
            pre_transport.returncode != 0
            or preflight.get("status") != "PASS"
        ):
            raise Stop(
                "r25_preflight_failed:"
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
            remote_prepare = stage + "/prepare_host.py"
            remote_install = stage + "/install.py"
            transport.scp_to(
                TARGET_PREPARE_HOST,
                remote_prepare,
                timeout=180,
            )
            transport.scp_to(
                TARGET_INSTALL,
                remote_install,
                timeout=180,
            )
            transport.run_remote(
                [
                    "chmod",
                    "0600",
                    remote_prepare,
                    remote_install,
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
            write_remote_evidence(
                evidence,
                "execute_remote",
                execute_transport,
            )
            return_code = (
                0
                if (
                    execute_transport.returncode == 0
                    and result.get("status")
                    == "U6_R25_SOURCE_ACTIVATION_PASS"
                )
                else 2
            )
    except Exception as error:
        if result.get("status") in {
            "PASS",
            "U6_R25_SOURCE_ACTIVATION_PASS",
        }:
            result["completed_remote_status"] = result["status"]
            result["status"] = "STOP_POSTSUCCESS_LOCAL"
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
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
                if result.get("status") in {
                    "PASS",
                    "U6_R25_SOURCE_ACTIVATION_PASS",
                }:
                    result["completed_remote_status"] = result["status"]
                    result["status"] = "STOP_POSTSUCCESS_CLEANUP"
                return_code = 2

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
