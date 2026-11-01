from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

DOMAIN = "c06b2c_probe"
GREENHOUSE_HISTORY_DOMAIN = "greenhouse_history"
STATE_PATH = Path("/config/c06b2c-probe-state.json")
SAMPLE_HOUR = "2026-08-03T04:00:00.000Z"
EXPECTED_UNIQUE_IDS = (
    "node-0001_air_temperature_c",
    "node-0001_air_humidity_pct",
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({})},
    extra=vol.ALLOW_EXTRA,
)


def _write_snapshot(snapshot: dict[str, Any]) -> None:
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    temporary.replace(STATE_PATH)


def _timestamp_text(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        parsed = datetime.fromtimestamp(float(value), tz=UTC)
    elif isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        parsed = value.astimezone(UTC)
    else:
        return None
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _entity_snapshot(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    registry = er.async_get(hass)
    by_unique_id: dict[str, dict[str, Any]] = {}
    for entry in registry.entities.values():
        if entry.platform != "mqtt" or entry.unique_id not in EXPECTED_UNIQUE_IDS:
            continue
        state = hass.states.get(entry.entity_id)
        attributes = {} if state is None else state.attributes
        by_unique_id[str(entry.unique_id)] = {
            "entity_id": entry.entity_id,
            "platform": entry.platform,
            "disabled": entry.disabled_by is not None,
            "unit_of_measurement": attributes.get("unit_of_measurement"),
            "state_class": attributes.get("state_class"),
            "state": None if state is None else state.state,
        }
    return by_unique_id


def _runtime_and_ledger_snapshot(hass: HomeAssistant) -> dict[str, Any]:
    result: dict[str, Any] = {
        "runtime_loaded": False,
        "runtime_enabled": False,
        "mqtt_bridge_active": False,
        "recorder_write_active": False,
        "ledger_entries": {},
    }
    entries = hass.data.get(GREENHOUSE_HISTORY_DOMAIN)
    if not isinstance(entries, dict):
        return result
    for state in entries.values():
        if not isinstance(state, dict) or state.get("system_id") != "greenhouse":
            continue
        result["runtime_loaded"] = True
        result["runtime_enabled"] = bool(state.get("runtime_enabled"))
        result["mqtt_bridge_active"] = bool(state.get("mqtt_bridge_active"))
        result["recorder_write_active"] = bool(state.get("recorder_write_active"))
        ledger = state.get("ledger")
        if ledger is None:
            return result
        snapshot = ledger.snapshot()
        result["ledger_entries"] = {
            key: {
                "state": entry.state,
                "revision": entry.revision,
                "projection_hash": entry.projection_hash,
                "verified_at": entry.verified_at,
                "reconcile_attempts": entry.reconcile_attempts,
                "last_error_code": entry.last_error_code,
                "resolved_series": [
                    {
                        "measurement_key": item.measurement_key,
                        "entity_unique_id": item.entity_unique_id,
                        "entity_id": item.entity_id,
                        "unit_of_measurement": item.unit_of_measurement,
                        "mean": item.mean,
                        "minimum": item.minimum,
                        "maximum": item.maximum,
                    }
                    for item in entry.resolved_series
                ],
            }
            for key, entry in snapshot.items()
        }
        return result
    return result


async def _statistics_snapshot(
    hass: HomeAssistant,
    entity_ids: tuple[str, ...],
) -> tuple[dict[str, Any], str | None]:
    if not entity_ids:
        return {}, None
    try:
        from homeassistant.components.recorder.statistics import (
            statistics_during_period,
        )
        from homeassistant.components.recorder.util import get_instance

        start = datetime.fromisoformat(SAMPLE_HOUR.replace("Z", "+00:00"))
        rows_by_id = await get_instance(hass).async_add_executor_job(
            statistics_during_period,
            hass,
            start,
            start + timedelta(hours=1),
            set(entity_ids),
            "hour",
            None,
            {"mean", "min", "max"},
        )
        result: dict[str, Any] = {}
        for entity_id in entity_ids:
            exact = [
                row
                for row in rows_by_id.get(entity_id, ())
                if _timestamp_text(row.get("start"))
                == SAMPLE_HOUR.replace(".000Z", "Z")
            ]
            if len(exact) != 1:
                continue
            row = exact[0]
            state = hass.states.get(entity_id)
            result[entity_id] = {
                "start": SAMPLE_HOUR,
                "unit_of_measurement": (
                    None
                    if state is None
                    else state.attributes.get("unit_of_measurement")
                ),
                "mean": row.get("mean"),
                "min": row.get("min"),
                "max": row.get("max"),
            }
        return result, None
    except Exception as exc:  # noqa: BLE001 - probe reports, never mutates
        return {}, type(exc).__name__


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    boot_token = uuid.uuid4().hex
    stop = asyncio.Event()
    write_lock = asyncio.Lock()

    async def collect() -> None:
        entities = _entity_snapshot(hass)
        runtime = _runtime_and_ledger_snapshot(hass)
        entity_ids = tuple(
            str(item["entity_id"])
            for item in entities.values()
            if isinstance(item.get("entity_id"), str)
        )
        statistics, statistics_error = await _statistics_snapshot(hass, entity_ids)
        document = {
            "schema": "gh.c06b2c.homeassistant-probe/1",
            "boot_token": boot_token,
            "observed_at": datetime.now(UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "ready": True,
            "expected_unique_ids": list(EXPECTED_UNIQUE_IDS),
            "entities": entities,
            "statistics": statistics,
            "statistics_error": statistics_error,
            **runtime,
        }
        async with write_lock:
            await hass.async_add_executor_job(_write_snapshot, document)

    async def monitor() -> None:
        while not stop.is_set():
            await collect()
            try:
                await asyncio.wait_for(stop.wait(), timeout=1.0)
            except TimeoutError:
                continue

    await collect()
    task = hass.async_create_background_task(monitor(), "c06b2c-recorder-probe")

    @callback
    def on_stop(_event: Event[Any]) -> None:
        stop.set()
        task.cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_stop)
    return True
