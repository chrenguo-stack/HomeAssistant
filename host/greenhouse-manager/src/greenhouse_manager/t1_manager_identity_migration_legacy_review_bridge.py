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

from .t1_manager_identity_migration_postrollback_audit import (
    SCHEMA as POSTROLLBACK_AUDIT_SCHEMA,
)
from .t1_manager_identity_migration_postrollback_audit import (
    ManagerPostrollbackAuditError,
    build_manager_postrollback_audit,
)

SCHEMA = "gh.m2.t1-manager-identity-legacy-review-bridge/1"
DECISION_SCHEMA = "gh.m2.t1-manager-identity-legacy-review-decision/1"
OPERATOR_CONFIRMATION = "ACCEPT-M2-LEGACY-ROLLBACK-EVIDENCE-GAP"
_TOKEN = re.compile(r"^[a-z0-9_-]{4,32}$")

AuditBuilder = Callable[..., dict[str, object]]


class ManagerIdentityLegacyReviewBridgeError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_bytes(value: Any) -> bytes:
    return (_json(value) + "\n").encode()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _make_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def _require_private_directory(path: Path, label: str) -> None:
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ManagerIdentityLegacyReviewBridgeError(
            f"{label} is missing, public, or unsafe"
        )


def _require_private_file(path: Path, label: str) -> Path:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerIdentityLegacyReviewBridgeError(
            f"{label} is missing, public, or unsafe"
        )
    return path


def _write(path: Path, value: bytes) -> None:
    _make_private_directory(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _matches(actual: object, expected: object) -> bool:
    if isinstance(expected, bool):
        return actual is expected
    if expected is None:
        return actual is None
    return actual == expected


def _require_fields(
    document: Mapping[str, Any],
    required: Mapping[str, object],
    label: str,
) -> None:
    for field, expected in required.items():
        if field not in document or not _matches(document[field], expected):
            raise ManagerIdentityLegacyReviewBridgeError(
                f"{label} verification failed: {field}"
            )


def _require_exact_map(
    value: object,
    expected: Mapping[str, object],
    label: str,
) -> None:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ManagerIdentityLegacyReviewBridgeError(f"{label} is incomplete")
    _require_fields(value, expected, label)


def validate_legacy_manager_postrollback_audit(
    report: Mapping[str, Any],
) -> dict[str, object]:
    _require_fields(
        report,
        {
            "schema": POSTROLLBACK_AUDIT_SCHEMA,
            "read_only": True,
            "rollback_audit_passed": False,
            "baseline_unavailable": True,
            "environment_baseline_unavailable": True,
            "directory_baseline_unavailable": True,
            "baseline_required_for_pass": True,
            "manual_recovery_required": False,
            "manual_review_required": True,
            "environment_restored": False,
            "broad_compose_directory_considered": False,
            "current_services_modified": False,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "secret_values_included": False,
            "path_values_redacted": True,
        },
        "legacy postrollback audit",
    )
    _require_exact_map(
        report.get("checks"),
        {
            "journal_phase": True,
            "rollback_completed": True,
            "rollback_failed": True,
            "auth_overlay_exists": True,
            "auth_environment_exists": True,
            "password_target_exists": True,
            "password_mount_count": True,
            "manager_running": True,
            "manager_restart_count_zero": True,
            "manager_stable_mqtt_socket": True,
            "manager_image_preserved": True,
            "mosquitto_unchanged": True,
            "homeassistant_unchanged": True,
            "anonymous_retained_path_readable": True,
            "created_directory_targets_cleanup_complete": None,
        },
        "legacy postrollback checks",
    )
    _require_exact_map(
        report.get("environment_checks"),
        {
            "gh_mqtt_username_restored": None,
            "gh_mqtt_password_restored": None,
            "gh_mqtt_password_file_restored": None,
        },
        "legacy authentication environment checks",
    )
    _require_exact_map(
        report.get("exact_target_checks"),
        {
            "auth_overlay_removed": True,
            "auth_environment_removed": True,
            "password_target_removed": True,
            "password_mount_removed": True,
            "created_directory_targets_clean": None,
        },
        "legacy exact target checks",
    )
    try:
        normalized = json.loads(_json(report))
    except (TypeError, ValueError) as error:
        raise ManagerIdentityLegacyReviewBridgeError(
            "legacy postrollback audit is not canonical JSON"
        ) from error
    if not isinstance(normalized, dict):
        raise ManagerIdentityLegacyReviewBridgeError(
            "legacy postrollback audit must be an object"
        )
    return normalized


def _record(path: Path, root: Path) -> dict[str, object]:
    _require_private_file(path, "legacy review bridge record")
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _sha(path),
        "size": path.stat().st_size,
        "mode": "0600",
        "contains_secret": False,
    }


def prepare_manager_identity_legacy_review_bridge(
    transaction_workspace: str | Path,
    execution_preparation_directory: str | Path,
    output_directory: str | Path,
    *,
    expected_retained_topic: str,
    operator_confirmation: str,
    mqtt_port: int = 1883,
    timeout_s: float = 8.0,
    poll_interval_s: float = 1.0,
    proc_root: str | Path = "/proc",
    runner: Any | None = None,
    sleeper: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    now: datetime | None = None,
    token_factory: Callable[[], str] | None = None,
    audit_builder: AuditBuilder = build_manager_postrollback_audit,
) -> dict[str, object]:
    if operator_confirmation != OPERATOR_CONFIRMATION:
        raise ManagerIdentityLegacyReviewBridgeError(
            "operator confirmation does not accept the exact legacy evidence gap"
        )
    if (
        not expected_retained_topic.startswith("gh/")
        or "+" in expected_retained_topic
        or "#" in expected_retained_topic
    ):
        raise ValueError("expected retained topic must be an exact gh topic")

    audit_arguments: dict[str, Any] = {
        "expected_retained_topic": expected_retained_topic,
        "mqtt_port": mqtt_port,
        "timeout_s": timeout_s,
        "poll_interval_s": poll_interval_s,
        "proc_root": proc_root,
    }
    if runner is not None:
        audit_arguments["runner"] = runner
    if sleeper is not None:
        audit_arguments["sleeper"] = sleeper
    if monotonic is not None:
        audit_arguments["monotonic"] = monotonic
    audit = validate_legacy_manager_postrollback_audit(
        audit_builder(
            transaction_workspace,
            execution_preparation_directory,
            **audit_arguments,
        )
    )

    transaction = Path(transaction_workspace).expanduser().resolve()
    execution = Path(execution_preparation_directory).expanduser().resolve()
    journal = _require_private_file(
        transaction / "journal.json",
        "manager production transaction journal",
    )
    rollback_manifest = _require_private_file(
        execution / "fresh-rollback-manifest.json",
        "fresh rollback manifest",
    )
    rollback_archive = _require_private_file(
        execution / "fresh-manager-rollback.tar.gz",
        "fresh rollback archive",
    )

    output_root = Path(output_directory).expanduser().resolve()
    _make_private_directory(output_root)
    _require_private_directory(output_root, "legacy review output directory")
    observed = (now or datetime.now(UTC)).astimezone(UTC)
    created_at = observed.isoformat().replace("+00:00", "Z")
    token = token_factory() if token_factory else secrets.token_hex(4)
    if not isinstance(token, str) or _TOKEN.fullmatch(token) is None:
        raise ManagerIdentityLegacyReviewBridgeError("bridge token is invalid")
    name = f"greenhouse-manager-legacy-review-bridge-{observed:%Y%m%dT%H%M%SZ}-{token}"
    destination = output_root / name
    if destination.exists() or destination.is_symlink():
        raise ManagerIdentityLegacyReviewBridgeError(
            "legacy review bridge destination already exists"
        )

    audit_payload = _json_bytes(audit)
    audit_sha256 = _sha_bytes(audit_payload)
    confirmation_sha256 = _sha_bytes(operator_confirmation.encode())
    decision = {
        "schema": DECISION_SCHEMA,
        "created_at": created_at,
        "decision": "accept_legacy_baseline_gap_for_fresh_evidence_chain_only",
        "operator_decision_recorded": True,
        "operator_confirmation_sha256": confirmation_sha256,
        "legacy_audit_sha256": audit_sha256,
        "legacy_baseline_gap_accepted": True,
        "rollback_audit_passed": False,
        "manual_recovery_required": False,
        "manual_review_resolved": True,
        "future_baseline_waiver_enabled": False,
        "ready_for_fresh_evidence_chain": True,
        "ready_for_production_execution": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }

    with tempfile.TemporaryDirectory(
        prefix=".gh-manager-legacy-review-",
        dir=output_root,
    ) as temporary:
        root = Path(temporary) / name
        _make_private_directory(root)
        audit_path = root / "audit-report.json"
        decision_path = root / "operator-decision.json"
        _write(audit_path, audit_payload)
        _write(decision_path, _json_bytes(decision))
        records = [_record(audit_path, root), _record(decision_path, root)]
        manifest = {
            "schema": SCHEMA,
            "created_at": created_at,
            "classification": "private-operator-decision-record",
            "read_only_live_services": True,
            "current_services_modified": False,
            "operator_decision_recorded": True,
            "legacy_baseline_gap_accepted": True,
            "rollback_audit_passed": False,
            "manual_recovery_required": False,
            "manual_review_resolved": True,
            "future_baseline_waiver_enabled": False,
            "ready_for_fresh_evidence_chain": True,
            "ready_for_production_execution": False,
            "authorization_created": False,
            "authorization_claimed": False,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "bindings": {
                "transaction_journal_sha256": _sha(journal),
                "fresh_rollback_manifest_sha256": _sha(rollback_manifest),
                "fresh_rollback_archive_sha256": _sha(rollback_archive),
                "legacy_audit_sha256": audit_sha256,
                "operator_confirmation_sha256": confirmation_sha256,
                "expected_retained_topic_sha256": _sha_bytes(
                    expected_retained_topic.encode()
                ),
            },
            "records": records,
            "secret_values_included": False,
            "source_paths_included": False,
        }
        manifest_path = root / "manifest.json"
        _write(manifest_path, _json_bytes(manifest))
        manifest_sha256 = _sha(manifest_path)
        os.replace(root, destination)
        _fsync_directory(output_root)

    report = {
        "schema": SCHEMA,
        "prepared": True,
        "bridge_name": name,
        "operator_decision_recorded": True,
        "legacy_baseline_gap_accepted": True,
        "rollback_audit_passed": False,
        "manual_recovery_required": False,
        "manual_review_resolved": True,
        "future_baseline_waiver_enabled": False,
        "ready_for_fresh_evidence_chain": True,
        "ready_for_production_execution": False,
        "authorization_created": False,
        "authorization_claimed": False,
        "read_only_live_services": True,
        "current_services_modified": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "manifest_sha256": manifest_sha256,
        "secret_values_included": False,
        "source_paths_included": False,
    }
    serialized = _json(report)
    for source in (transaction, execution, output_root):
        if str(source) in serialized:
            raise ManagerIdentityLegacyReviewBridgeError(
                "sanitized report contains a source path"
            )
    if operator_confirmation in serialized:
        raise ManagerIdentityLegacyReviewBridgeError(
            "sanitized report contains the operator confirmation"
        )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Re-audit a legacy greenhouse-manager rollback and record an explicit "
            "operator acceptance of its unavailable historical baselines."
        )
    )
    parser.add_argument("transaction_workspace")
    parser.add_argument("execution_preparation_directory")
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--operator-confirmation", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = prepare_manager_identity_legacy_review_bridge(
            args.transaction_workspace,
            args.execution_preparation_directory,
            args.output,
            expected_retained_topic=args.expected_retained_topic,
            operator_confirmation=args.operator_confirmation,
            mqtt_port=args.mqtt_port,
            timeout_s=args.timeout_seconds,
            poll_interval_s=args.poll_interval_seconds,
        )
    except (
        ManagerIdentityLegacyReviewBridgeError,
        ManagerPostrollbackAuditError,
        OSError,
        UnicodeError,
        ValueError,
    ):
        print("T1 manager legacy review bridge failed safely", file=sys.stderr)
        return 2
    print(_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
