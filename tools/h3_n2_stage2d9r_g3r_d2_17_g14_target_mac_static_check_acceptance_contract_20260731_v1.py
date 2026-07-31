#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g14-target-mac-static-check-pass-20260731-v1.json"
PENDING = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g14-physical-execution-pending-20260731-v1.json"
EXPECTED_ACCEPTANCE = "44e21d03db295975439c77389f57b89b57e838db74a67c644035822d914adfe4"
EXPECTED_PENDING = "18b5d0f710ac8cd2bb1c889745795e5820a8df8ffceda0aebe1bb924cb0cc675"

def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("JSON_OBJECT_REQUIRED")
    return value

def verify_binding(value: dict[str, Any], field: str, expected: str) -> None:
    actual = value.pop(field, None)
    if actual != expected or canonical(value) != expected:
        raise SystemExit(field + "_MISMATCH")
    value[field] = actual

def main() -> int:
    acceptance = load(ACCEPTANCE)
    pending = load(PENDING)
    verify_binding(acceptance, "acceptance_binding_sha256", EXPECTED_ACCEPTANCE)
    verify_binding(pending, "physical_pending_binding_sha256", EXPECTED_PENDING)
    required = {
        "status": "PASS",
        "terminal_state": "TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "authorization_created": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_decision_created": False,
        "all_physical_operation_flags_false": True,
        "hardware_sentinels_all_zero": True,
        "g14_mode_conflict_confirmed": True,
        "g14_mode_normalized_execution_view_created": True,
        "g14_all_execution_view_files_mode_0600": True,
        "g14_execution_view_content_equivalent": True,
        "g14_canonical_execution_root_mutated": False,
        "g14_ready_for_inherited_preclaim": True,
        "public_source_pr": 251,
        "public_source_head_sha": "86d660d2c93e97122c52e9eeb0004151aa5184e7",
        "public_source_artifact_id": 8793691153,
        "public_source_artifact_sha256": "e3af195a904c75e7649a4c74f2c4b2085b46f5181b758790cbfafae9aa6a57ce",
        "private_delivery_binding_sha256": "012e02ca72a12044fd4c39caf3f750d5132e9c52acc3f60f291e994db21fe33b",
        "terminal_record_sha256": "78c532585e1c93cf0bd0489dfbbec310350112d05290b2411516b9fa49235345",
        "export_summary_sha256": "1f6b7aa2ca5708b5edb42f3ebb353b40cf2b3035af4dc33e297c3ac4509cdd75",
        "authorization_record_sha256": "47bd58b60acb94ccf3d9e470359936fd8b610987dba99cc81adcddaf09ce1b29",
        "authorization_expires_at": "2026-07-31T15:28:23.051833Z",
        "secret_values_included": False,
        "private_paths_included": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    for key, expected in required.items():
        if acceptance.get(key) != expected:
            raise SystemExit("ACCEPTANCE_FIELD_DRIFT:" + key)
    pending_required = {
        "g14_acceptance_binding_sha256": EXPECTED_ACCEPTANCE,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_execution_authorized": False,
        "state": "PHYSICAL_EXECUTION_PENDING_EXPLICIT_AUTHORIZATION",
        "next_gate": "D1-H3N2-STAGE2D9R-G3R-D2-17-G14-PHYSICAL-EXECUTION-20260731-01",
        "ready": False,
        "merge": False,
        "release": False,
        "tag": False,
        "deployment": False,
    }
    for key, expected in pending_required.items():
        if pending.get(key) != expected:
            raise SystemExit("PENDING_FIELD_DRIFT:" + key)
    print(json.dumps({"status":"PASS","acceptance_binding_sha256":EXPECTED_ACCEPTANCE,"physical_pending_binding_sha256":EXPECTED_PENDING,"physical_operation":False}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
