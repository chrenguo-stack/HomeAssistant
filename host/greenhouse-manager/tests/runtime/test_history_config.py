from __future__ import annotations

from pathlib import Path

import pytest

from greenhouse_manager.runtime.config import Settings


def test_history_replay_is_disabled_with_bounded_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GH_HISTORY_REPLAY_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.history_replay_enabled is False
    assert settings.history_db_path.endswith("/manager-state.sqlite3")
    assert settings.history_retention_days == 7
    assert settings.history_max_records_per_page == 256
    assert settings.history_max_payload_bytes == 262_144


def test_reads_opt_in_history_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "manager-state.sqlite3"
    monkeypatch.setenv("GH_HISTORY_REPLAY_ENABLED", "true")
    monkeypatch.setenv("GH_HISTORY_DB_PATH", str(path))
    monkeypatch.setenv("GH_HISTORY_RETENTION_DAYS", "14")
    monkeypatch.setenv("GH_HISTORY_MAX_RECORDS_PER_PAGE", "64")
    monkeypatch.setenv("GH_HISTORY_MAX_PAYLOAD_BYTES", "131072")

    settings = Settings.from_env()

    assert settings.history_replay_enabled is True
    assert settings.history_db_path == str(path)
    assert settings.history_retention_days == 14
    assert settings.history_max_records_per_page == 64
    assert settings.history_max_payload_bytes == 131_072


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("GH_HISTORY_RETENTION_DAYS", "0", "between 1 and 30"),
        ("GH_HISTORY_RETENTION_DAYS", "31", "between 1 and 30"),
        ("GH_HISTORY_MAX_RECORDS_PER_PAGE", "0", "between 1 and 256"),
        ("GH_HISTORY_MAX_RECORDS_PER_PAGE", "257", "between 1 and 256"),
        ("GH_HISTORY_MAX_PAYLOAD_BYTES", "4095", "between 4096 and 1048576"),
        ("GH_HISTORY_MAX_PAYLOAD_BYTES", "1048577", "between 4096 and 1048576"),
    ],
)
def test_rejects_unbounded_history_configuration(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        Settings.from_env()
