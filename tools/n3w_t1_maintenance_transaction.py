#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "gh.n3w-t1-maintenance-transaction/1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
TXID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,199}$")

STATES = frozenset(
    {
        "PREPARING",
        "READY",
        "APPLYING",
        "VERIFYING",
        "COMMITTED",
        "ROLLING_BACK",
        "ROLLED_BACK",
        "BLOCKED",
        "ABORTED",
    }
)
ACTIVE_STATES = frozenset({"PREPARING", "READY", "APPLYING", "VERIFYING", "ROLLING_BACK"})
TERMINAL_STATES = frozenset({"COMMITTED", "ROLLED_BACK", "BLOCKED", "ABORTED"})
MUTATION_STATES = frozenset({"APPLYING", "ROLLING_BACK"})

_ALLOWED = {
    "PREPARING": {"READY", "BLOCKED", "ABORTED"},
    "READY": {"APPLYING", "BLOCKED", "ABORTED"},
    "APPLYING": {"VERIFYING", "ROLLING_BACK", "BLOCKED"},
    "VERIFYING": {"COMMITTED", "ROLLING_BACK", "BLOCKED"},
    "ROLLING_BACK": {"ROLLED_BACK", "BLOCKED"},
    "COMMITTED": set(),
    "ROLLED_BACK": set(),
    "BLOCKED": set(),
    "ABORTED": set(),
}


class MaintenanceTransactionError(RuntimeError):
    pass


@dataclass(frozen=True)
class MaintenanceBinding:
    transaction_id: str
    authorization_id_sha256: str
    host_binding_sha256: str
    release_id: str
    artifact_sha256: str
    executor_source_head: str
    executor_blob: str
    scope: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["scope"] = list(self.scope)
        return value


def canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise MaintenanceTransactionError("document_not_canonical_json") from error


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise MaintenanceTransactionError("evidence_file_invalid")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha(value: Any, name: str, *, git: bool = False) -> str:
    pattern = SHA40 if git else SHA64
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise MaintenanceTransactionError(f"{name}_invalid")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise MaintenanceTransactionError(f"{name}_invalid")
    return value


def validate_binding(binding: MaintenanceBinding) -> MaintenanceBinding:
    if TXID.fullmatch(binding.transaction_id) is None:
        raise MaintenanceTransactionError("transaction_id_invalid")
    _sha(binding.authorization_id_sha256, "authorization_id_sha256")
    _sha(binding.host_binding_sha256, "host_binding_sha256")
    _sha(binding.release_id, "release_id")
    _sha(binding.artifact_sha256, "artifact_sha256")
    _sha(binding.executor_source_head, "executor_source_head", git=True)
    _sha(binding.executor_blob, "executor_blob", git=True)
    if not binding.scope or len(set(binding.scope)) != len(binding.scope):
        raise MaintenanceTransactionError("scope_invalid")
    for action in binding.scope:
        _text(action, "scope_action")
    return binding


def new_transaction(
    binding: MaintenanceBinding,
    *,
    predecessor_sha256: str,
    before: dict[str, str],
    intended_after: dict[str, str],
) -> dict[str, Any]:
    validate_binding(binding)
    _sha(predecessor_sha256, "predecessor_sha256")
    if not isinstance(before, dict) or not before:
        raise MaintenanceTransactionError("before_invalid")
    if not isinstance(intended_after, dict) or set(before) != set(intended_after):
        raise MaintenanceTransactionError("intended_after_invalid")
    for key, value in before.items():
        _text(key, "state_key")
        _sha(value, f"before_{key}")
        _sha(intended_after[key], f"intended_after_{key}")
    return {
        "schema": SCHEMA,
        **binding.to_dict(),
        "predecessor_sha256": predecessor_sha256,
        "state": "PREPARING",
        "authorization_consumed": False,
        "replay_allowed": False,
        "generation": 1,
        "operation_seq": 0,
        "before": deepcopy(before),
        "intended_after": deepcopy(intended_after),
        "observed_after": {},
        "operations": [],
        "last_operation": "created",
        "last_reason": None,
    }


def validate_transaction(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise MaintenanceTransactionError("transaction_not_object")
    expected = {
        "schema",
        "transaction_id",
        "authorization_id_sha256",
        "host_binding_sha256",
        "release_id",
        "artifact_sha256",
        "executor_source_head",
        "executor_blob",
        "scope",
        "predecessor_sha256",
        "state",
        "authorization_consumed",
        "replay_allowed",
        "generation",
        "operation_seq",
        "before",
        "intended_after",
        "observed_after",
        "operations",
        "last_operation",
        "last_reason",
    }
    if set(document) != expected:
        raise MaintenanceTransactionError("transaction_keys_invalid")
    if document.get("schema") != SCHEMA:
        raise MaintenanceTransactionError("transaction_schema_invalid")
    binding = MaintenanceBinding(
        transaction_id=document["transaction_id"],
        authorization_id_sha256=document["authorization_id_sha256"],
        host_binding_sha256=document["host_binding_sha256"],
        release_id=document["release_id"],
        artifact_sha256=document["artifact_sha256"],
        executor_source_head=document["executor_source_head"],
        executor_blob=document["executor_blob"],
        scope=tuple(document["scope"]) if isinstance(document["scope"], list) else (),
    )
    validate_binding(binding)
    _sha(document["predecessor_sha256"], "predecessor_sha256")
    state = document.get("state")
    if state not in STATES:
        raise MaintenanceTransactionError("transaction_state_invalid")
    if not isinstance(document.get("authorization_consumed"), bool):
        raise MaintenanceTransactionError("authorization_consumed_invalid")
    if document.get("replay_allowed") is not False:
        raise MaintenanceTransactionError("replay_allowed_invalid")
    for key in ("generation", "operation_seq"):
        value = document.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MaintenanceTransactionError(f"{key}_invalid")
    before = document.get("before")
    intended = document.get("intended_after")
    observed = document.get("observed_after")
    if not isinstance(before, dict) or not before:
        raise MaintenanceTransactionError("before_invalid")
    if not isinstance(intended, dict) or set(intended) != set(before):
        raise MaintenanceTransactionError("intended_after_invalid")
    if not isinstance(observed, dict) or not set(observed).issubset(before):
        raise MaintenanceTransactionError("observed_after_invalid")
    for group_name, group in (("before", before), ("intended_after", intended), ("observed_after", observed)):
        for key, value in group.items():
            _text(key, f"{group_name}_key")
            _sha(value, f"{group_name}_{key}")
    operations = document.get("operations")
    if not isinstance(operations, list):
        raise MaintenanceTransactionError("operations_invalid")
    expected_seq = 1
    for operation_record in operations:
        if not isinstance(operation_record, dict):
            raise MaintenanceTransactionError("operation_record_invalid")
        expected_keys = {
            "operation_seq",
            "operation_type",
            "before_fingerprint",
            "intended_after_fingerprint",
            "observed_after_fingerprint",
            "status",
            "last_error_code",
        }
        if set(operation_record) != expected_keys:
            raise MaintenanceTransactionError("operation_record_keys_invalid")
        if operation_record.get("operation_seq") != expected_seq:
            raise MaintenanceTransactionError("operation_sequence_invalid")
        _text(operation_record.get("operation_type"), "operation_type")
        _sha(operation_record.get("before_fingerprint"), "operation_before_fingerprint")
        _sha(
            operation_record.get("intended_after_fingerprint"),
            "operation_intended_after_fingerprint",
        )
        observed_value = operation_record.get("observed_after_fingerprint")
        if observed_value is not None:
            _sha(observed_value, "operation_observed_after_fingerprint")
        if operation_record.get("status") not in {"INTENT", "COMPLETE", "FAILED", "BLOCKED"}:
            raise MaintenanceTransactionError("operation_status_invalid")
        error_code = operation_record.get("last_error_code")
        if error_code is not None:
            _text(error_code, "operation_last_error_code")
        expected_seq += 1
    if value := document.get("operation_seq"):
        if value != len(operations):
            raise MaintenanceTransactionError("operation_seq_mismatch")
    elif operations:
        raise MaintenanceTransactionError("operation_seq_mismatch")
    _text(document.get("last_operation"), "last_operation")
    reason = document.get("last_reason")
    if reason is not None:
        _text(reason, "last_reason")
    return deepcopy(document)


def binding_from_transaction(document: dict[str, Any]) -> MaintenanceBinding:
    value = validate_transaction(document)
    return MaintenanceBinding(
        transaction_id=value["transaction_id"],
        authorization_id_sha256=value["authorization_id_sha256"],
        host_binding_sha256=value["host_binding_sha256"],
        release_id=value["release_id"],
        artifact_sha256=value["artifact_sha256"],
        executor_source_head=value["executor_source_head"],
        executor_blob=value["executor_blob"],
        scope=tuple(value["scope"]),
    )


def require_mutation_binding(
    document: dict[str, Any],
    expected: MaintenanceBinding,
    *,
    action: str,
    allowed_states: Iterable[str] = MUTATION_STATES,
) -> dict[str, Any]:
    value = validate_transaction(document)
    validate_binding(expected)
    actual = binding_from_transaction(value)
    if actual != expected:
        raise MaintenanceTransactionError("mutation_binding_mismatch")
    if action not in expected.scope:
        raise MaintenanceTransactionError("mutation_scope_forbidden")
    allowed = frozenset(allowed_states)
    if value["state"] not in allowed:
        raise MaintenanceTransactionError("mutation_state_forbidden")
    if value["authorization_consumed"] is not True:
        raise MaintenanceTransactionError("authorization_not_consumed")
    if value["replay_allowed"] is not False:
        raise MaintenanceTransactionError("replay_forbidden_contract_drift")
    return value


def transition(
    document: dict[str, Any],
    target_state: str,
    *,
    operation: str,
    reason: str | None = None,
    observed_after: dict[str, str] | None = None,
) -> dict[str, Any]:
    value = validate_transaction(document)
    current = value["state"]
    if target_state not in _ALLOWED[current]:
        raise MaintenanceTransactionError(f"transition_invalid:{current}:{target_state}")
    _text(operation, "operation")
    if reason is not None:
        _text(reason, "reason")
    if observed_after is not None:
        if not isinstance(observed_after, dict) or not set(observed_after).issubset(value["before"]):
            raise MaintenanceTransactionError("observed_after_invalid")
        for key, item in observed_after.items():
            _sha(item, f"observed_after_{key}")
        value["observed_after"] = deepcopy(observed_after)
    value["state"] = target_state
    value["generation"] += 1
    value["last_operation"] = operation
    value["last_reason"] = reason
    return value


def mark_ready(document: dict[str, Any]) -> dict[str, Any]:
    return transition(document, "READY", operation="prepare_complete")


def claim_authorization(document: dict[str, Any]) -> dict[str, Any]:
    value = validate_transaction(document)
    if value["state"] != "READY":
        raise MaintenanceTransactionError("claim_state_invalid")
    if value["authorization_consumed"] is True:
        raise MaintenanceTransactionError("authorization_already_consumed")
    value["authorization_consumed"] = True
    value["state"] = "APPLYING"
    value["generation"] += 1
    value["last_operation"] = "authorization_claimed"
    value["last_reason"] = None
    return value



def begin_operation(
    document: dict[str, Any],
    *,
    operation_type: str,
    before_fingerprint: str,
    intended_after_fingerprint: str,
) -> dict[str, Any]:
    value = validate_transaction(document)
    _text(operation_type, "operation_type")
    _sha(before_fingerprint, "operation_before_fingerprint")
    _sha(intended_after_fingerprint, "operation_intended_after_fingerprint")
    if value["state"] not in MUTATION_STATES:
        raise MaintenanceTransactionError("operation_state_forbidden")
    if value["operations"] and value["operations"][-1]["status"] == "INTENT":
        raise MaintenanceTransactionError("operation_intent_already_pending")
    sequence = value["operation_seq"] + 1
    value["operations"].append(
        {
            "operation_seq": sequence,
            "operation_type": operation_type,
            "before_fingerprint": before_fingerprint,
            "intended_after_fingerprint": intended_after_fingerprint,
            "observed_after_fingerprint": None,
            "status": "INTENT",
            "last_error_code": None,
        }
    )
    value["operation_seq"] = sequence
    value["generation"] += 1
    value["last_operation"] = operation_type + ":intent"
    value["last_reason"] = None
    return value


def finish_operation(
    document: dict[str, Any],
    *,
    observed_after_fingerprint: str,
    status: str = "COMPLETE",
    error_code: str | None = None,
) -> dict[str, Any]:
    value = validate_transaction(document)
    _sha(observed_after_fingerprint, "operation_observed_after_fingerprint")
    if status not in {"COMPLETE", "FAILED", "BLOCKED"}:
        raise MaintenanceTransactionError("operation_finish_status_invalid")
    if not value["operations"] or value["operations"][-1]["status"] != "INTENT":
        raise MaintenanceTransactionError("operation_intent_missing")
    if error_code is not None:
        _text(error_code, "operation_last_error_code")
    record = value["operations"][-1]
    record["observed_after_fingerprint"] = observed_after_fingerprint
    record["status"] = status
    record["last_error_code"] = error_code
    value["generation"] += 1
    value["last_operation"] = record["operation_type"] + ":" + status.casefold()
    value["last_reason"] = error_code
    return value


def pending_operation(document: dict[str, Any]) -> dict[str, Any] | None:
    value = validate_transaction(document)
    if not value["operations"]:
        return None
    record = value["operations"][-1]
    return deepcopy(record) if record["status"] == "INTENT" else None


def compose_state(before_sha256: str, after_sha256: str, observed_sha256: str) -> str:
    _sha(before_sha256, "compose_before_sha256")
    _sha(after_sha256, "compose_after_sha256")
    _sha(observed_sha256, "compose_observed_sha256")
    if before_sha256 == after_sha256:
        raise MaintenanceTransactionError("compose_contract_degenerate")
    if observed_sha256 == before_sha256:
        return "BEFORE"
    if observed_sha256 == after_sha256:
        return "AFTER"
    return "UNKNOWN"


def require_compose_publishable(
    before_sha256: str,
    after_sha256: str,
    observed_sha256: str,
) -> str:
    state = compose_state(before_sha256, after_sha256, observed_sha256)
    if state == "UNKNOWN":
        raise MaintenanceTransactionError("compose_unknown_blocked")
    return state


def require_compose_rollbackable(
    before_sha256: str,
    after_sha256: str,
    observed_sha256: str,
) -> str:
    state = compose_state(before_sha256, after_sha256, observed_sha256)
    if state == "UNKNOWN":
        raise MaintenanceTransactionError("rollback_compose_unknown_blocked")
    return state


def recovery_disposition(document: dict[str, Any], observed: dict[str, str]) -> str:
    value = validate_transaction(document)
    if set(observed) != set(value["before"]):
        raise MaintenanceTransactionError("recovery_observation_incomplete")
    states = {
        key: compose_state(value["before"][key], value["intended_after"][key], observed[key])
        for key in value["before"]
    }
    unique = set(states.values())
    if "UNKNOWN" in unique or len(unique) != 1:
        return "BLOCKED"
    only = next(iter(unique))
    if only == "BEFORE":
        return "BEFORE"
    if only == "AFTER":
        return "AFTER"
    raise MaintenanceTransactionError("recovery_state_invalid")


def assert_predecessor_immutable(path: Path, expected_sha256: str) -> None:
    _sha(expected_sha256, "predecessor_sha256")
    if sha256_file(path) != expected_sha256:
        raise MaintenanceTransactionError("predecessor_evidence_changed")


def ensure_no_other_active(
    documents: Iterable[dict[str, Any]],
    *,
    transaction_id: str,
) -> None:
    active = []
    for document in documents:
        value = validate_transaction(document)
        if value["transaction_id"] != transaction_id and value["state"] in ACTIVE_STATES:
            active.append(value["transaction_id"])
    if active:
        raise MaintenanceTransactionError("other_active_transaction")


class TransactionStore:
    def __init__(self, path: Path, *, enforce_root_metadata: bool = True):
        self.path = path
        self.enforce_root_metadata = enforce_root_metadata

    def _require_parent(self) -> None:
        parent = self.path.parent
        if parent.is_symlink() or not parent.is_dir():
            raise MaintenanceTransactionError("transaction_parent_invalid")
        if self.enforce_root_metadata:
            metadata = parent.stat()
            if metadata.st_uid != 0 or metadata.st_gid != 0:
                raise MaintenanceTransactionError("transaction_parent_owner_invalid")
            if (metadata.st_mode & 0o777) != 0o700:
                raise MaintenanceTransactionError("transaction_parent_mode_invalid")

    def _verify_file_metadata(self) -> None:
        if self.path.is_symlink() or not self.path.is_file():
            raise MaintenanceTransactionError("transaction_missing")
        metadata = self.path.stat()
        if (metadata.st_mode & 0o777) != 0o600:
            raise MaintenanceTransactionError("transaction_mode_invalid")
        if self.enforce_root_metadata and (metadata.st_uid != 0 or metadata.st_gid != 0):
            raise MaintenanceTransactionError("transaction_owner_invalid")

    def load(self) -> dict[str, Any]:
        self._require_parent()
        self._verify_file_metadata()
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise MaintenanceTransactionError("transaction_read_invalid") from error
        return validate_transaction(value)

    def create(self, document: dict[str, Any]) -> None:
        self._require_parent()
        value = validate_transaction(document)
        payload = canonical_bytes(value)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.path, flags, 0o600)
        except FileExistsError as error:
            raise MaintenanceTransactionError("transaction_exists") from error
        try:
            os.fchmod(fd, 0o600)
            if self.enforce_root_metadata:
                os.fchown(fd, 0, 0)
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        self._fsync_parent()

    def save(self, document: dict[str, Any], *, expected_generation: int) -> None:
        self._require_parent()
        current = self.load()
        if current["generation"] != expected_generation:
            raise MaintenanceTransactionError("transaction_generation_conflict")
        value = validate_transaction(document)
        if value["generation"] <= current["generation"]:
            raise MaintenanceTransactionError("transaction_generation_not_advanced")
        if value["transaction_id"] != current["transaction_id"]:
            raise MaintenanceTransactionError("transaction_id_changed")
        payload = canonical_bytes(value)
        fd, raw = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        tmp = Path(raw)
        try:
            os.fchmod(fd, 0o600)
            if self.enforce_root_metadata:
                os.fchown(fd, 0, 0)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
            self._fsync_parent()
        finally:
            tmp.unlink(missing_ok=True)

    def _fsync_parent(self) -> None:
        fd = os.open(self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
