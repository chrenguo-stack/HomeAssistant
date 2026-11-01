#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import socket
import ssl
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

SCHEMA = "gh.n3w-broker-certificate-lifecycle-timer-runtime-activation/1"

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

SERVICE_SETTLE_SECONDS = 20


class TimerActivationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _progress(stage: str, **fields: object) -> None:
    print(
        "KF100_TIMER_ACTIVATE "
        + json.dumps({"stage": stage, **fields}, sort_keys=True, separators=(",", ":")),
        file=sys.stderr,
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
        raise TimerActivationError("command_unavailable") from error
    if result.returncode != 0 and not allow_failure:
        raise TimerActivationError("command_failed")
    return result


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


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
        raise TimerActivationError("installed_source_invalid")
    uid, gid, actual_mode = _owner_mode(path)
    if uid != 0 or gid != 0 or actual_mode != mode:
        raise TimerActivationError("installed_source_permissions_invalid")
    if _git_blob_sha1(path) != blob:
        raise TimerActivationError("installed_source_blob_mismatch")


def _systemctl_state(mode: str, unit: str) -> str:
    if mode not in {"is-active", "is-enabled"}:
        raise TimerActivationError("systemctl_state_mode_invalid")
    result = _run(("systemctl", mode, unit), timeout=10, allow_failure=True)
    return result.stdout.strip() or "unknown"


def _timer_properties() -> dict[str, str]:
    properties = (
        "ActiveState",
        "UnitFileState",
        "NextElapseUSecRealtime",
        "LastTriggerUSec",
        "Result",
    )
    argv: list[str] = ["systemctl", "show", LIFECYCLE_TIMER, "--no-pager"]
    for prop in properties:
        argv.append(f"--property={prop}")
    result = _run(tuple(argv), timeout=10)
    document: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name in properties:
            document[name] = value.strip()
    if set(document) != set(properties):
        raise TimerActivationError("timer_properties_incomplete")
    return document


def _parse_env() -> dict[str, str]:
    if not ENV_FILE.is_file() or ENV_FILE.is_symlink():
        raise TimerActivationError("environment_file_invalid")
    uid, gid, mode = _owner_mode(ENV_FILE)
    if uid != 0 or gid != 0 or mode != 0o600:
        raise TimerActivationError("environment_file_permissions_invalid")

    values: dict[str, str] = {}
    try:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise TimerActivationError("environment_file_unreadable") from error
    for line in lines:
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise TimerActivationError("environment_line_invalid")
        name, raw = line.split("=", 1)
        if name not in ENV_KEYS or name in values:
            raise TimerActivationError("environment_key_invalid")
        try:
            parsed = shlex.split(raw, posix=True)
        except ValueError as error:
            raise TimerActivationError("environment_value_invalid") from error
        if len(parsed) != 1 or not parsed[0] or "\x00" in parsed[0]:
            raise TimerActivationError("environment_value_invalid")
        values[name] = parsed[0]
    if set(values) != ENV_KEYS:
        raise TimerActivationError("environment_keys_incomplete")
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
        raise TimerActivationError("broker_container_not_unique")
    container = ids[0]
    result = _run(("docker", "inspect", container))
    try:
        document = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise TimerActivationError("broker_inspect_invalid") from error
    if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], dict):
        raise TimerActivationError("broker_inspect_invalid")
    inspect = document[0]
    state = inspect.get("State")
    if not isinstance(state, dict) or state.get("Running") is not True:
        raise TimerActivationError("broker_not_running")
    started = state.get("StartedAt")
    if not isinstance(started, str) or not started:
        raise TimerActivationError("broker_started_at_missing")
    return container, started, inspect


def _mount_source(inspect: dict[str, object], target: str) -> Path:
    mounts = inspect.get("Mounts")
    if not isinstance(mounts, list):
        raise TimerActivationError("broker_mounts_invalid")
    matches: list[Path] = []
    for item in mounts:
        if not isinstance(item, dict) or item.get("Destination") != target:
            continue
        if item.get("Type") != "bind" or item.get("RW") is not False:
            raise TimerActivationError("broker_tls_mount_invalid")
        source = item.get("Source")
        if not isinstance(source, str) or not source.startswith("/"):
            raise TimerActivationError("broker_tls_mount_invalid")
        matches.append(Path(source))
    if len(matches) != 1:
        raise TimerActivationError("broker_tls_mount_not_unique")
    path = matches[0]
    if not path.is_file() or path.is_symlink():
        raise TimerActivationError("broker_tls_source_invalid")
    return path


def _fingerprint(path: Path) -> str:
    result = _run(("openssl", "x509", "-in", str(path), "-noout", "-fingerprint", "-sha256"))
    match = re.search(r"Fingerprint=([0-9A-Fa-f:]+)", result.stdout)
    if match is None:
        raise TimerActivationError("certificate_fingerprint_missing")
    value = match.group(1).replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise TimerActivationError("certificate_fingerprint_invalid")
    return value


def _live_tls_fingerprint(ca_cert: Path) -> str:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(ca_cert))
    try:
        with socket.create_connection(("127.0.0.1", 8883), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname=EXPECTED_SERVER_NAME) as wrapped:
                der = wrapped.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as error:
        raise TimerActivationError("live_tls_probe_failed") from error
    if not der:
        raise TimerActivationError("live_tls_peer_certificate_missing")
    return hashlib.sha256(der).hexdigest()


def _status_document() -> tuple[dict[str, object], str, str]:
    if not STATUS_DIR.is_dir() or STATUS_DIR.is_symlink():
        raise TimerActivationError("status_directory_invalid")
    uid, gid, mode = _owner_mode(STATUS_DIR)
    if uid != 0 or gid != 0 or mode != 0o700:
        raise TimerActivationError("status_directory_permissions_invalid")

    try:
        names = {path.name for path in STATUS_DIR.iterdir()}
    except OSError as error:
        raise TimerActivationError("status_directory_unreadable") from error
    if names != {STATUS_FILE.name, LOCK_FILE.name}:
        raise TimerActivationError("status_directory_unexpected_entries")

    for path in (STATUS_FILE, LOCK_FILE):
        if not path.is_file() or path.is_symlink():
            raise TimerActivationError("status_authority_invalid")
        uid, gid, mode = _owner_mode(path)
        if uid != 0 or gid != 0 or mode != 0o600:
            raise TimerActivationError("status_authority_permissions_invalid")

    try:
        raw = STATUS_FILE.read_text(encoding="utf-8")
    except OSError as error:
        raise TimerActivationError("status_file_unreadable") from error
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise TimerActivationError("status_json_invalid") from error
    if not isinstance(document, dict):
        raise TimerActivationError("status_json_invalid")

    expected = {
        "schema": "gh.n3w-broker-certificate-lifecycle/1",
        "action": "audit",
        "result": "ok",
        "server_state": "HEALTHY",
        "ca_state": "HEALTHY",
        "system_ca_state": "HEALTHY",
        "renewal_attempted": False,
        "rollback_attempted": False,
        "server_sha256_fingerprint": EXPECTED_SERVER_FINGERPRINT,
        "ca_sha256_fingerprint": EXPECTED_CA_FINGERPRINT,
        "system_ca_sha256_fingerprint": EXPECTED_SYSTEM_CA_FINGERPRINT,
        "server_not_after": "2028-11-22T04:18:40Z",
        "ca_not_after": "2036-08-17T04:18:39Z",
        "system_ca_not_after": "2036-07-30T15:32:24Z",
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise TimerActivationError("lifecycle_status_unexpected")

    if "PRIVATE KEY" in raw or "BEGIN CERTIFICATE" in raw:
        raise TimerActivationError("status_contains_private_material")

    return document, raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _capture_runtime(env: dict[str, str]) -> dict[str, object]:
    if env["N3WFC4_CERT_SERVER_NAME"] != EXPECTED_SERVER_NAME:
        raise TimerActivationError("server_name_drift")
    if Path(env["N3WFC4_CERT_STATUS_FILE"]) != STATUS_FILE:
        raise TimerActivationError("status_path_drift")

    container, started, inspect = _broker_container()
    server_cert = _mount_source(inspect, "/mosquitto/tls/server.pem")
    server_key = _mount_source(inspect, "/mosquitto/tls/server.key")
    ca_cert = _mount_source(inspect, "/mosquitto/tls/ca.pem")

    if Path(env["N3WFC4_CERT_SERVER_CERT_FILE"]) != server_cert:
        raise TimerActivationError("server_cert_path_drift")
    if Path(env["N3WFC4_CERT_SERVER_KEY_FILE"]) != server_key:
        raise TimerActivationError("server_key_path_drift")
    if Path(env["N3WFC4_CERT_CA_CERT_FILE"]) != ca_cert:
        raise TimerActivationError("ca_cert_path_drift")

    system_ca = Path(env["N3WFC4_CERT_SYSTEM_CA_FILE"])
    if not system_ca.is_file() or system_ca.is_symlink():
        raise TimerActivationError("system_ca_invalid")

    if _fingerprint(server_cert) != EXPECTED_SERVER_FINGERPRINT:
        raise TimerActivationError("server_fingerprint_drift")
    if _fingerprint(ca_cert) != EXPECTED_CA_FINGERPRINT:
        raise TimerActivationError("ca_fingerprint_drift")
    if _fingerprint(system_ca) != EXPECTED_SYSTEM_CA_FINGERPRINT:
        raise TimerActivationError("system_ca_fingerprint_drift")
    if _live_tls_fingerprint(ca_cert) != EXPECTED_SERVER_FINGERPRINT:
        raise TimerActivationError("live_tls_fingerprint_drift")

    return {
        "container": container,
        "started": started,
        "server_cert_sha256": _sha256(server_cert),
        "server_key_sha256": _sha256(server_key),
        "ca_cert_sha256": _sha256(ca_cert),
        "ca_cert": ca_cert,
    }


def _validate_prestate() -> tuple[dict[str, str], dict[str, object], str]:
    _require_regular_exact(LIFECYCLE_TOOL, LIFECYCLE_TOOL_BLOB, 0o755)
    _require_regular_exact(SERVICE_FILE, SERVICE_BLOB, 0o644)
    _require_regular_exact(TIMER_FILE, TIMER_BLOB, 0o644)

    if _systemctl_state("is-enabled", LIFECYCLE_TIMER) != "enabled":
        raise TimerActivationError("timer_not_enabled")
    if _systemctl_state("is-active", LIFECYCLE_TIMER) in {"active", "activating"}:
        raise TimerActivationError("timer_already_active")
    if _systemctl_state("is-active", LIFECYCLE_SERVICE) in {"active", "activating"}:
        raise TimerActivationError("lifecycle_service_already_active")

    env = _parse_env()
    _status, _raw, status_sha256 = _status_document()
    runtime = _capture_runtime(env)
    return env, runtime, status_sha256


def _wait_service_quiescent() -> str:
    deadline = time.monotonic() + SERVICE_SETTLE_SECONDS
    while time.monotonic() < deadline:
        state = _systemctl_state("is-active", LIFECYCLE_SERVICE)
        if state not in {"active", "activating"}:
            return state
        time.sleep(1)
    return _systemctl_state("is-active", LIFECYCLE_SERVICE)


def _rollback_activation() -> str:
    stop = _run(("systemctl", "stop", LIFECYCLE_TIMER), timeout=30, allow_failure=True)
    disable = _run(("systemctl", "disable", LIFECYCLE_TIMER), timeout=30, allow_failure=True)
    timer_active = _systemctl_state("is-active", LIFECYCLE_TIMER)
    timer_enabled = _systemctl_state("is-enabled", LIFECYCLE_TIMER)
    service_active = _systemctl_state("is-active", LIFECYCLE_SERVICE)
    if (
        stop.returncode == 0
        and disable.returncode == 0
        and timer_active not in {"active", "activating"}
        and timer_enabled == "disabled"
        and service_active not in {"active", "activating"}
    ):
        return "PASS"
    return "UNPROVEN"


def _post_activation(
    env: dict[str, str],
    before: dict[str, object],
    before_status_sha256: str,
) -> dict[str, object]:
    initial_properties = _timer_properties()
    if initial_properties["ActiveState"] != "active":
        raise TimerActivationError("timer_not_active")
    if initial_properties["UnitFileState"] != "enabled":
        raise TimerActivationError("timer_not_enabled_after_start")
    initial_next_elapse = initial_properties["NextElapseUSecRealtime"]
    if initial_next_elapse in {"", "0", "n/a", "infinity"}:
        raise TimerActivationError("timer_next_elapse_missing")

    service_state = _wait_service_quiescent()
    if service_state != "inactive":
        raise TimerActivationError("lifecycle_service_not_inactive")

    properties = _timer_properties()
    if properties["ActiveState"] != "active":
        raise TimerActivationError("timer_not_active_after_settle")
    if properties["UnitFileState"] != "enabled":
        raise TimerActivationError("timer_not_enabled_after_settle")
    next_elapse = properties["NextElapseUSecRealtime"]
    if next_elapse in {"", "0", "n/a", "infinity"}:
        raise TimerActivationError("timer_next_elapse_missing_after_settle")

    status, _raw, after_status_sha256 = _status_document()
    status_changed = after_status_sha256 != before_status_sha256
    last_trigger = properties["LastTriggerUSec"]

    if status_changed and last_trigger in {"", "0", "n/a"}:
        raise TimerActivationError("status_changed_without_timer_trigger")

    after = _capture_runtime(env)
    if after["container"] != before["container"] or after["started"] != before["started"]:
        raise TimerActivationError("broker_runtime_changed")
    if after["server_cert_sha256"] != before["server_cert_sha256"]:
        raise TimerActivationError("server_certificate_changed")
    if after["server_key_sha256"] != before["server_key_sha256"]:
        raise TimerActivationError("server_private_key_changed")
    if after["ca_cert_sha256"] != before["ca_cert_sha256"]:
        raise TimerActivationError("ca_certificate_changed")

    return {
        "timer_properties": properties,
        "status_changed": status_changed,
        "status": status,
    }


def activate_timer() -> tuple[dict[str, object], int]:
    if os.geteuid() != 0:
        raise TimerActivationError("root_required")

    _progress("validate_prestate")
    env, before, status_sha256 = _validate_prestate()

    _progress("start_timer")
    start = _run(("systemctl", "start", LIFECYCLE_TIMER), timeout=30, allow_failure=True)
    if start.returncode != 0:
        rollback = _rollback_activation()
        return {
            "schema": SCHEMA,
            "result": "STOP",
            "reason": "timer_start_failed",
            "activation_rollback": rollback,
            "certificate_mutation": False,
            "broker_restart": False,
        }, 2 if rollback == "PASS" else 3

    try:
        _progress("validate_runtime_schedule")
        post = _post_activation(env, before, status_sha256)
    except TimerActivationError as error:
        rollback = _rollback_activation()
        return {
            "schema": SCHEMA,
            "result": "STOP",
            "reason": error.code,
            "activation_rollback": rollback,
            "certificate_mutation": False,
            "broker_restart": False,
        }, 2 if rollback == "PASS" else 3

    properties = post["timer_properties"]
    status_changed = bool(post["status_changed"])

    _progress("complete", result="PASS")
    return {
        "schema": SCHEMA,
        "result": "PASS",
        "timer_runtime_activation": True,
        "timer_enabled": "enabled",
        "timer_active": "active",
        "lifecycle_service_active": "inactive",
        "next_elapse_realtime": properties["NextElapseUSecRealtime"],
        "last_trigger_usec": properties["LastTriggerUSec"],
        "persistent_catchup_observed": status_changed,
        "status_changed_during_activation": status_changed,
        "status_health_valid": True,
        "renewal_attempted": False,
        "rollback_attempted": False,
        "broker_restart": False,
        "certificate_mutation": False,
        "broker_container_continuity": True,
        "broker_started_at_continuity": True,
        "server_certificate_unchanged": True,
        "server_private_key_unchanged": True,
        "ca_certificate_unchanged": True,
        "live_tls_verified": True,
    }, 0


def main() -> int:
    try:
        document, code = activate_timer()
    except TimerActivationError as error:
        document = {
            "schema": SCHEMA,
            "result": "STOP",
            "reason": error.code,
            "certificate_mutation": False,
            "broker_restart": False,
        }
        code = 2
    print(json.dumps(document, sort_keys=True, separators=(",", ":")), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
