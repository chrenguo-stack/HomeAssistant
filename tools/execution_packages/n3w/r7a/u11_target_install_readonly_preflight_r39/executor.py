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
R37_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u10_predecessor_capacity_release_readonly_preflight_r37"
    / "executor.py"
)

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U11_TARGET_INSTALL_READONLY_PREFLIGHT_R39_20261116_01"
)
MANIFEST_SCHEMA = "gh.n3w-t1-u11-r39-readonly-preflight-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u11-r39-local-result/1"


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
    return load_module(R37_EXECUTOR, "n3w_r39_r37")


def r37_remote_library() -> str:
    remote = load_r37().REMOTE_SCRIPT
    marker = "raise SystemExit(main())"
    if marker not in remote:
        raise Stop("r37_remote_library_marker_missing")
    return remote.rsplit(marker, 1)[0]


REMOTE_SCRIPT = r37_remote_library() + r"""
def verify_transaction_u10(plan):
    product = import_product()
    transaction = read_object(TX)
    product["validate_transaction_document"](transaction)
    if (
        sha_file(TX) != plan["transaction_sha256"]
        or transaction.get("phase")
        != "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or transaction.get("current_image_ref")
        != plan["predecessor_image"]
        or transaction.get("target_image_ref") != plan["target_image"]
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
        or transaction.get("usb_filesystem_uuid") != plan["filesystem_uuid"]
        or transaction.get("authorization_claimed") is not True
        or transaction.get("authorization_consumed") is not True
        or transaction.get("authorization_id_sha256")
        != plan["authorization_id_sha256"]
    ):
        raise Stop("u11_r39_u10_transaction_invalid")
    return transaction


def verify_r38_ledger(plan):
    root = Path(plan["r38_state_root"])
    claim = read_object(root / "authorization_claim.json")
    success = read_object(root / "success.json")
    if (
        claim.get("gate_id") != plan["r38_gate_id"]
        or claim.get("authorization_id") != plan["r38_authorization_id"]
        or claim.get("execution_id") != plan["r38_execution_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or success.get("status")
        != "U10_R38_PREDECESSOR_CAPACITY_RELEASE_PASS"
        or success.get("authorization_claimed") is not True
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or success.get("predecessor_runtime_delete") is not True
        or success.get("predecessor_image_delete") is not True
        or success.get("target_image_load") is not False
        or success.get("service_mutation") is not False
        or success.get("u11_plus") is not False
        or success.get("transaction_phase")
        != "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
        or success.get("transaction_sha256") != plan["transaction_sha256"]
    ):
        raise Stop("u11_r39_r38_ledger_invalid")
    return {
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
    }


def verify_usb_mirror_u10(plan, transaction):
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
        raise Stop("u11_r39_usb_mirror_invalid")
    observed = {
        "manifest": sha_file(root / "manifest.json"),
        "phase": sha_file(root / "phase.json"),
        "content_authority": sha_file(root / "content-authority.json"),
        "checksums": sha_file(root / "checksums.json"),
    }
    if observed != plan["mirror_sha256"]:
        raise Stop("u11_r39_usb_mirror_hash_drift")
    return {"exact": True, "sha256": observed}


def verify_u11_runtime_prestate(plan):
    require_unit(HOST_UNIT, active=True)
    services_owner = require_unit(SERVICES_UNIT, active=False)
    require_unit(BROKER_UNIT, active=True)
    documents = all_container_documents()
    expected = plan["containers"]

    broker_id = expected["broker"]["container_id"]
    manager_id = expected["manager"]["container_id"]
    if broker_id not in documents or manager_id not in documents:
        raise Stop("u11_r39_peer_container_missing")

    for service, container_id in (
        ("broker", broker_id),
        ("manager", manager_id),
    ):
        item = documents[container_id]
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
            raise Stop("u11_r39_peer_identity_drift:" + service)

    if documents[broker_id]["State"].get("Status") != "running":
        raise Stop("u11_r39_broker_not_running")
    if documents[manager_id]["State"].get("Status") == "running":
        raise Stop("u11_r39_manager_not_quiesced")

    old_ha_id = expected["homeassistant"]["container_id"]
    if old_ha_id in documents:
        raise Stop("u11_r39_predecessor_container_still_present")

    ha_residue = []
    for container_id, item in documents.items():
        config = item.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            isinstance(labels, dict)
            and labels.get("com.docker.compose.project") == PROJECT
            and labels.get("com.docker.compose.service") == "homeassistant"
        ):
            ha_residue.append(container_id)
    if ha_residue:
        raise Stop("u11_r39_homeassistant_container_residue")

    if not image_absent(plan["predecessor_runtime_image_id"]):
        raise Stop("u11_r39_predecessor_runtime_image_present")
    if not image_absent(plan["predecessor_image"]):
        raise Stop("u11_r39_predecessor_image_present")
    if not image_absent(plan["target_image"]):
        raise Stop("u11_r39_target_image_present")
    if exact_predecessor_users(plan["predecessor_runtime_image_id"]):
        raise Stop("u11_r39_predecessor_still_referenced")

    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_host import LocalHost
    host = LocalHost()
    binding = host.component_binding_v2("homeassistant")
    if binding != plan["predecessor_image"]:
        raise Stop("u11_r39_compose_binding_drift")

    return {
        "services_owner_state": services_owner,
        "broker_running": True,
        "manager_quiesced": True,
        "homeassistant_container_absent": True,
        "predecessor_image_absent": True,
        "target_image_absent": True,
        "homeassistant_binding": binding,
        "manager_broker_preserved": True,
    }


def verify_internal_target_capacity(plan):
    completed = run(
        ["docker", "info", "--format", "{{.DockerRootDir}}"],
        timeout=45,
    )
    docker_root = completed.stdout.strip()
    if not docker_root.startswith("/"):
        raise Stop("u11_r39_docker_root_invalid")
    values = os.statvfs(docker_root)
    free_bytes = values.f_bavail * values.f_frsize
    required = (
        plan["target_import_worst_case_allowance_bytes"]
        + plan["derived_post_peak_reserve_bytes"]
    )
    if free_bytes < required:
        raise Stop("u11_r39_internal_capacity_insufficient")
    return {
        "docker_root": docker_root,
        "observed_free_bytes": free_bytes,
        "required_free_bytes": required,
        "capacity_pass": True,
    }


def run_readonly(plan):
    source_hashes = verify_installed_sources(plan)
    transaction = verify_transaction_u10(plan)
    r38 = verify_r38_ledger(plan)
    mount = require_bound_mount(plan)
    mirror = verify_usb_mirror_u10(plan, transaction)
    recovery = verify_recovery_assets_and_capacity(
        plan,
        transaction,
        import_product(),
    )
    runtime = verify_u11_runtime_prestate(plan)
    internal_capacity = verify_internal_target_capacity(plan)
    return {
        "schema": "gh.n3w-t1-u11-r39-readonly-preflight/1",
        "status": "U11_R39_READONLY_PREFLIGHT_PASS",
        "read_only": True,
        "source_hash_count": len(source_hashes),
        "transaction_phase": transaction["phase"],
        "transaction_sha256": sha_file(TX),
        "r38": r38,
        "mount": mount,
        "mirror": mirror,
        "recovery": recovery,
        "runtime": runtime,
        "internal_capacity": internal_capacity,
        "u11_readonly_eligible": True,
        "u11_live_execution_authorized": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "target_image_load": False,
        "compose_binding_mutation": False,
        "service_mutation": False,
        "u11_transition": False,
        "u12_plus": False,
        "board_access": False,
        "merge": False,
    }


def main():
    try:
        mode = sys.argv[1]
        plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U11_TARGET_INSTALL_READONLY_PREFLIGHT_R39_20261116_01"
        ):
            raise Stop("gate_id_invalid")
        if mode != "preflight":
            raise Stop("mode_invalid")
        result = run_readonly(plan)
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-u11-r39-readonly-preflight/1",
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "read_only": True,
            "u11_readonly_eligible": False,
            "u11_live_execution_authorized": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "target_image_load": False,
            "compose_binding_mutation": False,
            "service_mutation": False,
            "u11_transition": False,
            "u12_plus": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "U11_R39_READONLY_PREFLIGHT_PASS" else 2


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
    readonly_authorized = document.get(
        "real_t1_readonly_execution_authorized"
    )
    if (
        document.get("schema") != MANIFEST_SCHEMA
        or document.get("gate_id") != GATE_ID
        or document.get("read_only_preflight") is not True
        or type(readonly_authorized) is not bool
        or document.get("live_execution_authorized") is not False
        or document.get("authorization_state")
        != {
            "granted": readonly_authorized,
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


def remote_mode(transport, plan, *, timeout=1200):
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
        "target_image_load": False,
        "compose_binding_mutation": False,
        "service_mutation": False,
        "u11_transition": False,
        "u12_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    r37 = load_r37()
    base = r37.load_base()

    try:
        manifest = read_manifest(args.expected_package_commit)
        if manifest["real_t1_readonly_execution_authorized"] is not True:
            raise Stop("r39_real_t1_readonly_execution_not_authorized")
        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_u10_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "r38_state_root": manifest["r38_state_root"],
                "mount_target": manifest["mount_target"],
                "installed_source_sha256": manifest["installed_source_sha256"],
                "target_import_worst_case_allowance_bytes": manifest[
                    "internal_capacity_policy"
                ]["target_import_worst_case_allowance_bytes"],
                "derived_post_peak_reserve_bytes": manifest[
                    "internal_capacity_policy"
                ]["derived_post_peak_reserve_bytes"],
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
        completed, remote = remote_mode(transport, plan)
        result["remote_returncode"] = completed.returncode
        result.update(remote)
        base.write_remote_evidence(
            evidence,
            "r39_preflight_remote",
            completed,
        )
        base.write_private_json(
            evidence / "r39_preflight.json",
            remote,
        )
        return_code = (
            0
            if completed.returncode == 0
            and remote.get("status") == "U11_R39_READONLY_PREFLIGHT_PASS"
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
