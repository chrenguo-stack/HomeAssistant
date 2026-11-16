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
REPAIRED_HOST_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_host.py"
REPAIRED_U11_HOST_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_ha_u11_host.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U11_POST_R40_SUCCESSOR_READONLY_PREFLIGHT_R41_20261116_01"
)
MANIFEST_SCHEMA = "gh.n3w-t1-u11-r41-post-r40-readonly-preflight-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u11-r41-post-r40-local-result/1"


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
    return load_module(R39_EXECUTOR, "n3w_r41_r39")


def r39_remote_library() -> str:
    remote = load_r39().REMOTE_SCRIPT
    marker = "raise SystemExit(main())"
    if marker not in remote:
        raise Stop("r39_remote_library_marker_missing")
    return remote.rsplit(marker, 1)[0]


REMOTE_SCRIPT = r39_remote_library() + r"""
def verify_r40_consumed_failure(plan):
    root = Path(plan["r40_state_root"])
    claim = read_object(root / "authorization_claim.json")
    failure = read_object(root / "failure.json")
    if (
        claim.get("schema") != "gh.n3w-t1-u11-r40-authorization-claim/1"
        or claim.get("gate_id") != plan["r40_gate_id"]
        or claim.get("authorization_id") != plan["r40_authorization_id"]
        or claim.get("execution_id") != plan["r40_execution_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or failure.get("status") != "STOP_POSTCLAIM"
        or failure.get("authorization_claimed") is not True
        or failure.get("authorization_consumed") is not True
        or failure.get("replay_permitted") is not False
        or failure.get("recovery_required") is not True
        or failure.get("reason")
        != "UpdaterError:services_supervision_contract_drift"
        or failure.get("target_image_load") is not True
        or failure.get("compose_binding_mutation") is not True
        or failure.get("service_mutation") is not False
        or failure.get("transaction_mutation") is not False
        or failure.get("usb_mutation") is not False
        or failure.get("u11_transition") is not False
        or failure.get("observed_transaction_phase")
        != "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
        or failure.get("observed_usb_phase")
        != "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
        or failure.get("observed_homeassistant_binding")
        != plan["target_image"]
        or failure.get("observed_services_owner_state") != "failed"
        or failure.get("observed_manager_running_count") != 0
        or failure.get("observed_homeassistant_running_count") != 0
    ):
        raise Stop("u11_r41_r40_consumed_failure_ledger_invalid")
    return {
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
        "status": "STOP_POSTCLAIM",
        "reason": "services_supervision_contract_drift",
    }


def verify_partial_u10_runtime(plan, transaction):
    require_unit(HOST_UNIT, active=True)
    services_owner = require_unit(SERVICES_UNIT, active=False)
    if services_owner != "failed":
        raise Stop("u11_r41_services_owner_not_exact_failed")
    require_unit(BROKER_UNIT, active=True)
    documents = all_container_documents()
    expected = plan["containers"]

    broker_id = expected["broker"]["container_id"]
    manager_id = expected["manager"]["container_id"]
    if broker_id not in documents or manager_id not in documents:
        raise Stop("u11_r41_peer_container_missing")

    for service, container_id in (("broker", broker_id), ("manager", manager_id)):
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
            raise Stop("u11_r41_peer_identity_drift:" + service)

    if documents[broker_id]["State"].get("Status") != "running":
        raise Stop("u11_r41_broker_not_running")
    if documents[manager_id]["State"].get("Status") != "exited":
        raise Stop("u11_r41_manager_not_exactly_exited")

    ha_residue = []
    target_users = []
    for container_id, item in documents.items():
        config = item.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            isinstance(labels, dict)
            and labels.get("com.docker.compose.project") == PROJECT
            and labels.get("com.docker.compose.service") == "homeassistant"
        ):
            ha_residue.append(container_id)
        if item.get("Image") == plan["expected_target_runtime_image_id"]:
            target_users.append(container_id)
    if ha_residue:
        raise Stop("u11_r41_unexpected_homeassistant_container_residue")
    if target_users:
        raise Stop("u11_r41_target_image_container_residue")

    if not image_absent(plan["predecessor_runtime_image_id"]):
        raise Stop("u11_r41_predecessor_runtime_image_present")
    if not image_absent(plan["predecessor_image"]):
        raise Stop("u11_r41_predecessor_image_present")

    target_probe = run(
        ["docker", "image", "inspect", plan["target_image"]],
        timeout=45,
        check=False,
    )
    if target_probe.returncode != 0:
        raise Stop("u11_r41_target_image_missing")
    try:
        target_doc = json.loads(target_probe.stdout)
    except Exception as error:
        raise Stop("u11_r41_target_image_invalid") from error
    if (
        not isinstance(target_doc, list)
        or len(target_doc) != 1
        or target_doc[0].get("Id") != plan["expected_target_runtime_image_id"]
    ):
        raise Stop("u11_r41_target_runtime_identity_drift")

    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_host import LocalHost

    host = LocalHost()
    binding = host.component_binding_v2("homeassistant")
    if binding != plan["target_image"]:
        raise Stop("u11_r41_target_binding_drift")

    from n3w_t1_portable_image_identity import (
        parse_image_archive,
        verify_docker_image,
    )
    from n3w_t1_core_updater_v2_common import canonical, sha256_bytes

    target_archive = (
        Path(plan["mount_target"])
        / "n3w-update"
        / "target"
        / "homeassistant-arm64.tar.gz"
    )
    identity = parse_image_archive(
        target_archive,
        expected_archive_sha256=plan["target_archive_sha256"],
        expected_archive_size_bytes=plan["target_archive_size_bytes"],
        expected_tag=plan["target_image"],
        platform_os="linux",
        platform_architecture="arm64",
    )
    portable_sha256 = sha256_bytes(canonical(identity.to_dict()))
    target_record = transaction.get("target_artifact_identity")
    if (
        not isinstance(target_record, dict)
        or target_record.get("portable_identity_sha256") != portable_sha256
    ):
        raise Stop("u11_r41_target_portable_identity_drift")
    verdict = verify_docker_image(identity, plan["target_image"])
    if (
        verdict.status != "VERIFIED"
        or verdict.runtime_image_id != plan["expected_target_runtime_image_id"]
    ):
        raise Stop("u11_r41_target_runtime_portable_mismatch")

    return {
        "services_owner_state": services_owner,
        "broker_running": True,
        "manager_quiesced": True,
        "homeassistant_container_absent": True,
        "predecessor_image_absent": True,
        "target_image_present": True,
        "target_runtime_image_id": verdict.runtime_image_id,
        "target_portable_identity_sha256": portable_sha256,
        "homeassistant_binding": binding,
        "manager_broker_preserved": True,
    }


def verify_repaired_supervision_contract(plan):
    types = __import__("types")
    host_raw = base64.b64decode(plan["repaired_host_source_b64"])
    u11_host_raw = base64.b64decode(plan["repaired_u11_host_source_b64"])
    if (
        hashlib.sha256(host_raw).hexdigest()
        != plan["repaired_host_source_sha256"]
        or hashlib.sha256(u11_host_raw).hexdigest()
        != plan["repaired_u11_host_source_sha256"]
    ):
        raise Stop("u11_r41_repaired_source_payload_hash_drift")

    names = ("n3w_t1_core_updater_host", "n3w_t1_core_updater_ha_u11_host")
    previous = {name: sys.modules.get(name) for name in names}
    try:
        host_module = types.ModuleType(names[0])
        host_module.__file__ = "<memory:n3w_t1_core_updater_host.py>"
        sys.modules[names[0]] = host_module
        exec(
            compile(
                host_raw.decode("utf-8"),
                host_module.__file__,
                "exec",
            ),
            host_module.__dict__,
        )

        u11_host_module = types.ModuleType(names[1])
        u11_host_module.__file__ = "<memory:n3w_t1_core_updater_ha_u11_host.py>"
        sys.modules[names[1]] = u11_host_module
        exec(
            compile(
                u11_host_raw.decode("utf-8"),
                u11_host_module.__file__,
                "exec",
            ),
            u11_host_module.__dict__,
        )

        host = host_module.LocalHost()
        host._activation_env()
        unit = host._service_unit(
            expected_execstart=u11_host_module.EXPECTED_U11_EXECSTART,
            expected_execstop=u11_host_module.EXPECTED_U11_EXECSTOP,
        )
        return {
            "repair_source_authority": plan["source_repair_authority"],
            "host_source_sha256": plan["repaired_host_source_sha256"],
            "u11_host_source_sha256": plan["repaired_u11_host_source_sha256"],
            "execstart_sha256": unit["execstart_sha256"],
            "execstop_sha256": unit["execstop_sha256"],
            "effective_contract": "EXACT_HA_OTA_OVERLAY",
        }
    finally:
        for name in names:
            prior = previous[name]
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior


def verify_postload_internal_reserve(plan):
    completed = run(
        ["docker", "info", "--format", "{{.DockerRootDir}}"],
        timeout=45,
    )
    docker_root = completed.stdout.strip()
    if not docker_root.startswith("/"):
        raise Stop("u11_r41_docker_root_invalid")
    values = os.statvfs(docker_root)
    free_bytes = values.f_bavail * values.f_frsize
    required = plan["derived_post_peak_reserve_bytes"]
    if free_bytes < required:
        raise Stop("u11_r41_postload_internal_reserve_insufficient")
    return {
        "docker_root": docker_root,
        "observed_free_bytes": free_bytes,
        "required_free_bytes": required,
        "capacity_pass": True,
        "capacity_mode": "POST_TARGET_LOAD_RESERVE_ONLY",
    }


def run_successor_readonly(plan):
    source_hashes = verify_installed_sources(plan)
    transaction = verify_transaction_u10(plan)
    r38 = verify_r38_ledger(plan)
    r40 = verify_r40_consumed_failure(plan)
    mount = require_bound_mount(plan)
    mirror = verify_usb_mirror_u10(plan, transaction)
    recovery = verify_recovery_assets_and_capacity(
        plan,
        transaction,
        import_product(),
    )
    runtime = verify_partial_u10_runtime(plan, transaction)
    supervision = verify_repaired_supervision_contract(plan)
    internal_reserve = verify_postload_internal_reserve(plan)
    return {
        "schema": "gh.n3w-t1-u11-r41-post-r40-readonly-preflight/1",
        "status": "U11_R41_POST_R40_READONLY_PREFLIGHT_PASS",
        "read_only": True,
        "source_hash_count": len(source_hashes),
        "installed_repaired_source_required": False,
        "transaction_phase": transaction["phase"],
        "transaction_sha256": sha_file(TX),
        "r38": r38,
        "r40": r40,
        "mount": mount,
        "mirror": mirror,
        "recovery": recovery,
        "runtime": runtime,
        "supervision": supervision,
        "internal_reserve": internal_reserve,
        "successor_live_recovery_eligible": True,
        "successor_live_recovery_authorized": False,
        "r40_replay": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "target_image_load": False,
        "compose_binding_mutation": False,
        "service_mutation": False,
        "u11_transition": False,
        "u12_plus": False,
        "u13_plus": False,
        "board_access": False,
        "merge": False,
    }


def main():
    try:
        mode = sys.argv[1]
        plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U11_POST_R40_SUCCESSOR_READONLY_PREFLIGHT_R41_20261116_01"
        ):
            raise Stop("gate_id_invalid")
        if mode != "preflight":
            raise Stop("mode_invalid")
        result = run_successor_readonly(plan)
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-u11-r41-post-r40-readonly-preflight/1",
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "read_only": True,
            "successor_live_recovery_eligible": False,
            "successor_live_recovery_authorized": False,
            "r40_replay": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "target_image_load": False,
            "compose_binding_mutation": False,
            "service_mutation": False,
            "u11_transition": False,
            "u12_plus": False,
            "u13_plus": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result.get("status")
        == "U11_R41_POST_R40_READONLY_PREFLIGHT_PASS"
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
    readonly_authorized = document.get(
        "real_t1_readonly_execution_authorized"
    )
    if (
        document.get("schema") != MANIFEST_SCHEMA
        or document.get("gate_id") != GATE_ID
        or document.get("read_only_preflight") is not True
        or type(readonly_authorized) is not bool
        or document.get("live_recovery_authorized") is not False
        or document.get("r40_replay_permitted") is not False
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


def remote_mode(transport, plan, *, timeout=1800):
    payload = base64.b64encode(
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
        "successor_live_recovery_eligible": False,
        "successor_live_recovery_authorized": False,
        "r40_replay": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "target_image_load": False,
        "compose_binding_mutation": False,
        "service_mutation": False,
        "u11_transition": False,
        "u12_plus": False,
        "u13_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    r39 = load_r39()
    base = r39.load_r37().load_base()

    try:
        manifest = read_manifest(args.expected_package_commit)
        if manifest["real_t1_readonly_execution_authorized"] is not True:
            raise Stop("r41_real_t1_readonly_execution_not_authorized")
        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_u10_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "r38_state_root": manifest["r38_state_root"],
                "r40_state_root": manifest["r40_state_root"],
                "r40_gate_id": manifest["r40"]["gate_id"],
                "r40_authorization_id": manifest["r40"]["authorization_id"],
                "r40_execution_id": manifest["r40"]["execution_id"],
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
                "execution_id": args.execution_id,
            }
        )
        for prefix, source in (
            ("repaired_host", REPAIRED_HOST_SOURCE),
            ("repaired_u11_host", REPAIRED_U11_HOST_SOURCE),
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
        result["remote_preflight_invoked"] = True
        completed, remote = remote_mode(transport, plan)
        result["remote_returncode"] = completed.returncode
        result.update(remote)
        base.write_remote_evidence(
            evidence,
            "r41_preflight_remote",
            completed,
        )
        base.write_private_json(
            evidence / "r41_preflight.json",
            remote,
        )
        return_code = (
            0
            if completed.returncode == 0
            and remote.get("status")
            == "U11_R41_POST_R40_READONLY_PREFLIGHT_PASS"
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
