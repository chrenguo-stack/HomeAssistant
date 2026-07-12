from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.t1_broker_identity_activation_handoff import (
    BrokerIdentityActivationHandoffError,
    prepare_broker_identity_activation_handoff,
    verify_broker_identity_activation_handoff,
)


class FakeRunner:
    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        del command, input_text
        return 0, ""


def _stage(tmp_path: Path) -> Path:
    stage = tmp_path / "stage"
    stage.mkdir(mode=0o700)
    (stage / "stage-manifest.json").write_text("{}\n", encoding="utf-8")
    (stage / "stage-manifest.json").chmod(0o600)
    plan = {
        "schema": "gh.m2.t1-auth-migration-stage-plan/1",
        "activation_enabled": False,
        "current_services_modified": False,
        "active_paths_modified": False,
        "requires_explicit_gate": True,
        "requires_fresh_backup_immediately_before_apply": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }
    (stage / "activation-plan.json").write_text(
        json.dumps(plan),
        encoding="utf-8",
    )
    (stage / "activation-plan.json").chmod(0o600)

    files = {
        "payload/broker/dynsec-request.json": json.dumps(
            {
                "commands": [
                    {
                        "command": "createClient",
                        "username": "gh-ha-user",
                        "password": "broker-secret-password",
                    }
                ]
            }
        ),
        "payload/broker/mosquitto-plugin.conf": (
            "plugin /usr/lib/mosquitto_dynamic_security.so\n"
            "plugin_opt_config_file /mosquitto/data/dynamic-security.json\n"
        ),
        "payload/bootstrap/dynsec-password-init": "bootstrap-secret-password\n",
        "payload/bootstrap/admin-client.conf": (
            "-h 127.0.0.1\n-u admin\n-P bootstrap-secret-password\n"
            "-i gh-m2-bootstrap-admin\n-V 5\n"
        ),
        "payload/provisioning/mosquitto-client.conf": (
            "-h 127.0.0.1\n-u gh-provisioning\n-P provisioning-secret\n"
            "-i gh-provisioning-client\n-V 5\n"
        ),
        "payload/provisioning/identity.json": json.dumps(
            {
                "label": "provisioning",
                "username": "gh-provisioning",
                "client_id": "gh-provisioning-client",
            }
        ),
        "payload/homeassistant/mqtt-update.json": json.dumps(
            {
                "schema": "gh.m2.homeassistant-mqtt-update/1",
                "username": "gh-ha-user",
                "password": "homeassistant-secret-password",
                "required_client_id": "gh-ha-client",
            }
        ),
        "payload/homeassistant/identity.json": json.dumps(
            {
                "label": "homeassistant",
                "username": "gh-ha-user",
                "client_id": "gh-ha-client",
            }
        ),
    }
    for relative, content in files.items():
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
    return stage


def _stage_manifest(_path: str | Path) -> dict[str, Any]:
    return {
        "schema": "gh.m2.t1-auth-migration-stage/1",
        "readiness_binding": {
            "broker_config_sha256": "a" * 64,
        },
    }


def _audit(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "schema": "gh.m2.t1-auth-client-migration-audit/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "audit_complete": True,
        "ready_for_live_apply": False,
        "live_readiness": {
            "ready": True,
            "source_binding": True,
            "retained_topic_readable": True,
        },
        "stage": {
            "verified": True,
            "activation_enabled": False,
            "active_paths_modified": False,
        },
    }
    report.update(overrides)
    return report


def _rehearsal(**overrides: object) -> dict[str, object]:
    report: dict[str, object] = {
        "schema": "gh.m2.t1-auth-migration-stage-rehearsal/1",
        "network": "none",
        "stage_verified": True,
        "staged_package_verified": True,
        "fault_after_exact_request_injected": True,
        "fault_candidate_cleanup": True,
        "success_candidate_cleanup": True,
        "stage_immutable": True,
        "live_sources_unchanged": True,
        "source_binding": True,
        "exact_package_request_applied": True,
        "exact_package_identity_matrix": True,
        "client_id_binding": True,
        "provisioning_control_only": True,
        "bootstrap_admin_removed": True,
        "provisioning_after_admin_removal": True,
        "legacy_anonymous_after_admin_removal": True,
        "anonymous_control_denied": True,
        "retained_state_recovered": True,
        "activation_enabled": False,
        "active_paths_modified": False,
        "current_services_modified": False,
    }
    report.update(overrides)
    return report


def _backup_creator(output: Path, **_kwargs: object) -> Path:
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = output / "greenhouse-t1-rollback-test.tar.gz"
    path.write_bytes(b"fresh-rollback")
    path.chmod(0o600)
    return path


def _backup_verifier(_path: str | Path) -> dict[str, Any]:
    return {"schema": "gh.m2.t1-backup/1"}


def _prepare(
    tmp_path: Path,
    *,
    audit: dict[str, object] | None = None,
    rehearsal: dict[str, object] | None = None,
) -> dict[str, object]:
    stage = _stage(tmp_path)
    output = tmp_path / "output"
    return prepare_broker_identity_activation_handoff(
        stage,
        output,
        expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
        runner=FakeRunner(),
        now=datetime(2026, 7, 12, 7, 0, tzinfo=UTC),
        token_factory=lambda: "testtoken",
        stage_verifier=_stage_manifest,
        audit_builder=lambda *_args, **_kwargs: audit or _audit(),
        rehearsal_runner=lambda *_args, **_kwargs: rehearsal or _rehearsal(),
        backup_creator=_backup_creator,
        backup_verifier=_backup_verifier,
    )


def test_prepare_creates_private_disabled_handoff(tmp_path: Path) -> None:
    report = _prepare(tmp_path)

    assert report["schema"] == "gh.m2.t1-broker-identity-activation-handoff/1"
    assert report["preserve_anonymous"] is True
    assert report["apply_enabled"] is False
    assert report["operator_action_authorized"] is False
    assert report["ready_for_live_activation"] is False
    assert report["current_services_modified"] is False

    root = Path(str(report["handoff_directory"]))
    assert root.stat().st_mode & 0o777 == 0o700
    plan = json.loads((root / "activation-plan.json").read_text(encoding="utf-8"))
    assert plan["direct_live_apply_forbidden"] is True
    assert plan["preserve_anonymous"] is True
    assert plan["anonymous_closure_enabled"] is False
    assert (root / "material/broker/dynsec-request.json").stat().st_mode & 0o777 == 0o600
    assert "broker-secret-password" not in json.dumps(report)
    assert "homeassistant-secret-password" not in json.dumps(report)


def test_prepare_rejects_stage_manifest_drift(tmp_path: Path) -> None:
    stage = _stage(tmp_path)
    output = tmp_path / "output"

    with pytest.raises(
        BrokerIdentityActivationHandoffError,
        match="manifest fingerprint has drifted",
    ):
        prepare_broker_identity_activation_handoff(
            stage,
            output,
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            expected_stage_manifest_sha256="0" * 64,
            runner=FakeRunner(),
            stage_verifier=_stage_manifest,
        )


def test_prepare_rejects_unsafe_live_audit(tmp_path: Path) -> None:
    unsafe = _audit(
        live_readiness={
            "ready": True,
            "source_binding": True,
            "retained_topic_readable": False,
        }
    )

    with pytest.raises(
        BrokerIdentityActivationHandoffError,
        match="live readiness is not safe",
    ):
        _prepare(tmp_path, audit=unsafe)


def test_prepare_rejects_missing_anonymous_rehearsal_proof(
    tmp_path: Path,
) -> None:
    rehearsal = _rehearsal(legacy_anonymous_after_admin_removal=False)

    with pytest.raises(
        BrokerIdentityActivationHandoffError,
        match="legacy_anonymous_after_admin_removal",
    ):
        _prepare(tmp_path, rehearsal=rehearsal)


def test_prepare_rejects_output_overlap(tmp_path: Path) -> None:
    stage = _stage(tmp_path)

    with pytest.raises(
        BrokerIdentityActivationHandoffError,
        match="must not overlap",
    ):
        prepare_broker_identity_activation_handoff(
            stage,
            stage / "handoff",
            expected_retained_topic="gh/v1/greenhouse/state/node/telemetry",
            runner=FakeRunner(),
            stage_verifier=_stage_manifest,
        )


def test_verify_accepts_complete_handoff(tmp_path: Path) -> None:
    report = _prepare(tmp_path)

    verified = verify_broker_identity_activation_handoff(
        str(report["handoff_directory"]),
        backup_verifier=_backup_verifier,
    )

    assert verified["schema"] == (
        "gh.m2.t1-broker-identity-activation-handoff-verify/1"
    )
    assert verified["fresh_rollback_verified"] is True
    assert verified["candidate_rehearsal_verified"] is True
    assert verified["apply_enabled"] is False
    assert verified["operator_action_authorized"] is False


def test_verify_rejects_tampered_material(tmp_path: Path) -> None:
    report = _prepare(tmp_path)
    root = Path(str(report["handoff_directory"]))
    target = root / "material/broker/mosquitto-plugin.conf"
    target.write_text("tampered\n", encoding="utf-8")
    target.chmod(0o600)

    with pytest.raises(
        BrokerIdentityActivationHandoffError,
        match="size mismatch|checksum mismatch",
    ):
        verify_broker_identity_activation_handoff(
            root,
            backup_verifier=_backup_verifier,
        )
