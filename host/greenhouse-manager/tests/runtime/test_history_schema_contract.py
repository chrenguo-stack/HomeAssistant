from __future__ import annotations

import json
from importlib.resources import files

from history_samples import history_page, history_record
from jsonschema import Draft202012Validator, FormatChecker


def _schema(name: str) -> dict[str, object]:
    path = files("greenhouse_manager").joinpath(f"schemas/{name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        _schema(name),
        format_checker=FormatChecker(),
    )


def test_batch_schema_accepts_frozen_clock_contracts() -> None:
    trusted = history_page()
    estimated = history_page(
        records=[
            history_record(
                uptime_ms=120_000,
                sampled_at="2026-08-03T04:02:00Z",
                time_quality="estimated",
                time_anchor={
                    "sampled_at": "2026-08-03T04:00:00Z",
                    "uptime_ms": 0,
                },
            )
        ]
    )
    relative = history_page(
        records=[
            history_record(
                sampled_at=None,
                time_quality="relative_only",
                time_anchor=None,
            )
        ]
    )
    validator = _validator("gh.history-replay.batch-1.schema.json")

    assert list(validator.iter_errors(trusted)) == []
    assert list(validator.iter_errors(estimated)) == []
    assert list(validator.iter_errors(relative)) == []


def test_batch_schema_rejects_inconsistent_clock_shapes() -> None:
    value = history_page(
        records=[
            history_record(
                sampled_at=None,
                time_quality="trusted",
                time_anchor=None,
            )
        ]
    )
    assert list(_validator("gh.history-replay.batch-1.schema.json").iter_errors(value))


def test_history_measurement_quality_and_power_contracts_match_canonical_schema() -> None:
    telemetry = _schema("gh.telemetry-1.schema.json")
    history = _schema("gh.history-replay.batch-1.schema.json")
    telemetry_properties = telemetry["properties"]
    record_properties = history["$defs"]["record"]["properties"]

    for field in ("measurements", "quality", "power"):
        assert record_properties[field] == telemetry_properties[field]
    assert history["$defs"]["quality"] == telemetry["$defs"]["quality"]


def test_ack_schema_requires_rejected_ack_to_be_uncommitted() -> None:
    ack = {
        "schema": "gh.history-replay.ack/1",
        "node_id": "node-0001",
        "batch_id": "batch-000001",
        "page_index": 0,
        "page_count": 1,
        "status": "rejected",
        "committed": False,
        "records_total": 1,
        "inserted_records": 0,
        "duplicate_records": 0,
        "next_page_index": 0,
        "processed_at": "2026-08-03T04:05:00Z",
        "reason": "record conflict",
    }
    validator = _validator("gh.history-replay.ack-1.schema.json")
    assert list(validator.iter_errors(ack)) == []

    ack["committed"] = True
    assert list(validator.iter_errors(ack))
