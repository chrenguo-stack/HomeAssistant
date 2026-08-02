from __future__ import annotations

import pytest

from greenhouse_manager.bootstrap.legacy_adoption import (
    ADOPTION_CONTRACT_DECISION_ID,
    CLASSIFICATION_DECISION_ID,
    CLASSIFICATION_RESULT_SHA256,
    CLASSIFICATION_SCHEMA,
    CLASSIFIED_ARTIFACT_ID,
    CLASSIFIED_ARTIFACT_SHA256,
    CLASSIFIED_BASE_SHA,
    CLASSIFIED_BASELINE_RESULT_SHA256,
    CLASSIFIED_BASELINE_SCRIPT_SHA256,
    CLASSIFIED_SOURCE_HEAD_SHA,
    CLASSIFIED_SOURCE_PR,
    LegacyAdoptionError,
    build_legacy_adoption_plan,
    system_id_fingerprint,
)
from greenhouse_manager.bootstrap.portable_restore import REQUIRED_ROLES

LEGACY_SYSTEM_ID = "greenhouse-host-only-legacy"


def classification_result() -> dict[str, object]:
    fingerprint = system_id_fingerprint(LEGACY_SYSTEM_ID)
    return {
        "schema": CLASSIFICATION_SCHEMA,
        "status": "PASS",
        "decision_id": CLASSIFICATION_DECISION_ID,
        "classification": "LEGACY_RUNTIME_OR_CONFIGURATION_STATE_PRESENT",
        "runtime_hidden_state_classified": True,
        "legacy_import_or_adoption_required": True,
        "new_system_initialization_permitted_by_this_decision": False,
        "candidate_root_preparation_permitted_by_this_decision": False,
        "real_backup_permitted_by_this_decision": False,
        "restore_permitted_by_this_decision": False,
        "anonymous_closure_permitted_by_this_decision": False,
        "deployment_permitted_by_this_decision": False,
        "baseline_drift": [],
        "blocked_reasons": ["EXPLICIT_LEGACY_ADOPTION_OR_IMPORT_REQUIRED"],
        "binding": {
            "source_pr": CLASSIFIED_SOURCE_PR,
            "base_sha": CLASSIFIED_BASE_SHA,
            "source_head_sha": CLASSIFIED_SOURCE_HEAD_SHA,
            "artifact_id": CLASSIFIED_ARTIFACT_ID,
            "artifact_sha256": CLASSIFIED_ARTIFACT_SHA256,
            "baseline_result_sha256": CLASSIFIED_BASELINE_RESULT_SHA256,
            "baseline_script_sha256": CLASSIFIED_BASELINE_SCRIPT_SHA256,
        },
        "operation_flags": {
            "read_only": True,
            "anonymous_closure_executed": False,
            "backup_created": False,
            "board_operation": False,
            "broker_modified": False,
            "candidate_root_created": False,
            "container_created": False,
            "container_modified": False,
            "container_restarted": False,
            "docker_cp_executed": False,
            "file_created_on_t1": False,
            "file_modified_on_t1": False,
            "flash_nvs_operation": False,
            "home_assistant_modified": False,
            "identity_generated": False,
            "manager_modified": False,
            "merge_executed": False,
            "network_probe_executed": False,
            "ready_executed": False,
            "release_tag_deployment": False,
            "restore_executed": False,
            "usb_serial_operation": False,
        },
        "evidence": {
            "container_state_scan": {
                "available": True,
                "scan_complete": True,
                "candidate_count": 0,
                "identity_document_count": 0,
                "recognized_manager_row_count": 0,
                "scanned_file_count": 0,
                "errors": [],
                "open_state_fds": [],
            },
            "container_writable_layer": {
                "available": True,
                "state_related_entries": [],
                "truncated": False,
            },
            "log_signals": {
                "signal_counts": {
                    "accepted_telemetry": 8,
                    "pairing": 1,
                    "registration": 0,
                    "credential": 0,
                    "retirement": 0,
                    "outbox": 0,
                }
            },
            "manager_container": {
                "running": True,
                "state": "running",
                "version": "0.4.64",
                "mounts": [
                    {
                        "destination": "/run/secrets/gh_manager_mqtt_password",
                        "type": "bind",
                        "rw": False,
                    }
                ],
                "environment": {
                    "state_related_keys": ["GH_SYSTEM_ID"],
                    "secret_bearing_value_count": 0,
                    "non_secret_state_values": {
                        "GH_SYSTEM_ID": {
                            "present": True,
                            "fingerprint": fingerprint,
                        }
                    },
                },
            },
        },
    }


def test_plan_preserves_existing_system_id_and_blocks_execution() -> None:
    plan = build_legacy_adoption_plan(
        classification_result(),
        source_sha256=CLASSIFICATION_RESULT_SHA256,
    )

    assert plan.status == "CONTRACT_COMPLETE_EXECUTION_BLOCKED"
    assert plan.decision_id == ADOPTION_CONTRACT_DECISION_ID
    assert plan.source_system_id_fingerprint == system_id_fingerprint(LEGACY_SYSTEM_ID)
    assert plan.adoption_contract["preserve_existing_system_id"] is True
    assert plan.adoption_contract["generate_new_system_id"] is False
    assert plan.manager_state_contract["business_rows_initial"] == 0
    assert plan.manager_state_contract["legacy_rows_reconstructed_from_logs"] is False
    assert set(plan.role_inventory) == REQUIRED_ROLES
    assert plan.gates["raw_legacy_system_id_loaded"] is False
    assert plan.gates["execution_authorized"] is False
    assert plan.operation_flags["production_services_modified"] is False


def test_binding_or_mutation_drift_fails_closed() -> None:
    wrong_binding = classification_result()
    wrong_binding["binding"]["artifact_id"] = 1  # type: ignore[index]
    with pytest.raises(LegacyAdoptionError, match="artifact_id"):
        build_legacy_adoption_plan(wrong_binding)

    mutated = classification_result()
    mutated["operation_flags"]["candidate_root_created"] = True  # type: ignore[index]
    with pytest.raises(LegacyAdoptionError, match="mutation flags"):
        build_legacy_adoption_plan(mutated)


def test_structured_state_or_continuity_drift_fails_closed() -> None:
    stateful = classification_result()
    stateful["evidence"]["container_state_scan"][  # type: ignore[index]
        "recognized_manager_row_count"
    ] = 1
    with pytest.raises(LegacyAdoptionError, match="recognized_manager_row_count"):
        build_legacy_adoption_plan(stateful)

    inactive = classification_result()
    inactive["evidence"]["log_signals"]["signal_counts"][  # type: ignore[index]
        "accepted_telemetry"
    ] = 0
    with pytest.raises(LegacyAdoptionError, match="continuity"):
        build_legacy_adoption_plan(inactive)
