from __future__ import annotations

import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import socket
import sqlite3
import ssl
import stat
import subprocess
import tempfile
import time
import urllib.request
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-first-pairing-onboarding/1"
TRANSACTION_SCHEMA = "gh.n3w-t1-first-pairing-onboarding-transaction/1"
OPEN_CONFIRMATION = "OPEN FIRST PAIRING WINDOW: YES"
CLOSE_CONFIRMATION = "CLOSE FIRST PAIRING WINDOW: YES"

COMPOSE_PROJECT = "n3wfc4"
COMPOSE_TARGET = Path("/etc/n3wfc4/docker-compose.yml")
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
CA_CERT = Path("/etc/n3wfc4/tls/ca.pem")
PROVISIONING_ROOT = Path("/var/lib/n3w-t1-provisioning")
FACTORY_ACCEPTED_PATH = PROVISIONING_ROOT / "FACTORY_ACCEPTED.json"
TRANSACTION_PATH = PROVISIONING_ROOT / "FIRST_PAIRING_ONBOARDING.json"
RUNTIME_ROOT = Path("/run/n3w-first-pairing-onboarding")
OVERRIDE_PATH = RUNTIME_ROOT / "manager-pairing.override.yml"
WATCHDOG_TOOL_PATH = RUNTIME_ROOT / "onboarding-watchdog.py"
WATCHDOG_UNIT_PREFIX = "n3w-first-pairing-watchdog-"
PYTHON_EXECUTABLE = "/usr/bin/python3"
MANAGER_DB = Path("/var/lib/greenhouse-manager/manager/manager-state.sqlite3")
CREDENTIAL_DB = Path("/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3")
APPLICATION_KEY_DB = Path("/var/lib/greenhouse-manager/n3w/relay-authorization.sqlite3")
APPLICATION_KEY_DIR = Path("/var/lib/greenhouse-manager/n3w/relay-keys")
PEER_TRUST_DB = Path("/var/lib/greenhouse-manager/n3w/system-peer-trust.sqlite3")

PAIRING_UDP_PORT = 47111
PAIRING_HTTP_PORT = 47112
BROKER_TLS_PORT = 8883
BROKER_TLS_SERVER_NAME = "armbian"
FACTORY_BROKER_PLACEHOLDER = "gate-f-unbound.invalid"
EXPECTED_SERVICES = frozenset({"broker", "manager", "homeassistant"})
EXPECTED_TABLES = (
    "registrations",
    "pairing_sessions",
    "registration_events",
    "node_id_leases",
)


class OnboardingError(RuntimeError):
    pass


OPERATION_ERRORS = (
    OnboardingError,
    OSError,
    RuntimeError,
    sqlite3.Error,
    ssl.SSLError,
    subprocess.SubprocessError,
    TypeError,
    ValueError,
)


def _run(
    argv: Sequence[str],
    *,
    timeout: float = 60.0,
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
        reason_sha256 = _sha256_text(reason) if reason else "none"
        raise OnboardingError(
            "command_failed:"
            f"{argv[0]}:{completed.returncode}:"
            f"detail_sha256={reason_sha256}"
        )
    return completed.stdout


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise OnboardingError(f"record_unavailable:{path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as error:
        raise OnboardingError(f"record_invalid:{path.name}") from error
    if not isinstance(value, dict):
        raise OnboardingError(f"record_invalid:{path.name}")
    return value


def _read_private_json(path: Path) -> dict[str, Any]:
    _require_file(path)
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise OnboardingError(f"private_record_metadata_invalid:{path.name}")
    return _read_json(path)


def _require_root() -> None:
    if os.geteuid() != 0:
        raise OnboardingError("root_required")


def _require_private_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise OnboardingError(f"private_directory_invalid:{path.name}")
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise OnboardingError(f"private_directory_metadata_invalid:{path.name}")


def _write_private_json(path: Path, document: dict[str, Any]) -> None:
    _require_private_directory(path.parent)
    payload = (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")
    fd, raw_tmp = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
    )
    tmp = Path(raw_tmp)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


@contextmanager
def _exclusive_lock(*, blocking: bool = False):
    _require_private_directory(PROVISIONING_ROOT)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        fd = os.open(PROVISIONING_ROOT, flags)
    except OSError as error:
        raise OnboardingError("onboarding_lock_root_unavailable") from error
    try:
        try:
            flags = fcntl.LOCK_EX
            if not blocking:
                flags |= fcntl.LOCK_NB
            fcntl.flock(fd, flags)
        except BlockingIOError as error:
            raise OnboardingError("onboarding_lock_busy") from error
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _require_file(path: Path, *, mode: int | None = None) -> None:
    if path.is_symlink() or not path.is_file():
        raise OnboardingError(f"required_file_invalid:{path}")
    if mode is not None and stat.S_IMODE(path.stat().st_mode) != mode:
        raise OnboardingError(f"required_file_mode_invalid:{path}")


def _compose_argv(
    *tail: str,
    override: bool = False,
) -> tuple[str, ...]:
    argv = [
        "docker",
        "compose",
        "--project-name",
        COMPOSE_PROJECT,
        "--env-file",
        str(COMPOSE_ENV),
        "-f",
        str(COMPOSE_TARGET),
    ]
    if override:
        argv.extend(("-f", str(OVERRIDE_PATH)))
    argv.extend(("--profile", "application"))
    argv.extend(tail)
    return tuple(argv)


def _render_compose(*, override: bool = False) -> dict[str, Any]:
    raw = _run(
        _compose_argv(
            "config",
            "--format",
            "json",
            override=override,
        )
    )
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise OnboardingError("rendered_compose_json_invalid") from error
    if not isinstance(document, dict):
        raise OnboardingError("rendered_compose_invalid")
    return document


def _service(document: dict[str, Any], name: str) -> dict[str, Any]:
    services = document.get("services")
    if not isinstance(services, dict) or set(services) != EXPECTED_SERVICES:
        raise OnboardingError("compose_service_set_invalid")
    value = services.get(name)
    if not isinstance(value, dict):
        raise OnboardingError(f"compose_service_invalid:{name}")
    return value


def _env_map(service: dict[str, Any]) -> dict[str, str]:
    raw = service.get("environment")
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        result: dict[str, str] = {}
        for item in raw:
            if not isinstance(item, str) or "=" not in item:
                raise OnboardingError("manager_environment_invalid")
            key, value = item.split("=", 1)
            result[key] = value
        return result
    raise OnboardingError("manager_environment_invalid")


def _validate_factory_compose() -> dict[str, Any]:
    document = _render_compose()
    manager = _service(document, "manager")
    _service(document, "broker")
    _service(document, "homeassistant")
    env = _env_map(manager)
    expected = {
        "GH_N3W_RUNTIME_ENABLED": "true",
        "GH_N3W_PRODUCT_PAIRING_ENABLED": "false",
        "GH_N3W_PAIRING_ADVERTISED_HOST": "auto",
        "GH_N3W_NODE_BROKER_HOST": FACTORY_BROKER_PLACEHOLDER,
        "GH_N3W_NODE_BROKER_PORT": str(BROKER_TLS_PORT),
        "GH_N3W_NODE_BROKER_TLS_SERVER_NAME": BROKER_TLS_SERVER_NAME,
    }
    for key, value in expected.items():
        if env.get(key) != value:
            raise OnboardingError(f"factory_compose_environment_invalid:{key}")
    if manager.get("network_mode") != "host":
        raise OnboardingError("factory_manager_network_mode_invalid")
    if manager.get("ports") not in (None, []):
        raise OnboardingError("factory_manager_ports_invalid")
    profiles = manager.get("profiles")
    if not isinstance(profiles, list) or "application" not in profiles:
        raise OnboardingError("factory_manager_profile_invalid")
    return document


def _validate_override_compose(expected_host: str) -> dict[str, Any]:
    document = _render_compose(override=True)
    manager = _service(document, "manager")
    env = _env_map(manager)
    if env.get("GH_N3W_PRODUCT_PAIRING_ENABLED") != "true":
        raise OnboardingError("onboarding_pairing_not_enabled")
    if env.get("GH_N3W_NODE_BROKER_HOST") != expected_host:
        raise OnboardingError("onboarding_broker_host_mismatch")
    if env.get("GH_N3W_PAIRING_ADVERTISED_HOST") != "auto":
        raise OnboardingError("onboarding_advertised_host_drift")
    if env.get("GH_N3W_NODE_BROKER_TLS_SERVER_NAME") != BROKER_TLS_SERVER_NAME:
        raise OnboardingError("onboarding_tls_server_name_drift")
    if manager.get("network_mode") != "host":
        raise OnboardingError("onboarding_manager_network_mode_invalid")
    if manager.get("ports") not in (None, []):
        raise OnboardingError("onboarding_manager_ports_invalid")
    return document


def _service_id(service: str) -> str:
    raw = _run(
        (
            "docker",
            "ps",
            "-aq",
            "--filter",
            f"label=com.docker.compose.project={COMPOSE_PROJECT}",
            "--filter",
            f"label=com.docker.compose.service={service}",
        )
    )
    values = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(values) != 1:
        raise OnboardingError(f"{service}_container_count_{len(values)}")
    return values[0]


def _inspect_container(container_id: str) -> dict[str, Any]:
    try:
        document = json.loads(_run(("docker", "inspect", container_id)))
    except json.JSONDecodeError as error:
        raise OnboardingError("container_inspect_json_invalid") from error
    if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], dict):
        raise OnboardingError("container_inspect_invalid")
    return document[0]


def _container_snapshot(service: str) -> dict[str, Any]:
    container_id = _service_id(service)
    document = _inspect_container(container_id)
    config = document.get("Config")
    state = document.get("State")
    host_config = document.get("HostConfig")
    if not isinstance(config, dict) or not isinstance(state, dict) or not isinstance(host_config, dict):
        raise OnboardingError(f"{service}_container_inspect_shape_invalid")
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        raise OnboardingError(f"{service}_container_labels_invalid")
    if labels.get("com.docker.compose.project") != COMPOSE_PROJECT:
        raise OnboardingError(f"{service}_container_project_invalid")
    if labels.get("com.docker.compose.service") != service:
        raise OnboardingError(f"{service}_container_service_invalid")
    if state.get("Running") is not True:
        raise OnboardingError(f"{service}_container_not_running")
    env: dict[str, str] = {}
    for item in config.get("Env") or []:
        if isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            env[key] = value
    return {
        "id": container_id,
        "id_sha256": _sha256_text(container_id),
        "restart_count": int(document.get("RestartCount", 0)),
        "network_mode": str(host_config.get("NetworkMode", "")),
        "env": env,
    }


def _runtime_snapshot() -> dict[str, dict[str, Any]]:
    return {
        service: _container_snapshot(service)
        for service in sorted(EXPECTED_SERVICES)
    }


def _validate_factory_runtime(snapshot: dict[str, dict[str, Any]]) -> None:
    manager = snapshot["manager"]
    env = manager["env"]
    if manager["network_mode"] != "host":
        raise OnboardingError("manager_runtime_network_mode_invalid")
    if env.get("GH_N3W_RUNTIME_ENABLED") != "true":
        raise OnboardingError("manager_runtime_n3w_disabled")
    if env.get("GH_N3W_PRODUCT_PAIRING_ENABLED") != "false":
        raise OnboardingError("manager_runtime_pairing_not_disabled")
    if env.get("GH_N3W_PAIRING_ADVERTISED_HOST") != "auto":
        raise OnboardingError("manager_runtime_advertised_host_invalid")
    if env.get("GH_N3W_NODE_BROKER_HOST") != FACTORY_BROKER_PLACEHOLDER:
        raise OnboardingError("manager_runtime_factory_broker_invalid")
    if env.get("GH_N3W_NODE_BROKER_TLS_SERVER_NAME") != BROKER_TLS_SERVER_NAME:
        raise OnboardingError("manager_runtime_tls_server_name_invalid")
    if _listener_count("udp", PAIRING_UDP_PORT) != 0:
        raise OnboardingError("factory_pairing_udp_listener_present")
    if _listener_count("tcp", PAIRING_HTTP_PORT) != 0:
        raise OnboardingError("factory_pairing_tcp_listener_present")
    _probe_manager_broker_tls(manager["id"])


def _validate_factory_marker() -> dict[str, Any]:
    document = _read_private_json(FACTORY_ACCEPTED_PATH)
    if (
        document.get("schema") != "gh.n3w.t1-factory-accepted/1"
        or document.get("status") != "PASS"
        or document.get("factory_accepted") is not True
    ):
        raise OnboardingError("factory_acceptance_invalid")
    for key in ("release_id", "host_instance_id", "system_id"):
        if not isinstance(document.get(key), str) or not document[key]:
            raise OnboardingError(f"factory_acceptance_binding_invalid:{key}")
    return document


def _db_counts() -> dict[str, int]:
    _require_file(MANAGER_DB)
    try:
        connection = sqlite3.connect(
            f"file:{MANAGER_DB}?mode=ro",
            uri=True,
        )
    except sqlite3.Error as error:
        raise OnboardingError("manager_database_open_failed") from error
    try:
        connection.execute("PRAGMA query_only=ON")
        result: dict[str, int] = {}
        for table in EXPECTED_TABLES:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists is None:
                raise OnboardingError(f"manager_table_missing:{table}")
            row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            if row is None:
                raise OnboardingError(f"manager_table_count_failed:{table}")
            result[table] = int(row[0])
        return result
    except sqlite3.Error as error:
        raise OnboardingError("manager_database_query_failed") from error
    finally:
        connection.close()


def _read_only_connection(path: Path) -> sqlite3.Connection:
    _require_file(path)
    try:
        connection = sqlite3.connect(
            f"file:{path}?mode=ro",
            uri=True,
        )
    except sqlite3.Error as error:
        raise OnboardingError(f"database_open_failed:{path.name}") from error
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _security_state_counts() -> dict[str, int]:
    credentials = _read_only_connection(CREDENTIAL_DB)
    try:
        table = credentials.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='credential_assignments'"
        ).fetchone()
        if table is None:
            raise OnboardingError("credential_assignments_table_missing")
        credential_assignments = int(
            credentials.execute(
                "SELECT COUNT(*) FROM credential_assignments"
            ).fetchone()[0]
        )
    finally:
        credentials.close()

    keys = _read_only_connection(APPLICATION_KEY_DB)
    try:
        required = {"n3w_relay_meta", "n3w_relay_nodes", "n3w_relay_key_epochs"}
        names = {
            str(row["name"])
            for row in keys.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not required <= names:
            raise OnboardingError("application_key_schema_invalid")
        active_nodes = int(
            keys.execute(
                "SELECT COUNT(*) FROM n3w_relay_nodes WHERE active = 1"
            ).fetchone()[0]
        )
        key_epochs = int(
            keys.execute(
                "SELECT COUNT(*) FROM n3w_relay_key_epochs"
            ).fetchone()[0]
        )
    finally:
        keys.close()

    return {
        "credential_assignments": credential_assignments,
        "application_key_active_nodes": active_nodes,
        "application_key_epochs": key_epochs,
    }


def _require_clean_first_pair_state(
    counts: dict[str, int],
    security_counts: dict[str, int],
) -> None:
    if any(counts.get(table) != 0 for table in EXPECTED_TABLES):
        raise OnboardingError("first_pair_state_not_clean")
    if any(value != 0 for value in security_counts.values()):
        raise OnboardingError("first_pair_security_state_not_clean")


def _first_pair_success_evidence(expected_system_id: str) -> dict[str, Any]:
    counts = _db_counts()
    if not (
        counts["registrations"] == 1
        and counts["node_id_leases"] == 1
        and counts["pairing_sessions"] >= 1
        and counts["registration_events"] >= 1
    ):
        raise OnboardingError("first_pair_success_state_not_observed")

    manager = _read_only_connection(MANAGER_DB)
    try:
        rows = manager.execute(
            """
            SELECT
                r.hardware_id,
                r.current_pairing_id AS pairing_id,
                r.node_id,
                s.state AS pairing_state,
                l.state AS lease_state
            FROM registrations AS r
            JOIN pairing_sessions AS s
              ON s.pairing_id = r.current_pairing_id
            JOIN node_id_leases AS l
              ON l.node_id = r.node_id
             AND l.hardware_id = r.hardware_id
            """
        ).fetchall()
    finally:
        manager.close()
    if len(rows) != 1:
        raise OnboardingError("first_pair_registration_binding_ambiguous")
    registration = rows[0]
    if (
        not isinstance(registration["hardware_id"], str)
        or not isinstance(registration["pairing_id"], str)
        or not isinstance(registration["node_id"], str)
        or registration["pairing_state"] != "approved"
        or registration["lease_state"] != "active"
    ):
        raise OnboardingError("first_pair_registration_binding_invalid")

    security_counts = _security_state_counts()
    if security_counts != {
        "credential_assignments": 1,
        "application_key_active_nodes": 1,
        "application_key_epochs": 1,
    }:
        raise OnboardingError("first_pair_security_state_not_exact")

    credentials = _read_only_connection(CREDENTIAL_DB)
    try:
        rows = credentials.execute(
            """
            SELECT
                hardware_id,
                pairing_id,
                node_id,
                active_generation,
                pending_generation,
                state,
                revoked_at
            FROM credential_assignments
            WHERE state != 'revoked'
            """
        ).fetchall()
    finally:
        credentials.close()
    if len(rows) != 1:
        raise OnboardingError("first_pair_credential_binding_ambiguous")
    credential = rows[0]
    if (
        credential["hardware_id"] != registration["hardware_id"]
        or credential["pairing_id"] != registration["pairing_id"]
        or credential["node_id"] != registration["node_id"]
        or credential["state"] != "active"
        or credential["pending_generation"] is not None
        or credential["revoked_at"] is not None
        or not isinstance(credential["active_generation"], int)
        or credential["active_generation"] != 1
    ):
        raise OnboardingError("first_pair_credential_binding_invalid")

    keys = _read_only_connection(APPLICATION_KEY_DB)
    try:
        versions = keys.execute(
            "SELECT schema_version FROM n3w_relay_meta"
        ).fetchall()
        if len(versions) != 1 or versions[0]["schema_version"] != 2:
            raise OnboardingError("application_key_schema_version_invalid")
        node_rows = keys.execute(
            "SELECT node_id, active FROM n3w_relay_nodes WHERE active = 1"
        ).fetchall()
        key_rows = keys.execute(
            """
            SELECT
                node_id,
                key_epoch,
                key_file,
                enabled,
                state,
                key_sha256
            FROM n3w_relay_key_epochs
            WHERE enabled = 1
              AND state IN ('ACTIVE', 'GRACE')
            """
        ).fetchall()
    finally:
        keys.close()
    if len(node_rows) != 1 or len(key_rows) != 1:
        raise OnboardingError("first_pair_application_key_binding_ambiguous")
    node = node_rows[0]
    key = key_rows[0]
    if (
        node["node_id"] != registration["node_id"]
        or key["node_id"] != registration["node_id"]
        or key["state"] != "ACTIVE"
        or key["key_epoch"] != credential["active_generation"]
        or not isinstance(key["key_file"], str)
        or "/" in key["key_file"]
        or key["key_file"] in {"", ".", ".."}
        or not isinstance(key["key_sha256"], str)
        or len(key["key_sha256"]) != 64
    ):
        raise OnboardingError("first_pair_application_key_binding_invalid")

    if (
        APPLICATION_KEY_DIR.is_symlink()
        or not APPLICATION_KEY_DIR.is_dir()
        or stat.S_IMODE(APPLICATION_KEY_DIR.stat().st_mode) & 0o077
    ):
        raise OnboardingError("application_key_directory_invalid")
    key_path = APPLICATION_KEY_DIR / key["key_file"]
    _require_file(key_path)
    if stat.S_IMODE(key_path.stat().st_mode) & 0o077:
        raise OnboardingError("application_key_file_permissions_invalid")
    material = key_path.read_bytes()
    if (
        len(material) != 32
        or hashlib.sha256(material).hexdigest() != key["key_sha256"]
    ):
        raise OnboardingError("first_pair_application_key_material_invalid")

    if not isinstance(expected_system_id, str) or not expected_system_id:
        raise OnboardingError("first_pair_system_id_invalid")
    peer_trust = _read_only_connection(PEER_TRUST_DB)
    try:
        table = peer_trust.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='n3w_system_peer_trust'"
        ).fetchone()
        if table is None:
            raise OnboardingError("peer_trust_table_missing")
        peer_rows = peer_trust.execute(
            """
            SELECT system_id, generation, key_material
            FROM n3w_system_peer_trust
            """
        ).fetchall()
    finally:
        peer_trust.close()
    if len(peer_rows) != 1:
        raise OnboardingError("first_pair_peer_trust_binding_ambiguous")
    peer = peer_rows[0]
    peer_key = peer["key_material"]
    if (
        peer["system_id"] != expected_system_id
        or peer["generation"] != 1
        or not isinstance(peer_key, bytes)
        or len(peer_key) != 32
        or not any(peer_key)
    ):
        raise OnboardingError("first_pair_peer_trust_binding_invalid")

    return {
        "database_counts": counts,
        "security_counts": security_counts,
        "hardware_id_sha256": _sha256_text(registration["hardware_id"]),
        "pairing_id_sha256": _sha256_text(registration["pairing_id"]),
        "node_id_sha256": _sha256_text(registration["node_id"]),
        "credential_generation": credential["active_generation"],
        "application_key_epoch": key["key_epoch"],
        "peer_trust_generation": peer["generation"],
        "peer_trust_system_id_sha256": _sha256_text(peer["system_id"]),
    }


def _is_rfc1918_ipv4(address: ipaddress.IPv4Address) -> bool:
    value = int(address)
    return (
        value & 0xFF000000 == 0x0A000000
        or value & 0xFFF00000 == 0xAC100000
        or value & 0xFFFF0000 == 0xC0A80000
    )


def _resolve_route_selected_broker(
    manager_id: str,
    peer_ip: str,
) -> str:
    try:
        peer = ipaddress.ip_address(peer_ip)
    except ValueError as error:
        raise OnboardingError("peer_ip_invalid") from error
    if (
        peer.version != 4
        or peer.is_unspecified
        or peer.is_multicast
        or peer.is_loopback
        or peer.is_link_local
        or not _is_rfc1918_ipv4(peer)
    ):
        raise OnboardingError("peer_ip_invalid")
    script = (
        "import json,sys;"
        "from greenhouse_manager.runtime.pairing_discovery import is_local_source;"
        "from greenhouse_manager.runtime.n3w_simplified_discovery import resolve_route_selected_ipv4;"
        "peer=sys.argv[1];"
        "local=is_local_source(peer);"
        "selected=resolve_route_selected_ipv4(peer) if local else '';"
        "print(json.dumps({'local':local,'selected':selected},separators=(',',':')))"
    )
    raw = _run(
        (
            "docker",
            "exec",
            manager_id,
            "python",
            "-c",
            script,
            str(peer),
        )
    )
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise OnboardingError("route_selected_result_invalid") from error
    if not isinstance(document, dict) or document.get("local") is not True:
        raise OnboardingError("peer_not_local")
    selected_raw = document.get("selected")
    if not isinstance(selected_raw, str):
        raise OnboardingError("route_selected_ipv4_invalid")
    try:
        selected = ipaddress.ip_address(selected_raw)
    except ValueError as error:
        raise OnboardingError("route_selected_ipv4_invalid") from error
    if (
        selected.version != 4
        or selected.is_unspecified
        or selected.is_multicast
        or selected.is_loopback
        or selected.is_link_local
        or not _is_rfc1918_ipv4(selected)
    ):
        raise OnboardingError("route_selected_ipv4_not_private_lan")
    return str(selected)


def _probe_external_broker_tls(host: str) -> None:
    _require_file(CA_CERT)
    context = ssl.create_default_context(cafile=str(CA_CERT))
    try:
        with socket.create_connection(
            (host, BROKER_TLS_PORT),
            timeout=5,
        ) as raw, context.wrap_socket(
            raw,
            server_hostname=BROKER_TLS_SERVER_NAME,
        ):
            pass
    except (OSError, ssl.SSLError) as error:
        raise OnboardingError("external_broker_tls_probe_failed") from error


def _probe_manager_broker_tls(manager_id: str) -> None:
    script = (
        "import socket,ssl;"
        "ctx=ssl.create_default_context(cafile='/run/n3w/tls/ca.pem');"
        "raw=socket.create_connection(('armbian',8883),5);"
        "tls=ctx.wrap_socket(raw,server_hostname='armbian');"
        "tls.close()"
    )
    _run(
        (
            "docker",
            "exec",
            manager_id,
            "python",
            "-c",
            script,
        ),
        timeout=15,
    )


def _listener_count(protocol: str, port: int) -> int:
    if protocol == "udp":
        raw = _run(("ss", "-H", "-lun", f"sport = :{port}"))
    elif protocol == "tcp":
        raw = _run(("ss", "-H", "-ltn", f"sport = :{port}"))
    else:
        raise OnboardingError("listener_protocol_invalid")
    return sum(1 for line in raw.splitlines() if line.strip())


def _pairing_health() -> None:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{PAIRING_HTTP_PORT}/healthz",
            timeout=3,
        ) as response:
            if response.status != 200:
                raise OnboardingError("pairing_health_http_status_invalid")
            payload = response.read(4096)
    except OSError as error:
        raise OnboardingError("pairing_health_unavailable") from error
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise OnboardingError("pairing_health_json_invalid") from error
    if document != {
        "schema": "gh.pair.simple-health/1",
        "status": "ok",
    }:
        raise OnboardingError("pairing_health_contract_invalid")


def _pairing_socket_ready(manager_id: str) -> None:
    _run(
        (
            "docker",
            "exec",
            manager_id,
            "test",
            "-S",
            "/run/greenhouse-manager/pairing.sock",
        )
    )


def _prepare_runtime_root(transaction: dict[str, Any]) -> None:
    if RUNTIME_ROOT.exists() or RUNTIME_ROOT.is_symlink():
        raise OnboardingError("onboarding_runtime_root_not_fresh")
    RUNTIME_ROOT.mkdir(mode=0o700)
    _require_private_directory(RUNTIME_ROOT)

    source = Path(__file__).resolve()
    source_sha = _sha256_file(source)
    if transaction.get("tool_sha256") != source_sha:
        raise OnboardingError("onboarding_tool_binding_drift")

    payload = source.read_bytes()
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        fd = os.open(WATCHDOG_TOOL_PATH, flags, 0o600)
    except OSError as error:
        raise OnboardingError("watchdog_tool_copy_create_failed") from error
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if WATCHDOG_TOOL_PATH.exists():
            metadata = WATCHDOG_TOOL_PATH.stat()
            if (
                metadata.st_uid != os.geteuid()
                or metadata.st_gid != os.getegid()
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_nlink != 1
                or _sha256_file(WATCHDOG_TOOL_PATH) != source_sha
            ):
                raise OnboardingError("watchdog_tool_copy_binding_invalid")

    dir_fd = os.open(
        RUNTIME_ROOT,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _write_override(broker_host: str) -> None:
    _require_private_directory(RUNTIME_ROOT)
    content = (
        "services:\n"
        "  manager:\n"
        "    environment:\n"
        '      GH_N3W_PRODUCT_PAIRING_ENABLED: "true"\n'
        f'      GH_N3W_NODE_BROKER_HOST: "{broker_host}"\n'
    )
    fd, raw_tmp = tempfile.mkstemp(
        prefix=".manager-pairing.",
        suffix=".yml",
        dir=str(RUNTIME_ROOT),
    )
    tmp = Path(raw_tmp)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", closefd=True) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, OVERRIDE_PATH)
        dir_fd = os.open(RUNTIME_ROOT, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


def _remove_override() -> None:
    try:
        OVERRIDE_PATH.unlink()
    except FileNotFoundError:
        return
    if RUNTIME_ROOT.exists():
        dir_fd = os.open(RUNTIME_ROOT, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def _watchdog_unit_name(authorization_id: str) -> str:
    return (
        WATCHDOG_UNIT_PREFIX
        + _sha256_text(authorization_id)[:16]
    )


def _systemctl_is_active(unit: str) -> bool:
    output = _run(
        ("systemctl", "is-active", unit),
        timeout=20,
        allowed=frozenset({0, 3, 4}),
    )
    return output.strip() == "active"


def _watchdog_is_active(transaction: dict[str, Any]) -> bool:
    unit = transaction.get("watchdog_unit")
    if not isinstance(unit, str) or not unit.startswith(WATCHDOG_UNIT_PREFIX):
        return False
    return _systemctl_is_active(f"{unit}.timer")


def _arm_watchdog(transaction: dict[str, Any]) -> dict[str, Any]:
    authorization_id = transaction.get("authorization_id")
    expires_at = transaction.get("expires_at_unix")
    if (
        not isinstance(authorization_id, str)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
    ):
        raise OnboardingError("watchdog_transaction_binding_invalid")

    authorization_sha = _sha256_text(authorization_id)
    unit = _watchdog_unit_name(authorization_id)
    remaining = expires_at - int(time.time())
    if remaining < 1:
        raise OnboardingError("watchdog_deadline_elapsed")

    _prepare_runtime_root(transaction)

    command_error_type = ""
    try:
        _run(
            (
                "systemd-run",
                "--quiet",
                "--collect",
                f"--unit={unit}",
                f"--on-active={remaining}s",
                "--timer-property=AccuracySec=1s",
                "--property=Type=exec",
                "--property=Restart=on-failure",
                "--property=RestartSec=10s",
                PYTHON_EXECUTABLE,
                str(WATCHDOG_TOOL_PATH),
                "expire",
                "--authorization-sha256",
                authorization_sha,
            ),
            timeout=20,
        )
    except OPERATION_ERRORS as error:
        command_error_type = type(error).__name__

    if not _systemctl_is_active(f"{unit}.timer"):
        raise OnboardingError(
            "watchdog_not_active:"
            f"{command_error_type or 'no_command_error'}"
        )

    return _advance_transaction(
        status="WATCHDOG_ARMED",
        watchdog_unit=unit,
        watchdog_armed=True,
        watchdog_authorization_sha256=authorization_sha,
        watchdog_tool_sha256=_sha256_file(WATCHDOG_TOOL_PATH),
        watchdog_command_error_type=command_error_type,
        watchdog_armed_at_unix=int(time.time()),
    )


def _cancel_watchdog(transaction: dict[str, Any]) -> str:
    unit = transaction.get("watchdog_unit")
    if not isinstance(unit, str) or not unit.startswith(WATCHDOG_UNIT_PREFIX):
        return "NOT_PRESENT"

    command_error_type = ""
    try:
        _run(
            (
                "systemctl",
                "stop",
                f"{unit}.timer",
                f"{unit}.service",
            ),
            timeout=20,
            allowed=frozenset({0, 5}),
        )
    except OPERATION_ERRORS as error:
        command_error_type = type(error).__name__

    if _systemctl_is_active(f"{unit}.timer"):
        raise OnboardingError("watchdog_timer_still_active")
    if _systemctl_is_active(f"{unit}.service"):
        raise OnboardingError("watchdog_service_still_active")
    return command_error_type


def _start_watchdog_recovery_now(
    transaction: dict[str, Any],
) -> str:
    unit = transaction.get("watchdog_unit")
    if (
        not isinstance(unit, str)
        or re.fullmatch(
            rf"{re.escape(WATCHDOG_UNIT_PREFIX)}[0-9a-f]{{16}}",
            unit,
        )
        is None
    ):
        raise OnboardingError("watchdog_recovery_unit_invalid")

    command_error_type = ""
    try:
        _run(
            (
                "systemctl",
                "start",
                f"{unit}.service",
            ),
            timeout=20,
        )
    except OPERATION_ERRORS as error:
        command_error_type = type(error).__name__

    if not _systemctl_is_active(f"{unit}.service"):
        raise OnboardingError(
            "watchdog_recovery_service_not_active:"
            f"{command_error_type or 'no_command_error'}"
        )
    return command_error_type


def _watchdog_terminal_status(status: object) -> bool:
    return status in {
        "STOPPED_WATCHDOG_ARM_FAILED",
        "STOPPED_OPEN_FAILED",
        "STOPPED_TIMEOUT_RESTORE_FAILED",
        "FACTORY_RESTORED",
        "CLOSED_PASS",
        "CLOSED_ABORTED",
        "CLOSED_FAIL_WINDOW_EXPIRED",
        "CLOSED_FAIL_WATCHDOG_LOST",
        "CLOSED_TIMEOUT",
        "CLOSED_TIMEOUT_PREOPEN",
        "CLOSED_RECOVERY_AFTER_OPEN_FAILURE",
    }


def _recreate_manager(*, override: bool) -> None:
    _run(
        _compose_argv(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "manager",
            override=override,
        ),
        timeout=60,
    )


def _restore_factory_manager(
    non_manager_baseline: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    command_error_type = ""
    try:
        _recreate_manager(override=False)
    except OPERATION_ERRORS as error:
        command_error_type = type(error).__name__
    _remove_override()
    try:
        manager = _wait_factory_ready()
        after = _runtime_snapshot()
        _validate_non_manager_continuity(
            non_manager_baseline,
            after,
        )
    except OPERATION_ERRORS as error:
        raise OnboardingError(
            "factory_restore_unproven:"
            f"command_{command_error_type or 'none'}:"
            f"verify_{type(error).__name__}"
        ) from error
    return manager, command_error_type


def _wait_onboarding_ready(
    expected_host: str,
    *,
    timeout_s: float = 45.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last_error = "unknown"
    while time.monotonic() < deadline:
        try:
            manager = _container_snapshot("manager")
            env = manager["env"]
            if env.get("GH_N3W_PRODUCT_PAIRING_ENABLED") != "true":
                raise OnboardingError("manager_pairing_not_enabled")
            if env.get("GH_N3W_NODE_BROKER_HOST") != expected_host:
                raise OnboardingError("manager_broker_host_mismatch")
            if _listener_count("udp", PAIRING_UDP_PORT) != 1:
                raise OnboardingError("pairing_udp_listener_count_invalid")
            if _listener_count("tcp", PAIRING_HTTP_PORT) != 1:
                raise OnboardingError("pairing_tcp_listener_count_invalid")
            _pairing_health()
            _pairing_socket_ready(manager["id"])
            _probe_manager_broker_tls(manager["id"])
            return manager
        except OnboardingError as error:
            last_error = str(error)
            time.sleep(1)
    raise OnboardingError(f"onboarding_ready_timeout:{last_error}")


def _wait_factory_ready(
    *,
    timeout_s: float = 45.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last_error = "unknown"
    while time.monotonic() < deadline:
        try:
            manager = _container_snapshot("manager")
            env = manager["env"]
            if env.get("GH_N3W_PRODUCT_PAIRING_ENABLED") != "false":
                raise OnboardingError("manager_pairing_not_disabled")
            if env.get("GH_N3W_NODE_BROKER_HOST") != FACTORY_BROKER_PLACEHOLDER:
                raise OnboardingError("manager_factory_broker_not_restored")
            if _listener_count("udp", PAIRING_UDP_PORT) != 0:
                raise OnboardingError("pairing_udp_listener_still_open")
            if _listener_count("tcp", PAIRING_HTTP_PORT) != 0:
                raise OnboardingError("pairing_tcp_listener_still_open")
            _probe_manager_broker_tls(manager["id"])
            return manager
        except OnboardingError as error:
            last_error = str(error)
            time.sleep(1)
    raise OnboardingError(f"factory_ready_timeout:{last_error}")


def _validate_non_manager_continuity(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> None:
    for service in ("broker", "homeassistant"):
        if before[service]["id"] != after[service]["id"]:
            raise OnboardingError(f"{service}_container_identity_changed")
        if after[service]["restart_count"] != before[service]["restart_count"]:
            raise OnboardingError(f"{service}_restart_count_changed")


def _authorization_id(value: str) -> str:
    if (
        not value.startswith("N3W_T1_FIRST_PAIRING_")
        or len(value) > 200
        or not value.replace("_", "").replace("-", "").isalnum()
    ):
        raise OnboardingError("authorization_id_invalid")
    return value


def _claim_transaction(
    *,
    authorization_id: str,
    factory: dict[str, Any],
    peer_ip: str,
    broker_host: str,
    baseline: dict[str, dict[str, Any]],
    window_seconds: int,
) -> dict[str, Any]:
    if TRANSACTION_PATH.exists() or TRANSACTION_PATH.is_symlink():
        raise OnboardingError("onboarding_transaction_already_exists")
    now = int(time.time())
    document = {
        "schema": TRANSACTION_SCHEMA,
        "status": "CLAIMED",
        "authorization_id": authorization_id,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "release_id": factory["release_id"],
        "host_instance_id": factory["host_instance_id"],
        "system_id": factory["system_id"],
        "peer_ip": peer_ip,
        "broker_host": broker_host,
        "broker_host_sha256": _sha256_text(broker_host),
        "window_seconds": window_seconds,
        "claimed_at_unix": now,
        "expires_at_unix": now + window_seconds,
        "baseline_container_ids": {
            service: baseline[service]["id"]
            for service in sorted(EXPECTED_SERVICES)
        },
        "manager_recreate_command_count": 0,
        "tool_sha256": _sha256_file(Path(__file__).resolve()),
    }
    _write_private_json(TRANSACTION_PATH, document)
    return document


def _advance_transaction(**fields: Any) -> dict[str, Any]:
    document = _read_private_json(TRANSACTION_PATH)
    document.update(fields)
    document["authorization_claimed"] = True
    document["authorization_consumed"] = True
    document["replay_allowed"] = False
    _write_private_json(TRANSACTION_PATH, document)
    return document


def _transaction() -> dict[str, Any]:
    document = _read_private_json(TRANSACTION_PATH)
    if (
        document.get("schema") != TRANSACTION_SCHEMA
        or document.get("authorization_claimed") is not True
        or document.get("authorization_consumed") is not True
        or document.get("replay_allowed") is not False
    ):
        raise OnboardingError("onboarding_transaction_invalid")

    authorization_id = document.get("authorization_id")
    if not isinstance(authorization_id, str):
        raise OnboardingError("onboarding_transaction_authorization_invalid")
    _authorization_id(authorization_id)

    status = document.get("status")
    allowed_statuses = {
        "CLAIMED",
        "WATCHDOG_ARMED",
        "OPEN",
        "STOPPED_WATCHDOG_ARM_FAILED",
        "STOPPED_OPEN_FAILED",
        "STOPPED_TIMEOUT_RESTORE_FAILED",
        "FACTORY_RESTORED",
        "CLOSED_PASS",
        "CLOSED_ABORTED",
        "CLOSED_FAIL_WINDOW_EXPIRED",
        "CLOSED_FAIL_WATCHDOG_LOST",
        "CLOSED_TIMEOUT",
        "CLOSED_TIMEOUT_PREOPEN",
        "CLOSED_RECOVERY_AFTER_OPEN_FAILURE",
    }
    if status not in allowed_statuses:
        raise OnboardingError("onboarding_transaction_status_invalid")

    for key in ("release_id", "host_instance_id", "system_id"):
        if not isinstance(document.get(key), str) or not document[key]:
            raise OnboardingError(f"onboarding_transaction_binding_invalid:{key}")

    peer_raw = document.get("peer_ip")
    broker_raw = document.get("broker_host")
    if not isinstance(peer_raw, str) or not isinstance(broker_raw, str):
        raise OnboardingError("onboarding_transaction_locator_invalid")
    try:
        peer = ipaddress.ip_address(peer_raw)
        broker = ipaddress.ip_address(broker_raw)
    except ValueError as error:
        raise OnboardingError("onboarding_transaction_locator_invalid") from error
    if (
        not isinstance(peer, ipaddress.IPv4Address)
        or not isinstance(broker, ipaddress.IPv4Address)
        or not _is_rfc1918_ipv4(peer)
        or not _is_rfc1918_ipv4(broker)
    ):
        raise OnboardingError("onboarding_transaction_locator_invalid")

    if document.get("broker_host_sha256") != _sha256_text(broker_raw):
        raise OnboardingError("onboarding_transaction_locator_hash_invalid")

    window_seconds = document.get("window_seconds")
    claimed_at = document.get("claimed_at_unix")
    expires_at = document.get("expires_at_unix")
    if (
        not isinstance(window_seconds, int)
        or isinstance(window_seconds, bool)
        or not 180 <= window_seconds <= 600
        or not isinstance(claimed_at, int)
        or isinstance(claimed_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or expires_at != claimed_at + window_seconds
    ):
        raise OnboardingError("onboarding_transaction_deadline_invalid")

    baseline = document.get("baseline_container_ids")
    if (
        not isinstance(baseline, dict)
        or set(baseline) != EXPECTED_SERVICES
        or any(
            not isinstance(value, str)
            or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in baseline.values()
        )
    ):
        raise OnboardingError("onboarding_transaction_container_binding_invalid")

    command_count = document.get("manager_recreate_command_count")
    if (
        not isinstance(command_count, int)
        or isinstance(command_count, bool)
        or command_count < 0
    ):
        raise OnboardingError("onboarding_transaction_command_count_invalid")

    tool_sha = document.get("tool_sha256")
    if (
        not isinstance(tool_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", tool_sha) is None
        or _sha256_file(Path(__file__).resolve()) != tool_sha
    ):
        raise OnboardingError("onboarding_transaction_tool_binding_invalid")

    if status in {
        "WATCHDOG_ARMED",
        "OPEN",
        "FACTORY_RESTORED",
        "CLOSED_PASS",
        "CLOSED_ABORTED",
        "CLOSED_FAIL_WINDOW_EXPIRED",
        "CLOSED_FAIL_WATCHDOG_LOST",
        "CLOSED_TIMEOUT",
        "CLOSED_TIMEOUT_PREOPEN",
    }:
        unit = document.get("watchdog_unit")
        auth_sha = document.get("watchdog_authorization_sha256")
        watchdog_tool_sha = document.get("watchdog_tool_sha256")
        if (
            not isinstance(unit, str)
            or re.fullmatch(
                rf"{re.escape(WATCHDOG_UNIT_PREFIX)}[0-9a-f]{{16}}",
                unit,
            )
            is None
            or unit != _watchdog_unit_name(authorization_id)
            or auth_sha != _sha256_text(authorization_id)
            or watchdog_tool_sha != tool_sha
        ):
            raise OnboardingError("onboarding_transaction_watchdog_binding_invalid")

    return document


def _public_runtime(snapshot: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "manager_running": True,
        "manager_restart_count": snapshot["manager"]["restart_count"],
        "manager_network_mode": snapshot["manager"]["network_mode"],
        "broker_running": True,
        "broker_restart_count": snapshot["broker"]["restart_count"],
        "homeassistant_running": True,
        "homeassistant_restart_count": snapshot["homeassistant"]["restart_count"],
    }


def inspect() -> dict[str, Any]:
    _require_root()
    _require_file(COMPOSE_TARGET)
    _require_file(COMPOSE_ENV)
    _validate_factory_compose()
    factory = _validate_factory_marker()
    runtime = _runtime_snapshot()
    counts = _db_counts()
    transaction: dict[str, Any] | None = None
    if TRANSACTION_PATH.exists() and not TRANSACTION_PATH.is_symlink():
        transaction = _transaction()
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "inspect",
        "factory_accepted": True,
        "factory_release_sha256": _sha256_text(str(factory["release_id"])),
        "database_counts": counts,
        "security_counts": _security_state_counts(),
        "transaction_present": transaction is not None,
        "mutation": False,
        "factory_pairing_udp_listener_count": (
            _listener_count("udp", PAIRING_UDP_PORT)
        ),
        "factory_pairing_http_listener_count": (
            _listener_count("tcp", PAIRING_HTTP_PORT)
        ),
    }
    report.update(_public_runtime(runtime))
    if transaction is None:
        _validate_factory_runtime(runtime)
        report.update(
            {
                "pairing_enabled": False,
                "pairing_window_state": "CLOSED_FACTORY",
                "authorization_reusable": None,
            }
        )
    else:
        status = str(transaction.get("status", "UNKNOWN"))
        report.update(
            {
                "pairing_window_state": status,
                "authorization_reusable": False,
                "broker_host_sha256": transaction.get("broker_host_sha256"),
                "window_expired": int(time.time())
                > int(transaction.get("expires_at_unix", 0)),
            }
        )
    return report


def open_window(
    *,
    authorization_id: str,
    peer_ip: str,
    confirmation: str,
    window_seconds: int,
) -> dict[str, Any]:
    _require_root()
    if confirmation != OPEN_CONFIRMATION:
        raise OnboardingError("open_confirmation_invalid")
    if not 180 <= window_seconds <= 600:
        raise OnboardingError("window_seconds_invalid")
    authorization_id = _authorization_id(authorization_id)
    _require_file(COMPOSE_TARGET)
    _require_file(COMPOSE_ENV)
    _require_file(CA_CERT)
    _validate_factory_compose()
    factory = _validate_factory_marker()
    baseline = _runtime_snapshot()
    _validate_factory_runtime(baseline)
    counts = _db_counts()
    security_counts = _security_state_counts()
    _require_clean_first_pair_state(counts, security_counts)
    if _listener_count("udp", PAIRING_UDP_PORT) != 0:
        raise OnboardingError("preopen_pairing_udp_listener_present")
    if _listener_count("tcp", PAIRING_HTTP_PORT) != 0:
        raise OnboardingError("preopen_pairing_tcp_listener_present")
    broker_host = _resolve_route_selected_broker(
        baseline["manager"]["id"],
        peer_ip,
    )
    _probe_external_broker_tls(broker_host)
    transaction = _claim_transaction(
        authorization_id=authorization_id,
        factory=factory,
        peer_ip=peer_ip,
        broker_host=broker_host,
        baseline=baseline,
        window_seconds=window_seconds,
    )
    try:
        transaction = _arm_watchdog(transaction)
    except OPERATION_ERRORS as error:
        try:
            _advance_transaction(
                status="STOPPED_WATCHDOG_ARM_FAILED",
                watchdog_arm_failure_type=type(error).__name__,
            )
        except OPERATION_ERRORS:
            pass
        raise OnboardingError(
            f"watchdog_arm_failed:{type(error).__name__}"
        ) from error

    manager_mutation_started = False
    try:
        _write_override(broker_host)
        _validate_override_compose(broker_host)
        manager_mutation_started = True
        _recreate_manager(override=True)
        opened_manager = _wait_onboarding_ready(broker_host)
        after = _runtime_snapshot()
        _validate_non_manager_continuity(baseline, after)
        if opened_manager["id"] == baseline["manager"]["id"]:
            raise OnboardingError("manager_not_recreated")
        watchdog_active = _watchdog_is_active(transaction)
        if not watchdog_active:
            raise OnboardingError("watchdog_lost_before_open_acceptance")
        transaction = _advance_transaction(
            status="OPEN",
            manager_recreate_command_count=1,
            watchdog_confirmed_active=True,
            opened_manager_id=opened_manager["id"],
            opened_manager_id_sha256=opened_manager["id_sha256"],
            opened_at_unix=int(time.time()),
            broker_continuity=True,
            homeassistant_continuity=True,
            pairing_udp_listener_count=1,
            pairing_http_listener_count=1,
            pairing_health="PASS",
            pairing_socket="PASS",
            manager_broker_tls="PASS",
            external_broker_tls="PASS",
        )
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "open",
            "authorization_consumed": True,
            "replay_allowed": False,
            "pairing_window_state": "OPEN",
            "broker_host_sha256": transaction["broker_host_sha256"],
            "window_seconds": window_seconds,
            "watchdog_active": True,
            "manager_recreated": True,
            "broker_container_unchanged": True,
            "homeassistant_container_unchanged": True,
            "pairing_udp_listener_count": 1,
            "pairing_http_listener_count": 1,
            "pairing_health": "PASS",
            "pairing_socket": "PASS",
            "manager_broker_tls": "PASS",
            "external_broker_tls": "PASS",
            "raw_locator_in_output": False,
        }
    except OPERATION_ERRORS as error:
        rollback_status = "NOT_REQUIRED"
        rollback_error = ""
        rollback_command_error = ""
        if manager_mutation_started:
            try:
                _restored_manager, rollback_command_error = (
                    _restore_factory_manager(baseline)
                )
                rollback_status = "PASS"
            except OPERATION_ERRORS as rollback:
                rollback_status = "FAIL"
                rollback_error = type(rollback).__name__
        else:
            _remove_override()

        if rollback_status == "FAIL":
            pending = _advance_transaction(
                status="OPEN_RESTORE_PENDING",
                manager_recreate_command_count=2,
                rollback_status=rollback_status,
                rollback_error_type=rollback_error,
                rollback_command_error_type=rollback_command_error,
                failure_type=type(error).__name__,
                watchdog_recovery_required=True,
            )
            recovery_start_error = ""
            try:
                recovery_start_error = _start_watchdog_recovery_now(
                    pending
                )
            except OPERATION_ERRORS as recovery_error:
                _advance_transaction(
                    status="OPEN_RESTORE_PENDING",
                    watchdog_recovery_start_failure_type=type(
                        recovery_error
                    ).__name__,
                    watchdog_recovery_required=True,
                )
                raise OnboardingError(
                    "open_failed:"
                    f"{type(error).__name__}:rollback_FAIL:"
                    "watchdog_recovery_start_failed"
                ) from recovery_error
            _advance_transaction(
                status="OPEN_RESTORE_PENDING",
                watchdog_recovery_start_error_type=recovery_start_error,
                watchdog_recovery_required=True,
            )
            raise OnboardingError(
                f"open_failed:{type(error).__name__}:"
                "rollback_FAIL:watchdog_recovery_active"
            ) from error

        stopped = _advance_transaction(
            status="STOPPED_OPEN_FAILED",
            manager_recreate_command_count=2 if manager_mutation_started else 0,
            rollback_status=rollback_status,
            rollback_error_type=rollback_error,
            rollback_command_error_type=rollback_command_error,
            failure_type=type(error).__name__,
        )
        try:
            _cancel_watchdog(stopped)
        except OPERATION_ERRORS:
            pass
        raise OnboardingError(
            f"open_failed:{type(error).__name__}:rollback_{rollback_status}"
        ) from error


def close_window(
    *,
    authorization_id: str,
    confirmation: str,
    outcome: str,
) -> dict[str, Any]:
    _require_root()
    if confirmation != CLOSE_CONFIRMATION:
        raise OnboardingError("close_confirmation_invalid")
    authorization_id = _authorization_id(authorization_id)
    transaction = _transaction()
    if transaction.get("authorization_id") != authorization_id:
        raise OnboardingError("close_authorization_mismatch")
    if transaction.get("status") != "OPEN":
        raise OnboardingError("pairing_window_not_open")
    baseline_ids = transaction.get("baseline_container_ids")
    if not isinstance(baseline_ids, dict):
        raise OnboardingError("baseline_container_binding_missing")
    before = _runtime_snapshot()
    for service in ("broker", "homeassistant"):
        if before[service]["id"] != baseline_ids.get(service):
            raise OnboardingError(f"{service}_container_drift_before_close")
    manager = before["manager"]
    if manager["env"].get("GH_N3W_PRODUCT_PAIRING_ENABLED") != "true":
        raise OnboardingError("pairing_not_enabled_before_close")
    if manager["env"].get("GH_N3W_NODE_BROKER_HOST") != transaction.get("broker_host"):
        raise OnboardingError("broker_host_drift_before_close")
    if outcome not in {"success", "abort"}:
        raise OnboardingError("close_outcome_invalid")
    watchdog_active_before_close = _watchdog_is_active(transaction)
    success_evidence: dict[str, Any] | None = None
    if outcome == "success":
        expected_system_id = transaction.get("system_id")
        if not isinstance(expected_system_id, str) or not expected_system_id:
            raise OnboardingError("onboarding_transaction_system_id_invalid")
        success_evidence = _first_pair_success_evidence(
            expected_system_id
        )
        counts = dict(success_evidence["database_counts"])
        security_counts = dict(success_evidence["security_counts"])
    else:
        counts = _db_counts()
        security_counts = _security_state_counts()
    expired = int(time.time()) > int(transaction.get("expires_at_unix", 0))
    closed_manager, close_command_error = _restore_factory_manager(before)
    post_counts = _db_counts()
    post_security_counts = _security_state_counts()
    if post_counts != counts:
        raise OnboardingError("manager_database_counts_changed_during_close")
    if post_security_counts != security_counts:
        raise OnboardingError("security_state_counts_changed_during_close")

    restored = _advance_transaction(
        status="FACTORY_RESTORED",
        factory_restored_at_unix=int(time.time()),
        manager_recreate_command_count=(
            int(transaction.get("manager_recreate_command_count", 1)) + 1
        ),
        closed_manager_id=closed_manager["id"],
        closed_manager_id_sha256=closed_manager["id_sha256"],
        close_command_error_type=close_command_error,
        final_database_counts=post_counts,
        final_security_counts=post_security_counts,
        success_evidence=success_evidence,
        broker_continuity=True,
        homeassistant_continuity=True,
        factory_pairing_disabled=True,
        factory_broker_placeholder_restored=True,
        watchdog_active_before_close=watchdog_active_before_close,
    )
    watchdog_cancel_error = _cancel_watchdog(restored)

    terminal = "CLOSED_ABORTED"
    result_status = "PASS"
    if outcome == "success":
        if expired:
            terminal = "CLOSED_FAIL_WINDOW_EXPIRED"
            result_status = "FAIL"
        elif not watchdog_active_before_close:
            terminal = "CLOSED_FAIL_WATCHDOG_LOST"
            result_status = "FAIL"
        else:
            terminal = "CLOSED_PASS"
    _advance_transaction(
        status=terminal,
        closed_at_unix=int(time.time()),
        close_outcome=outcome,
        window_expired=expired,
        manager_recreate_command_count=restored[
            "manager_recreate_command_count"
        ],
        watchdog_active_before_close=watchdog_active_before_close,
        watchdog_cancel_error_type=watchdog_cancel_error,
    )
    return {
        "schema": SCHEMA,
        "status": result_status,
        "operation": "close",
        "authorization_consumed": True,
        "replay_allowed": False,
        "pairing_window_state": terminal,
        "close_outcome": outcome,
        "window_expired": expired,
        "watchdog_active_before_close": watchdog_active_before_close,
        "watchdog_cancel_error_type": watchdog_cancel_error,
        "database_counts": post_counts,
        "security_counts": post_security_counts,
        "success_evidence": success_evidence,
        "manager_factory_state_observed": True,
        "compose_command_error_type": close_command_error,
        "broker_container_unchanged": True,
        "homeassistant_container_unchanged": True,
        "factory_pairing_disabled": True,
        "factory_broker_placeholder_restored": True,
        "pairing_udp_listener_count": 0,
        "pairing_http_listener_count": 0,
        "raw_locator_in_output": False,
    }


def expire_window(
    *,
    authorization_sha256: str,
) -> dict[str, Any]:
    _require_root()
    if re.fullmatch(r"[0-9a-f]{64}", authorization_sha256) is None:
        raise OnboardingError("watchdog_authorization_hash_invalid")

    transaction = _transaction()
    authorization_id = transaction.get("authorization_id")
    if (
        not isinstance(authorization_id, str)
        or _sha256_text(authorization_id) != authorization_sha256
    ):
        raise OnboardingError("watchdog_authorization_binding_mismatch")

    status = transaction.get("status")
    if _watchdog_terminal_status(status):
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "expire",
            "pairing_window_state": status,
            "mutation": False,
            "already_terminal": True,
            "raw_locator_in_output": False,
        }
    if status not in {
        "CLAIMED",
        "WATCHDOG_ARMED",
        "OPEN",
        "OPEN_RESTORE_PENDING",
        "TIMEOUT_RESTORE_PENDING",
    }:
        raise OnboardingError("watchdog_transaction_state_invalid")

    expires_at = int(transaction["expires_at_unix"])
    remaining = expires_at - int(time.time())
    if (
        status not in {
            "OPEN_RESTORE_PENDING",
            "TIMEOUT_RESTORE_PENDING",
        }
        and remaining > 0
    ):
        time.sleep(remaining)

    transaction = _transaction()
    status = transaction.get("status")
    if _watchdog_terminal_status(status):
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "expire",
            "pairing_window_state": status,
            "mutation": False,
            "already_terminal": True,
            "raw_locator_in_output": False,
        }

    baseline_ids = transaction.get("baseline_container_ids")
    if not isinstance(baseline_ids, dict):
        raise OnboardingError("watchdog_baseline_binding_missing")

    non_manager_before = {
        "broker": _container_snapshot("broker"),
        "homeassistant": _container_snapshot("homeassistant"),
    }
    for service in ("broker", "homeassistant"):
        if non_manager_before[service]["id"] != baseline_ids.get(service):
            raise OnboardingError(
                f"watchdog_{service}_container_drift"
            )

    manager_restore_required = True
    try:
        manager = _container_snapshot("manager")
        env = manager["env"]
        factory_runtime = (
            env.get("GH_N3W_PRODUCT_PAIRING_ENABLED") == "false"
            and env.get("GH_N3W_NODE_BROKER_HOST")
            == FACTORY_BROKER_PLACEHOLDER
            and _listener_count("udp", PAIRING_UDP_PORT) == 0
            and _listener_count("tcp", PAIRING_HTTP_PORT) == 0
        )
        if factory_runtime:
            _probe_manager_broker_tls(manager["id"])
            manager_restore_required = False
    except OPERATION_ERRORS:
        manager_restore_required = True

    command_error = ""
    command_count = int(
        transaction.get("manager_recreate_command_count", 0)
    )
    if manager_restore_required:
        try:
            _closed_manager, command_error = _restore_factory_manager(
                non_manager_before
            )
            command_count += 1
        except OPERATION_ERRORS as error:
            try:
                _advance_transaction(
                    status="TIMEOUT_RESTORE_PENDING",
                    timeout_failure_type=type(error).__name__,
                    timeout_at_unix=int(time.time()),
                    manager_recreate_command_count=command_count + 1,
                    watchdog_recovery_required=True,
                )
            except OPERATION_ERRORS:
                pass
            raise

    post_counts = _db_counts()
    post_security_counts = _security_state_counts()
    previous_status = status
    if previous_status == "OPEN_RESTORE_PENDING":
        terminal = "CLOSED_RECOVERY_AFTER_OPEN_FAILURE"
    else:
        terminal = (
            "CLOSED_TIMEOUT"
            if manager_restore_required
            else "CLOSED_TIMEOUT_PREOPEN"
        )
    _advance_transaction(
        status=terminal,
        timeout_at_unix=int(time.time()),
        manager_recreate_command_count=command_count,
        timeout_restore_command_error_type=command_error,
        final_database_counts=post_counts,
        final_security_counts=post_security_counts,
        factory_pairing_disabled=True,
        factory_broker_placeholder_restored=True,
    )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "expire",
        "pairing_window_state": terminal,
        "authorization_consumed": True,
        "replay_allowed": False,
        "factory_pairing_disabled": True,
        "factory_broker_placeholder_restored": True,
        "pairing_udp_listener_count": 0,
        "pairing_http_listener_count": 0,
        "raw_locator_in_output": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="n3w-t1-first-pairing-onboarding",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("inspect")

    open_command = subparsers.add_parser("open")
    open_command.add_argument("--authorization-id", required=True)
    open_command.add_argument("--peer-ip", required=True)
    open_command.add_argument("--confirm", required=True)
    open_command.add_argument(
        "--window-seconds",
        type=int,
        default=300,
    )

    expire_command = subparsers.add_parser("expire")
    expire_command.add_argument(
        "--authorization-sha256",
        required=True,
    )

    close_command = subparsers.add_parser("close")
    close_command.add_argument("--authorization-id", required=True)
    close_command.add_argument("--confirm", required=True)
    close_command.add_argument(
        "--outcome",
        choices=("success", "abort"),
        required=True,
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "inspect":
            report = inspect()
        elif args.command == "expire":
            with _exclusive_lock(blocking=True):
                report = expire_window(
                    authorization_sha256=args.authorization_sha256,
                )
        else:
            with _exclusive_lock():
                if args.command == "open":
                    report = open_window(
                        authorization_id=args.authorization_id,
                        peer_ip=args.peer_ip,
                        confirmation=args.confirm,
                        window_seconds=args.window_seconds,
                    )
                else:
                    report = close_window(
                        authorization_id=args.authorization_id,
                        confirmation=args.confirm,
                        outcome=args.outcome,
                    )
    except (
        OnboardingError,
        OSError,
        sqlite3.Error,
        subprocess.SubprocessError,
        ValueError,
    ) as error:
        report = {
            "schema": SCHEMA,
            "status": "STOP",
            "error": str(error),
            "mutation_state": "UNKNOWN_IF_POSTCLAIM"
            if TRANSACTION_PATH.exists()
            else "NONE",
            "authorization_reusable": False
            if TRANSACTION_PATH.exists()
            else None,
            "raw_locator_in_output": False,
        }
        print(
            json.dumps(
                report,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )
        return 2
    print(
        json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
