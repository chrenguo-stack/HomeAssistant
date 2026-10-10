from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace


SOURCE = (
    Path(__file__).resolve().parents[2]
    / "infra/n3w-t1/homeassistant/custom_components"
    / "n3w_mqtt_bootstrap/__init__.py"
)


def _load_module():
    name = "n3w_mqtt_bootstrap_test_module"
    spec = importlib.util.spec_from_file_location(
        name,
        SOURCE,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_private(path: Path, value: str) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o700,
    )
    os.chmod(path.parent, 0o700)
    path.write_text(value, encoding="utf-8")
    os.chmod(path, 0o600)


def _material(tmp_path: Path):
    module = _load_module()
    password = tmp_path / "password"
    metadata = tmp_path / "mqtt-bootstrap.json"
    module._PASSWORD_FILE = str(password)
    _write_private(password, "private-password\n")
    _write_private(
        metadata,
        json.dumps(
            {
                "schema": (
                    "gh.n3w.t1-clean-homeassistant-"
                    "mqtt-bootstrap/1"
                ),
                "service": "homeassistant",
                "broker": "127.0.0.1",
                "port": 1883,
                "protocol": "5",
                "username": "ghs_greenhouse_homeassistant",
                "client_id": "gh-homeassistant-greenhouse",
                "generation": 1,
                "password_file": str(password),
                "official_config_flow_only": True,
                "direct_storage_edit_forbidden": True,
                "automatic_apply": True,
                "operator_plaintext_copy_required": False,
                "runtime_verified": False,
            },
            separators=(",", ":"),
        )
        + "\n",
    )
    return module, metadata


class FakeFlow:
    def __init__(self) -> None:
        self.initialized = []
        self.configured = []

    async def async_init(self, domain, *, context):
        self.initialized.append(
            (domain, context)
        )
        return {
            "type": "form",
            "step_id": "broker",
            "flow_id": "flow-1",
        }

    async def async_configure(
        self,
        flow_id,
        user_input,
    ):
        self.configured.append(
            (flow_id, user_input)
        )
        return {
            "type": "create_entry",
        }


class FakeConfigEntries:
    def __init__(self, entries=None) -> None:
        self._entries = list(entries or [])
        self.flow = FakeFlow()

    def async_entries(self, domain):
        assert domain == "mqtt"
        return list(self._entries)


def _hass(entries=None):
    return SimpleNamespace(
        config_entries=FakeConfigEntries(entries)
    )


def test_first_boot_uses_mqtt_config_flow(
    tmp_path,
) -> None:
    module, metadata = _material(tmp_path)
    hass = _hass()

    result = asyncio.run(
        module.async_setup(
            hass,
            {
                module.DOMAIN: {
                    "metadata_file": str(metadata),
                }
            },
        )
    )

    assert result is True
    assert hass.config_entries.flow.initialized == [
        (
            "mqtt",
            {"source": "user"},
        )
    ]
    assert len(
        hass.config_entries.flow.configured
    ) == 1
    flow_id, user_input = (
        hass.config_entries.flow.configured[0]
    )
    assert flow_id == "flow-1"
    assert user_input["broker"] == "127.0.0.1"
    assert user_input["port"] == 1883
    assert user_input["protocol"] == "5"
    assert user_input["username"] == (
        "ghs_greenhouse_homeassistant"
    )
    assert user_input["password"] == (
        "private-password"
    )
    assert user_input["other_settings"] == {
        "client_id": "gh-homeassistant-greenhouse",
        "set_client_cert": False,
        "set_ca_cert": "off",
        "transport": "tcp",
    }


def test_existing_exact_entry_is_noop(
    tmp_path,
) -> None:
    module, metadata = _material(tmp_path)
    entry = SimpleNamespace(
        data={
            "broker": "127.0.0.1",
            "port": 1883,
            "protocol": "5",
            "username": "ghs_greenhouse_homeassistant",
            "client_id": "gh-homeassistant-greenhouse",
            "password": "private-password",
        }
    )
    hass = _hass([entry])

    result = asyncio.run(
        module.async_setup(
            hass,
            {
                module.DOMAIN: {
                    "metadata_file": str(metadata),
                }
            },
        )
    )

    assert result is True
    assert not hass.config_entries.flow.initialized
    assert not hass.config_entries.flow.configured


def test_existing_mismatch_fails_closed(
    tmp_path,
) -> None:
    module, metadata = _material(tmp_path)
    entry = SimpleNamespace(
        data={
            "broker": "127.0.0.1",
            "port": 1883,
            "protocol": "5",
            "username": "wrong-user",
            "client_id": "gh-homeassistant-greenhouse",
            "password": "private-password",
        }
    )
    hass = _hass([entry])

    result = asyncio.run(
        module.async_setup(
            hass,
            {
                module.DOMAIN: {
                    "metadata_file": str(metadata),
                }
            },
        )
    )

    assert result is False
    assert not hass.config_entries.flow.initialized
    assert not hass.config_entries.flow.configured


def test_multiple_mqtt_entries_fail_closed(
    tmp_path,
) -> None:
    module, metadata = _material(tmp_path)
    entries = [
        SimpleNamespace(data={}),
        SimpleNamespace(data={}),
    ]
    hass = _hass(entries)

    result = asyncio.run(
        module.async_setup(
            hass,
            {
                module.DOMAIN: {
                    "metadata_file": str(metadata),
                }
            },
        )
    )

    assert result is False
    assert not hass.config_entries.flow.initialized


def test_secret_permissions_are_enforced(
    tmp_path,
) -> None:
    module, metadata = _material(tmp_path)
    document = json.loads(
        metadata.read_text(encoding="utf-8")
    )
    password = Path(document["password_file"])
    os.chmod(password, 0o640)

    result = asyncio.run(
        module.async_setup(
            _hass(),
            {
                module.DOMAIN: {
                    "metadata_file": str(metadata),
                }
            },
        )
    )

    assert result is False


def test_metadata_contains_no_password_value(
    tmp_path,
) -> None:
    _module, metadata = _material(tmp_path)
    text = metadata.read_text(encoding="utf-8")

    assert "private-password" not in text
    assert (
        "/config/.storage/core.config_entries"
        not in SOURCE.read_text(encoding="utf-8")
    )


def test_metadata_cannot_redirect_secret_path(
    tmp_path,
) -> None:
    module, metadata = _material(tmp_path)
    document = json.loads(
        metadata.read_text(encoding="utf-8")
    )
    document["password_file"] = str(
        tmp_path / "other-secret"
    )
    metadata.write_text(
        json.dumps(
            document,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(metadata, 0o600)

    result = asyncio.run(
        module.async_setup(
            _hass(),
            {
                module.DOMAIN: {
                    "metadata_file": str(metadata),
                }
            },
        )
    )

    assert result is False
