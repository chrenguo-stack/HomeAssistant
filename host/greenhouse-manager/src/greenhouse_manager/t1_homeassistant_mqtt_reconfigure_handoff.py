from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import secrets
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .t1_backup import BackupError, create_backup, verify_backup
from .t1_homeassistant_mqtt_target_gate import (
    DEFAULT_CANDIDATES,
    BrokerCandidate,
    HomeAssistantMqttTargetGateError,
    build_homeassistant_mqtt_target_gate,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

HANDOFF_SCHEMA = "gh.m2.t1-homeassistant-mqtt-reconfigure-handoff/1"
POSTCHECK_SCHEMA = "gh.m2.t1-homeassistant-mqtt-reconfigure-postcheck/1"
_STORAGE = "/config/.storage/core.config_entries"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{4,32}$")


class HomeAssistantMqttReconfigureHandoffError(RuntimeError):
    pass


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise HomeAssistantMqttReconfigureHandoffError("directory must be private and not a symlink")


def _write_private(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise HomeAssistantMqttReconfigureHandoffError(f"{label} is missing or unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HomeAssistantMqttReconfigureHandoffError(f"{label} is invalid") from error
    if not isinstance(value, dict):
        raise HomeAssistantMqttReconfigureHandoffError(f"{label} must be an object")
    return value


def _run(runner: CommandRunner, command: Sequence[str], message: str) -> str:
    return_code, output = runner.run(tuple(command))
    if return_code != 0:
        raise HomeAssistantMqttReconfigureHandoffError(message)
    return output


def _homeassistant_name(runner: CommandRunner) -> str:
    output = _run(
        runner,
        ("docker", "ps", "-a", "--format", "{{json .}}"),
        "Docker inventory could not be read",
    )
    names: set[str] = set()
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise HomeAssistantMqttReconfigureHandoffError("Docker inventory is invalid") from error
        if not isinstance(row, dict):
            continue
        name = str(row.get("Names", ""))
        image = str(row.get("Image", ""))
        if name and "homeassistant" in f"{name} {image}".lower().replace("-", ""):
            names.add(name)
    if len(names) != 1:
        raise HomeAssistantMqttReconfigureHandoffError(
            "exactly one Home Assistant container must be discoverable"
        )
    return next(iter(names))


def _storage(runner: CommandRunner, name: str) -> tuple[str, dict[str, Any]]:
    raw = _run(
        runner,
        ("docker", "exec", name, "sh", "-c", f"cat {_STORAGE}"),
        "Home Assistant config entries could not be read",
    )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise HomeAssistantMqttReconfigureHandoffError("config entries are invalid") from error
    if not isinstance(value, dict):
        raise HomeAssistantMqttReconfigureHandoffError("config entries must be an object")
    return raw, value


def _mqtt_entry(storage: dict[str, Any]) -> dict[str, Any]:
    data = storage.get("data")
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise HomeAssistantMqttReconfigureHandoffError("config entry list is missing")
    matches = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("domain") == "mqtt"
        and entry.get("disabled_by") is None
    ]
    if len(matches) != 1:
        raise HomeAssistantMqttReconfigureHandoffError(
            "exactly one enabled MQTT config entry is required"
        )
    return matches[0]


def _entry_fingerprint(entry: dict[str, Any]) -> str:
    entry_id = str(entry.get("entry_id", ""))
    if not entry_id:
        raise HomeAssistantMqttReconfigureHandoffError("MQTT entry ID is missing")
    return _fingerprint(entry_id)


def _runtime(runner: CommandRunner, name: str) -> dict[str, object]:
    output = _run(runner, ("docker", "inspect", name), "Home Assistant metadata could not be read")
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise HomeAssistantMqttReconfigureHandoffError("Home Assistant metadata is invalid") from error
    if not isinstance(documents, list) or len(documents) != 1 or not isinstance(documents[0], dict):
        raise HomeAssistantMqttReconfigureHandoffError("Home Assistant metadata is incomplete")
    state = documents[0].get("State")
    if not isinstance(state, dict):
        raise HomeAssistantMqttReconfigureHandoffError("Home Assistant state is missing")
    return {"state": state.get("Status"), "restart_count": int(documents[0].get("RestartCount", 0))}


def _stage_values(stage: Path) -> dict[str, Any]:
    value = _read_json(stage / "payload/homeassistant/mqtt-update.json", "staged MQTT update")
    valid = (
        value.get("schema") == "gh.m2.homeassistant-mqtt-update/1"
        and value.get("automatic_apply") is False
        and value.get("operation") == "update_existing_mqtt_config_entry"
        and isinstance(value.get("port"), int)
        and bool(value.get("username"))
        and bool(value.get("password"))
        and bool(value.get("required_client_id"))
        and value.get("preserve_discovery") is True
    )
    if not valid:
        raise HomeAssistantMqttReconfigureHandoffError("staged MQTT update is incomplete or unsafe")
    return value


def _validate_gate(
    report: dict[str, object],
    *,
    expected_kind: str,
    expected_target_fingerprint: str | None,
    expected_entry_fingerprint: str | None,
    expected_storage_sha256: str | None,
) -> dict[str, Any]:
    required = {
        "schema": "gh.m2.t1-homeassistant-mqtt-target-gate/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "prior_audit_complete": True,
        "target_model_ready": True,
        "ready_for_operator_reconfigure": False,
        "ready_for_live_apply": False,
    }
    if any(report.get(key) != value for key, value in required.items()):
        raise HomeAssistantMqttReconfigureHandoffError("target gate is unsafe or incomplete")
    if report.get("selected_target_kind") != expected_kind:
        raise HomeAssistantMqttReconfigureHandoffError("Broker target kind has drifted")
    if expected_target_fingerprint and not hmac.compare_digest(
        str(report.get("selected_target_fingerprint", "")), expected_target_fingerprint
    ):
        raise HomeAssistantMqttReconfigureHandoffError("Broker target fingerprint has drifted")
    official = report.get("homeassistant_official_reconfigure")
    if not isinstance(official, dict):
        raise HomeAssistantMqttReconfigureHandoffError("official reconfigure gate is missing")
    safe = (
        official.get("official_config_flow_only") is True
        and official.get("direct_storage_edit_forbidden") is True
        and official.get("automatic_apply") is False
        and official.get("operator_action_authorized") is False
        and official.get("staged_material_complete") is True
        and official.get("discovery_preserved") is True
        and official.get("retained_baseline_readable") is True
    )
    if not safe:
        raise HomeAssistantMqttReconfigureHandoffError("official reconfigure preconditions are unsafe")
    comparisons = (
        (expected_entry_fingerprint, official.get("pre_change_entry_fingerprint"), "entry"),
        (expected_storage_sha256, official.get("pre_change_storage_sha256"), "storage"),
    )
    for expected, actual, label in comparisons:
        if expected and not hmac.compare_digest(str(actual or ""), expected):
            raise HomeAssistantMqttReconfigureHandoffError(f"{label} fingerprint has drifted")
    blockers = {str(item) for item in report.get("activation_blockers", [])}
    expected_blockers = {
        "broker_identity_not_activated",
        "homeassistant_operator_reconfigure_required",
        "node_credential_delivery_path_unverified",
    }
    if blockers != expected_blockers:
        raise HomeAssistantMqttReconfigureHandoffError("target gate has unexpected blockers")
    return official


def _selected(report: dict[str, object], candidates: Sequence[BrokerCandidate]) -> BrokerCandidate:
    matches = [
        candidate
        for candidate in candidates
        if candidate.kind == report.get("selected_target_kind")
        and _fingerprint(candidate.host) == report.get("selected_target_fingerprint")
    ]
    if len(matches) != 1:
        raise HomeAssistantMqttReconfigureHandoffError("target does not bind to one candidate")
    return matches[0]


def _record(path: Path, root: Path, secret: bool) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise HomeAssistantMqttReconfigureHandoffError("handoff file is missing or not mode 0600")
    return {
        "path": path.relative_to(root).as_posix(),
        "size": path.stat().st_size,
        "sha256": _sha256_path(path),
        "mode": 0o600,
        "contains_secret": secret,
    }


def prepare_homeassistant_mqtt_reconfigure_handoff(
    stage_directory: str | Path,
    output_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_target_kind: str = "loopback",
    expected_target_fingerprint: str | None = None,
    expected_entry_fingerprint: str | None = None,
    expected_storage_sha256: str | None = None,
    candidates: Sequence[BrokerCandidate] = DEFAULT_CANDIDATES,
    port: int = 1883,
    allow_host_address_fallback: bool = False,
    compose_directory: str | Path = "/opt/HomeAssistant/infra/compose/t1",
    secret_root: str | Path = "/opt/greenhouse-secrets/mqtt",
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    token_factory: Callable[[], str] | None = None,
) -> dict[str, object]:
    command_runner = runner or SubprocessRunner()
    stage = Path(stage_directory).expanduser().resolve()
    output = Path(output_directory).expanduser().resolve()
    _private_directory(output)
    gate = build_homeassistant_mqtt_target_gate(
        stage,
        expected_retained_topic=expected_retained_topic,
        candidates=candidates,
        port=port,
        allow_host_address_fallback=allow_host_address_fallback,
        compose_directory=compose_directory,
        secret_root=secret_root,
        runner=command_runner,
    )
    official = _validate_gate(
        gate,
        expected_kind=expected_target_kind,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_entry_fingerprint=expected_entry_fingerprint,
        expected_storage_sha256=expected_storage_sha256,
    )
    selected = _selected(gate, candidates)
    staged = _stage_values(stage)
    name = _homeassistant_name(command_runner)
    raw, storage = _storage(command_runner, name)
    entry = _mqtt_entry(storage)
    entry_fp = _entry_fingerprint(entry)
    storage_sha = _sha256_bytes(raw.encode())
    if not hmac.compare_digest(entry_fp, str(official.get("pre_change_entry_fingerprint", ""))):
        raise HomeAssistantMqttReconfigureHandoffError("MQTT entry changed after target audit")
    if not hmac.compare_digest(storage_sha, str(official.get("pre_change_storage_sha256", ""))):
        raise HomeAssistantMqttReconfigureHandoffError("config entry storage changed after target audit")

    observed = (now or datetime.now(UTC)).astimezone(UTC)
    token = token_factory() if token_factory else secrets.token_hex(4)
    if not isinstance(token, str) or _TOKEN_RE.fullmatch(token) is None:
        raise HomeAssistantMqttReconfigureHandoffError("handoff token is invalid")
    root = output / (
        "greenhouse-ha-mqtt-handoff-" + observed.strftime("%Y%m%dT%H%M%SZ") + "-" + token
    )
    root.mkdir(mode=0o700)
    rollback_dir = root / "rollback"
    rollback_dir.mkdir(mode=0o700)
    archive = create_backup(rollback_dir, runner=command_runner, now=observed)
    backup_manifest = verify_backup(archive)
    created_at = observed.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if backup_manifest.get("created_at") != created_at:
        raise HomeAssistantMqttReconfigureHandoffError("rollback backup is not bound to this handoff")

    data = entry.get("data") if isinstance(entry.get("data"), dict) else {}
    options = entry.get("options") if isinstance(entry.get("options"), dict) else {}
    checkpoint = root / "homeassistant/core.config_entries.before.json"
    rollback_values = root / "homeassistant/rollback-values.json"
    reconfigure_values = root / "homeassistant/reconfigure-values.json"
    runbook = root / "operator-runbook.txt"
    _write_private(checkpoint, raw)
    _write_private(
        rollback_values,
        _json_text(
            {
                "schema": "gh.m2.homeassistant-mqtt-rollback-values/1",
                "official_config_flow_only": True,
                "entry_id_fingerprint": entry_fp,
                "data": data,
                "options": options,
            }
        ),
    )
    _write_private(
        reconfigure_values,
        _json_text(
            {
                "schema": "gh.m2.homeassistant-mqtt-reconfigure-values/1",
                "official_config_flow_only": True,
                "broker": selected.host,
                "port": staged["port"],
                "username": staged["username"],
                "password": staged["password"],
                "client_id": staged["required_client_id"],
                "generation": staged.get("generation"),
                "preserve_discovery": True,
                "advanced_options_required": True,
            }
        ),
    )
    _write_private(
        runbook,
        "Home Assistant official MQTT reconfigure handoff\n\n"
        "DO NOT EXECUTE YET. operator_action_authorized=false.\n"
        "Broker identity activation and verification must pass first.\n\n"
        "When a later gate authorizes the action:\n"
        "1. Open Settings > Devices & services.\n"
        "2. Select MQTT and choose Reconfigure.\n"
        "3. Enter values from homeassistant/reconfigure-values.json.\n"
        "4. Open Advanced options and set the custom client ID.\n"
        "5. Keep MQTT discovery enabled and submit once.\n"
        "6. Run the repository postcheck immediately.\n"
        "7. On failure, Reconfigure with homeassistant/rollback-values.json.\n"
        "8. Never copy the .storage checkpoint over a running Home Assistant.\n",
    )
    records = [
        _record(checkpoint, root, True),
        _record(rollback_values, root, True),
        _record(reconfigure_values, root, True),
        _record(runbook, root, False),
    ]
    manifest = {
        "schema": HANDOFF_SCHEMA,
        "created_at": created_at,
        "classification": "sensitive-local-operator-handoff",
        "read_only_live_services": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "operator_action_required": True,
        "operator_action_authorized": False,
        "ready_for_operator_reconfigure": False,
        "target": {"kind": selected.kind, "fingerprint": _fingerprint(selected.host), "port": staged["port"]},
        "pre_change": {"entry_fingerprint": entry_fp, "storage_sha256": storage_sha},
        "rollback": {
            "archive": archive.name,
            "archive_sha256": _sha256_path(archive),
            "archive_schema": backup_manifest.get("schema"),
            "homeassistant_checkpoint_sha256": _sha256_path(checkpoint),
            "official_reconfigure_values_present": True,
            "emergency_storage_restore_authorized": False,
        },
        "expected_retained_topic": expected_retained_topic,
        "activation_blockers": gate["activation_blockers"],
        "records": records,
    }
    _write_private(root / "manifest.json", _json_text(manifest))
    report = {
        "schema": HANDOFF_SCHEMA,
        "prepared": True,
        "handoff_directory": str(root),
        "read_only_live_services": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "operator_action_authorized": False,
        "ready_for_operator_reconfigure": False,
        "target_kind": selected.kind,
        "target_fingerprint": _fingerprint(selected.host),
        "pre_change_entry_fingerprint": entry_fp,
        "pre_change_storage_sha256": storage_sha,
        "fresh_rollback_archive_created": True,
        "homeassistant_checkpoint_created": True,
        "rollback_material_complete": True,
        "activation_blockers": gate["activation_blockers"],
    }
    serialized = _json_text(report)
    for secret in (staged["username"], staged["password"], staged["required_client_id"], selected.host):
        if str(secret) in serialized:
            raise HomeAssistantMqttReconfigureHandoffError("sanitized report contains secret material")
    return report


def audit_homeassistant_mqtt_reconfigure_postcheck(
    handoff_directory: str | Path,
    *,
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    command_runner = runner or SubprocessRunner()
    root = Path(handoff_directory).expanduser().resolve()
    manifest = _read_json(root / "manifest.json", "handoff manifest")
    if (
        manifest.get("schema") != HANDOFF_SCHEMA
        or manifest.get("operator_action_authorized") is not False
        or manifest.get("apply_enabled") is not False
        or manifest.get("current_services_modified") is not False
    ):
        raise HomeAssistantMqttReconfigureHandoffError("handoff manifest is unsafe")
    expected = _read_json(root / "homeassistant/reconfigure-values.json", "reconfigure values")
    name = _homeassistant_name(command_runner)
    raw, storage = _storage(command_runner, name)
    entry = _mqtt_entry(storage)
    data = entry.get("data") if isinstance(entry.get("data"), dict) else {}
    options = entry.get("options") if isinstance(entry.get("options"), dict) else {}
    broker = data.get("broker", data.get("host"))
    matches = {
        "broker": hmac.compare_digest(str(broker or ""), str(expected.get("broker", ""))),
        "port": data.get("port") == expected.get("port"),
        "username": hmac.compare_digest(str(data.get("username") or ""), str(expected.get("username") or "")),
        "password": hmac.compare_digest(str(data.get("password") or ""), str(expected.get("password") or "")),
        "client_id": hmac.compare_digest(str(data.get("client_id") or ""), str(expected.get("client_id") or "")),
    }
    pre = manifest.get("pre_change") if isinstance(manifest.get("pre_change"), dict) else {}
    storage_changed = not hmac.compare_digest(_sha256_bytes(raw.encode()), str(pre.get("storage_sha256", "")))
    entry_unchanged = _entry_fingerprint(entry) == pre.get("entry_fingerprint")
    discovery_preserved = options.get("discovery") is not False
    runtime = _runtime(command_runner, name)
    runtime_healthy = runtime["state"] == "running" and runtime["restart_count"] == 0
    verified = all(matches.values()) and storage_changed and entry_unchanged and discovery_preserved and runtime_healthy
    return {
        "schema": POSTCHECK_SCHEMA,
        "read_only": True,
        "current_services_modified": False,
        "homeassistant_runtime": runtime,
        "runtime_healthy": runtime_healthy,
        "entry_fingerprint_unchanged": entry_unchanged,
        "storage_changed": storage_changed,
        "discovery_preserved": discovery_preserved,
        "field_matches": matches,
        "reconfigure_verified": verified,
        "rollback_required": not verified,
        "ready_for_live_apply": False,
    }


def _candidate(value: str) -> BrokerCandidate:
    label, separator, remainder = value.partition("=")
    kind, kind_separator, host = remainder.partition(":")
    if not separator or not kind_separator:
        raise argparse.ArgumentTypeError("candidate must use LABEL=KIND:HOST")
    try:
        return BrokerCandidate(label=label, kind=kind, host=host)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or verify an official MQTT reconfigure handoff")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("stage_directory")
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--expected-retained-topic", required=True)
    prepare.add_argument("--expected-target-kind", default="loopback")
    prepare.add_argument("--expected-target-fingerprint")
    prepare.add_argument("--expected-entry-fingerprint")
    prepare.add_argument("--expected-storage-sha256")
    prepare.add_argument("--candidate", action="append", type=_candidate, default=None)
    prepare.add_argument("--port", type=int, default=1883)
    prepare.add_argument("--allow-host-address-fallback", action="store_true")
    prepare.add_argument("--compose-directory", default="/opt/HomeAssistant/infra/compose/t1")
    prepare.add_argument("--secret-root", default="/opt/greenhouse-secrets/mqtt")
    postcheck = commands.add_parser("postcheck")
    postcheck.add_argument("handoff_directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            report = prepare_homeassistant_mqtt_reconfigure_handoff(
                args.stage_directory,
                args.output,
                expected_retained_topic=args.expected_retained_topic,
                expected_target_kind=args.expected_target_kind,
                expected_target_fingerprint=args.expected_target_fingerprint,
                expected_entry_fingerprint=args.expected_entry_fingerprint,
                expected_storage_sha256=args.expected_storage_sha256,
                candidates=tuple(args.candidate or DEFAULT_CANDIDATES),
                port=args.port,
                allow_host_address_fallback=args.allow_host_address_fallback,
                compose_directory=args.compose_directory,
                secret_root=args.secret_root,
            )
        else:
            report = audit_homeassistant_mqtt_reconfigure_postcheck(args.handoff_directory)
    except (
        BackupError,
        HomeAssistantMqttReconfigureHandoffError,
        HomeAssistantMqttTargetGateError,
        OSError,
        ValueError,
    ) as error:
        print(f"T1 Home Assistant MQTT reconfigure handoff failed: {error}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
