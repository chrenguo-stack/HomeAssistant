from __future__ import annotations

from typing import Any

from .const import DOMAIN, validate_system_id
from .ledger import TargetLedger


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Load the inactive C06-B2A target core for one configured system."""

    from .storage import HomeAssistantLedgerStore

    system_id = validate_system_id(str(entry.data["system_id"]))
    ledger = TargetLedger(HomeAssistantLedgerStore(hass))
    await ledger.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "system_id": system_id,
        "ledger": ledger,
        "mqtt_bridge_active": False,
        "recorder_write_active": False,
    }
    return True


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    entries = hass.data.get(DOMAIN)
    if isinstance(entries, dict):
        entries.pop(entry.entry_id, None)
        if not entries:
            hass.data.pop(DOMAIN, None)
    return True
