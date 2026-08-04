from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from datetime import UTC, datetime
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from custom_components.greenhouse_history import _runtime_enabled
from custom_components.greenhouse_history.const import request_topic, result_topic
from custom_components.greenhouse_history.entity_resolver import EntityDescriptor, EntityResolver
from custom_components.greenhouse_history.ledger import MemoryLedgerStore, TargetLedger
from custom_components.greenhouse_history.mqtt_bridge import MqttProjectionBridge
from custom_components.greenhouse_history.recorder_adapter import (
    HomeAssistantRecorderAdapter,
    RecorderAdapterError,
    StatisticReadback,
    projection_writes,
)
from custom_components.greenhouse_history.runtime import ProjectionRequestProcessor

from greenhouse_manager.runtime.c06b2_ha_projection_protocol import (
    build_projection_request,
    build_projection_result,
    parse_projection_request,
    parse_projection_result,
    projection_hash,
    projection_result_topic,
)
from greenhouse_manager.runtime.c06b2_mqtt_rpc_adapter import MqttProjectionRpcAdapter
from greenhouse_manager.runtime.c06b2_runtime_wiring import manager_c06b2_runtime_enabled
from greenhouse_manager.runtime.history_projection_contract import ProjectionBatch

SYSTEM = "sys_001"
NODE = "node_0001"
HOUR = "2026-08-03T12:00:00Z"
NOW = datetime(2026, 8, 3, 12, 30, tzinfo=UTC)
KEYS = (
    "air_temperature_c", "air_humidity_pct", "co2_ppm", "illuminance_lx",
    "soil_temperature_c", "soil_moisture_pct", "soil_ec_us_cm", "vpd_kpa",
    "dew_point_c", "absolute_humidity_g_m3", "ppfd_umol_m2_s", "battery_v",
    "battery_pct",
)


def projection(revision: int = 1, mean: float = 20.0) -> dict[str, Any]:
    item = {
        "measurement_key": "air_temperature_c",
        "entity_unique_id": f"{NODE}_air_temperature_c",
        "name": "空气温度", "unit_of_measurement": "°C",
        "device_class": "temperature", "unit_class_hint": "temperature",
        "state_class": "measurement", "mean_type": "arithmetic",
        "has_sum": False, "samples": 1, "mean": mean, "min": mean, "max": mean,
    }
    return {
        "schema": "gh.c06-hourly-projection/1",
        "idempotency_key": f"{NODE}|{HOUR}|v1", "node_id": NODE,
        "sample_hour": HOUR, "projection_version": 1, "revision": revision,
        "algorithm_version": 2, "quality_policy": "ok-only/1",
        "source_record_count": 1, "source_set_sha256": "a" * 64,
        "eligible_record_count": 1, "skipped_time_quality": 0,
        "series": [item],
        "audit": {
            key: {
                "present": int(key == "air_temperature_c"),
                "accepted": int(key == "air_temperature_c"),
                "excluded_quality": 0, "invalid_or_null": 0,
                "missing": int(key != "air_temperature_c"),
            }
            for key in KEYS
        },
    }


def batch(revision: int = 1, mean: float = 20.0) -> ProjectionBatch:
    payload = projection(revision, mean)
    return ProjectionBatch(NODE, HOUR, 1, revision, projection_hash(payload), payload)


def request_payload(revision: int = 1, mean: float = 20.0) -> bytes:
    return build_projection_request(
        batch=batch(revision, mean), system_id=SYSTEM,
        request_id=f"request_{revision:016d}", sent_at=NOW,
    ).as_payload()


def verified(payload: bytes) -> bytes:
    request = parse_projection_request(payload, expected_system_id=SYSTEM)
    return build_projection_result(
        request=request, status="verified", monotonic_revision_enforced=True,
        verified_at=datetime(2026, 8, 3, 12, 31, tzinfo=UTC),
    ).as_payload()


class FakeTransport:
    def __init__(self) -> None:
        self.on_message: Any = None
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.published: list[tuple[str, bytes, int, bool]] = []
        self.hook: Any = None

    def set_callbacks(self, *, on_message: Any, on_connect: Any, on_disconnect: Any) -> None:
        self.on_message, self.on_connect, self.on_disconnect = (
            on_message, on_connect, on_disconnect
        )

    def start(self) -> None:
        self.on_connect()

    def publish(self, *, topic: str, payload: bytes, qos: int, retain: bool) -> bool:
        self.published.append((topic, payload, qos, retain))
        if self.hook:
            self.hook(payload)
        return True

    def stop(self) -> None:
        return

    def emit(self, payload: bytes) -> None:
        self.on_message(projection_result_topic(SYSTEM), payload)


def test_manager_rpc_exact_binding_timeout_and_reconnect() -> None:
    transport = FakeTransport()
    adapter = MqttProjectionRpcAdapter(
        system_id=SYSTEM, transport=transport, timeout_seconds=0.03,
        request_id_factory=lambda: "request_0000000001", clock=lambda: NOW,
    )

    def respond(payload: bytes) -> None:
        request = parse_projection_request(payload, expected_system_id=SYSTEM)
        mismatch = build_projection_result(
            request=request, status="verified", monotonic_revision_enforced=True,
            verified_at=NOW,
        ).as_document()
        mismatch["request_id"] = "different_request_0001"
        transport.emit(json.dumps(mismatch, separators=(",", ":")).encode())
        transport.emit(verified(payload))

    transport.hook = respond
    result = adapter.dispatch(batch())
    assert result.status == "verified" and adapter.ignored_result_count == 1
    assert transport.published[0][2:] == (1, False)

    transport.hook = None
    timeout = adapter.dispatch(batch(2, 21.0))
    assert timeout.code == "mqtt_rpc_timeout"
    transport.emit(verified(transport.published[-1][1]))
    assert adapter.ignored_result_count == 2

    transport.hook = lambda payload: transport.emit(verified(payload))
    result = adapter.dispatch(batch(3, 22.0))
    assert result.status == "verified"

    transport.hook = None
    adapter.timeout_seconds = 1.0
    output: list[Any] = []
    thread = threading.Thread(target=lambda: output.append(adapter.dispatch(batch(4, 23.0))))
    thread.start()
    while len(transport.published) < 4:
        time.sleep(0.005)
    first = transport.published[-1][1]
    transport.on_disconnect()
    transport.hook = lambda payload: transport.emit(verified(payload))
    transport.on_connect()
    thread.join(1)
    assert output[0].status == "verified"
    assert transport.published[-1][1] == first
    assert adapter.republish_count == 1


def test_ha_bridge_is_bounded_and_callback_does_not_process() -> None:
    async def run() -> None:
        started, release = asyncio.Event(), asyncio.Event()
        calls = 0
        callback: Any = None
        published: list[tuple[str, bytes, int, bool]] = []

        class Processor:
            async def async_process(self, **_: Any) -> bytes:
                nonlocal calls
                calls += 1
                started.set()
                await release.wait()
                return b"ok"

        async def subscribe(topic: str, cb: Any, qos: int) -> Any:
            nonlocal callback
            assert topic == request_topic(SYSTEM) and qos == 1
            callback = cb
            return lambda: None

        async def publish(topic: str, payload: bytes, qos: int, retain: bool) -> None:
            published.append((topic, payload, qos, retain))

        bridge = MqttProjectionBridge(
            request_topic=request_topic(SYSTEM), result_topic=result_topic(SYSTEM),
            processor=Processor(), subscribe=subscribe, publish=publish,
            queue_capacity=1,
        )
        await bridge.async_start()
        message = SimpleNamespace(
            topic=request_topic(SYSTEM), payload=b"x", qos=1, retain=False
        )
        callback(message)
        callback(message)
        assert calls == 0
        assert bridge.health.enqueued == 1 and bridge.health.dropped_queue_full == 1
        await started.wait()
        release.set()
        await bridge._queue.join()
        assert published == [(result_topic(SYSTEM), b"ok", 1, False)]
        await bridge.async_stop()
        assert not bridge.active

    asyncio.run(run())


class MemoryRecorder:
    def __init__(self, fail_once: bool = False) -> None:
        self.imports: list[Any] = []
        self.fail_once = fail_once

    async def async_import_statistics(self, statistics: tuple[Any, ...]) -> None:
        self.imports.append(statistics)

    async def async_read_statistics(
        self, statistic_ids: tuple[str, ...], *, start: str
    ) -> tuple[StatisticReadback, ...]:
        if self.fail_once:
            self.fail_once = False
            raise RecorderAdapterError("recorder_read_failed", "injected")
        by_id = {item.statistic_id: item for item in self.imports[-1]}
        return tuple(
            StatisticReadback(
                statistic_id=statistic_id, start=start,
                unit_of_measurement=by_id[statistic_id].unit_of_measurement,
                mean=by_id[statistic_id].mean,
                minimum=by_id[statistic_id].minimum,
                maximum=by_id[statistic_id].maximum,
            )
            for statistic_id in statistic_ids
        )


def resolver() -> EntityResolver:
    return EntityResolver((EntityDescriptor(
        entity_id="sensor.user_renamed_temperature", domain="sensor", platform="mqtt",
        unique_id=f"{NODE}_air_temperature_c", unit_of_measurement="°C",
        state_class="measurement",
    ),))


def test_processor_monotonic_idempotency_and_pending_restart() -> None:
    async def process(processor: ProjectionRequestProcessor, payload: bytes) -> Any:
        raw = await processor.async_process(
            topic=request_topic(SYSTEM), payload=payload, qos=1, retain=False
        )
        return parse_projection_result(raw)

    async def run() -> None:
        store = MemoryLedgerStore()
        ledger = TargetLedger(store, configured_system_id=SYSTEM)
        await ledger.async_load()
        recorder = MemoryRecorder()
        processor = ProjectionRequestProcessor(
            system_id=SYSTEM, ledger=ledger, resolver_factory=resolver,
            recorder=recorder, clock=lambda: NOW,
        )
        first = request_payload()
        assert (await process(processor, first)).status == "verified"
        assert (await process(processor, first)).status == "verified"
        assert len(recorder.imports) == 1
        assert (await process(processor, request_payload(2, 21.0))).status == "verified"
        lower = await process(processor, first)
        assert lower.code == "target_newer_revision"
        conflict = await process(processor, request_payload(2, 22.0))
        assert conflict.code == "target_same_revision_hash_conflict"

        pending_store = MemoryLedgerStore()
        pending = TargetLedger(pending_store, configured_system_id=SYSTEM)
        await pending.async_load()
        failing = ProjectionRequestProcessor(
            system_id=SYSTEM, ledger=pending, resolver_factory=resolver,
            recorder=MemoryRecorder(True), clock=lambda: NOW,
        )
        assert (await process(failing, first)).code == "recorder_read_failed"
        restarted = TargetLedger(pending_store, configured_system_id=SYSTEM)
        await restarted.async_load()
        resumed = ProjectionRequestProcessor(
            system_id=SYSTEM, ledger=restarted, resolver_factory=resolver,
            recorder=MemoryRecorder(), clock=lambda: NOW,
        )
        assert (await process(resumed, first)).status == "verified"

    asyncio.run(run())


def test_supported_recorder_api_and_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        captured: list[Any] = []
        packages = {
            name: ModuleType(name)
            for name in (
                "homeassistant", "homeassistant.components",
                "homeassistant.components.recorder",
                "homeassistant.components.recorder.const",
                "homeassistant.components.recorder.models",
                "homeassistant.components.recorder.statistics",
                "homeassistant.components.recorder.util",
            )
        }
        for name, module in packages.items():
            monkeypatch.setitem(sys.modules, name, module)
        packages["homeassistant.components.recorder.const"].DOMAIN = "recorder"
        packages["homeassistant.components.recorder.models"].StatisticMeanType = (
            SimpleNamespace(ARITHMETIC=1)
        )

        def import_stats(hass: Any, metadata: Any, rows: Any) -> None:
            captured.append((metadata, rows))

        def query(*_: Any) -> dict[str, list[dict[str, Any]]]:
            return {"sensor.user_renamed_temperature": [{
                "start": datetime(2026, 8, 3, 12, tzinfo=UTC),
                "mean": 20.0, "min": 20.0, "max": 20.0,
            }]}

        class Instance:
            async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
                return func(*args)

        packages["homeassistant.components.recorder.statistics"].async_import_statistics = import_stats
        packages["homeassistant.components.recorder.statistics"].statistics_during_period = query
        packages["homeassistant.components.recorder.util"].get_instance = lambda hass: Instance()
        state = SimpleNamespace(attributes={"unit_of_measurement": "°C"})
        hass = SimpleNamespace(states=SimpleNamespace(get=lambda _: state))
        adapter = HomeAssistantRecorderAdapter(
            hass, readback_timeout_seconds=0.05, readback_poll_seconds=0.01
        )
        writes = projection_writes(
            sample_hour=HOUR, resolved=resolver().resolve_projection(projection())
        )
        await adapter.async_import_statistics(writes)
        readback = await adapter.async_read_statistics(
            ("sensor.user_renamed_temperature",), start=HOUR
        )
        assert len(readback) == 1
        assert captured[0][0]["source"] == "recorder"
        assert captured[0][0]["statistic_id"].startswith("sensor.")

    asyncio.run(run())
    monkeypatch.delenv("GH_C06B2_RUNTIME_ENABLED", raising=False)
    assert manager_c06b2_runtime_enabled() is False
    entry = SimpleNamespace(data={"system_id": SYSTEM}, options={})
    assert _runtime_enabled(entry) is False
