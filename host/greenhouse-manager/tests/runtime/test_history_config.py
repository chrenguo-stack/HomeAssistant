from __future__ import annotations

from pathlib import Path

import pytest

from greenhouse_manager.runtime.config import Settings


def test_history_replay_is_disabled_with_bounded_portable_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GH_HISTORY_REPLAY_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.history_replay_enabled is False
    assert settings.history_db_path == (
        "/var/lib/greenhouse-manager/manager/manager-state.sqlite3"
    )
    assert settings.history_retention_days == 7
    assert settings.history_max_future_skew_s == 300
    assert settings.history_max_records_per_page == 256
    assert settings.history_max_payload_bytes == 262_144
    assert settings.history_max_records == 250_000
    assert settings.history_max_db_bytes == 268_435_456
    assert settings.history_queue_capacity == 64
    assert settings.history_max_pages_per_minute == 60
    assert settings.history_prune_interval_s == 300


def test_reads_opt_in_history_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "manager" / "manager-state.sqlite3"
    monkeypatch.setenv("GH_HISTORY_REPLAY_ENABLED", "true")
    monkeypatch.setenv("GH_HISTORY_DB_PATH", str(path))
    monkeypatch.setenv("GH_HISTORY_RETENTION_DAYS", "14")
    monkeypatch.setenv("GH_HISTORY_MAX_FUTURE_SKEW_S", "600")
    monkeypatch.setenv("GH_HISTORY_MAX_RECORDS_PER_PAGE", "64")
    monkeypatch.setenv("GH_HISTORY_MAX_PAYLOAD_BYTES", "131072")
    monkeypatch.setenv("GH_HISTORY_MAX_RECORDS", "100000")
    monkeypatch.setenv("GH_HISTORY_MAX_DB_BYTES", "134217728")
    monkeypatch.setenv("GH_HISTORY_QUEUE_CAPACITY", "32")
    monkeypatch.setenv("GH_HISTORY_MAX_PAGES_PER_MINUTE", "30")
    monkeypatch.setenv("GH_HISTORY_PRUNE_INTERVAL_S", "60")

    settings = Settings.from_env()

    assert settings.history_replay_enabled is True
    assert settings.history_db_path == str(path)
    assert settings.history_retention_days == 14
    assert settings.history_max_future_skew_s == 600
    assert settings.history_max_records_per_page == 64
    assert settings.history_max_payload_bytes == 131_072
    assert settings.history_max_records == 100_000
    assert settings.history_max_db_bytes == 134_217_728
    assert settings.history_queue_capacity == 32
    assert settings.history_max_pages_per_minute == 30
    assert settings.history_prune_interval_s == 60


def test_enabled_history_requires_absolute_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_HISTORY_REPLAY_ENABLED", "true")
    monkeypatch.setenv("GH_HISTORY_DB_PATH", "manager-state.sqlite3")

    with pytest.raises(ValueError, match="must be absolute"):
        Settings.from_env()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("GH_HISTORY_RETENTION_DAYS", "0", "between 1 and 30"),
        ("GH_HISTORY_RETENTION_DAYS", "31", "between 1 and 30"),
        ("GH_HISTORY_MAX_FUTURE_SKEW_S", "-1", "between 0 and 86400"),
        ("GH_HISTORY_MAX_FUTURE_SKEW_S", "86401", "between 0 and 86400"),
        ("GH_HISTORY_MAX_RECORDS_PER_PAGE", "0", "between 1 and 256"),
        ("GH_HISTORY_MAX_RECORDS_PER_PAGE", "257", "between 1 and 256"),
        ("GH_HISTORY_MAX_PAYLOAD_BYTES", "4095", "between 4096 and 1048576"),
        ("GH_HISTORY_MAX_PAYLOAD_BYTES", "1048577", "between 4096 and 1048576"),
        ("GH_HISTORY_MAX_RECORDS", "1023", "between 1024 and 2000000"),
        ("GH_HISTORY_MAX_RECORDS", "2000001", "between 1024 and 2000000"),
        ("GH_HISTORY_MAX_DB_BYTES", "1048575", "between 1048576 and 2147483648"),
        ("GH_HISTORY_MAX_DB_BYTES", "2147483649", "between 1048576 and 2147483648"),
        ("GH_HISTORY_QUEUE_CAPACITY", "0", "between 1 and 1024"),
        ("GH_HISTORY_QUEUE_CAPACITY", "1025", "between 1 and 1024"),
        ("GH_HISTORY_MAX_PAGES_PER_MINUTE", "0", "between 1 and 600"),
        ("GH_HISTORY_MAX_PAGES_PER_MINUTE", "601", "between 1 and 600"),
        ("GH_HISTORY_PRUNE_INTERVAL_S", "29", "between 30 and 86400"),
        ("GH_HISTORY_PRUNE_INTERVAL_S", "86401", "between 30 and 86400"),
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
