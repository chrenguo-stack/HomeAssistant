from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from custom_components.greenhouse_history.entity_resolver import (
    EntityDescriptor,
    EntityResolutionError,
    EntityResolver,
)
from custom_components.greenhouse_history.ledger import (
    LedgerCorruptionError,
    MemoryLedgerStore,
    ResolvedSeries,
    TargetLedger,
)
from custom_components.greenhouse_history.protocol import ProtocolError
from custom_components.greenhouse_history.protocol import parse_request as parse_ha_request
from custom_components.greenhouse_history.recorder_adapter import (
    RecorderAdapterError,
    StatisticReadback,
    projection_writes,
    verify_readback,
)

from greenhouse_manager.runtime.c06b2_ha_projection_protocol import (
    ProjectionProtocolError,
    build_projection_request,
    build_projection_result,
    parse_projection_request,
    parse_projection_result,
    projection_hash,
    projection_request_topic,
    projection_result_topic,
)
from greenhouse_manager.runtime.history_projection_contract import ProjectionBatch

_MEASUREMENTS = (
    "air_temperature_c",
    "air_humidity_pct",
    "co2_ppm",
    "illuminance_lx",
    "soil_temperature_c",
    "soil_moisture_pct",
    "soil_ec_us_cm",
    "vpd_kpa",
    "dew_point_c",
    "absolute_humidity_g_m3",
    "ppfd_umol_m2_s",
    "battery_v",
    "battery_pct",
)
_SYSTEM_ID = "sys_001"
_NODE_ID = "node_0001"
_HOUR = "2026-08-03T12:00:00Z"


def _projection(revision: int = 1, mean: float = 20.0) -> dict[str, Any]:
    return {
        "schema": "gh.c06-hourly-projection/1",
        "idempotency_key": f"{_NODE_ID}|{_HOUR}|v1",
        "node_id": _NODE_ID,
        "sample_hour": _HOUR,
        "projection_version": 1,
        "revision": revision,
        "algorithm_version": 2,
        "quality_policy": "ok-only/1",
        "source_record_count": 1,
        "source_set_sha256": "a" * 64,
        "eligible_record_count": 1,
        "skipped_time_quality": 0,
        "series": [
            {
                "measurement_key": "air_temperature_c",
                "entity_unique_id": f"{_NODE_ID}_air_temperature_c",
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
        ],
        "audit": {
            key: {
                "present": int(key == "air_temperature_c"),
                "accepted": int(key == "air_temperature_c"),
                "excluded_quality": 0,
                "invalid_or_null": 0,
                "missing": int(key != "air_temperature_c"),
            }
            for key in _MEASUREMENTS
        },
    }


def _manager_request(revision: int = 1, mean: float = 20.0):
    payload = _projection(revision, mean)
    batch = ProjectionBatch(
        node_id=_NODE_ID,
        sample_hour=_HOUR,
        projection_version=1,
        revision=revision,
        projection_hash=projection_hash(payload),
        payload=payload,
    )
    return build_projection_request(
        batch=batch,
        system_id=_SYSTEM_ID,
        request_id=f"request_{revision:08d}_abcdef",
        sent_at=datetime(2026, 8, 3, 12, 30, tzinfo=UTC),
    )


def _ha_request(revision: int = 1, mean: float = 20.0):
    return parse_ha_request(
        _manager_request(revision, mean).as_payload(),
        configured_system_id=_SYSTEM_ID,
    )


def _resolver(unit: str = "°C") -> EntityResolver:
    return EntityResolver(
        [
            EntityDescriptor(
                entity_id="sensor.user_renamed_temperature",
                domain="sensor",
                platform="mqtt",
                unique_id=f"{_NODE_ID}_air_temperature_c",
                unit_of_measurement=unit,
                state_class="measurement",
            )
        ]
    )


def test_manager_and_ha_protocols_agree() -> None:
    assert projection_request_topic(_SYSTEM_ID).endswith(
        "/out/homeassistant/history/projection"
    )
    assert projection_result_topic(_SYSTEM_ID).endswith(
        "/ingress/homeassistant/history/projection/result"
    )
    request = _manager_request()
    manager = parse_projection_request(
        request.as_payload(), expected_system_id=_SYSTEM_ID
    )
    home_assistant = parse_ha_request(
        request.as_payload(), configured_system_id=_SYSTEM_ID
    )
    assert (
        manager.request_id,
        manager.projection_hash,
        manager.idempotency_key,
        manager.revision,
    ) == (
        home_assistant.request_id,
        home_assistant.projection_hash,
        home_assistant.idempotency_key,
        home_assistant.revision,
    )


def test_protocol_rejects_duplicate_hash_drift_and_wrong_system() -> None:
    request = _manager_request()
    encoded = request.as_payload().decode()
    duplicate = encoded.replace(
        '"request_id":"request_00000001_abcdef"',
        '"request_id":"request_00000001_abcdef","request_id":"duplicate_00000001"',
    )
    with pytest.raises(ProjectionProtocolError, match="duplicate JSON key"):
        parse_projection_request(duplicate, expected_system_id=_SYSTEM_ID)
    with pytest.raises(ProtocolError, match="duplicate JSON key"):
        parse_ha_request(duplicate, configured_system_id=_SYSTEM_ID)

    drift = json.loads(encoded)
    drift["projection"]["series"][0]["mean"] = 21.0
    with pytest.raises(ProjectionProtocolError, match="projection_hash"):
        parse_projection_request(drift, expected_system_id=_SYSTEM_ID)
    with pytest.raises(ProtocolError, match="projection_hash"):
        parse_ha_request(drift, configured_system_id=_SYSTEM_ID)
    with pytest.raises(ProjectionProtocolError, match="system_id"):
        parse_projection_request(request.as_payload(), expected_system_id="sys_002")


def test_result_contract_requires_exact_monotonic_verification() -> None:
    request = _manager_request()
    result = build_projection_result(
        request=request,
        status="verified",
        monotonic_revision_enforced=True,
        verified_at=datetime(2026, 8, 3, 12, 31, tzinfo=UTC),
    )
    assert parse_projection_result(result.as_payload()).status == "verified"
    with pytest.raises(ProjectionProtocolError):
        build_projection_result(
            request=request,
            status="verified",
            monotonic_revision_enforced=False,
            verified_at=datetime(2026, 8, 3, 12, 31, tzinfo=UTC),
        )


def test_target_ledger_monotonic_matrix_and_persistence() -> None:
    async def scenario() -> None:
        store = MemoryLedgerStore()
        ledger = TargetLedger(store)
        await ledger.async_load()
        revision_1 = _ha_request()
        assert (
            await ledger.async_prepare(revision_1, accepted_at="2026-08-03T12:30:00Z")
        ).status == "accepted"
        assert (
            await ledger.async_prepare(revision_1, accepted_at="2026-08-03T12:30:01Z")
        ).status == "resume"
        await ledger.async_mark_verified(
            revision_1,
            verified_at="2026-08-03T12:31:00Z",
            resolved_series=(
                ResolvedSeries(
                    "air_temperature_c",
                    f"{_NODE_ID}_air_temperature_c",
                    "sensor.user_renamed_temperature",
                    "°C",
                    20.0,
                    20.0,
                    20.0,
                ),
            ),
        )
        assert (
            await ledger.async_prepare(revision_1, accepted_at="2026-08-03T12:31:01Z")
        ).status == "verified"
        conflict = await ledger.async_prepare(
            _ha_request(1, 21.0), accepted_at="2026-08-03T12:31:02Z"
        )
        assert conflict.code == "target_same_revision_hash_conflict"
        assert (
            await ledger.async_prepare(
                _ha_request(2, 22.0), accepted_at="2026-08-03T12:32:00Z"
            )
        ).status == "accepted"
        assert (
            await ledger.async_prepare(revision_1, accepted_at="2026-08-03T12:32:01Z")
        ).code == "target_newer_revision"
        assert (
            await ledger.async_prepare(
                _ha_request(3, 23.0), accepted_at="2026-08-03T12:32:02Z"
            )
        ).code == "prior_revision_pending"

        reloaded = TargetLedger(store)
        await reloaded.async_load()
        target = reloaded.read(revision_1.idempotency_key)
        assert target is not None
        assert (target.revision, target.state, store.saves) == (2, "pending", 3)

    asyncio.run(scenario())


def test_target_ledger_corruption_fails_closed() -> None:
    async def scenario() -> None:
        for document in (
            {"storage_schema_version": 1, "entries": []},
            {"storage_schema_version": 2, "entries": {}},
        ):
            with pytest.raises(LedgerCorruptionError):
                await TargetLedger(MemoryLedgerStore(document)).async_load()

    asyncio.run(scenario())


def test_entity_rename_and_recorder_readback_contract() -> None:
    projection = _projection()
    resolved = _resolver().resolve_projection(projection)
    assert resolved[0].entity_id == "sensor.user_renamed_temperature"
    writes = projection_writes(sample_hour=_HOUR, resolved=resolved)
    verify_readback(
        writes,
        tuple(
            StatisticReadback(
                item.statistic_id,
                item.start,
                item.unit_of_measurement,
                item.mean,
                item.minimum,
                item.maximum,
            )
            for item in writes
        ),
    )


def test_entity_and_recorder_boundaries_fail_closed() -> None:
    projection = _projection()
    with pytest.raises(EntityResolutionError) as missing:
        EntityResolver([]).resolve_projection(projection)
    assert missing.value.code == "target_entity_missing"
    with pytest.raises(EntityResolutionError) as mismatch:
        _resolver("°F").resolve_projection(projection)
    assert mismatch.value.code == "target_unit_mismatch"
    writes = projection_writes(
        sample_hour=_HOUR, resolved=_resolver().resolve_projection(projection)
    )
    with pytest.raises(RecorderAdapterError) as readback:
        verify_readback(writes, ())
    assert readback.value.code == "target_readback_incomplete"
