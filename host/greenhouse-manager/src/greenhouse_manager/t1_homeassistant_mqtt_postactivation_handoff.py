from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .t1_broker_identity_activation_checks import Runner
from .t1_broker_identity_postactivation_audit import (
    audit_broker_identity_postactivation,
)
from .t1_homeassistant_mqtt_reconfigure_handoff import (
    HANDOFF_SCHEMA as HOMEASSISTANT_HANDOFF_SCHEMA,
    POSTCHECK_SCHEMA as HOMEASSISTANT_POSTCHECK_SCHEMA,
    audit_homeassistant_mqtt_reconfigure_postcheck,
)
from .t1_shadow import SubprocessRunner

SCHEMA = "gh.m2.t1-homeassistant-mqtt-postactivation-handoff/1"
BROKER_HANDOFF_SCHEMA = "gh.m2.t1-broker-identity-activation-handoff/1"
BROKER_JOURNAL_SCHEMA = "gh.m2.t1-broker-identity-production-activation-journal/1"
BROKER_AUDIT_SCHEMA = "gh.m2.t1-broker-identity-postactivation-audit/1"
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{4,32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BLOCKERS = (
    "manager_identity_not_migrated",
    "node_credentials_not_delivered",
    "anonymous_closure_not_reviewed",
)

BrokerAuditor = Callable[..., dict[str, object]]
HomeAssistantAuditor = Callable[..., dict[str, object]]


class HomeAssistantMqttPostactivationHandoffError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise HomeAssistantMqttPostactivationHandoffError(
            "directory must be private and not a symlink"
        )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_private_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _read_json(path: Path, label: str, *, private: bool) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise HomeAssistantMqttPostactivationHandoffError(
            f"{label} is missing or unsafe"
        )
    if private and path.stat().st_mode & 0o777 != 0o600:
        raise HomeAssistantMqttPostactivationHandoffError(f"{label} must use mode 0600")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HomeAssistantMqttPostactivationHandoffError(
            f"{label} is invalid"
        ) from error
    if not isinstance(value, dict):
        raise HomeAssistantMqttPostactivationHandoffError(f"{label} must be an object")
    return value


def _require(
    document: Mapping[str, Any],
    required: Mapping[str, object],
    label: str,
) -> None:
    for field, expected in required.items():
        if document.get(field) != expected:
            raise HomeAssistantMqttPostactivationHandoffError(
                f"{label} verification failed: {field}"
            )


def _committed_journal(root: Path) -> tuple[Path, dict[str, Any]]:
    if not root.is_dir() or root.is_symlink():
        raise HomeAssistantMqttPostactivationHandoffError(
            "Broker transaction directory is missing or unsafe"
        )
    committed: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(root.glob("transaction-*/journal.json")):
        document = _read_json(path, "Broker transaction journal", private=True)
        if document.get("phase") == "committed":
            committed.append((path, document))
    if len(committed) != 1:
        raise HomeAssistantMqttPostactivationHandoffError(
            "exactly one committed Broker transaction journal is required"
        )
    path, document = committed[0]
    _require(
        document,
        {
            "schema": BROKER_JOURNAL_SCHEMA,
            "phase": "committed",
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "secret_values_included": False,
            "path_values_redacted": True,
        },
        "Broker transaction journal",
    )
    return path, document


def _validate_broker_handoff(root: Path) -> tuple[Path, dict[str, Any]]:
    if not root.is_dir() or root.is_symlink() or root.stat().st_mode & 0o077:
        raise HomeAssistantMqttPostactivationHandoffError(
            "Broker activation handoff directory is missing, public, or unsafe"
        )
    path = root / "manifest.json"
    document = _read_json(path, "Broker activation handoff manifest", private=True)
    _require(
        document,
        {
            "schema": BROKER_HANDOFF_SCHEMA,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_live_activation": False,
            "current_services_modified": False,
        },
        "Broker activation handoff manifest",
    )
    return path, document


def _validate_homeassistant_handoff(
    root: Path,
    expected_retained_topic: str,
) -> tuple[Path, dict[str, Any]]:
    if not root.is_dir() or root.is_symlink() or root.stat().st_mode & 0o077:
        raise HomeAssistantMqttPostactivationHandoffError(
            "Home Assistant handoff directory is missing, public, or unsafe"
        )
    path = root / "manifest.json"
    document = _read_json(path, "Home Assistant handoff manifest", private=True)
    _require(
        document,
        {
            "schema": HOMEASSISTANT_HANDOFF_SCHEMA,
            "read_only_live_services": True,
            "apply_enabled": False,
            "current_services_modified": False,
            "operator_action_required": True,
            "operator_action_authorized": False,
            "ready_for_operator_reconfigure": False,
            "expected_retained_topic": expected_retained_topic,
        },
        "Home Assistant handoff manifest",
    )
    return path, document


def _validate_homeassistant_postcheck(
    report: Mapping[str, Any],
    label: str,
) -> None:
    _require(
        report,
        {
            "schema": HOMEASSISTANT_POSTCHECK_SCHEMA,
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
        label,
    )
    field_matches = report.get("field_matches")
    if (
        not isinstance(field_matches, dict)
        or set(field_matches) != {"broker", "port", "username", "password", "client_id"}
        or any(value is not True for value in field_matches.values())
    ):
        raise HomeAssistantMqttPostactivationHandoffError(
            f"{label} field verification is incomplete"
        )


def _validate_broker_audit(report: Mapping[str, Any]) -> None:
    _require(
        report,
        {
            "schema": BROKER_AUDIT_SCHEMA,
            "read_only": True,
            "activation_verified": True,
            "rollback_required": False,
            "broker_identity_activated": True,
            "ready_for_homeassistant_reconfigure_handoff": True,
            "operator_action_authorized": False,
            "ready_for_live_apply": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "current_services_modified": False,
        },
        "Broker postactivation audit",
    )
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise HomeAssistantMqttPostactivationHandoffError(
            "Broker postactivation checks are not all passing"
        )


def _postcheck_projection(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "runtime_healthy": report.get("runtime_healthy"),
        "entry_fingerprint_unchanged": report.get("entry_fingerprint_unchanged"),
        "storage_changed": report.get("storage_changed"),
        "discovery_preserved": report.get("discovery_preserved"),
        "field_matches": report.get("field_matches"),
        "reconfigure_verified": report.get("reconfigure_verified"),
        "rollback_required": report.get("rollback_required"),
    }


def _record(path: Path, root: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise HomeAssistantMqttPostactivationHandoffError(
            "postactivation handoff file is missing or not mode 0600"
        )
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _sha256_path(path),
        "size": path.stat().st_size,
        "mode": "0600",
        "contains_secret": False,
    }


def prepare_homeassistant_mqtt_postactivation_handoff(
    broker_transaction_directory: str | Path,
    broker_activation_handoff_directory: str | Path,
    homeassistant_handoff_directory: str | Path,
    homeassistant_postcheck_file: str | Path,
    output_directory: str | Path,
    *,
    expected_retained_topic: str,
    runner: Runner | None = None,
    now: datetime | None = None,
    token_factory: Callable[[], str] | None = None,
    broker_auditor: BrokerAuditor = audit_broker_identity_postactivation,
    homeassistant_auditor: HomeAssistantAuditor = (
        audit_homeassistant_mqtt_reconfigure_postcheck
    ),
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")

    transaction_root = Path(broker_transaction_directory).expanduser().resolve()
    broker_handoff_root = (
        Path(broker_activation_handoff_directory).expanduser().resolve()
    )
    homeassistant_handoff_root = (
        Path(homeassistant_handoff_directory).expanduser().resolve()
    )
    postcheck_path = Path(homeassistant_postcheck_file).expanduser().resolve()
    output_root = Path(output_directory).expanduser().resolve()
    _private_directory(output_root)

    journal_path, journal = _committed_journal(transaction_root)
    broker_manifest_path, _broker_manifest = _validate_broker_handoff(
        broker_handoff_root
    )
    homeassistant_manifest_path, _homeassistant_manifest = (
        _validate_homeassistant_handoff(
            homeassistant_handoff_root,
            expected_retained_topic,
        )
    )
    supplied_postcheck = _read_json(
        postcheck_path,
        "supplied Home Assistant postcheck",
        private=False,
    )
    _validate_homeassistant_postcheck(
        supplied_postcheck,
        "supplied Home Assistant postcheck",
    )

    command_runner = runner or SubprocessRunner()
    try:
        live_postcheck = homeassistant_auditor(
            homeassistant_handoff_root,
            runner=command_runner,
        )
    except Exception as error:
        raise HomeAssistantMqttPostactivationHandoffError(
            "live Home Assistant postcheck could not be completed"
        ) from error
    _validate_homeassistant_postcheck(
        live_postcheck,
        "live Home Assistant postcheck",
    )
    if _postcheck_projection(supplied_postcheck) != _postcheck_projection(
        live_postcheck
    ):
        raise HomeAssistantMqttPostactivationHandoffError(
            "supplied and live Home Assistant postchecks do not match"
        )

    try:
        broker_audit = broker_auditor(
            broker_handoff_root,
            expected_retained_topic=expected_retained_topic,
            runner=command_runner,
        )
    except Exception as error:
        raise HomeAssistantMqttPostactivationHandoffError(
            "live Broker postactivation audit could not be completed"
        ) from error
    _validate_broker_audit(broker_audit)

    transaction_id = journal.get("transaction_id")
    authorization_id = journal.get("authorization_id")
    if not all(
        isinstance(value, str) and value for value in (transaction_id, authorization_id)
    ):
        raise HomeAssistantMqttPostactivationHandoffError(
            "Broker transaction identity is incomplete"
        )
    for label, value in (
        ("bundle", journal.get("bundle_sha256")),
        ("adapter contract", journal.get("adapter_contract_sha256")),
    ):
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise HomeAssistantMqttPostactivationHandoffError(
                f"Broker transaction {label} fingerprint is invalid"
            )

    observed = (now or datetime.now(UTC)).astimezone(UTC)
    token = token_factory() if token_factory else secrets.token_hex(4)
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        raise HomeAssistantMqttPostactivationHandoffError("handoff token is invalid")
    name = f"greenhouse-ha-postactivation-handoff-{observed:%Y%m%dT%H%M%SZ}-{token}"
    destination = output_root / name
    if destination.exists():
        raise HomeAssistantMqttPostactivationHandoffError(
            "postactivation handoff destination already exists"
        )
    destination.mkdir(mode=0o700)

    broker_audit_path = destination / "broker-postactivation-audit.json"
    supplied_postcheck_path = destination / "homeassistant-postcheck-supplied.json"
    live_postcheck_path = destination / "homeassistant-postcheck-live.json"
    runbook_path = destination / "operator-runbook.txt"
    _atomic_private_write(
        broker_audit_path,
        _canonical_json(broker_audit) + "\n",
    )
    _atomic_private_write(
        supplied_postcheck_path,
        _canonical_json(supplied_postcheck) + "\n",
    )
    _atomic_private_write(
        live_postcheck_path,
        _canonical_json(live_postcheck) + "\n",
    )
    _atomic_private_write(
        runbook_path,
        "Home Assistant MQTT postactivation handoff\n\n"
        "This handoff is read-only evidence for manager migration preparation.\n"
        "It does not authorize manager migration, node credential delivery, service restart, "
        "Home Assistant storage edits, or anonymous closure.\n"
        "Create a new, state-bound manager migration gate before any live change.\n",
    )

    records = [
        _record(broker_audit_path, destination),
        _record(supplied_postcheck_path, destination),
        _record(live_postcheck_path, destination),
        _record(runbook_path, destination),
    ]
    manifest = {
        "schema": SCHEMA,
        "created_at": observed.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "classification": "sensitive-local-audit-handoff",
        "read_only_live_services": True,
        "current_services_modified": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "direct_storage_edit_forbidden": True,
        "broker_identity_activated": True,
        "homeassistant_authenticated": True,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "ready_for_manager_migration_preparation": True,
        "ready_for_manager_migration_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "blockers": list(_BLOCKERS),
        "bindings": {
            "broker_transaction_journal_sha256": _sha256_path(journal_path),
            "broker_activation_handoff_manifest_sha256": _sha256_path(
                broker_manifest_path
            ),
            "homeassistant_handoff_manifest_sha256": _sha256_path(
                homeassistant_manifest_path
            ),
            "homeassistant_postcheck_source_sha256": _sha256_path(postcheck_path),
            "broker_transaction_id_fingerprint": _sha256_bytes(transaction_id.encode())[
                :16
            ],
            "broker_authorization_id_fingerprint": _sha256_bytes(
                authorization_id.encode()
            )[:16],
            "broker_bundle_sha256": journal["bundle_sha256"],
            "broker_adapter_contract_sha256": journal["adapter_contract_sha256"],
            "broker_handoff_name_fingerprint": _sha256_bytes(
                broker_handoff_root.name.encode()
            )[:16],
            "homeassistant_handoff_name_fingerprint": _sha256_bytes(
                homeassistant_handoff_root.name.encode()
            )[:16],
            "expected_retained_topic_sha256": _sha256_bytes(
                expected_retained_topic.encode()
            ),
        },
        "records": records,
        "secret_values_included": False,
        "source_paths_included": False,
    }
    manifest_path = destination / "manifest.json"
    _atomic_private_write(manifest_path, _canonical_json(manifest) + "\n")

    report = {
        "schema": SCHEMA,
        "prepared": True,
        "handoff_name": name,
        "read_only_live_services": True,
        "current_services_modified": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "broker_identity_activated": True,
        "homeassistant_authenticated": True,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "ready_for_manager_migration_preparation": True,
        "ready_for_manager_migration_apply": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "blockers": list(_BLOCKERS),
        "manifest_sha256": _sha256_path(manifest_path),
        "secret_values_included": False,
        "source_paths_included": False,
    }
    serialized = _canonical_json(report)
    for forbidden in (
        str(transaction_root),
        str(broker_handoff_root),
        str(homeassistant_handoff_root),
        str(postcheck_path),
        str(output_root),
    ):
        if forbidden in serialized:
            raise HomeAssistantMqttPostactivationHandoffError(
                "sanitized report contains a source path"
            )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a read-only bridge from successful Broker and Home Assistant "
            "postactivation evidence to manager-migration preparation."
        )
    )
    parser.add_argument("broker_transaction_directory")
    parser.add_argument("broker_activation_handoff_directory")
    parser.add_argument("homeassistant_handoff_directory")
    parser.add_argument("homeassistant_postcheck_file")
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-retained-topic", required=True)
    args = parser.parse_args(argv)
    try:
        report = prepare_homeassistant_mqtt_postactivation_handoff(
            args.broker_transaction_directory,
            args.broker_activation_handoff_directory,
            args.homeassistant_handoff_directory,
            args.homeassistant_postcheck_file,
            args.output,
            expected_retained_topic=args.expected_retained_topic,
        )
    except (HomeAssistantMqttPostactivationHandoffError, OSError, ValueError) as error:
        print(
            f"T1 Home Assistant MQTT postactivation handoff failed: {error}",
            file=sys.stderr,
        )
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
