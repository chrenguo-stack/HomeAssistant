#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

SCHEMA = "gh.n3w-t1-clean-reference-r2a/1"
PACKAGE_SCHEMA = "gh.n3w-t1-clean-reference-r2a-package/1"
TRANSACTION_SCHEMA = "gh.n3w-t1-clean-reference-r2a-transaction/1"

PRODUCT_SOURCE_HEAD = "24382caae4a1f5d459297f86e8d18f10a848ca64"
CONFIRMATION = "START N3W T1 CLEAN REFERENCE R2A: YES"
AUTHORIZATION_PREFIX = "N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2A_"

PRODUCT_ROOT = Path("/opt/HomeAssistant")
RELEASE_PATH = PRODUCT_ROOT / "infra/n3w-t1/production/fresh-release.json"
LIVE_COMPOSE_SOURCE = PRODUCT_ROOT / "infra/n3w-t1/production/docker-compose.yml"

ETC_N3W = Path("/etc/n3wfc4")
COMPOSE_TARGET = ETC_N3W / "docker-compose.yml"
COMPOSE_ENV = ETC_N3W / "docker-compose.env"
BROKER_ENV = ETC_N3W / "broker-activation.env"
CERT_ENV = ETC_N3W / "broker-certificate-lifecycle.env"

CA_CERT = ETC_N3W / "tls/ca.pem"
SERVER_CERT = ETC_N3W / "tls/server.pem"
SERVER_KEY = ETC_N3W / "tls/server.key"
CA_KEY = Path("/opt/greenhouse-secrets/broker-ca/ca.key")
SYSTEM_CA = Path("/var/lib/greenhouse-manager/identity/system-ca.pem")
CERT_STATUS_ROOT = Path("/var/lib/n3wfc4-certificate-lifecycle")

TRANSACTION_ROOT = Path("/var/lib/n3w-t1-clean-reference-r2a")
TRANSACTION_PATH = TRANSACTION_ROOT / "transaction.json"

BROKER_UNIT = "n3wfc4-broker-activation.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
CERT_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
CERT_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"
GUARD_UNIT = "n3wfc4-broker-ingress-guard.service"
REGISTRATION_GUARD_UNIT = "n3wfc4-registration-ingress-guard.service"
PROVISION_UNIT = "n3wfc4-provision-resume.service"

EXPECTED_RUNTIME_SERVICES = frozenset({"broker", "manager", "homeassistant"})
DEFAULT_NETWORKS = frozenset({"bridge", "host", "none"})
TARGET_PORTS = frozenset({1883, 8883, 18883, 8123, 47110, 47111, 47112})

INSTALL_MAP = {
    "tools/n3w_t1_clean_reference_r2a.py": (
        Path("/usr/local/sbin/n3w-t1-clean-reference-r2a"),
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
    "infra/n3w-t1/clean-reference/n3wfc4-broker-activation.service": (
        Path("/etc/systemd/system/n3wfc4-broker-activation.service"),
        0o644,
    ),
    "infra/n3w-t1/clean-reference/n3wfc4-services-activation.service": (
        Path("/etc/systemd/system/n3wfc4-services-activation.service"),
        0o644,
    ),
    "infra/n3w-t1/clean-reference/n3wfc4-broker-certificate-lifecycle.service": (
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

GENERATED_TARGETS = (
    COMPOSE_TARGET,
    BROKER_ENV,
    CERT_ENV,
)

class R2AError(RuntimeError):
    pass


def _emit(document: dict[str, object], *, error: bool = False) -> None:
    stream = sys.stderr if error else sys.stdout
    stream.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")


def _run(
    argv: Sequence[str],
    *,
    timeout: float = 180.0,
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
        raise R2AError(
            f"command_failed:{Path(argv[0]).name}:{completed.returncode}:{reason[:300]}"
        )
    return completed.stdout


def _systemctl(mode: str, unit: str) -> str:
    completed = subprocess.run(
        ("systemctl", mode, unit),
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
    )
    return completed.stdout.strip() or "unknown"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise R2AError(f"json_file_invalid:{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise R2AError(f"json_file_invalid:{path}") from error
    if not isinstance(value, dict):
        raise R2AError(f"json_file_invalid:{path}")
    return value


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise R2AError("transaction_parent_symlink")
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.chown(temporary, 0, 0)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _transaction() -> dict[str, object]:
    value = _read_json(TRANSACTION_PATH)
    if value.get("schema") != TRANSACTION_SCHEMA:
        raise R2AError("transaction_schema_invalid")
    return value


def _advance(stage: str, **fields: object) -> dict[str, object]:
    current = _transaction()
    current.update(fields)
    current["stage"] = stage
    _atomic_json(TRANSACTION_PATH, current)
    return current


def _package(root: Path) -> dict[str, object]:
    manifest_path = root / "package-manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("schema") != PACKAGE_SCHEMA:
        raise R2AError("package_schema_invalid")
    if manifest.get("product_source_head") != PRODUCT_SOURCE_HEAD:
        raise R2AError("package_product_source_invalid")
    control_head = manifest.get("control_plane_head")
    if not isinstance(control_head, str) or re.fullmatch(r"[0-9a-f]{40}", control_head) is None:
        raise R2AError("package_control_head_invalid")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise R2AError("package_files_invalid")
    expected: dict[str, dict[str, object]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise R2AError("package_file_record_invalid")
        relative = record.get("path")
        digest = record.get("sha256")
        size = record.get("size")
        mode = record.get("mode")
        if (
            not isinstance(relative, str)
            or relative not in INSTALL_MAP
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(mode, int)
            or mode != INSTALL_MAP[relative][1]
        ):
            raise R2AError("package_file_record_invalid")
        expected[relative] = record
    if set(expected) != set(INSTALL_MAP):
        raise R2AError("package_file_set_invalid")
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item != manifest_path
    }
    if actual != set(expected):
        raise R2AError("package_actual_file_set_invalid")
    for relative, record in expected.items():
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise R2AError(f"package_file_invalid:{relative}")
        if path.stat().st_size != record["size"] or _sha256_file(path) != record["sha256"]:
            raise R2AError(f"package_file_binding_invalid:{relative}")
    return manifest


def _listeners() -> list[int]:
    output = _run(("ss", "-H", "-lntu"), timeout=30)
    ports: set[int] = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        local = fields[4]
        try:
            port = int(local.rsplit(":", 1)[1].rstrip("]"))
        except (IndexError, ValueError):
            continue
        if port in TARGET_PORTS:
            ports.add(port)
    return sorted(ports)


def _validate_tls_material() -> None:
    expected = {
        CA_CERT: (0, 0, 0o644),
        SERVER_CERT: (0, 0, 0o644),
        SERVER_KEY: (1883, 1883, 0o600),
        CA_KEY: (0, 0, 0o600),
        SYSTEM_CA: (0, 0, 0o600),
    }
    for path, (uid, gid, mode) in expected.items():
        if path.is_symlink() or not path.is_file():
            raise R2AError(f"tls_material_missing:{path.name}")
        metadata = path.stat()
        if (
            metadata.st_uid != uid
            or metadata.st_gid != gid
            or stat.S_IMODE(metadata.st_mode) != mode
            or metadata.st_nlink != 1
        ):
            raise R2AError(f"tls_material_metadata_invalid:{path.name}")
    cert_pub = _run(("openssl", "x509", "-in", str(CA_CERT), "-pubkey", "-noout"))
    key_pub = _run(("openssl", "pkey", "-in", str(CA_KEY), "-pubout"))
    if cert_pub != key_pub:
        raise R2AError("broker_ca_key_mismatch")
    server_pub = _run(("openssl", "x509", "-in", str(SERVER_CERT), "-pubkey", "-noout"))
    server_key_pub = _run(("openssl", "pkey", "-in", str(SERVER_KEY), "-pubout"))
    if server_pub != server_key_pub:
        raise R2AError("broker_server_key_mismatch")
    _run(
        (
            "openssl",
            "verify",
            "-CAfile",
            str(CA_CERT),
            "-verify_hostname",
            "armbian",
            str(SERVER_CERT),
        )
    )


def _r1_preflight() -> dict[str, object]:
    if TRANSACTION_ROOT.exists() or TRANSACTION_ROOT.is_symlink():
        raise R2AError("r2a_transaction_state_present")
    release = _read_json(RELEASE_PATH)
    if (
        release.get("schema") != "gh.n3w-t1-fresh-release/1"
        or release.get("source_head") != PRODUCT_SOURCE_HEAD
        or release.get("production_service_start") is not False
    ):
        raise R2AError("r1_release_binding_invalid")
    if _run(("docker", "ps", "-aq")).strip():
        raise R2AError("r1_container_present")
    if _run(("docker", "volume", "ls", "-q")).strip():
        raise R2AError("r1_volume_present")
    networks = frozenset(
        line.strip()
        for line in _run(("docker", "network", "ls", "--format", "{{.Name}}")).splitlines()
        if line.strip()
    )
    if networks != DEFAULT_NETWORKS:
        raise R2AError("r1_network_set_invalid")
    images = {
        line.strip()
        for line in _run(("docker", "image", "ls", "--no-trunc", "-q")).splitlines()
        if line.strip()
    }
    if len(images) != 3:
        raise R2AError("r1_image_count_invalid")
    for image in (
        "local/greenhouse-manager:fresh-24382caae4a1",
        "local/n3w-homeassistant:2026.10.0-0c73235a",
        "local/n3w-mosquitto:2.1.2-3184566d",
    ):
        _run(("docker", "image", "inspect", image))
    for unit in (GUARD_UNIT, REGISTRATION_GUARD_UNIT, PROVISION_UNIT):
        if _systemctl("is-enabled", unit) != "enabled":
            raise R2AError(f"r1_staged_unit_not_enabled:{unit}")
        if _systemctl("is-active", unit) == "active":
            raise R2AError(f"r1_staged_unit_active:{unit}")
    for relative, (target, _mode) in INSTALL_MAP.items():
        if target.exists() or target.is_symlink():
            raise R2AError(f"activation_target_exists:{relative}")
    for target in GENERATED_TARGETS:
        if target.exists() or target.is_symlink():
            raise R2AError(f"activation_generated_target_exists:{target.name}")
    if CERT_STATUS_ROOT.exists() or CERT_STATUS_ROOT.is_symlink():
        raise R2AError("certificate_status_root_exists")
    if _listeners():
        raise R2AError("r1_product_listener_present")
    if LIVE_COMPOSE_SOURCE.is_symlink() or not LIVE_COMPOSE_SOURCE.is_file():
        raise R2AError("live_compose_source_invalid")
    _validate_tls_material()
    return {
        "status": "PASS",
        "source_head": PRODUCT_SOURCE_HEAD,
        "image_count": 3,
        "container_count": 0,
        "volume_count": 0,
        "product_listener_count": 0,
        "staged_units_enabled": True,
        "staged_units_active": False,
    }


def _atomic_install(source: Path, target: Path, mode: int) -> None:
    if source.is_symlink() or not source.is_file():
        raise R2AError(f"install_source_invalid:{source}")
    if target.exists() or target.is_symlink():
        raise R2AError(f"install_target_exists:{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.parent.is_symlink():
        raise R2AError(f"install_parent_invalid:{target.parent}")
    temporary = target.parent / f".{target.name}.{os.getpid()}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    installed = False
    try:
        with source.open("rb") as input_stream, os.fdopen(descriptor, "wb") as output_stream:
            descriptor = -1
            shutil.copyfileobj(input_stream, output_stream)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.chmod(temporary, mode)
        os.chown(temporary, 0, 0)
        os.link(temporary, target, follow_symlinks=False)
        temporary.unlink()
        installed = True
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if not installed:
            temporary.unlink(missing_ok=True)


def _write_new(path: Path, payload: str, mode: int) -> None:
    temporary_source = path.parent / f".{path.name}.{os.getpid()}.source"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_source.write_text(payload, encoding="utf-8")
    os.chmod(temporary_source, mode)
    try:
        _atomic_install(temporary_source, path, mode)
    finally:
        temporary_source.unlink(missing_ok=True)


def _broker_env_payload() -> str:
    return (
        "N3WFC4_COMPOSE_FILE=/etc/n3wfc4/docker-compose.yml\n"
        "N3WFC4_COMPOSE_ENV_FILE=/etc/n3wfc4/docker-compose.env\n"
        "N3WFC4_COMPOSE_PROJECT_NAME=n3wfc4\n"
    )


def _certificate_env_payload() -> str:
    return (
        "N3WFC4_CERT_SERVER_CERT_FILE=/etc/n3wfc4/tls/server.pem\n"
        "N3WFC4_CERT_SERVER_KEY_FILE=/etc/n3wfc4/tls/server.key\n"
        "N3WFC4_CERT_CA_CERT_FILE=/etc/n3wfc4/tls/ca.pem\n"
        "N3WFC4_CERT_CA_KEY_FILE=/opt/greenhouse-secrets/broker-ca/ca.key\n"
        "N3WFC4_CERT_SYSTEM_CA_FILE=/var/lib/greenhouse-manager/identity/system-ca.pem\n"
        "N3WFC4_CERT_SERVER_NAME=armbian\n"
        "N3WFC4_CERT_STATUS_FILE=/var/lib/n3wfc4-certificate-lifecycle/status.json\n"
        "N3WFC4_CERT_ALLOWED_ROOT_FC4=/etc/n3wfc4\n"
        "N3WFC4_CERT_ALLOWED_ROOT_BROKER_CA=/opt/greenhouse-secrets/broker-ca\n"
        "N3WFC4_CERT_ALLOWED_ROOT_SYSTEM=/var/lib/greenhouse-manager/identity\n"
    )


def _file_binding(path: Path) -> dict[str, object]:
    metadata = path.stat()
    return {
        "sha256": _sha256_file(path),
        "size": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
        "gid": metadata.st_gid,
    }


def _install_material(root: Path, manifest: dict[str, object]) -> dict[str, object]:
    created: list[Path] = []
    status_root_created = False
    try:
        records = {
            str(item["path"]): item
            for item in manifest["files"]
            if isinstance(item, dict)
        }
        for relative, (target, mode) in INSTALL_MAP.items():
            record = records[relative]
            source = root / relative
            if source.stat().st_size != record["size"] or _sha256_file(source) != record["sha256"]:
                raise R2AError(f"install_source_binding_invalid:{relative}")
            _atomic_install(source, target, mode)
            created.append(target)
        _atomic_install(LIVE_COMPOSE_SOURCE, COMPOSE_TARGET, 0o644)
        created.append(COMPOSE_TARGET)
        _write_new(BROKER_ENV, _broker_env_payload(), 0o600)
        created.append(BROKER_ENV)
        _write_new(CERT_ENV, _certificate_env_payload(), 0o600)
        created.append(CERT_ENV)
        CERT_STATUS_ROOT.mkdir(mode=0o700)
        os.chown(CERT_STATUS_ROOT, 0, 0)
        os.chmod(CERT_STATUS_ROOT, 0o700)
        status_root_created = True
        _run(("systemctl", "daemon-reload"), timeout=60)
        for unit in (BROKER_UNIT, SERVICES_UNIT, CERT_SERVICE, CERT_TIMER):
            if _systemctl("is-active", unit) in {"active", "activating", "reloading"}:
                raise R2AError(f"installed_unit_active:{unit}")
            if _systemctl("is-enabled", unit) == "enabled":
                raise R2AError(f"installed_unit_enabled:{unit}")
        installed = {str(path): _file_binding(path) for path in created}
        return {"status": "PASS", "installed_files": installed}
    except Exception as error:
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
        except Exception as cleanup_error:
            cleanup_errors.append(type(cleanup_error).__name__)
        if cleanup_errors:
            raise R2AError(
                "activation_install_failed_cleanup_unproven:" + ",".join(cleanup_errors)
            ) from error
        raise


def _enable_persistence() -> None:
    _run(("systemctl", "enable", BROKER_UNIT, SERVICES_UNIT, CERT_TIMER), timeout=60)
    for unit in (BROKER_UNIT, SERVICES_UNIT, CERT_TIMER):
        if _systemctl("is-enabled", unit) != "enabled":
            raise R2AError(f"activation_enable_failed:{unit}")
    if _systemctl("is-active", CERT_TIMER) == "active":
        raise R2AError("certificate_timer_started_unexpectedly")


def _running_services() -> frozenset[str]:
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
    return frozenset(line.strip() for line in output.splitlines() if line.strip())


def _wait_for_runtime_services(timeout_seconds: float = 90.0) -> frozenset[str]:
    deadline = time.monotonic() + timeout_seconds
    observed: frozenset[str] = frozenset()
    while True:
        observed = _running_services()
        if observed == EXPECTED_RUNTIME_SERVICES:
            return observed
        if observed - EXPECTED_RUNTIME_SERVICES:
            raise R2AError("runtime_service_set_unexpected")
        if time.monotonic() >= deadline:
            raise R2AError(
                "runtime_service_set_timeout:" + ",".join(sorted(observed))
            )
        time.sleep(1.0)


def _rollback_runtime() -> dict[str, object]:
    errors: list[str] = []
    for unit in (SERVICES_UNIT, BROKER_UNIT, REGISTRATION_GUARD_UNIT, GUARD_UNIT):
        try:
            _run(("systemctl", "stop", unit), timeout=120, allowed=frozenset({0, 5}))
        except Exception:
            errors.append(f"stop:{unit}")
    if COMPOSE_TARGET.is_file() and COMPOSE_ENV.is_file():
        try:
            _run(
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
                    "down",
                    "--remove-orphans",
                ),
                timeout=180,
            )
        except Exception:
            errors.append("compose_down")
    try:
        _run(
            ("systemctl", "disable", BROKER_UNIT, SERVICES_UNIT, CERT_TIMER),
            timeout=60,
            allowed=frozenset({0, 1}),
        )
    except Exception:
        errors.append("disable")
    try:
        containers = _run(("docker", "ps", "-aq")).strip()
        networks = frozenset(
            line.strip()
            for line in _run(("docker", "network", "ls", "--format", "{{.Name}}")).splitlines()
            if line.strip()
        )
        listeners = _listeners()
        safe = (
            not containers
            and networks == DEFAULT_NETWORKS
            and not listeners
            and all(_systemctl("is-enabled", unit) != "enabled" for unit in (BROKER_UNIT, SERVICES_UNIT, CERT_TIMER))
        )
    except Exception:
        safe = False
    return {
        "rollback_proven": safe and not errors,
        "rollback_error_count": len(errors),
        "rollback_errors": errors,
    }


def execute_apply(root: Path, confirmation: str, authorization_id: str) -> dict[str, object]:
    if confirmation != CONFIRMATION:
        raise R2AError("confirmation_invalid")
    if (
        not authorization_id.startswith(AUTHORIZATION_PREFIX)
        or len(authorization_id) > 200
        or not authorization_id.replace("_", "").replace("-", "").isalnum()
    ):
        raise R2AError("authorization_id_invalid")
    manifest = _package(root)
    preflight = _r1_preflight()
    TRANSACTION_ROOT.mkdir(mode=0o700)
    os.chown(TRANSACTION_ROOT, 0, 0)
    os.chmod(TRANSACTION_ROOT, 0o700)
    transaction = {
        "schema": TRANSACTION_SCHEMA,
        "stage": "CLAIMED",
        "authorization_id": authorization_id,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_replay_allowed": False,
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "control_plane_head": manifest["control_plane_head"],
        "production_service_start": False,
        "persistence_enabled": False,
        "certificate_timer_enabled": False,
        "board_access": False,
    }
    _atomic_json(TRANSACTION_PATH, transaction)
    try:
        install = _install_material(root, manifest)
        _advance(
            "MATERIAL_INSTALLED",
            installed_files=install["installed_files"],
            production_service_start=False,
            persistence_enabled=False,
        )
        _enable_persistence()
        _advance(
            "PERSISTENCE_ENABLED",
            production_service_start=False,
            persistence_enabled=True,
            certificate_timer_enabled=True,
        )
        _run(("systemctl", "start", GUARD_UNIT), timeout=60)
        if _systemctl("is-active", GUARD_UNIT) != "active":
            raise R2AError("ingress_guard_not_active")
        _advance("BROKER_STARTING", production_service_start=False)
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
        _advance("BROKER_READY", broker_ready=True, production_service_start=True)
        _advance("SERVICES_STARTING", production_service_start=True)
        _run(("systemctl", "start", SERVICES_UNIT), timeout=240)
        if _systemctl("is-active", SERVICES_UNIT) != "active":
            raise R2AError("application_services_not_active")
        running = _wait_for_runtime_services()
        if _systemctl("is-active", BROKER_UNIT) != "active":
            raise R2AError("broker_unit_not_active")
        if _systemctl("is-active", REGISTRATION_GUARD_UNIT) != "active":
            raise R2AError("registration_guard_not_active")
        if _systemctl("is-enabled", CERT_TIMER) != "enabled":
            raise R2AError("certificate_timer_not_enabled")
        if _systemctl("is-active", CERT_TIMER) == "active":
            raise R2AError("certificate_timer_active_before_reboot")
        _advance(
            "RUNTIME_STARTED",
            broker_ready=True,
            runtime_services=sorted(running),
            runtime_started=True,
            production_service_start=True,
            persistence_enabled=True,
            certificate_timer_enabled=True,
            pre_reboot_ready=True,
        )
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "state": "RUNTIME_STARTED",
            "authorization_id": authorization_id,
            "product_source_head": PRODUCT_SOURCE_HEAD,
            "control_plane_head": manifest["control_plane_head"],
            "r1_preflight": preflight,
            "runtime_services": sorted(running),
            "broker_ready": True,
            "production_service_start": True,
            "persistence_enabled": True,
            "certificate_timer_enabled": True,
            "certificate_timer_active_before_reboot": False,
            "pre_reboot_ready": True,
            "board_access": False,
        }
    except Exception as error:
        rollback = _rollback_runtime()
        try:
            _advance(
                "STOPPED_ROLLED_BACK" if rollback["rollback_proven"] else "STOPPED_ROLLBACK_UNPROVEN",
                error_code=str(error)[:300],
                production_service_start=False if rollback["rollback_proven"] else None,
                rollback_proven=rollback["rollback_proven"],
                rollback_error_count=rollback["rollback_error_count"],
                rollback_errors=rollback["rollback_errors"],
            )
        except Exception as record_error:
            raise R2AError(
                "r2a_failed_stop_record_unproven:" + type(record_error).__name__
            ) from error
        raise


def eligibility(phase: str) -> dict[str, object]:
    current = _transaction()
    stage = str(current.get("stage"))
    if current.get("authorization_consumed") is not True:
        raise R2AError("authorization_state_invalid")
    if phase == "broker":
        if stage not in {"BROKER_STARTING", "BROKER_READY", "SERVICES_STARTING", "RUNTIME_STARTED"}:
            raise R2AError("broker_eligibility_stage_invalid")
    elif phase == "services":
        if stage not in {"SERVICES_STARTING", "RUNTIME_STARTED"}:
            raise R2AError("services_eligibility_stage_invalid")
        if _systemctl("is-active", BROKER_UNIT) != "active":
            raise R2AError("services_broker_not_active")
    elif phase == "certificate":
        if stage != "RUNTIME_STARTED":
            raise R2AError("certificate_eligibility_stage_invalid")
        if current.get("persistence_enabled") is not True:
            raise R2AError("certificate_persistence_not_enabled")
        if _systemctl("is-active", BROKER_UNIT) != "active":
            raise R2AError("certificate_broker_not_active")
    else:
        raise R2AError("eligibility_phase_invalid")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "phase": phase,
        "transaction_stage": stage,
        "board_access": False,
    }


def status() -> dict[str, object]:
    present = TRANSACTION_PATH.is_file() and not TRANSACTION_PATH.is_symlink()
    transaction = _transaction() if present else None
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "transaction_present": present,
        "transaction_stage": transaction.get("stage") if transaction else "UNCLAIMED",
        "broker_active": _systemctl("is-active", BROKER_UNIT),
        "services_active": _systemctl("is-active", SERVICES_UNIT),
        "certificate_timer_enabled": _systemctl("is-enabled", CERT_TIMER),
        "production_service_start": (
            bool(_running_services()) if present and COMPOSE_TARGET.is_file() and COMPOSE_ENV.is_file() else False
        ),
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-clean-reference-r2a")
    sub = parser.add_subparsers(dest="command", required=True)
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--package-root", required=True)
    apply_parser.add_argument("--confirm", required=True)
    apply_parser.add_argument("--authorization-id", required=True)
    eligibility_parser = sub.add_parser("eligibility")
    eligibility_parser.add_argument(
        "--phase",
        choices=("broker", "services", "certificate"),
        required=True,
    )
    sub.add_parser("status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "apply":
            report = execute_apply(
                Path(os.path.abspath(args.package_root)),
                args.confirm,
                args.authorization_id,
            )
        elif args.command == "eligibility":
            report = eligibility(args.phase)
        else:
            report = status()
    except (R2AError, OSError, subprocess.SubprocessError, ValueError) as error:
        _emit(
            {
                "schema": SCHEMA,
                "status": "STOP",
                "reason": str(error)[:300],
                "production_service_start": None,
                "board_access": False,
            },
            error=True,
        )
        return 2
    _emit(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
