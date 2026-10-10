from __future__ import annotations

import hmac
import json
import logging
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DOMAIN = "n3w_mqtt_bootstrap"
DEFAULT_METADATA_FILE = "/run/n3w/ha-mqtt-bootstrap.json"
_PASSWORD_FILE = "/run/secrets/gh_homeassistant_mqtt_password"
_METADATA_SCHEMA = "gh.n3w.t1-clean-homeassistant-mqtt-bootstrap/1"
_LOGGER = logging.getLogger(__name__)


class BootstrapError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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
        or password_file != _PASSWORD_FILE
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


def _load_material(
    metadata_file: str,
) -> tuple[BootstrapSettings, str]:
    settings = _load_settings(metadata_file)
    password = _read_password(settings.password_file)
    return settings, password


def _safe_flow_token(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "none"
    return "".join(
        character
        if character.isalnum() or character in ("_", "-")
        else "_"
        for character in value[:80]
    )


def _flow_diagnostic(result: object) -> str:
    if not isinstance(result, dict):
        return "type=non_dict"
    result_type = _safe_flow_token(result.get("type"))
    step_id = _safe_flow_token(result.get("step_id"))
    errors = result.get("errors")
    safe_errors: list[str] = []
    if isinstance(errors, dict):
        for key, value in sorted(errors.items()):
            safe_errors.append(
                f"{_safe_flow_token(key)}={_safe_flow_token(value)}"
            )
    error_text = (
        ",".join(safe_errors)
        if safe_errors
        else "none"
    )
    return (
        f"type={result_type};"
        f"step={step_id};"
        f"errors={error_text}"
    )


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
    if not isinstance(data, Mapping):
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
    if data.get("transport", "tcp") != "tcp":
        return False
    if data.get("certificate") is not None:
        return False
    if data.get("client_cert") is not None:
        return False
    if data.get("client_key") is not None:
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
) -> str:
    entries = hass.config_entries.async_entries("mqtt")
    if len(entries) == 1:
        entry = entries[0]
        if getattr(entry, "disabled_by", None) is not None:
            raise BootstrapError("existing_entry_disabled")
        if _entry_matches(
            entry.data,
            settings,
            password,
        ):
            return "existing_match"
        raise BootstrapError("existing_entry_mismatch")
    if entries:
        raise BootstrapError("multiple_mqtt_entries")

    first = await hass.config_entries.flow.async_init(
        "mqtt",
        context={"source": "user"},
    )
    if (
        not isinstance(first, dict)
        or first.get("step_id") != "broker"
        or not isinstance(first.get("flow_id"), str)
    ):
        raise BootstrapError(
            "flow_init_mismatch;"
            + _flow_diagnostic(first)
        )

    result = await hass.config_entries.flow.async_configure(
        first["flow_id"],
        _flow_input(settings, password),
    )
    if (
        isinstance(result, dict)
        and result.get("type") == "create_entry"
    ):
        return "created"
    raise BootstrapError(
        "flow_submit_mismatch;"
        + _flow_diagnostic(result)
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
        settings, password = await hass.async_add_executor_job(
            _load_material,
            metadata_file,
        )
        outcome = await _bootstrap(
            hass,
            settings,
            password,
        )
    except BootstrapError as error:
        _LOGGER.error(
            "N3-W MQTT bootstrap failed class=%s",
            error.code,
        )
        return False
    except Exception as error:
        _LOGGER.error(
            "N3-W MQTT bootstrap failed class=%s",
            type(error).__name__,
        )
        return False

    _LOGGER.info(
        "N3-W MQTT bootstrap success class=%s",
        outcome,
    )
    return True
