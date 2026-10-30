#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-maintenance-transaction/1"
TRANSACTION_ROOT = Path("/var/lib/n3w-t1-maintenance/transactions")
PRODUCTION_COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
ACTIVE_BLOCKING_STATES = frozenset({"APPLYING", "BLOCKED"})
ACTIVE_ALLOWING_STATES = frozenset(
    {"PREPARING", "READY", "VERIFYING", "ROLLING_BACK"}
)
TERMINAL_STATES = frozenset({"COMMITTED", "ROLLED_BACK", "ABORTED"})
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
TRANSACTION_KEYS = frozenset(
    {
        "schema",
        "transaction_id",
        "authorization_id_sha256",
        "host_binding_sha256",
        "current_release_id",
        "target_release_id",
        "artifact_sha256",
        "executor_source_head",
        "executor_blob",
        "module_set_sha256",
        "plan_sha256",
        "scope",
        "predecessor_sha256",
        "plan",
        "state",
        "authorization_consumed",
        "replay_allowed",
        "generation",
        "operation_seq",
        "before",
        "intended_after",
        "observed_after",
        "execution_sessions",
        "operations",
        "last_operation",
        "last_reason",
    }
)


class GateError(RuntimeError):
    pass


def _private_root(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise GateError("transaction_root_invalid")
    meta = path.stat()
    if meta.st_uid != 0 or meta.st_gid != 0 or stat.S_IMODE(meta.st_mode) != 0o700:
        raise GateError("transaction_root_metadata_invalid")


def _validate_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise GateError("transaction_record_schema_invalid")
    if set(value) != TRANSACTION_KEYS:
        raise GateError("transaction_record_keys_invalid")
    state = value.get("state")
    if state not in ACTIVE_BLOCKING_STATES | ACTIVE_ALLOWING_STATES | TERMINAL_STATES:
        raise GateError("transaction_record_state_invalid")
    if value.get("replay_allowed") is not False:
        raise GateError("transaction_record_replay_invalid")
    if state in {"READY", "APPLYING", "VERIFYING", "ROLLING_BACK", "BLOCKED", "ROLLED_BACK", "COMMITTED"}:
        if value.get("authorization_consumed") is not True:
            raise GateError("transaction_record_authorization_invalid")
    for name in (
        "authorization_id_sha256",
        "host_binding_sha256",
        "current_release_id",
        "target_release_id",
        "artifact_sha256",
        "module_set_sha256",
        "plan_sha256",
        "predecessor_sha256",
    ):
        if not isinstance(value.get(name), str) or SHA64.fullmatch(value[name]) is None:
            raise GateError("transaction_record_digest_invalid")
    for name in ("executor_source_head", "executor_blob"):
        if not isinstance(value.get(name), str) or SHA40.fullmatch(value[name]) is None:
            raise GateError("transaction_record_executor_invalid")
    if (
        not isinstance(value.get("generation"), int)
        or isinstance(value.get("generation"), bool)
        or value["generation"] < 1
    ):
        raise GateError("transaction_record_generation_invalid")
    if (
        not isinstance(value.get("operation_seq"), int)
        or isinstance(value.get("operation_seq"), bool)
        or value["operation_seq"] < 0
    ):
        raise GateError("transaction_record_operation_seq_invalid")
    plan = value.get("plan")
    if not isinstance(plan, dict) or not plan:
        raise GateError("transaction_record_plan_invalid")
    encoded_plan = (
        json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    if hashlib.sha256(encoded_plan).hexdigest() != value["plan_sha256"]:
        raise GateError("transaction_record_plan_hash_invalid")
    before = value.get("before")
    intended = value.get("intended_after")
    observed = value.get("observed_after")
    operations = value.get("operations")
    sessions = value.get("execution_sessions")
    if (
        not isinstance(before, dict)
        or not before
        or not isinstance(intended, dict)
        or set(intended) != set(before)
        or not isinstance(observed, dict)
        or not set(observed).issubset(before)
        or not isinstance(sessions, list)
        or not isinstance(operations, list)
    ):
        raise GateError("transaction_record_state_maps_invalid")
    for group in (before, intended, observed):
        for key, digest in group.items():
            if (
                not isinstance(key, str)
                or not key
                or key.strip() != key
                or not isinstance(digest, str)
                or SHA64.fullmatch(digest) is None
            ):
                raise GateError("transaction_record_state_binding_invalid")
    seen_sessions: set[str] = set()
    for session in sessions:
        if (
            not isinstance(session, dict)
            or set(session) != {"session_id_sha256", "action"}
            or not isinstance(session.get("session_id_sha256"), str)
            or SHA64.fullmatch(session["session_id_sha256"]) is None
            or session["session_id_sha256"] in seen_sessions
            or not isinstance(session.get("action"), str)
            or not session["action"]
            or session["action"].strip() != session["action"]
        ):
            raise GateError("transaction_record_session_invalid")
        seen_sessions.add(session["session_id_sha256"])
    for index, record in enumerate(operations, start=1):
        if (
            not isinstance(record, dict)
            or set(record)
            != {
                "operation_seq",
                "operation_type",
                "before_fingerprint",
                "intended_after_fingerprint",
                "observed_after_fingerprint",
                "status",
                "last_error_code",
            }
            or record.get("operation_seq") != index
            or not isinstance(record.get("operation_type"), str)
            or not record["operation_type"]
            or record["operation_type"].strip() != record["operation_type"]
            or not isinstance(record.get("before_fingerprint"), str)
            or SHA64.fullmatch(record["before_fingerprint"]) is None
            or not isinstance(record.get("intended_after_fingerprint"), str)
            or SHA64.fullmatch(record["intended_after_fingerprint"]) is None
            or record.get("status") not in {"INTENT", "COMPLETE", "FAILED", "BLOCKED"}
        ):
            raise GateError("transaction_record_operation_invalid")
        observed_fingerprint = record.get("observed_after_fingerprint")
        if record["status"] == "INTENT":
            if observed_fingerprint is not None or index != len(operations):
                raise GateError("transaction_record_pending_operation_invalid")
        elif (
            not isinstance(observed_fingerprint, str)
            or SHA64.fullmatch(observed_fingerprint) is None
        ):
            raise GateError("transaction_record_operation_observation_invalid")
        last_error = record.get("last_error_code")
        if last_error is not None and (
            not isinstance(last_error, str)
            or not last_error
            or last_error.strip() != last_error
        ):
            raise GateError("transaction_record_operation_error_invalid")
    if value["operation_seq"] != len(operations):
        raise GateError("transaction_record_operation_seq_mismatch")
    if state == "VERIFYING":
        compose_after = intended.get("compose")
        if (
            not isinstance(compose_after, str)
            or SHA64.fullmatch(compose_after) is None
            or observed.get("compose") != compose_after
        ):
            raise GateError("verifying_compose_not_proven")
        completed = any(
            isinstance(record, dict)
            and record.get("operation_type") == "compose_publish"
            and record.get("status") == "COMPLETE"
            and record.get("intended_after_fingerprint") == compose_after
            and record.get("observed_after_fingerprint") == compose_after
            for record in operations
        )
        if not completed:
            raise GateError("verifying_publish_not_proven")
    return value


def _rollback_predecessor_restored(value: dict[str, Any]) -> bool:
    before = value.get("before")
    operations = value.get("operations")
    if not isinstance(before, dict) or not isinstance(operations, list):
        return False
    compose_before = before.get("compose")
    if not isinstance(compose_before, str) or SHA64.fullmatch(compose_before) is None:
        return False
    return any(
        isinstance(record, dict)
        and record.get("operation_type") == "compose_rollback"
        and record.get("status") == "COMPLETE"
        and record.get("intended_after_fingerprint") == compose_before
        and record.get("observed_after_fingerprint") == compose_before
        for record in operations
    )


def _current_compose_sha256(
    path: Path = PRODUCTION_COMPOSE,
) -> str:
    if path.is_symlink() or not path.is_file():
        raise GateError("compose_reality_unavailable")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise GateError("compose_reality_unavailable") from error
    return digest.hexdigest()


def _record(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise GateError("transaction_record_invalid")
    meta = path.stat()
    if (
        meta.st_uid != 0
        or meta.st_gid != 0
        or stat.S_IMODE(meta.st_mode) != 0o600
        or meta.st_nlink != 1
    ):
        raise GateError("transaction_record_metadata_invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GateError("transaction_record_json_invalid") from error
    return _validate_record(value)

def evaluate(root: Path = TRANSACTION_ROOT) -> tuple[bool, str]:
    if not root.exists():
        return True, "NO_TRANSACTION_ROOT"
    _private_root(root)
    active: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        value = _record(path)
        state = str(value["state"])
        if state in ACTIVE_BLOCKING_STATES | ACTIVE_ALLOWING_STATES:
            txid = value.get("transaction_id")
            if not isinstance(txid, str) or not txid:
                raise GateError("transaction_id_invalid")
            active.append(value)
    if len(active) > 1:
        raise GateError("multiple_active_transactions")
    if not active:
        return True, "NO_ACTIVE_TRANSACTION"
    value = active[0]
    state = str(value["state"])
    if state in ACTIVE_BLOCKING_STATES:
        return False, "MAINTENANCE_BLOCKING"
    if state == "ROLLING_BACK":
        if not _rollback_predecessor_restored(value):
            return False, "MAINTENANCE_BLOCKING"
        before = value.get("before", {}).get("compose")
        if _current_compose_sha256() != before:
            return False, "MAINTENANCE_BLOCKING"
        return True, "MAINTENANCE_ROLLBACK_RESTORED"
    if state == "VERIFYING":
        intended = value.get("intended_after", {}).get("compose")
        if _current_compose_sha256() != intended:
            return False, "MAINTENANCE_BLOCKING"
        return True, "MAINTENANCE_VERIFYING"
    if state in ACTIVE_ALLOWING_STATES:
        return True, "MAINTENANCE_VERIFYING"
    raise GateError("active_state_unhandled")


def main() -> int:
    try:
        allowed, reason = evaluate()
    except GateError as error:
        sys.stderr.write(f"n3w-maintenance-gate: BLOCKED:{error}\n")
        return 1
    if not allowed:
        sys.stderr.write(f"n3w-maintenance-gate: BLOCKED:{reason}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
