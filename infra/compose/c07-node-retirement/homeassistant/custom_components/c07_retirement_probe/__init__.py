from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

DOMAIN = "c07_retirement_probe"
NODE_ID = "gh-n1-a9f2f8"
STATE_PATH = Path("/config/c07-probe-state.json")
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({})},
    extra=vol.ALLOW_EXTRA,
)


def _write_snapshot(snapshot: dict[str, Any]) -> None:
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(STATE_PATH)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    registry = er.async_get(hass)
    current_entities: set[str] = set()
    created_entities: set[str] = set()
    removed_entities: set[str] = set()
    write_lock = asyncio.Lock()

    def snapshot() -> dict[str, Any]:
        return {
            "schema": "gh.c07.homeassistant-retirement-probe/1",
            "ready": True,
            "current_entities": sorted(current_entities),
            "created_entities": sorted(created_entities),
            "removed_entities": sorted(removed_entities),
        }

    async def write_state() -> None:
        async with write_lock:
            document = snapshot()
            await hass.async_add_executor_job(_write_snapshot, document)

    def schedule_write() -> None:
        hass.async_create_task(write_state())

    def matches(entity_id: str) -> bool:
        entry = registry.async_get(entity_id)
        return bool(
            entry is not None
            and entry.platform == "mqtt"
            and entry.unique_id is not None
            and NODE_ID in entry.unique_id
        )

    @callback
    def registry_updated(event: Event[dict[str, Any]]) -> None:
        entity_id = event.data.get("entity_id")
        action = event.data.get("action")
        if not isinstance(entity_id, str):
            return
        if action in {"create", "update"} and matches(entity_id):
            current_entities.add(entity_id)
            created_entities.add(entity_id)
            schedule_write()
            return
        if action == "remove" and entity_id in current_entities:
            current_entities.discard(entity_id)
            removed_entities.add(entity_id)
            schedule_write()

    @callback
    def state_changed(event: Event[dict[str, Any]]) -> None:
        entity_id = event.data.get("entity_id")
        if (
            isinstance(entity_id, str)
            and entity_id in current_entities
            and event.data.get("new_state") is None
        ):
            current_entities.discard(entity_id)
            removed_entities.add(entity_id)
            schedule_write()

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, registry_updated)
    hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed)
    await write_state()
    return True
