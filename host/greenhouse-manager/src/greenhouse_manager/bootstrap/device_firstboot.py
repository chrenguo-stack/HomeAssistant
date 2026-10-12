from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

SCHEMA = "gh.n3w.t1-device-firstboot/1"
TRANSACTION_SCHEMA = "gh.n3w.t1-device-firstboot-transaction/1"
COMPLETE_SCHEMA = "gh.n3w.t1-device-firstboot-complete/1"
TRANSACTION_NAME = "transaction.json"
COMPLETE_NAME = "FIRSTBOOT_COMPLETE.json"
STAGES = (
    "PRECHECK",
    "OS_IDENTITY",
    "PRODUCT_IDENTITY",
    "STATE",
    "BROKER",
    "DYNSEC",
    "INSTANCE_STAGE",
    "COMMIT",
    "VERIFY",
)


class DeviceFirstbootError(RuntimeError):
    pass


class DeviceFirstbootAdapters(Protocol):
    def preflight_clone(self) -> Mapping[str, object]: ...
    def ensure_os_identity(self) -> Mapping[str, object]: ...
    def create_identity(self, candidate_root: Path) -> Mapping[str, object]: ...
    def create_state(
        self,
        candidate_root: Path,
        system_id_sha256: str,
    ) -> Mapping[str, object]: ...
    def create_broker(
        self,
        candidate_root: Path,
        system_id: str,
    ) -> Mapping[str, object]: ...
    def initialize_dynsec(
        self,
        candidate_root: Path,
        system_id: str,
    ) -> Mapping[str, object]: ...
    def stage_instance_runtime(
        self,
        candidate_root: Path,
        system_id: str,
    ) -> Mapping[str, object]: ...
    def commit_instance_candidate(
        self,
        candidate_root: Path,
        system_id: str,
    ) -> Mapping[str, object]: ...
    def instance_stopped_postcheck(self, system_id: str) -> Mapping[str, object]: ...


def _validate_private_directory(path: Path, label: str) -> os.stat_result:
    if path.is_symlink() or not path.is_dir():
        raise DeviceFirstbootError(f"{label}_unsafe")
    metadata = path.stat()
    if metadata.st_uid != os.geteuid():
        raise DeviceFirstbootError(f"{label}_owner_invalid")
    if metadata.st_mode & 0o777 != 0o700:
        raise DeviceFirstbootError(f"{label}_mode_invalid")
    return metadata


def _private_root(path: Path) -> Path:
    if not path.is_absolute():
        raise DeviceFirstbootError("transaction_root_not_absolute")
    if path.is_symlink():
        raise DeviceFirstbootError("transaction_root_symlink_forbidden")
    if not path.exists():
        path.mkdir(parents=True, mode=0o700)
        path.chmod(0o700)
    _validate_private_directory(path, "transaction_root")
    return path


def _validate_candidate_root(
    path: Path,
    *,
    allow_absent: bool,
) -> os.stat_result | None:
    if not path.is_absolute():
        raise DeviceFirstbootError("candidate_root_not_absolute")
    if path.is_symlink():
        raise DeviceFirstbootError("candidate_root_symlink_forbidden")
    if not path.exists():
        if allow_absent:
            return None
        raise DeviceFirstbootError("candidate_root_missing")
    if not path.is_dir():
        raise DeviceFirstbootError("candidate_root_unsafe")
    metadata = path.stat()
    if metadata.st_uid != os.geteuid():
        raise DeviceFirstbootError("candidate_root_owner_invalid")
    if metadata.st_mode & 0o777 != 0o700:
        raise DeviceFirstbootError("candidate_root_mode_invalid")
    return metadata


def _validate_record_metadata(path: Path) -> os.stat_result:
    if path.is_symlink() or not path.is_file():
        raise DeviceFirstbootError("firstboot_record_unsafe")
    metadata = path.stat()
    if metadata.st_uid != os.geteuid():
        raise DeviceFirstbootError("firstboot_record_owner_invalid")
    if metadata.st_mode & 0o777 != 0o600:
        raise DeviceFirstbootError("firstboot_record_mode_invalid")
    return metadata


def _write_atomic(path: Path, document: Mapping[str, object]) -> None:
    _validate_private_directory(path.parent, "transaction_root")
    if path.exists() or path.is_symlink():
        _validate_record_metadata(path)

    payload = (
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    temporary = path.with_name(
        f".{path.name}.{secrets.token_hex(8)}.tmp"
    )
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(temporary, flags, 0o600)
    except FileExistsError as error:
        raise DeviceFirstbootError("firstboot_record_temp_exists") from error

    try:
        os.fchmod(descriptor, 0o600)
        metadata = os.fstat(descriptor)
        if metadata.st_uid != os.geteuid():
            raise DeviceFirstbootError("firstboot_record_temp_owner_invalid")
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _validate_record_metadata(path)
        parent_descriptor = os.open(
            path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    _validate_record_metadata(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeviceFirstbootError("firstboot_record_invalid") from error
    if not isinstance(value, dict):
        raise DeviceFirstbootError("firstboot_record_invalid")
    return value

def _require(report: Mapping[str, object], expected: Mapping[str, object], label: str) -> None:
    for key, value in expected.items():
        if report.get(key) != value:
            raise DeviceFirstbootError(f"{label}:{key}_invalid")


def _system_id(report: Mapping[str, object]) -> str:
    value = report.get("system_id")
    if not isinstance(value, str) or not value:
        raise DeviceFirstbootError("identity:system_id_invalid")
    return value


def _load_transaction(
    root: Path,
    release_id: str,
    candidate_root: Path,
) -> dict[str, Any]:
    path = root / TRANSACTION_NAME
    candidate_text = str(candidate_root)
    if not path.exists():
        document: dict[str, Any] = {
            "schema": TRANSACTION_SCHEMA,
            "release_id": release_id,
            "candidate_root": candidate_text,
            "candidate_dev": None,
            "candidate_ino": None,
            "stage": "PRECHECK",
            "host_instance_id": None,
            "system_id": None,
            "system_id_sha256": None,
        }
        _write_atomic(path, document)
        return document
    document = _read_json(path)
    if (
        document.get("schema") != TRANSACTION_SCHEMA
        or document.get("release_id") != release_id
        or document.get("candidate_root") != candidate_text
        or document.get("stage") not in STAGES
    ):
        raise DeviceFirstbootError("firstboot_transaction_binding_invalid")
    return document


def _advance(root: Path, transaction: dict[str, Any], stage: str, **values: object) -> None:
    current = transaction.get("stage")
    if current not in STAGES or stage not in STAGES:
        raise DeviceFirstbootError("firstboot_stage_invalid")
    if STAGES.index(stage) < STAGES.index(str(current)):
        raise DeviceFirstbootError("firstboot_stage_regression")
    transaction.update(values)
    transaction["stage"] = stage
    _write_atomic(root / TRANSACTION_NAME, transaction)


def _complete_report(
    root: Path,
    release_id: str,
    candidate_root: Path,
) -> dict[str, Any] | None:
    path = root / COMPLETE_NAME
    if not path.exists() and not path.is_symlink():
        return None
    document = _read_json(path)
    system_id = document.get("system_id")
    if (
        document.get("schema") != COMPLETE_SCHEMA
        or document.get("release_id") != release_id
        or document.get("status") != "PASS"
        or not isinstance(document.get("host_instance_id"), str)
        or not isinstance(system_id, str)
        or not system_id
    ):
        raise DeviceFirstbootError("firstboot_complete_binding_invalid")
    system_id_sha256 = hashlib.sha256(system_id.encode()).hexdigest()
    if document.get("system_id_sha256") != system_id_sha256:
        raise DeviceFirstbootError("firstboot_complete_binding_invalid")
    transaction = _read_json(root / TRANSACTION_NAME)
    if (
        transaction.get("schema") != TRANSACTION_SCHEMA
        or transaction.get("release_id") != release_id
        or transaction.get("candidate_root") != str(candidate_root)
        or transaction.get("stage") != "VERIFY"
        or transaction.get("host_instance_id") != document.get("host_instance_id")
        or transaction.get("system_id") != system_id
        or transaction.get("system_id_sha256") != system_id_sha256
    ):
        raise DeviceFirstbootError("firstboot_complete_transaction_drift")
    return document


def run_device_firstboot(
    adapters: DeviceFirstbootAdapters,
    transaction_root: str | Path,
    candidate_root: str | Path,
    *,
    release_id: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", release_id):
        raise DeviceFirstbootError("release_id_invalid")

    root = _private_root(Path(transaction_root).expanduser())
    candidate = Path(candidate_root).expanduser()
    _validate_candidate_root(candidate, allow_absent=True)

    complete = _complete_report(root, release_id, candidate)
    if complete is not None:
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "release_id": release_id,
            "host_instance_id": complete["host_instance_id"],
            "system_id": complete["system_id"],
            "already_complete": True,
            "production_service_start": False,
            "board_access": False,
        }

    transaction = _load_transaction(root, release_id, candidate)
    stage = str(transaction["stage"])

    preflight = adapters.preflight_clone()
    _require(
        preflight,
        {
            "status": "PASS",
            "sealed_image": True,
            "release_id": release_id,
            "production_service_start": False,
        },
        "preflight",
    )

    os_identity = adapters.ensure_os_identity()
    _require(
        os_identity,
        {
            "status": "PASS",
            "machine_id_ready": True,
            "ssh_host_identity_ready": True,
            "production_service_start": False,
        },
        "os_identity",
    )
    host_instance_id = os_identity.get("host_instance_id")
    if not isinstance(host_instance_id, str) or not host_instance_id:
        raise DeviceFirstbootError("os_identity:host_instance_id_invalid")
    bound_host = transaction.get("host_instance_id")
    if STAGES.index(stage) >= STAGES.index("OS_IDENTITY"):
        if not isinstance(bound_host, str) or not bound_host:
            raise DeviceFirstbootError("firstboot_host_binding_missing")
        if bound_host != host_instance_id:
            raise DeviceFirstbootError("firstboot_host_binding_drift")
    elif bound_host is not None:
        raise DeviceFirstbootError("firstboot_host_binding_invalid")
    else:
        _advance(
            root,
            transaction,
            "OS_IDENTITY",
            host_instance_id=host_instance_id,
        )
        stage = "OS_IDENTITY"

    system_id = transaction.get("system_id")
    system_id_sha256 = transaction.get("system_id_sha256")

    if STAGES.index(stage) < STAGES.index("PRODUCT_IDENTITY"):
        identity = adapters.create_identity(candidate)
        _require(
            identity,
            {
                "created": True,
                "production_services_modified": False,
                "network_operation": False,
            },
            "identity",
        )
        system_id = _system_id(identity)
        system_id_sha256 = hashlib.sha256(system_id.encode()).hexdigest()
        candidate_metadata = _validate_candidate_root(
            candidate,
            allow_absent=False,
        )
        assert candidate_metadata is not None
        _advance(
            root,
            transaction,
            "PRODUCT_IDENTITY",
            system_id=system_id,
            system_id_sha256=system_id_sha256,
            candidate_dev=int(candidate_metadata.st_dev),
            candidate_ino=int(candidate_metadata.st_ino),
        )
        stage = "PRODUCT_IDENTITY"

    if not isinstance(system_id, str) or not system_id:
        raise DeviceFirstbootError("firstboot_system_id_missing")
    if (
        not isinstance(system_id_sha256, str)
        or system_id_sha256 != hashlib.sha256(system_id.encode()).hexdigest()
    ):
        raise DeviceFirstbootError("firstboot_system_id_binding_invalid")

    candidate_metadata = _validate_candidate_root(
        candidate,
        allow_absent=False,
    )
    assert candidate_metadata is not None
    if (
        transaction.get("candidate_dev") != int(candidate_metadata.st_dev)
        or transaction.get("candidate_ino") != int(candidate_metadata.st_ino)
    ):
        raise DeviceFirstbootError("firstboot_candidate_binding_drift")

    if STAGES.index(stage) < STAGES.index("STATE"):
        state = adapters.create_state(candidate, system_id_sha256)
        _require(
            state,
            {
                "status": "PASS",
                "fresh_product_state": True,
                "legacy_state_imported": False,
                "node_credential_count": 0,
                "production_service_start": False,
            },
            "state",
        )
        if state.get("system_id_sha256") != system_id_sha256:
            raise DeviceFirstbootError("state:system_identity_binding_invalid")
        _advance(root, transaction, "STATE")
        stage = "STATE"

    if STAGES.index(stage) < STAGES.index("BROKER"):
        broker = adapters.create_broker(candidate, system_id)
        _require(
            broker,
            {
                "service_count": 3,
                "node_credential_count": 0,
                "broker_transport_ca_separate_from_system_ca": True,
                "secret_values_included": False,
                "production_service_start": False,
                "network_operation": False,
            },
            "broker",
        )
        if broker.get("system_id") != system_id:
            raise DeviceFirstbootError("broker:system_identity_binding_invalid")
        _advance(root, transaction, "BROKER")
        stage = "BROKER"

    if STAGES.index(stage) < STAGES.index("DYNSEC"):
        dynsec = adapters.initialize_dynsec(candidate, system_id)
        _require(
            dynsec,
            {
                "status": "PASS",
                "service_client_count": 3,
                "service_role_count": 3,
                "node_client_count": 0,
                "node_role_count": 0,
                "default_acl_exact": True,
                "admin_runtime_use_forbidden": True,
                "secret_values_included": False,
                "production_service_start": False,
            },
            "dynsec",
        )
        _advance(root, transaction, "DYNSEC")
        stage = "DYNSEC"

    if STAGES.index(stage) < STAGES.index("INSTANCE_STAGE"):
        staged = adapters.stage_instance_runtime(candidate, system_id)
        _require(
            staged,
            {
                "status": "PASS",
                "instance_only": True,
                "public_material_modified": False,
                "services_stopped": True,
                "production_service_start": False,
            },
            "instance_stage",
        )
        _advance(root, transaction, "INSTANCE_STAGE")
        stage = "INSTANCE_STAGE"

    if STAGES.index(stage) < STAGES.index("COMMIT"):
        committed = adapters.commit_instance_candidate(candidate, system_id)
        _require(
            committed,
            {
                "status": "PASS",
                "instance_committed": True,
                "transaction_owned_only": True,
                "public_material_modified": False,
                "production_service_start": False,
            },
            "instance_commit",
        )
        _advance(root, transaction, "COMMIT")
        stage = "COMMIT"

    postcheck = adapters.instance_stopped_postcheck(system_id)
    _require(
        postcheck,
        {
            "status": "PASS",
            "device_ready": True,
            "node_credential_count": 0,
            "product_listener_count": 0,
            "production_service_start": False,
        },
        "instance_postcheck",
    )
    if STAGES.index(stage) < STAGES.index("VERIFY"):
        _advance(root, transaction, "VERIFY")

    complete_document = {
        "schema": COMPLETE_SCHEMA,
        "status": "PASS",
        "release_id": release_id,
        "host_instance_id": host_instance_id,
        "system_id": system_id,
        "system_id_sha256": system_id_sha256,
        "production_service_start": False,
        "board_access": False,
    }
    _write_atomic(root / COMPLETE_NAME, complete_document)
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "release_id": release_id,
        "host_instance_id": host_instance_id,
        "system_id": system_id,
        "already_complete": False,
        "production_service_start": False,
        "board_access": False,
    }
