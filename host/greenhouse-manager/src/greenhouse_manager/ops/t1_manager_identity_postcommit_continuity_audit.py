from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

SCHEMA = "gh.m2.t1-manager-identity-postcommit-continuity-audit/1"
_JOURNAL_SCHEMA = "gh.m2.t1-manager-identity-production-journal/1"
_EXECUTION_SCHEMAS = {
    "gh.m2.t1-manager-identity-production-execution-packet/1",
    "gh.m2.t1-manager-target-production-execution/1",
}
_TARGET = "greenhouse-manager"
_PROTECTED_SERVICES = ("mosquitto", "homeassistant")
_SERVICES = (_TARGET, *_PROTECTED_SERVICES)
_PASSWORD_MOUNT = "/run/secrets/gh_manager_mqtt_password"
_MAX_PRIVATE_FILES = 256
_MAX_PRIVATE_BYTES = 64 * 1024 * 1024


class ManagerPostcommitContinuityAuditError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def run(self, command: Sequence[str]) -> tuple[int, str]: ...


class SubprocessRunner:
    def run(self, command: Sequence[str]) -> tuple[int, str]:
        import subprocess

        completed = subprocess.run(
            tuple(command),
            check=False,
            capture_output=True,
            text=True,
        )
        output = completed.stdout if completed.stdout else completed.stderr
        return completed.returncode, output


def _parse_time(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ManagerPostcommitContinuityAuditError(f"{label} is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ManagerPostcommitContinuityAuditError(f"{label} is invalid") from error
    if parsed.tzinfo is None:
        raise ManagerPostcommitContinuityAuditError(f"{label} has no timezone")
    return parsed.astimezone(UTC)


def _private_directory(path: Path, label: str) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ManagerPostcommitContinuityAuditError(f"{label} is missing or unsafe")
    resolved = expanded.resolve()
    if (
        not resolved.is_dir()
        or resolved.is_symlink()
        or resolved.stat().st_mode & 0o077
    ):
        raise ManagerPostcommitContinuityAuditError(f"{label} is missing or unsafe")
    return resolved


def _private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
        or path.stat().st_size > 1024 * 1024
    ):
        raise ManagerPostcommitContinuityAuditError(f"{label} is missing or unsafe")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerPostcommitContinuityAuditError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerPostcommitContinuityAuditError(f"{label} must be an object")
    return document


def _workspace_digest(root: Path) -> str:
    digest = hashlib.sha256()
    count = 0
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ManagerPostcommitContinuityAuditError(
                "transaction workspace contains a symlink"
            )
        relative = path.relative_to(root).as_posix()
        metadata = path.stat()
        if path.is_dir():
            digest.update(f"D\0{relative}\0{metadata.st_mode & 0o777:o}\0".encode())
            continue
        if not path.is_file():
            raise ManagerPostcommitContinuityAuditError(
                "transaction workspace contains a special file"
            )
        count += 1
        total += metadata.st_size
        if count > _MAX_PRIVATE_FILES or total > _MAX_PRIVATE_BYTES:
            raise ManagerPostcommitContinuityAuditError(
                "transaction workspace inventory exceeds the audit bound"
            )
        digest.update(
            f"F\0{relative}\0{metadata.st_mode & 0o777:o}\0{metadata.st_size}\0".encode()
        )
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def _execution_result(workspace: Path, journal: Mapping[str, Any]) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for path in sorted(workspace.rglob("*.json")):
        if path.name == "journal.json" or path.is_symlink() or not path.is_file():
            continue
        if path.stat().st_mode & 0o077 or path.stat().st_size > 1024 * 1024:
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        schema = document.get("schema")
        looks_like_result = (
            schema in _EXECUTION_SCHEMAS
            or (
                document.get("production_execution_completed") is True
                and document.get("postactivation_verified") is True
                and document.get("manager_identity_migrated") is True
                and document.get("authorization_claimed") is True
                and document.get("authorization_consumed") is True
            )
        )
        if looks_like_result:
            matches.append(document)
    bound = [
        item
        for item in matches
        if item.get("transaction_id") == journal.get("transaction_id")
        and item.get("authorization_id") == journal.get("authorization_id")
    ]
    if len(bound) != 1:
        raise ManagerPostcommitContinuityAuditError(
            "exactly one bound production execution result is required"
        )
    return bound[0]


def _validate_transaction(
    journal: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> tuple[datetime, datetime]:
    required_journal = {
        "schema": _JOURNAL_SCHEMA,
        "phase": "committed",
        "target": _TARGET,
        "mosquitto_target_allowed": False,
        "homeassistant_target_allowed": False,
        "node_target_allowed": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    if any(journal.get(field) != expected for field, expected in required_journal.items()):
        raise ManagerPostcommitContinuityAuditError(
            "committed manager transaction journal binding is invalid"
        )
    required_execution = {
        "production_execution_completed": True,
        "postactivation_verified": True,
        "manager_identity_migrated": True,
        "greenhouse_manager_recreated": True,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    if any(
        execution.get(field) != expected
        for field, expected in required_execution.items()
    ):
        raise ManagerPostcommitContinuityAuditError(
            "manager production execution result is not a committed success"
        )
    image_preserved = execution.get("runtime_manager_image_preserved")
    if image_preserved is None:
        image_preserved = execution.get("greenhouse_manager_image_preserved")
    if image_preserved is not True:
        raise ManagerPostcommitContinuityAuditError(
            "manager runtime image preservation evidence is missing"
        )
    if execution.get("rollback_completed") not in {False, None}:
        raise ManagerPostcommitContinuityAuditError(
            "committed manager transaction unexpectedly records rollback"
        )
    created_at = _parse_time(journal.get("created_at"), "journal created_at")
    committed_at = _parse_time(journal.get("updated_at"), "journal updated_at")
    if committed_at < created_at:
        raise ManagerPostcommitContinuityAuditError(
            "manager transaction timestamps are contradictory"
        )
    return created_at, committed_at


def _inspect(runner: CommandRunner, name: str) -> dict[str, Any]:
    if name not in _SERVICES:
        raise ManagerPostcommitContinuityAuditError(
            "container inspection target is not allowed"
        )
    code, output = runner.run(("docker", "inspect", name))
    if code != 0:
        raise ManagerPostcommitContinuityAuditError(
            "required container is not inspectable"
        )
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise ManagerPostcommitContinuityAuditError(
            "container inspection returned invalid JSON"
        ) from error
    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
    ):
        raise ManagerPostcommitContinuityAuditError(
            "exactly one required container is expected"
        )
    document = documents[0]
    state = document.get("State")
    if (
        not isinstance(state, dict)
        or state.get("Status") != "running"
        or document.get("RestartCount") != 0
    ):
        raise ManagerPostcommitContinuityAuditError(
            "required container must be running with restart count zero"
        )
    return document


def _snapshot(runner: CommandRunner) -> dict[str, tuple[object, ...]]:
    result: dict[str, tuple[object, ...]] = {}
    for name in _SERVICES:
        document = _inspect(runner, name)
        state = document["State"]
        assert isinstance(state, dict)
        result[name] = (
            document.get("Id"),
            document.get("Image"),
            state.get("StartedAt"),
            document.get("RestartCount"),
            state.get("Status"),
        )
        if any(value in {None, ""} for value in result[name][:3]):
            raise ManagerPostcommitContinuityAuditError(
                "required container identity is incomplete"
            )
    return result


def _environment(document: Mapping[str, Any]) -> dict[str, str]:
    config = document.get("Config")
    raw = config.get("Env") if isinstance(config, Mapping) else None
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager environment metadata is invalid"
        )
    values: dict[str, str] = {}
    for item in raw:
        key, separator, value = item.partition("=")
        if separator:
            values[key] = value
    return values


def _process_identity(proc_root: Path, pid: int) -> tuple[int, int]:
    status_path = proc_root / str(pid) / "status"
    if not status_path.is_file() or status_path.is_symlink():
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager process identity is unavailable"
        )
    uid: int | None = None
    gid: int | None = None
    for line in status_path.read_text(encoding="ascii").splitlines():
        if line.startswith("Uid:"):
            fields = line.split()
            if len(fields) >= 3:
                uid = int(fields[2])
        elif line.startswith("Gid:"):
            fields = line.split()
            if len(fields) >= 3:
                gid = int(fields[2])
    if uid is None or gid is None:
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager process identity is invalid"
        )
    return uid, gid


def _validate_manager_identity(
    document: Mapping[str, Any],
    *,
    proc_root: Path,
) -> int:
    values = _environment(document)
    if (
        not values.get("GH_MQTT_USERNAME")
        or not values.get("GH_MQTT_CLIENT_ID")
        or values.get("GH_MQTT_PASSWORD_FILE") != _PASSWORD_MOUNT
        or bool(values.get("GH_MQTT_PASSWORD", ""))
    ):
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager authenticated environment is incomplete or unsafe"
        )
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager mount inventory is missing"
        )
    matching = [
        item
        for item in mounts
        if isinstance(item, Mapping)
        and item.get("Destination") == _PASSWORD_MOUNT
        and item.get("RW") is False
        and isinstance(item.get("Source"), str)
    ]
    if len(matching) != 1:
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager password mount binding is invalid"
        )
    source = Path(str(matching[0]["Source"]))
    if (
        not source.is_absolute()
        or source.is_symlink()
        or not source.is_file()
        or stat.S_IMODE(source.stat().st_mode) != 0o600
    ):
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager password source is missing or unsafe"
        )
    state = document.get("State")
    pid = state.get("Pid") if isinstance(state, Mapping) else None
    if not isinstance(pid, int) or pid <= 0:
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager process ID is invalid"
        )
    uid, gid = _process_identity(proc_root, pid)
    metadata = source.stat()
    if metadata.st_uid != uid or metadata.st_gid != gid:
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager password ownership drifted"
        )
    return pid


def _socket_inodes(proc_root: Path, pid: int, mqtt_port: int) -> set[str]:
    observed: set[str] = set()
    for name in ("tcp", "tcp6"):
        path = proc_root / str(pid) / "net" / name
        if not path.is_file() or path.is_symlink():
            continue
        for line in path.read_text(encoding="ascii").splitlines()[1:]:
            fields = line.split()
            if len(fields) < 10 or fields[3] != "01" or ":" not in fields[2]:
                continue
            try:
                port = int(fields[2].rsplit(":", 1)[1], 16)
            except ValueError:
                continue
            if port == mqtt_port:
                observed.add(fields[9])
    return observed


def _stable_socket(
    proc_root: Path,
    pid: int,
    mqtt_port: int,
    *,
    timeout_s: float,
    poll_interval_s: float,
) -> bool:
    deadline = time.monotonic() + timeout_s
    while True:
        first = _socket_inodes(proc_root, pid, mqtt_port)
        remaining = deadline - time.monotonic()
        if first and remaining > 0:
            time.sleep(min(poll_interval_s, 2.0, remaining))
            if first & _socket_inodes(proc_root, pid, mqtt_port):
                return True
        elif remaining > 0:
            time.sleep(min(poll_interval_s, remaining))
        if time.monotonic() >= deadline:
            return False


def _retained(
    runner: CommandRunner,
    topic: str,
    *,
    timeout_s: float,
) -> dict[str, Any]:
    if (
        not (topic.startswith("gh/") or topic.startswith("homeassistant/"))
        or "+" in topic
        or "#" in topic
    ):
        raise ValueError("retained topic is outside the exact allowed namespaces")
    code, output = runner.run(
        (
            "docker",
            "exec",
            "mosquitto",
            "mosquitto_sub",
            "-h",
            "127.0.0.1",
            "-V",
            "5",
            "-C",
            "1",
            "-W",
            str(max(1, min(30, int(timeout_s)))),
            "-F",
            "%p",
            "-t",
            topic,
        )
    )
    if code != 0 or not output.strip():
        raise ManagerPostcommitContinuityAuditError(
            "anonymous retained compatibility read failed"
        )
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise ManagerPostcommitContinuityAuditError(
            "retained compatibility payload is invalid"
        ) from error
    if not isinstance(document, dict):
        raise ManagerPostcommitContinuityAuditError(
            "retained compatibility payload must be an object"
        )
    return document


def _validate_retained(
    canonical: Mapping[str, Any],
    availability: Mapping[str, Any],
    discovery: Mapping[str, Any],
    *,
    system_id: str,
    node_id: str,
) -> None:
    canonical_topic = f"gh/v1/{system_id}/state/{node_id}/telemetry"
    availability_topic = f"gh/v1/{system_id}/state/{node_id}/availability"
    if canonical.get("node_id") != node_id:
        raise ManagerPostcommitContinuityAuditError(
            "canonical retained node identity changed"
        )
    if (
        availability.get("node_id") != node_id
        or availability.get("state") not in {"online", "unavailable"}
    ):
        raise ManagerPostcommitContinuityAuditError(
            "availability retained state is invalid"
        )
    device = discovery.get("device")
    identifiers = device.get("identifiers") if isinstance(device, Mapping) else None
    components = discovery.get("components")
    if (
        not isinstance(identifiers, list)
        or not any(isinstance(item, str) and node_id in item for item in identifiers)
        or not isinstance(components, Mapping)
        or not components
        or discovery.get("state_topic") != canonical_topic
    ):
        raise ManagerPostcommitContinuityAuditError(
            "Home Assistant Discovery identity continuity failed"
        )
    availability_entries = discovery.get("availability")
    if not isinstance(availability_entries, list) or not any(
        isinstance(item, Mapping) and item.get("topic") == availability_topic
        for item in availability_entries
    ):
        raise ManagerPostcommitContinuityAuditError(
            "Home Assistant Discovery availability binding changed"
        )
    unique_ids = [
        component.get("unique_id")
        for component in components.values()
        if isinstance(component, Mapping)
    ]
    if (
        len(unique_ids) != len(components)
        or any(not isinstance(item, str) or node_id not in item for item in unique_ids)
    ):
        raise ManagerPostcommitContinuityAuditError(
            "Home Assistant entity identity continuity failed"
        )


def _validate_logs(
    runner: CommandRunner,
    *,
    started_at: str,
    system_id: str,
    node_id: str,
    discovery_topic: str,
) -> None:
    code, output = runner.run(
        ("docker", "logs", "--since", started_at, "greenhouse-manager")
    )
    if code != 0:
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager runtime log evidence is unavailable"
        )
    required = (
        f"Subscribed to gh/v1/{system_id}/ingress/node/+/telemetry",
        f"Subscribed to gh/v1/{system_id}/state/+/telemetry",
        f"Published Home Assistant discovery node={node_id} topic={discovery_topic}",
    )
    if any(marker not in output for marker in required):
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager runtime continuity log evidence is incomplete"
        )
    if (
        f"Accepted telemetry node={node_id} " not in output
        and f"Recovered retained canonical node={node_id} " not in output
        and f"Published Home Assistant discovery node={node_id} " not in output
    ):
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager canonical continuity evidence is incomplete"
        )


def build_manager_identity_postcommit_continuity_audit(
    transaction_workspace: str | Path,
    *,
    system_id: str,
    node_id: str,
    discovery_topic: str,
    mqtt_port: int = 1883,
    timeout_s: float = 8.0,
    poll_interval_s: float = 1.0,
    proc_root: str | Path = "/proc",
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    if (
        not system_id
        or not node_id
        or not discovery_topic.startswith("homeassistant/")
        or "+" in discovery_topic
        or "#" in discovery_topic
        or not 1 <= mqtt_port <= 65535
        or timeout_s <= 0
        or poll_interval_s <= 0
    ):
        raise ValueError("postcommit continuity audit inputs are invalid")

    workspace = _private_directory(
        Path(transaction_workspace),
        "manager production transaction workspace",
    )
    before_digest = _workspace_digest(workspace)
    journal = _private_json(workspace / "journal.json", "manager transaction journal")
    execution = _execution_result(workspace, journal)
    created_at, committed_at = _validate_transaction(journal, execution)

    command_runner = runner or SubprocessRunner()
    before_runtime = _snapshot(command_runner)
    manager = _inspect(command_runner, _TARGET)
    state = manager["State"]
    assert isinstance(state, dict)
    manager_started = _parse_time(state.get("StartedAt"), "manager started_at")
    if manager_started < created_at or manager_started > committed_at:
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager was not preserved from the committed transaction"
        )
    for name in _PROTECTED_SERVICES:
        started = _parse_time(
            before_runtime[name][2],
            f"{name} started_at",
        )
        if started > created_at:
            raise ManagerPostcommitContinuityAuditError(
                "a protected service changed after the manager transaction began"
            )

    pid = _validate_manager_identity(manager, proc_root=Path(proc_root))
    if not _stable_socket(
        Path(proc_root),
        pid,
        mqtt_port,
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    ):
        raise ManagerPostcommitContinuityAuditError(
            "greenhouse-manager MQTT socket is not stable"
        )

    canonical_topic = f"gh/v1/{system_id}/state/{node_id}/telemetry"
    availability_topic = f"gh/v1/{system_id}/state/{node_id}/availability"
    canonical = _retained(command_runner, canonical_topic, timeout_s=timeout_s)
    availability = _retained(command_runner, availability_topic, timeout_s=timeout_s)
    discovery = _retained(command_runner, discovery_topic, timeout_s=timeout_s)
    _validate_retained(
        canonical,
        availability,
        discovery,
        system_id=system_id,
        node_id=node_id,
    )
    _validate_logs(
        command_runner,
        started_at=str(state["StartedAt"]),
        system_id=system_id,
        node_id=node_id,
        discovery_topic=discovery_topic,
    )

    after_runtime = _snapshot(command_runner)
    after_digest = _workspace_digest(workspace)
    if after_runtime != before_runtime:
        raise ManagerPostcommitContinuityAuditError(
            "a protected service changed during the read-only audit"
        )
    if after_digest != before_digest:
        raise ManagerPostcommitContinuityAuditError(
            "transaction files changed during the read-only audit"
        )

    checks = {
        "transaction_committed": True,
        "execution_result_bound": True,
        "manager_running_zero_restart": True,
        "manager_container_preserved_since_commit": True,
        "manager_authenticated_environment_present": True,
        "manager_password_mount_read_only": True,
        "manager_password_source_private": True,
        "manager_password_ownership_bound": True,
        "manager_mqtt_socket_stable": True,
        "ingress_subscription_continuous": True,
        "canonical_retained_continuous": True,
        "availability_retained_continuous": True,
        "discovery_retained_continuous": True,
        "existing_entity_identity_continuous": True,
        "anonymous_retained_compatibility_present": True,
        "mosquitto_unchanged": True,
        "homeassistant_unchanged": True,
        "protected_services_stable_during_audit": True,
        "transaction_files_unchanged_during_audit": True,
    }
    return {
        "schema": SCHEMA,
        "status": "manager_identity_postcommit_continuity_audit_succeeded",
        "read_only": True,
        "continuity_audit_passed": all(checks.values()),
        "checks": checks,
        "transaction_phase": "committed",
        "transaction_terminal": True,
        "execution_committed": True,
        "production_execution_completed": True,
        "postactivation_verified": True,
        "manager_identity_migrated": True,
        "greenhouse_manager_recreated": True,
        "runtime_manager_image_preserved": True,
        "runtime_manager_upgrade_performed": False,
        "rollback_completed": False,
        "rollback_failed": False,
        "mosquitto_modified": False,
        "homeassistant_modified": False,
        "nodes_modified": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "current_services_modified": False,
        "transaction_files_modified": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "authorization_reused": False,
        "production_execution_invoked": False,
        "manual_recovery_required": False,
        "ready_for_broker_preactivation_fresh_evidence": True,
        "secret_values_included": False,
        "path_values_redacted": True,
        "container_ids_included": False,
        "image_ids_included": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only continuity audit for a committed greenhouse-manager "
            "MQTT identity migration."
        )
    )
    parser.add_argument("transaction_workspace")
    parser.add_argument("--system-id", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--discovery-topic", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = build_manager_identity_postcommit_continuity_audit(
            args.transaction_workspace,
            system_id=args.system_id,
            node_id=args.node_id,
            discovery_topic=args.discovery_topic,
            mqtt_port=args.mqtt_port,
            timeout_s=args.timeout_seconds,
            poll_interval_s=args.poll_interval_seconds,
        )
    except (ManagerPostcommitContinuityAuditError, OSError, UnicodeError, ValueError):
        print(
            "T1 manager postcommit continuity audit failed safely",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if report["continuity_audit_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
