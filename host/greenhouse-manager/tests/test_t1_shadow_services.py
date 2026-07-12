from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.dynsec_api import DynsecError
from greenhouse_manager.t1_backup import create_backup
from greenhouse_manager.t1_shadow_services import (
    MosquittoRRTransport,
    _copy_client_config,
    build_identity_bundle,
    run_shadow_service_candidate,
)


class RecordingRunner:
    def __init__(self, response: dict[str, Any], *, return_code: int = 0) -> None:
        self.response = response
        self.return_code = return_code
        self.calls: list[tuple[tuple[str, ...], str | None]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        self.calls.append((command, input_text))
        return self.return_code, json.dumps(self.response)


class ServiceShadowDocker:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], str | None]] = []
        self.mounts: list[str] = []
        self.copied_configs: dict[str, str] = {}

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        self.calls.append((command, input_text))
        if command[:3] == ("docker", "inspect", "-f"):
            if command[3].startswith('{"image_id"'):
                name = command[-1]
                return (
                    0,
                    json.dumps(
                        {
                            "image_id": f"sha256:{name}",
                            "image_ref": f"test/{name}:latest",
                        }
                    ),
                )
            return (0, "running\n")
        if command[:4] == ("docker", "exec", "greenhouse-manager", "sh"):
            return (0, "absent\n")
        if command[:3] == ("docker", "cp", "--archive") and ":" in command[3]:
            destination = Path(command[4])
            destination.mkdir(parents=True)
            if "mosquitto:/mosquitto/config" in command[3]:
                (destination / "mosquitto.conf").write_text(
                    "persistence true\nlistener 1883\nallow_anonymous true\n",
                    encoding="utf-8",
                )
            elif "mosquitto:/mosquitto/data" in command[3]:
                (destination / "mosquitto.db").write_bytes(b"retained-state")
            return (0, "")
        if command[:2] == ("docker", "create"):
            self.mounts = [
                item for item in command if item.startswith("type=bind,src=")
            ]
            return (0, "shadow-service-container\n")
        if command[:2] == ("docker", "start"):
            config_mount = next(
                item
                for item in self.mounts
                if item.endswith("dst=/mosquitto/config")
            )
            data_mount = next(
                item
                for item in self.mounts
                if item.endswith("dst=/mosquitto/data")
            )
            config_directory = Path(
                config_mount.removeprefix("type=bind,src=").removesuffix(
                    ",dst=/mosquitto/config"
                )
            )
            data_directory = Path(
                data_mount.removeprefix("type=bind,src=").removesuffix(
                    ",dst=/mosquitto/data"
                )
            )
            self.password_init = (
                config_directory / "dynsec-password-init"
            ).read_text(encoding="utf-8")
            (data_directory / "dynamic-security.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            return (0, "")
        if command[:2] == ("docker", "rm"):
            return (0, "")
        if command[:3] == ("docker", "cp", "--archive"):
            source = Path(command[3])
            self.copied_configs[command[4]] = source.read_text(encoding="utf-8")
            return (0, "")
        if command[:3] == (
            "docker",
            "exec",
            "shadow-service-container",
        ):
            if "mosquitto_sub" in command:
                topic = command[-1]
                if topic == "gh/m2/shadow/services/legacy-probe":
                    return (0, "legacy-ok\n")
                return (0, "retained-payload\n")
            return (0, "")
        if command[:4] == (
            "docker",
            "exec",
            "-i",
            "shadow-service-container",
        ):
            if "mosquitto_rr" in command:
                request = json.loads(input_text or "{}")
                dynsec_command = request["commands"][0]["command"]
                if dynsec_command == "getClient":
                    return (
                        0,
                        json.dumps(
                            {
                                "responses": [
                                    {
                                        "command": "getClient",
                                        "error": "not found",
                                    }
                                ]
                            }
                        ),
                    )
                return (
                    0,
                    json.dumps(
                        {
                            "responses": [
                                {"command": dynsec_command}
                            ]
                        }
                    ),
                )
            return (0, "")
        return (1, "unexpected")


def test_builds_frozen_unique_service_and_node_identities() -> None:
    bundle = build_identity_bundle()

    assert bundle.node_plan.client_id == "gh-n1-a9f2f8"
    assert (
        bundle.service_plans["provisioning"].client_id
        == "gh-provisioning-greenhouse"
    )
    assert (
        bundle.service_plans["manager"].client_id
        == "gh-manager-greenhouse"
    )
    assert (
        bundle.service_plans["homeassistant"].client_id
        == "gh-homeassistant-greenhouse"
    )
    credentials = (
        bundle.node_credentials,
        *bundle.service_credentials.values(),
    )
    assert len({item.username for item in credentials}) == 4
    assert len({item.client_id for item in credentials}) == 4
    for item in credentials:
        assert item.password not in repr(item)


def test_mosquitto_rr_transport_uses_stdin_and_redacts_errors() -> None:
    runner = RecordingRunner(
        {"responses": [{"command": "listClients"}]}
    )
    transport = MosquittoRRTransport(
        runner,
        "candidate",
        "/tmp/admin.conf",
    )

    result = transport.execute(({"command": "listClients"},))

    assert result == ({"command": "listClients"},)
    command, input_text = runner.calls[0]
    assert command[:4] == ("docker", "exec", "-i", "candidate")
    assert command[-1] == "-s"
    assert json.loads(input_text or "{}") == {
        "commands": [{"command": "listClients"}]
    }

    error_runner = RecordingRunner(
        {
            "responses": [
                {
                    "command": "createClient",
                    "error": "secret broker detail",
                }
            ]
        }
    )
    with pytest.raises(DynsecError) as captured:
        MosquittoRRTransport(
            error_runner,
            "candidate",
            "/tmp/admin.conf",
        ).execute(({"command": "createClient"},))

    assert "createClient" in str(captured.value)
    assert "secret broker detail" not in str(captured.value)


def test_client_config_secret_stays_out_of_argv_and_host_file_is_removed(
    tmp_path: Path,
) -> None:
    runner = ServiceShadowDocker()
    config_path = _copy_client_config(
        runner,
        "shadow-service-container",
        tmp_path,
        label="manager",
        username="ghs_greenhouse_manager",
        password="candidate-secret",
        client_id="gh-manager-greenhouse",
    )

    assert config_path == "/tmp/manager.conf"
    assert not (tmp_path / "manager.conf").exists()
    command_text = "\n".join(
        " ".join(command) for command, _input in runner.calls
    )
    assert "candidate-secret" not in command_text
    copied = runner.copied_configs[
        "shadow-service-container:/tmp/manager.conf"
    ]
    assert "-P candidate-secret" in copied
    assert "-i gh-manager-greenhouse" in copied


def test_service_candidate_is_network_none_and_invokes_matrix(
    tmp_path: Path,
) -> None:
    docker = ServiceShadowDocker()
    output = tmp_path / "private"
    output.mkdir(mode=0o700)
    archive = create_backup(
        output,
        runner=docker,
        now=datetime(2026, 7, 12, 2, 0, tzinfo=UTC),
    )
    password = "test-shadow-service-password-32-chars"
    matrix_calls: list[tuple[str, str, str]] = []

    def matrix_executor(
        _runner: Any,
        container_id: str,
        _staging: Path,
        admin_config_path: str,
        system_id: str,
        node_id: str,
    ) -> dict[str, bool]:
        matrix_calls.append((container_id, system_id, node_id))
        assert admin_config_path == "/tmp/gh-m2-admin.conf"
        return {
            "service_identity_matrix": True,
            "client_id_binding": True,
            "provisioning_control_only": True,
            "transaction_rollback": True,
            "legacy_anonymous_after_rollback": True,
        }

    result = run_shadow_service_candidate(
        archive,
        expected_retained_topic=(
            "gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry"
        ),
        runner=docker,
        password_factory=lambda: password,
        name_factory=lambda: "gh-m2-shadow-services-test",
        matrix_executor=matrix_executor,
    )

    assert result["schema"] == "gh.m2.t1-shadow-service-candidate/1"
    assert result["network"] == "none"
    assert result["node_id"] == "gh-n1-a9f2f8"
    assert result["service_identity_matrix"] is True
    assert result["current_services_modified"] is False
    assert matrix_calls == [
        (
            "shadow-service-container",
            "greenhouse",
            "gh-n1-a9f2f8",
        )
    ]
    command_text = "\n".join(
        " ".join(command) for command, _input in docker.calls
    )
    assert password not in command_text
    assert docker.password_init == password + "\n"
    assert any(
        command[:4]
        == ("docker", "create", "--network", "none")
        for command, _input in docker.calls
    )
    assert any(
        command[:3] == ("docker", "rm", "-f")
        for command, _input in docker.calls
    )
