from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from greenhouse_manager.t1_broker_identity_activation_authorization import (
    BrokerIdentityActivationAuthorizationError,
    _confirmation,
    build_activation_authorization_request,
    create_activation_authorization,
    verify_activation_authorization,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
TARGET = "12ca17b49af22894"
ENTRY = "9dda2c31088e933e"
STORAGE = "e" * 64
NOW = datetime(2026, 7, 12, 8, 0, tzinfo=UTC)


class FakeRunner:
    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        raise AssertionError((command, input_text))


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    handoff = tmp_path / "greenhouse-broker-identity-handoff-test"
    handoff.mkdir(mode=0o700)
    stage = tmp_path / "stage"
    stage.mkdir(mode=0o700)
    output = tmp_path / "authorization"
    _write(
        handoff / "manifest.json",
        json.dumps(
            {
                "schema": (
                    "gh.m2.t1-broker-identity-activation-handoff/1"
                )
            }
        ),
    )
    _write(
        handoff / "activation-plan.json",
        json.dumps(
            {
                "schema": (
                    "gh.m2.t1-broker-identity-activation-plan/1"
                )
            }
        ),
    )
    _write(stage / "stage-manifest.json", "{}\n")
    return handoff, stage, output


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


def _gate(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-broker-identity-preactivation-gate/1",
        "read_only": True,
        "preconditions_ready": True,
        "checks": {
            "handoff_verified": True,
            "fresh_rollback_verified": True,
        },
        "target_kind": "loopback",
        "target_fingerprint": TARGET,
        "entry_fingerprint": ENTRY,
        "storage_sha256": STORAGE,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
    }


def _request(handoff: Path, stage: Path) -> dict[str, object]:
    return build_activation_authorization_request(
        handoff,
        stage,
        expected_retained_topic=TOPIC,
        expected_target_fingerprint=TARGET,
        expected_entry_fingerprint=ENTRY,
        expected_storage_sha256=STORAGE,
        runner=FakeRunner(),
        handoff_verifier=_verified,
        preactivation_builder=_gate,
    )


def _authorize(
    handoff: Path,
    stage: Path,
    output: Path,
    *,
    confirmation: str | None = None,
    now: datetime = NOW,
) -> dict[str, object]:
    return create_activation_authorization(
        handoff,
        stage,
        output,
        expected_retained_topic=TOPIC,
        expected_target_fingerprint=TARGET,
        expected_entry_fingerprint=ENTRY,
        expected_storage_sha256=STORAGE,
        confirmation=confirmation or _confirmation(handoff),
        runner=FakeRunner(),
        now=now,
        token_factory=lambda: "test_authorization_token_12345678",
        handoff_verifier=_verified,
        preactivation_builder=_gate,
    )


def test_request_is_read_only_and_not_authorized(
    tmp_path: Path,
) -> None:
    handoff, stage, _output = _paths(tmp_path)

    report = _request(handoff, stage)

    assert report["schema"] == (
        "gh.m2.t1-broker-identity-activation-authorization-request/1"
    )
    assert report["preconditions_ready"] is True
    assert report["required_confirmation"] == _confirmation(handoff)
    assert report["operator_action_authorized"] is False
    assert report["apply_enabled"] is False
    assert report["ready_for_live_activation"] is False
    assert report["current_services_modified"] is False
    assert report["preserve_anonymous"] is True


def test_wrong_confirmation_creates_no_authorization(
    tmp_path: Path,
) -> None:
    handoff, stage, output = _paths(tmp_path)

    with pytest.raises(
        BrokerIdentityActivationAuthorizationError,
        match="confirmation",
    ):
        _authorize(
            handoff,
            stage,
            output,
            confirmation="wrong",
        )

    assert not output.exists()


def test_authorization_is_private_short_lived_and_still_non_executable(
    tmp_path: Path,
) -> None:
    handoff, stage, output = _paths(tmp_path)

    report = _authorize(handoff, stage, output)

    path = Path(str(report["authorization_file"]))
    document = json.loads(path.read_text(encoding="utf-8"))
    assert output.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert document["single_use"] is True
    assert document["consumed"] is False
    assert document["operator_action_authorized"] is True
    assert document["apply_enabled"] is False
    assert document["ready_for_live_activation"] is False
    assert document["current_services_modified"] is False
    assert document["preserve_anonymous"] is True
    assert document["anonymous_closure_enabled"] is False
    assert document["authorization_token"] not in json.dumps(report)


def test_verify_binds_authorization_to_all_live_fingerprints(
    tmp_path: Path,
) -> None:
    handoff, stage, output = _paths(tmp_path)
    report = _authorize(handoff, stage, output)

    verified = verify_activation_authorization(
        str(report["authorization_file"]),
        handoff,
        stage,
        expected_retained_topic=TOPIC,
        expected_target_fingerprint=TARGET,
        expected_entry_fingerprint=ENTRY,
        expected_storage_sha256=STORAGE,
        now=NOW + timedelta(minutes=1),
    )

    assert verified["valid_now"] is True
    assert verified["single_use"] is True
    assert verified["consumed"] is False
    assert verified["operator_action_authorized"] is True
    assert verified["apply_enabled"] is False
    assert verified["ready_for_live_activation"] is False


def test_expired_authorization_is_rejected(tmp_path: Path) -> None:
    handoff, stage, output = _paths(tmp_path)
    report = _authorize(handoff, stage, output)

    with pytest.raises(
        BrokerIdentityActivationAuthorizationError,
        match="not currently valid",
    ):
        verify_activation_authorization(
            str(report["authorization_file"]),
            handoff,
            stage,
            expected_retained_topic=TOPIC,
            expected_target_fingerprint=TARGET,
            expected_entry_fingerprint=ENTRY,
            expected_storage_sha256=STORAGE,
            now=NOW + timedelta(minutes=16),
        )


def test_tampered_binding_is_rejected(tmp_path: Path) -> None:
    handoff, stage, output = _paths(tmp_path)
    report = _authorize(handoff, stage, output)
    path = Path(str(report["authorization_file"]))
    document = json.loads(path.read_text(encoding="utf-8"))
    document["target_fingerprint"] = "0" * 16
    _write(path, json.dumps(document))

    with pytest.raises(
        BrokerIdentityActivationAuthorizationError,
        match="target_fingerprint",
    ):
        verify_activation_authorization(
            path,
            handoff,
            stage,
            expected_retained_topic=TOPIC,
            expected_target_fingerprint=TARGET,
            expected_entry_fingerprint=ENTRY,
            expected_storage_sha256=STORAGE,
            now=NOW + timedelta(minutes=1),
        )


def test_failed_preactivation_cannot_produce_request(
    tmp_path: Path,
) -> None:
    handoff, stage, _output = _paths(tmp_path)

    def blocked(*_args: object, **_kwargs: object) -> dict[str, object]:
        report = _gate()
        report["preconditions_ready"] = False
        return report

    with pytest.raises(
        BrokerIdentityActivationAuthorizationError,
        match="preconditions_ready",
    ):
        build_activation_authorization_request(
            handoff,
            stage,
            expected_retained_topic=TOPIC,
            expected_target_fingerprint=TARGET,
            expected_entry_fingerprint=ENTRY,
            expected_storage_sha256=STORAGE,
            runner=FakeRunner(),
            handoff_verifier=_verified,
            preactivation_builder=blocked,
        )
