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
R37_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u10_predecessor_capacity_release_readonly_preflight_r37"
    / "executor.py"
)
TRANSITION_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_ha_usb.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U10_PREDECESSOR_CAPACITY_RELEASE_R38_20261116_01"
)
AUTHORIZATION_ID = (
    "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U10_R38_20261116_01"
)
CONFIRMATION = "EXECUTE U10 R38 PREDECESSOR CAPACITY RELEASE: YES"
MANIFEST_SCHEMA = "gh.n3w-t1-u10-r38-predecessor-capacity-release-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u10-r38-local-result/1"
EXECUTE_TIMEOUT_SECONDS = 1500


class Stop(RuntimeError):
    pass


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stop("module_load_failed:" + path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_r37():
    return load_module(R37_EXECUTOR, "n3w_r38_r37")


def r37_remote_library() -> str:
    remote = load_r37().REMOTE_SCRIPT
    marker = "raise SystemExit(main())"
    if marker not in remote:
        raise Stop("r37_remote_library_marker_missing")
    return remote.rsplit(marker, 1)[0]


REMOTE_SCRIPT = r37_remote_library() + r"""
import tempfile
import time

R38_REMOTE_SCHEMA = "gh.n3w-t1-u10-r38-predecessor-capacity-release/1"


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


def load_exact_transition_source(plan):
    try:
        raw = base64.b64decode(
            plan["transition_source_b64"],
            validate=True,
        )
    except Exception as error:
        raise Stop("u10_r38_transition_source_invalid") from error
    observed = hashlib.sha256(raw).hexdigest()
    if observed != plan["transition_source_sha256"]:
        raise Stop("u10_r38_transition_source_hash_mismatch")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Stop("u10_r38_transition_source_encoding_invalid") from error
    namespace = {
        "__name__": "n3w_r38_exact_ha_usb_transition",
        "__file__": "<n3w-r38-exact-ha-usb-transition>",
    }
    try:
        exec(
            compile(
                source,
                "<n3w-r38-exact-ha-usb-transition>",
                "exec",
            ),
            namespace,
        )
    except Exception as error:
        raise Stop("u10_r38_transition_source_load_failed") from error
    function = namespace.get("record_predecessor_capacity_released")
    allowed = namespace.get("destructive_cutover_allowed")
    if not callable(function) or not callable(allowed):
        raise Stop("u10_r38_transition_source_contract_missing")
    return function, allowed


def import_u10_runtime():
    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_prepare_host import (
        SubprocessPrepareBackend,
    )
    from n3w_t1_core_updater_ha_usb_state import (
        HaUsbStateStore,
        validate_transaction_document,
    )
    return {
        "SubprocessPrepareBackend": SubprocessPrepareBackend,
        "HaUsbStateStore": HaUsbStateStore,
        "validate_transaction_document": validate_transaction_document,
    }


def container_absent(container_id):
    completed = run(
        ["docker", "inspect", container_id],
        timeout=45,
        check=False,
    )
    return completed.returncode != 0


def image_absent(reference):
    completed = run(
        ["docker", "image", "inspect", reference],
        timeout=45,
        check=False,
    )
    return completed.returncode != 0


def exact_predecessor_users(predecessor_id):
    documents = all_container_documents()
    return sorted(
        container_id
        for container_id, item in documents.items()
        if item.get("Image") == predecessor_id
    )


def verify_peer_continuity(plan):
    documents = all_container_documents()
    expected = plan["containers"]
    for service in ("broker", "manager"):
        container_id = expected[service]["container_id"]
        item = documents.get(container_id)
        if item is None:
            raise Stop("u10_r38_peer_container_missing:" + service)
        state = item.get("State")
        config = item.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            not isinstance(state, dict)
            or not isinstance(config, dict)
            or not isinstance(labels, dict)
            or labels.get("com.docker.compose.project") != PROJECT
            or labels.get("com.docker.compose.service") != service
            or item.get("Image") != expected[service]["runtime_image_id"]
            or config.get("Image") != expected[service]["image"]
            or item.get("RestartCount") != 0
        ):
            raise Stop("u10_r38_peer_identity_drift:" + service)
    if documents[expected["broker"]["container_id"]]["State"].get("Status") != "running":
        raise Stop("u10_r38_broker_not_running")
    if documents[expected["manager"]["container_id"]]["State"].get("Status") == "running":
        raise Stop("u10_r38_manager_not_quiesced")
    return {
        "broker_running": True,
        "manager_quiesced": True,
        "manager_broker_release_forbidden": True,
    }


def verify_terminal_u10(plan):
    runtime = import_u10_runtime()
    transition, allowed = load_exact_transition_source(plan)
    del transition

    transaction = read_object(TX)
    runtime["validate_transaction_document"](transaction)
    if (
        transaction.get("phase")
        != "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("current_image_ref")
        != plan["predecessor_image"]
        or transaction.get("target_image_ref")
        != plan["target_image"]
        or transaction.get("target_archive_sha256")
        != plan["target_archive_sha256"]
        or transaction.get("target_archive_size")
        != plan["target_archive_size_bytes"]
        or transaction.get("authorization_claimed") is not True
        or transaction.get("authorization_consumed") is not True
        or transaction.get("authorization_id_sha256")
        != plan["authorization_id_sha256"]
        or allowed(transaction) is not True
    ):
        raise Stop("u10_r38_terminal_transaction_invalid")

    if not container_absent(
        plan["containers"]["homeassistant"]["container_id"]
    ):
        raise Stop("u10_r38_terminal_ha_container_present")
    if not image_absent(plan["predecessor_runtime_image_id"]):
        raise Stop("u10_r38_terminal_predecessor_id_present")
    if not image_absent(plan["predecessor_image"]):
        raise Stop("u10_r38_terminal_predecessor_ref_present")
    if not image_absent(plan["target_image"]):
        raise Stop("u10_r38_terminal_target_present")
    if exact_predecessor_users(plan["predecessor_runtime_image_id"]):
        raise Stop("u10_r38_terminal_predecessor_still_referenced")

    require_unit(HOST_UNIT, active=True)
    require_unit(SERVICES_UNIT, active=False)
    require_unit(BROKER_UNIT, active=True)
    peers = verify_peer_continuity(plan)

    root = Path(plan["mount_target"]) / "n3w-update" / "transaction"
    manifest = read_object(root / "manifest.json")
    phase = read_object(root / "phase.json")
    authority = read_object(root / "content-authority.json")
    checksums = read_object(root / "checksums.json")
    if (
        manifest.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or manifest.get("usb_filesystem_uuid")
        != transaction["usb_filesystem_uuid"]
        or phase.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or phase.get("phase")
        != "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
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
        raise Stop("u10_r38_terminal_usb_mirror_invalid")

    return {
        "transaction_phase": transaction["phase"],
        "transaction_sha256": sha_file(TX),
        "usb_mirror_exact": True,
        "mirror_sha256": {
            "manifest": sha_file(root / "manifest.json"),
            "phase": sha_file(root / "phase.json"),
            "content_authority": sha_file(
                root / "content-authority.json"
            ),
            "checksums": sha_file(root / "checksums.json"),
        },
        "predecessor_runtime_released": True,
        "predecessor_image_released": True,
        "target_internal_image_absent": True,
        **peers,
    }


def status(plan):
    root = Path(plan["state_root"])
    claim_path = root / "authorization_claim.json"
    success_path = root / "success.json"
    failure_path = root / "failure.json"

    if success_path.exists():
        terminal = verify_terminal_u10(plan)
        value = read_object(success_path)
        value.update(
            status="U10_R38_PREDECESSOR_CAPACITY_RELEASE_PASS_RECONCILED",
            terminal=True,
            reconciled_from_durable_u10=True,
            post=terminal,
        )
        return value
    if failure_path.exists():
        value = read_object(failure_path)
        value["terminal"] = True
        value["reconciled_from_ledger"] = True
        return value

    claim = read_object(claim_path) if claim_path.exists() else None
    transaction = read_object(TX)
    return {
        "schema": R38_REMOTE_SCHEMA,
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
        "destructive_cutover": bool(claim),
        "u11_plus": False,
        "target_image_load": False,
        "service_mutation": False,
    }


def execute(plan, authorization_id, confirmation):
    result = {
        "schema": R38_REMOTE_SCHEMA,
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "destructive_cutover": False,
        "predecessor_runtime_delete": False,
        "predecessor_image_delete": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u10_transition": False,
        "target_image_load": False,
        "service_mutation": False,
        "u11_plus": False,
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
        raise Stop("u10_r38_state_root_residue")

    pre = run_readonly(plan)
    if pre.get("status") != "U10_R37_READONLY_PREFLIGHT_PASS":
        raise Stop("u10_r38_embedded_preclaim_failed")

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    claim = {
        "schema": "gh.n3w-t1-u10-r38-authorization-claim/1",
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
        destructive_cutover=True,
    )

    def progress(phase, value=0):
        durable_json_replace(
            state_root / "progress.json",
            {
                "schema": "gh.n3w-t1-u10-r38-progress/1",
                "phase": phase,
                "value": value,
                "updated_at_unix": int(time.time()),
            },
        )

    try:
        progress("executor_claimed")
        runtime = import_u10_runtime()
        transition, allowed = load_exact_transition_source(plan)
        store = runtime["HaUsbStateStore"]()
        backend = runtime["SubprocessPrepareBackend"]()

        with store.lock():
            current = store.read()
            if current is None:
                raise Stop("u10_r38_transaction_missing")
            current = runtime["validate_transaction_document"](current)
            if (
                sha_file(TX) != plan["transaction_sha256"]
                or current.get("phase")
                != "U9_LIVE_AUTHORIZATION_CLAIMED"
                or allowed(current) is not True
            ):
                raise Stop("u10_r38_u9_transaction_drift_after_claim")

            verify_runtime_and_release_candidate(plan)
            require_bound_mount(plan)
            if image_absent(plan["target_image"]) is not True:
                raise Stop("u10_r38_target_present_before_release")

            media = backend.resolve_transaction_media(
                current,
                write_required=True,
            )
            if (
                media is None
                or media.filesystem_uuid != plan["filesystem_uuid"]
                or media.mount_path != plan["mount_target"]
            ):
                raise Stop("u10_r38_bound_media_drift_after_claim")

            ha_id = plan["containers"]["homeassistant"]["container_id"]
            predecessor_id = plan["predecessor_runtime_image_id"]

            progress("remove_exact_homeassistant_container")
            run(["docker", "rm", ha_id], timeout=120)
            if not container_absent(ha_id):
                raise Stop("u10_r38_ha_container_remove_verify_failed")
            if exact_predecessor_users(predecessor_id):
                raise Stop("u10_r38_predecessor_still_referenced_after_container_release")
            result["predecessor_runtime_delete"] = True

            verify_peer_continuity(plan)
            if image_absent(plan["target_image"]) is not True:
                raise Stop("u10_r38_target_loaded_before_image_release")

            progress("remove_exact_predecessor_image")
            run(["docker", "image", "rm", predecessor_id], timeout=300)
            if not image_absent(predecessor_id):
                raise Stop("u10_r38_predecessor_image_remove_verify_failed")
            if not image_absent(plan["predecessor_image"]):
                raise Stop("u10_r38_predecessor_ref_remove_verify_failed")
            if image_absent(plan["target_image"]) is not True:
                raise Stop("u10_r38_target_loaded_before_u10")
            result["predecessor_image_delete"] = True

            verify_peer_continuity(plan)

            progress("record_u10")
            next_tx = transition(
                current,
                predecessor_runtime_released=True,
                predecessor_image_released=True,
                target_internal_image_absent=True,
            )
            if (
                next_tx.get("phase")
                != "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
                or allowed(next_tx) is not True
            ):
                raise Stop("u10_r38_transition_result_invalid")

            progress("u10_usb_sync")
            backend.sync_transaction_metadata(next_tx, media)
            result["usb_mutation"] = True

            progress("u10_host_sync")
            store.write(next_tx)
            result["transaction_mutation"] = True
            result["u10_transition"] = True

        terminal = verify_terminal_u10(plan)
        result.update(
            status="U10_R38_PREDECESSOR_CAPACITY_RELEASE_PASS",
            pre=pre,
            post=terminal,
            transaction_phase=terminal["transaction_phase"],
            transaction_sha256=terminal["transaction_sha256"],
            destructive_cutover=True,
            predecessor_runtime_delete=True,
            predecessor_image_delete=True,
            transaction_mutation=True,
            usb_mutation=True,
            u10_transition=True,
            target_image_load=False,
            service_mutation=False,
            u11_plus=False,
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
            result["u10_transition"] = (
                current.get("phase")
                == "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
            )
            result["transaction_mutation"] = (
                sha_file(TX) != plan["transaction_sha256"]
            )
        except Exception:
            pass
        try:
            terminal = verify_terminal_u10(plan)
            result.update(
                status="STOP_POSTSUCCESS_LOCAL",
                postclaim_terminal_probe=terminal,
                predecessor_runtime_delete=True,
                predecessor_image_delete=True,
                transaction_mutation=True,
                usb_mutation=True,
                u10_transition=True,
            )
        except Exception as reconcile_error:
            result["status"] = "STOP_POSTCLAIM"
            result["reconciliation_error"] = (
                type(reconcile_error).__name__
                + ":"
                + str(reconcile_error)[:180]
            )
        result["target_image_load"] = False
        result["service_mutation"] = False
        result["u11_plus"] = False
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
        plan = json.loads(
            base64.b64decode(sys.argv[2]).decode("utf-8")
        )
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U10_PREDECESSOR_CAPACITY_RELEASE_R38_20261116_01"
        ):
            raise Stop("gate_id_invalid")
        if mode == "status":
            result = status(plan)
        elif mode == "execute":
            result = execute(plan, sys.argv[3], sys.argv[4])
        else:
            raise Stop("mode_invalid")
    except Exception as error:
        result = {
            "schema": R38_REMOTE_SCHEMA,
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
            "destructive_cutover": False,
            "predecessor_runtime_delete": False,
            "predecessor_image_delete": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "u10_transition": False,
            "target_image_load": False,
            "service_mutation": False,
            "u11_plus": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {
        "U10_R38_PREDECESSOR_CAPACITY_RELEASE_PASS",
        "U10_R38_PREDECESSOR_CAPACITY_RELEASE_PASS_RECONCILED",
    } else 2


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


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(expected_commit: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")

    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    live_authorized = document.get("live_execution_authorized")
    if (
        document.get("schema") != MANIFEST_SCHEMA
        or document.get("gate_id") != GATE_ID
        or type(live_authorized) is not bool
        or document.get("authorization_id") != AUTHORIZATION_ID
        or document.get("confirmation") != CONFIRMATION
        or document.get("authorization_state")
        != {
            "granted": live_authorized,
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
        completed, status = remote_mode(
            transport,
            "status",
            plan,
            timeout=180,
        )
        base.write_remote_evidence(
            evidence,
            "status_reconcile_remote",
            completed,
        )
        base.write_private_json(
            evidence / "status_reconcile.json",
            status,
        )
        return completed, status
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
            "destructive_cutover": True,
            "u11_plus": False,
            "target_image_load": False,
            "service_mutation": False,
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
        "remote_preclaim_invoked": False,
        "remote_execute_invoked": False,
        "remote_execute_result_observed": False,
        "status_reconciliation_attempted": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "destructive_cutover": False,
        "predecessor_runtime_delete": False,
        "predecessor_image_delete": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u10_transition": False,
        "target_image_load": False,
        "service_mutation": False,
        "u11_plus": False,
        "board_access": False,
        "merge": False,
    }

    transport = None
    return_code = 2
    r37 = load_r37()
    base = r37.load_base()

    try:
        manifest = read_manifest(args.expected_package_commit)
        if manifest["live_execution_authorized"] is not True:
            raise Stop("r38_live_execution_not_authorized")
        if (
            args.authorization_id != AUTHORIZATION_ID
            or args.confirm != CONFIRMATION
        ):
            raise Stop("authorization_invalid")

        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_u9_entry"])
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
                "r35_state_root": manifest["r35_state_root"],
                "r36_state_root": manifest["r36_state_root"],
                "mount_target": manifest["mount_target"],
                "installed_source_sha256": (
                    manifest["installed_source_sha256"]
                ),
                "execution_id": args.execution_id,
            }
        )
        source_bytes = TRANSITION_SOURCE.read_bytes()
        plan["transition_source_sha256"] = hashlib.sha256(
            source_bytes
        ).hexdigest()
        plan["transition_source_b64"] = base64.b64encode(
            source_bytes
        ).decode("ascii")

        transport_type = base.load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        result["remote_preclaim_invoked"] = True
        pre_transport, pre = r37.remote_preflight(transport, plan)
        base.write_remote_evidence(
            evidence,
            "r37_preclaim_remote",
            pre_transport,
        )
        base.write_private_json(
            evidence / "r37_preclaim.json",
            pre,
        )
        if (
            pre_transport.returncode != 0
            or pre.get("status")
            != "U10_R37_READONLY_PREFLIGHT_PASS"
            or pre.get("u10_readonly_eligible") is not True
        ):
            result.update(
                status="STOP_PRECLAIM",
                preclaim=pre,
                remote_preclaim_returncode=pre_transport.returncode,
            )
            return_code = 2
        else:
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
                base.write_private_json(
                    evidence / "execute.json",
                    remote,
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
                        reason=(
                            "postinvoke_unknown:"
                            + type(invoke_error).__name__
                            + ":"
                            + str(invoke_error)[:180]
                        ),
                        authorization_claimed=True,
                        authorization_consumed=True,
                        replay_permitted=False,
                        destructive_cutover=True,
                        u11_plus=False,
                        target_image_load=False,
                        service_mutation=False,
                    )

            if result.get("status") in {
                "U10_R38_PREDECESSOR_CAPACITY_RELEASE_PASS",
                "U10_R38_PREDECESSOR_CAPACITY_RELEASE_PASS_RECONCILED",
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
                    result["completed_remote_status"] = result.get(
                        "status"
                    )
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
