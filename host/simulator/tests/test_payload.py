from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from greenhouse_simulator.payload import build_telemetry


def _schema() -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "protocols/mqtt/schemas/gh.telemetry-1.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_valid_payload_matches_frozen_schema() -> None:
    payload = build_telemetry(
        node_id="node_01HZX7AQ5FJ3",
        boot_id="boot_0123456789abcdef",
        seq=7,
        uptime_ms=12345,
        now=datetime(2026, 7, 10, 6, 0, tzinfo=UTC),
    )

    errors = list(Draft202012Validator(_schema(), format_checker=FormatChecker()).iter_errors(payload))

    assert errors == []
    assert payload["seq"] == 7
    assert payload["sampled_at"] == "2026-07-10T06:00:00Z"


def test_invalid_mode_produces_schema_error() -> None:
    payload = build_telemetry(
        node_id="node_01HZX7AQ5FJ3",
        boot_id="boot_0123456789abcdef",
        seq=8,
        uptime_ms=13000,
        now=datetime(2026, 7, 10, 6, 0, tzinfo=UTC),
        invalid=True,
    )

    errors = list(Draft202012Validator(_schema(), format_checker=FormatChecker()).iter_errors(payload))

    assert errors
    assert payload["measurements"]["air_humidity_pct"] == 140.0
