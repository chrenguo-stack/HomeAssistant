from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .t1_backup import BackupError
from .t1_migration_package import MigrationPackageError
from .t1_migration_readiness import CommandRunner, ReadinessError, SubprocessRunner
from .t1_migration_readiness_live import build_live_readiness_report
from .t1_migration_stage import MigrationStageError, verify_migration_stage

AUDIT_SCHEMA = "gh.m2.t1-auth-client-migration-audit/1"


class ClientMigrationAuditError(RuntimeError):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_success(
    runner: CommandRunner,
    command: Sequence[str],
    message: str,
) -> str:
    return_code, output = runner.run(tuple(command))
    if return_code != 0:
        raise ClientMigrationAuditError(message)
    return output


def _read_json_file(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ClientMigrationAuditError(f"{label} is missing or unsafe")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ClientMigrationAuditError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ClientMigrationAuditError(f"{label} must be a JSON object")
    return document


def _read_key_value_file(path: Path, label: str) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise ClientMigrationAuditError(f"{label} is missing or unsafe")
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise ClientMigrationAuditError(f"{label} cannot be read") from error
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, found, value = line.partition("=")
        if not found or not key or key in values:
            raise ClientMigrationAuditError(f"{label} contains invalid entries")
        values[key] = value
    return values


def _stage_safety(stage_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = verify_migration_stage(stage_root)
    activation_plan = _read_json_file(
        stage_root / "activation-plan.json",
        "stage activation plan",
    )
    required_false = (
        "activation_enabled",
        "current_services_modified",
        "active_paths_modified",
        "anonymous_closure_enabled",
    )
    for field in required_false:
        if activation_plan.get(field) is not False:
            raise ClientMigrationAuditError(
                f"stage activation plan safety flag is invalid: {field}"
            )
    if (
        activation_plan.get("preserve_anonymous") is not True
        or activation_plan.get("requires_explicit_gate") is not True
        or activation_plan.get("requires_fresh_backup_immediately_before_apply")
        is not True
    ):
        raise ClientMigrationAuditError("stage activation plan preconditions are invalid")
    return manifest, activation_plan


def _live_readiness(
    manifest: dict[str, Any],
    *,
    expected_retained_topic: str,
    compose_directory: str | Path,
    secret_root: str | Path,
    runner: CommandRunner,
) -> dict[str, object]:
    rollback = manifest.get("source_rollback")
    package = manifest.get("source_migration_package")
    if not isinstance(rollback, dict) or not isinstance(package, dict):
        raise ClientMigrationAuditError("stage source binding is incomplete")
    rollback_path = Path(str(rollback.get("path", ""))).expanduser().resolve()
    package_path = Path(str(package.get("path", ""))).expanduser().resolve()
    report = build_live_readiness_report(
        rollback_path,
        package_path,
        compose_directory=compose_directory,
        secret_root=secret_root,
        expected_retained_topic=expected_retained_topic,
        runner=runner,
    )
    if (
        report.get("schema") != "gh.m2.t1-auth-migration-readiness/1"
        or report.get("read_only") is not True
        or report.get("apply_enabled") is not False
        or report.get("current_services_modified") is not False
        or report.get("source_binding") is not True
        or report.get("ready") is not True
    ):
        raise ClientMigrationAuditError("live migration readiness is no longer passing")
    gates = report.get("gates")
    if not isinstance(gates, dict) or any(value is not True for value in gates.values()):
        raise ClientMigrationAuditError("live migration readiness gates are not all true")
    return report


def _docker_rows(runner: CommandRunner) -> list[dict[str, Any]]:
    output = _require_success(
        runner,
        ("docker", "ps", "-a", "--format", "{{json .}}"),
        "Docker container inventory could not be read",
    )
    rows: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ClientMigrationAuditError(
                "Docker container inventory contains invalid JSON"
            ) from error
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _discover_homeassistant(runner: CommandRunner) -> str:
    candidates: list[str] = []
    for row in _docker_rows(runner):
        name = str(row.get("Names", ""))
        image = str(row.get("Image", ""))
        normalized = f"{name} {image}".lower().replace("-", "")
        if "homeassistant" in normalized:
            candidates.append(name)
    unique = sorted({name for name in candidates if name})
    if len(unique) != 1:
        raise ClientMigrationAuditError(
            "exactly one Home Assistant container must be discoverable"
        )
    return unique[0]


def _inspect_container(runner: CommandRunner, name: str) -> dict[str, Any]:
    output = _require_success(
        runner,
        ("docker", "inspect", name),
        f"container could not be inspected: {name}",
    )
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise ClientMigrationAuditError("Docker inspect returned invalid JSON") from error
    if not isinstance(documents, list) or len(documents) != 1:
        raise ClientMigrationAuditError("Docker inspect returned an unexpected document")
    document = documents[0]
    if not isinstance(document, dict):
        raise ClientMigrationAuditError("Docker inspect document is invalid")
    return document


def _homeassistant_runtime(
    runner: CommandRunner,
    name: str,
) -> dict[str, Any]:
    document = _inspect_container(runner, name)
    state = document.get("State")
    config = document.get("Config")
    if not isinstance(state, dict) or not isinstance(config, dict):
        raise ClientMigrationAuditError("Home Assistant container metadata is incomplete")
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise ClientMigrationAuditError("Home Assistant mount metadata is missing")
    config_mounts = [
        mount
        for mount in mounts
        if isinstance(mount, dict) and mount.get("Destination") == "/config"
    ]
    if len(config_mounts) != 1:
        raise ClientMigrationAuditError(
            "Home Assistant must have exactly one /config mount"
        )
    mount = config_mounts[0]
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        labels = {}
    image = str(config.get("Image", ""))
    return {
        "name": name,
        "state": state.get("Status"),
        "restart_count": int(document.get("RestartCount", 0)),
        "image_ref": image,
        "image_id": document.get("Image"),
        "config_mount_type": mount.get("Type"),
        "config_mount_source": mount.get("Source"),
        "compose_project": labels.get("com.docker.compose.project"),
        "compose_working_dir": labels.get("com.docker.compose.project.working_dir"),
        "compose_config_files_present": bool(
            labels.get("com.docker.compose.project.config_files")
        ),
    }


def _homeassistant_version(runner: CommandRunner, name: str) -> str | None:
    return_code, output = runner.run(
        (
            "docker",
            "exec",
            name,
            "python3",
            "-c",
            "import homeassistant.const as c; print(c.__version__)",
        )
    )
    if return_code != 0:
        return None
    value = output.strip()
    return value or None


def _homeassistant_entries(runner: CommandRunner, name: str) -> dict[str, Any]:
    output = _require_success(
        runner,
        (
            "docker",
            "exec",
            name,
            "sh",
            "-c",
            "cat /config/.storage/core.config_entries",
        ),
        "Home Assistant config entries could not be read",
    )
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise ClientMigrationAuditError(
            "Home Assistant config entries contain invalid JSON"
        ) from error
    if not isinstance(document, dict):
        raise ClientMigrationAuditError("Home Assistant config entries are invalid")
    data = document.get("data")
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ClientMigrationAuditError("Home Assistant config entry list is missing")
    mqtt_entries = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("domain") == "mqtt"
    ]
    enabled = [entry for entry in mqtt_entries if entry.get("disabled_by") is None]
    summary: dict[str, Any] = {
        "storage_version": document.get("version"),
        "mqtt_entry_count": len(mqtt_entries),
        "enabled_mqtt_entry_count": len(enabled),
        "entry_present": len(enabled) == 1,
        "direct_storage_edit_forbidden": True,
        "automatic_update_supported": False,
        "migration_method": "homeassistant_ui_reconfigure",
        "operator_action_required": True,
    }
    if len(enabled) != 1:
        return summary
    entry = enabled[0]
    entry_data = entry.get("data")
    options = entry.get("options")
    if not isinstance(entry_data, dict):
        entry_data = {}
    if not isinstance(options, dict):
        options = {}
    entry_id = str(entry.get("entry_id", ""))
    broker = entry_data.get("broker", entry_data.get("host"))
    summary.update(
        {
            "entry_id_fingerprint": _sha256_text(entry_id)[:16]
            if entry_id
            else None,
            "source": entry.get("source"),
            "title_present": bool(entry.get("title")),
            "broker_present": isinstance(broker, str) and bool(broker),
            "port_present": isinstance(entry_data.get("port"), int),
            "username_present": bool(entry_data.get("username")),
            "password_present": bool(entry_data.get("password")),
            "client_id_present": bool(entry_data.get("client_id")),
            "discovery_disabled": options.get("discovery") is False,
        }
    )
    return summary


def _stage_client_material(stage_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    manager_env = _read_key_value_file(
        stage_root / "payload/manager/manager.env",
        "staged manager environment",
    )
    manager_password = stage_root / "payload/manager/password"
    manager_fragment = stage_root / "payload/manager/compose-secret-fragment.yaml"
    for path, label in (
        (manager_password, "staged manager password"),
        (manager_fragment, "staged manager Compose fragment"),
    ):
        if not path.is_file() or path.is_symlink():
            raise ClientMigrationAuditError(f"{label} is missing or unsafe")

    ha_update = _read_json_file(
        stage_root / "payload/homeassistant/mqtt-update.json",
        "staged Home Assistant MQTT update",
    )
    node_id = str(manifest.get("source_migration_package", {}).get("node_id", ""))
    if not node_id:
        payload_manifest = _read_json_file(
            stage_root / "payload/manifest.json",
            "staged package manifest",
        )
        node_id = str(payload_manifest.get("node_id", ""))
    if not node_id:
        raise ClientMigrationAuditError("staged node identity scope is missing")
    node_update = _read_json_file(
        stage_root / f"payload/node/{node_id}/mqtt-credentials.json",
        "staged node MQTT credentials",
    )

    manager_ready = (
        bool(manager_env.get("GH_MQTT_USERNAME"))
        and bool(manager_env.get("GH_MQTT_CLIENT_ID"))
        and manager_env.get("GH_MQTT_PASSWORD_FILE")
        == "/run/secrets/gh_manager_mqtt_password"
        and manager_password.stat().st_mode & 0o777 == 0o600
    )
    homeassistant_ready = (
        ha_update.get("schema") == "gh.m2.homeassistant-mqtt-update/1"
        and ha_update.get("automatic_apply") is False
        and ha_update.get("operation") == "update_existing_mqtt_config_entry"
        and bool(ha_update.get("username"))
        and bool(ha_update.get("password"))
        and bool(ha_update.get("required_client_id"))
    )
    node_ready = (
        node_update.get("schema") == "gh.m2.node-mqtt-credentials/1"
        and node_update.get("automatic_apply") is False
        and node_update.get("node_id") == node_id
        and bool(node_update.get("username"))
        and bool(node_update.get("password"))
        and bool(node_update.get("client_id"))
    )
    return {
        "manager": {
            "staged_material_complete": manager_ready,
            "automatic_apply": False,
            "migration_method": "compose_secret_overlay",
        },
        "homeassistant": {
            "staged_material_complete": homeassistant_ready,
            "automatic_apply": False,
            "operation": ha_update.get("operation"),
            "required_client_id_present": bool(ha_update.get("required_client_id")),
        },
        "node": {
            "node_id": node_id,
            "staged_material_complete": node_ready,
            "automatic_apply": False,
            "migration_method": "firmware_or_provisioning_update_required",
            "live_delivery_path_verified": False,
        },
    }


def build_client_migration_audit(
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_broker: str = "mosquitto",
    compose_directory: str | Path = "/opt/HomeAssistant/infra/compose/t1",
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")
    command_runner = runner or SubprocessRunner()
    stage_root = Path(stage_directory).expanduser().resolve()
    manifest, _activation_plan = _stage_safety(stage_root)
    readiness = _live_readiness(
        manifest,
        expected_retained_topic=expected_retained_topic,
        compose_directory=compose_directory,
        secret_root=secret_root,
        runner=command_runner,
    )
    materials = _stage_client_material(stage_root, manifest)

    homeassistant_name = _discover_homeassistant(command_runner)
    runtime = _homeassistant_runtime(command_runner, homeassistant_name)
    entries = _homeassistant_entries(command_runner, homeassistant_name)
    version = _homeassistant_version(command_runner, homeassistant_name)

    mqtt_entry_ready = (
        runtime["state"] == "running"
        and runtime["restart_count"] == 0
        and entries.get("entry_present") is True
        and entries.get("broker_present") is True
    )
    blockers: list[str] = []
    if not mqtt_entry_ready:
        blockers.append("homeassistant_mqtt_entry_not_ready")
    if materials["homeassistant"]["staged_material_complete"] is not True:
        blockers.append("homeassistant_staged_material_incomplete")
    blockers.append("homeassistant_operator_reconfigure_required")
    if materials["node"]["staged_material_complete"] is not True:
        blockers.append("node_staged_material_incomplete")
    blockers.append("node_credential_delivery_path_unverified")

    broker_matches_expected: bool | None = None
    if entries.get("entry_present") is True:
        raw_entries = _require_success(
            command_runner,
            (
                "docker",
                "exec",
                homeassistant_name,
                "sh",
                "-c",
                "cat /config/.storage/core.config_entries",
            ),
            "Home Assistant config entries could not be re-read",
        )
        document = json.loads(raw_entries)
        enabled = [
            entry
            for entry in document["data"]["entries"]
            if isinstance(entry, dict)
            and entry.get("domain") == "mqtt"
            and entry.get("disabled_by") is None
        ]
        if len(enabled) == 1:
            data = enabled[0].get("data")
            if isinstance(data, dict):
                broker = data.get("broker", data.get("host"))
                broker_matches_expected = broker == expected_broker
    entries["broker_matches_expected"] = broker_matches_expected
    if broker_matches_expected is False:
        blockers.append("homeassistant_broker_target_mismatch")

    retained_ready = bool(
        isinstance(readiness.get("gates"), dict)
        and readiness["gates"].get("retained_topic_readable") is True
    )
    report = {
        "schema": AUDIT_SCHEMA,
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "stage": {
            "name": stage_root.name,
            "verified": True,
            "activation_enabled": False,
            "active_paths_modified": False,
        },
        "live_readiness": {
            "ready": True,
            "source_binding": True,
            "retained_topic_readable": retained_ready,
        },
        "manager": materials["manager"],
        "homeassistant": {
            "runtime": runtime,
            "version": version,
            "mqtt_config_entry": entries,
            "staged_material": materials["homeassistant"],
            "direct_storage_edit_forbidden": True,
            "operator_reconfigure_required": True,
        },
        "node": materials["node"],
        "activation_blockers": sorted(set(blockers)),
        "audit_complete": True,
        "ready_for_live_apply": False,
    }
    serialized = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    secret_documents = (
        stage_root / "payload/homeassistant/mqtt-update.json",
        stage_root / f"payload/node/{materials['node']['node_id']}/mqtt-credentials.json",
        stage_root / "payload/manager/password",
    )
    for path in secret_documents:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeError:
                continue
            if content and content.strip() in serialized:
                raise ClientMigrationAuditError("audit report contains secret material")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit real Home Assistant and node credential migration capabilities "
            "without applying credentials or modifying live services."
        )
    )
    parser.add_argument("stage_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--expected-broker", default="mosquitto")
    parser.add_argument(
        "--compose-directory",
        default="/opt/HomeAssistant/infra/compose/t1",
    )
    parser.add_argument(
        "--secret-root",
        default="/opt/greenhouse-secrets/mqtt",
    )
    args = parser.parse_args(argv)
    try:
        report = build_client_migration_audit(
            args.stage_directory,
            expected_retained_topic=args.expected_retained_topic,
            expected_broker=args.expected_broker,
            compose_directory=args.compose_directory,
            secret_root=args.secret_root,
        )
    except (
        BackupError,
        ClientMigrationAuditError,
        MigrationPackageError,
        MigrationStageError,
        ReadinessError,
        OSError,
        ValueError,
    ) as error:
        print(f"T1 client migration audit failed: {error}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
