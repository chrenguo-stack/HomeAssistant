#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
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
    "U8_POST_R33_READONLY_RECONCILIATION_R34_20261115_01"
)
MANIFEST_SCHEMA = "gh.n3w-t1-u8-r34-readonly-reconciliation-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u8-r34-local-result/1"
REMOTE_SCHEMA = "gh.n3w-t1-u8-r34-readonly-reconciliation/1"
TIMEOUT_SECONDS = 600


class Stop(RuntimeError):
    pass


def load_base():
    spec = importlib.util.spec_from_file_location("n3w_r34_base", BASE_EXECUTOR)
    if spec is None or spec.loader is None:
        raise Stop("base_executor_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REMOTE_SCRIPT = r'''
import hashlib
import json
import re
import stat
import subprocess
import sys
from pathlib import Path

TX = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
TOOLS_ROOT = Path("/opt/HomeAssistant/tools")
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
HOST_UNIT = "n3w-t1-ha-ota.service"


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
        raise Stop("required_file_invalid:" + path.name)
    digest = hashlib.sha256()
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


def require_unit(unit, *, active):
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
    if completed.returncode != 0:
        raise Stop("unit_probe_failed:" + unit)
    result = {"returncode": completed.returncode}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    if active:
        if (
            result.get("ActiveState") != "active"
            or result.get("SubState") != "running"
            or result.get("Result") != "success"
            or result.get("NRestarts") != "0"
        ):
            raise Stop("unit_not_healthy:" + unit)
    else:
        if (
            result.get("ActiveState") not in {"inactive", "failed"}
            or result.get("MainPID") != "0"
            or result.get("NRestarts") != "0"
        ):
            raise Stop("unit_not_quiesced:" + unit)
    return result


def docker_snapshot(expected):
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
        result["container_id"] != expected["container_id"]
        or result["runtime_image_id"] != expected["runtime_image_id"]
        or result["configured_image_ref"] != expected["image"]
        or result["restart_count"] != 0
    ):
        raise Stop("container_identity_drift:" + expected["image"])
    return result


def verify_runtime(plan):
    units = {
        "host": require_unit(HOST_UNIT, active=True),
        "services_owner": require_unit(SERVICES_UNIT, active=False),
        "broker_owner": require_unit(BROKER_UNIT, active=True),
    }
    containers = {
        name: docker_snapshot(expected)
        for name, expected in plan["containers"].items()
    }
    if containers["broker"].get("status") != "running":
        raise Stop("broker_not_running")
    if containers["manager"].get("status") == "running":
        raise Stop("manager_not_quiesced")
    if containers["homeassistant"].get("status") == "running":
        raise Stop("homeassistant_not_quiesced")
    return {"units": units, "containers": containers}


def verify_images(plan):
    predecessor = run(
        ["docker", "image", "inspect", plan["predecessor_image"]],
        timeout=45,
        check=False,
    )
    if predecessor.returncode != 0:
        raise Stop("predecessor_internal_image_missing")
    docs = json.loads(predecessor.stdout)
    if (
        not isinstance(docs, list)
        or len(docs) != 1
        or docs[0].get("Id") != plan["predecessor_runtime_image_id"]
    ):
        raise Stop("predecessor_internal_image_drift")

    target = run(
        ["docker", "image", "inspect", plan["target_image"]],
        timeout=45,
        check=False,
    )
    if target.returncode == 0:
        raise Stop("target_internal_image_unexpectedly_present")
    return {
        "predecessor_present": True,
        "predecessor_image_id": plan["predecessor_runtime_image_id"],
        "target_absent": True,
    }


def verify_mount(plan):
    completed = run(
        [
            "findmnt",
            "--noheadings",
            "--output",
            "SOURCE,TARGET,FSTYPE,OPTIONS",
            "--target",
            plan["mount_target"],
        ],
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("u8_media_not_mounted")
    fields = completed.stdout.strip().split(None, 3)
    if len(fields) != 4:
        raise Stop("u8_media_mount_probe_invalid")
    source, target, fstype, options = fields
    option_set = set(options.split(","))
    if (
        not source.startswith("/dev/")
        or target != plan["mount_target"]
        or fstype != "ext4"
        or "rw" not in option_set
        or not {"nodev", "nosuid", "noexec"}.issubset(option_set)
    ):
        raise Stop("u8_media_mount_invalid")
    return {
        "source_kind": "block_device",
        "target": target,
        "fstype": fstype,
        "rw": True,
        "nodev": True,
        "nosuid": True,
        "noexec": True,
    }


def import_product():
    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_usb_state import (
        compute_recovery_content_manifest_sha256,
        validate_transaction_document,
    )
    return (
        compute_recovery_content_manifest_sha256,
        validate_transaction_document,
    )


def verify_r33_ledger(plan):
    root = Path(plan["r33_state_root"])
    claim = read_object(root / "authorization_claim.json")
    failure = read_object(root / "failure.json")
    if (
        claim.get("authorization_id") != plan["r33_gate_id"]
        or claim.get("execution_id") != plan["r33_execution_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or failure.get("status") != "STOP_POSTCLAIM"
        or failure.get("first_failed_operation")
        != "Stop:r33_terminal_usb_mirror_mismatch"
        or failure.get("authorization_claimed") is not True
        or failure.get("authorization_consumed") is not True
        or failure.get("replay_permitted") is not False
        or failure.get("transaction_mutation") is not True
        or failure.get("usb_mutation") is not True
        or failure.get("u8_transition") is not True
        or failure.get("transaction_phase")
        != "U8_RECOVERY_ADMISSION_COMPLETE"
        or failure.get("u9_plus") is not False
        or failure.get("destructive_cutover") is not False
        or failure.get("predecessor_image_delete") is not False
        or failure.get("target_image_load") is not False
        or failure.get("service_stop") is not False
        or failure.get("service_restart") is not False
        or failure.get("rollback_required") is not False
    ):
        raise Stop("r33_failure_ledger_invalid")
    return {
        "r33_claimed": True,
        "r33_consumed": True,
        "r33_replay_permitted": False,
        "r33_status": "STOP_POSTCLAIM",
        "r33_failure_operation": "r33_terminal_usb_mirror_mismatch",
    }


def verify_transaction(plan):
    compute_manifest, validate_transaction = import_product()
    transaction = read_object(TX)
    validate_transaction(transaction)
    if (
        sha_file(TX) != plan["transaction_sha256"]
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("phase") != "U8_RECOVERY_ADMISSION_COMPLETE"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("recovery_content_manifest_sha256")
        != plan["recovery_content_manifest_sha256"]
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not True
        or transaction.get("ha_data_backup_verified") is not True
        or transaction.get("production_prestate_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
    ):
        raise Stop("r34_u8_transaction_invalid")
    if (
        compute_manifest(transaction)
        != plan["recovery_content_manifest_sha256"]
    ):
        raise Stop("r34_recovery_manifest_recompute_mismatch")
    return transaction


def verify_mirror(plan, transaction):
    mirror = Path(plan["mount_target"]) / "n3w-update" / "transaction"
    files = {
        "manifest": mirror / "manifest.json",
        "phase": mirror / "phase.json",
        "content_authority": mirror / "content-authority.json",
        "checksums": mirror / "checksums.json",
    }
    for name, path in files.items():
        if sha_file(path) != plan["mirror_sha256"][name]:
            raise Stop("r34_usb_mirror_file_drift:" + name)

    manifest = read_object(files["manifest"])
    phase = read_object(files["phase"])
    authority = read_object(files["content_authority"])
    checksums = read_object(files["checksums"])

    session_fingerprint = manifest.get(
        "usb_device_identity_public_fingerprint"
    )
    if (
        not isinstance(session_fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", session_fingerprint) is None
    ):
        raise Stop("r34_usb_session_fingerprint_invalid")

    durable_checks = {
        "manifest.transaction_id": (
            manifest.get("transaction_id_sha256")
            == transaction.get("transaction_id_sha256")
        ),
        "manifest.filesystem_uuid": (
            manifest.get("usb_filesystem_uuid")
            == transaction.get("usb_filesystem_uuid")
        ),
        "phase.transaction_id": (
            phase.get("transaction_id_sha256")
            == transaction.get("transaction_id_sha256")
        ),
        "phase.phase": (
            phase.get("phase") == "U8_RECOVERY_ADMISSION_COMPLETE"
        ),
        "phase.target_verified": (
            phase.get("target_artifact_verified") is True
        ),
        "phase.capacity_verified": (
            phase.get("usb_capacity_verified") is True
        ),
        "authority.transaction_id": (
            authority.get("transaction_id_sha256")
            == transaction.get("transaction_id_sha256")
        ),
        "authority.target_identity": (
            authority.get("target_artifact_identity")
            == transaction.get("target_artifact_identity")
        ),
        "authority.predecessor_identity": (
            authority.get("predecessor_recovery_identity")
            == transaction.get("predecessor_recovery_identity")
        ),
        "authority.backup_identity": (
            authority.get("ha_data_backup_identity")
            == transaction.get("ha_data_backup_identity")
        ),
        "authority.recovery_manifest": (
            authority.get("recovery_content_manifest_sha256")
            == transaction.get("recovery_content_manifest_sha256")
        ),
        "checksums.target_sha256": (
            checksums.get("target_archive_sha256")
            == transaction.get("target_archive_sha256")
        ),
        "checksums.target_size": (
            checksums.get("target_archive_size_bytes")
            == transaction.get("target_archive_size")
        ),
    }
    mismatches = [
        key for key, value in durable_checks.items() if value is not True
    ]
    if mismatches:
        raise Stop("r34_durable_usb_mirror_mismatch:" + ",".join(mismatches))

    transaction_fingerprint = transaction.get(
        "usb_device_identity_public_fingerprint"
    )
    return {
        "durable_mirror_exact": True,
        "durable_checks": durable_checks,
        "session_public_fingerprint_valid": True,
        "session_public_fingerprint_differs_from_transaction": (
            session_fingerprint != transaction_fingerprint
        ),
        "session_public_fingerprint_cross_session_authority": False,
        "filesystem_uuid_cross_session_authority": True,
        "filesystem_uuid": transaction.get("usb_filesystem_uuid"),
        "mirror_sha256": {
            name: sha_file(path) for name, path in files.items()
        },
    }


def main():
    try:
        plan = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U8_POST_R33_READONLY_RECONCILIATION_R34_20261115_01"
        ):
            raise Stop("gate_id_invalid")

        ledger = verify_r33_ledger(plan)
        transaction = verify_transaction(plan)
        mount = verify_mount(plan)
        mirror = verify_mirror(plan, transaction)
        runtime = verify_runtime(plan)
        images = verify_images(plan)

        if mirror["session_public_fingerprint_differs_from_transaction"] is not True:
            raise Stop("r34_expected_session_fingerprint_delta_missing")

        result = {
            "schema": "gh.n3w-t1-u8-r34-readonly-reconciliation/1",
            "status": "U8_R34_POST_R33_READONLY_RECONCILIATION_PASS",
            "read_only": True,
            "r33_false_stop_confirmed": True,
            "false_stop_reason": (
                "session_public_fingerprint_was_compared_as_cross_session_authority"
            ),
            "u8_durable": True,
            "transaction_phase": transaction["phase"],
            "transaction_sha256": sha_file(TX),
            "recovery_content_manifest_sha256": (
                transaction["recovery_content_manifest_sha256"]
            ),
            "usb_durable_mirror_exact": True,
            "session_public_fingerprint_non_authoritative": True,
            "same_bound_usb_filesystem_uuid": True,
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_permitted": False,
            "product_u9_authorization_claimed": False,
            "product_u9_authorization_consumed": False,
            "destructive_cutover": False,
            "predecessor_image_delete": False,
            "target_image_load": False,
            "service_mutation": False,
            "u9_plus": False,
            "ledger": ledger,
            "mount": mount,
            "mirror": mirror,
            "runtime": runtime,
            "images": images,
        }
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-u8-r34-readonly-reconciliation/1",
            "status": "STOP",
            "read_only": True,
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "u9_plus": False,
            "destructive_cutover": False,
        }

    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status")
        == "U8_R34_POST_R33_READONLY_RECONCILIATION_PASS"
        else 2
    )


raise SystemExit(main())
'''


def git_text(*args: str) -> str:
    import subprocess

    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("git_command_failed:" + args[0])
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
        document.get("schema") != MANIFEST_SCHEMA
        or document.get("gate_id") != GATE_ID
        or document.get("read_only") is not True
        or document.get("live_execution_authorized") is not False
    ):
        raise Stop("manifest_contract_invalid")

    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema": LOCAL_RESULT_SCHEMA,
        "status": "STOP",
        "read_only": True,
        "t1_access": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "u9_plus": False,
        "destructive_cutover": False,
        "board_access": False,
        "merge": False,
    }
    base = load_base()
    transport = None
    return_code = 2

    try:
        manifest = read_manifest(args.expected_package_commit)
        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_live_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "mount_target": manifest["mount_target"],
                "r33_state_root": manifest["r33_state_root"],
            }
        )

        payload = base64.b64encode(
            json.dumps(
                plan,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii")

        transport_type = base.load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        completed = transport.run_remote(
            ["python3", "-B", "-c", REMOTE_SCRIPT, payload],
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        base.write_remote_evidence(
            evidence,
            "readonly_reconciliation_remote",
            completed,
        )
        lines = [
            line.strip()
            for line in completed.stdout.splitlines()
            if line.strip()
        ]
        try:
            remote = json.loads(lines[-1]) if lines else {}
        except Exception:
            remote = {}
        if not isinstance(remote, dict) or not remote:
            raise Stop("remote_result_invalid")
        base.write_private_json(
            evidence / "readonly_reconciliation.json",
            remote,
        )
        result.update(remote)
        result["t1_access"] = True
        result["remote_returncode"] = completed.returncode
        if (
            completed.returncode == 0
            and remote.get("status")
            == "U8_R34_POST_R33_READONLY_RECONCILIATION_PASS"
        ):
            return_code = 0
        else:
            return_code = 2
    except Exception as error:
        result.update(
            status="STOP",
            reason=type(error).__name__ + ":" + str(error)[:300],
        )
        return_code = 2
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
                    + str(cleanup_error)[:180]
                )
                if return_code == 0:
                    result["status"] = "STOP_POSTSUCCESS_LOCAL"
                    return_code = 2
        try:
            if "evidence" in locals():
                base.write_private_json(
                    evidence / "local_result.json",
                    result,
                )
        except Exception:
            if return_code == 0:
                result["status"] = "STOP_POSTSUCCESS_LOCAL"
                return_code = 2

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
