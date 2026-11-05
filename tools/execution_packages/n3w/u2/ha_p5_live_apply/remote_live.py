#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_a1_policy import LocalA1Policy
from n3w_t1_core_updater_host import LocalHost
from n3w_t1_core_updater_v2 import MultiComponentCoreUpdater
from n3w_t1_core_updater_v2_common import (
    APPLY_CONFIRMATION_V2,
    ComponentTarget,
    UpgradeBaseline,
)
from n3w_t1_core_updater_v2_state import V2StateStore

SCHEMA = "gh.n3w-t1-core-updater-ha-p5-live/1"
TARGET_PATH = Path("target.json")
BASELINE_PATH = Path("baseline.json")

P4_BASELINE_SHA256 = "78c3b0b58ad39cf887689658bec90c8466d30a93d58830b0289f1463dafad868"
P4_TRANSACTION_SHA256 = "6ad39528f43407c6f48b83a07cb2d4ddfc916e808b3957aae176608c89a98fa3"
EXPECTED_PREDECESSOR_IMAGES = {
    "manager": "local/greenhouse-manager:fresh-5b32e1ae8210",
    "homeassistant": "local/n3w-homeassistant:2026.10.0-0c73235a",
    "broker": "local/n3w-mosquitto:2.1.2-3184566d",
}
EXPECTED_PREDECESSOR_MODES = {
    "manager": "dynamic",
    "homeassistant": "legacy_static",
    "broker": "legacy_static",
}
EXPECTED_TARGET_IMAGES = {
    "manager": "local/greenhouse-manager:fresh-5b32e1ae8210",
    "homeassistant": "local/n3w-homeassistant:2026.10.4-5881590f",
    "broker": "local/n3w-mosquitto:2.1.2-3184566d",
}
EXPECTED_TARGET_MODES = {
    "manager": "dynamic",
    "homeassistant": "dynamic",
    "broker": "legacy_static",
}
EXPECTED_TARGET_IMAGE = EXPECTED_TARGET_IMAGES["homeassistant"]
EXPECTED_PREDECESSOR_IMAGE = EXPECTED_PREDECESSOR_IMAGES["homeassistant"]
EXPECTED_LISTENERS = {
    "tcp_8883": 1,
    "tcp_47110": 1,
    "udp_47111": 1,
    "tcp_47112": 0,
}


class StopLive(RuntimeError):
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


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise StopLive(reason)


def write_private(path: Path, value: Any) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            require(written > 0, "private_write_short")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def baseline_from_document(document: dict[str, Any]) -> UpgradeBaseline:
    return UpgradeBaseline(
        stack_images=dict(document["stack_images"]),
        image_binding_modes=dict(document["image_binding_modes"]),
        platforms=dict(document["platforms"]),
        runtime_contract_sha256=dict(document["runtime_contract_sha256"]),
        a1_hard_authority=dict(document["a1_hard_authority"]),
        a1_classification_sha256=str(document["a1_classification_sha256"]),
    )


def validate_predecessor_status(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "pre_status_not_pass")
    require(document.get("operation") == "status", "pre_status_operation_invalid")
    require(document.get("mutation") is False, "pre_status_mutation_invalid")
    require(document.get("recovery_required") is False, "pre_recovery_required")
    transaction = document.get("transaction")
    require(isinstance(transaction, dict), "pre_transaction_missing")
    require(transaction.get("component") == "manager", "pre_transaction_component_invalid")
    require(transaction.get("status") == "COMMITTED", "pre_transaction_status_invalid")
    require(transaction.get("phase") == "COMMITTED", "pre_transaction_phase_invalid")
    require(transaction.get("authorization_consumed") is True, "pre_transaction_authority_invalid")
    require(
        sha256_bytes(canonical(transaction)) == P4_TRANSACTION_SHA256,
        "pre_transaction_drift_from_p4",
    )
    require(document.get("legacy_manager_transaction") is None, "pre_legacy_transaction_present")


def validate_predecessor_runtime(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "pre_runtime_not_pass")
    require(document.get("operation") == "runtime-state", "pre_runtime_operation_invalid")
    require(document.get("mutation") is False, "pre_runtime_mutation_invalid")
    require(document.get("component") == "manager", "pre_runtime_component_invalid")
    require(document.get("runtime_class") == "TARGET_BOUND_RUNNING", "pre_runtime_class_invalid")
    require(document.get("health_state") == "HEALTHY", "pre_health_invalid")
    observed = document.get("observed")
    require(isinstance(observed, dict), "pre_runtime_observed_invalid")
    require(observed.get("image_bindings") == EXPECTED_PREDECESSOR_IMAGES, "pre_image_binding_drift")
    require(observed.get("image_binding_modes") == EXPECTED_PREDECESSOR_MODES, "pre_binding_mode_drift")


def validate_predecessor_inspect(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "pre_inspect_not_pass")
    require(document.get("operation") == "inspect", "pre_inspect_operation_invalid")
    require(document.get("component") == "homeassistant", "pre_inspect_component_invalid")
    require(document.get("mutation") is False, "pre_inspect_mutation_invalid")
    snapshot = document.get("snapshot")
    require(isinstance(snapshot, dict), "pre_snapshot_invalid")
    require(snapshot.get("image_bindings") == EXPECTED_PREDECESSOR_IMAGES, "pre_inspect_image_drift")
    require(snapshot.get("image_binding_modes") == EXPECTED_PREDECESSOR_MODES, "pre_inspect_mode_drift")
    require(snapshot.get("listeners") == EXPECTED_LISTENERS, "pre_listener_drift")
    mqtt = snapshot.get("mqtt_authenticated")
    require(isinstance(mqtt, dict), "pre_mqtt_state_invalid")
    require(mqtt.get("manager") is True, "pre_manager_mqtt_missing")
    require(mqtt.get("homeassistant") is True, "pre_homeassistant_mqtt_missing")
    require(snapshot.get("homeassistant_http_status") in {200, 401}, "pre_homeassistant_http_invalid")


def validate_baseline(document: dict[str, Any]) -> None:
    require(document.get("schema") == "gh.n3w-t1-core-updater-baseline/1", "baseline_schema_invalid")
    require(document.get("stack_images") == EXPECTED_PREDECESSOR_IMAGES, "baseline_image_drift")
    require(document.get("image_binding_modes") == EXPECTED_PREDECESSOR_MODES, "baseline_mode_drift")
    require(sha256_bytes(canonical(document)) == P4_BASELINE_SHA256, "baseline_drift_from_p4")


def validate_plan(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "plan_not_pass")
    require(document.get("operation") == "plan", "plan_operation_invalid")
    require(document.get("component") == "homeassistant", "plan_component_invalid")
    require(document.get("mutation") is False, "plan_mutation_invalid")
    current = document.get("current")
    require(isinstance(current, dict), "plan_current_invalid")
    require(current.get("image") == EXPECTED_PREDECESSOR_IMAGE, "plan_predecessor_drift")
    require(current.get("binding_mode") == "legacy_static", "plan_predecessor_mode_drift")
    target = document.get("target")
    require(isinstance(target, dict), "plan_target_invalid")
    require(target.get("target_image_ref") == EXPECTED_TARGET_IMAGE, "plan_target_image_drift")
    require(target.get("expected_predecessor_image_ref") == EXPECTED_PREDECESSOR_IMAGE, "plan_target_predecessor_drift")
    require(document.get("target_image_prestate") == "ABSENT", "plan_target_prestate_invalid")
    require(document.get("target_archive_verified") is True, "plan_archive_not_verified")
    actions = document.get("actions")
    require(isinstance(actions, list), "plan_actions_invalid")
    require("converge_homeassistant_runtime_template" in actions, "plan_template_convergence_missing")
    require("replace_only_homeassistant_image_binding" in actions, "plan_ha_binding_action_missing")
    require(document.get("rollback_available") is True, "plan_rollback_unavailable")


def validate_target_status(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "post_status_not_pass")
    require(document.get("operation") == "status", "post_status_operation_invalid")
    require(document.get("mutation") is False, "post_status_mutation_invalid")
    require(document.get("component") == "homeassistant", "post_status_component_invalid")
    require(document.get("recovery_required") is False, "post_recovery_required")
    transaction = document.get("transaction")
    require(isinstance(transaction, dict), "post_transaction_missing")
    require(transaction.get("component") == "homeassistant", "post_transaction_component_invalid")
    require(transaction.get("status") == "COMMITTED", "post_transaction_status_invalid")
    require(transaction.get("phase") == "COMMITTED", "post_transaction_phase_invalid")
    require(transaction.get("authorization_consumed") is True, "post_transaction_authority_invalid")
    require(transaction.get("predecessor_image") == EXPECTED_PREDECESSOR_IMAGE, "post_predecessor_image_invalid")
    require(transaction.get("predecessor_binding_mode") == "legacy_static", "post_predecessor_mode_invalid")


def validate_target_runtime(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "post_runtime_not_pass")
    require(document.get("operation") == "runtime-state", "post_runtime_operation_invalid")
    require(document.get("mutation") is False, "post_runtime_mutation_invalid")
    require(document.get("component") == "homeassistant", "post_runtime_component_invalid")
    require(document.get("runtime_class") == "TARGET_BOUND_RUNNING", "post_runtime_class_invalid")
    require(document.get("health_state") == "HEALTHY", "post_health_invalid")
    observed = document.get("observed")
    require(isinstance(observed, dict), "post_runtime_observed_invalid")
    require(observed.get("image_bindings") == EXPECTED_TARGET_IMAGES, "post_image_binding_drift")
    require(observed.get("image_binding_modes") == EXPECTED_TARGET_MODES, "post_binding_mode_drift")


def validate_target_inspect(document: dict[str, Any]) -> None:
    require(document.get("status") == "PASS", "post_inspect_not_pass")
    require(document.get("operation") == "inspect", "post_inspect_operation_invalid")
    require(document.get("component") == "homeassistant", "post_inspect_component_invalid")
    require(document.get("mutation") is False, "post_inspect_mutation_invalid")
    snapshot = document.get("snapshot")
    require(isinstance(snapshot, dict), "post_snapshot_invalid")
    require(snapshot.get("image_bindings") == EXPECTED_TARGET_IMAGES, "post_inspect_image_drift")
    require(snapshot.get("image_binding_modes") == EXPECTED_TARGET_MODES, "post_inspect_mode_drift")
    require(snapshot.get("listeners") == EXPECTED_LISTENERS, "post_listener_drift")
    mqtt = snapshot.get("mqtt_authenticated")
    require(isinstance(mqtt, dict), "post_mqtt_state_invalid")
    require(mqtt.get("manager") is True, "post_manager_mqtt_missing")
    require(mqtt.get("homeassistant") is True, "post_homeassistant_mqtt_missing")
    require(snapshot.get("homeassistant_http_status") in {200, 401}, "post_homeassistant_http_invalid")


def updater() -> MultiComponentCoreUpdater:
    return MultiComponentCoreUpdater(LocalHost(), V2StateStore(), LocalA1Policy())


def target() -> ComponentTarget:
    require(TARGET_PATH.is_file() and not TARGET_PATH.is_symlink(), "target_manifest_invalid")
    value = ComponentTarget.load(TARGET_PATH)
    require(value.component == "homeassistant", "target_component_invalid")
    require(value.target_image_ref == EXPECTED_TARGET_IMAGE, "target_image_invalid")
    require(value.expected_predecessor_image_ref == EXPECTED_PREDECESSOR_IMAGE, "target_predecessor_invalid")
    return value


def preflight(image_tar: Path) -> dict[str, Any]:
    require(os.geteuid() == 0, "root_required")
    require(image_tar.is_file() and not image_tar.is_symlink(), "image_tar_invalid")
    core = updater()
    status = core.status()
    validate_predecessor_status(status)
    runtime = core.runtime_state()
    validate_predecessor_runtime(runtime)
    inspect = core.inspect("homeassistant")
    validate_predecessor_inspect(inspect)

    first = core.baseline()
    validate_baseline(first)
    second = core.baseline()
    validate_baseline(second)
    require(canonical(first) == canonical(second), "baseline_double_read_drift")

    write_private(BASELINE_PATH, first)
    baseline = UpgradeBaseline.load(BASELINE_PATH)
    plan = core.plan(target(), baseline, image_tar)
    validate_plan(plan)

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "preflight",
        "mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "runtime_class": runtime["runtime_class"],
        "health_state": runtime["health_state"],
        "recovery_required": status["recovery_required"],
        "baseline_double_read_stable": True,
        "baseline_sha256": sha256_bytes(canonical(first)),
        "transaction_sha256": sha256_bytes(canonical(status["transaction"])),
        "plan_sha256": sha256_bytes(canonical(plan)),
        "target_image_prestate": plan["target_image_prestate"],
        "target_archive_verified": plan["target_archive_verified"],
        "template_convergence_planned": "converge_homeassistant_runtime_template" in plan["actions"],
        "rollback_available": plan["rollback_available"],
    }


def apply(image_tar: Path, authorization_id: str) -> dict[str, Any]:
    require(os.geteuid() == 0, "root_required")
    require(BASELINE_PATH.is_file() and not BASELINE_PATH.is_symlink(), "baseline_manifest_missing")
    result = updater().apply(
        target(),
        UpgradeBaseline.load(BASELINE_PATH),
        image_tar,
        authorization_id=authorization_id,
        confirmation=APPLY_CONFIRMATION_V2,
    )
    require(result.get("status") == "PASS", "apply_not_pass")
    require(result.get("operation") == "apply", "apply_operation_invalid")
    require(result.get("component") == "homeassistant", "apply_component_invalid")
    require(result.get("transaction_status") == "COMMITTED", "apply_transaction_invalid")
    require(result.get("authorization_consumed") is True, "apply_authorization_invalid")
    require(result.get("t1_mutation") is True, "apply_mutation_invalid")
    return result


def post() -> dict[str, Any]:
    core = updater()
    status = core.status()
    validate_target_status(status)
    runtime = core.runtime_state()
    validate_target_runtime(runtime)
    inspect = core.inspect("homeassistant")
    validate_target_inspect(inspect)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "post",
        "mutation": False,
        "recovery_required": status["recovery_required"],
        "runtime_class": runtime["runtime_class"],
        "health_state": runtime["health_state"],
        "image_bindings": runtime["observed"]["image_bindings"],
        "image_binding_modes": runtime["observed"]["image_binding_modes"],
        "transaction_sha256": sha256_bytes(canonical(status["transaction"])),
        "manager_mqtt_authenticated": inspect["snapshot"]["mqtt_authenticated"]["manager"],
        "homeassistant_mqtt_authenticated": inspect["snapshot"]["mqtt_authenticated"]["homeassistant"],
        "homeassistant_http_status": inspect["snapshot"]["homeassistant_http_status"],
        "listeners": inspect["snapshot"]["listeners"],
    }


def diagnose() -> dict[str, Any]:
    core = updater()
    output: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "diagnose",
        "mutation": False,
    }
    for name, callback in (
        ("status_report", core.status),
        ("runtime_report", core.runtime_state),
        ("inspect_report", lambda: core.inspect("homeassistant")),
    ):
        try:
            output[name] = callback()
        except Exception as error:
            output[name] = {
                "status": "STOP",
                "reason": type(error).__name__,
            }
    return output


def main() -> int:
    parser = argparse.ArgumentParser(prog="n3w-ha-p5-remote-live")
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--image-tar", type=Path, required=True)
    app = sub.add_parser("apply")
    app.add_argument("--image-tar", type=Path, required=True)
    app.add_argument("--authorization-id", required=True)
    sub.add_parser("post")
    sub.add_parser("diagnose")
    args = parser.parse_args()

    try:
        if args.command == "preflight":
            result = preflight(args.image_tar)
        elif args.command == "apply":
            result = apply(args.image_tar, args.authorization_id)
        elif args.command == "post":
            result = post()
        else:
            result = diagnose()
    except Exception as error:
        reason = str(error)
        if not reason or len(reason) > 200 or "/" in reason or "\\" in reason or "@" in reason:
            reason = type(error).__name__
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "operation": args.command,
                    "mutation": args.command == "apply",
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
