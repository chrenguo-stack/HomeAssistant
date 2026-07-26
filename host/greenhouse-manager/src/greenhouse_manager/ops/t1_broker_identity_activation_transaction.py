from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .t1_broker_identity_activation_authorization import (
    BrokerIdentityActivationAuthorizationError,
    verify_activation_authorization,
)
from .t1_broker_identity_activation_checks import (
    BrokerIdentityActivationCheckError,
    BrokerIdentityActivationHandoffError,
    Runner,
    Verifier,
    read_json,
)
from .t1_broker_identity_activation_handoff import (
    verify_broker_identity_activation_handoff,
)
from .t1_broker_identity_preactivation_gate import (
    build_broker_identity_preactivation_gate,
)
from .t1_shadow import SubprocessRunner

PLAN_SCHEMA = "gh.m2.t1-broker-identity-activation-transaction-plan/1"
TRANSACTION_SCHEMA = "gh.m2.t1-broker-identity-activation-transaction/1"
JOURNAL_SCHEMA = "gh.m2.t1-broker-identity-activation-transaction-journal/1"
_TRANSACTION_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

AuthorizationVerifier = Callable[..., dict[str, object]]
PreactivationBuilder = Callable[..., dict[str, object]]
MutationExecutor = Callable[[Path, Runner], dict[str, object]]
PostactivationAuditor = Callable[[Path, Runner], dict[str, object]]
RollbackExecutor = Callable[[Path, Runner], dict[str, object]]
TokenFactory = Callable[[], str]


class BrokerIdentityActivationTransactionError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _timestamp(value: datetime | None = None) -> str:
    observed = (value or datetime.now(UTC)).astimezone(UTC)
    return observed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_private_write(path: Path, value: str) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _validate_preactivation(report: dict[str, object]) -> None:
    required = {
        "schema": "gh.m2.t1-broker-identity-preactivation-gate/1",
        "read_only": True,
        "preconditions_ready": True,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if report.get(field) != expected:
            raise BrokerIdentityActivationTransactionError(
                f"preactivation gate is unsafe or incomplete: {field}"
            )
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise BrokerIdentityActivationTransactionError(
            "preactivation checks are not all passing"
        )


def _validate_postactivation(report: dict[str, object]) -> None:
    required = {
        "activation_verified": True,
        "rollback_required": False,
        "broker_identity_activated": True,
        "ready_for_homeassistant_reconfigure_handoff": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if report.get(field) != expected:
            raise BrokerIdentityActivationTransactionError(
                f"postactivation audit failed: {field}"
            )
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise BrokerIdentityActivationTransactionError(
            "postactivation checks are not all passing"
        )


def _validate_mutation(report: dict[str, object]) -> None:
    required = {
        "mutation_started": True,
        "mosquitto_restarted": True,
        "bootstrap_admin_removed": True,
        "provisioning_identity_verified": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    for field, expected in required.items():
        if report.get(field) != expected:
            raise BrokerIdentityActivationTransactionError(
                f"mutation executor contract failed: {field}"
            )


def _validate_rollback(report: dict[str, object]) -> None:
    required = {
        "rollback_completed": True,
        "baseline_config_restored": True,
        "dynamic_security_state_absent": True,
        "anonymous_retained_state_readable": True,
    }
    for field, expected in required.items():
        if report.get(field) != expected:
            raise BrokerIdentityActivationTransactionError(
                f"rollback executor contract failed: {field}"
            )


def _authorization_document(path: Path) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise BrokerIdentityActivationTransactionError(
            "authorization file is missing or unsafe"
        )
    return read_json(path, "activation authorization")


def _claim_authorization(
    authorization_file: Path,
) -> tuple[Path, dict[str, Any]]:
    document = _authorization_document(authorization_file)
    authorization_id = document.get("authorization_id")
    if not isinstance(authorization_id, str) or not authorization_id:
        raise BrokerIdentityActivationTransactionError(
            "authorization ID is missing"
        )
    claim = authorization_file.with_name(
        f"claimed-{authorization_id}.json"
    )
    try:
        os.link(
            authorization_file,
            claim,
            follow_symlinks=False,
        )
    except FileExistsError as error:
        raise BrokerIdentityActivationTransactionError(
            "authorization has already been claimed"
        ) from error
    except OSError as error:
        raise BrokerIdentityActivationTransactionError(
            "authorization could not be atomically claimed"
        ) from error
    try:
        authorization_file.unlink()
    except OSError as error:
        claim.unlink(missing_ok=True)
        raise BrokerIdentityActivationTransactionError(
            "authorization claim could not remove the unclaimed name"
        ) from error

    return claim, document


def _mark_authorization_consumed(
    claim: Path,
    document: dict[str, Any],
    *,
    transaction_id: str,
    claimed_at: str,
) -> None:
    document["consumed"] = True
    document["consumed_at"] = claimed_at
    document["transaction_id"] = transaction_id
    _atomic_private_write(claim, _json(document))


def _write_journal(
    path: Path,
    document: dict[str, Any],
    *,
    phase: str,
    now: datetime | None,
    details: dict[str, object] | None = None,
) -> None:
    document["phase"] = phase
    document["updated_at"] = _timestamp(now)
    if details is not None:
        document["details"] = details
    _atomic_private_write(path, _json(document))


def build_activation_transaction_plan(
    authorization_file: str | Path,
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_target_fingerprint: str,
    expected_entry_fingerprint: str,
    expected_storage_sha256: str,
    expected_target_kind: str = "loopback",
    runner: Runner | None = None,
    now: datetime | None = None,
    authorization_verifier: AuthorizationVerifier = (
        verify_activation_authorization
    ),
    handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
    preactivation_builder: PreactivationBuilder = (
        build_broker_identity_preactivation_gate
    ),
) -> dict[str, object]:
    command_runner = runner or SubprocessRunner()
    authorization = Path(authorization_file).expanduser().resolve()
    root = Path(handoff_directory).expanduser().resolve()
    stage = Path(stage_directory).expanduser().resolve()
    validated = authorization_verifier(
        authorization,
        root,
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_entry_fingerprint=expected_entry_fingerprint,
        expected_storage_sha256=expected_storage_sha256,
        expected_target_kind=expected_target_kind,
        now=now,
    )
    if (
        validated.get("valid_now") is not True
        or validated.get("single_use") is not True
        or validated.get("consumed") is not False
        or validated.get("operator_action_authorized") is not True
        or validated.get("apply_enabled") is not False
        or validated.get("ready_for_live_activation") is not False
        or validated.get("current_services_modified") is not False
        or validated.get("preserve_anonymous") is not True
        or validated.get("anonymous_closure_enabled") is not False
    ):
        raise BrokerIdentityActivationTransactionError(
            "authorization verification is incomplete"
        )
    gate = preactivation_builder(
        root,
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_entry_fingerprint=expected_entry_fingerprint,
        expected_storage_sha256=expected_storage_sha256,
        expected_target_kind=expected_target_kind,
        runner=command_runner,
        handoff_verifier=handoff_verifier,
    )
    _validate_preactivation(gate)
    return {
        "schema": PLAN_SCHEMA,
        "authorization_id": validated.get("authorization_id"),
        "handoff": root.name,
        "preconditions_ready": True,
        "authorization_valid": True,
        "single_use": True,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "rollback_mandatory_on_failure": True,
        "postactivation_audit_mandatory": True,
    }


def execute_activation_transaction(
    authorization_file: str | Path,
    handoff_directory: str | Path,
    stage_directory: str | Path,
    *,
    expected_retained_topic: str,
    expected_target_fingerprint: str,
    expected_entry_fingerprint: str,
    expected_storage_sha256: str,
    expected_target_kind: str = "loopback",
    execution_enabled: bool = False,
    runner: Runner | None = None,
    now: datetime | None = None,
    token_factory: TokenFactory | None = None,
    authorization_verifier: AuthorizationVerifier = (
        verify_activation_authorization
    ),
    handoff_verifier: Verifier = verify_broker_identity_activation_handoff,
    preactivation_builder: PreactivationBuilder = (
        build_broker_identity_preactivation_gate
    ),
    mutation_executor: MutationExecutor | None = None,
    postactivation_auditor: PostactivationAuditor | None = None,
    rollback_executor: RollbackExecutor | None = None,
) -> dict[str, object]:
    if not execution_enabled:
        raise BrokerIdentityActivationTransactionError(
            "live activation execution is disabled"
        )
    if (
        mutation_executor is None
        or postactivation_auditor is None
        or rollback_executor is None
    ):
        raise BrokerIdentityActivationTransactionError(
            "production transaction executors are not installed"
        )
    command_runner = runner or SubprocessRunner()
    authorization = Path(authorization_file).expanduser().resolve()
    root = Path(handoff_directory).expanduser().resolve()
    stage = Path(stage_directory).expanduser().resolve()

    plan = build_activation_transaction_plan(
        authorization,
        root,
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_entry_fingerprint=expected_entry_fingerprint,
        expected_storage_sha256=expected_storage_sha256,
        expected_target_kind=expected_target_kind,
        runner=command_runner,
        now=now,
        authorization_verifier=authorization_verifier,
        handoff_verifier=handoff_verifier,
        preactivation_builder=preactivation_builder,
    )
    token = token_factory() if token_factory else secrets.token_hex(12)
    if (
        not isinstance(token, str)
        or _TRANSACTION_ID.fullmatch(token) is None
    ):
        raise BrokerIdentityActivationTransactionError(
            "transaction ID generator returned an invalid value"
        )
    transaction_id = token
    observed_at = _timestamp(now)
    claimed, authorization_document = _claim_authorization(
        authorization,
    )
    authorization_verifier(
        claimed,
        root,
        stage,
        expected_retained_topic=expected_retained_topic,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_entry_fingerprint=expected_entry_fingerprint,
        expected_storage_sha256=expected_storage_sha256,
        expected_target_kind=expected_target_kind,
        now=now,
    )
    _mark_authorization_consumed(
        claimed,
        authorization_document,
        transaction_id=transaction_id,
        claimed_at=observed_at,
    )
    journal_path = claimed.with_name(f"transaction-{transaction_id}.json")
    journal: dict[str, Any] = {
        "schema": JOURNAL_SCHEMA,
        "transaction_id": transaction_id,
        "authorization_id": plan.get("authorization_id"),
        "authorization_file": claimed.name,
        "handoff": root.name,
        "created_at": observed_at,
        "updated_at": observed_at,
        "phase": "authorization_claimed",
        "mutation_started": False,
        "rollback_attempted": False,
        "rollback_completed": False,
        "postactivation_verified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    _atomic_private_write(journal_path, _json(journal))

    mutation_started = False
    mutation: dict[str, object] | None = None
    postactivation: dict[str, object] | None = None
    try:
        _write_journal(
            journal_path,
            journal,
            phase="mutation_requested",
            now=now,
        )
        mutation_started = True
        journal["mutation_started"] = True
        mutation = mutation_executor(root, command_runner)
        _validate_mutation(mutation)
        _write_journal(
            journal_path,
            journal,
            phase="mutation_completed",
            now=now,
            details={"mutation_report_present": bool(mutation)},
        )
        postactivation = postactivation_auditor(root, command_runner)
        _validate_postactivation(postactivation)
        journal["postactivation_verified"] = True
        _write_journal(
            journal_path,
            journal,
            phase="completed",
            now=now,
        )
    except Exception as error:
        if mutation_started:
            journal["rollback_attempted"] = True
            _write_journal(
                journal_path,
                journal,
                phase="rollback_requested",
                now=now,
            )
            try:
                rollback = rollback_executor(root, command_runner)
                _validate_rollback(rollback)
            except Exception as rollback_error:
                _write_journal(
                    journal_path,
                    journal,
                    phase="rollback_failed",
                    now=now,
                    details={"rollback_error": type(rollback_error).__name__},
                )
                raise BrokerIdentityActivationTransactionError(
                    "activation transaction failed and rollback failed"
                ) from rollback_error
            journal["rollback_completed"] = True
            _write_journal(
                journal_path,
                journal,
                phase="rolled_back",
                now=now,
                details={"rollback_report_present": bool(rollback)},
            )
            raise BrokerIdentityActivationTransactionError(
                "activation transaction failed; rollback completed"
            ) from error
        _write_journal(
            journal_path,
            journal,
            phase="failed_before_mutation",
            now=now,
            details={"error": type(error).__name__},
        )
        raise BrokerIdentityActivationTransactionError(
            "activation transaction failed before mutation"
        ) from error

    return {
        "schema": TRANSACTION_SCHEMA,
        "transaction_id": transaction_id,
        "authorization_id": plan.get("authorization_id"),
        "authorization_consumed": True,
        "activation_executed": True,
        "activation_verified": True,
        "rollback_required": False,
        "rollback_executed": False,
        "broker_identity_activated": True,
        "ready_for_homeassistant_reconfigure_handoff": True,
        "operator_action_authorized": True,
        "apply_enabled": True,
        "current_services_modified": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "journal_file": str(journal_path),
        "mutation_report_present": bool(mutation),
        "postactivation_checks": (
            postactivation.get("checks")
            if isinstance(postactivation, dict)
            else None
        ),
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Runner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a Broker activation transaction plan. "
            "Production execution is intentionally unavailable."
        )
    )
    parser.add_argument("authorization_file")
    parser.add_argument("handoff_directory")
    parser.add_argument("stage_directory")
    parser.add_argument("--expected-retained-topic", required=True)
    parser.add_argument("--expected-target-fingerprint", required=True)
    parser.add_argument("--expected-entry-fingerprint", required=True)
    parser.add_argument("--expected-storage-sha256", required=True)
    parser.add_argument("--expected-target-kind", default="loopback")
    args = parser.parse_args(argv)
    try:
        result = build_activation_transaction_plan(
            args.authorization_file,
            args.handoff_directory,
            args.stage_directory,
            expected_retained_topic=args.expected_retained_topic,
            expected_target_fingerprint=args.expected_target_fingerprint,
            expected_entry_fingerprint=args.expected_entry_fingerprint,
            expected_storage_sha256=args.expected_storage_sha256,
            expected_target_kind=args.expected_target_kind,
            runner=runner,
        )
    except (
        BrokerIdentityActivationAuthorizationError,
        BrokerIdentityActivationCheckError,
        BrokerIdentityActivationHandoffError,
        BrokerIdentityActivationTransactionError,
        OSError,
        ValueError,
    ) as error:
        print(
            f"T1 Broker activation transaction plan failed: {error}",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
