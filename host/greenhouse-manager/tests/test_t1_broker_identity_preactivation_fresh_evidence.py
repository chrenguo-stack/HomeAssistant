from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager import t1_broker_identity_preactivation_fresh_evidence as module

SYSTEM_ID = "greenhouse"
NODE_ID = "gh-n1-a9f2f8"
CANONICAL_TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry"
AVAILABILITY_TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/availability"
DISCOVERY_TOPIC = f"homeassistant/device/{NODE_ID}/config"
REPOSITORY_SHA = "a" * 40


class FakeRunner:
    def __init__(
        self,
        *,
        anonymous: bool = True,
        dynsec_configured: bool = False,
        topology_ready: bool = True,
    ) -> None:
        self.anonymous = anonymous
        self.dynsec_configured = dynsec_configured
        self.topology_ready = topology_ready
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command[:4] == ("docker", "exec", "mosquitto", "sh"):
            return self._mosquitto_shell(command[-1])
        if command[:3] == ("docker", "exec", "homeassistant"):
            return 0, json.dumps(
                {
                    "dns_resolved": self.topology_ready,
                    "tcp_connectable": self.topology_ready,
                    "address_count": 1 if self.topology_ready else 0,
                }
            )
        return 1, f"unexpected command: {command!r}"

    def _mosquitto_shell(self, script: str) -> tuple[int, str]:
        if "cat /mosquitto/config/mosquitto.conf" in script:
            anonymous = "true" if self.anonymous else "false"
            plugin = (
                "plugin /usr/lib/mosquitto_dynamic_security.so\n"
                if self.dynsec_configured
                else ""
            )
            return 0, (
                f"listener 1883\nallow_anonymous {anonymous}\n"
                f"{plugin}persistence true\n"
            )
        if "mosquitto_dynamic_security.so" in script:
            return 0, "available\n"
        if "dynamic-security.json" in script:
            return 0, "present\n" if self.dynsec_configured else "absent\n"
        return 1, "unexpected mosquitto shell command"


def _documents(password: Path) -> dict[str, dict[str, object]]:
    manager = {
        "Config": {
            "Env": [
                "GH_MQTT_USERNAME=manager-user",
                "GH_MQTT_CLIENT_ID=manager-client",
                "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password",
            ]
        },
        "Mounts": [
            {
                "Destination": "/run/secrets/gh_manager_mqtt_password",
                "RW": False,
                "Source": str(password),
            }
        ],
        "HostConfig": {"NetworkMode": "bridge"},
        "NetworkSettings": {
            "Networks": {"stack": {"Aliases": ["greenhouse-manager"]}}
        },
    }
    mosquitto = {
        "HostConfig": {"NetworkMode": "bridge"},
        "NetworkSettings": {
            "Networks": {"stack": {"Aliases": ["mosquitto"]}}
        },
    }
    homeassistant = {
        "HostConfig": {"NetworkMode": "host"},
        "NetworkSettings": {"Networks": {}},
    }
    return {
        "greenhouse-manager": manager,
        "mosquitto": mosquitto,
        "homeassistant": homeassistant,
    }


def _patch_runtime(
    monkeypatch: pytest.MonkeyPatch,
    password: Path,
) -> None:
    documents = _documents(password)
    snapshot = {
        "greenhouse-manager": ("manager-id", "manager-image", "start", 0, "running"),
        "mosquitto": ("broker-id", "broker-image", "start", 0, "running"),
        "homeassistant": ("ha-id", "ha-image", "start", 0, "running"),
    }
    monkeypatch.setattr(module, "_snapshot", lambda _runner: snapshot)
    monkeypatch.setattr(
        module,
        "_inspect",
        lambda _runner, name: documents[name],
    )
    monkeypatch.setattr(
        module,
        "_validate_manager_identity",
        lambda *_args, **_kwargs: 123,
    )
    monkeypatch.setattr(
        module,
        "_stable_socket",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        module,
        "_validate_retained",
        lambda *_args, **_kwargs: None,
    )

    def retained(
        _runner: object,
        topic: str,
        *,
        timeout_s: float,
    ) -> dict[str, object]:
        assert timeout_s > 0
        if topic == CANONICAL_TOPIC:
            return {"node_id": NODE_ID, "seq": 1}
        if topic == AVAILABILITY_TOPIC:
            return {"node_id": NODE_ID, "state": "online"}
        if topic == DISCOVERY_TOPIC:
            return {"device": {"identifiers": [NODE_ID]}}
        raise AssertionError(topic)

    monkeypatch.setattr(module, "_retained", retained)


def _build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    anonymous: bool = True,
    dynsec_configured: bool = False,
    topology_ready: bool = True,
) -> tuple[dict[str, object], FakeRunner]:
    password = tmp_path / "password"
    password.write_text("secret", encoding="utf-8")
    password.chmod(0o600)
    _patch_runtime(monkeypatch, password)
    runner = FakeRunner(
        anonymous=anonymous,
        dynsec_configured=dynsec_configured,
        topology_ready=topology_ready,
    )
    report = module.build_broker_preactivation_fresh_evidence(
        tmp_path,
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        discovery_topic=DISCOVERY_TOPIC,
        expected_retained_topic=CANONICAL_TOPIC,
        timeout_s=0.2,
        poll_interval_s=0.001,
        proc_root=tmp_path / "proc",
        runner=runner,
        now=datetime(2026, 7, 16, tzinfo=UTC),
        token_factory=lambda: "test1234",
        repository_sha=REPOSITORY_SHA,
        manager_source_version="0.4.81",
    )
    return report, runner


def test_reconstructs_private_read_only_evidence_without_storage_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, runner = _build(tmp_path, monkeypatch)

    assert report["fresh_evidence_reconstructed"] is True
    assert report["ready_for_broker_preactivation_gate"] is True
    assert report["ready_for_live_activation"] is False
    assert report["homeassistant_storage_read"] is False
    assert report["current_services_modified"] is False
    assert report["authorization_created"] is False
    assert report["production_execution_invoked"] is False
    assert not any(".storage" in " ".join(command) for command in runner.commands)

    output = tmp_path / str(report["evidence_name"])
    assert output.stat().st_mode & 0o777 == 0o700
    assert (output / "evidence.json").stat().st_mode & 0o777 == 0o600
    assert (output / "manifest.json").stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".greenhouse-m2-broker-preactivation-*"))


def test_rejects_anonymous_disabled_without_partial_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(
        module.BrokerPreactivationFreshEvidenceError,
        match="anonymous MQTT",
    ):
        _build(tmp_path, monkeypatch, anonymous=False)
    assert not list(tmp_path.glob("greenhouse-m2-broker-preactivation-*"))


def test_rejects_existing_dynamic_security_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(
        module.BrokerPreactivationFreshEvidenceError,
        match="already configured",
    ):
        _build(tmp_path, monkeypatch, dynsec_configured=True)


def test_rejects_unresolved_homeassistant_topology(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(
        module.BrokerPreactivationFreshEvidenceError,
        match="topology is unresolved",
    ):
        _build(tmp_path, monkeypatch, topology_ready=False)


def test_rejects_invalid_repository_sha(tmp_path: Path) -> None:
    runner = FakeRunner()
    with pytest.raises(ValueError, match="40-character"):
        module.build_broker_preactivation_fresh_evidence(
            tmp_path,
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            discovery_topic=DISCOVERY_TOPIC,
            expected_retained_topic=CANONICAL_TOPIC,
            runner=runner,
            repository_sha="not-a-git-sha",
        )
    assert runner.commands == []
