from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager.runtime.history_projection_contract import ProjectionBatch
from greenhouse_manager.runtime.history_projection_protocol import (
    ProjectionProtocolError,
    build_projection_request,
    build_projection_result,
    parse_projection_request,
    parse_projection_result,
    projection_hash,
    projection_request_topic,
    projection_result_topic,
)

_HOMEASSISTANT_ROOT = Path(__file__).resolve().parents[3] / "homeassistant"
if str(_HOMEASSISTANT_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOMEASSISTANT_ROOT))

from custom_components.greenhouse_history.entity_resolver import (  # noqa: E402
    EntityDescriptor,
    EntityResolutionError,
    EntityResolver,
)
from custom_components.greenhouse_history.ledger import (  # noqa: E402
    LedgerCorruptionError,
    MemoryLedgerStore,
    ResolvedSeries,
    TargetLedger,
)
from custom_components.greenhouse_history.protocol import (  # noqa: E402
    ProtocolError,
    parse_request as parse_ha_request,
)
from custom_components.greenhouse_history.recorder_adapter import (  # noqa: E402
    RecorderAdapterError,
    StatisticReadback,
    projection_writes,
    verify_readback,
)

_MEASUREMENT_KEYS = (
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


def _projection(*, revision: int = 1, mean: float = 20.0) -> dict[str, object]:
    node_id = "node_0001"
    sample_hour = "2026-08-03T12:00:00Z"
    audit = {
        key: {
            "present": 1 if key == "air_temperature_c" else 0,
            "accepted": 1 if key == "air_temperature_c" else 0,
            "excluded_quality": 0,
            "invalid_or_null": 0,
            "missing": 0 if key == "air_temperature_c" else 1,
        }
        for key in _MEASUREMENT_KEYS
    }
    return {
        "schema": "gh.c06-hourly-projection/1",
        "idempotency_key": f"{node_id}|{sample_hour}|v1",
        "node_id": node_id,
        "sample_hour": sample_hour,
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
                "entity_unique_id": f"{node_id}_air_temperature_c",
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
        "audit": audit,
    }


def _batch(*, revision: int = 1, mean: float = 20.0) -> ProjectionBatch:
    payload = _projection(revision=revision, mean=mean)
    return ProjectionBatch(
        node_id="node_0001",
        sample_hour="2026-08-03T12:00:00Z",
        projection_version=1,
        revision=revision,
        projection_hash=projection_hash(payload),
        payload=payload,
    )


def _request(*, revision: int = 1, mean: float = 20.0):
    manager_request = build_projection_request(
        batch=_batch(revision=revision, mean=mean),
        system_id="sys_001",
        request_id=f"request_{revision:08d}_abcdef",
        sent_at=datetime(2026, 8, 3, 12, 30, tzinfo=UTC),
    )
    return parse_ha_request(manager_request.as_payload(), configured_system_id="sys_001")


def test_manager_and_ha_protocols_agree_on_topics_and_request() -> None:
    assert projection_request_topic("sys_001") == (
        "gh/v1/sys_001/out/homeassistant/history/projection"
    )
    assert projection_result_topic("sys_001") == (
        "gh/v1/sys_001/ingress/homeassistant/history/projection/result"
    )
    request = build_projection_request(
        batch=_batch(),
        system_id="sys_001",
        request_id="request_00000001_abcdef",
        sent_at=datetime(2026, 8, 3, 12, 30, tzinfo=UTC),
    )
    parsed_manager = parse_projection_request(
        request.as_payload(), expected_system_id="sys_001"
    )
    parsed_ha = parse_ha_request(request.as_payload(), configured_system_id="sys_001")
    assert parsed_manager.request_id == parsed_ha.request_id
    assert parsed_manager.projection_hash == parsed_ha.projection_hash
    assert parsed_manager.idempotency_key == parsed_ha.idempotency_key
    assert parsed_manager.revision == parsed_ha.revision


def test_protocol_rejects_duplicate_keys_hash_drift_and_wrong_system() -> None:
    request = build_projection_request(
        batch=_batch(),
        system_id="sys_001",
        request_id="request_00000001_abcdef",
        sent_at=datetime(2026, 8, 3, 12, 30, tzinfo=UTC),
    )
    encoded = request.as_payload().decode("utf-8")
    duplicate = encoded.replace(
        '"request_id":"request_00000001_abcdef"',
        '"request_id":"request_00000001_abcdef","request_id":"other_request_0001"',
    )
    with pytest.raises(ProjectionProtocolError, match="duplicate JSON key"):
        parse_projection_request(duplicate, expected_system_id="sys_001")
    with pytest.raises(ProtocolError, match="duplicate JSON key"):
        parse_ha_request(duplicate, configured_system_id="sys_001")

    document = json.loads(encoded)
    document["projection"]["series"][0]["mean"] = 21.0
    with pytest.raises(ProjectionProtocolError, match="projection_hash"):
        parse_projection_request(document, expected_system_id="sys_001")
    with pytest.raises(ProtocolError, match="projection_hash"):
        parse_ha_request(document, configured_system_id="sys_001")
    with pytest.raises(ProjectionProtocolError, match="system_id"):
        parse_projection_request(request.as_payload(), expected_system_id="sys_002")


def test_projection_result_contract_is_exact() -> None:
    request = build_projection_request(
        batch=_batch(),
        system_id="sys_001",
        request_id="request_00000001_abcdef",
        sent_at=datetime(2026, 8, 3, 12, 30, tzinfo=UTC),
    )
    verified = build_projection_result(
        request=request,
        status="verified",
        monotonic_revision_enforced=True,
        verified_at=datetime(2026, 8, 3, 12, 31, tzinfo=UTC),
    )
    parsed = parse_projection_result(verified.as_payload())
    assert parsed.status == "verified"
    assert parsed.monotonic_revision_enforced is True
    assert parsed.code is None
    with pytest.raises(ProjectionProtocolError):
        build_projection_result(
            request=request,
            status="verified",
            monotonic_revision_enforced=False,
            verified_at=datetime(2026, 8, 3, 12, 31, tzinfo=UTC),
        )


def test_target_ledger_enforces_full_monotonic_matrix_and_persists() -> None:
    async def scenario() -> None:
        store = MemoryLedgerStore()
        ledger = TargetLedger(store)
        await ledger.async_load()
        revision_1 = _request(revision=1, mean=20.0)
        first = await ledger.async_prepare(revision_1, accepted_at="2026-08-03T12:30:00Z")
        assert (first.status, first.code) == ("accepted", "accepted_new_target")
        pending_retry = await ledger.async_prepare(
            revision_1, accepted_at="2026-08-03T12:30:01Z"
        )
        assert pending_retry.status == "resume"
        resolved = (
            ResolvedSeries(
                measurement_key="air_temperature_c",
                entity_unique_id="node_0001_air_temperature_c",
                entity_id="sensor.renamed_air_temperature",
                unit_of_measurement="°C",
                mean=20.0,
                minimum=20.0,
                maximum=20.0,
            ),
        )
        verified = await ledger.async_mark_verified(
            revision_1,
            verified_at="2026-08-03T12:31:00Z",
            resolved_series=resolved,
        )
        assert verified.state == "verified"
        idempotent = await ledger.async_prepare(
            revision_1, accepted_at="2026-08-03T12:31:01Z"
        )
        assert idempotent.status == "verified"

        conflict = await ledger.async_prepare(
            _request(revision=1, mean=21.0), accepted_at="2026-08-03T12:31:02Z"
        )
        assert (conflict.status, conflict.code) == (
            "blocked",
            "target_same_revision_hash_conflict",
        )
        higher = await ledger.async_prepare(
            _request(revision=2, mean=22.0), accepted_at="2026-08-03T12:32:00Z"
        )
        assert (higher.status, higher.code) == ("accepted", "accepted_higher_revision")
        lower = await ledger.async_prepare(
            revision_1, accepted_at="2026-08-03T12:32:01Z"
        )
        assert (lower.status, lower.code) == ("blocked", "target_newer_revision")
        still_pending_higher = await ledger.async_prepare(
            _request(revision=3, mean=23.0), accepted_at="2026-08-03T12:32:02Z"
        )
        assert (still_pending_higher.status, still_pending_higher.code) == (
            "retry",
            "prior_revision_pending",
        )

        reloaded = TargetLedger(store)
        await reloaded.async_load()
        readback = reloaded.read(revision_1.idempotency_key)
        assert readback is not None
        assert readback.revision == 2
        assert readback.state == "pending"
        assert store.saves == 3

    asyncio.run(scenario())


def test_target_ledger_fails_closed_on_corrupt_or_unsupported_storage() -> None:
    async def scenario() -> None:
        corrupt = TargetLedger(MemoryLedgerStore({"storage_schema_version": 1, "entries": []}))
        with pytest.raises(LedgerCorruptionError):
            await corrupt.async_load()
        unsupported = TargetLedger(
            MemoryLedgerStore({"storage_schema_version": 2, "entries": {}})
        )
        with pytest.raises(LedgerCorruptionError):
            await unsupported.async_load()

    asyncio.run(scenario())


def test_entity_resolver_uses_mqtt_unique_id_after_entity_rename() -> None:
    projection = _projection()
    resolver = EntityResolver(
        [
            EntityDescriptor(
                entity_id="sensor.user_renamed_temperature",
                domain="sensor",
                platform="mqtt",
                unique_id="node_0001_air_temperature_c",
                unit_of_measurement="°C",
                state_class="measurement",
            )
        ]
    )
    resolved = resolver.resolve_projection(projection)
    assert resolved[0].entity_id == "sensor.user_renamed_temperature"
    writes = projection_writes(sample_hour=projection["sample_hour"], resolved=resolved)
    verify_readback(
        writes,
        (
            StatisticReadback(
                statistic_id="sensor.user_renamed_temperature",
                start="2026-08-03T12:00:00Z",
                unit_of_measurement="°C",
                mean=20.0,
                minimum=20.0,
                maximum=20.0,
            ),
        ),
    )


def test_entity_and_recorder_boundaries_fail_closed() -> None:
    projection = _projection()
    with pytest.raises(EntityResolutionError) as missing:
        EntityResolver([]).resolve_projection(projection)
    assert missing.value.code == "target_entity_missing"

    wrong_unit = EntityResolver(
        [
            EntityDescriptor(
                entity_id="sensor.temperature",
                domain="sensor",
                platform="mqtt",
                unique_id="node_0001_air_temperature_c",
                unit_of_measurement="°F",
                state_class="measurement",
            )
        ]
    )
    with pytest.raises(EntityResolutionError) as mismatch:
        wrong_unit.resolve_projection(projection)
    assert mismatch.value.code == "target_unit_mismatch"

    resolved = EntityResolver(
        [
            EntityDescriptor(
                entity_id="sensor.temperature",
                domain="sensor",
                platform="mqtt",
                unique_id="node_0001_air_temperature_c",
                unit_of_measurement="°C",
                state_class="measurement",
            )
        ]
    ).resolve_projection(projection)
    writes = projection_writes(sample_hour=projection["sample_hour"], resolved=resolved)
    with pytest.raises(RecorderAdapterError) as readback:
        verify_readback(writes, ())
    assert readback.value.code == "target_readback_incomplete"
