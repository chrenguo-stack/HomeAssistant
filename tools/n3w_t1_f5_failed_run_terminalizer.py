#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import n3w_t1_production_authority as authority

SCHEMA = "gh.n3w-t1-f5-failed-run-terminalizer/1"
RUN_ID = "56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e"
PHASE = "HOST_BASELINE"
SOURCE_HEAD = "6e228a4b2c7c4ff78918571abb7b583e416615ee"
RELEASE_ID = "b89c9e227e53fcac2ef2717d7b11cd6b64536ce27c9b6b16c2429980049c8a69"
RELEASE_SHA256 = "5291042f87686aecbd6b7e52641c10f69cdae0d56abbf675b8eab8c9bfeb8804"
TARGET_BINDING_SHA256 = "280c06d1753dc676ca7c11b1967ae603a432bb3c996abb305a449c85cf5ca3b3"
SSH_HOST_KEY_SHA256 = "2e6cae2b43ba5d7d0818fa53b4175a6bf58442077b32caf44b0bf886e6e4a901"
BASELINE_LEDGER_ROOT = Path("/var/lib/n3w-t1-host-baseline-production-executions")
CONFIRMATION = "TERMINALIZE FAILED F5 RUN: YES"
FAILURE_CODE = "KF122_PHASE_CONTEXT_CLI_STATUS_MISSING"


class FailedRunTerminalizationError(RuntimeError):
    pass


def _baseline_paths(claim_sha256: str, root: Path) -> tuple[Path, Path]:
    digest = hashlib.sha256(
        f"{RUN_ID}\n{PHASE}\n{claim_sha256}\n".encode("utf-8")
    ).hexdigest()
    return root / f"{digest}.claim.json", root / f"{digest}.complete.json"


def _identity(expected: dict[str, str] | None) -> dict[str, str]:
    observed = authority.target_identity() if expected is None else expected
    if (
        observed.get("target_binding_sha256") != TARGET_BINDING_SHA256
        or observed.get("ssh_host_key_sha256") != SSH_HOST_KEY_SHA256
    ):
        raise FailedRunTerminalizationError("target_identity_mismatch")
    return observed


def inspect_failed_run(
    *,
    ledger_root: Path = authority.LEDGER_ROOT,
    baseline_root: Path = BASELINE_LEDGER_ROOT,
    identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    authority._require_root()
    _identity(identity)
    run = authority._load_run(ledger_root, RUN_ID)
    phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
    plan = run["plan"]
    if (
        run.get("authorization_consumed") is not True
        or run.get("replay_allowed") is not False
        or run.get("state") != "IN_PROGRESS"
        or run.get("terminal_state") is not None
        or run.get("failure_class") is not None
        or run.get("last_claimed_phase") != PHASE
        or run.get("last_completed_phase") is not None
        or plan.get("source_head") != SOURCE_HEAD
        or plan.get("release_id") != RELEASE_ID
        or plan.get("release_sha256") != RELEASE_SHA256
        or plan.get("target_binding_sha256") != TARGET_BINDING_SHA256
        or plan.get("ssh_host_key_sha256") != SSH_HOST_KEY_SHA256
        or phase.get("state") != "APPLYING"
        or phase.get("authorization_consumed") is not True
        or phase.get("replay_allowed") is not False
        or phase.get("result_sha256") is not None
        or phase.get("failure_code") is not None
        or phase.get("binding", {}).get("source_head") != SOURCE_HEAD
        or phase.get("binding", {}).get("release_id") != RELEASE_ID
        or phase.get("binding", {}).get("target_binding_sha256")
        != TARGET_BINDING_SHA256
    ):
        raise FailedRunTerminalizationError("failed_run_prestate_mismatch")
    phase_path = authority._phase_path(ledger_root, RUN_ID, PHASE)
    claim_sha256 = authority._sha256_file(phase_path)
    claim_path, complete_path = _baseline_paths(claim_sha256, baseline_root)
    if (
        claim_path.exists()
        or claim_path.is_symlink()
        or complete_path.exists()
        or complete_path.is_symlink()
    ):
        raise FailedRunTerminalizationError(
            "host_baseline_business_execution_present"
        )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "ELIGIBLE_FOR_TERMINALIZATION",
        "run_id": RUN_ID,
        "phase": PHASE,
        "phase_state": "APPLYING",
        "phase_claim_sha256": claim_sha256,
        "host_baseline_business_execution_claim_absent": True,
        "host_baseline_business_execution_complete_absent": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "mutation_performed": False,
        "product_service_start": False,
        "reboot_executed": False,
        "board_access": False,
    }


def terminalize_failed_run(
    *,
    expected_claim_sha256: str,
    confirmation: str,
    ledger_root: Path = authority.LEDGER_ROOT,
    baseline_root: Path = BASELINE_LEDGER_ROOT,
    identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise FailedRunTerminalizationError("terminalization_confirmation_invalid")
    preflight = inspect_failed_run(
        ledger_root=ledger_root,
        baseline_root=baseline_root,
        identity=identity,
    )
    if preflight["phase_claim_sha256"] != expected_claim_sha256:
        raise FailedRunTerminalizationError("phase_claim_sha256_drift")
    failed = authority.fail_phase(
        RUN_ID,
        PHASE,
        expected_claim_sha256,
        state="FAILED",
        failure_code=FAILURE_CODE,
        root=ledger_root,
    )
    run = authority._load_run(ledger_root, RUN_ID)
    phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
    if (
        failed.get("status") != "FAIL"
        or failed.get("state") != "FAILED"
        or run.get("state") != "TERMINAL"
        or run.get("terminal_state") != "FAIL"
        or run.get("failure_class") != "FAILED"
        or run.get("last_claimed_phase") != PHASE
        or run.get("last_completed_phase") is not None
        or phase.get("state") != "FAILED"
        or phase.get("failure_code") != FAILURE_CODE
        or phase.get("result_sha256") is not None
        or phase.get("authorization_consumed") is not True
        or phase.get("replay_allowed") is not False
    ):
        raise FailedRunTerminalizationError(
            "failed_run_terminalization_poststate_invalid"
        )
    claim_path, complete_path = _baseline_paths(expected_claim_sha256, baseline_root)
    if (
        claim_path.exists()
        or claim_path.is_symlink()
        or complete_path.exists()
        or complete_path.is_symlink()
    ):
        raise FailedRunTerminalizationError(
            "host_baseline_business_execution_poststate_invalid"
        )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "FAILED_RUN_TERMINALIZED",
        "run_id": RUN_ID,
        "phase": PHASE,
        "phase_state": "FAILED",
        "failure_code": FAILURE_CODE,
        "target_run_state": "TERMINAL",
        "target_terminal_state": "FAIL",
        "authorization_consumed": True,
        "replay_allowed": False,
        "mutation_performed": True,
        "mutation_scope": "f5_production_authority_ledger_only",
        "host_baseline_business_execution_claim_absent": True,
        "host_baseline_business_execution_complete_absent": True,
        "product_service_start": False,
        "reboot_executed": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    terminalize = sub.add_parser("terminalize")
    terminalize.add_argument("--expected-claim-sha256", required=True)
    terminalize.add_argument("--confirm", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "inspect":
            report = inspect_failed_run()
        else:
            report = terminalize_failed_run(
                expected_claim_sha256=args.expected_claim_sha256,
                confirmation=args.confirm,
            )
    except (
        FailedRunTerminalizationError,
        authority.ProductionAuthorityError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error_code": str(error)[:300],
                    "mutation_performed": False,
                    "product_service_start": False,
                    "reboot_executed": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
