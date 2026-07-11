from __future__ import annotations

import pytest

from greenhouse_manager.config import Settings


def test_pairing_intake_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_PAIRING_INTAKE_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.pairing_intake_enabled is False
    assert settings.pairing_pending_ttl_s == 120


def test_reads_opt_in_pairing_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    database = f"{tmp_path}/registration.sqlite3"
    monkeypatch.setenv("GH_PAIRING_INTAKE_ENABLED", "true")
    monkeypatch.setenv("GH_PAIRING_DB_PATH", database)
    monkeypatch.setenv("GH_PAIRING_PENDING_TTL_S", "180")

    settings = Settings.from_env()

    assert settings.pairing_intake_enabled is True
    assert settings.pairing_db_path == database
    assert settings.pairing_pending_ttl_s == 180


@pytest.mark.parametrize("ttl", ["29", "601"])
def test_rejects_unsafe_pairing_timeout(monkeypatch: pytest.MonkeyPatch, ttl: str) -> None:
    monkeypatch.setenv("GH_PAIRING_PENDING_TTL_S", ttl)

    with pytest.raises(ValueError, match="between 30 and 600"):
        Settings.from_env()
