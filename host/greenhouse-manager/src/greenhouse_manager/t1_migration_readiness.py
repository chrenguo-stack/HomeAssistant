from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .t1_backup import BackupError, verify_backup
from .t1_migration_package import MigrationPackageError, verify_migration_package
from .t1_preflight import parse_safe_directives

REPORT_SCHEMA = "gh.m2.t1-auth-migration-readiness/1"
_COMPOSE_FILENAMES = (
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
)
_CANDIDATE_PREFIXES = (
    "gh-m2-restore-",
    "gh-m2-shadow-",
    "gh-m2-shadow-services-",
    "gh-m2-package-rehearsal-",
)
_MANAGER_AUTH_KEYS = (
    "GH_MQTT_USERNAME",
    "GH_MQTT_PASSWORD",
    "GH_MQTT_PASSWORD_FILE",
)


class ReadinessError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def run(self, command: Sequence[str]) -> tuple[int, str]: ...


class SubprocessRunner:
    def run(self, command: Sequence[str]) -> tuple[int, str]:
        completed = subprocess.run(
            tuple(command),
            check=False,
            capture_output=True,
            text=True,
        )
        output = completed.stdout if completed.stdout else completed.stderr
        return completed.returncode, output


@dataclass(frozen=True, slots=True)
class ContainerObservation:
    name: str
    state: str
    restart_count: int
    image_id: str
    image_ref: str


@dataclass(frozen=True, slots=True)
class FileObservation:
    path: str
    exists: bool
    mode: str | None
    sha256: str | None


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _private_file_observation(path: Path) -> FileObservation:
    if not path.is_file():
        return FileObservation(str(path), False, None, None)
    return FileObservation(
        path=str(path),
        exists=True,
        mode=format(path.stat().st_mode & 0o777, "03o"),
        sha256=_sha256_path(path),
    )


def _command_output(
    runner: CommandRunner,
    command: Sequence[str],
    *,
    error: str,
) -> str:
    return_code, output = runner.run(command)
    if return_code != 0:
        raise ReadinessError(error)
    return output.strip()


def _inspect_container(
    runner: CommandRunner,
    name: str,
) -> ContainerObservation:
    template = json.dumps(
        {
            "state": "{{.State.Status}}",
            "restarts": "{{.RestartCount}}",
            "image_id": "{{.Image}}",
            "image_ref": "{{.Config.Image}}",
        },
        separators=(",", ":"),
    )
    output = _command_output(
        runner,
        ("docker", "inspect", "-f", template, name),
        error=f"required container cannot be inspected: {name}",
    )
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise ReadinessError(
            f"container inspection returned invalid JSON: {name}"
        ) from error
    return ContainerObservation(
        name=name,
        state=str(document.get("state", "unknown")),
        restart_count=int(document.get("restarts", -1)),
        image_id=str(document.get("image_id", "unknown")),
        image_ref=str(document.get("image_ref", "unknown")),
    )


def _manager_auth_flags(
    runner: CommandRunner,
) -> dict[str, bool]:
    output = _command_output(
        runner,
        ("docker", "inspect", "-f", "{{json .Config.Env}}", "greenhouse-manager"),
        error="greenhouse-manager environment cannot be inspected",
    )
    try:
        values = json.loads(output)
    except json.JSONDecodeError as error:
        raise ReadinessError(
            "greenhouse-manager environment inspection returned invalid JSON"
        ) from error
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ReadinessError("greenhouse-manager environment inspection is invalid")
    environment: dict[str, str] = {}
    for item in values:
        key, separator, value = item.partition("=")
        if separator:
            environment[key] = value
    return {
        key.lower(): bool(environment.get(key, ""))
        for key in _MANAGER_AUTH_KEYS
    }


def _read_backup_config(archive: Path) -> bytes:
    with tarfile.open(archive, mode="r:gz") as backup:
        try:
            member = backup.getmember("mosquitto-config/mosquitto.conf")
        except KeyError as error:
            raise ReadinessError(
                "rollback archive does not contain mosquitto.conf"
            ) from error
        stream = backup.extractfile(member)
        if stream is None:
            raise ReadinessError("rollback mosquitto.conf cannot be read")
        return stream.read()


def _read_live_config(runner: CommandRunner) -> bytes:
    output = _command_output(
        runner,
        (
            "docker",
            "exec",
            "mosquitto",
            "sh",
            "-c",
            "test -r /mosquitto/config/mosquitto.conf && "
            "cat /mosquitto/config/mosquitto.conf",
        ),
        error="live mosquitto.conf cannot be read",
    )
    return (output + "\n").encode("utf-8")


def _source_binding(
    rollback_path: Path,
    rollback_manifest: dict[str, Any],
    package_manifest: dict[str, Any],
) -> bool:
    source = package_manifest.get("source_rollback")
    if not isinstance(source, dict):
        return False
    expected = (
        rollback_path.name,
        _sha256_path(rollback_path),
        rollback_manifest.get("schema"),
        rollback_manifest.get("sources", {})
        .get("mosquitto", {})
        .get("image_id"),
    )
    actual = (
        source.get("archive"),
        source.get("sha256"),
        source.get("schema"),
        source.get("mosquitto_image_id"),
    )
    return actual == expected


def _compose_observations(compose_directory: Path) -> tuple[
    tuple[FileObservation, ...],
    FileObservation,
]:
    compose_files = tuple(
        _private_file_observation(compose_directory / name)
        for name in _COMPOSE_FILENAMES
        if (compose_directory / name).is_file()
    )
    env_file = _private_file_observation(compose_directory / ".env")
    return compose_files, env_file


def _secret_root_status(path: Path) -> dict[str, object]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "mode": None,
            "empty": True,
            "safe": True,
        }
    if not path.is_dir():
        return {
            "path": str(path),
            "exists": True,
            "mode": format(path.stat().st_mode & 0o777, "03o"),
            "empty": False,
            "safe": False,
        }
    entries = tuple(path.iterdir())
    mode = path.stat().st_mode & 0o777
    return {
        "path": str(path),
        "exists": True,
        "mode": format(mode, "03o"),
        "empty": not entries,
        "safe": not entries and mode & 0o077 == 0,
    }


def _candidate_names(runner: CommandRunner) -> tuple[str, ...]:
    output = _command_output(
        runner,
        ("docker", "ps", "-a", "--format", "{{.Names}}"),
        error="Docker container inventory cannot be read",
    )
    return tuple(
        name
        for name in output.splitlines()
        if any(name.startswith(prefix) for prefix in _CANDIDATE_PREFIXES)
    )


def _retained_topic_readable(
    runner: CommandRunner,
    topic: str,
) -> bool:
    return_code, output = runner.run(
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
            "5",
            "-F",
            "%p",
            "-t",
            topic,
        )
    )
    return return_code == 0 and bool(output.strip())


def _transaction_plan() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-auth-migration-transaction-plan/1",
        "apply_enabled": False,
        "requires_explicit_gate": True,
        "requires_fresh_backup_immediately_before_apply": True,
        "steps": [
            {
                "order": 1,
                "stage": "capture_fresh_rollback_and_revalidate_live_baseline",
                "automatic": False,
            },
            {
                "order": 2,
                "stage": "stage_private_host_secrets_and_compose_overlay",
                "automatic": False,
            },
            {
                "order": 3,
                "stage": "enable_dynamic_security_while_preserving_anonymous",
                "automatic": False,
            },
            {
                "order": 4,
                "stage": "verify_provisioning_then_remove_bootstrap_admin",
                "automatic": False,
            },
            {
                "order": 5,
                "stage": "migrate_greenhouse_manager_identity",
                "automatic": False,
            },
            {
                "order": 6,
                "stage": "migrate_home_assistant_mqtt_config_entry",
                "automatic": False,
                "direct_storage_edit_forbidden": True,
            },
            {
                "order": 7,
                "stage": "migrate_node_identity",
                "automatic": False,
            },
            {
                "order": 8,
                "stage": "authenticated_observation_window",
                "automatic": False,
            },
            {
                "order": 9,
                "stage": "close_anonymous_access_separate_gate",
                "automatic": False,
                "blocked_until_all_authenticated": True,
            },
        ],
        "rollback_checkpoints": [
            "before_dynamic_security_enablement",
            "after_broker_restart_before_client_migration",
            "after_manager_migration",
            "after_home_assistant_migration",
            "after_node_migration_before_anonymous_closure",
        ],
    }


def build_readiness_report(
    rollback_archive: str | Path,
    migration_package: str | Path,
    *,
    compose_directory: str | Path = "/opt/HomeAssistant/infra/compose/t1",
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    expected_retained_topic: str,
    runner: CommandRunner | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    rollback_path = Path(rollback_archive).expanduser().resolve()
    package_path = Path(migration_package).expanduser().resolve()
    compose_path = Path(compose_directory).expanduser().resolve()
    secret_path = Path(secret_root).expanduser().resolve()

    try:
        rollback_manifest = verify_backup(rollback_path)
        package_manifest = verify_migration_package(package_path)
    except (BackupError, MigrationPackageError, OSError) as error:
        raise ReadinessError("verified rollback and migration packages are required") from error

    mosquitto = _inspect_container(command_runner, "mosquitto")
    manager = _inspect_container(command_runner, "greenhouse-manager")
    manager_auth = _manager_auth_flags(command_runner)
    live_config = _read_live_config(command_runner)
    backup_config = _read_backup_config(rollback_path)
    directives = parse_safe_directives(live_config.decode("utf-8"))
    directive_map = {
        entry["directive"]: entry["value"]
        for entry in directives
    }

    plugin_available = (
        _command_output(
            command_runner,
            (
                "docker",
                "exec",
                "mosquitto",
                "sh",
                "-c",
                "test -f /usr/lib/mosquitto_dynamic_security.so && echo available",
            ),
            error="Dynamic Security plugin availability cannot be inspected",
        )
        == "available"
    )
    dynsec_state_absent = (
        _command_output(
            command_runner,
            (
                "docker",
                "exec",
                "mosquitto",
                "sh",
                "-c",
                "test ! -e /mosquitto/data/dynamic-security.json && "
                "echo absent || echo present",
            ),
            error="Dynamic Security state presence cannot be inspected",
        )
        == "absent"
    )
    candidates = _candidate_names(command_runner)
    compose_files, env_file = _compose_observations(compose_path)
    secret_status = _secret_root_status(secret_path)
    rollback_observation = _private_file_observation(rollback_path)
    package_observation = _private_file_observation(package_path)

    anonymous_value = directive_map.get("allow_anonymous", "").lower()
    dynamic_security_configured = any(
        entry["directive"] == "plugin"
        and "dynamic_security" in entry["value"]
        for entry in directives
    )
    package_apply_disabled = package_manifest.get("apply_enabled") is False
    source_bound = _source_binding(
        rollback_path,
        rollback_manifest,
        package_manifest,
    )
    source_images = rollback_manifest.get("sources", {})
    gates = {
        "mosquitto_running_zero_restart": (
            mosquitto.state == "running" and mosquitto.restart_count == 0
        ),
        "manager_running_zero_restart": (
            manager.state == "running" and manager.restart_count == 0
        ),
        "mosquitto_image_matches_rollback": (
            mosquitto.image_id
            == source_images.get("mosquitto", {}).get("image_id")
        ),
        "manager_image_matches_rollback": (
            manager.image_id
            == source_images.get("greenhouse_manager", {}).get("image_id")
        ),
        "live_mosquitto_config_matches_rollback": (
            _sha256_bytes(live_config) == _sha256_bytes(backup_config)
        ),
        "anonymous_access_still_enabled": anonymous_value in {"true", "yes", "1", "on"},
        "dynamic_security_not_configured": not dynamic_security_configured,
        "dynamic_security_state_absent": dynsec_state_absent,
        "dynamic_security_plugin_available": plugin_available,
        "manager_authentication_not_configured": not any(manager_auth.values()),
        "rollback_archive_private": rollback_observation.mode == "600",
        "migration_package_private": package_observation.mode == "600",
        "migration_package_directory_private": (
            package_path.parent.stat().st_mode & 0o077 == 0
        ),
        "migration_package_apply_disabled": package_apply_disabled,
        "migration_package_source_binding": source_bound,
        "compose_directory_present": compose_path.is_dir(),
        "compose_configuration_present": bool(compose_files),
        "compose_env_private": env_file.exists and env_file.mode == "600",
        "host_secret_root_safe": bool(secret_status["safe"]),
        "retained_topic_readable": _retained_topic_readable(
            command_runner,
            expected_retained_topic,
        ),
        "no_candidate_containers": not candidates,
    }
    observed_at = (generated_at or datetime.now(UTC)).astimezone(UTC)
    return {
        "schema": REPORT_SCHEMA,
        "generated_at": observed_at.isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "rollback": asdict(rollback_observation),
        "migration_package": asdict(package_observation),
        "source_binding": source_bound,
        "containers": {
            "mosquitto": asdict(mosquitto),
            "greenhouse_manager": asdict(manager),
        },
        "broker": {
            "safe_directives": directives,
            "live_config_sha256": _sha256_bytes(live_config),
            "rollback_config_sha256": _sha256_bytes(backup_config),
            "anonymous_mode": anonymous_value,
            "dynamic_security_configured": dynamic_security_configured,
            "dynamic_security_state_absent": dynsec_state_absent,
            "dynamic_security_plugin_available": plugin_available,
            "expected_retained_topic": expected_retained_topic,
        },
        "manager": {
            "authentication_flags": manager_auth,
        },
        "compose": {
            "directory": str(compose_path),
            "files": [asdict(item) for item in compose_files],
            "env": asdict(env_file),
        },
        "host_secret_root": secret_status,
        "candidate_containers": candidates,
        "gates": gates,
        "ready": all(gates.values()),
        "transaction_plan": _transaction_plan(),
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only real T1 authenticated MQTT migration readiness audit."
    )
    parser.add_argument("rollback_archive")
    parser.add_argument("migration_package")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument(
        "--compose-directory",
        default="/opt/HomeAssistant/infra/compose/t1",
    )
    parser.add_argument(
        "--secret-root",
        default="/opt/greenhouse-secrets/mqtt",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_readiness_report(
            args.rollback_archive,
            args.migration_package,
            compose_directory=args.compose_directory,
            secret_root=args.secret_root,
            expected_retained_topic=args.expected_retained_topic,
            runner=runner,
        )
    except (ReadinessError, OSError, ValueError) as error:
        print(f"T1 migration readiness audit failed: {error}", file=sys.stderr)
        return 2
    json.dump(
        report,
        sys.stdout,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
    )
    sys.stdout.write("\n")
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
