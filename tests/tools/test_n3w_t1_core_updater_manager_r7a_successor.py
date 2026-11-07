from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPATIBILITY = (
    ROOT
    / "infra/n3w-t1/upgrades/manager-c28130da1fcd-compatibility.json"
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
    assert payload["schema"] == "gh.n3w-t1-core-updater-compatibility/1"
    assert payload["component"] == "manager"
    assert payload["mutation_profile"] == "IMAGE_ONLY_V1"
    assert (
        payload["predecessor_source_head"]
        == "5b32e1ae82104a42f9e4e6907fe44d9172e87615"
    )
    assert (
        payload["target_source_head"]
        == "c28130da1fcdeaa16d61a186d5a27c4c06fe791d"
    )
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
