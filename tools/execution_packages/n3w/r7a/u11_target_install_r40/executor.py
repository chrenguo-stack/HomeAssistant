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
R39_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u11_target_install_readonly_preflight_r39"
    / "executor.py"
)
U11_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_ha_u11.py"
U11_HOST_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_ha_u11_host.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U11_TARGET_INSTALL_R40_20261116_01"
)
AUTHORIZATION_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U11_R40_20261116_01"
CONFIRMATION = "EXECUTE U11 R40 TARGET INSTALL: YES"
MANIFEST_SCHEMA = "gh.n3w-t1-u11-r40-target-install-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u11-r40-local-result/1"
EXECUTE_TIMEOUT_SECONDS = 2400


class Stop(RuntimeError):
    pass


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stop("module_load_failed:" + path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_r39():
    return load_module(R39_EXECUTOR, "n3w_r40_r39")


def r39_remote_library() -> str:
    remote = load_r39().REMOTE_SCRIPT
    marker = "raise SystemExit(main())"
    if marker not in remote:
        raise Stop("r39_remote_library_marker_missing")
    return remote.rsplit(marker, 1)[0]


REMOTE_SCRIPT = r39_remote_library() + r"""
import importlib.util
import tempfile
import time

R40_REMOTE_SCHEMA = "gh.n3w-t1-u11-r40-target-install/1"


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


def _decode_exact_source(plan, prefix):
    try:
        raw = base64.b64decode(
            plan[prefix + "_source_b64"],
            validate=True,
        )
    except Exception as error:
        raise Stop("u11_r40_exact_source_invalid:" + prefix) from error
    if hashlib.sha256(raw).hexdigest() != plan[prefix + "_source_sha256"]:
        raise Stop("u11_r40_exact_source_hash_mismatch:" + prefix)
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Stop("u11_r40_exact_source_encoding_invalid:" + prefix) from error
    return raw


def load_exact_u11_modules(plan):
    controller_raw = _decode_exact_source(plan, "u11")
    host_raw = _decode_exact_source(plan, "u11_host")
    temporary = tempfile.TemporaryDirectory(prefix="n3w-r40-u11-")
    root = Path(temporary.name)
    controller_path = root / "n3w_t1_core_updater_ha_u11.py"
    host_path = root / "n3w_t1_core_updater_ha_u11_host.py"
    controller_path.write_bytes(controller_raw)
    host_path.write_bytes(host_raw)
    os.chmod(controller_path, 0o600)
    os.chmod(host_path, 0o600)

    loaded = []
    try:
        for name, path in (
            ("n3w_t1_core_updater_ha_u11", controller_path),
            ("n3w_t1_core_updater_ha_u11_host", host_path),
        ):
            prior = sys.modules.pop(name, None)
            if prior is not None:
                loaded.append((name, prior))
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise Stop("u11_r40_exact_source_spec_invalid:" + name)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        return (
            temporary,
            sys.modules["n3w_t1_core_updater_ha_u11"],
            sys.modules["n3w_t1_core_updater_ha_u11_host"],
            loaded,
        )
    except Exception:
        for name in (
            "n3w_t1_core_updater_ha_u11_host",
            "n3w_t1_core_updater_ha_u11",
        ):
            sys.modules.pop(name, None)
        for name, module in loaded:
            sys.modules[name] = module
        temporary.cleanup()
        raise


def cleanup_exact_u11_modules(temporary, loaded):
    for name in (
        "n3w_t1_core_updater_ha_u11_host",
        "n3w_t1_core_updater_ha_u11",
    ):
        sys.modules.pop(name, None)
    for name, module in loaded:
        sys.modules[name] = module
    temporary.cleanup()


def import_installed_u11_runtime():
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


def verify_terminal_u11(plan):
    runtime = import_installed_u11_runtime()
    transaction = read_object(TX)
    runtime["validate_transaction_document"](transaction)
    if (
        transaction.get("phase") != "U11_TARGET_INSTALLED_STARTED"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("current_image_ref")
        != plan["predecessor_image"]
        or transaction.get("target_image_ref") != plan["target_image"]
        or transaction.get("target_archive_sha256")
        != plan["target_archive_sha256"]
        or transaction.get("authorization_claimed") is not True
        or transaction.get("authorization_consumed") is not True
    ):
        raise Stop("u11_r40_terminal_transaction_invalid")

    require_unit(HOST_UNIT, active=True)
    require_unit(BROKER_UNIT, active=True)
    require_unit(SERVICES_UNIT, active=True)

    documents = all_container_documents()
    expected = plan["containers"]
    for service in ("broker", "manager"):
        container_id = expected[service]["container_id"]
        item = documents.get(container_id)
        if item is None:
            raise Stop("u11_r40_peer_container_missing:" + service)
        state = item.get("State")
        config = item.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            not isinstance(state, dict)
            or state.get("Status") != "running"
            or not isinstance(config, dict)
            or not isinstance(labels, dict)
            or labels.get("com.docker.compose.project") != PROJECT
            or labels.get("com.docker.compose.service") != service
            or item.get("Image") != expected[service]["runtime_image_id"]
            or config.get("Image") != expected[service]["image"]
            or item.get("RestartCount") != 0
        ):
            raise Stop("u11_r40_peer_identity_drift:" + service)

    homeassistant = [
        item
        for item in documents.values()
        if isinstance(item.get("Config"), dict)
        and isinstance(item["Config"].get("Labels"), dict)
        and item["Config"]["Labels"].get("com.docker.compose.project") == PROJECT
        and item["Config"]["Labels"].get("com.docker.compose.service")
        == "homeassistant"
        and isinstance(item.get("State"), dict)
        and item["State"].get("Status") == "running"
    ]
    if len(homeassistant) != 1:
        raise Stop("u11_r40_homeassistant_runtime_count_invalid")
    ha = homeassistant[0]
    if ha["Config"].get("Image") != plan["target_image"]:
        raise Stop("u11_r40_homeassistant_target_ref_drift")
    target_runtime_id = ha.get("Image")
    if (
        not isinstance(target_runtime_id, str)
        or not target_runtime_id.startswith("sha256:")
    ):
        raise Stop("u11_r40_target_runtime_id_invalid")

    mounts = ha.get("Mounts")
    if not isinstance(mounts, list):
        raise Stop("u11_r40_homeassistant_mounts_invalid")
    production_mounts = [
        row
        for row in mounts
        if isinstance(row, dict)
        and row.get("Type") == "bind"
        and row.get("Source") == "/var/lib/n3wfc4-homeassistant"
        and row.get("Destination") == "/config"
        and row.get("RW") is True
    ]
    if len(production_mounts) != 1:
        raise Stop("u11_r40_homeassistant_production_config_missing")

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
        or phase.get("phase") != "U11_TARGET_INSTALLED_STARTED"
        or authority.get("transaction_id_sha256")
        != transaction["transaction_id_sha256"]
        or authority.get("target_artifact_identity")
        != transaction["target_artifact_identity"]
        or authority.get("predecessor_recovery_identity")
        != transaction["predecessor_recovery_identity"]
        or authority.get("ha_data_backup_identity")
        != transaction["ha_data_backup_identity"]
        or checksums.get("target_archive_sha256")
        != transaction["target_archive_sha256"]
        or checksums.get("target_archive_size_bytes")
        != transaction["target_archive_size"]
    ):
        raise Stop("u11_r40_terminal_usb_mirror_invalid")

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
        "target_image_loaded": True,
        "target_runtime_image_id": target_runtime_id,
        "target_homeassistant_running": True,
        "manager_running": True,
        "broker_running": True,
        "production_config_mounted": True,
        "u12_acceptance": False,
    }


def status(plan):
    root = Path(plan["state_root"])
    claim_path = root / "authorization_claim.json"
    success_path = root / "success.json"
    failure_path = root / "failure.json"

    if success_path.exists():
        terminal = verify_terminal_u11(plan)
        value = read_object(success_path)
        value.update(
            status="U11_R40_TARGET_INSTALL_PASS_RECONCILED",
            terminal=True,
            reconciled_from_durable_u11=True,
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
        "schema": R40_REMOTE_SCHEMA,
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
        "target_image_load_may_have_occurred": bool(claim),
        "service_mutation_may_have_occurred": bool(claim),
        "u12_plus": False,
    }


def execute(plan, authorization_id, confirmation):
    result = {
        "schema": R40_REMOTE_SCHEMA,
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "target_image_load": False,
        "compose_binding_mutation": False,
        "service_mutation": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u11_transition": False,
        "u12_plus": False,
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
        raise Stop("u11_r40_state_root_residue")

    r39_plan = dict(plan)
    r39_plan["gate_id"] = (
        "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
        "U11_TARGET_INSTALL_READONLY_PREFLIGHT_R39_20261116_01"
    )
    pre = run_readonly(r39_plan)
    if pre.get("status") != "U11_R39_READONLY_PREFLIGHT_PASS":
        raise Stop("u11_r40_embedded_preclaim_failed")

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    claim = {
        "schema": "gh.n3w-t1-u11-r40-authorization-claim/1",
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
                "schema": "gh.n3w-t1-u11-r40-progress/1",
                "phase": phase,
                "value": value,
                "updated_at_unix": int(time.time()),
            },
        )

    temporary = None
    loaded = []
    try:
        progress("executor_claimed")
        runtime = import_installed_u11_runtime()
        temporary, u11, u11_host, loaded = load_exact_u11_modules(plan)

        store = runtime["HaUsbStateStore"]()
        backend = runtime["SubprocessPrepareBackend"]()
        expected = plan["containers"]
        owner = u11_host.LocalU11RuntimeOwner(
            expected_manager_container_id=expected["manager"]["container_id"],
            expected_manager_image_ref=expected["manager"]["image"],
            expected_manager_runtime_image_id=expected["manager"][
                "runtime_image_id"
            ],
            expected_broker_container_id=expected["broker"]["container_id"],
            expected_broker_image_ref=expected["broker"]["image"],
            expected_broker_runtime_image_id=expected["broker"][
                "runtime_image_id"
            ],
        )
        controller = u11.HaUsbU11TargetInstallController(
            transaction_store=store,
            backend=backend,
            runtime_owner=owner,
        )

        progress("target_install_begin")
        with store.lock():
            installed = controller.install()

        result.update(
            target_image_load=True,
            compose_binding_mutation=True,
            service_mutation=True,
            transaction_mutation=True,
            usb_mutation=True,
            u11_transition=True,
        )
        progress("terminal_verify")
        post = verify_terminal_u11(plan)
        result.update(
            status="U11_R40_TARGET_INSTALL_PASS",
            post=post,
            target_runtime_image_id=installed.target_runtime_image_id,
        )
        durable_json_once(state_root / "success.json", result)
        progress("executor_success")
        return result
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:300]
        result["status"] = "STOP_POSTCLAIM"
        result["recovery_required"] = True
        result["replay_permitted"] = False
        try:
            transaction = read_object(TX)
            result["observed_transaction_phase"] = transaction.get("phase")
            result["transaction_mutation"] = (
                sha_file(TX) != plan["transaction_sha256"]
            )
        except Exception:
            pass
        try:
            target_present = not image_absent(plan["target_image"])
            result["target_image_load"] = target_present
        except Exception:
            pass
        try:
            progress("executor_failure")
        except Exception:
            pass
        try:
            durable_json_once(state_root / "failure.json", result)
        except Exception:
            pass
        return result
    finally:
        if temporary is not None:
            try:
                cleanup_exact_u11_modules(temporary, loaded)
            except Exception:
                pass


def main():
    try:
        mode = sys.argv[1]
        plan = json.loads(
            base64.b64decode(sys.argv[2]).decode("utf-8")
        )
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U11_TARGET_INSTALL_R40_20261116_01"
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
            "schema": R40_REMOTE_SCHEMA,
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
            "target_image_load": False,
            "compose_binding_mutation": False,
            "service_mutation": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "u11_transition": False,
            "u12_plus": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {
        "U11_R40_TARGET_INSTALL_PASS",
        "U11_R40_TARGET_INSTALL_PASS_RECONCILED",
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


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        completed, status_value = remote_mode(
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
            status_value,
        )
        return completed, status_value
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
            "recovery_required": True,
            "u12_plus": False,
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
        "target_image_load": False,
        "compose_binding_mutation": False,
        "service_mutation": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u11_transition": False,
        "u12_plus": False,
        "board_access": False,
        "merge": False,
    }

    transport = None
    return_code = 2
    r39 = load_r39()
    base = r39.load_r37().load_base()

    try:
        manifest = read_manifest(args.expected_package_commit)
        if manifest["live_execution_authorized"] is not True:
            raise Stop("r40_live_execution_not_authorized")
        if (
            args.authorization_id != AUTHORIZATION_ID
            or args.confirm != CONFIRMATION
        ):
            raise Stop("authorization_invalid")

        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_u10_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "authorization_id": manifest["authorization_id"],
                "confirmation": manifest["confirmation"],
                "live_execution_authorized": manifest[
                    "live_execution_authorized"
                ],
                "authorization_state": manifest["authorization_state"],
                "state_root": manifest["state_root"],
                "r38_state_root": manifest["r38_state_root"],
                "mount_target": manifest["mount_target"],
                "installed_source_sha256": manifest[
                    "installed_source_sha256"
                ],
                "target_import_worst_case_allowance_bytes": manifest[
                    "internal_capacity_policy"
                ]["target_import_worst_case_allowance_bytes"],
                "derived_post_peak_reserve_bytes": manifest[
                    "internal_capacity_policy"
                ]["derived_post_peak_reserve_bytes"],
                "execution_id": args.execution_id,
            }
        )
        for prefix, source in (
            ("u11", U11_SOURCE),
            ("u11_host", U11_HOST_SOURCE),
        ):
            raw = source.read_bytes()
            plan[prefix + "_source_sha256"] = hashlib.sha256(raw).hexdigest()
            plan[prefix + "_source_b64"] = base64.b64encode(raw).decode("ascii")

        transport_type = base.load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        result["remote_preclaim_invoked"] = True
        r39_plan = dict(plan)
        r39_plan["gate_id"] = r39.GATE_ID
        pre_transport, pre = r39.remote_mode(
            transport,
            r39_plan,
            timeout=1200,
        )
        base.write_remote_evidence(
            evidence,
            "r39_preclaim_remote",
            pre_transport,
        )
        base.write_private_json(
            evidence / "r39_preclaim.json",
            pre,
        )
        if (
            pre_transport.returncode != 0
            or pre.get("status") != "U11_R39_READONLY_PREFLIGHT_PASS"
            or pre.get("u11_readonly_eligible") is not True
        ):
            result.update(
                status="STOP_PRECLAIM",
                preclaim=pre,
                remote_preclaim_returncode=pre_transport.returncode,
            )
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
                status_transport, status_value = reconcile_after_invoke(
                    transport,
                    plan,
                    evidence,
                    base,
                )
                if status_value.get("terminal") is True:
                    result.update(status_value)
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
                        recovery_required=True,
                    )

            if result.get("status") in {
                "U11_R40_TARGET_INSTALL_PASS",
                "U11_R40_TARGET_INSTALL_PASS_RECONCILED",
            }:
                return_code = 0

    except Exception as error:
        result.update(
            status="STOP",
            reason=type(error).__name__ + ":" + str(error)[:300],
        )
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
