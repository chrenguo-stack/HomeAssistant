#!/usr/bin/python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import time
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from types import ModuleType

SCHEMA = "gh.n3w-t1-f4-activation-host/1"
TRANSACTION_SCHEMA = "gh.n3w-t1-f4-activation-transaction/1"
FACTORY_ACCEPTED_SCHEMA = "gh.n3w.t1-factory-accepted/1"
PACKAGE_SCHEMA = "gh.n3w-t1-f4-activation-package/1"
PACKAGE_MANIFEST_NAME = "f4-package-manifest.json"

PREPARE_CONFIRMATION = "PREPARE F4 ACTIVATION: YES"
ACTIVATE_CONFIRMATION = "START F4 ACTIVATION: YES"
CONTROL_REPAIR_CONFIRMATION = "REPAIR F4 CONTROL MATERIAL: YES"

CONTROL_REPAIR_DEFECT_SOURCE_HEAD = (
    "ad65bf7d10db76f12a09e19b337f4a0c7782894a"
)
CONTROL_REPAIR_DEFECT_MANIFEST_SHA256 = (
    "9ed2ce124fbe0e621b4443a655c1cb78285db79b30489e2d41bcf73f4ee5e230"
)
CONTROL_REPAIR_DEFECT_LAUNCHER_SHA256 = (
    "070f24eb3e53953747392562d425e2c43385c9b5d9c704bc89c4a82bfdc766b7"
)

ACTIVATION_AUTHORITY_REPAIR_CONFIRMATION = (
    "REPAIR F4 ACTIVATION AUTHORITY: YES"
)
ACTIVATION_AUTHORITY_REPAIR_FROM_SOURCE_HEAD = (
    "2b30e541d561e6878525a95ee15aa426cc743595"
)
ACTIVATION_AUTHORITY_REPAIR_FROM_MANIFEST_SHA256 = (
    "4407e16e29b3da2fe498f82909dedce85dd6c822bd0cd1f4da5c58330a64a7b4"
)
ACTIVATION_AUTHORITY_REPAIR_FROM_LAUNCHER_SHA256 = (
    "2a91b0fe3edfce86187d98eadbe47d3f91a5e40a477f938bf8ff728bd0bef0ff"
)

RUNTIME_START_REPAIR_CONFIRMATION = "REPAIR F4 RUNTIME START: YES"
RUNTIME_START_REPAIR_FROM_SOURCE_HEAD = (
    "444ed085104080ea68ea073c1ff426f676d70db1"
)
RUNTIME_START_REPAIR_FROM_MANIFEST_SHA256 = (
    "b5d06fa0531b23155c41c245ae07f8edc2fc71a0552cb566d96dc83e424eaad1"
)
RUNTIME_START_REPAIR_FROM_LAUNCHER_SHA256 = (
    "fcbbf9d20f1ca82089f5e3dfd1bd8923cc8893ebaf6a04c36b36e0c46f330a01"
)

RUNTIME_CONTINUATION_AUTHORITY_REPAIR_CONFIRMATION = (
    "REPAIR F4 RUNTIME CONTINUATION AUTHORITY: YES"
)
RUNTIME_CONTINUATION_AUTHORITY_REPAIR_FROM_SOURCE_HEAD = (
    "8f870d027eea674a4443097ab0d5761542b28a73"
)
RUNTIME_CONTINUATION_AUTHORITY_REPAIR_FROM_MANIFEST_SHA256 = (
    "c88c4677cb621f20e7f093bfcfca9d6ef8ae3752b2c8d0bddba9d0bc1732e868"
)
RUNTIME_CONTINUATION_AUTHORITY_REPAIR_FROM_LAUNCHER_SHA256 = (
    "56445c031e20a7b4870b65dd8d0ee96b019314deb634123904f418630b268907"
)

RUNTIME_ACCEPTANCE_RECOVERY_CONFIRMATION = (
    "RECOVER F4 STOPPED RUNTIME ACCEPTANCE: YES"
)
RUNTIME_ACCEPTANCE_RECOVERY_FROM_SOURCE_HEAD = (
    "ffcbb1a890e42ac776c6d90000bf3f25195da01d"
)
RUNTIME_ACCEPTANCE_RECOVERY_FROM_MANIFEST_SHA256 = (
    "4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669"
)
RUNTIME_ACCEPTANCE_RECOVERY_FROM_LAUNCHER_SHA256 = (
    "f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b"
)

EXPECTED_RUNTIME_SERVICES = frozenset({"broker", "manager", "homeassistant"})
RUNTIME_SERVICE_SET_TIMEOUT_SECONDS = 60.0
RUNTIME_SERVICE_SET_POLL_SECONDS = 1.0

PRODUCT_ROOT = Path("/opt/HomeAssistant")
RELEASE_PATH = PRODUCT_ROOT / "infra/n3w-t1/production/fresh-release.json"
LIVE_COMPOSE_SOURCE = PRODUCT_ROOT / "infra/n3w-t1/production/docker-compose.yml"
FRESH_TOOL_PATH = PRODUCT_ROOT / "tools/n3w_t1_fresh_product_bootstrap.py"
PROVISION_CLI = Path("/usr/local/sbin/n3w-t1-provision")

PROVISIONING_ROOT = Path("/var/lib/n3w-t1-provisioning")
FACTORY_ACCEPTED_PATH = PROVISIONING_ROOT / "FACTORY_ACCEPTED.json"
TRANSACTION_PATH = PROVISIONING_ROOT / "F4_ACTIVATION_TRANSACTION.json"
RUNTIME_ACCEPTANCE_PATH = PROVISIONING_ROOT / "F4_RUNTIME_ACCEPTANCE.json"
F4_LOCK_PATH = PROVISIONING_ROOT / ".f4-activation.lock"

BROKER_UNIT = "n3wfc4-broker-activation.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
GUARD_UNIT = "n3wfc4-broker-ingress-guard.service"
PROVISION_UNIT = "n3wfc4-provision-resume.service"
CERT_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
CERT_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"

ETC_N3W = Path("/etc/n3wfc4")
BROKER_ENV = ETC_N3W / "broker-activation.env"
COMPOSE_TARGET = ETC_N3W / "docker-compose.yml"
COMPOSE_ENV = ETC_N3W / "docker-compose.env"
CERT_ENV = ETC_N3W / "broker-certificate-lifecycle.env"
CERT_STATUS_ROOT = Path("/var/lib/n3wfc4-certificate-lifecycle")

CA_CERT = ETC_N3W / "tls/ca.pem"
SERVER_CERT = ETC_N3W / "tls/server.pem"
SERVER_KEY = ETC_N3W / "tls/server.key"
CA_KEY = Path("/opt/greenhouse-secrets/broker-ca/ca.key")
SYSTEM_CA = Path("/var/lib/greenhouse-manager/identity/system-ca.pem")
SERVER_NAME = "armbian"
BROKER_PROJECT = "n3wfc4"
BROKER_NETWORKS = frozenset({"n3wfc4-private", "n3wfc4-services"})
SERVICE_SECRET_ROOT = Path("/opt/greenhouse-secrets/mqtt")
PRODUCT_TARGET_PORTS = frozenset(
    {1883, 8883, 18883, 8123, 47110, 47111, 47112}
)
CERT_STATUS_FILE = CERT_STATUS_ROOT / "status.json"
CERT_LOCK_FILE = CERT_STATUS_ROOT / ".certificate-lifecycle.lock"

INSTALL_MAP = {
    "tools/n3w_t1_f4_activation_host.py": (
        Path("/usr/local/sbin/n3w-t1-f4-activation"),
        0o755,
    ),
    "tools/n3w_t1_broker_authenticated_readiness.py": (
        Path("/usr/local/sbin/n3w-t1-broker-authenticated-readiness"),
        0o755,
    ),
    "tools/n3w_broker_certificate_lifecycle.py": (
        Path("/usr/local/sbin/n3w-broker-certificate-lifecycle"),
        0o755,
    ),
    "infra/n3w-t1/f4/n3wfc4-broker-activation.service": (
        Path("/etc/systemd/system/n3wfc4-broker-activation.service"),
        0o644,
    ),
    "infra/n3w-t1/f4/n3wfc4-services-activation.service": (
        Path("/etc/systemd/system/n3wfc4-services-activation.service"),
        0o644,
    ),
    "infra/n3w-t1/f4/n3wfc4-broker-certificate-lifecycle.service": (
        Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service"),
        0o644,
    ),
    "infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.timer": (
        Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer"),
        0o644,
    ),
    "infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard": (
        Path("/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard"),
        0o755,
    ),
}

INSPECT_STAGES = frozenset(
    {
        "PREPARED",
        "BROKER_STARTING",
        "BROKER_READY",
        "SERVICES_STARTING",
        "RUNTIME_STARTED",
        "RUNTIME_ACCEPTED",
        "PERSISTENCE_ENABLED",
    }
)


class F4Error(RuntimeError):
    pass


OPERATION_ERRORS = (
    F4Error,
    ImportError,
    KeyError,
    OSError,
    RuntimeError,
    subprocess.SubprocessError,
    TypeError,
    ValueError,
)


def _emit(document: dict[str, object], *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    )


def _run(
    argv: Sequence[str],
    *,
    timeout: float = 300.0,
    allowed: frozenset[int] = frozenset({0}),
) -> str:
    completed = subprocess.run(
        tuple(argv),
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode not in allowed:
        reason = completed.stderr.strip() or completed.stdout.strip()
        raise F4Error(
            f"command_failed:{argv[0]}:{completed.returncode}:{reason[:300]}"
        )
    return completed.stdout


def _systemctl(mode: str, unit: str) -> str:
    completed = subprocess.run(
        ("systemctl", mode, unit),
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=20,
    )
    return completed.stdout.strip() or "unknown"


def _runtime_activity() -> dict[str, object]:
    broker_state = _systemctl("is-active", BROKER_UNIT)
    services_state = _systemctl("is-active", SERVICES_UNIT)
    active_states = {"active", "activating", "reloading"}
    unit_active = broker_state in active_states or services_state in active_states
    running_services: list[str] | None = None
    runtime_probe = "NOT_APPLICABLE"
    if COMPOSE_TARGET.is_file() and not COMPOSE_TARGET.is_symlink():
        if not COMPOSE_ENV.is_file() or COMPOSE_ENV.is_symlink():
            return {
                "broker_active_state": broker_state,
                "services_active_state": services_state,
                "runtime_service_probe": "UNPROVEN",
                "running_services": None,
                "production_service_start": None,
            }
        try:
            output = _run(
                (
                    "docker",
                    "compose",
                    "--project-name",
                    "n3wfc4",
                    "--env-file",
                    str(COMPOSE_ENV),
                    "-f",
                    str(COMPOSE_TARGET),
                    "--profile",
                    "application",
                    "ps",
                    "--status",
                    "running",
                    "--services",
                ),
                timeout=60,
            )
            running_services = sorted(
                line.strip()
                for line in output.splitlines()
                if line.strip()
            )
            runtime_probe = "PASS"
        except OPERATION_ERRORS:
            return {
                "broker_active_state": broker_state,
                "services_active_state": services_state,
                "runtime_service_probe": "UNPROVEN",
                "running_services": None,
                "production_service_start": None,
            }
    containers_active = bool(running_services)
    return {
        "broker_active_state": broker_state,
        "services_active_state": services_state,
        "runtime_service_probe": runtime_probe,
        "running_services": running_services,
        "production_service_start": unit_active or containers_active,
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_binding(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise F4Error(f"installed_file_invalid:{path}")
    metadata = path.stat()
    return {
        "sha256": _sha256_file(path),
        "size": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
    }


def _private_service_json(
    path: Path,
    *,
    uid: int,
    gid: int,
) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise F4Error(f"service_identity_file_invalid:{path.name}")
    metadata = path.stat()
    if (
        metadata.st_uid != uid
        or metadata.st_gid != gid
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise F4Error(f"service_identity_metadata_invalid:{path.name}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise F4Error(f"service_identity_json_invalid:{path.name}") from error
    if not isinstance(document, dict):
        raise F4Error(f"service_identity_document_invalid:{path.name}")
    return document


def _runtime_container_snapshot() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for service in ("broker", "manager", "homeassistant"):
        document = _compose_service_inspect(service)
        state = document.get("State")
        identifier = document.get("Id")
        if (
            not isinstance(state, dict)
            or not isinstance(identifier, str)
            or not identifier
            or not isinstance(state.get("StartedAt"), str)
            or not state.get("StartedAt")
        ):
            raise F4Error(f"runtime_identity_invalid:{service}")
        result[service] = {
            "id": identifier,
            "started_at": str(state["StartedAt"]),
        }
    return result


def _product_listener_ports() -> list[int]:
    output = _run(("ss", "-ltnH"), timeout=20)
    observed: set[int] = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        local = fields[3]
        try:
            port = int(local.rsplit(":", 1)[1])
        except (IndexError, ValueError):
            continue
        if port in PRODUCT_TARGET_PORTS:
            observed.add(port)
    return sorted(observed)


def _require_root() -> None:
    if os.geteuid() != 0:
        raise F4Error("root_required")


def _read_json_file(path: Path, *, mode: int | None = None) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise F4Error(f"record_invalid:{path.name}")
    metadata = path.stat()
    if metadata.st_uid != 0 or metadata.st_nlink != 1:
        raise F4Error(f"record_metadata_invalid:{path.name}")
    if mode is not None and stat.S_IMODE(metadata.st_mode) != mode:
        raise F4Error(f"record_mode_invalid:{path.name}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise F4Error(f"record_json_invalid:{path.name}") from error
    if not isinstance(document, dict):
        raise F4Error(f"record_document_invalid:{path.name}")
    return document


def _read_release() -> dict[str, object]:
    document = _read_json_file(RELEASE_PATH, mode=0o644)
    release_id = document.get("release_id")
    if (
        document.get("schema") != "gh.n3w-t1-fresh-release/1"
        or not isinstance(release_id, str)
        or release_id != document.get("source_head")
        or document.get("explicit_provisioning_required") is not True
        or document.get("production_service_start") is not False
    ):
        raise F4Error("fresh_release_binding_invalid")
    return document


def _provision_verify() -> dict[str, object]:
    output = _run((str(PROVISION_CLI), "verify"), timeout=1800.0)
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise F4Error("provision_verify_json_invalid") from error
    release = _read_release()
    if (
        not isinstance(document, dict)
        or document.get("status") != "PASS"
        or document.get("state") != "DEVICE_READY"
        or document.get("release_id") != release.get("release_id")
        or document.get("production_service_start") is not False
        or document.get("board_access") is not False
    ):
        raise F4Error("provision_verify_not_device_ready")
    for key in ("host_instance_id", "system_id"):
        if not isinstance(document.get(key), str) or not document.get(key):
            raise F4Error(f"provision_verify_{key}_invalid")
    return document


def _load_fresh_module() -> ModuleType:
    if FRESH_TOOL_PATH.is_symlink() or not FRESH_TOOL_PATH.is_file():
        raise F4Error("fresh_tool_invalid")
    specification = importlib.util.spec_from_file_location(
        "n3w_f4_fresh_bootstrap",
        FRESH_TOOL_PATH,
    )
    if specification is None or specification.loader is None:
        raise F4Error("fresh_tool_import_invalid")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _stopped_instance_audit(
    release: dict[str, object],
    system_id: str,
) -> dict[str, object]:
    module = _load_fresh_module()
    manifest = {
        "images": release["images"],
        "image_lock": release["image_lock"],
        "source_head": release["source_head"],
    }
    adapters = module.LiveFreshInstallerAdapters(
        PRODUCT_ROOT,
        manifest,
        module.Runner(),
    )
    for label in ("homeassistant", "manager", "broker"):
        record = release["images"][label]
        adapters.loaded_image_bindings[label] = module._verify_runtime_image(
            adapters.runner,
            label,
            record,
        )
    report = adapters.instance_stopped_postcheck(system_id)
    if (
        report.get("status") != "PASS"
        or report.get("device_ready") is not True
        or int(report.get("node_credential_count", -1)) != 0
        or int(report.get("product_listener_count", -1)) != 0
        or report.get("production_service_start") is not False
    ):
        raise F4Error("stopped_instance_audit_failed")
    return report


def _preactivation_unit_boundary() -> dict[str, object]:
    guard_enabled = _systemctl("is-enabled", GUARD_UNIT)
    provision_enabled = _systemctl("is-enabled", PROVISION_UNIT)
    if guard_enabled != "enabled" or provision_enabled != "enabled":
        raise F4Error("staged_unit_enablement_invalid")
    states: dict[str, str] = {}
    for unit in (BROKER_UNIT, SERVICES_UNIT, CERT_TIMER):
        active = _systemctl("is-active", unit)
        enabled = _systemctl("is-enabled", unit)
        if active in {"active", "activating", "reloading"}:
            raise F4Error(f"preactivation_unit_active:{unit}")
        if enabled == "enabled":
            raise F4Error(f"preactivation_unit_enabled:{unit}")
        states[f"{unit}:active"] = active
        states[f"{unit}:enabled"] = enabled
    return {
        "guard_enabled": True,
        "provision_resume_enabled": True,
        "activation_units_stopped": True,
        "activation_units_disabled": True,
        "states": states,
    }


def _factory_audit(*, require_claim_absent: bool) -> dict[str, object]:
    release = _read_release()
    verified = _provision_verify()
    if FACTORY_ACCEPTED_PATH.exists() or FACTORY_ACCEPTED_PATH.is_symlink():
        raise F4Error("factory_acceptance_already_present")
    if require_claim_absent and (
        TRANSACTION_PATH.exists() or TRANSACTION_PATH.is_symlink()
    ):
        raise F4Error("f4_transaction_already_present")
    stopped = _stopped_instance_audit(
        release,
        str(verified["system_id"]),
    )
    boundary = _preactivation_unit_boundary()
    return {
        "status": "PASS",
        "release_id": str(verified["release_id"]),
        "host_instance_id": str(verified["host_instance_id"]),
        "system_id": str(verified["system_id"]),
        "system_id_sha256": _sha256_text(str(verified["system_id"])),
        "stopped_instance_audit": stopped,
        "unit_boundary": boundary,
        "production_service_start": False,
        "board_access": False,
    }


def _validate_private_root() -> Path:
    if PROVISIONING_ROOT.is_symlink() or not PROVISIONING_ROOT.is_dir():
        raise F4Error("provisioning_root_invalid")
    metadata = PROVISIONING_ROOT.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise F4Error("provisioning_root_metadata_invalid")
    return PROVISIONING_ROOT


@contextmanager
def _exclusive_f4():
    root = _validate_private_root()
    if F4_LOCK_PATH.parent != root:
        raise F4Error("f4_lock_parent_invalid")
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = os.open(F4_LOCK_PATH, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, 0, 0)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != 0
            or metadata.st_gid != 0
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
        ):
            raise F4Error("f4_lock_metadata_invalid")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise F4Error("f4_operation_already_running") from error
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _new_private_record(path: Path, document: dict[str, object]) -> None:
    root = _validate_private_root()
    if path.parent != root:
        raise F4Error("record_parent_invalid")
    if path.exists() or path.is_symlink():
        raise F4Error(f"record_already_exists:{path.name}")
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    temporary = root / f".{path.name}.{os.getpid()}.claim"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, 0, 0)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
        directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_private_record(path: Path) -> dict[str, object]:
    root = _validate_private_root()
    if path.parent != root:
        raise F4Error("record_parent_invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise F4Error(f"private_record_unavailable:{path.name}") from error
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != 0
            or metadata.st_gid != 0
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
        ):
            raise F4Error(f"private_record_metadata_invalid:{path.name}")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            payload = stream.read(131072)
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise F4Error(f"private_record_json_invalid:{path.name}") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(document, dict):
        raise F4Error(f"private_record_document_invalid:{path.name}")
    return document


def _replace_transaction(document: dict[str, object]) -> None:
    current = _read_private_record(TRANSACTION_PATH)
    if current.get("schema") != TRANSACTION_SCHEMA:
        raise F4Error("f4_transaction_schema_invalid")
    root = _validate_private_root()
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    temporary = root / f".{TRANSACTION_PATH.name}.{os.getpid()}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    replaced = False
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, 0, 0)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, TRANSACTION_PATH)
        replaced = True
        directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not replaced:
            temporary.unlink(missing_ok=True)


def _factory_document(audit: dict[str, object]) -> dict[str, object]:
    return {
        "schema": FACTORY_ACCEPTED_SCHEMA,
        "status": "PASS",
        "factory_accepted": True,
        "release_id": audit["release_id"],
        "host_instance_id": audit["host_instance_id"],
        "system_id": audit["system_id"],
        "system_id_sha256": audit["system_id_sha256"],
    }


def _transaction_document(
    audit: dict[str, object],
    authorization_id: str,
    package: dict[str, object],
) -> dict[str, object]:
    if (
        not authorization_id.startswith("N3W_T1_F4_")
        or len(authorization_id) > 200
        or not authorization_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise F4Error("authorization_id_invalid")
    return {
        "schema": TRANSACTION_SCHEMA,
        "status": "CLAIMED",
        "stage": "CLAIMED",
        "authorization_id": authorization_id,
        "package_source_head": package["source_head"],
        "package_manifest_sha256": package["manifest_sha256"],
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "release_id": audit["release_id"],
        "host_instance_id": audit["host_instance_id"],
        "system_id": audit["system_id"],
        "system_id_sha256": audit["system_id_sha256"],
        "production_service_start": False,
        "board_access": False,
    }


def _advance_transaction(stage: str, **fields: object) -> dict[str, object]:
    document = _read_private_record(TRANSACTION_PATH)
    document.update(fields)
    document["stage"] = stage
    document["status"] = "PASS" if not stage.startswith("STOPPED") else "STOP"
    document["authorization_claimed"] = True
    document["authorization_consumed"] = True
    document["replay_allowed"] = False
    _replace_transaction(document)
    return document


def _validate_factory_binding(
    verified: dict[str, object],
) -> dict[str, object]:
    document = _read_private_record(FACTORY_ACCEPTED_PATH)
    expected = {
        "schema": FACTORY_ACCEPTED_SCHEMA,
        "status": "PASS",
        "factory_accepted": True,
        "release_id": verified["release_id"],
        "host_instance_id": verified["host_instance_id"],
        "system_id": verified["system_id"],
        "system_id_sha256": _sha256_text(str(verified["system_id"])),
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise F4Error(f"factory_acceptance_binding_invalid:{key}")
    return document


def _validate_transaction_binding(
    verified: dict[str, object],
) -> dict[str, object]:
    document = _read_private_record(TRANSACTION_PATH)
    expected = {
        "schema": TRANSACTION_SCHEMA,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "release_id": verified["release_id"],
        "host_instance_id": verified["host_instance_id"],
        "system_id": verified["system_id"],
        "system_id_sha256": _sha256_text(str(verified["system_id"])),
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise F4Error(f"f4_transaction_binding_invalid:{key}")
    if (
        not isinstance(document.get("package_source_head"), str)
        or re.fullmatch(r"[0-9a-f]{40}", str(document["package_source_head"]))
        is None
        or not isinstance(document.get("package_manifest_sha256"), str)
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document["package_manifest_sha256"]),
        )
        is None
    ):
        raise F4Error("f4_transaction_package_binding_invalid")
    return document


def _verify_installed_material(
    transaction: dict[str, object],
) -> None:
    expected = transaction.get("installed_files")
    if not isinstance(expected, dict):
        raise F4Error("installed_material_binding_missing")
    required = {
        str(target)
        for target, _mode in INSTALL_MAP.values()
    } | {
        str(COMPOSE_TARGET),
        str(BROKER_ENV),
        str(CERT_ENV),
    }
    if set(expected) != required:
        raise F4Error("installed_material_file_set_invalid")
    for raw_path, binding in expected.items():
        if not isinstance(raw_path, str) or not isinstance(binding, dict):
            raise F4Error("installed_material_binding_invalid")
        observed = _file_binding(Path(raw_path))
        if observed != binding:
            raise F4Error(f"installed_material_drift:{raw_path}")


def _validate_runtime_acceptance_binding(
    transaction: dict[str, object],
) -> dict[str, object]:
    expected_sha = transaction.get("runtime_acceptance_report_sha256")
    if (
        transaction.get("runtime_acceptance_passed") is not True
        or not isinstance(expected_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None
        or not RUNTIME_ACCEPTANCE_PATH.is_file()
        or RUNTIME_ACCEPTANCE_PATH.is_symlink()
        or _sha256_file(RUNTIME_ACCEPTANCE_PATH) != expected_sha
    ):
        raise F4Error("runtime_acceptance_binding_invalid")
    report = _read_private_record(RUNTIME_ACCEPTANCE_PATH)
    if (
        report.get("schema") != "gh.n3w-t1-f4-runtime-acceptance/1"
        or report.get("status") != "PASS"
        or report.get("package_source_head")
        != transaction.get("package_source_head")
        or report.get("package_manifest_sha256")
        != transaction.get("package_manifest_sha256")
        or report.get("production_service_start") is not True
        or report.get("persistence_enabled") is not False
        or report.get("certificate_timer_enabled") is not False
        or report.get("secret_values_included") is not False
        or report.get("board_access") is not False
    ):
        raise F4Error("runtime_acceptance_report_contract_invalid")
    homeassistant = report.get("homeassistant")
    if (
        not isinstance(homeassistant, dict)
        or transaction.get("homeassistant_mqtt_entry_id_sha256")
        != homeassistant.get("entry_id_sha256")
    ):
        raise F4Error("runtime_acceptance_homeassistant_binding_invalid")
    return report


def _activation_eligibility(phase: str) -> dict[str, object]:
    verified = _provision_verify()
    marker = _validate_factory_binding(verified)
    transaction = _validate_transaction_binding(verified)
    stage = str(transaction.get("stage", "UNKNOWN"))
    required = {
        "inspect": INSPECT_STAGES,
        "broker": frozenset(
            {
                "BROKER_STARTING",
                "BROKER_READY",
                "SERVICES_STARTING",
                "RUNTIME_STARTED",
                "RUNTIME_ACCEPTED",
                "PERSISTENCE_ENABLED",
            }
        ),
        "services": frozenset(
            {
                "SERVICES_STARTING",
                "RUNTIME_STARTED",
                "RUNTIME_ACCEPTED",
                "PERSISTENCE_ENABLED",
            }
        ),
        "certificate": frozenset({"PERSISTENCE_ENABLED"}),
    }
    allowed = required.get(phase)
    if allowed is None:
        raise F4Error("eligibility_phase_invalid")
    if stage not in allowed:
        raise F4Error(f"f4_transaction_stage_not_eligible:{phase}:{stage}")
    if phase == "certificate":
        status_sha256 = transaction.get("certificate_status_sha256")
        if (
            transaction.get("broker_services_persistence_enabled") is not True
            or transaction.get("certificate_first_audit_passed") is not True
            or transaction.get("certificate_timer_enabled") is not True
            or transaction.get("pre_reboot_ready") is not True
            or not isinstance(status_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", status_sha256) is None
            or not CERT_STATUS_FILE.is_file()
            or CERT_STATUS_FILE.is_symlink()
            or _sha256_file(CERT_STATUS_FILE) != status_sha256
        ):
            raise F4Error("certificate_runtime_not_authorized")
    _verify_installed_material(transaction)
    runtime = _runtime_activity()
    return {
        "status": "PASS",
        "state": "FACTORY_ACCEPTED",
        "activation_eligible": True,
        "release_id": verified["release_id"],
        "factory_accepted": marker["factory_accepted"],
        "transaction_stage": stage,
        "eligibility_phase": phase,
        "package_source_head": transaction["package_source_head"],
        "package_manifest_sha256": transaction["package_manifest_sha256"],
        "production_service_start": runtime["production_service_start"],
        "runtime_service_probe": runtime["runtime_service_probe"],
        "running_services": runtime["running_services"],
        "board_access": False,
    }


def _regular_source(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise F4Error(f"package_source_invalid:{path}")


def _safe_package_file(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.as_posix() != relative
    ):
        raise F4Error("package_manifest_path_invalid")
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise F4Error(f"package_source_symlink:{relative}")
    if not current.is_file():
        raise F4Error(f"package_source_missing:{relative}")
    return current


def _validate_package(
    package_root: Path,
    *,
    expected_manifest_sha256: str,
    expected_source_head: str,
) -> dict[str, object]:
    root = Path(os.path.abspath(os.fspath(package_root)))
    if root.is_symlink() or not root.is_dir():
        raise F4Error("package_root_invalid")
    if re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256) is None:
        raise F4Error("package_manifest_sha256_invalid")
    if re.fullmatch(r"[0-9a-f]{40}", expected_source_head) is None:
        raise F4Error("package_source_head_invalid")

    manifest_path = root / PACKAGE_MANIFEST_NAME
    _regular_source(manifest_path)
    if _sha256_file(manifest_path) != expected_manifest_sha256:
        raise F4Error("package_manifest_sha256_mismatch")
    if manifest_path.stat().st_size > 1024 * 1024:
        raise F4Error("package_manifest_oversized")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise F4Error("package_manifest_json_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != PACKAGE_SCHEMA
        or document.get("source_head") != expected_source_head
        or document.get("secret_values_included") is not False
        or document.get("production_service_start") is not False
        or document.get("board_access") is not False
    ):
        raise F4Error("package_manifest_contract_invalid")

    records = document.get("files")
    if not isinstance(records, list):
        raise F4Error("package_manifest_files_invalid")
    expected_paths = set(INSTALL_MAP)
    observed: dict[str, dict[str, object]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise F4Error("package_manifest_record_invalid")
        relative = record.get("path")
        sha256 = record.get("sha256")
        size = record.get("size")
        if (
            not isinstance(relative, str)
            or relative in observed
            or not isinstance(sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            raise F4Error("package_manifest_record_invalid")
        source = _safe_package_file(root, relative)
        if source.stat().st_size != size or _sha256_file(source) != sha256:
            raise F4Error(f"package_file_binding_invalid:{relative}")
        observed[relative] = {
            "sha256": sha256,
            "size": size,
        }
    if set(observed) != expected_paths:
        raise F4Error("package_file_set_invalid")
    return {
        "root": root,
        "manifest_sha256": expected_manifest_sha256,
        "source_head": expected_source_head,
        "files": observed,
    }


def _atomic_install(
    source: Path,
    target: Path,
    mode: int,
    *,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
) -> None:
    _regular_source(source)
    if target.exists() or target.is_symlink():
        raise F4Error(f"install_target_exists:{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.is_symlink() or not target.parent.is_dir():
        raise F4Error(f"install_parent_invalid:{target.parent}")
    temporary = target.parent / f".{target.name}.{os.getpid()}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    installed = False
    try:
        with source.open("rb") as input_stream, os.fdopen(
            descriptor,
            "wb",
        ) as output_stream:
            descriptor = -1
            shutil.copyfileobj(input_stream, output_stream)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.chmod(temporary, mode)
        os.chown(temporary, 0, 0)
        if expected_size is not None and temporary.stat().st_size != expected_size:
            raise F4Error(f"install_size_mismatch:{target}")
        if (
            expected_sha256 is not None
            and _sha256_file(temporary) != expected_sha256
        ):
            raise F4Error(f"install_sha256_mismatch:{target}")
        os.link(temporary, target, follow_symlinks=False)
        temporary.unlink()
        installed = True
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not installed:
            temporary.unlink(missing_ok=True)


def _atomic_replace_bound_file(
    source: Path,
    target: Path,
    mode: int,
    *,
    expected_current: dict[str, object],
    expected_sha256: str,
    expected_size: int,
) -> None:
    _regular_source(source)
    if _file_binding(target) != expected_current:
        raise F4Error(f"repair_target_binding_changed:{target}")
    if source.stat().st_size != expected_size or _sha256_file(source) != expected_sha256:
        raise F4Error(f"repair_source_binding_invalid:{target}")
    temporary = target.parent / f".{target.name}.{os.getpid()}.repair"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    replaced = False
    try:
        with source.open("rb") as input_stream, os.fdopen(
            descriptor,
            "wb",
        ) as output_stream:
            descriptor = -1
            shutil.copyfileobj(input_stream, output_stream)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.chmod(temporary, mode)
        os.chown(temporary, 0, 0)
        if _sha256_file(temporary) != expected_sha256:
            raise F4Error(f"repair_temporary_sha256_invalid:{target}")
        if temporary.stat().st_size != expected_size:
            raise F4Error(f"repair_temporary_size_invalid:{target}")
        os.replace(temporary, target)
        replaced = True
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not replaced:
            temporary.unlink(missing_ok=True)


def _write_new_file(path: Path, payload: str, mode: int) -> None:
    if path.exists() or path.is_symlink():
        raise F4Error(f"install_target_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    installed = False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.chown(temporary, 0, 0)
        os.link(temporary, path, follow_symlinks=False)
        temporary.unlink()
        installed = True
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not installed:
            temporary.unlink(missing_ok=True)


def _openssl_public_from_cert(path: Path) -> str:
    return _run(("openssl", "x509", "-in", str(path), "-pubkey", "-noout"))


def _openssl_public_from_key(path: Path) -> str:
    return _run(("openssl", "pkey", "-in", str(path), "-pubout"))


def _validate_tls_material() -> None:
    expected = {
        CA_CERT: (0, 0, 0o644),
        SERVER_CERT: (0, 0, 0o644),
        SERVER_KEY: (1883, 1883, 0o600),
        CA_KEY: (0, 0, 0o600),
        SYSTEM_CA: (0, 0, 0o600),
    }
    for path, (uid, gid, mode) in expected.items():
        _regular_source(path)
        metadata = path.stat()
        if (
            metadata.st_uid != uid
            or metadata.st_gid != gid
            or stat.S_IMODE(metadata.st_mode) != mode
            or metadata.st_nlink != 1
        ):
            raise F4Error(f"tls_material_metadata_invalid:{path.name}")
    if _openssl_public_from_cert(CA_CERT) != _openssl_public_from_key(CA_KEY):
        raise F4Error("broker_ca_key_mismatch")
    if _openssl_public_from_cert(SERVER_CERT) != _openssl_public_from_key(SERVER_KEY):
        raise F4Error("broker_server_key_mismatch")
    _run(
        (
            "openssl",
            "verify",
            "-CAfile",
            str(CA_CERT),
            "-verify_hostname",
            SERVER_NAME,
            str(SERVER_CERT),
        )
    )


def _broker_env_payload() -> str:
    return (
        "N3WFC4_COMPOSE_FILE=/etc/n3wfc4/docker-compose.yml\n"
        "N3WFC4_COMPOSE_ENV_FILE=/etc/n3wfc4/docker-compose.env\n"
        "N3WFC4_COMPOSE_PROJECT_NAME=n3wfc4\n"
    )


def _certificate_env_payload() -> str:
    return (
        f"N3WFC4_CERT_SERVER_CERT_FILE={SERVER_CERT}\n"
        f"N3WFC4_CERT_SERVER_KEY_FILE={SERVER_KEY}\n"
        f"N3WFC4_CERT_CA_CERT_FILE={CA_CERT}\n"
        f"N3WFC4_CERT_CA_KEY_FILE={CA_KEY}\n"
        f"N3WFC4_CERT_SYSTEM_CA_FILE={SYSTEM_CA}\n"
        f"N3WFC4_CERT_SERVER_NAME={SERVER_NAME}\n"
        "N3WFC4_CERT_STATUS_FILE=/var/lib/n3wfc4-certificate-lifecycle/status.json\n"
        "N3WFC4_CERT_ALLOWED_ROOT_FC4=/etc/n3wfc4\n"
        "N3WFC4_CERT_ALLOWED_ROOT_BROKER_CA=/opt/greenhouse-secrets/broker-ca\n"
        "N3WFC4_CERT_ALLOWED_ROOT_SYSTEM=/var/lib/greenhouse-manager/identity\n"
    )


def _install_activation_material(
    package: dict[str, object],
) -> dict[str, object]:
    root = Path(str(package["root"]))
    files = package["files"]
    if not isinstance(files, dict):
        raise F4Error("package_files_invalid")
    _validate_tls_material()
    created: list[Path] = []
    status_root_created = False
    try:
        for relative, (target, mode) in INSTALL_MAP.items():
            binding = files.get(relative)
            if not isinstance(binding, dict):
                raise F4Error(f"package_file_binding_missing:{relative}")
            _atomic_install(
                root / relative,
                target,
                mode,
                expected_sha256=str(binding["sha256"]),
                expected_size=int(binding["size"]),
            )
            created.append(target)

        _atomic_install(LIVE_COMPOSE_SOURCE, COMPOSE_TARGET, 0o644)
        created.append(COMPOSE_TARGET)

        _write_new_file(BROKER_ENV, _broker_env_payload(), 0o600)
        created.append(BROKER_ENV)
        _write_new_file(CERT_ENV, _certificate_env_payload(), 0o600)
        created.append(CERT_ENV)

        if CERT_STATUS_ROOT.exists() or CERT_STATUS_ROOT.is_symlink():
            raise F4Error("certificate_status_root_exists")
        CERT_STATUS_ROOT.mkdir(mode=0o700)
        os.chown(CERT_STATUS_ROOT, 0, 0)
        os.chmod(CERT_STATUS_ROOT, 0o700)
        status_root_created = True

        _run(("systemctl", "daemon-reload"), timeout=60)
        for unit in (BROKER_UNIT, SERVICES_UNIT, CERT_SERVICE, CERT_TIMER):
            if _systemctl("is-active", unit) in {"active", "activating", "reloading"}:
                raise F4Error(f"installed_unit_active:{unit}")
            if _systemctl("is-enabled", unit) == "enabled":
                raise F4Error(f"installed_unit_enabled:{unit}")
        installed_files = {
            str(target): _file_binding(target)
            for target in created
        }
        return {
            "status": "PASS",
            "activation_material_installed": True,
            "installed_files": installed_files,
            "production_service_start": False,
            "persistence_enabled": False,
            "certificate_timer_enabled": False,
        }
    except OPERATION_ERRORS as original_error:
        cleanup_errors: list[str] = []
        for target in reversed(created):
            try:
                target.unlink(missing_ok=True)
            except OSError as cleanup_error:
                cleanup_errors.append(type(cleanup_error).__name__)
        if status_root_created:
            try:
                CERT_STATUS_ROOT.rmdir()
            except OSError as cleanup_error:
                cleanup_errors.append(type(cleanup_error).__name__)
        try:
            _run(("systemctl", "daemon-reload"), timeout=60)
        except OPERATION_ERRORS as cleanup_error:
            cleanup_errors.append(type(cleanup_error).__name__)
        if cleanup_errors:
            raise F4Error(
                "activation_install_failed_cleanup_unproven:"
                + ",".join(cleanup_errors)
            ) from original_error
        raise


def _prepare(
    package_root: Path,
    confirmation: str,
    authorization_id: str,
    package_manifest_sha256: str,
    package_source_head: str,
) -> dict[str, object]:
    if confirmation != PREPARE_CONFIRMATION:
        raise F4Error("prepare_confirmation_invalid")
    package = _validate_package(
        package_root,
        expected_manifest_sha256=package_manifest_sha256,
        expected_source_head=package_source_head,
    )
    with _exclusive_f4():
        audit = _factory_audit(require_claim_absent=True)
        _new_private_record(
            TRANSACTION_PATH,
            _transaction_document(audit, authorization_id, package),
        )
        try:
            fresh = _factory_audit(require_claim_absent=False)
            for key in (
                "release_id",
                "host_instance_id",
                "system_id",
                "system_id_sha256",
            ):
                if fresh.get(key) != audit.get(key):
                    raise F4Error(f"factory_audit_binding_changed:{key}")
            _new_private_record(
                FACTORY_ACCEPTED_PATH,
                _factory_document(fresh),
            )
            install = _install_activation_material(package)
            _advance_transaction(
                "PREPARED",
                activation_material_installed=True,
                installed_files=install["installed_files"],
                package_source_head=package["source_head"],
                package_manifest_sha256=package["manifest_sha256"],
                production_service_start=False,
                persistence_enabled=False,
            )
            return {
                "status": "PASS",
                "state": "FACTORY_ACCEPTED",
                "factory_accepted": True,
                "activation_material_installed": install[
                    "activation_material_installed"
                ],
                "authorization_id": authorization_id,
                "package_source_head": package["source_head"],
                "package_manifest_sha256": package["manifest_sha256"],
                "authorization_claimed": True,
                "authorization_consumed": True,
                "replay_allowed": False,
                "production_service_start": False,
                "persistence_enabled": False,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            try:
                _advance_transaction(
                    "STOPPED_PREPARE",
                    error_code=str(error)[:300],
                    production_service_start=False,
                    persistence_enabled=False,
                )
            except OPERATION_ERRORS as stop_record_error:
                raise F4Error(
                    "prepare_failed_stop_record_unproven:"
                    + type(stop_record_error).__name__
                ) from error
            raise


def _repair_prepared_control(
    package_root: Path,
    confirmation: str,
    repair_authorization_id: str,
    package_manifest_sha256: str,
    package_source_head: str,
) -> dict[str, object]:
    if confirmation != CONTROL_REPAIR_CONFIRMATION:
        raise F4Error("control_repair_confirmation_invalid")
    if (
        not repair_authorization_id.startswith("N3W_T1_F4_")
        or len(repair_authorization_id) > 200
        or not repair_authorization_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise F4Error("control_repair_authorization_id_invalid")
    package = _validate_package(
        package_root,
        expected_manifest_sha256=package_manifest_sha256,
        expected_source_head=package_source_head,
    )
    launcher_relative = "tools/n3w_t1_f4_activation_host.py"
    launcher_target, launcher_mode = INSTALL_MAP[launcher_relative]
    launcher_binding = package["files"].get(launcher_relative)
    if not isinstance(launcher_binding, dict):
        raise F4Error("control_repair_launcher_binding_missing")
    launcher_source = Path(str(package["root"])) / launcher_relative
    if not launcher_source.read_bytes().startswith(b"#!/usr/bin/python3\n"):
        raise F4Error("control_repair_launcher_shebang_invalid")

    with _exclusive_f4():
        verified = _provision_verify()
        _validate_factory_binding(verified)
        transaction = _validate_transaction_binding(verified)
        if (
            transaction.get("stage") != "PREPARED"
            or transaction.get("package_source_head")
            != CONTROL_REPAIR_DEFECT_SOURCE_HEAD
            or transaction.get("package_manifest_sha256")
            != CONTROL_REPAIR_DEFECT_MANIFEST_SHA256
            or transaction.get("control_repair_authorization_claimed") is True
        ):
            raise F4Error("control_repair_prestate_invalid")
        _verify_installed_material(transaction)
        current_installed = transaction.get("installed_files")
        if not isinstance(current_installed, dict):
            raise F4Error("control_repair_installed_files_invalid")
        current_launcher = current_installed.get(str(launcher_target))
        if (
            not isinstance(current_launcher, dict)
            or current_launcher.get("sha256")
            != CONTROL_REPAIR_DEFECT_LAUNCHER_SHA256
        ):
            raise F4Error("control_repair_defect_binding_invalid")

        for relative, (target, _mode) in INSTALL_MAP.items():
            if relative == launcher_relative:
                continue
            new_binding = package["files"].get(relative)
            installed_binding = current_installed.get(str(target))
            if (
                not isinstance(new_binding, dict)
                or not isinstance(installed_binding, dict)
                or new_binding.get("sha256") != installed_binding.get("sha256")
                or new_binding.get("size") != installed_binding.get("size")
            ):
                raise F4Error(f"control_repair_unexpected_package_delta:{relative}")

        runtime = _runtime_activity()
        if (
            runtime["production_service_start"] is not False
            or runtime["running_services"] not in ([], None)
            or _product_listener_ports() != []
        ):
            raise F4Error("control_repair_runtime_not_stopped")

        _advance_transaction(
            "CONTROL_REPAIR_CLAIMED",
            control_repair_authorization_id=repair_authorization_id,
            control_repair_authorization_claimed=True,
            control_repair_authorization_consumed=True,
            control_repair_replay_allowed=False,
            control_repair_from_source_head=CONTROL_REPAIR_DEFECT_SOURCE_HEAD,
            control_repair_from_manifest_sha256=(
                CONTROL_REPAIR_DEFECT_MANIFEST_SHA256
            ),
            control_repair_target_source_head=package["source_head"],
            control_repair_target_manifest_sha256=package["manifest_sha256"],
            production_service_start=False,
            persistence_enabled=False,
        )
        try:
            _atomic_replace_bound_file(
                launcher_source,
                launcher_target,
                launcher_mode,
                expected_current=current_launcher,
                expected_sha256=str(launcher_binding["sha256"]),
                expected_size=int(launcher_binding["size"]),
            )
            updated_files = dict(current_installed)
            updated_files[str(launcher_target)] = _file_binding(launcher_target)
            _advance_transaction(
                "PREPARED",
                installed_files=updated_files,
                package_source_head=package["source_head"],
                package_manifest_sha256=package["manifest_sha256"],
                control_repair_passed=True,
                control_repair_launcher_sha256=launcher_binding["sha256"],
                production_service_start=False,
                persistence_enabled=False,
            )
            repaired = _read_private_record(TRANSACTION_PATH)
            _verify_installed_material(repaired)
            return {
                "status": "PASS",
                "state": "PREPARED",
                "control_repair_passed": True,
                "control_repair_authorization_id": repair_authorization_id,
                "control_repair_authorization_claimed": True,
                "control_repair_authorization_consumed": True,
                "control_repair_replay_allowed": False,
                "package_source_head": package["source_head"],
                "package_manifest_sha256": package["manifest_sha256"],
                "production_service_start": False,
                "persistence_enabled": False,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            try:
                _advance_transaction(
                    "STOPPED_CONTROL_REPAIR",
                    control_repair_passed=False,
                    control_repair_error_code=str(error)[:300],
                    production_service_start=False,
                    persistence_enabled=False,
                )
            except OPERATION_ERRORS as stop_record_error:
                raise F4Error(
                    "control_repair_failed_stop_record_unproven:"
                    + type(stop_record_error).__name__
                ) from error
            raise


def _repair_prepared_activation_authority(
    package_root: Path,
    confirmation: str,
    repair_authorization_id: str,
    package_manifest_sha256: str,
    package_source_head: str,
) -> dict[str, object]:
    if confirmation != ACTIVATION_AUTHORITY_REPAIR_CONFIRMATION:
        raise F4Error("activation_authority_repair_confirmation_invalid")
    if (
        not repair_authorization_id.startswith("N3W_T1_F4_")
        or len(repair_authorization_id) > 200
        or not repair_authorization_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise F4Error("activation_authority_repair_authorization_id_invalid")
    package = _validate_package(
        package_root,
        expected_manifest_sha256=package_manifest_sha256,
        expected_source_head=package_source_head,
    )
    launcher_relative = "tools/n3w_t1_f4_activation_host.py"
    launcher_target, launcher_mode = INSTALL_MAP[launcher_relative]
    launcher_binding = package["files"].get(launcher_relative)
    if not isinstance(launcher_binding, dict):
        raise F4Error("activation_authority_repair_launcher_binding_missing")
    launcher_source = Path(str(package["root"])) / launcher_relative
    if not launcher_source.read_bytes().startswith(b"#!/usr/bin/python3\n"):
        raise F4Error("activation_authority_repair_launcher_shebang_invalid")

    with _exclusive_f4():
        verified = _provision_verify()
        _validate_factory_binding(verified)
        transaction = _validate_transaction_binding(verified)
        if (
            transaction.get("stage") != "PREPARED"
            or transaction.get("package_source_head")
            != ACTIVATION_AUTHORITY_REPAIR_FROM_SOURCE_HEAD
            or transaction.get("package_manifest_sha256")
            != ACTIVATION_AUTHORITY_REPAIR_FROM_MANIFEST_SHA256
            or transaction.get("control_repair_passed") is not True
            or transaction.get("activation_authorization_claimed") is True
            or transaction.get(
                "activation_authority_repair_authorization_claimed"
            )
            is True
        ):
            raise F4Error("activation_authority_repair_prestate_invalid")
        _verify_installed_material(transaction)
        current_installed = transaction.get("installed_files")
        if not isinstance(current_installed, dict):
            raise F4Error("activation_authority_repair_installed_files_invalid")
        current_launcher = current_installed.get(str(launcher_target))
        if (
            not isinstance(current_launcher, dict)
            or current_launcher.get("sha256")
            != ACTIVATION_AUTHORITY_REPAIR_FROM_LAUNCHER_SHA256
        ):
            raise F4Error("activation_authority_repair_source_binding_invalid")

        for relative, (target, _mode) in INSTALL_MAP.items():
            if relative == launcher_relative:
                continue
            new_binding = package["files"].get(relative)
            installed_binding = current_installed.get(str(target))
            if (
                not isinstance(new_binding, dict)
                or not isinstance(installed_binding, dict)
                or new_binding.get("sha256") != installed_binding.get("sha256")
                or new_binding.get("size") != installed_binding.get("size")
            ):
                raise F4Error(
                    f"activation_authority_repair_unexpected_delta:{relative}"
                )

        runtime = _runtime_activity()
        if (
            runtime["production_service_start"] is not False
            or runtime["running_services"] not in ([], None)
            or _product_listener_ports() != []
        ):
            raise F4Error("activation_authority_repair_runtime_not_stopped")

        _advance_transaction(
            "ACTIVATION_AUTHORITY_REPAIR_CLAIMED",
            activation_authority_repair_authorization_id=repair_authorization_id,
            activation_authority_repair_authorization_claimed=True,
            activation_authority_repair_authorization_consumed=True,
            activation_authority_repair_replay_allowed=False,
            activation_authority_repair_from_source_head=(
                ACTIVATION_AUTHORITY_REPAIR_FROM_SOURCE_HEAD
            ),
            activation_authority_repair_from_manifest_sha256=(
                ACTIVATION_AUTHORITY_REPAIR_FROM_MANIFEST_SHA256
            ),
            activation_authority_repair_target_source_head=package[
                "source_head"
            ],
            activation_authority_repair_target_manifest_sha256=package[
                "manifest_sha256"
            ],
            production_service_start=False,
            persistence_enabled=False,
        )
        try:
            _atomic_replace_bound_file(
                launcher_source,
                launcher_target,
                launcher_mode,
                expected_current=current_launcher,
                expected_sha256=str(launcher_binding["sha256"]),
                expected_size=int(launcher_binding["size"]),
            )
            updated_files = dict(current_installed)
            updated_files[str(launcher_target)] = _file_binding(launcher_target)
            _advance_transaction(
                "PREPARED",
                installed_files=updated_files,
                package_source_head=package["source_head"],
                package_manifest_sha256=package["manifest_sha256"],
                activation_authority_repair_passed=True,
                activation_authority_repair_launcher_sha256=launcher_binding[
                    "sha256"
                ],
                production_service_start=False,
                persistence_enabled=False,
            )
            repaired = _read_private_record(TRANSACTION_PATH)
            _verify_installed_material(repaired)
            return {
                "status": "PASS",
                "state": "PREPARED",
                "activation_authority_repair_passed": True,
                "activation_authority_repair_authorization_id": (
                    repair_authorization_id
                ),
                "activation_authority_repair_authorization_claimed": True,
                "activation_authority_repair_authorization_consumed": True,
                "activation_authority_repair_replay_allowed": False,
                "package_source_head": package["source_head"],
                "package_manifest_sha256": package["manifest_sha256"],
                "production_service_start": False,
                "persistence_enabled": False,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            try:
                _advance_transaction(
                    "STOPPED_ACTIVATION_AUTHORITY_REPAIR",
                    activation_authority_repair_passed=False,
                    activation_authority_repair_error_code=str(error)[:300],
                    production_service_start=False,
                    persistence_enabled=False,
                )
            except OPERATION_ERRORS as stop_record_error:
                raise F4Error(
                    "activation_authority_repair_failed_stop_record_unproven:"
                    + type(stop_record_error).__name__
                ) from error
            raise


def _repair_runtime_continuation_authority(
    package_root: Path,
    confirmation: str,
    repair_authorization_id: str,
    package_manifest_sha256: str,
    package_source_head: str,
) -> dict[str, object]:
    if confirmation != RUNTIME_CONTINUATION_AUTHORITY_REPAIR_CONFIRMATION:
        raise F4Error("runtime_continuation_authority_repair_confirmation_invalid")
    if (
        not repair_authorization_id.startswith("N3W_T1_F4_")
        or len(repair_authorization_id) > 200
        or not repair_authorization_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise F4Error(
            "runtime_continuation_authority_repair_authorization_id_invalid"
        )
    package = _validate_package(
        package_root,
        expected_manifest_sha256=package_manifest_sha256,
        expected_source_head=package_source_head,
    )
    launcher_relative = "tools/n3w_t1_f4_activation_host.py"
    launcher_target, launcher_mode = INSTALL_MAP[launcher_relative]
    launcher_binding = package["files"].get(launcher_relative)
    if not isinstance(launcher_binding, dict):
        raise F4Error(
            "runtime_continuation_authority_repair_launcher_binding_missing"
        )
    launcher_source = Path(str(package["root"])) / launcher_relative
    if not launcher_source.read_bytes().startswith(b"#!/usr/bin/python3\n"):
        raise F4Error(
            "runtime_continuation_authority_repair_launcher_shebang_invalid"
        )

    with _exclusive_f4():
        verified = _provision_verify()
        _validate_factory_binding(verified)
        transaction = _validate_transaction_binding(verified)
        if (
            transaction.get("stage") != "RUNTIME_STARTED"
            or transaction.get("runtime_started") is not True
            or transaction.get("runtime_acceptance_required") is not True
            or transaction.get("production_service_start") is not True
            or transaction.get("persistence_enabled") is not False
            or transaction.get("package_source_head")
            != RUNTIME_CONTINUATION_AUTHORITY_REPAIR_FROM_SOURCE_HEAD
            or transaction.get("package_manifest_sha256")
            != RUNTIME_CONTINUATION_AUTHORITY_REPAIR_FROM_MANIFEST_SHA256
            or transaction.get(
                "runtime_continuation_authority_repair_authorization_claimed"
            )
            is True
        ):
            raise F4Error(
                "runtime_continuation_authority_repair_prestate_invalid"
            )

        _verify_installed_material(transaction)
        current_installed = transaction.get("installed_files")
        if not isinstance(current_installed, dict):
            raise F4Error(
                "runtime_continuation_authority_repair_installed_files_invalid"
            )
        current_launcher = current_installed.get(str(launcher_target))
        if (
            not isinstance(current_launcher, dict)
            or current_launcher.get("sha256")
            != RUNTIME_CONTINUATION_AUTHORITY_REPAIR_FROM_LAUNCHER_SHA256
        ):
            raise F4Error(
                "runtime_continuation_authority_repair_source_binding_invalid"
            )

        for relative, (target, _mode) in INSTALL_MAP.items():
            if relative == launcher_relative:
                continue
            new_binding = package["files"].get(relative)
            installed_binding = current_installed.get(str(target))
            if (
                not isinstance(new_binding, dict)
                or not isinstance(installed_binding, dict)
                or new_binding.get("sha256") != installed_binding.get("sha256")
                or new_binding.get("size") != installed_binding.get("size")
            ):
                raise F4Error(
                    "runtime_continuation_authority_repair_unexpected_delta:"
                    + relative
                )

        _validate_successor_authorization(
            transaction,
            repair_authorization_id,
            claimed_field=(
                "runtime_continuation_authority_repair_authorization_claimed"
            ),
            invalid_code=(
                "runtime_continuation_authority_repair_authorization_id_invalid"
            ),
            replay_code=(
                "runtime_continuation_authority_repair_authorization_replay_forbidden"
            ),
        )

        runtime_before = _runtime_activity()
        if (
            runtime_before["production_service_start"] is not True
            or set(runtime_before["running_services"] or [])
            != EXPECTED_RUNTIME_SERVICES
        ):
            raise F4Error(
                "runtime_continuation_authority_repair_runtime_not_active"
            )
        before_snapshot = _runtime_container_snapshot()

        _advance_transaction(
            "RUNTIME_STARTED",
            runtime_continuation_authority_repair_authorization_id=(
                repair_authorization_id
            ),
            runtime_continuation_authority_repair_authorization_claimed=True,
            runtime_continuation_authority_repair_authorization_consumed=True,
            runtime_continuation_authority_repair_replay_allowed=False,
            runtime_continuation_authority_repair_from_source_head=(
                RUNTIME_CONTINUATION_AUTHORITY_REPAIR_FROM_SOURCE_HEAD
            ),
            runtime_continuation_authority_repair_from_manifest_sha256=(
                RUNTIME_CONTINUATION_AUTHORITY_REPAIR_FROM_MANIFEST_SHA256
            ),
            runtime_continuation_authority_repair_target_source_head=(
                package["source_head"]
            ),
            runtime_continuation_authority_repair_target_manifest_sha256=(
                package["manifest_sha256"]
            ),
            production_service_start=True,
            persistence_enabled=False,
        )
        try:
            _atomic_replace_bound_file(
                launcher_source,
                launcher_target,
                launcher_mode,
                expected_current=current_launcher,
                expected_sha256=str(launcher_binding["sha256"]),
                expected_size=int(launcher_binding["size"]),
            )
            updated_files = dict(current_installed)
            updated_files[str(launcher_target)] = _file_binding(launcher_target)
            runtime_after = _runtime_activity()
            if (
                runtime_after["production_service_start"] is not True
                or set(runtime_after["running_services"] or [])
                != EXPECTED_RUNTIME_SERVICES
                or _runtime_container_snapshot() != before_snapshot
            ):
                raise F4Error(
                    "runtime_continuation_authority_repair_runtime_changed"
                )
            _advance_transaction(
                "RUNTIME_STARTED",
                installed_files=updated_files,
                package_source_head=package["source_head"],
                package_manifest_sha256=package["manifest_sha256"],
                runtime_continuation_authority_repair_passed=True,
                runtime_started=True,
                runtime_acceptance_required=True,
                production_service_start=True,
                persistence_enabled=False,
            )
            repaired = _read_private_record(TRANSACTION_PATH)
            _verify_installed_material(repaired)
            return {
                "status": "PASS",
                "state": "RUNTIME_STARTED",
                "runtime_continuation_authority_repair_passed": True,
                "runtime_continuation_authority_repair_authorization_id": (
                    repair_authorization_id
                ),
                "runtime_continuation_authority_repair_authorization_claimed": True,
                "runtime_continuation_authority_repair_authorization_consumed": True,
                "runtime_continuation_authority_repair_replay_allowed": False,
                "package_source_head": package["source_head"],
                "package_manifest_sha256": package["manifest_sha256"],
                "production_service_start": True,
                "persistence_enabled": False,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            try:
                _downstream_fail_closed(
                    "RUNTIME_CONTINUATION_CONTROL_REPAIR",
                    error,
                )
            except OPERATION_ERRORS as rollback_error:
                raise F4Error(
                    "runtime_continuation_authority_repair_failed_"
                    "rollback_unproven:"
                    + type(rollback_error).__name__
                ) from error
            raise


def _runtime_acceptance_recovery_entrypoint(
    launcher_source: Path,
    launcher_binding: dict[str, object],
) -> None:
    executing = Path(os.path.abspath(__file__))
    if (
        executing.is_symlink()
        or not executing.is_file()
        or executing != launcher_source
        or executing.stat().st_size != launcher_binding.get("size")
        or _sha256_file(executing) != launcher_binding.get("sha256")
    ):
        raise F4Error("runtime_acceptance_recovery_entrypoint_invalid")


def _runtime_acceptance_recovery_stopped_prestate() -> None:
    runtime = _runtime_activity()
    if (
        runtime["production_service_start"] is not False
        or runtime["runtime_service_probe"] != "PASS"
        or runtime["running_services"] != []
        or runtime["broker_active_state"] not in {"inactive", "failed"}
        or runtime["services_active_state"] not in {"inactive", "failed"}
        or _product_listener_ports() != []
        or _systemctl("is-enabled", BROKER_UNIT) != "disabled"
        or _systemctl("is-enabled", SERVICES_UNIT) != "disabled"
        or _systemctl("is-enabled", CERT_TIMER) != "disabled"
        or _systemctl("is-active", CERT_TIMER) != "inactive"
        or _systemctl("is-active", CERT_SERVICE) != "inactive"
        or RUNTIME_ACCEPTANCE_PATH.exists()
        or RUNTIME_ACCEPTANCE_PATH.is_symlink()
    ):
        raise F4Error("runtime_acceptance_recovery_runtime_not_stopped")


def _repair_stopped_runtime_acceptance(
    package_root: Path,
    confirmation: str,
    repair_authorization_id: str,
    package_manifest_sha256: str,
    package_source_head: str,
) -> dict[str, object]:
    if confirmation != RUNTIME_ACCEPTANCE_RECOVERY_CONFIRMATION:
        raise F4Error("runtime_acceptance_recovery_confirmation_invalid")
    package = _validate_package(
        package_root,
        expected_manifest_sha256=package_manifest_sha256,
        expected_source_head=package_source_head,
    )
    launcher_relative = "tools/n3w_t1_f4_activation_host.py"
    launcher_target, launcher_mode = INSTALL_MAP[launcher_relative]
    launcher_binding = package["files"].get(launcher_relative)
    if not isinstance(launcher_binding, dict):
        raise F4Error("runtime_acceptance_recovery_launcher_binding_missing")
    launcher_source = Path(str(package["root"])) / launcher_relative
    if not launcher_source.read_bytes().startswith(b"#!/usr/bin/python3\n"):
        raise F4Error("runtime_acceptance_recovery_launcher_shebang_invalid")
    if (
        package["source_head"] == RUNTIME_ACCEPTANCE_RECOVERY_FROM_SOURCE_HEAD
        or package["manifest_sha256"]
        == RUNTIME_ACCEPTANCE_RECOVERY_FROM_MANIFEST_SHA256
        or launcher_binding.get("sha256")
        == RUNTIME_ACCEPTANCE_RECOVERY_FROM_LAUNCHER_SHA256
    ):
        raise F4Error("runtime_acceptance_recovery_successor_not_distinct")
    _runtime_acceptance_recovery_entrypoint(
        launcher_source,
        launcher_binding,
    )

    with _exclusive_f4():
        verified = _provision_verify()
        _validate_factory_binding(verified)
        transaction = _validate_transaction_binding(verified)
        if (
            transaction.get("stage") != "STOPPED_RUNTIME_ACCEPTANCE"
            or transaction.get("error_code")
            != "manager_mqtt_socket_count_invalid"
            or transaction.get("rollback_proven") is not True
            or transaction.get("rollback_error_count") != 0
            or transaction.get("production_service_start") is not False
            or transaction.get("persistence_enabled") is not False
            or transaction.get("certificate_timer_enabled") is not False
            or transaction.get("product_listener_ports") != []
            or transaction.get("runtime_acceptance_authorization_claimed")
            is not True
            or transaction.get("runtime_acceptance_authorization_consumed")
            is not True
            or transaction.get("runtime_acceptance_authorization_replay_allowed")
            is not False
            or transaction.get("runtime_acceptance_passed") is True
            or transaction.get("package_source_head")
            != RUNTIME_ACCEPTANCE_RECOVERY_FROM_SOURCE_HEAD
            or transaction.get("package_manifest_sha256")
            != RUNTIME_ACCEPTANCE_RECOVERY_FROM_MANIFEST_SHA256
            or transaction.get(
                "runtime_acceptance_recovery_authorization_claimed"
            )
            is True
        ):
            raise F4Error("runtime_acceptance_recovery_prestate_invalid")

        failed_acceptance_authorization = transaction.get(
            "runtime_acceptance_authorization_id"
        )
        if not isinstance(failed_acceptance_authorization, str):
            raise F4Error(
                "runtime_acceptance_recovery_failed_authorization_missing"
            )

        _verify_installed_material(transaction)
        current_installed = transaction.get("installed_files")
        if not isinstance(current_installed, dict):
            raise F4Error(
                "runtime_acceptance_recovery_installed_files_invalid"
            )
        current_launcher = current_installed.get(str(launcher_target))
        if (
            not isinstance(current_launcher, dict)
            or current_launcher.get("sha256")
            != RUNTIME_ACCEPTANCE_RECOVERY_FROM_LAUNCHER_SHA256
        ):
            raise F4Error(
                "runtime_acceptance_recovery_source_binding_invalid"
            )

        for relative, (target, _mode) in INSTALL_MAP.items():
            if relative == launcher_relative:
                continue
            new_binding = package["files"].get(relative)
            installed_binding = current_installed.get(str(target))
            if (
                not isinstance(new_binding, dict)
                or not isinstance(installed_binding, dict)
                or new_binding.get("sha256") != installed_binding.get("sha256")
                or new_binding.get("size") != installed_binding.get("size")
            ):
                raise F4Error(
                    "runtime_acceptance_recovery_unexpected_delta:"
                    + relative
                )

        _runtime_acceptance_recovery_stopped_prestate()
        _validate_successor_authorization(
            transaction,
            repair_authorization_id,
            claimed_field=(
                "runtime_acceptance_recovery_authorization_claimed"
            ),
            invalid_code=(
                "runtime_acceptance_recovery_authorization_id_invalid"
            ),
            replay_code=(
                "runtime_acceptance_recovery_authorization_replay_forbidden"
            ),
        )

        _advance_transaction(
            "STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_CLAIMED",
            runtime_acceptance_recovery_authorization_id=(
                repair_authorization_id
            ),
            runtime_acceptance_recovery_authorization_claimed=True,
            runtime_acceptance_recovery_authorization_consumed=True,
            runtime_acceptance_recovery_authorization_replay_allowed=False,
            runtime_acceptance_recovery_from_source_head=(
                RUNTIME_ACCEPTANCE_RECOVERY_FROM_SOURCE_HEAD
            ),
            runtime_acceptance_recovery_from_manifest_sha256=(
                RUNTIME_ACCEPTANCE_RECOVERY_FROM_MANIFEST_SHA256
            ),
            runtime_acceptance_recovery_target_source_head=(
                package["source_head"]
            ),
            runtime_acceptance_recovery_target_manifest_sha256=(
                package["manifest_sha256"]
            ),
            runtime_acceptance_last_failure_stage=(
                "STOPPED_RUNTIME_ACCEPTANCE"
            ),
            runtime_acceptance_last_failure_error_code=(
                "manager_mqtt_socket_count_invalid"
            ),
            runtime_acceptance_last_failure_authorization_id=(
                failed_acceptance_authorization
            ),
            runtime_acceptance_last_failure_source_head=(
                RUNTIME_ACCEPTANCE_RECOVERY_FROM_SOURCE_HEAD
            ),
            runtime_acceptance_last_failure_manifest_sha256=(
                RUNTIME_ACCEPTANCE_RECOVERY_FROM_MANIFEST_SHA256
            ),
            runtime_acceptance_last_failure_rollback_proven=True,
            runtime_acceptance_last_failure_rollback_error_count=0,
            activation_retry_eligible=False,
            runtime_acceptance_retry_eligible=False,
            production_service_start=False,
            persistence_enabled=False,
            certificate_timer_enabled=False,
        )

        try:
            _atomic_replace_bound_file(
                launcher_source,
                launcher_target,
                launcher_mode,
                expected_current=current_launcher,
                expected_sha256=str(launcher_binding["sha256"]),
                expected_size=int(launcher_binding["size"]),
            )
            updated_files = dict(current_installed)
            updated_files[str(launcher_target)] = _file_binding(
                launcher_target
            )
            _advance_transaction(
                "STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_CLAIMED",
                installed_files=updated_files,
                package_source_head=package["source_head"],
                package_manifest_sha256=package["manifest_sha256"],
                runtime_acceptance_recovery_launcher_replaced=True,
                production_service_start=False,
                persistence_enabled=False,
                certificate_timer_enabled=False,
            )
            _runtime_acceptance_recovery_stopped_prestate()
            _advance_transaction(
                "PREPARED",
                installed_files=updated_files,
                package_source_head=package["source_head"],
                package_manifest_sha256=package["manifest_sha256"],
                runtime_acceptance_recovery_passed=True,
                activation_retry_eligible=True,
                runtime_acceptance_retry_eligible=True,
                broker_ready=False,
                runtime_started=False,
                runtime_acceptance_required=True,
                runtime_acceptance_passed=False,
                runtime_acceptance_report_sha256=None,
                homeassistant_mqtt_entry_id_sha256=None,
                error_code=None,
                rollback_proven=None,
                rollback_error_count=None,
                product_listener_ports=[],
                production_service_start=False,
                persistence_enabled=False,
                certificate_timer_enabled=False,
            )
            repaired = _read_private_record(TRANSACTION_PATH)
            _verify_installed_material(repaired)
            _runtime_acceptance_recovery_stopped_prestate()
            return {
                "status": "PASS",
                "state": "PREPARED",
                "runtime_acceptance_recovery_passed": True,
                "runtime_acceptance_recovery_authorization_id": (
                    repair_authorization_id
                ),
                "runtime_acceptance_recovery_authorization_claimed": True,
                "runtime_acceptance_recovery_authorization_consumed": True,
                "runtime_acceptance_recovery_authorization_replay_allowed": False,
                "failed_runtime_acceptance_authorization_id": (
                    failed_acceptance_authorization
                ),
                "failed_runtime_acceptance_authorization_preserved": True,
                "activation_retry_eligible": True,
                "runtime_acceptance_retry_eligible": True,
                "package_source_head": package["source_head"],
                "package_manifest_sha256": package["manifest_sha256"],
                "production_service_start": False,
                "persistence_enabled": False,
                "certificate_timer_enabled": False,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            launcher_state_proven = False
            try:
                current = _read_private_record(TRANSACTION_PATH)
                expected_new_launcher = {
                    "sha256": str(launcher_binding["sha256"]),
                    "size": int(launcher_binding["size"]),
                    "mode": launcher_mode,
                    "uid": 0,
                    "gid": 0,
                }
                try:
                    observed_launcher = _file_binding(launcher_target)
                except OPERATION_ERRORS:
                    observed_launcher = None

                if observed_launcher == expected_new_launcher:
                    reconciled_files = dict(current_installed)
                    reconciled_files[str(launcher_target)] = observed_launcher
                    _advance_transaction(
                        str(current["stage"]),
                        installed_files=reconciled_files,
                        package_source_head=package["source_head"],
                        package_manifest_sha256=package["manifest_sha256"],
                        runtime_acceptance_recovery_launcher_replaced=True,
                        runtime_acceptance_recovery_launcher_state_unproven=False,
                    )
                    launcher_state_proven = True
                elif observed_launcher == current_launcher:
                    _advance_transaction(
                        str(current["stage"]),
                        runtime_acceptance_recovery_launcher_replaced=False,
                        runtime_acceptance_recovery_launcher_state_unproven=False,
                    )
                    launcher_state_proven = True
                else:
                    _advance_transaction(
                        str(current["stage"]),
                        runtime_acceptance_recovery_launcher_state_unproven=True,
                    )

                _downstream_fail_closed(
                    "RUNTIME_ACCEPTANCE_RECOVERY",
                    error,
                )
                stopped = _read_private_record(TRANSACTION_PATH)
                stop_stage = str(stopped["stage"])
                rollback_proven = (
                    stopped.get("rollback_proven") is True
                    and launcher_state_proven
                )
                if not rollback_proven:
                    stop_stage = (
                        "STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_"
                        "ROLLBACK_UNPROVEN"
                    )
                _advance_transaction(
                    stop_stage,
                    runtime_acceptance_recovery_passed=False,
                    runtime_acceptance_recovery_error_code=str(error)[:300],
                    activation_retry_eligible=False,
                    runtime_acceptance_retry_eligible=False,
                    production_service_start=False,
                    persistence_enabled=False,
                    certificate_timer_enabled=False,
                    rollback_proven=rollback_proven,
                )
            except OPERATION_ERRORS as rollback_error:
                try:
                    _advance_transaction(
                        "STOPPED_RUNTIME_ACCEPTANCE_RECOVERY_"
                        "ROLLBACK_UNPROVEN",
                        runtime_acceptance_recovery_passed=False,
                        runtime_acceptance_recovery_error_code=str(error)[:300],
                        runtime_acceptance_recovery_launcher_state_unproven=True,
                        activation_retry_eligible=False,
                        runtime_acceptance_retry_eligible=False,
                        production_service_start=False,
                        persistence_enabled=False,
                        certificate_timer_enabled=False,
                        rollback_proven=False,
                    )
                except OPERATION_ERRORS:
                    pass
                raise F4Error(
                    "runtime_acceptance_recovery_failed_"
                    "rollback_unproven:"
                    + type(rollback_error).__name__
                ) from error
            raise


def _repair_stopped_runtime_start(
    package_root: Path,
    confirmation: str,
    repair_authorization_id: str,
    package_manifest_sha256: str,
    package_source_head: str,
) -> dict[str, object]:
    if confirmation != RUNTIME_START_REPAIR_CONFIRMATION:
        raise F4Error("runtime_start_repair_confirmation_invalid")
    if (
        not repair_authorization_id.startswith("N3W_T1_F4_")
        or len(repair_authorization_id) > 200
        or not repair_authorization_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise F4Error("runtime_start_repair_authorization_id_invalid")
    package = _validate_package(
        package_root,
        expected_manifest_sha256=package_manifest_sha256,
        expected_source_head=package_source_head,
    )
    launcher_relative = "tools/n3w_t1_f4_activation_host.py"
    launcher_target, launcher_mode = INSTALL_MAP[launcher_relative]
    launcher_binding = package["files"].get(launcher_relative)
    if not isinstance(launcher_binding, dict):
        raise F4Error("runtime_start_repair_launcher_binding_missing")
    launcher_source = Path(str(package["root"])) / launcher_relative
    if not launcher_source.read_bytes().startswith(b"#!/usr/bin/python3\n"):
        raise F4Error("runtime_start_repair_launcher_shebang_invalid")

    with _exclusive_f4():
        verified = _provision_verify()
        _validate_factory_binding(verified)
        transaction = _validate_transaction_binding(verified)
        if (
            transaction.get("stage") != "STOPPED_RUNTIME"
            or transaction.get("error_code") != "runtime_service_set_invalid"
            or transaction.get("rollback_proven") is not True
            or transaction.get("rollback_error_count") != 0
            or transaction.get("production_service_start") is not False
            or transaction.get("activation_authorization_claimed") is not True
            or transaction.get("activation_authorization_consumed") is not True
            or transaction.get("activation_authorization_replay_allowed")
            is not False
            or transaction.get("package_source_head")
            != RUNTIME_START_REPAIR_FROM_SOURCE_HEAD
            or transaction.get("package_manifest_sha256")
            != RUNTIME_START_REPAIR_FROM_MANIFEST_SHA256
            or transaction.get("runtime_start_repair_authorization_claimed")
            is True
        ):
            raise F4Error("runtime_start_repair_prestate_invalid")

        _verify_installed_material(transaction)
        current_installed = transaction.get("installed_files")
        if not isinstance(current_installed, dict):
            raise F4Error("runtime_start_repair_installed_files_invalid")
        current_launcher = current_installed.get(str(launcher_target))
        if (
            not isinstance(current_launcher, dict)
            or current_launcher.get("sha256")
            != RUNTIME_START_REPAIR_FROM_LAUNCHER_SHA256
        ):
            raise F4Error("runtime_start_repair_source_binding_invalid")

        for relative, (target, _mode) in INSTALL_MAP.items():
            if relative == launcher_relative:
                continue
            new_binding = package["files"].get(relative)
            installed_binding = current_installed.get(str(target))
            if (
                not isinstance(new_binding, dict)
                or not isinstance(installed_binding, dict)
                or new_binding.get("sha256") != installed_binding.get("sha256")
                or new_binding.get("size") != installed_binding.get("size")
            ):
                raise F4Error(
                    f"runtime_start_repair_unexpected_delta:{relative}"
                )

        runtime = _runtime_activity()
        if (
            runtime["production_service_start"] is not False
            or runtime["running_services"] not in ([], None)
            or _product_listener_ports() != []
        ):
            raise F4Error("runtime_start_repair_runtime_not_stopped")

        failed_authorization = transaction.get("activation_authorization_id")
        if not isinstance(failed_authorization, str):
            raise F4Error("runtime_start_repair_failed_authorization_missing")
        history_raw = transaction.get("activation_authorization_history", [])
        if not isinstance(history_raw, list) or not all(
            isinstance(value, str) for value in history_raw
        ):
            raise F4Error("activation_authorization_history_invalid")
        history = list(dict.fromkeys(history_raw + [failed_authorization]))

        _advance_transaction(
            "RUNTIME_START_REPAIR_CLAIMED",
            runtime_start_repair_authorization_id=repair_authorization_id,
            runtime_start_repair_authorization_claimed=True,
            runtime_start_repair_authorization_consumed=True,
            runtime_start_repair_replay_allowed=False,
            runtime_start_repair_from_source_head=(
                RUNTIME_START_REPAIR_FROM_SOURCE_HEAD
            ),
            runtime_start_repair_from_manifest_sha256=(
                RUNTIME_START_REPAIR_FROM_MANIFEST_SHA256
            ),
            runtime_start_repair_target_source_head=package["source_head"],
            runtime_start_repair_target_manifest_sha256=package[
                "manifest_sha256"
            ],
            activation_authorization_history=history,
            activation_retry_eligible=False,
            production_service_start=False,
            persistence_enabled=False,
        )
        try:
            _atomic_replace_bound_file(
                launcher_source,
                launcher_target,
                launcher_mode,
                expected_current=current_launcher,
                expected_sha256=str(launcher_binding["sha256"]),
                expected_size=int(launcher_binding["size"]),
            )
            updated_files = dict(current_installed)
            updated_files[str(launcher_target)] = _file_binding(launcher_target)
            _advance_transaction(
                "PREPARED",
                installed_files=updated_files,
                package_source_head=package["source_head"],
                package_manifest_sha256=package["manifest_sha256"],
                runtime_start_race_repair_passed=True,
                activation_retry_eligible=True,
                production_service_start=False,
                persistence_enabled=False,
            )
            repaired = _read_private_record(TRANSACTION_PATH)
            _verify_installed_material(repaired)
            return {
                "status": "PASS",
                "state": "PREPARED",
                "runtime_start_race_repair_passed": True,
                "runtime_start_repair_authorization_id": repair_authorization_id,
                "runtime_start_repair_authorization_claimed": True,
                "runtime_start_repair_authorization_consumed": True,
                "runtime_start_repair_replay_allowed": False,
                "failed_activation_authorization_id": failed_authorization,
                "failed_activation_authorization_preserved": True,
                "activation_retry_eligible": True,
                "package_source_head": package["source_head"],
                "package_manifest_sha256": package["manifest_sha256"],
                "production_service_start": False,
                "persistence_enabled": False,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            try:
                _advance_transaction(
                    "STOPPED_RUNTIME_START_REPAIR",
                    runtime_start_race_repair_passed=False,
                    runtime_start_repair_error_code=str(error)[:300],
                    activation_retry_eligible=False,
                    production_service_start=False,
                    persistence_enabled=False,
                )
            except OPERATION_ERRORS as stop_record_error:
                raise F4Error(
                    "runtime_start_repair_failed_stop_record_unproven:"
                    + type(stop_record_error).__name__
                ) from error
            raise


def _running_services() -> frozenset[str]:
    output = _run(
        (
            "docker",
            "compose",
            "--project-name",
            "n3wfc4",
            "--env-file",
            "/etc/n3wfc4/docker-compose.env",
            "-f",
            "/etc/n3wfc4/docker-compose.yml",
            "--profile",
            "application",
            "ps",
            "--status",
            "running",
            "--services",
        ),
        timeout=60,
    )
    return frozenset(line.strip() for line in output.splitlines() if line.strip())


def _wait_for_runtime_service_set(
    *,
    timeout_seconds: float = RUNTIME_SERVICE_SET_TIMEOUT_SECONDS,
    poll_seconds: float = RUNTIME_SERVICE_SET_POLL_SECONDS,
) -> frozenset[str]:
    deadline = time.monotonic() + timeout_seconds
    observed = frozenset()
    while True:
        unit_state = _systemctl("is-active", SERVICES_UNIT)
        if unit_state not in {"active", "activating"}:
            raise F4Error(
                f"application_services_not_active_during_start:{unit_state}"
            )
        observed = _running_services()
        unexpected = observed - EXPECTED_RUNTIME_SERVICES
        if unexpected:
            raise F4Error(
                "runtime_service_set_unexpected:"
                + ",".join(sorted(unexpected))
            )
        if observed == EXPECTED_RUNTIME_SERVICES:
            return observed
        if time.monotonic() >= deadline:
            raise F4Error(
                "runtime_service_set_timeout:"
                + ",".join(sorted(observed))
            )
        time.sleep(poll_seconds)


def _all_prior_authorization_ids(
    transaction: dict[str, object],
) -> frozenset[str]:
    values: set[str] = set()
    for key in (
        "authorization_id",
        "control_repair_authorization_id",
        "activation_authority_repair_authorization_id",
        "runtime_start_repair_authorization_id",
        "runtime_continuation_authority_repair_authorization_id",
        "runtime_acceptance_recovery_authorization_id",
        "activation_authorization_id",
        "runtime_acceptance_authorization_id",
        "persistence_authorization_id",
        "certificate_audit_authorization_id",
        "certificate_timer_authorization_id",
    ):
        value = transaction.get(key)
        if isinstance(value, str):
            values.add(value)
    for history_field, error_code in (
        (
            "activation_authorization_history",
            "activation_authorization_history_invalid",
        ),
        (
            "runtime_acceptance_authorization_history",
            "runtime_acceptance_authorization_history_invalid",
        ),
    ):
        history = transaction.get(history_field, [])
        if not isinstance(history, list) or not all(
            isinstance(value, str) for value in history
        ):
            raise F4Error(error_code)
        values.update(history)
    return frozenset(values)


def _validate_successor_authorization(
    transaction: dict[str, object],
    authorization_id: str,
    *,
    claimed_field: str,
    invalid_code: str,
    replay_code: str,
) -> None:
    if (
        not authorization_id.startswith("N3W_T1_F4_")
        or len(authorization_id) > 200
        or not authorization_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise F4Error(invalid_code)
    if authorization_id in _all_prior_authorization_ids(transaction):
        raise F4Error("continuation_authorization_not_distinct")
    if transaction.get(claimed_field) is True:
        raise F4Error(replay_code)


def _activation_prior_authorization_ids(
    transaction: dict[str, object],
) -> frozenset[str]:
    return _all_prior_authorization_ids(transaction)


def _activate(confirmation: str, authorization_id: str) -> dict[str, object]:
    if confirmation != ACTIVATE_CONFIRMATION:
        raise F4Error("activate_confirmation_invalid")
    if (
        not authorization_id.startswith("N3W_T1_F4_")
        or len(authorization_id) > 200
        or not authorization_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise F4Error("activation_authorization_id_invalid")
    with _exclusive_f4():
        eligible = _activation_eligibility("inspect")
        if eligible.get("transaction_stage") != "PREPARED":
            raise F4Error("activation_replay_forbidden")
        transaction = _read_private_record(TRANSACTION_PATH)
        prior_authorizations = _activation_prior_authorization_ids(
            transaction
        )
        if authorization_id in prior_authorizations:
            raise F4Error("activation_authorization_not_distinct")
        prior_activation_claimed = (
            transaction.get("activation_authorization_claimed") is True
        )
        retry_eligible = transaction.get("activation_retry_eligible") is True
        if prior_activation_claimed and not retry_eligible:
            raise F4Error("activation_authorization_replay_forbidden")

        history_raw = transaction.get("activation_authorization_history", [])
        if not isinstance(history_raw, list) or not all(
            isinstance(value, str) for value in history_raw
        ):
            raise F4Error("activation_authorization_history_invalid")
        history = list(dict.fromkeys(history_raw))
        previous_activation = transaction.get("activation_authorization_id")
        if (
            prior_activation_claimed
            and isinstance(previous_activation, str)
            and previous_activation not in history
        ):
            history.append(previous_activation)

        _advance_transaction(
            "ACTIVATION_CLAIMED",
            activation_authorization_history=history,
            activation_authorization_id=authorization_id,
            activation_authorization_claimed=True,
            activation_authorization_consumed=True,
            activation_authorization_replay_allowed=False,
            activation_retry_eligible=False,
            production_service_start=False,
            persistence_enabled=False,
        )

        broker_attempted = False
        services_attempted = False
        try:
            _run(("systemctl", "start", GUARD_UNIT), timeout=60)
            if _systemctl("is-active", GUARD_UNIT) != "active":
                raise F4Error("ingress_guard_not_active")

            _advance_transaction(
                "BROKER_STARTING",
                production_service_start=False,
                persistence_enabled=False,
            )
            broker_attempted = True
            _run(("systemctl", "start", BROKER_UNIT), timeout=180)
            _run(
                (
                    "/usr/local/sbin/n3w-t1-broker-authenticated-readiness",
                    "--metadata-file",
                    "/opt/greenhouse-secrets/mqtt/homeassistant/mqtt-bootstrap.json",
                    "--password-file",
                    "/opt/greenhouse-secrets/mqtt/homeassistant/password",
                    "--timeout-seconds",
                    "120",
                ),
                timeout=150,
            )
            _advance_transaction(
                "BROKER_READY",
                broker_ready=True,
                production_service_start=True,
                persistence_enabled=False,
            )

            _advance_transaction(
                "SERVICES_STARTING",
                broker_ready=True,
                production_service_start=True,
                persistence_enabled=False,
            )
            services_attempted = True
            _run(("systemctl", "start", SERVICES_UNIT), timeout=240)
            if _systemctl("is-active", SERVICES_UNIT) != "active":
                raise F4Error("application_services_not_active")
            running = _wait_for_runtime_service_set()
            _advance_transaction(
                "RUNTIME_STARTED",
                broker_ready=True,
                runtime_started=True,
                production_service_start=True,
                persistence_enabled=False,
                runtime_acceptance_required=True,
            )
            return {
                "status": "PASS",
                "state": "RUNTIME_STARTED",
                "authorization_id": authorization_id,
                "broker_ready": True,
                "runtime_services": sorted(running),
                "runtime_acceptance_required": True,
                "production_service_start": True,
                "persistence_enabled": False,
                "certificate_timer_enabled": False,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            rollback_errors: list[str] = []
            if services_attempted:
                try:
                    _run(("systemctl", "stop", SERVICES_UNIT), timeout=120)
                except OPERATION_ERRORS as rollback_error:
                    rollback_errors.append(type(rollback_error).__name__)
            if broker_attempted:
                try:
                    _run(("systemctl", "stop", BROKER_UNIT), timeout=120)
                except OPERATION_ERRORS as rollback_error:
                    rollback_errors.append(type(rollback_error).__name__)
            runtime = _runtime_activity()
            rollback_proven = (
                runtime["production_service_start"] is False
                and not rollback_errors
            )
            stop_stage = (
                "STOPPED_RUNTIME"
                if rollback_proven
                else "STOPPED_RUNTIME_ROLLBACK_UNPROVEN"
            )
            try:
                _advance_transaction(
                    stop_stage,
                    error_code=str(error)[:300],
                    production_service_start=runtime[
                        "production_service_start"
                    ],
                    persistence_enabled=False,
                    rollback_proven=rollback_proven,
                    rollback_error_count=len(rollback_errors),
                )
            except OPERATION_ERRORS as stop_record_error:
                raise F4Error(
                    "runtime_failed_stop_record_unproven:"
                    + type(stop_record_error).__name__
                ) from error
            raise



def _compose_service_inspect(service: str) -> dict[str, object]:
    output = _run(
        (
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={BROKER_PROJECT}",
            "--filter",
            f"label=com.docker.compose.service={service}",
            "--format",
            "{{.ID}}",
        ),
        timeout=30,
    )
    identifiers = tuple(
        line.strip() for line in output.splitlines() if line.strip()
    )
    if len(identifiers) != 1:
        raise F4Error(f"runtime_service_not_unique:{service}")
    try:
        documents = json.loads(
            _run(("docker", "inspect", identifiers[0]), timeout=30)
        )
    except json.JSONDecodeError as error:
        raise F4Error(f"runtime_inspect_json_invalid:{service}") from error
    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
    ):
        raise F4Error(f"runtime_inspect_invalid:{service}")
    document = documents[0]
    state = document.get("State")
    config = document.get("Config")
    if (
        not isinstance(state, dict)
        or state.get("Running") is not True
        or not isinstance(config, dict)
    ):
        raise F4Error(f"runtime_service_not_running:{service}")
    labels = config.get("Labels")
    if (
        not isinstance(labels, dict)
        or labels.get("com.docker.compose.project") != BROKER_PROJECT
        or labels.get("com.docker.compose.service") != service
    ):
        raise F4Error(f"runtime_service_labels_invalid:{service}")
    return document


def _runtime_image_acceptance(
    release: dict[str, object],
    inspects: dict[str, dict[str, object]],
) -> dict[str, object]:
    module = _load_fresh_module()
    bindings: dict[str, dict[str, str]] = {}
    for label in ("broker", "manager", "homeassistant"):
        record = release["images"][label]
        binding = module._verify_runtime_image(
            module.Runner(),
            label,
            record,
        )
        document = inspects[label]
        config = document["Config"]
        if (
            document.get("Image") != binding["runtime_id"]
            or config.get("Image") != record["image"]
        ):
            raise F4Error(f"runtime_container_image_drift:{label}")
        bindings[label] = binding
    return {
        label: {
            "rootfs_layers_sha256": value["rootfs_layers_sha256"],
            "config_contract_sha256": value["config_contract_sha256"],
        }
        for label, value in bindings.items()
    }


def _product_container_guard(
    release: dict[str, object],
    inspects: dict[str, dict[str, object]],
) -> dict[str, object]:
    expected_ids = {
        str(document.get("Id"))
        for document in inspects.values()
        if isinstance(document.get("Id"), str)
    }
    if len(expected_ids) != 3:
        raise F4Error("expected_runtime_container_set_invalid")
    images = release.get("images")
    if not isinstance(images, dict):
        raise F4Error("release_images_invalid")
    product_images = {
        str(images[label]["image"])
        for label in ("broker", "manager", "homeassistant")
    }
    identifiers = tuple(
        line.strip()
        for line in _run(
            ("docker", "ps", "--format", "{{.ID}}"),
            timeout=30,
        ).splitlines()
        if line.strip()
    )
    if not identifiers:
        raise F4Error("running_container_inventory_empty")
    try:
        documents = json.loads(
            _run(("docker", "inspect", *identifiers), timeout=30)
        )
    except json.JSONDecodeError as error:
        raise F4Error("running_container_inventory_invalid") from error
    if not isinstance(documents, list):
        raise F4Error("running_container_inventory_invalid")
    seen_expected: set[str] = set()
    unexpected = 0
    for document in documents:
        if not isinstance(document, dict):
            raise F4Error("running_container_inventory_invalid")
        identifier = document.get("Id")
        config = document.get("Config")
        if not isinstance(identifier, str) or not isinstance(config, dict):
            raise F4Error("running_container_inventory_invalid")
        if identifier in expected_ids:
            seen_expected.add(identifier)
            continue
        if config.get("Image") in product_images:
            unexpected += 1
    if seen_expected != expected_ids or unexpected != 0:
        raise F4Error("unexpected_product_container_running")
    return {
        "expected_product_container_count": 3,
        "unexpected_product_container_count": 0,
    }


def _broker_runtime_contract(document: dict[str, object]) -> None:
    network = document.get("NetworkSettings")
    host = document.get("HostConfig")
    if not isinstance(network, dict) or not isinstance(host, dict):
        raise F4Error("broker_runtime_metadata_invalid")
    networks = network.get("Networks")
    ports = network.get("Ports")
    if not isinstance(networks, dict) or set(networks) != BROKER_NETWORKS:
        raise F4Error("broker_network_set_invalid")
    if not isinstance(ports, dict):
        raise F4Error("broker_port_binding_invalid")
    expected = {
        "1883/tcp": ("127.0.0.1", "1883"),
        "8883/tcp": ("0.0.0.0", "8883"),
    }
    if not set(expected) <= set(ports):
        raise F4Error("broker_port_set_invalid")
    for key, rows in ports.items():
        if key not in expected:
            if rows not in (None, []):
                raise F4Error(f"broker_unexpected_publication:{key}")
            continue
        pair = expected[key]
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], dict)
            or (rows[0].get("HostIp"), rows[0].get("HostPort")) != pair
        ):
            raise F4Error(f"broker_port_binding_invalid:{key}")


def _mount_contract(
    document: dict[str, object],
    expected: dict[str, tuple[str, bool]],
    *,
    label: str,
) -> None:
    mounts = document.get("Mounts")
    if not isinstance(mounts, list):
        raise F4Error(f"{label}_mounts_invalid")
    observed: dict[str, tuple[str, bool]] = {}
    for item in mounts:
        if not isinstance(item, dict):
            raise F4Error(f"{label}_mount_invalid")
        mount_type = item.get("Type")
        target = item.get("Destination")
        if not isinstance(target, str):
            raise F4Error(f"{label}_mount_target_invalid")
        if mount_type == "tmpfs":
            continue
        if mount_type != "bind":
            raise F4Error(f"{label}_unexpected_mount_type")
        source = item.get("Source")
        if not isinstance(source, str):
            raise F4Error(f"{label}_mount_source_invalid")
        observed[target] = (source, item.get("RW") is True)
    if observed != expected:
        raise F4Error(f"{label}_mount_contract_invalid")


def _tmpfs_option_set(value: object) -> frozenset[str]:
    if not isinstance(value, str):
        raise F4Error("manager_tmpfs_options_invalid")
    return frozenset(
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    )


def _tmpfs_size_matches(options: frozenset[str], mib: int) -> bool:
    values = {
        item.split("=", 1)[1]
        for item in options
        if item.startswith("size=") and "=" in item
    }
    return len(values) == 1 and next(iter(values)) in {
        f"{mib}m",
        str(mib * 1024 * 1024),
        f"{mib * 1024}k",
    }


def _manager_tmpfs_contract(host: dict[str, object]) -> None:
    tmpfs = host.get("Tmpfs")
    if not isinstance(tmpfs, dict) or set(tmpfs) != {
        "/tmp",
        "/run/greenhouse-manager",
    }:
        raise F4Error("manager_tmpfs_set_invalid")

    temporary = _tmpfs_option_set(tmpfs["/tmp"])
    runtime = _tmpfs_option_set(tmpfs["/run/greenhouse-manager"])
    if (
        not _tmpfs_size_matches(temporary, 16)
        or "mode=1777" not in temporary
        or not _tmpfs_size_matches(runtime, 4)
        or not ({"mode=0700", "mode=700"} & runtime)
        or "uid=999" not in runtime
        or "gid=999" not in runtime
    ):
        raise F4Error("manager_tmpfs_contract_invalid")


def _manager_runtime_contract(document: dict[str, object]) -> None:
    config = document.get("Config")
    host = document.get("HostConfig")
    if not isinstance(config, dict) or not isinstance(host, dict):
        raise F4Error("manager_runtime_metadata_invalid")
    if (
        config.get("User") != "999:999"
        or host.get("NetworkMode") != "host"
        or host.get("ReadonlyRootfs") is not True
    ):
        raise F4Error("manager_runtime_contract_invalid")
    env = config.get("Env")
    if not isinstance(env, list):
        raise F4Error("manager_environment_invalid")
    values = {
        item.split("=", 1)[0]: item.split("=", 1)[1]
        for item in env
        if isinstance(item, str) and "=" in item
    }
    required = {
        "GH_MQTT_HOST": "armbian",
        "GH_MQTT_PORT": "8883",
        "GH_MQTT_TLS": "true",
        "GH_MQTT_PASSWORD_FILE": "/run/secrets/gh_manager_mqtt_password",
        "GH_N3W_PROVISIONING_PASSWORD_FILE": (
            "/run/secrets/gh_n3w_provisioning_mqtt_password"
        ),
        "GH_N3W_PRODUCT_PAIRING_ENABLED": "false",
    }
    if any(values.get(key) != value for key, value in required.items()):
        raise F4Error("manager_environment_contract_invalid")
    for key in (
        "GH_MQTT_USERNAME",
        "GH_MQTT_CLIENT_ID",
        "GH_N3W_PROVISIONING_USERNAME",
        "GH_N3W_PROVISIONING_CLIENT_ID",
    ):
        if not values.get(key):
            raise F4Error(f"manager_environment_missing:{key}")
    if (
        values["GH_MQTT_USERNAME"] == values["GH_N3W_PROVISIONING_USERNAME"]
        or values["GH_MQTT_CLIENT_ID"]
        == values["GH_N3W_PROVISIONING_CLIENT_ID"]
    ):
        raise F4Error("manager_service_identity_not_distinct")
    _mount_contract(
        document,
        {
            "/var/lib/greenhouse-manager/manager": (
                "/var/lib/greenhouse-manager/manager",
                True,
            ),
            "/var/lib/greenhouse-manager/n3w": (
                "/var/lib/greenhouse-manager/n3w",
                True,
            ),
            "/run/secrets/gh_manager_mqtt_password": (
                "/opt/greenhouse-secrets/mqtt/manager/password",
                False,
            ),
            "/run/secrets/gh_n3w_provisioning_mqtt_password": (
                "/opt/greenhouse-secrets/mqtt/provisioning/password",
                False,
            ),
            "/run/n3w/tls/ca.pem": (
                "/etc/n3wfc4/tls/ca.pem",
                False,
            ),
        },
        label="manager",
    )
    _manager_tmpfs_contract(host)


def _homeassistant_runtime_contract(document: dict[str, object]) -> None:
    host = document.get("HostConfig")
    if not isinstance(host, dict) or host.get("NetworkMode") != "host":
        raise F4Error("homeassistant_network_contract_invalid")
    _mount_contract(
        document,
        {
            "/config": (
                "/var/lib/n3wfc4-homeassistant",
                True,
            ),
            "/config/configuration.yaml": (
                (
                    "/opt/HomeAssistant/infra/n3w-t1/production/"
                    "homeassistant-configuration.yaml"
                ),
                False,
            ),
            "/config/custom_components/n3w_mqtt_bootstrap": (
                (
                    "/opt/HomeAssistant/infra/n3w-t1/homeassistant/"
                    "custom_components/n3w_mqtt_bootstrap"
                ),
                False,
            ),
            "/run/secrets/gh_homeassistant_mqtt_password": (
                "/opt/greenhouse-secrets/mqtt/homeassistant/password",
                False,
            ),
            "/run/n3w/ha-mqtt-bootstrap.json": (
                (
                    "/opt/greenhouse-secrets/mqtt/homeassistant/"
                    "mqtt-bootstrap.json"
                ),
                False,
            ),
        },
        label="homeassistant",
    )


def _verified_tls_runtime() -> dict[str, object]:
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=str(CA_CERT))
        with (
            socket.create_connection(("127.0.0.1", 8883), timeout=10) as raw,
            context.wrap_socket(
                raw,
                server_hostname=SERVER_NAME,
            ) as wrapped,
        ):
            peer = wrapped.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as error:
        raise F4Error("broker_live_tls_probe_failed") from error
    if not peer:
        raise F4Error("broker_live_tls_peer_missing")
    local_der = ssl.PEM_cert_to_DER_cert(
        SERVER_CERT.read_text(encoding="ascii")
    )
    if hashlib.sha256(peer).hexdigest() != hashlib.sha256(local_der).hexdigest():
        raise F4Error("broker_live_tls_certificate_mismatch")
    return {
        "ca_verified": True,
        "server_name_verified": True,
        "live_certificate_matches": True,
    }


def _guard_runtime_verify() -> dict[str, object]:
    source = Path("/usr/local/sbin/n3w-broker-ingress-guard")
    _regular_source(source)
    if _systemctl("is-active", GUARD_UNIT) != "active":
        raise F4Error("ingress_guard_not_active")
    if _systemctl("is-enabled", GUARD_UNIT) != "enabled":
        raise F4Error("ingress_guard_not_enabled")
    script = r"""
import json
import runpy
m = runpy.run_path("/usr/local/sbin/n3w-broker-ingress-guard")
decision = m["read_network_decision"]()
inventory = m["parse_firewall_inventory"](m["_save_filter_table"]())
m["_validate_prestate"](inventory)
m["validate_applied_state"](inventory, decision.trusted_subnet)
print(json.dumps({
    "status": "PASS",
    "anchor_count": len(inventory.anchor_positions),
    "input_anchor_count": len(inventory.input_anchor_positions),
    "last_drop": bool(inventory.custom_chain_rules and "DROP" in inventory.custom_chain_rules[-1]),
}, sort_keys=True))
"""
    try:
        document = json.loads(
            _run(("python3", "-c", script), timeout=30)
        )
    except json.JSONDecodeError as error:
        raise F4Error("guard_runtime_verify_json_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("status") != "PASS"
        or document.get("anchor_count") != 1
        or document.get("input_anchor_count") != 1
        or document.get("last_drop") is not True
    ):
        raise F4Error("guard_runtime_verify_failed")
    return {
        **document,
        "active": True,
        "enabled": True,
        "effective": True,
    }


def _container_established_socket_count(
    container: str,
    remote_port: int,
) -> int:
    script = r"""
import glob
import json
import os
import socket
import sys

port = int(sys.argv[1])
inodes = set()
for path in ("/proc/net/tcp", "/proc/net/tcp6"):
    try:
        rows = open(path, encoding="ascii").read().splitlines()[1:]
    except OSError:
        continue
    for row in rows:
        fields = row.split()
        if len(fields) < 10 or fields[3] != "01":
            continue
        remote = fields[2]
        try:
            remote_port = int(remote.rsplit(":", 1)[1], 16)
        except (ValueError, IndexError):
            continue
        if remote_port == port:
            inodes.add(fields[9])

owned = set()
for fd in glob.glob("/proc/[0-9]*/fd/*"):
    try:
        target = os.readlink(fd)
    except OSError:
        continue
    if target.startswith("socket:[") and target.endswith("]"):
        owned.add(target[8:-1])

print(json.dumps({"count": len(inodes & owned)}))
"""
    try:
        document = json.loads(
            _run(
                (
                    "docker",
                    "exec",
                    container,
                    "python3",
                    "-c",
                    script,
                    str(remote_port),
                ),
                timeout=30,
            )
        )
    except json.JSONDecodeError as error:
        raise F4Error("runtime_socket_probe_json_invalid") from error
    count = document.get("count") if isinstance(document, dict) else None
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise F4Error("runtime_socket_probe_invalid")
    return count


def _manager_runtime_stability(
    container: str,
    *,
    expected_id: str,
    expected_started_at: str,
) -> dict[str, object]:
    samples = 0
    deadline = time.monotonic() + 10
    while True:
        document = _compose_service_inspect("manager")
        state = document.get("State")
        if (
            document.get("Id") != expected_id
            or not isinstance(state, dict)
            or state.get("StartedAt") != expected_started_at
            or state.get("Running") is not True
        ):
            raise F4Error("manager_runtime_identity_changed")
        socket_count = _container_established_socket_count(container, 8883)
        if socket_count != 1:
            raise F4Error(
                f"manager_mqtt_socket_count_invalid:{socket_count}"
            )
        samples += 1
        if time.monotonic() >= deadline:
            break
        time.sleep(1)
    return {
        "stable_window_seconds": 10,
        "sample_count": samples,
        "container_identity_stable": True,
        "mqtt_socket_stable": True,
    }


def _manager_state_audit(container: str) -> dict[str, object]:
    script = r"""
import hashlib
import json
import os
from pathlib import Path
from greenhouse_manager.bootstrap.fresh_product_state import audit_fresh_state

system_id = os.environ["GH_SYSTEM_ID"]
report = audit_fresh_state(
    Path("/var/lib/greenhouse-manager/manager"),
    Path("/var/lib/greenhouse-manager/n3w"),
    expected_system_id_sha256=hashlib.sha256(system_id.encode()).hexdigest(),
)
print(json.dumps({
    "status": report["status"],
    "manager_business_row_count": report["manager_business_row_count"],
    "replay_node_count": report["replay_node_count"],
    "replay_tuple_count": report["replay_tuple_count"],
    "relay_active_node_count": report["relay_active_node_count"],
    "relay_key_file_count": report["relay_key_file_count"],
    "node_credential_count": report["node_credential_count"],
}, sort_keys=True))
"""
    try:
        document = json.loads(
            _run(
                (
                    "docker",
                    "exec",
                    "--user",
                    "999:999",
                    container,
                    "python",
                    "-c",
                    script,
                ),
                timeout=90,
            )
        )
    except json.JSONDecodeError as error:
        raise F4Error("manager_state_audit_json_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("status") != "PASS"
        or any(
            document.get(key) != 0
            for key in (
                "manager_business_row_count",
                "replay_node_count",
                "replay_tuple_count",
                "relay_active_node_count",
                "relay_key_file_count",
                "node_credential_count",
            )
        )
    ):
        raise F4Error("manager_state_audit_failed")
    return document


def _homeassistant_private_audit(container: str) -> dict[str, object]:
    script = r"""
import hashlib
import hmac
import json
from pathlib import Path

storage = json.loads(Path("/config/.storage/core.config_entries").read_text())
metadata = json.loads(Path("/run/n3w/ha-mqtt-bootstrap.json").read_text())
password = Path("/run/secrets/gh_homeassistant_mqtt_password").read_text().rstrip("\r\n")
entries = storage.get("data", {}).get("entries", [])
mqtt = [item for item in entries if isinstance(item, dict) and item.get("domain") == "mqtt"]
enabled = [item for item in mqtt if item.get("disabled_by") is None]
match = False
entry_hash = None
if len(enabled) == 1:
    entry = enabled[0]
    data = entry.get("data") if isinstance(entry.get("data"), dict) else {}
    entry_id = entry.get("entry_id")
    match = (
        data.get("broker", data.get("host")) == metadata.get("broker")
        and data.get("port") == metadata.get("port")
        and str(data.get("protocol")) == str(metadata.get("protocol"))
        and data.get("username") == metadata.get("username")
        and data.get("client_id") == metadata.get("client_id")
        and data.get("transport", "tcp") == "tcp"
        and data.get("certificate") is None
        and data.get("client_cert") is None
        and data.get("client_key") is None
        and isinstance(data.get("password"), str)
        and hmac.compare_digest(data["password"], password)
    )
    if isinstance(entry_id, str) and entry_id:
        entry_hash = hashlib.sha256(entry_id.encode()).hexdigest()

entity_path = Path("/config/.storage/core.entity_registry")
mqtt_entity_count = 0
if entity_path.is_file():
    entity = json.loads(entity_path.read_text())
    rows = entity.get("data", {}).get("entities", [])
    mqtt_entity_count = sum(
        1
        for item in rows
        if isinstance(item, dict) and item.get("platform") == "mqtt"
    )

print(json.dumps({
    "mqtt_entry_count": len(mqtt),
    "enabled_mqtt_entry_count": len(enabled),
    "entry_matches_private_bootstrap": match,
    "entry_id_sha256": entry_hash,
    "mqtt_entity_count": mqtt_entity_count,
}, sort_keys=True))
"""
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            document = json.loads(
                _run(
                    (
                        "docker",
                        "exec",
                        "--user",
                        "0:0",
                        container,
                        "python3",
                        "-c",
                        script,
                    ),
                    timeout=30,
                )
            )
        except (F4Error, json.JSONDecodeError):
            time.sleep(2)
            continue
        if (
            isinstance(document, dict)
            and document.get("mqtt_entry_count") == 1
            and document.get("enabled_mqtt_entry_count") == 1
            and document.get("entry_matches_private_bootstrap") is True
            and isinstance(document.get("entry_id_sha256"), str)
            and re.fullmatch(
                r"[0-9a-f]{64}",
                str(document["entry_id_sha256"]),
            )
            and document.get("mqtt_entity_count") == 0
        ):
            return document
        time.sleep(2)
    raise F4Error("homeassistant_private_runtime_audit_failed")


def _homeassistant_http_readiness() -> dict[str, object]:
    deadline = time.monotonic() + 60
    last_error = "not_attempted"
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 8123), timeout=5) as stream:
                stream.settimeout(5)
                stream.sendall(
                    b"GET /api/ HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\n"
                    b"Connection: close\r\n\r\n"
                )
                first = stream.recv(256).split(b"\r\n", 1)[0]
            parts = first.split()
            if (
                len(parts) >= 2
                and parts[0].startswith(b"HTTP/")
                and parts[1].isdigit()
            ):
                status = int(parts[1])
                if status in {200, 401}:
                    return {
                        "ready": True,
                        "http_status": status,
                    }
                last_error = f"http_status_{status}"
            else:
                last_error = "http_status_line_invalid"
        except OSError as error:
            last_error = type(error).__name__
        time.sleep(2)
    raise F4Error(f"homeassistant_http_readiness_failed:{last_error}")


def _service_identity_runtime_binding(
    manager_document: dict[str, object],
    *,
    expected_system_id: str,
) -> dict[str, object]:
    config = manager_document.get("Config")
    if not isinstance(config, dict) or not isinstance(config.get("Env"), list):
        raise F4Error("manager_environment_invalid")
    environment = {
        item.split("=", 1)[0]: item.split("=", 1)[1]
        for item in config["Env"]
        if isinstance(item, str) and "=" in item
    }
    manager = _private_service_json(
        SERVICE_SECRET_ROOT / "manager/identity.json",
        uid=999,
        gid=999,
    )
    provisioning = _private_service_json(
        SERVICE_SECRET_ROOT / "provisioning/identity.json",
        uid=999,
        gid=999,
    )
    homeassistant = _private_service_json(
        SERVICE_SECRET_ROOT / "homeassistant/identity.json",
        uid=0,
        gid=0,
    )
    bootstrap = _private_service_json(
        SERVICE_SECRET_ROOT / "homeassistant/mqtt-bootstrap.json",
        uid=0,
        gid=0,
    )
    identities = {
        "manager": manager,
        "provisioning": provisioning,
        "homeassistant": homeassistant,
    }
    for service, identity in identities.items():
        if (
            identity.get("service") != service
            or identity.get("system_id") != expected_system_id
            or not isinstance(identity.get("generation"), int)
            or not isinstance(identity.get("username"), str)
            or not identity.get("username")
            or not isinstance(identity.get("client_id"), str)
            or not identity.get("client_id")
        ):
            raise F4Error(f"service_identity_binding_invalid:{service}")
    if (
        environment.get("GH_SYSTEM_ID") != expected_system_id
        or environment.get("GH_MQTT_USERNAME") != manager["username"]
        or environment.get("GH_MQTT_CLIENT_ID") != manager["client_id"]
        or environment.get("GH_N3W_PROVISIONING_USERNAME")
        != provisioning["username"]
        or environment.get("GH_N3W_PROVISIONING_CLIENT_ID")
        != provisioning["client_id"]
    ):
        raise F4Error("manager_runtime_service_identity_drift")
    if (
        bootstrap.get("schema")
        != "gh.n3w.t1-clean-homeassistant-mqtt-bootstrap/1"
        or bootstrap.get("service") != "homeassistant"
        or bootstrap.get("username") != homeassistant["username"]
        or bootstrap.get("client_id") != homeassistant["client_id"]
        or bootstrap.get("generation") != homeassistant["generation"]
        or bootstrap.get("broker") != "127.0.0.1"
        or bootstrap.get("port") != 1883
        or str(bootstrap.get("protocol")) != "5"
        or bootstrap.get("official_config_flow_only") is not True
        or bootstrap.get("direct_storage_edit_forbidden") is not True
        or bootstrap.get("automatic_apply") is not True
        or bootstrap.get("runtime_verified") is not False
    ):
        raise F4Error("homeassistant_bootstrap_identity_drift")
    usernames = {str(identity["username"]) for identity in identities.values()}
    client_ids = {str(identity["client_id"]) for identity in identities.values()}
    if len(usernames) != 3 or len(client_ids) != 3:
        raise F4Error("service_identity_distinctness_invalid")
    return {
        "manager_identity_exact": True,
        "provisioning_identity_exact": True,
        "homeassistant_identity_exact": True,
        "manager_runtime_identity_exact": True,
        "homeassistant_bootstrap_identity_exact": True,
        "service_usernames_distinct": True,
        "service_client_ids_distinct": True,
    }


def _root_identity_runtime_audit(manager_image: str) -> dict[str, object]:
    script = r"""
import json
from pathlib import Path
from greenhouse_manager.bootstrap.system_init import verify_initialization
from greenhouse_manager.bootstrap.fresh_broker import audit_fresh_dynsec_document
from greenhouse_manager.ops.t1_clean_service_credential_bundle import verify_clean_service_credential_bundle

identity = verify_initialization(Path("/identity"))
dynsec = audit_fresh_dynsec_document(
    Path("/broker/dynamic-security.json"),
    system_id=identity.system_id,
)
credentials = verify_clean_service_credential_bundle(Path("/secrets/mqtt"))
if credentials.get("system_id") != identity.system_id:
    raise RuntimeError("credential_system_id_drift")
print(json.dumps({
    "dynsec_service_client_count": dynsec["service_client_count"],
    "dynsec_service_role_count": dynsec["service_role_count"],
    "dynsec_node_client_count": dynsec["node_client_count"],
    "dynsec_node_role_count": dynsec["node_role_count"],
    "credential_service_count": credentials["service_count"],
    "credential_node_count": credentials["node_credential_count"],
}, sort_keys=True))
"""
    name = f"n3w-f4-root-audit-{os.getpid()}"
    try:
        document = json.loads(
            _run(
                (
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    name,
                    "--network",
                    "none",
                    "--user",
                    "0:0",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:size=4m,mode=1777",
                    "--mount",
                    "type=bind,src=/var/lib/greenhouse-manager/identity,dst=/identity,readonly",
                    "--mount",
                    "type=bind,src=/var/lib/n3wfc4-broker,dst=/broker,readonly",
                    "--mount",
                    "type=bind,src=/opt/greenhouse-secrets,dst=/secrets,readonly",
                    "--entrypoint",
                    "python",
                    manager_image,
                    "-c",
                    script,
                ),
                timeout=120,
            )
        )
    except json.JSONDecodeError as error:
        raise F4Error("root_identity_runtime_audit_json_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("dynsec_service_client_count") != 3
        or document.get("dynsec_service_role_count") != 3
        or document.get("dynsec_node_client_count") != 0
        or document.get("dynsec_node_role_count") != 0
        or document.get("credential_service_count") != 3
        or document.get("credential_node_count") != 0
    ):
        raise F4Error("root_identity_runtime_audit_failed")
    return document


def _broker_auth_negative_and_provisioning_probe(
    manager_image: str,
) -> dict[str, object]:
    script = r"""
import json
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

SERVICES = ("manager", "provisioning", "homeassistant")


def material(service):
    identity = json.loads(
        Path(f"/secrets/{service}/identity.json").read_text()
    )
    password = Path(f"/secrets/{service}/password").read_text().rstrip("\r\n")
    return identity, password


def attempt(*, username, password, client_id):
    event = threading.Event()
    result = {"known": False, "accepted": False}

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        result["known"] = True
        result["accepted"] = not reason_code.is_failure
        event.set()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv5,
    )
    client.on_connect = on_connect
    if username is not None:
        client.username_pw_set(username, password)
    client.tls_set(ca_certs="/ca.pem")
    client.connect("127.0.0.1", 8883, keepalive=10)
    client.loop_start()
    try:
        if not event.wait(8):
            raise RuntimeError("mqtt_probe_outcome_unknown")
    finally:
        client.loop_stop()
        try:
            client.disconnect()
        except Exception:
            pass
    return result


materials = {
    service: material(service)
    for service in SERVICES
}
negative = {}
for service, (identity, password) in materials.items():
    probe = attempt(
        username=identity["username"],
        password=password,
        client_id=identity["client_id"] + "-f4-invalid",
    )
    if not probe["known"]:
        raise RuntimeError("wrong_client_id_probe_unknown")
    negative[service] = not probe["accepted"]

anonymous = attempt(
    username=None,
    password=None,
    client_id="n3w-f4-anonymous-probe",
)
if not anonymous["known"]:
    raise RuntimeError("anonymous_probe_unknown")

identity, password = materials["provisioning"]
provisioning = attempt(
    username=identity["username"],
    password=password,
    client_id=identity["client_id"],
)
if not provisioning["known"]:
    raise RuntimeError("provisioning_probe_unknown")

print(json.dumps({
    "manager_wrong_client_id_rejected": negative["manager"],
    "provisioning_wrong_client_id_rejected": negative["provisioning"],
    "homeassistant_wrong_client_id_rejected": negative["homeassistant"],
    "anonymous_rejected": not anonymous["accepted"],
    "provisioning_exact_credential_auth": provisioning["accepted"],
}, sort_keys=True))
"""
    name = f"n3w-f4-auth-probe-{os.getpid()}"
    try:
        document = json.loads(
            _run(
                (
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    name,
                    "--network",
                    "host",
                    "--user",
                    "0:0",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:size=4m,mode=1777",
                    "--mount",
                    "type=bind,src=/opt/greenhouse-secrets/mqtt,dst=/secrets,readonly",
                    "--mount",
                    "type=bind,src=/etc/n3wfc4/tls/ca.pem,dst=/ca.pem,readonly",
                    "--entrypoint",
                    "python",
                    manager_image,
                    "-c",
                    script,
                ),
                timeout=90,
            )
        )
    except json.JSONDecodeError as error:
        raise F4Error("broker_auth_probe_json_invalid") from error
    expected_true = (
        "manager_wrong_client_id_rejected",
        "provisioning_wrong_client_id_rejected",
        "homeassistant_wrong_client_id_rejected",
        "anonymous_rejected",
        "provisioning_exact_credential_auth",
    )
    if (
        not isinstance(document, dict)
        or any(document.get(key) is not True for key in expected_true)
    ):
        raise F4Error("broker_auth_probe_failed")
    return document


def _runtime_acceptance_report() -> dict[str, object]:
    verified = _provision_verify()
    transaction = _validate_transaction_binding(verified)
    _validate_factory_binding(verified)
    if transaction.get("stage") != "RUNTIME_STARTED":
        raise F4Error("runtime_acceptance_stage_invalid")
    _verify_installed_material(transaction)

    running = _running_services()
    if running != frozenset({"broker", "manager", "homeassistant"}):
        raise F4Error("runtime_service_set_invalid")

    release = _read_release()
    inspects = {
        label: _compose_service_inspect(label)
        for label in ("broker", "manager", "homeassistant")
    }
    image_bindings = _runtime_image_acceptance(release, inspects)
    product_containers = _product_container_guard(release, inspects)
    _broker_runtime_contract(inspects["broker"])
    _manager_runtime_contract(inspects["manager"])
    _homeassistant_runtime_contract(inspects["homeassistant"])
    identity_binding = _service_identity_runtime_binding(
        inspects["manager"],
        expected_system_id=str(verified["system_id"]),
    )

    guard = _guard_runtime_verify()
    tls = _verified_tls_runtime()

    manager_name = str(inspects["manager"].get("Name", "")).lstrip("/")
    homeassistant_name = str(
        inspects["homeassistant"].get("Name", "")
    ).lstrip("/")
    if not manager_name or not homeassistant_name:
        raise F4Error("runtime_container_name_missing")

    manager_state = _manager_state_audit(manager_name)
    manager_id = inspects["manager"].get("Id")
    manager_state_doc = inspects["manager"].get("State")
    if (
        not isinstance(manager_id, str)
        or not isinstance(manager_state_doc, dict)
        or not isinstance(manager_state_doc.get("StartedAt"), str)
    ):
        raise F4Error("manager_runtime_identity_invalid")
    manager_stability = _manager_runtime_stability(
        manager_name,
        expected_id=manager_id,
        expected_started_at=str(manager_state_doc["StartedAt"]),
    )
    manager_socket_count = 1

    homeassistant = _homeassistant_private_audit(homeassistant_name)
    homeassistant_readiness = _homeassistant_http_readiness()
    ha_socket_count = _container_established_socket_count(
        homeassistant_name,
        1883,
    )
    if ha_socket_count < 1:
        raise F4Error("homeassistant_mqtt_socket_missing")

    manager_image = str(release["images"]["manager"]["image"])
    root_audit = _root_identity_runtime_audit(manager_image)
    auth_probe = _broker_auth_negative_and_provisioning_probe(
        manager_image
    )

    runtime = _runtime_activity()
    if runtime["production_service_start"] is not True:
        raise F4Error("runtime_activity_not_proven")

    return {
        "schema": "gh.n3w-t1-f4-runtime-acceptance/1",
        "status": "PASS",
        "release_id": verified["release_id"],
        "host_instance_id_sha256": _sha256_text(
            str(verified["host_instance_id"])
        ),
        "system_id_sha256": _sha256_text(str(verified["system_id"])),
        "package_source_head": transaction["package_source_head"],
        "package_manifest_sha256": transaction[
            "package_manifest_sha256"
        ],
        "running_services": sorted(running),
        "image_bindings": image_bindings,
        "product_containers": product_containers,
        "broker_port_binding_exact": True,
        "broker_network_set_exact": True,
        "service_identity_binding": identity_binding,
        "ingress_guard": guard,
        "tls": tls,
        "manager_runtime_stability": manager_stability,
        "manager_state": manager_state,
        "manager_mqtt_socket_count": manager_socket_count,
        "homeassistant": homeassistant,
        "homeassistant_readiness": homeassistant_readiness,
        "homeassistant_mqtt_socket_count": ha_socket_count,
        "identity_runtime_audit": root_audit,
        "broker_auth_probe": auth_probe,
        "manager_live_authenticated_connection_proven": True,
        "homeassistant_live_authenticated_connection_proven": True,
        "product_pairing_enabled": False,
        "production_service_start": True,
        "persistence_enabled": False,
        "certificate_timer_enabled": False,
        "secret_values_included": False,
        "board_access": False,
    }


def _downstream_fail_closed(
    stage_prefix: str,
    error: BaseException,
) -> None:
    rollback_errors: list[str] = []
    for argv, timeout in (
        (("systemctl", "stop", CERT_TIMER), 60),
        (("systemctl", "disable", CERT_TIMER), 60),
        (("systemctl", "stop", CERT_SERVICE), 120),
        (("systemctl", "disable", SERVICES_UNIT, BROKER_UNIT), 60),
        (("systemctl", "stop", SERVICES_UNIT), 120),
        (("systemctl", "stop", BROKER_UNIT), 120),
    ):
        try:
            _run(argv, timeout=timeout)
        except OPERATION_ERRORS as rollback_error:
            rollback_errors.append(type(rollback_error).__name__)
    runtime = _runtime_activity()
    try:
        listener_ports = _product_listener_ports()
    except OPERATION_ERRORS as rollback_error:
        rollback_errors.append(type(rollback_error).__name__)
        listener_ports = None
    rollback_proven = (
        runtime["production_service_start"] is False
        and listener_ports == []
        and _systemctl("is-enabled", BROKER_UNIT) != "enabled"
        and _systemctl("is-enabled", SERVICES_UNIT) != "enabled"
        and _systemctl("is-enabled", CERT_TIMER) != "enabled"
        and _systemctl("is-active", CERT_TIMER)
        not in {"active", "activating", "reloading"}
        and _systemctl("is-active", CERT_SERVICE)
        not in {"active", "activating", "reloading"}
        and not rollback_errors
    )
    stop_stage = (
        f"STOPPED_{stage_prefix}"
        if rollback_proven
        else f"STOPPED_{stage_prefix}_ROLLBACK_UNPROVEN"
    )
    _advance_transaction(
        stop_stage,
        error_code=str(error)[:300],
        production_service_start=runtime["production_service_start"],
        persistence_enabled=False,
        certificate_timer_enabled=False,
        product_listener_ports=listener_ports,
        rollback_proven=rollback_proven,
        rollback_error_count=len(rollback_errors),
    )


def _accept_runtime(authorization_id: str) -> dict[str, object]:
    with _exclusive_f4():
        verified = _provision_verify()
        transaction = _validate_transaction_binding(verified)
        if transaction.get("stage") != "RUNTIME_STARTED":
            raise F4Error("runtime_acceptance_replay_forbidden")
        if (
            not authorization_id.startswith("N3W_T1_F4_")
            or len(authorization_id) > 200
            or not authorization_id.replace("_", "").replace("-", "").isalnum()
        ):
            raise F4Error("runtime_acceptance_authorization_id_invalid")
        if authorization_id in _all_prior_authorization_ids(transaction):
            raise F4Error("continuation_authorization_not_distinct")

        prior_claimed = (
            transaction.get("runtime_acceptance_authorization_claimed")
            is True
        )
        retry_eligible = (
            transaction.get("runtime_acceptance_retry_eligible") is True
        )
        if prior_claimed and (
            not retry_eligible
            or transaction.get("runtime_acceptance_recovery_passed")
            is not True
            or transaction.get(
                "runtime_acceptance_recovery_authorization_claimed"
            )
            is not True
            or transaction.get(
                "runtime_acceptance_recovery_authorization_consumed"
            )
            is not True
            or transaction.get(
                "runtime_acceptance_recovery_authorization_replay_allowed"
            )
            is not False
        ):
            raise F4Error(
                "runtime_acceptance_authorization_replay_forbidden"
            )

        history_raw = transaction.get(
            "runtime_acceptance_authorization_history",
            [],
        )
        if not isinstance(history_raw, list) or not all(
            isinstance(value, str) for value in history_raw
        ):
            raise F4Error(
                "runtime_acceptance_authorization_history_invalid"
            )
        history = list(dict.fromkeys(history_raw))
        previous_acceptance = transaction.get(
            "runtime_acceptance_authorization_id"
        )
        if prior_claimed:
            if not isinstance(previous_acceptance, str):
                raise F4Error(
                    "runtime_acceptance_prior_authorization_missing"
                )
            if (
                transaction.get(
                    "runtime_acceptance_last_failure_authorization_id"
                )
                != previous_acceptance
            ):
                raise F4Error(
                    "runtime_acceptance_recovery_failure_binding_invalid"
                )
            if previous_acceptance not in history:
                history.append(previous_acceptance)

        _advance_transaction(
            "RUNTIME_STARTED",
            runtime_acceptance_authorization_history=history,
            runtime_acceptance_authorization_id=authorization_id,
            runtime_acceptance_authorization_claimed=True,
            runtime_acceptance_authorization_consumed=True,
            runtime_acceptance_authorization_replay_allowed=False,
            runtime_acceptance_retry_eligible=False,
            production_service_start=True,
            persistence_enabled=False,
        )
        try:
            report = _runtime_acceptance_report()
            _new_private_record(RUNTIME_ACCEPTANCE_PATH, report)
            report_sha256 = _sha256_file(RUNTIME_ACCEPTANCE_PATH)
            _advance_transaction(
                "RUNTIME_ACCEPTED",
                runtime_acceptance_passed=True,
                runtime_acceptance_report_sha256=report_sha256,
                homeassistant_mqtt_entry_id_sha256=report[
                    "homeassistant"
                ]["entry_id_sha256"],
                production_service_start=True,
                persistence_enabled=False,
                certificate_timer_enabled=False,
            )
            return {
                "status": "PASS",
                "state": "RUNTIME_ACCEPTED",
                "runtime_acceptance_report_sha256": report_sha256,
                "production_service_start": True,
                "persistence_enabled": False,
                "certificate_timer_enabled": False,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            try:
                _downstream_fail_closed("RUNTIME_ACCEPTANCE", error)
            except OPERATION_ERRORS as rollback_error:
                raise F4Error(
                    "runtime_acceptance_failed_rollback_unproven:"
                    + type(rollback_error).__name__
                ) from error
            raise


def _enable_persistence(authorization_id: str) -> dict[str, object]:
    with _exclusive_f4():
        verified = _provision_verify()
        transaction = _validate_transaction_binding(verified)
        _validate_factory_binding(verified)
        _verify_installed_material(transaction)
        if (
            transaction.get("stage") != "RUNTIME_ACCEPTED"
            or transaction.get("runtime_acceptance_passed") is not True
        ):
            raise F4Error("persistence_stage_invalid")
        _validate_successor_authorization(
            transaction,
            authorization_id,
            claimed_field="persistence_authorization_claimed",
            invalid_code="persistence_authorization_id_invalid",
            replay_code="persistence_authorization_replay_forbidden",
        )
        _validate_runtime_acceptance_binding(transaction)
        before = _runtime_activity()
        if (
            before["production_service_start"] is not True
            or set(before["running_services"] or [])
            != {"broker", "manager", "homeassistant"}
        ):
            raise F4Error("persistence_runtime_not_active")
        before_snapshot = _runtime_container_snapshot()
        _advance_transaction(
            "RUNTIME_ACCEPTED",
            persistence_authorization_id=authorization_id,
            persistence_authorization_claimed=True,
            persistence_authorization_consumed=True,
            persistence_authorization_replay_allowed=False,
            production_service_start=True,
            persistence_enabled=False,
        )
        try:
            _run(
                (
                    "systemctl",
                    "enable",
                    BROKER_UNIT,
                    SERVICES_UNIT,
                ),
                timeout=60,
            )
            if (
                _systemctl("is-enabled", BROKER_UNIT) != "enabled"
                or _systemctl("is-enabled", SERVICES_UNIT) != "enabled"
                or _systemctl("is-enabled", CERT_TIMER) == "enabled"
            ):
                raise F4Error("persistence_enablement_invalid")
            after = _runtime_activity()
            if (
                after["production_service_start"] is not True
                or set(after["running_services"] or [])
                != {"broker", "manager", "homeassistant"}
                or after["running_services"] != before["running_services"]
                or _runtime_container_snapshot() != before_snapshot
            ):
                raise F4Error("persistence_runtime_changed")
            _validate_runtime_acceptance_binding(transaction)
            _advance_transaction(
                "PERSISTENCE_ENABLED",
                broker_services_persistence_enabled=True,
                production_service_start=True,
                persistence_enabled=True,
                certificate_timer_enabled=False,
            )
            return {
                "status": "PASS",
                "state": "PERSISTENCE_ENABLED",
                "broker_services_persistence_enabled": True,
                "certificate_timer_enabled": False,
                "production_service_start": True,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            try:
                _downstream_fail_closed("PERSISTENCE", error)
            except OPERATION_ERRORS as rollback_error:
                raise F4Error(
                    "persistence_failed_rollback_unproven:"
                    + type(rollback_error).__name__
                ) from error
            raise


def _certificate_identity_snapshot() -> dict[str, str]:
    return {
        "server_cert": _sha256_file(SERVER_CERT),
        "server_key": _sha256_file(SERVER_KEY),
        "ca_cert": _sha256_file(CA_CERT),
        "ca_key": _sha256_file(CA_KEY),
        "system_ca": _sha256_file(SYSTEM_CA),
    }


def _certificate_audit_command() -> tuple[str, ...]:
    return (
        "/usr/local/sbin/n3w-broker-certificate-lifecycle",
        "audit",
        "--server-cert",
        str(SERVER_CERT),
        "--server-key",
        str(SERVER_KEY),
        "--ca-cert",
        str(CA_CERT),
        "--ca-key",
        str(CA_KEY),
        "--system-ca",
        str(SYSTEM_CA),
        "--server-name",
        SERVER_NAME,
        "--status-file",
        str(CERT_STATUS_FILE),
        "--allowed-root",
        str(ETC_N3W),
        "--allowed-root",
        str(CA_KEY.parent),
        "--allowed-root",
        str(SYSTEM_CA.parent),
        "--activation-unit",
        BROKER_UNIT,
        "--probe-host",
        "127.0.0.1",
        "--probe-port",
        "8883",
    )


def _certificate_first_audit(authorization_id: str) -> dict[str, object]:
    with _exclusive_f4():
        verified = _provision_verify()
        transaction = _validate_transaction_binding(verified)
        _validate_factory_binding(verified)
        _verify_installed_material(transaction)
        if (
            transaction.get("stage") != "PERSISTENCE_ENABLED"
            or transaction.get("broker_services_persistence_enabled")
            is not True
            or transaction.get("certificate_first_audit_passed") is True
        ):
            raise F4Error("certificate_audit_stage_invalid")
        _validate_successor_authorization(
            transaction,
            authorization_id,
            claimed_field="certificate_audit_authorization_claimed",
            invalid_code="certificate_audit_authorization_id_invalid",
            replay_code="certificate_audit_authorization_replay_forbidden",
        )
        if _systemctl("is-enabled", CERT_TIMER) == "enabled":
            raise F4Error("certificate_timer_enabled_too_early")
        _validate_runtime_acceptance_binding(transaction)
        runtime = _runtime_activity()
        if (
            runtime["production_service_start"] is not True
            or set(runtime["running_services"] or [])
            != {"broker", "manager", "homeassistant"}
        ):
            raise F4Error("certificate_audit_runtime_not_active")
        if (
            not CERT_STATUS_ROOT.is_dir()
            or CERT_STATUS_ROOT.is_symlink()
            or CERT_STATUS_ROOT.stat().st_uid != 0
            or CERT_STATUS_ROOT.stat().st_gid != 0
            or stat.S_IMODE(CERT_STATUS_ROOT.stat().st_mode) != 0o700
            or any(CERT_STATUS_ROOT.iterdir())
        ):
            raise F4Error("certificate_first_audit_prestate_invalid")

        _advance_transaction(
            "PERSISTENCE_ENABLED",
            certificate_audit_authorization_id=authorization_id,
            certificate_audit_authorization_claimed=True,
            certificate_audit_authorization_consumed=True,
            certificate_audit_authorization_replay_allowed=False,
            production_service_start=True,
            persistence_enabled=True,
            certificate_timer_enabled=False,
        )
        try:
            _validate_tls_material()
            before_identity = _certificate_identity_snapshot()
            before_snapshot = _runtime_container_snapshot()
            try:
                document = json.loads(
                    _run(_certificate_audit_command(), timeout=120)
                )
            except json.JSONDecodeError as error:
                raise F4Error("certificate_audit_json_invalid") from error
            if (
                not isinstance(document, dict)
                or document.get("action") != "audit"
                or document.get("result") != "ok"
                or document.get("server_state") != "HEALTHY"
                or document.get("ca_state") != "HEALTHY"
                or document.get("system_ca_state") != "HEALTHY"
                or document.get("renewal_attempted") is not False
                or document.get("rollback_attempted") is not False
            ):
                raise F4Error("certificate_first_audit_not_healthy")

            after_identity = _certificate_identity_snapshot()
            after_runtime = _runtime_activity()
            if (
                after_identity != before_identity
                or after_runtime["production_service_start"] is not True
                or set(after_runtime["running_services"] or [])
                != {"broker", "manager", "homeassistant"}
                or _runtime_container_snapshot() != before_snapshot
            ):
                raise F4Error("certificate_audit_runtime_changed")

            _validate_runtime_acceptance_binding(transaction)
            _verified_tls_runtime()
            if (
                not CERT_STATUS_FILE.is_file()
                or CERT_STATUS_FILE.is_symlink()
                or not CERT_LOCK_FILE.is_file()
                or CERT_LOCK_FILE.is_symlink()
                or {item.name for item in CERT_STATUS_ROOT.iterdir()}
                != {CERT_STATUS_FILE.name, CERT_LOCK_FILE.name}
            ):
                raise F4Error("certificate_status_authority_invalid")
            for target in (CERT_STATUS_FILE, CERT_LOCK_FILE):
                metadata = target.stat()
                if (
                    metadata.st_uid != 0
                    or metadata.st_gid != 0
                    or stat.S_IMODE(metadata.st_mode) != 0o600
                    or metadata.st_nlink != 1
                ):
                    raise F4Error("certificate_status_metadata_invalid")
            try:
                durable_status = json.loads(
                    CERT_STATUS_FILE.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise F4Error("certificate_status_json_invalid") from error
            if durable_status != document:
                raise F4Error("certificate_status_document_mismatch")
            status_sha256 = _sha256_file(CERT_STATUS_FILE)
            _advance_transaction(
                "PERSISTENCE_ENABLED",
                certificate_first_audit_passed=True,
                certificate_status_sha256=status_sha256,
                certificate_server_state="HEALTHY",
                certificate_ca_state="HEALTHY",
                certificate_system_ca_state="HEALTHY",
                certificate_timer_enabled=False,
                production_service_start=True,
                persistence_enabled=True,
            )
            return {
                "status": "PASS",
                "state": "PERSISTENCE_ENABLED",
                "certificate_first_audit_passed": True,
                "certificate_status_sha256": status_sha256,
                "certificate_timer_enabled": False,
                "production_service_start": True,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            try:
                _downstream_fail_closed("CERTIFICATE_AUDIT", error)
            except OPERATION_ERRORS as rollback_error:
                raise F4Error(
                    "certificate_audit_failed_rollback_unproven:"
                    + type(rollback_error).__name__
                ) from error
            raise


def _enable_certificate_timer(authorization_id: str) -> dict[str, object]:
    with _exclusive_f4():
        verified = _provision_verify()
        transaction = _validate_transaction_binding(verified)
        _validate_factory_binding(verified)
        _verify_installed_material(transaction)
        if (
            transaction.get("stage") != "PERSISTENCE_ENABLED"
            or transaction.get("certificate_first_audit_passed") is not True
            or not isinstance(transaction.get("certificate_status_sha256"), str)
            or _sha256_file(CERT_STATUS_FILE)
            != transaction.get("certificate_status_sha256")
        ):
            raise F4Error("certificate_timer_stage_invalid")
        _validate_successor_authorization(
            transaction,
            authorization_id,
            claimed_field="certificate_timer_authorization_claimed",
            invalid_code="certificate_timer_authorization_id_invalid",
            replay_code="certificate_timer_authorization_replay_forbidden",
        )
        _validate_runtime_acceptance_binding(transaction)
        runtime_before = _runtime_activity()
        if (
            runtime_before["production_service_start"] is not True
            or set(runtime_before["running_services"] or [])
            != {"broker", "manager", "homeassistant"}
            or _systemctl("is-enabled", BROKER_UNIT) != "enabled"
            or _systemctl("is-enabled", SERVICES_UNIT) != "enabled"
            or _systemctl("is-active", CERT_SERVICE)
            in {"active", "activating", "reloading"}
        ):
            raise F4Error("certificate_timer_runtime_prestate_invalid")
        if _systemctl("is-active", CERT_TIMER) in {
            "active",
            "activating",
            "reloading",
        }:
            raise F4Error("certificate_timer_active_before_enable")
        before_snapshot = _runtime_container_snapshot()
        before_certificate_identity = _certificate_identity_snapshot()
        _advance_transaction(
            "PERSISTENCE_ENABLED",
            certificate_timer_authorization_id=authorization_id,
            certificate_timer_authorization_claimed=True,
            certificate_timer_authorization_consumed=True,
            certificate_timer_authorization_replay_allowed=False,
            production_service_start=True,
            persistence_enabled=True,
            certificate_timer_enabled=False,
        )
        try:
            _run(("systemctl", "enable", CERT_TIMER), timeout=60)
            if _systemctl("is-enabled", CERT_TIMER) != "enabled":
                raise F4Error("certificate_timer_enable_failed")
            if _systemctl("is-active", CERT_TIMER) in {
                "active",
                "activating",
                "reloading",
            }:
                raise F4Error("certificate_timer_started_unexpectedly")
            runtime = _runtime_activity()
            if (
                runtime["production_service_start"] is not True
                or set(runtime["running_services"] or [])
                != {"broker", "manager", "homeassistant"}
                or _runtime_container_snapshot() != before_snapshot
                or _certificate_identity_snapshot()
                != before_certificate_identity
                or _systemctl("is-active", CERT_SERVICE)
                in {"active", "activating", "reloading"}
                or _sha256_file(CERT_STATUS_FILE)
                != transaction.get("certificate_status_sha256")
            ):
                raise F4Error("certificate_timer_runtime_changed")
            _validate_runtime_acceptance_binding(transaction)
            _advance_transaction(
                "PERSISTENCE_ENABLED",
                certificate_timer_enabled=True,
                certificate_timer_active_before_reboot=False,
                pre_reboot_ready=True,
                production_service_start=True,
                persistence_enabled=True,
            )
            return {
                "status": "PASS",
                "state": "PRE_REBOOT_READY",
                "pre_reboot_ready": True,
                "certificate_timer_enabled": True,
                "certificate_timer_active_before_reboot": False,
                "production_service_start": True,
                "board_access": False,
            }
        except OPERATION_ERRORS as error:
            try:
                _downstream_fail_closed("CERTIFICATE_TIMER", error)
            except OPERATION_ERRORS as rollback_error:
                raise F4Error(
                    "certificate_timer_failed_rollback_unproven:"
                    + type(rollback_error).__name__
                ) from error
            raise


def _status() -> dict[str, object]:
    transaction_present = TRANSACTION_PATH.exists() or TRANSACTION_PATH.is_symlink()
    factory_present = (
        FACTORY_ACCEPTED_PATH.exists() or FACTORY_ACCEPTED_PATH.is_symlink()
    )
    stage = "UNCLAIMED"
    if transaction_present:
        transaction = _read_private_record(TRANSACTION_PATH)
        stage = str(transaction.get("stage", "UNKNOWN"))
    runtime = _runtime_activity()
    return {
        "status": "PASS",
        "transaction_present": transaction_present,
        "factory_accepted_present": factory_present,
        "transaction_stage": stage,
        "broker_active_state": runtime["broker_active_state"],
        "services_active_state": runtime["services_active_state"],
        "runtime_service_probe": runtime["runtime_service_probe"],
        "running_services": runtime["running_services"],
        "production_service_start": runtime["production_service_start"],
        "board_access": False,
    }


def _public_audit(audit: dict[str, object]) -> dict[str, object]:
    return {
        "status": "PASS",
        "state": "DEVICE_READY",
        "release_id": audit["release_id"],
        "host_instance_id_sha256": _sha256_text(str(audit["host_instance_id"])),
        "system_id_sha256": audit["system_id_sha256"],
        "stopped_instance_audit": True,
        "activation_units_stopped": True,
        "activation_units_disabled": True,
        "factory_accepted_present": False,
        "production_service_start": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-f4-activation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("audit")

    eligibility = subparsers.add_parser("eligibility")
    eligibility.add_argument(
        "--phase",
        choices=("inspect", "broker", "services", "certificate"),
        default="inspect",
    )

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--confirm", required=True)
    prepare.add_argument("--authorization-id", required=True)
    prepare.add_argument("--package-root", required=True)
    prepare.add_argument("--package-manifest-sha256", required=True)
    prepare.add_argument("--package-source-head", required=True)

    repair = subparsers.add_parser("repair-prepared-control")
    repair.add_argument("--confirm", required=True)
    repair.add_argument("--authorization-id", required=True)
    repair.add_argument("--package-root", required=True)
    repair.add_argument("--package-manifest-sha256", required=True)
    repair.add_argument("--package-source-head", required=True)

    activation_authority_repair = subparsers.add_parser(
        "repair-prepared-activation-authority"
    )
    activation_authority_repair.add_argument("--confirm", required=True)
    activation_authority_repair.add_argument(
        "--authorization-id",
        required=True,
    )
    activation_authority_repair.add_argument("--package-root", required=True)
    activation_authority_repair.add_argument(
        "--package-manifest-sha256",
        required=True,
    )
    activation_authority_repair.add_argument(
        "--package-source-head",
        required=True,
    )

    runtime_continuation_repair = subparsers.add_parser(
        "repair-runtime-continuation-authority"
    )
    runtime_continuation_repair.add_argument("--confirm", required=True)
    runtime_continuation_repair.add_argument(
        "--authorization-id",
        required=True,
    )
    runtime_continuation_repair.add_argument("--package-root", required=True)
    runtime_continuation_repair.add_argument(
        "--package-manifest-sha256",
        required=True,
    )
    runtime_continuation_repair.add_argument(
        "--package-source-head",
        required=True,
    )

    runtime_start_repair = subparsers.add_parser(
        "repair-stopped-runtime-start"
    )
    runtime_start_repair.add_argument("--confirm", required=True)
    runtime_start_repair.add_argument("--authorization-id", required=True)
    runtime_start_repair.add_argument("--package-root", required=True)
    runtime_start_repair.add_argument(
        "--package-manifest-sha256",
        required=True,
    )
    runtime_start_repair.add_argument(
        "--package-source-head",
        required=True,
    )

    runtime_acceptance_recovery = subparsers.add_parser(
        "repair-stopped-runtime-acceptance"
    )
    runtime_acceptance_recovery.add_argument("--confirm", required=True)
    runtime_acceptance_recovery.add_argument(
        "--authorization-id",
        required=True,
    )
    runtime_acceptance_recovery.add_argument(
        "--package-root",
        required=True,
    )
    runtime_acceptance_recovery.add_argument(
        "--package-manifest-sha256",
        required=True,
    )
    runtime_acceptance_recovery.add_argument(
        "--package-source-head",
        required=True,
    )

    activate = subparsers.add_parser("activate")
    activate.add_argument("--confirm", required=True)
    activate.add_argument("--authorization-id", required=True)

    for command in (
        "accept-runtime",
        "enable-persistence",
        "certificate-audit",
        "enable-certificate-timer",
    ):
        item = subparsers.add_parser(command)
        item.add_argument("--authorization-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _require_root()
        if args.command == "status":
            report = _status()
        elif args.command == "audit":
            report = _public_audit(
                _factory_audit(require_claim_absent=True)
            )
        elif args.command == "eligibility":
            report = _activation_eligibility(args.phase)
        elif args.command == "prepare":
            report = _prepare(
                Path(args.package_root),
                args.confirm,
                args.authorization_id,
                args.package_manifest_sha256,
                args.package_source_head,
            )
        elif args.command == "repair-prepared-control":
            report = _repair_prepared_control(
                Path(args.package_root),
                args.confirm,
                args.authorization_id,
                args.package_manifest_sha256,
                args.package_source_head,
            )
        elif args.command == "repair-prepared-activation-authority":
            report = _repair_prepared_activation_authority(
                Path(args.package_root),
                args.confirm,
                args.authorization_id,
                args.package_manifest_sha256,
                args.package_source_head,
            )
        elif args.command == "repair-runtime-continuation-authority":
            report = _repair_runtime_continuation_authority(
                Path(args.package_root),
                args.confirm,
                args.authorization_id,
                args.package_manifest_sha256,
                args.package_source_head,
            )
        elif args.command == "repair-stopped-runtime-start":
            report = _repair_stopped_runtime_start(
                Path(args.package_root),
                args.confirm,
                args.authorization_id,
                args.package_manifest_sha256,
                args.package_source_head,
            )
        elif args.command == "repair-stopped-runtime-acceptance":
            report = _repair_stopped_runtime_acceptance(
                Path(args.package_root),
                args.confirm,
                args.authorization_id,
                args.package_manifest_sha256,
                args.package_source_head,
            )
        elif args.command == "activate":
            report = _activate(
                args.confirm,
                args.authorization_id,
            )
        elif args.command == "accept-runtime":
            report = _accept_runtime(args.authorization_id)
        elif args.command == "enable-persistence":
            report = _enable_persistence(args.authorization_id)
        elif args.command == "certificate-audit":
            report = _certificate_first_audit(args.authorization_id)
        else:
            report = _enable_certificate_timer(args.authorization_id)
        _emit({**report, "schema": SCHEMA})
        return 0
    except OPERATION_ERRORS as error:
        try:
            runtime = _runtime_activity()
        except OPERATION_ERRORS:
            runtime = {
                "production_service_start": None,
                "broker_active_state": "unknown",
                "services_active_state": "unknown",
                "runtime_service_probe": "UNPROVEN",
                "running_services": None,
            }
        _emit(
            {
                "schema": SCHEMA,
                "status": "FAIL",
                "error_code": str(error)[:400] or type(error).__name__,
                "production_service_start": runtime[
                    "production_service_start"
                ],
                "broker_active_state": runtime["broker_active_state"],
                "services_active_state": runtime["services_active_state"],
                "runtime_service_probe": runtime["runtime_service_probe"],
                "running_services": runtime["running_services"],
                "board_access": False,
            },
            error=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
