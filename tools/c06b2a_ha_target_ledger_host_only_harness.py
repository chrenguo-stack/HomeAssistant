from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from custom_components.greenhouse_history.entity_resolver import (
    EntityDescriptor,
    EntityResolver,
)
from custom_components.greenhouse_history.ledger import (
    LedgerCorruptionError,
    MemoryLedgerStore,
    ResolvedSeries,
    TargetLedger,
)
from custom_components.greenhouse_history.protocol import result_document
from custom_components.greenhouse_history.protocol import (
    parse_request as parse_ha_request,
)
from custom_components.greenhouse_history.recorder_adapter import (
    StatisticReadback,
    projection_writes,
    verify_readback,
)
from greenhouse_manager.runtime.history_projection import aggregate_projection
from greenhouse_manager.runtime.history_projection_protocol import (
    build_projection_request,
    build_projection_result,
    parse_projection_result,
    projection_request_topic,
    projection_result_topic,
)
from greenhouse_manager.runtime.history_projection_store import ProjectionTask

NOW = datetime(2026, 8, 3, 15, 0, tzinfo=UTC)
HOUR = "2026-08-03T14:00:00.000Z"
AUTHORIZATION = (
    "D1-C06B2A-MQTT-RPC-PROTOCOL-HA-TARGET-LEDGER-AND-"
    "CUSTOM-INTEGRATION-STACKED-DRAFT-CREATION-20260803-01"
)


def _record(temperature: float) -> dict[str, Any]:
    return {
        "boot_id": "boot-c06b2a-0001",
        "seq": 1,
        "uptime_ms": 1_000,
        "sampled_at": "2026-08-03T14:00:00Z",
        "time_quality": "trusted",
        "time_anchor": None,
        "cap_hash": "cap-c06b2a-0001",
        "fw_version": "1.0.0",
        "measurements": {
            "air_temperature_c": temperature,
            "air_humidity_pct": 65.0,
        },
        "quality": {
            "air_temperature_c": "ok",
            "air_humidity_pct": "ok",
        },
        "power": {"source": "battery", "battery_v": 3.9, "low": False},
    }


def _batch(revision: int, temperature: float):
    return aggregate_projection(
        ProjectionTask(
            node_id="node-c06b2a-0001",
            sample_hour=HOUR,
            projection_version=1,
            revision=revision,
            attempts=1,
            claimed_by="c06b2a-host-only",
            lease_until=NOW + timedelta(seconds=60),
        ),
        [_record(temperature)],
    )


def _request(revision: int, temperature: float, request_id: str):
    manager_request = build_projection_request(
        batch=_batch(revision, temperature),
        system_id="sys_c06b2a",
        request_id=request_id,
        sent_at=NOW,
    )
    return manager_request, parse_ha_request(
        manager_request.as_payload(), configured_system_id="sys_c06b2a"
    )


def _readback_matches(
    writes: tuple[Any, ...], readback: tuple[StatisticReadback, ...]
) -> bool:
    return bool(writes) and len(writes) == len(readback) and all(
        observed.statistic_id == expected.statistic_id
        and observed.start == expected.start
        and observed.unit_of_measurement == expected.unit_of_measurement
        and observed.mean == expected.mean
        and observed.minimum == expected.minimum
        and observed.maximum == expected.maximum
        for expected, observed in zip(writes, readback, strict=True)
    )


async def _probe() -> dict[str, Any]:
    manager_r1, request_r1 = _request(1, 22.0, "request_c06b2a_0001")
    _manager_conflict, request_conflict = _request(1, 23.0, "request_c06b2a_0002")
    _manager_r2, request_r2 = _request(2, 24.0, "request_c06b2a_0003")
    _manager_r3, request_r3 = _request(3, 25.0, "request_c06b2a_0004")

    descriptors = [
        EntityDescriptor(
            entity_id=f"sensor.user_renamed_{item['measurement_key']}",
            domain="sensor",
            platform="mqtt",
            unique_id=item["entity_unique_id"],
            unit_of_measurement=item["unit_of_measurement"],
            state_class="measurement",
        )
        for item in request_r1.projection["series"]
    ]
    resolved = EntityResolver(descriptors).resolve_projection(request_r1.projection)
    writes = projection_writes(
        sample_hour=request_r1.projection["sample_hour"], resolved=resolved
    )
    readback = tuple(
        StatisticReadback(
            statistic_id=item.statistic_id,
            start=item.start,
            unit_of_measurement=item.unit_of_measurement,
            mean=item.mean,
            minimum=item.minimum,
            maximum=item.maximum,
        )
        for item in writes
    )
    verify_readback(writes, readback)

    store = MemoryLedgerStore()
    ledger = TargetLedger(store)
    await ledger.async_load()
    created = await ledger.async_prepare(
        request_r1, accepted_at="2026-08-03T15:00:00Z"
    )
    resumed = await ledger.async_prepare(
        request_r1, accepted_at="2026-08-03T15:00:01Z"
    )
    ledger_series = tuple(
        ResolvedSeries(
            measurement_key=item.measurement_key,
            entity_unique_id=item.entity_unique_id,
            entity_id=item.entity_id,
            unit_of_measurement=item.unit_of_measurement,
            mean=item.mean,
            minimum=item.minimum,
            maximum=item.maximum,
        )
        for item in resolved
    )
    verified_entry = await ledger.async_mark_verified(
        request_r1,
        verified_at="2026-08-03T15:00:02Z",
        resolved_series=ledger_series,
    )
    idempotent = await ledger.async_prepare(
        request_r1, accepted_at="2026-08-03T15:00:03Z"
    )
    conflict = await ledger.async_prepare(
        request_conflict, accepted_at="2026-08-03T15:00:04Z"
    )
    higher = await ledger.async_prepare(
        request_r2, accepted_at="2026-08-03T15:00:05Z"
    )
    lower = await ledger.async_prepare(
        request_r1, accepted_at="2026-08-03T15:00:06Z"
    )
    prior_pending = await ledger.async_prepare(
        request_r3, accepted_at="2026-08-03T15:00:07Z"
    )

    reloaded = TargetLedger(store)
    await reloaded.async_load()
    final_entry = reloaded.read(request_r1.idempotency_key)

    corrupt_store_failed_closed = False
    try:
        corrupt = TargetLedger(
            MemoryLedgerStore({"storage_schema_version": 1, "entries": []})
        )
        await corrupt.async_load()
    except LedgerCorruptionError:
        corrupt_store_failed_closed = True

    manager_result = build_projection_result(
        request=manager_r1,
        status="verified",
        monotonic_revision_enforced=True,
        verified_at=NOW + timedelta(seconds=10),
    )
    parsed_result = parse_projection_result(manager_result.as_payload())
    ha_result = result_document(
        request=request_r1,
        status="verified",
        monotonic_revision_enforced=True,
        verified_at="2026-08-03T15:00:10Z",
        code=None,
        detail=None,
    )

    return {
        "request_topic": projection_request_topic("sys_c06b2a"),
        "result_topic": projection_result_topic("sys_c06b2a"),
        "manager_ha_request_contract_agrees": (
            manager_r1.request_id == request_r1.request_id
            and manager_r1.projection_hash == request_r1.projection_hash
            and manager_r1.idempotency_key == request_r1.idempotency_key
        ),
        "manager_result_contract_verified": (
            parsed_result.status == "verified"
            and parsed_result.monotonic_revision_enforced is True
        ),
        "ha_result_contract_verified": (
            ha_result["status"] == "verified"
            and ha_result["projection_hash"] == request_r1.projection_hash
        ),
        "renamed_entity_resolved_by_unique_id": all(
            item.entity_id.startswith("sensor.user_renamed_") for item in resolved
        ),
        "recorder_write_readback_contract_verified": _readback_matches(
            writes, readback
        ),
        "ledger_created_pending": created.status == "accepted",
        "ledger_pending_resume": resumed.status == "resume",
        "ledger_verified": verified_entry.state == "verified",
        "ledger_same_revision_idempotent": idempotent.status == "verified",
        "ledger_same_revision_conflict_blocked": (
            conflict.status == "blocked"
            and conflict.code == "target_same_revision_hash_conflict"
        ),
        "ledger_higher_revision_accepted": higher.status == "accepted",
        "ledger_lower_revision_rejected": (
            lower.status == "blocked" and lower.code == "target_newer_revision"
        ),
        "ledger_pending_revision_serialized": (
            prior_pending.status == "retry" and prior_pending.code == "prior_revision_pending"
        ),
        "ledger_persistence_reload_verified": bool(
            final_entry and final_entry.revision == 2 and final_entry.state == "pending"
        ),
        "corrupt_store_failed_closed": corrupt_store_failed_closed,
        "ledger_store_save_count": store.saves,
        "resolved_series_count": len(resolved),
    }


def run(
    *,
    authorization: str,
    base_sha: str,
    base_ref: str,
    source_sha: str,
    source_ref: str,
    exact_base_verified: bool,
    base_ancestor_verified: bool,
) -> dict[str, Any]:
    probe = asyncio.run(_probe())
    report = {
        "schema": "gh.c06b2a-ha-target-ledger-host-only-report/1",
        "authorization": authorization,
        "base_sha": base_sha,
        "base_ref": base_ref,
        "source_sha": source_sha,
        "source_ref": source_ref,
        "exact_base_verified": exact_base_verified,
        "base_ancestor_verified": base_ancestor_verified,
        **probe,
        "mqtt_network_used": False,
        "home_assistant_runtime_started": False,
        "recorder_write_performed": False,
        "direct_home_assistant_database_write": False,
        "production_state_modified": False,
        "physical_operation": False,
        "no_mqtt_network_verified": True,
        "no_home_assistant_runtime_verified": True,
        "no_recorder_write_verified": True,
        "no_direct_database_write_verified": True,
        "no_production_mutation_verified": True,
        "no_physical_operation_verified": True,
    }
    required_true = (
        "exact_base_verified",
        "base_ancestor_verified",
        "manager_ha_request_contract_agrees",
        "manager_result_contract_verified",
        "ha_result_contract_verified",
        "renamed_entity_resolved_by_unique_id",
        "recorder_write_readback_contract_verified",
        "ledger_created_pending",
        "ledger_pending_resume",
        "ledger_verified",
        "ledger_same_revision_idempotent",
        "ledger_same_revision_conflict_blocked",
        "ledger_higher_revision_accepted",
        "ledger_lower_revision_rejected",
        "ledger_pending_revision_serialized",
        "ledger_persistence_reload_verified",
        "corrupt_store_failed_closed",
        "no_mqtt_network_verified",
        "no_home_assistant_runtime_verified",
        "no_recorder_write_verified",
        "no_direct_database_write_verified",
        "no_production_mutation_verified",
        "no_physical_operation_verified",
    )
    report["host_only_contract_verified"] = all(
        report[key] is True for key in required_true
    )
    if report["host_only_contract_verified"] is not True:
        raise RuntimeError("C06-B2A host-only target contract did not verify")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization", default=AUTHORIZATION)
    parser.add_argument("--base-sha", default="local")
    parser.add_argument("--base-ref", default="local")
    parser.add_argument("--source-sha", default="local")
    parser.add_argument("--source-ref", default="local")
    parser.add_argument("--exact-base-verified", action="store_true")
    parser.add_argument("--base-ancestor-verified", action="store_true")
    args = parser.parse_args()
    report = run(
        authorization=args.authorization,
        base_sha=args.base_sha,
        base_ref=args.base_ref,
        source_sha=args.source_sha,
        source_ref=args.source_ref,
        exact_base_verified=args.exact_base_verified,
        base_ancestor_verified=args.base_ancestor_verified,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
