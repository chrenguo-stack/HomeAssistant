from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from greenhouse_manager.bootstrap.persistence_migration import (
    AUDIT_DECISION_ID,
    AUDITED_ARTIFACT_ID,
    AUDITED_ARTIFACT_SHA256,
    AUDITED_BASE_SHA,
    AUDITED_SOURCE_HEAD_SHA,
    AUDITED_SOURCE_PR,
    BASELINE_SCHEMA,
    build_persistence_migration_plan,
)


def _synthetic_baseline() -> dict[str, Any]:
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
        "operation_flags": {
            "read_only": True,
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
        },
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    plan = build_persistence_migration_plan(_synthetic_baseline())
    result = {
        "schema": "gh.h0h1.persistence-migration-host-only-result/1",
        "status": "PASS",
        "plan_schema": plan.schema,
        "classification": plan.classification,
        "manager_persistence_mount_required": True,
        "complete_role_layout": len(plan.role_inventory) == 10,
        "runtime_state_classification_required": (
            plan.gates["runtime_hidden_state_classified"] is False
        ),
        "execution_authorized": plan.gates["execution_authorized"],
        "real_backup_authorized": plan.gates["ready_for_real_backup"],
        "restore_authorized": plan.gates["ready_for_restore"],
        "anonymous_closure_authorized": plan.gates["ready_for_anonymous_closure"],
        "production_services_modified": plan.operation_flags[
            "production_services_modified"
        ],
        "network_operation": plan.operation_flags["network_operation"],
        "secret_values_included": plan.operation_flags["secret_values_included"],
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
