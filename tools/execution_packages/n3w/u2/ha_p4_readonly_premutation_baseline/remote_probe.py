#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_a1_policy import LocalA1Policy
from n3w_t1_core_updater_host import LocalHost
from n3w_t1_core_updater_v2 import MultiComponentCoreUpdater
from n3w_t1_core_updater_v2_common import ComponentTarget, UpgradeBaseline
from n3w_t1_core_updater_v2_state import V2StateStore

SCHEMA = "gh.n3w-t1-core-updater-ha-p4-readonly-premutation-baseline/1"
EXPECTED_IMAGES = {
    "manager": "local/greenhouse-manager:fresh-5b32e1ae8210",
    "homeassistant": "local/n3w-homeassistant:2026.10.0-0c73235a",
    "broker": "local/n3w-mosquitto:2.1.2-3184566d",
}
EXPECTED_MODES = {
    "manager": "dynamic",
    "homeassistant": "legacy_static",
    "broker": "legacy_static",
}
EXPECTED_TARGET = "local/n3w-homeassistant:2026.10.4-5881590f"
EXPECTED_PREDECESSOR = EXPECTED_IMAGES["homeassistant"]
TARGET_PATH = Path("target.json")
PRODUCT_PATHS = (
    Path("/etc/n3wfc4/docker-compose.yml"),
    Path("/etc/n3wfc4/docker-compose.env"),
)
STATE_ROOT = Path("/var/lib/n3w-t1-core-updater")
UNITS = (
    "n3wfc4-broker-activation.service",
    "n3wfc4-services-activation.service",
    "n3wfc4-registration-ingress-guard.service",
    "n3wfc4-broker-ingress-guard.service",
)


class StopProbe(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise StopProbe(reason)


def file_snapshot(path: Path) -> dict[str, Any]:
    require(path.exists(), f"file_missing:{path.name}")
    require(not path.is_symlink(), f"file_symlink:{path.name}")
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode), f"file_type_invalid:{path.name}")
    return {
        "sha256": sha256_path(path),
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
        "size": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
    }


def product_snapshot() -> dict[str, Any]:
    return {str(path): file_snapshot(path) for path in PRODUCT_PATHS}


def state_snapshot() -> dict[str, Any]:
    if not STATE_ROOT.exists():
        return {"exists": False, "entries": {}}
    require(not STATE_ROOT.is_symlink(), "state_root_symlink")
    require(STATE_ROOT.is_dir(), "state_root_invalid")
    entries: dict[str, Any] = {}
    for path in sorted(STATE_ROOT.rglob("*")):
        relative = str(path.relative_to(STATE_ROOT))
        require(not path.is_symlink(), f"state_entry_symlink:{relative}")
        metadata = path.stat()
        if stat.S_ISDIR(metadata.st_mode):
            entries[relative] = {
                "type": "dir",
                "mode": stat.S_IMODE(metadata.st_mode),
                "uid": metadata.st_uid,
                "gid": metadata.st_gid,
                "mtime_ns": metadata.st_mtime_ns,
            }
        elif stat.S_ISREG(metadata.st_mode):
            entries[relative] = {
                "type": "file",
                "sha256": sha256_path(path),
                "mode": stat.S_IMODE(metadata.st_mode),
                "uid": metadata.st_uid,
                "gid": metadata.st_gid,
                "size": metadata.st_size,
                "mtime_ns": metadata.st_mtime_ns,
            }
        else:
            raise StopProbe(f"state_entry_type_invalid:{relative}")
    root = STATE_ROOT.stat()
    return {
        "exists": True,
        "mode": stat.S_IMODE(root.st_mode),
        "uid": root.st_uid,
        "gid": root.st_gid,
        "mtime_ns": root.st_mtime_ns,
        "entries": entries,
    }


def unit_snapshot() -> dict[str, str]:
    result: dict[str, str] = {}
    for unit in UNITS:
        completed = subprocess.run(
            (
                "systemctl",
                "show",
                unit,
                "--property=ActiveState",
                "--property=SubState",
                "--property=NRestarts",
                "--property=ActiveEnterTimestampMonotonic",
                "--property=ExecMainStartTimestampMonotonic",
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        require(completed.returncode == 0, f"systemctl_show_failed:{unit}")
        result[unit] = completed.stdout.decode(errors="strict").strip()
    return result


def baseline_from_document(document: dict[str, Any]) -> UpgradeBaseline:
    return UpgradeBaseline(
        stack_images=dict(document["stack_images"]),
        image_binding_modes=dict(document["image_binding_modes"]),
        platforms=dict(document["platforms"]),
        runtime_contract_sha256=dict(document["runtime_contract_sha256"]),
        a1_hard_authority=dict(document["a1_hard_authority"]),
        a1_classification_sha256=str(document["a1_classification_sha256"]),
    )


def validate_runtime_state(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "runtime_state_not_pass")
    require(document.get("operation") == "runtime-state", "runtime_state_operation_invalid")
    require(document.get("mutation") is False, "runtime_state_mutation_invalid")
    require(document.get("component") == "manager", "runtime_state_component_invalid")
    require(document.get("runtime_class") == "TARGET_BOUND_RUNNING", "runtime_class_invalid")
    require(document.get("health_state") == "HEALTHY", "runtime_health_invalid")
    observed = document.get("observed")
    require(isinstance(observed, dict), "runtime_observed_invalid")
    require(observed.get("image_bindings") == EXPECTED_IMAGES, "runtime_image_binding_drift")
    require(observed.get("image_binding_modes") == EXPECTED_MODES, "runtime_binding_mode_drift")
    transaction = document.get("transaction")
    require(isinstance(transaction, dict), "runtime_transaction_missing")
    require(transaction.get("component") == "manager", "runtime_transaction_component_invalid")
    require(transaction.get("status") == "COMMITTED", "runtime_transaction_status_invalid")
    require(transaction.get("phase") == "COMMITTED", "runtime_transaction_phase_invalid")
    require(transaction.get("authorization_consumed") is True, "runtime_transaction_authority_invalid")
    require(document.get("legacy_manager_transaction") is None, "legacy_transaction_present")


def validate_status(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "status_not_pass")
    require(document.get("operation") == "status", "status_operation_invalid")
    require(document.get("mutation") is False, "status_mutation_invalid")
    require(document.get("component") == "manager", "status_component_invalid")
    require(document.get("recovery_required") is False, "status_recovery_required")
    transaction = document.get("transaction")
    require(isinstance(transaction, dict), "status_transaction_missing")
    require(transaction.get("component") == "manager", "status_transaction_component_invalid")
    require(transaction.get("status") == "COMMITTED", "status_transaction_status_invalid")
    require(transaction.get("phase") == "COMMITTED", "status_transaction_phase_invalid")
    require(transaction.get("authorization_consumed") is True, "status_transaction_authority_invalid")
    require(document.get("legacy_manager_transaction") is None, "status_legacy_transaction_present")


def validate_inspect(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "inspect_not_pass")
    require(document.get("operation") == "inspect", "inspect_operation_invalid")
    require(document.get("component") == "homeassistant", "inspect_component_invalid")
    require(document.get("mutation") is False, "inspect_mutation_invalid")
    snapshot = document.get("snapshot")
    require(isinstance(snapshot, dict), "inspect_snapshot_invalid")
    require(snapshot.get("image_bindings") == EXPECTED_IMAGES, "inspect_image_binding_drift")
    require(snapshot.get("image_binding_modes") == EXPECTED_MODES, "inspect_binding_mode_drift")
    runtime = snapshot.get("runtime")
    require(isinstance(runtime, dict), "inspect_runtime_invalid")
    for component, expected in EXPECTED_IMAGES.items():
        item = runtime.get(component)
        require(isinstance(item, dict), f"inspect_runtime_missing:{component}")
        require(item.get("image_ref") == expected, f"inspect_runtime_image_drift:{component}")
        require(item.get("platform") == "linux/arm64", f"inspect_platform_drift:{component}")


def validate_baseline(document: dict[str, Any]) -> None:
    require(document.get("schema") == "gh.n3w-t1-core-updater-baseline/1", "baseline_schema_invalid")
    require(document.get("stack_images") == EXPECTED_IMAGES, "baseline_image_binding_drift")
    require(document.get("image_binding_modes") == EXPECTED_MODES, "baseline_binding_mode_drift")
    require(
        document.get("platforms")
        == {"manager": "linux/arm64", "homeassistant": "linux/arm64", "broker": "linux/arm64"},
        "baseline_platform_drift",
    )
    contracts = document.get("runtime_contract_sha256")
    require(isinstance(contracts, dict), "baseline_runtime_contract_invalid")
    require(set(contracts) == set(EXPECTED_IMAGES), "baseline_runtime_contract_shape_invalid")
    for value in contracts.values():
        require(isinstance(value, str) and len(value) == 64, "baseline_runtime_contract_hash_invalid")


def validate_plan(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "plan_not_pass")
    require(document.get("operation") == "plan", "plan_operation_invalid")
    require(document.get("component") == "homeassistant", "plan_component_invalid")
    require(document.get("mutation") is False, "plan_mutation_invalid")
    current = document.get("current")
    require(isinstance(current, dict), "plan_current_invalid")
    require(current.get("image") == EXPECTED_PREDECESSOR, "plan_predecessor_drift")
    require(current.get("binding_mode") == "legacy_static", "plan_predecessor_mode_drift")
    target = document.get("target")
    require(isinstance(target, dict), "plan_target_invalid")
    require(target.get("target_image_ref") == EXPECTED_TARGET, "plan_target_image_drift")
    require(target.get("expected_predecessor_image_ref") == EXPECTED_PREDECESSOR, "plan_target_predecessor_drift")
    require(document.get("target_image_prestate") == "ABSENT", "plan_target_image_prestate_invalid")
    require(document.get("target_archive_verified") is False, "plan_archive_verification_invalid")
    actions = document.get("actions")
    require(isinstance(actions, list), "plan_actions_invalid")
    require("converge_homeassistant_runtime_template" in actions, "plan_template_convergence_missing")
    require("replace_only_homeassistant_image_binding" in actions, "plan_ha_binding_action_missing")
    require(document.get("rollback_available") is True, "plan_rollback_unavailable")


def execute() -> dict[str, Any]:
    require(os.geteuid() == 0, "root_required")
    require(TARGET_PATH.is_file() and not TARGET_PATH.is_symlink(), "target_manifest_invalid")

    target = ComponentTarget.load(TARGET_PATH)
    require(target.component == "homeassistant", "target_component_invalid")
    require(target.target_image_ref == EXPECTED_TARGET, "target_image_invalid")
    require(target.expected_predecessor_image_ref == EXPECTED_PREDECESSOR, "target_predecessor_invalid")

    host = LocalHost()
    store = V2StateStore()
    updater = MultiComponentCoreUpdater(host, store, LocalA1Policy())

    product_before = product_snapshot()
    state_before = state_snapshot()
    units_before = unit_snapshot()

    status_before = updater.status()
    validate_status(status_before)
    runtime_before = updater.runtime_state()
    validate_runtime_state(runtime_before)
    inspect = updater.inspect("homeassistant")
    validate_inspect(inspect)

    baseline_1 = updater.baseline()
    validate_baseline(baseline_1)
    baseline_2 = updater.baseline()
    validate_baseline(baseline_2)
    require(canonical(baseline_1) == canonical(baseline_2), "baseline_double_read_drift")

    plan = updater.plan(target, baseline_from_document(baseline_1), None)
    validate_plan(plan)

    status_after = updater.status()
    validate_status(status_after)
    runtime_after = updater.runtime_state()
    validate_runtime_state(runtime_after)

    product_after = product_snapshot()
    state_after = state_snapshot()
    units_after = unit_snapshot()

    require(canonical(status_before) == canonical(status_after), "status_changed_during_readonly_gate")
    require(canonical(runtime_before) == canonical(runtime_after), "runtime_changed_during_readonly_gate")
    require(product_before == product_after, "product_files_changed_during_readonly_gate")
    require(state_before == state_after, "updater_state_changed_during_readonly_gate")
    require(units_before == units_after, "service_state_changed_during_readonly_gate")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "readonly_premutation_baseline",
        "mutation": False,
        "persistent_t1_file_write": False,
        "temporary_scratch_write": True,
        "service_restart": False,
        "image_load": False,
        "updater_apply": False,
        "updater_rollback": False,
        "component": "homeassistant",
        "runtime_class": runtime_before["runtime_class"],
        "health_state": runtime_before["health_state"],
        "recovery_required": status_before["recovery_required"],
        "image_bindings": EXPECTED_IMAGES,
        "image_binding_modes": EXPECTED_MODES,
        "baseline_double_read_stable": True,
        "baseline_sha256": sha256_bytes(canonical(baseline_1)),
        "plan_sha256": sha256_bytes(canonical(plan)),
        "transaction_sha256": sha256_bytes(canonical(status_before["transaction"])),
        "product_snapshot_sha256": sha256_bytes(canonical(product_before)),
        "state_snapshot_sha256": sha256_bytes(canonical(state_before)),
        "service_snapshot_sha256": sha256_bytes(canonical(units_before)),
        "target_image_prestate": plan["target_image_prestate"],
        "target_archive_verified": plan["target_archive_verified"],
        "template_convergence_planned": "converge_homeassistant_runtime_template" in plan["actions"],
        "rollback_available": plan["rollback_available"],
        "readonly_state_stable": True,
    }


def main() -> int:
    try:
        result = execute()
    except Exception as error:
        reason = str(error)
        if not reason or len(reason) > 200 or "/" in reason or "\\" in reason or "@" in reason:
            reason = type(error).__name__
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "operation": "readonly_premutation_baseline",
                    "mutation": False,
                    "reason": reason,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
