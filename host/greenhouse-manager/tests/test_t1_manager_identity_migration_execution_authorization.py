from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from manager_execution_preparation_fixtures import build_preparation, preclaim_report

from greenhouse_manager.t1_manager_identity_migration_execution_authorization import (
    ManagerIdentityExecutionAuthorizationError,
    build_manager_identity_execution_authorization_request,
    create_manager_identity_execution_authorization,
    verify_manager_identity_execution_authorization,
)
from greenhouse_manager.t1_manager_identity_migration_execution_preparation import (
    prepare_manager_identity_execution,
)
from greenhouse_manager.t1_manager_identity_migration_execution_preparation_common import (
    ManagerIdentityExecutionPreparationError,
)

NOW = datetime(2026, 7, 13, 5, 30, tzinfo=UTC)


class FakeRunner:
    pass


def _gate_builder(gate: dict[str, object]):
    def build(*_args, **_kwargs) -> dict[str, object]:
        return copy.deepcopy(gate)

    return build


def _execution_package(
    tmp_path: Path,
    *,
    include_environment: bool = True,
) -> tuple[Path, Path, Path, dict[str, object]]:
    preparation, driver, output, gate = build_preparation(
        tmp_path,
        include_environment=include_environment,
    )
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
    return execution, driver, preparation, gate


def _request(
    execution: Path,
    driver: Path,
    preparation: Path,
    gate: dict[str, object],
    *,
    now: datetime = NOW + timedelta(seconds=30),
) -> dict[str, object]:
    return build_manager_identity_execution_authorization_request(
        execution,
        driver,
        preparation,
        runner=FakeRunner(),
        live_gate_builder=_gate_builder(gate),
        now=now,
    )


def test_request_binds_fresh_rollback_and_live_gate(tmp_path: Path) -> None:
    execution, driver, preparation, gate = _execution_package(tmp_path)

    request = _request(execution, driver, preparation, gate)

    assert request["schema"] == (
        "gh.m2.t1-manager-identity-execution-authorization-request/1"
    )
    assert request["execution_preparation_fresh"] is True
    assert request["fresh_runtime_gate_passed"] is True
    assert request["fresh_rollback_verified"] is True
    assert request["max_authorization_ttl_seconds"] == 870
    assert str(request["required_confirmation"]).startswith(
        "AUTHORIZE-M2-MANAGER-EXECUTION:"
    )
    assert request["authorization_created"] is False
    assert request["operator_decision_required"] is True
    assert request["operator_action_authorized"] is False
    assert request["execution_enabled"] is False
    assert request["apply_enabled"] is False
    assert request["current_services_modified"] is False
    assert request["preserve_anonymous"] is True
    assert request["anonymous_closure_enabled"] is False
    serialized = json.dumps(request)
    assert str(execution) not in serialized
    assert str(driver) not in serialized
    assert str(preparation) not in serialized


def test_create_and_verify_authorization_without_claim_or_apply(tmp_path: Path) -> None:
    execution, driver, preparation, gate = _execution_package(tmp_path)
    observed = NOW + timedelta(seconds=30)
    request = _request(
        execution,
        driver,
        preparation,
        gate,
        now=observed,
    )
    output = tmp_path / "greenhouse-m2-manager-execution-authorizations.test"

    created = create_manager_identity_execution_authorization(
        execution,
        driver,
        preparation,
        output,
        confirmation=str(request["required_confirmation"]),
        ttl_seconds=600,
        runner=FakeRunner(),
        live_gate_builder=_gate_builder(gate),
        now=observed,
        token_factory=lambda: "authorization_token_123456",
    )

    authorization = output / str(created["authorization_file"])
    assert authorization.stat().st_mode & 0o777 == 0o600
    assert output.stat().st_mode & 0o777 == 0o700
    assert created["operator_action_authorized"] is True
    assert created["authorization_claimed"] is False
    assert created["production_manager_driver_installed"] is False
    assert created["production_executor_available"] is False
    assert created["execution_enabled"] is False
    assert created["apply_enabled"] is False
    assert created["manager_identity_migrated"] is False
    assert created["node_credentials_delivered"] is False

    verified = verify_manager_identity_execution_authorization(
        authorization,
        execution,
        driver,
        preparation,
        runner=FakeRunner(),
        live_gate_builder=_gate_builder(gate),
        now=observed + timedelta(seconds=60),
    )

    assert verified["valid_now"] is True
    assert verified["execution_preparation_fresh"] is True
    assert verified["fresh_runtime_gate_passed"] is True
    assert verified["single_use"] is True
    assert verified["consumed"] is False
    assert verified["operator_action_authorized"] is True
    assert verified["authorization_claimed"] is False
    assert verified["execution_enabled"] is False
    assert verified["apply_enabled"] is False
    assert verified["current_services_modified"] is False
    assert "authorization_token" not in json.dumps(created)
    assert str(output) not in json.dumps(created)


def test_wrong_confirmation_is_rejected(tmp_path: Path) -> None:
    execution, driver, preparation, gate = _execution_package(tmp_path)
    output = tmp_path / "greenhouse-m2-manager-execution-authorizations.test"

    with pytest.raises(
        ManagerIdentityExecutionAuthorizationError,
        match="confirmation",
    ):
        create_manager_identity_execution_authorization(
            execution,
            driver,
            preparation,
            output,
            confirmation="AUTHORIZE-M2-MANAGER-EXECUTION:wrong",
            ttl_seconds=300,
            runner=FakeRunner(),
            live_gate_builder=_gate_builder(gate),
            now=NOW + timedelta(seconds=30),
        )

    assert not output.exists()


def test_authorization_cannot_outlive_execution_preparation(tmp_path: Path) -> None:
    execution, driver, preparation, gate = _execution_package(tmp_path)
    observed = NOW + timedelta(seconds=800)
    request = _request(
        execution,
        driver,
        preparation,
        gate,
        now=observed,
    )
    assert request["max_authorization_ttl_seconds"] == 100
    output = tmp_path / "greenhouse-m2-manager-execution-authorizations.test"

    with pytest.raises(
        ManagerIdentityExecutionAuthorizationError,
        match="outlive",
    ):
        create_manager_identity_execution_authorization(
            execution,
            driver,
            preparation,
            output,
            confirmation=str(request["required_confirmation"]),
            ttl_seconds=120,
            runner=FakeRunner(),
            live_gate_builder=_gate_builder(gate),
            now=observed,
            token_factory=lambda: "authorization_token_123456",
        )


def test_request_rejects_insufficient_freshness(tmp_path: Path) -> None:
    execution, driver, preparation, gate = _execution_package(tmp_path)

    with pytest.raises(
        ManagerIdentityExecutionAuthorizationError,
        match="insufficient freshness",
    ):
        _request(
            execution,
            driver,
            preparation,
            gate,
            now=NOW + timedelta(seconds=850),
        )


def test_request_rejects_expired_execution_preparation(tmp_path: Path) -> None:
    execution, driver, preparation, gate = _execution_package(tmp_path)

    with pytest.raises(
        ManagerIdentityExecutionPreparationError,
        match="expired",
    ):
        _request(
            execution,
            driver,
            preparation,
            gate,
            now=NOW + timedelta(seconds=901),
        )


def test_request_rejects_live_gate_drift(tmp_path: Path) -> None:
    execution, driver, preparation, gate = _execution_package(tmp_path)
    drifted = copy.deepcopy(gate)
    drifted["live_binding_sha256"] = "9" * 64

    with pytest.raises(
        ManagerIdentityExecutionAuthorizationError,
        match="drifted",
    ):
        _request(execution, driver, preparation, drifted)


def test_consumed_authorization_is_rejected(tmp_path: Path) -> None:
    execution, driver, preparation, gate = _execution_package(tmp_path)
    observed = NOW + timedelta(seconds=30)
    request = _request(
        execution,
        driver,
        preparation,
        gate,
        now=observed,
    )
    output = tmp_path / "greenhouse-m2-manager-execution-authorizations.test"
    created = create_manager_identity_execution_authorization(
        execution,
        driver,
        preparation,
        output,
        confirmation=str(request["required_confirmation"]),
        ttl_seconds=300,
        runner=FakeRunner(),
        live_gate_builder=_gate_builder(gate),
        now=observed,
        token_factory=lambda: "authorization_token_123456",
    )
    authorization = output / str(created["authorization_file"])
    document = json.loads(authorization.read_text(encoding="utf-8"))
    document["consumed"] = True
    authorization.write_text(json.dumps(document), encoding="utf-8")
    authorization.chmod(0o600)

    with pytest.raises(
        ManagerIdentityExecutionAuthorizationError,
        match="consumed",
    ):
        verify_manager_identity_execution_authorization(
            authorization,
            execution,
            driver,
            preparation,
            runner=FakeRunner(),
            live_gate_builder=_gate_builder(gate),
            now=observed + timedelta(seconds=30),
        )


def test_output_may_not_overlap_execution_package(tmp_path: Path) -> None:
    execution, driver, preparation, gate = _execution_package(tmp_path)
    observed = NOW + timedelta(seconds=30)
    request = _request(
        execution,
        driver,
        preparation,
        gate,
        now=observed,
    )
    output = execution / "greenhouse-m2-manager-execution-authorizations.bad"

    with pytest.raises(
        ManagerIdentityExecutionAuthorizationError,
        match="overlaps protected paths",
    ):
        create_manager_identity_execution_authorization(
            execution,
            driver,
            preparation,
            output,
            confirmation=str(request["required_confirmation"]),
            ttl_seconds=300,
            runner=FakeRunner(),
            live_gate_builder=_gate_builder(gate),
            now=observed,
            token_factory=lambda: "authorization_token_123456",
        )
