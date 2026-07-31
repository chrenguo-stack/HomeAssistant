#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g08_expired_unexecuted_g09_reauthorization_contract_20260731_v1.py"
DISPOSITION = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g08-expired-unexecuted-disposition-20260731-v1.json"
PENDING = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g09-private-package-static-check-authorization-pending-20260731-v1.json"

spec = importlib.util.spec_from_file_location("g08_expiry", TOOL)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def expect_failure(fn, value, prefix: str) -> None:
    try:
        fn(value)
    except module.G08ExpiryContractError as exc:
        assert str(exc).startswith(prefix), (str(exc), prefix)
    else:
        raise AssertionError("EXPECTED_FAILURE:" + prefix)


def rebind(value: dict, field: str) -> dict:
    changed = copy.deepcopy(value)
    changed[field] = module.canonical_sha256(
        {key: item for key, item in changed.items() if key != field}
    )
    return changed


def main() -> int:
    disposition = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    pending = json.loads(PENDING.read_text(encoding="utf-8"))

    module.verify_disposition(disposition)
    module.verify_pending(pending)

    changed = copy.deepcopy(disposition)
    changed["authorization_claimed"] = True
    expect_failure(module.verify_disposition, changed, "DISPOSITION_BINDING_DRIFT")

    changed = copy.deepcopy(disposition)
    changed["authorization_claimed"] = True
    changed = rebind(changed, "disposition_binding_sha256")
    expect_failure(module.verify_disposition, changed, "DISPOSITION_BINDING_DRIFT")

    changed = copy.deepcopy(disposition)
    changed["board_operation"] = True
    expect_failure(module.verify_disposition, changed, "DISPOSITION_BINDING_DRIFT")

    changed = copy.deepcopy(pending)
    changed["g08_authorization_reusable"] = True
    expect_failure(module.verify_pending, changed, "PENDING_BINDING_DRIFT")

    changed = copy.deepcopy(pending)
    changed["next_gate"] = "D1-DRIFT"
    changed = rebind(changed, "pending_binding_sha256")
    expect_failure(module.verify_pending, changed, "PENDING_BINDING_DRIFT")

    changed = copy.deepcopy(pending)
    changed["g09_private_package_created"] = True
    expect_failure(module.verify_pending, changed, "PENDING_BINDING_DRIFT")

    public_text = "\n".join(path.read_text(encoding="utf-8") for path in (DISPOSITION, PENDING, TOOL))
    for forbidden in (
        "/Users/",
        "ActiveTestRuns",
        "BEGIN PRIVATE KEY",
        "D2_17_AUTHORIZATION.json",
        "authorization-state-g08",
    ):
        assert forbidden not in public_text, forbidden

    print(
        json.dumps(
            {
                "status": "PASS",
                "g08_state": disposition["state"],
                "g08_authorization_claimed": False,
                "g08_authorization_consumed": False,
                "g08_replay_permitted": False,
                "next_package_generation": "G09",
                "next_gate": pending["next_gate"],
                "g09_private_package_created": False,
                "g09_physical_execution_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
