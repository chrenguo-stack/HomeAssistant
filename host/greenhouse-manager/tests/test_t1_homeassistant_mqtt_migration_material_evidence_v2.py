from __future__ import annotations

import json
from pathlib import Path

import pytest

from greenhouse_manager import t1_homeassistant_mqtt_migration_material_evidence_v2 as module
from greenhouse_manager.t1_homeassistant_mqtt_migration_material_evidence import (
    CandidateMaterial,
)

SYSTEM_ID = "greenhouse"
NODE_ID = "gh-n1-a9f2f8"
TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry"


def _candidate(
    password: str,
    *,
    broker: str | None = None,
    schema: str = "gh.m2.homeassistant-mqtt-update/1",
) -> CandidateMaterial:
    return CandidateMaterial(
        username="ghs_greenhouse_homeassistant",
        password=password,
        client_id="gh-homeassistant-greenhouse",
        port=1883,
        schema=schema,
        broker=broker,
    )


def test_deduplication_excludes_broker_target_and_schema() -> None:
    first = _candidate("secret", broker=None)
    second = _candidate(
        "secret",
        broker="127.0.0.1",
        schema="gh.m2.homeassistant-mqtt-reconfigure-values/1",
    )
    unique = module._deduplicate_materials((first, second))
    assert len(unique) == 1


def test_selects_only_live_authenticated_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale = _candidate("stale")
    current = _candidate("current")

    monkeypatch.setattr(
        module,
        "_correct_identity_probe",
        lambda _runner, material, **_kwargs: material.password == "current",
    )
    selected, unique_count, exact_count = module._select_live_material(
        object(),  # type: ignore[arg-type]
        (stale, current),
        expected_username=current.username,
        expected_client_id=current.client_id,
        expected_retained_topic=TOPIC,
        node_id=NODE_ID,
    )
    assert selected.password == "current"
    assert unique_count == 2
    assert exact_count == 2


def test_rejects_multiple_live_authenticated_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _candidate("one")
    second = _candidate("two")
    monkeypatch.setattr(
        module,
        "_correct_identity_probe",
        lambda *_args, **_kwargs: True,
    )
    with pytest.raises(
        module.HomeAssistantMigrationMaterialEvidenceError,
        match="exactly one live-authenticated",
    ):
        module._select_live_material(
            object(),  # type: ignore[arg-type]
            (first, second),
            expected_username=first.username,
            expected_client_id=first.client_id,
            expected_retained_topic=TOPIC,
            node_id=NODE_ID,
        )


def test_correct_identity_probe_rejects_wrong_retained_identity() -> None:
    material = _candidate("secret")

    class Runner:
        def run(
            self,
            command: tuple[str, ...],
            *,
            input_text: str | None = None,
        ) -> tuple[int, str]:
            assert input_text is not None
            return 0, json.dumps({"node_id": "other"})

    assert (
        module._correct_identity_probe(
            Runner(),
            material,
            expected_retained_topic=TOPIC,
            node_id=NODE_ID,
        )
        is False
    )


def test_build_reports_historical_material_tolerance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = _candidate("current")
    snapshot = {
        "greenhouse-manager": ("m", "mi", "start", 0, "running"),
        "mosquitto": ("b", "bi", "start", 0, "running"),
        "homeassistant": ("h", "hi", "start", 0, "running"),
    }
    state = {
        "clients": [
            {
                "username": selected.username,
                "clientid": selected.client_id,
                "disabled": False,
                "roles": [
                    {
                        "rolename": "gh-service-greenhouse-homeassistant",
                        "priority": 100,
                    }
                ],
            }
        ]
    }
    monkeypatch.setattr(module, "_snapshot", lambda _runner: snapshot)
    monkeypatch.setattr(
        module,
        "_broker_config_and_state",
        lambda _runner: (
            {
                "anonymous_enabled": True,
                "dynamic_security_configured": True,
            },
            state,
            "c" * 64,
            "s" * 64,
        ),
    )
    monkeypatch.setattr(module, "_candidate_files", lambda _roots: [])
    monkeypatch.setattr(
        module,
        "_load_materials",
        lambda _paths: ([_candidate("stale"), selected], 4),
    )
    monkeypatch.setattr(
        module,
        "_select_live_material",
        lambda *_args, **_kwargs: (selected, 2, 2),
    )
    monkeypatch.setattr(
        module,
        "_validate_credentials",
        lambda *_args, **_kwargs: {
            "correct_identity_retained_readable": True,
            "wrong_client_id_rejected": True,
            "password_verified_without_output": True,
        },
    )
    monkeypatch.setattr(
        module,
        "_target_topology",
        lambda *_args, **_kwargs: {
            "selected_target_kind": "loopback",
            "selected_target_fingerprint": "t" * 16,
            "official_config_flow_only": True,
            "direct_storage_edit_forbidden": True,
        },
    )

    report = module.build_homeassistant_mqtt_migration_material_evidence_v2(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        expected_retained_topic=TOPIC,
        search_roots=(tmp_path,),
        runner=object(),  # type: ignore[arg-type]
    )
    material = report["material"]
    assert isinstance(material, dict)
    assert material["historical_or_duplicate_material_tolerated"] is True
    assert material["broker_target_excluded_from_credential_deduplication"] is True
    assert material["live_authenticated_binding_count"] == 1
    assert report["homeassistant_storage_read"] is False
    assert report["ready_for_homeassistant_official_reconfigure_handoff"] is True
