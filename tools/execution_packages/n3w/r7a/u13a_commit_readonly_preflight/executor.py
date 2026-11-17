from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
U12_READONLY_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u12_target_acceptance_readonly_preflight"
    / "executor.py"
)

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U13A_COMMIT_READONLY_PREFLIGHT_20261117_01"
)
MANIFEST_SCHEMA = "gh.n3w-t1-u13a-commit-readonly-preflight-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u13a-commit-readonly-preflight-local-result/1"


class Stop(RuntimeError):
    pass


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stop("module_load_failed:" + path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_u12_readonly():
    return load_module(U12_READONLY_EXECUTOR, "n3w_u13a_u12_readonly")


def u12_remote_library() -> str:
    remote = load_u12_readonly().REMOTE_SCRIPT
    marker = "raise SystemExit(main())"
    if marker not in remote:
        raise Stop("u12_readonly_remote_marker_missing")
    return remote.rsplit(marker, 1)[0]


REMOTE_SCRIPT = u12_remote_library() + r"""
U12_LIVE_SCHEMA = "gh.n3w-t1-u12-live-acceptance/1"
U12_PERFORMANCE_SCHEMA = "gh.n3w-t1-u12-live-performance/1"


def import_u13_product():
    product = import_product()
    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_usb import (
        classify_power_loss_reentry,
        destructive_cutover_allowed,
    )
    product.update(
        {
            "classify_power_loss_reentry": classify_power_loss_reentry,
            "destructive_cutover_allowed": destructive_cutover_allowed,
        }
    )
    return product


def verify_transaction_u12(plan, product):
    transaction = read_object(TX)
    product["validate_transaction_document"](transaction)
    if (
        sha_file(TX) != plan["transaction_sha256"]
        or transaction.get("phase") != "U12_TARGET_ACCEPTANCE"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("current_image_ref") != plan["predecessor_image"]
        or transaction.get("target_image_ref") != plan["target_image"]
        or transaction.get("target_archive_sha256")
        != plan["target_archive_sha256"]
        or transaction.get("target_archive_size")
        != plan["target_archive_size_bytes"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not True
        or transaction.get("ha_data_backup_verified") is not True
        or transaction.get("production_prestate_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
        or transaction.get("recovery_content_manifest_sha256")
        != plan["recovery_content_manifest_sha256"]
        or transaction.get("usb_filesystem_uuid") != plan["filesystem_uuid"]
        or transaction.get("authorization_claimed") is not True
        or transaction.get("authorization_consumed") is not True
        or transaction.get("authorization_id_sha256")
        != plan["authorization_id_sha256"]
        or product["destructive_cutover_allowed"](transaction) is not True
    ):
        raise Stop("u13a_preflight_u12_transaction_invalid")
    return transaction


def verify_usb_mirror_u12(plan, transaction):
    root = Path(plan["mount_target"]) / "n3w-update" / "transaction"
    manifest_path = root / "manifest.json"
    phase_path = root / "phase.json"
    authority_path = root / "content-authority.json"
    checksums_path = root / "checksums.json"
    manifest = read_object(manifest_path)
    phase = read_object(phase_path)
    authority = read_object(authority_path)
    checksums = read_object(checksums_path)
    if (
        manifest.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or manifest.get("usb_filesystem_uuid")
        != transaction["usb_filesystem_uuid"]
        or phase.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or phase.get("phase") != "U12_TARGET_ACCEPTANCE"
        or phase.get("target_artifact_verified") is not True
        or phase.get("usb_capacity_verified") is not True
        or authority.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or authority.get("target_artifact_identity")
        != transaction["target_artifact_identity"]
        or authority.get("predecessor_recovery_identity")
        != transaction["predecessor_recovery_identity"]
        or authority.get("ha_data_backup_identity")
        != transaction["ha_data_backup_identity"]
        or authority.get("recovery_content_manifest_sha256")
        != transaction["recovery_content_manifest_sha256"]
        or checksums.get("target_archive_sha256")
        != transaction["target_archive_sha256"]
        or checksums.get("target_archive_size_bytes")
        != transaction["target_archive_size"]
    ):
        raise Stop("u13a_preflight_usb_mirror_invalid")
    observed = {
        "manifest": sha_file(manifest_path),
        "phase": sha_file(phase_path),
        "content_authority": sha_file(authority_path),
        "checksums": sha_file(checksums_path),
    }
    if observed != plan["mirror_sha256"]:
        raise Stop("u13a_preflight_usb_mirror_hash_drift")
    return {"exact": True, "sha256": observed}


def verify_u12_live_ledger(plan):
    root = Path(plan["u12_live_state_root"])
    claim_path = root / "authorization_claim.json"
    success_path = root / "success.json"
    failure_path = root / "failure.json"
    performance_path = root / "performance.json"
    if failure_path.exists() or failure_path.is_symlink():
        raise Stop("u13a_preflight_u12_failure_ledger_present")
    claim = read_object(claim_path)
    success = read_object(success_path)
    performance = read_object(performance_path)
    if (
        claim.get("gate_id") != plan["u12_live_gate_id"]
        or claim.get("authorization_id")
        != plan["u12_live_authorization_id"]
        or claim.get("execution_id") != plan["u12_live_execution_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or success.get("schema") != U12_LIVE_SCHEMA
        or success.get("status") != "U12_LIVE_ACCEPTANCE_PASS"
        or success.get("authorization_claimed") is not True
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or success.get("transaction_phase") != "U12_TARGET_ACCEPTANCE"
        or success.get("transaction_sha256") != plan["transaction_sha256"]
        or success.get("u12_acceptance") is not True
        or success.get("u12_transition") is not True
        or success.get("u13_plus") is not False
        or success.get("service_mutation") is not False
        or success.get("image_mutation") is not False
        or performance.get("schema") != U12_PERFORMANCE_SCHEMA
        or performance.get("u12_acceptance_duration_ms")
        != plan["u12_acceptance_duration_ms"]
        or performance.get("normal_ota_baseline_available") is not False
        or performance.get("user_visible_downtime_measured") is not False
    ):
        raise Stop("u13a_preflight_u12_live_ledger_invalid")
    return {
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
        "failure_ledger_present": False,
        "success_sha256": sha_file(success_path),
        "claim_sha256": sha_file(claim_path),
        "performance_sha256": sha_file(performance_path),
    }


def verify_recovery_assets(plan, transaction, product):
    recovery_plan = dict(plan)
    recovery_plan["predecessor_identity"] = plan["predecessor_identity"]
    recovery_plan["backup_identity"] = plan["backup_identity"]
    recovery = verify_recovery_assets_and_capacity(
        recovery_plan,
        transaction,
        product,
    )
    if (
        recovery.get("target_archive", {}).get("sha256")
        != plan["target_archive_sha256"]
        or recovery.get("predecessor_archive", {}).get("sha256")
        != plan["predecessor_identity"]["archive_sha256"]
        or recovery.get("backup_verified") is not True
        or recovery.get("capacity_pass") is not True
    ):
        raise Stop("u13a_preflight_recovery_assets_invalid")
    return recovery


def run_u13a_readonly(plan):
    total_started = time.monotonic_ns()
    product = import_u13_product()

    step_started = time.monotonic_ns()
    source_hashes = verify_installed_sources(plan)
    source_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    transaction = verify_transaction_u12(plan, product)
    transaction_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    u12_live = verify_u12_live_ledger(plan)
    u12_ledger_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    mount = require_bound_mount(plan)
    mirror = verify_usb_mirror_u12(plan, transaction)
    mirror_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    recovery = verify_recovery_assets(plan, transaction, product)
    recovery_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    runtime = verify_runtime_u11(plan)
    readiness = observe_acceptance_readiness(plan)
    runtime_readiness_ms = elapsed_ms(step_started)

    classification = product["classify_power_loss_reentry"](
        transaction,
        recovery_media_present=True,
        exact_recovery_content_verified=True,
    )
    if classification != "FORWARD_COMMIT_ELIGIBLE":
        raise Stop("u13a_preflight_forward_commit_not_eligible")

    return {
        "schema": "gh.n3w-t1-u13a-commit-readonly-preflight/1",
        "status": "U13A_COMMIT_READONLY_PREFLIGHT_PASS",
        "read_only": True,
        "transaction_phase": transaction["phase"],
        "transaction_sha256": sha_file(TX),
        "u12_live": u12_live,
        "mount": mount,
        "mirror": mirror,
        "recovery": recovery,
        "runtime": runtime,
        "readiness": readiness,
        "power_loss_reentry_classification": classification,
        "forward_commit_eligible": True,
        "rollback_required": False,
        "source_hash_count": len(source_hashes),
        "timings_ms": {
            "installed_source_verification_ms": source_ms,
            "transaction_verification_ms": transaction_ms,
            "u12_live_ledger_verification_ms": u12_ledger_ms,
            "usb_mirror_verification_ms": mirror_ms,
            "recovery_assets_verification_ms": recovery_ms,
            "runtime_readiness_verification_ms": runtime_readiness_ms,
            "preflight_total_ms": elapsed_ms(total_started),
        },
        "normal_ota_baseline_available": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "u13a_live_execution_authorized": False,
        "u13a_transition": False,
        "u13b_transition": False,
        "board_access": False,
        "merge": False,
    }


def main():
    try:
        mode = sys.argv[1]
        plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U13A_COMMIT_READONLY_PREFLIGHT_20261117_01"
        ):
            raise Stop("gate_id_invalid")
        if mode != "preflight":
            raise Stop("mode_invalid")
        result = run_u13a_readonly(plan)
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-u13a-commit-readonly-preflight/1",
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "read_only": True,
            "forward_commit_eligible": False,
            "rollback_required": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "service_mutation": False,
            "image_mutation": False,
            "u13a_live_execution_authorized": False,
            "u13a_transition": False,
            "u13b_transition": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status")
        == "U13A_COMMIT_READONLY_PREFLIGHT_PASS"
        else 2
    )


raise SystemExit(main())
"""


def git_text(*args: str) -> str:
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
        or document.get("read_only_preflight") is not True
        or document.get("real_t1_readonly_execution_authorized") is not True
        or document.get("u13a_live_execution_authorized") is not False
        or document.get("u13b_live_execution_authorized") is not False
    ):
        raise Stop("manifest_gate_invalid")
    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


def remote_preflight(transport, plan, *, timeout=1800):
    payload = __import__("base64").b64encode(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    completed = transport.run_remote(
        ["python3", "-B", "-c", REMOTE_SCRIPT, "preflight", payload],
        timeout=timeout,
        check=False,
    )
    lines = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    try:
        result = json.loads(lines[-1]) if lines else {}
    except Exception:
        result = {}
    if not isinstance(result, dict) or not result:
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
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema": LOCAL_RESULT_SCHEMA,
        "status": "STOP",
        "t1_access": False,
        "read_only": True,
        "remote_preflight_invoked": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "u13a_live_execution_authorized": False,
        "u13a_transition": False,
        "u13b_transition": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    u12 = load_u12_readonly()
    base = u12.load_r37().load_base()

    try:
        manifest = read_manifest(args.expected_package_commit)
        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_u12_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "mount_target": manifest["mount_target"],
                "installed_source_sha256": manifest[
                    "installed_source_sha256"
                ],
                "u12_live_state_root": manifest["u12_live"][
                    "state_root"
                ],
                "u12_live_gate_id": manifest["u12_live"]["gate_id"],
                "u12_live_authorization_id": manifest["u12_live"][
                    "authorization_id"
                ],
                "u12_live_execution_id": manifest["u12_live"][
                    "execution_id"
                ],
                "u12_acceptance_duration_ms": manifest["u12_live"][
                    "u12_acceptance_duration_ms"
                ],
                "predecessor_identity": manifest["recovery_authority"][
                    "predecessor_identity"
                ],
                "backup_identity": manifest["recovery_authority"][
                    "backup_identity"
                ],
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
        result["remote_preflight_invoked"] = True
        completed, remote = remote_preflight(transport, plan)
        result["remote_returncode"] = completed.returncode
        result.update(remote)
        base.write_remote_evidence(
            evidence,
            "u13a_preflight_remote",
            completed,
        )
        base.write_private_json(
            evidence / "u13a_preflight.json",
            remote,
        )
        return_code = (
            0
            if completed.returncode == 0
            and remote.get("status")
            == "U13A_COMMIT_READONLY_PREFLIGHT_PASS"
            else 2
        )
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
                    result["completed_remote_status"] = result.get("status")
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
                result["completed_remote_status"] = result.get("status")
                result["status"] = "STOP_POSTSUCCESS_LOCAL"
                return_code = 2

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
