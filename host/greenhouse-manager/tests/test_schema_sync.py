from __future__ import annotations

import json
from pathlib import Path


def test_packaged_telemetry_schema_matches_protocol_contract() -> None:
    manager_root = Path(__file__).resolve().parents[1]
    repo_root = Path(__file__).resolve().parents[3]

    packaged = manager_root / "src/greenhouse_manager/schemas/gh.telemetry-1.schema.json"
    canonical = repo_root / "protocols/mqtt/schemas/gh.telemetry-1.schema.json"

    assert json.loads(packaged.read_text(encoding="utf-8")) == json.loads(
        canonical.read_text(encoding="utf-8")
    )
