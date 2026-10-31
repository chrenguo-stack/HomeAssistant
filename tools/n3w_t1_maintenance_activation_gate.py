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
INVALIDATION_ROOT = Path("/var/lib/n3w-t1-maintenance/invalidations")
INVALIDATION_SCHEMA = "gh.n3w-t1-e03-replacement-baseline-invalidation/1"
INVALIDATION_REASON = "BROKER_STARTED_AT_CHANGED_AFTER_T1_REBOOT"
INVALIDATION_LAST_OPERATION = "baseline_invalidated_before_apply"
PRODUCTION_COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
PRODUCTION_COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
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
        deployment_after = intended.get("deployment_inputs")
        if (
            not isinstance(deployment_after, str)
            or SHA64.fullmatch(deployment_after) is None
            or observed.get("deployment_inputs") != deployment_after
        ):
            raise GateError("verifying_deployment_not_proven")
        completed = any(
            isinstance(record, dict)
            and record.get("operation_type") == "deployment_inputs_publish"
            and record.get("status") == "COMPLETE"
            and record.get("intended_after_fingerprint") == deployment_after
            and record.get("observed_after_fingerprint") == deployment_after
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
    deployment_before = before.get("deployment_inputs")
    if (
        not isinstance(deployment_before, str)
        or SHA64.fullmatch(deployment_before) is None
    ):
        return False
    return any(
        isinstance(record, dict)
        and record.get("operation_type") == "deployment_inputs_rollback"
        and record.get("status") == "COMPLETE"
        and record.get("intended_after_fingerprint") == deployment_before
        and record.get("observed_after_fingerprint") == deployment_before
        for record in operations
    )


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise GateError("deployment_reality_unavailable")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise GateError("deployment_reality_unavailable") from error
    return digest.hexdigest()


def _current_deployment_fingerprint(
    compose: Path = PRODUCTION_COMPOSE,
    compose_env: Path = PRODUCTION_COMPOSE_ENV,
) -> str:
    material = {
        "compose_sha256": _sha256_file(compose),
        "compose_env_sha256": _sha256_file(compose_env),
    }
    encoded = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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

def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _committed_invalidation_for_blocked(
    transaction_path: Path,
    value: dict[str, Any],
    invalidation_root: Path,
) -> bool:
    if (
        value.get("state") != "BLOCKED"
        or value.get("last_operation") != INVALIDATION_LAST_OPERATION
        or value.get("last_reason") != INVALIDATION_REASON
        or value.get("authorization_consumed") is not True
        or value.get("replay_allowed") is not False
        or value.get("operation_seq") != 0
        or value.get("operations") != []
        or value.get("observed_after") != {}
    ):
        return False
    if (
        invalidation_root.is_symlink()
        or not invalidation_root.is_dir()
    ):
        return False
    meta = invalidation_root.stat()
    if meta.st_uid != 0 or meta.st_gid != 0 or stat.S_IMODE(meta.st_mode) != 0o700:
        return False
    target_id_hash = _sha256_text(str(value["transaction_id"]))
    target_sha = _sha256_file(transaction_path)
    matches = 0
    for path in sorted(invalidation_root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            return False
        meta = path.stat()
        if meta.st_uid != 0 or meta.st_gid != 0 or stat.S_IMODE(meta.st_mode) != 0o600:
            return False
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return False
        if not isinstance(record, dict):
            return False
        if record.get("schema") != INVALIDATION_SCHEMA:
            continue
        if record.get("target_transaction_id_sha256") != target_id_hash:
            continue
        plan = record.get("plan")
        if not isinstance(plan, dict):
            return False
        if record.get("plan_sha256") != _sha256_bytes(_canonical_bytes(plan)):
            return False
        if (
            record.get("state") != "COMMITTED"
            or record.get("authorization_consumed") is not True
            or record.get("replay_allowed") is not False
            or record.get("reason") != INVALIDATION_REASON
            or record.get("product_mutation") is not False
            or record.get("service_stop_start") is not False
            or record.get("docker_mutation") is not False
            or record.get("board_access") is not False
            or record.get("target_transaction_sha256_after") != target_sha
            or record.get("target_generation_after") != value.get("generation")
            or plan.get("reason") != INVALIDATION_REASON
            or plan.get("target_transaction_id_sha256") != target_id_hash
            or plan.get("product_mutation") is not False
            or plan.get("service_stop_start") is not False
            or plan.get("docker_mutation") is not False
            or plan.get("board_access") is not False
        ):
            return False
        matches += 1
    return matches == 1


def evaluate(
    root: Path = TRANSACTION_ROOT,
    invalidation_root: Path = INVALIDATION_ROOT,
) -> tuple[bool, str]:
    if not root.exists():
        return True, "NO_TRANSACTION_ROOT"
    _private_root(root)
    active: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        value = _record(path)
        state = str(value["state"])
        if state == "BLOCKED" and _committed_invalidation_for_blocked(
            path,
            value,
            invalidation_root,
        ):
            continue
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
        before = value.get("before", {}).get("deployment_inputs")
        if _current_deployment_fingerprint() != before:
            return False, "MAINTENANCE_BLOCKING"
        return True, "MAINTENANCE_ROLLBACK_RESTORED"
    if state == "VERIFYING":
        intended = value.get("intended_after", {}).get("deployment_inputs")
        if _current_deployment_fingerprint() != intended:
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
