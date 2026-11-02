#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-clean-reference-observation-compare/1"
OBSERVATION_SCHEMA = "gh.n3w-t1-clean-reference-observation/1"

BUSINESS_PREFIXES = (
    "runtime_observations.sqlite.",
    "runtime_observations.dynsec_counts.",
    "runtime_observations.homeassistant_registry_counts.",
    "runtime_observations.persistent_tree_stats.",
)


class CompareError(RuntimeError):
    pass


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CompareError(f"{label}_observation_invalid") from error
    if not isinstance(document, dict):
        raise CompareError(f"{label}_observation_invalid")
    if (
        document.get("schema") != OBSERVATION_SCHEMA
        or document.get("status") != "PASS"
        or document.get("reference_label") != label
        or document.get("read_only") is not True
        or document.get("network_mutation") is not False
        or document.get("board_access") is not False
    ):
        raise CompareError(f"{label}_observation_contract_invalid")
    return document


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(value[key], child))
        return result
    if isinstance(value, list):
        return {prefix: value}
    return {prefix: value}


def _diff(a: Any, b: Any, prefix: str) -> list[dict[str, Any]]:
    left = _flatten(a, prefix)
    right = _flatten(b, prefix)
    changes: list[dict[str, Any]] = []
    for path in sorted(set(left) | set(right)):
        before = left.get(path, {"__missing__": True})
        after = right.get(path, {"__missing__": True})
        if before != after:
            changes.append(
                {
                    "field": path,
                    "before": before,
                    "after": after,
                }
            )
    return changes


def compare(
    r2: dict[str, Any],
    r3: dict[str, Any],
    *,
    require_business_drift: bool,
) -> dict[str, Any]:
    if r2.get("health", {}).get("overall_pass") is not True:
        raise CompareError("r2_health_not_pass")
    if r3.get("health", {}).get("overall_pass") is not True:
        raise CompareError("r3_health_not_pass")

    stable_changes = _diff(
        r2.get("stable_contracts"),
        r3.get("stable_contracts"),
        "stable_contracts",
    )

    runtime_changes = _diff(
        r2.get("runtime_observations"),
        r3.get("runtime_observations"),
        "runtime_observations",
    )

    r2_runtime = r2.get("runtime_observations")
    r3_runtime = r3.get("runtime_observations")
    if not isinstance(r2_runtime, dict) or not isinstance(r3_runtime, dict):
        raise CompareError("runtime_observations_invalid")

    boot_unchanged = (
        r2_runtime.get("boot_id_sha256")
        == r3_runtime.get("boot_id_sha256")
    )

    service_restart_changes: list[str] = []
    r2_containers = r2_runtime.get("containers")
    r3_containers = r3_runtime.get("containers")
    if not isinstance(r2_containers, dict) or not isinstance(r3_containers, dict):
        raise CompareError("container_observations_invalid")
    for service in ("broker", "homeassistant", "manager"):
        before = r2_containers.get(service)
        after = r3_containers.get(service)
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise CompareError(f"container_observation_invalid:{service}")
        if (
            before.get("started_at") != after.get("started_at")
            or before.get("restart_count") != after.get("restart_count")
        ):
            service_restart_changes.append(service)

    business_changes = [
        item
        for item in runtime_changes
        if any(item["field"].startswith(prefix) for prefix in BUSINESS_PREFIXES)
    ]

    status = "PASS"
    reasons: list[str] = []
    if stable_changes:
        status = "STOP"
        reasons.append("stable_contract_drift")
    if not boot_unchanged:
        status = "STOP"
        reasons.append("unexpected_reboot")
    if service_restart_changes:
        status = "STOP"
        reasons.append("service_restart_or_recreation")
    if require_business_drift and not business_changes:
        status = "STOP"
        reasons.append("business_runtime_drift_not_observed")

    return {
        "schema": SCHEMA,
        "status": status,
        "r2_reference": "PASS",
        "r3_reference": "PASS",
        "stable_contract_change_count": len(stable_changes),
        "stable_contract_changes": stable_changes,
        "runtime_change_count": len(runtime_changes),
        "runtime_changes": runtime_changes,
        "business_runtime_change_count": len(business_changes),
        "business_runtime_changes": business_changes,
        "boot_unchanged": boot_unchanged,
        "service_restart_change_count": len(service_restart_changes),
        "service_restart_services": service_restart_changes,
        "require_business_drift": require_business_drift,
        "stop_reasons": reasons,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r2", required=True)
    parser.add_argument("--r3", required=True)
    parser.add_argument("--require-business-drift", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        r2 = _load(Path(args.r2), "R2")
        r3 = _load(Path(args.r3), "R3")
        report = compare(
            r2,
            r3,
            require_business_drift=args.require_business_drift,
        )
    except (CompareError, OSError, ValueError, TypeError) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:300],
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
