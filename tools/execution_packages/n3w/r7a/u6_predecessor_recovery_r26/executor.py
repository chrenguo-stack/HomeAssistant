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
    "U6_PREDECESSOR_RECOVERY_R26_20261114_01"
)
CONFIRMATION = "EXECUTE U6 R26 PREDECESSOR RECOVERY: YES"


class Stop(RuntimeError):
    pass


REMOTE_SCRIPT = r'''
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
R25_ROOT = Path(
    "/var/lib/n3w-t1-core-updater/"
    "u6-r25-source-activation-20261114-01"
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


def ipc_status(manager_id, expected_phase):
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
        or value.get("phase") != expected_phase
        or value.get("error_code") is not None
        or value.get("installed_version") != "2026.10.0"
    ):
        raise Stop("ipc_phase_invalid:" + str(value.get("phase")))
    return value


def media_view(plan, transaction, expected_phase, *, require_predecessor_absent):
    mount_path = Path(plan["mount_target"])
    if mount_path.is_symlink() or not mount_path.is_dir():
        raise Stop("u6_mount_target_invalid")

    source = run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE",
            "--target",
            str(mount_path),
        ],
        timeout=30,
    ).stdout.strip()
    fstype = run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "FSTYPE",
            "--target",
            str(mount_path),
        ],
        timeout=30,
    ).stdout.strip()
    options = {
        item.strip()
        for item in run(
            [
                "findmnt",
                "--noheadings",
                "--output",
                "OPTIONS",
                "--target",
                str(mount_path),
            ],
            timeout=30,
        ).stdout.strip().split(",")
        if item.strip()
    }
    if (
        not source.startswith("/dev/")
        or fstype != "ext4"
        or "rw" not in options
        or not {"nodev", "nosuid", "noexec"}.issubset(options)
    ):
        raise Stop("u6_mounted_media_contract_invalid")

    label = run(
        ["blkid", "-s", "LABEL", "-o", "value", source],
        timeout=30,
    ).stdout.strip()
    if label != "N3W-UPDATE":
        raise Stop("u6_media_label_invalid")

    update_dir = mount_path / "n3w-update"
    transaction_dir = update_dir / "transaction"
    phase_document = read_object(transaction_dir / "phase.json")
    if (
        phase_document.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or phase_document.get("phase") != expected_phase
        or phase_document.get("target_artifact_verified") is not True
        or phase_document.get("usb_capacity_verified") is not True
    ):
        raise Stop("u6_usb_transaction_phase_invalid")

    target = update_dir / "target" / "homeassistant-arm64.tar.gz"
    if (
        sha_file(target) != transaction.get("target_archive_sha256")
        or target.stat().st_size != transaction.get("target_archive_size")
    ):
        raise Stop("u6_target_archive_drift")

    predecessor_dir = update_dir / "predecessor"
    predecessor = predecessor_dir / "homeassistant-predecessor.tar.gz"
    entries = []
    if predecessor_dir.exists():
        if predecessor_dir.is_symlink() or not predecessor_dir.is_dir():
            raise Stop("u6_predecessor_directory_invalid")
        entries = sorted(item.name for item in predecessor_dir.iterdir())
    if require_predecessor_absent and entries:
        raise Stop("u6_predecessor_residue_present")

    return {
        "mount_target": str(mount_path),
        "source_observed": True,
        "filesystem_type": fstype,
        "mount_options_required": True,
        "transaction_phase": phase_document.get("phase"),
        "target_sha256": sha_file(target),
        "target_size_bytes": target.stat().st_size,
        "predecessor_entries": entries,
        "predecessor_present": predecessor.is_file() and not predecessor.is_symlink(),
    }


def verify_units_and_containers(plan, expected_ipc_phase):
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

    ipc = ipc_status(
        containers["manager"]["container_id"],
        expected_ipc_phase,
    )
    return units, containers, ipc


def verify_prestate(plan):
    transaction = read_object(TX_PATH)
    if (
        transaction.get("phase") != "U5_INSTALL_REQUESTED_REVALIDATING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
    ):
        raise Stop("u6_u5_transaction_invalid")
    transaction_sha = sha_file(TX_PATH)
    if transaction_sha != plan["transaction_sha256"]:
        raise Stop("u6_u5_transaction_sha256_drift")

    r25_claim = read_object(R25_ROOT / "authorization_claim.json")
    if (
        r25_claim.get("authorization_id") != plan["r25_gate_id"]
        or r25_claim.get("claimed") is not True
        or r25_claim.get("consumed") is not True
        or r25_claim.get("replay_permitted") is not False
    ):
        raise Stop("r25_claim_invalid")

    sources = {}
    for path, expected in plan["installed_source_sha256"].items():
        observed = sha_file(path)
        if observed != expected:
            raise Stop("installed_source_drift:" + Path(path).name)
        sources[path] = observed

    units, containers, ipc = verify_units_and_containers(
        plan,
        "INSTALL_REQUESTED_REVALIDATING",
    )
    media = media_view(
        plan,
        transaction,
        "U5_INSTALL_REQUESTED_REVALIDATING",
        require_predecessor_absent=True,
    )
    return {
        "transaction_phase": transaction["phase"],
        "transaction_sha256": transaction_sha,
        "sources": sources,
        "units": units,
        "containers": containers,
        "ipc": ipc,
        "media": media,
    }


def observe_post(plan, pre, predecessor):
    transaction = read_object(TX_PATH)
    if (
        transaction.get("phase") != "U6_PREDECESSOR_RECOVERY_PREPARING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
    ):
        raise Stop("u6_post_transaction_invalid")

    transaction_sha = sha_file(TX_PATH)
    if transaction_sha == pre["transaction_sha256"]:
        raise Stop("u6_transaction_not_mutated")

    media = media_view(
        plan,
        transaction,
        "U6_PREDECESSOR_RECOVERY_PREPARING",
        require_predecessor_absent=False,
    )
    predecessor_path = (
        Path(plan["mount_target"])
        / "n3w-update"
        / "predecessor"
        / "homeassistant-predecessor.tar.gz"
    )
    if (
        predecessor_path.is_symlink()
        or not predecessor_path.is_file()
        or predecessor_path.stat().st_size
        != predecessor.get("archive_size_bytes")
        or sha_file(predecessor_path) != predecessor.get("archive_sha256")
        or predecessor.get("kind") != "predecessor"
        or predecessor.get("image_ref") != transaction.get("current_image_ref")
        or predecessor.get("verified") is not True
        or predecessor.get("fsynced") is not True
    ):
        raise Stop("u6_predecessor_recovery_invalid")

    units, containers, ipc = verify_units_and_containers(
        plan,
        "PREDECESSOR_RECOVERY_PREPARING",
    )
    for name in ("host", "services_owner", "broker_owner"):
        if units[name]["MainPID"] != pre["units"][name]["MainPID"]:
            raise Stop("u6_unit_pid_drift:" + name)
    for name in ("manager", "homeassistant", "broker"):
        if containers[name]["container_id"] != pre["containers"][name]["container_id"]:
            raise Stop("u6_container_identity_drift:" + name)

    return {
        "transaction_phase": transaction["phase"],
        "transaction_sha256": transaction_sha,
        "predecessor": predecessor,
        "media": media,
        "units": units,
        "containers": containers,
        "ipc": ipc,
    }


def invoke_product_controller(plan):
    sys.path.insert(0, "/opt/HomeAssistant/tools")
    try:
        from n3w_t1_core_updater_ha_install import (
            HaUsbU6PredecessorController,
        )
        from n3w_t1_core_updater_ha_prepare_host import (
            SubprocessPrepareBackend,
        )
        from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
    except Exception as error:
        raise Stop(
            "u6_product_import_failed:"
            + type(error).__name__
            + ":"
            + str(error)[:180]
        ) from error

    store = HaUsbStateStore()
    backend = SubprocessPrepareBackend()
    controller = HaUsbU6PredecessorController(
        transaction_store=store,
        backend=backend,
    )
    with store.lock():
        result = controller.prepare_or_resume()
    if result.resumed_from_u6 is not False:
        raise Stop("u6_unexpected_resume")
    return result.predecessor.public()


def partial_observation(plan):
    observed = {
        "transaction_phase": None,
        "transaction_mutation": False,
        "u6_transition": False,
        "usb_mutation": False,
        "usb_transaction_metadata_mutation": False,
    }
    try:
        transaction = read_object(TX_PATH)
        observed["transaction_phase"] = transaction.get("phase")
        if transaction.get("phase") == "U6_PREDECESSOR_RECOVERY_PREPARING":
            observed["transaction_mutation"] = True
            observed["u6_transition"] = True
    except Exception:
        pass
    try:
        phase = read_object(
            Path(plan["mount_target"])
            / "n3w-update"
            / "transaction"
            / "phase.json"
        )
        if phase.get("phase") == "U6_PREDECESSOR_RECOVERY_PREPARING":
            observed["usb_transaction_metadata_mutation"] = True
            observed["usb_mutation"] = True
    except Exception:
        pass
    predecessor_dir = (
        Path(plan["mount_target"]) / "n3w-update" / "predecessor"
    )
    try:
        if predecessor_dir.is_dir() and any(predecessor_dir.iterdir()):
            observed["usb_mutation"] = True
    except Exception:
        pass
    return observed


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
        raise Stop("r26_not_authorized")
    if (
        authorization != plan["authorization_id"]
        or confirmation != plan["confirmation"]
    ):
        raise Stop("r26_authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("r26_state_root_exists")

    pre = verify_prestate(plan)
    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    fsync_dir(state_root.parent)
    durable_json(state_root / "preflight.json", pre)

    result = {
        "schema": "gh.n3w-t1-u6-r26-predecessor-recovery/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "authorization_claim_persistence_unknown": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "usb_transaction_metadata_mutation": False,
        "predecessor_recovery_prepared": False,
        "service_restart": False,
        "ha_quiesced": False,
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
        postclaim = verify_prestate(plan)
        if postclaim["transaction_sha256"] != pre["transaction_sha256"]:
            raise Stop("r26_postclaim_transaction_drift")
        for name in ("host", "services_owner", "broker_owner"):
            if postclaim["units"][name]["MainPID"] != pre["units"][name]["MainPID"]:
                raise Stop("r26_postclaim_unit_pid_drift:" + name)

        predecessor = invoke_product_controller(plan)
        post = observe_post(plan, pre, predecessor)
        result.update(
            status="U6_R26_PREDECESSOR_RECOVERY_PASS",
            transaction_mutation=True,
            usb_mutation=True,
            usb_transaction_metadata_mutation=True,
            predecessor_recovery_prepared=True,
            u6_transition=True,
            post=post,
        )
        durable_json(state_root / "success.json", result)
        return result
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        result.update(partial_observation(plan))
        result["status"] = "STOP_PARTIAL"
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
            "U6_PREDECESSOR_RECOVERY_R26_20261114_01"
        ):
            raise Stop("gate_id_invalid")

        if mode == "preflight":
            if (
                Path(plan["state_root"]).exists()
                or Path(plan["state_root"]).is_symlink()
            ):
                raise Stop("r26_state_root_residue")
            pre = verify_prestate(plan)
            result = {
                "schema": "gh.n3w-t1-u6-r26-predecessor-recovery-preflight/1",
                "status": "PASS",
                "read_only": True,
                "u6_predecessor_recovery_eligible": True,
                "live_execution_authorized": (
                    plan.get("live_execution_authorized") is True
                ),
                "preflight": pre,
                "transaction_mutation": False,
                "usb_mutation": False,
                "usb_transaction_metadata_mutation": False,
                "service_restart": False,
                "ha_quiesced": False,
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
            "U6_R26_PREDECESSOR_RECOVERY_PASS",
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
        "n3w_r26_transport",
        SSH_TRANSPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport


def remote_mode(transport, mode, plan, *extra, timeout=2400):
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
    lines = [
        line.strip()
        for line in (completed.stdout or "").splitlines()
        if line.strip()
    ]
    if not lines:
        result = {"status": "STOP", "reason": "remote_result_invalid"}
    else:
        try:
            result = json.loads(lines[-1])
        except Exception:
            result = {"status": "STOP", "reason": "remote_result_invalid"}
        if not isinstance(result, dict):
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
        "schema": "gh.n3w-t1-u6-r26-predecessor-recovery-local-result/1",
        "status": "STOP",
        "read_only_preflight": bool(args.preflight_only),
        "t1_access": False,
        "remote_execute_invoked": False,
        "remote_execute_result_observed": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "usb_transaction_metadata_mutation": False,
        "service_restart": False,
        "ha_quiesced": False,
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
                "mount_target": manifest["mount_target"],
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
            timeout=300,
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
                "r26_preflight_failed:"
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

            result["remote_execute_invoked"] = True
            try:
                execute_transport, remote = remote_mode(
                    transport,
                    "execute",
                    plan,
                    args.authorization_id,
                    args.confirm,
                    timeout=2400,
                )
                result["remote_execute_result_observed"] = True
                write_remote_evidence(
                    evidence,
                    "execute_remote",
                    execute_transport,
                )
                write_private_json(
                    evidence / "execute.json",
                    remote,
                )
            except Exception as error:
                result.update(
                    status="STOP_UNKNOWN",
                    reason=(
                        "remote_execute_claim_state_unknown:"
                        + type(error).__name__
                        + ":"
                        + str(error)[:180]
                    ),
                    authorization_claimed=True,
                    authorization_consumed=True,
                    replay_permitted=False,
                )
                return_code = 2
            else:
                if not isinstance(remote, dict):
                    result.update(
                        status="STOP_UNKNOWN",
                        reason="remote_execute_result_invalid",
                        authorization_claimed=True,
                        authorization_consumed=True,
                        replay_permitted=False,
                    )
                    return_code = 2
                else:
                    result.update(remote)
                    result["t1_access"] = True
                    result["remote_execute_invoked"] = True
                    result["remote_execute_result_observed"] = True
                    if execute_transport.returncode == 0 and remote.get(
                        "status"
                    ) == "U6_R26_PREDECESSOR_RECOVERY_PASS":
                        return_code = 0
                    else:
                        return_code = 2
    except Exception as error:
        if result.get("remote_execute_invoked"):
            result.update(
                status="STOP_UNKNOWN",
                reason=(
                    "postinvoke_local_failure:"
                    + type(error).__name__
                    + ":"
                    + str(error)[:180]
                ),
                authorization_claimed=True,
                authorization_consumed=True,
                replay_permitted=False,
            )
        else:
            result["status"] = "STOP"
            result["reason"] = (
                type(error).__name__ + ":" + str(error)[:240]
            )
        return_code = 2
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception as error:
                result["ssh_master_cleanup"] = False
                result["ssh_master_cleanup_error"] = (
                    type(error).__name__ + ":" + str(error)[:180]
                )
                if result.get("remote_execute_invoked"):
                    result["authorization_claimed"] = True
                    result["authorization_consumed"] = True
                    result["replay_permitted"] = False
                    if return_code == 0:
                        result["completed_remote_status"] = result.get(
                            "status"
                        )
                        result["status"] = "STOP_POSTSUCCESS_CLEANUP"
                    return_code = 2

        try:
            if "evidence" in locals():
                write_private_json(evidence / "result.json", result)
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
