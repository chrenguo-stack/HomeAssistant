from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.history_replay import (
    MAX_HISTORY_UPTIME_MS,
    HistoryReplayProcessor,
)
from greenhouse_manager.runtime.history_store import HistoryStore
from greenhouse_manager.runtime.history_worker import (
    HistoryReplayWorker,
    HistoryWorkItem,
)
from greenhouse_manager.runtime.mqtt_service import ManagerMqttService


def _record(
    *,
    seq: int = 1,
    uptime_ms: int | None = None,
    sampled_at: str | None = "2026-08-03T04:00:00Z",
    time_quality: str = "trusted",
    time_anchor: dict[str, Any] | None = None,
    temperature: float = 25.0,
) -> dict[str, Any]:
    return {
        "boot_id": "boot-00000001",
        "seq": seq,
        "uptime_ms": seq * 1000 if uptime_ms is None else uptime_ms,
        "sampled_at": sampled_at,
        "time_quality": time_quality,
        "time_anchor": time_anchor,
        "cap_hash": "cap-hash-0001",
        "fw_version": "1.0.0",
        "measurements": {"air_temperature_c": temperature},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "battery", "battery_v": 3.9, "low": False},
    }


def _page(
    *,
    batch_id: str,
    node_id: str = "node-0001",
    page_index: int = 0,
    page_count: int = 1,
    records: list[dict[str, Any]] | None = None,
) -> bytes:
    value = {
        "schema": "gh.history-replay.batch/1",
        "node_id": node_id,
        "batch_id": batch_id,
        "page_index": page_index,
        "page_count": page_count,
        "records": records or [_record()],
    }
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _work_item(
    *,
    node_id: str,
    batch_id: str,
    now: datetime,
) -> HistoryWorkItem:
    return HistoryWorkItem(
        node_id=node_id,
        topic=f"gh/v1/system-001/ingress/node/{node_id}/history",
        payload=_page(node_id=node_id, batch_id=batch_id),
        retained=False,
        node_allowed=True,
        received_at=now,
    )


def _close_service(service: ManagerMqttService) -> None:
    if service.history_worker is not None:
        service.history_worker.stop()
    if service.history_store is not None:
        service.history_store.close()
    if service.registration_registry is not None:
        service.registration_registry.close()


def run(
    *,
    authorization: str = "local-host-only",
    prior_reviewed_head_sha: str = "local",
    final_reviewed_head_sha: str = "local",
    source_sha: str = "local",
    source_ref: str = "local",
    base_sha: str = "local",
    base_ref: str = "local",
    exact_base_verified: bool = False,
    prior_reviewed_head_ancestor_verified: bool = False,
    final_reviewed_head_ancestor_verified: bool = False,
) -> dict[str, Any]:
    topic = "gh/v1/system-001/ingress/node/node-0001/history"
    now = datetime(2026, 8, 3, 4, 5, tzinfo=UTC)
    results = []
    with tempfile.TemporaryDirectory(prefix="c06-host-only-") as directory:
        root = Path(directory)
        path = root / "manager" / "manager-state.sqlite3"
        with HistoryStore(path) as store:
            processor = HistoryReplayProcessor(system_id="system-001", store=store)
            worker = HistoryReplayWorker(
                processor=processor,
                on_result=results.append,
                queue_capacity=1,
            )
            queued = worker.submit(
                HistoryWorkItem(
                    node_id="node-0001",
                    topic=topic,
                    payload=_page(
                        batch_id="batch-000001",
                        page_index=1,
                        page_count=2,
                        records=[
                            _record(
                                seq=2,
                                sampled_at="2026-08-03T04:02:00Z",
                            )
                        ],
                    ),
                    retained=False,
                    node_allowed=True,
                    received_at=now,
                )
            )
            callback_deferred = store.count_records() == 0 and results == []
            accepted_second = worker.process_one_for_test()
            accepted_first = processor.process(
                topic,
                _page(
                    batch_id="batch-000001",
                    page_index=0,
                    page_count=2,
                    records=[_record()],
                ),
                received_at=now,
            )
            relative = processor.process(
                topic,
                _page(
                    batch_id="batch-relative",
                    records=[
                        _record(
                            seq=3,
                            sampled_at=None,
                            time_quality="relative_only",
                        )
                    ],
                ),
                received_at=now,
            )
            oversized_uptime = processor.process(
                topic,
                _page(
                    batch_id="batch-uptime",
                    records=[
                        _record(
                            seq=4,
                            uptime_ms=MAX_HISTORY_UPTIME_MS + 1,
                            sampled_at="2026-08-03T04:00:00Z",
                            time_quality="estimated",
                            time_anchor={
                                "sampled_at": "2026-08-03T04:00:00Z",
                                "uptime_ms": 0,
                            },
                        )
                    ],
                ),
                received_at=now,
            )
            accepted_record_count = store.count_records()
            accepted_projection_hours = store.pending_projection_hours()

            original_process = processor.process

            def fail_processing(*_: object, **__: object) -> object:
                raise OverflowError("synthetic worker failure")

            processor.process = fail_processing  # type: ignore[method-assign]
            failure_results = []
            failure_worker = HistoryReplayWorker(
                processor=processor,
                on_result=failure_results.append,
            )
            failure_worker.submit(
                _work_item(
                    node_id="node-0001",
                    batch_id="batch-failure1",
                    now=now,
                )
            )
            contained_result = failure_worker.process_one_for_test()
            worker_failure_contained = (
                contained_result is not None
                and contained_result.status == "retry"
                and failure_worker.health.failure_count == 1
                and len(failure_results) == 1
            )
            processor.process = original_process  # type: ignore[method-assign]

            rate_worker = HistoryReplayWorker(
                processor=processor,
                on_result=lambda _: None,
                queue_capacity=2,
                rate_state_capacity=1,
            )
            rate_first = rate_worker.submit(
                _work_item(
                    node_id="node-0001",
                    batch_id="batch-rate001",
                    now=now,
                )
            )
            rate_second = rate_worker.submit(
                _work_item(
                    node_id="node-0002",
                    batch_id="batch-rate002",
                    now=now,
                )
            )
            rate_state_bounded = (
                rate_first == "queued"
                and rate_second == "rate_state_full"
                and rate_worker.rate_state_count == 1
            )

        with HistoryStore(path) as reopened:
            processor = HistoryReplayProcessor(system_id="system-001", store=reopened)
            duplicate = processor.process(
                topic,
                _page(
                    batch_id="batch-000001",
                    page_index=0,
                    page_count=2,
                    records=[_record()],
                ),
                received_at=now,
            )
            collision = processor.process(
                topic,
                _page(
                    batch_id="batch-000002",
                    records=[_record(temperature=31.0)],
                ),
                received_at=now,
            )
            final_record_count = reopened.count_records()
            schema_version = reopened.schema_version()

        portable_rejected = False
        try:
            HistoryStore(root / "nonportable.sqlite3")
        except ValueError:
            portable_rejected = True

        dangling_path = root / "dangling" / "manager" / "manager-state.sqlite3"
        dangling_path.parent.mkdir(parents=True, mode=0o700)
        dangling_path.symlink_to(root / "missing.sqlite3")
        dangling_rejected = False
        try:
            HistoryStore(dangling_path)
        except ValueError:
            dangling_rejected = True

        capacity_path = root / "capacity" / "manager" / "manager-state.sqlite3"
        with HistoryStore(capacity_path, max_db_bytes=1_048_576) as capacity_store:
            connection = sqlite3.connect(capacity_path)
            connection.execute("CREATE TABLE capacity_filler (payload BLOB NOT NULL)")
            connection.execute(
                "INSERT INTO capacity_filler(payload) VALUES (zeroblob(2000000))"
            )
            connection.commit()
            connection.close()
            capacity_processor = HistoryReplayProcessor(
                system_id="system-001",
                store=capacity_store,
            )
            capacity_result = capacity_processor.process(
                topic,
                _page(batch_id="batch-capacity"),
                received_at=now,
            )
            database_byte_capacity_verified = (
                capacity_result.status == "rejected"
                and "database byte capacity" in str(capacity_result.reason)
                and capacity_store.count_records() == 0
            )

        service_path = root / "service" / "manager" / "manager-state.sqlite3"
        service = ManagerMqttService(
            Settings(
                system_id="system-001",
                history_replay_enabled=True,
                history_db_path=str(service_path),
                history_max_payload_bytes=4_096,
            )
        )
        assert service.history_worker is not None
        service._on_history_message(
            SimpleNamespace(
                topic=topic,
                payload=b"x" * 4_097,
                qos=1,
                retain=False,
            )
        )
        service._on_history_message(
            SimpleNamespace(
                topic=topic,
                payload=_page(batch_id="batch-qos-zero"),
                qos=0,
                retain=False,
            )
        )
        prequeue_payload_and_qos_verified = service.history_worker.pending_count == 0
        _close_service(service)

    assert accepted_second is not None
    ack_messages = (
        *accepted_second.messages,
        *accepted_first.messages,
        *relative.messages,
        *duplicate.messages,
    )
    ack_topics = [message.topic for message in ack_messages]
    report = {
        "schema": "gh.c06-history-replay-host-only-report/3",
        "authorization": authorization,
        "prior_reviewed_head_sha": prior_reviewed_head_sha,
        "final_reviewed_head_sha": final_reviewed_head_sha,
        "source_sha": source_sha,
        "source_ref": source_ref,
        "base_sha": base_sha,
        "base_ref": base_ref,
        "exact_base_verified": exact_base_verified,
        "prior_reviewed_head_ancestor_verified": (
            prior_reviewed_head_ancestor_verified
        ),
        "final_reviewed_head_ancestor_verified": (
            final_reviewed_head_ancestor_verified
        ),
        "portable_manager_state_relative_path": "manager/manager-state.sqlite3",
        "portable_path_verified": path.parts[-2:] == (
            "manager",
            "manager-state.sqlite3",
        ),
        "portable_role_enforced": portable_rejected,
        "dangling_symlink_rejected": dangling_rejected,
        "schema_version": schema_version,
        "worker_submit_status": queued,
        "mqtt_callback_storage_deferred": callback_deferred,
        "out_of_order_first_status": accepted_second.status,
        "out_of_order_first_next_page_index": accepted_second.messages[0].payload[
            "next_page_index"
        ],
        "batch_complete_status": accepted_first.status,
        "batch_complete_next_page_index": accepted_first.messages[0].payload[
            "next_page_index"
        ],
        "relative_only_status": relative.status,
        "oversized_uptime_status": oversized_uptime.status,
        "worker_failure_contained": worker_failure_contained,
        "rate_state_bounded": rate_state_bounded,
        "prequeue_payload_and_qos_verified": prequeue_payload_and_qos_verified,
        "database_byte_capacity_verified": database_byte_capacity_verified,
        "duplicate_after_restart_status": duplicate.status,
        "collision_status": collision.status,
        "collision_committed": (
            collision.messages[0].payload["committed"] if collision.messages else None
        ),
        "collision_next_page_index": (
            collision.messages[0].payload["next_page_index"]
            if collision.messages
            else None
        ),
        "accepted_record_count": accepted_record_count,
        "final_record_count": final_record_count,
        "projection_hour_count": len(accepted_projection_hours),
        "ack_retain_values": [message.retain for message in ack_messages],
        "ack_topics": ack_topics,
        "ack_acl_namespace_verified": all(
            ack_topic.startswith("gh/v1/system-001/out/node/node-0001/")
            for ack_topic in ack_topics
        ),
        "canonical_topics_emitted": [
            ack_topic for ack_topic in ack_topics if "/state/" in ack_topic
        ],
        "network_used": False,
        "production_state_modified": False,
    }
    expected = {
        "portable_path_verified": True,
        "portable_role_enforced": True,
        "dangling_symlink_rejected": True,
        "schema_version": 2,
        "worker_submit_status": "queued",
        "mqtt_callback_storage_deferred": True,
        "out_of_order_first_status": "accepted",
        "out_of_order_first_next_page_index": 0,
        "batch_complete_status": "accepted",
        "batch_complete_next_page_index": None,
        "relative_only_status": "accepted",
        "oversized_uptime_status": "rejected",
        "worker_failure_contained": True,
        "rate_state_bounded": True,
        "prequeue_payload_and_qos_verified": True,
        "database_byte_capacity_verified": True,
        "duplicate_after_restart_status": "duplicate",
        "collision_status": "rejected",
        "collision_committed": False,
        "collision_next_page_index": 0,
        "accepted_record_count": 3,
        "final_record_count": 3,
        "projection_hour_count": 1,
        "ack_acl_namespace_verified": True,
        "canonical_topics_emitted": [],
        "network_used": False,
        "production_state_modified": False,
    }
    for key, value in expected.items():
        if report[key] != value:
            raise RuntimeError(f"host-only assertion failed: {key}={report[key]!r}")
    if any(report["ack_retain_values"]):
        raise RuntimeError("host-only assertion failed: retained ACK detected")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization", default="local-host-only")
    parser.add_argument("--prior-reviewed-head-sha", default="local")
    parser.add_argument("--final-reviewed-head-sha", default="local")
    parser.add_argument("--source-sha", default="local")
    parser.add_argument("--source-ref", default="local")
    parser.add_argument("--base-sha", default="local")
    parser.add_argument("--base-ref", default="local")
    parser.add_argument("--exact-base-verified", action="store_true")
    parser.add_argument(
        "--prior-reviewed-head-ancestor-verified",
        action="store_true",
    )
    parser.add_argument(
        "--final-reviewed-head-ancestor-verified",
        action="store_true",
    )
    args = parser.parse_args()
    report = run(
        authorization=args.authorization,
        prior_reviewed_head_sha=args.prior_reviewed_head_sha,
        final_reviewed_head_sha=args.final_reviewed_head_sha,
        source_sha=args.source_sha,
        source_ref=args.source_ref,
        base_sha=args.base_sha,
        base_ref=args.base_ref,
        exact_base_verified=args.exact_base_verified,
        prior_reviewed_head_ancestor_verified=(
            args.prior_reviewed_head_ancestor_verified
        ),
        final_reviewed_head_ancestor_verified=(
            args.final_reviewed_head_ancestor_verified
        ),
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
