from __future__ import annotations

import json
import secrets
from importlib.resources import files
from pathlib import Path
from typing import Any

import jsonschema

from .node_mqtt_board_lab_common import (
    OBSERVATION_SCHEMA,
    REQUIRED_CASE_IDS,
    SCHEMA,
    SUMMARY_SCHEMA,
    _canonical_json,
    _fingerprint,
    _private_write,
    _require,
)


def init_fault_matrix(output: str | Path, *, run_id: str | None = None) -> dict[str, object]:
    output_path = Path(output).expanduser().resolve()
    _require(output_path.parent.exists(), "fault-matrix output parent does not exist")
    _require(not output_path.exists(), "fault-matrix output already exists")
    run_id = run_id or secrets.token_hex(8)
    _require(len(run_id) >= 8, "run ID is too short")
    documents = []
    for case_id in REQUIRED_CASE_IDS:
        documents.append(
            {
                "schema": OBSERVATION_SCHEMA,
                "run_id": run_id,
                "case_id": case_id,
                "outcome": "blocked",
                "profile_before": "unknown",
                "profile_after": "unknown",
                "phase_after": "unknown",
                "mqtt_connected_after": False,
                "candidate_failure_count": 0,
                "observation_success_count": 0,
                "ready_for_commit": False,
                "local_functions": {
                    "lcd": "not_checked",
                    "sensors": "not_checked",
                    "rs485": "not_checked",
                    "local_calculations": "not_checked",
                    "low_power_protection": "not_checked",
                },
                "evidence_fingerprints": [],
                "operator_observed": False,
                "production_endpoint_used": False,
                "production_identity_used": False,
                "production_execution_invoked": False,
                "current_services_modified": False,
                "homeassistant_storage_read": False,
                "node_credentials_delivered": False,
                "anonymous_closure_enabled": False,
                "secret_values_included": False,
                "secure_erase_claimed": False,
                "notes_redacted": True,
            }
        )
    encoded = "".join(_canonical_json(document) + "\n" for document in documents)
    _private_write(output_path, encoded)
    return {
        "schema": SCHEMA,
        "status": "node_mqtt_board_lab_fault_matrix_initialized",
        "run_id": run_id,
        "required_case_count": len(REQUIRED_CASE_IDS),
        "matrix_fingerprint": _fingerprint(encoded),
        "matrix_private": output_path.stat().st_mode & 0o777 == 0o600,
        "secret_values_included": False,
        "source_paths_included": False,
        "production_execution_invoked": False,
        "current_services_modified": False,
        "homeassistant_storage_read": False,
        "node_credentials_delivered": False,
        "anonymous_closure_enabled": False,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
        "ready_for_node_credential_generation": False,
    }


def _observation_schema() -> dict[str, Any]:
    schema_path = files("greenhouse_manager").joinpath("schemas/node_mqtt_board_lab_observation_v1.json")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def summarize_fault_matrix(records: str | Path) -> dict[str, object]:
    records_path = Path(records).expanduser().resolve()
    documents = [
        json.loads(line)
        for line in records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    _require(documents, "fault-matrix record set is empty")
    validator = jsonschema.Draft202012Validator(_observation_schema())
    for document in documents:
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        message = errors[0].message if errors else ""
        _require(not errors, f"fault-matrix record failed schema validation: {message}")
    run_ids = {str(document["run_id"]) for document in documents}
    _require(len(run_ids) == 1, "fault-matrix records contain multiple run IDs")
    by_case: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for document in documents:
        case_id = str(document["case_id"])
        if case_id in by_case:
            duplicates.add(case_id)
        by_case[case_id] = document
    missing = [case_id for case_id in REQUIRED_CASE_IDS if case_id not in by_case]
    failed = [
        case_id
        for case_id in REQUIRED_CASE_IDS
        if case_id in by_case and by_case[case_id]["outcome"] != "pass"
    ]
    unsafe = [
        case_id
        for case_id, document in by_case.items()
        if document["production_endpoint_used"]
        or document["production_identity_used"]
        or document["production_execution_invoked"]
        or document["current_services_modified"]
        or document["homeassistant_storage_read"]
        or document["node_credentials_delivered"]
        or document["anonymous_closure_enabled"]
        or document["secret_values_included"]
        or document["secure_erase_claimed"]
        or not document["notes_redacted"]
    ]
    evidence_missing = [
        case_id
        for case_id in REQUIRED_CASE_IDS
        if case_id in by_case
        and (
            not by_case[case_id]["operator_observed"]
            or not by_case[case_id]["evidence_fingerprints"]
        )
    ]
    succeeded = not missing and not failed and not unsafe and not evidence_missing and not duplicates
    encoded = records_path.read_text(encoding="utf-8")
    return {
        "schema": SUMMARY_SCHEMA,
        "status": (
            "node_mqtt_board_lab_fault_matrix_succeeded"
            if succeeded
            else "node_mqtt_board_lab_fault_matrix_incomplete"
        ),
        "run_id": next(iter(run_ids)),
        "required_case_count": len(REQUIRED_CASE_IDS),
        "record_count": len(documents),
        "passed_case_count": sum(
            1 for case_id in REQUIRED_CASE_IDS if case_id in by_case and by_case[case_id]["outcome"] == "pass"
        ),
        "missing_case_count": len(missing),
        "failed_or_blocked_case_count": len(failed),
        "unsafe_case_count": len(unsafe),
        "evidence_missing_case_count": len(evidence_missing),
        "duplicate_case_count": len(duplicates),
        "missing_case_ids": missing,
        "failed_or_blocked_case_ids": failed,
        "unsafe_case_ids": sorted(unsafe),
        "evidence_missing_case_ids": evidence_missing,
        "duplicate_case_ids": sorted(duplicates),
        "records_fingerprint": _fingerprint(encoded),
        "secret_values_included": False,
        "source_paths_included": False,
        "production_execution_invoked": False,
        "current_services_modified": False,
        "homeassistant_storage_read": False,
        "node_credentials_delivered": False,
        "anonymous_closure_enabled": False,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
        "ready_for_node_credential_generation": False,
        "real_board_test_complete": succeeded,
    }
