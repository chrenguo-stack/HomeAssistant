from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from history_samples import history_page, history_record

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.history_replay import (
    MAX_HISTORY_UPTIME_MS,
    HistoryReplayProcessor,
    HistoryReplayResult,
)
from greenhouse_manager.runtime.history_store import HistoryStore
from greenhouse_manager.runtime.history_worker import (
    HistoryReplayWorker,
    HistoryWorkItem,
)
from greenhouse_manager.runtime.mqtt_service import ManagerMqttService

_TOPIC = "gh/v1/system-001/ingress/node/node-0001/history"
_NOW = datetime(2026, 8, 3, 4, 5, tzinfo=UTC)


def _path(tmp_path: Path) -> Path:
    return tmp_path / "manager" / "manager-state.sqlite3"


def _payload(document: object) -> bytes:
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode()


def _item(node_id: str, *, batch_id: str) -> HistoryWorkItem:
    return HistoryWorkItem(
        node_id=node_id,
        topic=f"gh/v1/system-001/ingress/node/{node_id}/history",
        payload=_payload(history_page(node_id=node_id, batch_id=batch_id)),
        retained=False,
        node_allowed=True,
        received_at=_NOW,
    )


def _close(service: ManagerMqttService) -> None:
    if service.history_worker is not None:
        service.history_worker.stop()
    if service.history_store is not None:
        service.history_store.close()
    if service.registration_registry is not None:
        service.registration_registry.close()


def test_huge_estimated_uptime_is_rejected_without_overflow(tmp_path: Path) -> None:
    record = history_record(
        uptime_ms=MAX_HISTORY_UPTIME_MS + 1,
        sampled_at="2026-08-03T04:00:00Z",
        time_quality="estimated",
        time_anchor={"sampled_at": "2026-08-03T04:00:00Z", "uptime_ms": 0},
    )
    with HistoryStore(_path(tmp_path)) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)

        direct_reason = processor._validate_record_time(record, now=_NOW)
        result = processor.process(
            _TOPIC,
            _payload(history_page(batch_id="batch-overflow", records=[record])),
            received_at=_NOW,
        )

        assert "between 0" in str(direct_reason)
        assert result.status == "rejected"
        assert store.count_records() == 0


def test_worker_survives_processing_and_result_callback_exceptions(
    tmp_path: Path,
) -> None:
    with HistoryStore(_path(tmp_path)) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        processor.process = Mock(  # type: ignore[method-assign]
            side_effect=[
                OverflowError("synthetic processing failure"),
                HistoryReplayResult(status="rejected", node_id="node-0001"),
            ]
        )
        callback_count = 0
        second_result = threading.Event()

        def on_result(_: HistoryReplayResult) -> None:
            nonlocal callback_count
            callback_count += 1
            if callback_count == 1:
                raise RuntimeError("synthetic publish failure")
            second_result.set()

        worker = HistoryReplayWorker(
            processor=processor,
            on_result=on_result,
            queue_capacity=4,
        )
        worker.start()
        try:
            assert worker.submit(_item("node-0001", batch_id="batch-worker01")) == (
                "queued"
            )
            assert worker.submit(_item("node-0001", batch_id="batch-worker02")) == (
                "queued"
            )
            assert second_result.wait(timeout=5)
            assert worker.is_alive is True
            health = worker.health
            assert health.failure_count == 2
            assert health.last_failure_stage == "result_callback"
        finally:
            worker.stop()


def test_maintenance_failure_is_observed_and_next_run_continues(
    tmp_path: Path,
) -> None:
    with HistoryStore(_path(tmp_path)) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        store.prune = Mock(  # type: ignore[method-assign]
            side_effect=[sqlite3.OperationalError("locked"), 2]
        )
        worker = HistoryReplayWorker(processor=processor, on_result=Mock())

        assert worker.run_maintenance(now=_NOW, force=True) == 0
        assert worker.health.failure_count == 1
        assert worker.health.last_failure_stage == "maintenance"
        assert worker.run_maintenance(now=_NOW, force=True) == 2


def test_rate_state_has_global_capacity_and_ttl_cleanup(tmp_path: Path) -> None:
    now = [0.0]
    with HistoryStore(_path(tmp_path)) as store:
        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        worker = HistoryReplayWorker(
            processor=processor,
            on_result=Mock(),
            queue_capacity=4,
            rate_state_capacity=2,
            rate_state_ttl_s=10,
            monotonic=lambda: now[0],
        )

        assert worker.submit(_item("node-0001", batch_id="batch-rate001")) == (
            "queued"
        )
        assert worker.submit(_item("node-0002", batch_id="batch-rate002")) == (
            "queued"
        )
        assert worker.submit(_item("node-0003", batch_id="batch-rate003")) == (
            "rate_state_full"
        )
        assert worker.rate_state_count == 2

        now[0] = 11.0
        assert worker.submit(_item("node-0003", batch_id="batch-rate004")) == (
            "queued"
        )
        assert worker.rate_state_count == 1


def test_portable_role_and_dangling_symlinks_fail_closed(tmp_path: Path) -> None:
    nonportable = tmp_path / "other.sqlite3"
    with pytest.raises(ValueError, match="portable"):
        Settings(
            system_id="system-001",
            history_replay_enabled=True,
            history_db_path=str(nonportable),
        ).validate()

    dangling_target = tmp_path / "outside.sqlite3"
    dangling_path = _path(tmp_path)
    dangling_path.parent.mkdir(mode=0o700)
    dangling_path.symlink_to(dangling_target)

    with pytest.raises(ValueError, match="symlink"):
        Settings(
            system_id="system-001",
            history_replay_enabled=True,
            history_db_path=str(dangling_path),
        ).validate()
    with pytest.raises(ValueError, match="symlink"):
        HistoryStore(dangling_path)

    ancestor = tmp_path / "dangling-root"
    ancestor.symlink_to(tmp_path / "missing-root", target_is_directory=True)
    descendant = ancestor / "manager" / "manager-state.sqlite3"
    with pytest.raises(ValueError, match="ancestors"):
        HistoryStore(descendant)


def test_real_database_byte_capacity_rejects_before_history_write(
    tmp_path: Path,
) -> None:
    path = _path(tmp_path)
    with HistoryStore(path, max_db_bytes=1_048_576) as store:
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE capacity_filler (payload BLOB NOT NULL)")
        connection.execute(
            "INSERT INTO capacity_filler(payload) VALUES (zeroblob(2000000))"
        )
        connection.commit()
        connection.close()

        processor = HistoryReplayProcessor(system_id="system-001", store=store)
        document = history_page(batch_id="batch-db-bytes")
        result = processor.process(_TOPIC, _payload(document), received_at=_NOW)

        assert result.status == "rejected"
        assert "database byte capacity" in str(result.reason)
        assert store.count_records() == 0


@patch("greenhouse_manager.runtime.mqtt_service.mqtt.Client")
def test_mqtt_prequeue_rejects_oversize_and_non_qos1(
    client_class: object,
    tmp_path: Path,
) -> None:
    client = client_class.return_value
    client.publish.return_value = Mock(rc=0)
    service = ManagerMqttService(
        Settings(
            system_id="system-001",
            history_replay_enabled=True,
            history_db_path=str(_path(tmp_path)),
            history_max_payload_bytes=4_096,
        )
    )
    assert service.history_worker is not None

    oversized = Mock(
        topic=_TOPIC,
        payload=b"x" * 4_097,
        qos=1,
        retain=False,
    )
    qos_zero = Mock(
        topic=_TOPIC,
        payload=_payload(history_page()),
        qos=0,
        retain=False,
    )

    service._on_message(client, None, oversized)
    service._on_message(client, None, qos_zero)

    assert service.history_worker.pending_count == 0
    assert client.publish.call_count == 0
    _close(service)


def test_schema_uptime_limit_matches_runtime_constant() -> None:
    document = history_page(
        records=[
            history_record(
                uptime_ms=MAX_HISTORY_UPTIME_MS,
                sampled_at="2026-08-03T04:00:00Z",
            )
        ]
    )
    text = json.dumps(document, separators=(",", ":"), sort_keys=True)
    assert hashlib.sha256(text.encode()).hexdigest()
