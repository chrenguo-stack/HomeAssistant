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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import n3w_t1_maintenance_transaction as maintenance
import n3w_t1_r10_e03_claimed_transaction_retirement as retirement
import n3w_t1_r10_e03_successor_recovery as e03

SCHEMA = "gh.n3w-t1-e03-replacement-baseline-invalidation/1"
PLAN_SCHEMA = "gh.n3w-t1-e03-replacement-baseline-invalidation-plan/1"
CONFIRMATION = "N3W_T1_R10_E03_REPLACEMENT_BASELINE_INVALIDATION"
REASON = "BROKER_STARTED_AT_CHANGED_AFTER_T1_REBOOT"

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,199}$")

IMMUTABLE_RECORD_KEYS = frozenset(
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


class InvalidationError(RuntimeError):
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
        raise InvalidationError("file_invalid")
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
        raise InvalidationError(f"{name}_invalid")
    return value


def _identifier(value: str, name: str) -> str:
    if IDENTIFIER.fullmatch(value or "") is None:
        raise InvalidationError(f"{name}_invalid")
    return value


def _authorization_id(value: str) -> str:
    prefix = "N3W_T1_R10_E03_REPLACEMENT_BASELINE_INVALIDATION_"
    if (
        not value.startswith(prefix)
        or len(value) > 200
        or not value.replace("_", "").replace("-", "").isalnum()
    ):
        raise InvalidationError("authorization_id_invalid")
    return value


def invalidation_root() -> Path:
    return e03.MAINTENANCE_ROOT / "invalidations"


def _invalidation_path(invalidation_id: str) -> Path:
    value = _identifier(invalidation_id, "invalidation_id")
    return invalidation_root() / f"{value}.json"


def _target_path(transaction_id: str) -> Path:
    return e03._transaction_path(
        _identifier(transaction_id, "target_transaction_id")
    )


def runtime_authority() -> dict[str, str]:
    injected_head = globals().get("BUNDLE_INVALIDATION_SOURCE_HEAD")
    injected_blob = globals().get("BUNDLE_INVALIDATION_EXECUTOR_BLOB")
    injected_modules = globals().get("BUNDLE_INVALIDATION_MODULE_SET_SHA256")
    source_head = (
        injected_head
        if isinstance(injected_head, str)
        else os.environ.get("N3W_INVALIDATION_SOURCE_HEAD")
    )
    if not isinstance(source_head, str) or SHA40.fullmatch(source_head) is None:
        raise InvalidationError("executor_source_head_unbound")

    current = Path(__file__)
    executor_blob = (
        injected_blob
        if isinstance(injected_blob, str)
        else git_blob(current)
    )
    if not isinstance(executor_blob, str) or SHA40.fullmatch(executor_blob) is None:
        raise InvalidationError("executor_blob_invalid")

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
            base / "n3w_t1_r10_e03_claimed_transaction_retirement.py",
            current,
        )
        if any(path.is_symlink() or not path.is_file() for path in paths):
            raise InvalidationError("executor_module_set_unavailable")
        module_set_sha256 = sha_bytes(
            canonical({path.name: git_blob(path) for path in paths})
        )
    _sha(module_set_sha256, "executor_module_set_sha256")
    return {
        "source_head": source_head,
        "executor_blob": executor_blob,
        "module_set_sha256": module_set_sha256,
    }


def _target_invariant_sha256(document: dict[str, Any]) -> str:
    value = maintenance.validate_transaction(document)
    mutable = {"state", "generation", "last_operation", "last_reason"}
    material = {key: value[key] for key in sorted(value) if key not in mutable}
    return sha_bytes(canonical(material))


def _validate_target_ready(document: dict[str, Any]) -> dict[str, Any]:
    value = maintenance.validate_transaction(document)
    if value["state"] != "READY":
        raise InvalidationError("target_state_not_ready")
    if value["authorization_consumed"] is not True:
        raise InvalidationError("target_authorization_not_consumed")
    if value["replay_allowed"] is not False:
        raise InvalidationError("target_replay_contract_drift")
    if value["operation_seq"] != 0 or value["operations"]:
        raise InvalidationError("target_operation_history_present")
    if maintenance.pending_operation(value) is not None:
        raise InvalidationError("target_pending_operation")
    if value["observed_after"]:
        raise InvalidationError("target_observed_after_present")
    if any(
        session.get("action") != "claim"
        for session in value["execution_sessions"]
    ):
        raise InvalidationError("target_execution_session_forbidden")
    return value


def _parse_docker_started_at(value: Any) -> float:
    if not isinstance(value, str):
        raise InvalidationError("broker_started_at_invalid")
    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z",
        value,
    )
    if match is None:
        raise InvalidationError("broker_started_at_invalid")
    base = datetime.strptime(
        match.group(1),
        "%Y-%m-%dT%H:%M:%S",
    ).replace(tzinfo=timezone.utc).timestamp()
    fraction = match.group(2) or ""
    return base if not fraction else base + int(fraction) / (10 ** len(fraction))


def _boot_evidence() -> dict[str, Any]:
    boot_id_path = Path("/proc/sys/kernel/random/boot_id")
    stat_path = Path("/proc/stat")
    if (
        boot_id_path.is_symlink()
        or not boot_id_path.is_file()
        or stat_path.is_symlink()
        or not stat_path.is_file()
    ):
        raise InvalidationError("boot_authority_invalid")
    boot_id = boot_id_path.read_text(encoding="utf-8").strip()
    if not boot_id:
        raise InvalidationError("boot_id_invalid")
    btime = None
    for line in stat_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("btime "):
            raw = line.split()
            if len(raw) != 2:
                raise InvalidationError("boot_time_invalid")
            try:
                btime = int(raw[1])
            except ValueError as error:
                raise InvalidationError("boot_time_invalid") from error
            break
    if btime is None or btime <= 0:
        raise InvalidationError("boot_time_invalid")
    return {
        "boot_id_sha256": sha_text(boot_id),
        "boot_time_unix": btime,
    }


def _verify_broker_reboot_invalidation(
    plan: dict[str, Any],
) -> dict[str, Any]:
    expected = plan.get("broker_baseline")
    if not isinstance(expected, dict):
        raise InvalidationError("broker_baseline_invalid")
    observed = e03.runtime("broker")

    for key in (
        "container_id",
        "image_id",
        "image_ref",
        "network_mode",
        "restart_count",
    ):
        if observed.get(key) != expected.get(key):
            raise InvalidationError(f"broker_non_started_at_drift:{key}")

    if observed.get("restart_count") != 0:
        raise InvalidationError("broker_restart_count_invalid")
    if observed.get("started_at") == expected.get("started_at"):
        raise InvalidationError("broker_started_at_not_invalidated")
    if e03.systemctl("is-active", e03.BROKER_UNIT) != "active":
        raise InvalidationError("broker_unit_inactive")
    if e03.systemctl("is-enabled", e03.BROKER_UNIT) != "enabled":
        raise InvalidationError("broker_unit_disabled")
    if e03.listener_count("tcp", 8883) != 1:
        raise InvalidationError("broker_listener_continuity_failed")

    boot = _boot_evidence()
    expected_started = _parse_docker_started_at(expected.get("started_at"))
    observed_started = _parse_docker_started_at(observed.get("started_at"))
    boot_time = float(boot["boot_time_unix"])
    if not (expected_started < boot_time <= observed_started):
        raise InvalidationError("broker_started_at_not_current_boot")

    return {
        "expected_broker_started_at": expected["started_at"],
        "observed_broker_started_at": observed["started_at"],
        "broker_container_id": observed["container_id"],
        "broker_image_id": observed["image_id"],
        "broker_restart_count": observed["restart_count"],
        "boot_id_sha256": boot["boot_id_sha256"],
        "boot_time_unix": boot["boot_time_unix"],
    }


def _verify_invalidation_prestate(
    transaction_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    target_path = _target_path(transaction_id)
    document = _validate_target_ready(
        maintenance.TransactionStore(target_path).load()
    )
    plan = document["plan"]
    if (
        plan.get("schema") != e03.PLAN_SCHEMA
        or tuple(document["scope"]) != tuple(e03.SCOPE)
        or plan.get("predecessor_sha256") != document["predecessor_sha256"]
        or plan.get("current_release_id") != document["current_release_id"]
        or plan.get("target_release_id") != document["target_release_id"]
        or plan.get("artifact_sha256") != document["artifact_sha256"]
    ):
        raise InvalidationError("target_e03_transaction_contract_invalid")

    if e03.host_binding_sha256() != document["host_binding_sha256"]:
        raise InvalidationError("target_host_binding_drift")
    maintenance.assert_predecessor_immutable(
        e03.PREDECESSOR_TX,
        document["predecessor_sha256"],
    )
    e03.predecessor_evidence(document["predecessor_sha256"])

    if e03._deployment_reality(plan) != plan["deployment_before_fingerprint"]:
        raise InvalidationError("deployment_reality_not_exact_before")
    if e03._service_fingerprint() != plan["service_before_fingerprint"]:
        raise InvalidationError("service_reality_not_exact_before")
    if e03._gate_fingerprint() != plan["gate_before_fingerprint"]:
        raise InvalidationError("gate_reality_not_exact_before")

    manager = e03.runtime("manager")
    if (
        manager.get("container_id") != plan["manager_predecessor_container_id"]
        or manager.get("image_ref") != e03.OLD_MANAGER_IMAGE
        or manager.get("image_id") != e03.OLD_MANAGER_ID
        or manager.get("network_mode") != "host"
        or manager.get("restart_count") != 0
    ):
        raise InvalidationError("manager_predecessor_continuity_failed")

    homeassistant = e03.runtime("homeassistant")
    if (
        homeassistant.get("image_ref") != e03.HA_IMAGE
        or homeassistant.get("image_id") != e03.HA_IMAGE_ID
        or homeassistant.get("network_mode") != "host"
        or homeassistant.get("restart_count") != 0
    ):
        raise InvalidationError("homeassistant_continuity_failed")
    if e03.ha_mqtt_hash() != plan["ha_mqtt_sha256"]:
        raise InvalidationError("homeassistant_mqtt_continuity_failed")

    broker = _verify_broker_reboot_invalidation(plan)

    if e03.listener_snapshot() != e03.EXPECTED_LISTENERS:
        raise InvalidationError("listener_contract_failed")
    if e03.systemd_nrestarts(e03.SERVICES_UNIT) != plan["services_nrestarts"]:
        raise InvalidationError("services_restart_continuity_failed")

    current_f4 = e03._current_f4_authority()
    current_f4_sha256 = e03.sha_bytes(e03.canonical(current_f4))
    if current_f4_sha256 != plan["current_f4_authority_sha256"]:
        raise InvalidationError("current_f4_authority_drift")

    retirement.assert_supersession(
        plan.get("supersession"),
        predecessor_sha256=document["predecessor_sha256"],
        current_release_id=document["current_release_id"],
        target_release_id=document["target_release_id"],
        artifact_sha256=document["artifact_sha256"],
    )

    documents = e03._active_maintenance_documents()
    maintenance.ensure_no_other_active(
        documents,
        transaction_id=document["transaction_id"],
    )

    snapshot = {
        "target_transaction_sha256": sha_file(target_path),
        "target_generation": document["generation"],
        "target_invariant_sha256": _target_invariant_sha256(document),
        "deployment_before_fingerprint": plan["deployment_before_fingerprint"],
        "service_before_fingerprint": plan["service_before_fingerprint"],
        "gate_before_fingerprint": plan["gate_before_fingerprint"],
        "current_f4_authority_sha256": current_f4_sha256,
        "current_f4_transaction_sha256": current_f4["transaction_sha256"],
        "broker_invalidation": broker,
    }
    return document, snapshot


def _plan_locked(
    target_transaction_id: str,
    *,
    authority: dict[str, str],
) -> dict[str, Any]:
    document, snapshot = _verify_invalidation_prestate(target_transaction_id)
    return {
        "schema": PLAN_SCHEMA,
        "reason": REASON,
        "target_transaction_id_sha256": sha_text(document["transaction_id"]),
        "target_transaction_sha256": snapshot["target_transaction_sha256"],
        "target_generation": snapshot["target_generation"],
        "target_invariant_sha256": snapshot["target_invariant_sha256"],
        "target_authorization_id_sha256": document["authorization_id_sha256"],
        "target_host_binding_sha256": document["host_binding_sha256"],
        "target_executor_source_head": document["executor_source_head"],
        "target_executor_blob": document["executor_blob"],
        "target_module_set_sha256": document["module_set_sha256"],
        "target_plan_sha256": document["plan_sha256"],
        "target_predecessor_sha256": document["predecessor_sha256"],
        "target_current_release_id": document["current_release_id"],
        "target_release_id": document["target_release_id"],
        "target_artifact_sha256": document["artifact_sha256"],
        "deployment_before_fingerprint": snapshot["deployment_before_fingerprint"],
        "service_before_fingerprint": snapshot["service_before_fingerprint"],
        "gate_before_fingerprint": snapshot["gate_before_fingerprint"],
        "current_f4_authority_sha256": snapshot["current_f4_authority_sha256"],
        "current_f4_transaction_sha256": snapshot["current_f4_transaction_sha256"],
        "broker_invalidation": snapshot["broker_invalidation"],
        "invalidation_executor_source_head": authority["source_head"],
        "invalidation_executor_blob": authority["executor_blob"],
        "invalidation_module_set_sha256": authority["module_set_sha256"],
        "product_mutation": False,
        "service_stop_start": False,
        "docker_mutation": False,
        "board_access": False,
    }


def preflight(target_transaction_id: str) -> dict[str, Any]:
    authority = runtime_authority()
    with retirement.readonly_global_lock():
        plan = _plan_locked(target_transaction_id, authority=authority)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "preflight",
        "invalidation_plan_sha256": sha_bytes(canonical(plan)),
        "target_transaction_id_sha256": plan["target_transaction_id_sha256"],
        "target_transaction_sha256": plan["target_transaction_sha256"],
        "target_generation": plan["target_generation"],
        "broker_invalidation": plan["broker_invalidation"],
        "reason": REASON,
        "product_mutation": False,
        "service_stop_start": False,
        "docker_mutation": False,
        "board_access": False,
    }


def _record_from_plan(
    *,
    plan: dict[str, Any],
    invalidation_id: str,
    authorization_id_sha256: str,
    execution_session_id_sha256: str,
) -> dict[str, Any]:
    invalidation_id = _identifier(invalidation_id, "invalidation_id")
    return {
        "schema": SCHEMA,
        "invalidation_id": invalidation_id,
        "invalidation_id_sha256": sha_text(invalidation_id),
        "authorization_id_sha256": _sha(
            authorization_id_sha256,
            "authorization_id_sha256",
        ),
        "execution_session_id_sha256": _sha(
            execution_session_id_sha256,
            "execution_session_id_sha256",
        ),
        "plan_sha256": sha_bytes(canonical(plan)),
        "plan": json.loads(canonical(plan)),
        "executor_source_head": plan["invalidation_executor_source_head"],
        "executor_blob": plan["invalidation_executor_blob"],
        "module_set_sha256": plan["invalidation_module_set_sha256"],
        "target_transaction_id_sha256": plan["target_transaction_id_sha256"],
        "target_transaction_sha256_before": plan["target_transaction_sha256"],
        "target_generation_before": plan["target_generation"],
        "target_invariant_sha256": plan["target_invariant_sha256"],
        "reason": REASON,
        "product_mutation": False,
        "service_stop_start": False,
        "docker_mutation": False,
        "board_access": False,
        "state": "CLAIMED",
        "authorization_consumed": True,
        "replay_allowed": False,
        "generation": 1,
        "target_transaction_sha256_after": None,
        "target_generation_after": None,
        "last_operation": "authorization_claimed",
        "last_reason": None,
    }


def validate_record(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != RECORD_KEYS:
        raise InvalidationError("invalidation_record_keys_invalid")
    if document.get("schema") != SCHEMA:
        raise InvalidationError("invalidation_record_schema_invalid")
    _identifier(document.get("invalidation_id", ""), "invalidation_id")
    if document.get("invalidation_id_sha256") != sha_text(
        document["invalidation_id"]
    ):
        raise InvalidationError("invalidation_id_binding_invalid")
    for key in (
        "authorization_id_sha256",
        "execution_session_id_sha256",
        "plan_sha256",
        "module_set_sha256",
        "target_transaction_id_sha256",
        "target_transaction_sha256_before",
        "target_invariant_sha256",
    ):
        _sha(document.get(key), key)
    for key in ("executor_source_head", "executor_blob"):
        _sha(document.get(key), key, git=True)
    plan = document.get("plan")
    if (
        not isinstance(plan, dict)
        or sha_bytes(canonical(plan)) != document["plan_sha256"]
        or plan.get("schema") != PLAN_SCHEMA
        or plan.get("reason") != REASON
        or plan.get("target_transaction_id_sha256")
        != document["target_transaction_id_sha256"]
        or plan.get("target_transaction_sha256")
        != document["target_transaction_sha256_before"]
        or plan.get("target_generation") != document["target_generation_before"]
        or plan.get("target_invariant_sha256")
        != document["target_invariant_sha256"]
        or plan.get("invalidation_executor_source_head")
        != document["executor_source_head"]
        or plan.get("invalidation_executor_blob") != document["executor_blob"]
        or plan.get("invalidation_module_set_sha256")
        != document["module_set_sha256"]
    ):
        raise InvalidationError("invalidation_plan_binding_invalid")
    if document.get("state") not in {"CLAIMED", "COMMITTED"}:
        raise InvalidationError("invalidation_state_invalid")
    if document.get("authorization_consumed") is not True:
        raise InvalidationError("invalidation_authorization_not_consumed")
    if document.get("replay_allowed") is not False:
        raise InvalidationError("invalidation_replay_contract_invalid")
    for key in (
        "product_mutation",
        "service_stop_start",
        "docker_mutation",
        "board_access",
    ):
        if document.get(key) is not False or plan.get(key) is not False:
            raise InvalidationError(f"invalidation_{key}_contract_invalid")
    generation = document.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise InvalidationError("invalidation_generation_invalid")
    before_generation = document.get("target_generation_before")
    if (
        isinstance(before_generation, bool)
        or not isinstance(before_generation, int)
        or before_generation < 1
    ):
        raise InvalidationError("target_generation_before_invalid")
    if document["state"] == "COMMITTED":
        _sha(
            document.get("target_transaction_sha256_after"),
            "target_transaction_sha256_after",
        )
        if document.get("target_generation_after") != before_generation + 1:
            raise InvalidationError("target_generation_after_invalid")
    elif (
        document.get("target_transaction_sha256_after") is not None
        or document.get("target_generation_after") is not None
    ):
        raise InvalidationError("invalidation_poststate_premature")
    if document.get("reason") != REASON:
        raise InvalidationError("invalidation_reason_invalid")
    return json.loads(canonical(document))


class InvalidationStore:
    def __init__(self, path: Path, *, enforce_root_metadata: bool = True):
        self.path = path
        self.enforce_root_metadata = enforce_root_metadata

    def _require_parent(self) -> None:
        parent = self.path.parent
        if parent.is_symlink() or not parent.is_dir():
            raise InvalidationError("invalidation_parent_invalid")
        if self.enforce_root_metadata:
            meta = parent.stat()
            if (
                meta.st_uid != 0
                or meta.st_gid != 0
                or stat.S_IMODE(meta.st_mode) != 0o700
            ):
                raise InvalidationError("invalidation_parent_metadata_invalid")

    def load(self) -> dict[str, Any]:
        self._require_parent()
        if self.path.is_symlink() or not self.path.is_file():
            raise InvalidationError("invalidation_record_missing")
        meta = self.path.stat()
        if stat.S_IMODE(meta.st_mode) != 0o600:
            raise InvalidationError("invalidation_record_mode_invalid")
        if self.enforce_root_metadata and (
            meta.st_uid != 0 or meta.st_gid != 0
        ):
            raise InvalidationError("invalidation_record_owner_invalid")
        return validate_record(
            json.loads(self.path.read_text(encoding="utf-8"))
        )

    def create(self, document: dict[str, Any]) -> None:
        self._require_parent()
        payload = canonical(validate_record(document))
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            fd = os.open(self.path, flags, 0o600)
        except FileExistsError as error:
            raise InvalidationError("invalidation_record_exists") from error
        try:
            os.fchmod(fd, 0o600)
            if self.enforce_root_metadata:
                os.fchown(fd, 0, 0)
            with os.fdopen(fd, "wb") as stream:
                fd = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            self._fsync_parent()
        finally:
            if fd >= 0:
                os.close(fd)

    def save(self, document: dict[str, Any], *, expected_generation: int) -> None:
        current = self.load()
        if current["generation"] != expected_generation:
            raise InvalidationError("invalidation_generation_conflict")
        value = validate_record(document)
        if value["generation"] <= current["generation"]:
            raise InvalidationError("invalidation_generation_not_advanced")
        for key in IMMUTABLE_RECORD_KEYS:
            if value[key] != current[key]:
                raise InvalidationError(
                    f"invalidation_immutable_binding_changed:{key}"
                )
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


def _invalidation_documents() -> list[dict[str, Any]]:
    root = invalidation_root()
    if not root.exists():
        return []
    if root.is_symlink() or not root.is_dir():
        raise InvalidationError("invalidation_root_invalid")
    return [
        InvalidationStore(path).load()
        for path in sorted(root.glob("*.json"))
    ]


def claim(
    *,
    target_transaction_id: str,
    expected_preauth_plan_sha256: str,
    invalidation_id: str,
    authorization_id: str,
    execution_session_id: str,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise InvalidationError("confirmation_missing")
    _identifier(invalidation_id, "invalidation_id")
    authorization_id = _authorization_id(authorization_id)
    _identifier(execution_session_id, "execution_session_id")
    _sha(expected_preauth_plan_sha256, "preauth_plan_sha256")

    with e03.global_lock():
        authority = runtime_authority()
        plan = _plan_locked(target_transaction_id, authority=authority)
        if sha_bytes(canonical(plan)) != expected_preauth_plan_sha256:
            raise InvalidationError("preauth_plan_sha256_mismatch")

        e03._ensure_private_dir(invalidation_root())
        target_hash = plan["target_transaction_id_sha256"]
        for existing in _invalidation_documents():
            if existing["target_transaction_id_sha256"] == target_hash:
                raise InvalidationError("target_invalidation_already_exists")

        record = _record_from_plan(
            plan=plan,
            invalidation_id=invalidation_id,
            authorization_id_sha256=sha_text(authorization_id),
            execution_session_id_sha256=sha_text(execution_session_id),
        )
        store = InvalidationStore(_invalidation_path(invalidation_id))
        store.create(record)
        result = store.load()

    return public_result(
        result,
        operation="claim",
        reason_code="INVALIDATION_AUTHORIZATION_CLAIMED",
        target_state="READY",
    )


def _assert_executor_authority(document: dict[str, Any]) -> None:
    authority = runtime_authority()
    if (
        authority["source_head"] != document["executor_source_head"]
        or authority["executor_blob"] != document["executor_blob"]
        or authority["module_set_sha256"] != document["module_set_sha256"]
    ):
        raise InvalidationError("invalidation_executor_authority_drift")


def _block_target(document: dict[str, Any]) -> dict[str, Any]:
    value = _validate_target_ready(document)
    return maintenance.transition(
        value,
        "BLOCKED",
        operation="baseline_invalidated_before_apply",
        reason=REASON,
    )


def _assert_blocked_poststate(
    document: dict[str, Any],
    record: dict[str, Any],
) -> None:
    value = maintenance.validate_transaction(document)
    if (
        value["state"] != "BLOCKED"
        or value["generation"] != record["target_generation_before"] + 1
        or value["last_operation"] != "baseline_invalidated_before_apply"
        or value["last_reason"] != REASON
        or value["authorization_consumed"] is not True
        or value["replay_allowed"] is not False
        or value["operation_seq"] != 0
        or value["operations"]
        or value["observed_after"]
        or _target_invariant_sha256(value)
        != record["target_invariant_sha256"]
    ):
        raise InvalidationError("invalidated_target_poststate_invalid")


def invalidate(
    *,
    invalidation_id: str,
    target_transaction_id: str,
    execution_session_id: str,
) -> dict[str, Any]:
    with e03.global_lock():
        store = InvalidationStore(_invalidation_path(invalidation_id))
        record = store.load()
        _assert_executor_authority(record)

        session_id = _identifier(execution_session_id, "execution_session_id")
        if sha_text(session_id) != record["execution_session_id_sha256"]:
            raise InvalidationError("invalidation_execution_session_drift")
        target_id_hash = sha_text(
            _identifier(target_transaction_id, "target_transaction_id")
        )
        if target_id_hash != record["target_transaction_id_sha256"]:
            raise InvalidationError("target_transaction_id_binding_drift")

        target_path = _target_path(target_transaction_id)
        target_store = maintenance.TransactionStore(target_path)
        target = target_store.load()

        if record["state"] == "COMMITTED":
            _assert_blocked_poststate(target, record)
            if sha_file(target_path) != record["target_transaction_sha256_after"]:
                raise InvalidationError(
                    "invalidated_target_transaction_sha256_drift"
                )
            return public_result(
                record,
                operation="invalidate",
                reason_code="ALREADY_COMMITTED",
                target_state="BLOCKED",
            )

        if target["state"] == "READY":
            plan = _plan_locked(
                target_transaction_id,
                authority={
                    "source_head": record["executor_source_head"],
                    "executor_blob": record["executor_blob"],
                    "module_set_sha256": record["module_set_sha256"],
                },
            )
            if sha_bytes(canonical(plan)) != record["plan_sha256"]:
                raise InvalidationError("invalidation_prestate_binding_drift")
            blocked = _block_target(target)
            target_store.save(
                blocked,
                expected_generation=target["generation"],
            )
            target = target_store.load()
        elif target["state"] != "BLOCKED":
            raise InvalidationError("target_state_not_invalidatable")

        _assert_blocked_poststate(target, record)
        after_sha256 = sha_file(target_path)
        committed = json.loads(canonical(record))
        committed["state"] = "COMMITTED"
        committed["generation"] += 1
        committed["target_transaction_sha256_after"] = after_sha256
        committed["target_generation_after"] = target["generation"]
        committed["last_operation"] = "target_transaction_blocked"
        committed["last_reason"] = None
        committed = validate_record(committed)
        store.save(
            committed,
            expected_generation=record["generation"],
        )
        result = store.load()

    return public_result(
        result,
        operation="invalidate",
        reason_code="TARGET_TRANSACTION_BLOCKED",
        target_state="BLOCKED",
    )


def status(
    *,
    invalidation_id: str,
    target_transaction_id: str,
) -> dict[str, Any]:
    with retirement.readonly_global_lock():
        record = InvalidationStore(_invalidation_path(invalidation_id)).load()
        target_hash = sha_text(
            _identifier(target_transaction_id, "target_transaction_id")
        )
        if target_hash != record["target_transaction_id_sha256"]:
            raise InvalidationError("target_transaction_id_binding_drift")
        target = maintenance.TransactionStore(
            _target_path(target_transaction_id)
        ).load()
    return public_result(
        record,
        operation="status",
        reason_code="READ_ONLY_STATUS",
        target_state=target["state"],
    )


def public_result(
    document: dict[str, Any],
    *,
    operation: str,
    reason_code: str,
    target_state: Any,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": operation,
        "reason_code": reason_code,
        "invalidation_id_sha256": document["invalidation_id_sha256"],
        "invalidation_stage": document["state"],
        "authorization_consumed": document["authorization_consumed"],
        "replay_allowed": document["replay_allowed"],
        "target_transaction_id_sha256": document["target_transaction_id_sha256"],
        "target_state": target_state,
        "product_mutation": False,
        "service_stop_start": False,
        "docker_mutation": False,
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
    claim_parser.add_argument("--invalidation-id", required=True)
    claim_parser.add_argument("--authorization-id", required=True)
    claim_parser.add_argument("--execution-session-id", required=True)
    claim_parser.add_argument("--confirmation", required=True)

    execute_parser = sub.add_parser("invalidate")
    execute_parser.add_argument("--invalidation-id", required=True)
    execute_parser.add_argument("--target-transaction-id", required=True)
    execute_parser.add_argument("--execution-session-id", required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--invalidation-id", required=True)
    status_parser.add_argument("--target-transaction-id", required=True)

    args = parser.parse_args()

    try:
        if args.operation == "preflight":
            result = preflight(args.target_transaction_id)
        elif args.operation == "claim":
            result = claim(
                target_transaction_id=args.target_transaction_id,
                expected_preauth_plan_sha256=args.preauth_plan_sha256,
                invalidation_id=args.invalidation_id,
                authorization_id=args.authorization_id,
                execution_session_id=args.execution_session_id,
                confirmation=args.confirmation,
            )
        elif args.operation == "invalidate":
            result = invalidate(
                invalidation_id=args.invalidation_id,
                target_transaction_id=args.target_transaction_id,
                execution_session_id=args.execution_session_id,
            )
        else:
            result = status(
                invalidation_id=args.invalidation_id,
                target_transaction_id=args.target_transaction_id,
            )
    except Exception as error:
        _emit(
            {
                "schema": SCHEMA,
                "status": "STOP",
                "operation": args.operation,
                "reason_code": str(error).split(":", 1)[0],
                "product_mutation": False,
                "service_stop_start": False,
                "docker_mutation": False,
                "board_access": False,
            },
            error=True,
        )
        return 2

    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
