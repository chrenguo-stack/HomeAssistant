#!/usr/bin/env python3
"""Validate exact B2 evidence and emit hash-only correction dispositions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_contract_20260729_v1 as contract


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    contract.require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
    return value


def capture(b2_result_path: Path) -> dict:
    value = read_json(b2_result_path)
    contract.validate_b2_result(value)
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-baseline-aggregate-digest-correction-capture/1",
        "status": "PASS",
        "b2_disposition": contract.b2_disposition(),
        "invalid_digest_disposition": contract.invalid_legacy_digest_disposition(),
        "corrected_baseline_candidate": contract.corrected_baseline_candidate(),
        "mac_candidate_policy": contract.mac_candidate_policy(),
        "board_operation": False,
        "network_operation": False,
        "physical_request_created": False,
        "physical_request_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--b2-result", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.b2_result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
