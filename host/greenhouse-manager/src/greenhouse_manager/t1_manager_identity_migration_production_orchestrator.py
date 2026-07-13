from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .t1_manager_identity_migration_execution_transaction_gate import (
    ManagerIdentityExecutionTransactionGateError,
    build_manager_identity_execution_transaction_gate,
)
from .t1_migration_readiness import CommandRunner, SubprocessRunner

REQUEST_SCHEMA = "gh.m2.t1-manager-identity-production-execution-request/1"
TRANSACTION_SCHEMA = "gh.m2.t1-manager-identity-production-transaction/1"
JOURNAL_SCHEMA = "gh.m2.t1-manager-identity-production-journal/1"
_AUTHORIZATION_ID = re.compile(r"^[0-9a-f]{24}$")
_TRANSACTION_ID = re.compile(r"^[A-Za-z0-9_-]{16,96}$")

TransactionGateBuilder = Callable[..., dict[str, object]]
TokenFactory = Callable[[], str]


class ManagerMigrationAdapters(Protocol):
    mutation_started: bool

    def prepare(self) -> dict[str, object]: ...

    def mutation_executor(self) -> dict[str, object]: ...

    def postactivation_auditor(self) -> dict[str, object]: ...

    def rollback_executor(self) -> dict[str, object]: ...


AdaptersFactory = Callable[..., ManagerMigrationAdapters]


class ManagerIdentityProductionOrchestratorError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_document(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _timestamp(value: datetime | None = None) -> str:
    observed = (value or datetime.now(UTC)).astimezone(UTC)
    return observed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerIdentityProductionOrchestratorError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerIdentityProductionOrchestratorError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerIdentityProductionOrchestratorError(
            f"{label} must be a JSON object"
        )
    return document


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_private_write(path: Path, document: Mapping[str, Any]) -> None:
    if path.exists() and path.is_symlink():
        raise ManagerIdentityProductionOrchestratorError(
            "private write target cannot be a symlink"
        )
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(_canonical_json(document) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _private_transaction_directory(path: Path) -> Path:
    if not path.name.startswith("greenhouse-m2-manager-production-transactions"):
        raise ManagerIdentityProductionOrchestratorError(
            "manager production transaction directory name is not allowed"
        )
    if path.exists() and path.is_symlink():
        raise ManagerIdentityProductionOrchestratorError(
            "manager production transaction directory is unsafe"
        )
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved = path.resolve()
    if resolved.is_symlink() or resolved.stat().st_mode & 0o077:
        raise ManagerIdentityProductionOrchestratorError(
            "manager production transaction directory must be private"
        )
    return resolved


def _must(
    document: Mapping[str, Any],
    required: Mapping[str, object],
    label: str,
) -> None:
    for field, expected in required.items():
        if document.get(field) is not expected:
            raise ManagerIdentityProductionOrchestratorError(
                f"{label} verification failed: {field}"
            )


def _validate_transaction_gate(gate: Mapping[str, Any]) -> None:
    _must(
        gate,
        {
            "transaction_gate_ready": True,
            "authorization_valid": True,
            "authorization_single_use": True,
            "operator_decision_required": True,
            "second_operator_confirmation_present": False,
            "authorization_claim_required": True,
            "authorization_claimed": False,
            "claim_enabled": False,
            "production_manager_driver_installed": False,
            "production_executor_available": False,
            "execution_enabled": False,
            "apply_enabled": False,
            "operator_action_authorized": True,
            "ready_for_manager_migration_apply": False,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "rollback_mandatory_on_any_post_claim_failure": True,
            "postactivation_audit_mandatory": True,
            "secret_values_included": False,
            "path_values_redacted": True,
        },
        "manager execution transaction gate",
    )
    confirmation = gate.get("required_confirmation")
    if (
        not isinstance(confirmation, str)
        or not confirmation.startswith("EXECUTE-M2-MANAGER-MIGRATION:")
    ):
        raise ManagerIdentityProductionOrchestratorError(
            "manager execution confirmation is missing or invalid"
        )
    authorization_id = gate.get("authorization_id")
    if (
        not isinstance(authorization_id, str)
        or _AUTHORIZATION_ID.fullmatch(authorization_id) is None
    ):
        raise ManagerIdentityProductionOrchestratorError(
            "manager execution authorization ID is invalid"
        )


def build_manager_identity_production_execution_request(
    authorization_file: str | Path,
    execution_preparation_directory: str | Path,
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    *,
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    transaction_gate_builder: TransactionGateBuilder = (
        build_manager_identity_execution_transaction_gate
    ),
) -> dict[str, object]:
    gate = transaction_gate_builder(
        authorization_file,
        execution_preparation_directory,
        driver_contract_file,
        preparation_directory,
        runner=runner or SubprocessRunner(),
        now=now,
    )
    _validate_transaction_gate(gate)
    return {
        "schema": REQUEST_SCHEMA,
        "transaction_gate_sha256": _sha_document(gate),
        "authorization_id": gate["authorization_id"],
        "authorization_expires_at": gate["authorization_expires_at"],
        "execution_preparation_name": gate["execution_preparation_name"],
        "execution_preparation_expires_at": gate[
            "execution_preparation_expires_at"
        ],
        "execution_preparation_manifest_sha256": gate[
            "execution_preparation_manifest_sha256"
        ],
        "fresh_rollback_archive_sha256": gate[
            "fresh_rollback_archive_sha256"
        ],
        "driver_contract_sha256": gate["driver_contract_sha256"],
        "adapter_contract_sha256": gate["adapter_contract_sha256"],
        "runtime_binding_sha256": gate["runtime_binding_sha256"],
        "live_binding_sha256": gate["live_binding_sha256"],
        "required_confirmation": gate["required_confirmation"],
        "execution_request_ready": True,
        "authorization_valid": True,
        "authorization_claimed": False,
        "second_operator_confirmation_required": True,
        "production_transaction_adapters_installed": False,
        "production_manager_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": True,
        "ready_for_manager_migration_apply": False,
        "manager_identity_migrated": False,
        "node_credentials_delivered": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def _claim_authorization(
    path: Path,
    *,
    expected_authorization_id: str,
) -> tuple[Path, dict[str, Any]]:
    document = _read_private_json(path, "manager execution authorization")
    _must(
        document,
        {
            "single_use": True,
            "consumed": False,
            "operator_action_authorized": True,
            "authorization_claimed": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        },
        "manager execution authorization",
    )
    authorization_id = document.get("authorization_id")
    if authorization_id != expected_authorization_id:
        raise ManagerIdentityProductionOrchestratorError(
            "manager execution authorization ID binding failed"
        )
    claim = path.with_name(f"claimed-manager-execution-authorization-{authorization_id}.json")
    try:
        source_inode = path.stat().st_ino
        os.link(path, claim, follow_symlinks=False)
        _fsync_directory(path.parent)
    except FileExistsError as error:
        raise ManagerIdentityProductionOrchestratorError(
            "manager execution authorization has already been claimed"
        ) from error
    except OSError as error:
        raise ManagerIdentityProductionOrchestratorError(
            "manager execution authorization could not be atomically claimed"
        ) from error
    try:
        path.unlink()
        _fsync_directory(path.parent)
    except OSError as error:
        claim.unlink(missing_ok=True)
        _fsync_directory(path.parent)
        raise ManagerIdentityProductionOrchestratorError(
            "manager execution authorization claim could not remove the source name"
        ) from error
    if (
        path.exists()
        or not claim.is_file()
        or claim.is_symlink()
        or claim.stat().st_mode & 0o777 != 0o600
        or claim.stat().st_ino != source_inode
    ):
        raise ManagerIdentityProductionOrchestratorError(
            "manager execution authorization claim verification failed"
        )
    return claim, document


def _mark_consumed(
    claim: Path,
    document: dict[str, Any],
    *,
    transaction_id: str,
    consumed_at: str,
) -> None:
    document["authorization_claimed"] = True
    document["consumed"] = True
    document["consumed_at"] = consumed_at
    document["transaction_id"] = transaction_id
    _atomic_private_write(claim, document)


def _validate_adapter_installation(report: Mapping[str, Any]) -> None:
    _must(
        report,
        {
            "production_transaction_adapters_installed": True,
            "production_manager_driver_installed": True,
            "execution_entrypoint_installed": False,
            "greenhouse_manager_only": True,
            "mosquitto_target_allowed": False,
            "homeassistant_target_allowed": False,
            "node_target_allowed": False,
            "current_services_modified": False,
        },
        "manager production adapter preparation",
    )


def _validate_mutation(report: Mapping[str, Any]) -> None:
    _must(
        report,
        {
            "mutation_started": True,
            "manager_material_installed": True,
            "greenhouse_manager_recreated": True,
            "manager_restart_count_zero": True,
            "mosquitto_modified": False,
            "homeassistant_modified": False,
            "nodes_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        },
        "manager production mutation",
    )


def _validate_postactivation(report: Mapping[str, Any]) -> None:
    _must(
        report,
        {
            "manager_identity_migrated": True,
            "manager_authenticated": True,
            "ingress_subscription_verified": True,
            "canonical_publication_verified": True,
            "availability_publication_verified": True,
            "discovery_publication_verified": True,
            "reconnect_verified": True,
            "existing_entities_verified": True,
            "rollback_required": False,
            "node_credentials_delivered": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        },
        "manager production postactivation audit",
    )
    checks = report.get("checks")
    if not isinstance(checks, dict) or not checks or any(
        value is not True for value in checks.values()
    ):
        raise ManagerIdentityProductionOrchestratorError(
            "manager production postactivation checks are not all passing"
        )


def _validate_rollback(report: Mapping[str, Any]) -> None:
    _must(
        report,
        {
            "rollback_completed": True,
            "manager_material_restored": True,
            "compose_binding_restored": True,
            "greenhouse_manager_recreated": True,
            "legacy_anonymous_path_verified": True,
            "existing_entities_verified": True,
            "mosquitto_modified": False,
            "homeassistant_modified": False,
            "nodes_modified": False,
            "current_services_modified": False,
        },
        "manager production rollback",
    )


def _journal(
    path: Path,
    document: dict[str, Any],
    *,
    phase: str,
    now: datetime | None = None,
    details: Mapping[str, object] | None = None,
) -> None:
    document["phase"] = phase
    document["updated_at"] = _timestamp(now)
    if details is not None:
        document["details"] = dict(details)
    else:
        document.pop("details", None)
    _atomic_private_write(path, document)


def _disabled_adapters_factory(*_args: object, **_kwargs: object) -> ManagerMigrationAdapters:
    raise ManagerIdentityProductionOrchestratorError(
        "production manager transaction adapters are not installed"
    )


def _request_binding(request: Mapping[str, Any]) -> tuple[object, ...]:
    fields = (
        "transaction_gate_sha256",
        "authorization_id",
        "execution_preparation_name",
        "execution_preparation_manifest_sha256",
        "fresh_rollback_archive_sha256",
        "driver_contract_sha256",
        "adapter_contract_sha256",
        "runtime_binding_sha256",
        "live_binding_sha256",
        "required_confirmation",
    )
    return tuple(request.get(field) for field in fields)


def execute_manager_identity_production_migration(
    authorization_file: str | Path,
    execution_preparation_directory: str | Path,
    driver_contract_file: str | Path,
    preparation_directory: str | Path,
    transaction_directory: str | Path,
    *,
    execution_confirmation: str,
    execution_enabled: bool = False,
    runner: CommandRunner | None = None,
    now: datetime | None = None,
    token_factory: TokenFactory | None = None,
    transaction_gate_builder: TransactionGateBuilder = (
        build_manager_identity_execution_transaction_gate
    ),
    adapters_factory: AdaptersFactory = _disabled_adapters_factory,
) -> dict[str, object]:
    if not execution_enabled:
        raise ManagerIdentityProductionOrchestratorError(
            "production manager migration execution is disabled"
        )

    command_runner = runner or SubprocessRunner()
    request = build_manager_identity_production_execution_request(
        authorization_file,
        execution_preparation_directory,
        driver_contract_file,
        preparation_directory,
        runner=command_runner,
        now=now,
        transaction_gate_builder=transaction_gate_builder,
    )
    required_confirmation = request.get("required_confirmation")
    if not isinstance(required_confirmation, str) or not hmac.compare_digest(
        execution_confirmation,
        required_confirmation,
    ):
        raise ManagerIdentityProductionOrchestratorError(
            "explicit manager migration execution confirmation is missing or does not match"
        )

    authorization_path = Path(authorization_file).expanduser().resolve()
    authorization_preview = _read_private_json(
        authorization_path,
        "manager execution authorization",
    )
    if authorization_preview.get("authorization_id") != request.get("authorization_id"):
        raise ManagerIdentityProductionOrchestratorError(
            "manager execution authorization ID binding failed"
        )
    execution_root = Path(execution_preparation_directory).expanduser().resolve()
    driver_path = Path(driver_contract_file).expanduser().resolve()
    preparation_root = Path(preparation_directory).expanduser().resolve()
    transaction_root = _private_transaction_directory(
        Path(transaction_directory).expanduser()
    )

    transaction_id = token_factory() if token_factory else secrets.token_urlsafe(24)
    if (
        not isinstance(transaction_id, str)
        or _TRANSACTION_ID.fullmatch(transaction_id) is None
    ):
        raise ManagerIdentityProductionOrchestratorError(
            "manager production transaction ID is invalid"
        )
    workspace = transaction_root / f"transaction-{transaction_id}"
    workspace.mkdir(mode=0o700)
    if workspace.stat().st_mode & 0o077:
        raise ManagerIdentityProductionOrchestratorError(
            "manager production transaction workspace must be private"
        )
    journal_path = workspace / "journal.json"
    journal: dict[str, Any] = {
        "schema": JOURNAL_SCHEMA,
        "transaction_id": transaction_id,
        "authorization_id": request["authorization_id"],
        "transaction_gate_sha256": request["transaction_gate_sha256"],
        "execution_preparation_manifest_sha256": request[
            "execution_preparation_manifest_sha256"
        ],
        "fresh_rollback_archive_sha256": request[
            "fresh_rollback_archive_sha256"
        ],
        "live_binding_sha256": request["live_binding_sha256"],
        "created_at": _timestamp(now),
        "target": "greenhouse-manager",
        "mosquitto_target_allowed": False,
        "homeassistant_target_allowed": False,
        "node_target_allowed": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
    _journal(journal_path, journal, phase="preparing_snapshot", now=now)

    adapters = adapters_factory(
        driver_path,
        execution_root,
        preparation_root,
        workspace,
        runner=command_runner,
    )
    installation = adapters.prepare()
    _validate_adapter_installation(installation)
    _journal(journal_path, journal, phase="snapshot_ready", now=now)

    refreshed = build_manager_identity_production_execution_request(
        authorization_path,
        execution_root,
        driver_path,
        preparation_root,
        runner=command_runner,
        now=now,
        transaction_gate_builder=transaction_gate_builder,
    )
    if _request_binding(refreshed) != _request_binding(request):
        raise ManagerIdentityProductionOrchestratorError(
            "manager production execution binding drifted before authorization claim"
        )

    claim_succeeded = False
    mutation: dict[str, object] | None = None
    postactivation: dict[str, object] | None = None
    rollback: dict[str, object] | None = None
    failure: Exception | None = None
    rollback_failure: Exception | None = None
    try:
        claim, authorization_document = _claim_authorization(
            authorization_path,
            expected_authorization_id=str(request["authorization_id"]),
        )
        claim_succeeded = True
        _mark_consumed(
            claim,
            authorization_document,
            transaction_id=transaction_id,
            consumed_at=_timestamp(now),
        )
        _journal(journal_path, journal, phase="authorization_claimed", now=now)

        _journal(journal_path, journal, phase="mutation_started", now=now)
        mutation = adapters.mutation_executor()
        _validate_mutation(mutation)
        _journal(journal_path, journal, phase="mutation_completed", now=now)

        postactivation = adapters.postactivation_auditor()
        _validate_postactivation(postactivation)
        _journal(journal_path, journal, phase="postactivation_verified", now=now)
    except Exception as error:
        failure = error
        if claim_succeeded:
            try:
                _journal(journal_path, journal, phase="rollback_started", now=now)
                rollback = adapters.rollback_executor()
                _validate_rollback(rollback)
                _journal(journal_path, journal, phase="rollback_completed", now=now)
            except Exception as error_after_rollback:
                rollback_failure = error_after_rollback
                _journal(
                    journal_path,
                    journal,
                    phase="rollback_failed",
                    now=now,
                    details={"terminal": True},
                )

    if rollback_failure is not None:
        raise ManagerIdentityProductionOrchestratorError(
            "manager migration failed and rollback failed"
        ) from rollback_failure
    if failure is not None:
        if claim_succeeded and rollback is None:
            raise ManagerIdentityProductionOrchestratorError(
                "manager migration failed after authorization claim without verified rollback"
            ) from failure
        raise ManagerIdentityProductionOrchestratorError(
            "manager migration failed and verified rollback completed"
        ) from failure
    if mutation is None or postactivation is None:
        raise ManagerIdentityProductionOrchestratorError(
            "manager migration ended without complete reports"
        )

    _journal(journal_path, journal, phase="committed", now=now)
    return {
        "schema": TRANSACTION_SCHEMA,
        "transaction_id": transaction_id,
        "authorization_id": request["authorization_id"],
        "authorization_claimed": True,
        "authorization_consumed": True,
        "mutation_completed": True,
        "postactivation_verified": True,
        "rollback_completed": False,
        "manager_identity_migrated": True,
        "ready_for_node_credential_delivery_preparation": True,
        "node_credentials_delivered": False,
        "production_transaction_adapters_installed": True,
        "production_manager_driver_installed": True,
        "production_executor_available": True,
        "execution_enabled": True,
        "apply_enabled": True,
        "current_services_modified": True,
        "mosquitto_modified": False,
        "homeassistant_modified": False,
        "nodes_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
