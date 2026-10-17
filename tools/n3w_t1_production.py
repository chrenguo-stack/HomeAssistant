#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import stat
import sys
import time
from pathlib import Path
from typing import Any, Callable, Protocol

from n3w_t1_production_contract import (
    PHASES,
    PLAN_SCHEMA,
    RESULT_SCHEMA,
    ProductionContractError,
    canonical_sha256,
    final_outcome,
    phase_artifact_sha256,
    public_result,
    validate_preflight_report,
    validate_release,
)


APPROVAL_RECORD_SCHEMA = "gh.n3w-t1-production-approval-record/1"


class ProductionError(RuntimeError):
    pass


class ProductionBackend(Protocol):
    def connect_pre_reboot(self) -> dict[str, object]:
        ...

    def target_identity(self) -> dict[str, str]:
        ...

    def preflight(
        self,
        *,
        release: dict[str, Any],
        identity: dict[str, str],
    ) -> dict[str, object]:
        ...

    def approve_run(self, plan: dict[str, Any]) -> dict[str, object]:
        ...

    def execute_phase(
        self,
        phase: str,
        *,
        plan: dict[str, Any],
        predecessor_sha256: str | None,
    ) -> dict[str, object]:
        ...

    def transition_reboot(self) -> dict[str, object]:
        ...

    def connect_post_reboot(self) -> dict[str, object]:
        ...

    def close_session(self) -> dict[str, object]:
        ...


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_new_json(path: Path, document: dict[str, Any], mode: int = 0o600) -> None:
    if path.exists() or path.is_symlink():
        raise ProductionError("record_already_exists")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ProductionError("record_parent_invalid")
    os.chmod(path.parent, 0o700)
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, mode)
    directory_fd = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _approval_record_path(private_record_path: Path) -> Path:
    return private_record_path.with_name(f"{private_record_path.name}.approval.json")


def _read_private_record(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ProductionError("private_record_missing")
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise ProductionError("private_record_metadata_invalid")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProductionError("private_record_invalid") from error
    if not isinstance(document, dict):
        raise ProductionError("private_record_invalid")
    return document


def load_release(path: Path) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file():
        raise ProductionError("release_file_invalid")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProductionError("release_file_invalid") from error
    normalized = validate_release(document)
    return normalized, _sha256_file(path)


def build_plan(
    release: dict[str, Any],
    *,
    release_sha256: str,
    target_binding_sha256: str,
    ssh_host_key_sha256: str,
    preflight_sha256: str,
    now: int | None = None,
    max_duration_seconds: int = 4 * 60 * 60,
    run_id: str | None = None,
) -> dict[str, Any]:
    current = int(time.time()) if now is None else now
    if max_duration_seconds <= 0:
        raise ProductionError("max_duration_invalid")
    identifier = run_id or secrets.token_hex(32)
    if len(identifier) != 64 or any(character not in "0123456789abcdef" for character in identifier):
        raise ProductionError("run_id_invalid")
    plan = {
        "schema": PLAN_SCHEMA,
        "run_id": identifier,
        "release_id": release["release_id"],
        "release_sha256": release_sha256,
        "source_head": release["source_head"],
        "target_binding_sha256": target_binding_sha256,
        "ssh_host_key_sha256": ssh_host_key_sha256,
        "preflight_sha256": preflight_sha256,
        "phase_artifact_sha256": {
            phase: phase_artifact_sha256(release, phase) for phase in PHASES
        },
        "plan_digest": "0" * 64,
        "approved_at": current,
        "expires_at": current + max_duration_seconds,
        "max_duration_seconds": max_duration_seconds,
        "phases": list(PHASES),
        "reboot_budget": 1,
    }
    plan["plan_digest"] = canonical_sha256(plan)
    return plan


def approval_summary(plan: dict[str, Any]) -> str:
    return (
        "START PRODUCTION RUN "
        f"{plan['run_id'][:12]} "
        f"TARGET {plan['target_binding_sha256'][:12]} "
        f"RELEASE {plan['release_id'][:12]} "
        "PLAN install+provision+activate+persistence+certificate+one-reboot"
    )


def _result_digest(report: object) -> str:
    if not isinstance(report, dict):
        raise ProductionError("phase_report_invalid")
    if report.get("status") != "PASS":
        raise ProductionError(
            f"phase_report_not_pass:{str(report.get('status'))[:80]}"
        )
    return canonical_sha256(report)


def run_production(
    release: dict[str, Any],
    *,
    release_sha256: str,
    backend: ProductionBackend,
    approval: Callable[[str], bool],
    private_record_path: Path,
    public_record_path: Path,
    now: int | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    normalized_release = validate_release(release)
    approval_record_path = _approval_record_path(private_record_path)
    for output_path in (
        approval_record_path,
        private_record_path,
        public_record_path,
    ):
        if output_path.exists() or output_path.is_symlink():
            raise ProductionError("record_already_exists")
    connected = False
    post_reboot_connected = False
    device_acceptance = False
    session_closed = False
    override_check_ids: list[str] = []
    terminal_phase: str | None = None
    plan: dict[str, Any] | None = None
    phase_reports: dict[str, dict[str, Any]] = {}
    failure_code: str | None = None
    approval_record_sha256: str | None = None
    try:
        connection = backend.connect_pre_reboot()
        if connection.get("status") != "PASS":
            raise ProductionError("pre_reboot_connection_failed")
        connected = True
        identity = backend.target_identity()
        target_binding = identity.get("target_binding_sha256")
        host_key = identity.get("ssh_host_key_sha256")
        if not isinstance(target_binding, str) or not isinstance(host_key, str):
            raise ProductionError("target_identity_invalid")
        preflight = validate_preflight_report(
            backend.preflight(
                release=normalized_release,
                identity=dict(identity),
            )
        )
        preflight_sha256 = canonical_sha256(preflight)
        plan = build_plan(
            normalized_release,
            release_sha256=release_sha256,
            target_binding_sha256=target_binding,
            ssh_host_key_sha256=host_key,
            preflight_sha256=preflight_sha256,
            now=now,
            run_id=run_id,
        )
        if approval(approval_summary(plan)) is not True:
            raise ProductionError("production_approval_declined")
        approval_record = {
            "schema": APPROVAL_RECORD_SCHEMA,
            "status": "PASS",
            "state": "APPROVED_PENDING_TARGET_CLAIM",
            "run_id": plan["run_id"],
            "plan": plan,
            "preflight": preflight,
            "release_sha256": release_sha256,
            "board_access": False,
        }
        _atomic_new_json(approval_record_path, approval_record, 0o600)
        approval_record_sha256 = _sha256_file(approval_record_path)
        approved = backend.approve_run(plan)
        if approved.get("status") != "PASS":
            raise ProductionError("production_approval_not_persisted")

        predecessor: str | None = None
        for phase in PHASES:
            report = backend.execute_phase(
                phase,
                plan=plan,
                predecessor_sha256=predecessor,
            )
            digest = _result_digest(report)
            phase_reports[phase] = dict(report)
            predecessor = digest
            terminal_phase = phase
            for check_id in report.get("override_check_ids", []):
                if isinstance(check_id, str) and check_id not in override_check_ids:
                    override_check_ids.append(check_id)
            if phase == "REBOOT_CONTROL":
                reboot = backend.transition_reboot()
                if reboot.get("status") != "PASS":
                    raise ProductionError("reboot_transition_failed")
                reconnect = backend.connect_post_reboot()
                if reconnect.get("status") != "PASS":
                    raise ProductionError("post_reboot_connection_failed")
                post_reboot_connected = True
            if phase == "FINALIZE":
                if report.get("device_acceptance") is not True:
                    raise ProductionError("device_acceptance_not_proven")
                device_acceptance = True

        if terminal_phase != "CLOSE_RUN":
            raise ProductionError("run_terminal_phase_missing")
    except Exception as error:
        failure_code = str(error)[:300] or type(error).__name__
    finally:
        try:
            closed = backend.close_session()
            session_closed = closed.get("status") == "PASS" and closed.get(
                "session_closed"
            ) is True
        except Exception:
            session_closed = False

    if plan is None:
        raise ProductionError(failure_code or "plan_not_created")

    outcome = (
        "FAIL"
        if failure_code is not None
        else final_outcome(
            device_acceptance=device_acceptance,
            operator_session_closed=session_closed,
            evidence_complete=True,
            override_check_ids=override_check_ids,
        )
    )
    private = {
        "schema": RESULT_SCHEMA,
        "status": "PASS" if outcome != "FAIL" else "FAIL",
        "final_outcome": outcome,
        "release_id": normalized_release["release_id"],
        "release_sha256": release_sha256,
        "source_head": normalized_release["source_head"],
        "run_id_sha256": hashlib.sha256(plan["run_id"].encode("ascii")).hexdigest(),
        "target_binding_sha256": plan["target_binding_sha256"],
        "ssh_host_key_sha256": plan["ssh_host_key_sha256"],
        "device_acceptance": device_acceptance,
        "operator_session_closed": session_closed,
        "evidence_complete": True,
        "override_used": bool(override_check_ids),
        "override_check_ids": override_check_ids,
        "terminal_phase": terminal_phase,
        "board_access": False,
        "production_service_start": device_acceptance,
        "failure_code": failure_code,
        "connection_epoch_count": 2 if post_reboot_connected else (1 if connected else 0),
        "phase_reports": phase_reports,
        "plan": plan,
        "approval_record_sha256": approval_record_sha256,
    }
    try:
        _atomic_new_json(private_record_path, private, 0o600)
        public = public_result(private)
        _atomic_new_json(public_record_path, public, 0o600)
    except Exception as error:
        raise ProductionError("evidence_write_failed") from error
    return private


def inspect_record(path: Path) -> dict[str, Any]:
    document = _read_private_record(path)
    if document.get("schema") != RESULT_SCHEMA:
        raise ProductionError("private_record_schema_invalid")
    return {
        "schema": RESULT_SCHEMA,
        "status": "PASS",
        "final_outcome": document.get("final_outcome"),
        "terminal_phase": document.get("terminal_phase"),
        "device_acceptance": document.get("device_acceptance"),
        "operator_session_closed": document.get("operator_session_closed"),
        "evidence_complete": document.get("evidence_complete"),
        "override_used": document.get("override_used"),
        "board_access": False,
    }


def verify_record(path: Path) -> dict[str, Any]:
    document = _read_private_record(path)
    public = public_result(document)
    return {
        "schema": RESULT_SCHEMA,
        "status": "PASS",
        "private_result_sha256": _sha256_file(path),
        "public_result": public,
        "board_access": False,
    }


def prompt_for_approval(summary: str) -> bool:
    print(summary, flush=True)
    return input("Type START PRODUCTION RUN to approve: ").strip() == (
        "START PRODUCTION RUN"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-production")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--release", type=Path, required=True)
    run.add_argument("--private-record", type=Path, required=True)
    run.add_argument("--public-record", type=Path, required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--record", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--record", type=Path, required=True)
    return parser


def main(
    argv: list[str] | None = None,
    *,
    backend_factory: Callable[[dict[str, Any], Path], ProductionBackend] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "inspect":
            document = inspect_record(args.record)
        elif args.command == "verify":
            document = verify_record(args.record)
        else:
            release, release_sha256 = load_release(args.release)
            if backend_factory is None:
                raise ProductionError("exact_release_runtime_backend_required")
            backend = backend_factory(release, args.release)
            document = run_production(
                release,
                release_sha256=release_sha256,
                backend=backend,
                approval=prompt_for_approval,
                private_record_path=args.private_record,
                public_record_path=args.public_record,
            )
        print(json.dumps(document, sort_keys=True, separators=(",", ":")))
        return 0 if document.get("status") == "PASS" else 2
    except (
        OSError,
        ProductionContractError,
        ProductionError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": str(error)[:300] or type(error).__name__,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
