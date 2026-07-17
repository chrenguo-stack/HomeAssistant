from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import pytest

from greenhouse_manager import node_mqtt_board_lab_native as native_cli
from greenhouse_manager.node_mqtt_board_lab_common import NodeMqttBoardLabError


def test_private_mosquitto_cli_is_registered() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as stream:
        document = tomllib.load(stream)
    assert (
        document["project"]["scripts"]["greenhouse-manager-node-mqtt-private-mosquitto"]
        == "greenhouse_manager.node_mqtt_private_mosquitto:main"
    )


def test_native_board_lab_accepts_private_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        native_cli,
        "load_private_mosquitto_manifest",
        lambda path: ("/private/bin/mosquitto", "/private/bin/mosquitto_passwd", {}),
    )
    args = argparse.Namespace(
        private_mosquitto_manifest=Path("manifest.json"),
        mosquitto_bin="mosquitto",
        mosquitto_passwd_bin="mosquitto_passwd",
    )
    assert native_cli._resolve_native_tools(args) == (
        "/private/bin/mosquitto",
        "/private/bin/mosquitto_passwd",
    )


def test_native_board_lab_rejects_manifest_and_explicit_paths() -> None:
    args = argparse.Namespace(
        private_mosquitto_manifest=Path("manifest.json"),
        mosquitto_bin="/other/mosquitto",
        mosquitto_passwd_bin="mosquitto_passwd",
    )
    with pytest.raises(NodeMqttBoardLabError, match="cannot be combined"):
        native_cli._resolve_native_tools(args)
