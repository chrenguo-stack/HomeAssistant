from __future__ import annotations

import json
from pathlib import Path

import pytest

from greenhouse_manager.bootstrap.persistence_migration import (
    AUDIT_DECISION_ID,
    AUDITED_ARTIFACT_ID,
    AUDITED_ARTIFACT_SHA256,
    AUDITED_BASE_SHA,
    AUDITED_SOURCE_HEAD_SHA,
    AUDITED_SOURCE_PR,
    BASELINE_SCHEMA,
    DEFAULT_ROLE_LAYOUT,
    PLAN_SCHEMA,
    PersistenceMigrationError,
    build_persistence_migration_plan,
)
from greenhouse_manager.bootstrap.persistence_migration_cli import main


def _baseline() -> dict[str, object]:
    mutation_flags = {
        "anonymous_closure_executed": False,
        "backup_created": False,
        "broker_modified": False,
        "container_created": False,
        "container_modified": False,
        "container_restarted": False,
        "docker_cp_executed": False,
        "file_created": False,
        "file_modified": False,
        "flash_nvs_operation": False,
        "home_assistant_modified": False,
        "manager_modified": False,
        "merge_executed": False,
        "network_probe_executed": False,
        "ready_executed": False,
        "release_tag_deployment": False,
        "restore_executed": False,
        "usb_serial_operation": False,
    }
    return {
        "schema": BASELINE_SCHEMA,
        "status": "PASS",
        "decision_id": AUDIT_DECISION_ID,
        "binding": {
            "source_pr": AUDITED_SOURCE_PR,
            "base_sha": AUDITED_BASE_SHA,
            "source_head_sha": AUDITED_SOURCE_HEAD_SHA,
            "artifact_id": AUDITED_ARTIFACT_ID,
            "artifact_sha256": AUDITED_ARTIFACT_SHA256,
        },
        "operation_flags": {"read_only": True, **mutation_flags},
        "containers": {
            "versions": {"greenhouse-manager": "0.4.64"},
            "targets": {
                name: {"exists": True, "running": True}
                for name in ("greenhouse-manager", "homeassistant", "mosquitto")
            },
        },
        "readiness": {
            "manager_data_mount_present": False,
            "portable_restore_role_inventory_complete": False,
            "ready_for_real_backup": False,
            "ready_for_restore": False,
            "ready_for_anonymous_closure": False,
        },
        "portable_restore_role_presence": {
            "system_identity": False,
            "system_root_key": False,
            "system_ca_certificate": False,
            "system_ca_private_key": False,
            "manager_identity": False,
            "manager_registration_state": False,
            "manager_credential_lifecycle_state": False,
            "manager_retirement_outbox_state": False,
            "broker_dynamic_security_state": True,
            "broker_persistence_state": True,
        },
        "follow_up_codes": ["PORTABLE_RESTORE_ROLE_INVENTORY_INCOMPLETE"],
    }


def test_plan_is_complete_but_execution_remains_blocked() -> None:
    plan = build_persistence_migration_plan(_baseline())

    assert plan.schema == PLAN_SCHEMA
    assert plan.status == "DESIGN_COMPLETE_EXECUTION_BLOCKED"
    assert plan.observed_manager_version == "0.4.64"
    assert plan.target_manager_version == "0.4.98"
    assert plan.target_mount["container_path"] == "/var/lib/greenhouse-manager"
    assert plan.target_mount["root_mode"] == "0700"
    assert plan.target_mount["member_mode"] == "0600"
    assert plan.role_inventory == dict(sorted(DEFAULT_ROLE_LAYOUT.items()))
    assert len(plan.role_inventory) == 10
    assert plan.hidden_runtime_state_classification == "NOT_PROVEN_ABSENT"
    assert plan.gates["runtime_hidden_state_classified"] is False
    assert plan.gates["execution_authorized"] is False
    assert plan.gates["ready_for_real_backup"] is False
    assert plan.gates["ready_for_restore"] is False
    assert plan.gates["ready_for_anonymous_closure"] is False
    assert plan.operation_flags["production_services_modified"] is False
    assert plan.operation_flags["secret_values_included"] is False


def test_binding_or_mutation_drift_fails_closed() -> None:
    wrong_binding = _baseline()
    wrong_binding["binding"]["source_head_sha"] = "0" * 40  # type: ignore[index]
    with pytest.raises(PersistenceMigrationError, match="source_head_sha"):
        build_persistence_migration_plan(wrong_binding)

    mutated = _baseline()
    mutated["operation_flags"]["container_restarted"] = True  # type: ignore[index]
    with pytest.raises(PersistenceMigrationError, match="mutation flags"):
        build_persistence_migration_plan(mutated)


def test_gap_drift_or_missing_broker_role_fails_closed() -> None:
    mounted = _baseline()
    mounted["readiness"]["manager_data_mount_present"] = True  # type: ignore[index]
    with pytest.raises(PersistenceMigrationError, match="gap is no longer present"):
        build_persistence_migration_plan(mounted)

    missing_broker = _baseline()
    missing_broker["portable_restore_role_presence"][  # type: ignore[index]
        "broker_dynamic_security_state"
    ] = False
    with pytest.raises(PersistenceMigrationError, match="Dynamic Security"):
        build_persistence_migration_plan(missing_broker)


def test_cli_can_render_synthetic_host_only_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(_baseline()), encoding="utf-8")

    assert main([str(baseline)], require_exact_audited_file=False) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "DESIGN_COMPLETE_EXECUTION_BLOCKED"
    assert output["gates"]["execution_authorized"] is False
    assert output["operation_flags"]["network_operation"] is False
