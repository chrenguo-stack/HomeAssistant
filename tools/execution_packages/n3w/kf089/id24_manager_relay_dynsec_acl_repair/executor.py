#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
REMOTE_MUTATOR_PATH = PACKAGE_DIR / "remote_dynsec_acl_mutator.py"

DEPLOYED_MANAGER_SOURCE = "8fbedc7e0778ce91d146cd5f0772bebdd20ad13a"
REPAIRED_SERVICE_PLAN_BLOB = "19d95cfe59c12ee0abeaddf8c777fb663a5bd399"
MANAGER_NAME = "greenhouse-manager"
MANAGER_IMAGE_PREFIX = "greenhouse-manager:"
BROKER_SERVICE = "broker"
BROKER_PROJECT = "n3wfc4"
TARGET_ACL_TYPES = (
    "subscribePattern",
    "publishClientReceive",
    "unsubscribePattern",
)
PLACEHOLDERS = ("你的", "t1_ssh_target", "placeholder", "example", "<", ">")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


class StopExecution(RuntimeError):
    def __init__(self, operation: str, reason: str):
        super().__init__(reason)
        self.operation = operation
        self.reason = reason


def decode(data: bytes) -> str:
    return data.decode("utf-8", errors="backslashreplace")


def dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def git_text(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise StopExecution(
            "HOST_PREFLIGHT",
            decode(completed.stderr).strip()
            or f"git {' '.join(args)} failed",
        )
    return decode(completed.stdout).strip()


def run_op(
    root: Path,
    index: int,
    name: str,
    argv: list[str],
    *,
    input_bytes: bytes | None = None,
) -> tuple[int, str, str]:
    directory = root / f"op_{index:02d}_{name}"
    directory.mkdir(parents=True, exist_ok=False)
    dump(
        directory / "command.json",
        {"argv": argv, "stdin_bytes": len(input_bytes or b"")},
    )
    completed = subprocess.run(
        argv,
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    stdout, stderr = decode(completed.stdout), decode(completed.stderr)
    (directory / "stdout.txt").write_text(stdout, encoding="utf-8")
    (directory / "stderr.txt").write_text(stderr, encoding="utf-8")
    dump(
        directory / "result.json",
        {
            "returncode": completed.returncode,
            "stdout_bytes": len(completed.stdout),
            "stderr_bytes": len(completed.stderr),
        },
    )
    return completed.returncode, stdout, stderr


def ssh_op(
    root: Path,
    index: int,
    name: str,
    target: str,
    command: str,
    *,
    input_bytes: bytes | None = None,
) -> tuple[int, str, str]:
    return run_op(
        root,
        index,
        name,
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ConnectionAttempts=1",
            target,
            command,
        ],
        input_bytes=input_bytes,
    )


def require_ok(
    result: tuple[int, str, str],
    operation: str,
    message: str,
) -> str:
    return_code, stdout, stderr = result
    if return_code:
        raise StopExecution(
            operation,
            f"{message}: "
            f"{(stderr.strip() or stdout.strip() or 'rc='+str(return_code))[:800]}",
        )
    return stdout


def validate_target(target: str) -> None:
    if (
        not target
        or target.strip() != target
        or any(character.isspace() for character in target)
    ):
        raise StopExecution(
            "HOST_PREFLIGHT",
            "T1 SSH target is empty or contains whitespace",
        )
    folded = target.casefold()
    if any(marker.casefold() in folded for marker in PLACEHOLDERS):
        raise StopExecution(
            "HOST_PREFLIGHT",
            "T1 SSH target looks like documentation placeholder",
        )
    try:
        target.encode("ascii")
    except UnicodeEncodeError as exc:
        raise StopExecution(
            "HOST_PREFLIGHT",
            "T1 SSH target must be ASCII",
        ) from exc


def validate_output_root(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise StopExecution(
            "HOST_PREFLIGHT",
            "evidence root exists and is non-empty",
        )
    root.mkdir(parents=True, exist_ok=True)


def source_contract_check() -> dict[str, str]:
    blob = git_text(
        [
            "rev-parse",
            "HEAD:host/greenhouse-manager/src/"
            "greenhouse_manager/runtime/service_identity_plan.py",
        ]
    )
    if blob != REPAIRED_SERVICE_PLAN_BLOB:
        raise StopExecution(
            "HOST_PREFLIGHT",
            "repaired Manager service identity plan blob drift",
        )
    source = git_text(
        [
            "show",
            "HEAD:host/greenhouse-manager/src/"
            "greenhouse_manager/runtime/service_identity_plan.py",
        ]
    )
    required = (
        'relay_ingress = f"gh/v1/{system_id}/ingress/gateway/+/+/frame"',
        "*_allow_topic(relay_ingress)",
    )
    if not all(token in source for token in required):
        raise StopExecution(
            "HOST_PREFLIGHT",
            "repaired Manager source does not grant exact Relay ingress topic",
        )
    if 'relay_ingress = f"gh/v1/{system_id}/ingress/gateway/#"' in source:
        raise StopExecution(
            "HOST_PREFLIGHT",
            "repaired Manager source is broader than the exact Relay topic",
        )
    if not REMOTE_MUTATOR_PATH.is_file():
        raise StopExecution(
            "HOST_PREFLIGHT",
            "remote DynSec mutator is missing",
        )
    return {"service_identity_plan_blob": blob}


def parse_inventory(raw: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise StopExecution(
            "T1_RUNTIME_PRECLAIM",
            f"inspect JSON invalid: {exc}",
        ) from exc
    if not isinstance(value, list):
        raise StopExecution(
            "T1_RUNTIME_PRECLAIM",
            "inspect root is not a list",
        )
    return [item for item in value if isinstance(item, dict)]


def bind_runtime(
    items: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    managers: list[dict[str, Any]] = []
    brokers: list[dict[str, Any]] = []
    for item in items:
        config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
        labels = (
            config.get("Labels")
            if isinstance(config.get("Labels"), dict)
            else {}
        )
        host = (
            item.get("HostConfig")
            if isinstance(item.get("HostConfig"), dict)
            else {}
        )
        state = item.get("State") if isinstance(item.get("State"), dict) else {}
        if (
            str(item.get("Name") or "").lstrip("/") == MANAGER_NAME
            and str(config.get("Image") or "").startswith(MANAGER_IMAGE_PREFIX)
            and labels.get("org.opencontainers.image.revision")
            == DEPLOYED_MANAGER_SOURCE
            and host.get("NetworkMode") == "host"
            and state.get("Running") is True
        ):
            managers.append(item)
        if (
            labels.get("com.docker.compose.service") == BROKER_SERVICE
            and labels.get("com.docker.compose.project") == BROKER_PROJECT
            and state.get("Running") is True
        ):
            brokers.append(item)
    if len(managers) != 1:
        raise StopExecution(
            "T1_RUNTIME_PRECLAIM",
            f"Manager count={len(managers)}, expected 1",
        )
    if len(brokers) != 1:
        raise StopExecution(
            "T1_RUNTIME_PRECLAIM",
            f"Broker count={len(brokers)}, expected 1",
        )
    return managers[0], brokers[0]


def env_map(container: dict[str, Any]) -> dict[str, str]:
    config = container.get("Config") if isinstance(container.get("Config"), dict) else {}
    values = config.get("Env") if isinstance(config.get("Env"), list) else []
    result: dict[str, str] = {}
    for value in values:
        if isinstance(value, str) and "=" in value:
            key, raw = value.split("=", 1)
            result[key] = raw
    return result


def dynsec_path(conf: str) -> str:
    plugin = False
    paths: list[str] = []
    for raw in conf.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("plugin ", "global_plugin ")) and "dynamic_security" in line:
            plugin = True
        if line.startswith("plugin_opt_config_file "):
            paths.append(line.split(None, 1)[1].strip())
    unique = sorted(set(paths))
    if not plugin or len(unique) != 1 or not unique[0].startswith("/"):
        raise StopExecution(
            "T1_DYNSEC_CONFIG",
            f"cannot derive active DynSec path: plugin={plugin} paths={unique}",
        )
    return unique[0]


def role_names(client: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for value in client.get("roles") or []:
        if isinstance(value, str):
            result.append(value)
        elif isinstance(value, dict) and isinstance(value.get("rolename"), str):
            result.append(value["rolename"])
    return result


def _allowed_topics(
    role: dict[str, Any],
    acl_type: str,
) -> set[str]:
    return {
        str(acl["topic"])
        for acl in role.get("acls") or []
        if isinstance(acl, dict)
        and acl.get("acltype") == acl_type
        and acl.get("allow") is True
        and isinstance(acl.get("topic"), str)
    }


def _allowed_exact_count(
    role: dict[str, Any],
    acl_type: str,
    topic: str,
) -> int:
    return sum(
        1
        for acl in role.get("acls") or []
        if isinstance(acl, dict)
        and acl.get("acltype") == acl_type
        and acl.get("allow") is True
        and acl.get("topic") == topic
    )


def analyze_dynsec(
    raw: str,
    runtime_env: dict[str, str],
    *,
    require_defect: bool,
) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise StopExecution(
            "T1_DYNSEC_STATE",
            f"DynSec JSON invalid: {exc}",
        ) from exc
    if not isinstance(value, dict):
        raise StopExecution("T1_DYNSEC_STATE", "DynSec root is not an object")

    clients = [item for item in (value.get("clients") or []) if isinstance(item, dict)]
    roles_list = [item for item in (value.get("roles") or []) if isinstance(item, dict)]
    roles = {
        item.get("rolename"): item
        for item in roles_list
        if isinstance(item.get("rolename"), str)
    }

    runtime_user = runtime_env.get("GH_MQTT_USERNAME") or ""
    runtime_cid = runtime_env.get("GH_MQTT_CLIENT_ID") or "greenhouse-manager"
    if not runtime_user or not runtime_cid:
        raise StopExecution(
            "T1_DYNSEC_STATE",
            "runtime Manager MQTT identity is incomplete",
        )

    matches = [
        client
        for client in clients
        if client.get("username") == runtime_user
        and client.get("clientid") == runtime_cid
    ]
    if len(matches) != 1:
        raise StopExecution(
            "T1_DYNSEC_STATE",
            f"active Manager exact DynSec match count={len(matches)}",
        )
    manager = matches[0]

    user_match = re.fullmatch(
        r"ghs_([A-Za-z0-9_-]{3,64})_manager",
        runtime_user,
    )
    cid_match = re.fullmatch(
        r"gh-manager-([A-Za-z0-9_-]{3,64})",
        runtime_cid,
    )
    if (
        user_match is None
        or cid_match is None
        or user_match.group(1) != cid_match.group(1)
    ):
        raise StopExecution(
            "T1_DYNSEC_STATE",
            "active Manager identity does not encode one consistent system id",
        )
    system_id = user_match.group(1)
    if not _ID_RE.fullmatch(system_id):
        raise StopExecution("T1_DYNSEC_STATE", "system id is invalid")

    expected_role = f"gh-service-{system_id}-manager"
    names = role_names(manager)
    if expected_role not in names or expected_role not in roles:
        raise StopExecution(
            "T1_DYNSEC_STATE",
            "active Manager does not bind the expected service role",
        )
    role = roles[expected_role]

    defaults = value.get("defaultACLAccess")
    if not isinstance(defaults, dict):
        raise StopExecution(
            "T1_DYNSEC_STATE",
            "defaultACLAccess is missing",
        )
    default_subscribe_deny = defaults.get("subscribe") is False
    default_receive_deny = defaults.get("publishClientReceive") is False

    relay_topic = f"gh/v1/{system_id}/ingress/gateway/+/+/frame"
    broad = {
        relay_topic,
        f"gh/v1/{system_id}/ingress/gateway/#",
        f"gh/v1/{system_id}/ingress/#",
        f"gh/v1/{system_id}/#",
        "gh/#",
        "#",
    }
    relay_exact_entry_counts = {
        acl_type: _allowed_exact_count(role, acl_type, relay_topic)
        for acl_type in TARGET_ACL_TYPES
    }
    relay_exact_present = {
        acl_type: count == 1
        for acl_type, count in relay_exact_entry_counts.items()
    }
    relay_subscribe_broad_count = len(
        _allowed_topics(role, "subscribePattern") & broad
    )
    relay_receive_broad_count = len(
        _allowed_topics(role, "publishClientReceive") & broad
    )
    relay_unsubscribe_broad_count = len(
        _allowed_topics(role, "unsubscribePattern") & broad
    )

    direct_topic = f"gh/v1/{system_id}/ingress/node/+/telemetry"
    direct_contract_ok = all(
        direct_topic in _allowed_topics(role, acl_type)
        for acl_type in TARGET_ACL_TYPES
    )
    if not direct_contract_ok:
        raise StopExecution(
            "T1_DYNSEC_STATE",
            "active Manager Direct ingress ACL contract is not intact",
        )

    defect = (
        default_subscribe_deny
        and default_receive_deny
        and relay_subscribe_broad_count == 0
        and relay_receive_broad_count == 0
        and relay_unsubscribe_broad_count == 0
        and all(count == 0 for count in relay_exact_entry_counts.values())
    )
    if require_defect and not defect:
        raise StopExecution(
            "T1_DYNSEC_STATE",
            "live Manager Relay ACL prestate no longer matches the proven defect",
        )

    exact_repaired_contract = (
        default_subscribe_deny
        and default_receive_deny
        and direct_contract_ok
        and all(count == 1 for count in relay_exact_entry_counts.values())
        and relay_subscribe_broad_count == 1
        and relay_receive_broad_count == 1
        and relay_unsubscribe_broad_count == 1
    )

    return {
        "system_id": system_id,
        "role_name": expected_role,
        "relay_topic": relay_topic,
        "default_subscribe_deny": default_subscribe_deny,
        "default_publish_client_receive_deny": default_receive_deny,
        "relay_exact_present": relay_exact_present,
        "relay_exact_entry_counts": relay_exact_entry_counts,
        "relay_exact_count": sum(relay_exact_entry_counts.values()),
        "relay_subscribe_broad_allow_count": relay_subscribe_broad_count,
        "relay_receive_broad_allow_count": relay_receive_broad_count,
        "relay_unsubscribe_broad_allow_count": relay_unsubscribe_broad_count,
        "direct_contract_ok": direct_contract_ok,
        "defect": defect,
        "exact_repaired_contract": exact_repaired_contract,
    }


def require_exact_repaired_poststate(analysis: dict[str, Any]) -> None:
    if not analysis.get("exact_repaired_contract"):
        raise StopExecution(
            "T1_DYNSEC_POSTCHECK",
            "live DynSec poststate is not the exact least-privilege repaired contract",
        )


def runtime_fingerprint(item: dict[str, Any]) -> dict[str, Any]:
    config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
    state = item.get("State") if isinstance(item.get("State"), dict) else {}
    return {
        "id": item.get("Id"),
        "image": config.get("Image"),
        "restart_count": item.get("RestartCount"),
        "started_at": state.get("StartedAt"),
        "running": state.get("Running"),
    }


def require_runtime_stable(
    before_manager: dict[str, Any],
    before_broker: dict[str, Any],
    after_items: list[dict[str, Any]],
) -> dict[str, bool]:
    manager, broker = bind_runtime(after_items)
    before_manager_fp = runtime_fingerprint(before_manager)
    before_broker_fp = runtime_fingerprint(before_broker)
    after_manager_fp = runtime_fingerprint(manager)
    after_broker_fp = runtime_fingerprint(broker)
    manager_stable = (
        after_manager_fp["id"] == before_manager_fp["id"]
        and after_manager_fp["image"] == before_manager_fp["image"]
        and after_manager_fp["restart_count"] == before_manager_fp["restart_count"]
        and after_manager_fp["started_at"] == before_manager_fp["started_at"]
        and after_manager_fp["running"] is True
    )
    broker_stable = (
        after_broker_fp["id"] == before_broker_fp["id"]
        and after_broker_fp["image"] == before_broker_fp["image"]
        and after_broker_fp["restart_count"] == before_broker_fp["restart_count"]
        and after_broker_fp["started_at"] == before_broker_fp["started_at"]
        and after_broker_fp["running"] is True
    )
    if not manager_stable or not broker_stable:
        raise StopExecution(
            "T1_RUNTIME_POSTCHECK",
            "Manager or Broker runtime identity/restart state changed",
        )
    return {
        "manager_runtime_stable": manager_stable,
        "broker_runtime_stable": broker_stable,
    }


def mutator_command(
    manager_id: str,
    python_path: str,
    action: str,
    role_name: str,
    acl_type: str,
    topic: str,
) -> str:
    return " ".join(
        [
            "docker",
            "exec",
            "-i",
            shlex.quote(manager_id),
            shlex.quote(python_path),
            "-",
            shlex.quote(action),
            shlex.quote(role_name),
            shlex.quote(acl_type),
            shlex.quote(topic),
        ]
    )


def mutator_result_ok(result: tuple[int, str, str]) -> bool:
    return_code, stdout, _stderr = result
    if return_code != 0:
        return False
    try:
        value = json.loads(stdout.strip())
    except Exception:
        return False
    return (
        isinstance(value, dict)
        and value.get("result") == "PASS"
        and value.get("response_error") is False
    )


def read_live_dynsec(
    root: Path,
    index: int,
    name: str,
    target: str,
    broker_id: str,
    path: str,
) -> str:
    return require_ok(
        ssh_op(
            root,
            index,
            name,
            target,
            f"docker exec {shlex.quote(broker_id)} cat {shlex.quote(path)}",
        ),
        "T1_DYNSEC_STATE",
        "cannot read live Dynamic Security state",
    )


def save_prechange_snapshot(root: Path, raw: str) -> str:
    snapshot_path = root / "prechange_dynamic_security_private.json"
    snapshot_path.write_text(raw, encoding="utf-8")
    digest = sha256_text(raw)
    dump(
        root / "prechange_dynamic_security_authority_private.json",
        {
            "sha256": digest,
            "utf8_bytes": len(raw.encode("utf-8")),
            "snapshot_file": snapshot_path.name,
        },
    )
    return digest


def rollback_target_acls(
    *,
    root: Path,
    next_op: int,
    target: str,
    manager_id: str,
    python_path: str,
    role_name: str,
    topic: str,
    mutator_bytes: bytes,
    broker_id: str,
    dynsec_state_path: str,
    runtime_env: dict[str, str],
) -> tuple[int, bool, str]:
    failures = 0
    for acl_type in TARGET_ACL_TYPES:
        result = ssh_op(
            root,
            next_op,
            f"rollback_remove_{acl_type}",
            target,
            mutator_command(
                manager_id,
                python_path,
                "remove",
                role_name,
                acl_type,
                topic,
            ),
            input_bytes=mutator_bytes,
        )
        next_op += 1
        if not mutator_result_ok(result):
            failures += 1

    try:
        rollback_raw = read_live_dynsec(
            root,
            next_op,
            "rollback_broker_dynamic_security_json",
            target,
            broker_id,
            dynsec_state_path,
        )
        next_op += 1
        rollback = analyze_dynsec(
            rollback_raw,
            runtime_env,
            require_defect=True,
        )
        restored = rollback["defect"] is True
    except Exception as exc:
        return next_op, False, f"rollback verification failed: {type(exc).__name__}: {exc}"

    if not restored:
        return next_op, False, "rollback state did not restore proven prestate defect"
    # Live readback is the rollback authority. A removeRoleACL response can be
    # non-PASS when the target ACL was never committed; that is benign if the
    # authoritative post-rollback state exactly matches the proven prestate.
    return next_op, True, (
        "" if failures == 0 else
        f"prestate restored despite {failures} non-PASS remove responses"
    )


def self_check() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("gate_id") != "id24_manager_relay_dynsec_acl_repair":
        raise SystemExit("manifest gate mismatch")
    if (
        manifest.get("authority_references", {}).get(
            "repaired_service_identity_plan_blob"
        )
        != REPAIRED_SERVICE_PLAN_BLOB
    ):
        raise SystemExit("repaired source blob mismatch")
    source_contract_check()
    remote = REMOTE_MUTATOR_PATH.read_text(encoding="utf-8")
    if not all(token in remote for token in ("addRoleACL", "removeRoleACL")):
        raise SystemExit("remote mutator command contract missing")
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
        "board_a_physical_access": False,
        "board_b_physical_access": False,
        "controlled_rf_experiment": False,
        "dynsec_mutation": False,
        "manager_restart": False,
        "broker_restart": False,
        "mqtt_test_publish": False,
        "application_topic_subscriber": False,
        "source_contract_repaired": False,
        "live_prestate_defect_proven": False,
        "prechange_dynsec_snapshot_sha256_recorded": False,
        "target_acl_add_success_count": 0,
        "poststate_exact_relay_acl_count": 0,
        "poststate_exact_contract_proven": False,
        "rollback_attempted": False,
        "rollback_result": "NOT_NEEDED",
        "repair_result": "STOP",
        "first_failed_operation": None,
        "stop_reason": None,
        "kf089_end_to_end_relay_telemetry": "NOT_PROVEN",
        "next_route": "STOP_RETURN_TO_HIGH_LEVEL_MODEL",
    }

    mutator_bytes = b""
    manager: dict[str, Any] | None = None
    broker: dict[str, Any] | None = None
    runtime_env: dict[str, str] | None = None
    target_context: dict[str, Any] | None = None
    dynsec_state_path = ""
    manager_id = ""
    broker_id = ""
    python_path = ""
    next_op = 1
    mutation_started = False
    mutation_completed = False

    try:
        validate_target(args.t1_ssh_target)
        validate_output_root(root)
        head = git_text(["rev-parse", "HEAD"])
        if head != args.expected_package_commit:
            raise StopExecution(
                "HOST_PREFLIGHT",
                f"HEAD {head} != expected package commit",
            )
        if git_text(["status", "--porcelain", "--untracked-files=no"]):
            raise StopExecution(
                "HOST_PREFLIGHT",
                "tracked worktree is dirty",
            )
        source_blobs = source_contract_check()
        closure["source_contract_repaired"] = True
        mutator_bytes = REMOTE_MUTATOR_PATH.read_bytes()
        dump(
            root / "host_preflight_private.json",
            {"head": head, "source_blobs": source_blobs},
        )
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

        ids_raw = require_ok(
            ssh_op(
                root,
                next_op,
                "preclaim_t1_container_ids",
                args.t1_ssh_target,
                "docker ps -aq --no-trunc",
            ),
            "T1_RUNTIME_PRECLAIM",
            "cannot enumerate T1 containers",
        )
        next_op += 1
        ids = [line.strip() for line in ids_raw.splitlines() if line.strip()]
        if not ids:
            raise StopExecution(
                "T1_RUNTIME_PRECLAIM",
                "T1 container inventory is empty",
            )

        inspect_raw = require_ok(
            ssh_op(
                root,
                next_op,
                "preclaim_t1_container_inspect",
                args.t1_ssh_target,
                "docker inspect " + " ".join(shlex.quote(value) for value in ids),
            ),
            "T1_RUNTIME_PRECLAIM",
            "cannot inspect T1 containers",
        )
        next_op += 1
        items = parse_inventory(inspect_raw)
        manager, broker = bind_runtime(items)
        runtime_env = env_map(manager)
        manager_id = str(manager.get("Id") or "")
        broker_id = str(broker.get("Id") or "")
        if not manager_id or not broker_id:
            raise StopExecution(
                "T1_RUNTIME_PRECLAIM",
                "bound Manager or Broker container id is missing",
            )

        conf = require_ok(
            ssh_op(
                root,
                next_op,
                "preclaim_broker_mosquitto_conf",
                args.t1_ssh_target,
                f"docker exec {shlex.quote(broker_id)} "
                "sh -c 'cat /mosquitto/config/mosquitto.conf'",
            ),
            "T1_DYNSEC_CONFIG",
            "cannot read mosquitto.conf",
        )
        next_op += 1
        dynsec_state_path = dynsec_path(conf)

        prestate_raw = read_live_dynsec(
            root,
            next_op,
            "preclaim_broker_dynamic_security_json",
            args.t1_ssh_target,
            broker_id,
            dynsec_state_path,
        )
        next_op += 1
        target_context = analyze_dynsec(
            prestate_raw,
            runtime_env,
            require_defect=True,
        )
        closure["live_prestate_defect_proven"] = True
        digest = save_prechange_snapshot(root, prestate_raw)
        closure["prechange_dynsec_snapshot_sha256_recorded"] = bool(digest)
        dump(root / "prestate_analysis_private.json", target_context)

        required_env = (
            "GH_N3W_PROVISIONING_USERNAME",
            "GH_N3W_PROVISIONING_PASSWORD_FILE",
            "GH_N3W_PROVISIONING_CLIENT_ID",
            "GH_MQTT_HOST",
            "GH_MQTT_PORT",
        )
        if any(not runtime_env.get(key) for key in required_env):
            raise StopExecution(
                "T1_PROVISIONING_PRECLAIM",
                "runtime provisioning identity or Broker endpoint is incomplete",
            )
        tls = (runtime_env.get("GH_MQTT_TLS") or "").strip().lower()
        if tls in {"1", "true", "yes", "on"} and not runtime_env.get(
            "GH_MQTT_CA_FILE"
        ):
            raise StopExecution(
                "T1_PROVISIONING_PRECLAIM",
                "TLS provisioning path lacks GH_MQTT_CA_FILE",
            )

        python_raw = require_ok(
            ssh_op(
                root,
                next_op,
                "preclaim_manager_python",
                args.t1_ssh_target,
                f"docker exec {shlex.quote(manager_id)} "
                "sh -c 'command -v python3 || command -v python'",
            ),
            "T1_PROVISIONING_PRECLAIM",
            "Manager Python runtime is unavailable",
        )
        next_op += 1
        python_path = python_raw.strip().splitlines()[0] if python_raw.strip() else ""
        if not python_path.startswith("/"):
            raise StopExecution(
                "T1_PROVISIONING_PRECLAIM",
                "Manager Python runtime path is invalid",
            )

        preflight = ssh_op(
            root,
            next_op,
            "preclaim_remote_mutator",
            args.t1_ssh_target,
            mutator_command(
                manager_id,
                python_path,
                "preflight",
                target_context["role_name"],
                TARGET_ACL_TYPES[0],
                target_context["relay_topic"],
            ),
            input_bytes=mutator_bytes,
        )
        next_op += 1
        if not mutator_result_ok(preflight):
            raise StopExecution(
                "T1_PROVISIONING_PRECLAIM",
                "in-container provisioning transport preflight failed",
            )

        mutation_started = True
        for acl_type in TARGET_ACL_TYPES:
            result = ssh_op(
                root,
                next_op,
                f"mutate_add_{acl_type}",
                args.t1_ssh_target,
                mutator_command(
                    manager_id,
                    python_path,
                    "add",
                    target_context["role_name"],
                    acl_type,
                    target_context["relay_topic"],
                ),
                input_bytes=mutator_bytes,
            )
            next_op += 1
            closure["dynsec_mutation"] = True
            if not mutator_result_ok(result):
                raise StopExecution(
                    "T1_DYNSEC_MUTATION",
                    f"addRoleACL failed or response was uncertain for {acl_type}",
                )
            closure["target_acl_add_success_count"] += 1

        post_raw = read_live_dynsec(
            root,
            next_op,
            "postmutation_broker_dynamic_security_json",
            args.t1_ssh_target,
            broker_id,
            dynsec_state_path,
        )
        next_op += 1
        post = analyze_dynsec(
            post_raw,
            runtime_env,
            require_defect=False,
        )
        closure["poststate_exact_relay_acl_count"] = post["relay_exact_count"]
        require_exact_repaired_poststate(post)
        closure["poststate_exact_contract_proven"] = True

        ids_after_raw = require_ok(
            ssh_op(
                root,
                next_op,
                "postcheck_t1_container_ids",
                args.t1_ssh_target,
                "docker ps -aq --no-trunc",
            ),
            "T1_RUNTIME_POSTCHECK",
            "cannot enumerate T1 containers after repair",
        )
        next_op += 1
        ids_after = [line.strip() for line in ids_after_raw.splitlines() if line.strip()]
        inspect_after_raw = require_ok(
            ssh_op(
                root,
                next_op,
                "postcheck_t1_container_inspect",
                args.t1_ssh_target,
                "docker inspect " + " ".join(shlex.quote(value) for value in ids_after),
            ),
            "T1_RUNTIME_POSTCHECK",
            "cannot inspect T1 containers after repair",
        )
        next_op += 1
        stability = require_runtime_stable(
            manager,
            broker,
            parse_inventory(inspect_after_raw),
        )
        closure.update(stability)

        mutation_completed = True
        closure["repair_result"] = "PASS"
        closure["next_route"] = (
            "PREPARE_KF089_MANAGER_RELAY_SUBSCRIPTION_REACTIVATION_PACKAGE"
        )

    except StopExecution as exc:
        closure["first_failed_operation"] = exc.operation
        closure["stop_reason"] = exc.reason
    except Exception as exc:
        closure["first_failed_operation"] = "UNEXPECTED_EXCEPTION"
        closure["stop_reason"] = f"{type(exc).__name__}: {exc}"

    if (
        mutation_started
        and not mutation_completed
        and target_context is not None
        and runtime_env is not None
        and manager_id
        and broker_id
        and python_path
        and dynsec_state_path
        and mutator_bytes
    ):
        closure["rollback_attempted"] = True
        try:
            next_op, rollback_ok, rollback_reason = rollback_target_acls(
                root=root,
                next_op=next_op,
                target=args.t1_ssh_target,
                manager_id=manager_id,
                python_path=python_path,
                role_name=target_context["role_name"],
                topic=target_context["relay_topic"],
                mutator_bytes=mutator_bytes,
                broker_id=broker_id,
                dynsec_state_path=dynsec_state_path,
                runtime_env=runtime_env,
            )
        except Exception as exc:
            rollback_ok = False
            rollback_reason = f"{type(exc).__name__}: {exc}"
        closure["rollback_result"] = "PASS" if rollback_ok else "FAIL"
        if not rollback_ok:
            original = closure.get("stop_reason") or "mutation failed"
            closure["first_failed_operation"] = "T1_DYNSEC_ROLLBACK"
            closure["stop_reason"] = (
                f"{original}; rollback incomplete: {rollback_reason}"
            )
        else:
            original = closure.get("stop_reason") or "mutation did not complete"
            closure["stop_reason"] = f"{original}; exact prestate restored"

    if root.exists():
        dump(root / "closure.json", closure)
    print(json.dumps(closure, sort_keys=True))
    return 0 if closure["repair_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
