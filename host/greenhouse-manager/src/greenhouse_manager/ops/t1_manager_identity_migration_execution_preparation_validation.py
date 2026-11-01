from __future__ import annotations

from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_execution_preparation_constants import (
    GATE_CHECKS,
    GATE_FLAGS,
    PREPARATION_PREFIX,
    PREPARATION_RECORDS,
    PREPARATION_SCHEMA,
    RUNTIME_SCHEMA,
    ManagerIdentityExecutionPreparationError,
)
from .t1_manager_identity_migration_execution_preparation_io import (
    canonical,
    must,
    private_dir,
    private_file,
    read_json,
    require_sha,
    safe_relative,
    sha_bytes,
    sha_path,
)


def validate_gate(gate: dict[str, Any]) -> None:
    must(gate, GATE_FLAGS, "live runtime gate")
    checks = gate.get("checks")
    if not isinstance(checks, dict) or not GATE_CHECKS.issubset(checks):
        raise ManagerIdentityExecutionPreparationError(
            "live runtime gate check inventory is incomplete"
        )
    if any(checks[name] is not True for name in GATE_CHECKS):
        raise ManagerIdentityExecutionPreparationError("live runtime gate is not passing")
    for field in (
        "driver_contract_sha256",
        "adapter_contract_sha256",
        "runtime_binding_sha256",
        "live_binding_sha256",
    ):
        require_sha(gate.get(field), field)


def validate_preparation(root: Path) -> dict[str, Any]:
    if not root.name.startswith(PREPARATION_PREFIX):
        raise ManagerIdentityExecutionPreparationError(
            "manager preparation directory name is invalid"
        )
    private_dir(root, "manager preparation directory")
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path, "manager preparation manifest")
    must(
        manifest,
        {
            "schema": PREPARATION_SCHEMA,
            "read_only_live_services": True,
            "current_services_modified": False,
            "apply_enabled": False,
            "operator_action_authorized": False,
            "broker_identity_activated": True,
            "homeassistant_authenticated": True,
            "manager_identity_migrated": False,
            "node_credentials_delivered": False,
            "ready_for_manager_migration_authorization": True,
            "ready_for_manager_migration_apply": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
            "secret_values_included": True,
            "normal_report_contains_secrets": False,
            "normal_report_contains_source_paths": False,
        },
        "manager preparation manifest",
    )
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ManagerIdentityExecutionPreparationError(
            "manager preparation record inventory is missing"
        )
    observed: dict[str, str] = {}
    for item in records:
        if not isinstance(item, dict):
            raise ManagerIdentityExecutionPreparationError(
                "manager preparation record inventory is invalid"
            )
        relative = safe_relative(item.get("path"), "manager preparation record")
        name = relative.as_posix()
        if name in observed or name not in PREPARATION_RECORDS:
            raise ManagerIdentityExecutionPreparationError(
                "manager preparation record inventory is unexpected"
            )
        path = root.joinpath(*relative.parts)
        private_file(path, f"manager preparation record {name}")
        digest = sha_path(path)
        if (
            item.get("size") != path.stat().st_size
            or item.get("sha256") != digest
            or item.get("contains_secret") is not PREPARATION_RECORDS[name]
        ):
            raise ManagerIdentityExecutionPreparationError(
                f"manager preparation record verification failed: {name}"
            )
        observed[name] = digest
    if set(observed) != set(PREPARATION_RECORDS):
        raise ManagerIdentityExecutionPreparationError(
            "manager preparation record inventory is incomplete"
        )
    runtime_path = root / "manager-runtime-binding.json"
    runtime = read_json(runtime_path, "manager runtime binding")
    must(
        runtime,
        {
            "schema": RUNTIME_SCHEMA,
            "read_only_capture": True,
            "current_services_modified": False,
        },
        "manager runtime binding",
    )
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict) or bindings.get(
        "manager_runtime_binding_sha256"
    ) != sha_path(runtime_path):
        raise ManagerIdentityExecutionPreparationError(
            "manager runtime binding SHA-256 does not match preparation"
        )
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "manifest_sha256": sha_path(manifest_path),
        "records": observed,
        "record_set_sha256": sha_bytes(canonical(observed).encode()),
        "runtime": runtime,
        "runtime_path": runtime_path,
    }
