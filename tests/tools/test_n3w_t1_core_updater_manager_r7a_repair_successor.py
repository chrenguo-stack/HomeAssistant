from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPATIBILITY = (
    ROOT
    / "infra/n3w-t1/upgrades/manager-7807271e4c48-compatibility.json"
)
TARGET = ROOT / "infra/n3w-t1/upgrades/manager-7807271e4c48.json"
BASELINE = (
    ROOT
    / "infra/n3w-t1/clean-reference/"
    "r7a-repaired-manager-predecessor-bf38-baseline-20261108.json"
)
PREVIOUS_BASELINE = (
    ROOT
    / "infra/n3w-t1/clean-reference/"
    "r7a-manager-predecessor-baseline-20261107.json"
)

PREDECESSOR_SOURCE = "bf38e388497b0d480f4bd322426e32a98652cf6c"
TARGET_SOURCE = "7807271e4c48161f2fad96a7886fa4c24b038321"
PREDECESSOR_IMAGE = "local/greenhouse-manager:fresh-bf38e388497b"
TARGET_IMAGE = "local/greenhouse-manager:fresh-7807271e4c48"
EXPECTED_DELTA = [
    (
        "host/greenhouse-manager/src/greenhouse_manager/runtime/"
        "n3w_simplified_isolated_mqtt_service.py"
    )
]
COMPATIBILITY_SHA256 = (
    "1b8c6233a1b2de7aa8922df0647bc90e5e9c1a6bef0b6fa4a79cd2ef4230b19c"
)
DERIVED_BASELINE_CANONICAL_SHA256 = (
    "2c0f8a9a1b4634eab2a54a42c29ec9a6c9159972d3069043f49fd3ddd5583bc5"
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_repaired_manager_compatibility_authority_is_self_consistent() -> None:
    document = read(COMPATIBILITY)
    payload = document["payload"]

    assert hashlib.sha256(canonical(payload)).hexdigest() == COMPATIBILITY_SHA256
    assert document["canonical_payload_sha256"] == COMPATIBILITY_SHA256
    assert payload["schema"] == "gh.n3w-t1-core-updater-compatibility/1"
    assert payload["component"] == "manager"
    assert payload["mutation_profile"] == "IMAGE_ONLY_V1"
    assert payload["predecessor_source_head"] == PREDECESSOR_SOURCE
    assert payload["target_source_head"] == TARGET_SOURCE
    assert payload["product_delta_paths"] == EXPECTED_DELTA
    for key in (
        "peer_contracts_compatible",
        "persistent_schema_compatible",
        "rollback_compatible",
    ):
        assert payload[key] is True
    for key in (
        "database_migration_required",
        "config_migration_required",
        "runtime_template_change_required",
        "broker_change_required",
        "homeassistant_change_required",
        "board_change_required",
    ):
        assert payload[key] is False


def test_repaired_manager_product_delta_is_exactly_one_runtime_file() -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "diff",
            "--name-only",
            PREDECESSOR_SOURCE,
            TARGET_SOURCE,
            "--",
            "host/greenhouse-manager/src/greenhouse_manager/runtime",
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    assert result.stdout.splitlines() == EXPECTED_DELTA


def test_repaired_manager_target_binds_successful_rerun_artifact() -> None:
    compatibility = read(COMPATIBILITY)
    target = read(TARGET)

    assert target["schema"] == "gh.n3w-t1-core-updater-target/2"
    assert target["component"] == "manager"
    assert target["mutation_profile"] == "IMAGE_ONLY_V1"
    assert target["target_image_ref"] == TARGET_IMAGE
    assert target["target_platform"] == "linux/arm64"
    assert (
        target["target_archive_sha256"]
        == "9746222b145df33d98056f1349456780377875534b28f633b736360c528a0c67"
    )
    assert target["artifact_identity"] == {
        "artifact_id": 13615963302,
        "artifact_digest_sha256": (
            "72b05593b91c75912e05ccd3b00bc72"
            "af5bd7ec03e39c283d0ce7acfb513fbe7"
        ),
        "artifact_name": (
            "n3w-t1-fresh-exact-arm64-"
            "7807271e4c48161f2fad96a7886fa4c24b038321"
        ),
    }
    assert target["expected_predecessor_image_ref"] == PREDECESSOR_IMAGE
    assert target["rollback_compatible"] is True
    evidence = target["compatibility_evidence"]
    assert evidence["review_evidence_sha256"] == compatibility[
        "canonical_payload_sha256"
    ]
    assert evidence["predecessor_source_head"] == PREDECESSOR_SOURCE
    assert evidence["target_source_head"] == TARGET_SOURCE


def test_repaired_predecessor_baseline_is_only_manager_image_advance() -> None:
    previous = read(PREVIOUS_BASELINE)
    derived = read(BASELINE)

    previous["stack_images"]["manager"] = PREDECESSOR_IMAGE
    assert derived == previous
    assert hashlib.sha256(canonical(derived)).hexdigest() == (
        DERIVED_BASELINE_CANONICAL_SHA256
    )


def test_repair_source_keeps_ota_object_carried_without_migration_surface() -> None:
    source = (
        ROOT
        / "host/greenhouse-manager/src/greenhouse_manager/runtime/"
        "n3w_simplified_isolated_mqtt_service.py"
    ).read_text(encoding="utf-8")
    assert "n3w_t1_ota_enabled=False" in source
    assert "ota_manager=ota_manager" in source
    for forbidden in (
        "sqlite3",
        "CREATE TABLE",
        "ALTER TABLE",
        "DROP TABLE",
    ):
        assert forbidden not in source
