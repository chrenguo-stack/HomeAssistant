from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .t1_homeassistant_mqtt_reconfigure_handoff import (
    HANDOFF_SCHEMA as CURRENT_HANDOFF_SCHEMA,
)
from .t1_homeassistant_mqtt_reconfigure_handoff import (
    POSTCHECK_SCHEMA as CURRENT_POSTCHECK_SCHEMA,
)
from .t1_homeassistant_mqtt_reconfigure_handoff import (
    audit_homeassistant_mqtt_reconfigure_postcheck,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

SCHEMA = "gh.m2.t1-homeassistant-mqtt-legacy-evidence-bridge/1"
LEGACY_HANDOFF_SCHEMA = "gh.m2.t1-homeassistant-mqtt-postactivation-handoff/1"
LEGACY_POSTCHECK_SCHEMA = "gh.m2.t1-homeassistant-mqtt-ui-retry-postcheck/1"
RECONFIGURE_VALUES_SCHEMA = "gh.m2.homeassistant-mqtt-reconfigure-values/1"
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{4,32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ENTRY_FINGERPRINT = re.compile(r"^[0-9a-f]{16}$")
_MATCH_FIELDS = {"broker", "port", "username", "password", "client_id"}

HomeAssistantAuditor = Callable[..., dict[str, object]]


class HomeAssistantMqttLegacyEvidenceBridgeError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _make_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def _require_private_dir(path: Path, label: str) -> None:
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            f"{label} is missing, public, or unsafe"
        )


def _load(path: Path, label: str, *, private: bool = True) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise HomeAssistantMqttLegacyEvidenceBridgeError(f"{label} is missing or unsafe")
    if private and path.stat().st_mode & 0o777 != 0o600:
        raise HomeAssistantMqttLegacyEvidenceBridgeError(f"{label} must use mode 0600")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HomeAssistantMqttLegacyEvidenceBridgeError(f"{label} is invalid") from error
    if not isinstance(value, dict):
        raise HomeAssistantMqttLegacyEvidenceBridgeError(f"{label} must be an object")
    return value


def _write(path: Path, value: bytes) -> None:
    _make_private_dir(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        _fsync_dir(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    _write(path, (_json(value) + "\n").encode())


def _must(document: Mapping[str, Any], required: Mapping[str, object], label: str) -> None:
    for field, expected in required.items():
        if document.get(field) != expected:
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                f"{label} verification failed: {field}"
            )


def _mode(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"0?[0-7]{3}", value):
        return int(value, 8)
    return None


def _relative_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise HomeAssistantMqttLegacyEvidenceBridgeError("legacy record path is invalid")
    relative = PurePosixPath(value)
    if relative.is_absolute() or "." in relative.parts or ".." in relative.parts:
        raise HomeAssistantMqttLegacyEvidenceBridgeError("legacy record path is unsafe")
    return relative


def _validate_records(root: Path, manifest: Mapping[str, Any]) -> set[str]:
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise HomeAssistantMqttLegacyEvidenceBridgeError("legacy records are missing")

    verified: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise HomeAssistantMqttLegacyEvidenceBridgeError("legacy record is invalid")
        relative = _relative_path(record.get("path"))
        name = relative.as_posix()
        if name in verified:
            raise HomeAssistantMqttLegacyEvidenceBridgeError("legacy record is duplicated")
        path = root.joinpath(*relative.parts)
        if not path.is_file() or path.is_symlink():
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                f"legacy record is missing or unsafe: {name}"
            )
        expected_mode = _mode(record.get("mode"))
        if expected_mode is None or path.stat().st_mode & 0o777 != expected_mode:
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                f"legacy record mode verification failed: {name}"
            )
        if record.get("size") != path.stat().st_size:
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                f"legacy record size verification failed: {name}"
            )
        expected_sha = record.get("sha256")
        if (
            not isinstance(expected_sha, str)
            or _SHA256.fullmatch(expected_sha) is None
            or not hmac.compare_digest(_sha(path), expected_sha)
        ):
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                f"legacy record hash verification failed: {name}"
            )
        if not isinstance(record.get("contains_secret"), bool):
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                f"legacy record classification is invalid: {name}"
            )
        verified.add(name)
    return verified


def _validate_legacy_manifest(
    root: Path,
    expected_retained_topic: str,
) -> tuple[Path, dict[str, Any]]:
    manifest_path = root / "manifest.json"
    manifest = _load(manifest_path, "legacy Home Assistant handoff manifest")
    _must(
        manifest,
        {
            "schema": LEGACY_HANDOFF_SCHEMA,
            "read_only_live_services": True,
            "apply_enabled": False,
            "current_services_modified": False,
            "operator_decision_required": True,
            "operator_action_authorized": False,
            "ready_for_operator_reconfigure": False,
            "broker_identity_activated": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "expected_retained_topic": expected_retained_topic,
        },
        "legacy Home Assistant handoff",
    )

    pre_change = manifest.get("pre_change")
    if not isinstance(pre_change, dict):
        raise HomeAssistantMqttLegacyEvidenceBridgeError("legacy pre-change binding is missing")
    entry_fingerprint = pre_change.get("entry_fingerprint")
    storage_sha256 = pre_change.get("storage_sha256")
    if (
        not isinstance(entry_fingerprint, str)
        or _ENTRY_FINGERPRINT.fullmatch(entry_fingerprint) is None
        or not isinstance(storage_sha256, str)
        or _SHA256.fullmatch(storage_sha256) is None
    ):
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            "legacy pre-change binding is invalid"
        )

    target = manifest.get("target")
    if (
        not isinstance(target, dict)
        or not isinstance(target.get("kind"), str)
        or not isinstance(target.get("fingerprint"), str)
        or not isinstance(target.get("port"), int)
    ):
        raise HomeAssistantMqttLegacyEvidenceBridgeError("legacy target is invalid")

    rollback = manifest.get("rollback")
    if not isinstance(rollback, dict):
        raise HomeAssistantMqttLegacyEvidenceBridgeError("legacy rollback binding is missing")
    for field in ("archive_sha256", "homeassistant_checkpoint_sha256"):
        value = rollback.get(field)
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                f"legacy rollback binding is invalid: {field}"
            )
    if (
        rollback.get("official_reconfigure_values_present") is not True
        or rollback.get("emergency_storage_restore_authorized") is not False
    ):
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            "legacy rollback safety flags are invalid"
        )

    verified = _validate_records(root, manifest)
    if "homeassistant/reconfigure-values.json" not in verified:
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            "legacy reconfigure values are not bound by records"
        )
    return manifest_path, manifest


def _validate_reconfigure_values(path: Path) -> dict[str, Any]:
    values = _load(path, "legacy Home Assistant reconfigure values")
    _must(
        values,
        {
            "schema": RECONFIGURE_VALUES_SCHEMA,
            "official_config_flow_only": True,
            "preserve_discovery": True,
            "advanced_options_required": True,
        },
        "legacy Home Assistant reconfigure values",
    )
    for field in ("broker", "username", "password", "client_id"):
        if not isinstance(values.get(field), str) or not values[field]:
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                f"legacy Home Assistant reconfigure values are incomplete: {field}"
            )
    port = values.get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            "legacy Home Assistant reconfigure port is invalid"
        )
    return values


def _validate_legacy_postcheck(path: Path) -> dict[str, Any]:
    report = _load(path, "legacy Home Assistant UI retry postcheck")
    _must(
        report,
        {
            "schema": LEGACY_POSTCHECK_SCHEMA,
            "authorization_claimed": True,
            "authorization_consumed": True,
            "operator_reported_submission": True,
            "operator_validation_required": True,
            "homeassistant_reconfigured": True,
            "mqtt_socket_established": True,
            "services_stable": True,
            "entry_identity_unchanged": True,
            "entry_semantic_changed": True,
            "entry_semantic_stable": True,
            "storage_changed": True,
            "storage_stable": True,
            "discovery_preserved": True,
            "postcheck_verified": True,
            "rollback_required": False,
            "current_services_modified": False,
            "node_credentials_delivered": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "secret_values_included": False,
        },
        "legacy Home Assistant UI retry postcheck",
    )
    authorization_id = report.get("authorization_id")
    if not isinstance(authorization_id, str) or not authorization_id:
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            "legacy postcheck authorization binding is missing"
        )
    matches = report.get("field_matches")
    if (
        not isinstance(matches, dict)
        or set(matches) != _MATCH_FIELDS
        or any(value is not True for value in matches.values())
    ):
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            "legacy postcheck field verification is incomplete"
        )
    return report


def _legacy_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "runtime_healthy": bool(
            report.get("services_stable") and report.get("mqtt_socket_established")
        ),
        "entry_fingerprint_unchanged": report.get("entry_identity_unchanged"),
        "storage_changed": report.get("storage_changed"),
        "discovery_preserved": report.get("discovery_preserved"),
        "field_matches": report.get("field_matches"),
        "reconfigure_verified": bool(
            report.get("postcheck_verified") and report.get("homeassistant_reconfigured")
        ),
        "rollback_required": report.get("rollback_required"),
    }


def _validate_current_postcheck(report: Mapping[str, Any]) -> None:
    _must(
        report,
        {
            "schema": CURRENT_POSTCHECK_SCHEMA,
            "read_only": True,
            "current_services_modified": False,
            "runtime_healthy": True,
            "entry_fingerprint_unchanged": True,
            "storage_changed": True,
            "discovery_preserved": True,
            "reconfigure_verified": True,
            "rollback_required": False,
            "ready_for_live_apply": False,
        },
        "live Home Assistant postcheck",
    )
    matches = report.get("field_matches")
    if (
        not isinstance(matches, dict)
        or set(matches) != _MATCH_FIELDS
        or any(value is not True for value in matches.values())
    ):
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            "live Home Assistant field verification is incomplete"
        )


def _current_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "runtime_healthy",
        "entry_fingerprint_unchanged",
        "storage_changed",
        "discovery_preserved",
        "field_matches",
        "reconfigure_verified",
        "rollback_required",
    )
    return {field: report.get(field) for field in fields}


def _record(path: Path, root: Path, *, contains_secret: bool) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            "bridge record is missing or not mode 0600"
        )
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _sha(path),
        "size": path.stat().st_size,
        "mode": "0600",
        "contains_secret": contains_secret,
    }


def _string_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _string_values(child)
    elif isinstance(value, list | tuple):
        for child in value:
            yield from _string_values(child)


def prepare_homeassistant_mqtt_legacy_evidence_bridge(
    legacy_handoff_directory: str | Path,
    legacy_postcheck_file: str | Path,
    output_directory: str | Path,
    *,
    expected_retained_topic: str,
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    token_factory: Callable[[], str] | None = None,
    homeassistant_auditor: HomeAssistantAuditor = (
        audit_homeassistant_mqtt_reconfigure_postcheck
    ),
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")

    legacy_root = Path(legacy_handoff_directory).expanduser().resolve()
    legacy_postcheck_path = Path(legacy_postcheck_file).expanduser().resolve()
    output_root = Path(output_directory).expanduser().resolve()
    _require_private_dir(legacy_root, "legacy Home Assistant handoff directory")
    _make_private_dir(output_root)
    _require_private_dir(output_root, "output directory")

    legacy_manifest_path, legacy_manifest = _validate_legacy_manifest(
        legacy_root,
        expected_retained_topic,
    )
    values_path = legacy_root / "homeassistant/reconfigure-values.json"
    values = _validate_reconfigure_values(values_path)
    legacy_postcheck = _validate_legacy_postcheck(legacy_postcheck_path)

    observed = (now or datetime.now(UTC)).astimezone(UTC)
    token = token_factory() if token_factory else secrets.token_hex(4)
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        raise HomeAssistantMqttLegacyEvidenceBridgeError("bridge token is invalid")
    name = f"greenhouse-ha-legacy-evidence-bridge-{observed:%Y%m%dT%H%M%SZ}-{token}"
    destination = output_root / name
    if destination.exists():
        raise HomeAssistantMqttLegacyEvidenceBridgeError(
            "legacy evidence bridge destination already exists"
        )

    with tempfile.TemporaryDirectory(prefix=".gh-ha-legacy-bridge-", dir=output_root) as tmp:
        root = Path(tmp) / name
        _make_private_dir(root)
        normalized = root / "homeassistant-reconfigure-handoff"
        _make_private_dir(normalized)
        normalized_values_path = normalized / "homeassistant/reconfigure-values.json"
        _write(normalized_values_path, values_path.read_bytes())

        pre_change = legacy_manifest["pre_change"]
        normalized_manifest = {
            "schema": CURRENT_HANDOFF_SCHEMA,
            "created_at": legacy_manifest.get("created_at"),
            "classification": "sensitive-local-compatibility-handoff",
            "read_only_live_services": True,
            "apply_enabled": False,
            "current_services_modified": False,
            "operator_action_required": True,
            "operator_action_authorized": False,
            "ready_for_operator_reconfigure": False,
            "target": legacy_manifest["target"],
            "pre_change": {
                "entry_fingerprint": pre_change["entry_fingerprint"],
                "storage_sha256": pre_change["storage_sha256"],
            },
            "rollback": legacy_manifest["rollback"],
            "expected_retained_topic": expected_retained_topic,
            "activation_blockers": ["legacy_evidence_bridge_for_postactivation_only"],
            "compatibility_source": {
                "schema": LEGACY_HANDOFF_SCHEMA,
                "manifest_sha256": _sha(legacy_manifest_path),
                "postcheck_schema": LEGACY_POSTCHECK_SCHEMA,
                "postcheck_sha256": _sha(legacy_postcheck_path),
                "reconfigure_values_sha256": _sha(values_path),
            },
        }
        normalized_manifest_path = normalized / "manifest.json"
        _write_json(normalized_manifest_path, normalized_manifest)

        command_runner = runner or SubprocessRunner()
        try:
            live_postcheck = homeassistant_auditor(normalized, runner=command_runner)
        except Exception as error:
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                "live Home Assistant postcheck could not be completed"
            ) from error
        _validate_current_postcheck(live_postcheck)
        if _legacy_projection(legacy_postcheck) != _current_projection(live_postcheck):
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                "legacy and live Home Assistant postchecks do not match"
            )

        normalized_postcheck_path = root / "postcheck-result.json"
        _write_json(normalized_postcheck_path, live_postcheck)
        runbook_path = root / "operator-runbook.txt"
        _write(
            runbook_path,
            b"Home Assistant MQTT legacy evidence bridge\n\n"
            b"Read-only compatibility material for the current postactivation handoff.\n"
            b"Use homeassistant-reconfigure-handoff as the Home Assistant handoff input.\n"
            b"Use postcheck-result.json as the supplied Home Assistant postcheck input.\n"
            b"This bridge does not authorize service changes, credential delivery, "
            b"storage edits, or anonymous closure.\n",
        )

        records = [
            _record(normalized_manifest_path, root, contains_secret=False),
            _record(normalized_values_path, root, contains_secret=True),
            _record(normalized_postcheck_path, root, contains_secret=False),
            _record(runbook_path, root, contains_secret=False),
        ]
        bridge_manifest = {
            "schema": SCHEMA,
            "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "classification": "sensitive-local-compatibility-bridge",
            "prepared": True,
            "read_only_live_services": True,
            "current_services_modified": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "homeassistant_authenticated": True,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "ready_for_postactivation_handoff": True,
            "ready_for_manager_migration_apply": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "bindings": {
                "legacy_handoff_manifest_sha256": _sha(legacy_manifest_path),
                "legacy_postcheck_sha256": _sha(legacy_postcheck_path),
                "legacy_reconfigure_values_sha256": _sha(values_path),
                "normalized_handoff_manifest_sha256": _sha(normalized_manifest_path),
                "normalized_postcheck_sha256": _sha(normalized_postcheck_path),
                "expected_retained_topic_sha256": _sha_bytes(
                    expected_retained_topic.encode()
                ),
            },
            "records": records,
            "secret_values_included": False,
            "source_paths_included": False,
        }
        bridge_manifest_path = root / "manifest.json"
        _write_json(bridge_manifest_path, bridge_manifest)
        manifest_sha = _sha(bridge_manifest_path)
        os.replace(root, destination)
        _fsync_dir(output_root)

    report = {
        "schema": SCHEMA,
        "prepared": True,
        "bridge_name": name,
        "normalized_handoff_relative": "homeassistant-reconfigure-handoff",
        "normalized_postcheck_relative": "postcheck-result.json",
        "read_only_live_services": True,
        "current_services_modified": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "homeassistant_authenticated": True,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "ready_for_postactivation_handoff": True,
        "ready_for_manager_migration_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "manifest_sha256": manifest_sha,
        "secret_values_included": False,
        "source_paths_included": False,
    }
    serialized = _json(report)
    for source_path in (legacy_root, legacy_postcheck_path, output_root):
        if str(source_path) in serialized:
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                "sanitized report contains a source path"
            )
    reported_strings = set(_string_values(report))
    for secret in (
        values.get("broker"),
        values.get("username"),
        values.get("password"),
        values.get("client_id"),
        legacy_postcheck.get("authorization_id"),
    ):
        if isinstance(secret, str) and secret in reported_strings:
            raise HomeAssistantMqttLegacyEvidenceBridgeError(
                "sanitized report contains secret material"
            )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize verified legacy Home Assistant MQTT evidence for the current "
            "read-only postactivation handoff."
        )
    )
    parser.add_argument("legacy_handoff_directory")
    parser.add_argument("legacy_postcheck_file")
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-retained-topic", required=True)
    args = parser.parse_args(argv)
    try:
        report = prepare_homeassistant_mqtt_legacy_evidence_bridge(
            args.legacy_handoff_directory,
            args.legacy_postcheck_file,
            args.output,
            expected_retained_topic=args.expected_retained_topic,
        )
    except (HomeAssistantMqttLegacyEvidenceBridgeError, OSError, ValueError) as error:
        print(f"T1 Home Assistant MQTT legacy evidence bridge failed: {error}", file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
