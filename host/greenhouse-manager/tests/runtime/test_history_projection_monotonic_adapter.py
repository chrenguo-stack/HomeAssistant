from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from history_samples import history_record

from greenhouse_manager.runtime.history_projection import (
    FakeProjectionAdapter,
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


def _task(revision: int) -> ProjectionTask:
    return ProjectionTask(
        node_id="node-0001",
        sample_hour=HOUR,
        projection_version=1,
        revision=revision,
        attempts=1,
        claimed_by="worker-a",
        lease_until=NOW + timedelta(seconds=60),
    )


def _batch(revision: int, temperature: float):
    return aggregate_projection(
        _task(revision),
        [history_record(seq=1, temperature=temperature)],
    )


def _db_path(root: Path) -> Path:
    return root / "manager" / "manager-state.sqlite3"


def test_fake_adapter_enforces_stateful_monotonic_revision_contract() -> None:
    adapter = FakeProjectionAdapter()
    revision_1 = _batch(1, 22.0)
    conflicting_revision_1 = _batch(1, 23.0)
    revision_2 = _batch(2, 24.0)

    created = adapter.dispatch(revision_1)
    idempotent = adapter.dispatch(revision_1)
    conflict = adapter.dispatch(conflicting_revision_1)
    replaced = adapter.dispatch(revision_2)
    rejected_lower = adapter.dispatch(revision_1)

    assert created.status == "verified"
    assert idempotent.status == "verified"
    assert conflict.status == "blocked"
    assert conflict.code == "target_same_revision_hash_conflict"
    assert replaced.status == "verified"
    assert rejected_lower.status == "blocked"
    assert rejected_lower.code == "target_newer_revision"

    target = adapter.read_target(revision_1.idempotency_key)
    assert target is not None
    assert target.revision == 2
    assert target.projection_hash == revision_2.projection_hash
    assert target.payload_json == revision_2.payload_json
    assert adapter.operations == [
        "created",
        "verified-idempotent-readback",
        "rejected-same-revision-conflict",
        "replaced-higher-revision",
        "rejected-lower-revision",
    ]


def test_timeout_unknown_result_recovers_by_exact_idempotent_readback(
    tmp_path: Path,
) -> None:
    path = _db_path(tmp_path)
    with HistoryStore(path) as history:
        history.commit_page(
            node_id="node-0001",
            batch_id="batch-timeout-readback",
            page_index=0,
            page_count=1,
            records=[history_record(seq=1, temperature=22.0)],
            payload_sha256=hashlib.sha256(b"batch-timeout-readback").hexdigest(),
            received_at=NOW,
        )

    adapter = FakeProjectionAdapter()
    with ProjectionStore(path) as store:
        runner = ProjectionRunner(
            store=store,
            adapter=adapter,
            worker_id="worker-a",
            lease_seconds=60,
            adapter_timeout_seconds=30,
            retry_base_seconds=10,
        )
        first = runner.run_once(
            now=NOW,
            settled_at=NOW + timedelta(seconds=31),
        )
        second = runner.run_once(now=NOW + timedelta(seconds=41))

    assert first.status == "retry"
    assert first.code == "adapter_timeout_exceeded"
    assert second.status == "completed"
    assert first.projection_hash == second.projection_hash
    assert adapter.operations == ["created", "verified-idempotent-readback"]
    assert second.task is not None
    target = adapter.read_target(
        f"{second.task.node_id}|{second.task.sample_hour}|v{second.task.projection_version}"
    )
    assert target is not None
    assert target.revision == second.task.revision
    assert target.projection_hash == second.projection_hash
