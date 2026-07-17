from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

import pytest

from greenhouse_manager import node_mqtt_board_lab_native_broker as native
from greenhouse_manager.node_mqtt_board_lab_common import (
    CONFIRMATION,
    ESPHOME_SECRETS_NAME,
    MANIFEST_NAME,
    PASSWORD_NAME,
    SECRETS_NAME,
    NodeMqttBoardLabError,
)


def _executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o700)
    return path


def _runner_for_version(version: str):
    def runner(
        command: list[str] | tuple[str, ...],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = list(command)
        executable = Path(command[0]).name
        if command[1:] == ["-h"]:
            return subprocess.CompletedProcess(command, 0, f"mosquitto version {version}\n", "")
        if executable == "mosquitto_passwd":
            password_path = Path(command[-1])
            rows = []
            for line in password_path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                username, _ = line.split(":", 1)
                rows.append(f"{username}:$7$101$redacted-hash")
            password_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    return runner


def _tools(tmp_path: Path) -> tuple[Path, Path]:
    return (
        _executable(tmp_path / "mosquitto"),
        _executable(tmp_path / "mosquitto_passwd"),
    )


def _create(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    mosquitto, passwd = _tools(tmp_path)
    monkeypatch.setattr(native, "_start_native_broker", lambda *args, **kwargs: None)
    workspace = tmp_path / "native-board-lab"
    report = native.create_native_board_lab(
        workspace,
        confirmation=CONFIRMATION,
        bind_host="127.0.0.1",
        port=18884,
        mosquitto_bin=str(mosquitto),
        mosquitto_passwd_bin=str(passwd),
        runner=_runner_for_version("2.0.22"),
        waiter=lambda host, port, timeout: None,
    )
    assert report["status"] == "node_mqtt_board_lab_native_created"
    assert report["backend"] == "native"
    assert report["docker_required"] is False
    assert report["secret_values_included"] is False
    assert report["production_endpoint_used"] is False
    return workspace


def test_native_plan_requires_non_global_ipv4_and_mosquitto_2_0(tmp_path: Path) -> None:
    mosquitto, passwd = _tools(tmp_path)
    with pytest.raises(NodeMqttBoardLabError, match="globally routable"):
        native.plan_native_board_lab(
            tmp_path / "global",
            bind_host="8.8.8.8",
            mosquitto_bin=str(mosquitto),
            mosquitto_passwd_bin=str(passwd),
            runner=_runner_for_version("2.0.22"),
        )
    with pytest.raises(NodeMqttBoardLabError, match="2.0 release family"):
        native.plan_native_board_lab(
            tmp_path / "old-version",
            mosquitto_bin=str(mosquitto),
            mosquitto_passwd_bin=str(passwd),
            runner=_runner_for_version("1.6.15"),
        )
    report = native.plan_native_board_lab(
        tmp_path / "accepted",
        bind_host="127.0.0.1",
        port=18884,
        mosquitto_bin=str(mosquitto),
        mosquitto_passwd_bin=str(passwd),
        runner=_runner_for_version("2.0.22"),
    )
    assert report["native_mosquitto_version"] == "2.0.22"
    assert report["ready_for_live_apply"] is False
    assert report["ready_for_node_credential_generation"] is False


def test_native_create_writes_private_redacted_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _create(tmp_path, monkeypatch)
    assert workspace.stat().st_mode & 0o777 == 0o700
    for name in (MANIFEST_NAME, SECRETS_NAME, ESPHOME_SECRETS_NAME, PASSWORD_NAME):
        assert (workspace / name).stat().st_mode & 0o777 == 0o600

    secrets_document = json.loads((workspace / SECRETS_NAME).read_text(encoding="utf-8"))
    manifest = json.loads((workspace / MANIFEST_NAME).read_text(encoding="utf-8"))
    encoded_manifest = json.dumps(manifest, sort_keys=True)
    assert secrets_document["candidate_password"] not in encoded_manifest
    assert secrets_document["observer_password"] not in encoded_manifest
    assert manifest["backend"] == "native"
    assert manifest["native_mosquitto_version"] == "2.0.22"

    password_file = (workspace / PASSWORD_NAME).read_text(encoding="utf-8")
    assert secrets_document["candidate_password"] not in password_file
    assert secrets_document["observer_password"] not in password_file
    config = (workspace / "mosquitto.conf").read_text(encoding="utf-8")
    assert "listener 18884 127.0.0.1" in config
    assert "allow_anonymous true" in config
    assert "persistence false" in config
    assert "0.0.0.0" not in config


def test_native_workspace_rejects_whitespace(tmp_path: Path) -> None:
    mosquitto, passwd = _tools(tmp_path)
    with pytest.raises(NodeMqttBoardLabError, match="whitespace"):
        native.plan_native_board_lab(
            tmp_path / "space in path",
            mosquitto_bin=str(mosquitto),
            mosquitto_passwd_bin=str(passwd),
            runner=_runner_for_version("2.0.22"),
        )


def test_native_destroy_requires_workspace_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _create(tmp_path, monkeypatch)
    monkeypatch.setattr(native, "_stop_native_broker", lambda *args, **kwargs: False)
    report = native.destroy_native_board_lab(workspace, runner=_runner_for_version("2.0.22"))
    assert report["status"] == "node_mqtt_board_lab_native_destroyed"
    assert report["workspace_removed"] is True
    assert report["ready_for_live_apply"] is False
    assert report["ready_for_anonymous_closure"] is False
    assert not workspace.exists()


def test_native_cli_and_public_contract_are_registered() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as stream:
        document = tomllib.load(stream)
    assert (
        document["project"]["scripts"]["greenhouse-manager-node-mqtt-board-lab-native"]
        == "greenhouse_manager.node_mqtt_board_lab_native:main"
    )
    source = (
        root / "src/greenhouse_manager/node_mqtt_board_lab_native_broker.py"
    ).read_text(encoding="utf-8")
    assert 'NATIVE_BACKEND = "native"' in source
    assert "CONFIRMATION" in source
    assert '"docker"' not in source
    assert "allow_anonymous true" in source
    assert "ready_for_live_apply" in source
