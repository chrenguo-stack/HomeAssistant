#!/usr/bin/env python3
"""Build the source-only corrected execution closure and H5 request draft."""
from __future__ import annotations

import argparse
import json

import h3_n2_stage2d9r_g3r_baseline_aggregate_digest_correction_contract_20260729_v1 as contract


def build(source_sha: str, review_binding_sha256: str) -> dict:
    closure = contract.build_corrected_execution_closure(source_sha, review_binding_sha256)
    request = contract.build_h5_request_draft(source_sha, review_binding_sha256)
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-corrected-execution-closure-builder/1",
        "status": "PASS",
        "corrected_execution_closure": closure,
        "corrected_execution_closure_sha256": contract.canonical_json_sha256(closure),
        "h5_request_draft": request,
        "h5_request_draft_sha256": contract.canonical_json_sha256(request),
        "physical_request_created": False,
        "physical_request_authorized": False,
        "board_operation": False,
        "network_operation": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--review-binding-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_sha, args.review_binding_sha256), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
