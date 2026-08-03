from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from greenhouse_manager.runtime.history_projection import (
    AdapterDispatchResult,
    FakeProjectionAdapter,
    ProjectionRunner,
)
from greenhouse_manager.runtime.history_projection_store import ProjectionStore
from greenhouse_manager.runtime.history_store import HistoryStore


def _record(
    *,
    seq: int,
    sampled_at: str,
    temperature: float,
    quality: str = "ok",
    time_quality: str = "trusted",
) -> dict[str, Any]:
    return {
        "boot_id": "boot-00000001",
        "seq": seq,
        "uptime_ms": seq * 1000,
        "sampled_at": sampled_at,
        "time_quality": time_quality,
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
    *,
    batch_id: str,
    records: list[dict[str, Any]],
    received_at: datetime,
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
    now = datetime(2026, 8, 3, 4, 10, tzinfo=UTC)
    with tempfile.TemporaryDirectory(prefix="c06b1-host-only-") as directory:
        root = Path(directory)
        path = root / "manager" / "manager-state.sqlite3"
        with HistoryStore(path) as history:
            _commit(
                history,
                batch_id="batch-initial",
                received_at=now,
                records=[
                    _record(
                        seq=1,
                        sampled_at="2026-08-03T04:00:00Z",
                        temperature=22.0,
                    ),
                    _record(
                        seq=2,
                        sampled_at="2026-08-03T04:05:00Z",
                        temperature=26.0,
                    ),
                    _record(
                        seq=3,
                        sampled_at="2026-08-03T04:10:00Z",
                        temperature=99.0,
                        quality="stale",
                    ),
                ],
            )
            with ProjectionStore(path) as projections:
                adapter = FakeProjectionAdapter()
                runner = ProjectionRunner(
                    store=projections,
                    adapter=adapter,
                    worker_id="host-only-worker",
                    retry_base_seconds=10,
                )
                first = runner.run_once(now=now)
                if first.task is None:
                    raise RuntimeError("initial projection task was not claimed")
                first_batch = adapter.dispatched[-1]
                first_temperature = next(
                    series
                    for series in first_batch.payload["series"]
                    if series["measurement_key"] == "air_temperature_c"
                )
                initial_revision = first.task.revision

                _commit(
                    history,
                    batch_id="batch-late",
                    received_at=now,
                    records=[
                        _record(
                            seq=4,
                            sampled_at="2026-08-03T04:15:00Z",
                            temperature=28.0,
                        )
                    ],
                )
                reopened = projections.get_job(
                    "node-0001", "2026-08-03T04:00:00.000Z"
                )
                stale_completion_rejected = not projections.mark_completed(
                    first.task,
                    projection_hash=first.projection_hash or "0" * 64,
                    payload_json=first_batch.payload_json,
                    adapter_kind=adapter.kind,
                    adapter_version=adapter.version,
                    now=now,
                )
                second = runner.run_once(now=now)
                second_batch = adapter.dispatched[-1]
                second_temperature = next(
                    series
                    for series in second_batch.payload["series"]
                    if series["measurement_key"] == "air_temperature_c"
                )

                _commit(
                    history,
                    batch_id="batch-next-hour",
                    received_at=now + timedelta(hours=1),
                    records=[
                        _record(
                            seq=5,
                            sampled_at="2026-08-03T05:00:00Z",
                            temperature=30.0,
                        )
                    ],
                )
                adapter.outcomes.extend(
                    [
                        AdapterDispatchResult(
                            status="retry", code="isolated_adapter_unavailable"
                        ),
                        AdapterDispatchResult(status="verified"),
                    ]
                )
                retry = runner.run_once(now=now + timedelta(hours=1))
                idle_before_due = runner.run_once(now=now + timedelta(hours=1)).status
                retried = runner.run_once(
                    now=now + timedelta(hours=1, seconds=10)
                )
                retry_job = projections.get_job(
                    "node-0001", "2026-08-03T05:00:00.000Z"
                )

                report = {
                    "schema": "gh.c06b1-history-projection-host-only-report/1",
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
                    "projection_schema_version": projections.schema_version(),
                    "initial_status": first.status,
                    "initial_revision": initial_revision,
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
                    "stale_completion_rejected": stale_completion_rejected,
                    "late_status": second.status,
                    "late_temperature_mean": second_temperature["mean"],
                    "late_temperature_samples": second_temperature["samples"],
                    "retry_status": retry.status,
                    "idle_before_retry_due": idle_before_due,
                    "retried_status": retried.status,
                    "retry_attempts": retry_job.attempts if retry_job else None,
                    "adapter_kind": retry_job.adapter_kind if retry_job else None,
                    "same_database_file": list(root.rglob("*.sqlite3")) == [path],
                    "relative_only_reconstruction": first_batch.payload[
                        "relative_only_reconstruction"
                    ],
                    "home_assistant_write_enabled": first_batch.payload[
                        "home_assistant_write_enabled"
                    ],
                    "direct_home_assistant_database_write": first_batch.payload[
                        "direct_home_assistant_database_write"
                    ],
                    "network_used": False,
                    "production_state_modified": False,
                }

    expected = {
        "projection_schema_version": 1,
        "initial_status": "completed",
        "initial_revision": 1,
        "initial_temperature_mean": 24.0,
        "initial_temperature_samples": 2,
        "stale_quality_excluded": 1,
        "dli_projected": False,
        "late_revision": 2,
        "stale_completion_rejected": True,
        "late_status": "completed",
        "late_temperature_samples": 3,
        "retry_status": "retry",
        "idle_before_retry_due": "idle",
        "retried_status": "completed",
        "retry_attempts": 2,
        "adapter_kind": "fake-host-only",
        "same_database_file": True,
        "relative_only_reconstruction": False,
        "home_assistant_write_enabled": False,
        "direct_home_assistant_database_write": False,
        "network_used": False,
        "production_state_modified": False,
    }
    for key, value in expected.items():
        if report[key] != value:
            raise RuntimeError(f"host-only assertion failed: {key}={report[key]!r}")
    if abs(report["late_temperature_mean"] - (76.0 / 3.0)) > 1e-12:
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
