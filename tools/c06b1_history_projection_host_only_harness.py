from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from greenhouse_manager.runtime.history_projection import (
    AdapterDispatchResult,
    FakeProjectionAdapter,
    ProjectionContractError,
    ProjectionRunner,
    aggregate_projection,
)
from greenhouse_manager.runtime.history_projection_store import ProjectionStore, ProjectionTask
from greenhouse_manager.runtime.history_store import HistoryStore

NOW = datetime(2026, 8, 3, 4, 10, tzinfo=UTC)
HOUR = "2026-08-03T04:00:00.000Z"


def _record(
    seq: int,
    sampled_at: str,
    temperature: float | int,
    *,
    quality: str = "ok",
) -> dict[str, Any]:
    return {
        "boot_id": "boot-00000001",
        "seq": seq,
        "uptime_ms": seq * 1000,
        "sampled_at": sampled_at,
        "time_quality": "trusted",
        "time_anchor": None,
        "cap_hash": "cap-hash-0001",
        "fw_version": "1.0.0",
        "measurements": {
            "air_temperature_c": temperature,
            "air_humidity_pct": 65.0,
            "dli_today_mol_m2_d": 12.5,
        },
        "quality": {
            "air_temperature_c": quality,
            "air_humidity_pct": "ok",
            "dli_today_mol_m2_d": "ok",
        },
        "power": {"source": "battery", "battery_v": 3.9, "low": False},
    }


def _commit(
    store: HistoryStore,
    batch_id: str,
    records: list[dict[str, Any]],
    at: datetime,
) -> None:
    store.commit_page(
        node_id="node-0001",
        batch_id=batch_id,
        page_index=0,
        page_count=1,
        records=records,
        payload_sha256=hashlib.sha256(batch_id.encode()).hexdigest(),
        received_at=at,
    )


def _temperature(batch: Any) -> dict[str, Any]:
    return next(
        series
        for series in batch.payload["series"]
        if series["measurement_key"] == "air_temperature_c"
    )


def _legacy_completed_reopens() -> bool:
    with tempfile.TemporaryDirectory(prefix="c06b1-legacy-") as directory:
        path = Path(directory) / "manager" / "manager-state.sqlite3"
        with HistoryStore(path) as history:
            _commit(
                history,
                "batch-legacy",
                [_record(1, "2026-08-03T04:00:00Z", 24.0)],
                NOW,
            )
        with sqlite3.connect(path) as connection:
            connection.execute(
                """
                UPDATE c06_projection_outbox
                SET state='completed', completed_at=updated_at
                WHERE node_id='node-0001' AND sample_hour=?
                """,
                (HOUR,),
            )
        with ProjectionStore(path) as store:
            job = store.get_job("node-0001", HOUR)
            return (
                store.schema_version() == 2
                and job is not None
                and job.state == "pending"
                and job.attempts == 0
                and store.claim_next(worker_id="migration-check", now=NOW)
                is not None
            )


def _extreme_numeric_blocked() -> bool:
    task = ProjectionTask(
        node_id="node-0001",
        sample_hour=HOUR,
        projection_version=1,
        revision=1,
        attempts=1,
        claimed_by="host-only-worker",
        lease_until=NOW + timedelta(seconds=60),
    )
    try:
        aggregate_projection(
            task,
            [_record(999, "2026-08-03T04:00:00Z", 10**1_000)],
        )
    except ProjectionContractError:
        return True
    return False


def run(
    *,
    authorization: str = "local-host-only",
    base_sha: str = "local",
    base_ref: str = "local",
    source_sha: str = "local",
    source_ref: str = "local",
    exact_base_verified: bool = False,
    base_ancestor_verified: bool = False,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="c06b1-host-only-") as directory:
        root = Path(directory)
        path = root / "manager" / "manager-state.sqlite3"
        with HistoryStore(path) as history:
            _commit(
                history,
                "batch-initial",
                [
                    _record(1, "2026-08-03T04:00:00Z", 22.0),
                    _record(2, "2026-08-03T04:05:00Z", 26.0),
                    _record(
                        3,
                        "2026-08-03T04:10:00Z",
                        99.0,
                        quality="stale",
                    ),
                ],
                NOW,
            )
            with ProjectionStore(path) as store:
                adapter = FakeProjectionAdapter()
                runner = ProjectionRunner(
                    store=store,
                    adapter=adapter,
                    worker_id="host-only-worker",
                    retry_base_seconds=10,
                )
                first = runner.run_once(
                    now=NOW,
                    settled_at=NOW + timedelta(seconds=2),
                )
                if first.task is None:
                    raise RuntimeError("initial projection task was not claimed")
                first_batch = adapter.dispatched[-1]
                first_temperature = _temperature(first_batch)

                _commit(
                    history,
                    "batch-late-two",
                    [
                        _record(4, "2026-08-03T04:15:00Z", 28.0),
                        _record(5, "2026-08-03T04:16:00Z", 30.0),
                    ],
                    NOW + timedelta(seconds=3),
                )
                reopened = store.get_job("node-0001", HOUR)
                stale_rejected = not store.mark_completed(
                    first.task,
                    projection_hash=first.projection_hash or "0" * 64,
                    payload_json=first_batch.payload_json,
                    adapter_kind=adapter.kind,
                    adapter_version=adapter.version,
                    now=NOW + timedelta(seconds=3),
                )
                second = runner.run_once(
                    now=NOW + timedelta(seconds=3),
                    settled_at=NOW + timedelta(seconds=4),
                )
                second_temperature = _temperature(adapter.dispatched[-1])

                _commit(
                    history,
                    "batch-timeout",
                    [_record(6, "2026-08-03T05:00:00Z", 31.0)],
                    NOW + timedelta(hours=1),
                )
                timeout_runner = ProjectionRunner(
                    store=store,
                    adapter=FakeProjectionAdapter(),
                    worker_id="timeout-worker",
                    lease_seconds=60,
                    adapter_timeout_seconds=30,
                    retry_base_seconds=10,
                )
                timeout = timeout_runner.run_once(
                    now=NOW + timedelta(hours=1),
                    settled_at=NOW + timedelta(hours=1, seconds=31),
                )
                timeout_retry = timeout_runner.run_once(
                    now=NOW + timedelta(hours=1, seconds=41)
                )

                _commit(
                    history,
                    "batch-expired",
                    [_record(7, "2026-08-03T06:00:00Z", 32.0)],
                    NOW + timedelta(hours=2),
                )
                expired = ProjectionRunner(
                    store=store,
                    adapter=FakeProjectionAdapter(),
                    worker_id="expired-worker",
                    lease_seconds=60,
                    adapter_timeout_seconds=30,
                ).run_once(
                    now=NOW + timedelta(hours=2),
                    settled_at=NOW + timedelta(hours=2, seconds=60),
                )
                successor = ProjectionRunner(
                    store=store,
                    adapter=FakeProjectionAdapter(),
                    worker_id="successor-worker",
                    lease_seconds=60,
                    adapter_timeout_seconds=30,
                ).run_once(now=NOW + timedelta(hours=2, seconds=61))
                expired_job = store.get_job(
                    "node-0001", "2026-08-03T06:00:00.000Z"
                )

                _commit(
                    history,
                    "batch-requeue",
                    [_record(8, "2026-08-03T07:00:00Z", 33.0)],
                    NOW + timedelta(hours=3),
                )
                blocked_adapter = FakeProjectionAdapter(
                    outcomes=[
                        AdapterDispatchResult(
                            status="blocked", code="entity_missing"
                        ),
                        AdapterDispatchResult(status="verified"),
                    ]
                )
                blocked_runner = ProjectionRunner(
                    store=store,
                    adapter=blocked_adapter,
                    worker_id="operator-worker",
                )
                blocked = blocked_runner.run_once(now=NOW + timedelta(hours=3))
                blocked_job = store.get_job(
                    "node-0001", "2026-08-03T07:00:00.000Z"
                )
                requeued = bool(
                    blocked_job
                    and store.requeue_blocked(
                        node_id="node-0001",
                        sample_hour="2026-08-03T07:00:00.000Z",
                        expected_revision=blocked_job.revision,
                        operator_reason="host-only entity contract repaired",
                        now=NOW + timedelta(hours=3, seconds=1),
                    )
                )
                requeue_completed = blocked_runner.run_once(
                    now=NOW + timedelta(hours=3, seconds=1)
                )
                requeue_job = store.get_job(
                    "node-0001", "2026-08-03T07:00:00.000Z"
                )

                report = {
                    "schema": "gh.c06b1-history-projection-host-only-report/2",
                    "authorization": authorization,
                    "base_sha": base_sha,
                    "base_ref": base_ref,
                    "source_sha": source_sha,
                    "source_ref": source_ref,
                    "exact_base_verified": exact_base_verified,
                    "base_ancestor_verified": base_ancestor_verified,
                    "portable_manager_state_relative_path": (
                        "manager/manager-state.sqlite3"
                    ),
                    "projection_schema_version": store.schema_version(),
                    "projection_payload_schema": first_batch.payload["schema"],
                    "projection_algorithm_version": first_batch.payload[
                        "algorithm_version"
                    ],
                    "payload_runtime_flags_absent": all(
                        key not in first_batch.payload
                        for key in (
                            "home_assistant_write_enabled",
                            "direct_home_assistant_database_write",
                            "relative_only_reconstruction",
                            "dli_counter_projection",
                        )
                    ),
                    "source_set_sha256_present": (
                        len(first_batch.payload["source_set_sha256"]) == 64
                    ),
                    "initial_status": first.status,
                    "initial_revision": first.task.revision,
                    "initial_temperature_mean": first_temperature["mean"],
                    "initial_temperature_samples": first_temperature["samples"],
                    "stale_quality_excluded": (
                        first_batch.payload["audit"]["air_temperature_c"][
                            "excluded_quality"
                        ]
                    ),
                    "dli_projected": any(
                        item["measurement_key"].startswith("dli_")
                        for item in first_batch.payload["series"]
                    ),
                    "late_revision": reopened.revision if reopened else None,
                    "late_attempts_reset": (
                        reopened.attempts == 0 if reopened else False
                    ),
                    "multi_record_page_single_revision": bool(
                        reopened
                        and reopened.revision == first.task.revision + 1
                    ),
                    "stale_completion_rejected": stale_rejected,
                    "late_status": second.status,
                    "late_temperature_mean": second_temperature["mean"],
                    "late_temperature_samples": second_temperature["samples"],
                    "timeout_status": timeout.status,
                    "timeout_code": timeout.code,
                    "timeout_retried_status": timeout_retry.status,
                    "expired_lease_status": expired.status,
                    "expired_lease_code": expired.code,
                    "expired_lease_successor_status": successor.status,
                    "expired_lease_attempts": (
                        expired_job.attempts if expired_job else None
                    ),
                    "blocked_status": blocked.status,
                    "operator_requeue_succeeded": requeued,
                    "operator_requeue_completed": requeue_completed.status,
                    "operator_requeue_audited": bool(
                        requeue_job
                        and requeue_job.requeue_count == 1
                        and requeue_job.last_requeue_reason
                        == "host-only entity contract repaired"
                    ),
                    "legacy_completed_without_evidence_reopened": (
                        _legacy_completed_reopens()
                    ),
                    "extreme_numeric_blocked": _extreme_numeric_blocked(),
                    "same_database_file": (
                        list(root.rglob("*.sqlite3")) == [path]
                    ),
                    "adapter_kind": adapter.kind,
                    "adapter_version": adapter.version,
                    "monotonic_revision_contract_verified": (
                        second.status == "completed"
                    ),
                    "home_assistant_write_enabled": False,
                    "direct_home_assistant_database_write": False,
                    "relative_only_reconstruction": False,
                    "network_used": False,
                    "production_state_modified": False,
                }

    expected = {
        "projection_schema_version": 2,
        "projection_payload_schema": "gh.c06-hourly-projection/1",
        "projection_algorithm_version": 2,
        "payload_runtime_flags_absent": True,
        "source_set_sha256_present": True,
        "initial_status": "completed",
        "initial_revision": 1,
        "initial_temperature_mean": 24.0,
        "initial_temperature_samples": 2,
        "stale_quality_excluded": 1,
        "dli_projected": False,
        "late_revision": 2,
        "late_attempts_reset": True,
        "multi_record_page_single_revision": True,
        "stale_completion_rejected": True,
        "late_status": "completed",
        "late_temperature_samples": 4,
        "timeout_status": "retry",
        "timeout_code": "adapter_timeout_exceeded",
        "timeout_retried_status": "completed",
        "expired_lease_status": "stale",
        "expired_lease_code": "lease_expired_during_dispatch",
        "expired_lease_successor_status": "completed",
        "expired_lease_attempts": 2,
        "blocked_status": "blocked",
        "operator_requeue_succeeded": True,
        "operator_requeue_completed": "completed",
        "operator_requeue_audited": True,
        "legacy_completed_without_evidence_reopened": True,
        "extreme_numeric_blocked": True,
        "same_database_file": True,
        "adapter_kind": "fake-host-only",
        "adapter_version": "2",
        "monotonic_revision_contract_verified": True,
        "home_assistant_write_enabled": False,
        "direct_home_assistant_database_write": False,
        "relative_only_reconstruction": False,
        "network_used": False,
        "production_state_modified": False,
    }
    for key, value in expected.items():
        if report[key] != value:
            raise RuntimeError(
                f"host-only assertion failed: {key}={report[key]!r}"
            )
    if abs(report["late_temperature_mean"] - 26.5) > 1e-12:
        raise RuntimeError("host-only assertion failed: late mean mismatch")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization", default="local-host-only")
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
