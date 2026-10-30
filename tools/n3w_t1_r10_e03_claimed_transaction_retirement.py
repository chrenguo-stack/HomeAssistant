#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import n3w_t1_maintenance_transaction as maintenance

SCHEMA = "gh.n3w-t1-maintenance-transaction-retirement/1"
PLAN_SCHEMA = "gh.n3w-t1-maintenance-transaction-retirement-plan/1"
CONFIRMATION = "N3W_T1_R10_E03_CLAIMED_TRANSACTION_RETIREMENT"
REASON = "SOURCE_REPAIR_BEFORE_APPLY"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,199}$")

STATES = frozenset({"PREPARED", "CLAIMED", "COMMITTED", "BLOCKED"})
_ALLOWED = {
    "PREPARED": {"CLAIMED", "BLOCKED"},
    "CLAIMED": {"COMMITTED", "BLOCKED"},
    "COMMITTED": set(),
    "BLOCKED": set(),
}
IMMUTABLE_RECORD_KEYS = frozenset(
    {
        "schema",
        "retirement_id",
        "retirement_id_sha256",
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
        "target_retirement_invariant_sha256",
        "reason",
        "product_mutation",
        "board_access",
    }
)
RECORD_KEYS = frozenset(
    {
        *IMMUTABLE_RECORD_KEYS,
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


class RetirementError(RuntimeError):
    pass


def _e03():
    import n3w_t1_r10_e03_successor_recovery as e03

    return e03


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
        raise RetirementError("file_invalid")
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


def _sha(value: Any, name: str, *, git: bool = False) -> str:
    pattern = SHA40 if git else SHA64
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise RetirementError(f"{name}_invalid")
    return value


def _identifier(value: str, name: str) -> str:
    if IDENTIFIER.fullmatch(value or "") is None:
        raise RetirementError(f"{name}_invalid")
    return value


def _authorization_id(value: str) -> str:
    prefix = "N3W_T1_R10_E03_CLAIMED_TRANSACTION_RETIREMENT_"
    if (
        not value.startswith(prefix)
        or len(value) > 200
        or not value.replace("_", "").replace("-", "").isalnum()
    ):
        raise RetirementError("authorization_id_invalid")
    return value


def safe_reason(error: BaseException) -> str:
    raw = str(error).split(":", 1)[0]
    if re.fullmatch(r"[A-Za-z0-9_.-]{3,120}", raw or ""):
        return raw
    return type(error).__name__


def retirement_root() -> Path:
    return _e03().MAINTENANCE_ROOT / "retirements"


def _retirement_path(retirement_id: str) -> Path:
    rid = _identifier(retirement_id, "retirement_id")
    return retirement_root() / f"{rid}.json"


def _target_path(transaction_id: str) -> Path:
    return _e03()._transaction_path(
        _identifier(transaction_id, "target_transaction_id")
    )


def runtime_authority() -> dict[str, str]:
    injected_head = globals().get("BUNDLE_RETIREMENT_SOURCE_HEAD")
    injected_blob = globals().get("BUNDLE_RETIREMENT_EXECUTOR_BLOB")
    injected_modules = globals().get("BUNDLE_RETIREMENT_MODULE_SET_SHA256")
    source_head = (
        injected_head
        if isinstance(injected_head, str)
        else os.environ.get("N3W_RETIREMENT_SOURCE_HEAD")
    )
    if not isinstance(source_head, str) or SHA40.fullmatch(source_head) is None:
        raise RetirementError("executor_source_head_unbound")

    current = Path(__file__)
    executor_blob = (
        injected_blob
        if isinstance(injected_blob, str)
        else git_blob(current)
    )
    if not isinstance(executor_blob, str) or SHA40.fullmatch(executor_blob) is None:
        raise RetirementError("executor_blob_invalid")

    if isinstance(injected_modules, str):
        module_set_sha256 = injected_modules
    else:
        base = current.parent
        paths = (
            base / "n3w_t1_portable_image_identity.py",
            base / "n3w_t1_maintenance_transaction.py",
            base / "n3w_t1_maintenance_activation_gate.py",
            base / "n3w_t1_production_v2_contract.py",
            base / "n3w_t1_r10_e03_successor_recovery.py",
            current,
        )
        if any(path.is_symlink() or not path.is_file() for path in paths):
            raise RetirementError("executor_module_set_unavailable")
        module_set_sha256 = sha_bytes(
            canonical({path.name: git_blob(path) for path in paths})
        )
    _sha(module_set_sha256, "executor_module_set_sha256")
    return {
        "source_head": source_head,
        "executor_blob": executor_blob,
        "module_set_sha256": module_set_sha256,
    }


def target_retirement_invariant_sha256(
    document: dict[str, Any],
) -> str:
    value = maintenance.validate_transaction(document)
    mutable = {"state", "generation", "last_operation", "last_reason"}
    material = {key: value[key] for key in sorted(value) if key not in mutable}
    return sha_bytes(canonical(material))


def _validate_target_ready(document: dict[str, Any]) -> dict[str, Any]:
    value = maintenance.validate_transaction(document)
    maintenance.abort_claimed_ready_before_apply(
        value,
        reason=REASON,
    )
    if any(
        session.get("action") in {"apply", "rollback"}
        for session in value["execution_sessions"]
    ):
        raise RetirementError("target_execution_session_forbidden")
    return value


def _target_binding_projection(document: dict[str, Any]) -> dict[str, Any]:
    value = maintenance.validate_transaction(document)
    return {
        "authorization_id_sha256": value["authorization_id_sha256"],
        "host_binding_sha256": value["host_binding_sha256"],
        "executor_source_head": value["executor_source_head"],
        "executor_blob": value["executor_blob"],
        "module_set_sha256": value["module_set_sha256"],
        "plan_sha256": value["plan_sha256"],
        "predecessor_sha256": value["predecessor_sha256"],
        "current_release_id": value["current_release_id"],
        "target_release_id": value["target_release_id"],
        "artifact_sha256": value["artifact_sha256"],
    }


def _verify_exact_before(
    transaction_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    e03 = _e03()
    target_path = _target_path(transaction_id)
    store = maintenance.TransactionStore(target_path)
    document = _validate_target_ready(store.load())
    plan = document["plan"]
    if (
        plan.get("schema") != e03.PLAN_SCHEMA
        or tuple(document["scope"]) != tuple(e03.SCOPE)
        or plan.get("predecessor_sha256")
        != document["predecessor_sha256"]
        or plan.get("current_release_id")
        != document["current_release_id"]
        or plan.get("target_release_id")
        != document["target_release_id"]
        or plan.get("artifact_sha256")
        != document["artifact_sha256"]
    ):
        raise RetirementError("target_e03_transaction_contract_invalid")
    if (
        e03.host_binding_sha256()
        != document["host_binding_sha256"]
    ):
        raise RetirementError("target_host_binding_drift")
    maintenance.assert_predecessor_immutable(
        e03.PREDECESSOR_TX,
        document["predecessor_sha256"],
    )
    e03.predecessor_evidence(document["predecessor_sha256"])

    if e03._deployment_reality(plan) != plan["deployment_before_fingerprint"]:
        raise RetirementError("deployment_reality_not_exact_before")
    if e03._service_fingerprint() != plan["service_before_fingerprint"]:
        raise RetirementError("service_reality_not_exact_before")
    if e03._gate_fingerprint() != plan["gate_before_fingerprint"]:
        raise RetirementError("gate_reality_not_exact_before")

    manager = e03.runtime("manager")
    if (
        manager.get("container_id") != plan["manager_predecessor_container_id"]
        or manager.get("image_ref") != e03.OLD_MANAGER_IMAGE
        or manager.get("image_id") != e03.OLD_MANAGER_ID
        or manager.get("network_mode") != "host"
        or manager.get("restart_count") != 0
    ):
        raise RetirementError("manager_predecessor_continuity_failed")

    homeassistant = e03.runtime("homeassistant")
    if (
        homeassistant.get("image_ref") != e03.HA_IMAGE
        or homeassistant.get("image_id") != e03.HA_IMAGE_ID
        or homeassistant.get("network_mode") != "host"
        or homeassistant.get("restart_count") != 0
    ):
        raise RetirementError("homeassistant_continuity_failed")
    if e03.ha_mqtt_hash() != plan["ha_mqtt_sha256"]:
        raise RetirementError("homeassistant_mqtt_continuity_failed")

    e03._broker_continuity(plan)
    if e03.listener_snapshot() != e03.EXPECTED_LISTENERS:
        raise RetirementError("listener_contract_failed")
    if e03.systemd_nrestarts(e03.SERVICES_UNIT) != plan["services_nrestarts"]:
        raise RetirementError("services_restart_continuity_failed")

    current_f4 = e03._current_f4_authority()
    current_f4_sha256 = e03.sha_bytes(e03.canonical(current_f4))

    documents = e03._active_maintenance_documents()
    maintenance.ensure_no_other_active(
        documents,
        transaction_id=document["transaction_id"],
    )

    snapshot = {
        "target_transaction_sha256": sha_file(target_path),
        "target_generation": document["generation"],
        "target_retirement_invariant_sha256": (
            target_retirement_invariant_sha256(document)
        ),
        "deployment_before_fingerprint": plan[
            "deployment_before_fingerprint"
        ],
        "service_before_fingerprint": plan["service_before_fingerprint"],
        "gate_before_fingerprint": plan["gate_before_fingerprint"],
        "current_f4_authority_sha256": current_f4_sha256,
        "current_f4_transaction_sha256": current_f4[
            "transaction_sha256"
        ],
    }
    return document, snapshot


def _plan_locked(
    target_transaction_id: str,
    *,
    authority: dict[str, str],
) -> dict[str, Any]:
    document, snapshot = _verify_exact_before(target_transaction_id)
    binding = _target_binding_projection(document)
    return {
        "schema": PLAN_SCHEMA,
        "reason": REASON,
        "target_transaction_id_sha256": sha_text(
            document["transaction_id"]
        ),
        "target_transaction_sha256": snapshot[
            "target_transaction_sha256"
        ],
        "target_generation": snapshot["target_generation"],
        "target_retirement_invariant_sha256": snapshot[
            "target_retirement_invariant_sha256"
        ],
        "target_authorization_id_sha256": binding[
            "authorization_id_sha256"
        ],
        "target_host_binding_sha256": binding[
            "host_binding_sha256"
        ],
        "target_executor_source_head": binding["executor_source_head"],
        "target_executor_blob": binding["executor_blob"],
        "target_module_set_sha256": binding["module_set_sha256"],
        "target_plan_sha256": binding["plan_sha256"],
        "target_predecessor_sha256": binding["predecessor_sha256"],
        "target_current_release_id": binding["current_release_id"],
        "target_release_id": binding["target_release_id"],
        "target_artifact_sha256": binding["artifact_sha256"],
        "target_state": "READY",
        "target_authorization_consumed": True,
        "target_replay_allowed": False,
        "target_operation_seq": 0,
        "deployment_before_fingerprint": snapshot[
            "deployment_before_fingerprint"
        ],
        "service_before_fingerprint": snapshot[
            "service_before_fingerprint"
        ],
        "gate_before_fingerprint": snapshot[
            "gate_before_fingerprint"
        ],
        "current_f4_authority_sha256": snapshot[
            "current_f4_authority_sha256"
        ],
        "current_f4_transaction_sha256": snapshot[
            "current_f4_transaction_sha256"
        ],
        "retirement_executor_source_head": authority["source_head"],
        "retirement_executor_blob": authority["executor_blob"],
        "retirement_module_set_sha256": authority["module_set_sha256"],
        "product_mutation": False,
        "board_access": False,
    }


@contextmanager
def readonly_global_lock() -> Iterator[None]:
    e03 = _e03()
    root = e03.MAINTENANCE_ROOT
    path = e03.LOCK_PATH
    if (
        root.is_symlink()
        or not root.is_dir()
        or path.is_symlink()
        or not path.is_file()
    ):
        raise RetirementError("maintenance_lock_authority_missing")
    root_meta = root.stat()
    lock_meta = path.stat()
    if (
        root_meta.st_uid != 0
        or root_meta.st_gid != 0
        or stat.S_IMODE(root_meta.st_mode) != 0o700
        or lock_meta.st_uid != 0
        or lock_meta.st_gid != 0
        or stat.S_IMODE(lock_meta.st_mode) != 0o600
    ):
        raise RetirementError("maintenance_lock_metadata_invalid")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    acquired = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RetirementError("maintenance_lock_busy") from error
        acquired = True
        yield
    finally:
        try:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def preflight(target_transaction_id: str) -> dict[str, Any]:
    authority = runtime_authority()
    with readonly_global_lock():
        plan = _plan_locked(
            target_transaction_id,
            authority=authority,
        )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "preflight",
        "retirement_plan_sha256": sha_bytes(canonical(plan)),
        "target_transaction_id_sha256": plan[
            "target_transaction_id_sha256"
        ],
        "target_transaction_sha256": plan[
            "target_transaction_sha256"
        ],
        "target_generation": plan["target_generation"],
        "reason": REASON,
        "product_mutation": False,
        "board_access": False,
    }


def _record_from_plan(
    *,
    plan: dict[str, Any],
    retirement_id: str,
    authorization_id_sha256: str,
    execution_session_id_sha256: str,
) -> dict[str, Any]:
    retirement_id = _identifier(retirement_id, "retirement_id")
    _sha(authorization_id_sha256, "authorization_id_sha256")
    _sha(execution_session_id_sha256, "execution_session_id_sha256")
    return {
        "schema": SCHEMA,
        "retirement_id": retirement_id,
        "retirement_id_sha256": sha_text(retirement_id),
        "authorization_id_sha256": authorization_id_sha256,
        "execution_session_id_sha256": execution_session_id_sha256,
        "plan_sha256": sha_bytes(canonical(plan)),
        "plan": json.loads(canonical(plan)),
        "executor_source_head": plan[
            "retirement_executor_source_head"
        ],
        "executor_blob": plan["retirement_executor_blob"],
        "module_set_sha256": plan["retirement_module_set_sha256"],
        "target_transaction_id_sha256": plan[
            "target_transaction_id_sha256"
        ],
        "target_transaction_sha256_before": plan[
            "target_transaction_sha256"
        ],
        "target_generation_before": plan["target_generation"],
        "target_retirement_invariant_sha256": plan[
            "target_retirement_invariant_sha256"
        ],
        "reason": REASON,
        "product_mutation": False,
        "board_access": False,
        "state": "PREPARED",
        "authorization_consumed": False,
        "replay_allowed": False,
        "generation": 1,
        "target_transaction_sha256_after": None,
        "target_generation_after": None,
        "last_operation": "prepared",
        "last_reason": None,
    }


def validate_record(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != RECORD_KEYS:
        raise RetirementError("retirement_record_keys_invalid")
    if document.get("schema") != SCHEMA:
        raise RetirementError("retirement_record_schema_invalid")
    _identifier(document.get("retirement_id", ""), "retirement_id")
    if document.get("retirement_id_sha256") != sha_text(
        document["retirement_id"]
    ):
        raise RetirementError("retirement_id_binding_invalid")
    for key in (
        "authorization_id_sha256",
        "execution_session_id_sha256",
        "plan_sha256",
        "module_set_sha256",
        "target_transaction_id_sha256",
        "target_transaction_sha256_before",
        "target_retirement_invariant_sha256",
    ):
        _sha(document.get(key), key)
    for key in ("executor_source_head", "executor_blob"):
        _sha(document.get(key), key, git=True)
    plan = document.get("plan")
    if not isinstance(plan, dict) or sha_bytes(canonical(plan)) != document[
        "plan_sha256"
    ]:
        raise RetirementError("retirement_plan_binding_invalid")
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("reason") != REASON
        or plan.get("target_transaction_id_sha256")
        != document["target_transaction_id_sha256"]
        or plan.get("target_transaction_sha256")
        != document["target_transaction_sha256_before"]
        or plan.get("target_generation")
        != document["target_generation_before"]
        or plan.get("target_retirement_invariant_sha256")
        != document["target_retirement_invariant_sha256"]
        or plan.get("retirement_executor_source_head")
        != document["executor_source_head"]
        or plan.get("retirement_executor_blob")
        != document["executor_blob"]
        or plan.get("retirement_module_set_sha256")
        != document["module_set_sha256"]
        or plan.get("product_mutation") is not False
        or plan.get("board_access") is not False
    ):
        raise RetirementError("retirement_plan_record_cross_binding_invalid")
    if document.get("state") not in STATES:
        raise RetirementError("retirement_state_invalid")
    if not isinstance(document.get("authorization_consumed"), bool):
        raise RetirementError("retirement_authorization_consumed_invalid")
    if document.get("replay_allowed") is not False:
        raise RetirementError("retirement_replay_contract_invalid")
    if document.get("product_mutation") is not False:
        raise RetirementError("retirement_product_mutation_contract_invalid")
    if document.get("board_access") is not False:
        raise RetirementError("retirement_board_contract_invalid")
    generation = document.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise RetirementError("retirement_generation_invalid")
    before_generation = document.get("target_generation_before")
    if (
        isinstance(before_generation, bool)
        or not isinstance(before_generation, int)
        or before_generation < 1
    ):
        raise RetirementError("target_generation_before_invalid")
    after_sha = document.get("target_transaction_sha256_after")
    after_generation = document.get("target_generation_after")
    if document["state"] == "COMMITTED":
        _sha(after_sha, "target_transaction_sha256_after")
        if (
            isinstance(after_generation, bool)
            or not isinstance(after_generation, int)
            or after_generation != before_generation + 1
        ):
            raise RetirementError("target_generation_after_invalid")
    elif after_sha is not None or after_generation is not None:
        raise RetirementError("retirement_poststate_premature")
    if document["state"] in {"CLAIMED", "COMMITTED"} and (
        document["authorization_consumed"] is not True
    ):
        raise RetirementError("retirement_claim_state_invalid")
    if document.get("reason") != REASON:
        raise RetirementError("retirement_reason_invalid")
    if not isinstance(document.get("last_operation"), str):
        raise RetirementError("retirement_last_operation_invalid")
    last_reason = document.get("last_reason")
    if last_reason is not None and not isinstance(last_reason, str):
        raise RetirementError("retirement_last_reason_invalid")
    return json.loads(canonical(document))


def _transition_record(
    document: dict[str, Any],
    target: str,
    *,
    operation: str,
    reason: str | None = None,
    target_transaction_sha256_after: str | None = None,
    target_generation_after: int | None = None,
) -> dict[str, Any]:
    value = validate_record(document)
    if target not in _ALLOWED[value["state"]]:
        raise RetirementError(
            f"retirement_transition_invalid:{value['state']}:{target}"
        )
    value["state"] = target
    value["generation"] += 1
    value["last_operation"] = operation
    value["last_reason"] = reason
    if target == "CLAIMED":
        value["authorization_consumed"] = True
    if target == "COMMITTED":
        _sha(
            target_transaction_sha256_after,
            "target_transaction_sha256_after",
        )
        if (
            isinstance(target_generation_after, bool)
            or not isinstance(target_generation_after, int)
            or target_generation_after
            != value["target_generation_before"] + 1
        ):
            raise RetirementError("target_generation_after_invalid")
        value["target_transaction_sha256_after"] = (
            target_transaction_sha256_after
        )
        value["target_generation_after"] = target_generation_after
    return validate_record(value)


class RetirementStore:
    def __init__(
        self,
        path: Path,
        *,
        enforce_root_metadata: bool = True,
    ):
        self.path = path
        self.enforce_root_metadata = enforce_root_metadata

    def _require_parent(self) -> None:
        parent = self.path.parent
        if parent.is_symlink() or not parent.is_dir():
            raise RetirementError("retirement_parent_invalid")
        if self.enforce_root_metadata:
            meta = parent.stat()
            if (
                meta.st_uid != 0
                or meta.st_gid != 0
                or stat.S_IMODE(meta.st_mode) != 0o700
            ):
                raise RetirementError("retirement_parent_metadata_invalid")

    def _verify_file(self) -> None:
        if self.path.is_symlink() or not self.path.is_file():
            raise RetirementError("retirement_record_missing")
        meta = self.path.stat()
        if stat.S_IMODE(meta.st_mode) != 0o600:
            raise RetirementError("retirement_record_mode_invalid")
        if self.enforce_root_metadata and (
            meta.st_uid != 0 or meta.st_gid != 0
        ):
            raise RetirementError("retirement_record_owner_invalid")

    def load(self) -> dict[str, Any]:
        self._require_parent()
        self._verify_file()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RetirementError("retirement_record_read_invalid") from error
        return validate_record(raw)

    def create(self, document: dict[str, Any]) -> None:
        self._require_parent()
        payload = canonical(validate_record(document))
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        fd = -1
        created = False
        try:
            try:
                fd = os.open(self.path, flags, 0o600)
            except FileExistsError as error:
                raise RetirementError("retirement_record_exists") from error
            created = True
            os.fchmod(fd, 0o600)
            if self.enforce_root_metadata:
                os.fchown(fd, 0, 0)
            with os.fdopen(fd, "wb") as stream:
                fd = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            self._fsync_parent()
        except Exception:
            if fd >= 0:
                os.close(fd)
                fd = -1
            if created:
                self.path.unlink(missing_ok=True)
                self._fsync_parent()
            raise
        finally:
            if fd >= 0:
                os.close(fd)

    def save(
        self,
        document: dict[str, Any],
        *,
        expected_generation: int,
    ) -> None:
        current = self.load()
        if current["generation"] != expected_generation:
            raise RetirementError("retirement_generation_conflict")
        value = validate_record(document)
        if value["generation"] <= current["generation"]:
            raise RetirementError("retirement_generation_not_advanced")
        for key in IMMUTABLE_RECORD_KEYS:
            if value[key] != current[key]:
                raise RetirementError(
                    f"retirement_immutable_binding_changed:{key}"
                )
        if (
            current["authorization_consumed"] is True
            and value["authorization_consumed"] is not True
        ):
            raise RetirementError(
                "retirement_authorization_consumed_reverted"
            )
        if (
            current["state"] != value["state"]
            and value["state"] not in _ALLOWED[current["state"]]
        ):
            raise RetirementError("retirement_state_jump_invalid")

        payload = canonical(value)
        fd, raw = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.path.parent,
        )
        tmp = Path(raw)
        try:
            os.fchmod(fd, 0o600)
            if self.enforce_root_metadata:
                os.fchown(fd, 0, 0)
            with os.fdopen(fd, "wb") as stream:
                fd = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
            self._fsync_parent()
        finally:
            if fd >= 0:
                os.close(fd)
            tmp.unlink(missing_ok=True)

    def _fsync_parent(self) -> None:
        fd = os.open(
            self.path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _retirement_documents() -> list[dict[str, Any]]:
    root = retirement_root()
    if not root.exists():
        return []
    if root.is_symlink() or not root.is_dir():
        raise RetirementError("retirement_root_invalid")
    meta = root.stat()
    if (
        meta.st_uid != 0
        or meta.st_gid != 0
        or stat.S_IMODE(meta.st_mode) != 0o700
    ):
        raise RetirementError("retirement_root_metadata_invalid")
    values = []
    for path in sorted(root.glob("*.json")):
        values.append(RetirementStore(path).load())
    return values


def _ensure_no_target_retirement(
    target_transaction_id_sha256: str,
    *,
    exclude_retirement_id: str | None = None,
) -> None:
    for document in _retirement_documents():
        if (
            exclude_retirement_id is not None
            and document["retirement_id"] == exclude_retirement_id
        ):
            continue
        if (
            document["target_transaction_id_sha256"]
            == target_transaction_id_sha256
        ):
            raise RetirementError("target_retirement_already_exists")


def claim(
    *,
    target_transaction_id: str,
    expected_preauth_plan_sha256: str,
    retirement_id: str,
    authorization_id: str,
    execution_session_id: str,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise RetirementError("confirmation_missing")
    _identifier(retirement_id, "retirement_id")
    authorization_id = _authorization_id(authorization_id)
    _identifier(execution_session_id, "execution_session_id")
    _sha(expected_preauth_plan_sha256, "preauth_plan_sha256")

    e03 = _e03()
    with e03.global_lock():
        authority = runtime_authority()
        plan = _plan_locked(
            target_transaction_id,
            authority=authority,
        )
        observed = sha_bytes(canonical(plan))
        if observed != expected_preauth_plan_sha256:
            raise RetirementError("preauth_plan_sha256_mismatch")
        e03._ensure_private_dir(retirement_root())
        path = _retirement_path(retirement_id)
        store = RetirementStore(path)
        prepared = _record_from_plan(
            plan=plan,
            retirement_id=retirement_id,
            authorization_id_sha256=sha_text(authorization_id),
            execution_session_id_sha256=sha_text(execution_session_id),
        )
        if path.exists() or path.is_symlink():
            existing = store.load()
            _ensure_no_target_retirement(
                plan["target_transaction_id_sha256"],
                exclude_retirement_id=retirement_id,
            )
            if (
                existing["state"] != "PREPARED"
                or existing["generation"] != 1
                or existing["authorization_consumed"] is not False
                or any(
                    existing[key] != prepared[key]
                    for key in IMMUTABLE_RECORD_KEYS
                )
            ):
                raise RetirementError(
                    "retirement_prepared_resume_binding_drift"
                )
            prepared = existing
        else:
            _ensure_no_target_retirement(
                plan["target_transaction_id_sha256"]
            )
            store.create(prepared)
        claimed = _transition_record(
            prepared,
            "CLAIMED",
            operation="authorization_claimed",
        )
        store.save(
            claimed,
            expected_generation=prepared["generation"],
        )
        result = store.load()
    return public_result(
        result,
        operation="claim",
        reason_code="RETIREMENT_AUTHORIZATION_CLAIMED",
        target_state="READY",
    )


def _assert_retirement_authority(
    document: dict[str, Any],
) -> dict[str, str]:
    authority = runtime_authority()
    if (
        authority["source_head"] != document["executor_source_head"]
        or authority["executor_blob"] != document["executor_blob"]
        or authority["module_set_sha256"]
        != document["module_set_sha256"]
    ):
        raise RetirementError("retirement_executor_authority_drift")
    return authority


def _assert_aborted_poststate(
    document: dict[str, Any],
    record: dict[str, Any],
) -> None:
    value = maintenance.validate_transaction(document)
    if (
        value["state"] != "ABORTED"
        or value["generation"]
        != record["target_generation_before"] + 1
        or value["last_operation"] != "retired_before_apply"
        or value["last_reason"] != REASON
        or value["authorization_consumed"] is not True
        or value["replay_allowed"] is not False
        or value["operation_seq"] != 0
        or value["operations"]
        or value["observed_after"]
        or target_retirement_invariant_sha256(value)
        != record["target_retirement_invariant_sha256"]
    ):
        raise RetirementError("retired_target_poststate_invalid")


def _block_record(
    store: RetirementStore,
    document: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    if document["state"] not in {"PREPARED", "CLAIMED"}:
        return document
    blocked = _transition_record(
        document,
        "BLOCKED",
        operation="blocked",
        reason=reason,
    )
    store.save(
        blocked,
        expected_generation=document["generation"],
    )
    return store.load()


def retire(
    *,
    retirement_id: str,
    target_transaction_id: str,
    execution_session_id: str,
) -> dict[str, Any]:
    e03 = _e03()
    with e03.global_lock():
        record_store = RetirementStore(_retirement_path(retirement_id))
        record = record_store.load()
        _assert_retirement_authority(record)
        session_id = _identifier(
            execution_session_id,
            "execution_session_id",
        )
        if sha_text(session_id) != record["execution_session_id_sha256"]:
            raise RetirementError("retirement_execution_session_drift")
        target_id_hash = sha_text(
            _identifier(
                target_transaction_id,
                "target_transaction_id",
            )
        )
        if target_id_hash != record["target_transaction_id_sha256"]:
            raise RetirementError("target_transaction_id_binding_drift")

        target_store = maintenance.TransactionStore(
            _target_path(target_transaction_id)
        )
        target = target_store.load()

        if record["state"] == "COMMITTED":
            _assert_aborted_poststate(target, record)
            if sha_file(_target_path(target_transaction_id)) != record[
                "target_transaction_sha256_after"
            ]:
                raise RetirementError(
                    "retired_target_transaction_sha256_drift"
                )
            return public_result(
                record,
                operation="retire",
                reason_code="ALREADY_COMMITTED",
                target_state="ABORTED",
            )
        if record["state"] == "BLOCKED":
            return public_result(
                record,
                operation="retire",
                reason_code=record.get("last_reason") or "BLOCKED",
                target_state=target.get("state"),
            )
        if record["state"] != "CLAIMED":
            raise RetirementError("retirement_not_claimed")

        poststate_verified = False
        try:
            if target["state"] == "READY":
                plan = _plan_locked(
                    target_transaction_id,
                    authority=_assert_retirement_authority(record),
                )
                if (
                    sha_bytes(canonical(plan))
                    != record["plan_sha256"]
                    or plan["target_transaction_sha256"]
                    != record["target_transaction_sha256_before"]
                    or plan["target_generation"]
                    != record["target_generation_before"]
                ):
                    raise RetirementError(
                        "retirement_prestate_binding_drift"
                    )
                aborted = maintenance.abort_claimed_ready_before_apply(
                    target,
                    reason=REASON,
                )
                target_store.save(
                    aborted,
                    expected_generation=target["generation"],
                )
                target = target_store.load()
            elif target["state"] != "ABORTED":
                raise RetirementError("target_state_not_retirable")

            _assert_aborted_poststate(target, record)
            poststate_verified = True
            after_sha256 = sha_file(
                _target_path(target_transaction_id)
            )
            committed = _transition_record(
                record,
                "COMMITTED",
                operation="target_transaction_aborted",
                target_transaction_sha256_after=after_sha256,
                target_generation_after=target["generation"],
            )
            record_store.save(
                committed,
                expected_generation=record["generation"],
            )
            result = record_store.load()
            return public_result(
                result,
                operation="retire",
                reason_code="TARGET_TRANSACTION_RETIRED",
                target_state="ABORTED",
            )
        except Exception as error:
            latest = record_store.load()
            latest_target = target_store.load()
            if (
                latest["state"] == "CLAIMED"
                and (
                    latest_target["state"] != "ABORTED"
                    or not poststate_verified
                )
            ):
                _block_record(
                    record_store,
                    latest,
                    safe_reason(error),
                )
            raise


def status(
    *,
    retirement_id: str,
    target_transaction_id: str,
) -> dict[str, Any]:
    with readonly_global_lock():
        record = RetirementStore(_retirement_path(retirement_id)).load()
        target_hash = sha_text(
            _identifier(
                target_transaction_id,
                "target_transaction_id",
            )
        )
        if target_hash != record["target_transaction_id_sha256"]:
            raise RetirementError("target_transaction_id_binding_drift")
        target = maintenance.TransactionStore(
            _target_path(target_transaction_id)
        ).load()
        return public_result(
            record,
            operation="status",
            reason_code="READ_ONLY_STATUS",
            target_state=target["state"],
        )


def committed_supersession(
    *,
    predecessor_sha256: str,
    current_release_id: str,
    target_release_id: str,
    artifact_sha256: str,
) -> dict[str, Any] | None:
    e03 = _e03()
    matches: list[tuple[dict[str, Any], dict[str, Any], Path]] = []
    aborted_candidates: list[tuple[dict[str, Any], Path]] = []

    if e03.TRANSACTION_ROOT.exists():
        for path in sorted(e03.TRANSACTION_ROOT.glob("*.json")):
            document = maintenance.TransactionStore(path).load()
            if (
                document["state"] == "ABORTED"
                and document["predecessor_sha256"] == predecessor_sha256
                and document["current_release_id"] == current_release_id
                and document["target_release_id"] == target_release_id
                and document["artifact_sha256"] == artifact_sha256
            ):
                aborted_candidates.append((document, path))

    for record in _retirement_documents():
        if record["state"] != "COMMITTED":
            continue
        for document, path in aborted_candidates:
            if (
                sha_text(document["transaction_id"])
                == record["target_transaction_id_sha256"]
                and sha_file(path)
                == record["target_transaction_sha256_after"]
                and document["generation"]
                == record["target_generation_after"]
            ):
                _assert_aborted_poststate(document, record)
                matches.append(
                    (
                        record,
                        document,
                        _retirement_path(record["retirement_id"]),
                    )
                )

    if not aborted_candidates and not matches:
        return None
    if len(aborted_candidates) != 1 or len(matches) != 1:
        raise RetirementError("retirement_supersession_ambiguous")
    record, document, evidence_path = matches[0]
    return {
        "mode": "TERMINAL_REPLACEMENT",
        "reason": REASON,
        "retired_transaction_id_sha256": record[
            "target_transaction_id_sha256"
        ],
        "retired_transaction_sha256": record[
            "target_transaction_sha256_after"
        ],
        "retirement_evidence_sha256": sha_file(evidence_path),
        "retired_state": "ABORTED",
        "retired_authorization_consumed": True,
        "retired_replay_allowed": False,
        "retired_operation_seq": 0,
    }


def assert_supersession(
    supersession: Any,
    *,
    predecessor_sha256: str,
    current_release_id: str,
    target_release_id: str,
    artifact_sha256: str,
) -> dict[str, Any] | None:
    observed = committed_supersession(
        predecessor_sha256=predecessor_sha256,
        current_release_id=current_release_id,
        target_release_id=target_release_id,
        artifact_sha256=artifact_sha256,
    )
    if supersession is None:
        if observed is not None:
            raise RetirementError("retirement_supersession_missing")
        return None
    if not isinstance(supersession, dict) or observed != supersession:
        raise RetirementError("retirement_supersession_drift")
    return observed


def public_result(
    document: dict[str, Any],
    *,
    operation: str,
    reason_code: str,
    target_state: Any,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": (
            "STOP" if document.get("state") == "BLOCKED" else "PASS"
        ),
        "operation": operation,
        "reason_code": reason_code,
        "retirement_id_sha256": document["retirement_id_sha256"],
        "retirement_stage": document["state"],
        "authorization_consumed": document["authorization_consumed"],
        "replay_allowed": document["replay_allowed"],
        "target_transaction_id_sha256": document[
            "target_transaction_id_sha256"
        ],
        "target_state": target_state,
        "product_mutation": False,
        "board_access": False,
    }


def _emit(document: dict[str, Any], *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)

    pre = sub.add_parser("preflight")
    pre.add_argument("--target-transaction-id", required=True)

    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--target-transaction-id", required=True)
    claim_parser.add_argument("--preauth-plan-sha256", required=True)
    claim_parser.add_argument("--retirement-id", required=True)
    claim_parser.add_argument("--authorization-id", required=True)
    claim_parser.add_argument("--execution-session-id", required=True)
    claim_parser.add_argument("--confirmation", required=True)

    retire_parser = sub.add_parser("retire")
    retire_parser.add_argument("--retirement-id", required=True)
    retire_parser.add_argument("--target-transaction-id", required=True)
    retire_parser.add_argument("--execution-session-id", required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--retirement-id", required=True)
    status_parser.add_argument("--target-transaction-id", required=True)

    args = parser.parse_args()
    try:
        if args.operation == "preflight":
            result = preflight(args.target_transaction_id)
        elif args.operation == "claim":
            result = claim(
                target_transaction_id=args.target_transaction_id,
                expected_preauth_plan_sha256=args.preauth_plan_sha256,
                retirement_id=args.retirement_id,
                authorization_id=args.authorization_id,
                execution_session_id=args.execution_session_id,
                confirmation=args.confirmation,
            )
        elif args.operation == "retire":
            result = retire(
                retirement_id=args.retirement_id,
                target_transaction_id=args.target_transaction_id,
                execution_session_id=args.execution_session_id,
            )
        elif args.operation == "status":
            result = status(
                retirement_id=args.retirement_id,
                target_transaction_id=args.target_transaction_id,
            )
        else:
            raise RetirementError("operation_invalid")
        _emit(result)
        return 0 if result.get("status") == "PASS" else 3
    except Exception as error:
        _emit(
            {
                "schema": SCHEMA,
                "status": "STOP",
                "operation": args.operation,
                "reason_code": safe_reason(error),
                "authorization_replay": False,
                "product_mutation": False,
                "board_access": False,
            },
            error=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
