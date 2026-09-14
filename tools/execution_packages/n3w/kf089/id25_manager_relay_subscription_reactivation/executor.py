#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shlex
import time
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
ID24_EXECUTOR_PATH = (
    PACKAGE_DIR.parent / "id24_manager_relay_dynsec_acl_repair" / "executor.py"
)

ID24_EXECUTOR_BLOB = "0ee29a4b8378813498ad2c41d7f44fd8b5801245"
SUBSCRIPTION_SOURCE_PATH = (
    "host/greenhouse-manager/src/greenhouse_manager/runtime/"
    "n3w_simplified_isolated_mqtt_service.py"
)
SUBSCRIPTION_SOURCE_BLOB = "2a478300e66bed341f55b44e629c24847128f413"
RUNTIME_WIRING_PATH = (
    "host/greenhouse-manager/src/greenhouse_manager/runtime/"
    "n3w_manager_runtime_wiring.py"
)
RUNTIME_WIRING_BLOB = "90cd70249200a810711b0388a38bcd6c8e64ef16"
POSTRESTART_OBSERVATION_SECONDS = 5


def _load_id24():
    spec = importlib.util.spec_from_file_location("kf089_id24_executor", ID24_EXECUTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load accepted ID24 executor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


id24 = _load_id24()


class StopExecution(RuntimeError):
    def __init__(self, operation: str, reason: str):
        super().__init__(reason)
        self.operation = operation
        self.reason = reason


def dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def git_text(args: list[str]) -> str:
    try:
        return id24.git_text(args)
    except id24.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc


def validate_output_root(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise StopExecution("HOST_PREFLIGHT", "evidence root exists and is non-empty")
    root.mkdir(parents=True, exist_ok=True)


def source_contract_check() -> dict[str, str]:
    try:
        id24.source_contract_check()
    except id24.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc

    id24_blob = git_text(
        [
            "rev-parse",
            "HEAD:tools/execution_packages/n3w/kf089/"
            "id24_manager_relay_dynsec_acl_repair/executor.py",
        ]
    )
    if id24_blob != ID24_EXECUTOR_BLOB:
        raise StopExecution("HOST_PREFLIGHT", "accepted ID24 executor blob drift")

    subscription_blob = git_text(["rev-parse", f"HEAD:{SUBSCRIPTION_SOURCE_PATH}"])
    if subscription_blob != SUBSCRIPTION_SOURCE_BLOB:
        raise StopExecution("HOST_PREFLIGHT", "N3-W Relay subscription source blob drift")

    subscription_source = git_text(["show", f"HEAD:{SUBSCRIPTION_SOURCE_PATH}"])
    required_subscription_tokens = (
        'return f"gh/v1/{self.settings.system_id}/ingress/gateway/+/+/frame"',
        "client.subscribe(self.simplified_relay_subscription, qos=1)",
        '_LOGGER.info("Subscribed to %s", self.simplified_relay_subscription)',
    )
    if not all(token in subscription_source for token in required_subscription_tokens):
        raise StopExecution(
            "HOST_PREFLIGHT",
            "N3-W Relay subscription source contract is incomplete",
        )

    wiring_blob = git_text(["rev-parse", f"HEAD:{RUNTIME_WIRING_PATH}"])
    if wiring_blob != RUNTIME_WIRING_BLOB:
        raise StopExecution("HOST_PREFLIGHT", "N3-W runtime wiring blob drift")

    wiring_source = git_text(["show", f"HEAD:{RUNTIME_WIRING_PATH}"])
    required_wiring_tokens = (
        "if settings.n3w_runtime_enabled:",
        "build_n3w_simplified_manager_service(",
        "N3wSimplifiedIsolatedMqttService",
    )
    if not all(token in wiring_source for token in required_wiring_tokens):
        raise StopExecution(
            "HOST_PREFLIGHT",
            "N3-W Manager runtime selector contract is incomplete",
        )

    return {
        "id24_executor_blob": id24_blob,
        "n3w_subscription_source_blob": subscription_blob,
        "n3w_runtime_wiring_blob": wiring_blob,
    }


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
    result = id24.ssh_op(root, index, name, target, command)
    try:
        return id24.require_ok(result, operation, message)
    except id24.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc


def read_live_dynsec(
    root: Path,
    index: int,
    target: str,
    broker_id: str,
    path: str,
    *,
    name: str,
) -> str:
    return ssh_text(
        root,
        index,
        name,
        target,
        f"docker exec {shlex.quote(broker_id)} cat {shlex.quote(path)}",
        operation="T1_DYNSEC_STATE",
        message="cannot read live Dynamic Security state",
    )


def save_dynsec_snapshot(root: Path, prefix: str, raw: str) -> str:
    snapshot = root / f"{prefix}_dynamic_security_private.json"
    snapshot.write_text(raw, encoding="utf-8")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    dump(
        root / f"{prefix}_dynamic_security_authority_private.json",
        {
            "sha256": digest,
            "utf8_bytes": len(raw.encode("utf-8")),
            "snapshot_file": snapshot.name,
        },
    )
    return digest


def analyze_exact_repaired(raw: str, runtime_env: dict[str, str]) -> dict[str, Any]:
    try:
        analysis = id24.analyze_dynsec(raw, runtime_env, require_defect=False)
        id24.require_exact_repaired_poststate(analysis)
    except id24.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc
    return analysis


def require_postrestart_runtime(
    before_manager: dict[str, Any],
    before_broker: dict[str, Any],
    after_items: list[dict[str, Any]],
) -> dict[str, bool]:
    try:
        after_manager, after_broker = id24.bind_runtime(after_items)
    except id24.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc

    before_manager_fp = id24.runtime_fingerprint(before_manager)
    after_manager_fp = id24.runtime_fingerprint(after_manager)
    before_broker_fp = id24.runtime_fingerprint(before_broker)
    after_broker_fp = id24.runtime_fingerprint(after_broker)

    manager_id_preserved = after_manager_fp["id"] == before_manager_fp["id"]
    manager_image_preserved = after_manager_fp["image"] == before_manager_fp["image"]
    manager_started_at_changed = (
        bool(before_manager_fp["started_at"])
        and bool(after_manager_fp["started_at"])
        and after_manager_fp["started_at"] != before_manager_fp["started_at"]
    )
    manager_running = after_manager_fp["running"] is True
    broker_runtime_stable = after_broker_fp == before_broker_fp

    if not (
        manager_id_preserved
        and manager_image_preserved
        and manager_started_at_changed
        and manager_running
        and broker_runtime_stable
    ):
        raise StopExecution(
            "T1_RUNTIME_POSTCHECK",
            "Manager restart or Broker stability contract not satisfied",
        )

    return {
        "manager_container_id_preserved": manager_id_preserved,
        "manager_image_preserved": manager_image_preserved,
        "manager_started_at_changed": manager_started_at_changed,
        "manager_running": manager_running,
        "broker_runtime_stable": broker_runtime_stable,
    }


def analyze_postrestart_logs(logs: str, system_id: str) -> dict[str, bool]:
    relay_topic = f"gh/v1/{system_id}/ingress/gateway/+/+/frame"
    direct_topic = f"gh/v1/{system_id}/ingress/node/+/telemetry"
    relay_observed = f"Subscribed to {relay_topic}" in logs
    direct_observed = f"Subscribed to {direct_topic}" in logs

    lowered = logs.lower()
    failure_markers = (
        "mqtt connection rejected",
        "mqtt simplified relay subscribe failed",
    )
    failure_absent = not any(marker in lowered for marker in failure_markers)

    if not relay_observed:
        raise StopExecution(
            "T1_MANAGER_SUBSCRIPTION_POSTCHECK",
            "post-restart Relay subscription request log was not observed",
        )
    if not direct_observed:
        raise StopExecution(
            "T1_MANAGER_SUBSCRIPTION_POSTCHECK",
            "post-restart Direct subscription request log was not observed",
        )
    if not failure_absent:
        raise StopExecution(
            "T1_MANAGER_SUBSCRIPTION_POSTCHECK",
            "post-restart MQTT subscription failure marker was observed",
        )

    return {
        "postrestart_relay_subscription_request_observed": relay_observed,
        "postrestart_direct_subscription_request_observed": direct_observed,
        "postrestart_failure_log_absent": failure_absent,
    }


def self_check() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("gate_id") != "id25_manager_relay_subscription_reactivation":
        raise SystemExit("manifest gate mismatch")
    if manifest.get("live_reactivation_contract", {}).get(
        "manager_restart_command_count"
    ) != 1:
        raise SystemExit("manager restart count contract mismatch")
    source_contract_check()
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
        "execution_id": args.execution_id,
        "execution_package_commit": args.expected_package_commit,
        "replay_permitted": False,
        "t1_access_occurred": False,
        "source_subscription_contract_proven": False,
        "live_repaired_dynsec_prestate_proven": False,
        "pre_restart_dynsec_snapshot_sha256_recorded": False,
        "manager_restart": False,
        "manager_restart_command_count": 0,
        "manager_restart_completed": False,
        "manager_container_id_preserved": False,
        "manager_image_preserved": False,
        "manager_started_at_changed": False,
        "manager_running": False,
        "broker_restart": False,
        "broker_runtime_stable": False,
        "postrestart_relay_subscription_request_observed": False,
        "postrestart_direct_subscription_request_observed": False,
        "postrestart_failure_log_absent": False,
        "live_repaired_dynsec_poststate_proven": False,
        "dynsec_state_unchanged": False,
        "dynsec_mutation": False,
        "t1_file_write": False,
        "mqtt_test_publish": False,
        "application_topic_subscriber": False,
        "board_a_access": False,
        "board_b_access": False,
        "controlled_rf_experiment": False,
        "reactivation_result": "STOP",
        "first_failed_operation": None,
        "stop_reason": None,
        "kf089_end_to_end_relay_telemetry": "NOT_PROVEN",
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
        closure["source_subscription_contract_proven"] = True
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

        ids_raw = ssh_text(
            root,
            next_op,
            "preclaim_t1_container_ids",
            args.t1_ssh_target,
            "docker ps -aq --no-trunc",
            operation="T1_RUNTIME_PRECLAIM",
            message="cannot enumerate T1 containers",
        )
        next_op += 1
        ids = [line.strip() for line in ids_raw.splitlines() if line.strip()]
        if not ids:
            raise StopExecution("T1_RUNTIME_PRECLAIM", "T1 container inventory is empty")

        inspect_raw = ssh_text(
            root,
            next_op,
            "preclaim_t1_container_inspect",
            args.t1_ssh_target,
            "docker inspect " + " ".join(shlex.quote(value) for value in ids),
            operation="T1_RUNTIME_PRECLAIM",
            message="cannot inspect T1 containers",
        )
        next_op += 1
        try:
            items = id24.parse_inventory(inspect_raw)
            manager, broker = id24.bind_runtime(items)
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc

        manager_id = str(manager.get("Id") or "")
        broker_id = str(broker.get("Id") or "")
        if not manager_id or not broker_id:
            raise StopExecution(
                "T1_RUNTIME_PRECLAIM",
                "bound Manager or Broker container id is missing",
            )
        runtime_env = id24.env_map(manager)

        conf = ssh_text(
            root,
            next_op,
            "preclaim_broker_mosquitto_conf",
            args.t1_ssh_target,
            f"docker exec {shlex.quote(broker_id)} "
            "sh -c 'cat /mosquitto/config/mosquitto.conf'",
            operation="T1_DYNSEC_CONFIG",
            message="cannot read mosquitto.conf",
        )
        next_op += 1
        try:
            dynsec_state_path = id24.dynsec_path(conf)
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc

        pre_raw = read_live_dynsec(
            root,
            next_op,
            args.t1_ssh_target,
            broker_id,
            dynsec_state_path,
            name="preclaim_broker_dynamic_security_json",
        )
        next_op += 1
        pre_analysis = analyze_exact_repaired(pre_raw, runtime_env)
        closure["live_repaired_dynsec_prestate_proven"] = True
        pre_digest = save_dynsec_snapshot(root, "pre_restart", pre_raw)
        closure["pre_restart_dynsec_snapshot_sha256_recorded"] = bool(pre_digest)
        dump(root / "pre_restart_dynsec_analysis_private.json", pre_analysis)

        epoch_raw = ssh_text(
            root,
            next_op,
            "pre_restart_t1_epoch",
            args.t1_ssh_target,
            "date +%s",
            operation="T1_RUNTIME_PRECLAIM",
            message="cannot read T1 epoch marker",
        )
        next_op += 1
        try:
            restart_epoch = int(epoch_raw.strip())
        except ValueError as exc:
            raise StopExecution(
                "T1_RUNTIME_PRECLAIM",
                "T1 epoch marker is invalid",
            ) from exc

        closure["manager_restart"] = True
        closure["manager_restart_command_count"] = 1
        restart_result = id24.ssh_op(
            root,
            next_op,
            "manager_restart_once",
            args.t1_ssh_target,
            f"docker restart --time 10 {shlex.quote(manager_id)}",
        )
        next_op += 1
        if restart_result[0] != 0:
            raise StopExecution(
                "T1_MANAGER_RESTART",
                "single Manager restart command failed",
            )
        closure["manager_restart_completed"] = True

        time.sleep(POSTRESTART_OBSERVATION_SECONDS)

        ids_after_raw = ssh_text(
            root,
            next_op,
            "postrestart_t1_container_ids",
            args.t1_ssh_target,
            "docker ps -aq --no-trunc",
            operation="T1_RUNTIME_POSTCHECK",
            message="cannot enumerate T1 containers after Manager restart",
        )
        next_op += 1
        ids_after = [
            line.strip() for line in ids_after_raw.splitlines() if line.strip()
        ]
        if not ids_after:
            raise StopExecution(
                "T1_RUNTIME_POSTCHECK",
                "T1 container inventory is empty after Manager restart",
            )

        inspect_after_raw = ssh_text(
            root,
            next_op,
            "postrestart_t1_container_inspect",
            args.t1_ssh_target,
            "docker inspect " + " ".join(shlex.quote(value) for value in ids_after),
            operation="T1_RUNTIME_POSTCHECK",
            message="cannot inspect T1 containers after Manager restart",
        )
        next_op += 1
        try:
            after_items = id24.parse_inventory(inspect_after_raw)
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc

        closure.update(require_postrestart_runtime(manager, broker, after_items))

        log_since = max(0, restart_epoch - 2)
        logs_result = id24.ssh_op(
            root,
            next_op,
            "postrestart_manager_logs",
            args.t1_ssh_target,
            f"docker logs --since {log_since} {shlex.quote(manager_id)}",
        )
        next_op += 1
        if logs_result[0] != 0:
            raise StopExecution(
                "T1_MANAGER_SUBSCRIPTION_POSTCHECK",
                "cannot read bounded post-restart Manager logs",
            )
        postrestart_logs = logs_result[1] + logs_result[2]
        (root / "postrestart_manager_logs_private.txt").write_text(
            postrestart_logs,
            encoding="utf-8",
        )
        closure.update(
            analyze_postrestart_logs(
                postrestart_logs,
                str(pre_analysis["system_id"]),
            )
        )

        post_raw = read_live_dynsec(
            root,
            next_op,
            args.t1_ssh_target,
            broker_id,
            dynsec_state_path,
            name="postrestart_broker_dynamic_security_json",
        )
        next_op += 1
        post_analysis = analyze_exact_repaired(post_raw, runtime_env)
        closure["live_repaired_dynsec_poststate_proven"] = True
        post_digest = save_dynsec_snapshot(root, "post_restart", post_raw)
        dump(root / "post_restart_dynsec_analysis_private.json", post_analysis)

        closure["dynsec_state_unchanged"] = post_digest == pre_digest
        if not closure["dynsec_state_unchanged"]:
            raise StopExecution(
                "T1_DYNSEC_POSTCHECK",
                "Dynamic Security state changed during subscription reactivation",
            )

        closure["reactivation_result"] = "PASS"
        closure["next_route"] = (
            "PREPARE_KF089_MINIMAL_END_TO_END_RELAY_REVALIDATION_PACKAGE"
        )

    except StopExecution as exc:
        closure["first_failed_operation"] = exc.operation
        closure["stop_reason"] = exc.reason
    except Exception as exc:
        closure["first_failed_operation"] = "UNEXPECTED_EXCEPTION"
        closure["stop_reason"] = f"{type(exc).__name__}: {exc}"

    if root.exists():
        dump(root / "closure.json", closure)
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["reactivation_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
