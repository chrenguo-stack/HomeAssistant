from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from history_samples import history_record

from greenhouse_manager.runtime.history_projection import (
    AdapterDispatchResult,
    FakeProjectionAdapter,
    ProjectionContractError,
    ProjectionRunner,
    aggregate_projection,
)
from greenhouse_manager.runtime.history_projection_store import (
    ProjectionStore,
    ProjectionTask,
)
from greenhouse_manager.runtime.history_store import HistoryStore

NOW = datetime(2026, 8, 3, 4, 10, tzinfo=UTC)
HOUR = "2026-08-03T04:00:00.000Z"


def db_path(root: Path) -> Path:
    return root / "manager" / "manager-state.sqlite3"


def commit_records(
    store: HistoryStore,
    records: list[dict],
    *,
    batch_id: str,
    received_at: datetime = NOW,
) -> None:
    store.commit_page(
        node_id="node-0001",
        batch_id=batch_id,
        page_index=0,
        page_count=1,
        records=records,
        payload_sha256=hashlib.sha256(batch_id.encode()).hexdigest(),
        received_at=received_at,
    )


def direct_task(revision: int = 1) -> ProjectionTask:
    return ProjectionTask(
        node_id="node-0001",
        sample_hour=HOUR,
        projection_version=1,
        revision=revision,
        attempts=1,
        claimed_by="worker-a",
        lease_until=NOW + timedelta(seconds=60),
    )


def test_aggregate_uses_only_ok_bounded_values() -> None:
    records = [
        history_record(seq=1, temperature=25.0),
        history_record(seq=2, temperature=27.0),
        history_record(seq=3, temperature=99.0),
        history_record(seq=4, temperature=23.0),
    ]
    records[1]["quality"]["air_temperature_c"] = "stale"
    records[2]["measurements"]["air_temperature_c"] = None
    records[3]["quality"]["air_temperature_c"] = "ok"
    batch = aggregate_projection(direct_task(), records)
    temperature = next(
        item
        for item in batch.payload["series"]
        if item["measurement_key"] == "air_temperature_c"
    )
    assert temperature["samples"] == 2
    assert temperature["mean"] == 24.0
    assert temperature["min"] == 23.0
    assert temperature["max"] == 25.0
    assert batch.payload["audit"]["air_temperature_c"] == {
        "present": 4,
        "accepted": 2,
        "excluded_quality": 1,
        "invalid_or_null": 1,
        "missing": 0,
    }


@pytest.mark.parametrize(
    "value", [10**1_000, 1e308], ids=["huge-int", "huge-float"]
)
def test_extreme_numeric_source_is_deterministically_blocked(value: object) -> None:
    record = history_record()
    record["measurements"]["air_temperature_c"] = value
    with pytest.raises(ProjectionContractError, match="air_temperature_c"):
        aggregate_projection(direct_task(), [record])


def test_malformed_stored_timestamp_is_deterministically_blocked() -> None:
    record = history_record()
    record["sampled_at"] = "not-a-time"
    with pytest.raises(ProjectionContractError, match="invalid sampled_at"):
        aggregate_projection(direct_task(), [record])


def test_duplicate_source_identity_is_blocked() -> None:
    record = history_record()
    with pytest.raises(ProjectionContractError, match="duplicate source record"):
        aggregate_projection(direct_task(), [record, record.copy()])


def test_aggregate_skips_relative_only_and_excludes_dli_counters() -> None:
    trusted = history_record(seq=1)
    trusted["measurements"]["dli_today_mol_m2_d"] = 12.5
    trusted["quality"]["dli_today_mol_m2_d"] = "ok"
    relative = history_record(
        seq=2,
        sampled_at=None,
        time_quality="relative_only",
    )
    batch = aggregate_projection(direct_task(), [trusted, relative])
    keys = {item["measurement_key"] for item in batch.payload["series"]}
    assert "air_temperature_c" in keys
    assert "dli_today_mol_m2_d" not in keys
    assert batch.payload["eligible_record_count"] == 1
    assert batch.payload["skipped_time_quality"] == 1
    assert "relative_only_reconstruction" not in batch.payload
    assert "dli_counter_projection" not in batch.payload
    assert "home_assistant_write_enabled" not in batch.payload
    assert "direct_home_assistant_database_write" not in batch.payload


def test_projection_hash_and_source_set_are_deterministic_for_record_order() -> None:
    first = history_record(seq=1, temperature=22.0)
    second = history_record(seq=2, temperature=26.0)
    a = aggregate_projection(direct_task(), [first, second])
    b = aggregate_projection(direct_task(), [second, first])
    assert a.projection_hash == b.projection_hash
    assert a.payload["source_set_sha256"] == b.payload["source_set_sha256"]
    assert json.loads(a.payload_json) == a.payload


def test_source_set_hash_changes_when_source_content_changes() -> None:
    first = history_record(seq=1, temperature=22.0)
    changed = history_record(seq=1, temperature=23.0)
    a = aggregate_projection(direct_task(), [first])
    b = aggregate_projection(direct_task(), [changed])
    assert a.payload["source_set_sha256"] != b.payload["source_set_sha256"]
    assert a.projection_hash != b.projection_hash


def test_projection_payload_matches_packaged_schema() -> None:
    batch = aggregate_projection(direct_task(), [history_record()])
    assert batch.payload["schema"] == "gh.c06-hourly-projection/1"
    assert batch.payload["algorithm_version"] == 2
    assert batch.payload["idempotency_key"] == f"node-0001|{HOUR}|v1"
    assert len(batch.payload_json.encode()) < 1_048_576


def test_runner_completes_only_after_exact_monotonic_verification(
    tmp_path: Path,
) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(
            history,
            [
                history_record(seq=1, temperature=22.0),
                history_record(
                    seq=2,
                    sampled_at="2026-08-03T04:05:00Z",
                    temperature=26.0,
                ),
            ],
            batch_id="batch-complete",
        )
    with ProjectionStore(path) as store:
        adapter = FakeProjectionAdapter()
        result = ProjectionRunner(
            store=store,
            adapter=adapter,
            worker_id="worker-a",
        ).run_once(now=NOW, settled_at=NOW + timedelta(seconds=5))
        assert result.status == "completed"
        assert len(adapter.dispatched) == 1
        job = store.get_job("node-0001", HOUR)
        assert job is not None
        assert job.state == "completed"
        assert job.projection_hash == result.projection_hash
        assert job.verified_at == NOW + timedelta(seconds=5)
        assert job.adapter_kind == "fake-host-only"


@pytest.mark.parametrize(
    ("outcome", "code"),
    [
        (
            AdapterDispatchResult(
                status="verified",
                verified_projection_hash="0" * 64,
            ),
            "adapter_hash_mismatch",
        ),
        (
            AdapterDispatchResult(
                status="verified",
                verified_revision=99,
            ),
            "adapter_revision_mismatch",
        ),
        (
            AdapterDispatchResult(
                status="verified",
                verified_idempotency_key="wrong",
            ),
            "adapter_idempotency_key_mismatch",
        ),
        (
            AdapterDispatchResult(
                status="verified",
                monotonic_revision_enforced=False,
            ),
            "adapter_monotonic_revision_unverified",
        ),
    ],
)
def test_adapter_verification_contract_failures_block(
    tmp_path: Path,
    outcome: AdapterDispatchResult,
    code: str,
) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id=f"batch-{code}")
    adapter = FakeProjectionAdapter(outcomes=[outcome])
    with ProjectionStore(path) as store:
        result = ProjectionRunner(
            store=store,
            adapter=adapter,
            worker_id="worker-a",
        ).run_once(now=NOW)
        assert result.status == "blocked"
        assert result.code == code
        job = store.get_job("node-0001", HOUR)
        assert job is not None
        assert job.state == "blocked"


def test_retry_then_success_is_idempotent(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-retry")
    adapter = FakeProjectionAdapter(
        outcomes=[
            AdapterDispatchResult(status="retry", code="adapter_unavailable"),
            AdapterDispatchResult(status="verified"),
        ]
    )
    with ProjectionStore(path) as store:
        runner = ProjectionRunner(
            store=store,
            adapter=adapter,
            worker_id="worker-a",
            retry_base_seconds=10,
        )
        first = runner.run_once(now=NOW)
        assert first.status == "retry"
        assert runner.run_once(now=NOW).status == "idle"
        second = runner.run_once(now=NOW + timedelta(seconds=10))
        assert second.status == "completed"
        assert first.projection_hash == second.projection_hash
        assert len(adapter.dispatched) == 2


def test_adapter_timeout_uses_actual_settlement_time(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-timeout")
    with ProjectionStore(path) as store:
        result = ProjectionRunner(
            store=store,
            adapter=FakeProjectionAdapter(),
            worker_id="worker-a",
            lease_seconds=60,
            adapter_timeout_seconds=30,
            retry_base_seconds=10,
        ).run_once(now=NOW, settled_at=NOW + timedelta(seconds=31))
        assert result.status == "retry"
        assert result.code == "adapter_timeout_exceeded"
        job = store.get_job("node-0001", HOUR)
        assert job is not None
        assert job.next_attempt_at == NOW + timedelta(seconds=41)


def test_expired_lease_cannot_complete_and_is_reclaimed(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-expired")
    with ProjectionStore(path) as store:
        first = ProjectionRunner(
            store=store,
            adapter=FakeProjectionAdapter(),
            worker_id="worker-a",
            lease_seconds=60,
            adapter_timeout_seconds=30,
        ).run_once(now=NOW, settled_at=NOW + timedelta(seconds=60))
        assert first.status == "stale"
        assert first.code == "lease_expired_during_dispatch"
        leased = store.get_job("node-0001", HOUR)
        assert leased is not None
        assert leased.state == "leased"

        second = ProjectionRunner(
            store=store,
            adapter=FakeProjectionAdapter(),
            worker_id="worker-b",
            lease_seconds=60,
            adapter_timeout_seconds=30,
        ).run_once(now=NOW + timedelta(seconds=61))
        assert second.status == "completed"
        completed = store.get_job("node-0001", HOUR)
        assert completed is not None
        assert completed.attempts == 2


def test_blocked_job_can_be_operator_requeued_without_new_source(
    tmp_path: Path,
) -> None:
    path = db_path(tmp_path)
    with HistoryStore(path) as history:
        commit_records(history, [history_record()], batch_id="batch-blocked")
    adapter = FakeProjectionAdapter(
        outcomes=[
            AdapterDispatchResult(status="blocked", code="entity_missing"),
            AdapterDispatchResult(status="verified"),
        ]
    )
    with ProjectionStore(path) as store:
        runner = ProjectionRunner(
            store=store,
            adapter=adapter,
            worker_id="worker-a",
        )
        first = runner.run_once(now=NOW)
        assert first.status == "blocked"
        blocked = store.get_job("node-0001", HOUR)
        assert blocked is not None
        assert store.requeue_blocked(
            node_id="node-0001",
            sample_hour=HOUR,
            expected_revision=blocked.revision,
            operator_reason="entity registry repaired",
            now=NOW + timedelta(seconds=1),
        )
        assert runner.run_once(now=NOW + timedelta(seconds=1)).status == "completed"
        completed = store.get_job("node-0001", HOUR)
        assert completed is not None
        assert completed.requeue_count == 1
        assert completed.last_requeue_reason == "entity registry repaired"


def test_no_output_hour_completes_as_verified_noop(tmp_path: Path) -> None:
    path = db_path(tmp_path)
    record = history_record()
    record["quality"] = {
        "air_temperature_c": "fault",
        "air_humidity_pct": "warming",
    }
    with HistoryStore(path) as history:
        commit_records(history, [record], batch_id="batch-empty")
    with ProjectionStore(path) as store:
        adapter = FakeProjectionAdapter()
        result = ProjectionRunner(
            store=store,
            adapter=adapter,
            worker_id="worker-a",
        ).run_once(now=NOW)
        assert result.status == "completed"
        assert adapter.dispatched[0].payload["series"] == []


def test_projection_catalog_matches_discovery_units_for_included_keys() -> None:
    from greenhouse_manager.runtime.ha_discovery import _MEASUREMENT_DEFINITIONS
    from greenhouse_manager.runtime.history_projection import MEASUREMENT_RULES

    for rule in MEASUREMENT_RULES:
        discovery = _MEASUREMENT_DEFINITIONS[rule.key]
        assert discovery[0] == rule.name
        assert discovery[1] == rule.device_class
        assert discovery[2] == rule.unit
        assert discovery[3] == "measurement"
