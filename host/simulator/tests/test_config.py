from __future__ import annotations

import pytest

from greenhouse_simulator.config import Settings


def test_pairing_hello_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_SIM_PAIRING_HELLO", raising=False)

    settings = Settings.from_env()

    assert settings.pairing_hello_enabled is False


def test_reads_pairing_hello_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_SIM_PAIRING_HELLO", "true")
    monkeypatch.setenv("GH_HARDWARE_ID", "ghw-c6-98a316a9f2f8")
    monkeypatch.setenv("GH_PAIRING_EPOCH", "3")

    settings = Settings.from_env()

    assert settings.pairing_hello_enabled is True
    assert settings.hardware_id == "ghw-c6-98a316a9f2f8"
    assert settings.pairing_epoch == 3


def test_rejects_invalid_enabled_hardware_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_SIM_PAIRING_HELLO", "true")
    monkeypatch.setenv("GH_HARDWARE_ID", "node-not-hardware")

    with pytest.raises(ValueError, match="GH_HARDWARE_ID"):
        Settings.from_env()
