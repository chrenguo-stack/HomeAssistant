from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from history_samples import history_page, history_record

from greenhouse_manager.runtime.history_replay import HistoryReplayProcessor
from greenhouse_manager.runtime.history_store import HistoryStore

_TOPIC = "gh/v1/system-001/ingress/node/node-0001/history"
_NOW = datetime(2026, 8, 3, 4, 5, tzinfo=UTC)


def _payload(document: object) -> bytes:
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")


def test_accepts_page_only_after_durable_commit_and_emits_nonretained_ack(
    tmp_path: Path,
) -> None:
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        result = processor.process(_TOPIC, _payload(history_page()), received_at=_NOW)

        assert result.status == "accepted"
        assert store.count_records() == 1
        assert len(result.messages) == 1
        ack = result.messages[0]
        assert ack.topic == "gh/v1/system-001/command/node/node-0001/history/ack"
        assert ack.retain is False
        assert ack.qos == 1
        assert ack.payload["committed"] is True
        assert ack.payload["inserted_records"] == 1
        assert "/state/" not in ack.topic


def test_exact_retry_is_durable_duplicate_across_restart(tmp_path: Path) -> None:
    path = tmp_path / "manager-state.sqlite3"
    with HistoryStore(path) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        assert processor.process(_TOPIC, _payload(history_page()), received_at=_NOW).status == (
            "accepted"
        )

    with HistoryStore(path) as reopened:
        processor = HistoryReplayProcessor(system_id="system-001", store=reopened)
        result = processor.process(_TOPIC, _payload(history_page()), received_at=_NOW)
        assert result.status == "duplicate"
        assert result.messages[0].payload["status"] == "duplicate"
        assert result.messages[0].payload["committed"] is True
        assert reopened.count_records() == 1


def test_record_collision_returns_nack_and_preserves_original(tmp_path: Path) -> None:
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        processor.process(_TOPIC, _payload(history_page()), received_at=_NOW)
        conflict = history_page(
            batch_id="batch-000002",
            records=[history_record(temperature=32.0)],
        )

        result = processor.process(_TOPIC, _payload(conflict), received_at=_NOW)

        assert result.status == "rejected"
        assert "different historical content" in str(result.reason)
        assert result.messages[0].payload["committed"] is False
        assert result.messages[0].payload["next_page_index"] == 0
        assert store.count_records() == 1


def test_pages_and_sequences_can_arrive_out_of_order_without_canonical_comparison(
    tmp_path: Path,
) -> None:
    page_two = history_page(
        batch_id="batch-000003",
        page_index=1,
        page_count=2,
        records=[history_record(seq=200, sampled_at="2026-08-03T04:02:00Z")],
    )
    page_one = history_page(
        batch_id="batch-000003",
        page_index=0,
        page_count=2,
        records=[history_record(seq=100, sampled_at="2026-08-03T04:01:00Z")],
    )
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        assert processor.process(_TOPIC, _payload(page_two), received_at=_NOW).status == (
            "accepted"
        )
        assert processor.process(_TOPIC, _payload(page_one), received_at=_NOW).status == (
            "accepted"
        )
        assert store.count_records() == 2


def test_rejects_retained_page_and_inactive_node_without_storage(tmp_path: Path) -> None:
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        retained = processor.process(
            _TOPIC,
            _payload(history_page()),
            retained=True,
            received_at=_NOW,
        )
        inactive = processor.process(
            _TOPIC,
            _payload(history_page(batch_id="batch-000002")),
            node_allowed=False,
            received_at=_NOW,
        )

        assert retained.status == "rejected"
        assert retained.messages[0].payload["reason"] == (
            "retained history replay pages are forbidden"
        )
        assert retained.messages[0].payload["next_page_index"] == 0
        assert inactive.status == "rejected"
        assert "retired or unassigned" in str(inactive.reason)
        assert inactive.messages[0].payload["next_page_index"] == 0
        assert store.count_records() == 0


def test_rejects_page_geometry_and_duplicate_keys(tmp_path: Path) -> None:
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        invalid_geometry = history_page(page_index=1, page_count=1)
        duplicate_keys = history_page(
            batch_id="batch-000002",
            records=[history_record(), history_record()],
        )

        geometry_result = processor.process(
            _TOPIC, _payload(invalid_geometry), received_at=_NOW
        )
        duplicate_result = processor.process(
            _TOPIC, _payload(duplicate_keys), received_at=_NOW
        )

        assert geometry_result.status == "rejected"
        assert geometry_result.messages == ()
        assert duplicate_result.status == "rejected"
        assert "duplicate boot_id + seq" in str(duplicate_result.reason)
        assert store.count_records() == 0


def test_durable_store_failure_returns_retry_without_ack(tmp_path: Path) -> None:
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        def fail_commit(**_: object) -> object:
            import sqlite3

            raise sqlite3.OperationalError("database is locked")

        store.commit_page = fail_commit  # type: ignore[method-assign]
        result = processor.process(_TOPIC, _payload(history_page()), received_at=_NOW)

        assert result.status == "retry"
        assert result.messages == ()
        assert "OperationalError" in str(result.reason)


def test_rejects_non_finite_json_number(tmp_path: Path) -> None:
    document = history_page()
    document["records"][0]["measurements"]["air_temperature_c"] = float("nan")
    raw = json.dumps(document, allow_nan=True).encode("utf-8")
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        result = processor.process(_TOPIC, raw, received_at=_NOW)

        assert result.status == "rejected"
        assert result.messages == ()
        assert "non-finite JSON number" in str(result.reason)
        assert store.count_records() == 0


def test_rejects_overflowing_json_float(tmp_path: Path) -> None:
    raw = _payload(history_page()).replace(b"25.0", b"1e400", 1)
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        result = processor.process(_TOPIC, raw, received_at=_NOW)

        assert result.status == "rejected"
        assert result.messages == ()
        assert "non-finite JSON number" in str(result.reason)
        assert store.count_records() == 0


def test_rejects_duplicate_json_object_key(tmp_path: Path) -> None:
    raw = _payload(history_page()).replace(
        b'{"batch_id":',
        b'{"batch_id":"batch-duplicate","batch_id":',
        1,
    )
    with HistoryStore(tmp_path / "manager-state.sqlite3") as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        result = processor.process(_TOPIC, raw, received_at=_NOW)

        assert result.status == "rejected"
        assert result.messages == ()
        assert "duplicate JSON object key: batch_id" in str(result.reason)
        assert store.count_records() == 0
