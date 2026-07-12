from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_activation_authorization import (
    BrokerIdentityActivationAuthorizationError,
)
from greenhouse_manager.t1_broker_identity_activation_transaction import (
    BrokerIdentityActivationTransactionError,
    build_activation_transaction_plan,
    execute_activation_transaction,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
TARGET = "12ca17b49af22894"
ENTRY = "9dda2c31088e933e"
STORAGE = "e" * 64
NOW = datetime(2026, 7, 12, 9, 0, tzinfo=UTC)
AUTHORIZATION_ID = "0123456789abcdef01234567"
TRANSACTION_ID = "transaction_test_123456"


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        del input_text
        self.commands.append(command)
        return 1, "unexpected command"


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    handoff = tmp_path / "greenhouse-broker-identity-handoff-test"
    handoff.mkdir(mode=0o700)
    stage = tmp_path / "stage"
    stage.mkdir(mode=0o700)
    authorization = tmp_path / "broker-activation-authorization.json"
    _write(handoff / "manifest.json", "{}\n")
    _write(handoff / "activation-plan.json", "{}\n")
    _write(stage / "stage-manifest.json", "{}\n")
    _write(
        authorization,
        json.dumps(
            {
                "schema": (
                    "gh.m2.t1-broker-identity-activation-authorization/1"
                ),
                "authorization_id": AUTHORIZATION_ID,
                "single_use": True,
                "consumed": False,
                "operator_action_authorized": True,
                "apply_enabled": False,
                "ready_for_live_activation": False,
                "current_services_modified": False,
                "preserve_anonymous": True,
                "anonymous_closure_enabled": False,
            }
        ),
    )
    return authorization, handoff, stage


def _authorization_verifier(
    authorization_file: str | Path,
    *_args: object,
    **_kwargs: object,
) -> dict[str, object]:
    path = Path(authorization_file)
    if not path.is_file():
        raise BrokerIdentityActivationAuthorizationError(
            "authorization file is missing"
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("consumed") is not False:
        raise BrokerIdentityActivationAuthorizationError(
            "authorization is consumed"
        )
    return {
        "authorization_id": document["authorization_id"],
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


def _gate(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-broker-identity-preactivation-gate/1",
        "read_only": True,
        "preconditions_ready": True,
        "checks": {
            "handoff_verified": True,
            "fresh_rollback_verified": True,
        },
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def _mutation(*_args: object) -> dict[str, object]:
    return {
        "mutation_started": True,
        "mosquitto_restarted": True,
        "bootstrap_admin_removed": True,
        "provisioning_identity_verified": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def _post(*_args: object) -> dict[str, object]:
    return {
        "activation_verified": True,
        "rollback_required": False,
        "broker_identity_activated": True,
        "ready_for_homeassistant_reconfigure_handoff": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "checks": {
            "dynamic_security_plugin_configured": True,
            "anonymous_compatibility_enabled": True,
        },
    }


def _rollback(*_args: object) -> dict[str, object]:
    return {
        "rollback_completed": True,
        "baseline_config_restored": True,
        "dynamic_security_state_absent": True,
        "anonymous_retained_state_readable": True,
    }


def _plan(
    authorization: Path,
    handoff: Path,
    stage: Path,
    runner: FakeRunner,
) -> dict[str, object]:
    return build_activation_transaction_plan(
        authorization,
        handoff,
        stage,
        expected_retained_topic=TOPIC,
        expected_target_fingerprint=TARGET,
        expected_entry_fingerprint=ENTRY,
        expected_storage_sha256=STORAGE,
        runner=runner,
        now=NOW,
        authorization_verifier=_authorization_verifier,
        preactivation_builder=_gate,
    )


def _execute(
    authorization: Path,
    handoff: Path,
    stage: Path,
    runner: FakeRunner,
    **overrides: Any,
) -> dict[str, object]:
    return execute_activation_transaction(
        authorization,
        handoff,
        stage,
        expected_retained_topic=TOPIC,
        expected_target_fingerprint=TARGET,
        expected_entry_fingerprint=ENTRY,
        expected_storage_sha256=STORAGE,
        execution_enabled=bool(overrides.pop("execution_enabled", True)),
        runner=runner,
        now=NOW,
        token_factory=overrides.pop(
            "token_factory",
            lambda: TRANSACTION_ID,
        ),
        authorization_verifier=overrides.pop(
            "authorization_verifier",
            _authorization_verifier,
        ),
        preactivation_builder=overrides.pop(
            "preactivation_builder",
            _gate,
        ),
        mutation_executor=overrides.pop("mutation_executor", _mutation),
        postactivation_auditor=overrides.pop(
            "postactivation_auditor",
            _post,
        ),
        rollback_executor=overrides.pop(
            "rollback_executor",
            _rollback,
        ),
    )


def _claimed(authorization: Path) -> Path:
    return authorization.with_name(f"claimed-{AUTHORIZATION_ID}.json")


def _journal(authorization: Path) -> Path:
    return authorization.with_name(f"transaction-{TRANSACTION_ID}.json")


def test_plan_is_read_only_and_production_execution_stays_unavailable(
    tmp_path: Path,
) -> None:
    authorization, handoff, stage = _paths(tmp_path)
    runner = FakeRunner()

    report = _plan(authorization, handoff, stage, runner)

    assert report["schema"] == (
        "gh.m2.t1-broker-identity-activation-transaction-plan/1"
    )
    assert report["preconditions_ready"] is True
    assert report["authorization_valid"] is True
    assert report["production_executor_available"] is False
    assert report["execution_enabled"] is False
    assert report["apply_enabled"] is False
    assert report["ready_for_live_activation"] is False
    assert report["current_services_modified"] is False
    assert authorization.is_file()
    assert not _claimed(authorization).exists()
    assert runner.commands == []


def test_execution_disabled_stops_before_authorization_claim(
    tmp_path: Path,
) -> None:
    authorization, handoff, stage = _paths(tmp_path)

    with pytest.raises(
        BrokerIdentityActivationTransactionError,
        match="execution is disabled",
    ):
        _execute(
            authorization,
            handoff,
            stage,
            FakeRunner(),
            execution_enabled=False,
        )

    assert authorization.is_file()
    assert not _claimed(authorization).exists()


def test_missing_executor_stops_before_authorization_claim(
    tmp_path: Path,
) -> None:
    authorization, handoff, stage = _paths(tmp_path)

    with pytest.raises(
        BrokerIdentityActivationTransactionError,
        match="executors are not installed",
    ):
        _execute(
            authorization,
            handoff,
            stage,
            FakeRunner(),
            mutation_executor=None,
        )

    assert authorization.is_file()
    assert not _claimed(authorization).exists()


def test_success_claims_once_and_writes_completed_journal(
    tmp_path: Path,
) -> None:
    authorization, handoff, stage = _paths(tmp_path)

    report = _execute(
        authorization,
        handoff,
        stage,
        FakeRunner(),
    )

    assert report["schema"] == (
        "gh.m2.t1-broker-identity-activation-transaction/1"
    )
    assert report["authorization_consumed"] is True
    assert report["activation_executed"] is True
    assert report["activation_verified"] is True
    assert report["rollback_executed"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert not authorization.exists()
    claimed = _claimed(authorization)
    assert claimed.stat().st_mode & 0o777 == 0o600
    claimed_document = json.loads(claimed.read_text(encoding="utf-8"))
    assert claimed_document["consumed"] is True
    assert claimed_document["transaction_id"] == TRANSACTION_ID
    journal = json.loads(_journal(authorization).read_text(encoding="utf-8"))
    assert journal["phase"] == "completed"
    assert journal["mutation_started"] is True
    assert journal["postactivation_verified"] is True
    assert journal["rollback_attempted"] is False


def test_second_execution_cannot_reuse_claimed_authorization(
    tmp_path: Path,
) -> None:
    authorization, handoff, stage = _paths(tmp_path)
    _execute(authorization, handoff, stage, FakeRunner())

    with pytest.raises(BrokerIdentityActivationAuthorizationError):
        _execute(authorization, handoff, stage, FakeRunner())


def test_mutation_failure_always_runs_rollback_after_executor_entry(
    tmp_path: Path,
) -> None:
    authorization, handoff, stage = _paths(tmp_path)
    calls: list[str] = []

    def fail_mutation(*_args: object) -> dict[str, object]:
        calls.append("mutation")
        raise OSError("injected mutation failure")

    def rollback(*_args: object) -> dict[str, object]:
        calls.append("rollback")
        return _rollback()

    with pytest.raises(
        BrokerIdentityActivationTransactionError,
        match="rollback completed",
    ):
        _execute(
            authorization,
            handoff,
            stage,
            FakeRunner(),
            mutation_executor=fail_mutation,
            rollback_executor=rollback,
        )

    assert calls == ["mutation", "rollback"]
    journal = json.loads(_journal(authorization).read_text(encoding="utf-8"))
    assert journal["phase"] == "rolled_back"
    assert journal["rollback_attempted"] is True
    assert journal["rollback_completed"] is True


def test_postactivation_failure_runs_rollback(tmp_path: Path) -> None:
    authorization, handoff, stage = _paths(tmp_path)
    calls: list[str] = []

    def failed_post(*_args: object) -> dict[str, object]:
        calls.append("post")
        result = _post()
        result["activation_verified"] = False
        result["rollback_required"] = True
        return result

    def rollback(*_args: object) -> dict[str, object]:
        calls.append("rollback")
        return _rollback()

    with pytest.raises(
        BrokerIdentityActivationTransactionError,
        match="rollback completed",
    ):
        _execute(
            authorization,
            handoff,
            stage,
            FakeRunner(),
            postactivation_auditor=failed_post,
            rollback_executor=rollback,
        )

    assert calls == ["post", "rollback"]


def test_incomplete_rollback_is_reported_as_rollback_failure(
    tmp_path: Path,
) -> None:
    authorization, handoff, stage = _paths(tmp_path)

    def fail_mutation(*_args: object) -> dict[str, object]:
        raise OSError("injected mutation failure")

    with pytest.raises(
        BrokerIdentityActivationTransactionError,
        match="rollback failed",
    ):
        _execute(
            authorization,
            handoff,
            stage,
            FakeRunner(),
            mutation_executor=fail_mutation,
            rollback_executor=lambda *_args: {
                "rollback_completed": True,
            },
        )

    journal = json.loads(_journal(authorization).read_text(encoding="utf-8"))
    assert journal["phase"] == "rollback_failed"


def test_claim_collision_fails_closed_without_removing_original(
    tmp_path: Path,
) -> None:
    authorization, handoff, stage = _paths(tmp_path)
    _write(_claimed(authorization), "{}\n")

    with pytest.raises(
        BrokerIdentityActivationTransactionError,
        match="already been claimed",
    ):
        _execute(authorization, handoff, stage, FakeRunner())

    assert authorization.is_file()


def test_invalid_transaction_id_stops_before_claim(tmp_path: Path) -> None:
    authorization, handoff, stage = _paths(tmp_path)

    with pytest.raises(
        BrokerIdentityActivationTransactionError,
        match="invalid value",
    ):
        _execute(
            authorization,
            handoff,
            stage,
            FakeRunner(),
            token_factory=lambda: "../escape",
        )

    assert authorization.is_file()
    assert not _claimed(authorization).exists()
