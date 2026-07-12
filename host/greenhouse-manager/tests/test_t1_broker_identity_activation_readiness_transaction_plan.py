from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_manager.t1_broker_identity_activation_readiness_transaction_plan import (
    BrokerIdentityActivationReadinessTransactionPlanError,
    build_activation_readiness_transaction_plan,
    verify_activation_readiness_transaction_plan,
)

AUTHORIZATION_ID = "0123456789abcdef01234567"
BUNDLE_SHA = "a" * 64
DRIVER_SHA = "b" * 64
CONTRACT_SHA = "c" * 64
MOUNT_SHA = "d" * 64
MANIFEST_SHA = "e" * 64
PREFLIGHT_SHA = "f" * 64
HA_GATE_SHA = "1" * 64
RUNTIME_FP = "0123456789abcdef"
TARGET_FP = "12ca17b49af22894"
ENTRY_FP = "9dda2c31088e933e"
STORAGE_SHA = "2" * 64
TOKEN = "bundle_bound_authorization_token_123456"
CREATED = datetime(2026, 7, 12, 10, 30, tzinfo=UTC)
EXPIRES = CREATED + timedelta(minutes=15)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_private(path: Path, document: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    return path


def _homeassistant_binding() -> dict[str, object]:
    return {
        "target_kind": "loopback",
        "target_fingerprint": TARGET_FP,
        "entry_fingerprint": ENTRY_FP,
        "storage_sha256": STORAGE_SHA,
    }


def _activation_scope() -> dict[str, object]:
    return {
        "broker_identity_activation_only": True,
        "preserve_anonymous": True,
        "anonymous_closure_in_transaction": False,
        "homeassistant_reconfigure_in_transaction": False,
        "node_credential_delivery_in_transaction": False,
        "successful_activation_restart_count": 1,
        "rollback_may_require_additional_restart": True,
    }


def _bundle() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-broker-identity-activation-readiness-bundle/1",
        "bundle_sha256": BUNDLE_SHA,
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "runtime_binding_manifest_sha256": MANIFEST_SHA,
        "production_driver_preflight_sha256": PREFLIGHT_SHA,
        "homeassistant_target_gate_sha256": HA_GATE_SHA,
        "broker_runtime_fingerprint": RUNTIME_FP,
        "homeassistant_binding": _homeassistant_binding(),
        "activation_scope": _activation_scope(),
    }


def _authorization() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-broker-identity-activation-readiness-authorization/1",
        "authorization_id": AUTHORIZATION_ID,
        "authorization_token": TOKEN,
        "created_at": _timestamp(CREATED),
        "expires_at": _timestamp(EXPIRES),
        "activation_readiness_file": "readiness.json",
        "bundle_sha256": BUNDLE_SHA,
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "runtime_binding_manifest_sha256": MANIFEST_SHA,
        "production_driver_preflight_sha256": PREFLIGHT_SHA,
        "homeassistant_target_gate_sha256": HA_GATE_SHA,
        "broker_runtime_fingerprint": RUNTIME_FP,
        "homeassistant_binding": _homeassistant_binding(),
        "activation_scope": _activation_scope(),
        "single_use": True,
        "consumed": False,
        "operator_action_authorized": True,
        "apply_enabled": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def _bundle_verifier(_document: dict[str, object]) -> dict[str, object]:
    return {
        "verified": True,
        "bundle_sha256": BUNDLE_SHA,
    }


def _authorization_verifier(
    _authorization_file: str | Path,
    _bundle_file: str | Path,
    **_kwargs: object,
) -> dict[str, object]:
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


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    bundle_root = tmp_path / "greenhouse-m2-runtime-bindings-test"
    authorization_root = tmp_path / "greenhouse-m2-activation-authorizations-test"
    output = tmp_path / "greenhouse-m2-activation-plans-test"
    bundle = _write_private(bundle_root / "readiness.json", _bundle())
    authorization = _write_private(
        authorization_root / "authorization.json",
        _authorization(),
    )
    return authorization, bundle, output


def _build(tmp_path: Path) -> tuple[dict[str, object], Path]:
    authorization, bundle, output = _fixture(tmp_path)
    summary = build_activation_readiness_transaction_plan(
        authorization,
        bundle,
        output,
        now=CREATED + timedelta(minutes=5),
        authorization_verifier=_authorization_verifier,
        bundle_verifier=_bundle_verifier,
    )
    plan_path = output / str(summary["transaction_plan_file"])
    return summary, plan_path


def test_builds_private_non_executable_transaction_plan(tmp_path: Path) -> None:
    summary, plan_path = _build(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    verified = verify_activation_readiness_transaction_plan(plan)

    assert verified["verified"] is True
    assert summary["transaction_plan_ready"] is True
    assert summary["authorization_valid"] is True
    assert summary["authorization_claimed"] is False
    assert summary["claim_enabled"] is False
    assert summary["production_transaction_adapters_installed"] is False
    assert summary["production_executor_available"] is False
    assert summary["execution_enabled"] is False
    assert summary["apply_enabled"] is False
    assert summary["operator_action_authorized"] is True
    assert summary["ready_for_live_activation"] is False
    assert summary["current_services_modified"] is False
    assert summary["preserve_anonymous"] is True
    assert summary["anonymous_closure_enabled"] is False
    assert summary["secret_values_redacted"] is True
    assert summary["path_values_redacted"] is True
    assert plan_path.stat().st_mode & 0o777 == 0o600
    assert TOKEN not in json.dumps(summary)
    assert TOKEN not in json.dumps(plan)
    assert plan["authorization_document_sha256"] == hashlib.sha256(
        json.dumps(
            _authorization(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert plan["transaction_contract"] == {
        "authorization_claim_required": True,
        "authorization_claim_method": "same_filesystem_hardlink_then_unlink",
        "private_journal_required": True,
        "postactivation_audit_required": True,
        "rollback_mandatory_on_failure": True,
        "successful_activation_restart_count": 1,
        "rollback_may_require_additional_restart": True,
        "homeassistant_reconfigure_after_activation_only": True,
        "node_credential_delivery_after_activation_only": True,
        "anonymous_closure_forbidden": True,
    }


def test_plan_survives_json_round_trip(tmp_path: Path) -> None:
    _summary, plan_path = _build(tmp_path)
    parsed = json.loads(json.dumps(json.loads(plan_path.read_text(encoding="utf-8"))))
    assert verify_activation_readiness_transaction_plan(parsed)["verified"] is True


def test_rejects_authorization_verifier_failure(tmp_path: Path) -> None:
    authorization, bundle, output = _fixture(tmp_path)

    def invalid_verifier(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "valid_now": False,
            "single_use": True,
            "consumed": False,
            "operator_action_authorized": True,
            "apply_enabled": False,
            "ready_for_live_activation": False,
            "current_services_modified": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }

    with pytest.raises(
        BrokerIdentityActivationReadinessTransactionPlanError,
        match="authorization verification failed: valid_now",
    ):
        build_activation_readiness_transaction_plan(
            authorization,
            bundle,
            output,
            now=CREATED + timedelta(minutes=5),
            authorization_verifier=invalid_verifier,
            bundle_verifier=_bundle_verifier,
        )


def test_rejects_authorization_bundle_binding_drift(tmp_path: Path) -> None:
    authorization, bundle, output = _fixture(tmp_path)
    document = json.loads(authorization.read_text(encoding="utf-8"))
    document["mount_binding_sha256"] = "9" * 64
    _write_private(authorization, document)

    with pytest.raises(
        BrokerIdentityActivationReadinessTransactionPlanError,
        match="authorization-to-bundle binding failed: mount_binding_sha256",
    ):
        build_activation_readiness_transaction_plan(
            authorization,
            bundle,
            output,
            now=CREATED + timedelta(minutes=5),
            authorization_verifier=_authorization_verifier,
            bundle_verifier=_bundle_verifier,
        )


def test_rejects_plan_output_over_source_directory(tmp_path: Path) -> None:
    bundle_root = tmp_path / "greenhouse-m2-runtime-bindings-test"
    source = tmp_path / "greenhouse-m2-activation-plans-source"
    bundle = _write_private(bundle_root / "readiness.json", _bundle())
    authorization = _write_private(source / "authorization.json", _authorization())

    with pytest.raises(
        BrokerIdentityActivationReadinessTransactionPlanError,
        match="must be separate from source artifacts",
    ):
        build_activation_readiness_transaction_plan(
            authorization,
            bundle,
            source,
            now=CREATED + timedelta(minutes=5),
            authorization_verifier=_authorization_verifier,
            bundle_verifier=_bundle_verifier,
        )


def test_cli_exposes_no_claim_execute_apply_or_live_option() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_activation_readiness_transaction_plan.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "build" in completed.stdout
    assert "verify" in completed.stdout
    assert "--claim" not in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
