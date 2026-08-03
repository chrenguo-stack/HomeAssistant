from __future__ import annotations

from typing import Any


def history_record(
    *,
    boot_id: str = "boot-00000001",
    seq: int = 1,
    sampled_at: str = "2026-08-03T04:00:00Z",
    temperature: float = 25.0,
) -> dict[str, Any]:
    return {
        "boot_id": boot_id,
        "seq": seq,
        "uptime_ms": seq * 1000,
        "sampled_at": sampled_at,
        "cap_hash": "cap-hash-0001",
        "fw_version": "1.0.0",
        "measurements": {
            "air_temperature_c": temperature,
            "air_humidity_pct": 65.0,
        },
        "quality": {
            "air_temperature_c": "ok",
            "air_humidity_pct": "ok",
        },
        "power": {"source": "battery", "battery_v": 3.9, "low": False},
    }


def history_page(
    *,
    node_id: str = "node-0001",
    batch_id: str = "batch-000001",
    page_index: int = 0,
    page_count: int = 1,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema": "gh.history-replay.batch/1",
        "node_id": node_id,
        "batch_id": batch_id,
        "page_index": page_index,
        "page_count": page_count,
        "records": records or [history_record()],
    }
