from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
READONLY_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u13a_commit_readonly_preflight"
    / "executor.py"
)
TRANSITION_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_ha_usb.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U13A_LIVE_COMMIT_20261117_01"
)
AUTHORIZATION_ID = (
    "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U13A_LIVE_20261117_01"
)
CONFIRMATION = "EXECUTE U13A LIVE COMMIT: YES"
MANIFEST_SCHEMA = "gh.n3w-t1-u13a-live-commit-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u13a-live-commit-local-result/1"
REMOTE_SCHEMA = "gh.n3w-t1-u13a-live-commit/1"
EXECUTE_TIMEOUT_SECONDS = 300


class Stop(RuntimeError):
    pass


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stop("module_load_failed:" + path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_readonly():
    return load_module(READONLY_EXECUTOR, "n3w_u13a_live_readonly")


def readonly_remote_library() -> str:
    remote = load_readonly().REMOTE_SCRIPT
    marker = "raise SystemExit(main())"
    if marker not in remote:
        raise Stop("u13a_readonly_remote_marker_missing")
    return remote.rsplit(marker, 1)[0]


REMOTE_SCRIPT = readonly_remote_library() + r"""
import tempfile


def _fsync_directory(path):
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_json_once(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise Stop("durable_file_already_exists:" + path.name)
    payload = (
        json.dumps(value, sort_keys=True, separators=(",", ":"))
        + "\n"
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
    _fsync_directory(path.parent)


def durable_json_replace(path, value):
    path = Path(path)
    payload = (
        json.dumps(value, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    descriptor, raw = tempfile.mkstemp(
        prefix="." + path.name + ".",
        dir=path.parent,
    )
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def load_exact_commit_source(plan):
    try:
        raw = base64.b64decode(
            plan["transition_source_b64"],
            validate=True,
        )
    except Exception as error:
        raise Stop("u13a_live_transition_source_invalid") from error
    if hashlib.sha256(raw).hexdigest() != plan["transition_source_sha256"]:
        raise Stop("u13a_live_transition_source_hash_mismatch")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Stop("u13a_live_transition_source_encoding_invalid") from error
    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    namespace = {
        "__name__": "n3w_u13a_live_exact_ha_usb_transition",
        "__file__": "<n3w-u13a-live-exact-ha-usb-transition>",
    }
    try:
        exec(
            compile(
                source,
                "<n3w-u13a-live-exact-ha-usb-transition>",
                "exec",
            ),
            namespace,
        )
    except Exception as error:
        raise Stop("u13a_live_transition_source_load_failed") from error
    transition = namespace.get("record_commit")
    allowed = namespace.get("destructive_cutover_allowed")
    if not callable(transition) or not callable(allowed):
        raise Stop("u13a_live_transition_source_contract_missing")
    return transition, allowed


def import_u13a_runtime():
    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_usb_state import (
        HaUsbStateStore,
        validate_transaction_document,
    )
    return {
        "SubprocessPrepareBackend": SubprocessPrepareBackend,
        "HaUsbStateStore": HaUsbStateStore,
        "validate_transaction_document": validate_transaction_document,
    }


def verify_transaction_u13a(plan):
    runtime = import_u13a_runtime()
    transaction = read_object(TX)
    runtime["validate_transaction_document"](transaction)
    if (
        transaction.get("phase") != "U13A_COMMITTED"
        or transaction.get("status") != "COMMITTED"
        or transaction.get("recovery_required") is not False
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
    ):
        raise Stop("u13a_live_terminal_transaction_invalid")
    return transaction


def verify_usb_mirror_u13a(plan, transaction):
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
        or phase.get("phase") != "U13A_COMMITTED"
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
        raise Stop("u13a_live_terminal_usb_mirror_invalid")
    observed = {
        "manifest": sha_file(manifest_path),
        "phase": sha_file(phase_path),
        "content_authority": sha_file(authority_path),
        "checksums": sha_file(checksums_path),
    }
    prior = plan["mirror_sha256"]
    if (
        observed["manifest"] != prior["manifest"]
        or observed["content_authority"] != prior["content_authority"]
        or observed["checksums"] != prior["checksums"]
    ):
        raise Stop("u13a_live_terminal_usb_static_hash_drift")
    return {"exact": True, "sha256": observed}


def verify_terminal_u13a(plan):
    transaction = verify_transaction_u13a(plan)
    require_bound_mount(plan)
    mirror = verify_usb_mirror_u13a(plan, transaction)
    u12_live = verify_u12_live_ledger(plan)
    runtime = verify_runtime_u11(plan)
    readiness = observe_acceptance_readiness(plan)
    return {
        "transaction_phase": transaction["phase"],
        "transaction_status": transaction["status"],
        "recovery_required": transaction["recovery_required"],
        "transaction_sha256": sha_file(TX),
        "usb_mirror": mirror,
        "u12_live": u12_live,
        "runtime": runtime,
        "readiness": readiness,
        "u13a_committed": True,
        "u13a_transition": True,
        "u13b_transition": False,
    }


def current_usb_phase(plan):
    try:
        return read_object(
            Path(plan["mount_target"])
            / "n3w-update"
            / "transaction"
            / "phase.json"
        ).get("phase")
    except Exception:
        return None


def status(plan):
    root = Path(plan["u13a_state_root"])
    success_path = root / "success.json"
    failure_path = root / "failure.json"

    if success_path.exists():
        terminal = verify_terminal_u13a(plan)
        value = read_object(success_path)
        value.update(
            status="U13A_LIVE_COMMIT_PASS_RECONCILED",
            terminal=True,
            reconciled_from_durable_u13a=True,
            post=terminal,
        )
        return value

    try:
        transaction = read_object(TX)
        phase = transaction.get("phase")
    except Exception:
        phase = None
    usb_phase = current_usb_phase(plan)

    if phase == "U13A_COMMITTED" and usb_phase == "U13A_COMMITTED":
        terminal = verify_terminal_u13a(plan)
        return {
            "schema": "gh.n3w-t1-u13a-live-commit/1",
            "status": "U13A_LIVE_COMMIT_PASS_RECONCILED",
            "terminal": True,
            "reconciled_from_durable_u13a": True,
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_permitted": False,
            "post": terminal,
            "u13a_committed": True,
            "u13a_transition": True,
            "u13b_transition": False,
            "service_mutation": False,
            "image_mutation": False,
            "board_access": False,
            "merge": False,
        }

    claim_path = root / "authorization_claim.json"
    claim = read_object(claim_path) if claim_path.exists() else None

    if phase == "U12_TARGET_ACCEPTANCE" and usb_phase == "U13A_COMMITTED":
        return {
            "schema": "gh.n3w-t1-u13a-live-commit/1",
            "status": "STOP_PARTIAL_U13A_USB_ONLY",
            "terminal": True,
            "authorization_claimed": bool(claim),
            "authorization_consumed": bool(claim),
            "replay_permitted": False,
            "transaction_phase": phase,
            "usb_phase": usb_phase,
            "u13a_committed": False,
            "u13a_transition": False,
            "u13b_transition": False,
            "board_access": False,
            "merge": False,
        }

    if phase == "U13A_COMMITTED" and usb_phase != "U13A_COMMITTED":
        return {
            "schema": "gh.n3w-t1-u13a-live-commit/1",
            "status": "STOP_PARTIAL_U13A_HOST_ONLY",
            "terminal": True,
            "authorization_claimed": bool(claim),
            "authorization_consumed": bool(claim),
            "replay_permitted": False,
            "transaction_phase": phase,
            "usb_phase": usb_phase,
            "u13a_committed": False,
            "u13a_transition": True,
            "u13b_transition": False,
            "board_access": False,
            "merge": False,
        }

    if failure_path.exists():
        value = read_object(failure_path)
        value.update(
            terminal=True,
            transaction_phase=phase,
            usb_phase=usb_phase,
            replay_permitted=False,
        )
        return value

    return {
        "schema": "gh.n3w-t1-u13a-live-commit/1",
        "status": (
            "RUNNING_OR_INTERRUPTED"
            if claim
            else "U13A_LIVE_COMMIT_NOT_STARTED"
        ),
        "terminal": False,
        "authorization_claimed": bool(
            claim and claim.get("claimed") is True
        ),
        "authorization_consumed": bool(
            claim and claim.get("consumed") is True
        ),
        "replay_permitted": False,
        "transaction_phase": phase,
        "usb_phase": usb_phase,
        "u13a_committed": False,
        "u13a_transition": False,
        "u13b_transition": False,
        "board_access": False,
        "merge": False,
    }


def execute(plan, authorization_id, confirmation):
    result = {
        "schema": "gh.n3w-t1-u13a-live-commit/1",
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "u13a_committed": False,
        "u13a_transition": False,
        "u13b_transition": False,
        "board_access": False,
        "merge": False,
    }
    if (
        authorization_id != plan["authorization_id"]
        or confirmation != plan["confirmation"]
        or plan.get("u13a_live_execution_authorized") is not True
        or plan.get("authorization_state")
        != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("u13a_live_authorization_invalid")

    state_root = Path(plan["u13a_state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("u13a_live_state_root_residue")

    pre = run_u13a_readonly(plan)
    if (
        pre.get("status") != "U13A_COMMIT_READONLY_PREFLIGHT_PASS"
        or pre.get("forward_commit_eligible") is not True
        or pre.get("rollback_required") is not False
    ):
        raise Stop("u13a_live_embedded_preclaim_failed")

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    claim = {
        "schema": "gh.n3w-t1-u13a-live-authorization-claim/1",
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

    def progress(phase, **extra):
        value = {
            "schema": "gh.n3w-t1-u13a-live-progress/1",
            "phase": phase,
            "updated_at_unix": int(time.time()),
        }
        value.update(extra)
        durable_json_replace(state_root / "progress.json", value)

    try:
        progress("authorization_claimed")
        runtime = import_u13a_runtime()
        transition, allowed = load_exact_commit_source(plan)
        store = runtime["HaUsbStateStore"]()
        backend = runtime["SubprocessPrepareBackend"]()

        with store.lock():
            current = store.read()
            if current is None:
                raise Stop("u13a_live_transaction_missing")
            current = runtime["validate_transaction_document"](current)
            if (
                sha_file(TX) != plan["transaction_sha256"]
                or current.get("phase") != "U12_TARGET_ACCEPTANCE"
                or current.get("status") != "ACTIVE"
                or allowed(current) is not True
            ):
                raise Stop("u13a_live_u12_transaction_drift_after_claim")

            progress("postclaim_revalidation")
            product = import_u13_product()
            verify_transaction_u12(plan, product)
            verify_u12_live_ledger(plan)
            require_bound_mount(plan)
            verify_usb_mirror_u12(plan, current)
            verify_runtime_u11(plan)
            observe_acceptance_readiness(plan)
            classification = product["classify_power_loss_reentry"](
                current,
                recovery_media_present=True,
                exact_recovery_content_verified=True,
            )
            if classification != "FORWARD_COMMIT_ELIGIBLE":
                raise Stop("u13a_live_forward_commit_not_eligible_after_claim")

            media = backend.resolve_transaction_media(
                current,
                write_required=True,
            )
            if (
                media is None
                or media.filesystem_uuid != plan["filesystem_uuid"]
                or media.mount_path != plan["mount_target"]
            ):
                raise Stop("u13a_live_bound_media_drift_after_claim")

            progress("record_u13a")
            next_tx = transition(current)
            if (
                next_tx.get("phase") != "U13A_COMMITTED"
                or next_tx.get("status") != "COMMITTED"
                or next_tx.get("recovery_required") is not False
            ):
                raise Stop("u13a_live_transition_result_invalid")

            progress("u13a_usb_sync")
            backend.sync_transaction_metadata(next_tx, media)
            result["usb_mutation"] = True

            progress("u13a_host_sync")
            store.write(next_tx)
            result["transaction_mutation"] = True
            result["u13a_transition"] = True
            result["u13a_committed"] = True

        progress("u13a_durable")
        terminal = verify_terminal_u13a(plan)
        result.update(
            status="U13A_LIVE_COMMIT_PASS",
            pre=pre,
            post=terminal,
            transaction_phase=terminal["transaction_phase"],
            transaction_status=terminal["transaction_status"],
            transaction_sha256=terminal["transaction_sha256"],
            usb_phase_sha256=terminal["usb_mirror"]["sha256"]["phase"],
            transaction_mutation=True,
            usb_mutation=True,
            service_mutation=False,
            image_mutation=False,
            u13a_committed=True,
            u13a_transition=True,
            u13b_transition=False,
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
            result["transaction_phase"] = current.get("phase")
            result["transaction_mutation"] = (
                sha_file(TX) != plan["transaction_sha256"]
            )
            result["u13a_transition"] = (
                current.get("phase") == "U13A_COMMITTED"
            )
            result["u13a_committed"] = result["u13a_transition"]
        except Exception:
            pass
        try:
            terminal = verify_terminal_u13a(plan)
            result.update(
                status="STOP_POSTSUCCESS_LOCAL",
                postclaim_terminal_probe=terminal,
                transaction_phase=terminal["transaction_phase"],
                transaction_status=terminal["transaction_status"],
                transaction_sha256=terminal["transaction_sha256"],
                usb_phase_sha256=terminal["usb_mirror"]["sha256"]["phase"],
                transaction_mutation=True,
                usb_mutation=True,
                u13a_committed=True,
                u13a_transition=True,
                u13b_transition=False,
            )
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
            "U13A_LIVE_COMMIT_20261117_01"
        ):
            raise Stop("gate_id_invalid")
        if mode == "execute":
            result = execute(plan, sys.argv[3], sys.argv[4])
        elif mode == "status":
            result = status(plan)
        else:
            raise Stop("mode_invalid")
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-u13a-live-commit/1",
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "service_mutation": False,
            "image_mutation": False,
            "u13a_committed": False,
            "u13a_transition": False,
            "u13b_transition": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status") in {
            "U13A_LIVE_COMMIT_PASS",
            "U13A_LIVE_COMMIT_PASS_RECONCILED",
        }
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
        or document.get("authorization_id") != AUTHORIZATION_ID
        or document.get("confirmation") != CONFIRMATION
    ):
        raise Stop("manifest_gate_invalid")
    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


def build_plan(manifest: dict[str, Any], execution_id: str) -> dict[str, Any]:
    plan = dict(manifest["expected_u12_entry"])
    plan.update(
        {
            "gate_id": GATE_ID,
            "authorization_id": AUTHORIZATION_ID,
            "confirmation": CONFIRMATION,
            "execution_id": execution_id,
            "u13a_live_execution_authorized": manifest[
                "u13a_live_execution_authorized"
            ],
            "authorization_state": manifest["authorization_state"],
            "mount_target": manifest["mount_target"],
            "u12_live_state_root": manifest["u12_live"]["state_root"],
            "u12_live_gate_id": manifest["u12_live"]["gate_id"],
            "u12_live_authorization_id": manifest["u12_live"][
                "authorization_id"
            ],
            "u12_live_execution_id": manifest["u12_live"]["execution_id"],
            "u12_acceptance_duration_ms": manifest["u12_live"][
                "u12_acceptance_duration_ms"
            ],
            "u13a_state_root": manifest["u13a_state_root"],
            "installed_source_sha256": manifest["installed_source_sha256"],
            "predecessor_identity": manifest["recovery_authority"][
                "predecessor_identity"
            ],
            "backup_identity": manifest["recovery_authority"][
                "backup_identity"
            ],
            "transition_source_b64": base64.b64encode(
                TRANSITION_SOURCE.read_bytes()
            ).decode("ascii"),
            "transition_source_sha256": hashlib.sha256(
                TRANSITION_SOURCE.read_bytes()
            ).hexdigest(),
        }
    )
    return plan


def remote_mode(
    transport,
    plan: dict[str, Any],
    mode: str,
    *extra: str,
    timeout: int = EXECUTE_TIMEOUT_SECONDS,
):
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
        completed, result = remote_mode(
            transport,
            plan,
            "status",
            timeout=120,
        )
        base.write_remote_evidence(evidence, "status_remote", completed)
        base.write_private_json(evidence / "status.json", result)
        return completed, result
    except Exception as error:
        return None, {
            "status": "STOP_UNKNOWN",
            "reason": type(error).__name__ + ":" + str(error)[:180],
            "terminal": False,
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
    group.add_argument("--execute", action="store_true")
    group.add_argument("--status-only", action="store_true")
    parser.add_argument("--authorization-id", default="")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()

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
        "service_mutation": False,
        "image_mutation": False,
        "u13a_committed": False,
        "u13a_transition": False,
        "u13b_transition": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    readonly = load_readonly()
    u12 = readonly.load_u12_readonly()
    base = u12.load_r37().load_base()

    try:
        manifest = read_manifest(args.expected_package_commit)
        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = build_plan(manifest, args.execution_id)
        transport_type = base.load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        if args.status_only:
            completed, remote = remote_mode(
                transport,
                plan,
                "status",
                timeout=120,
            )
            result["remote_returncode"] = completed.returncode
            result.update(remote)
            base.write_remote_evidence(
                evidence,
                "status_remote",
                completed,
            )
            base.write_private_json(evidence / "status.json", remote)
            return_code = (
                0
                if remote.get("status")
                == "U13A_LIVE_COMMIT_PASS_RECONCILED"
                else 2
            )
        else:
            if manifest.get("u13a_live_execution_authorized") is not True:
                raise Stop("u13a_live_not_authorized")
            if (
                manifest.get("authorization_state")
                != {
                    "granted": True,
                    "claimed": False,
                    "consumed": False,
                    "replay_permitted": False,
                }
                or args.authorization_id != AUTHORIZATION_ID
                or args.confirm != CONFIRMATION
            ):
                raise Stop("local_u13a_live_authorization_invalid")

            readonly_plan = dict(plan)
            readonly_plan["gate_id"] = readonly.GATE_ID
            readonly_plan.pop("transition_source_b64", None)
            readonly_plan.pop("transition_source_sha256", None)
            pre_transport, pre = readonly.remote_preflight(
                transport,
                readonly_plan,
                timeout=1800,
            )
            base.write_remote_evidence(
                evidence,
                "fresh_preflight_remote",
                pre_transport,
            )
            base.write_private_json(
                evidence / "fresh_preflight.json",
                pre,
            )
            if (
                pre_transport.returncode != 0
                or pre.get("status")
                != "U13A_COMMIT_READONLY_PREFLIGHT_PASS"
                or pre.get("forward_commit_eligible") is not True
                or pre.get("rollback_required") is not False
            ):
                raise Stop("u13a_live_fresh_preflight_failed")
            result["fresh_preflight_pass"] = True

            try:
                result["remote_execute_invoked"] = True
                execute_transport, remote = remote_mode(
                    transport,
                    plan,
                    "execute",
                    args.authorization_id,
                    args.confirm,
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
                base.write_private_json(
                    evidence / "execute.json",
                    remote,
                )
                if remote.get("status") not in {
                    "U13A_LIVE_COMMIT_PASS",
                    "U13A_LIVE_COMMIT_PASS_RECONCILED",
                }:
                    result["status_reconciliation_attempted"] = True
                    _, status_result = reconcile_after_invoke(
                        transport,
                        plan,
                        evidence,
                        base,
                    )
                    if status_result.get("terminal") is True:
                        result.update(status_result)
            except Exception as invoke_error:
                result["status_reconciliation_attempted"] = True
                _, status_result = reconcile_after_invoke(
                    transport,
                    plan,
                    evidence,
                    base,
                )
                if status_result.get("terminal") is True:
                    result.update(status_result)
                    result["remote_execute_result_observed"] = True
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
                    )

            return_code = (
                0
                if result.get("status") in {
                    "U13A_LIVE_COMMIT_PASS",
                    "U13A_LIVE_COMMIT_PASS_RECONCILED",
                }
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
