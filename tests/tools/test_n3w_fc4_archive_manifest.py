from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "docs"
    / "development"
    / "archive-manifests"
    / "n3w-fc4-archive-audit-20260820.json"
)
SHA256 = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")


def test_fc4_archive_manifest_is_public_safe_and_machine_checkable() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert document["schema"] == "gh.development-artifact-archive/1"
    assert document["public_raw_evidence_exposed"] is False
    assert document["secret_values_included"] is False
    assert document["pending_live_authorization"]["claimed"] is False
    assert document["pending_live_authorization"]["consumed"] is False

    source = document["authoritative_source"]
    assert GIT_OBJECT_ID.fullmatch(source["main_head"])
    assert GIT_OBJECT_ID.fullmatch(source["main_tree"])
    assert source["ci_failure"] == 0

    runtime = document["p2b3d_runtime_binding"]
    assert runtime["terminal"] == "CLOSED_HEALTHY"
    assert runtime["health"]["pairing_http_schema"] == ("gh.pair.simple-health/1")
    assert runtime["health"]["kf036_recovery_executed"] is False
    assert runtime["health"]["board_access"] is False

    for evidence in runtime["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["secret_values_included_in_public_binding"] is False

    artifacts = document["private_local_artifacts"]
    assert len(artifacts) == 6
    assert all(SHA256.fullmatch(item["sha256"]) for item in artifacts)
    assert all(item["identity_binding"] == "QUARANTINED_UNBOUND" for item in artifacts)
    assert all("board-a" not in item["id"] for item in artifacts)
    assert all("board-b" not in item["id"] for item in artifacts)
    assert all("board-c" not in item["id"] for item in artifacts)
