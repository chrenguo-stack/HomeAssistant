from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_manager.t1_broker_identity_production_activation_orchestrator import (
    BrokerIdentityProductionActivationOrchestratorError,
    build_production_activation_execution_request,
    execute_production_activation,
)

AUTHORIZATION_ID = "0123456789abcdef01234567"
BUNDLE_SHA = "a" * 64
DRIVER_SHA = "b" * 64
CONTRACT_SHA = "c" * 64
MOUNT_SHA = "d" * 64
MANIFEST_SHA = "e" * 64
PREFLIGHT_SHA = "f" * 64
HA_GATE_SHA = "1" * 64
PLAN_SHA = "2" * 64
ADAPTER_SHA = "3" * 64
RUNTIME_FP = "0123456789abcdef"
CREATED = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
EXPIRES = CREATED + timedelta(minutes=15)
TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"


def _canonical(value: dict[str, object]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha(value: dict[str, object]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _write_private(path: Path, value: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(_canonical(value) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def _binding() -> dict[str, object]:
    return {
        "bundle_sha256": BUNDLE_SHA,
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "runtime_binding_manifest_sha256": MANIFEST_SHA,
        "production_driver_preflight_sha256": PREFLIGHT_SHA,
        "homeassistant_target_gate_sha256": HA_GATE_SHA,
    }


def _scope() -> dict[str, object]:
    return {
        "broker_identity_activation_only": True,
        "preserve_anonymous": True,
        "anonymous_closure_in_transaction": False,
        "homeassistant_reconfigure_in_transaction": False,
        "node_credential_delivery_in_transaction": False,
        "successful_activation_restart_count": 1,
        "rollback_may_require_additional_restart": True,
    }


def _homeassistant() -> dict[str, object]:
    return {
        "target_kind": "loopback",
        "target_fingerprint": "12ca17b49af22894",
        "entry_fingerprint": "9dda2c31088e933e",
        "storage_sha256": "4" * 64,
    }


def _fixture(tmp_path: Path) -> dict[str, object]:
    authorization = {
        "schema": "gh.m2.t1-broker-identity-activation-readiness-authorization/1",
        "authorization_id": AUTHORIZATION_ID,
        "authorization_token": "bundle_bound_authorization_token_123456",
        "created_at": CREATED.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expires_at": EXPIRES.isoformat(timespec="seconds").replace("+00:00", "Z"),
        **_binding(),
        "broker_runtime_fingerprint": RUNTIME_FP,
        "homeassistant_binding": _homeassistant(),
        "activation_scope": _scope(),
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    bundle = {
        "schema": "gh.m2.t1-broker-identity-activation-readiness-bundle/1",
        **_binding(),
        "broker_runtime_fingerprint": RUNTIME_FP,
        "homeassistant_binding": _homeassistant(),
        "activation_scope": _scope(),
    }
    plan = {
        "schema": "gh.m2.t1-broker-identity-activation-readiness-transaction-plan/1",
        "plan_sha256": PLAN_SHA,
        "authorization_id": AUTHORIZATION_ID,
        "authorization_document_sha256": _sha(authorization),
        **_binding(),
        "broker_runtime_fingerprint": RUNTIME_FP,
        "homeassistant_binding": _homeassistant(),
        "activation_scope": _scope(),
    }
    adapter = {
        "schema": "gh.m2.t1-broker-identity-production-transaction-adapter-contract/1",
        "adapter_contract_sha256": ADAPTER_SHA,
        "transaction_plan_sha256": PLAN_SHA,
        "authorization_document_sha256": _sha(authorization),
        **_binding(),
    }
    executor = {
        "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
        "contract_sha256": CONTRACT_SHA,
    }
    manifest = {
        "schema": "gh.m2.t1-broker-identity-runtime-binding-manifest/1",
        "manifest_sha256": MANIFEST_SHA,
    }
    root = tmp_path / "inputs"
    handoff = tmp_path / "handoff"
    handoff.mkdir()
    return {
        "authorization": _write_private(root / "authorization.json", authorization),
        "bundle": _write_private(root / "bundle.json", bundle),
        "plan": _write_private(root / "plan.json", plan),
        "adapter": _write_private(root / "adapter.json", adapter),
        "executor": _write_private(root / "executor.json", executor),
        "manifest": _write_private(root / "manifest.json", manifest),
        "handoff": handoff,
        "transaction_root": tmp_path / "greenhouse-m2-production-transactions-test",
        "authorization_document": authorization,
    }


def _authorization_verifier(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {
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


def _document_verifier(digest_name: str, digest: str):
    def verifier(_document: dict[str, object]) -> dict[str, object]:
        return {"verified": True, digest_name: digest}

    return verifier


def _manifest_verifier(_path: str | Path) -> dict[str, object]:
    return {"verified": True, "manifest_sha256": MANIFEST_SHA}


class FakeAdapters:
    def __init__(self, *, failure: str | None = None) -> None:
        self.failure = failure
        self.mutation_started = False
        self.calls: list[str] = []

    def prepare(self) -> dict[str, object]:
        self.calls.append("prepare")
        return {
            "production_transaction_adapters_installed": True,
            "execution_entrypoint_installed": False,
            "current_services_modified": False,
        }

    def mutation_executor(self) -> dict[str, object]:
        self.calls.append("mutation")
        self.mutation_started = True
        if self.failure == "mutation":
            raise RuntimeError("injected mutation failure")
        return {
            "mutation_started": True,
            "mosquitto_restarted": True,
            "bootstrap_admin_removed": True,
            "provisioning_identity_verified": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }

    def postactivation_auditor(self) -> dict[str, object]:
        self.calls.append("audit")
        if self.failure == "audit":
            raise RuntimeError("injected audit failure")
        return {
            "checks": {"all": True},
            "activation_verified": True,
            "rollback_required": False,
            "broker_identity_activated": True,
            "ready_for_homeassistant_reconfigure_handoff": True,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }

    def rollback_executor(self) -> dict[str, object]:
        self.calls.append("rollback")
        if self.failure == "rollback":
            raise RuntimeError("injected rollback failure")
        return {
            "rollback_completed": True,
            "baseline_config_restored": True,
            "complete_snapshot_inventory_restored": True,
            "dynamic_security_state_absent": True,
            "anonymous_retained_state_readable": True,
            "current_services_modified": False,
        }


def _request(fixture: dict[str, object]) -> dict[str, object]:
    return build_production_activation_execution_request(
        fixture["authorization"],
        fixture["bundle"],
        fixture["plan"],
        fixture["adapter"],
        fixture["executor"],
        fixture["manifest"],
        now=CREATED + timedelta(minutes=5),
        authorization_verifier=_authorization_verifier,
        bundle_verifier=_document_verifier("bundle_sha256", BUNDLE_SHA),
        plan_verifier=_document_verifier("plan_sha256", PLAN_SHA),
        adapter_contract_verifier=_document_verifier(
            "adapter_contract_sha256",
            ADAPTER_SHA,
        ),
        executor_verifier=_document_verifier("contract_sha256", CONTRACT_SHA),
        manifest_verifier=_manifest_verifier,
    )


def _execute(
    fixture: dict[str, object],
    adapters: FakeAdapters,
    *,
    confirmation: str,
    enabled: bool = True,
) -> dict[str, object]:
    return execute_production_activation(
        fixture["authorization"],
        fixture["bundle"],
        fixture["plan"],
        fixture["adapter"],
        fixture["executor"],
        fixture["manifest"],
        fixture["handoff"],
        fixture["transaction_root"],
        expected_retained_topic=TOPIC,
        execution_confirmation=confirmation,
        execution_enabled=enabled,
        now=CREATED + timedelta(minutes=5),
        token_factory=lambda: "transaction_token_1234567890",
        authorization_verifier=_authorization_verifier,
        bundle_verifier=_document_verifier("bundle_sha256", BUNDLE_SHA),
        plan_verifier=_document_verifier("plan_sha256", PLAN_SHA),
        adapter_contract_verifier=_document_verifier(
            "adapter_contract_sha256",
            ADAPTER_SHA,
        ),
        executor_verifier=_document_verifier("contract_sha256", CONTRACT_SHA),
        manifest_verifier=_manifest_verifier,
        driver_factory=lambda *_args, **_kwargs: object(),
        adapters_factory=lambda *_args, **_kwargs: adapters,
    )


def test_builds_secret_free_execution_request(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    report = _request(fixture)

    assert report["execution_request_ready"] is True
    assert report["authorization_valid"] is True
    assert report["authorization_claimed"] is False
    assert report["execution_enabled"] is False
    assert report["current_services_modified"] is False
    assert report["required_confirmation"] == (
        f"EXECUTE-M2-BROKER-ACTIVATION:{BUNDLE_SHA[:16]}:{RUNTIME_FP}:{ADAPTER_SHA[:16]}"
    )
    assert "bundle_bound_authorization_token" not in json.dumps(report)


def test_execution_is_disabled_by_default(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    confirmation = str(_request(fixture)["required_confirmation"])

    with pytest.raises(
        BrokerIdentityProductionActivationOrchestratorError,
        match="execution is disabled",
    ):
        _execute(
            fixture,
            FakeAdapters(),
            confirmation=confirmation,
            enabled=False,
        )
    assert fixture["authorization"].exists()


def test_rejects_wrong_execution_confirmation(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(
        BrokerIdentityProductionActivationOrchestratorError,
        match="confirmation is missing or does not match",
    ):
        _execute(fixture, FakeAdapters(), confirmation="wrong-confirmation")
    assert fixture["authorization"].exists()


def test_success_claims_authorization_and_commits_transaction(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    confirmation = str(_request(fixture)["required_confirmation"])
    adapters = FakeAdapters()

    report = _execute(fixture, adapters, confirmation=confirmation)

    assert report["broker_identity_activated"] is True
    assert report["authorization_claimed"] is True
    assert report["authorization_consumed"] is True
    assert report["postactivation_verified"] is True
    assert report["rollback_completed"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert not fixture["authorization"].exists()
    claim = fixture["authorization"].with_name(f"claimed-{AUTHORIZATION_ID}.json")
    consumed = json.loads(claim.read_text(encoding="utf-8"))
    assert consumed["consumed"] is True
    assert consumed["transaction_id"] == "transaction_token_1234567890"
    assert adapters.calls == ["prepare", "mutation", "audit"]
    journal = fixture["transaction_root"] / "transaction-transaction_token_1234567890/journal.json"
    journal_document = json.loads(journal.read_text(encoding="utf-8"))
    assert journal_document["phase"] == "committed"
    assert journal.stat().st_mode & 0o777 == 0o600


def test_mutation_failure_forces_verified_rollback(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    confirmation = str(_request(fixture)["required_confirmation"])
    adapters = FakeAdapters(failure="mutation")

    with pytest.raises(
        BrokerIdentityProductionActivationOrchestratorError,
        match="verified rollback completed",
    ):
        _execute(fixture, adapters, confirmation=confirmation)
    assert adapters.calls == ["prepare", "mutation", "rollback"]
    journal = fixture["transaction_root"] / "transaction-transaction_token_1234567890/journal.json"
    assert json.loads(journal.read_text(encoding="utf-8"))["phase"] == ("rollback_completed")


def test_postactivation_failure_forces_verified_rollback(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    confirmation = str(_request(fixture)["required_confirmation"])
    adapters = FakeAdapters(failure="audit")

    with pytest.raises(
        BrokerIdentityProductionActivationOrchestratorError,
        match="verified rollback completed",
    ):
        _execute(fixture, adapters, confirmation=confirmation)
    assert adapters.calls == ["prepare", "mutation", "audit", "rollback"]


def test_rollback_failure_is_terminal(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    confirmation = str(_request(fixture)["required_confirmation"])
    adapters = FakeAdapters(failure="rollback")

    original_mutation = adapters.mutation_executor

    def failed_mutation() -> dict[str, object]:
        original_mutation()
        raise RuntimeError("failure after mutation")

    adapters.mutation_executor = failed_mutation  # type: ignore[method-assign]
    with pytest.raises(
        BrokerIdentityProductionActivationOrchestratorError,
        match="activation failed and rollback failed",
    ):
        _execute(fixture, adapters, confirmation=confirmation)
    assert adapters.calls == ["prepare", "mutation", "rollback"]
