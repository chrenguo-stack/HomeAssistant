#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Sequence

SCHEMA = "gh.n3w-t1-f4-activation-host/1"
TRANSACTION_SCHEMA = "gh.n3w-t1-f4-activation-transaction/1"
FACTORY_ACCEPTED_SCHEMA = "gh.n3w.t1-factory-accepted/1"

PREPARE_CONFIRMATION = "PREPARE F4 ACTIVATION: YES"
ACTIVATE_CONFIRMATION = "START F4 ACTIVATION: YES"

PRODUCT_ROOT = Path("/opt/HomeAssistant")
RELEASE_PATH = PRODUCT_ROOT / "infra/n3w-t1/production/fresh-release.json"
LIVE_COMPOSE_SOURCE = PRODUCT_ROOT / "infra/n3w-t1/production/docker-compose.yml"
FRESH_TOOL_PATH = PRODUCT_ROOT / "tools/n3w_t1_fresh_product_bootstrap.py"
PROVISION_CLI = Path("/usr/local/sbin/n3w-t1-provision")

PROVISIONING_ROOT = Path("/var/lib/n3w-t1-provisioning")
FACTORY_ACCEPTED_PATH = PROVISIONING_ROOT / "FACTORY_ACCEPTED.json"
TRANSACTION_PATH = PROVISIONING_ROOT / "F4_ACTIVATION_TRANSACTION.json"

BROKER_UNIT = "n3wfc4-broker-activation.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
GUARD_UNIT = "n3wfc4-broker-ingress-guard.service"
PROVISION_UNIT = "n3wfc4-provision-resume.service"
CERT_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
CERT_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"

ETC_N3W = Path("/etc/n3wfc4")
BROKER_ENV = ETC_N3W / "broker-activation.env"
COMPOSE_TARGET = ETC_N3W / "docker-compose.yml"
CERT_ENV = ETC_N3W / "broker-certificate-lifecycle.env"
CERT_STATUS_ROOT = Path("/var/lib/n3wfc4-certificate-lifecycle")

CA_CERT = ETC_N3W / "tls/ca.pem"
SERVER_CERT = ETC_N3W / "tls/server.pem"
SERVER_KEY = ETC_N3W / "tls/server.key"
CA_KEY = Path("/opt/greenhouse-secrets/broker-ca/ca.key")
SYSTEM_CA = Path("/var/lib/greenhouse-manager/identity/system-ca.pem")
SERVER_NAME = "armbian"

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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def _transaction_document(audit: dict[str, object]) -> dict[str, object]:
    return {
        "schema": TRANSACTION_SCHEMA,
        "status": "CLAIMED",
        "stage": "CLAIMED",
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
    return document


def _activation_eligibility(phase: str) -> dict[str, object]:
    verified = _provision_verify()
    marker = _validate_factory_binding(verified)
    transaction = _validate_transaction_binding(verified)
    stage = str(transaction.get("stage", "UNKNOWN"))
    required = {
        "inspect": INSPECT_STAGES,
        "broker": frozenset({"BROKER_STARTING"}),
        "services": frozenset({"SERVICES_STARTING"}),
        "certificate": frozenset({"RUNTIME_ACCEPTED", "PERSISTENCE_ENABLED"}),
    }
    allowed = required.get(phase)
    if allowed is None:
        raise F4Error("eligibility_phase_invalid")
    if stage not in allowed:
        raise F4Error(f"f4_transaction_stage_not_eligible:{phase}:{stage}")
    return {
        "status": "PASS",
        "state": "FACTORY_ACCEPTED",
        "activation_eligible": True,
        "release_id": verified["release_id"],
        "factory_accepted": marker["factory_accepted"],
        "transaction_stage": stage,
        "eligibility_phase": phase,
        "production_service_start": False,
        "board_access": False,
    }


def _regular_source(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise F4Error(f"package_source_invalid:{path}")


def _atomic_install(source: Path, target: Path, mode: int) -> None:
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
    for path in (CA_CERT, SERVER_CERT, SERVER_KEY, CA_KEY, SYSTEM_CA):
        _regular_source(path)
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
        "N3WFC4_CERT_ALLOWED_ROOT_SECRET=/opt/greenhouse-secrets/broker-ca\n"
        "N3WFC4_CERT_ALLOWED_ROOT_SYSTEM=/var/lib/greenhouse-manager/identity\n"
    )


def _install_activation_material(package_root: Path) -> dict[str, object]:
    root = Path(os.path.abspath(os.fspath(package_root)))
    if root.is_symlink() or not root.is_dir():
        raise F4Error("package_root_invalid")
    _validate_tls_material()
    created: list[Path] = []
    status_root_created = False
    try:
        for relative, (target, mode) in INSTALL_MAP.items():
            _atomic_install(root / relative, target, mode)
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
        return {
            "status": "PASS",
            "activation_material_installed": True,
            "production_service_start": False,
            "persistence_enabled": False,
            "certificate_timer_enabled": False,
        }
    except Exception:
        for target in reversed(created):
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        if status_root_created:
            try:
                CERT_STATUS_ROOT.rmdir()
            except OSError:
                pass
        try:
            _run(("systemctl", "daemon-reload"), timeout=60)
        except Exception:
            pass
        raise


def _prepare(package_root: Path, confirmation: str) -> dict[str, object]:
    if confirmation != PREPARE_CONFIRMATION:
        raise F4Error("prepare_confirmation_invalid")
    audit = _factory_audit(require_claim_absent=True)
    _new_private_record(TRANSACTION_PATH, _transaction_document(audit))
    try:
        fresh = _factory_audit(require_claim_absent=False)
        for key in ("release_id", "host_instance_id", "system_id", "system_id_sha256"):
            if fresh.get(key) != audit.get(key):
                raise F4Error(f"factory_audit_binding_changed:{key}")
        _new_private_record(
            FACTORY_ACCEPTED_PATH,
            _factory_document(fresh),
        )
        install = _install_activation_material(package_root)
        _advance_transaction(
            "PREPARED",
            activation_material_installed=True,
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
            "authorization_claimed": True,
            "authorization_consumed": True,
            "replay_allowed": False,
            "production_service_start": False,
            "persistence_enabled": False,
            "board_access": False,
        }
    except Exception as error:
        try:
            _advance_transaction(
                "STOPPED_PREPARE",
                error_code=str(error)[:300],
                production_service_start=False,
                persistence_enabled=False,
            )
        except Exception:
            pass
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


def _activate(confirmation: str) -> dict[str, object]:
    if confirmation != ACTIVATE_CONFIRMATION:
        raise F4Error("activate_confirmation_invalid")
    eligible = _activation_eligibility("inspect")
    if eligible.get("transaction_stage") != "PREPARED":
        raise F4Error("activation_replay_forbidden")
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
        running = _running_services()
        if running != frozenset({"broker", "manager", "homeassistant"}):
            raise F4Error("runtime_service_set_invalid")
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
            "broker_ready": True,
            "runtime_services": sorted(running),
            "runtime_acceptance_required": True,
            "production_service_start": True,
            "persistence_enabled": False,
            "certificate_timer_enabled": False,
            "board_access": False,
        }
    except Exception as error:
        if services_attempted:
            try:
                _run(("systemctl", "stop", SERVICES_UNIT), timeout=120)
            except Exception:
                pass
        if broker_attempted:
            try:
                _run(("systemctl", "stop", BROKER_UNIT), timeout=120)
            except Exception:
                pass
        try:
            _advance_transaction(
                "STOPPED_RUNTIME",
                error_code=str(error)[:300],
                production_service_start=False,
                persistence_enabled=False,
            )
        except Exception:
            pass
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
    return {
        "status": "PASS",
        "transaction_present": transaction_present,
        "factory_accepted_present": factory_present,
        "transaction_stage": stage,
        "production_service_start": False,
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
    prepare.add_argument(
        "--package-root",
        default=str(PRODUCT_ROOT),
    )

    activate = subparsers.add_parser("activate")
    activate.add_argument("--confirm", required=True)
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
            )
        else:
            report = _activate(args.confirm)
        _emit({**report, "schema": SCHEMA})
        return 0
    except (
        F4Error,
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as error:
        _emit(
            {
                "schema": SCHEMA,
                "status": "FAIL",
                "error_code": str(error)[:400] or type(error).__name__,
                "production_service_start": False,
                "board_access": False,
            },
            error=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
