from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPATIBILITY = (
    ROOT
    / "infra/n3w-t1/upgrades/manager-bf38e388497b-compatibility.json"
)
TARGET = ROOT / "infra/n3w-t1/upgrades/manager-bf38e388497b.json"
BASELINE = (
    ROOT
    / "infra/n3w-t1/clean-reference/r7a-manager-predecessor-baseline-20261107.json"
)

EXPECTED_DELTA = [
    "host/greenhouse-manager/src/greenhouse_manager/runtime/config.py",
    "host/greenhouse-manager/src/greenhouse_manager/runtime/ha_update.py",
    "host/greenhouse-manager/src/greenhouse_manager/runtime/mqtt_service.py",
    "host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_manager_runtime_wiring.py",
    "host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_isolated_mqtt_service.py",
    "host/greenhouse-manager/src/greenhouse_manager/runtime/t1_ota_ipc.py",
    "host/greenhouse-manager/src/greenhouse_manager/runtime/t1_ota_manager.py",
    "host/greenhouse-manager/src/greenhouse_manager/runtime/topics.py",
]

PREDECESSOR_SOURCE = "5b32e1ae82104a42f9e4e6907fe44d9172e87615"
TARGET_SOURCE = "bf38e388497b0d480f4bd322426e32a98652cf6c"
PREDECESSOR_IMAGE = "local/greenhouse-manager:fresh-5b32e1ae8210"
TARGET_IMAGE = "local/greenhouse-manager:fresh-bf38e388497b"
P4_BASELINE_SHA256 = (
    "78c3b0b58ad39cf887689658bec90c8466d30a93d58830b0289f1463dafad868"
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_r7a_manager_compatibility_authority_is_self_consistent() -> None:
    document = json.loads(COMPATIBILITY.read_text(encoding="utf-8"))
    payload = document["payload"]

    assert hashlib.sha256(canonical(payload)).hexdigest() == document[
        "canonical_payload_sha256"
    ]
    assert (
        document["canonical_payload_sha256"]
        == "d898d0439f628522343f8d367d179bf42ae43a9868be1d52c2cb28534a3824b0"
    )
    assert payload["schema"] == "gh.n3w-t1-core-updater-compatibility/1"
    assert payload["component"] == "manager"
    assert payload["mutation_profile"] == "IMAGE_ONLY_V1"
    assert payload["predecessor_source_head"] == PREDECESSOR_SOURCE
    assert payload["target_source_head"] == TARGET_SOURCE
    assert payload["product_delta_paths"] == EXPECTED_DELTA
    assert payload["peer_contracts_compatible"] is True
    assert payload["persistent_schema_compatible"] is True
    assert payload["database_migration_required"] is False
    assert payload["config_migration_required"] is False
    assert payload["runtime_template_change_required"] is False
    assert payload["broker_change_required"] is False
    assert payload["homeassistant_change_required"] is False
    assert payload["board_change_required"] is False
    assert payload["rollback_compatible"] is True


def test_r7a_manager_target_binds_exact_artifact_and_compatibility() -> None:
    compatibility = json.loads(COMPATIBILITY.read_text(encoding="utf-8"))
    target = json.loads(TARGET.read_text(encoding="utf-8"))

    assert target["schema"] == "gh.n3w-t1-core-updater-target/2"
    assert target["component"] == "manager"
    assert target["mutation_profile"] == "IMAGE_ONLY_V1"
    assert target["target_image_ref"] == TARGET_IMAGE
    assert target["target_platform"] == "linux/arm64"
    assert (
        target["target_archive_sha256"]
        == "4c4492ef5008a968b2553240b3fde97912eb3ae862604ae492e5a639a93db008"
    )
    assert target["artifact_identity"] == {
        "artifact_id": 13564472128,
        "artifact_digest_sha256": (
            "eca37ec38d29c488e271b16de11af2d13b18ca2867694e92ccc4b5366cea3dd8"
        ),
        "artifact_name": (
            "n3w-t1-fresh-exact-arm64-"
            "bf38e388497b0d480f4bd322426e32a98652cf6c"
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


def test_r7a_manager_baseline_matches_p4_current_stack_authority() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    assert hashlib.sha256(canonical(baseline)).hexdigest() == P4_BASELINE_SHA256
    assert baseline["schema"] == "gh.n3w-t1-core-updater-baseline/1"
    assert baseline["stack_images"] == {
        "broker": "local/n3w-mosquitto:2.1.2-3184566d",
        "homeassistant": "local/n3w-homeassistant:2026.10.0-0c73235a",
        "manager": PREDECESSOR_IMAGE,
    }
    assert baseline["image_binding_modes"] == {
        "broker": "legacy_static",
        "homeassistant": "legacy_static",
        "manager": "dynamic",
    }


def test_r7a_manager_successor_is_default_off_and_has_no_db_migration_surface() -> None:
    config = (
        ROOT
        / "host/greenhouse-manager/src/greenhouse_manager/runtime/config.py"
    ).read_text(encoding="utf-8")
    wiring = (
        ROOT
        / "host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_manager_runtime_wiring.py"
    ).read_text(encoding="utf-8")

    assert "n3w_t1_ota_enabled: bool = False" in config
    assert '"GH_N3W_T1_OTA_ENABLED",\n                False,' in config
    assert (
        'if not getattr(settings, "n3w_t1_ota_enabled", False):\n'
        "        return None"
        in wiring
    )

    ota_sources = [
        ROOT
        / "host/greenhouse-manager/src/greenhouse_manager/runtime/ha_update.py",
        ROOT
        / "host/greenhouse-manager/src/greenhouse_manager/runtime/t1_ota_ipc.py",
        ROOT
        / "host/greenhouse-manager/src/greenhouse_manager/runtime/t1_ota_manager.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in ota_sources)
    for forbidden in (
        "sqlite3",
        "CREATE TABLE",
        "ALTER TABLE",
        "DROP TABLE",
    ):
        assert forbidden not in combined
