from __future__ import annotations

from typing import Any

from .const import STORAGE_KEY, STORAGE_VERSION


class HomeAssistantLedgerStore:
    """Small adapter around Home Assistant's versioned Store helper."""

    def __init__(self, hass: Any) -> None:
        from homeassistant.helpers.storage import Store

        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> dict[str, Any] | None:
        return await self._store.async_load()

    async def async_save(self, document: dict[str, Any]) -> None:
        await self._store.async_save(document)
