from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from greenhouse_manager.runtime.history_replay import HistoryReplayProcessor
from greenhouse_manager.runtime.history_store import HistoryStore


def _record(*, temperature: float = 25.0) -> dict[str, Any]:
    return {
        "boot_id": "boot-00000001",
        "seq": 1,
        "uptime_ms": 1000,
        "sampled_at": "2026-08-03T04:00:00Z",
        "cap_hash": "cap-hash-0001",
        "fw_version": "1.0.0",
        "measurements": {"air_temperature_c": temperature},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "battery", "battery_v": 3.9, "low": False},
    }


def _page(*, batch_id: str, temperature: float = 25.0) -> bytes:
    value = {
        "schema": "gh.history-replay.batch/1",
        "node_id": "node-0001",
        "batch_id": batch_id,
        "page_index": 0,
        "page_count": 1,
        "records": [_record(temperature=temperature)],
    }
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def run(
    *,
    authorization: str = "local-host-only",
    source_sha: str = "local",
    source_ref: str = "local",
    base_sha: str = "local",
    base_ref: str = "local",
    exact_base_verified: bool = False,
) -> dict[str, Any]:
    topic = "gh/v1/system-001/ingress/node/node-0001/history"
    now = datetime(2026, 8, 3, 4, 5, tzinfo=UTC)
    with tempfile.TemporaryDirectory(prefix="c06-host-only-") as directory:
        path = Path(directory) / "manager-state.sqlite3"
        with HistoryStore(path) as store:
            processor = HistoryReplayProcessor(system_id="system-001", store=store)
            accepted = processor.process(
                topic, _page(batch_id="batch-000001"), received_at=now
            )
            accepted_record_count = store.count_records()
            accepted_projection_hours = store.pending_projection_hours()

        with HistoryStore(path) as reopened:
            processor = HistoryReplayProcessor(system_id="system-001", store=reopened)
            duplicate = processor.process(
                topic, _page(batch_id="batch-000001"), received_at=now
            )
            collision = processor.process(
                topic,
                _page(batch_id="batch-000002", temperature=31.0),
                received_at=now,
            )
            final_record_count = reopened.count_records()

    ack_topics = [message.topic for message in (*accepted.messages, *duplicate.messages)]
    report = {
        "schema": "gh.c06-history-replay-host-only-report/1",
        "authorization": authorization,
        "source_sha": source_sha,
        "source_ref": source_ref,
        "base_sha": base_sha,
        "base_ref": base_ref,
        "exact_base_verified": exact_base_verified,
        "accepted_status": accepted.status,
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
        "ack_retain_values": [message.retain for message in accepted.messages],
        "canonical_topics_emitted": [topic for topic in ack_topics if "/state/" in topic],
        "network_used": False,
        "production_state_modified": False,
    }
    expected = {
        "accepted_status": "accepted",
        "duplicate_after_restart_status": "duplicate",
        "collision_status": "rejected",
        "collision_committed": False,
        "collision_next_page_index": 0,
        "accepted_record_count": 1,
        "final_record_count": 1,
        "projection_hour_count": 1,
        "ack_retain_values": [False],
        "canonical_topics_emitted": [],
        "network_used": False,
        "production_state_modified": False,
    }
    for key, value in expected.items():
        if report[key] != value:
            raise RuntimeError(f"host-only assertion failed: {key}={report[key]!r}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization", default="local-host-only")
    parser.add_argument("--source-sha", default="local")
    parser.add_argument("--source-ref", default="local")
    parser.add_argument("--base-sha", default="local")
    parser.add_argument("--base-ref", default="local")
    parser.add_argument("--exact-base-verified", action="store_true")
    args = parser.parse_args()
    report = run(
        authorization=args.authorization,
        source_sha=args.source_sha,
        source_ref=args.source_ref,
        base_sha=args.base_sha,
        base_ref=args.base_ref,
        exact_base_verified=args.exact_base_verified,
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
