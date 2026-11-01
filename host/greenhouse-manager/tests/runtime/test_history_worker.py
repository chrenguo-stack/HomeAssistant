from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

from history_samples import history_page

from greenhouse_manager.runtime.history_replay import HistoryReplayProcessor
from greenhouse_manager.runtime.history_store import HistoryStore
from greenhouse_manager.runtime.history_worker import HistoryReplayWorker, HistoryWorkItem

_TOPIC = "gh/v1/system-001/ingress/node/node-0001/history"
_NOW = datetime(2026, 8, 3, 4, 5, tzinfo=UTC)


def _item(*, batch_id: str = "batch-000001") -> HistoryWorkItem:
    payload = json.dumps(
        history_page(batch_id=batch_id),
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return HistoryWorkItem(
        node_id="node-0001",
        topic=_TOPIC,
        payload=payload,
        retained=False,
        node_allowed=True,
        received_at=_NOW,
    )


def test_bounded_queue_defers_processing_and_ack_until_worker_runs(tmp_path: Path) -> None:
    with HistoryStore(tmp_path / "manager" / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        on_result = Mock()
        worker = HistoryReplayWorker(
            processor=processor,
            on_result=on_result,
            queue_capacity=1,
        )

        assert worker.submit(_item()) == "queued"
        assert store.count_records() == 0
        assert on_result.call_count == 0
        assert worker.submit(_item(batch_id="batch-000002")) == "queue_full"

        result = worker.process_one_for_test()

        assert result is not None and result.status == "accepted"
        assert store.count_records() == 1
        on_result.assert_called_once_with(result)


def test_per_node_rate_limit_does_not_ack_dropped_queue_item(tmp_path: Path) -> None:
    clock = iter([0.0, 1.0, 2.0]).__next__
    with HistoryStore(tmp_path / "manager" / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        on_result = Mock()
        worker = HistoryReplayWorker(
            processor=processor,
            on_result=on_result,
            queue_capacity=4,
            max_pages_per_minute=1,
            monotonic=clock,
        )

        assert worker.submit(_item()) == "queued"
        assert worker.submit(_item(batch_id="batch-000002")) == "rate_limited"
        assert on_result.call_count == 0


def test_periodic_maintenance_prunes_without_new_replay_page(tmp_path: Path) -> None:
    values = iter([0.0, 31.0, 62.0])
    clock = values.__next__
    with HistoryStore(tmp_path / "manager" / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        worker = HistoryReplayWorker(
            processor=processor,
            on_result=Mock(),
            prune_interval_s=30,
            monotonic=clock,
        )
        store.prune = Mock(return_value=3)  # type: ignore[method-assign]

        assert worker.run_maintenance(now=_NOW) == 3
        assert worker.run_maintenance(now=_NOW) == 3
        assert store.prune.call_count == 2
