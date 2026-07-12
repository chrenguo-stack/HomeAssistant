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

from .t1_broker_identity_activation_checks import Runner
from .t1_broker_identity_activation_readiness_authorization import (
    verify_activation_readiness_authorization,
)
from .t1_broker_identity_activation_readiness_bundle import (
    verify_activation_readiness_bundle,
)
from .t1_broker_identity_activation_readiness_transaction_plan import (
    verify_activation_readiness_transaction_plan,
)
from .t1_broker_identity_production_broker_driver import (
    LiveProductionBrokerDriver,
)
from .t1_broker_identity_production_executor_contract import (
    verify_production_executor_contract,
)
from .t1_broker_identity_production_transaction_adapter_contract import (
    verify_production_transaction_adapter_contract,
)
from .t1_broker_identity_production_transaction_adapters import (
    ProductionTransactionAdapters,
)
from .t1_broker_identity_runtime_binding_manifest import (
    verify_runtime_binding_manifest,
)
from .t1_shadow import SubprocessRunner

REQUEST_SCHEMA = "gh.m2.t1-broker-identity-production-activation-execution-request/1"
TRANSACTION_SCHEMA = "gh.m2.t1-broker-identity-production-activation-transaction/1"
JOURNAL_SCHEMA = "gh.m2.t1-broker-identity-production-activation-journal/1"
_AUTHORIZATION_ID = re.compile(r"^[0-9a-f]{24}$")
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,96}$")

AuthorizationVerifier = Callable[..., dict[str, object]]
DocumentVerifier = Callable[[dict[str, object]], dict[str, object]]
ManifestVerifier = Callable[[str | Path], dict[str, object]]
TokenFactory = Callable[[], str]


class ActivationAdapters(Protocol):
    mutation_started: bool

    def prepare(self) -> dict[str, object]: ...

    def mutation_executor(self) -> dict[str, object]: ...

    def postactivation_auditor(self) -> dict[str, object]: ...

    def rollback_executor(self) -> dict[str, object]: ...


AdaptersFactory = Callable[..., ActivationAdapters]
DriverFactory = Callable[..., Any]


class BrokerIdentityProductionActivationOrchestratorError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_document(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(document).encode("utf-8")).hexdigest()


def _timestamp(value: datetime | None = None) -> str:
    observed = (value or datetime.now(UTC)).astimezone(UTC)
    return observed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise BrokerIdentityProductionActivationOrchestratorError(
            f"{label} is missing, unsafe, or not mode 0600"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityProductionActivationOrchestratorError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise BrokerIdentityProductionActivationOrchestratorError(f"{label} must be a JSON object")
    return document


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_private_write(path: Path, document: Mapping[str, Any]) -> None:
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
    if not path.name.startswith("greenhouse-m2-production-transactions"):
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production transaction directory name is not allowed"
        )
    if path.exists() and path.is_symlink():
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production transaction directory is unsafe"
        )
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved = path.resolve()
    if resolved.is_symlink() or resolved.stat().st_mode & 0o077:
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production transaction directory must be private"
        )
    return resolved


def _verified(
    result: Mapping[str, Any],
    label: str,
    *,
    required: Mapping[str, object] | None = None,
) -> None:
    if result.get("verified") is not True:
        raise BrokerIdentityProductionActivationOrchestratorError(f"{label} verification is incomplete")
    for field, expected in (required or {}).items():
        if result.get(field) is not expected:
            raise BrokerIdentityProductionActivationOrchestratorError(f"{label} verification failed: {field}")


def _validate_bindings(
    authorization: Mapping[str, Any],
    bundle: Mapping[str, Any],
    plan: Mapping[str, Any],
    adapter_contract: Mapping[str, Any],
    executor_contract: Mapping[str, Any],
    runtime_manifest: Mapping[str, Any],
) -> None:
    fields = (
        "bundle_sha256",
        "driver_contract_sha256",
        "contract_sha256",
        "mount_binding_sha256",
        "runtime_binding_manifest_sha256",
        "production_driver_preflight_sha256",
        "homeassistant_target_gate_sha256",
    )
    for field in fields:
        expected = plan.get(field)
        if (
            not isinstance(expected, str)
            or authorization.get(field) != expected
            or bundle.get(field) != expected
            or adapter_contract.get(field) != expected
        ):
            raise BrokerIdentityProductionActivationOrchestratorError(
                f"production activation binding failed: {field}"
            )
    if executor_contract.get("contract_sha256") != plan.get("contract_sha256"):
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production executor binding does not match"
        )
    if runtime_manifest.get("manifest_sha256") != plan.get("runtime_binding_manifest_sha256"):
        raise BrokerIdentityProductionActivationOrchestratorError("runtime manifest binding does not match")
    if adapter_contract.get("transaction_plan_sha256") != plan.get("plan_sha256"):
        raise BrokerIdentityProductionActivationOrchestratorError("transaction plan binding does not match")
    authorization_sha = _sha256_document(authorization)
    if (
        plan.get("authorization_document_sha256") != authorization_sha
        or adapter_contract.get("authorization_document_sha256") != authorization_sha
    ):
        raise BrokerIdentityProductionActivationOrchestratorError(
            "authorization document binding does not match"
        )
    for field in (
        "broker_runtime_fingerprint",
        "homeassistant_binding",
        "activation_scope",
    ):
        expected = plan.get(field)
        if authorization.get(field) != expected or bundle.get(field) != expected:
            raise BrokerIdentityProductionActivationOrchestratorError(
                f"production activation scope binding failed: {field}"
            )


def _confirmation(
    plan: Mapping[str, Any],
    adapter_contract: Mapping[str, Any],
) -> str:
    bundle_sha = plan.get("bundle_sha256")
    runtime = plan.get("broker_runtime_fingerprint")
    adapter_sha = adapter_contract.get("adapter_contract_sha256")
    if not all(isinstance(value, str) and value for value in (bundle_sha, runtime, adapter_sha)):
        raise BrokerIdentityProductionActivationOrchestratorError(
            "execution confirmation binding is incomplete"
        )
    return f"EXECUTE-M2-BROKER-ACTIVATION:{bundle_sha[:16]}:{runtime}:{adapter_sha[:16]}"


def build_production_activation_execution_request(
    authorization_file: str | Path,
    activation_readiness_bundle_file: str | Path,
    transaction_plan_file: str | Path,
    adapter_contract_file: str | Path,
    executor_contract_file: str | Path,
    runtime_binding_manifest_file: str | Path,
    *,
    now: datetime | None = None,
    authorization_verifier: AuthorizationVerifier = (verify_activation_readiness_authorization),
    bundle_verifier: DocumentVerifier = verify_activation_readiness_bundle,
    plan_verifier: DocumentVerifier = verify_activation_readiness_transaction_plan,
    adapter_contract_verifier: DocumentVerifier = (verify_production_transaction_adapter_contract),
    executor_verifier: DocumentVerifier = verify_production_executor_contract,
    manifest_verifier: ManifestVerifier = verify_runtime_binding_manifest,
) -> dict[str, object]:
    authorization_path = Path(authorization_file).expanduser().resolve()
    bundle_path = Path(activation_readiness_bundle_file).expanduser().resolve()
    plan_path = Path(transaction_plan_file).expanduser().resolve()
    adapter_path = Path(adapter_contract_file).expanduser().resolve()
    executor_path = Path(executor_contract_file).expanduser().resolve()
    manifest_path = Path(runtime_binding_manifest_file).expanduser().resolve()

    authorization = _read_private_json(authorization_path, "activation authorization")
    bundle = _read_private_json(bundle_path, "activation readiness bundle")
    plan = _read_private_json(plan_path, "transaction plan")
    adapter_contract = _read_private_json(
        adapter_path,
        "production transaction adapter contract",
    )
    executor_contract = _read_private_json(
        executor_path,
        "production executor contract",
    )
    runtime_manifest = _read_private_json(
        manifest_path,
        "runtime binding manifest",
    )

    authorization_result = authorization_verifier(
        authorization_path,
        bundle_path,
        now=now,
        bundle_verifier=bundle_verifier,
    )
    required_authorization = {
        "valid_now": True,
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required_authorization.items():
        if authorization_result.get(field) is not expected:
            raise BrokerIdentityProductionActivationOrchestratorError(
                f"activation authorization verification failed: {field}"
            )

    _verified(bundle_verifier(bundle), "activation readiness bundle")
    _verified(plan_verifier(plan), "transaction plan")
    _verified(adapter_contract_verifier(adapter_contract), "adapter contract")
    _verified(executor_verifier(executor_contract), "executor contract")
    _verified(manifest_verifier(manifest_path), "runtime manifest")
    _validate_bindings(
        authorization,
        bundle,
        plan,
        adapter_contract,
        executor_contract,
        runtime_manifest,
    )

    authorization_id = authorization.get("authorization_id")
    if not isinstance(authorization_id, str) or _AUTHORIZATION_ID.fullmatch(authorization_id) is None:
        raise BrokerIdentityProductionActivationOrchestratorError("activation authorization ID is invalid")
    return {
        "schema": REQUEST_SCHEMA,
        "authorization_id": authorization_id,
        "bundle_sha256": plan["bundle_sha256"],
        "broker_runtime_fingerprint": plan["broker_runtime_fingerprint"],
        "adapter_contract_sha256": adapter_contract["adapter_contract_sha256"],
        "required_confirmation": _confirmation(plan, adapter_contract),
        "execution_request_ready": True,
        "authorization_valid": True,
        "authorization_claimed": False,
        "production_transaction_adapters_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }


def _claim_authorization(path: Path) -> tuple[Path, dict[str, Any]]:
    document = _read_private_json(path, "activation authorization")
    authorization_id = document.get("authorization_id")
    if not isinstance(authorization_id, str) or _AUTHORIZATION_ID.fullmatch(authorization_id) is None:
        raise BrokerIdentityProductionActivationOrchestratorError("activation authorization ID is invalid")
    claim = path.with_name(f"claimed-{authorization_id}.json")
    try:
        os.link(path, claim, follow_symlinks=False)
        _fsync_directory(path.parent)
    except FileExistsError as error:
        raise BrokerIdentityProductionActivationOrchestratorError(
            "activation authorization has already been claimed"
        ) from error
    except OSError as error:
        raise BrokerIdentityProductionActivationOrchestratorError(
            "activation authorization could not be atomically claimed"
        ) from error
    try:
        path.unlink()
        _fsync_directory(path.parent)
    except OSError as error:
        claim.unlink(missing_ok=True)
        _fsync_directory(path.parent)
        raise BrokerIdentityProductionActivationOrchestratorError(
            "activation authorization claim could not remove the source name"
        ) from error
    return claim, document


def _mark_consumed(
    claim: Path,
    document: dict[str, Any],
    *,
    transaction_id: str,
    consumed_at: str,
) -> None:
    document["consumed"] = True
    document["consumed_at"] = consumed_at
    document["transaction_id"] = transaction_id
    _atomic_private_write(claim, document)


def _validate_mutation(report: Mapping[str, Any]) -> None:
    required = {
        "mutation_started": True,
        "mosquitto_restarted": True,
        "bootstrap_admin_removed": True,
        "provisioning_identity_verified": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if report.get(field) is not expected:
            raise BrokerIdentityProductionActivationOrchestratorError(f"production mutation failed: {field}")


def _validate_postactivation(report: Mapping[str, Any]) -> None:
    required = {
        "activation_verified": True,
        "rollback_required": False,
        "broker_identity_activated": True,
        "ready_for_homeassistant_reconfigure_handoff": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if report.get(field) is not expected:
            raise BrokerIdentityProductionActivationOrchestratorError(
                f"production postactivation audit failed: {field}"
            )
    checks = report.get("checks")
    if not isinstance(checks, dict) or not checks or any(value is not True for value in checks.values()):
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production postactivation checks are not all passing"
        )


def _validate_rollback(report: Mapping[str, Any]) -> None:
    required = {
        "rollback_completed": True,
        "baseline_config_restored": True,
        "complete_snapshot_inventory_restored": True,
        "dynamic_security_state_absent": True,
        "anonymous_retained_state_readable": True,
        "current_services_modified": False,
    }
    for field, expected in required.items():
        if report.get(field) is not expected:
            raise BrokerIdentityProductionActivationOrchestratorError(f"production rollback failed: {field}")


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
    _atomic_private_write(path, document)


def execute_production_activation(
    authorization_file: str | Path,
    activation_readiness_bundle_file: str | Path,
    transaction_plan_file: str | Path,
    adapter_contract_file: str | Path,
    executor_contract_file: str | Path,
    runtime_binding_manifest_file: str | Path,
    handoff_directory: str | Path,
    transaction_directory: str | Path,
    *,
    expected_retained_topic: str,
    execution_confirmation: str,
    execution_enabled: bool = False,
    runner: Runner | None = None,
    now: datetime | None = None,
    token_factory: TokenFactory | None = None,
    authorization_verifier: AuthorizationVerifier = (verify_activation_readiness_authorization),
    bundle_verifier: DocumentVerifier = verify_activation_readiness_bundle,
    plan_verifier: DocumentVerifier = verify_activation_readiness_transaction_plan,
    adapter_contract_verifier: DocumentVerifier = (verify_production_transaction_adapter_contract),
    executor_verifier: DocumentVerifier = verify_production_executor_contract,
    manifest_verifier: ManifestVerifier = verify_runtime_binding_manifest,
    driver_factory: DriverFactory = LiveProductionBrokerDriver,
    adapters_factory: AdaptersFactory = ProductionTransactionAdapters,
) -> dict[str, object]:
    if not execution_enabled:
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production activation execution is disabled"
        )
    if not expected_retained_topic.startswith("gh/"):
        raise ValueError("expected retained topic must be in the gh namespace")

    request = build_production_activation_execution_request(
        authorization_file,
        activation_readiness_bundle_file,
        transaction_plan_file,
        adapter_contract_file,
        executor_contract_file,
        runtime_binding_manifest_file,
        now=now,
        authorization_verifier=authorization_verifier,
        bundle_verifier=bundle_verifier,
        plan_verifier=plan_verifier,
        adapter_contract_verifier=adapter_contract_verifier,
        executor_verifier=executor_verifier,
        manifest_verifier=manifest_verifier,
    )
    required_confirmation = request.get("required_confirmation")
    if not isinstance(required_confirmation, str) or not hmac.compare_digest(
        execution_confirmation, required_confirmation
    ):
        raise BrokerIdentityProductionActivationOrchestratorError(
            "explicit production execution confirmation is missing or does not match"
        )

    authorization_path = Path(authorization_file).expanduser().resolve()
    bundle_path = Path(activation_readiness_bundle_file).expanduser().resolve()
    plan_path = Path(transaction_plan_file).expanduser().resolve()
    adapter_path = Path(adapter_contract_file).expanduser().resolve()
    executor_path = Path(executor_contract_file).expanduser().resolve()
    manifest_path = Path(runtime_binding_manifest_file).expanduser().resolve()
    handoff = Path(handoff_directory).expanduser().resolve()
    transaction_root = _private_transaction_directory(Path(transaction_directory).expanduser())

    transaction_id = token_factory() if token_factory else secrets.token_urlsafe(24)
    if not isinstance(transaction_id, str) or _TOKEN.fullmatch(transaction_id) is None:
        raise BrokerIdentityProductionActivationOrchestratorError("production transaction ID is invalid")
    workspace = transaction_root / f"transaction-{transaction_id}"
    workspace.mkdir(mode=0o700)
    if workspace.stat().st_mode & 0o077:
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production transaction workspace must be private"
        )
    journal_path = workspace / "journal.json"
    journal: dict[str, Any] = {
        "schema": JOURNAL_SCHEMA,
        "transaction_id": transaction_id,
        "authorization_id": request["authorization_id"],
        "bundle_sha256": request["bundle_sha256"],
        "adapter_contract_sha256": request["adapter_contract_sha256"],
        "created_at": _timestamp(now),
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
    _journal(journal_path, journal, phase="preparing_snapshot", now=now)

    command_runner = runner or SubprocessRunner()
    driver = driver_factory(manifest_path, runner=command_runner)
    adapters = adapters_factory(
        adapter_path,
        plan_path,
        executor_path,
        manifest_path,
        handoff,
        workspace,
        expected_retained_topic=expected_retained_topic,
        driver=driver,
    )
    installation = adapters.prepare()
    if (
        installation.get("production_transaction_adapters_installed") is not True
        or installation.get("execution_entrypoint_installed") is not False
        or installation.get("current_services_modified") is not False
    ):
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production adapter preparation is incomplete"
        )
    _journal(journal_path, journal, phase="snapshot_ready", now=now)

    build_production_activation_execution_request(
        authorization_path,
        bundle_path,
        plan_path,
        adapter_path,
        executor_path,
        manifest_path,
        now=now,
        authorization_verifier=authorization_verifier,
        bundle_verifier=bundle_verifier,
        plan_verifier=plan_verifier,
        adapter_contract_verifier=adapter_contract_verifier,
        executor_verifier=executor_verifier,
        manifest_verifier=manifest_verifier,
    )

    claim, authorization_document = _claim_authorization(authorization_path)
    consumed_at = _timestamp(now)
    _mark_consumed(
        claim,
        authorization_document,
        transaction_id=transaction_id,
        consumed_at=consumed_at,
    )
    _journal(journal_path, journal, phase="authorization_claimed", now=now)

    mutation: dict[str, object] | None = None
    postactivation: dict[str, object] | None = None
    rollback: dict[str, object] | None = None
    failure: Exception | None = None
    rollback_failure: Exception | None = None
    try:
        _journal(journal_path, journal, phase="mutation_started", now=now)
        mutation = adapters.mutation_executor()
        _validate_mutation(mutation)
        _journal(journal_path, journal, phase="mutation_completed", now=now)
        postactivation = adapters.postactivation_auditor()
        _validate_postactivation(postactivation)
        _journal(journal_path, journal, phase="postactivation_verified", now=now)
    except Exception as error:
        failure = error
        if adapters.mutation_started:
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
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production activation failed and rollback failed"
        ) from rollback_failure
    if failure is not None:
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production activation failed and verified rollback completed"
        ) from failure
    if mutation is None or postactivation is None:
        raise BrokerIdentityProductionActivationOrchestratorError(
            "production activation ended without complete reports"
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
        "broker_identity_activated": True,
        "ready_for_homeassistant_reconfigure_handoff": True,
        "homeassistant_reconfigured": False,
        "node_credentials_delivered": False,
        "production_executor_available": True,
        "execution_enabled": True,
        "apply_enabled": True,
        "current_services_modified": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "path_values_redacted": True,
    }
