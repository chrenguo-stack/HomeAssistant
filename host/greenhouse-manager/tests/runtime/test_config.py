from __future__ import annotations

from pathlib import Path

import pytest

from greenhouse_manager.runtime.config import Settings


def test_pairing_intake_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_PAIRING_INTAKE_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.pairing_intake_enabled is False
    assert settings.pairing_pending_ttl_s == 120


def test_reads_opt_in_pairing_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
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


def test_reads_mqtt_password_from_private_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    password_file = tmp_path / "mqtt-password"
    password_file.write_text("private-password\n", encoding="utf-8")
    password_file.chmod(0o600)
    monkeypatch.setenv("GH_MQTT_USERNAME", "manager-user")
    monkeypatch.setenv("GH_MQTT_PASSWORD_FILE", str(password_file))
    monkeypatch.delenv("GH_MQTT_PASSWORD", raising=False)

    settings = Settings.from_env()

    assert settings.mqtt_username == "manager-user"
    assert settings.mqtt_password == "private-password"


def test_rejects_world_readable_mqtt_password_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    password_file = tmp_path / "mqtt-password"
    password_file.write_text("private-password\n", encoding="utf-8")
    password_file.chmod(0o644)
    monkeypatch.setenv("GH_MQTT_USERNAME", "manager-user")
    monkeypatch.setenv("GH_MQTT_PASSWORD_FILE", str(password_file))
    monkeypatch.delenv("GH_MQTT_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="group or other"):
        Settings.from_env()


def test_rejects_inline_and_file_mqtt_passwords(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    password_file = tmp_path / "mqtt-password"
    password_file.write_text("file-password\n", encoding="utf-8")
    password_file.chmod(0o600)
    monkeypatch.setenv("GH_MQTT_USERNAME", "manager-user")
    monkeypatch.setenv("GH_MQTT_PASSWORD", "inline-password")
    monkeypatch.setenv("GH_MQTT_PASSWORD_FILE", str(password_file))

    with pytest.raises(ValueError, match="mutually exclusive"):
        Settings.from_env()


def test_n3w_runtime_is_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_N3W_RUNTIME_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.n3w_runtime_enabled is False
    assert settings.n3w_path_stability_window_s == 5
    assert settings.n3w_path_minimum_distinct_frames == 2
    assert settings.n3w_path_lease_ttl_s == 30
    assert settings.n3w_path_old_grace_s == 5


def test_reads_explicit_n3w_runtime_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GH_N3W_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("GH_PAIRING_DB_PATH", str(tmp_path / "registration.sqlite3"))
    monkeypatch.setenv("GH_N3W_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))
    monkeypatch.setenv(
        "GH_N3W_RELAY_AUTHORIZATION_DB_PATH",
        str(tmp_path / "relay-authorization.sqlite3"),
    )
    monkeypatch.setenv("GH_N3W_RELAY_KEY_DIR", str(tmp_path / "relay-keys"))
    monkeypatch.setenv("GH_N3W_PATH_STABILITY_WINDOW_S", "1.5")
    monkeypatch.setenv("GH_N3W_PATH_MINIMUM_DISTINCT_FRAMES", "3")
    monkeypatch.setenv("GH_N3W_PATH_LEASE_TTL_S", "45")
    monkeypatch.setenv("GH_N3W_PATH_OLD_GRACE_S", "2.5")

    settings = Settings.from_env()

    assert settings.n3w_runtime_enabled is True
    assert settings.n3w_replay_db_path == str(tmp_path / "replay.sqlite3")
    assert settings.n3w_relay_authorization_db_path == str(
        tmp_path / "relay-authorization.sqlite3"
    )
    assert settings.n3w_relay_key_dir == str(tmp_path / "relay-keys")
    assert settings.n3w_path_stability_window_s == 1.5
    assert settings.n3w_path_minimum_distinct_frames == 3
    assert settings.n3w_path_lease_ttl_s == 45
    assert settings.n3w_path_old_grace_s == 2.5


def test_n3w_enabled_requires_absolute_distinct_state_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="GH_N3W_REPLAY_DB_PATH must be absolute"):
        Settings(
            system_id="dev",
            n3w_runtime_enabled=True,
            pairing_db_path=str(tmp_path / "registration.sqlite3"),
            n3w_replay_db_path="relative.sqlite3",
            n3w_relay_authorization_db_path=str(tmp_path / "authorization.sqlite3"),
            n3w_relay_key_dir=str(tmp_path / "keys"),
        ).validate()

    shared = str(tmp_path / "shared.sqlite3")
    with pytest.raises(ValueError, match="databases must differ"):
        Settings(
            system_id="dev",
            n3w_runtime_enabled=True,
            pairing_db_path=shared,
            n3w_replay_db_path=shared,
            n3w_relay_authorization_db_path=str(tmp_path / "authorization.sqlite3"),
            n3w_relay_key_dir=str(tmp_path / "keys"),
        ).validate()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("n3w_path_stability_window_s", -1, "STABILITY_WINDOW"),
        ("n3w_path_minimum_distinct_frames", 0, "MINIMUM_DISTINCT_FRAMES"),
        ("n3w_path_lease_ttl_s", 0, "LEASE_TTL"),
        ("n3w_path_old_grace_s", -1, "OLD_GRACE"),
    ],
)
def test_rejects_unsafe_n3w_path_policy(
    field: str,
    value: float,
    message: str,
) -> None:
    values = {field: value}
    with pytest.raises(ValueError, match=message):
        Settings(system_id="dev", **values).validate()
