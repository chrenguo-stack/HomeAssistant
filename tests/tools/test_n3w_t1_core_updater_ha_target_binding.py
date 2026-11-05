from __future__ import annotations

import hashlib
import json
from pathlib import Path

import n3w_t1_core_updater_v2_common as common

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"
REVIEW = ROOT / "infra/n3w-t1/upgrades/homeassistant-2026.10.4-compatibility-review.json"

EXPECTED_REVIEW_SHA256 = "8b02e9bb0143fc4fc7900c4c0e4c52b27f92725cd41f1f03b82ba67ffb9e0267"
EXPECTED_ARTIFACT_ID = 13391983948
EXPECTED_ARTIFACT_DIGEST = "df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2"
EXPECTED_ARCHIVE_SHA256 = "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
EXPECTED_TARGET_IMAGE = "local/n3w-homeassistant:2026.10.4-5881590f"
EXPECTED_PREDECESSOR_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
EXPECTED_ARTIFACT_SOURCE_HEAD = "fb7cfc857003ace3d368521d76ca2320ba399736"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def test_homeassistant_target_v2_loads_with_frozen_exact_identity() -> None:
    target = common.ComponentTarget.load(TARGET)

    assert target.component == "homeassistant"
    assert target.mutation_profile == "IMAGE_ONLY_V1"
    assert target.target_platform == "linux/arm64"
    assert target.target_image_ref == EXPECTED_TARGET_IMAGE
    assert target.target_archive_sha256 == EXPECTED_ARCHIVE_SHA256
    assert target.expected_predecessor_image_ref == EXPECTED_PREDECESSOR_IMAGE
    assert target.rollback_compatible is True
    assert target.artifact_identity == {
        "artifact_id": EXPECTED_ARTIFACT_ID,
        "artifact_digest_sha256": EXPECTED_ARTIFACT_DIGEST,
        "artifact_name": (
            "n3w-t1-core-updater-homeassistant-2026.10.4-arm64-"
            + EXPECTED_ARTIFACT_SOURCE_HEAD
        ),
    }


def test_homeassistant_target_compatibility_evidence_binds_review() -> None:
    target = common.ComponentTarget.load(TARGET)
    review = json.loads(REVIEW.read_text(encoding="utf-8"))

    assert _canonical_sha256(review) == EXPECTED_REVIEW_SHA256
    evidence = target.compatibility_evidence
    assert evidence["review_evidence_sha256"] == EXPECTED_REVIEW_SHA256
    assert evidence["peer_contracts_compatible"] is True
    assert evidence["persistent_schema_compatible"] is True
    assert evidence["target_source_head"] == EXPECTED_ARTIFACT_SOURCE_HEAD
    assert review["component"] == "homeassistant"
    assert review["mutation_profile"] == "IMAGE_ONLY_V1"
    assert review["predecessor"]["image"] == EXPECTED_PREDECESSOR_IMAGE
    assert review["candidate"]["version"] == "2026.10.4"
    assert review["rollback_compatible_source_review"] is True
    assert review["live_apply_authorized"] is False
