from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from greenhouse_manager.t1_broker_identity_activation_readiness_authorization import (
    BrokerIdentityActivationReadinessAuthorizationError,
    build_activation_readiness_authorization_request,
    create_activation_readiness_authorization,
    verify_activation_readiness_authorization,
)

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


def _write_private(path: Path, document: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    return path


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
        "homeassistant_binding": {
            "target_kind": "loopback",
            "target_fingerprint": TARGET_FP,
            "entry_fingerprint": ENTRY_FP,
            "storage_sha256": STORAGE_SHA,
        },
        "activation_scope": {
            "broker_identity_activation_only": True,
            "preserve_anonymous": True,
            "anonymous_closure_in_transaction": False,
            "homeassistant_reconfigure_in_transaction": False,
            "node_credential_delivery_in_transaction": False,
            "successful_activation_restart_count": 1,
            "rollback_may_require_additional_restart": True,
        },
        "readiness_bundle_complete": True,
        "operator_decision_required": True,
        "single_use_authorization_created": False,
        "production_driver_installed": False,
        "production_executor_available": False,
        "execution_enabled": False,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "path_values_redacted": True,
        "secret_values_included": False,
    }


def _bundle_verifier(_document: dict[str, object]) -> dict[str, object]:
    return {
        "verified": True,
        "bundle_sha256": BUNDLE_SHA,
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    runtime = tmp_path / "greenhouse-m2-runtime-bindings-test"
    runtime.mkdir(mode=0o700)
    bundle_path = _write_private(runtime / "readiness.json", _bundle())
    output = tmp_path / "greenhouse-m2-activation-authorizations-test"
    return bundle_path, output


def _confirmation() -> str:
    return f"AUTHORIZE-M2-BROKER-BUNDLE:{BUNDLE_SHA[:16]}:{RUNTIME_FP}"


def test_builds_non_authorizing_request(tmp_path: Path) -> None:
    bundle_path, _output = _fixture(tmp_path)
    request = build_activation_readiness_authorization_request(
        bundle_path,
        bundle_verifier=_bundle_verifier,
    )

    assert request["required_confirmation"] == _confirmation()
    assert request["authorization_created"] is False
    assert request["operator_action_authorized"] is False
    assert request["apply_enabled"] is False
    assert request["ready_for_live_activation"] is False
    assert request["current_services_modified"] is False
    assert request["preserve_anonymous"] is True
    assert request["anonymous_closure_enabled"] is False
    assert request["secret_values_included"] is False
    assert request["path_values_redacted"] is True
    assert request["bundle_sha256"] == BUNDLE_SHA
    assert request["broker_runtime_fingerprint"] == RUNTIME_FP


def test_creates_and_verifies_short_lived_single_use_authorization(tmp_path: Path) -> None:
    bundle_path, output = _fixture(tmp_path)
    created_at = datetime(2026, 7, 12, 10, 30, tzinfo=UTC)
    summary = create_activation_readiness_authorization(
        bundle_path,
        output,
        confirmation=_confirmation(),
        ttl_seconds=900,
        now=created_at,
        token_factory=lambda: TOKEN,
        bundle_verifier=_bundle_verifier,
    )
    authorization_path = output / str(summary["authorization_file"])
    verified = verify_activation_readiness_authorization(
        authorization_path,
        bundle_path,
        now=created_at + timedelta(minutes=5),
        bundle_verifier=_bundle_verifier,
    )
    document = json.loads(authorization_path.read_text(encoding="utf-8"))

    assert authorization_path.stat().st_mode & 0o777 == 0o600
    assert verified["valid_now"] is True
    assert verified["single_use"] is True
    assert verified["consumed"] is False
    assert verified["operator_action_authorized"] is True
    assert verified["apply_enabled"] is False
    assert verified["ready_for_live_activation"] is False
    assert verified["current_services_modified"] is False
    assert verified["preserve_anonymous"] is True
    assert verified["anonymous_closure_enabled"] is False
    assert summary["secret_values_redacted"] is True
    assert TOKEN not in json.dumps(summary)
    assert str(output) not in json.dumps(summary)
    assert document["authorization_token"] == TOKEN
    assert document["authorization_id"] == hashlib.sha256(TOKEN.encode()).hexdigest()[:24]
    assert document["bundle_sha256"] == BUNDLE_SHA
    assert document["homeassistant_binding"]["storage_sha256"] == STORAGE_SHA


def test_rejects_wrong_confirmation(tmp_path: Path) -> None:
    bundle_path, output = _fixture(tmp_path)
    with pytest.raises(
        BrokerIdentityActivationReadinessAuthorizationError,
        match="confirmation is missing or does not match",
    ):
        create_activation_readiness_authorization(
            bundle_path,
            output,
            confirmation="AUTHORIZE-NOTHING",
            token_factory=lambda: TOKEN,
            bundle_verifier=_bundle_verifier,
        )
    assert not output.exists()


def test_rejects_expired_authorization(tmp_path: Path) -> None:
    bundle_path, output = _fixture(tmp_path)
    created_at = datetime(2026, 7, 12, 10, 30, tzinfo=UTC)
    summary = create_activation_readiness_authorization(
        bundle_path,
        output,
        confirmation=_confirmation(),
        ttl_seconds=60,
        now=created_at,
        token_factory=lambda: TOKEN,
        bundle_verifier=_bundle_verifier,
    )
    authorization_path = output / str(summary["authorization_file"])
    with pytest.raises(
        BrokerIdentityActivationReadinessAuthorizationError,
        match="not currently valid",
    ):
        verify_activation_readiness_authorization(
            authorization_path,
            bundle_path,
            now=created_at + timedelta(seconds=61),
            bundle_verifier=_bundle_verifier,
        )


def test_rejects_consumed_authorization(tmp_path: Path) -> None:
    bundle_path, output = _fixture(tmp_path)
    created_at = datetime(2026, 7, 12, 10, 30, tzinfo=UTC)
    summary = create_activation_readiness_authorization(
        bundle_path,
        output,
        confirmation=_confirmation(),
        now=created_at,
        token_factory=lambda: TOKEN,
        bundle_verifier=_bundle_verifier,
    )
    authorization_path = output / str(summary["authorization_file"])
    document = json.loads(authorization_path.read_text(encoding="utf-8"))
    document["consumed"] = True
    _write_private(authorization_path, document)

    with pytest.raises(
        BrokerIdentityActivationReadinessAuthorizationError,
        match="binding failed: consumed",
    ):
        verify_activation_readiness_authorization(
            authorization_path,
            bundle_path,
            now=created_at + timedelta(minutes=1),
            bundle_verifier=_bundle_verifier,
        )


def test_rejects_bundle_binding_drift(tmp_path: Path) -> None:
    bundle_path, output = _fixture(tmp_path)
    created_at = datetime(2026, 7, 12, 10, 30, tzinfo=UTC)
    summary = create_activation_readiness_authorization(
        bundle_path,
        output,
        confirmation=_confirmation(),
        now=created_at,
        token_factory=lambda: TOKEN,
        bundle_verifier=_bundle_verifier,
    )
    authorization_path = output / str(summary["authorization_file"])
    document = json.loads(authorization_path.read_text(encoding="utf-8"))
    document["mount_binding_sha256"] = "9" * 64
    _write_private(authorization_path, document)

    with pytest.raises(
        BrokerIdentityActivationReadinessAuthorizationError,
        match="binding failed: mount_binding_sha256",
    ):
        verify_activation_readiness_authorization(
            authorization_path,
            bundle_path,
            now=created_at + timedelta(minutes=1),
            bundle_verifier=_bundle_verifier,
        )


def test_cli_exposes_no_apply_or_live_option() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_activation_readiness_authorization.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "request" in completed.stdout
    assert "create" in completed.stdout
    assert "verify" in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
