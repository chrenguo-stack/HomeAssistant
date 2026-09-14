#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shlex
import time
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
ID25_EXECUTOR_PATH = (
    PACKAGE_DIR.parent / "id25_manager_relay_subscription_reactivation" / "executor.py"
)
ID25_EXECUTOR_BLOB = "469192d7962dcf04e30e70d344bbdc66d72da12c"
MANAGER_SERVICE_PATH = (
    "host/greenhouse-manager/src/greenhouse_manager/runtime/"
    "n3w_simplified_isolated_mqtt_service.py"
)
MANAGER_SERVICE_BLOB = "2a478300e66bed341f55b44e629c24847128f413"

PREWINDOW_QUIESCENCE_SECONDS = 10
MIN_RELAY_WINDOW_SECONDS = 180
TOKEN_READY = "ID26_READY_BOARD_A_DIRECT_BOARD_B_OFF_RELAY_LOCATION"
TOKEN_COMPLETE = "ID26_BOARD_B_FRESH_RELAY_WINDOW_COMPLETE"

ACCEPTED_RELAY_RE = re.compile(
    r"Accepted simplified N3-W telemetry source=relay "
    r"node=(\S+) gateway=(\S+) key=(\S+)"
)
REJECTED_RELAY_RE = re.compile(
    r"Rejected simplified N3-W ingress source=relay "
    r"node=(\S+) gateway=(\S+) code=(\S+)"
)
DUPLICATE_RELAY_RE = re.compile(
    r"Ignored simplified N3-W duplicate source=relay "
    r"node=(\S+) key=(\S+) code=(\S+)"
)


class StopExecution(RuntimeError):
    def __init__(self, operation: str, reason: str):
        super().__init__(reason)
        self.operation = operation
        self.reason = reason


def _load_id25():
    spec = importlib.util.spec_from_file_location("kf089_id25_executor", ID25_EXECUTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load accepted ID25 executor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


id25 = _load_id25()
id24 = id25.id24


def dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def git_text(args: list[str]) -> str:
    try:
        return id25.git_text(args)
    except id25.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc


def validate_output_root(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise StopExecution("HOST_PREFLIGHT", "evidence root exists and is non-empty")
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)


def source_contract_check() -> dict[str, str]:
    try:
        id25.source_contract_check()
    except id25.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc

    id25_blob = git_text(
        [
            "rev-parse",
            "HEAD:tools/execution_packages/n3w/kf089/"
            "id25_manager_relay_subscription_reactivation/executor.py",
        ]
    )
    if id25_blob != ID25_EXECUTOR_BLOB:
        raise StopExecution("HOST_PREFLIGHT", "accepted ID25 executor blob drift")

    manager_blob = git_text(["rev-parse", f"HEAD:{MANAGER_SERVICE_PATH}"])
    if manager_blob != MANAGER_SERVICE_BLOB:
        raise StopExecution("HOST_PREFLIGHT", "Manager Relay oracle source blob drift")

    manager_source = git_text(["show", f"HEAD:{MANAGER_SERVICE_PATH}"])
    required_tokens = (
        'return f"gh/v1/{self.settings.system_id}/ingress/gateway/+/+/frame"',
        "client.subscribe(self.simplified_relay_subscription, qos=1)",
        '"Accepted simplified N3-W telemetry source=%s node=%s gateway=%s key=%s"',
        "self.phase4.process_relay(",
    )
    if not all(token in manager_source for token in required_tokens):
        raise StopExecution(
            "HOST_PREFLIGHT",
            "Manager Relay end-to-end oracle source contract is incomplete",
        )

    return {
        "id25_executor_blob": id25_blob,
        "manager_simplified_mqtt_service_blob": manager_blob,
    }


def ssh_result(
    root: Path,
    index: int,
    name: str,
    target: str,
    command: str,
) -> tuple[int, str, str]:
    return id24.ssh_op(root, index, name, target, command)


def ssh_text(
    root: Path,
    index: int,
    name: str,
    target: str,
    command: str,
    *,
    operation: str,
    message: str,
) -> str:
    result = ssh_result(root, index, name, target, command)
    try:
        return id24.require_ok(result, operation, message)
    except id24.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc


def read_runtime(
    root: Path,
    index: int,
    target: str,
    *,
    phase: str,
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    ids_raw = ssh_text(
        root,
        index,
        f"{phase}_t1_container_ids",
        target,
        "docker ps -aq --no-trunc",
        operation="T1_RUNTIME_PRECLAIM" if phase == "pre" else "T1_RUNTIME_POSTCHECK",
        message="cannot enumerate T1 containers",
    )
    index += 1
    ids = [line.strip() for line in ids_raw.splitlines() if line.strip()]
    if not ids:
        raise StopExecution(
            "T1_RUNTIME_PRECLAIM" if phase == "pre" else "T1_RUNTIME_POSTCHECK",
            "T1 container inventory is empty",
        )

    inspect_raw = ssh_text(
        root,
        index,
        f"{phase}_t1_container_inspect",
        target,
        "docker inspect " + " ".join(shlex.quote(value) for value in ids),
        operation="T1_RUNTIME_PRECLAIM" if phase == "pre" else "T1_RUNTIME_POSTCHECK",
        message="cannot inspect T1 containers",
    )
    index += 1
    try:
        items = id24.parse_inventory(inspect_raw)
        manager, broker = id24.bind_runtime(items)
    except id24.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc

    return index, manager, broker


def read_exact_repaired_dynsec(
    root: Path,
    index: int,
    target: str,
    manager: dict[str, Any],
    broker: dict[str, Any],
    *,
    phase: str,
) -> tuple[int, str, dict[str, Any]]:
    broker_id = str(broker.get("Id") or "")
    if not broker_id:
        raise StopExecution("T1_DYNSEC_STATE", "bound Broker container id is missing")

    conf = ssh_text(
        root,
        index,
        f"{phase}_broker_mosquitto_conf",
        target,
        f"docker exec {shlex.quote(broker_id)} cat /mosquitto/config/mosquitto.conf",
        operation="T1_DYNSEC_CONFIG",
        message="cannot read mosquitto.conf",
    )
    index += 1
    try:
        dynsec_path = id24.dynsec_path(conf)
    except id24.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc

    raw = ssh_text(
        root,
        index,
        f"{phase}_dynamic_security_state",
        target,
        f"docker exec {shlex.quote(broker_id)} cat {shlex.quote(dynsec_path)}",
        operation="T1_DYNSEC_STATE",
        message="cannot read live Dynamic Security state",
    )
    index += 1

    try:
        analysis = id25.analyze_exact_repaired(raw, id24.env_map(manager))
    except id25.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc

    snapshot = root / f"{phase}_dynamic_security_private.json"
    snapshot.write_text(raw, encoding="utf-8")
    digest = sha256_text(raw)
    dump(
        root / f"{phase}_dynamic_security_authority_private.json",
        {"sha256": digest, "utf8_bytes": len(raw.encode("utf-8"))},
    )
    return index, digest, analysis


def t1_utc(root: Path, index: int, target: str, *, name: str) -> tuple[int, str]:
    value = ssh_text(
        root,
        index,
        name,
        target,
        "date -u +%Y-%m-%dT%H:%M:%SZ",
        operation="T1_TIME_WINDOW",
        message="cannot read T1 UTC timestamp",
    ).strip()
    index += 1
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise StopExecution("T1_TIME_WINDOW", "T1 UTC timestamp shape invalid")
    return index, value


def parse_relay_logs(logs: str) -> dict[str, Any]:
    accepted = ACCEPTED_RELAY_RE.findall(logs)
    rejected = REJECTED_RELAY_RE.findall(logs)
    duplicates = DUPLICATE_RELAY_RE.findall(logs)
    routes = sorted({(node, gateway) for node, gateway, _key in accepted})
    return {
        "accepted_relay_count": len(accepted),
        "rejected_relay_count": len(rejected),
        "duplicate_relay_count": len(duplicates),
        "unique_accepted_relay_route_count": len(routes),
        "accepted_routes_private": [
            {"node": node, "gateway": gateway} for node, gateway in routes
        ],
    }


def capture_manager_logs(
    root: Path,
    index: int,
    target: str,
    manager_id: str,
    *,
    start: str,
    end: str,
    name: str,
) -> tuple[int, dict[str, Any]]:
    result = ssh_result(
        root,
        index,
        name,
        target,
        "docker logs --timestamps "
        f"--since {shlex.quote(start)} --until {shlex.quote(end)} "
        f"{shlex.quote(manager_id)}",
    )
    index += 1
    return_code, stdout, stderr = result
    if return_code:
        raise StopExecution(
            "T1_MANAGER_RELAY_ACCEPTANCE",
            "cannot read bounded Manager logs",
        )
    combined = stdout + "\n" + stderr
    parsed = parse_relay_logs(combined)
    dump(root / f"{name}_analysis_private.json", parsed)
    return index, parsed


def operator_interlock(
    root: Path,
    *,
    name: str,
    token: str,
    instructions: str,
    minimum_seconds: int = 0,
) -> float:
    print(f"\nID26 OPERATOR INTERLOCK: {name}\n{instructions}", flush=True)
    started = time.monotonic()
    observed = input(f"ID26 token [{token}]: ").strip()
    elapsed = time.monotonic() - started
    matched = observed == token
    dump(
        root / f"operator_interlock_{name.lower()}.json",
        {
            "name": name,
            "required_token": token,
            "token_match": matched,
            "minimum_elapsed_seconds": minimum_seconds,
            "observed_elapsed_seconds": elapsed,
        },
    )
    if not matched:
        raise StopExecution("OPERATOR_INTERLOCK", f"token mismatch: {name}")
    if elapsed < minimum_seconds:
        raise StopExecution(
            "OPERATOR_INTERLOCK",
            f"elapsed time below minimum for {name}",
        )
    return elapsed


def runtime_stability(
    pre_manager: dict[str, Any],
    pre_broker: dict[str, Any],
    post_manager: dict[str, Any],
    post_broker: dict[str, Any],
) -> dict[str, bool]:
    manager_stable = id24.runtime_fingerprint(pre_manager) == id24.runtime_fingerprint(post_manager)
    broker_stable = id24.runtime_fingerprint(pre_broker) == id24.runtime_fingerprint(post_broker)
    if not manager_stable or not broker_stable:
        raise StopExecution(
            "T1_RUNTIME_POSTCHECK",
            "Manager or Broker runtime fingerprint changed during ID26 window",
        )
    return {
        "manager_runtime_stable": manager_stable,
        "broker_runtime_stable": broker_stable,
    }


def self_check() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("gate_id") != "id26_minimal_end_to_end_relay_revalidation":
        raise SystemExit("manifest gate mismatch")
    contract = manifest.get("live_revalidation_contract", {})
    if contract.get("prewindow_quiescence_seconds") != PREWINDOW_QUIESCENCE_SECONDS:
        raise SystemExit("pre-window quiescence contract mismatch")
    if contract.get("board_b_power_window_min_seconds") != MIN_RELAY_WINDOW_SECONDS:
        raise SystemExit("Relay power-window timing contract mismatch")
    if contract.get("board_b_power_window_count") != 1:
        raise SystemExit("Board B power-window count contract mismatch")
    source_contract_check()

    sample = "\n".join(
        [
            "x Accepted simplified N3-W telemetry source=relay node=b gateway=a key=k1",
            "x Accepted simplified N3-W telemetry source=relay node=b gateway=a key=k2",
            "x Rejected simplified N3-W ingress source=relay node=b gateway=a code=x",
        ]
    )
    parsed = parse_relay_logs(sample)
    if parsed["accepted_relay_count"] != 2:
        raise SystemExit("accepted Relay parser self-check failed")
    if parsed["unique_accepted_relay_route_count"] != 1:
        raise SystemExit("Relay route parser self-check failed")

    source = Path(__file__).read_text(encoding="utf-8").lower()
    prohibited_tokens = (
        "docker restart ",
        "docker stop ",
        "docker start ",
        "docker rm ",
        "mosquitto_pub",
        "mosquitto_sub",
        "esptool",
        "/dev/cu.",
    )
    for token in prohibited_tokens:
        if token in source:
            raise SystemExit(f"prohibited live mutation/access token found: {token}")

    print(json.dumps({"self_check": "PASS"}, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    for name in (
        "expected-package-commit",
        "authorization-id",
        "execution-id",
        "evidence-root",
        "t1-ssh-target",
    ):
        parser.add_argument(f"--{name}")
    args = parser.parse_args()

    if args.self_check:
        self_check()
        return 0

    required = (
        "expected_package_commit",
        "authorization_id",
        "execution_id",
        "evidence_root",
        "t1_ssh_target",
    )
    if any(not getattr(args, name) for name in required):
        parser.error("all execution arguments are required")

    root = Path(args.evidence_root).expanduser().resolve()
    closure: dict[str, Any] = {
        "authorization": args.authorization_id,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "execution_id": args.execution_id,
        "execution_package_commit": args.expected_package_commit,
        "source_end_to_end_oracle_contract_proven": False,
        "t1_access_occurred": False,
        "board_a_physical_mutation": False,
        "board_a_usb_access": False,
        "board_b_usb_access": False,
        "board_b_fresh_relay_power_window_completed": False,
        "controlled_rf_experiment": False,
        "serial_open": False,
        "flash_write": False,
        "host_nvs_write": False,
        "otadata_write": False,
        "pairing_change": False,
        "credential_change": False,
        "t1_file_write": False,
        "t1_docker_mutation": False,
        "manager_restart": False,
        "broker_restart": False,
        "broker_config_mutation": False,
        "dynsec_mutation": False,
        "t1_network_mutation": False,
        "mqtt_test_publish": False,
        "mqtt_extra_subscriber": False,
        "automatic_retry": False,
        "automatic_rollback": False,
        "live_repaired_dynsec_prestate_proven": False,
        "pre_window_dynsec_snapshot_sha256_recorded": False,
        "prewindow_accepted_relay_count": None,
        "prewindow_quiescence_elapsed_seconds": None,
        "relay_window_elapsed_seconds": None,
        "window_accepted_relay_count": None,
        "window_rejected_relay_count": None,
        "window_duplicate_relay_count": None,
        "window_unique_accepted_relay_route_count": None,
        "manager_runtime_stable": False,
        "broker_runtime_stable": False,
        "live_repaired_dynsec_poststate_proven": False,
        "dynsec_state_unchanged": False,
        "t1_broker_mediated_relay_ingress": "NOT_PROVEN",
        "manager_relay_acceptance": "NOT_PROVEN",
        "kf089_end_to_end_relay_telemetry": "NOT_PROVEN",
        "home_assistant_entity_update": "NOT_IN_SCOPE",
        "revalidation_result": "STOP",
        "first_failed_operation": None,
        "stop_reason": None,
        "next_route": "STOP_RETURN_TO_HIGH_LEVEL_MODEL",
    }

    next_op = 1

    try:
        try:
            id24.validate_target(args.t1_ssh_target)
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc

        validate_output_root(root)

        head = git_text(["rev-parse", "HEAD"])
        if head != args.expected_package_commit:
            raise StopExecution(
                "HOST_PREFLIGHT",
                f"HEAD {head} != expected package commit",
            )
        if git_text(["status", "--porcelain", "--untracked-files=no"]):
            raise StopExecution("HOST_PREFLIGHT", "tracked worktree is dirty")

        source_blobs = source_contract_check()
        closure["source_end_to_end_oracle_contract_proven"] = True
        dump(root / "host_preflight_private.json", {"head": head, **source_blobs})
        dump(
            root / "authorization.json",
            {
                "authorization": args.authorization_id,
                "claimed": False,
                "consumed": False,
                "replay_permitted": False,
            },
        )

        closure["authorization_claimed"] = True
        closure["authorization_consumed"] = True
        dump(
            root / "authorization.json",
            {
                "authorization": args.authorization_id,
                "claimed": True,
                "consumed": True,
                "replay_permitted": False,
            },
        )

        closure["t1_access_occurred"] = True
        next_op, pre_manager, pre_broker = read_runtime(
            root, next_op, args.t1_ssh_target, phase="pre"
        )
        manager_id = str(pre_manager.get("Id") or "")
        if not manager_id:
            raise StopExecution("T1_RUNTIME_PRECLAIM", "Manager container id is missing")

        next_op, pre_dynsec_sha, _pre_analysis = read_exact_repaired_dynsec(
            root,
            next_op,
            args.t1_ssh_target,
            pre_manager,
            pre_broker,
            phase="pre",
        )
        closure["live_repaired_dynsec_prestate_proven"] = True
        closure["pre_window_dynsec_snapshot_sha256_recorded"] = True

        operator_interlock(
            root,
            name="READY",
            token=TOKEN_READY,
            instructions=(
                "1) Keep Board A powered in normal AP coverage and do not move/reboot it.\n"
                "2) Board B must be fully powered OFF at the previously qualified Relay-only location.\n"
                "3) Keep every other Relay-capable test sender powered OFF.\n"
                "4) Do not connect USB/serial to either board.\n"
                f"5) When these conditions are true, type exactly {TOKEN_READY}."
            ),
        )

        next_op, baseline_start = t1_utc(
            root, next_op, args.t1_ssh_target, name="prewindow_start_utc"
        )
        baseline_timer = time.monotonic()
        time.sleep(PREWINDOW_QUIESCENCE_SECONDS)
        baseline_elapsed = time.monotonic() - baseline_timer
        closure["prewindow_quiescence_elapsed_seconds"] = baseline_elapsed
        if baseline_elapsed < PREWINDOW_QUIESCENCE_SECONDS:
            raise StopExecution(
                "PREWINDOW_QUIESCENCE",
                "pre-window quiescence elapsed time below contract",
            )
        next_op, baseline_end = t1_utc(
            root, next_op, args.t1_ssh_target, name="prewindow_end_utc"
        )
        next_op, baseline = capture_manager_logs(
            root,
            next_op,
            args.t1_ssh_target,
            manager_id,
            start=baseline_start,
            end=baseline_end,
            name="prewindow_manager_logs",
        )
        closure["prewindow_accepted_relay_count"] = baseline["accepted_relay_count"]
        if baseline["accepted_relay_count"] != 0:
            raise StopExecution(
                "PREWINDOW_QUIESCENCE",
                "background Relay acceptance observed while Board B should be off",
            )

        next_op, window_start = t1_utc(
            root, next_op, args.t1_ssh_target, name="relay_window_start_utc"
        )

        relay_elapsed = operator_interlock(
            root,
            name="RELAY_WINDOW",
            token=TOKEN_COMPLETE,
            minimum_seconds=MIN_RELAY_WINDOW_SECONDS,
            instructions=(
                "1) Power Board B ON now at the qualified Relay-only location.\n"
                "2) Keep Board A untouched and powered Direct.\n"
                "3) Keep Board B powered for at least 180 seconds.\n"
                "4) Then power Board B OFF.\n"
                "5) Only after Board B is OFF, return here and type exactly "
                f"{TOKEN_COMPLETE}."
            ),
        )
        closure["relay_window_elapsed_seconds"] = relay_elapsed
        closure["board_b_fresh_relay_power_window_completed"] = True
        closure["controlled_rf_experiment"] = True

        next_op, window_end = t1_utc(
            root, next_op, args.t1_ssh_target, name="relay_window_end_utc"
        )
        next_op, window = capture_manager_logs(
            root,
            next_op,
            args.t1_ssh_target,
            manager_id,
            start=window_start,
            end=window_end,
            name="relay_window_manager_logs",
        )
        closure["window_accepted_relay_count"] = window["accepted_relay_count"]
        closure["window_rejected_relay_count"] = window["rejected_relay_count"]
        closure["window_duplicate_relay_count"] = window["duplicate_relay_count"]
        closure["window_unique_accepted_relay_route_count"] = window[
            "unique_accepted_relay_route_count"
        ]

        if window["accepted_relay_count"] < 1:
            raise StopExecution(
                "T1_MANAGER_RELAY_ACCEPTANCE",
                "no accepted Relay telemetry observed in fresh Board B window",
            )
        if window["unique_accepted_relay_route_count"] != 1:
            raise StopExecution(
                "T1_MANAGER_RELAY_ACCEPTANCE",
                "fresh window did not contain exactly one accepted Relay route",
            )

        next_op, post_manager, post_broker = read_runtime(
            root, next_op, args.t1_ssh_target, phase="post"
        )
        stability = runtime_stability(
            pre_manager, pre_broker, post_manager, post_broker
        )
        closure.update(stability)

        next_op, post_dynsec_sha, _post_analysis = read_exact_repaired_dynsec(
            root,
            next_op,
            args.t1_ssh_target,
            post_manager,
            post_broker,
            phase="post",
        )
        closure["live_repaired_dynsec_poststate_proven"] = True
        closure["dynsec_state_unchanged"] = post_dynsec_sha == pre_dynsec_sha
        if not closure["dynsec_state_unchanged"]:
            raise StopExecution(
                "T1_DYNSEC_POSTCHECK",
                "Dynamic Security state changed during ID26 window",
            )

        closure["t1_broker_mediated_relay_ingress"] = "PROVEN"
        closure["manager_relay_acceptance"] = "PROVEN"
        closure["kf089_end_to_end_relay_telemetry"] = "PROVEN"
        closure["revalidation_result"] = "PASS"
        closure["next_route"] = "KF089_RELAY_END_TO_END_CLOSEOUT"

    except StopExecution as exc:
        closure["first_failed_operation"] = exc.operation
        closure["stop_reason"] = exc.reason
    except Exception as exc:  # pragma: no cover - fail closed for unexpected host/runtime faults
        closure["first_failed_operation"] = "UNEXPECTED_EXCEPTION"
        closure["stop_reason"] = f"{type(exc).__name__}: {exc}"

    if root.exists():
        dump(root / "closure.json", closure)
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["revalidation_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
