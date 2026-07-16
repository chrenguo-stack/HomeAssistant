from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager import t1_homeassistant_mqtt_migration_material_evidence as module

SYSTEM_ID = "greenhouse"
NODE_ID = "gh-n1-a9f2f8"
TOPIC = f"gh/v1/{SYSTEM_ID}/state/{NODE_ID}/telemetry"
REPOSITORY_SHA = "a" * 40


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.inputs: list[str | None] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]:
        self.commands.append(command)
        self.inputs.append(input_text)
        return 1, "unexpected command"


def _material(path: Path, *, password: str = "p" * 43) -> None:
    path.parent.mkdir(parents=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_text(
        json.dumps(
            {
                "schema": "gh.m2.homeassistant-mqtt-update/1",
                "automatic_apply": False,
                "operation": "update_existing_mqtt_config_entry",
                "preserve_discovery": True,
                "username": "ghs_greenhouse_homeassistant",
                "password": password,
                "required_client_id": "gh-homeassistant-greenhouse",
                "port": 1883,
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)


def _patch_live(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = {
        "greenhouse-manager": ("m", "mi", "start", 0, "running"),
        "mosquitto": ("b", "bi", "start", 0, "running"),
        "homeassistant": ("h", "hi", "start", 0, "running"),
    }
    state = {
        "clients": [
            {
                "username": "ghs_greenhouse_homeassistant",
                "clientid": "gh-homeassistant-greenhouse",
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
                "config_sha256": "c" * 64,
                "state_sha256": "s" * 64,
            },
            state,
            "c" * 64,
            "s" * 64,
        ),
    )
    monkeypatch.setattr(
        module,
        "_validate_credentials",
        lambda *_args, **_kwargs: {
            "correct_identity_retained_readable": True,
            "wrong_client_id_rejected": True,
            "password_verified_without_output": True,
            "credential_binding_fingerprint": "f" * 16,
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


def test_verifies_one_unique_private_binding_without_storage_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _material(tmp_path / "handoff" / "mqtt-update.json")
    _patch_live(monkeypatch)
    runner = FakeRunner()

    report = module.build_homeassistant_mqtt_migration_material_evidence(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        expected_retained_topic=TOPIC,
        search_roots=(tmp_path,),
        runner=runner,
        repository_sha=REPOSITORY_SHA,
        manager_source_version="0.4.82",
    )

    assert report["material_evidence_verified"] is True
    assert report["ready_for_homeassistant_official_reconfigure_handoff"] is True
    assert report["ready_for_live_apply"] is False
    assert report["homeassistant_storage_read"] is False
    assert report["homeassistant_storage_written"] is False
    assert report["authorization_created"] is False
    assert report["production_execution_invoked"] is False
    assert report["node_credentials_delivered"] is False
    serialized = json.dumps(report)
    assert "p" * 43 not in serialized
    assert "ghs_greenhouse_homeassistant" not in serialized
    assert "gh-homeassistant-greenhouse" not in serialized
    assert not any(".storage" in " ".join(command) for command in runner.commands)


def test_deduplicates_identical_material_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _material(tmp_path / "one" / "mqtt-update.json")
    _material(tmp_path / "two" / "reconfigure-values.json")
    second = tmp_path / "two" / "reconfigure-values.json"
    document: dict[str, Any] = {
        "schema": "gh.m2.homeassistant-mqtt-reconfigure-values/1",
        "official_config_flow_only": True,
        "preserve_discovery": True,
        "username": "ghs_greenhouse_homeassistant",
        "password": "p" * 43,
        "client_id": "gh-homeassistant-greenhouse",
        "port": 1883,
    }
    second.write_text(json.dumps(document), encoding="utf-8")
    second.chmod(0o600)
    _patch_live(monkeypatch)

    report = module.build_homeassistant_mqtt_migration_material_evidence(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        expected_retained_topic=TOPIC,
        search_roots=(tmp_path,),
        runner=FakeRunner(),
    )
    material = report["material"]
    assert isinstance(material, dict)
    assert material["valid_candidate_file_count"] == 2
    assert material["unique_credential_binding_count"] == 1


def test_rejects_conflicting_exact_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _material(tmp_path / "one" / "mqtt-update.json", password="a" * 43)
    _material(tmp_path / "two" / "mqtt-update.json", password="b" * 43)
    _patch_live(monkeypatch)

    with pytest.raises(
        module.HomeAssistantMigrationMaterialEvidenceError,
        match="exactly one unique",
    ):
        module.build_homeassistant_mqtt_migration_material_evidence(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            expected_retained_topic=TOPIC,
            search_roots=(tmp_path,),
            runner=FakeRunner(),
        )


def test_ignores_public_candidate_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "public" / "mqtt-update.json"
    _material(path)
    path.chmod(0o644)
    _patch_live(monkeypatch)

    with pytest.raises(
        module.HomeAssistantMigrationMaterialEvidenceError,
        match="exactly one unique",
    ):
        module.build_homeassistant_mqtt_migration_material_evidence(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            expected_retained_topic=TOPIC,
            search_roots=(tmp_path,),
            runner=FakeRunner(),
        )


def test_credential_probe_requires_client_id_enforcement() -> None:
    material = module.CandidateMaterial(
        username="ghs_greenhouse_homeassistant",
        password="secret",
        client_id="gh-homeassistant-greenhouse",
        port=1883,
        schema="gh.m2.homeassistant-mqtt-update/1",
        broker=None,
    )

    class ProbeRunner:
        def run(
            self,
            command: tuple[str, ...],
            *,
            input_text: str | None = None,
        ) -> tuple[int, str]:
            assert input_text is not None
            return 0, json.dumps({"node_id": NODE_ID})

    with pytest.raises(
        module.HomeAssistantMigrationMaterialEvidenceError,
        match="client ID binding is not enforced",
    ):
        module._validate_credentials(
            ProbeRunner(),
            material,
            expected_username=material.username,
            expected_client_id=material.client_id,
            expected_retained_topic=TOPIC,
            node_id=NODE_ID,
        )


def test_invalid_repository_sha_fails_before_runtime(tmp_path: Path) -> None:
    runner = FakeRunner()
    with pytest.raises(ValueError, match="40-character"):
        module.build_homeassistant_mqtt_migration_material_evidence(
            system_id=SYSTEM_ID,
            node_id=NODE_ID,
            expected_retained_topic=TOPIC,
            search_roots=(tmp_path,),
            runner=runner,
            repository_sha="bad",
        )
    assert runner.commands == []
