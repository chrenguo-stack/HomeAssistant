#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g12-target-mac-static-check-pass-20260731-v1.json"
PENDING = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g12-physical-execution-pending-20260731-v1.json"
EXPECTED_ACCEPTANCE_BINDING = "f7bcfce8d3c10f337076fbaba916526fde54f152fda3876e321ab304bdcc37ff"
EXPECTED_PENDING_BINDING = "b7b1d4b71e815b28a2bb7468715abcdd5b9977962890f207a36c723122a3c64f"


def canonical(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"NOT_OBJECT:{path}")
    return value


def verify_binding(value: dict[str, Any], field: str, expected: str) -> None:
    actual = value.get(field)
    if actual != expected:
        raise SystemExit(f"{field}_EXPECTED_DRIFT:{actual}")
    core = dict(value)
    core.pop(field, None)
    semantic = canonical(core)
    if semantic != expected:
        raise SystemExit(f"{field}_SEMANTIC_DRIFT:{semantic}")


def main() -> int:
    acceptance = load(ACCEPTANCE)
    pending = load(PENDING)
    verify_binding(acceptance, "acceptance_binding_sha256", EXPECTED_ACCEPTANCE_BINDING)
    verify_binding(pending, "physical_pending_binding_sha256", EXPECTED_PENDING_BINDING)

    required_acceptance = {
        "status": "PASS",
        "terminal_state": "TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "authorization_created": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_decision_created": False,
        "all_physical_operation_flags_false": True,
        "hardware_sentinels_all_zero": True,
        "g12_baseline_directory_repair_validated": True,
        "g12_inherited_error_subcode_preservation_validated": True,
        "root_cause": "BASELINE_OUTPUT_PARENT_DIRECTORY_NOT_CREATED_BEFORE_READ_FLASH",
        "package_generation": "G12",
        "public_source_pr": 245,
        "public_source_head_sha": "759fc3d35cec6bbdf49d149c1422683645c3da6e",
        "public_source_artifact_id": 8788984113,
        "public_source_artifact_sha256": "470b7507e2492f4e59331caf04ae4f67367af5850e083e6ee1a1738fd4bdf292",
        "private_delivery_binding_sha256": "df9f78d95ba2391cfecb65377b25dd32803122c4d3a6fdca65bebc0c1674cf49",
        "terminal_record_sha256": "432ef9cbe74bb1c688ed7a88192c230b8c0e04ff2361dfe543282245ff9345fa",
        "export_summary_sha256": "560d559d5e9694333297a6716fd6d84fc06d2fd3e89bd4e101066a70e3a646d5",
        "authorization_record_sha256": "f670b5f5b637445a09975de1f9e0d23c3eda0d6c8910ec50a4e64a440b8a8963",
        "configured_runtime_validator_check_sha256": "7fbf5116f42271382649f1d0e32fb96e41c006b5ae14ddb1ffd6ab8ffd9b4920",
        "authorization_expires_at": "2026-07-31T11:44:35.654243Z",
        "secret_values_included": False,
        "private_paths_included": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    for key, expected in required_acceptance.items():
        if acceptance.get(key) != expected:
            raise SystemExit(f"ACCEPTANCE_FIELD_DRIFT:{key}")

    required_pending = {
        "g12_acceptance_binding_sha256": EXPECTED_ACCEPTANCE_BINDING,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_execution_authorized": False,
        "state": "PHYSICAL_EXECUTION_PENDING_EXPLICIT_AUTHORIZATION",
        "next_gate": "D1-H3N2-STAGE2D9R-G3R-D2-17-G12-PHYSICAL-EXECUTION-20260731-01",
        "ready": False,
        "merge": False,
        "release": False,
        "tag": False,
        "deployment": False,
    }
    for key, expected in required_pending.items():
        if pending.get(key) != expected:
            raise SystemExit(f"PENDING_FIELD_DRIFT:{key}")

    print(json.dumps({
        "status": "PASS",
        "acceptance_binding_sha256": EXPECTED_ACCEPTANCE_BINDING,
        "physical_pending_binding_sha256": EXPECTED_PENDING_BINDING,
        "physical_operation": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
