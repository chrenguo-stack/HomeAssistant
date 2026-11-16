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
R41_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u11_postclaim_recovery_readonly_preflight"
    / "executor.py"
)
REPAIRED_HOST_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_host.py"
U11_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_ha_u11.py"
U11_HOST_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_ha_u11_host.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U11_POST_R40_SUCCESSOR_LIVE_RECOVERY_R42_20261116_01"
)
AUTHORIZATION_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_U11_R42_20261116_01"
CONFIRMATION = "EXECUTE U11 R42 POST-R40 SUCCESSOR RECOVERY: YES"
MANIFEST_SCHEMA = "gh.n3w-t1-u11-r42-post-r40-successor-recovery-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u11-r42-local-result/1"
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


def load_r41():
    return load_module(R41_EXECUTOR, "n3w_r42_r41")


def r41_remote_library() -> str:
    remote = load_r41().REMOTE_SCRIPT
    marker = "raise SystemExit(main())"
    if marker not in remote:
        raise Stop("r41_remote_library_marker_missing")
    return remote.rsplit(marker, 1)[0]


REMOTE_SCRIPT = r41_remote_library() + r"""
import importlib.util
import tempfile
import time

R42_REMOTE_SCHEMA = "gh.n3w-t1-u11-r42-post-r40-successor-recovery/1"


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
        raise Stop("u11_r42_exact_source_invalid:" + prefix) from error
    if hashlib.sha256(raw).hexdigest() != plan[prefix + "_source_sha256"]:
        raise Stop("u11_r42_exact_source_hash_mismatch:" + prefix)
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Stop("u11_r42_exact_source_encoding_invalid:" + prefix) from error
    return raw


def load_exact_u11_modules(plan):
    types = __import__("types")
    names = (
        "n3w_t1_core_updater_host",
        "n3w_t1_core_updater_ha_u11",
        "n3w_t1_core_updater_ha_u11_host",
    )
    prefixes = ("repaired_host", "u11", "u11_host")
    previous = {name: sys.modules.get(name) for name in names}
    try:
        modules = {}
        for name, prefix in zip(names, prefixes):
            raw = _decode_exact_source(plan, prefix)
            module = types.ModuleType(name)
            module.__file__ = "<memory:" + name + ".py>"
            sys.modules[name] = module
            exec(
                compile(raw.decode("utf-8"), module.__file__, "exec"),
                module.__dict__,
            )
            modules[name] = module
        return modules, previous
    except Exception:
        for name, prior in previous.items():
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior
        raise


def cleanup_exact_u11_modules(previous):
    for name, prior in previous.items():
        if prior is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = prior


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
        raise Stop("u11_r42_terminal_transaction_invalid")

    require_unit(HOST_UNIT, active=True)
    require_unit(BROKER_UNIT, active=True)
    require_unit(SERVICES_UNIT, active=True)

    documents = all_container_documents()
    expected = plan["containers"]
    for service in ("broker", "manager"):
        container_id = expected[service]["container_id"]
        item = documents.get(container_id)
        if item is None:
            raise Stop("u11_r42_peer_container_missing:" + service)
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
            raise Stop("u11_r42_peer_identity_drift:" + service)

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
        raise Stop("u11_r42_homeassistant_runtime_count_invalid")
    ha = homeassistant[0]
    if ha["Config"].get("Image") != plan["target_image"]:
        raise Stop("u11_r42_homeassistant_target_ref_drift")
    target_runtime_id = ha.get("Image")
    if (
        not isinstance(target_runtime_id, str)
        or not target_runtime_id.startswith("sha256:")
    ):
        raise Stop("u11_r42_target_runtime_id_invalid")

    mounts = ha.get("Mounts")
    if not isinstance(mounts, list):
        raise Stop("u11_r42_homeassistant_mounts_invalid")
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
        raise Stop("u11_r42_homeassistant_production_config_missing")

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
        raise Stop("u11_r42_terminal_usb_mirror_invalid")

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
            status="U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS_RECONCILED",
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
        "schema": R42_REMOTE_SCHEMA,
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
        "schema": R42_REMOTE_SCHEMA,
        "status": "STOP",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "authorization_claim_persistence_unknown": False,
        "r40_replay": False,
        "target_image_load": False,
        "compose_binding_mutation": False,
        "service_mutation": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u11_transition": False,
        "u12_plus": False,
        "u13_plus": False,
        "board_access": False,
        "merge": False,
    }
    if (
        authorization_id != plan["authorization_id"]
        or confirmation != plan["confirmation"]
        or plan.get("live_recovery_authorized") is not True
        or plan.get("r40_replay_permitted") is not False
        or plan.get("authorization_state")
        != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("u11_r42_authorization_invalid")

    state_root = Path(plan["state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("u11_r42_state_root_residue")

    pre = run_successor_readonly(plan)
    if pre.get("status") != "U11_R41_POST_R40_READONLY_PREFLIGHT_PASS":
        raise Stop("u11_r42_embedded_r41_preclaim_failed")

    state_root.mkdir(mode=0o700)
    os.chown(state_root, 0, 0)
    _fsync_directory(state_root.parent)

    claim = {
        "schema": "gh.n3w-t1-u11-r42-authorization-claim/1",
        "gate_id": plan["gate_id"],
        "authorization_id": authorization_id,
        "execution_id": plan["execution_id"],
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
    }
    try:
        durable_json_once(state_root / "authorization_claim.json", claim)
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
            recovery_required=True,
        )
        return result

    result.update(
        authorization_claimed=True,
        authorization_consumed=True,
        replay_permitted=False,
    )

    previous = None
    try:
        postclaim = run_successor_readonly(plan)
        if postclaim.get("status") != "U11_R41_POST_R40_READONLY_PREFLIGHT_PASS":
            raise Stop("u11_r42_postclaim_r41_revalidation_failed")

        runtime = import_installed_u11_runtime()
        modules, previous = load_exact_u11_modules(plan)
        u11 = modules["n3w_t1_core_updater_ha_u11"]
        u11_host = modules["n3w_t1_core_updater_ha_u11_host"]

        store = runtime["HaUsbStateStore"]()
        backend = runtime["SubprocessPrepareBackend"]()
        current = runtime["validate_transaction_document"](store.read())
        if (
            current.get("phase") != "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
            or sha_file(TX) != plan["transaction_sha256"]
        ):
            raise Stop("u11_r42_transaction_drift_after_claim")

        media = backend.resolve_transaction_media(current, write_required=True)
        if media is None:
            raise Stop("u11_r42_transaction_media_unavailable")
        target = u11.validate_image_recovery_record(
            backend.verify_prepared_target(
                transaction=current,
                media=media,
            ),
            expected_kind="target",
            expected_image_ref=str(current["target_image_ref"]),
            expected_archive_sha256=str(current["target_archive_sha256"]),
        )
        if target.public() != current.get("target_artifact_identity"):
            raise Stop("u11_r42_target_identity_drift")

        archive = Path(media.mount_path) / u11.TARGET_ARCHIVE_RELATIVE
        if archive.is_symlink() or not archive.is_file():
            raise Stop("u11_r42_target_archive_invalid")

        expected = plan["containers"]
        owner = u11_host.LocalU11RuntimeOwner(
            expected_manager_container_id=expected["manager"]["container_id"],
            expected_manager_image_ref=expected["manager"]["image"],
            expected_manager_runtime_image_id=expected["manager"]["runtime_image_id"],
            expected_broker_container_id=expected["broker"]["container_id"],
            expected_broker_image_ref=expected["broker"]["image"],
            expected_broker_runtime_image_id=expected["broker"]["runtime_image_id"],
        )
        target_ref = str(current["target_image_ref"])
        if owner.target_image_id(target_ref) is None:
            raise Stop("u11_r42_preloaded_target_missing")
        runtime_id = owner.verify_loaded_target(
            image_ref=target_ref,
            archive=archive,
            expected_archive_sha256=target.archive_sha256,
        )
        if runtime_id != plan["expected_target_runtime_image_id"]:
            raise Stop("u11_r42_preloaded_target_identity_drift")
        if owner.homeassistant_binding() != target_ref:
            raise Stop("u11_r42_target_binding_drift")

        started = owner.start_target_owner(
            target_image_ref=target_ref,
            target_runtime_image_id=runtime_id,
        ).validate(
            expected_target_image_ref=target_ref,
            expected_target_runtime_image_id=runtime_id,
        )
        result["service_mutation"] = True

        next_transaction = u11.record_target_started(current)
        backend.sync_transaction_metadata(next_transaction, media)
        result["usb_mutation"] = True
        store.write(next_transaction)
        result["transaction_mutation"] = True
        result["u11_transition"] = True

        post = verify_terminal_u11(plan)
        if post.get("target_runtime_image_id") != plan["expected_target_runtime_image_id"]:
            raise Stop("u11_r42_terminal_target_identity_drift")
        result.update(
            status="U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS",
            recovery_required=False,
            post=post,
            target_runtime_image_id=runtime_id,
            target_homeassistant_running=started.homeassistant_running,
        )
        durable_json_once(state_root / "success.json", result)
        return result
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:300]
        result["status"] = "STOP_POSTCLAIM"
        result["recovery_required"] = True
        result["replay_permitted"] = False
        result["target_image_load"] = False
        result["compose_binding_mutation"] = False
        try:
            transaction = read_object(TX)
            observed_phase = transaction.get("phase")
            result["observed_transaction_phase"] = observed_phase
            result["transaction_mutation"] = (
                sha_file(TX) != plan["transaction_sha256"]
            )
            result["u11_transition"] = (
                observed_phase == "U11_TARGET_INSTALLED_STARTED"
            )
        except Exception:
            result["transaction_mutation_unknown"] = True
        try:
            if "owner" in locals():
                result["observed_homeassistant_binding"] = owner.homeassistant_binding()
        except Exception:
            pass
        try:
            if "owner" in locals():
                service_state = owner.host._systemctl("is-active", SERVICES_UNIT)
                manager_count = owner.host._running_count("manager")
                ha_count = owner.host._running_count("homeassistant")
                result["observed_services_owner_state"] = service_state
                result["observed_manager_running_count"] = manager_count
                result["observed_homeassistant_running_count"] = ha_count
                result["service_mutation"] = (
                    service_state == "active"
                    or manager_count > 0
                    or ha_count > 0
                )
        except Exception:
            result["service_mutation_unknown"] = True
        try:
            phase_path = (
                Path(plan["mount_target"])
                / "n3w-update"
                / "transaction"
                / "phase.json"
            )
            observed_phase_hash = sha_file(phase_path)
            result["observed_usb_phase_sha256"] = observed_phase_hash
            result["usb_mutation"] = (
                observed_phase_hash != plan["r41_mirror_sha256"]["phase"]
            )
        except Exception:
            result["usb_mutation_unknown"] = True
        try:
            durable_json_once(state_root / "failure.json", result)
        except Exception as ledger_error:
            result["failure_ledger_persistence_unknown"] = True
            result["failure_ledger_error"] = (
                type(ledger_error).__name__ + ":" + str(ledger_error)[:180]
            )
            result["status"] = "STOP_UNKNOWN"
        return result
    finally:
        if previous is not None:
            try:
                cleanup_exact_u11_modules(previous)
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
            "U11_POST_R40_SUCCESSOR_LIVE_RECOVERY_R42_20261116_01"
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
            "schema": R42_REMOTE_SCHEMA,
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
            "u13_plus": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {
        "U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS",
        "U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS_RECONCILED",
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
    live_authorized = document.get("live_recovery_authorized")
    if (
        document.get("schema") != MANIFEST_SCHEMA
        or document.get("gate_id") != GATE_ID
        or type(live_authorized) is not bool
        or document.get("authorization_id") != AUTHORIZATION_ID
        or document.get("confirmation") != CONFIRMATION
        or document.get("r40_replay_permitted") is not False
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
    argv = ["r42-remote", mode, payload, *extra]
    program = (
        "import sys\n"
        + "sys.argv = "
        + repr(argv)
        + "\n"
        + REMOTE_SCRIPT
    )
    command = (
        "ssh",
        *transport._child_options(),
        transport.target,
        "python3 -B -",
    )
    completed = subprocess.run(
        command,
        input=program,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
        "remote_execute_invoked": False,
        "remote_execute_result_observed": False,
        "status_reconciliation_attempted": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "r40_replay": False,
        "target_image_load": False,
        "compose_binding_mutation": False,
        "service_mutation": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "u11_transition": False,
        "u12_plus": False,
        "u13_plus": False,
        "board_access": False,
        "merge": False,
    }

    transport = None
    return_code = 2
    r41 = load_r41()
    base = r41.load_r39().load_r37().load_base()

    try:
        manifest = read_manifest(args.expected_package_commit)
        if manifest["live_recovery_authorized"] is not True:
            raise Stop("r42_live_recovery_not_authorized")
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
                "live_recovery_authorized": manifest["live_recovery_authorized"],
                "authorization_state": manifest["authorization_state"],
                "r40_replay_permitted": manifest["r40_replay_permitted"],
                "state_root": manifest["state_root"],
                "r38_state_root": manifest["r38_state_root"],
                "r40_state_root": manifest["r40_state_root"],
                "r40_gate_id": manifest["r40"]["gate_id"],
                "r40_authorization_id": manifest["r40"]["authorization_id"],
                "r40_execution_id": manifest["r40"]["execution_id"],
                "r40_durable_reason": manifest["r40"]["durable_reason"],
                "mount_target": manifest["mount_target"],
                "installed_source_sha256": manifest["installed_source_sha256"],
                "derived_post_peak_reserve_bytes": manifest[
                    "internal_capacity_policy"
                ]["derived_post_peak_reserve_bytes"],
                "expected_target_runtime_image_id": manifest[
                    "expected_target_runtime_image_id"
                ],
                "source_repair_authority": manifest[
                    "source_repair_authority"
                ],
                "r41_mirror_sha256": manifest["r41"]["mirror_sha256"],
                "execution_id": args.execution_id,
            }
        )
        for prefix, source in (
            ("repaired_host", REPAIRED_HOST_SOURCE),
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
                    result["remote_returncode"] = status_transport.returncode
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
            "U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS",
            "U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS_RECONCILED",
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
