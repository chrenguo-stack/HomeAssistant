#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

import n3w_t1_maintenance_transaction as maintenance
import n3w_t1_r10_e03_blocked_prepublish_predecessor_recovery as prepublish
import n3w_t1_r10_e03_claimed_transaction_retirement as retirement
import n3w_t1_r10_e03_successor_recovery as e03

SCHEMA = "gh.n3w-t1-e03-blocked-postpublish-predecessor-recovery/1"
PLAN_SCHEMA = (
    "gh.n3w-t1-e03-blocked-postpublish-predecessor-recovery-plan/1"
)
REASON = "SERVICE_START_GATE_CONFLICT_AFTER_CANDIDATE_PUBLISH"
CONFIRMATION = (
    "N3W_T1_R10_E03_BLOCKED_POSTPUBLISH_PREDECESSOR_RECOVERY"
)
AUTHORIZATION_PREFIX = (
    "N3W_T1_R10_E03_BLOCKED_POSTPUBLISH_PREDECESSOR_RECOVERY_"
)
RECOVERY_ROOT = e03.MAINTENANCE_ROOT / "postpublish-recoveries"

EXPECTED_TARGET_TRANSACTION_ID = (
    "n3w-t1-e03-successor-retry-20261031-02"
)
EXPECTED_TARGET_TRANSACTION_SHA256 = (
    "c722f03b59ebc127850e1a7dbd612d3192c2dcd9bb501f01cb0978e00bd561ba"
)
EXPECTED_TARGET_GENERATION = 16
EXPECTED_TARGET_OPERATION_SEQ = 4
EXPECTED_TARGET_EXECUTOR_SOURCE_HEAD = (
    "31f1398716c7dc2f144ef050bd5f8ac3a244a697"
)

HISTORICAL_TRANSACTION_ID = (
    "n3w-t1-e03-fresh-successor-replacement-20261031-01"
)
HISTORICAL_TRANSACTION_SHA256 = (
    "bb96c2fa6588a10bf3203b5000def7069bcf38ea94d84548884a0166f1c7fc11"
)
HISTORICAL_RECOVERY_ID = "n3w-e03-prepublish-recovery-20261031-01"
HISTORICAL_RECOVERY_SHA256 = (
    "37517f6e3c5270a67daeb05f569966395732478ecc8e476b3a24a3f2ec433b93"
)

EXPECTED_GATE_BEFORE_SHA256 = (
    "ee7e0a9dc4d6d256eaaec4ec9449d0af8bcdc0e0c4b679a19e61f81e1bc357e4"
)
EXPECTED_STOPPED_LISTENERS = {
    "tcp_8883": 1,
    "tcp_47110": 0,
    "udp_47111": 0,
    "tcp_47112": 0,
}
RECOVERY_STABILITY_SECONDS = 30.0
RECOVERY_POLL_SECONDS = 2.0

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,199}$")

RECORD_KEYS = frozenset(
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


class RecoveryError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def sha_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise RecoveryError("file_invalid")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    ).hexdigest()


def _identifier(value: str, name: str) -> str:
    if IDENTIFIER.fullmatch(value or "") is None:
        raise RecoveryError(f"{name}_invalid")
    return value


def _sha(value: Any, name: str, *, git: bool = False) -> str:
    pattern = SHA40 if git else SHA64
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise RecoveryError(f"{name}_invalid")
    return value


def _authorization_id(value: str) -> str:
    if (
        not value.startswith(AUTHORIZATION_PREFIX)
        or len(value) > 200
        or not value.replace("_", "").replace("-", "").isalnum()
    ):
        raise RecoveryError("authorization_id_invalid")
    return value


def runtime_authority() -> dict[str, str]:
    source_head = os.environ.get("N3W_POSTPUBLISH_RECOVERY_SOURCE_HEAD")
    if not isinstance(source_head, str) or SHA40.fullmatch(source_head) is None:
        raise RecoveryError("executor_source_head_unbound")
    current = Path(__file__)
    base = current.parent
    paths = (
        base / "n3w_t1_portable_image_identity.py",
        base / "n3w_t1_maintenance_transaction.py",
        base / "n3w_t1_maintenance_activation_gate.py",
        base / "n3w_t1_production_v2_contract.py",
        base / "n3w_t1_r10_e03_claimed_transaction_retirement.py",
        base / "n3w_t1_r10_e03_successor_recovery.py",
        base / "n3w_t1_r10_e03_blocked_prepublish_predecessor_recovery.py",
        current,
    )
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise RecoveryError("executor_module_set_unavailable")
    material = {path.name: git_blob(path) for path in paths}
    return {
        "source_head": source_head,
        "executor_blob": git_blob(current),
        "module_set_sha256": sha_bytes(canonical(material)),
    }


def _target_path(transaction_id: str) -> Path:
    _identifier(transaction_id, "target_transaction_id")
    return e03.TRANSACTION_ROOT / f"{transaction_id}.json"


def _recovery_path(recovery_id: str) -> Path:
    _identifier(recovery_id, "recovery_id")
    return RECOVERY_ROOT / f"{recovery_id}.json"


def _ensure_private_root() -> None:
    e03._ensure_private_dir(RECOVERY_ROOT)


def _assert_target_shape(document: dict[str, Any]) -> dict[str, Any]:
    value = maintenance.validate_transaction(document)
    operations = value["operations"]
    plan = value["plan"]
    if (
        value["transaction_id"] != EXPECTED_TARGET_TRANSACTION_ID
        or value["state"] != "BLOCKED"
        or value["authorization_consumed"] is not True
        or value["replay_allowed"] is not False
        or value["last_operation"] != "blocked"
        or value["last_reason"] != "operation_poststate_unproven"
        or value["generation"] != EXPECTED_TARGET_GENERATION
        or value["operation_seq"] != EXPECTED_TARGET_OPERATION_SEQ
        or len(operations) != 4
        or value["executor_source_head"]
        != EXPECTED_TARGET_EXECUTOR_SOURCE_HEAD
        or value["artifact_sha256"] != e03.TARGET_ARTIFACT_SHA256
        or not isinstance(plan, dict)
    ):
        raise RecoveryError("target_transaction_shape_invalid")
    expected = (
        ("activation_gate_install", "COMPLETE", None),
        ("service_stop", "COMPLETE", None),
        ("deployment_inputs_publish", "COMPLETE", None),
        (
            "service_start",
            "BLOCKED",
            "operation_poststate_unproven",
        ),
    )
    for operation, (kind, status, error) in zip(operations, expected):
        if (
            operation.get("operation_type") != kind
            or operation.get("status") != status
            or operation.get("last_error_code") != error
        ):
            raise RecoveryError("target_operation_shape_invalid")
    before = plan.get("deployment_before_fingerprint")
    candidate = plan.get("deployment_candidate_fingerprint")
    stopped = plan.get("service_stopped_fingerprint")
    running = plan.get("service_running_fingerprint")
    for name, value_sha in (
        ("deployment_before_fingerprint", before),
        ("deployment_candidate_fingerprint", candidate),
        ("service_stopped_fingerprint", stopped),
        ("service_running_fingerprint", running),
    ):
        _sha(value_sha, name)
    if (
        operations[1].get("intended_after_fingerprint") != stopped
        or operations[1].get("observed_after_fingerprint") != stopped
        or operations[2].get("before_fingerprint") != before
        or operations[2].get("intended_after_fingerprint") != candidate
        or operations[2].get("observed_after_fingerprint") != candidate
        or operations[3].get("before_fingerprint") != stopped
        or operations[3].get("intended_after_fingerprint") != running
        or operations[3].get("observed_after_fingerprint") != stopped
        or value["before"].get("deployment_inputs") != before
        or value["intended_after"].get("deployment_inputs") != candidate
        or value["observed_after"].get("deployment_inputs") != candidate
    ):
        raise RecoveryError("target_transaction_binding_invalid")
    return value


def _assert_historical_recovery() -> None:
    historical_path = _target_path(HISTORICAL_TRANSACTION_ID)
    if sha_file(historical_path) != HISTORICAL_TRANSACTION_SHA256:
        raise RecoveryError("historical_transaction_drift")
    historical = maintenance.TransactionStore(historical_path).load()
    prepublish._assert_target_shape(historical)
    recovery_path = (
        prepublish.RECOVERY_ROOT / f"{HISTORICAL_RECOVERY_ID}.json"
    )
    if sha_file(recovery_path) != HISTORICAL_RECOVERY_SHA256:
        raise RecoveryError("historical_recovery_drift")
    record = prepublish.RecoveryStore(recovery_path).load()
    if (
        record.get("state") != "COMMITTED"
        or record.get("authorization_consumed") is not True
        or record.get("replay_allowed") is not False
        or record.get("target_transaction_id_sha256")
        != sha_text(HISTORICAL_TRANSACTION_ID)
        or record.get("target_transaction_sha256")
        != HISTORICAL_TRANSACTION_SHA256
        or record.get("target_generation") != historical["generation"]
        or record.get("target_operation_seq")
        != historical["operation_seq"]
    ):
        raise RecoveryError("historical_recovery_not_committed")


def _assert_target_static_bindings(
    transaction_id: str,
    target: dict[str, Any],
) -> dict[str, Any]:
    if transaction_id != EXPECTED_TARGET_TRANSACTION_ID:
        raise RecoveryError("target_transaction_id_invalid")
    target_path = _target_path(transaction_id)
    if sha_file(target_path) != EXPECTED_TARGET_TRANSACTION_SHA256:
        raise RecoveryError("target_transaction_sha256_drift")
    if e03.host_binding_sha256() != target["host_binding_sha256"]:
        raise RecoveryError("host_binding_drift")
    maintenance.assert_predecessor_immutable(
        e03.PREDECESSOR_TX,
        target["predecessor_sha256"],
    )
    e03.predecessor_evidence(target["predecessor_sha256"])
    target_plan = target["plan"]
    expected_f4 = target_plan.get("current_f4_authority")
    expected_f4_sha = target_plan.get("current_f4_authority_sha256")
    if (
        not isinstance(expected_f4, dict)
        or not isinstance(expected_f4_sha, str)
        or SHA64.fullmatch(expected_f4_sha) is None
        or e03.sha_bytes(e03.canonical(expected_f4)) != expected_f4_sha
    ):
        raise RecoveryError("current_f4_authority_binding_invalid")
    e03._assert_current_f4_authority(expected_f4)
    _assert_historical_recovery()
    return target_plan


def _raw_stopped() -> dict[str, Any]:
    semantic = e03._service_semantic()
    if semantic != {
        "active": "inactive",
        "enabled": "enabled",
        "manager_count": 0,
        "homeassistant_count": 0,
    } and semantic != {
        "active": "failed",
        "enabled": "enabled",
        "manager_count": 0,
        "homeassistant_count": 0,
    }:
        raise RecoveryError("application_owner_not_stopped")
    return semantic


def _gate_blocking() -> None:
    result = e03.run(
        (str(e03.GATE_TARGET),),
        allowed=frozenset({0, 1}),
    )
    if result.returncode != 1:
        raise RecoveryError("maintenance_gate_not_blocking")


def _plan_locked(
    transaction_id: str,
    *,
    authority: dict[str, str],
) -> dict[str, Any]:
    target_path = _target_path(transaction_id)
    target = _assert_target_shape(
        maintenance.TransactionStore(target_path).load()
    )
    target_plan = _assert_target_static_bindings(
        transaction_id,
        target,
    )
    if e03._deployment_reality(target_plan) != target_plan[
        "deployment_candidate_fingerprint"
    ]:
        raise RecoveryError("deployment_not_exact_candidate")
    if e03._service_fingerprint() != target_plan[
        "service_stopped_fingerprint"
    ]:
        raise RecoveryError("stopped_service_fingerprint_drift")
    raw_service = _raw_stopped()
    rendered = e03.render_compose_payload(e03.COMPOSE.read_bytes())
    if (
        e03._service_record(rendered, "manager").get("image")
        != e03.TARGET_MANAGER_IMAGE
        or e03._service_record(rendered, "homeassistant").get("image")
        != e03.HA_IMAGE
        or e03._service_record(rendered, "broker").get("image")
        != e03.BROKER_IMAGE
    ):
        raise RecoveryError("rendered_candidate_drift")
    e03._broker_continuity(target_plan)
    if e03.listener_snapshot() != EXPECTED_STOPPED_LISTENERS:
        raise RecoveryError("stopped_listener_reality_drift")
    active = [
        document
        for document in e03._active_maintenance_documents()
        if document["state"] in maintenance.ACTIVE_STATES
    ]
    if active:
        raise RecoveryError("other_active_transaction")
    _gate_blocking()
    before_gate_sha = sha_file(e03.GATE_TARGET)
    after_gate_sha = sha_bytes(e03._gate_source_bytes())
    if before_gate_sha not in {
        EXPECTED_GATE_BEFORE_SHA256,
        after_gate_sha,
    }:
        raise RecoveryError("gate_source_prestate_unknown")
    return {
        "schema": PLAN_SCHEMA,
        "reason": REASON,
        "target_transaction_id_sha256": sha_text(transaction_id),
        "target_transaction_sha256": sha_file(target_path),
        "target_generation": target["generation"],
        "target_operation_seq": target["operation_seq"],
        "target_executor_source_head": target["executor_source_head"],
        "target_executor_blob": target["executor_blob"],
        "target_module_set_sha256": target["module_set_sha256"],
        "target_artifact_sha256": target["artifact_sha256"],
        "host_binding_sha256": target["host_binding_sha256"],
        "predecessor_sha256": target["predecessor_sha256"],
        "current_f4_authority_sha256": target_plan[
            "current_f4_authority_sha256"
        ],
        "historical_transaction_sha256": HISTORICAL_TRANSACTION_SHA256,
        "historical_recovery_sha256": HISTORICAL_RECOVERY_SHA256,
        "deployment_before_fingerprint": target_plan[
            "deployment_before_fingerprint"
        ],
        "deployment_candidate_fingerprint": target_plan[
            "deployment_candidate_fingerprint"
        ],
        "service_stopped_fingerprint": target_plan[
            "service_stopped_fingerprint"
        ],
        "service_running_fingerprint": target_plan[
            "service_running_fingerprint"
        ],
        "manager_predecessor_container_id": target_plan[
            "manager_predecessor_container_id"
        ],
        "services_nrestarts": target_plan["services_nrestarts"],
        "ha_mqtt_sha256": target_plan["ha_mqtt_sha256"],
        "broker_baseline": target_plan["broker_baseline"],
        "preauth_ledger": target_plan["preauth_ledger"],
        "raw_service_active_state": raw_service["active"],
        "gate_source_sha256_before": before_gate_sha,
        "gate_source_sha256_after": after_gate_sha,
        "recovery_executor_source_head": authority["source_head"],
        "recovery_executor_blob": authority["executor_blob"],
        "recovery_module_set_sha256": authority["module_set_sha256"],
        "product_mutation": True,
        "service_stop_start": True,
        "docker_mutation": True,
        "board_access": False,
    }


def preflight(transaction_id: str) -> dict[str, Any]:
    authority = runtime_authority()
    with retirement.readonly_global_lock():
        plan = _plan_locked(transaction_id, authority=authority)
        if _existing_recovery_for_target(
            plan["target_transaction_id_sha256"]
        ):
            raise RecoveryError("target_recovery_already_exists")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "preflight",
        "recovery_plan_sha256": sha_bytes(canonical(plan)),
        "target_transaction_id_sha256": plan[
            "target_transaction_id_sha256"
        ],
        "target_transaction_sha256": plan["target_transaction_sha256"],
        "target_generation": plan["target_generation"],
        "target_operation_seq": plan["target_operation_seq"],
        "deployment": "EXACT_CANDIDATE",
        "service_state": "STOPPED",
        "broker_continuity": True,
        "candidate_published": True,
        "product_mutation": True,
        "board_access": False,
    }


def _record_from_plan(
    *,
    plan: dict[str, Any],
    recovery_id: str,
    authorization_id: str,
    execution_session_id: str,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "recovery_id": _identifier(recovery_id, "recovery_id"),
        "recovery_id_sha256": sha_text(recovery_id),
        "authorization_id_sha256": sha_text(
            _authorization_id(authorization_id)
        ),
        "execution_session_id_sha256": sha_text(
            _identifier(execution_session_id, "execution_session_id")
        ),
        "plan_sha256": sha_bytes(canonical(plan)),
        "plan": json.loads(canonical(plan)),
        "executor_source_head": plan["recovery_executor_source_head"],
        "executor_blob": plan["recovery_executor_blob"],
        "module_set_sha256": plan["recovery_module_set_sha256"],
        "target_transaction_id_sha256": plan[
            "target_transaction_id_sha256"
        ],
        "target_transaction_sha256": plan["target_transaction_sha256"],
        "target_generation": plan["target_generation"],
        "target_operation_seq": plan["target_operation_seq"],
        "reason": REASON,
        "product_mutation": True,
        "service_stop_start": True,
        "docker_mutation": True,
        "board_access": False,
        "state": "CLAIMED",
        "authorization_consumed": True,
        "replay_allowed": False,
        "generation": 1,
        "last_operation": "authorization_claimed",
        "last_reason": None,
    }


def validate_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RECORD_KEYS:
        raise RecoveryError("recovery_record_keys_invalid")
    if value.get("schema") != SCHEMA:
        raise RecoveryError("recovery_record_schema_invalid")
    recovery_id = _identifier(value.get("recovery_id", ""), "recovery_id")
    if value.get("recovery_id_sha256") != sha_text(recovery_id):
        raise RecoveryError("recovery_id_binding_invalid")
    for key in (
        "authorization_id_sha256",
        "execution_session_id_sha256",
        "plan_sha256",
        "module_set_sha256",
        "target_transaction_id_sha256",
        "target_transaction_sha256",
    ):
        _sha(value.get(key), key)
    for key in ("executor_source_head", "executor_blob"):
        _sha(value.get(key), key, git=True)
    plan = value.get("plan")
    if (
        not isinstance(plan, dict)
        or sha_bytes(canonical(plan)) != value["plan_sha256"]
        or plan.get("schema") != PLAN_SCHEMA
        or plan.get("reason") != REASON
        or plan.get("target_transaction_id_sha256")
        != value["target_transaction_id_sha256"]
        or plan.get("target_transaction_sha256")
        != value["target_transaction_sha256"]
        or plan.get("target_generation") != value["target_generation"]
        or plan.get("target_operation_seq")
        != value["target_operation_seq"]
        or plan.get("recovery_executor_source_head")
        != value["executor_source_head"]
        or plan.get("recovery_executor_blob") != value["executor_blob"]
        or plan.get("recovery_module_set_sha256")
        != value["module_set_sha256"]
    ):
        raise RecoveryError("recovery_plan_binding_invalid")
    state = value.get("state")
    if state not in {"CLAIMED", "COMMITTED", "BLOCKED"}:
        raise RecoveryError("recovery_state_invalid")
    expected_generation = {
        "CLAIMED": 1,
        "COMMITTED": 2,
        "BLOCKED": 2,
    }[state]
    if value.get("generation") != expected_generation:
        raise RecoveryError("recovery_generation_invalid")
    if value.get("authorization_consumed") is not True:
        raise RecoveryError("recovery_authorization_invalid")
    if value.get("replay_allowed") is not False:
        raise RecoveryError("recovery_replay_invalid")
    for key, expected in (
        ("product_mutation", True),
        ("service_stop_start", True),
        ("docker_mutation", True),
        ("board_access", False),
    ):
        if value.get(key) is not expected or plan.get(key) is not expected:
            raise RecoveryError("recovery_scope_invalid")
    expected_last = {
        "CLAIMED": "authorization_claimed",
        "COMMITTED": "predecessor_runtime_restored",
        "BLOCKED": "recovery_blocked",
    }[state]
    if value.get("last_operation") != expected_last:
        raise RecoveryError("recovery_last_operation_invalid")
    if state in {"CLAIMED", "COMMITTED"} and value.get("last_reason") is not None:
        raise RecoveryError("recovery_last_reason_invalid")
    return json.loads(canonical(value))


class RecoveryStore:
    def __init__(self, path: Path):
        self.path = path

    def _require_parent(self) -> None:
        root = self.path.parent
        if root.is_symlink() or not root.is_dir():
            raise RecoveryError("recovery_root_invalid")
        meta = root.stat()
        if (
            meta.st_uid != 0
            or meta.st_gid != 0
            or stat.S_IMODE(meta.st_mode) != 0o700
        ):
            raise RecoveryError("recovery_root_metadata_invalid")

    def load(self) -> dict[str, Any]:
        self._require_parent()
        if self.path.is_symlink() or not self.path.is_file():
            raise RecoveryError("recovery_record_missing")
        meta = self.path.stat()
        if (
            meta.st_uid != 0
            or meta.st_gid != 0
            or stat.S_IMODE(meta.st_mode) != 0o600
            or meta.st_nlink != 1
        ):
            raise RecoveryError("recovery_record_metadata_invalid")
        try:
            return validate_record(
                json.loads(self.path.read_text(encoding="utf-8"))
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RecoveryError("recovery_record_read_invalid") from error

    def create(self, document: dict[str, Any]) -> None:
        self._require_parent()
        payload = canonical(validate_record(document))
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        fd = os.open(self.path, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.fchown(fd, 0, 0)
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        dfd = os.open(
            self.path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)

    def save(
        self,
        document: dict[str, Any],
        *,
        expected_generation: int,
    ) -> None:
        current = self.load()
        if current["generation"] != expected_generation:
            raise RecoveryError("recovery_generation_conflict")
        payload = canonical(validate_record(document))
        fd, raw = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.path.parent,
        )
        tmp = Path(raw)
        try:
            os.fchmod(fd, 0o600)
            os.fchown(fd, 0, 0)
            with os.fdopen(fd, "wb") as stream:
                fd = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
            dfd = os.open(
                self.path.parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        finally:
            if fd >= 0:
                os.close(fd)
            tmp.unlink(missing_ok=True)


def _existing_recovery_for_target(target_hash: str) -> bool:
    if not RECOVERY_ROOT.exists():
        return False
    if RECOVERY_ROOT.is_symlink() or not RECOVERY_ROOT.is_dir():
        raise RecoveryError("recovery_root_invalid")
    for path in sorted(RECOVERY_ROOT.glob("*.json")):
        record = RecoveryStore(path).load()
        if record["target_transaction_id_sha256"] == target_hash:
            return True
    return False


def claim(
    *,
    target_transaction_id: str,
    expected_plan_sha256: str,
    recovery_id: str,
    authorization_id: str,
    execution_session_id: str,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise RecoveryError("confirmation_missing")
    _sha(expected_plan_sha256, "recovery_plan_sha256")
    _identifier(recovery_id, "recovery_id")
    _authorization_id(authorization_id)
    _identifier(execution_session_id, "execution_session_id")
    with e03.global_lock():
        authority = runtime_authority()
        plan = _plan_locked(
            target_transaction_id,
            authority=authority,
        )
        if sha_bytes(canonical(plan)) != expected_plan_sha256:
            raise RecoveryError("recovery_plan_sha256_mismatch")
        _ensure_private_root()
        if _existing_recovery_for_target(
            plan["target_transaction_id_sha256"]
        ):
            raise RecoveryError("target_recovery_already_exists")
        document = _record_from_plan(
            plan=plan,
            recovery_id=recovery_id,
            authorization_id=authorization_id,
            execution_session_id=execution_session_id,
        )
        RecoveryStore(_recovery_path(recovery_id)).create(document)
    return public_result(
        document,
        operation="claim",
        reason_code="RECOVERY_AUTHORIZATION_CLAIMED",
    )


def _assert_authority(record: dict[str, Any]) -> dict[str, str]:
    authority = runtime_authority()
    if (
        authority["source_head"] != record["executor_source_head"]
        or authority["executor_blob"] != record["executor_blob"]
        or authority["module_set_sha256"] != record["module_set_sha256"]
    ):
        raise RecoveryError("recovery_executor_authority_drift")
    return authority


def _install_recovery_gate(plan: dict[str, Any]) -> None:
    current = sha_file(e03.GATE_TARGET)
    before = plan["gate_source_sha256_before"]
    after = plan["gate_source_sha256_after"]
    if current == after:
        return
    if current != before:
        raise RecoveryError("gate_source_prestate_unknown")
    e03._atomic_replace_exact(
        e03.GATE_TARGET,
        e03._gate_source_bytes(),
        before,
    )
    if sha_file(e03.GATE_TARGET) != after:
        raise RecoveryError("gate_source_poststate_unproven")


def _assert_gate_recovery_allowed() -> None:
    result = e03.run(
        (str(e03.GATE_TARGET),),
        allowed=frozenset({0, 1}),
    )
    if result.returncode != 0:
        raise RecoveryError("recovery_gate_not_allowing")


def _runtime_predecessor(
    target_plan: dict[str, Any],
) -> dict[str, Any]:
    return prepublish._runtime_predecessor(target_plan)


def _wait_predecessor(
    target_plan: dict[str, Any],
) -> dict[str, Any]:
    return prepublish._wait_predecessor(
        target_plan,
        timeout=e03.READINESS_TIMEOUT_SECONDS,
        poll=RECOVERY_POLL_SECONDS,
    )


def _stability(
    target_plan: dict[str, Any],
    baseline: dict[str, Any],
) -> int:
    return prepublish._stability(
        target_plan,
        baseline,
        seconds=RECOVERY_STABILITY_SECONDS,
        poll=RECOVERY_POLL_SECONDS,
    )


def _transition(
    record: dict[str, Any],
    *,
    state: str,
    operation: str,
    reason: str | None,
) -> dict[str, Any]:
    value = validate_record(record)
    if value["state"] != "CLAIMED":
        raise RecoveryError("recovery_transition_state_invalid")
    value["state"] = state
    value["generation"] = 2
    value["last_operation"] = operation
    value["last_reason"] = reason
    return validate_record(value)


def _classify_recovery_reality(
    plan: dict[str, Any],
    target_plan: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    deployment = e03._deployment_reality(target_plan)
    gate_sha = sha_file(e03.GATE_TARGET)
    after_gate = plan["gate_source_sha256_after"]
    if deployment == plan["deployment_candidate_fingerprint"]:
        if e03._service_fingerprint() != plan["service_stopped_fingerprint"]:
            raise RecoveryError("candidate_recovery_service_reality_unknown")
        if gate_sha == plan["gate_source_sha256_before"]:
            return "CANDIDATE_STOPPED_BEFORE_GATE", None
        if gate_sha == after_gate:
            return "CANDIDATE_STOPPED_AFTER_GATE", None
        raise RecoveryError("candidate_recovery_gate_reality_unknown")
    if deployment != plan["deployment_before_fingerprint"]:
        raise RecoveryError("recovery_deployment_reality_unknown")
    if gate_sha != after_gate:
        raise RecoveryError("predecessor_recovery_gate_not_installed")
    if e03._service_fingerprint() == plan["service_stopped_fingerprint"]:
        return "PREDECESSOR_STOPPED_AFTER_GATE", None
    try:
        baseline = _runtime_predecessor(target_plan)
    except Exception as error:
        raise RecoveryError("recovery_prestate_binding_drift") from error
    return "PREDECESSOR_RUNNING_AFTER_GATE", baseline


def recover(
    *,
    recovery_id: str,
    target_transaction_id: str,
) -> dict[str, Any]:
    with e03.global_lock():
        store = RecoveryStore(_recovery_path(recovery_id))
        record = store.load()
        if record["state"] == "COMMITTED":
            return public_result(
                record,
                operation="recover",
                reason_code="ALREADY_COMMITTED",
            )
        if record["state"] == "BLOCKED":
            return public_result(
                record,
                operation="recover",
                reason_code=record.get("last_reason") or "RECOVERY_BLOCKED",
            )
        _assert_authority(record)
        target_path = _target_path(target_transaction_id)
        target = _assert_target_shape(
            maintenance.TransactionStore(target_path).load()
        )
        target_plan = _assert_target_static_bindings(
            target_transaction_id,
            target,
        )
        plan = record["plan"]
        if (
            sha_text(target_transaction_id)
            != record["target_transaction_id_sha256"]
            or sha_file(target_path) != record["target_transaction_sha256"]
            or target["generation"] != record["target_generation"]
            or target["operation_seq"] != record["target_operation_seq"]
        ):
            raise RecoveryError("recovery_prestate_binding_drift")
        reality, running_baseline = _classify_recovery_reality(
            plan,
            target_plan,
        )
        start_attempted = running_baseline is not None
        deployment_restored = (
            e03._deployment_reality(target_plan)
            == plan["deployment_before_fingerprint"]
        )
        try:
            e03._broker_continuity(target_plan)
            if reality == "CANDIDATE_STOPPED_BEFORE_GATE":
                _install_recovery_gate(plan)
            elif reality == "CANDIDATE_STOPPED_AFTER_GATE":
                pass
            if e03._deployment_reality(target_plan) == plan[
                "deployment_candidate_fingerprint"
            ]:
                e03._restore_deployment_env(target_plan)
                deployment_restored = True
            if e03._deployment_reality(target_plan) != plan[
                "deployment_before_fingerprint"
            ]:
                raise RecoveryError("predecessor_deployment_restore_unproven")
            _assert_gate_recovery_allowed()
            if running_baseline is None:
                start_attempted = True
                e03.run(
                    ("systemctl", "start", e03.SERVICES_UNIT),
                    timeout=180,
                )
                baseline = _wait_predecessor(target_plan)
            else:
                baseline = running_baseline
            samples = _stability(target_plan, baseline)
            committed = _transition(
                record,
                state="COMMITTED",
                operation="predecessor_runtime_restored",
                reason=None,
            )
            store.save(
                committed,
                expected_generation=record["generation"],
            )
            return public_result(
                committed,
                operation="recover",
                reason_code="PREDECESSOR_RUNTIME_RESTORED",
                extra={
                    "stability_window_seconds": RECOVERY_STABILITY_SECONDS,
                    "stability_samples": samples,
                    "manager_container_id_sha256": sha_text(
                        baseline["manager"]["container_id"]
                    ),
                    "homeassistant_container_id_sha256": sha_text(
                        baseline["homeassistant"]["container_id"]
                    ),
                    "broker_container_id_sha256": sha_text(
                        baseline["broker"]["container_id"]
                    ),
                },
            )
        except Exception as error:
            reason = e03.safe_reason(error)
            if start_attempted:
                try:
                    e03._stop_services()
                    if e03._service_fingerprint() != plan[
                        "service_stopped_fingerprint"
                    ]:
                        raise RecoveryError(
                            "recovery_cleanup_stopped_state_unproven"
                        )
                except Exception as cleanup_error:
                    reason = (
                        "recovery_cleanup_unproven:"
                        + reason
                        + ":"
                        + e03.safe_reason(cleanup_error)
                    )
            if deployment_restored:
                try:
                    if e03._deployment_reality(target_plan) != plan[
                        "deployment_before_fingerprint"
                    ]:
                        raise RecoveryError(
                            "recovery_cleanup_deployment_unproven"
                        )
                except Exception as cleanup_error:
                    reason = (
                        "recovery_cleanup_unproven:"
                        + reason
                        + ":"
                        + e03.safe_reason(cleanup_error)
                    )
            latest = store.load()
            if latest["state"] == "CLAIMED":
                blocked = _transition(
                    latest,
                    state="BLOCKED",
                    operation="recovery_blocked",
                    reason=reason,
                )
                store.save(
                    blocked,
                    expected_generation=latest["generation"],
                )
            raise


def status(
    *,
    recovery_id: str,
    target_transaction_id: str,
) -> dict[str, Any]:
    with retirement.readonly_global_lock():
        record = RecoveryStore(_recovery_path(recovery_id)).load()
        if record["target_transaction_id_sha256"] != sha_text(
            target_transaction_id
        ):
            raise RecoveryError("target_transaction_id_binding_drift")
        target = _assert_target_shape(
            maintenance.TransactionStore(
                _target_path(target_transaction_id)
            ).load()
        )
        if (
            sha_file(_target_path(target_transaction_id))
            != record["target_transaction_sha256"]
            or target["generation"] != record["target_generation"]
            or target["operation_seq"] != record["target_operation_seq"]
        ):
            raise RecoveryError("target_transaction_binding_drift")
    return public_result(
        record,
        operation="status",
        reason_code="READ_ONLY_STATUS",
    )


def public_result(
    record: dict[str, Any],
    *,
    operation: str,
    reason_code: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = validate_record(record)
    result = {
        "schema": SCHEMA,
        "status": "STOP" if value["state"] == "BLOCKED" else "PASS",
        "operation": operation,
        "reason_code": reason_code,
        "recovery_stage": value["state"],
        "recovery_id_sha256": value["recovery_id_sha256"],
        "target_transaction_id_sha256": value[
            "target_transaction_id_sha256"
        ],
        "target_transaction_sha256": value["target_transaction_sha256"],
        "authorization_consumed": value["authorization_consumed"],
        "replay_allowed": value["replay_allowed"],
        "product_mutation": value["product_mutation"],
        "service_stop_start": value["service_stop_start"],
        "docker_mutation": value["docker_mutation"],
        "board_access": value["board_access"],
    }
    if extra:
        result.update(extra)
    return result


def _emit(value: dict[str, Any], *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)

    pre = sub.add_parser("preflight")
    pre.add_argument("--target-transaction-id", required=True)

    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--target-transaction-id", required=True)
    claim_parser.add_argument("--recovery-plan-sha256", required=True)
    claim_parser.add_argument("--recovery-id", required=True)
    claim_parser.add_argument("--authorization-id", required=True)
    claim_parser.add_argument("--execution-session-id", required=True)
    claim_parser.add_argument("--confirmation", required=True)

    recover_parser = sub.add_parser("recover")
    recover_parser.add_argument("--recovery-id", required=True)
    recover_parser.add_argument("--target-transaction-id", required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--recovery-id", required=True)
    status_parser.add_argument("--target-transaction-id", required=True)

    args = parser.parse_args()
    try:
        if args.operation == "preflight":
            result = preflight(args.target_transaction_id)
        elif args.operation == "claim":
            result = claim(
                target_transaction_id=args.target_transaction_id,
                expected_plan_sha256=args.recovery_plan_sha256,
                recovery_id=args.recovery_id,
                authorization_id=args.authorization_id,
                execution_session_id=args.execution_session_id,
                confirmation=args.confirmation,
            )
        elif args.operation == "recover":
            result = recover(
                recovery_id=args.recovery_id,
                target_transaction_id=args.target_transaction_id,
            )
        elif args.operation == "status":
            result = status(
                recovery_id=args.recovery_id,
                target_transaction_id=args.target_transaction_id,
            )
        else:
            raise RecoveryError("operation_invalid")
        _emit(result)
        return 0 if result.get("status") == "PASS" else 3
    except Exception as error:
        _emit(
            {
                "schema": SCHEMA,
                "status": "STOP",
                "operation": args.operation,
                "reason_code": e03.safe_reason(error),
                "authorization_replay": False,
                "board_access": False,
            },
            error=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
