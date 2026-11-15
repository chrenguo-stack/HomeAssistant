#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import re
import subprocess
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
R33_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u8_recovery_admission_r33"
    / "executor.py"
)

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U9_LIVE_AUTHORIZATION_R35_20261115_01"
)
CONFIRMATION = "EXECUTE U9 R35 LIVE AUTHORIZATION CLAIM: YES"
MANIFEST_SCHEMA = "gh.n3w-t1-u9-r35-live-authorization-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u9-r35-local-result/1"
EXECUTE_TIMEOUT_SECONDS = 1500


class Stop(RuntimeError):
    pass


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stop("module_import_invalid:" + path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_base():
    return load_module(BASE_EXECUTOR, "n3w_r35_base")


def load_r33():
    return load_module(R33_EXECUTOR, "n3w_r35_r33")


def r33_remote_library() -> str:
    remote = load_r33().REMOTE_SCRIPT
    marker = "raise SystemExit(main())"
    if marker not in remote:
        raise Stop("r33_remote_library_marker_missing")
    return remote.rsplit(marker, 1)[0]


REMOTE_SCRIPT = r33_remote_library() + r'''
R33_STATE = Path(
    "/var/lib/n3w-t1-core-updater/"
    "u8-r33-recovery-admission-20261115-01"
)


def import_product():
    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_backup import (
        ProtectedHaDataBackupProvider,
        backup_record_from_document,
    )
    from n3w_t1_core_updater_ha_capacity import (
        validate_recovery_admission_capacity,
    )
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_recovery import (
        image_recovery_record_from_document,
    )
    from n3w_t1_core_updater_ha_usb import (
        claim_live_authorization,
        destructive_cutover_allowed,
    )
    from n3w_t1_core_updater_ha_usb_media import assess_capacity
    from n3w_t1_core_updater_ha_usb_state import (
        HaUsbStateStore,
        validate_transaction_document,
    )

    return {
        "ProtectedHaDataBackupProvider": ProtectedHaDataBackupProvider,
        "backup_record_from_document": backup_record_from_document,
        "validate_recovery_admission_capacity": (
            validate_recovery_admission_capacity
        ),
        "SubprocessPrepareBackend": SubprocessPrepareBackend,
        "image_recovery_record_from_document": (
            image_recovery_record_from_document
        ),
        "claim_live_authorization": claim_live_authorization,
        "destructive_cutover_allowed": destructive_cutover_allowed,
        "assess_capacity": assess_capacity,
        "HaUsbStateStore": HaUsbStateStore,
        "validate_transaction_document": validate_transaction_document,
    }


def verify_transaction_u8(plan):
    transaction = read_object(TX)
    if (
        transaction.get("phase") != "U8_RECOVERY_ADMISSION_COMPLETE"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or sha_file(TX) != plan["transaction_sha256"]
        or transaction.get("target_image_ref") != plan["target_image"]
        or transaction.get("current_image_ref") != plan["predecessor_image"]
        or transaction.get("target_archive_sha256")
        != plan["target_archive_sha256"]
        or transaction.get("target_archive_size")
        != plan["target_archive_size_bytes"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not True
        or transaction.get("predecessor_recovery_identity")
        != plan["predecessor_identity"]
        or transaction.get("ha_data_backup_verified") is not True
        or transaction.get("ha_data_backup_identity")
        != plan["backup_identity"]
        or transaction.get("production_prestate_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
        or transaction.get("recovery_content_manifest_sha256")
        != plan["recovery_content_manifest_sha256"]
        or transaction.get("usb_filesystem_uuid")
        != plan["filesystem_uuid"]
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
    ):
        raise Stop("u9_r35_u8_transaction_invalid")
    product = import_product()
    product["validate_transaction_document"](transaction)
    return transaction


def verify_r33_ledger(plan):
    claim = read_object(R33_STATE / "authorization_claim.json")
    failure = read_object(R33_STATE / "failure.json")
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
        or failure.get("transaction_phase")
        != "U8_RECOVERY_ADMISSION_COMPLETE"
        or failure.get("u9_plus") is not False
        or failure.get("destructive_cutover") is not False
    ):
        raise Stop("u9_r35_r33_ledger_invalid")
    return {
        "r33_claimed": True,
        "r33_consumed": True,
        "r33_replay_permitted": False,
        "r33_status": "STOP_POSTCLAIM",
    }


def verify_mirror_u8(plan, transaction):
    mirror = Path(plan["mount_target"]) / "n3w-update" / "transaction"
    files = {
        "manifest": mirror / "manifest.json",
        "phase": mirror / "phase.json",
        "content_authority": mirror / "content-authority.json",
        "checksums": mirror / "checksums.json",
    }
    for name, path in files.items():
        if sha_file(path) != plan["mirror_sha256"][name]:
            raise Stop("u9_r35_u8_mirror_file_drift:" + name)

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
        raise Stop("u9_r35_session_fingerprint_invalid")

    if (
        manifest.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or manifest.get("usb_filesystem_uuid")
        != transaction["usb_filesystem_uuid"]
        or phase.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or phase.get("phase") != "U8_RECOVERY_ADMISSION_COMPLETE"
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
        raise Stop("u9_r35_u8_durable_mirror_mismatch")

    return {
        "durable_mirror_exact": True,
        "filesystem_uuid": transaction["usb_filesystem_uuid"],
        "same_bound_usb_filesystem_uuid": True,
        "session_public_fingerprint_valid": True,
        "session_public_fingerprint_cross_session_authority": False,
        "mirror_sha256": {
            name: sha_file(path) for name, path in files.items()
        },
    }


def verify_prestate_u9(plan):
    source_hashes = verify_source_hashes(plan)
    transaction = verify_transaction_u8(plan)
    ledger = verify_r33_ledger(plan)
    runtime = verify_quiesced_runtime(plan)
    predecessor_image = verify_predecessor_internal_image(plan)
    target_image = verify_target_internal_image_absent(plan)
    media = verify_media_and_recovery_inputs(plan, transaction)
    mirror = verify_mirror_u8(plan, transaction)
    return {
        "transaction_sha256": sha_file(TX),
        "transaction_phase": transaction["phase"],
        "source_hash_count": len(source_hashes),
        "r33_ledger": ledger,
        "runtime": runtime,
        "predecessor_internal_image": predecessor_image,
        "target_internal_image": target_image,
        "media": media,
        "mirror": mirror,
        "production_prestate_exact": True,
        "product_u9_authorization_claimed": False,
        "product_u9_authorization_consumed": False,
    }


def verify_terminal_u9_state(plan):
    transaction = read_object(TX)
    product = import_product()
    product["validate_transaction_document"](transaction)
    expected_authorization_sha256 = hashlib.sha256(
        plan["authorization_id"].encode("utf-8")
    ).hexdigest()

    if (
        transaction.get("phase") != "U9_LIVE_AUTHORIZATION_CLAIMED"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("target_image_ref") != plan["target_image"]
        or transaction.get("current_image_ref") != plan["predecessor_image"]
        or transaction.get("target_archive_sha256")
        != plan["target_archive_sha256"]
        or transaction.get("target_archive_size")
        != plan["target_archive_size_bytes"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not True
        or transaction.get("predecessor_recovery_identity")
        != plan["predecessor_identity"]
        or transaction.get("ha_data_backup_verified") is not True
        or transaction.get("ha_data_backup_identity")
        != plan["backup_identity"]
        or transaction.get("production_prestate_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
        or transaction.get("recovery_content_manifest_sha256")
        != plan["recovery_content_manifest_sha256"]
        or transaction.get("usb_filesystem_uuid")
        != plan["filesystem_uuid"]
        or transaction.get("authorization_claimed") is not True
        or transaction.get("authorization_consumed") is not True
        or transaction.get("authorization_id_sha256")
        != expected_authorization_sha256
    ):
        raise Stop("u9_r35_terminal_transaction_invalid")
    if product["destructive_cutover_allowed"](transaction) is not True:
        raise Stop("u9_r35_destructive_successor_not_eligible")

    require_existing_rw_mount(plan)
    mirror = Path(plan["mount_target"]) / "n3w-update" / "transaction"
    manifest = read_object(mirror / "manifest.json")
    phase = read_object(mirror / "phase.json")
    authority = read_object(mirror / "content-authority.json")
    checksums = read_object(mirror / "checksums.json")
    session_fingerprint = manifest.get(
        "usb_device_identity_public_fingerprint"
    )
    if (
        not isinstance(session_fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", session_fingerprint) is None
        or manifest.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or manifest.get("usb_filesystem_uuid")
        != transaction["usb_filesystem_uuid"]
        or phase.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or phase.get("phase") != "U9_LIVE_AUTHORIZATION_CLAIMED"
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
        raise Stop("u9_r35_terminal_usb_mirror_invalid")

    runtime = verify_quiesced_runtime(plan)
    predecessor = verify_predecessor_internal_image(plan)
    target = verify_target_internal_image_absent(plan)
    return {
        "transaction_exact": True,
        "transaction_sha256": sha_file(TX),
        "transaction_phase": transaction["phase"],
        "recovery_content_manifest_sha256": (
            transaction["recovery_content_manifest_sha256"]
        ),
        "authorization_id_sha256": transaction["authorization_id_sha256"],
        "product_u9_authorization_claimed": True,
        "product_u9_authorization_consumed": True,
        "usb_mirror_u9_exact": True,
        "same_bound_usb_filesystem_uuid": True,
        "session_public_fingerprint_cross_session_authority": False,
        "runtime": runtime,
        "predecessor_internal_image": predecessor,
        "target_internal_image": target,
        "u10_destructive_successor_eligible": True,
        "destructive_cutover_performed": False,
        "predecessor_image_delete": False,
        "target_image_load": False,
        "service_mutation": False,
    }


def read_terminal_status(plan):
    state_root = Path(plan["state_root"])
    if not state_root.exists():
        return {
            "schema": "gh.n3w-t1-u9-r35-status/1",
            "status": "NOT_STARTED",
            "terminal": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
        }
    if state_root.is_symlink() or not state_root.is_dir():
        raise Stop("r35_state_root_invalid")

    success_path = state_root / "success.json"
    failure_path = state_root / "failure.json"
    claim_path = state_root / "authorization_claim.json"
    claim = read_object(claim_path) if claim_path.exists() else None

    if success_path.exists():
        value = read_object(success_path)
        value["terminal_reconciliation"] = verify_terminal_u9_state(plan)
        value["terminal"] = True
        value["reconciled_from_ledger"] = True
        return value
    if failure_path.exists():
        value = read_object(failure_path)
        value["terminal"] = True
        value["reconciled_from_ledger"] = True
        return value
    if claim is not None:
        try:
            terminal = verify_terminal_u9_state(plan)
            return {
                "schema": "gh.n3w-t1-u9-r35-status/1",
                "status": "U9_R35_LIVE_AUTHORIZATION_CLAIM_PASS_RECONCILED",
                "terminal": True,
                "authorization_claimed": True,
                "authorization_consumed": True,
                "replay_permitted": False,
                "reconciled_from_durable_u9": True,
                "terminal_reconciliation": terminal,
                "u10_plus": False,
                "destructive_cutover": False,
            }
        except Exception:
            pass

    transaction = read_object(TX)
    return {
        "schema": "gh.n3w-t1-u9-r35-status/1",
        "status": "RUNNING_OR_INTERRUPTED",
        "terminal": False,
        "authorization_claimed": bool(
            claim and claim.get("claimed") is True
        ),
        "authorization_consumed": bool(
            claim and claim.get("consumed") is True
        ),
        "replay_permitted": False,
        "transaction_phase": transaction.get("phase"),
        "u10_plus": False,
        "destructive_cutover": False,
    }


def execute(plan, authorization_id, confirmation):
    result = {
        "schema": "gh.n3w-t1-u9-r35-live-authorization/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u9_transition": False,
        "u10_plus": False,
        "destructive_cutover": False,
        "predecessor_image_delete": False,
        "target_image_load": False,
        "service_mutation": False,
        "board_access": False,
        "merge": False,
    }
    if (
        authorization_id != plan["authorization_id"]
        or confirmation != plan["confirmation"]
        or plan.get("live_execution_authorized") is not True
        or plan.get("authorization_state")
        != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("r35_state_root_residue")

    pre = verify_prestate_u9(plan)

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    claim = {
        "schema": "gh.n3w-t1-u9-r35-authorization-claim/1",
        "gate_id": plan["gate_id"],
        "authorization_id": authorization_id,
        "execution_id": plan["execution_id"],
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
    }
    durable_json_once(state_root / "authorization_claim.json", claim)
    result.update(
        authorization_claimed=True,
        authorization_consumed=True,
        replay_permitted=False,
    )

    def progress(phase, value=0):
        durable_json_replace(
            state_root / "progress.json",
            {
                "schema": "gh.n3w-t1-u9-r35-progress/1",
                "phase": phase,
                "value": value,
                "updated_at_unix": int(time.time()),
            },
        )

    try:
        progress("executor_claimed")
        product = import_product()
        store = product["HaUsbStateStore"]()
        backend = product["SubprocessPrepareBackend"]()
        with store.lock():
            current = store.read()
            if current is None:
                raise Stop("u9_transaction_missing")
            current = product["validate_transaction_document"](current)
            if sha_file(TX) != plan["transaction_sha256"]:
                raise Stop("u9_transaction_drift_after_claim")

            (
                _product,
                _backend,
                media,
                _target,
                _predecessor,
                _backup,
                capacity_report,
                recovery_capacity,
            ) = build_admission_inputs(
                plan,
                current,
                write_required=True,
            )
            if (
                capacity_report.capacity_pass is not True
                or media.filesystem_uuid != plan["filesystem_uuid"]
                or recovery_capacity.recovery_capacity_pass is not True
            ):
                raise Stop("u9_final_revalidation_failed")

            progress("product_u9_claim")
            claimed = product["claim_live_authorization"](
                current,
                authorization_id,
            )
            if product["destructive_cutover_allowed"](claimed) is not True:
                raise Stop("u9_claimed_state_not_successor_eligible")

            progress("u9_usb_sync")
            backend.sync_transaction_metadata(claimed, media)
            result["usb_mutation"] = True

            progress("u9_host_sync")
            store.write(claimed)
            result["transaction_mutation"] = True
            result["u9_transition"] = True

        terminal = verify_terminal_u9_state(plan)
        result.update(
            status="U9_R35_LIVE_AUTHORIZATION_CLAIM_PASS",
            transaction_phase=terminal["transaction_phase"],
            transaction_sha256=terminal["transaction_sha256"],
            recovery_content_manifest_sha256=(
                terminal["recovery_content_manifest_sha256"]
            ),
            product_u9_authorization_claimed=True,
            product_u9_authorization_consumed=True,
            pre=pre,
            post=terminal,
            u10_plus=False,
            destructive_cutover=False,
            predecessor_image_delete=False,
            target_image_load=False,
            service_mutation=False,
        )
        progress("executor_success")
        durable_json_once(state_root / "success.json", result)
        return result
    except Exception as error:
        result["first_failed_operation"] = (
            type(error).__name__ + ":" + str(error)[:240]
        )
        try:
            current = read_object(TX)
            result["transaction_mutation"] = (
                sha_file(TX) != plan["transaction_sha256"]
            )
            result["transaction_phase"] = current.get("phase")
            result["u9_transition"] = (
                current.get("phase") == "U9_LIVE_AUTHORIZATION_CLAIMED"
            )
        except Exception:
            pass
        try:
            _manifest, phase, _authority = mirror_documents(plan)
            result["usb_mutation"] = (
                phase.get("phase") == "U9_LIVE_AUTHORIZATION_CLAIMED"
            )
        except Exception:
            pass
        try:
            result["postclaim_terminal_probe"] = verify_terminal_u9_state(plan)
            result["status"] = "STOP_POSTSUCCESS_LOCAL"
        except Exception as reconcile_error:
            result["status"] = "STOP_POSTCLAIM"
            result["reconciliation_error"] = (
                type(reconcile_error).__name__
                + ":"
                + str(reconcile_error)[:180]
            )
        result["u10_plus"] = False
        result["destructive_cutover"] = False
        result["predecessor_image_delete"] = False
        result["target_image_load"] = False
        result["service_mutation"] = False
        try:
            progress("executor_failure")
        except Exception:
            pass
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
            "U9_LIVE_AUTHORIZATION_R35_20261115_01"
        ):
            raise Stop("gate_id_invalid")
        if mode == "execute":
            result = execute(plan, sys.argv[3], sys.argv[4])
        elif mode == "status":
            result = read_terminal_status(plan)
        else:
            raise Stop("mode_invalid")
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-u9-r35-live-authorization/1",
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "u9_transition": False,
            "u10_plus": False,
            "destructive_cutover": False,
            "predecessor_image_delete": False,
            "target_image_load": False,
            "service_mutation": False,
        }

    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status")
        in {
            "U9_R35_LIVE_AUTHORIZATION_CLAIM_PASS",
            "U9_R35_LIVE_AUTHORIZATION_CLAIM_PASS_RECONCILED",
        }
        else 2
    )


raise SystemExit(main())
'''


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
        or document.get("authorization_id") != GATE_ID
        or document.get("confirmation") != CONFIRMATION
        or document.get("live_execution_authorized") is not True
        or document.get("authorization_state")
        != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("manifest_gate_invalid")

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


def reconcile_after_invoke(transport, plan, evidence, base):
    try:
        status_transport, status = remote_mode(
            transport,
            "status",
            plan,
            timeout=180,
        )
        base.write_remote_evidence(
            evidence,
            "status_reconcile_remote",
            status_transport,
        )
        base.write_private_json(
            evidence / "status_reconcile.json",
            status,
        )
        return status_transport, status
    except Exception as error:
        return None, {
            "status": "STOP_UNKNOWN",
            "reason": (
                "status_reconciliation_failed:"
                + type(error).__name__
                + ":"
                + str(error)[:180]
            ),
            "terminal": False,
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_permitted": False,
            "u10_plus": False,
            "destructive_cutover": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if args.execute is not True:
        raise SystemExit("--execute is required")

    result: dict[str, Any] = {
        "schema": LOCAL_RESULT_SCHEMA,
        "status": "STOP",
        "t1_access": False,
        "remote_execute_invoked": False,
        "remote_execute_result_observed": False,
        "status_reconciliation_attempted": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u9_transition": False,
        "u10_plus": False,
        "destructive_cutover": False,
        "predecessor_image_delete": False,
        "target_image_load": False,
        "service_mutation": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    base = load_base()

    try:
        manifest = read_manifest(args.expected_package_commit)
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
                "mount_target": manifest["mount_target"],
                "installed_source_sha256": (
                    manifest["installed_source_sha256"]
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
                timeout=EXECUTE_TIMEOUT_SECONDS,
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
            base.write_private_json(evidence / "execute.json", remote)
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
                    reason=(
                        "postinvoke_unknown:"
                        + type(invoke_error).__name__
                        + ":"
                        + str(invoke_error)[:180]
                    ),
                    authorization_claimed=True,
                    authorization_consumed=True,
                    replay_permitted=False,
                    u10_plus=False,
                    destructive_cutover=False,
                )

        if result.get("status") in {
            "U9_R35_LIVE_AUTHORIZATION_CLAIM_PASS",
            "U9_R35_LIVE_AUTHORIZATION_CLAIM_PASS_RECONCILED",
        }:
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
