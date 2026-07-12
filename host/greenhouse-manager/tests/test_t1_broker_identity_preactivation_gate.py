from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from greenhouse_manager.t1_broker_identity_activation_checks import (
    BrokerIdentityActivationCheckError,
)
from greenhouse_manager.t1_broker_identity_preactivation_gate import (
    build_broker_identity_preactivation_gate,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
TARGET = "12ca17b49af22894"
ENTRY = "9dda2c31088e933e"
STORAGE = "e" * 64


class FakeRunner:
    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        del input_text
        if command[:3] == ("docker", "inspect", "-f"):
            return 0, json.dumps(
                {
                    "state": "running",
                    "restarts": "0",
                    "image_id": f"sha256:{command[-1]}",
                }
            )
        return 1, "unexpected command"


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    stage = tmp_path / "stage"
    stage.mkdir(mode=0o700)
    _write(stage / "stage-manifest.json", "stage\n")
    handoff = tmp_path / "handoff"
    handoff.mkdir(mode=0o700)
    stage_binding = {
        "name": "stage",
        "manifest_sha256": hashlib.sha256(b"stage\n").hexdigest(),
        "broker_config_sha256": "a" * 64,
    }
    _write(
        handoff / "manifest.json",
        json.dumps(
            {
                "schema": "gh.m2.t1-broker-identity-activation-handoff/1",
                "stage": stage_binding,
            }
        ),
    )
    _write(
        handoff / "activation-plan.json",
        json.dumps(
            {
                "schema": "gh.m2.t1-broker-identity-activation-plan/1",
                "live_broker_config_sha256": "a" * 64,
            }
        ),
    )
    return handoff, stage


def _verified(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {
        "fresh_rollback_verified": True,
        "candidate_rehearsal_verified": True,
        "preserve_anonymous": True,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
    }


def _audit(live_sha: str = "a" * 64, **overrides: object) -> dict[str, object]:
    gates = {
        "anonymous_access_still_enabled": True,
        "dynamic_security_not_configured": True,
        "dynamic_security_state_absent": True,
        "dynamic_security_plugin_available": True,
        "retained_topic_readable": True,
        "no_candidate_containers": True,
    }
    gates.update(overrides)
    return {
        "schema": "gh.m2.t1-auth-client-migration-audit/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "audit_complete": True,
        "ready_for_live_apply": False,
        "live_readiness": {
            "ready": True,
            "broker": {"live_config_sha256": live_sha},
            "gates": gates,
        },
    }


def _target(fingerprint: str = TARGET) -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-homeassistant-mqtt-target-gate/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "target_model_ready": True,
        "selected_target_kind": "loopback",
        "selected_target_fingerprint": fingerprint,
        "ready_for_operator_reconfigure": False,
        "ready_for_live_apply": False,
        "homeassistant_official_reconfigure": {
            "pre_change_entry_fingerprint": ENTRY,
            "pre_change_storage_sha256": STORAGE,
        },
    }


def _build(tmp_path: Path, **kwargs: object) -> dict[str, object]:
    handoff, stage = _paths(tmp_path)
    return build_broker_identity_preactivation_gate(
        handoff,
        stage,
        expected_retained_topic=TOPIC,
        expected_target_fingerprint=TARGET,
        expected_entry_fingerprint=ENTRY,
        expected_storage_sha256=STORAGE,
        runner=FakeRunner(),
        handoff_verifier=_verified,
        audit_builder=kwargs.get("audit_builder", lambda *_a, **_k: _audit()),
        target_builder=kwargs.get("target_builder", lambda *_a, **_k: _target()),
    )


def test_ready_but_not_authorized(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["preconditions_ready"] is True
    assert report["apply_enabled"] is False
    assert report["operator_action_authorized"] is False
    assert report["ready_for_live_activation"] is False
    assert report["current_services_modified"] is False


def test_rejects_live_config_drift(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityActivationCheckError,
        match="live Broker config binding drifted",
    ):
        _build(tmp_path, audit_builder=lambda *_a, **_k: _audit("b" * 64))


def test_rejects_target_drift(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityActivationCheckError,
        match="target binding drifted",
    ):
        _build(tmp_path, target_builder=lambda *_a, **_k: _target("0" * 16))


def test_rejects_missing_anonymous_gate(tmp_path: Path) -> None:
    with pytest.raises(
        BrokerIdentityActivationCheckError,
        match="required preactivation state",
    ):
        _build(
            tmp_path,
            audit_builder=lambda *_a, **_k: _audit(
                anonymous_access_still_enabled=False
            ),
        )
