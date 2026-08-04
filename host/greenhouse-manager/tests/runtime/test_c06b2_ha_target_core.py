from __future__ import annotations

import asyncio
import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from custom_components.greenhouse_history.entity_resolver import EntityDescriptor, EntityResolver
from custom_components.greenhouse_history.ledger import (
    LedgerCorruptionError,
    MemoryLedgerStore,
    ResolvedSeries,
    TargetLedger,
)
from custom_components.greenhouse_history.protocol import ProtocolError
from custom_components.greenhouse_history.protocol import parse_request as parse_ha
from custom_components.greenhouse_history.recorder_adapter import (
    StatisticReadback,
    projection_writes,
    verify_readback,
)

from greenhouse_manager.runtime.c06b2_ha_projection_protocol import (
    ProjectionProtocolError,
    build_projection_request,
    build_projection_result,
    parse_and_bind_projection_result,
    parse_projection_request,
    projection_hash,
    projection_result_topic,
)
from greenhouse_manager.runtime.history_projection_contract import ProjectionBatch

SYSTEM = "sys_001"
NODE = "node_0001"
HOUR = "2026-08-03T12:00:00Z"
KEYS = (
    "air_temperature_c", "air_humidity_pct", "co2_ppm", "illuminance_lx",
    "soil_temperature_c", "soil_moisture_pct", "soil_ec_us_cm", "vpd_kpa",
    "dew_point_c", "absolute_humidity_g_m3", "ppfd_umol_m2_s", "battery_v",
    "battery_pct",
)


def projection(revision: int = 1, mean: float = 20.0, *, node: str = NODE, hour: str = HOUR):
    series = {
        "measurement_key": "air_temperature_c",
        "entity_unique_id": f"{node}_air_temperature_c",
        "name": "空气温度",
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "unit_class_hint": "temperature",
        "state_class": "measurement",
        "mean_type": "arithmetic",
        "has_sum": False,
        "samples": 1,
        "mean": mean,
        "min": mean,
        "max": mean,
    }
    return {
        "schema": "gh.c06-hourly-projection/1",
        "idempotency_key": f"{node}|{hour}|v1",
        "node_id": node,
        "sample_hour": hour,
        "projection_version": 1,
        "revision": revision,
        "algorithm_version": 2,
        "quality_policy": "ok-only/1",
        "source_record_count": 1,
        "source_set_sha256": "a" * 64,
        "eligible_record_count": 1,
        "skipped_time_quality": 0,
        "series": [series],
        "audit": {
            key: {
                "present": int(key == "air_temperature_c"),
                "accepted": int(key == "air_temperature_c"),
                "excluded_quality": 0,
                "invalid_or_null": 0,
                "missing": int(key != "air_temperature_c"),
            }
            for key in KEYS
        },
    }


def manager_request(revision: int = 1, mean: float = 20.0, *, node: str = NODE, hour: str = HOUR):
    payload = projection(revision, mean, node=node, hour=hour)
    return build_projection_request(
        batch=ProjectionBatch(node, hour, 1, revision, projection_hash(payload), payload),
        system_id=SYSTEM,
        request_id=f"request_{node}_{revision:04d}",
        sent_at=datetime(2026, 8, 3, 12, 30, tzinfo=UTC),
    )


def ha_request(*args, **kwargs):
    return parse_ha(manager_request(*args, **kwargs).as_payload(), configured_system_id=SYSTEM)


def resolved(request):
    return tuple(
        ResolvedSeries(
            item["measurement_key"], item["entity_unique_id"],
            f"sensor.renamed_{item['measurement_key']}", item["unit_of_measurement"],
            float(item["mean"]), float(item["min"]), float(item["max"]),
        )
        for item in request.projection["series"]
    )


def test_schema_parity_and_full_rejection() -> None:
    root = Path(__file__).resolve().parents[4]
    manager = (
        root
        / "host/greenhouse-manager/src/greenhouse_manager/schemas"
        / "gh.c06-hourly-projection-1.schema.json"
    )
    ha = (
        root
        / "host/homeassistant/custom_components/greenhouse_history"
        / "gh.c06-hourly-projection-1.schema.json"
    )
    assert manager.read_bytes() == ha.read_bytes()
    assert hashlib.sha256(manager.read_bytes()).digest() == hashlib.sha256(ha.read_bytes()).digest()
    for field, value in (
        ("measurement_key", "unknown"), ("name", "Wrong"),
        ("unit_of_measurement", "°F"), ("device_class", "humidity"),
        ("unit_class_hint", "unitless"), ("mean", 2000.0),
    ):
        doc = manager_request().as_document()
        item = doc["projection"]["series"][0]
        item[field] = value
        if field == "measurement_key":
            item["entity_unique_id"] = f"{NODE}_{value}"
        if field == "mean":
            item["min"] = item["max"] = value
        doc["projection_hash"] = projection_hash(doc["projection"])
        with pytest.raises(ProjectionProtocolError):
            parse_projection_request(doc, expected_system_id=SYSTEM)
        with pytest.raises(ProtocolError):
            parse_ha(doc, configured_system_id=SYSTEM)
    doc = manager_request().as_document()
    doc["projection"]["audit"]["unknown"] = doc["projection"]["audit"].pop("battery_pct")
    doc["projection_hash"] = projection_hash(doc["projection"])
    with pytest.raises((ProjectionProtocolError, ProtocolError)):
        parse_projection_request(doc, expected_system_id=SYSTEM)


def test_exact_result_binding() -> None:
    request = manager_request()
    result = build_projection_result(
        request=request, status="verified", monotonic_revision_enforced=True,
        verified_at=datetime(2026, 8, 3, 12, 31, tzinfo=UTC),
    )
    topic = projection_result_topic(SYSTEM)
    assert parse_and_bind_projection_result(
        result.as_payload(), expected_request=request, actual_topic=topic,
        expected_system_id=SYSTEM,
    ).status == "verified"
    for field, value in {
        "request_id": "different_request_01",
        "idempotency_key": f"{NODE}|2026-08-03T13:00:00Z|v1",
        "revision": 2,
        "projection_hash": "b" * 64,
    }.items():
        doc = result.as_document()
        doc[field] = value
        with pytest.raises(ProjectionProtocolError, match=field):
            parse_and_bind_projection_result(
                doc, expected_request=request, actual_topic=topic,
                expected_system_id=SYSTEM,
            )
    with pytest.raises(ProjectionProtocolError, match="topic"):
        parse_and_bind_projection_result(
            result.as_payload(), expected_request=request,
            actual_topic=projection_result_topic("sys_002"), expected_system_id=SYSTEM,
        )


class FailingStore(MemoryLedgerStore):
    async def async_save(self, document: dict[str, Any]) -> None:
        raise OSError("injected")


class BlockingStore(MemoryLedgerStore):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def async_save(self, document: dict[str, Any]) -> None:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        await super().async_save(document)


def test_ledger_atomic_monotonic_and_serialized() -> None:
    async def run():
        store = MemoryLedgerStore()
        ledger = TargetLedger(store, configured_system_id=SYSTEM)
        await ledger.async_load()
        first = ha_request()
        assert (await ledger.async_prepare(first, accepted_at="2026-08-03T12:30:00Z")).status == "accepted"
        assert (await ledger.async_prepare(first, accepted_at="2026-08-03T12:30:01Z")).status == "resume"
        await ledger.async_mark_verified(
            first,
            verified_at="2026-08-03T12:31:00Z",
            resolved_series=resolved(first),
        )
        assert (await ledger.async_prepare(first, accepted_at="2026-08-03T12:31:01Z")).status == "verified"
        conflict = await ledger.async_prepare(
            ha_request(mean=21), accepted_at="2026-08-03T12:31:02Z"
        )
        assert conflict.code == "target_same_revision_hash_conflict"
        higher = await ledger.async_prepare(
            ha_request(2, 22), accepted_at="2026-08-03T12:32:00Z"
        )
        assert higher.status == "accepted"
        lower = await ledger.async_prepare(
            first, accepted_at="2026-08-03T12:32:01Z"
        )
        assert lower.code == "target_newer_revision"
        pending_decision = await ledger.async_prepare(
            ha_request(3, 23), accepted_at="2026-08-03T12:32:02Z"
        )
        assert pending_decision.code == "prior_revision_pending"
        copy = ledger.read(first.idempotency_key)
        assert copy is not None
        copy.projection["revision"] = 99
        assert ledger.read(first.idempotency_key).projection["revision"] == 2  # type: ignore[union-attr]

        failed = TargetLedger(FailingStore(), configured_system_id=SYSTEM)
        await failed.async_load()
        with pytest.raises(OSError):
            await failed.async_prepare(first, accepted_at="2026-08-03T12:30:00Z")
        assert failed.read(first.idempotency_key) is None

        blocking_store = BlockingStore()
        blocking = TargetLedger(blocking_store, configured_system_id=SYSTEM)
        await blocking.async_load()
        one = ha_request(node="node_1001")
        two = ha_request(node="node_1002", hour="2026-08-03T13:00:00Z")
        task1 = asyncio.create_task(blocking.async_prepare(one, accepted_at="2026-08-03T14:00:00Z"))
        await blocking_store.started.wait()
        assert blocking.read(one.idempotency_key) is None
        task2 = asyncio.create_task(blocking.async_prepare(two, accepted_at="2026-08-03T14:00:01Z"))
        await asyncio.sleep(0)
        assert blocking_store.calls == 1
        blocking_store.release.set()
        await asyncio.gather(task1, task2)
        assert blocking_store.calls == 2 and len(blocking.snapshot()) == 2
    asyncio.run(run())


def test_ledger_semantics_capacity_and_retention() -> None:
    async def run():
        store = MemoryLedgerStore()
        ledger = TargetLedger(store, configured_system_id=SYSTEM)
        await ledger.async_load()
        request = ha_request()
        await ledger.async_prepare(request, accepted_at="2026-08-03T12:30:00Z")
        await ledger.async_mark_verified(
            request,
            verified_at="2026-08-03T12:31:00Z",
            resolved_series=resolved(request),
        )
        assert store.document is not None
        for field, value in (
            ("system_id", "sys_002"), ("projection_hash", "b" * 64),
            ("revision", 2), ("accepted_at", "2026-08-03T12:30:00+08:00"),
        ):
            doc = deepcopy(store.document)
            entry = next(iter(doc["entries"].values()))
            (doc if field == "system_id" else entry)[field] = value
            with pytest.raises(LedgerCorruptionError):
                await TargetLedger(MemoryLedgerStore(doc), configured_system_id=SYSTEM).async_load()
        doc = deepcopy(store.document)
        next(iter(doc["entries"].values()))["resolved_series"][0]["mean"] = float("nan")
        with pytest.raises(LedgerCorruptionError):
            await TargetLedger(MemoryLedgerStore(doc), configured_system_id=SYSTEM).async_load()

        cap = TargetLedger(MemoryLedgerStore(), configured_system_id=SYSTEM, max_entries=1)
        await cap.async_load()
        pending = ha_request(node="node_cap1")
        other = ha_request(node="node_cap2", hour="2026-08-03T13:00:00Z")
        await cap.async_prepare(pending, accepted_at="2026-08-03T14:00:00Z")
        full = await cap.async_prepare(
            other, accepted_at="2026-08-03T14:00:01Z"
        )
        assert full.code == "target_ledger_capacity_exceeded"
        tiny = TargetLedger(MemoryLedgerStore(), configured_system_id=SYSTEM, max_serialized_bytes=1)
        await tiny.async_load()
        oversized = await tiny.async_prepare(
            pending, accepted_at="2026-08-03T14:00:00Z"
        )
        assert oversized.code == "target_ledger_capacity_exceeded"

        retained_store = MemoryLedgerStore()
        retained = TargetLedger(retained_store, configured_system_id=SYSTEM, max_entries=1)
        await retained.async_load()
        old = ha_request(node="node_old1", hour="2026-07-01T00:00:00Z")
        await retained.async_prepare(old, accepted_at="2026-07-01T00:30:00Z")
        await retained.async_mark_verified(
            old,
            verified_at="2026-07-01T00:31:00Z",
            resolved_series=resolved(old),
        )
        new = ha_request(node="node_new1", hour="2026-08-03T00:00:00Z")
        assert (await retained.async_prepare(new, accepted_at="2026-08-03T00:30:00Z")).status == "accepted"
        restarted = TargetLedger(retained_store, configured_system_id=SYSTEM, max_entries=1)
        await restarted.async_load()
        assert set(restarted.snapshot()) == {new.idempotency_key}
    asyncio.run(run())


def test_entity_and_recorder_contract() -> None:
    resolver = EntityResolver([
        EntityDescriptor(
            entity_id="sensor.user_renamed_temperature", domain="sensor", platform="mqtt",
            unique_id=f"{NODE}_air_temperature_c", unit_of_measurement="°C",
            state_class="measurement",
        )
    ])
    writes = projection_writes(sample_hour=HOUR, resolved=resolver.resolve_projection(projection()))
    verify_readback(writes, tuple(
        StatisticReadback(item.statistic_id, item.start, item.unit_of_measurement,
                          item.mean, item.minimum, item.maximum)
        for item in writes
    ))
