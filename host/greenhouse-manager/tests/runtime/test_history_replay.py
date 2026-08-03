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


def _store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / "manager" / "manager-state.sqlite3")


def test_accepts_page_only_after_durable_commit_and_emits_nonretained_ack(
    tmp_path: Path,
) -> None:
    with _store(tmp_path) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        result = processor.process(_TOPIC, _payload(history_page()), received_at=_NOW)

        assert result.status == "accepted"
        assert store.count_records() == 1
        assert len(result.messages) == 1
        ack = result.messages[0]
        assert ack.topic == "gh/v1/system-001/out/node/node-0001/history/ack"
        assert ack.retain is False
        assert ack.qos == 1
        assert ack.payload["committed"] is True
        assert ack.payload["inserted_records"] == 1
        assert ack.payload["next_page_index"] is None
        assert "/state/" not in ack.topic


def test_exact_retry_is_durable_duplicate_across_restart(tmp_path: Path) -> None:
    path = tmp_path / "manager" / "manager-state.sqlite3"
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
        assert result.messages[0].payload["next_page_index"] is None
        assert reopened.count_records() == 1


def test_record_collision_returns_nack_and_preserves_original(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
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


def test_out_of_order_pages_report_smallest_missing_page(tmp_path: Path) -> None:
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
    with _store(tmp_path) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        second = processor.process(_TOPIC, _payload(page_two), received_at=_NOW)
        first = processor.process(_TOPIC, _payload(page_one), received_at=_NOW)

        assert second.status == "accepted"
        assert second.messages[0].payload["next_page_index"] == 0
        assert first.status == "accepted"
        assert first.messages[0].payload["next_page_index"] is None
        assert store.count_records() == 2


def test_rejects_retained_page_and_inactive_node_without_storage(tmp_path: Path) -> None:
    with _store(tmp_path) as store:
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
    with _store(tmp_path) as store:
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
    with _store(tmp_path) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        def fail_commit(**_: object) -> object:
            import sqlite3

            raise sqlite3.OperationalError("database is locked")

        store.commit_page = fail_commit  # type: ignore[method-assign]
        result = processor.process(_TOPIC, _payload(history_page()), received_at=_NOW)

        assert result.status == "retry"
        assert result.messages == ()
        assert "OperationalError" in str(result.reason)


def test_rejects_non_finite_and_overflowing_json_numbers(tmp_path: Path) -> None:
    document = history_page()
    document["records"][0]["measurements"]["air_temperature_c"] = float("nan")
    raw_nan = json.dumps(document, allow_nan=True).encode("utf-8")
    raw_overflow = _payload(history_page()).replace(b"25.0", b"1e400", 1)
    with _store(tmp_path) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        nan_result = processor.process(_TOPIC, raw_nan, received_at=_NOW)
        overflow_result = processor.process(_TOPIC, raw_overflow, received_at=_NOW)

        assert nan_result.status == "rejected"
        assert nan_result.messages == ()
        assert "non-finite JSON number" in str(nan_result.reason)
        assert overflow_result.status == "rejected"
        assert overflow_result.messages == ()
        assert "non-finite JSON number" in str(overflow_result.reason)
        assert store.count_records() == 0


def test_rejects_duplicate_json_object_key(tmp_path: Path) -> None:
    raw = _payload(history_page()).replace(
        b'{"batch_id":',
        b'{"batch_id":"batch-duplicate","batch_id":',
        1,
    )
    with _store(tmp_path) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        result = processor.process(_TOPIC, raw, received_at=_NOW)

        assert result.status == "rejected"
        assert result.messages == ()
        assert "duplicate JSON object key: batch_id" in str(result.reason)
        assert store.count_records() == 0


def test_accepts_estimated_and_relative_only_time_contracts(tmp_path: Path) -> None:
    estimated = history_record(
        seq=2,
        uptime_ms=120_000,
        sampled_at="2026-08-03T04:02:00Z",
        time_quality="estimated",
        time_anchor={"sampled_at": "2026-08-03T04:00:00Z", "uptime_ms": 0},
    )
    relative = history_record(
        seq=3,
        uptime_ms=180_000,
        sampled_at=None,
        time_quality="relative_only",
        time_anchor=None,
    )
    with _store(tmp_path) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        estimated_result = processor.process(
            _TOPIC,
            _payload(history_page(batch_id="batch-est-001", records=[estimated])),
            received_at=_NOW,
        )
        relative_result = processor.process(
            _TOPIC,
            _payload(history_page(batch_id="batch-rel-001", records=[relative])),
            received_at=_NOW,
        )

        assert estimated_result.status == "accepted"
        assert relative_result.status == "accepted"
        assert store.count_records() == 2
        assert store.pending_projection_hours() == (
            ("node-0001", "2026-08-03T04:00:00.000Z"),
        )


def test_rejects_invalid_clock_anchor_future_and_expired_absolute_time(
    tmp_path: Path,
) -> None:
    invalid_anchor = history_record(
        seq=2,
        uptime_ms=120_000,
        sampled_at="2026-08-03T04:03:00Z",
        time_quality="estimated",
        time_anchor={"sampled_at": "2026-08-03T04:00:00Z", "uptime_ms": 0},
    )
    future = history_record(seq=3, sampled_at="2026-08-03T04:11:00Z")
    expired = history_record(seq=4, sampled_at="2026-07-26T04:00:00Z")
    with _store(tmp_path) as store:
        processor = HistoryReplayProcessor(
            system_id="system-001",
            store=store,
            retention_days=7,
            max_future_skew_s=300,
        )

        anchor_result = processor.process(
            _TOPIC,
            _payload(history_page(batch_id="batch-anchor1", records=[invalid_anchor])),
            received_at=_NOW,
        )
        future_result = processor.process(
            _TOPIC,
            _payload(history_page(batch_id="batch-future1", records=[future])),
            received_at=_NOW,
        )
        expired_result = processor.process(
            _TOPIC,
            _payload(history_page(batch_id="batch-expire1", records=[expired])),
            received_at=_NOW,
        )

        assert "does not match time anchor" in str(anchor_result.reason)
        assert "future clock skew" in str(future_result.reason)
        assert "older than" in str(expired_result.reason)
        assert store.count_records() == 0


def test_accepts_lowercase_rfc3339_and_reuses_canonical_measurement_limits(
    tmp_path: Path,
) -> None:
    lowercase = history_record(sampled_at="2026-08-03t04:00:00z")
    invalid_humidity = history_record(seq=2)
    invalid_humidity["measurements"]["air_humidity_pct"] = 101.0
    with _store(tmp_path) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        accepted = processor.process(
            _TOPIC,
            _payload(history_page(batch_id="batch-lower01", records=[lowercase])),
            received_at=_NOW,
        )
        rejected = processor.process(
            _TOPIC,
            _payload(history_page(batch_id="batch-range01", records=[invalid_humidity])),
            received_at=_NOW,
        )

        assert accepted.status == "accepted"
        assert rejected.status == "rejected"
        assert "maximum of 100" in str(rejected.reason)
        assert store.count_records() == 1
