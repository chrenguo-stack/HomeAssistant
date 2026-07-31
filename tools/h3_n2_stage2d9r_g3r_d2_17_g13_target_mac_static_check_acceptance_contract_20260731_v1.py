#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g13-target-mac-static-check-pass-20260731-v1.json"
PENDING = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g13-physical-execution-pending-20260731-v1.json"
EXPECTED_ACCEPTANCE_BINDING = "80d85d4e44eaeff5f0eaaa979fd34651547f4aa5b055cc2d5ddfe9d46d4ae92a"
EXPECTED_PENDING_BINDING = "c87b17599c3c7e20182ca2c8ddc5abba0c49d8bfb7cda46bba48f2acf5b1ab03"

def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"NOT_OBJECT:{path}")
    return value

def verify_binding(value: dict[str, Any], field: str, expected: str) -> None:
    if value.get(field) != expected:
        raise SystemExit(f"{field}_EXPECTED_DRIFT")
    core = dict(value)
    core.pop(field)
    if canonical(core) != expected:
        raise SystemExit(f"{field}_SEMANTIC_DRIFT")

def main() -> int:
    acceptance = load(ACCEPTANCE)
    pending = load(PENDING)
    verify_binding(acceptance, "acceptance_binding_sha256", EXPECTED_ACCEPTANCE_BINDING)
    verify_binding(pending, "physical_pending_binding_sha256", EXPECTED_PENDING_BINDING)

    exact_acceptance = {
        "status": "PASS",
        "state": "TARGET_MAC_STATIC_CHECK_ACCEPTED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "terminal_state": "TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "authorization_created": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_decision_created": False,
        "all_physical_operation_flags_false": True,
        "hardware_sentinels_all_zero": True,
        "package_generation": "G13",
        "public_source_pr": 248,
        "public_source_head_sha": "89b8a4bf84d6cb236e775055d3427e21dde138e6",
        "public_source_artifact_id": 8791335916,
        "public_source_artifact_sha256": "6430bac9aeea3961df9f3f29fbd6c882ac25b40786f9313e542fbf2d1511ca17",
        "terminal_record_sha256": "7ed21be49a4322b6856b08f1648be4392f68b2bb8e001ddc6873b4ee69b87b14",
        "export_summary_sha256": "125d61749a15603a9d6f8f0cd017bd844e00da7a3a15ae06a6f8439df8c333b4",
        "authorization_record_sha256": "5eb016ae2ac929dcb5d407aaf16a1ffdbdffea743a60a376d244be03b398c75a",
        "authorization_expires_at": "2026-07-31T13:54:24.915627Z",
        "g13_baseline_compatibility_adapter_installed": True,
        "g13_bypasses_g12_incompatible_wrapper": True,
        "g13_claim_state_derivation_validated": True,
        "g13_existing_empty_real_0700_directory_validated": True,
        "g13_missing_directory_validated": True,
        "g13_negative_directory_cases_validated": True,
        "secret_values_included": False,
        "private_paths_included": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    for key, expected in exact_acceptance.items():
        if acceptance.get(key) != expected:
            raise SystemExit(f"ACCEPTANCE_FIELD_DRIFT:{key}")

    exact_pending = {
        "g13_acceptance_binding_sha256": EXPECTED_ACCEPTANCE_BINDING,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_execution_authorized": False,
        "state": "PHYSICAL_EXECUTION_PENDING_EXPLICIT_AUTHORIZATION",
        "next_gate": "D1-H3N2-STAGE2D9R-G3R-D2-17-G13-PHYSICAL-EXECUTION-20260731-01",
        "ready": False, "merge": False, "release": False, "tag": False, "deployment": False,
    }
    for key, expected in exact_pending.items():
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
