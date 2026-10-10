from __future__ import annotations

import hmac
import json
import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DOMAIN = "n3w_mqtt_bootstrap"
DEFAULT_METADATA_FILE = "/run/n3w/ha-mqtt-bootstrap.json"
_METADATA_SCHEMA = "gh.n3w.t1-clean-homeassistant-mqtt-bootstrap/1"
_LOGGER = logging.getLogger(__name__)


class BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BootstrapSettings:
    broker: str
    port: int
    protocol: str
    username: str
    client_id: str
    generation: int
    password_file: str


def _path_contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _require_private_file(path: Path, label: str) -> None:
    if (
        not path.is_absolute()
        or _path_contains_symlink(path)
        or not path.is_file()
    ):
        raise BootstrapError(f"{label}_path_invalid")
    info = path.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != os.getuid()
    ):
        raise BootstrapError(f"{label}_permissions_invalid")


def _load_settings(path: str | Path) -> BootstrapSettings:
    metadata = Path(path).expanduser()
    _require_private_file(metadata, "metadata")
    try:
        document = json.loads(
            metadata.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BootstrapError("metadata_invalid") from error
    if not isinstance(document, dict):
        raise BootstrapError("metadata_invalid")
    if (
        document.get("schema") != _METADATA_SCHEMA
        or document.get("service") != "homeassistant"
        or document.get("broker") != "127.0.0.1"
        or document.get("port") != 1883
        or document.get("protocol") != "5"
        or document.get("official_config_flow_only") is not True
        or document.get("direct_storage_edit_forbidden") is not True
        or document.get("automatic_apply") is not True
        or document.get("operator_plaintext_copy_required") is not False
    ):
        raise BootstrapError("metadata_contract_invalid")
    username = document.get("username")
    client_id = document.get("client_id")
    generation = document.get("generation")
    password_file = document.get("password_file")
    if (
        not isinstance(username, str)
        or not username
        or not isinstance(client_id, str)
        or not client_id
        or not isinstance(generation, int)
        or not 1 <= generation <= 4294967295
        or not isinstance(password_file, str)
        or not password_file
    ):
        raise BootstrapError("metadata_identity_invalid")
    return BootstrapSettings(
        broker="127.0.0.1",
        port=1883,
        protocol="5",
        username=username,
        client_id=client_id,
        generation=generation,
        password_file=password_file,
    )


def _read_password(raw_path: str) -> str:
    path = Path(raw_path).expanduser()
    _require_private_file(path, "password")
    try:
        value = path.read_text(
            encoding="utf-8"
        ).rstrip("\r\n")
    except (OSError, UnicodeError) as error:
        raise BootstrapError("password_unreadable") from error
    if (
        not value
        or "\n" in value
        or "\r" in value
        or "\x00" in value
    ):
        raise BootstrapError("password_invalid")
    return value


def _flow_input(
    settings: BootstrapSettings,
    password: str,
) -> dict[str, object]:
    return {
        "broker": settings.broker,
        "port": settings.port,
        "protocol": settings.protocol,
        "username": settings.username,
        "password": password,
        "other_settings": {
            "client_id": settings.client_id,
            "set_client_cert": False,
            "set_ca_cert": "off",
            "transport": "tcp",
        },
    }


def _entry_matches(
    data: object,
    settings: BootstrapSettings,
    password: str,
) -> bool:
    if not isinstance(data, dict):
        return False
    expected = {
        "broker": settings.broker,
        "port": settings.port,
        "protocol": settings.protocol,
        "username": settings.username,
        "client_id": settings.client_id,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            return False
    current_password = data.get("password")
    return (
        isinstance(current_password, str)
        and hmac.compare_digest(
            current_password,
            password,
        )
    )


async def _bootstrap(
    hass: Any,
    settings: BootstrapSettings,
    password: str,
) -> bool:
    entries = hass.config_entries.async_entries("mqtt")
    if len(entries) == 1:
        return _entry_matches(
            entries[0].data,
            settings,
            password,
        )
    if entries:
        return False

    first = await hass.config_entries.flow.async_init(
        "mqtt",
        context={"source": "user"},
    )
    if (
        not isinstance(first, dict)
        or first.get("step_id") != "broker"
        or not isinstance(first.get("flow_id"), str)
    ):
        return False

    result = await hass.config_entries.flow.async_configure(
        first["flow_id"],
        _flow_input(settings, password),
    )
    return (
        isinstance(result, dict)
        and result.get("type") == "create_entry"
    )


async def async_setup(
    hass: Any,
    config: dict[str, Any],
) -> bool:
    raw = config.get(DOMAIN)
    if raw is None:
        return True
    if raw is True:
        raw = {}
    if not isinstance(raw, dict):
        _LOGGER.error(
            "N3-W MQTT bootstrap failed class=config_invalid"
        )
        return False
    metadata_file = raw.get(
        "metadata_file",
        DEFAULT_METADATA_FILE,
    )
    if (
        not isinstance(metadata_file, str)
        or not metadata_file
    ):
        _LOGGER.error(
            "N3-W MQTT bootstrap failed class=config_invalid"
        )
        return False

    try:
        settings = _load_settings(metadata_file)
        password = _read_password(
            settings.password_file
        )
        result = await _bootstrap(
            hass,
            settings,
            password,
        )
    except Exception as error:
        _LOGGER.error(
            "N3-W MQTT bootstrap failed class=%s",
            type(error).__name__,
        )
        return False

    if not result:
        _LOGGER.error(
            "N3-W MQTT bootstrap failed class=flow_mismatch"
        )
        return False

    return True
