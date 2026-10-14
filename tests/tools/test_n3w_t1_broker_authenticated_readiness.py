from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_broker_authenticated_readiness.py"


def load_tool():
    name = "n3w_t1_broker_authenticated_readiness"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def metadata() -> dict[str, object]:
    return {
        "broker": "127.0.0.1",
        "port": 1883,
        "protocol": "5",
        "username": "ghs_greenhouse_homeassistant",
        "client_id": "gh-homeassistant-greenhouse",
        "password_file": "/run/secrets/gh_homeassistant_mqtt_password",
    }


def test_connect_packet_is_mqtt_v5_and_contains_no_plain_log_side_channel() -> None:
    tool = load_tool()
    packet = tool._connect_packet(
        "gh-homeassistant-greenhouse",
        "ghs_greenhouse_homeassistant",
        "secret-value",
    )

    assert packet[0] == 0x10
    assert b"MQTT" in packet
    assert b"gh-homeassistant-greenhouse" in packet
    assert b"ghs_greenhouse_homeassistant" in packet
    assert b"secret-value" in packet


def test_metadata_requires_exact_loopback_mqtt_v5_contract(tmp_path: Path) -> None:
    tool = load_tool()
    path = tmp_path / "mqtt-bootstrap.json"
    path.write_text(json.dumps(metadata()), encoding="utf-8")

    result = tool._metadata(path)

    assert result["broker"] == "127.0.0.1"
    assert result["port"] == 1883
    assert result["protocol"] == "5"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("broker", "0.0.0.0"),
        ("port", 8883),
        ("protocol", "3.1.1"),
        ("password_file", "/tmp/password"),
    ],
)
def test_metadata_rejects_endpoint_drift(
    tmp_path: Path,
    key: str,
    value: object,
) -> None:
    tool = load_tool()
    document = metadata()
    document[key] = value
    path = tmp_path / "mqtt-bootstrap.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(tool.ReadinessError, match="metadata_endpoint_invalid"):
        tool._metadata(path)


def test_private_password_requires_mode_0600(tmp_path: Path) -> None:
    tool = load_tool()
    path = tmp_path / "password"
    path.write_text("secret-value\n", encoding="utf-8")
    path.chmod(0o600)

    assert tool._private_password(path) == "secret-value"

    path.chmod(0o640)
    with pytest.raises(tool.ReadinessError, match="password_file_mode_invalid"):
        tool._private_password(path)


def test_wait_retries_and_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tool = load_tool()
    metadata_file = tmp_path / "mqtt-bootstrap.json"
    metadata_file.write_text(json.dumps(metadata()), encoding="utf-8")
    password_file = tmp_path / "password"
    password_file.write_text("secret-value\n", encoding="utf-8")
    password_file.chmod(0o600)
    attempts = {"count": 0}

    def fake_probe(**kwargs: object) -> None:
        attempts["count"] += 1
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 1883
        assert kwargs["username"] == "ghs_greenhouse_homeassistant"
        assert kwargs["password"] == "secret-value"
        if attempts["count"] == 1:
            raise OSError("not ready")

    monkeypatch.setattr(tool, "_probe", fake_probe)
    monkeypatch.setattr(tool.time, "sleep", lambda _: None)

    tool.wait_for_authenticated_broker(
        metadata_file=metadata_file,
        password_file=password_file,
        timeout_seconds=1,
        retry_seconds=0.1,
        socket_timeout_seconds=0.1,
    )

    assert attempts["count"] == 2
    assert capsys.readouterr().out == "BROKER_AUTHENTICATED_READINESS=PASS\n"
