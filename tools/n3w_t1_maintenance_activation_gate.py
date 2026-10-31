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
INVALIDATION_PLAN_SCHEMA = "gh.n3w-t1-e03-replacement-baseline-invalidation-plan/1"
INVALIDATION_REASON = "BROKER_STARTED_AT_CHANGED_AFTER_T1_REBOOT"
INVALIDATION_LAST_OPERATION = "baseline_invalidated_before_apply"
RECOVERY_ROOT = Path("/var/lib/n3w-t1-maintenance/prepublish-recoveries")
RECOVERY_SCHEMA = "gh.n3w-t1-e03-blocked-prepublish-predecessor-recovery/1"
RECOVERY_PLAN_SCHEMA = "gh.n3w-t1-e03-blocked-prepublish-predecessor-recovery-plan/1"
RECOVERY_REASON = "SERVICE_STOP_OWNER_EXIT_137_BEFORE_CANDIDATE_PUBLISH"
PRODUCTION_COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
PRODUCTION_COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
ACTIVE_BLOCKING_STATES = frozenset({"APPLYING", "BLOCKED"})
ACTIVE_ALLOWING_STATES = frozenset(
    {"PREPARING", "READY", "VERIFYING", "ROLLING_BACK"}
)
TERMINAL_STATES = frozenset({"COMMITTED", "ROLLED_BACK", "ABORTED"})
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,199}$")
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


INVALIDATION_RECORD_KEYS = frozenset(
    {
        "schema",
        "invalidation_id",
        "invalidation_id_sha256",
        "authorization_id_sha256",
        "execution_session_id_sha256",
        "plan_sha256",
        "plan",
        "executor_source_head",
        "executor_blob",
        "module_set_sha256",
        "target_transaction_id_sha256",
        "target_transaction_sha256_before",
        "target_generation_before",
        "target_invariant_sha256",
        "reason",
        "product_mutation",
        "service_stop_start",
        "docker_mutation",
        "board_access",
        "state",
        "authorization_consumed",
        "replay_allowed",
        "generation",
        "target_transaction_sha256_after",
        "target_generation_after",
        "last_operation",
        "last_reason",
    }
)
RECOVERY_RECORD_KEYS = frozenset(
    {
        "schema",
        "recovery_id",
        "recovery_id_sha256",
        "authorization_id_sha256",
        "execution_session_id_sha256",
        "plan_sha256",
        "plan",
        "executor_source_head",
        "executor_blob",
        "module_set_sha256",
        "target_transaction_id_sha256",
        "target_transaction_sha256",
        "target_generation",
        "target_operation_seq",
        "reason",
        "product_mutation",
        "service_stop_start",
        "docker_mutation",
        "board_access",
        "state",
        "authorization_consumed",
        "replay_allowed",
        "generation",
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
    transaction_id = value.get("transaction_id")
    if (
        not isinstance(transaction_id, str)
        or IDENTIFIER.fullmatch(transaction_id) is None
    ):
        raise GateError("transaction_id_invalid")
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


def _valid_committed_invalidation_record(record: Any) -> bool:
    if not isinstance(record, dict) or set(record) != INVALIDATION_RECORD_KEYS:
        return False
    if record.get("schema") != INVALIDATION_SCHEMA:
        return False
    invalidation_id = record.get("invalidation_id")
    if (
        not isinstance(invalidation_id, str)
        or IDENTIFIER.fullmatch(invalidation_id) is None
        or record.get("invalidation_id_sha256") != _sha256_text(invalidation_id)
    ):
        return False
    for key in (
        "authorization_id_sha256",
        "execution_session_id_sha256",
        "plan_sha256",
        "module_set_sha256",
        "target_transaction_id_sha256",
        "target_transaction_sha256_before",
        "target_invariant_sha256",
        "target_transaction_sha256_after",
    ):
        value = record.get(key)
        if not isinstance(value, str) or SHA64.fullmatch(value) is None:
            return False
    for key in ("executor_source_head", "executor_blob"):
        value = record.get(key)
        if not isinstance(value, str) or SHA40.fullmatch(value) is None:
            return False
    plan = record.get("plan")
    if (
        not isinstance(plan, dict)
        or record.get("plan_sha256") != _sha256_bytes(_canonical_bytes(plan))
        or plan.get("schema") != INVALIDATION_PLAN_SCHEMA
        or plan.get("reason") != INVALIDATION_REASON
        or plan.get("target_transaction_id_sha256")
        != record.get("target_transaction_id_sha256")
        or plan.get("target_transaction_sha256")
        != record.get("target_transaction_sha256_before")
        or plan.get("target_generation")
        != record.get("target_generation_before")
        or plan.get("target_invariant_sha256")
        != record.get("target_invariant_sha256")
        or plan.get("invalidation_executor_source_head")
        != record.get("executor_source_head")
        or plan.get("invalidation_executor_blob")
        != record.get("executor_blob")
        or plan.get("invalidation_module_set_sha256")
        != record.get("module_set_sha256")
    ):
        return False
    before_generation = record.get("target_generation_before")
    if (
        record.get("state") != "COMMITTED"
        or record.get("generation") != 2
        or record.get("authorization_consumed") is not True
        or record.get("replay_allowed") is not False
        or record.get("reason") != INVALIDATION_REASON
        or record.get("last_operation") != "target_transaction_blocked"
        or record.get("last_reason") is not None
        or not isinstance(before_generation, int)
        or isinstance(before_generation, bool)
        or before_generation < 1
        or record.get("target_generation_after") != before_generation + 1
    ):
        return False
    for key in (
        "product_mutation",
        "service_stop_start",
        "docker_mutation",
        "board_access",
    ):
        if record.get(key) is not False or plan.get(key) is not False:
            return False
    return True


def _committed_invalidation_for_blocked(
    transaction_path: Path,
    value: dict[str, Any],
    invalidation_root: Path,
    *,
    enforce_root_metadata: bool = True,
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
    if enforce_root_metadata:
        meta = invalidation_root.stat()
        if meta.st_uid != 0 or meta.st_gid != 0 or stat.S_IMODE(meta.st_mode) != 0o700:
            return False
    target_id_hash = _sha256_text(str(value["transaction_id"]))
    target_sha = _sha256_file(transaction_path)
    matches = 0
    for path in sorted(invalidation_root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            return False
        if enforce_root_metadata:
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
        if not _valid_committed_invalidation_record(record):
            return False
        if (
            record.get("target_generation_after") != value.get("generation")
            or record.get("target_transaction_sha256_after") != target_sha
        ):
            return False
        matches += 1
    return matches == 1


def _blocked_prepublish_recovery_target(value: dict[str, Any]) -> bool:
    operations = value.get("operations")
    plan = value.get("plan")
    if (
        value.get("state") != "BLOCKED"
        or value.get("authorization_consumed") is not True
        or value.get("replay_allowed") is not False
        or value.get("last_operation") != "blocked"
        or value.get("last_reason") != "operation_reality_unknown"
        or value.get("operation_seq") != 2
        or not isinstance(operations, list)
        or len(operations) != 2
        or not isinstance(plan, dict)
    ):
        return False
    gate_op, stop_op = operations
    if (
        gate_op.get("operation_type") != "activation_gate_install"
        or gate_op.get("status") != "COMPLETE"
        or gate_op.get("last_error_code") is not None
        or gate_op.get("observed_after_fingerprint")
        != gate_op.get("intended_after_fingerprint")
    ):
        return False
    if (
        stop_op.get("operation_type") != "service_stop"
        or stop_op.get("status") != "BLOCKED"
        or stop_op.get("last_error_code") != "application_owner_not_stopped"
        or stop_op.get("before_fingerprint")
        != plan.get("service_before_fingerprint")
        or stop_op.get("intended_after_fingerprint")
        != plan.get("service_stopped_fingerprint")
        or stop_op.get("observed_after_fingerprint")
        in {None, plan.get("service_stopped_fingerprint")}
    ):
        return False
    before = value.get("before")
    intended = value.get("intended_after")
    return (
        isinstance(before, dict)
        and isinstance(intended, dict)
        and before.get("deployment_inputs")
        == plan.get("deployment_before_fingerprint")
        and intended.get("deployment_inputs")
        == plan.get("deployment_candidate_fingerprint")
        and value.get("observed_after") == {}
    )


def _valid_prepublish_recovery_record(
    record: Any,
    *,
    transaction_path: Path,
    target: dict[str, Any],
) -> bool:
    if not isinstance(record, dict) or set(record) != RECOVERY_RECORD_KEYS:
        return False
    if record.get("schema") != RECOVERY_SCHEMA:
        return False
    recovery_id = record.get("recovery_id")
    if (
        not isinstance(recovery_id, str)
        or IDENTIFIER.fullmatch(recovery_id) is None
        or record.get("recovery_id_sha256") != _sha256_text(recovery_id)
    ):
        return False
    for key in (
        "authorization_id_sha256",
        "execution_session_id_sha256",
        "plan_sha256",
        "module_set_sha256",
        "target_transaction_id_sha256",
        "target_transaction_sha256",
    ):
        item = record.get(key)
        if not isinstance(item, str) or SHA64.fullmatch(item) is None:
            return False
    for key in ("executor_source_head", "executor_blob"):
        item = record.get(key)
        if not isinstance(item, str) or SHA40.fullmatch(item) is None:
            return False
    plan = record.get("plan")
    if (
        not isinstance(plan, dict)
        or record.get("plan_sha256") != _sha256_bytes(_canonical_bytes(plan))
        or plan.get("schema") != RECOVERY_PLAN_SCHEMA
        or plan.get("reason") != RECOVERY_REASON
        or plan.get("target_transaction_id_sha256")
        != record.get("target_transaction_id_sha256")
        or plan.get("target_transaction_sha256")
        != record.get("target_transaction_sha256")
        or plan.get("target_generation") != record.get("target_generation")
        or plan.get("target_operation_seq") != record.get("target_operation_seq")
        or plan.get("recovery_executor_source_head")
        != record.get("executor_source_head")
        or plan.get("recovery_executor_blob")
        != record.get("executor_blob")
        or plan.get("recovery_module_set_sha256")
        != record.get("module_set_sha256")
        or plan.get("gate_source_sha256_after")
        != _sha256_file(Path(__file__))
    ):
        return False
    state = record.get("state")
    if (
        record.get("reason") != RECOVERY_REASON
        or record.get("authorization_consumed") is not True
        or record.get("replay_allowed") is not False
        or state not in {"CLAIMED", "COMMITTED", "BLOCKED"}
        or record.get("target_generation") != target.get("generation")
        or record.get("target_operation_seq") != target.get("operation_seq")
        or record.get("target_transaction_id_sha256")
        != _sha256_text(str(target.get("transaction_id")))
        or record.get("target_transaction_sha256")
        != _sha256_file(transaction_path)
    ):
        return False
    expected_generation = {"CLAIMED": 1, "COMMITTED": 2, "BLOCKED": 2}[str(state)]
    expected_last = {
        "CLAIMED": "authorization_claimed",
        "COMMITTED": "predecessor_runtime_restored",
        "BLOCKED": "recovery_blocked",
    }[str(state)]
    if (
        record.get("generation") != expected_generation
        or record.get("last_operation") != expected_last
        or (
            state in {"CLAIMED", "COMMITTED"}
            and record.get("last_reason") is not None
        )
    ):
        return False
    for key, expected in (
        ("product_mutation", False),
        ("service_stop_start", True),
        ("docker_mutation", True),
        ("board_access", False),
    ):
        if record.get(key) is not expected or plan.get(key) is not expected:
            return False
    return True


def _prepublish_recovery_for_blocked(
    transaction_path: Path,
    value: dict[str, Any],
    recovery_root: Path,
    *,
    enforce_root_metadata: bool = True,
) -> str | None:
    if not _blocked_prepublish_recovery_target(value):
        return None
    if recovery_root.is_symlink() or not recovery_root.is_dir():
        return None
    if enforce_root_metadata:
        meta = recovery_root.stat()
        if (
            meta.st_uid != 0
            or meta.st_gid != 0
            or stat.S_IMODE(meta.st_mode) != 0o700
        ):
            return None
    target_id_hash = _sha256_text(str(value["transaction_id"]))
    matches: list[dict[str, Any]] = []
    for path in sorted(recovery_root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            return None
        if enforce_root_metadata:
            meta = path.stat()
            if (
                meta.st_uid != 0
                or meta.st_gid != 0
                or stat.S_IMODE(meta.st_mode) != 0o600
                or meta.st_nlink != 1
            ):
                return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(record, dict):
            return None
        if record.get("schema") != RECOVERY_SCHEMA:
            continue
        if record.get("target_transaction_id_sha256") != target_id_hash:
            continue
        if not _valid_prepublish_recovery_record(
            record,
            transaction_path=transaction_path,
            target=value,
        ):
            return None
        matches.append(record)
    if len(matches) != 1:
        return None
    record = matches[0]
    if record["state"] not in {"CLAIMED", "COMMITTED"}:
        return None
    before = record["plan"].get("deployment_before_fingerprint")
    if (
        not isinstance(before, str)
        or SHA64.fullmatch(before) is None
        or _current_deployment_fingerprint() != before
    ):
        return None
    return str(record["state"])


def evaluate(
    root: Path = TRANSACTION_ROOT,
    invalidation_root: Path = INVALIDATION_ROOT,
    recovery_root: Path = RECOVERY_ROOT,
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
        recovery_state = (
            _prepublish_recovery_for_blocked(path, value, recovery_root)
            if state == "BLOCKED"
            else None
        )
        if recovery_state in {"CLAIMED", "COMMITTED"}:
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
