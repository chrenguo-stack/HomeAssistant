from __future__ import annotations

import json
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker

from history_samples import history_page


def _validator(name: str) -> Draft202012Validator:
    path = files("greenhouse_manager").joinpath(f"schemas/{name}")
    return Draft202012Validator(
        json.loads(path.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    )


def test_batch_schema_accepts_frozen_v1_contract() -> None:
    errors = list(
        _validator("gh.history-replay.batch-1.schema.json").iter_errors(history_page())
    )
    assert errors == []


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
        "next_page_index": None,
        "processed_at": "2026-08-03T04:05:00Z",
        "reason": "record conflict",
    }
    validator = _validator("gh.history-replay.ack-1.schema.json")
    assert list(validator.iter_errors(ack)) == []

    ack["committed"] = True
    assert list(validator.iter_errors(ack))
