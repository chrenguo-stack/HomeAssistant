from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.dynsec_api import DynsecError
from greenhouse_manager.t1_broker_identity_production_broker_driver import (
    BrokerIdentityProductionBrokerDriverError,
    ClientConfig,
    LiveProductionBrokerDriver,
    _client_config,
)
from greenhouse_manager.t1_shadow import (
    PLUGIN_CONFIG_LINE,
    PLUGIN_LINE,
    PLUGIN_PASSWORD_INIT_LINE,
)

TOPIC = "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
CONTAINER_ID = "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
MANIFEST_SHA = "c" * 64


class FakeRunner:
    def __init__(self, inspect_document: dict[str, Any]) -> None:
        self.inspect_document = inspect_document
        self.calls: list[tuple[str, ...]] = []
        self.restart_code = 0
        self.restart_output = "mosquitto\n"

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        del input_text
        self.calls.append(command)
        if command == ("docker", "inspect", "mosquitto"):
            return 0, json.dumps([self.inspect_document])
        if command == ("docker", "restart", "mosquitto"):
            return self.restart_code, self.restart_output
        return 2, "unexpected command"


class FakeSession:
    def __init__(
        self,
        config: ClientConfig | None,
        *,
        behavior: dict[str, object],
        calls: list[tuple[str, str | None]],
    ) -> None:
        self.config = config
        self.behavior = behavior
        self.calls = calls

    def execute(
        self,
        commands: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    ) -> tuple[dict[str, Any], ...]:
        username = self.config.username if self.config is not None else None
        command = str(commands[0].get("command"))
        self.calls.append((f"execute:{command}", username))
        rejected = self.behavior.get("rejected_users", set())
        if command == "listClients" and username in rejected:
            raise DynsecError("rejected")
        if command == "listClients":
            return ({"command": "listClients"},)
        if command == "deleteClient":
            return ({"command": "deleteClient"},)
        return tuple({"command": item["command"]} for item in commands)

    def retained_message(self, topic: str) -> bytes:
        username = self.config.username if self.config is not None else None
        client_id = self.config.client_id if self.config is not None else None
        self.calls.append((f"retained:{topic}", username))
        rejected_ids = self.behavior.get("rejected_client_ids", set())
        if client_id in rejected_ids:
            raise BrokerIdentityProductionBrokerDriverError("rejected")
        return b"retained-payload"


def _write_private_json(path: Path, value: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    return path


def _fixture(tmp_path: Path) -> dict[str, object]:
    deployment = tmp_path / "deployment"
    config_dir = deployment / "mosquitto/config"
    data_dir = deployment / "mosquitto/data"
    config_dir.mkdir(parents=True, mode=0o700)
    data_dir.mkdir(parents=True, mode=0o700)
    config_file = config_dir / "mosquitto.conf"
    config_file.write_text(
        "allow_anonymous true\n"
        f"{PLUGIN_LINE}\n{PLUGIN_CONFIG_LINE}\n{PLUGIN_PASSWORD_INIT_LINE}\n",
        encoding="utf-8",
    )
    state_file = data_dir / "dynamic-security.json"
    state_file.write_text("{}\n", encoding="utf-8")
    state_file.chmod(0o600)
    inspect_document = {
        "Id": CONTAINER_ID,
        "Image": IMAGE_ID,
        "State": {"Status": "running"},
    }
    manifest = {
        "schema": "gh.m2.t1-broker-identity-runtime-binding-manifest/1",
        "manifest_sha256": MANIFEST_SHA,
        "runtime": {
            "container_id": CONTAINER_ID,
            "image_id": IMAGE_ID,
        },
        "paths": {
            "config_file": str(config_file.resolve()),
            "dynamic_security_state_file": str(state_file.resolve()),
        },
        "baseline_config_sha256": "0" * 64,
    }
    manifest_path = _write_private_json(tmp_path / "runtime-manifest.json", manifest)
    runner = FakeRunner(inspect_document)
    behavior: dict[str, object] = {
        "rejected_users": {"admin", None},
        "rejected_client_ids": {"homeassistant-client-wrong"},
    }
    session_calls: list[tuple[str, str | None]] = []

    def session_factory(config: ClientConfig | None) -> FakeSession:
        return FakeSession(
            config,
            behavior=behavior,
            calls=session_calls,
        )

    driver = LiveProductionBrokerDriver(
        manifest_path,
        runner=runner,
        manifest_verifier=lambda _path: {
            "verified": True,
            "manifest_sha256": MANIFEST_SHA,
        },
        session_factory=session_factory,
        timeout_s=0.2,
        mqtt_timeout_s=0.2,
    )
    return {
        "driver": driver,
        "runner": runner,
        "behavior": behavior,
        "session_calls": session_calls,
        "config_file": config_file,
        "state_file": state_file,
        "inspect": inspect_document,
    }


def _client_text(username: str, client_id: str) -> str:
    return (
        "-h 127.0.0.1\n"
        f"-u {username}\n"
        "-P secret-password\n"
        f"-i {client_id}\n"
        "-V 5\n"
    )


def test_parses_only_supported_private_client_options() -> None:
    config = _client_config(
        _client_text("provisioning", "provisioning-client"),
        "test client",
    )
    assert config == ClientConfig(
        host="127.0.0.1",
        port=1883,
        username="provisioning",
        password="secret-password",
        client_id="provisioning-client",
    )

    with pytest.raises(
        BrokerIdentityProductionBrokerDriverError,
        match="unsupported option",
    ):
        _client_config("--cafile /tmp/unsafe\n", "test client")


def test_restart_uses_only_bound_inspect_and_restart_commands(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["driver"].restart_mosquitto()
    assert fixture["runner"].calls == [
        ("docker", "inspect", "mosquitto"),
        ("docker", "restart", "mosquitto"),
        ("docker", "inspect", "mosquitto"),
    ]


def test_rejects_runtime_identity_drift_before_restart(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["inspect"]["Id"] = "9" * 64

    with pytest.raises(
        BrokerIdentityProductionBrokerDriverError,
        match="runtime identity has drifted",
    ):
        fixture["driver"].restart_mosquitto()
    assert fixture["runner"].calls == [("docker", "inspect", "mosquitto")]


def test_executes_identity_lifecycle_only_through_injected_sessions(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    driver = fixture["driver"]
    bootstrap = _client_text("admin", "bootstrap-client")
    provisioning = _client_text("provisioning", "provisioning-client")

    driver.apply_exact_request(
        ({"command": "setDefaultACLAccess", "acls": []},),
        bootstrap,
    )
    driver.verify_provisioning_identity(provisioning)
    driver.delete_bootstrap_admin(provisioning)
    driver.verify_bootstrap_rejected(bootstrap)

    assert fixture["session_calls"] == [
        ("execute:setDefaultACLAccess", "admin"),
        ("execute:listClients", "provisioning"),
        ("execute:deleteClient", "provisioning"),
        ("execute:listClients", "admin"),
    ]
    assert fixture["runner"].calls == []


def test_postactivation_audit_requires_all_identity_and_anonymous_checks(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    report = fixture["driver"].postactivation_audit(
        expected_retained_topic=TOPIC,
        homeassistant_update={
            "username": "homeassistant",
            "password": "ha-password",
            "required_client_id": "homeassistant-client",
        },
        provisioning_config=_client_text(
            "provisioning",
            "provisioning-client",
        ),
        bootstrap_config=_client_text("admin", "bootstrap-client"),
    )

    assert report["activation_verified"] is True
    assert report["rollback_required"] is False
    assert report["preserve_anonymous"] is True
    assert report["anonymous_closure_enabled"] is False
    assert all(report["checks"].values())
    assert fixture["runner"].calls == [("docker", "inspect", "mosquitto")]


def test_postactivation_failure_requires_rollback(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["behavior"]["rejected_users"] = {"admin", "provisioning", None}

    report = fixture["driver"].postactivation_audit(
        expected_retained_topic=TOPIC,
        homeassistant_update={
            "username": "homeassistant",
            "password": "ha-password",
            "required_client_id": "homeassistant-client",
        },
        provisioning_config=_client_text(
            "provisioning",
            "provisioning-client",
        ),
        bootstrap_config=_client_text("admin", "bootstrap-client"),
    )

    assert report["activation_verified"] is False
    assert report["rollback_required"] is True
    assert report["checks"]["provisioning_control_readable"] is False


def test_waiter_rejects_unbound_state_path(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(
        BrokerIdentityProductionBrokerDriverError,
        match="waiter path is not bound",
    ):
        fixture["driver"].wait_for_dynamic_security_state(
            tmp_path / "other-state.json"
        )
