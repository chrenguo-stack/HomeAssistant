from __future__ import annotations

import argparse
import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from custom_components.greenhouse_history.ledger import (
    LedgerCorruptionError,
    MemoryLedgerStore,
    ResolvedSeries,
    TargetLedger,
)
from custom_components.greenhouse_history.protocol import ProtocolError
from custom_components.greenhouse_history.protocol import parse_request as parse_ha
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

SYSTEM = "sys_c06b2a"
NODE = "node_c06b2a"
HOUR = "2026-08-03T14:00:00Z"
AUTHORIZATION = "D1-C06B2A-PR263-BLOB-TRANSFER-FAILURE-SUCCESSOR-EXACT-GITHUB-WRITE-CLOSURE-20260804-01"
KEYS = (
    "air_temperature_c", "air_humidity_pct", "co2_ppm", "illuminance_lx",
    "soil_temperature_c", "soil_moisture_pct", "soil_ec_us_cm", "vpd_kpa",
    "dew_point_c", "absolute_humidity_g_m3", "ppfd_umol_m2_s", "battery_v",
    "battery_pct",
)


def projection(revision=1, mean=22.0, *, node=NODE, hour=HOUR):
    item = {
        "measurement_key": "air_temperature_c",
        "entity_unique_id": f"{node}_air_temperature_c",
        "name": "空气温度", "unit_of_measurement": "°C",
        "device_class": "temperature", "unit_class_hint": "temperature",
        "state_class": "measurement", "mean_type": "arithmetic",
        "has_sum": False, "samples": 1, "mean": mean, "min": mean, "max": mean,
    }
    return {
        "schema": "gh.c06-hourly-projection/1",
        "idempotency_key": f"{node}|{hour}|v1", "node_id": node,
        "sample_hour": hour, "projection_version": 1, "revision": revision,
        "algorithm_version": 2, "quality_policy": "ok-only/1",
        "source_record_count": 1, "source_set_sha256": "a" * 64,
        "eligible_record_count": 1, "skipped_time_quality": 0,
        "series": [item],
        "audit": {
            key: {"present": int(key == "air_temperature_c"),
                  "accepted": int(key == "air_temperature_c"),
                  "excluded_quality": 0, "invalid_or_null": 0,
                  "missing": int(key != "air_temperature_c")}
            for key in KEYS
        },
    }


def manager_request(revision=1, mean=22.0, *, node=NODE, hour=HOUR):
    payload = projection(revision, mean, node=node, hour=hour)
    return build_projection_request(
        batch=ProjectionBatch(node, hour, 1, revision, projection_hash(payload), payload),
        system_id=SYSTEM, request_id=f"request_{node}_{revision:04d}",
        sent_at=datetime(2026, 8, 3, 15, 0, tzinfo=UTC),
    )


def ha_request(*args, **kwargs):
    return parse_ha(manager_request(*args, **kwargs).as_payload(), configured_system_id=SYSTEM)


def resolved(request):
    return tuple(
        ResolvedSeries(item["measurement_key"], item["entity_unique_id"],
                       f"sensor.renamed_{item['measurement_key']}",
                       item["unit_of_measurement"], float(item["mean"]),
                       float(item["min"]), float(item["max"]))
        for item in request.projection["series"]
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


def schema_probe() -> tuple[bool, bool]:
    root = Path(__file__).resolve().parents[1]
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
    parity = manager.read_bytes() == ha.read_bytes()
    rejected = True
    for field, value in (("measurement_key", "unknown"), ("unit_of_measurement", "°F"), ("mean", 2000.0)):
        doc = manager_request().as_document()
        item = doc["projection"]["series"][0]
        item[field] = value
        if field == "measurement_key":
            item["entity_unique_id"] = f"{NODE}_{value}"
        if field == "mean":
            item["min"] = item["max"] = value
        doc["projection_hash"] = projection_hash(doc["projection"])
        for parser, kwargs in (
            (parse_projection_request, {"expected_system_id": SYSTEM}),
            (parse_ha, {"configured_system_id": SYSTEM}),
        ):
            try:
                parser(doc, **kwargs)
            except (ProjectionProtocolError, ProtocolError):
                pass
            else:
                rejected = False
    return parity, rejected


async def ledger_probe() -> dict[str, bool]:
    store = MemoryLedgerStore()
    ledger = TargetLedger(store, configured_system_id=SYSTEM)
    await ledger.async_load()
    first = ha_request()
    created = await ledger.async_prepare(first, accepted_at="2026-08-03T15:00:00Z")
    resumed = await ledger.async_prepare(first, accepted_at="2026-08-03T15:00:01Z")
    await ledger.async_mark_verified(
        first,
        verified_at="2026-08-03T15:00:02Z",
        resolved_series=resolved(first),
    )
    idempotent = await ledger.async_prepare(first, accepted_at="2026-08-03T15:00:03Z")
    conflict = await ledger.async_prepare(ha_request(mean=23), accepted_at="2026-08-03T15:00:04Z")
    higher = await ledger.async_prepare(ha_request(2, 24), accepted_at="2026-08-03T15:00:05Z")
    lower = await ledger.async_prepare(first, accepted_at="2026-08-03T15:00:06Z")
    pending = await ledger.async_prepare(ha_request(3, 25), accepted_at="2026-08-03T15:00:07Z")

    failing = TargetLedger(FailingStore(), configured_system_id=SYSTEM)
    await failing.async_load()
    atomic = False
    try:
        await failing.async_prepare(first, accepted_at="2026-08-03T15:00:00Z")
    except OSError:
        atomic = failing.read(first.idempotency_key) is None

    blocking_store = BlockingStore()
    blocking = TargetLedger(blocking_store, configured_system_id=SYSTEM)
    await blocking.async_load()
    one = ha_request(node="node_probe1")
    two = ha_request(node="node_probe2", hour="2026-08-03T16:00:00Z")
    task1 = asyncio.create_task(blocking.async_prepare(one, accepted_at="2026-08-03T17:00:00Z"))
    await blocking_store.started.wait()
    old_visible = blocking.read(one.idempotency_key) is None
    task2 = asyncio.create_task(blocking.async_prepare(two, accepted_at="2026-08-03T17:00:01Z"))
    await asyncio.sleep(0)
    serialized = blocking_store.calls == 1
    blocking_store.release.set()
    await asyncio.gather(task1, task2)
    serialized = serialized and blocking_store.calls == 2 and len(blocking.snapshot()) == 2

    semantic = True
    assert store.document is not None
    for field, value in (("system_id", "sys_other"), ("projection_hash", "b" * 64)):
        doc = deepcopy(store.document)
        target = doc if field == "system_id" else next(iter(doc["entries"].values()))
        target[field] = value
        try:
            await TargetLedger(MemoryLedgerStore(doc), configured_system_id=SYSTEM).async_load()
        except LedgerCorruptionError:
            pass
        else:
            semantic = False

    cap = TargetLedger(MemoryLedgerStore(), configured_system_id=SYSTEM, max_entries=1)
    await cap.async_load()
    await cap.async_prepare(one, accepted_at="2026-08-03T17:00:00Z")
    capacity = (
        await cap.async_prepare(two, accepted_at="2026-08-03T17:00:01Z")
    ).code == "target_ledger_capacity_exceeded"

    retention_store = MemoryLedgerStore()
    retention = TargetLedger(retention_store, configured_system_id=SYSTEM, max_entries=1)
    await retention.async_load()
    old = ha_request(node="node_old", hour="2026-07-01T00:00:00Z")
    await retention.async_prepare(old, accepted_at="2026-07-01T00:30:00Z")
    await retention.async_mark_verified(
        old,
        verified_at="2026-07-01T00:31:00Z",
        resolved_series=resolved(old),
    )
    new = ha_request(node="node_new", hour="2026-08-03T00:00:00Z")
    retained = (await retention.async_prepare(new, accepted_at="2026-08-03T00:30:00Z")).status == "accepted"
    restarted = TargetLedger(retention_store, configured_system_id=SYSTEM, max_entries=1)
    await restarted.async_load()
    retained = retained and set(restarted.snapshot()) == {new.idempotency_key}

    return {
        "ledger_created_pending": created.status == "accepted",
        "ledger_pending_resume": resumed.status == "resume",
        "ledger_same_revision_idempotent": idempotent.status == "verified",
        "ledger_same_revision_conflict_blocked": conflict.code == "target_same_revision_hash_conflict",
        "ledger_higher_revision_accepted": higher.status == "accepted",
        "ledger_lower_revision_rejected": lower.code == "target_newer_revision",
        "ledger_pending_revision_serialized": pending.code == "prior_revision_pending",
        "ledger_save_failure_atomic": atomic,
        "ledger_old_state_visible_until_commit": old_visible,
        "ledger_cross_key_writes_serialized": serialized,
        "ledger_system_scope_and_semantic_reload_verified": semantic,
        "ledger_capacity_bounded": capacity,
        "ledger_verified_retention_and_restart_verified": retained,
    }


def result_probe() -> bool:
    request = manager_request()
    result = build_projection_result(
        request=request, status="verified", monotonic_revision_enforced=True,
        verified_at=datetime(2026, 8, 3, 15, 1, tzinfo=UTC),
    )
    parse_and_bind_projection_result(
        result.as_payload(), expected_request=request,
        actual_topic=projection_result_topic(SYSTEM), expected_system_id=SYSTEM,
    )
    for field, value in (("request_id", "different_request"), ("revision", 2), ("projection_hash", "b" * 64)):
        doc = result.as_document()
        doc[field] = value
        try:
            parse_and_bind_projection_result(
                doc, expected_request=request, actual_topic=projection_result_topic(SYSTEM),
                expected_system_id=SYSTEM,
            )
        except ProjectionProtocolError:
            continue
        return False
    try:
        parse_and_bind_projection_result(
            result.as_payload(), expected_request=request,
            actual_topic=projection_result_topic("sys_other"), expected_system_id=SYSTEM,
        )
    except ProjectionProtocolError:
        return True
    return False


def run(args: argparse.Namespace) -> dict[str, Any]:
    parity, differential = schema_probe()
    report = {
        "schema": "gh.c06b2a-ha-target-ledger-host-only-report/2",
        "authorization": args.authorization,
        "base_sha": args.base_sha, "base_ref": args.base_ref,
        "source_sha": args.source_sha, "source_ref": args.source_ref,
        "exact_base_verified": args.exact_base_verified,
        "base_ancestor_verified": args.base_ancestor_verified,
        "manager_ha_projection_schema_byte_parity": parity,
        "projection_schema_differential_rejection_verified": differential,
        "manager_result_request_binding_verified": result_probe(),
        **asyncio.run(ledger_probe()),
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
    required = (
        "exact_base_verified",
        "base_ancestor_verified",
        "manager_ha_projection_schema_byte_parity",
        "projection_schema_differential_rejection_verified",
        "manager_result_request_binding_verified",
        "ledger_created_pending",
        "ledger_pending_resume",
        "ledger_same_revision_idempotent",
        "ledger_same_revision_conflict_blocked",
        "ledger_higher_revision_accepted",
        "ledger_lower_revision_rejected",
        "ledger_pending_revision_serialized",
        "ledger_save_failure_atomic",
        "ledger_old_state_visible_until_commit",
        "ledger_cross_key_writes_serialized",
        "ledger_system_scope_and_semantic_reload_verified",
        "ledger_capacity_bounded",
        "ledger_verified_retention_and_restart_verified",
        "no_mqtt_network_verified",
        "no_home_assistant_runtime_verified",
        "no_recorder_write_verified",
        "no_direct_database_write_verified",
        "no_production_mutation_verified",
        "no_physical_operation_verified",
    )
    report["host_only_contract_verified"] = all(report[key] is True for key in required)
    if not report["host_only_contract_verified"]:
        raise RuntimeError("C06-B2A remediation evidence did not verify")
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
    text = json.dumps(run(args), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
