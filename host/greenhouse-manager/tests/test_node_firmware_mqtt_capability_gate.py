from __future__ import annotations

import pytest
from greenhouse_manager import node_firmware_mqtt_capability_gate as module


def _evidence() -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-node-synchronized-reconnect-evidence/1",
        "status": "node_synchronized_reconnect_evidence_succeeded",
        "repository_sha": "9b70576bcac47c9e3f95cedfd467652b517c1b11",
        "manager_source_version": "0.4.87",
        "system_id": "greenhouse",
        "node_id": "gh-n1-a9f2f8",
        "generation": 1,
        "read_only": True,
        "evidence_verified": True,
        "anonymous_enabled": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "protected_services_stable": True,
        "broker_config_and_state_stable": True,
        "homeassistant_storage_read": False,
        "homeassistant_storage_written": False,
        "node_credentials_delivered": False,
        "production_execution_invoked": False,
        "production_manager_upgraded": False,
        "current_services_modified": False,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
        "broker": {
            "anonymous_enabled": True,
            "dynamic_security_configured": True,
            "state_private": True,
            "state_runtime_owner_bound": True,
            "state_single_hardlink": True,
            "config_sha256": "8fbd8cd18259ac071d602ffaf85ecdb4033aed57bf4c0889801ccabf403c2c84",
            "state_sha256": "0d21faa86f4d3f47d64a027de5d2bf524803f5a1d4ecd5d3b070996fcf416320",
        },
        "node_identity": {
            "identity_exact": True,
            "role_exact": True,
            "acl_exact": True,
            "default_access_exact": True,
            "identity_preconfigured": True,
            "credential_material_present": True,
            "identity_disabled": False,
            "acl_count": 10,
        },
        "continuity": {
            "canonical_retained_continuous": True,
            "availability_retained_continuous": True,
            "discovery_retained_continuous": True,
            "existing_entity_identity_continuous": True,
            "fresh_ingress_observed": True,
            "fresh_ingress_after_synchronized_reconnect": True,
            "component_count": 19,
        },
        "node_runtime": {
            "observer_connection_log_visible": True,
            "synchronized_reconnect_observed": True,
            "runtime_connection_anonymous": True,
            "legacy_runtime_client_id_differs_from_target": True,
            "authenticated_node_connection_observed": False,
            "observed_client_id_matches_target": False,
            "exact_client_id_connection_observed": False,
            "observed_client_id_fingerprint": "97b32e78cb7b4ad3",
        },
    }


def test_builds_firmware_capability_plan_from_v96_evidence() -> None:
    report = module.build_node_firmware_mqtt_capability_gate_plan(
        _evidence(),
        repository_sha="9b70576bcac47c9e3f95cedfd467652b517c1b11",
        manager_source_version="0.4.87",
    )

    assert report["status"] == "node_firmware_mqtt_capability_gate_plan_created"
    assert report["candidate_identity"]["username"] == "ghn_gh-n1-a9f2f8"
    assert report["candidate_identity"]["client_id"] == "gh-n1-a9f2f8"
    assert report["legacy_runtime"]["client_id_differs_from_target"] is True
    assert report["legacy_runtime"]["raw_client_id_included"] is False
    assert report["continuity_baseline"]["component_count"] == 19
    assert report["requirement_count"] == 8
    assert report["ready_for_candidate_firmware_design"] is True
    assert report["ready_for_candidate_firmware_build"] is False
    assert report["ready_for_node_credential_generation"] is False
    assert report["anonymous_closure_enabled"] is False
    assert report["secret_values_included"] is False


def test_rejects_unsynchronized_evidence_schema() -> None:
    evidence = _evidence()
    evidence["schema"] = "gh.m2.t1-node-mqtt-migration-readiness-evidence/1"

    with pytest.raises(
        module.NodeFirmwareMqttCapabilityGateError,
        match="not synchronized V96",
    ):
        module.build_node_firmware_mqtt_capability_gate_plan(evidence)


def test_rejects_authenticated_runtime_before_authorization() -> None:
    evidence = _evidence()
    runtime = evidence["node_runtime"]
    assert isinstance(runtime, dict)
    runtime["authenticated_node_connection_observed"] = True

    with pytest.raises(
        module.NodeFirmwareMqttCapabilityGateError,
        match="authenticated_node_connection_observed must be false",
    ):
        module.build_node_firmware_mqtt_capability_gate_plan(evidence)


def test_rejects_legacy_runtime_that_already_matches_target() -> None:
    evidence = _evidence()
    runtime = evidence["node_runtime"]
    assert isinstance(runtime, dict)
    runtime["legacy_runtime_client_id_differs_from_target"] = False
    runtime["observed_client_id_matches_target"] = True
    runtime["exact_client_id_connection_observed"] = True

    with pytest.raises(
        module.NodeFirmwareMqttCapabilityGateError,
        match="legacy_runtime_client_id_differs_from_target must be true",
    ):
        module.build_node_firmware_mqtt_capability_gate_plan(evidence)


def test_rejects_continuity_drift() -> None:
    evidence = _evidence()
    continuity = evidence["continuity"]
    assert isinstance(continuity, dict)
    continuity["discovery_retained_continuous"] = False

    with pytest.raises(
        module.NodeFirmwareMqttCapabilityGateError,
        match="discovery_retained_continuous must be true",
    ):
        module.build_node_firmware_mqtt_capability_gate_plan(evidence)


def test_rejects_repository_binding_drift() -> None:
    with pytest.raises(
        module.NodeFirmwareMqttCapabilityGateError,
        match="repository SHA binding has drifted",
    ):
        module.build_node_firmware_mqtt_capability_gate_plan(
            _evidence(),
            repository_sha="0" * 40,
        )


def test_requirements_are_stable_and_secret_free() -> None:
    requirements = module.firmware_capability_requirements()

    assert len(requirements) == 8
    assert {item.requirement_id for item in requirements} == {
        "explicit_authenticated_identity",
        "private_candidate_and_fallback_slots",
        "bounded_authenticated_failure_fallback",
        "candidate_preserved_after_fallback",
        "local_operation_independent",
        "secret_redaction",
        "power_and_network_fault_recovery",
        "retired_generation_erasure",
    }
    assert all(item.isolated_test_required for item in requirements)
    assert all(item.real_board_test_required for item in requirements)
    assert not any("password=" in item.description for item in requirements)
