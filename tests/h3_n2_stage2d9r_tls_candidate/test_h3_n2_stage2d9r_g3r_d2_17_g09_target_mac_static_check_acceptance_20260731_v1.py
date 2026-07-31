#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g09_target_mac_static_check_acceptance_contract_20260731_v1.py"
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g09-target-mac-static-check-pass-20260731-v1.json"
PENDING = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g09-physical-execution-pending-20260731-v1.json"

spec = importlib.util.spec_from_file_location("g09_acceptance", TOOL)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def expect_failure(fn, value, code_prefix: str) -> None:
    try:
        fn(value)
    except module.G09AcceptanceError as exc:
        assert str(exc).startswith(code_prefix), (str(exc), code_prefix)
    else:
        raise AssertionError("EXPECTED_FAILURE:" + code_prefix)


def main() -> int:
    acceptance = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    pending = json.loads(PENDING.read_text(encoding="utf-8"))

    module.verify_acceptance(acceptance)
    module.verify_pending(pending)

    changed = copy.deepcopy(acceptance)
    changed["configured_core_validate_authorization_executed"] = False
    expect_failure(module.verify_acceptance, changed, "ACCEPTANCE_BINDING_DRIFT")

    rebound = copy.deepcopy(acceptance)
    rebound["authorization_claimed"] = True
    rebound["acceptance_binding_sha256"] = module.canonical_sha256(
        {key: value for key, value in rebound.items() if key != "acceptance_binding_sha256"}
    )
    expect_failure(module.verify_acceptance, rebound, "ACCEPTANCE_BINDING_DRIFT")

    changed = copy.deepcopy(pending)
    changed["physical_execution_authorized"] = True
    expect_failure(module.verify_pending, changed, "PHYSICAL_PENDING_BINDING_DRIFT")

    rebound_pending = copy.deepcopy(pending)
    rebound_pending["next_gate"] = "D1-DRIFT"
    rebound_pending["physical_pending_binding_sha256"] = module.canonical_sha256(
        {key: value for key, value in rebound_pending.items() if key != "physical_pending_binding_sha256"}
    )
    expect_failure(module.verify_pending, rebound_pending, "PHYSICAL_PENDING_BINDING_DRIFT")

    public_text = "\n".join(path.read_text(encoding="utf-8") for path in (ACCEPTANCE, PENDING, TOOL))
    for forbidden in ("/Users/", "ActiveTestRuns", "D2_17_AUTHORIZATION.json", "BEGIN PRIVATE KEY"):
        assert forbidden not in public_text, forbidden

    print(json.dumps({
        "status": "PASS",
        "acceptance_binding_sha256": acceptance["acceptance_binding_sha256"],
        "physical_pending_binding_sha256": pending["physical_pending_binding_sha256"],
        "configured_core_validate_authorization_executed": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_execution_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
