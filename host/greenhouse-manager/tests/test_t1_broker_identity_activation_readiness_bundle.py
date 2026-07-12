from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager.t1_broker_identity_activation_readiness_bundle import (
    BrokerIdentityActivationReadinessBundleError,
    build_activation_readiness_bundle,
    verify_activation_readiness_bundle,
)

DRIVER_SHA = "a" * 64
CONTRACT_SHA = "b" * 64
MOUNT_SHA = "c" * 64
MANIFEST_SHA = "d" * 64
PREFLIGHT_SHA = "e" * 64
TARGET = "12ca17b49af22894"
ENTRY = "9dda2c31088e933e"
STORAGE = "f" * 64


def _write_private(path: Path, document: dict[str, object]) -> Path:
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    return path


def _documents() -> dict[str, dict[str, object]]:
    driver = {
        "schema": "gh.m2.t1-broker-identity-production-driver-contract/1",
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
    }
    executor = {
        "schema": "gh.m2.t1-broker-identity-production-executor-contract/1",
        "contract_sha256": CONTRACT_SHA,
    }
    manifest = {
        "schema": "gh.m2.t1-broker-identity-runtime-binding-manifest/1",
        "manifest_sha256": MANIFEST_SHA,
        "created_at": "2026-07-12T09:57:16Z",
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "runtime": {
            "container_id": "1" * 64,
            "image_id": "sha256:" + "2" * 64,
            "started_at": "2026-07-12T08:00:00Z",
            "restart_count": 0,
        },
    }
    preflight = {
        "schema": "gh.m2.t1-broker-identity-production-driver-preflight/1",
        "preflight_sha256": PREFLIGHT_SHA,
        "driver_contract_sha256": DRIVER_SHA,
        "contract_sha256": CONTRACT_SHA,
        "mount_binding_sha256": MOUNT_SHA,
        "runtime_binding_manifest_sha256": MANIFEST_SHA,
    }
    ha_gate = {
        "schema": "gh.m2.t1-homeassistant-mqtt-target-gate/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "prior_audit_complete": True,
        "target_model_ready": True,
        "selected_target_kind": "loopback",
        "selected_target_fingerprint": TARGET,
        "ready_for_operator_reconfigure": False,
        "ready_for_live_apply": False,
        "activation_blockers": [
            "broker_identity_not_activated",
            "homeassistant_operator_reconfigure_required",
            "node_credential_delivery_path_unverified",
        ],
        "homeassistant_official_reconfigure": {
            "official_config_flow_only": True,
            "direct_storage_edit_forbidden": True,
            "automatic_apply": False,
            "operator_action_required": True,
            "operator_action_authorized": False,
            "pre_change_entry_fingerprint": ENTRY,
            "pre_change_storage_sha256": STORAGE,
            "staged_material_complete": True,
            "discovery_preserved": True,
            "retained_baseline_readable": True,
            "post_change_reaudit_required": True,
            "rollback_via_official_reconfigure_or_fresh_backup": True,
        },
    }
    return {
        "driver": driver,
        "executor": executor,
        "manifest": manifest,
        "preflight": preflight,
        "ha_gate": ha_gate,
    }


def _fixture(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "greenhouse-m2-runtime-bindings-test"
    root.mkdir(mode=0o700)
    documents = _documents()
    return {
        "root": root,
        "driver": _write_private(root / "driver.json", documents["driver"]),
        "executor": _write_private(root / "executor.json", documents["executor"]),
        "manifest": _write_private(root / "manifest.json", documents["manifest"]),
        "preflight": _write_private(root / "preflight.json", documents["preflight"]),
        "ha_gate": _write_private(root / "ha-gate.json", documents["ha_gate"]),
    }


def _build(tmp_path: Path, *, now: datetime | None = None) -> tuple[dict[str, object], Path]:
    fixture = _fixture(tmp_path)
    summary = build_activation_readiness_bundle(
        fixture["driver"],
        fixture["executor"],
        fixture["manifest"],
        fixture["preflight"],
        fixture["ha_gate"],
        fixture["root"],
        now=now or datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        driver_verifier=lambda _document: {
            "verified": True,
            "driver_contract_sha256": DRIVER_SHA,
        },
        executor_verifier=lambda _document: {
            "verified": True,
            "contract_sha256": CONTRACT_SHA,
        },
        manifest_verifier=lambda _path: {
            "verified": True,
            "manifest_sha256": MANIFEST_SHA,
        },
        preflight_verifier=lambda _document: {
            "verified": True,
            "preflight_sha256": PREFLIGHT_SHA,
        },
    )
    bundle_path = fixture["root"] / str(summary["activation_readiness_file"])
    return summary, bundle_path


def test_builds_private_non_authorizing_activation_readiness_bundle(tmp_path: Path) -> None:
    summary, bundle_path = _build(tmp_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    verified = verify_activation_readiness_bundle(bundle)

    assert verified["verified"] is True
    assert summary["readiness_bundle_complete"] is True
    assert summary["operator_decision_required"] is True
    assert summary["production_driver_installed"] is False
    assert summary["production_executor_available"] is False
    assert summary["execution_enabled"] is False
    assert summary["apply_enabled"] is False
    assert summary["operator_action_authorized"] is False
    assert summary["ready_for_live_activation"] is False
    assert summary["current_services_modified"] is False
    assert summary["preserve_anonymous"] is True
    assert summary["anonymous_closure_enabled"] is False
    assert summary["path_values_redacted"] is True
    assert summary["secret_values_included"] is False
    assert summary["target_kind"] == "loopback"
    assert summary["target_fingerprint"] == TARGET
    assert bundle_path.stat().st_mode & 0o777 == 0o600
    assert bundle["single_use_authorization_created"] is False
    assert bundle["activation_scope"] == {
        "broker_identity_activation_only": True,
        "preserve_anonymous": True,
        "anonymous_closure_in_transaction": False,
        "homeassistant_reconfigure_in_transaction": False,
        "node_credential_delivery_in_transaction": False,
        "successful_activation_restart_count": 1,
        "rollback_may_require_additional_restart": True,
    }
    serialized_summary = json.dumps(summary)
    assert str(bundle_path.parent) not in serialized_summary
    assert STORAGE in json.dumps(bundle)


def test_bundle_survives_json_round_trip(tmp_path: Path) -> None:
    _summary, bundle_path = _build(tmp_path)
    parsed = json.loads(json.dumps(json.loads(bundle_path.read_text(encoding="utf-8"))))
    assert verify_activation_readiness_bundle(parsed)["verified"] is True


def test_rejects_cross_bound_preflight(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    document = json.loads(fixture["preflight"].read_text(encoding="utf-8"))
    document["runtime_binding_manifest_sha256"] = "9" * 64
    _write_private(fixture["preflight"], document)

    with pytest.raises(
        BrokerIdentityActivationReadinessBundleError,
        match="input binding does not match",
    ):
        build_activation_readiness_bundle(
            fixture["driver"],
            fixture["executor"],
            fixture["manifest"],
            fixture["preflight"],
            fixture["ha_gate"],
            fixture["root"],
            now=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
            driver_verifier=lambda _document: {
                "verified": True,
                "driver_contract_sha256": DRIVER_SHA,
            },
            executor_verifier=lambda _document: {
                "verified": True,
                "contract_sha256": CONTRACT_SHA,
            },
            manifest_verifier=lambda _path: {
                "verified": True,
                "manifest_sha256": MANIFEST_SHA,
            },
            preflight_verifier=lambda _document: {
                "verified": True,
                "preflight_sha256": PREFLIGHT_SHA,
            },
        )


def test_rejects_stale_runtime_binding(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityActivationReadinessBundleError,
        match="manifest is stale",
    ):
        _build(tmp_path, now=datetime(2026, 7, 12, 11, 0, tzinfo=UTC))


def test_rejects_inputs_from_another_directory(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    misplaced = _write_private(
        other / "ha-gate.json",
        _documents()["ha_gate"],
    )

    with pytest.raises(
        BrokerIdentityActivationReadinessBundleError,
        match="must share the private output directory",
    ):
        build_activation_readiness_bundle(
            fixture["driver"],
            fixture["executor"],
            fixture["manifest"],
            fixture["preflight"],
            misplaced,
            fixture["root"],
            now=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
            driver_verifier=lambda _document: {
                "verified": True,
                "driver_contract_sha256": DRIVER_SHA,
            },
            executor_verifier=lambda _document: {
                "verified": True,
                "contract_sha256": CONTRACT_SHA,
            },
            manifest_verifier=lambda _path: {
                "verified": True,
                "manifest_sha256": MANIFEST_SHA,
            },
            preflight_verifier=lambda _document: {
                "verified": True,
                "preflight_sha256": PREFLIGHT_SHA,
            },
        )


def test_cli_has_no_authorize_or_execute_option() -> None:
    project = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "tools/run_t1_broker_identity_activation_readiness_bundle.py",
            "--help",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "production_driver_preflight_file" in completed.stdout
    assert "homeassistant_target_gate_file" in completed.stdout
    assert "--authorize" not in completed.stdout
    assert "--execute" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
