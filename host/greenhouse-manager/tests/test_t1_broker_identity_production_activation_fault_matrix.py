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

AUTH_ID = "0123456789abcdef01234567"
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
NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"


def _canonical(value: dict[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha(value: dict[str, object]) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _write(path: Path, value: dict[str, object]) -> Path:
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


def _fixture(tmp_path: Path) -> dict[str, Path]:
    authorization = {
        "schema": "gh.m2.t1-broker-identity-activation-readiness-authorization/1",
        "authorization_id": AUTH_ID,
        "authorization_token": "fault_matrix_authorization_token_123456",
        "created_at": NOW.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "expires_at": (NOW + timedelta(minutes=15))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
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
    root = tmp_path / "inputs"
    handoff = tmp_path / "handoff"
    handoff.mkdir()
    return {
        "authorization": _write(root / "authorization.json", authorization),
        "bundle": _write(root / "bundle.json", bundle),
        "plan": _write(root / "plan.json", plan),
        "adapter": _write(root / "adapter.json", adapter),
        "executor": _write(
            root / "executor.json",
            {
                "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
                "contract_sha256": CONTRACT_SHA,
            },
        ),
        "manifest": _write(
            root / "manifest.json",
            {
                "schema": "gh.m2.t1-broker-identity-runtime-binding-manifest/1",
                "manifest_sha256": MANIFEST_SHA,
            },
        ),
        "handoff": handoff,
        "transactions": tmp_path / "greenhouse-m2-production-transactions-matrix",
    }


def _auth_ok(*_args: object, **_kwargs: object) -> dict[str, object]:
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


def _verified(field: str, value: str):
    return lambda _document: {"verified": True, field: value}


def _manifest_ok(_path: str | Path) -> dict[str, object]:
    return {"verified": True, "manifest_sha256": MANIFEST_SHA}


class MatrixAdapters:
    def __init__(self, *, prepare_error: bool = False) -> None:
        self.prepare_error = prepare_error
        self.mutation_started = False
        self.calls: list[str] = []

    def prepare(self) -> dict[str, object]:
        self.calls.append("prepare")
        if self.prepare_error:
            raise RuntimeError("injected prepare failure")
        return {
            "production_transaction_adapters_installed": True,
            "execution_entrypoint_installed": False,
            "current_services_modified": False,
        }

    def mutation_executor(self) -> dict[str, object]:
        self.calls.append("mutation")
        self.mutation_started = True
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
        return {
            "rollback_completed": True,
            "baseline_config_restored": True,
            "complete_snapshot_inventory_restored": True,
            "dynamic_security_state_absent": True,
            "anonymous_retained_state_readable": True,
            "current_services_modified": False,
        }


def _request(files: dict[str, Path], auth_verifier=_auth_ok) -> dict[str, object]:
    return build_production_activation_execution_request(
        files["authorization"],
        files["bundle"],
        files["plan"],
        files["adapter"],
        files["executor"],
        files["manifest"],
        now=NOW + timedelta(minutes=5),
        authorization_verifier=auth_verifier,
        bundle_verifier=_verified("bundle_sha256", BUNDLE_SHA),
        plan_verifier=_verified("plan_sha256", PLAN_SHA),
        adapter_contract_verifier=_verified(
            "adapter_contract_sha256", ADAPTER_SHA
        ),
        executor_verifier=_verified("contract_sha256", CONTRACT_SHA),
        manifest_verifier=_manifest_ok,
    )


def _execute(
    files: dict[str, Path],
    adapters: MatrixAdapters,
    *,
    auth_verifier=_auth_ok,
) -> dict[str, object]:
    confirmation = str(_request(files, auth_verifier)["required_confirmation"])
    return execute_production_activation(
        files["authorization"],
        files["bundle"],
        files["plan"],
        files["adapter"],
        files["executor"],
        files["manifest"],
        files["handoff"],
        files["transactions"],
        expected_retained_topic=TOPIC,
        execution_confirmation=confirmation,
        execution_enabled=True,
        now=NOW + timedelta(minutes=5),
        token_factory=lambda: "fault_matrix_transaction_123456",
        authorization_verifier=auth_verifier,
        bundle_verifier=_verified("bundle_sha256", BUNDLE_SHA),
        plan_verifier=_verified("plan_sha256", PLAN_SHA),
        adapter_contract_verifier=_verified(
            "adapter_contract_sha256", ADAPTER_SHA
        ),
        executor_verifier=_verified("contract_sha256", CONTRACT_SHA),
        manifest_verifier=_manifest_ok,
        driver_factory=lambda *_args, **_kwargs: object(),
        adapters_factory=lambda *_args, **_kwargs: adapters,
    )


def test_prepare_failure_does_not_claim_authorization(tmp_path: Path) -> None:
    files = _fixture(tmp_path)
    adapters = MatrixAdapters(prepare_error=True)
    with pytest.raises(RuntimeError, match="prepare failure"):
        _execute(files, adapters)
    assert files["authorization"].exists()
    assert adapters.calls == ["prepare"]


def test_second_revalidation_failure_does_not_claim_or_mutate(tmp_path: Path) -> None:
    files = _fixture(tmp_path)
    calls = 0

    def expiring_verifier(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls < 3:
            return _auth_ok()
        raise RuntimeError("authorization expired during snapshot preparation")

    adapters = MatrixAdapters()
    with pytest.raises(RuntimeError, match="expired during snapshot"):
        _execute(files, adapters, auth_verifier=expiring_verifier)
    assert files["authorization"].exists()
    assert adapters.calls == ["prepare"]


def test_existing_claim_name_blocks_execution_before_mutation(tmp_path: Path) -> None:
    files = _fixture(tmp_path)
    claim = files["authorization"].with_name(f"claimed-{AUTH_ID}.json")
    claim.write_text("occupied\n", encoding="utf-8")
    claim.chmod(0o600)
    adapters = MatrixAdapters()

    with pytest.raises(
        BrokerIdentityProductionActivationOrchestratorError,
        match="already been claimed",
    ):
        _execute(files, adapters)
    assert files["authorization"].exists()
    assert adapters.calls == ["prepare"]


def test_successful_authorization_cannot_be_replayed(tmp_path: Path) -> None:
    files = _fixture(tmp_path)
    first = MatrixAdapters()
    report = _execute(files, first)
    assert report["authorization_consumed"] is True
    assert not files["authorization"].exists()

    with pytest.raises(
        BrokerIdentityProductionActivationOrchestratorError,
        match="authorization is missing",
    ):
        _execute(files, MatrixAdapters())


def test_binding_drift_rejected_before_workspace_creation(tmp_path: Path) -> None:
    files = _fixture(tmp_path)
    adapter = json.loads(files["adapter"].read_text(encoding="utf-8"))
    adapter["mount_binding_sha256"] = "9" * 64
    _write(files["adapter"], adapter)

    with pytest.raises(
        BrokerIdentityProductionActivationOrchestratorError,
        match="binding failed: mount_binding_sha256",
    ):
        _request(files)
    assert not files["transactions"].exists()
