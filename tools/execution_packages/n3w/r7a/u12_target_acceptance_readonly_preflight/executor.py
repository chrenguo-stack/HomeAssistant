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
    "U12_TARGET_ACCEPTANCE_READONLY_PREFLIGHT_20261117_01"
)
MANIFEST_SCHEMA = "gh.n3w-t1-u12-readonly-preflight-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u12-readonly-preflight-local-result/1"


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
    return load_module(R37_EXECUTOR, "n3w_u12_r37")


def r37_remote_library() -> str:
    remote = load_r37().REMOTE_SCRIPT
    marker = "raise SystemExit(main())"
    if marker not in remote:
        raise Stop("r37_remote_library_marker_missing")
    return remote.rsplit(marker, 1)[0]


REMOTE_SCRIPT = r37_remote_library() + r"""
import http.client
import time

EXPECTED_LISTENERS = {
    "tcp_8883": 1,
    "tcp_47110": 1,
    "udp_47111": 1,
    "tcp_47112": 0,
}
MQTT_IDENTITY_FILES = {
    "manager": Path("/opt/greenhouse-secrets/mqtt/manager/runtime.env"),
    "homeassistant": Path(
        "/opt/greenhouse-secrets/mqtt/homeassistant/mqtt-bootstrap.json"
    ),
}
PRODUCTION_HA_CONFIG = "/var/lib/n3wfc4-homeassistant"


def elapsed_ms(start_ns):
    return max(0, (time.monotonic_ns() - start_ns) // 1_000_000)


def verify_transaction_u11(plan):
    product = import_product()
    transaction = read_object(TX)
    product["validate_transaction_document"](transaction)
    if (
        sha_file(TX) != plan["transaction_sha256"]
        or transaction.get("phase") != "U11_TARGET_INSTALLED_STARTED"
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
    ):
        raise Stop("u12_preflight_u11_transaction_invalid")
    return transaction


def verify_r42_ledger(plan):
    root = Path(plan["r42_state_root"])
    claim_path = root / "authorization_claim.json"
    success_path = root / "success.json"
    failure_path = root / "failure.json"
    if failure_path.exists() or failure_path.is_symlink():
        raise Stop("u12_preflight_r42_failure_ledger_present")
    claim = read_object(claim_path)
    success = read_object(success_path)
    if (
        sha_file(claim_path) != plan["r42_claim_sha256"]
        or sha_file(success_path) != plan["r42_success_sha256"]
        or claim.get("gate_id") != plan["r42_gate_id"]
        or claim.get("authorization_id") != plan["r42_authorization_id"]
        or claim.get("execution_id") != plan["r42_execution_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or success.get("status")
        != "U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS"
        or success.get("authorization_claimed") is not True
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or success.get("u12_plus") is not False
        or success.get("u13_plus") is not False
    ):
        raise Stop("u12_preflight_r42_ledger_invalid")
    return {
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
        "success_sha256": plan["r42_success_sha256"],
        "failure_ledger_present": False,
    }


def verify_usb_mirror_u11(plan, transaction):
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
        or phase.get("phase") != "U11_TARGET_INSTALLED_STARTED"
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
        raise Stop("u12_preflight_usb_mirror_invalid")
    observed = {
        "manifest": sha_file(manifest_path),
        "phase": sha_file(phase_path),
        "content_authority": sha_file(authority_path),
        "checksums": sha_file(checksums_path),
    }
    if observed != plan["mirror_sha256"]:
        raise Stop("u12_preflight_usb_mirror_hash_drift")
    return {"exact": True, "sha256": observed}


def verify_runtime_u11(plan):
    require_unit(HOST_UNIT, active=True)
    require_unit(BROKER_UNIT, active=True)
    require_unit(SERVICES_UNIT, active=True)
    documents = all_container_documents()
    expected = plan["containers"]

    for service in ("broker", "manager"):
        item = documents.get(expected[service]["container_id"])
        if item is None:
            raise Stop("u12_preflight_peer_container_missing:" + service)
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
            raise Stop("u12_preflight_peer_identity_drift:" + service)

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
        raise Stop("u12_preflight_homeassistant_runtime_count_invalid")
    ha = homeassistant[0]
    if (
        ha["Config"].get("Image") != plan["target_image"]
        or ha.get("Image") != plan["target_runtime_image_id"]
        or ha.get("RestartCount") != 0
    ):
        raise Stop("u12_preflight_homeassistant_identity_drift")
    mounts = ha.get("Mounts")
    if not isinstance(mounts, list):
        raise Stop("u12_preflight_homeassistant_mounts_invalid")
    matches = [
        row
        for row in mounts
        if isinstance(row, dict)
        and row.get("Type") == "bind"
        and row.get("Source") == PRODUCTION_HA_CONFIG
        and row.get("Destination") == "/config"
        and row.get("RW") is True
    ]
    if len(matches) != 1:
        raise Stop("u12_preflight_production_config_missing")
    return {
        "owner_active": True,
        "broker_running": True,
        "manager_running": True,
        "homeassistant_running": True,
        "target_runtime_image_id": plan["target_runtime_image_id"],
        "production_config_mounted": True,
    }


def listener_count(protocol, port):
    flag = "-ltn" if protocol == "tcp" else "-lun"
    completed = run(
        ["ss", "-H", flag, "sport", "=", ":" + str(port)],
        timeout=20,
    )
    return len([line for line in completed.stdout.splitlines() if line.strip()])


def listener_snapshot():
    return {
        "tcp_8883": listener_count("tcp", 8883),
        "tcp_47110": listener_count("tcp", 47110),
        "udp_47111": listener_count("udp", 47111),
        "tcp_47112": listener_count("tcp", 47112),
    }


def mqtt_identity(service):
    path = MQTT_IDENTITY_FILES[service]
    if path.is_symlink() or not path.is_file():
        raise Stop("u12_preflight_mqtt_identity_invalid:" + service)
    raw = path.read_text(encoding="utf-8")
    if service == "manager":
        values = {}
        for line in raw.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in {"GH_MQTT_CLIENT_ID", "GH_MQTT_USERNAME"}:
                if key in values:
                    raise Stop("u12_preflight_manager_identity_duplicate")
                values[key] = value
        client_id = values.get("GH_MQTT_CLIENT_ID")
        username = values.get("GH_MQTT_USERNAME")
    else:
        try:
            value = json.loads(raw)
        except Exception as error:
            raise Stop("u12_preflight_homeassistant_identity_invalid") from error
        if not isinstance(value, dict):
            raise Stop("u12_preflight_homeassistant_identity_invalid")
        client_id = value.get("client_id")
        username = value.get("username")
    if not all(
        isinstance(item, str)
        and re.fullmatch(r"[A-Za-z0-9_.:-]+", item)
        for item in (client_id, username)
    ):
        raise Stop("u12_preflight_mqtt_identity_invalid:" + service)
    return client_id, username


def mqtt_authenticated(service, broker):
    client_id, username = mqtt_identity(service)
    completed = run(
        [
            "docker",
            "logs",
            "--timestamps",
            "--since",
            broker["State"]["StartedAt"],
            "--tail",
            "10000",
            broker["Id"],
        ],
        timeout=30,
    )
    lines = (completed.stdout + completed.stderr).splitlines()
    if len(lines) >= 10000:
        raise Stop("u12_preflight_broker_log_coverage_insufficient")
    connected = re.compile(
        r"New client connected from .+ as "
        + re.escape(client_id)
        + r" \(p5, c[01], k[0-9]+, u'"
        + re.escape(username)
        + r"'\)\."
    )
    any_connection = re.compile(
        r"New client connected from .+ as "
        + re.escape(client_id)
        + r" \("
    )
    terminal = re.compile(
        r"(?:Client|client) "
        + re.escape(client_id)
        + r"(?: \[[^\]\r\n]+\] disconnected(?:\.|:)"
        + r"| disconnected\b| closed its connection\b"
        + r"| already connected, closing old connection\b"
        + r"| has exceeded timeout, disconnecting\b)"
    )
    current = False
    for line in lines:
        if any_connection.search(line):
            if connected.search(line) is None:
                raise Stop(
                    "u12_preflight_mqtt_identity_mismatch:" + service
                )
            current = True
            continue
        if terminal.search(line):
            current = False
    return current


def homeassistant_http_status():
    connection = http.client.HTTPConnection("127.0.0.1", 8123, timeout=5)
    try:
        connection.request("GET", "/api/")
        response = connection.getresponse()
        response.read(1024)
        return int(response.status)
    except (OSError, http.client.HTTPException) as error:
        raise Stop("u12_preflight_homeassistant_http_unavailable") from error
    finally:
        connection.close()


def observe_acceptance_readiness(plan):
    timings = {}

    started = time.monotonic_ns()
    listeners = listener_snapshot()
    timings["broker_listener_readiness_ms"] = elapsed_ms(started)
    if listeners != EXPECTED_LISTENERS:
        raise Stop("u12_preflight_listener_contract_drift")

    documents = all_container_documents()
    broker = documents.get(plan["containers"]["broker"]["container_id"])
    if not isinstance(broker, dict):
        raise Stop("u12_preflight_broker_runtime_missing")

    started = time.monotonic_ns()
    authenticated = {
        service: mqtt_authenticated(service, broker)
        for service in ("manager", "homeassistant")
    }
    timings["mqtt_acceptance_observation_ms"] = elapsed_ms(started)
    if authenticated != {"manager": True, "homeassistant": True}:
        raise Stop("u12_preflight_mqtt_current_authentication_missing")

    started = time.monotonic_ns()
    http_status = homeassistant_http_status()
    timings["homeassistant_readiness_observation_ms"] = elapsed_ms(started)
    if http_status not in {200, 401}:
        raise Stop("u12_preflight_homeassistant_http_not_ready")

    return {
        "listeners": listeners,
        "mqtt_authenticated": authenticated,
        "homeassistant_http_status": http_status,
        "timings_ms": timings,
    }


def run_readonly(plan):
    total_started = time.monotonic_ns()
    state_root = Path(plan["u12_state_root"])
    if state_root.exists() or state_root.is_symlink():
        raise Stop("u12_preflight_state_root_already_exists")

    step_started = time.monotonic_ns()
    source_hashes = verify_installed_sources(plan)
    source_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    transaction = verify_transaction_u11(plan)
    transaction_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    r42 = verify_r42_ledger(plan)
    r42_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    mount = require_bound_mount(plan)
    mirror = verify_usb_mirror_u11(plan, transaction)
    mirror_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    runtime = verify_runtime_u11(plan)
    runtime_ms = elapsed_ms(step_started)

    step_started = time.monotonic_ns()
    readiness = observe_acceptance_readiness(plan)
    readiness_ms = elapsed_ms(step_started)

    return {
        "schema": "gh.n3w-t1-u12-readonly-preflight/1",
        "status": "U12_READONLY_PREFLIGHT_PASS",
        "read_only": True,
        "transaction_phase": transaction["phase"],
        "transaction_sha256": sha_file(TX),
        "r42": r42,
        "mount": mount,
        "mirror": mirror,
        "runtime": runtime,
        "readiness": readiness,
        "timings_ms": {
            "installed_source_verification_ms": source_ms,
            "transaction_verification_ms": transaction_ms,
            "r42_ledger_verification_ms": r42_ms,
            "usb_mirror_verification_ms": mirror_ms,
            "runtime_identity_verification_ms": runtime_ms,
            "acceptance_readiness_observation_ms": readiness_ms,
            "preflight_total_ms": elapsed_ms(total_started),
        },
        "source_hash_count": len(source_hashes),
        "u11_durable_pass": True,
        "u12_readonly_eligible": True,
        "u12_acceptance": False,
        "u12_live_execution_authorized": False,
        "normal_ota_baseline_available": False,
        "performance_instrumentation_design_only": True,
        "r42_replay": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "u12_transition": False,
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
            "U12_TARGET_ACCEPTANCE_READONLY_PREFLIGHT_20261117_01"
        ):
            raise Stop("gate_id_invalid")
        if mode != "preflight":
            raise Stop("mode_invalid")
        result = run_readonly(plan)
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-u12-readonly-preflight/1",
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "read_only": True,
            "u11_durable_pass": False,
            "u12_readonly_eligible": False,
            "u12_acceptance": False,
            "u12_live_execution_authorized": False,
            "normal_ota_baseline_available": False,
            "r42_replay": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "service_mutation": False,
            "u12_transition": False,
            "u13_plus": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "U12_READONLY_PREFLIGHT_PASS" else 2


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
        or readonly_authorized is not True
        or document.get("u12_live_execution_authorized") is not False
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


def remote_mode(transport, plan, *, timeout=600):
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
        "u12_transition": False,
        "u13_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    r37 = load_r37()
    base = r37.load_base()

    try:
        manifest = read_manifest(args.expected_package_commit)
        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_u11_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "r42_state_root": manifest["r42"]["state_root"],
                "r42_gate_id": manifest["r42"]["gate_id"],
                "r42_authorization_id": manifest["r42"]["authorization_id"],
                "r42_execution_id": manifest["r42"]["execution_id"],
                "r42_claim_sha256": manifest["r42"]["claim_sha256"],
                "r42_success_sha256": manifest["r42"]["success_sha256"],
                "mount_target": manifest["mount_target"],
                "u12_state_root": manifest["u12_state_root"],
                "installed_source_sha256": manifest[
                    "installed_source_sha256"
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
        completed, remote = remote_mode(transport, plan)
        result["remote_returncode"] = completed.returncode
        result.update(remote)
        base.write_remote_evidence(
            evidence,
            "u12_preflight_remote",
            completed,
        )
        base.write_private_json(
            evidence / "u12_preflight.json",
            remote,
        )
        return_code = (
            0
            if completed.returncode == 0
            and remote.get("status") == "U12_READONLY_PREFLIGHT_PASS"
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
