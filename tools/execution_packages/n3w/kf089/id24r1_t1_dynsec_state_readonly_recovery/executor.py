#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shlex
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
ID24_EXECUTOR_PATH = (
    PACKAGE_DIR.parent / "id24_manager_relay_dynsec_acl_repair" / "executor.py"
)


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


def read_live_dynsec(
    root: Path,
    index: int,
    target: str,
    broker_id: str,
    path: str,
) -> str:
    try:
        return id24.require_ok(
            id24.ssh_op(
                root,
                index,
                "readonly_broker_dynamic_security_json",
                target,
                f"docker exec {shlex.quote(broker_id)} cat {shlex.quote(path)}",
            ),
            "T1_DYNSEC_STATE",
            "cannot read live Dynamic Security state",
        )
    except id24.StopExecution as exc:
        raise StopExecution(exc.operation, exc.reason) from exc


def save_current_snapshot(root: Path, raw: str) -> str:
    snapshot = root / "current_dynamic_security_private.json"
    snapshot.write_text(raw, encoding="utf-8")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    dump(
        root / "current_dynamic_security_authority_private.json",
        {
            "sha256": digest,
            "utf8_bytes": len(raw.encode("utf-8")),
            "snapshot_file": snapshot.name,
        },
    )
    return digest


def classify(analysis: dict[str, Any]) -> str:
    if analysis.get("defect") is True:
        return "PRE_REPAIR_DEFECT"
    if analysis.get("exact_repaired_contract") is True:
        return "EXACT_REPAIRED"
    return "PARTIAL_OR_DRIFT"


def sanitized_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "default_subscribe_deny": analysis.get("default_subscribe_deny"),
        "default_publish_client_receive_deny": analysis.get(
            "default_publish_client_receive_deny"
        ),
        "relay_exact_entry_counts": analysis.get("relay_exact_entry_counts"),
        "relay_exact_count": analysis.get("relay_exact_count"),
        "relay_subscribe_broad_allow_count": analysis.get(
            "relay_subscribe_broad_allow_count"
        ),
        "relay_receive_broad_allow_count": analysis.get(
            "relay_receive_broad_allow_count"
        ),
        "relay_unsubscribe_broad_allow_count": analysis.get(
            "relay_unsubscribe_broad_allow_count"
        ),
        "direct_contract_ok": analysis.get("direct_contract_ok"),
        "defect": analysis.get("defect"),
        "exact_repaired_contract": analysis.get("exact_repaired_contract"),
    }


def self_check() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("gate_id") != "id24r1_t1_dynsec_state_readonly_recovery":
        raise SystemExit("manifest gate mismatch")
    if not ID24_EXECUTOR_PATH.is_file():
        raise SystemExit("accepted ID24 executor missing")
    try:
        id24.source_contract_check()
    except id24.StopExecution as exc:
        raise SystemExit(f"ID24 source contract check failed: {exc.reason}") from exc
    if classify({"defect": True, "exact_repaired_contract": False}) != "PRE_REPAIR_DEFECT":
        raise SystemExit("pre-repair classifier mismatch")
    if classify({"defect": False, "exact_repaired_contract": True}) != "EXACT_REPAIRED":
        raise SystemExit("repaired classifier mismatch")
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
        "dynsec_mutation": False,
        "t1_file_write": False,
        "docker_mutation": False,
        "manager_restart": False,
        "broker_restart": False,
        "mqtt_test_publish": False,
        "application_topic_subscriber": False,
        "board_a_access": False,
        "board_b_access": False,
        "rf_execution": False,
        "current_dynsec_snapshot_sha256_recorded": False,
        "live_state_classification": "NOT_PROVEN",
        "manager_runtime_stable": False,
        "broker_runtime_stable": False,
        "recovery_result": "STOP",
        "first_failed_operation": None,
        "stop_reason": None,
        "kf089_end_to_end_relay_telemetry": "NOT_PROVEN",
        "next_route": "STOP_RETURN_TO_HIGH_LEVEL_MODEL",
    }

    manager: dict[str, Any] | None = None
    broker: dict[str, Any] | None = None
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
        try:
            source_blobs = id24.source_contract_check()
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc
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

        try:
            ids_raw = id24.require_ok(
                id24.ssh_op(
                    root,
                    next_op,
                    "readonly_t1_container_ids",
                    args.t1_ssh_target,
                    "docker ps -aq --no-trunc",
                ),
                "T1_RUNTIME_PRECLAIM",
                "cannot enumerate T1 containers",
            )
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc
        next_op += 1
        ids = [line.strip() for line in ids_raw.splitlines() if line.strip()]
        if not ids:
            raise StopExecution("T1_RUNTIME_PRECLAIM", "T1 container inventory is empty")

        try:
            inspect_raw = id24.require_ok(
                id24.ssh_op(
                    root,
                    next_op,
                    "readonly_t1_container_inspect",
                    args.t1_ssh_target,
                    "docker inspect " + " ".join(shlex.quote(value) for value in ids),
                ),
                "T1_RUNTIME_PRECLAIM",
                "cannot inspect T1 containers",
            )
            items = id24.parse_inventory(inspect_raw)
            manager, broker = id24.bind_runtime(items)
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc
        next_op += 1

        manager_id = str(manager.get("Id") or "")
        broker_id = str(broker.get("Id") or "")
        if not manager_id or not broker_id:
            raise StopExecution(
                "T1_RUNTIME_PRECLAIM",
                "bound Manager or Broker container id is missing",
            )
        runtime_env = id24.env_map(manager)

        try:
            conf = id24.require_ok(
                id24.ssh_op(
                    root,
                    next_op,
                    "readonly_broker_mosquitto_conf",
                    args.t1_ssh_target,
                    f"docker exec {shlex.quote(broker_id)} "
                    "sh -c 'cat /mosquitto/config/mosquitto.conf'",
                ),
                "T1_DYNSEC_CONFIG",
                "cannot read mosquitto.conf",
            )
            dynsec_state_path = id24.dynsec_path(conf)
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc
        next_op += 1

        raw = read_live_dynsec(
            root,
            next_op,
            args.t1_ssh_target,
            broker_id,
            dynsec_state_path,
        )
        next_op += 1
        digest = save_current_snapshot(root, raw)
        closure["current_dynsec_snapshot_sha256_recorded"] = bool(digest)

        analysis: dict[str, Any] | None = None
        try:
            analysis = id24.analyze_dynsec(
                raw,
                runtime_env,
                require_defect=False,
            )
        except id24.StopExecution as exc:
            if exc.reason == "active Manager Direct ingress ACL contract is not intact":
                closure["live_state_classification"] = "PARTIAL_OR_DRIFT"
                closure["direct_contract_ok"] = False
            else:
                raise StopExecution(exc.operation, exc.reason) from exc

        if analysis is not None:
            public = sanitized_analysis(analysis)
            closure.update(public)
            closure["live_state_classification"] = classify(analysis)
            dump(root / "current_dynsec_analysis_private.json", analysis)

        try:
            ids_after_raw = id24.require_ok(
                id24.ssh_op(
                    root,
                    next_op,
                    "readonly_postcheck_t1_container_ids",
                    args.t1_ssh_target,
                    "docker ps -aq --no-trunc",
                ),
                "T1_RUNTIME_POSTCHECK",
                "cannot enumerate T1 containers after read-only capture",
            )
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc
        next_op += 1
        ids_after = [line.strip() for line in ids_after_raw.splitlines() if line.strip()]

        try:
            inspect_after_raw = id24.require_ok(
                id24.ssh_op(
                    root,
                    next_op,
                    "readonly_postcheck_t1_container_inspect",
                    args.t1_ssh_target,
                    "docker inspect "
                    + " ".join(shlex.quote(value) for value in ids_after),
                ),
                "T1_RUNTIME_POSTCHECK",
                "cannot inspect T1 containers after read-only capture",
            )
            stability = id24.require_runtime_stable(
                manager,
                broker,
                id24.parse_inventory(inspect_after_raw),
            )
        except id24.StopExecution as exc:
            raise StopExecution(exc.operation, exc.reason) from exc
        closure.update(stability)

        state = closure["live_state_classification"]
        if state == "PRE_REPAIR_DEFECT":
            closure["next_route"] = (
                "REQUEST_NEW_KF089_MANAGER_RELAY_DYNSEC_ACL_REPAIR_"
                "T1_MUTATION_AUTHORIZATION"
            )
        elif state == "EXACT_REPAIRED":
            closure["next_route"] = (
                "PREPARE_KF089_MANAGER_RELAY_SUBSCRIPTION_REACTIVATION_PACKAGE"
            )
        elif state == "PARTIAL_OR_DRIFT":
            closure["next_route"] = "STOP_RETURN_TO_HIGH_LEVEL_MODEL"
        else:
            raise StopExecution(
                "T1_DYNSEC_STATE",
                f"unexpected live state classification {state}",
            )
        closure["recovery_result"] = "PASS"

    except StopExecution as exc:
        closure["first_failed_operation"] = exc.operation
        closure["stop_reason"] = exc.reason
    except Exception as exc:
        closure["first_failed_operation"] = "UNEXPECTED_EXCEPTION"
        closure["stop_reason"] = f"{type(exc).__name__}: {exc}"

    if root.exists():
        dump(root / "closure.json", closure)
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["recovery_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
