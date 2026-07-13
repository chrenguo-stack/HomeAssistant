from __future__ import annotations

import hashlib
import json
from pathlib import Path

from greenhouse_manager.t1_broker_identity_postactivation_audit import (
    audit_broker_identity_postactivation,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
CONFIG = (
    "listener 1883\n"
    "allow_anonymous true\n"
    "plugin /usr/lib/mosquitto_dynamic_security.so\n"
    "plugin_opt_config_file /mosquitto/data/dynamic-security.json\n"
)


class FakeRunner:
    def __init__(
        self,
        *,
        bootstrap_rejected: bool = True,
        config: str = CONFIG,
    ) -> None:
        self.bootstrap_rejected = bootstrap_rejected
        self.config = config

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        joined = " ".join(command)
        if command[:3] == ("docker", "inspect", "-f"):
            return 0, json.dumps(
                {
                    "state": "running",
                    "restarts": "0",
                    "image_id": f"sha256:{command[-1]}",
                }
            )
        if "cat /mosquitto/config/mosquitto.conf" in joined:
            return 0, self.config
        if "stat -c '%a' /mosquitto/data/dynamic-security.json" in joined:
            return 0, "600\n"
        if command[:4] == (
            "docker",
            "exec",
            "mosquitto",
            "mosquitto_sub",
        ):
            return 0, '{"temperature":23}\n'
        if command[:5] == (
            "docker",
            "exec",
            "-i",
            "mosquitto",
            "sh",
        ):
            assert input_text is not None
            if "mosquitto_sub" in joined:
                return (
                    (1, "client identifier rejected")
                    if "-wrong" in input_text
                    else (0, '{"temperature":23}\n')
                )
            if "bootstrap-secret" in input_text:
                return (
                    (1, "not authorised")
                    if self.bootstrap_rejected
                    else (0, _list_response())
                )
            return 0, _list_response()
        if command[:4] == (
            "docker",
            "exec",
            "mosquitto",
            "mosquitto_rr",
        ):
            return 1, "not authorised"
        return 1, "unexpected command"


def _list_response() -> str:
    return json.dumps(
        {
            "responses": [
                {
                    "command": "listClients",
                    "data": {"clients": ["gh-homeassistant"]},
                }
            ]
        }
    )


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


def _handoff(tmp_path: Path, baseline: str = "a" * 64) -> Path:
    root = tmp_path / "handoff"
    root.mkdir(mode=0o700)
    _write(
        root / "manifest.json",
        json.dumps(
            {
                "schema": "gh.m2.t1-broker-identity-activation-handoff/1",
                "stage": {"broker_config_sha256": baseline},
            }
        ),
    )
    _write(
        root / "activation-plan.json",
        json.dumps({"schema": "gh.m2.t1-broker-identity-activation-plan/1"}),
    )
    _write(
        root / "material/homeassistant/mqtt-update.json",
        json.dumps(
            {
                "username": "gh-homeassistant-user",
                "password": "homeassistant-secret",
                "required_client_id": "gh-homeassistant-client",
            }
        ),
    )
    _write(
        root / "material/provisioning/mosquitto-client.conf",
        "-h 127.0.0.1\n-u gh-provisioning\n-P provisioning-secret\n-i gh-provisioning-client\n-V 5\n",
    )
    _write(
        root / "material/bootstrap/admin-client.conf",
        "-h 127.0.0.1\n-u admin\n-P bootstrap-secret\n-i gh-m2-bootstrap-admin\n-V 5\n",
    )
    return root


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


def test_verifies_identity_and_anonymous_path(tmp_path: Path) -> None:
    report = audit_broker_identity_postactivation(
        _handoff(tmp_path),
        expected_retained_topic=TOPIC,
        runner=FakeRunner(),
        handoff_verifier=_verified,
    )

    assert report["activation_verified"] is True
    assert report["rollback_required"] is False
    assert report["broker_identity_activated"] is True
    assert report["ready_for_homeassistant_reconfigure_handoff"] is True
    assert report["operator_action_authorized"] is False
    assert all(report["checks"].values())


def test_requires_rollback_if_bootstrap_remains(tmp_path: Path) -> None:
    report = audit_broker_identity_postactivation(
        _handoff(tmp_path),
        expected_retained_topic=TOPIC,
        runner=FakeRunner(bootstrap_rejected=False),
        handoff_verifier=_verified,
    )

    assert report["activation_verified"] is False
    assert report["rollback_required"] is True
    assert report["checks"]["bootstrap_admin_rejected"] is False


def test_requires_config_change(tmp_path: Path) -> None:
    baseline = hashlib.sha256(CONFIG.encode()).hexdigest()
    report = audit_broker_identity_postactivation(
        _handoff(tmp_path, baseline),
        expected_retained_topic=TOPIC,
        runner=FakeRunner(),
        handoff_verifier=_verified,
    )

    assert report["activation_verified"] is False
    assert report["rollback_required"] is True
    assert report["checks"]["broker_config_changed_from_baseline"] is False


def test_report_redacts_secret_material(tmp_path: Path) -> None:
    report = audit_broker_identity_postactivation(
        _handoff(tmp_path),
        expected_retained_topic=TOPIC,
        runner=FakeRunner(),
        handoff_verifier=_verified,
    )
    serialized = json.dumps(report)

    for secret in (
        "homeassistant-secret",
        "provisioning-secret",
        "bootstrap-secret",
        "gh-homeassistant-user",
        "gh-homeassistant-client",
    ):
        assert secret not in serialized


class AnonymousDeniedWithZeroExitRunner(FakeRunner):
    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        if command[:4] == (
            "docker",
            "exec",
            "mosquitto",
            "mosquitto_rr",
        ):
            return 0, "Not authorized\n"
        return super().run(command, input_text=input_text)


def test_accepts_zero_exit_authorization_denial(tmp_path: Path) -> None:
    report = audit_broker_identity_postactivation(
        _handoff(tmp_path),
        expected_retained_topic=TOPIC,
        runner=AnonymousDeniedWithZeroExitRunner(),
        handoff_verifier=_verified,
    )

    assert report["checks"]["anonymous_control_denied"] is True
    assert report["activation_verified"] is True
    assert report["rollback_required"] is False
