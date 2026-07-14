from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .t1_migration_readiness import CommandRunner, SubprocessRunner

SCHEMA = "gh.m2.t1-manager-identity-postrollback-audit/1"
AUTHENTICATION_ENVIRONMENT_KEYS = (
    "GH_MQTT_USERNAME",
    "GH_MQTT_PASSWORD",
    "GH_MQTT_PASSWORD_FILE",
)
_JOURNAL_SCHEMA = "gh.m2.t1-manager-identity-production-journal/1"
_ROLLBACK_SCHEMA = "gh.m2.t1-manager-identity-fresh-rollback/1"
_AUTH_ENV_NAME = "manager-auth.env"
_OVERLAY_NAME = "docker-compose.manager-auth.yml"
_PASSWORD_MOUNT = "/run/secrets/gh_manager_mqtt_password"
_SERVICES = ("greenhouse-manager", "mosquitto", "homeassistant")

_REQUIRED_OBSERVATIONS: dict[str, object] = {
    "journal_phase": "rollback_completed",
    "rollback_completed": True,
    "rollback_failed": False,
    "auth_overlay_exists": False,
    "auth_environment_exists": False,
    "password_target_exists": False,
    "password_mount_count": 0,
    "manager_running": True,
    "manager_restart_count_zero": True,
    "manager_stable_mqtt_socket": True,
    "manager_image_preserved": True,
    "mosquitto_unchanged": True,
    "homeassistant_unchanged": True,
    "anonymous_retained_path_readable": True,
}

Sleeper = Callable[[float], None]
Clock = Callable[[], float]


class ManagerPostrollbackAuditError(RuntimeError):
    pass


def redacted_authentication_environment_state(
    environment: Mapping[str, str],
) -> dict[str, dict[str, bool]]:
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in environment.items()
    ):
        raise ManagerPostrollbackAuditError(
            "manager authentication environment input is invalid"
        )
    return {
        key: {
            "present": key in environment,
            "nonempty": bool(environment.get(key, "")),
        }
        for key in AUTHENTICATION_ENVIRONMENT_KEYS
    }


def validate_authentication_environment_state(
    state: Mapping[str, Any],
) -> dict[str, dict[str, bool]]:
    if set(state) != set(AUTHENTICATION_ENVIRONMENT_KEYS):
        raise ManagerPostrollbackAuditError(
            "manager authentication environment baseline is incomplete"
        )
    normalized: dict[str, dict[str, bool]] = {}
    for key in AUTHENTICATION_ENVIRONMENT_KEYS:
        item = state.get(key)
        if not isinstance(item, Mapping):
            raise ManagerPostrollbackAuditError(
                "manager authentication environment state is invalid"
            )
        present = item.get("present")
        nonempty = item.get("nonempty")
        if not isinstance(present, bool) or not isinstance(nonempty, bool):
            raise ManagerPostrollbackAuditError(
                "manager authentication environment flags are invalid"
            )
        if nonempty and not present:
            raise ManagerPostrollbackAuditError(
                "manager authentication environment state is contradictory"
            )
        normalized[key] = {"present": present, "nonempty": nonempty}
    return normalized


def evaluate_manager_postrollback_audit(
    *,
    preclaim_environment: Mapping[str, Any] | None,
    current_environment: Mapping[str, Any],
    observations: Mapping[str, Any],
) -> dict[str, object]:
    current = validate_authentication_environment_state(current_environment)
    environment_baseline_unavailable = preclaim_environment is None
    baseline = (
        None
        if environment_baseline_unavailable
        else validate_authentication_environment_state(preclaim_environment)
    )
    environment_checks = {
        f"{key.lower()}_restored": (
            None if baseline is None else current[key] == baseline[key]
        )
        for key in AUTHENTICATION_ENVIRONMENT_KEYS
    }
    checks: dict[str, bool | None] = {
        name: observations.get(name) == expected
        for name, expected in _REQUIRED_OBSERVATIONS.items()
    }
    directory_state = observations.get(
        "created_directory_targets_cleanup_complete"
    )
    if directory_state is not None and not isinstance(directory_state, bool):
        raise ManagerPostrollbackAuditError(
            "created directory target observation is invalid"
        )
    directory_baseline_unavailable = directory_state is None
    checks["created_directory_targets_cleanup_complete"] = directory_state
    exact_target_checks = {
        "auth_overlay_removed": checks["auth_overlay_exists"],
        "auth_environment_removed": checks["auth_environment_exists"],
        "password_target_removed": checks["password_target_exists"],
        "password_mount_removed": checks["password_mount_count"],
        "created_directory_targets_clean": directory_state,
    }
    environment_restored = baseline is not None and all(
        value is True for value in environment_checks.values()
    )
    definite_failure = any(
        value is not True
        for name, value in checks.items()
        if name != "created_directory_targets_cleanup_complete"
    ) or directory_state is False
    if baseline is not None and any(
        value is not True for value in environment_checks.values()
    ):
        definite_failure = True
    baseline_unavailable = (
        environment_baseline_unavailable or directory_baseline_unavailable
    )
    audit_passed = (
        not baseline_unavailable
        and environment_restored
        and directory_state is True
        and not definite_failure
    )
    manual_recovery_required = definite_failure
    return {
        "schema": SCHEMA,
        "read_only": True,
        "rollback_audit_passed": audit_passed,
        "baseline_unavailable": baseline_unavailable,
        "environment_baseline_unavailable": environment_baseline_unavailable,
        "directory_baseline_unavailable": directory_baseline_unavailable,
        "baseline_required_for_pass": True,
        "manual_recovery_required": manual_recovery_required,
        "manual_review_required": not audit_passed and not manual_recovery_required,
        "environment_restored": environment_restored,
        "environment_checks": environment_checks,
        "checks": checks,
        "exact_target_checks": exact_target_checks,
        "broad_compose_directory_considered": False,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def _private_directory(path: Path, label: str) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ManagerPostrollbackAuditError(f"{label} is missing or unsafe")
    resolved = expanded.resolve()
    if (
        not resolved.is_dir()
        or resolved.is_symlink()
        or resolved.stat().st_mode & 0o077
    ):
        raise ManagerPostrollbackAuditError(f"{label} is missing or unsafe")
    return resolved


def _private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerPostrollbackAuditError(f"{label} is missing or unsafe")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerPostrollbackAuditError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerPostrollbackAuditError(f"{label} must be an object")
    return document


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _archived_rollback_manifest(path: Path) -> dict[str, Any]:
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = [
                item
                for item in archive.getmembers()
                if item.name == "rollback-manifest.json"
            ]
            if (
                len(members) != 1
                or not members[0].isfile()
                or members[0].size > 1024 * 1024
            ):
                raise ManagerPostrollbackAuditError(
                    "archived fresh rollback manifest is invalid"
                )
            stream = archive.extractfile(members[0])
            if stream is None:
                raise ManagerPostrollbackAuditError(
                    "archived fresh rollback manifest is unreadable"
                )
            document = json.loads(stream.read().decode("utf-8"))
    except (tarfile.TarError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerPostrollbackAuditError(
            "archived fresh rollback manifest is invalid"
        ) from error
    if not isinstance(document, dict):
        raise ManagerPostrollbackAuditError(
            "archived fresh rollback manifest must be an object"
        )
    return document


def _inspect(runner: CommandRunner, name: str) -> dict[str, Any]:
    if name not in _SERVICES:
        raise ManagerPostrollbackAuditError("container target is not allowed")
    code, output = runner.run(("docker", "inspect", name))
    if code != 0:
        raise ManagerPostrollbackAuditError("required container is not inspectable")
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise ManagerPostrollbackAuditError(
            "container inspection returned invalid JSON"
        ) from error
    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
    ):
        raise ManagerPostrollbackAuditError("exactly one container is required")
    return documents[0]


def _environment(document: Mapping[str, Any]) -> dict[str, str]:
    config = document.get("Config")
    raw = config.get("Env") if isinstance(config, Mapping) else None
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ManagerPostrollbackAuditError("manager environment is invalid")
    result: dict[str, str] = {}
    for item in raw:
        key, separator, value = item.partition("=")
        if separator:
            result[key] = value
    return result


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ManagerPostrollbackAuditError("container timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ManagerPostrollbackAuditError("container timestamp is invalid") from error
    if parsed.tzinfo is None:
        raise ManagerPostrollbackAuditError("container timestamp is invalid")
    return parsed.astimezone(UTC)


def _service_unchanged(document: Mapping[str, Any], transaction_at: datetime) -> bool:
    state = document.get("State")
    return bool(
        isinstance(state, Mapping)
        and state.get("Status") == "running"
        and document.get("RestartCount") == 0
        and _parse_timestamp(state.get("StartedAt")) <= transaction_at
    )


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
    timeout_s: float,
    poll_interval_s: float,
    sleeper: Sleeper,
    monotonic: Clock,
) -> bool:
    deadline = monotonic() + timeout_s
    while True:
        first = _socket_inodes(proc_root, pid, mqtt_port)
        remaining = deadline - monotonic()
        if first and remaining > 0:
            sleeper(min(poll_interval_s, 2.0, remaining))
            if first & _socket_inodes(proc_root, pid, mqtt_port):
                return True
        elif not first and remaining > 0:
            sleeper(min(poll_interval_s, remaining))
        if monotonic() >= deadline:
            return False


def _anonymous_retained(
    runner: CommandRunner,
    topic: str,
    timeout_s: float,
) -> bool:
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
    return code == 0 and bool(output.strip())


def _target_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _created_directories_clean(
    rollback: Mapping[str, Any],
    secret_root: Path,
) -> bool | None:
    raw = rollback.get("created_directory_targets")
    if raw is None:
        return None
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ManagerPostrollbackAuditError(
            "created directory target baseline is invalid"
        )
    targets: list[Path] = []
    for item in raw:
        target = Path(item).expanduser()
        if not target.is_absolute():
            raise ManagerPostrollbackAuditError(
                "created directory target baseline is unsafe"
            )
        if target.is_symlink():
            return False
        resolved = target.resolve(strict=False)
        if resolved != secret_root and not resolved.is_relative_to(secret_root):
            raise ManagerPostrollbackAuditError(
                "created directory target escaped the secret root"
            )
        targets.append(resolved)
    if len(set(targets)) != len(targets):
        raise ManagerPostrollbackAuditError(
            "created directory target baseline contains duplicates"
        )
    return not any(_target_exists(path) for path in targets)


def build_manager_postrollback_audit(
    transaction_workspace: str | Path,
    execution_preparation_directory: str | Path,
    *,
    expected_retained_topic: str,
    mqtt_port: int = 1883,
    timeout_s: float = 8.0,
    poll_interval_s: float = 1.0,
    proc_root: str | Path = "/proc",
    runner: CommandRunner | None = None,
    sleeper: Sleeper = time.sleep,
    monotonic: Clock = time.monotonic,
) -> dict[str, object]:
    if (
        not expected_retained_topic.startswith("gh/")
        or "+" in expected_retained_topic
        or "#" in expected_retained_topic
    ):
        raise ValueError("expected retained topic must be an exact gh topic")
    if not 1 <= mqtt_port <= 65535 or timeout_s <= 0 or poll_interval_s <= 0:
        raise ValueError("postrollback audit timing or port is invalid")
    workspace = _private_directory(
        Path(transaction_workspace),
        "manager production transaction workspace",
    )
    execution = _private_directory(
        Path(execution_preparation_directory),
        "manager execution preparation directory",
    )
    journal = _private_json(workspace / "journal.json", "manager journal")
    rollback = _private_json(
        execution / "fresh-rollback-manifest.json",
        "fresh rollback manifest",
    )
    if (
        journal.get("schema") != _JOURNAL_SCHEMA
        or journal.get("target") != "greenhouse-manager"
        or journal.get("preserve_anonymous") is not True
        or journal.get("anonymous_closure_enabled") is not False
    ):
        raise ManagerPostrollbackAuditError("manager journal binding is invalid")
    if (
        rollback.get("schema") != _ROLLBACK_SCHEMA
        or rollback.get("manager_only") is not True
        or rollback.get("preserve_anonymous") is not True
        or rollback.get("anonymous_closure_enabled") is not False
    ):
        raise ManagerPostrollbackAuditError("fresh rollback binding is invalid")
    archive = execution / "fresh-manager-rollback.tar.gz"
    if (
        not archive.is_file()
        or archive.is_symlink()
        or archive.stat().st_mode & 0o777 != 0o600
        or journal.get("fresh_rollback_archive_sha256") != _sha256(archive)
        or rollback != _archived_rollback_manifest(archive)
    ):
        raise ManagerPostrollbackAuditError("fresh rollback archive binding is invalid")

    working_dir = Path(str(rollback.get("compose_working_directory", ""))).expanduser()
    secret_root = Path(str(rollback.get("manager_secret_root", ""))).expanduser()
    password_target = Path(
        str(rollback.get("manager_password_target", ""))
    ).expanduser()
    if (
        not working_dir.is_absolute()
        or working_dir.is_symlink()
        or not secret_root.is_absolute()
        or secret_root.is_symlink()
        or not password_target.is_absolute()
        or password_target.is_symlink()
    ):
        raise ManagerPostrollbackAuditError("fresh rollback path binding is unsafe")
    working_dir = working_dir.resolve(strict=False)
    secret_root = secret_root.resolve(strict=False)
    password_target = password_target.resolve(strict=False)
    if not password_target.is_relative_to(secret_root):
        raise ManagerPostrollbackAuditError(
            "manager password target escaped the secret root"
        )

    command_runner = runner or SubprocessRunner()
    manager = _inspect(command_runner, "greenhouse-manager")
    mosquitto = _inspect(command_runner, "mosquitto")
    homeassistant = _inspect(command_runner, "homeassistant")
    state = manager.get("State")
    mounts = manager.get("Mounts")
    if not isinstance(state, Mapping) or not isinstance(mounts, list):
        raise ManagerPostrollbackAuditError("manager runtime metadata is invalid")
    pid = state.get("Pid")
    if not isinstance(pid, int) or pid <= 0:
        raise ManagerPostrollbackAuditError("manager runtime PID is invalid")
    password_mount_count = sum(
        1
        for item in mounts
        if isinstance(item, Mapping) and item.get("Destination") == _PASSWORD_MOUNT
    )
    transaction_at = _parse_timestamp(journal.get("created_at"))
    baseline_raw = rollback.get("preclaim_authentication_environment_baseline")
    baseline = (
        validate_authentication_environment_state(baseline_raw)
        if isinstance(baseline_raw, Mapping)
        else None
    )
    observations = {
        "journal_phase": journal.get("phase"),
        "rollback_completed": journal.get("phase") == "rollback_completed",
        "rollback_failed": (
            journal.get("phase") == "rollback_failed"
            or (workspace / "rollback-failure-diagnostic.json").exists()
        ),
        "auth_overlay_exists": _target_exists(working_dir / _OVERLAY_NAME),
        "auth_environment_exists": _target_exists(working_dir / _AUTH_ENV_NAME),
        "password_target_exists": _target_exists(password_target),
        "password_mount_count": password_mount_count,
        "created_directory_targets_cleanup_complete": _created_directories_clean(
            rollback,
            secret_root,
        ),
        "manager_running": state.get("Status") == "running",
        "manager_restart_count_zero": manager.get("RestartCount") == 0,
        "manager_stable_mqtt_socket": _stable_socket(
            Path(proc_root),
            pid,
            mqtt_port,
            timeout_s,
            poll_interval_s,
            sleeper,
            monotonic,
        ),
        "manager_image_preserved": (
            manager.get("Image") == rollback.get("manager_runtime_image_id")
        ),
        "mosquitto_unchanged": _service_unchanged(mosquitto, transaction_at),
        "homeassistant_unchanged": _service_unchanged(homeassistant, transaction_at),
        "anonymous_retained_path_readable": _anonymous_retained(
            command_runner,
            expected_retained_topic,
            timeout_s,
        ),
    }
    return evaluate_manager_postrollback_audit(
        preclaim_environment=baseline,
        current_environment=redacted_authentication_environment_state(
            _environment(manager)
        ),
        observations=observations,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only, redacted audit after a greenhouse-manager identity "
            "migration rollback."
        )
    )
    parser.add_argument("transaction_workspace")
    parser.add_argument("execution_preparation_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build_manager_postrollback_audit(
            args.transaction_workspace,
            args.execution_preparation_directory,
            expected_retained_topic=args.expected_retained_topic,
            mqtt_port=args.mqtt_port,
            timeout_s=args.timeout_seconds,
            poll_interval_s=args.poll_interval_seconds,
        )
    except (ManagerPostrollbackAuditError, ValueError):
        print("T1 manager postrollback audit failed safely", file=sys.stderr)
        return 2
    except (OSError, UnicodeError):
        print("T1 manager postrollback audit host read failed safely", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result["rollback_audit_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
