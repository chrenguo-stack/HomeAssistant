#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Any

import n3w_t1_production_authority as authority

SCHEMA = "gh.n3w-t1-f5-failed-run-terminalizer/2"
RECOVERY_SCHEMA = "gh.n3w-t1-f5-failed-run-terminalization-recovery/1"
RUN_ID = "56e7cacb162fb2e2e56ff7e112f1a2177b64a68c4a1f1c0fdea66520e051602e"
PHASE = "HOST_BASELINE"
SOURCE_HEAD = "6e228a4b2c7c4ff78918571abb7b583e416615ee"
RELEASE_ID = "b89c9e227e53fcac2ef2717d7b11cd6b64536ce27c9b6b16c2429980049c8a69"
RELEASE_SHA256 = "5291042f87686aecbd6b7e52641c10f69cdae0d56abbf675b8eab8c9bfeb8804"
TARGET_BINDING_SHA256 = "280c06d1753dc676ca7c11b1967ae603a432bb3c996abb305a449c85cf5ca3b3"
SSH_HOST_KEY_SHA256 = "2e6cae2b43ba5d7d0818fa53b4175a6bf58442077b32caf44b0bf886e6e4a901"
BASELINE_LEDGER_ROOT = Path("/var/lib/n3w-t1-host-baseline-production-executions")
RECOVERY_ROOT = Path("/var/lib/n3w-t1-f5-failed-run-terminalizations")
CONFIRMATION = "TERMINALIZE FAILED F5 RUN: YES"
FAILURE_CODE = "KF122_PHASE_CONTEXT_CLI_STATUS_MISSING"
AUTHORIZATION_RE = re.compile(r"N3W_T1_F5_FAILED_RUN_TERMINALIZATION_LIVE_[A-Z0-9_]{8,160}")


class FailedRunTerminalizationError(RuntimeError):
    def __init__(self, code: str, *, mutation_state: str = "NONE") -> None:
        super().__init__(code)
        self.mutation_state = mutation_state


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


def _business_execution_absent(claim_sha256: str, baseline_root: Path) -> None:
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


def _exact_active_prestate(
    *,
    ledger_root: Path,
    baseline_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], str]:
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
    _business_execution_absent(claim_sha256, baseline_root)
    return run, phase, claim_sha256


def inspect_failed_run(
    *,
    ledger_root: Path = authority.LEDGER_ROOT,
    baseline_root: Path = BASELINE_LEDGER_ROOT,
    identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    authority._require_root()
    _identity(identity)
    _run, _phase, claim_sha256 = _exact_active_prestate(
        ledger_root=ledger_root,
        baseline_root=baseline_root,
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
        "mutation_state": "NONE",
        "product_service_start": False,
        "reboot_executed": False,
        "board_access": False,
    }


def _ensure_recovery_root(root: Path) -> None:
    if root.exists() or root.is_symlink():
        if root.is_symlink() or not root.is_dir():
            raise FailedRunTerminalizationError("recovery_root_invalid")
    else:
        root.mkdir(parents=True, mode=0o700)
        os.chmod(root, 0o700)
    metadata = root.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise FailedRunTerminalizationError("recovery_root_metadata_invalid")


def _recovery_path(root: Path) -> Path:
    return root / f"{RUN_ID}.json"


def _read_recovery(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise FailedRunTerminalizationError("recovery_record_invalid")
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise FailedRunTerminalizationError("recovery_record_metadata_invalid")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FailedRunTerminalizationError("recovery_record_invalid") from error
    required = {
        "schema",
        "run_id",
        "phase",
        "authorization_id",
        "authorization_consumed",
        "replay_allowed",
        "state",
        "original_phase_claim_sha256",
        "target_binding_sha256",
        "ssh_host_key_sha256",
        "source_head",
        "release_id",
        "release_sha256",
        "created_at",
        "updated_at",
        "board_access",
    }
    if (
        not isinstance(document, dict)
        or set(document) != required
        or document.get("schema") != RECOVERY_SCHEMA
        or document.get("run_id") != RUN_ID
        or document.get("phase") != PHASE
        or document.get("authorization_consumed") is not True
        or document.get("replay_allowed") is not False
        or document.get("state") not in {"CLAIMED", "APPLYING", "TERMINALIZED"}
        or document.get("target_binding_sha256") != TARGET_BINDING_SHA256
        or document.get("ssh_host_key_sha256") != SSH_HOST_KEY_SHA256
        or document.get("source_head") != SOURCE_HEAD
        or document.get("release_id") != RELEASE_ID
        or document.get("release_sha256") != RELEASE_SHA256
        or document.get("board_access") is not False
        or not isinstance(document.get("created_at"), int)
        or not isinstance(document.get("updated_at"), int)
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("original_phase_claim_sha256")),
        )
        is None
        or AUTHORIZATION_RE.fullmatch(str(document.get("authorization_id")))
        is None
    ):
        raise FailedRunTerminalizationError("recovery_record_invalid")
    return document


def _claim_or_load_recovery(
    *,
    recovery_root: Path,
    authorization_id: str,
    expected_claim_sha256: str,
) -> dict[str, Any]:
    if AUTHORIZATION_RE.fullmatch(authorization_id) is None:
        raise FailedRunTerminalizationError("recovery_authorization_id_invalid")
    _ensure_recovery_root(recovery_root)
    path = _recovery_path(recovery_root)
    if path.exists() or path.is_symlink():
        record = _read_recovery(path)
        if (
            record.get("authorization_id") != authorization_id
            or record.get("original_phase_claim_sha256") != expected_claim_sha256
        ):
            raise FailedRunTerminalizationError(
                "recovery_authorization_binding_mismatch"
            )
        return record
    now = int(time.time())
    record = {
        "schema": RECOVERY_SCHEMA,
        "run_id": RUN_ID,
        "phase": PHASE,
        "authorization_id": authorization_id,
        "authorization_consumed": True,
        "replay_allowed": False,
        "state": "CLAIMED",
        "original_phase_claim_sha256": expected_claim_sha256,
        "target_binding_sha256": TARGET_BINDING_SHA256,
        "ssh_host_key_sha256": SSH_HOST_KEY_SHA256,
        "source_head": SOURCE_HEAD,
        "release_id": RELEASE_ID,
        "release_sha256": RELEASE_SHA256,
        "created_at": now,
        "updated_at": now,
        "board_access": False,
    }
    authority._write_new(path, record)
    try:
        return _read_recovery(path)
    except FailedRunTerminalizationError as error:
        raise FailedRunTerminalizationError(
            str(error),
            mutation_state="UNKNOWN",
        ) from error


def _set_recovery_state(
    record: dict[str, Any],
    *,
    recovery_root: Path,
    state: str,
) -> dict[str, Any]:
    updated = dict(record)
    updated["state"] = state
    updated["updated_at"] = int(time.time())
    authority._replace(_recovery_path(recovery_root), updated)
    observed = _read_recovery(_recovery_path(recovery_root))
    if observed != updated:
        raise FailedRunTerminalizationError(
            "recovery_record_persistence_mismatch",
            mutation_state="UNKNOWN",
        )
    return observed


def _phase_failed_exact(phase: dict[str, Any]) -> bool:
    return (
        phase.get("state") == "FAILED"
        and phase.get("failure_code") == FAILURE_CODE
        and phase.get("result_sha256") is None
        and phase.get("authorization_consumed") is True
        and phase.get("replay_allowed") is False
        and phase.get("binding", {}).get("source_head") == SOURCE_HEAD
        and phase.get("binding", {}).get("release_id") == RELEASE_ID
        and phase.get("binding", {}).get("target_binding_sha256")
        == TARGET_BINDING_SHA256
    )


def _run_binding_exact(run: dict[str, Any]) -> bool:
    plan = run.get("plan")
    return (
        isinstance(plan, dict)
        and plan.get("source_head") == SOURCE_HEAD
        and plan.get("release_id") == RELEASE_ID
        and plan.get("release_sha256") == RELEASE_SHA256
        and plan.get("target_binding_sha256") == TARGET_BINDING_SHA256
        and plan.get("ssh_host_key_sha256") == SSH_HOST_KEY_SHA256
        and run.get("authorization_consumed") is True
        and run.get("replay_allowed") is False
        and run.get("last_claimed_phase") == PHASE
        and run.get("last_completed_phase") is None
    )


def _run_terminal_exact(run: dict[str, Any]) -> bool:
    return (
        _run_binding_exact(run)
        and run.get("state") == "TERMINAL"
        and run.get("terminal_state") == "FAIL"
        and run.get("failure_class") == "FAILED"
    )


def _apply_or_resume_terminalization(
    *,
    expected_claim_sha256: str,
    ledger_root: Path,
    baseline_root: Path,
) -> str:
    with authority._exclusive(ledger_root, RUN_ID):
        run = authority._load_run(ledger_root, RUN_ID)
        phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
        path = authority._phase_path(ledger_root, RUN_ID, PHASE)

        if (
            _run_binding_exact(run)
            and run.get("state") == "IN_PROGRESS"
            and run.get("terminal_state") is None
            and run.get("failure_class") is None
            and phase.get("state") == "APPLYING"
        ):
            if authority._sha256_file(path) != expected_claim_sha256:
                raise FailedRunTerminalizationError("phase_claim_sha256_drift")
            _business_execution_absent(expected_claim_sha256, baseline_root)
            updated_phase = dict(phase)
            updated_phase["state"] = "FAILED"
            updated_phase["failure_code"] = FAILURE_CODE
            updated_phase["updated_at"] = int(time.time())
            authority._replace(path, updated_phase)
            phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
            if not _phase_failed_exact(phase):
                raise FailedRunTerminalizationError(
                    "failed_phase_persistence_mismatch",
                    mutation_state="UNKNOWN",
                )
            mutation_state = "PHASE_FAILED"
        elif (
            _run_binding_exact(run)
            and run.get("state") == "IN_PROGRESS"
            and run.get("terminal_state") is None
            and run.get("failure_class") is None
            and _phase_failed_exact(phase)
        ):
            _business_execution_absent(expected_claim_sha256, baseline_root)
            mutation_state = "PHASE_FAILED"
        elif _run_terminal_exact(run) and _phase_failed_exact(phase):
            _business_execution_absent(expected_claim_sha256, baseline_root)
            return "ALREADY_TERMINAL"
        else:
            raise FailedRunTerminalizationError(
                "failed_run_recovery_prestate_mismatch"
            )

        run = authority._load_run(ledger_root, RUN_ID)
        if run.get("state") != "IN_PROGRESS":
            raise FailedRunTerminalizationError(
                "failed_run_recovery_run_state_drift",
                mutation_state=mutation_state,
            )
        updated_run = dict(run)
        updated_run["state"] = "TERMINAL"
        updated_run["terminal_state"] = "FAIL"
        updated_run["failure_class"] = "FAILED"
        updated_run["updated_at"] = int(time.time())
        authority._replace(authority._run_path(ledger_root, RUN_ID), updated_run)
        return "TERMINALIZED"


def terminalize_failed_run(
    *,
    expected_claim_sha256: str,
    confirmation: str,
    authorization_id: str,
    ledger_root: Path = authority.LEDGER_ROOT,
    baseline_root: Path = BASELINE_LEDGER_ROOT,
    recovery_root: Path = RECOVERY_ROOT,
    identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    authority._require_root()
    if confirmation != CONFIRMATION:
        raise FailedRunTerminalizationError("terminalization_confirmation_invalid")
    if re.fullmatch(r"[0-9a-f]{64}", expected_claim_sha256) is None:
        raise FailedRunTerminalizationError("phase_claim_sha256_invalid")
    _identity(identity)

    recovery_path = _recovery_path(recovery_root)
    if recovery_path.exists() or recovery_path.is_symlink():
        recovery = _read_recovery(recovery_path)
        if (
            recovery.get("authorization_id") != authorization_id
            or recovery.get("original_phase_claim_sha256")
            != expected_claim_sha256
        ):
            raise FailedRunTerminalizationError(
                "recovery_authorization_binding_mismatch"
            )
    else:
        preflight = inspect_failed_run(
            ledger_root=ledger_root,
            baseline_root=baseline_root,
            identity=identity,
        )
        if preflight["phase_claim_sha256"] != expected_claim_sha256:
            raise FailedRunTerminalizationError("phase_claim_sha256_drift")
        recovery = _claim_or_load_recovery(
            recovery_root=recovery_root,
            authorization_id=authorization_id,
            expected_claim_sha256=expected_claim_sha256,
        )

    if recovery["state"] == "TERMINALIZED":
        run = authority._load_run(ledger_root, RUN_ID)
        phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
        if not (_run_terminal_exact(run) and _phase_failed_exact(phase)):
            raise FailedRunTerminalizationError(
                "terminalized_recovery_poststate_drift"
            )
        _business_execution_absent(expected_claim_sha256, baseline_root)
        action = "ALREADY_TERMINAL"
    else:
        if recovery["state"] == "CLAIMED":
            _run, _phase, observed_claim_sha256 = _exact_active_prestate(
                ledger_root=ledger_root,
                baseline_root=baseline_root,
            )
            if observed_claim_sha256 != expected_claim_sha256:
                raise FailedRunTerminalizationError(
                    "claimed_recovery_prestate_drift"
                )
            recovery = _set_recovery_state(
                recovery,
                recovery_root=recovery_root,
                state="APPLYING",
            )
        if recovery["state"] != "APPLYING":
            raise FailedRunTerminalizationError("recovery_state_invalid")
        action = _apply_or_resume_terminalization(
            expected_claim_sha256=expected_claim_sha256,
            ledger_root=ledger_root,
            baseline_root=baseline_root,
        )

    run = authority._load_run(ledger_root, RUN_ID)
    phase = authority._load_phase(ledger_root, RUN_ID, PHASE)
    _business_execution_absent(expected_claim_sha256, baseline_root)
    if not (_run_terminal_exact(run) and _phase_failed_exact(phase)):
        raise FailedRunTerminalizationError(
            "failed_run_terminalization_poststate_invalid",
            mutation_state="UNKNOWN",
        )

    recovery = _read_recovery(recovery_path)
    recovery_transitioned = False
    if recovery["state"] != "TERMINALIZED":
        recovery = _set_recovery_state(
            recovery,
            recovery_root=recovery_root,
            state="TERMINALIZED",
        )
        recovery_transitioned = True
    if recovery["state"] != "TERMINALIZED":
        raise FailedRunTerminalizationError(
            "recovery_terminal_state_invalid",
            mutation_state="UNKNOWN",
        )

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "state": "FAILED_RUN_TERMINALIZED",
        "action": action,
        "run_id": RUN_ID,
        "phase": PHASE,
        "phase_state": "FAILED",
        "failure_code": FAILURE_CODE,
        "target_run_state": "TERMINAL",
        "target_terminal_state": "FAIL",
        "recovery_state": "TERMINALIZED",
        "recovery_authorization_id": authorization_id,
        "authorization_consumed": True,
        "replay_allowed": False,
        "mutation_performed": (
            action != "ALREADY_TERMINAL" or recovery_transitioned
        ),
        "mutation_state": "TERMINAL",
        "mutation_scope": "f5_production_authority_and_recovery_ledger_only",
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
    terminalize.add_argument("--authorization-id", required=True)
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
                authorization_id=args.authorization_id,
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
        mutation_state = (
            error.mutation_state
            if isinstance(error, FailedRunTerminalizationError)
            else "UNKNOWN"
        )
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error_code": str(error)[:300],
                    "mutation_state": mutation_state,
                    "mutation_performed": mutation_state != "NONE",
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
