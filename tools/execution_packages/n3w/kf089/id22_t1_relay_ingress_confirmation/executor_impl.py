#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
ID21_IMPL_PATH = PACKAGE_DIR.parent / "id21_schema5_two_board_relay_validation" / "executor_impl.py"
ID21_IMPL_GIT_BLOB = "b0ad0eff061d2e6a2455fd00681aee9e30009642"
ID21_EXECUTION_PACKAGE_COMMIT = "9ebe5968e2f06f23a657abbeeb68c4094b445a66"
MANAGER_SERVICE_PATH = Path("host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_isolated_mqtt_service.py")
MANAGER_SERVICE_GIT_BLOB = "2a478300e66bed341f55b44e629c24847128f413"
SCHEMA5_SOURCE_COMMIT = "5d58727f5040281ee2beb9597f66a6a2da9bac57"
SCHEMA5_FIRMWARE_SHA256 = "5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b"
EXPECTED_SELECTED_SLOT = 0
EXPECTED_ACTIVE_SEQ = 5
EXPECTED_ACTIVE_STATE = 2
EXPECTED_SCHEMA_VERSION = 5
MIN_RELAY_STAGING_SECONDS = 45
MIN_RELAY_WINDOW_SECONDS = 180
TOKEN_PRECLAIM = "T1_AND_BOTH_BOARDS_PRECLAIM_READY"
TOKEN_STAGING = "ID22_RELAY_STAGING_DIRECT_COMPLETE"
TOKEN_RELAY_COMPLETE = "ID22_RELAY_WINDOW_COMPLETE_AND_BOTH_ROM_READY"
ACCEPTED_RELAY_RE = re.compile(r"Accepted simplified N3-W telemetry source=relay\b")
REJECTED_RELAY_RE = re.compile(r"Rejected simplified N3-W ingress source=relay\b")
SUBSCRIPTION_RE = re.compile(r"Subscribed to gh/v1/.+/ingress/gateway/\+/\+/frame")


def _load_id21():
    spec = importlib.util.spec_from_file_location("id22_id21_common", ID21_IMPL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("ID21 implementation could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


id21 = _load_id21()
id18 = id21.id18
StopExecution = id21.StopExecution


def load_manifest() -> dict[str, Any]:
    value = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    if value.get("package_schema_version") != 1:
        raise StopExecution("manifest package schema version mismatch")
    if value.get("gate_id") != "id22_t1_relay_ingress_confirmation":
        raise StopExecution("manifest gate id mismatch")
    return value


def write_authorization(root: Path, auth: str, execution_id: str, *, claimed: bool) -> None:
    value: dict[str, Any] = {
        "authorization_id": auth,
        "execution_id": execution_id,
        "claimed": claimed,
        "consumed": claimed,
        "replay_permitted": False,
    }
    if claimed:
        now = id18.utc_now()
        value.update(
            {
                "claim_boundary": "immediately_before_t1_readonly_preclaim",
                "claimed_at": now,
                "consumed_at": now,
            }
        )
    id18.write_json(root / "authorization.json", value)


def run_recorded(*, root: Path, index: int, label: str, argv: list[str], cwd: Path, target_operation: bool = False, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return id18.run_recorded(
        root=root,
        index=index,
        label=label,
        argv=argv,
        cwd=cwd,
        target_operation=target_operation,
        extra_env=extra_env,
    )


def verify_host(root: Path, repo_root: Path, expected_commit: str) -> int:
    index = 1
    checks = (
        ("host_git_head", ["git", "rev-parse", "HEAD"], expected_commit),
        ("host_git_status", ["git", "status", "--porcelain", "--untracked-files=no"], ""),
        ("id21_impl_blob", ["git", "hash-object", str(ID21_IMPL_PATH.relative_to(repo_root))], ID21_IMPL_GIT_BLOB),
        ("manager_service_blob", ["git", "hash-object", str(MANAGER_SERVICE_PATH)], MANAGER_SERVICE_GIT_BLOB),
    )
    for label, argv, expected in checks:
        result = run_recorded(root=root, index=index, label=label, argv=argv, cwd=repo_root)
        if result.returncode != 0 or (result.stdout or "").strip() != expected:
            raise StopExecution(f"{label} binding failed")
        index += 1
    result = run_recorded(
        root=root,
        index=index,
        label="host_esptool_version",
        argv=[sys.executable, "-m", "esptool", "version"],
        cwd=repo_root,
    )
    versions = id18.VERSION_RE.findall((result.stdout or "") + "\n" + (result.stderr or ""))
    if result.returncode != 0 or id18.EXPECTED_ESPTOOL_VERSION not in versions:
        raise StopExecution("esptool version preflight failed")
    index += 1
    if shutil.which("ssh") is None:
        raise StopExecution("ssh executable not found")
    result = run_recorded(root=root, index=index, label="host_ssh_version", argv=["ssh", "-V"], cwd=repo_root)
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0 or "OpenSSH" not in combined:
        raise StopExecution("OpenSSH host preflight failed")
    return index + 1


def operator_interlock(root: Path, *, name: str, token: str, minimum_seconds: int, instructions: str) -> float:
    print(f"\nID22 OPERATOR INTERLOCK: {name}\n{instructions}", file=sys.stderr, flush=True)
    started = time.monotonic()
    started_utc = id18.utc_now()
    observed = input(f"ID22 token [{token}]: ").strip()
    elapsed = time.monotonic() - started
    matched = observed == token
    id18.write_json(
        root / f"operator_interlock_{name.lower()}.json",
        {
            "name": name,
            "required_token": token,
            "token_match": matched,
            "minimum_elapsed_seconds": minimum_seconds,
            "observed_elapsed_seconds": elapsed,
            "started_at": started_utc,
            "confirmed_at": id18.utc_now(),
        },
    )
    if not matched:
        raise StopExecution(f"operator interlock token mismatch: {name}")
    if elapsed < minimum_seconds:
        raise StopExecution(f"operator interlock elapsed time below minimum: {name}")
    return elapsed


def interlock_completed(root: Path, name: str) -> bool:
    path = root / f"operator_interlock_{name.lower()}.json"
    if not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        elapsed = float(value.get("observed_elapsed_seconds", -1))
        minimum = float(value.get("minimum_elapsed_seconds", -1))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False
    return value.get("token_match") is True and elapsed >= minimum >= 0


def ssh_argv(target: str, remote_argv: list[str]) -> list[str]:
    remote_command = shlex.join(remote_argv)
    return [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=1",
        target,
        remote_command,
    ]


def run_ssh(*, root: Path, index: int, label: str, target: str, remote_argv: list[str], cwd: Path) -> tuple[int, subprocess.CompletedProcess[str]]:
    result = run_recorded(
        root=root,
        index=index,
        label=label,
        argv=ssh_argv(target, remote_argv),
        cwd=cwd,
        target_operation=False,
    )
    if result.returncode != 0:
        raise StopExecution(f"{label}: SSH/read-only command failed")
    return index + 1, result


def parse_container_inspect(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) != 8:
            raise StopExecution("T1 container inspect row shape mismatch")
        cid, name_raw, image_raw, labels_raw, running_raw, restart_raw, network_raw, ports_raw = parts
        try:
            labels = json.loads(labels_raw)
            ports = json.loads(ports_raw)
            row = {
                "id": cid,
                "name": json.loads(name_raw),
                "image": json.loads(image_raw),
                "labels": labels or {},
                "running": running_raw.strip().lower() == "true",
                "restart_count": int(restart_raw),
                "network_mode": json.loads(network_raw),
                "ports": ports or {},
            }
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise StopExecution("T1 container inspect decode failed") from exc
        if not isinstance(row["labels"], dict) or not isinstance(row["ports"], dict):
            raise StopExecution("T1 container labels/ports shape invalid")
        rows.append(row)
    return rows


def classify_t1_runtime(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def service(row: dict[str, Any]) -> str | None:
        value = row["labels"].get("com.docker.compose.service")
        return value if isinstance(value, str) else None

    managers = [row for row in rows if service(row) == "manager"]
    brokers = [row for row in rows if service(row) == "broker"]
    if len(managers) != 1:
        raise StopExecution(f"T1 authoritative Manager service count is {len(managers)}, expected 1")
    if len(brokers) != 1:
        raise StopExecution(f"T1 authoritative Broker service count is {len(brokers)}, expected 1")
    manager = managers[0]
    broker = brokers[0]
    if not manager["running"]:
        raise StopExecution("T1 Manager is not running")
    if not broker["running"]:
        raise StopExecution("T1 Broker is not running")
    if manager["network_mode"] != "host":
        raise StopExecution("T1 Manager network mode is not host")
    tls_mapping = broker["ports"].get("8883/tcp")
    if not tls_mapping:
        raise StopExecution("T1 Broker has no live 8883/tcp runtime publication")
    return {"manager": manager, "broker": broker, "container_count": len(rows)}


def t1_runtime_snapshot(*, root: Path, repo_root: Path, op_index: int, target: str, phase: str) -> tuple[int, dict[str, Any]]:
    op_index, ids_result = run_ssh(
        root=root,
        index=op_index,
        label=f"{phase}_t1_container_ids",
        target=target,
        remote_argv=["docker", "ps", "-aq"],
        cwd=repo_root,
    )
    ids = [line.strip() for line in (ids_result.stdout or "").splitlines() if line.strip()]
    if not ids:
        raise StopExecution("T1 Docker inventory is empty")
    fmt = "{{.Id}}\t{{json .Name}}\t{{json .Config.Image}}\t{{json .Config.Labels}}\t{{json .State.Running}}\t{{.RestartCount}}\t{{json .HostConfig.NetworkMode}}\t{{json .NetworkSettings.Ports}}"
    op_index, inspect_result = run_ssh(
        root=root,
        index=op_index,
        label=f"{phase}_t1_container_inspect",
        target=target,
        remote_argv=["docker", "inspect", "--format", fmt, *ids],
        cwd=repo_root,
    )
    rows = parse_container_inspect(inspect_result.stdout or "")
    runtime = classify_t1_runtime(rows)
    private = {
        "phase": phase,
        "container_count": runtime["container_count"],
        "manager": runtime["manager"],
        "broker": runtime["broker"],
    }
    id18.write_json(root / f"{phase}_t1_runtime_private.json", private)
    return op_index, runtime


def t1_utc(*, root: Path, repo_root: Path, op_index: int, target: str, label: str) -> tuple[int, str]:
    op_index, result = run_ssh(
        root=root,
        index=op_index,
        label=label,
        target=target,
        remote_argv=["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
        cwd=repo_root,
    )
    value = (result.stdout or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise StopExecution(f"{label}: T1 UTC timestamp shape invalid")
    return op_index, value


def capture_manager_window(*, root: Path, repo_root: Path, op_index: int, target: str, manager_id: str, start: str, end: str) -> tuple[int, dict[str, int]]:
    op_index, result = run_ssh(
        root=root,
        index=op_index,
        label="t1_manager_relay_window_logs",
        target=target,
        remote_argv=["docker", "logs", "--timestamps", "--since", start, "--until", end, manager_id],
        cwd=repo_root,
    )
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    counts = {
        "accepted_relay_count": len(ACCEPTED_RELAY_RE.findall(combined)),
        "rejected_relay_count": len(REJECTED_RELAY_RE.findall(combined)),
        "subscription_line_count": len(SUBSCRIPTION_RE.findall(combined)),
    }
    id18.write_json(root / "t1_manager_relay_window_counts_private.json", counts)
    return op_index, counts


def public_t1_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    manager = runtime["manager"]
    broker = runtime["broker"]
    return {
        "container_count": runtime["container_count"],
        "manager_service_count": 1,
        "broker_service_count": 1,
        "manager_running": manager["running"],
        "broker_running": broker["running"],
        "manager_network_mode": manager["network_mode"],
        "broker_tls_runtime_publication": bool(broker["ports"].get("8883/tcp")),
        "manager_restart_count": manager["restart_count"],
        "broker_restart_count": broker["restart_count"],
    }


def adjudicate_board_prestate(role: str, summary: dict[str, Any]) -> dict[str, Any]:
    snapshot = summary["snapshot"]
    id21._schema5(snapshot)
    if summary["selected_slot"] != EXPECTED_SELECTED_SLOT:
        raise StopExecution(f"{role}: selected slot drifted from ID21")
    if summary["active_seq"] != EXPECTED_ACTIVE_SEQ:
        raise StopExecution(f"{role}: active OTA sequence drifted from ID21")
    if summary["active_state"] != EXPECTED_ACTIVE_STATE:
        raise StopExecution(f"{role}: active OTA state is not VALID")
    if summary["selected_image_sha256"] != SCHEMA5_FIRMWARE_SHA256:
        raise StopExecution(f"{role}: selected image is not exact Schema-v5")
    return {
        "selected_slot": summary["selected_slot"],
        "active_seq": summary["active_seq"],
        "active_state": summary["active_state"],
        "selected_image_exact_schema5": True,
        "schema_version": id21._int(snapshot, "schema_version"),
        "boot_session": id21._int(snapshot, "boot_session"),
    }


def t1_stability(pre: dict[str, Any], post: dict[str, Any]) -> dict[str, bool]:
    return {
        "manager_container_identity_stable": pre["manager"]["id"] == post["manager"]["id"],
        "broker_container_identity_stable": pre["broker"]["id"] == post["broker"]["id"],
        "manager_restart_count_unchanged": pre["manager"]["restart_count"] == post["manager"]["restart_count"],
        "broker_restart_count_unchanged": pre["broker"]["restart_count"] == post["broker"]["restart_count"],
    }


def evidence_manifest(root: Path) -> list[dict[str, Any]]:
    return id18.evidence_manifest(root)


def write_closure(root: Path, *, execution_id: str, package_commit: str, authorization_id: str, result: str, failed: str | None, stop_reason: str | None, t1_access: bool | str, board_access: bool | str, interlocks: dict[str, float], prestate: dict[str, Any] | None, board_relay: dict[str, Any] | None, t1_preclaim: dict[str, Any] | None, t1_window: dict[str, Any] | None, t1_postcheck: dict[str, Any] | None, next_route: str) -> None:
    auth = json.loads((root / "authorization.json").read_text(encoding="utf-8"))
    controlled_rf = interlock_completed(root, "RELAY_WINDOW")
    payload = {
        "execution_id": execution_id,
        "execution_package_commit": package_commit,
        "authorization": authorization_id,
        "authorization_claimed": bool(auth.get("claimed")),
        "authorization_consumed": bool(auth.get("consumed")),
        "replay_permitted": False,
        "t1_relay_ingress_result": result,
        "first_failed_operation": failed,
        "stop_reason": stop_reason,
        "t1_access_occurred": t1_access,
        "board_a_physical_access": board_access,
        "board_b_physical_access": board_access,
        "controlled_rf_experiment": controlled_rf,
        "controlled_rf_experiment_authorized": bool(auth.get("claimed")),
        "operator_interlock_elapsed_seconds": interlocks,
        "flash_write": False,
        "flash_erase": False,
        "host_nvs_write": False,
        "otadata_write": False,
        "pairing_change": False,
        "credential_change": False,
        "serial_open": False,
        "t1_file_write": False,
        "t1_docker_mutation": False,
        "t1_network_mutation": False,
        "mqtt_test_publish": False,
        "mqtt_extra_subscriber": False,
        "automatic_retry": False,
        "automatic_rollback": False,
        "prestate": prestate,
        "board_relay_phase": board_relay,
        "t1_preclaim": t1_preclaim,
        "t1_window": t1_window,
        "t1_postcheck": t1_postcheck,
        "home_assistant_entity_update": "NOT_IN_SCOPE",
        "next_route": next_route,
    }
    if result == "PASS":
        payload.update(
            {
                "board_side_relay_chain_proven_in_id22_session": True,
                "t1_broker_mediated_relay_ingress": "PROVEN",
                "manager_relay_ingress": "PROVEN",
                "manager_relay_acceptance": "PROVEN",
                "kf089_end_to_end_relay_telemetry": "PROVEN",
            }
        )
    else:
        payload.update(
            {
                "board_side_relay_chain_proven_in_id22_session": bool(board_relay and board_relay.get("board_side_relay_chain_proven")),
                "t1_broker_mediated_relay_ingress": "NOT_PROVEN",
                "manager_relay_ingress": "NOT_PROVEN",
                "manager_relay_acceptance": "NOT_PROVEN",
                "kf089_end_to_end_relay_telemetry": "NOT_PROVEN",
            }
        )
    id18.write_json(root / "closure.json", payload)
    id18.write_json(root / "evidence_manifest.json", {"schema_version": 1, "execution_id": execution_id, "authorization": authorization_id, "files": evidence_manifest(root)})


def self_check() -> None:
    manifest = load_manifest()
    if manifest["predecessor"]["execution_package_commit"] != ID21_EXECUTION_PACKAGE_COMMIT:
        raise StopExecution("ID21 predecessor binding mismatch")
    refs = manifest["authority_references"]
    if refs["id21_executor_impl_git_blob"] != ID21_IMPL_GIT_BLOB:
        raise StopExecution("ID21 helper blob mismatch")
    if refs["manager_simplified_mqtt_service_git_blob"] != MANAGER_SERVICE_GIT_BLOB:
        raise StopExecution("Manager service blob mismatch")
    if refs["schema5_source_commit"] != SCHEMA5_SOURCE_COMMIT:
        raise StopExecution("Schema-v5 source authority mismatch")
    if refs["schema5_firmware_sha256"] != SCHEMA5_FIRMWARE_SHA256:
        raise StopExecution("Schema-v5 firmware authority mismatch")
    if manifest["operator_contract"]["relay_staging_min_seconds"] != MIN_RELAY_STAGING_SECONDS:
        raise StopExecution("Relay staging timing mismatch")
    if manifest["operator_contract"]["relay_window_min_seconds"] != MIN_RELAY_WINDOW_SECONDS:
        raise StopExecution("Relay window timing mismatch")
    sample = "2026-09-13T00:00:00Z Accepted simplified N3-W telemetry source=relay node=x gateway=y key=z\n"
    if len(ACCEPTED_RELAY_RE.findall(sample)) != 1:
        raise StopExecution("Manager acceptance parser self-check failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--expected-package-commit")
    parser.add_argument("--authorization-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--t1-ssh-target")
    args = parser.parse_args()

    if args.self_check:
        if any(value is not None for value in (args.expected_package_commit, args.authorization_id, args.execution_id, args.evidence_root, args.t1_ssh_target)):
            parser.error("--self-check cannot be combined with execution arguments")
        self_check()
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0

    required = (args.expected_package_commit, args.authorization_id, args.execution_id, args.evidence_root, args.t1_ssh_target)
    if any(value is None or value == "" for value in required):
        parser.error("all execution arguments are required")
    if sys.version_info[:2] != (3, 11):
        raise StopExecution("Python 3.11 is required")

    repo_root = id18.find_repo_root(PACKAGE_DIR)
    root = args.evidence_root.expanduser().resolve()
    if id18.is_within(root, repo_root):
        raise StopExecution("private evidence root must be outside repository")
    if root.exists() and any(root.iterdir()):
        raise StopExecution("evidence root must be absent or empty")
    id18.ensure_private_dir(root)
    cfg = id18.make_esptool_cfg(root)
    env = {"ESPTOOL_CFGFILE": str(cfg), "ESPTOOL_OPEN_PORT_ATTEMPTS": "1"}
    write_authorization(root, args.authorization_id, args.execution_id, claimed=False)

    op_index = 1
    failed = "HOST_PREFLIGHT"
    t1_access: bool | str = False
    board_access: bool | str = False
    interlocks: dict[str, float] = {}
    public_prestate: dict[str, Any] | None = None
    board_relay_public: dict[str, Any] | None = None
    t1_preclaim_public: dict[str, Any] | None = None
    t1_window_public: dict[str, Any] | None = None
    t1_post_public: dict[str, Any] | None = None
    next_route = "STOP_RETURN_TO_HIGH_LEVEL_MODEL"

    try:
        op_index = verify_host(root, repo_root, args.expected_package_commit)
        write_authorization(root, args.authorization_id, args.execution_id, claimed=True)

        failed = "T1_RUNTIME_PRECLAIM"
        t1_access = "UNKNOWN"
        op_index, t1_pre = t1_runtime_snapshot(root=root, repo_root=repo_root, op_index=op_index, target=args.t1_ssh_target, phase="preclaim")
        t1_access = True
        t1_preclaim_public = public_t1_runtime(t1_pre)

        failed = "OPERATOR_PRECLAIM_ROM_PREPARATION"
        interlocks["preclaim"] = operator_interlock(
            root,
            name="PRECLAIM",
            token=TOKEN_PRECLAIM,
            minimum_seconds=0,
            instructions=(
                "1) Keep T1 running and do not access it manually.\n"
                "2) Fully power off Board A and Board B.\n"
                "3) Put each board into fresh ROM Download with BOOT/GPIO9 low during USB power-on, then release BOOT.\n"
                "4) Leave only these two target boards as /dev/cu.usbmodem* devices.\n"
                "5) Keep all other lab N3-W compact senders powered off.\n"
                f"6) Type exactly {TOKEN_PRECLAIM}.\n"
            ),
        )

        failed = "BOARD_PRECLAIM_IDENTITY_BINDING"
        board_access = "UNKNOWN"
        op_index, bindings = id21.discover_and_bind_boards(root=root, repo_root=repo_root, op_index=op_index, phase="preclaim", env=env)
        board_access = True
        pre_private: dict[str, Any] = {}
        pre_public: dict[str, Any] = {}
        for role in ("board_a", "board_b"):
            failed = f"BOARD_PRECLAIM_{role.upper()}"
            op_index, pre_private[role] = id21.capture_prestate(root=root, repo_root=repo_root, op_index=op_index, role=role, binding=bindings[role], env=env)
            pre_public[role] = adjudicate_board_prestate(role, pre_private[role])
        public_prestate = {
            role: {key: value for key, value in data.items() if key != "boot_session"}
            for role, data in pre_public.items()
        }

        failed = "OPERATOR_RELAY_STAGING"
        interlocks["relay_staging"] = operator_interlock(
            root,
            name="RELAY_STAGING",
            token=TOKEN_STAGING,
            minimum_seconds=MIN_RELAY_STAGING_SECONDS,
            instructions=(
                "1) Fully power both boards off from ROM.\n"
                "2) Normal-boot A and B exactly once with BOOT/GPIO9 released.\n"
                "3) Keep both in normal AP coverage for at least 45 seconds.\n"
                "4) Keep all other lab N3-W compact senders off; do not move/isolate B yet.\n"
                "5) Do not open serial and do not access T1 manually.\n"
                f"6) Type exactly {TOKEN_STAGING}.\n"
            ),
        )

        failed = "T1_RELAY_WINDOW_START"
        op_index, t1_start = t1_utc(root=root, repo_root=repo_root, op_index=op_index, target=args.t1_ssh_target, label="t1_relay_window_start_utc")

        failed = "OPERATOR_RELAY_WINDOW"
        interlocks["relay_window"] = operator_interlock(
            root,
            name="RELAY_WINDOW",
            token=TOKEN_RELAY_COMPLETE,
            minimum_seconds=MIN_RELAY_WINDOW_SECONDS,
            instructions=(
                "1) Keep Board A powered in normal AP coverage.\n"
                "2) Move/isolate only Board B into the already-qualified selective-RF condition: B loses AP/Wi-Fi while A<->B ESP-NOW remains viable.\n"
                "3) Maintain that condition for at least 180 seconds.\n"
                "4) Do not access T1 manually and do not open serial.\n"
                "5) At window end, fully power Board B off.\n"
                "6) Keep Board A running for at least 10 additional seconds, then power A off.\n"
                "7) Re-enter fresh ROM Download on both boards and leave only these two boards enumerated.\n"
                f"8) Type exactly {TOKEN_RELAY_COMPLETE}.\n"
            ),
        )

        failed = "T1_RELAY_WINDOW_END"
        op_index, t1_end = t1_utc(root=root, repo_root=repo_root, op_index=op_index, target=args.t1_ssh_target, label="t1_relay_window_end_utc")
        op_index, manager_counts = capture_manager_window(
            root=root,
            repo_root=repo_root,
            op_index=op_index,
            target=args.t1_ssh_target,
            manager_id=t1_pre["manager"]["id"],
            start=t1_start,
            end=t1_end,
        )
        t1_window_public = {"manager_accepted_relay_count": manager_counts["accepted_relay_count"], "manager_rejected_relay_count": manager_counts["rejected_relay_count"]}

        failed = "T1_RUNTIME_STABILITY_POSTCHECK"
        op_index, t1_post = t1_runtime_snapshot(root=root, repo_root=repo_root, op_index=op_index, target=args.t1_ssh_target, phase="post")
        stable = t1_stability(t1_pre, t1_post)
        t1_post_public = {**public_t1_runtime(t1_post), **stable}
        if not all(stable.values()):
            raise StopExecution("T1 Manager/Broker identity or restart count changed during ID22 window")

        failed = "BOARD_POST_IDENTITY_BINDING"
        op_index, post_bindings = id21.discover_and_bind_boards(root=root, repo_root=repo_root, op_index=op_index, phase="relay_post", env=env)
        relay_private: dict[str, dict[str, Any]] = {}
        for role in ("board_a", "board_b"):
            failed = f"BOARD_POST_{role.upper()}_NVS"
            op_index, relay_private[role] = id21.capture_nvs_phase(root=root, repo_root=repo_root, op_index=op_index, phase="relay_post", role=role, binding=post_bindings[role], env=env)

        failed = "BOARD_RELAY_CHAIN_ADJUDICATION"
        board_relay_public = id21.adjudicate_relay_phase(
            a=relay_private["board_a"],
            b=relay_private["board_b"],
            baseline_a_boot_session=pre_public["board_a"]["boot_session"],
            baseline_b_boot_session=pre_public["board_b"]["boot_session"],
        )
        if not board_relay_public["board_side_relay_chain_proven"]:
            raise StopExecution(f"ID22 board-side Relay chain unproven at {board_relay_public['first_unproven_stage']}")

        failed = "T1_MANAGER_RELAY_ACCEPTANCE"
        if manager_counts["accepted_relay_count"] < 1:
            raise StopExecution("Manager accepted no simplified N3-W source=relay telemetry in the bounded T1 window")

        next_route = "PREPARE_KF089_END_TO_END_RELAY_CLOSEOUT_PACKAGE"
        write_closure(
            root,
            execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id,
            result="PASS",
            failed=None,
            stop_reason=None,
            t1_access=t1_access,
            board_access=board_access,
            interlocks=interlocks,
            prestate=public_prestate,
            board_relay=board_relay_public,
            t1_preclaim=t1_preclaim_public,
            t1_window=t1_window_public,
            t1_postcheck=t1_post_public,
            next_route=next_route,
        )
    except (StopExecution, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        write_closure(
            root,
            execution_id=args.execution_id,
            package_commit=args.expected_package_commit,
            authorization_id=args.authorization_id,
            result="STOP",
            failed=failed,
            stop_reason=str(exc),
            t1_access=t1_access,
            board_access=board_access,
            interlocks=interlocks,
            prestate=public_prestate,
            board_relay=board_relay_public,
            t1_preclaim=t1_preclaim_public,
            t1_window=t1_window_public,
            t1_postcheck=t1_post_public,
            next_route="STOP_RETURN_TO_HIGH_LEVEL_MODEL",
        )

    closure = json.loads((root / "closure.json").read_text(encoding="utf-8"))
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["t1_relay_ingress_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
