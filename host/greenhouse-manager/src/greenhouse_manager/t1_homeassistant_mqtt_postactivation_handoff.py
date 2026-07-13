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
)
from .t1_homeassistant_mqtt_reconfigure_handoff import (
    POSTCHECK_SCHEMA as HOMEASSISTANT_POSTCHECK_SCHEMA,
)
from .t1_homeassistant_mqtt_reconfigure_handoff import (
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
_POSTCHECK_MATCH_FIELDS = {"broker", "port", "username", "password", "client_id"}

BrokerAuditor = Callable[..., dict[str, object]]
HomeAssistantAuditor = Callable[..., dict[str, object]]


class HomeAssistantMqttPostactivationHandoffError(RuntimeError):
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


def _private_dir(path: Path, label: str, *, create: bool = False) -> None:
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise HomeAssistantMqttPostactivationHandoffError(
            f"{label} is missing, public, or unsafe"
        )


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        _fsync_dir(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _load(path: Path, label: str, *, private: bool = True) -> dict[str, Any]:
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


def _must(
    document: Mapping[str, Any], required: Mapping[str, object], label: str
) -> None:
    for field, expected in required.items():
        if document.get(field) != expected:
            raise HomeAssistantMqttPostactivationHandoffError(
                f"{label} verification failed: {field}"
            )


def _journal(root: Path) -> tuple[Path, dict[str, Any]]:
    _private_dir(root, "Broker transaction directory")
    committed = [
        (path, document)
        for path in sorted(root.glob("transaction-*/journal.json"))
        if (document := _load(path, "Broker transaction journal")).get("phase")
        == "committed"
    ]
    if len(committed) != 1:
        raise HomeAssistantMqttPostactivationHandoffError(
            "exactly one committed Broker transaction journal is required"
        )
    path, document = committed[0]
    _must(
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
    for label, value in (
        ("transaction identity", document.get("transaction_id")),
        ("authorization identity", document.get("authorization_id")),
    ):
        if not isinstance(value, str) or not value:
            raise HomeAssistantMqttPostactivationHandoffError(
                f"Broker {label} is incomplete"
            )
    for label, value in (
        ("bundle", document.get("bundle_sha256")),
        ("adapter contract", document.get("adapter_contract_sha256")),
    ):
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            raise HomeAssistantMqttPostactivationHandoffError(
                f"Broker transaction {label} fingerprint is invalid"
            )
    return path, document


def _manifest(
    root: Path,
    *,
    label: str,
    schema: str,
    required: Mapping[str, object],
) -> Path:
    _private_dir(root, f"{label} directory")
    path = root / "manifest.json"
    document = _load(path, f"{label} manifest")
    _must(document, {"schema": schema, **required}, f"{label} manifest")
    return path


def _check_ha(report: Mapping[str, Any], label: str) -> None:
    _must(
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
    matches = report.get("field_matches")
    if (
        not isinstance(matches, dict)
        or set(matches) != _POSTCHECK_MATCH_FIELDS
        or any(value is not True for value in matches.values())
    ):
        raise HomeAssistantMqttPostactivationHandoffError(
            f"{label} field verification is incomplete"
        )


def _check_broker(report: Mapping[str, Any]) -> None:
    _must(
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


def _ha_projection(report: Mapping[str, Any]) -> dict[str, Any]:
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


def _record(path: Path, root: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise HomeAssistantMqttPostactivationHandoffError(
            "postactivation handoff file is missing or not mode 0600"
        )
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _sha(path),
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
    homeassistant_auditor: HomeAssistantAuditor = audit_homeassistant_mqtt_reconfigure_postcheck,
) -> dict[str, object]:
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")

    transaction_root = Path(broker_transaction_directory).expanduser().resolve()
    broker_handoff = Path(broker_activation_handoff_directory).expanduser().resolve()
    homeassistant_handoff = Path(homeassistant_handoff_directory).expanduser().resolve()
    postcheck_path = Path(homeassistant_postcheck_file).expanduser().resolve()
    output_root = Path(output_directory).expanduser().resolve()
    _private_dir(output_root, "output directory", create=True)

    journal_path, journal = _journal(transaction_root)
    broker_manifest_path = _manifest(
        broker_handoff,
        label="Broker activation handoff",
        schema=BROKER_HANDOFF_SCHEMA,
        required={
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "ready_for_live_activation": False,
            "current_services_modified": False,
        },
    )
    ha_manifest_path = _manifest(
        homeassistant_handoff,
        label="Home Assistant handoff",
        schema=HOMEASSISTANT_HANDOFF_SCHEMA,
        required={
            "read_only_live_services": True,
            "apply_enabled": False,
            "current_services_modified": False,
            "operator_action_required": True,
            "operator_action_authorized": False,
            "ready_for_operator_reconfigure": False,
            "expected_retained_topic": expected_retained_topic,
        },
    )
    supplied_postcheck = _load(
        postcheck_path, "supplied Home Assistant postcheck", private=False
    )
    _check_ha(supplied_postcheck, "supplied Home Assistant postcheck")

    command_runner = runner or SubprocessRunner()
    try:
        live_postcheck = homeassistant_auditor(
            homeassistant_handoff, runner=command_runner
        )
    except Exception as error:
        raise HomeAssistantMqttPostactivationHandoffError(
            "live Home Assistant postcheck could not be completed"
        ) from error
    _check_ha(live_postcheck, "live Home Assistant postcheck")
    if _ha_projection(supplied_postcheck) != _ha_projection(live_postcheck):
        raise HomeAssistantMqttPostactivationHandoffError(
            "supplied and live Home Assistant postchecks do not match"
        )

    try:
        broker_audit = broker_auditor(
            broker_handoff,
            expected_retained_topic=expected_retained_topic,
            runner=command_runner,
        )
    except Exception as error:
        raise HomeAssistantMqttPostactivationHandoffError(
            "live Broker postactivation audit could not be completed"
        ) from error
    _check_broker(broker_audit)

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

    with tempfile.TemporaryDirectory(
        prefix=".gh-ha-postactivation-", dir=output_root
    ) as temporary:
        root = Path(temporary) / name
        root.mkdir(mode=0o700)
        documents = {
            "broker-postactivation-audit.json": _json(broker_audit) + "\n",
            "homeassistant-postcheck-supplied.json": _json(supplied_postcheck) + "\n",
            "homeassistant-postcheck-live.json": _json(live_postcheck) + "\n",
            "operator-runbook.txt": (
                "Home Assistant MQTT postactivation handoff\n\n"
                "Read-only evidence for manager migration preparation.\n"
                "This does not authorize service changes, storage edits, credential delivery, "
                "or anonymous closure. Create a new state-bound manager migration gate.\n"
            ),
        }
        records = []
        for filename, content in documents.items():
            path = root / filename
            _write(path, content)
            records.append(_record(path, root))

        transaction_id = str(journal["transaction_id"])
        authorization_id = str(journal["authorization_id"])
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
                "broker_transaction_journal_sha256": _sha(journal_path),
                "broker_activation_handoff_manifest_sha256": _sha(broker_manifest_path),
                "homeassistant_handoff_manifest_sha256": _sha(ha_manifest_path),
                "homeassistant_postcheck_source_sha256": _sha(postcheck_path),
                "broker_transaction_id_fingerprint": _sha_bytes(
                    transaction_id.encode()
                )[:16],
                "broker_authorization_id_fingerprint": _sha_bytes(
                    authorization_id.encode()
                )[:16],
                "broker_bundle_sha256": journal["bundle_sha256"],
                "broker_adapter_contract_sha256": journal["adapter_contract_sha256"],
                "broker_handoff_name_fingerprint": _sha_bytes(
                    broker_handoff.name.encode()
                )[:16],
                "homeassistant_handoff_name_fingerprint": _sha_bytes(
                    homeassistant_handoff.name.encode()
                )[:16],
                "expected_retained_topic_sha256": _sha_bytes(
                    expected_retained_topic.encode()
                ),
            },
            "records": records,
            "secret_values_included": False,
            "source_paths_included": False,
        }
        manifest_path = root / "manifest.json"
        _write(manifest_path, _json(manifest) + "\n")
        manifest_sha = _sha(manifest_path)
        os.replace(root, destination)
        _fsync_dir(output_root)

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
        "manifest_sha256": manifest_sha,
        "secret_values_included": False,
        "source_paths_included": False,
    }
    serialized = _json(report)
    for forbidden in (
        transaction_root,
        broker_handoff,
        homeassistant_handoff,
        postcheck_path,
        output_root,
    ):
        if str(forbidden) in serialized:
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
