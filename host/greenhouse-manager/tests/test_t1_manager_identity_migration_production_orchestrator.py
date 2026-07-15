from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager.t1_manager_identity_migration_production_orchestrator import (
    ManagerIdentityProductionOrchestratorError,
    build_manager_identity_production_execution_request,
    execute_manager_identity_production_migration,
)

AUTHORIZATION_ID = "0123456789abcdef01234567"
EXECUTION_SHA = "a" * 64
ROLLBACK_SHA = "b" * 64
DRIVER_SHA = "c" * 64
ADAPTER_SHA = "d" * 64
RUNTIME_SHA = "e" * 64
LIVE_SHA = "f" * 64
CREATED = datetime(2026, 7, 13, 7, 0, tzinfo=UTC)
CONFIRMATION = (
    f"EXECUTE-M2-MANAGER-MIGRATION:{AUTHORIZATION_ID}:"
    f"{EXECUTION_SHA[:16]}:{ROLLBACK_SHA[:16]}:{LIVE_SHA[:16]}"
)


def _canonical(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_private(path: Path, value: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(_canonical(value) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def _gate() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-manager-identity-execution-transaction-gate/1",
        "transaction_gate_ready": True,
        "authorization_id": AUTHORIZATION_ID,
        "authorization_valid": True,
        "authorization_single_use": True,
        "authorization_expires_at": "2026-07-13T07:15:00Z",
        "execution_preparation_name": (
            "greenhouse-manager-execution-preparation-20260713T070000Z-test"
        ),
        "execution_preparation_expires_at": "2026-07-13T07:15:00Z",
        "execution_preparation_manifest_sha256": EXECUTION_SHA,
        "fresh_rollback_archive_sha256": ROLLBACK_SHA,
        "driver_contract_sha256": DRIVER_SHA,
        "adapter_contract_sha256": ADAPTER_SHA,
        "runtime_binding_sha256": RUNTIME_SHA,
        "live_binding_sha256": LIVE_SHA,
        "required_confirmation": CONFIRMATION,
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
    }


def _gate_builder(*_args: object, **_kwargs: object) -> dict[str, object]:
    return _gate()


def _fixture(tmp_path: Path) -> dict[str, Path]:
    authorization = {
        "schema": "gh.m2.t1-manager-identity-execution-authorization/1",
        "authorization_id": AUTHORIZATION_ID,
        "authorization_token": "private_authorization_token_never_returned",
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "authorization_claimed": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    inputs = tmp_path / "inputs"
    execution = inputs / "greenhouse-manager-execution-preparation-test"
    preparation = inputs / "greenhouse-manager-migration-preparation-test"
    execution.mkdir(parents=True)
    preparation.mkdir()
    driver = _write_private(inputs / "driver.json", {"driver": "contract"})
    return {
        "authorization": _write_private(inputs / "authorization.json", authorization),
        "execution": execution,
        "driver": driver,
        "preparation": preparation,
        "transaction_root": tmp_path
        / "greenhouse-m2-manager-production-transactions-test",
    }


class FakeAdapters:
    def __init__(self, *, failure: str | None = None) -> None:
        self.failure = failure
        self.mutation_started = False
        self.calls: list[str] = []

    def prepare(self) -> dict[str, object]:
        self.calls.append("prepare")
        if self.failure == "prepare":
            raise RuntimeError("injected prepare failure")
        return {
            "production_transaction_adapters_installed": True,
            "production_manager_driver_installed": True,
            "execution_entrypoint_installed": False,
            "greenhouse_manager_only": True,
            "mosquitto_target_allowed": False,
            "homeassistant_target_allowed": False,
            "node_target_allowed": False,
            "current_services_modified": False,
        }

    def mutation_executor(self) -> dict[str, object]:
        self.calls.append("mutation")
        self.mutation_started = True
        if self.failure == "mutation":
            raise RuntimeError("injected mutation failure")
        return {
            "mutation_started": True,
            "manager_material_installed": True,
            "greenhouse_manager_recreated": True,
            "manager_restart_count_zero": True,
            "mosquitto_modified": False,
            "homeassistant_modified": False,
            "nodes_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }

    def postactivation_auditor(self) -> dict[str, object]:
        self.calls.append("audit")
        if self.failure == "audit":
            raise RuntimeError("injected audit failure")
        return {
            "checks": {"all": True},
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
        }

    def rollback_executor(self) -> dict[str, object]:
        self.calls.append("rollback")
        if self.failure == "rollback":
            raise RuntimeError("injected rollback failure")
        return {
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
        }


def _request(fixture: dict[str, Path]) -> dict[str, object]:
    return build_manager_identity_production_execution_request(
        fixture["authorization"],
        fixture["execution"],
        fixture["driver"],
        fixture["preparation"],
        now=CREATED,
        transaction_gate_builder=_gate_builder,
    )


def _execute(
    fixture: dict[str, Path],
    adapters: FakeAdapters,
    *,
    confirmation: str = CONFIRMATION,
    enabled: bool = True,
) -> dict[str, object]:
    return execute_manager_identity_production_migration(
        fixture["authorization"],
        fixture["execution"],
        fixture["driver"],
        fixture["preparation"],
        fixture["transaction_root"],
        execution_confirmation=confirmation,
        execution_enabled=enabled,
        now=CREATED,
        token_factory=lambda: "manager_transaction_token_123456",
        transaction_gate_builder=_gate_builder,
        adapters_factory=lambda *_args, **_kwargs: adapters,
    )


def test_builds_secret_free_execution_request(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    report = _request(fixture)

    assert report["execution_request_ready"] is True
    assert report["authorization_valid"] is True
    assert report["authorization_claimed"] is False
    assert report["execution_enabled"] is False
    assert report["required_confirmation"] == CONFIRMATION
    assert "private_authorization_token" not in json.dumps(report)


def test_execution_is_disabled_by_default(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    with pytest.raises(
        ManagerIdentityProductionOrchestratorError,
        match="execution is disabled",
    ):
        _execute(fixture, FakeAdapters(), enabled=False)

    assert fixture["authorization"].exists()


def test_rejects_wrong_second_confirmation_before_claim(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    with pytest.raises(
        ManagerIdentityProductionOrchestratorError,
        match="confirmation is missing or does not match",
    ):
        _execute(fixture, FakeAdapters(), confirmation="wrong-confirmation")

    assert fixture["authorization"].exists()


def test_prepare_failure_leaves_authorization_unclaimed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    with pytest.raises(RuntimeError, match="injected prepare failure"):
        _execute(fixture, FakeAdapters(failure="prepare"))

    assert fixture["authorization"].exists()


def test_success_claims_authorization_and_commits(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    adapters = FakeAdapters()

    report = _execute(fixture, adapters)

    assert report["manager_identity_migrated"] is True
    assert report["authorization_claimed"] is True
    assert report["authorization_consumed"] is True
    assert report["postactivation_verified"] is True
    assert report["rollback_completed"] is False
    assert report["mosquitto_modified"] is False
    assert report["homeassistant_modified"] is False
    assert report["nodes_modified"] is False
    assert not fixture["authorization"].exists()
    claim = fixture["authorization"].with_name(
        f"claimed-manager-execution-authorization-{AUTHORIZATION_ID}.json"
    )
    consumed = json.loads(claim.read_text(encoding="utf-8"))
    assert consumed["consumed"] is True
    assert consumed["authorization_claimed"] is True
    assert consumed["transaction_id"] == "manager_transaction_token_123456"
    assert adapters.calls == ["prepare", "mutation", "audit"]
    journal = (
        fixture["transaction_root"]
        / "transaction-manager_transaction_token_123456"
        / "journal.json"
    )
    assert json.loads(journal.read_text(encoding="utf-8"))["phase"] == "committed"
    assert journal.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("failure", ["mutation", "audit"])
def test_post_claim_failure_forces_verified_rollback(
    tmp_path: Path,
    failure: str,
) -> None:
    fixture = _fixture(tmp_path)
    adapters = FakeAdapters(failure=failure)

    with pytest.raises(
        ManagerIdentityProductionOrchestratorError,
        match="verified rollback completed",
    ):
        _execute(fixture, adapters)

    assert not fixture["authorization"].exists()
    assert adapters.calls[-1] == "rollback"
    journal = (
        fixture["transaction_root"]
        / "transaction-manager_transaction_token_123456"
        / "journal.json"
    )
    document = json.loads(journal.read_text(encoding="utf-8"))
    assert document["phase"] == "rollback_completed"
    expected_phase = (
        "mutation_execution"
        if failure == "mutation"
        else "postactivation_execution"
    )
    assert document["details"] == {
        "failed_phase": expected_phase,
        "failure_exception_class": "RuntimeError",
        "rollback_verified": True,
    }
    serialized = json.dumps(document)
    assert "injected mutation failure" not in serialized
    assert "injected audit failure" not in serialized


@pytest.mark.parametrize(
    ("invalid_report", "expected_phase"),
    [
        ("mutation", "mutation_validation"),
        ("postactivation", "postactivation_validation"),
    ],
)
def test_invalid_adapter_report_records_validation_phase(
    tmp_path: Path,
    invalid_report: str,
    expected_phase: str,
) -> None:
    fixture = _fixture(tmp_path)

    class InvalidReportAdapters(FakeAdapters):
        def mutation_executor(self) -> dict[str, object]:
            report = super().mutation_executor()
            if invalid_report == "mutation":
                report["manager_material_installed"] = False
            return report

        def postactivation_auditor(self) -> dict[str, object]:
            report = super().postactivation_auditor()
            if invalid_report == "postactivation":
                report["manager_authenticated"] = False
            return report

    with pytest.raises(
        ManagerIdentityProductionOrchestratorError,
        match="verified rollback completed",
    ):
        _execute(fixture, InvalidReportAdapters())

    journal = (
        fixture["transaction_root"]
        / "transaction-manager_transaction_token_123456"
        / "journal.json"
    )
    document = json.loads(journal.read_text(encoding="utf-8"))
    assert document["phase"] == "rollback_completed"
    assert document["details"] == {
        "failed_phase": expected_phase,
        "failure_exception_class": "ManagerIdentityProductionOrchestratorError",
        "rollback_verified": True,
    }


def test_rollback_failure_is_terminal(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    adapters = FakeAdapters(failure="rollback")

    original_mutation = adapters.mutation_executor

    def failing_mutation() -> dict[str, object]:
        original_mutation()
        raise RuntimeError("injected mutation failure")

    adapters.mutation_executor = failing_mutation  # type: ignore[method-assign]

    with pytest.raises(
        ManagerIdentityProductionOrchestratorError,
        match="migration failed and rollback failed",
    ):
        _execute(fixture, adapters)

    journal = (
        fixture["transaction_root"]
        / "transaction-manager_transaction_token_123456"
        / "journal.json"
    )
    document = json.loads(journal.read_text(encoding="utf-8"))
    assert document["phase"] == "rollback_failed"
    assert document["details"] == {
        "failed_phase": "mutation_execution",
        "failure_exception_class": "RuntimeError",
        "rollback_exception_class": "RuntimeError",
        "terminal": True,
    }


def test_claimed_authorization_cannot_be_replayed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    _execute(fixture, FakeAdapters())

    with pytest.raises(
        ManagerIdentityProductionOrchestratorError,
        match="authorization is missing",
    ):
        _execute(fixture, FakeAdapters())
