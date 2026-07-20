from __future__ import annotations

import json

import pytest

from greenhouse_manager.pairing_lab_cli import main


def test_check_config_is_network_free_and_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("GH_PAIRING_SERVICE_ENABLED", raising=False)
    assert main(["--check-config"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["pairing_service_enabled"] is False
    assert report["network_attempted"] is False
    assert report["listener_count"] == 0


def test_serve_is_a_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("GH_PAIRING_SERVICE_ENABLED", raising=False)
    assert main(["--serve"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["pairing_service_enabled"] is False
    assert report["listener_count"] == 0


def test_invalid_boolean_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GH_PAIRING_SERVICE_ENABLED", "maybe")
    assert main(["--check-config"]) == 2
    assert "configuration" in capsys.readouterr().err
