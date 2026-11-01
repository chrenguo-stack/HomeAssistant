from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from greenhouse_manager.runtime.history_projection_store import ProjectionStore
from greenhouse_manager.runtime.history_store import HistoryStore

NODE_ID = "node-0001"
SAMPLE_HOUR = "2026-08-03T04:00:00.000Z"
BATCH_ID = "c06b2c-batch-0001"


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    database = Path(os.environ["GH_HISTORY_DB_PATH"])
    evidence = Path(os.environ.get("GH_C06B2C_EVIDENCE_DIR", "/evidence"))
    received_at = datetime(2026, 8, 3, 4, 10, tzinfo=UTC)
    record = {
        "boot_id": "boot-00000001",
        "seq": 1,
        "uptime_ms": 1000,
        "sampled_at": "2026-08-03T04:00:00Z",
        "time_quality": "trusted",
        "time_anchor": None,
        "cap_hash": "cap-hash-0001",
        "fw_version": "1.0.0",
        "measurements": {
            "air_temperature_c": 25.0,
            "air_humidity_pct": 65.0,
        },
        "quality": {
            "air_temperature_c": "ok",
            "air_humidity_pct": "ok",
        },
        "power": {
            "source": "battery",
            "battery_v": 3.9,
            "low": False,
        },
    }
    with HistoryStore(database) as history:
        history.commit_page(
            node_id=NODE_ID,
            batch_id=BATCH_ID,
            page_index=0,
            page_count=1,
            records=[record],
            payload_sha256=hashlib.sha256(BATCH_ID.encode()).hexdigest(),
            received_at=received_at,
        )
    with ProjectionStore(database) as projections:
        job = projections.get_job(NODE_ID, SAMPLE_HOUR)
        if job is None or job.state != "pending" or job.revision != 1:
            raise AssertionError("isolated projection job was not initialized as revision 1")
        document = {
            "schema": "gh.c06b2c.manager-db-init/1",
            "node_id": job.node_id,
            "sample_hour": job.sample_hour,
            "projection_version": job.projection_version,
            "revision": job.revision,
            "state": job.state,
            "record_count": 1,
            "secret_values_included": False,
            "production_state_modified": False,
        }
    _write_json(evidence / "manager-db-init.json", document)


if __name__ == "__main__":
    main()
