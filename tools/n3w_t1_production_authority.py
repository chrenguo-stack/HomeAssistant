#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from n3w_t1_production_contract import (
    PHASES,
    ProductionContractError,
    canonical_sha256,
    validate_plan,
)

RUN_SCHEMA = "gh.n3w-t1-production-run-authority/1"
PHASE_SCHEMA = "gh.n3w-t1-production-phase-claim/1"
CONTEXT_SCHEMA = "gh.n3w-t1-production-phase-context/1"
LEDGER_ROOT = Path("/var/lib/n3w-t1-production-runs")
MACHINE_ID_PATH = Path("/etc/machine-id")
SSH_HOST_PUBLIC_KEY = Path("/etc/ssh/ssh_host_ed25519_key.pub")
RUN_ID_RE = re.compile(r"[0-9a-f]{64}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")

RUN_RECORD_FIELDS = {
    "schema",
    "run_id",
    "plan",
    "plan_sha256",
    "state",
    "authorization_consumed",
    "replay_allowed",
    "last_completed_phase",
    "last_claimed_phase",
    "terminal_state",
    "failure_class",
    "created_at",
    "updated_at",
    "board_access",
}

PHASE_BINDING_FIELDS = {
    "source_head",
    "release_id",
    "artifact_sha256",
    "predecessor_sha256",
    "target_binding_sha256",
}

PHASE_RECORD_FIELDS = {
    "schema",
    "run_id",
    "phase",
    "state",
    "binding",
    "binding_sha256",
    "authorization_consumed",
    "replay_allowed",
    "result_sha256",
    "failure_code",
    "claimed_at",
    "updated_at",
    "board_access",
}


class ProductionAuthorityError(RuntimeError):
    pass


def _require_root() -> None:
    if os.geteuid() != 0:
        raise ProductionAuthorityError("root_required")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha(value: object, code: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ProductionAuthorityError(code)
    return value


def _run_dir(root: Path, run_id: str) -> Path:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise ProductionAuthorityError("run_id_invalid")
    return root / run_id


def _run_path(root: Path, run_id: str) -> Path:
    return _run_dir(root, run_id) / "run.json"


def _phase_path(root: Path, run_id: str, phase: str) -> Path:
    if phase not in PHASES:
        raise ProductionAuthorityError("phase_invalid")
    return _run_dir(root, run_id) / f"phase-{phase}.json"


def _validate_dir(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ProductionAuthorityError("ledger_directory_invalid")
    metadata = path.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ProductionAuthorityError("ledger_directory_metadata_invalid")


def _ensure_root(root: Path) -> None:
    if root.exists() or root.is_symlink():
        _validate_dir(root)
        return
    root.mkdir(parents=True, mode=0o700)
    os.chmod(root, 0o700)
    _validate_dir(root)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise ProductionAuthorityError("authority_record_duplicate_key")
        document[key] = value
    return document


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ProductionAuthorityError("authority_record_missing")
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise ProductionAuthorityError("authority_record_metadata_invalid")
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except ProductionAuthorityError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProductionAuthorityError("authority_record_invalid") from error
    if not isinstance(document, dict):
        raise ProductionAuthorityError("authority_record_invalid")
    return document


def _sync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new(path: Path, document: dict[str, Any]) -> None:
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise ProductionAuthorityError("authority_record_exists") from error
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, 0o600)
    _sync_parent(path)


def _replace(path: Path, document: dict[str, Any]) -> None:
    if path.is_symlink():
        raise ProductionAuthorityError("authority_record_symlink")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        _sync_parent(path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _exclusive(root: Path, run_id: str) -> Iterator[None]:
    run_dir = _run_dir(root, run_id)
    _validate_dir(run_dir)
    lock = run_dir / ".lock"
    descriptor = os.open(
        lock,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def target_identity(
    machine_id_path: Path = MACHINE_ID_PATH,
    ssh_public_key_path: Path = SSH_HOST_PUBLIC_KEY,
) -> dict[str, str]:
    if (
        machine_id_path.is_symlink()
        or not machine_id_path.is_file()
        or ssh_public_key_path.is_symlink()
        or not ssh_public_key_path.is_file()
    ):
        raise ProductionAuthorityError("target_identity_source_invalid")
    machine_id = machine_id_path.read_text(encoding="utf-8").strip()
    fields = ssh_public_key_path.read_text(encoding="utf-8").strip().split()
    if not machine_id or len(fields) < 2 or fields[0] != "ssh-ed25519":
        raise ProductionAuthorityError("target_identity_source_invalid")
    try:
        key_blob = base64.b64decode(fields[1], validate=True)
    except ValueError as error:
        raise ProductionAuthorityError("target_host_key_invalid") from error
    host_key_sha256 = _sha256_bytes(key_blob)
    target_binding_sha256 = _sha256_bytes(
        f"{machine_id}\n{host_key_sha256}\n".encode("utf-8")
    )
    return {
        "target_binding_sha256": target_binding_sha256,
        "ssh_host_key_sha256": host_key_sha256,
    }


def _load_run(root: Path, run_id: str) -> dict[str, Any]:
    run = _read(_run_path(root, run_id))
    if set(run) != RUN_RECORD_FIELDS:
        raise ProductionAuthorityError("run_record_fields_invalid")
    if (
        run.get("schema") != RUN_SCHEMA
        or run.get("run_id") != run_id
        or run.get("authorization_consumed") is not True
        or run.get("replay_allowed") is not False
        or run.get("board_access") is not False
        or not isinstance(run.get("plan"), dict)
        or run.get("state") not in {"APPROVED", "IN_PROGRESS", "TERMINAL"}
        or run.get("terminal_state") not in {None, "PASS", "FAIL"}
        or run.get("failure_class") not in {None, "FAILED", "UNKNOWN"}
        or run.get("last_completed_phase") not in {None, *PHASES}
        or run.get("last_claimed_phase") not in {None, *PHASES}
        or not isinstance(run.get("created_at"), int)
        or isinstance(run.get("created_at"), bool)
        or not isinstance(run.get("updated_at"), int)
        or isinstance(run.get("updated_at"), bool)
    ):
        raise ProductionAuthorityError("run_record_invalid")
    normalized_plan = validate_plan(run["plan"])
    if (
        normalized_plan["run_id"] != run_id
        or run.get("plan_sha256") != canonical_sha256(normalized_plan)
    ):
        raise ProductionAuthorityError("run_plan_binding_invalid")
    if run["terminal_state"] is None and run["state"] == "TERMINAL":
        raise ProductionAuthorityError("run_terminal_state_invalid")
    if run["terminal_state"] is not None and run["state"] != "TERMINAL":
        raise ProductionAuthorityError("run_terminal_state_invalid")
    return run


def _load_phase(root: Path, run_id: str, phase: str) -> dict[str, Any]:
    record = _read(_phase_path(root, run_id, phase))
    if set(record) != PHASE_RECORD_FIELDS:
        raise ProductionAuthorityError("phase_record_fields_invalid")
    binding = record.get("binding")
    if not isinstance(binding, dict) or set(binding) != PHASE_BINDING_FIELDS:
        raise ProductionAuthorityError("phase_record_binding_invalid")
    predecessor = binding.get("predecessor_sha256")
    if predecessor is not None:
        _sha(predecessor, "phase_record_predecessor_invalid")
    source_head = binding.get("source_head")
    if (
        not isinstance(source_head, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_head) is None
    ):
        raise ProductionAuthorityError("phase_record_source_invalid")
    for key, code in (
        ("release_id", "phase_record_release_invalid"),
        ("artifact_sha256", "phase_record_artifact_invalid"),
        ("target_binding_sha256", "phase_record_target_invalid"),
    ):
        _sha(binding.get(key), code)
    if (
        record.get("schema") != PHASE_SCHEMA
        or record.get("run_id") != run_id
        or record.get("phase") != phase
        or record.get("state")
        not in {"CLAIMED", "APPLYING", "SUCCEEDED", "FAILED", "UNKNOWN"}
        or record.get("authorization_consumed") is not True
        or record.get("replay_allowed") is not False
        or record.get("board_access") is not False
        or record.get("binding_sha256") != canonical_sha256(binding)
        or not isinstance(record.get("claimed_at"), int)
        or isinstance(record.get("claimed_at"), bool)
        or not isinstance(record.get("updated_at"), int)
        or isinstance(record.get("updated_at"), bool)
    ):
        raise ProductionAuthorityError("phase_record_invalid")
    result_sha = record.get("result_sha256")
    if result_sha is not None:
        _sha(result_sha, "phase_record_result_invalid")
    failure_code = record.get("failure_code")
    if failure_code is not None and (
        not isinstance(failure_code, str) or not failure_code
    ):
        raise ProductionAuthorityError("phase_record_failure_code_invalid")
    return record


def _guard_existing_target_runs(root: Path, target_binding_sha256: str) -> None:
    for entry in root.iterdir():
        if RUN_ID_RE.fullmatch(entry.name) is None:
            raise ProductionAuthorityError("ledger_root_entry_invalid")
        _validate_dir(entry)
        run = _load_run(root, entry.name)
        if run["plan"]["target_binding_sha256"] != target_binding_sha256:
            continue
        if run["terminal_state"] is None:
            raise ProductionAuthorityError("existing_active_run_blocks_approval")
        if run["failure_class"] == "UNKNOWN":
            raise ProductionAuthorityError("existing_unknown_run_blocks_approval")


def approve_run(
    plan: object,
    *,
    root: Path = LEDGER_ROOT,
    now: int | None = None,
    identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    _require_root()
    normalized = validate_plan(plan)
    current = int(time.time()) if now is None else now
    if current < normalized["approved_at"] or current >= normalized["expires_at"]:
        raise ProductionAuthorityError("run_approval_time_invalid")
    observed = identity or target_identity()
    if observed.get("target_binding_sha256") != normalized["target_binding_sha256"]:
        raise ProductionAuthorityError("run_target_binding_mismatch")
    if observed.get("ssh_host_key_sha256") != normalized["ssh_host_key_sha256"]:
        raise ProductionAuthorityError("run_host_key_binding_mismatch")
    _ensure_root(root)
    _guard_existing_target_runs(root, normalized["target_binding_sha256"])
    run_dir = _run_dir(root, normalized["run_id"])
    try:
        run_dir.mkdir(mode=0o700)
    except FileExistsError as error:
        raise ProductionAuthorityError("run_already_exists") from error
    os.chmod(run_dir, 0o700)
    record = {
        "schema": RUN_SCHEMA,
        "run_id": normalized["run_id"],
        "plan": normalized,
        "plan_sha256": canonical_sha256(normalized),
        "state": "APPROVED",
        "authorization_consumed": True,
        "replay_allowed": False,
        "last_completed_phase": None,
        "last_claimed_phase": None,
        "terminal_state": None,
        "failure_class": None,
        "created_at": current,
        "updated_at": current,
        "board_access": False,
    }
    _write_new(_run_path(root, normalized["run_id"]), record)
    return {
        "schema": RUN_SCHEMA,
        "status": "PASS",
        "state": "APPROVED",
        "run_id": normalized["run_id"],
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }


def _predecessor(phase: str) -> str | None:
    index = PHASES.index(phase)
    return PHASES[index - 1] if index else None


def claim_phase(
    run_id: str,
    phase: str,
    binding: object,
    *,
    root: Path = LEDGER_ROOT,
    now: int | None = None,
) -> dict[str, Any]:
    _require_root()
    if phase not in PHASES or not isinstance(binding, dict):
        raise ProductionAuthorityError("phase_binding_invalid")
    if set(binding) != PHASE_BINDING_FIELDS:
        raise ProductionAuthorityError("phase_binding_fields_invalid")
    current = int(time.time()) if now is None else now
    with _exclusive(root, run_id):
        run = _load_run(root, run_id)
        plan = run["plan"]
        if current >= plan["expires_at"] or run["terminal_state"] is not None:
            raise ProductionAuthorityError("run_not_claimable")
        if binding["source_head"] != plan["source_head"]:
            raise ProductionAuthorityError("phase_source_head_mismatch")
        if binding["release_id"] != plan["release_id"]:
            raise ProductionAuthorityError("phase_release_id_mismatch")
        artifact_sha256 = _sha(
            binding["artifact_sha256"],
            "phase_artifact_sha256_invalid",
        )
        if artifact_sha256 != plan["phase_artifact_sha256"][phase]:
            raise ProductionAuthorityError("phase_artifact_binding_mismatch")
        if binding["target_binding_sha256"] != plan["target_binding_sha256"]:
            raise ProductionAuthorityError("phase_target_binding_mismatch")
        predecessor = _predecessor(phase)
        predecessor_sha256 = None
        if predecessor is not None:
            predecessor_path = _phase_path(root, run_id, predecessor)
            predecessor_record = _load_phase(root, run_id, predecessor)
            if predecessor_record.get("state") != "SUCCEEDED":
                raise ProductionAuthorityError("phase_predecessor_not_succeeded")
            predecessor_sha256 = _sha256_file(predecessor_path)
        if binding["predecessor_sha256"] != predecessor_sha256:
            raise ProductionAuthorityError("phase_predecessor_binding_mismatch")
        path = _phase_path(root, run_id, phase)
        if path.exists() or path.is_symlink():
            raise ProductionAuthorityError("phase_already_claimed")
        record = {
            "schema": PHASE_SCHEMA,
            "run_id": run_id,
            "phase": phase,
            "state": "CLAIMED",
            "binding": dict(binding),
            "binding_sha256": canonical_sha256(binding),
            "authorization_consumed": True,
            "replay_allowed": False,
            "result_sha256": None,
            "failure_code": None,
            "claimed_at": current,
            "updated_at": current,
            "board_access": False,
        }
        _write_new(path, record)
        updated = dict(run)
        updated["state"] = "IN_PROGRESS"
        updated["last_claimed_phase"] = phase
        updated["updated_at"] = current
        _replace(_run_path(root, run_id), updated)
        claim_sha256 = _sha256_file(path)
    return {
        "schema": PHASE_SCHEMA,
        "status": "PASS",
        "state": "CLAIMED",
        "run_id": run_id,
        "phase": phase,
        "claim_sha256": claim_sha256,
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }


def begin_phase(
    run_id: str,
    phase: str,
    expected_claim_sha256: str,
    *,
    root: Path = LEDGER_ROOT,
) -> dict[str, Any]:
    expected = _sha(expected_claim_sha256, "phase_claim_sha256_invalid")
    with _exclusive(root, run_id):
        path = _phase_path(root, run_id, phase)
        if _sha256_file(path) != expected:
            raise ProductionAuthorityError("phase_claim_sha256_mismatch")
        record = _load_phase(root, run_id, phase)
        if record.get("state") != "CLAIMED":
            raise ProductionAuthorityError("phase_begin_prestate_invalid")
        record["state"] = "APPLYING"
        record["updated_at"] = int(time.time())
        _replace(path, record)
        claim_sha256 = _sha256_file(path)
    return {
        "schema": PHASE_SCHEMA,
        "status": "PASS",
        "state": "APPLYING",
        "run_id": run_id,
        "phase": phase,
        "claim_sha256": claim_sha256,
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }


def phase_context(
    run_id: str,
    phase: str,
    *,
    root: Path = LEDGER_ROOT,
) -> dict[str, Any]:
    run = _load_run(root, run_id)
    path = _phase_path(root, run_id, phase)
    claim = _load_phase(root, run_id, phase)
    if (
        claim.get("state") != "APPLYING"
        or claim.get("authorization_consumed") is not True
        or claim.get("replay_allowed") is not False
    ):
        raise ProductionAuthorityError("phase_context_prestate_invalid")
    return {
        "schema": CONTEXT_SCHEMA,
        "run_id": run_id,
        "phase": phase,
        "claim_sha256": _sha256_file(path),
        "plan_sha256": run["plan_sha256"],
        "binding": claim["binding"],
        "binding_sha256": claim["binding_sha256"],
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }


def validate_phase_context(
    context: object,
    *,
    required_phase: str,
    root: Path = LEDGER_ROOT,
) -> dict[str, Any]:
    if not isinstance(context, dict) or context.get("phase") != required_phase:
        raise ProductionAuthorityError("phase_context_invalid")
    run_id = context.get("run_id")
    if not isinstance(run_id, str):
        raise ProductionAuthorityError("phase_context_run_id_invalid")
    current = phase_context(run_id, required_phase, root=root)
    if current != context:
        raise ProductionAuthorityError("phase_context_drift")
    return {
        "status": "PASS",
        "run_id": run_id,
        "phase": required_phase,
        "claim_sha256": current["claim_sha256"],
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }


def complete_phase(
    run_id: str,
    phase: str,
    expected_claim_sha256: str,
    result_sha256: str,
    *,
    root: Path = LEDGER_ROOT,
) -> dict[str, Any]:
    expected = _sha(expected_claim_sha256, "phase_claim_sha256_invalid")
    result_digest = _sha(result_sha256, "phase_result_sha256_invalid")
    with _exclusive(root, run_id):
        path = _phase_path(root, run_id, phase)
        if _sha256_file(path) != expected:
            raise ProductionAuthorityError("phase_claim_sha256_mismatch")
        record = _load_phase(root, run_id, phase)
        if record.get("state") != "APPLYING":
            raise ProductionAuthorityError("phase_complete_prestate_invalid")
        record["state"] = "SUCCEEDED"
        record["result_sha256"] = result_digest
        record["updated_at"] = int(time.time())
        _replace(path, record)
        final_sha = _sha256_file(path)
        run = _load_run(root, run_id)
        updated = dict(run)
        updated["last_completed_phase"] = phase
        updated["updated_at"] = int(time.time())
        if phase == "CLOSE_RUN":
            updated["state"] = "TERMINAL"
            updated["terminal_state"] = "PASS"
        _replace(_run_path(root, run_id), updated)
    return {
        "schema": PHASE_SCHEMA,
        "status": "PASS",
        "state": "SUCCEEDED",
        "run_id": run_id,
        "phase": phase,
        "claim_sha256": final_sha,
        "result_sha256": result_digest,
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }


def fail_phase(
    run_id: str,
    phase: str,
    expected_claim_sha256: str,
    *,
    state: str,
    failure_code: str,
    root: Path = LEDGER_ROOT,
) -> dict[str, Any]:
    expected = _sha(expected_claim_sha256, "phase_claim_sha256_invalid")
    if state not in {"FAILED", "UNKNOWN"}:
        raise ProductionAuthorityError("phase_failure_state_invalid")
    if not failure_code or len(failure_code) > 200:
        raise ProductionAuthorityError("phase_failure_code_invalid")
    with _exclusive(root, run_id):
        path = _phase_path(root, run_id, phase)
        if _sha256_file(path) != expected:
            raise ProductionAuthorityError("phase_claim_sha256_mismatch")
        record = _load_phase(root, run_id, phase)
        if record.get("state") not in {"CLAIMED", "APPLYING"}:
            raise ProductionAuthorityError("phase_failure_prestate_invalid")
        record["state"] = state
        record["failure_code"] = failure_code
        record["updated_at"] = int(time.time())
        _replace(path, record)
        final_sha = _sha256_file(path)
        run = _load_run(root, run_id)
        updated = dict(run)
        updated["state"] = "TERMINAL"
        updated["terminal_state"] = "FAIL"
        updated["failure_class"] = state
        updated["updated_at"] = int(time.time())
        _replace(_run_path(root, run_id), updated)
    return {
        "schema": PHASE_SCHEMA,
        "status": "FAIL",
        "state": state,
        "run_id": run_id,
        "phase": phase,
        "claim_sha256": final_sha,
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }


def inspect_run(run_id: str, *, root: Path = LEDGER_ROOT) -> dict[str, Any]:
    run = _load_run(root, run_id)
    phases: dict[str, str] = {}
    for phase in PHASES:
        path = _phase_path(root, run_id, phase)
        if path.exists() or path.is_symlink():
            phases[phase] = str(
                _load_phase(root, run_id, phase).get("state", "UNKNOWN")
            )
    return {
        "schema": RUN_SCHEMA,
        "status": "PASS",
        "run_id": run_id,
        "state": run["state"],
        "terminal_state": run["terminal_state"],
        "last_completed_phase": run["last_completed_phase"],
        "authorization_consumed": True,
        "replay_allowed": False,
        "phases": phases,
        "board_access": False,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ProductionAuthorityError("json_input_invalid")
    document = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )
    if not isinstance(document, dict):
        raise ProductionAuthorityError("json_input_invalid")
    return document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-production-authority")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("identity")
    approve = sub.add_parser("approve")
    approve.add_argument("--plan", type=Path, required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--run-id", required=True)
    claim = sub.add_parser("claim")
    claim.add_argument("--run-id", required=True)
    claim.add_argument("--phase", choices=PHASES, required=True)
    claim.add_argument("--binding", type=Path, required=True)
    begin = sub.add_parser("begin")
    begin.add_argument("--run-id", required=True)
    begin.add_argument("--phase", choices=PHASES, required=True)
    begin.add_argument("--expected-claim-sha256", required=True)
    context = sub.add_parser("context")
    context.add_argument("--run-id", required=True)
    context.add_argument("--phase", choices=PHASES, required=True)
    complete = sub.add_parser("complete")
    complete.add_argument("--run-id", required=True)
    complete.add_argument("--phase", choices=PHASES, required=True)
    complete.add_argument("--expected-claim-sha256", required=True)
    complete.add_argument("--result-sha256", required=True)
    fail = sub.add_parser("fail")
    fail.add_argument("--run-id", required=True)
    fail.add_argument("--phase", choices=PHASES, required=True)
    fail.add_argument("--expected-claim-sha256", required=True)
    fail.add_argument("--state", choices=("FAILED", "UNKNOWN"), required=True)
    fail.add_argument("--failure-code", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "identity":
            document = {"status": "PASS", **target_identity(), "board_access": False}
        elif args.command == "approve":
            document = approve_run(_load_json(args.plan))
        elif args.command == "inspect":
            document = inspect_run(args.run_id)
        elif args.command == "claim":
            document = claim_phase(
                args.run_id,
                args.phase,
                _load_json(args.binding),
            )
        elif args.command == "begin":
            document = begin_phase(
                args.run_id,
                args.phase,
                args.expected_claim_sha256,
            )
        elif args.command == "context":
            document = phase_context(args.run_id, args.phase)
        elif args.command == "complete":
            document = complete_phase(
                args.run_id,
                args.phase,
                args.expected_claim_sha256,
                args.result_sha256,
            )
        else:
            document = fail_phase(
                args.run_id,
                args.phase,
                args.expected_claim_sha256,
                state=args.state,
                failure_code=args.failure_code,
            )
        print(json.dumps(document, sort_keys=True, separators=(",", ":")))
        return 0 if document.get("status") == "PASS" else 2
    except (
        OSError,
        ProductionAuthorityError,
        ProductionContractError,
        RuntimeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
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
