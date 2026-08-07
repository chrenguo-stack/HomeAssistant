from __future__ import annotations

from typing import Any

from .const import (
    C06B2_MQTT_QUEUE_CAPACITY,
    CONF_C06B2_RUNTIME_ENABLED,
    DEFAULT_C06B2_RUNTIME_ENABLED,
    DOMAIN,
    validate_system_id,
)
from .ledger import TargetLedger


def _runtime_enabled(entry: Any) -> bool:
    raw = entry.options.get(
        CONF_C06B2_RUNTIME_ENABLED,
        entry.data.get(CONF_C06B2_RUNTIME_ENABLED, DEFAULT_C06B2_RUNTIME_ENABLED),
    )
    if type(raw) is not bool:
        raise ValueError(f"{CONF_C06B2_RUNTIME_ENABLED} must be a boolean")
    return raw


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Load the target ledger and opt-in C06-B2B runtime for one system."""

    from .storage import HomeAssistantLedgerStore

    system_id = validate_system_id(str(entry.data["system_id"]))
    ledger = TargetLedger(
        HomeAssistantLedgerStore(hass),
        configured_system_id=system_id,
    )
    await ledger.async_load()

    runtime = None
    runtime_enabled = _runtime_enabled(entry)
    if runtime_enabled:
        from homeassistant.components import mqtt
        from homeassistant.exceptions import ConfigEntryNotReady

        if not await mqtt.async_wait_for_mqtt_client(hass):
            raise ConfigEntryNotReady("MQTT integration is not available")

        from .runtime import HomeAssistantProjectionRuntime

        runtime = HomeAssistantProjectionRuntime.create(
            hass=hass,
            system_id=system_id,
            ledger=ledger,
            queue_capacity=C06B2_MQTT_QUEUE_CAPACITY,
        )
        await runtime.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "system_id": system_id,
        "ledger": ledger,
        "runtime": runtime,
        "runtime_enabled": runtime_enabled,
        "mqtt_bridge_active": bool(runtime and runtime.active),
        "recorder_write_active": bool(runtime and runtime.active),
    }
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    entries = hass.data.get(DOMAIN)
    if not isinstance(entries, dict):
        return True

    state = entries.get(entry.entry_id)
    if isinstance(state, dict):
        runtime = state.get("runtime")
        if runtime is not None:
            await runtime.async_stop()

    entries.pop(entry.entry_id, None)
    if not entries:
        hass.data.pop(DOMAIN, None)
    return True
