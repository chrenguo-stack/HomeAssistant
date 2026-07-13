from __future__ import annotations

import json
from pathlib import Path

from greenhouse_manager.app import main


def test_check_config_reads_private_password_without_network(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    password = tmp_path / "password"
    password.write_text("do-not-print\n", encoding="utf-8")
    password.chmod(0o600)
    monkeypatch.setenv("GH_SYSTEM_ID", "greenhouse")
    monkeypatch.setenv("GH_MQTT_USERNAME", "manager")
    monkeypatch.setenv("GH_MQTT_PASSWORD_FILE", str(password))
    monkeypatch.setenv("GH_MQTT_CLIENT_ID", "manager-client")
    monkeypatch.delenv("GH_MQTT_PASSWORD", raising=False)

    assert main(["--check-config"]) == 0

    output = capsys.readouterr().out
    report = json.loads(output)
    assert report == {
        "configuration_valid": True,
        "inline_password_used": False,
        "mqtt_authentication_configured": True,
        "network_attempted": False,
        "password_file_used": True,
        "secret_values_included": False,
    }
    assert "do-not-print" not in output
