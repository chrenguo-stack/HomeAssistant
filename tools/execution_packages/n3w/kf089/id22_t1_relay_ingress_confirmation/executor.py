#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
IMPL_PATH = PACKAGE_DIR / "executor_impl.py"

CURRENT_MANAGER_CONTAINER_NAME = "greenhouse-manager"
CURRENT_MANAGER_IMAGE_PREFIX = "greenhouse-manager:"
FROZEN_MANAGER_SOURCE_REVISION = "8fbedc7e0778ce91d146cd5f0772bebdd20ad13a"
CURRENT_BROKER_COMPOSE_SERVICE = "broker"
CURRENT_BROKER_COMPOSE_PROJECT = "n3wfc4"


def _load_impl():
    spec = importlib.util.spec_from_file_location("id22_executor_impl", IMPL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("ID22 implementation module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _assert_no_mutation_call_sites() -> None:
    tree = ast.parse(IMPL_PATH.read_text(encoding="utf-8"), filename=str(IMPL_PATH))
    prohibited_attrs = {
        "flash_begin", "flash_block", "flash_finish", "write_flash",
        "erase_flash", "erase_region", "write_mem",
    }
    prohibited_tokens = {
        "docker restart", "docker start", "docker stop", "docker rm",
        "docker exec", "docker compose up", "docker compose down",
        "mosquitto_pub", "mosquitto_sub",
    }
    source = IMPL_PATH.read_text(encoding="utf-8")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in prohibited_attrs:
            raise RuntimeError(f"prohibited mutation call site found: {node.func.attr}")
    lowered = source.lower()
    for token in prohibited_tokens:
        if token in lowered:
            raise RuntimeError(f"prohibited T1/MQTT mutation token found: {token}")


def _extract_t1_target(argv: list[str]) -> str | None:
    for index, item in enumerate(argv):
        if item == "--t1-ssh-target":
            return argv[index + 1] if index + 1 < len(argv) else None
        if item.startswith("--t1-ssh-target="):
            return item.split("=", 1)[1]
    return None


def _validate_t1_target(value: str | None) -> str:
    if value is None or not value.strip():
        raise RuntimeError("ID22 T1 SSH target is required")
    target = value.strip()
    lowered = target.lower()
    placeholders = ("你的t1_ssh_target", "your_t1_ssh_target", "t1_ssh_target", "<t1_ssh_target>")
    if lowered in placeholders or "你的" in target:
        raise RuntimeError("ID22 T1 SSH target is still a documentation placeholder")
    if any(ch.isspace() for ch in target):
        raise RuntimeError("ID22 T1 SSH target must not contain whitespace")
    try:
        target.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError("ID22 T1 SSH target must be an ASCII SSH alias/host expression") from exc
    if target.startswith("-") or len(target) > 255:
        raise RuntimeError("ID22 T1 SSH target shape is invalid")
    return target


def _decode_process_bytes(value: bytes | None) -> str:
    return (value or b"").decode("utf-8", errors="backslashreplace")


def _normalized_container_name(row: dict[str, Any]) -> str:
    value = row.get("name")
    return value.lstrip("/").strip() if isinstance(value, str) else ""


def _compose_label(row: dict[str, Any], key: str) -> str:
    labels = row.get("labels")
    if not isinstance(labels, dict):
        return ""
    value = labels.get(key)
    return value.strip() if isinstance(value, str) else ""


def _manager_source_revision(row: dict[str, Any]) -> str:
    labels = row.get("labels")
    if not isinstance(labels, dict):
        return ""
    value = labels.get("org.opencontainers.image.revision")
    return value.strip() if isinstance(value, str) else ""


def _classify_current_t1_runtime(impl: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    managers = [
        row for row in rows
        if _normalized_container_name(row) == CURRENT_MANAGER_CONTAINER_NAME
        and isinstance(row.get("image"), str)
        and row["image"].startswith(CURRENT_MANAGER_IMAGE_PREFIX)
        and _manager_source_revision(row) == FROZEN_MANAGER_SOURCE_REVISION
    ]
    brokers = [
        row for row in rows
        if _compose_label(row, "com.docker.compose.service") == CURRENT_BROKER_COMPOSE_SERVICE
        and _compose_label(row, "com.docker.compose.project") == CURRENT_BROKER_COMPOSE_PROJECT
    ]
    if len(managers) != 1:
        raise impl.StopExecution(f"T1 authoritative Manager count is {len(managers)}, expected 1")
    if len(brokers) != 1:
        raise impl.StopExecution(f"T1 authoritative Broker count is {len(brokers)}, expected 1")
    manager = managers[0]
    broker = brokers[0]
    if not manager.get("running"):
        raise impl.StopExecution("T1 Manager is not running")
    if not broker.get("running"):
        raise impl.StopExecution("T1 Broker is not running")
    if manager.get("network_mode") != "host":
        raise impl.StopExecution("T1 Manager network mode is not host")
    ports = broker.get("ports")
    if not isinstance(ports, dict):
        raise impl.StopExecution("T1 Broker runtime port metadata is invalid")
    if not ports.get("8883/tcp"):
        raise impl.StopExecution("T1 Broker has no live 8883/tcp runtime publication")
    return {
        "manager": manager,
        "broker": broker,
        "container_count": len(rows),
        "manager_binding_mode": "container_name+image_prefix+frozen_source_revision",
        "broker_binding_mode": "compose_service+compose_project",
    }


def _install_current_t1_runtime_classifier(impl: Any) -> None:
    def classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return _classify_current_t1_runtime(impl, rows)

    original_public = impl.public_t1_runtime

    def public(runtime: dict[str, Any]) -> dict[str, Any]:
        value = original_public(runtime)
        value["manager_binding_mode"] = runtime.get("manager_binding_mode", "UNKNOWN")
        value["broker_binding_mode"] = runtime.get("broker_binding_mode", "UNKNOWN")
        return value

    impl.classify_t1_runtime = classify
    impl.public_t1_runtime = public


def _install_robust_recorded_runner(impl: Any) -> None:
    id18 = impl.id18

    def robust_run_recorded(
        *, root: Path, index: int, label: str, argv: list[str], cwd: Path,
        target_operation: bool = False, extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        id18.assert_read_only_argv(argv)
        op_dir = root / f"op_{index:02d}_{label}"
        id18.ensure_private_dir(op_dir)
        id18.write_json(op_dir / "command.json", {
            "argv": argv, "cwd": str(cwd), "label": label,
            "operation_index": index, "target_operation": target_operation,
            "mutation_operation": False, "utc_start": id18.utc_now(),
            "environment_overrides": dict(sorted((extra_env or {}).items())),
        })
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        try:
            raw = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=False, check=False)
        except OSError as exc:
            id18.write_text(op_dir / "stdout.txt", "")
            id18.write_text(op_dir / "stderr.txt", f"{type(exc).__name__}: {exc}\n")
            id18.write_json(op_dir / "result.json", {
                "command_started": False, "returncode": None,
                "target_access_occurred": False if target_operation else None,
                "utc_end": id18.utc_now(),
            })
            raise impl.StopExecution(f"{label} process launch failed") from exc
        stdout = _decode_process_bytes(raw.stdout)
        stderr = _decode_process_bytes(raw.stderr)
        id18.write_text(op_dir / "stdout.txt", stdout)
        id18.write_text(op_dir / "stderr.txt", stderr)
        id18.write_json(op_dir / "result.json", {
            "command_started": True, "returncode": raw.returncode,
            "target_access_occurred": (
                True if target_operation and raw.returncode == 0
                else "UNKNOWN" if target_operation else None
            ),
            "stdout_utf8_decode": "backslashreplace",
            "stderr_utf8_decode": "backslashreplace",
            "utc_end": id18.utc_now(),
        })
        return subprocess.CompletedProcess(args=raw.args, returncode=raw.returncode, stdout=stdout, stderr=stderr)

    impl.run_recorded = robust_run_recorded


def _classifier_self_check(impl: Any) -> None:
    manager = {
        "id": "m1",
        "name": "/greenhouse-manager",
        "image": "greenhouse-manager:fc4-kf075-test",
        "labels": {"org.opencontainers.image.revision": FROZEN_MANAGER_SOURCE_REVISION},
        "running": True,
        "restart_count": 0,
        "network_mode": "host",
        "ports": {},
    }
    broker = {
        "id": "b1",
        "name": "/n3wfc4-broker-1",
        "image": "local/mosquitto:test",
        "labels": {
            "com.docker.compose.service": "broker",
            "com.docker.compose.project": "n3wfc4",
        },
        "running": True,
        "restart_count": 0,
        "network_mode": "bridge",
        "ports": {"8883/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8883"}]},
    }
    result = _classify_current_t1_runtime(impl, [manager, broker])
    if result["manager"]["id"] != "m1" or result["broker"]["id"] != "b1":
        raise RuntimeError("current T1 runtime classifier self-check failed")
    drifted = dict(manager)
    drifted["labels"] = {"org.opencontainers.image.revision": "0" * 40}
    try:
        _classify_current_t1_runtime(impl, [drifted, broker])
    except impl.StopExecution:
        pass
    else:
        raise RuntimeError("drifted Manager source revision was not rejected")


def self_check() -> None:
    impl = _load_impl()
    impl.self_check()
    _assert_no_mutation_call_sites()
    refs = impl.load_manifest()["authority_references"]
    expected_refs = {
        "manager_container_name": CURRENT_MANAGER_CONTAINER_NAME,
        "manager_image_prefix": CURRENT_MANAGER_IMAGE_PREFIX,
        "frozen_deployed_product_manager_source": FROZEN_MANAGER_SOURCE_REVISION,
        "broker_compose_service": CURRENT_BROKER_COMPOSE_SERVICE,
        "broker_compose_project": CURRENT_BROKER_COMPOSE_PROJECT,
    }
    for key, expected in expected_refs.items():
        if refs.get(key) != expected:
            raise RuntimeError(f"ID22 runtime authority reference mismatch: {key}")
    if _validate_t1_target("root@t1") != "root@t1":
        raise RuntimeError("T1 target validator self-check failed")
    try:
        _validate_t1_target("你的T1_SSH_TARGET")
    except RuntimeError:
        pass
    else:
        raise RuntimeError("T1 placeholder validator self-check failed")
    if "\\xff" not in _decode_process_bytes(b"x\xff"):
        raise RuntimeError("subprocess byte decoder self-check failed")
    _classifier_self_check(impl)


def main() -> int:
    if "--self-check" in sys.argv[1:]:
        if sys.argv[1:] != ["--self-check"]:
            raise SystemExit("--self-check cannot be combined with execution arguments")
        self_check()
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0
    _validate_t1_target(_extract_t1_target(sys.argv[1:]))
    impl = _load_impl()
    _install_robust_recorded_runner(impl)
    _install_current_t1_runtime_classifier(impl)
    return int(impl.main())


if __name__ == "__main__":
    raise SystemExit(main())
