#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Sequence

SCHEMA = "gh.n3w-broker-certificate-lifecycle-install/1"
LIFECYCLE_BLOB = "65187b27a2ddd8f57221500a7019486e02bca101"
SERVICE_BLOB = "fa13967ef0ffb0a271fcb7122febd83b83079deb"
TIMER_BLOB = "65b0365c5ea5f5d3c896a133adc0d689bb2deced"
PREFLIGHT_BLOB = "8f3a09fee5cdad1d60dd76406e3dd03c7aa510ed"

LIFECYCLE_TARGET = Path("/usr/local/sbin/n3w-broker-certificate-lifecycle")
SERVICE_TARGET = Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service")
TIMER_TARGET = Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer")
ENV_TARGET = Path("/etc/n3wfc4/broker-certificate-lifecycle.env")
STATUS_DIR = Path("/var/lib/n3wfc4-certificate-lifecycle")
STATUS_FILE = STATUS_DIR / "status.json"

EXPECTED_GUARD_UNIT = "n3wfc4-broker-ingress-guard.service"
EXPECTED_ACTIVATION_UNIT = "n3wfc4-broker-activation.service"
LIFECYCLE_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
LIFECYCLE_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"


class InstallError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _progress(stage: str, **fields: object) -> None:
    print(
        "KF100_INSTALL " + json.dumps({"stage": stage, **fields}, sort_keys=True, separators=(",", ":")),
        file=sys.stderr,
        flush=True,
    )


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _require_source(path: Path, expected_blob: str) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    if not absolute.is_file() or absolute.is_symlink():
        raise InstallError("source_file_invalid")
    if _git_blob_sha1(absolute) != expected_blob:
        raise InstallError("source_blob_mismatch")
    return absolute


def _load_preflight(path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location("kf100_install_preflight", path)
    if specification is None or specification.loader is None:
        raise InstallError("preflight_import_failed")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _run(argv: Sequence[str], *, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            list(argv),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InstallError("command_unavailable") from error
    if result.returncode != 0:
        raise InstallError("command_failed")
    return result.stdout


def _systemctl_state(mode: str, unit: str) -> str:
    if mode not in {"is-active", "is-enabled"}:
        raise InstallError("systemctl_state_mode_invalid")
    try:
        result = subprocess.run(
            ("systemctl", mode, unit),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InstallError("systemctl_unavailable") from error
    return result.stdout.strip() or "unknown"


def _systemctl_daemon_reload() -> None:
    _run(("systemctl", "daemon-reload"), timeout=30)


def _env_quote(value: str) -> str:
    if "\n" in value or "\r" in value or "\x00" in value:
        raise InstallError("environment_value_invalid")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _write_atomic(path: Path, payload: bytes, mode: int) -> None:
    parent = path.parent
    temporary = parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    replaced = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.chown(temporary, 0, 0)
        os.replace(temporary, path)
        replaced = True
        directory = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        temporary.unlink(missing_ok=True)
        if replaced:
            path.unlink(missing_ok=True)
        raise


def _copy_atomic(source: Path, target: Path, mode: int) -> None:
    _write_atomic(target, source.read_bytes(), mode)


def _private_key_match(preflight: ModuleType, ca_cert: Path) -> tuple[Path, Path]:
    roots = preflight._search_roots(ca_cert)
    files, _skipped = preflight._walk_files(
        roots,
        max_files=preflight.DEFAULT_MAX_FILES,
        max_depth=preflight.DEFAULT_MAX_DEPTH,
    )
    candidates = [
        (index, path)
        for index, path in files
        if preflight._looks_like_private_key(path)
    ]
    ca_public = preflight._certificate_public_key_der(ca_cert)
    matches: list[tuple[int, Path]] = []
    for index, path in candidates:
        public = preflight._private_public_key_der(path)
        if public is not None and public == ca_public:
            matches.append((index, path))
    if len(matches) != 1:
        raise InstallError("ca_private_key_not_unique")
    index, key = matches[0]
    root = roots[index]
    uid, _gid, safe, _mode = preflight._key_mode(key)
    if uid != 0 or not safe:
        raise InstallError("ca_private_key_permissions_invalid")
    return key, root


def _container_identity(preflight: ModuleType) -> tuple[str, str]:
    container = preflight._broker_container()
    inspect = preflight._broker_inspect(container)
    state = inspect.get("State")
    if not isinstance(state, dict):
        raise InstallError("broker_state_invalid")
    started = state.get("StartedAt")
    if not isinstance(started, str) or not started:
        raise InstallError("broker_started_at_missing")
    return container, started


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _owner_mode(path: Path) -> tuple[int, int, int]:
    file_stat = path.stat()
    return (
        file_stat.st_uid,
        file_stat.st_gid,
        stat.S_IMODE(file_stat.st_mode),
    )


def _rollback(created: list[Path], status_created: bool) -> bool:
    ok = True
    for path in reversed(created):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            ok = False
    if status_created:
        try:
            STATUS_DIR.rmdir()
        except OSError:
            ok = False
    try:
        _systemctl_daemon_reload()
    except Exception:
        ok = False
    return ok


def install(
    lifecycle_source: Path,
    service_source: Path,
    timer_source: Path,
    preflight_source: Path,
) -> tuple[dict[str, object], int]:
    if os.geteuid() != 0:
        raise InstallError("root_required")

    lifecycle_source = _require_source(lifecycle_source, LIFECYCLE_BLOB)
    service_source = _require_source(service_source, SERVICE_BLOB)
    timer_source = _require_source(timer_source, TIMER_BLOB)
    preflight_source = _require_source(preflight_source, PREFLIGHT_BLOB)

    _progress("run_fresh_readonly_preflight")
    preflight = _load_preflight(preflight_source)
    preflight_doc = preflight.preflight(
        max_files=preflight.DEFAULT_MAX_FILES,
        max_depth=preflight.DEFAULT_MAX_DEPTH,
    )
    if preflight_doc.get("result") != "PASS":
        raise InstallError("fresh_preflight_not_pass")

    if STATUS_DIR.exists():
        raise InstallError("status_authority_already_present")

    broker_before, started_before = _container_identity(preflight)
    inspect = preflight._broker_inspect(broker_before)
    ca_cert = preflight._mount_source(inspect, "/mosquitto/tls/ca.pem", require_read_only=True)
    server_cert = preflight._mount_source(inspect, "/mosquitto/tls/server.pem", require_read_only=True)
    server_key = preflight._mount_source(inspect, "/mosquitto/tls/server.key", require_read_only=True)
    ca_key, ca_key_root = _private_key_match(preflight, ca_cert)
    fc4_root = preflight._persistent_root(ca_cert)
    if fc4_root not in ca_key.parents and ca_key != fc4_root:
        raise InstallError("ca_private_key_outside_persistent_root")
    if ca_key_root != fc4_root:
        raise InstallError("ca_private_key_authority_root_drift")

    system_ca = preflight.SYSTEM_CA_PATH
    system_root = system_ca.parent
    if not system_ca.is_file() or system_ca.is_symlink():
        raise InstallError("system_ca_invalid")

    for target in (LIFECYCLE_TARGET, SERVICE_TARGET, TIMER_TARGET, ENV_TARGET):
        if target.exists() or target.is_symlink():
            raise InstallError("deployment_target_already_present")

    if _systemctl_state("is-active", LIFECYCLE_TIMER) == "active":
        raise InstallError("timer_already_active")
    if _systemctl_state("is-enabled", LIFECYCLE_TIMER) == "enabled":
        raise InstallError("timer_already_enabled")

    server_cert_sha = _hash_file(server_cert)
    server_key_sha = _hash_file(server_key)
    ca_cert_sha = _hash_file(ca_cert)

    created: list[Path] = []
    status_created = False
    try:
        _progress("install_files")
        if not ENV_TARGET.parent.is_dir() or ENV_TARGET.parent.is_symlink():
            raise InstallError("environment_parent_invalid")
        env_parent_stat = ENV_TARGET.parent.stat()
        if env_parent_stat.st_uid != 0 or env_parent_stat.st_gid != 0:
            raise InstallError("environment_parent_owner_invalid")

        STATUS_DIR.mkdir(mode=0o700)
        status_created = True
        os.chown(STATUS_DIR, 0, 0)
        os.chmod(STATUS_DIR, 0o700)

        _copy_atomic(lifecycle_source, LIFECYCLE_TARGET, 0o755)
        created.append(LIFECYCLE_TARGET)
        _copy_atomic(service_source, SERVICE_TARGET, 0o644)
        created.append(SERVICE_TARGET)
        _copy_atomic(timer_source, TIMER_TARGET, 0o644)
        created.append(TIMER_TARGET)

        env_lines = (
            ("N3WFC4_CERT_SERVER_CERT_FILE", str(server_cert)),
            ("N3WFC4_CERT_SERVER_KEY_FILE", str(server_key)),
            ("N3WFC4_CERT_CA_CERT_FILE", str(ca_cert)),
            ("N3WFC4_CERT_CA_KEY_FILE", str(ca_key)),
            ("N3WFC4_CERT_SYSTEM_CA_FILE", str(system_ca)),
            ("N3WFC4_CERT_SERVER_NAME", preflight.EXPECTED_SERVER_NAME),
            ("N3WFC4_CERT_STATUS_FILE", str(STATUS_FILE)),
            ("N3WFC4_CERT_ALLOWED_ROOT_FC4", str(fc4_root)),
            ("N3WFC4_CERT_ALLOWED_ROOT_SYSTEM", str(system_root)),
        )
        env_payload = "".join(
            f"{name}={_env_quote(value)}\n"
            for name, value in env_lines
        ).encode("utf-8")
        _write_atomic(ENV_TARGET, env_payload, 0o600)
        created.append(ENV_TARGET)

        _progress("daemon_reload")
        _systemctl_daemon_reload()

        if _systemctl_state("is-active", LIFECYCLE_TIMER) == "active":
            raise InstallError("timer_became_active")
        timer_enabled = _systemctl_state("is-enabled", LIFECYCLE_TIMER)
        if timer_enabled == "enabled":
            raise InstallError("timer_became_enabled")
        service_active = _systemctl_state("is-active", LIFECYCLE_SERVICE)
        if service_active == "active":
            raise InstallError("lifecycle_service_became_active")

        if _git_blob_sha1(LIFECYCLE_TARGET) != LIFECYCLE_BLOB:
            raise InstallError("installed_lifecycle_hash_mismatch")
        if _git_blob_sha1(SERVICE_TARGET) != SERVICE_BLOB:
            raise InstallError("installed_service_hash_mismatch")
        if _git_blob_sha1(TIMER_TARGET) != TIMER_BLOB:
            raise InstallError("installed_timer_hash_mismatch")

        for path, expected_mode in (
            (LIFECYCLE_TARGET, 0o755),
            (SERVICE_TARGET, 0o644),
            (TIMER_TARGET, 0o644),
            (ENV_TARGET, 0o600),
            (STATUS_DIR, 0o700),
        ):
            uid, gid, mode = _owner_mode(path)
            if uid != 0 or gid != 0:
                raise InstallError("installed_owner_invalid")
            if mode != expected_mode:
                raise InstallError("installed_mode_invalid")

        broker_after, started_after = _container_identity(preflight)
        if broker_after != broker_before or started_after != started_before:
            raise InstallError("broker_runtime_changed")

        if _hash_file(server_cert) != server_cert_sha:
            raise InstallError("server_certificate_changed")
        if _hash_file(server_key) != server_key_sha:
            raise InstallError("server_private_key_changed")
        if _hash_file(ca_cert) != ca_cert_sha:
            raise InstallError("ca_certificate_changed")

        endpoint_fp = preflight._tls_endpoint_fingerprint(ca_cert, preflight.EXPECTED_SERVER_NAME)
        if endpoint_fp != preflight.EXPECTED_SERVER_FINGERPRINT:
            raise InstallError("postinstall_tls_fingerprint_changed")

        _progress("complete", result="PASS")
        return {
            "schema": SCHEMA,
            "result": "PASS",
            "installation_only": True,
            "certificate_mutation": False,
            "broker_restart": False,
            "timer_enablement": False,
            "timer_start": False,
            "auto_renew_start": False,
            "daemon_reload": True,
            "lifecycle_tool_installed": True,
            "lifecycle_service_installed": True,
            "lifecycle_timer_installed": True,
            "lifecycle_environment_installed": True,
            "status_authority_created": True,
            "lifecycle_tool_blob": LIFECYCLE_BLOB,
            "lifecycle_service_blob": SERVICE_BLOB,
            "lifecycle_timer_blob": TIMER_BLOB,
            "environment_mode": "0600",
            "status_directory_mode": "0700",
            "timer_active": _systemctl_state("is-active", LIFECYCLE_TIMER),
            "timer_enabled": timer_enabled,
            "service_active": service_active,
            "broker_container_continuity": True,
            "broker_started_at_continuity": True,
            "server_certificate_unchanged": True,
            "server_private_key_unchanged": True,
            "ca_certificate_unchanged": True,
            "live_tls_verified": True,
        }, 0
    except Exception as error:
        reason = error.code if isinstance(error, InstallError) else "installation_internal_failure"
        rollback_ok = _rollback(created, status_created)
        return {
            "schema": SCHEMA,
            "result": "STOP",
            "reason": reason,
            "installation_rollback": "PASS" if rollback_ok else "UNPROVEN",
            "certificate_mutation": False,
            "timer_enablement": False,
            "broker_restart": False,
        }, 2 if rollback_ok else 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lifecycle-source", required=True)
    parser.add_argument("--service-source", required=True)
    parser.add_argument("--timer-source", required=True)
    parser.add_argument("--preflight-source", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        document, code = install(
            Path(args.lifecycle_source),
            Path(args.service_source),
            Path(args.timer_source),
            Path(args.preflight_source),
        )
    except InstallError as error:
        document = {
            "schema": SCHEMA,
            "result": "STOP",
            "reason": error.code,
            "certificate_mutation": False,
            "timer_enablement": False,
            "broker_restart": False,
        }
        code = 2
    print(json.dumps(document, sort_keys=True, separators=(",", ":")), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
