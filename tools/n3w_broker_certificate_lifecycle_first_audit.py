#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import socket
import ssl
import stat
import subprocess
from pathlib import Path
from typing import Sequence

SCHEMA = "gh.n3w-broker-certificate-lifecycle-first-audit/1"
EXPECTED_PROJECT = "n3wfc4"
EXPECTED_SERVICE = "broker"
EXPECTED_SERVER_NAME = "armbian"
EXPECTED_SERVER_FINGERPRINT = "8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb"
EXPECTED_CA_FINGERPRINT = "b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351"
EXPECTED_SYSTEM_CA_FINGERPRINT = "745c29f156b35cdb222bb7150aa814ff4aa0c57f20c9bd23af9ee3b51e23ddf7"

LIFECYCLE_TOOL = Path("/usr/local/sbin/n3w-broker-certificate-lifecycle")
SERVICE_FILE = Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service")
TIMER_FILE = Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer")
ENV_FILE = Path("/etc/n3wfc4/broker-certificate-lifecycle.env")
STATUS_DIR = Path("/var/lib/n3wfc4-certificate-lifecycle")
STATUS_FILE = STATUS_DIR / "status.json"
LOCK_FILE = STATUS_DIR / ".certificate-lifecycle.lock"

LIFECYCLE_TOOL_BLOB = "65187b27a2ddd8f57221500a7019486e02bca101"
SERVICE_BLOB = "fa13967ef0ffb0a271fcb7122febd83b83079deb"
TIMER_BLOB = "65b0365c5ea5f5d3c896a133adc0d689bb2deced"

LIFECYCLE_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
LIFECYCLE_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"
ACTIVATION_UNIT = "n3wfc4-broker-activation.service"

ENV_KEYS = {
    "N3WFC4_CERT_SERVER_CERT_FILE",
    "N3WFC4_CERT_SERVER_KEY_FILE",
    "N3WFC4_CERT_CA_CERT_FILE",
    "N3WFC4_CERT_CA_KEY_FILE",
    "N3WFC4_CERT_SYSTEM_CA_FILE",
    "N3WFC4_CERT_SERVER_NAME",
    "N3WFC4_CERT_STATUS_FILE",
    "N3WFC4_CERT_ALLOWED_ROOT_FC4",
    "N3WFC4_CERT_ALLOWED_ROOT_SYSTEM",
}


class AuditGateError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _progress(stage: str, **fields: object) -> None:
    print(
        "KF100_FIRST_AUDIT "
        + json.dumps({"stage": stage, **fields}, sort_keys=True, separators=(",", ":")),
        file=os.sys.stderr,
        flush=True,
    )


def _run(
    argv: Sequence[str],
    *,
    timeout: int = 30,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(argv),
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AuditGateError("command_unavailable") from error
    if result.returncode != 0 and not allow_failure:
        raise AuditGateError("command_failed")
    return result


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _owner_mode(path: Path) -> tuple[int, int, int]:
    file_stat = path.stat()
    return file_stat.st_uid, file_stat.st_gid, stat.S_IMODE(file_stat.st_mode)


def _require_regular_exact(path: Path, blob: str, mode: int) -> None:
    if not path.is_file() or path.is_symlink():
        raise AuditGateError("installed_source_invalid")
    uid, gid, actual_mode = _owner_mode(path)
    if uid != 0 or gid != 0 or actual_mode != mode:
        raise AuditGateError("installed_source_permissions_invalid")
    if _git_blob_sha1(path) != blob:
        raise AuditGateError("installed_source_blob_mismatch")


def _systemctl_state(mode: str, unit: str) -> str:
    if mode not in {"is-active", "is-enabled"}:
        raise AuditGateError("systemctl_mode_invalid")
    result = _run(("systemctl", mode, unit), timeout=10, allow_failure=True)
    return result.stdout.strip() or "unknown"


def _parse_environment(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise AuditGateError("environment_file_invalid")
    uid, gid, mode = _owner_mode(path)
    if uid != 0 or gid != 0 or mode != 0o600:
        raise AuditGateError("environment_file_permissions_invalid")

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise AuditGateError("environment_file_unreadable") from error

    for line in lines:
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise AuditGateError("environment_line_invalid")
        name, raw = line.split("=", 1)
        if name not in ENV_KEYS or name in values:
            raise AuditGateError("environment_key_invalid")
        try:
            parsed = shlex.split(raw, posix=True)
        except ValueError as error:
            raise AuditGateError("environment_value_invalid") from error
        if len(parsed) != 1 or not parsed[0] or "\x00" in parsed[0]:
            raise AuditGateError("environment_value_invalid")
        values[name] = parsed[0]

    if set(values) != ENV_KEYS:
        raise AuditGateError("environment_keys_incomplete")
    return values


def _broker_container() -> tuple[str, str, dict[str, object]]:
    result = _run(
        (
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={EXPECTED_PROJECT}",
            "--filter",
            f"label=com.docker.compose.service={EXPECTED_SERVICE}",
            "--format",
            "{{.ID}}",
        )
    )
    ids = tuple(line.strip() for line in result.stdout.splitlines() if line.strip())
    if len(ids) != 1:
        raise AuditGateError("broker_container_not_unique")
    container = ids[0]
    inspect_result = _run(("docker", "inspect", container))
    try:
        doc = json.loads(inspect_result.stdout)
    except json.JSONDecodeError as error:
        raise AuditGateError("broker_inspect_invalid") from error
    if not isinstance(doc, list) or len(doc) != 1 or not isinstance(doc[0], dict):
        raise AuditGateError("broker_inspect_invalid")
    inspect = doc[0]
    state = inspect.get("State")
    if not isinstance(state, dict) or state.get("Running") is not True:
        raise AuditGateError("broker_not_running")
    started = state.get("StartedAt")
    if not isinstance(started, str) or not started:
        raise AuditGateError("broker_started_at_missing")
    return container, started, inspect


def _mount_source(inspect: dict[str, object], target: str) -> Path:
    mounts = inspect.get("Mounts")
    if not isinstance(mounts, list):
        raise AuditGateError("broker_mounts_invalid")
    matches: list[Path] = []
    for item in mounts:
        if not isinstance(item, dict) or item.get("Destination") != target:
            continue
        if item.get("Type") != "bind" or item.get("RW") is not False:
            raise AuditGateError("broker_tls_mount_invalid")
        source = item.get("Source")
        if not isinstance(source, str) or not source.startswith("/"):
            raise AuditGateError("broker_tls_mount_invalid")
        matches.append(Path(source))
    if len(matches) != 1:
        raise AuditGateError("broker_tls_mount_not_unique")
    path = matches[0]
    if not path.is_file() or path.is_symlink():
        raise AuditGateError("broker_tls_source_invalid")
    return path


def _fingerprint(path: Path) -> str:
    result = _run(("openssl", "x509", "-in", str(path), "-noout", "-fingerprint", "-sha256"))
    match = re.search(r"Fingerprint=([0-9A-Fa-f:]+)", result.stdout)
    if match is None:
        raise AuditGateError("certificate_fingerprint_missing")
    value = match.group(1).replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AuditGateError("certificate_fingerprint_invalid")
    return value


def _live_tls_fingerprint(ca_cert: Path, server_name: str) -> str:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(ca_cert))
    try:
        with socket.create_connection(("127.0.0.1", 8883), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname=server_name) as wrapped:
                der = wrapped.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as error:
        raise AuditGateError("live_tls_probe_failed") from error
    if not der:
        raise AuditGateError("live_tls_peer_certificate_missing")
    return hashlib.sha256(der).hexdigest()


def _validate_prestate(env: dict[str, str]) -> dict[str, object]:
    _require_regular_exact(LIFECYCLE_TOOL, LIFECYCLE_TOOL_BLOB, 0o755)
    _require_regular_exact(SERVICE_FILE, SERVICE_BLOB, 0o644)
    _require_regular_exact(TIMER_FILE, TIMER_BLOB, 0o644)

    if not STATUS_DIR.is_dir() or STATUS_DIR.is_symlink():
        raise AuditGateError("status_directory_invalid")
    uid, gid, mode = _owner_mode(STATUS_DIR)
    if uid != 0 or gid != 0 or mode != 0o700:
        raise AuditGateError("status_directory_permissions_invalid")
    if STATUS_FILE.exists() or STATUS_FILE.is_symlink():
        raise AuditGateError("first_audit_status_already_present")
    if LOCK_FILE.exists() or LOCK_FILE.is_symlink():
        raise AuditGateError("first_audit_lock_already_present")
    try:
        status_entries = tuple(STATUS_DIR.iterdir())
    except OSError as error:
        raise AuditGateError("status_directory_unreadable") from error
    if status_entries:
        raise AuditGateError("first_audit_status_directory_not_empty")

    if _systemctl_state("is-active", LIFECYCLE_SERVICE) == "active":
        raise AuditGateError("lifecycle_service_already_active")
    if _systemctl_state("is-active", LIFECYCLE_TIMER) == "active":
        raise AuditGateError("lifecycle_timer_already_active")
    if _systemctl_state("is-enabled", LIFECYCLE_TIMER) == "enabled":
        raise AuditGateError("lifecycle_timer_already_enabled")

    if env["N3WFC4_CERT_SERVER_NAME"] != EXPECTED_SERVER_NAME:
        raise AuditGateError("server_name_drift")
    if Path(env["N3WFC4_CERT_STATUS_FILE"]) != STATUS_FILE:
        raise AuditGateError("status_path_drift")

    container, started, inspect = _broker_container()
    ca_cert = _mount_source(inspect, "/mosquitto/tls/ca.pem")
    server_cert = _mount_source(inspect, "/mosquitto/tls/server.pem")
    server_key = _mount_source(inspect, "/mosquitto/tls/server.key")

    if Path(env["N3WFC4_CERT_CA_CERT_FILE"]) != ca_cert:
        raise AuditGateError("environment_ca_path_drift")
    if Path(env["N3WFC4_CERT_SERVER_CERT_FILE"]) != server_cert:
        raise AuditGateError("environment_server_cert_path_drift")
    if Path(env["N3WFC4_CERT_SERVER_KEY_FILE"]) != server_key:
        raise AuditGateError("environment_server_key_path_drift")

    system_ca = Path(env["N3WFC4_CERT_SYSTEM_CA_FILE"])
    if not system_ca.is_file() or system_ca.is_symlink():
        raise AuditGateError("system_ca_invalid")

    if _fingerprint(ca_cert) != EXPECTED_CA_FINGERPRINT:
        raise AuditGateError("ca_fingerprint_drift")
    if _fingerprint(server_cert) != EXPECTED_SERVER_FINGERPRINT:
        raise AuditGateError("server_fingerprint_drift")
    if _fingerprint(system_ca) != EXPECTED_SYSTEM_CA_FINGERPRINT:
        raise AuditGateError("system_ca_fingerprint_drift")
    if _live_tls_fingerprint(ca_cert, EXPECTED_SERVER_NAME) != EXPECTED_SERVER_FINGERPRINT:
        raise AuditGateError("live_tls_fingerprint_drift")

    return {
        "container": container,
        "started": started,
        "server_cert": server_cert,
        "server_key": server_key,
        "ca_cert": ca_cert,
        "system_ca": system_ca,
        "server_cert_sha256": _sha256(server_cert),
        "server_key_sha256": _sha256(server_key),
        "ca_cert_sha256": _sha256(ca_cert),
    }


def _audit_argv(env: dict[str, str]) -> tuple[str, ...]:
    return (
        str(LIFECYCLE_TOOL),
        "audit",
        "--server-cert",
        env["N3WFC4_CERT_SERVER_CERT_FILE"],
        "--ca-cert",
        env["N3WFC4_CERT_CA_CERT_FILE"],
        "--system-ca",
        env["N3WFC4_CERT_SYSTEM_CA_FILE"],
        "--server-name",
        env["N3WFC4_CERT_SERVER_NAME"],
        "--status-file",
        env["N3WFC4_CERT_STATUS_FILE"],
        "--allowed-root",
        env["N3WFC4_CERT_ALLOWED_ROOT_FC4"],
        "--allowed-root",
        env["N3WFC4_CERT_ALLOWED_ROOT_SYSTEM"],
        "--activation-unit",
        ACTIVATION_UNIT,
        "--probe-host",
        "127.0.0.1",
        "--probe-port",
        "8883",
    )


def _validate_audit_document(document: dict[str, object]) -> None:
    expected = {
        "schema": "gh.n3w-broker-certificate-lifecycle/1",
        "action": "audit",
        "result": "ok",
        "server_state": "HEALTHY",
        "ca_state": "HEALTHY",
        "system_ca_state": "HEALTHY",
        "renewal_attempted": False,
        "rollback_attempted": False,
        "server_not_after": "2028-11-22T04:18:40Z",
        "ca_not_after": "2036-08-17T04:18:39Z",
        "system_ca_not_after": "2036-07-30T15:32:24Z",
        "server_sha256_fingerprint": EXPECTED_SERVER_FINGERPRINT,
        "ca_sha256_fingerprint": EXPECTED_CA_FINGERPRINT,
        "system_ca_sha256_fingerprint": EXPECTED_SYSTEM_CA_FINGERPRINT,
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise AuditGateError("audit_document_unexpected")


def _validate_poststate(
    env: dict[str, str],
    before: dict[str, object],
    document: dict[str, object],
) -> None:
    if not STATUS_FILE.is_file() or STATUS_FILE.is_symlink():
        raise AuditGateError("status_file_missing")
    if not LOCK_FILE.is_file() or LOCK_FILE.is_symlink():
        raise AuditGateError("lock_file_missing")

    for path in (STATUS_FILE, LOCK_FILE):
        uid, gid, mode = _owner_mode(path)
        if uid != 0 or gid != 0 or mode != 0o600:
            raise AuditGateError("audit_state_permissions_invalid")
    try:
        entry_names = {path.name for path in STATUS_DIR.iterdir()}
    except OSError as error:
        raise AuditGateError("status_directory_unreadable") from error
    if entry_names != {STATUS_FILE.name, LOCK_FILE.name}:
        raise AuditGateError("audit_status_directory_unexpected_entries")

    raw = STATUS_FILE.read_text(encoding="utf-8")
    try:
        status_doc = json.loads(raw)
    except json.JSONDecodeError as error:
        raise AuditGateError("status_json_invalid") from error
    if status_doc != document:
        raise AuditGateError("status_document_mismatch")
    for private_value in (
        env["N3WFC4_CERT_SERVER_CERT_FILE"],
        env["N3WFC4_CERT_SERVER_KEY_FILE"],
        env["N3WFC4_CERT_CA_CERT_FILE"],
        env["N3WFC4_CERT_CA_KEY_FILE"],
        env["N3WFC4_CERT_SYSTEM_CA_FILE"],
        env["N3WFC4_CERT_ALLOWED_ROOT_FC4"],
        env["N3WFC4_CERT_ALLOWED_ROOT_SYSTEM"],
    ):
        if private_value in raw:
            raise AuditGateError("status_contains_private_path")
    if "PRIVATE KEY" in raw or "BEGIN CERTIFICATE" in raw:
        raise AuditGateError("status_contains_private_material")

    if _systemctl_state("is-active", LIFECYCLE_SERVICE) == "active":
        raise AuditGateError("lifecycle_service_became_active")
    if _systemctl_state("is-active", LIFECYCLE_TIMER) == "active":
        raise AuditGateError("lifecycle_timer_became_active")
    if _systemctl_state("is-enabled", LIFECYCLE_TIMER) == "enabled":
        raise AuditGateError("lifecycle_timer_became_enabled")

    container, started, inspect = _broker_container()
    if container != before["container"] or started != before["started"]:
        raise AuditGateError("broker_runtime_changed")

    server_cert = _mount_source(inspect, "/mosquitto/tls/server.pem")
    server_key = _mount_source(inspect, "/mosquitto/tls/server.key")
    ca_cert = _mount_source(inspect, "/mosquitto/tls/ca.pem")
    if _sha256(server_cert) != before["server_cert_sha256"]:
        raise AuditGateError("server_certificate_changed")
    if _sha256(server_key) != before["server_key_sha256"]:
        raise AuditGateError("server_private_key_changed")
    if _sha256(ca_cert) != before["ca_cert_sha256"]:
        raise AuditGateError("ca_certificate_changed")
    if _live_tls_fingerprint(ca_cert, EXPECTED_SERVER_NAME) != EXPECTED_SERVER_FINGERPRINT:
        raise AuditGateError("live_tls_changed")


def first_audit() -> tuple[dict[str, object], int]:
    if os.geteuid() != 0:
        raise AuditGateError("root_required")

    _progress("validate_installed_prestate")
    env = _parse_environment(ENV_FILE)
    before = _validate_prestate(env)

    argv = _audit_argv(env)
    if "--server-key" in argv or "--ca-key" in argv or "auto-renew" in argv:
        raise AuditGateError("audit_private_key_or_renewal_argument_forbidden")

    _progress("run_audit")
    result = _run(argv, timeout=60, allow_failure=True)
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AuditGateError("audit_output_invalid") from error
    if not isinstance(document, dict):
        raise AuditGateError("audit_output_invalid")
    if result.returncode != 0:
        raise AuditGateError("audit_return_code_nonzero")
    _validate_audit_document(document)

    _progress("validate_poststate")
    _validate_poststate(env, before, document)

    _progress("complete", result="PASS")
    return {
        "schema": SCHEMA,
        "result": "PASS",
        "first_audit": True,
        "audit_rc": 0,
        "audit_action": document["action"],
        "audit_result": document["result"],
        "server_state": document["server_state"],
        "ca_state": document["ca_state"],
        "system_ca_state": document["system_ca_state"],
        "renewal_attempted": document["renewal_attempted"],
        "rollback_attempted": document["rollback_attempted"],
        "server_sha256_fingerprint": document["server_sha256_fingerprint"],
        "ca_sha256_fingerprint": document["ca_sha256_fingerprint"],
        "system_ca_sha256_fingerprint": document["system_ca_sha256_fingerprint"],
        "status_written": True,
        "lock_created": True,
        "status_mode": "0600",
        "lock_mode": "0600",
        "certificate_mutation": False,
        "broker_restart": False,
        "timer_enablement": False,
        "timer_start": False,
        "auto_renew_invocation": False,
        "private_key_arguments_used": False,
        "broker_container_continuity": True,
        "broker_started_at_continuity": True,
        "server_certificate_unchanged": True,
        "server_private_key_unchanged": True,
        "ca_certificate_unchanged": True,
        "live_tls_verified": True,
    }, 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    try:
        document, code = first_audit()
    except AuditGateError as error:
        document = {
            "schema": SCHEMA,
            "result": "STOP",
            "reason": error.code,
            "certificate_mutation": False,
            "broker_restart": False,
            "timer_enablement": False,
        }
        code = 2
    print(json.dumps(document, sort_keys=True, separators=(",", ":")), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
