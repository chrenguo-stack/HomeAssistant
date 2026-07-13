from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from manager_execution_preparation_fixtures import build_preparation, preclaim_report

import greenhouse_manager.t1_manager_identity_migration_execution_transaction_gate as gate_module
from greenhouse_manager.t1_manager_identity_migration_execution_authorization import (
    build_manager_identity_execution_authorization_request,
    create_manager_identity_execution_authorization,
)
from greenhouse_manager.t1_manager_identity_migration_execution_preparation import (
    prepare_manager_identity_execution,
)

NOW = datetime(2026, 7, 13, 5, 30, tzinfo=UTC)
DRIVER_SHA = "1" * 64


class FakeRunner:
    pass


def _gate_builder(gate: dict[str, object]):
    def build(*_args, **_kwargs) -> dict[str, object]:
        return copy.deepcopy(gate)

    return build


def _stub_driver_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    def verify(contract: dict[str, object]) -> dict[str, object]:
        return {
            "verified": True,
            "driver_contract_sha256": contract.get("driver_contract_sha256"),
        }

    monkeypatch.setattr(
        gate_module,
        "verify_manager_production_driver_contract",
        verify,
    )


def _package(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, dict[str, object]]:
    preparation, driver, output, gate = build_preparation(
        tmp_path,
        include_environment=True,
    )
    driver.write_text(
        json.dumps({"driver_contract_sha256": DRIVER_SHA}),
        encoding="utf-8",
    )
    driver.chmod(0o600)

    report = prepare_manager_identity_execution(
        driver,
        preparation,
        output,
        freshness_seconds=900,
        runner=FakeRunner(),
        now=NOW,
        token_factory=lambda: "execution1",
        live_gate_builder=_gate_builder(gate),
        preclaim_probe=preclaim_report,
    )
    execution = output / str(report["execution_preparation_name"])

    observed = NOW + timedelta(seconds=30)
    request = build_manager_identity_execution_authorization_request(
        execution,
        driver,
        preparation,
        runner=FakeRunner(),
        live_gate_builder=_gate_builder(gate),
        now=observed,
    )
    auth_root = tmp_path / "greenhouse-m2-manager-execution-authorizations.test"
    created = create_manager_identity_execution_authorization(
        execution,
        driver,
        preparation,
        auth_root,
        confirmation=str(request["required_confirmation"]),
        ttl_seconds=600,
        runner=FakeRunner(),
        live_gate_builder=_gate_builder(gate),
        now=observed,
        token_factory=lambda: "authorization_token_123456",
    )
    authorization = auth_root / str(created["authorization_file"])
    return authorization, execution, driver, preparation, gate


def test_gate_binds_authorization_rollback_and_second_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_driver_verifier(monkeypatch)
    authorization, execution, driver, preparation, gate = _package(tmp_path)

    report = gate_module.build_manager_identity_execution_transaction_gate(
        authorization,
        execution,
        driver,
        preparation,
        runner=FakeRunner(),
        live_gate_builder=_gate_builder(gate),
        now=NOW + timedelta(seconds=60),
    )

    assert report["transaction_gate_ready"] is True
    assert report["authorization_valid"] is True
    assert report["authorization_single_use"] is True
    assert str(report["required_confirmation"]).startswith(
        "EXECUTE-M2-MANAGER-MIGRATION:"
    )
    assert report["operator_decision_required"] is True
    assert report["second_operator_confirmation_present"] is False
    assert report["authorization_claim_required"] is True
    assert report["authorization_claimed"] is False
    assert report["claim_enabled"] is False
    assert report["production_manager_driver_installed"] is False
    assert report["production_executor_available"] is False
    assert report["execution_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["ready_for_manager_migration_apply"] is False
    assert report["manager_identity_migrated"] is False
    assert report["node_credentials_delivered"] is False
    assert report["current_services_modified"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    serialized = json.dumps(report)
    assert str(authorization) not in serialized
    assert str(execution) not in serialized
    assert str(driver) not in serialized
    assert str(preparation) not in serialized
    assert "authorization_token_123456" not in serialized


def test_gate_rejects_expired_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_driver_verifier(monkeypatch)
    authorization, execution, driver, preparation, gate = _package(tmp_path)

    with pytest.raises(Exception, match="not currently valid"):
        gate_module.build_manager_identity_execution_transaction_gate(
            authorization,
            execution,
            driver,
            preparation,
            runner=FakeRunner(),
            live_gate_builder=_gate_builder(gate),
            now=NOW + timedelta(seconds=700),
        )


def test_gate_rejects_live_runtime_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_driver_verifier(monkeypatch)
    authorization, execution, driver, preparation, gate = _package(tmp_path)
    drifted = copy.deepcopy(gate)
    drifted["live_binding_sha256"] = "9" * 64

    with pytest.raises(Exception, match="drifted"):
        gate_module.build_manager_identity_execution_transaction_gate(
            authorization,
            execution,
            driver,
            preparation,
            runner=FakeRunner(),
            live_gate_builder=_gate_builder(drifted),
            now=NOW + timedelta(seconds=60),
        )


def test_gate_rejects_driver_binding_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_driver_verifier(monkeypatch)
    authorization, execution, driver, preparation, gate = _package(tmp_path)
    driver.write_text(
        json.dumps({"driver_contract_sha256": "8" * 64}),
        encoding="utf-8",
    )
    driver.chmod(0o600)

    with pytest.raises(
        gate_module.ManagerIdentityExecutionTransactionGateError,
        match="does not match execution preparation",
    ):
        gate_module.build_manager_identity_execution_transaction_gate(
            authorization,
            execution,
            driver,
            preparation,
            runner=FakeRunner(),
            live_gate_builder=_gate_builder(gate),
            now=NOW + timedelta(seconds=60),
        )
