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
TRANSACTION_SCHEMA = "gh.n3w-t1-first-pairing-onboarding-transaction/2"
LEGACY_TRANSACTION_SCHEMA = "gh.n3w-t1-first-pairing-onboarding-transaction/1"
SUCCESSOR_RECOVERY_SCHEMA = "gh.n3w-t1-first-pairing-successor-recovery/1"
OPEN_CONFIRMATION = "OPEN FIRST PAIRING WINDOW: YES"
CLOSE_CONFIRMATION = "CLOSE FIRST PAIRING WINDOW: YES"
SUCCESSOR_RECOVERY_CONFIRMATION = "RECOVER EXPIRED FIRST PAIRING: YES"

COMPOSE_PROJECT = "n3wfc4"
COMPOSE_TARGET = Path("/etc/n3wfc4/docker-compose.yml")
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
CA_CERT = Path("/etc/n3wfc4/tls/ca.pem")
SERVER_CERT = Path("/etc/n3wfc4/tls/server.pem")
PROVISIONING_ROOT = Path("/var/lib/n3w-t1-provisioning")
FACTORY_ACCEPTED_PATH = PROVISIONING_ROOT / "FACTORY_ACCEPTED.json"
TRANSACTION_PATH = PROVISIONING_ROOT / "FIRST_PAIRING_ONBOARDING.json"
SUCCESSOR_RECOVERY_PATH = PROVISIONING_ROOT / "FIRST_PAIRING_SUCCESSOR_RECOVERY.json"
TRANSACTION_ARCHIVE_ROOT = PROVISIONING_ROOT / "first-pairing-onboarding-archive"
RUNTIME_ROOT = Path("/run/n3w-first-pairing-onboarding")
WATCHDOG_TOOL_PATH = RUNTIME_ROOT / "onboarding-watchdog.py"
WATCHDOG_UNIT_PREFIX = "n3w-first-pairing-watchdog-"
WATCHDOG_GRACE_SECONDS = 15
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


def _is_container_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(
            r"(?:[0-9a-f]{12}|[0-9a-f]{64})",
            value,
        )
        is not None
    )


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


def _read_private_bytes(path: Path) -> bytes:
    _require_file(path)
    metadata = path.stat()
    if (
        metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise OnboardingError(
            f"private_record_metadata_invalid:{path.name}"
        )
    try:
        return path.read_bytes()
    except OSError as error:
        raise OnboardingError(
            f"private_record_read_failed:{path.name}"
        ) from error


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


def _ensure_private_directory(path: Path) -> None:
    if not path.exists():
        try:
            path.mkdir(mode=0o700)
        except OSError as error:
            raise OnboardingError(
                f"private_directory_create_failed:{path.name}"
            ) from error
    _require_private_directory(path)


def _archive_predecessor_transaction(
    expected_sha256: str,
) -> Path:
    payload = _read_private_bytes(
        TRANSACTION_PATH
    )
    actual_sha256 = hashlib.sha256(
        payload
    ).hexdigest()
    if actual_sha256 != expected_sha256:
        raise OnboardingError(
            "predecessor_transaction_sha256_changed"
        )

    _ensure_private_directory(
        TRANSACTION_ARCHIVE_ROOT
    )
    archive_path = (
        TRANSACTION_ARCHIVE_ROOT
        / (
            "FIRST_PAIRING_ONBOARDING."
            f"{expected_sha256}.json"
        )
    )
    if (
        archive_path.exists()
        or archive_path.is_symlink()
    ):
        raise OnboardingError(
            "predecessor_transaction_archive_exists"
        )

    try:
        os.replace(
            TRANSACTION_PATH,
            archive_path,
        )
        for directory in (
            TRANSACTION_ARCHIVE_ROOT,
            PROVISIONING_ROOT,
        ):
            fd = os.open(
                directory,
                os.O_RDONLY
                | getattr(
                    os,
                    "O_DIRECTORY",
                    0,
                ),
            )
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except OSError as error:
        raise OnboardingError(
            "predecessor_transaction_archive_failed"
        ) from error

    if (
        hashlib.sha256(
            _read_private_bytes(
                archive_path
            )
        ).hexdigest()
        != expected_sha256
    ):
        raise OnboardingError(
            "predecessor_transaction_archive_hash_mismatch"
        )
    return archive_path


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
        "--profile",
        "application",
    ]
    argv.extend(tail)
    return tuple(argv)


def _render_compose() -> dict[str, Any]:
    raw = _run(
        _compose_argv(
            "config",
            "--format",
            "json",
        )
    )
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise OnboardingError(
            "rendered_compose_json_invalid"
        ) from error
    if not isinstance(document, dict):
        raise OnboardingError(
            "rendered_compose_invalid"
        )
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
    container_id = values[0]
    if not _is_container_id(
        container_id
    ):
        raise OnboardingError(
            f"{service}_container_id_invalid"
        )
    return container_id


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


def _validate_factory_runtime_configuration(
    snapshot: dict[str, dict[str, Any]],
) -> None:
    manager = snapshot["manager"]
    env = manager["env"]
    if manager["network_mode"] != "host":
        raise OnboardingError(
            "manager_runtime_network_mode_invalid"
        )
    if env.get("GH_N3W_RUNTIME_ENABLED") != "true":
        raise OnboardingError(
            "manager_runtime_n3w_disabled"
        )
    if (
        env.get(
            "GH_N3W_PRODUCT_PAIRING_ENABLED"
        )
        != "false"
    ):
        raise OnboardingError(
            "manager_runtime_pairing_not_disabled"
        )
    if (
        env.get(
            "GH_N3W_PAIRING_ADVERTISED_HOST"
        )
        != "auto"
    ):
        raise OnboardingError(
            "manager_runtime_advertised_host_invalid"
        )
    if (
        env.get(
            "GH_N3W_NODE_BROKER_HOST"
        )
        != FACTORY_BROKER_PLACEHOLDER
    ):
        raise OnboardingError(
            "manager_runtime_factory_broker_invalid"
        )
    if (
        env.get(
            "GH_N3W_NODE_BROKER_TLS_SERVER_NAME"
        )
        != BROKER_TLS_SERVER_NAME
    ):
        raise OnboardingError(
            "manager_runtime_tls_server_name_invalid"
        )
    _probe_manager_broker_tls(
        manager["id"]
    )


def _validate_factory_runtime(
    snapshot: dict[str, dict[str, Any]],
) -> None:
    _validate_factory_runtime_configuration(
        snapshot
    )
    if (
        _listener_count(
            "udp",
            PAIRING_UDP_PORT,
        )
        != 0
    ):
        raise OnboardingError(
            "factory_pairing_udp_listener_present"
        )
    if (
        _listener_count(
            "tcp",
            PAIRING_HTTP_PORT,
        )
        != 0
    ):
        raise OnboardingError(
            "factory_pairing_tcp_listener_present"
        )


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


def _optional_private_db_count(
    path: Path,
    *,
    table: str,
) -> int:
    if path.is_symlink():
        raise OnboardingError(f"optional_database_symlink:{path.name}")
    if not path.exists():
        return 0
    if not path.is_file():
        raise OnboardingError(f"optional_database_invalid:{path.name}")

    connection = _read_only_connection(path)
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists is None:
            raise OnboardingError(
                f"optional_database_table_missing:{path.name}:{table}"
            )
        return int(
            connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
        )
    finally:
        connection.close()


def _security_state_counts() -> dict[str, int]:
    credential_assignments = _optional_private_db_count(
        CREDENTIAL_DB,
        table="credential_assignments",
    )
    peer_trust_records = _optional_private_db_count(
        PEER_TRUST_DB,
        table="n3w_system_peer_trust",
    )

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
        "peer_trust_records": peer_trust_records,
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


def _successor_recovery_candidate() -> dict[str, Any]:
    manager = _read_only_connection(
        MANAGER_DB
    )
    try:
        current = manager.execute(
            """
            SELECT
                r.hardware_id,
                r.current_pairing_id AS pairing_id,
                r.node_id,
                r.logical_location_id,
                s.state,
                s.reason,
                CASE
                    WHEN julianday(s.expires_at)
                         < julianday('now')
                    THEN 1
                    ELSE 0
                END AS expired_by_clock
            FROM registrations AS r
            JOIN pairing_sessions AS s
              ON s.pairing_id =
                 r.current_pairing_id
            """
        ).fetchall()
        if len(current) != 1:
            raise OnboardingError(
                "successor_recovery_current_registration_ambiguous"
            )
        row = current[0]
        if (
            not isinstance(
                row["hardware_id"],
                str,
            )
            or not isinstance(
                row["pairing_id"],
                str,
            )
            or row["node_id"]
            is not None
            or row[
                "logical_location_id"
            ]
            is not None
        ):
            raise OnboardingError(
                "successor_recovery_current_identity_invalid"
            )

        state = row["state"]
        if state == "pending":
            if int(
                row[
                    "expired_by_clock"
                ]
            ) != 1:
                raise OnboardingError(
                    "successor_recovery_current_not_expired"
                )
        elif (
            state != "expired"
            or row["reason"]
            != "expired"
        ):
            raise OnboardingError(
                "successor_recovery_current_state_invalid"
            )

        session = manager.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(
                    DISTINCT hardware_id
                ) AS hardware_count,
                SUM(
                    CASE
                        WHEN state = 'approved'
                        THEN 1
                        ELSE 0
                    END
                ) AS approved_count,
                SUM(
                    CASE
                        WHEN state = 'pending'
                        THEN 1
                        ELSE 0
                    END
                ) AS pending_count
            FROM pairing_sessions
            """
        ).fetchone()
        if (
            session is None
            or int(
                session["total"]
            )
            < 1
            or int(
                session[
                    "hardware_count"
                ]
            )
            != 1
            or int(
                session[
                    "approved_count"
                ]
                or 0
            )
            != 0
            or int(
                session[
                    "pending_count"
                ]
                or 0
            )
            != (
                1
                if state
                == "pending"
                else 0
            )
        ):
            raise OnboardingError(
                "successor_recovery_session_history_invalid"
            )

        same_hardware = manager.execute(
            """
            SELECT COUNT(*)
            FROM pairing_sessions
            WHERE hardware_id != ?
            """,
            (
                row[
                    "hardware_id"
                ],
            ),
        ).fetchone()[0]
        if int(same_hardware) != 0:
            raise OnboardingError(
                "successor_recovery_hardware_history_ambiguous"
            )

        assigned_events = manager.execute(
            """
            SELECT COUNT(*)
            FROM registration_events
            WHERE node_id IS NOT NULL
               OR logical_location_id
                  IS NOT NULL
            """
        ).fetchone()[0]
        node_history = manager.execute(
            """
            SELECT COUNT(*)
            FROM registration_node_history
            """
        ).fetchone()[0]
        retirement = manager.execute(
            """
            SELECT COUNT(*)
            FROM retirement_outbox
            """
        ).fetchone()[0]
        leases = manager.execute(
            """
            SELECT COUNT(*)
            FROM node_id_leases
            """
        ).fetchone()[0]
        if any(
            int(value) != 0
            for value
            in (
                assigned_events,
                node_history,
                retirement,
                leases,
            )
        ):
            raise OnboardingError(
                "successor_recovery_prior_identity_state_present"
            )
    finally:
        manager.close()

    return {
        "hardware_id_sha256": (
            _sha256_text(
                str(
                    row[
                        "hardware_id"
                    ]
                )
            )
        ),
        "pairing_id_sha256": (
            _sha256_text(
                str(
                    row[
                        "pairing_id"
                    ]
                )
            )
        ),
        "current_state": state,
        "current_expired_by_clock": True,
    }


def _require_successor_recovered_state(
    counts: dict[str, int],
    security_counts: dict[str, int],
    recovery: dict[str, Any],
) -> None:
    if (
        counts.get(
            "registrations"
        )
        != 0
        or counts.get(
            "node_id_leases"
        )
        != 0
        or int(
            counts.get(
                "pairing_sessions",
                0,
            )
        )
        < 1
        or int(
            counts.get(
                "registration_events",
                0,
            )
        )
        < 1
    ):
        raise OnboardingError(
            "successor_recovered_database_state_invalid"
        )
    if any(
        value != 0
        for value
        in security_counts.values()
    ):
        raise OnboardingError(
            "successor_recovered_security_state_invalid"
        )

    manager = _read_only_connection(
        MANAGER_DB
    )
    try:
        invalid_sessions = manager.execute(
            """
            SELECT COUNT(*)
            FROM pairing_sessions
            WHERE state NOT IN (
                'expired',
                'rejected'
            )
            """
        ).fetchone()[0]
        hardware_count = manager.execute(
            """
            SELECT COUNT(
                DISTINCT hardware_id
            )
            FROM pairing_sessions
            """
        ).fetchone()[0]
        assigned_events = manager.execute(
            """
            SELECT COUNT(*)
            FROM registration_events
            WHERE node_id IS NOT NULL
               OR logical_location_id
                  IS NOT NULL
            """
        ).fetchone()[0]
        if (
            int(
                invalid_sessions
            )
            != 0
            or int(
                hardware_count
            )
            != 1
            or int(
                assigned_events
            )
            != 0
        ):
            raise OnboardingError(
                "successor_recovered_tombstone_state_invalid"
            )

        matching_sessions = [
            row
            for row
            in manager.execute(
                """
                SELECT
                    hardware_id,
                    pairing_id,
                    state,
                    reason
                FROM pairing_sessions
                """
            ).fetchall()
            if (
                _sha256_text(
                    str(
                        row[
                            "hardware_id"
                        ]
                    )
                )
                == recovery[
                    "hardware_id_sha256"
                ]
                and _sha256_text(
                    str(
                        row[
                            "pairing_id"
                        ]
                    )
                )
                == recovery[
                    "pairing_id_sha256"
                ]
            )
        ]
        if (
            len(
                matching_sessions
            )
            != 1
            or matching_sessions[
                0
            ]["state"]
            != "expired"
            or matching_sessions[
                0
            ]["reason"]
            != "expired"
        ):
            raise OnboardingError(
                "successor_recovered_predecessor_tombstone_missing"
            )

        matching_events = [
            row
            for row
            in manager.execute(
                """
                SELECT
                    hardware_id,
                    pairing_id,
                    event,
                    reason
                FROM registration_events
                WHERE event =
                    'expired_first_registration_abandoned'
                """
            ).fetchall()
            if (
                _sha256_text(
                    str(
                        row[
                            "hardware_id"
                        ]
                    )
                )
                == recovery[
                    "hardware_id_sha256"
                ]
                and _sha256_text(
                    str(
                        row[
                            "pairing_id"
                        ]
                    )
                )
                == recovery[
                    "pairing_id_sha256"
                ]
            )
        ]
        if (
            len(
                matching_events
            )
            != 1
            or matching_events[
                0
            ]["reason"]
            != (
                "expired_first_pairing_recovery"
            )
        ):
            raise OnboardingError(
                "successor_recovered_audit_event_missing"
            )
    finally:
        manager.close()


def _require_first_pair_admission(
    counts: dict[str, int],
    security_counts: dict[str, int],
    factory: dict[str, Any],
) -> None:
    recovery_present = (
        SUCCESSOR_RECOVERY_PATH.exists()
        or SUCCESSOR_RECOVERY_PATH.is_symlink()
    )
    if not recovery_present:
        _require_clean_first_pair_state(
            counts,
            security_counts,
        )
        return

    recovery = _successor_recovery_record()
    if (
        recovery.get("status")
        != "CLOSED_PASS"
        or recovery[
            "recovery_release_id"
        ]
        != factory[
            "release_id"
        ]
        or recovery[
            "host_instance_id"
        ]
        != factory[
            "host_instance_id"
        ]
        or recovery[
            "system_id"
        ]
        != factory[
            "system_id"
        ]
    ):
        raise OnboardingError(
            "successor_recovery_not_admissible"
        )
    _require_successor_recovered_state(
        counts,
        security_counts,
        recovery,
    )


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
        "peer_trust_records": 1,
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
    _require_file(SERVER_CERT)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(CA_CERT))
    try:
        with socket.create_connection(
            (host, BROKER_TLS_PORT),
            timeout=5,
        ) as raw, context.wrap_socket(
            raw,
            server_hostname=BROKER_TLS_SERVER_NAME,
        ) as wrapped:
            peer = wrapped.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as error:
        raise OnboardingError("external_broker_tls_probe_failed") from error

    if not peer:
        raise OnboardingError("external_broker_tls_peer_missing")

    try:
        local_der = ssl.PEM_cert_to_DER_cert(
            SERVER_CERT.read_text(encoding="ascii")
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise OnboardingError("external_broker_server_certificate_invalid") from error

    if hashlib.sha256(peer).hexdigest() != hashlib.sha256(local_der).hexdigest():
        raise OnboardingError("external_broker_tls_certificate_mismatch")


def _probe_manager_broker_tls(manager_id: str) -> None:
    script = (
        "import socket,ssl;"
        "ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);"
        "ctx.check_hostname=True;"
        "ctx.verify_mode=ssl.CERT_REQUIRED;"
        "ctx.load_verify_locations(cafile='/run/n3w/tls/ca.pem');"
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


def _watchdog_unit_name(
    authorization_id: str,
) -> str:
    return (
        WATCHDOG_UNIT_PREFIX
        + _sha256_text(
            authorization_id
        )[:16]
    )


def _systemctl_is_active(
    unit: str,
) -> bool:
    output = _run(
        (
            "systemctl",
            "is-active",
            unit,
        ),
        timeout=20,
        allowed=frozenset(
            {
                0,
                3,
                4,
            }
        ),
    )
    return (
        output.strip()
        == "active"
    )


def _watchdog_is_active(
    transaction: dict[str, Any],
) -> bool:
    unit = transaction.get(
        "watchdog_unit"
    )
    if (
        not isinstance(unit, str)
        or not unit.startswith(
            WATCHDOG_UNIT_PREFIX
        )
    ):
        return False
    return _systemctl_is_active(
        f"{unit}.timer"
    )


def _arm_watchdog(
    transaction: dict[str, Any],
) -> dict[str, Any]:
    authorization_id = (
        transaction.get(
            "authorization_id"
        )
    )
    expires_at = transaction.get(
        "expires_at_unix"
    )
    if (
        not isinstance(
            authorization_id,
            str,
        )
        or not isinstance(
            expires_at,
            int,
        )
        or isinstance(
            expires_at,
            bool,
        )
        or transaction.get(
            "status"
        )
        != "OPEN"
    ):
        raise OnboardingError(
            "watchdog_transaction_binding_invalid"
        )

    authorization_sha = (
        _sha256_text(
            authorization_id
        )
    )
    unit = _watchdog_unit_name(
        authorization_id
    )
    remaining = (
        expires_at
        - int(time.time())
    )
    if remaining < 1:
        raise OnboardingError(
            "watchdog_deadline_elapsed"
        )

    _prepare_runtime_root(
        transaction
    )

    command_error_type = ""
    try:
        _run(
            (
                "systemd-run",
                "--quiet",
                "--collect",
                f"--unit={unit}",
                (
                    "--on-active="
                    f"{remaining + WATCHDOG_GRACE_SECONDS}s"
                ),
                "--timer-property=AccuracySec=1s",
                "--property=Type=exec",
                PYTHON_EXECUTABLE,
                str(
                    WATCHDOG_TOOL_PATH
                ),
                "expire",
                "--authorization-sha256",
                authorization_sha,
            ),
            timeout=20,
        )
    except OPERATION_ERRORS as error:
        command_error_type = (
            type(error).__name__
        )

    if not _systemctl_is_active(
        f"{unit}.timer"
    ):
        raise OnboardingError(
            "watchdog_not_active:"
            f"{command_error_type or 'no_command_error'}"
        )

    return _advance_transaction(
        watchdog_unit=unit,
        watchdog_armed=True,
        watchdog_authorization_sha256=(
            authorization_sha
        ),
        watchdog_tool_sha256=(
            _sha256_file(
                WATCHDOG_TOOL_PATH
            )
        ),
        watchdog_command_error_type=(
            command_error_type
        ),
        watchdog_armed_at_unix=(
            int(time.time())
        ),
        watchdog_grace_seconds=(
            WATCHDOG_GRACE_SECONDS
        ),
    )


def _cancel_watchdog(
    transaction: dict[str, Any],
) -> str:
    unit = transaction.get(
        "watchdog_unit"
    )
    if (
        not isinstance(unit, str)
        or not unit.startswith(
            WATCHDOG_UNIT_PREFIX
        )
    ):
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
            allowed=frozenset(
                {
                    0,
                    5,
                }
            ),
        )
    except OPERATION_ERRORS as error:
        command_error_type = (
            type(error).__name__
        )

    if _systemctl_is_active(
        f"{unit}.timer"
    ):
        raise OnboardingError(
            "watchdog_timer_still_active"
        )
    if _systemctl_is_active(
        f"{unit}.service"
    ):
        raise OnboardingError(
            "watchdog_service_still_active"
        )
    return command_error_type


def _watchdog_terminal_status(
    status: object,
) -> bool:
    return status in {
        "STOPPED_WATCHDOG_ARM_FAILED",
        "STOPPED_OPEN_FAILED",
        "CLOSED_PASS",
        "CLOSED_ABORTED",
        "CLOSED_FAIL_WINDOW_EXPIRED",
        "CLOSED_TIMEOUT",
        "CLOSED_TIMEOUT_CONTROL_UNAVAILABLE",
    }


def _window_control(
    manager_id: str,
    command: str,
    *,
    peer_ip: str | None = None,
    window_seconds: int | None = None,
) -> dict[str, Any]:
    if command not in {
        "open",
        "status",
        "close",
    }:
        raise OnboardingError(
            "pairing_control_command_invalid"
        )
    argv = [
        "docker",
        "exec",
        manager_id,
        "greenhouse-manager-pairing",
        f"window-{command}",
    ]
    if command == "open":
        if (
            not isinstance(
                peer_ip,
                str,
            )
            or not isinstance(
                window_seconds,
                int,
            )
            or isinstance(
                window_seconds,
                bool,
            )
        ):
            raise OnboardingError(
                "pairing_control_open_arguments_invalid"
            )
        argv.extend(
            (
                "--peer-ip",
                peer_ip,
                "--window-seconds",
                str(window_seconds),
            )
        )
    raw = _run(
        tuple(argv),
        timeout=20,
        allowed=frozenset(
            {
                0,
                2,
            }
        ),
    )
    try:
        document = json.loads(
            raw
        )
    except json.JSONDecodeError as error:
        raise OnboardingError(
            "pairing_control_response_invalid"
        ) from error
    if (
        not isinstance(document, dict)
        or not isinstance(
            document.get("accepted"),
            bool,
        )
        or not isinstance(
            document.get("code"),
            str,
        )
        or document.get(
            "pairing_window_state"
        )
        not in {
            "CLOSED",
            "OPENING",
            "OPEN",
            "CLOSING",
        }
        or document.get(
            "raw_locator_in_output"
        )
        is not False
    ):
        raise OnboardingError(
            "pairing_control_response_invalid"
        )
    return document


def _require_successor_recovery_capability(
    manager_id: str,
) -> None:
    output = _run(
        (
            "docker",
            "exec",
            manager_id,
            "greenhouse-manager-pairing",
            "recover-expired-first",
            "--help",
        ),
        timeout=20,
    )
    if (
        "recover-expired-first"
        not in output
        or "--hardware-id-sha256"
        not in output
        or "--pairing-id-sha256"
        not in output
    ):
        raise OnboardingError(
            "successor_recovery_capability_unproven"
        )


def _recover_expired_first_control(
    manager_id: str,
    *,
    hardware_id_sha256: str,
    pairing_id_sha256: str,
) -> dict[str, Any]:
    for value in (
        hardware_id_sha256,
        pairing_id_sha256,
    ):
        if (
            re.fullmatch(
                r"[0-9a-f]{64}",
                value,
            )
            is None
        ):
            raise OnboardingError(
                "successor_recovery_control_hash_invalid"
            )

    raw = _run(
        (
            "docker",
            "exec",
            manager_id,
            "greenhouse-manager-pairing",
            "recover-expired-first",
            "--hardware-id-sha256",
            hardware_id_sha256,
            "--pairing-id-sha256",
            pairing_id_sha256,
        ),
        timeout=20,
        allowed=frozenset(
            {
                0,
                2,
            }
        ),
    )
    try:
        document = json.loads(
            raw
        )
    except json.JSONDecodeError as error:
        raise OnboardingError(
            "successor_recovery_control_response_invalid"
        ) from error

    if (
        not isinstance(
            document,
            dict,
        )
        or not isinstance(
            document.get(
                "accepted"
            ),
            bool,
        )
        or not isinstance(
            document.get(
                "code"
            ),
            str,
        )
        or document.get(
            "pairing_window_state"
        )
        != "CLOSED"
        or document.get(
            "raw_locator_in_output"
        )
        is not False
    ):
        raise OnboardingError(
            "successor_recovery_control_response_invalid"
        )

    if document.get(
        "accepted"
    ) is True:
        if (
            document.get(
                "code"
            )
            != (
                "expired_first_recovery_complete"
            )
            or document.get(
                "hardware_id_sha256"
            )
            != hardware_id_sha256
            or document.get(
                "pairing_id_sha256"
            )
            != pairing_id_sha256
            or document.get(
                "current_registration_released"
            )
            is not True
            or document.get(
                "replay_tombstone_preserved"
            )
            is not True
            or document.get(
                "credential_history_absent"
            )
            is not True
            or document.get(
                "manager_recreated"
            )
            is not False
            or document.get(
                "raw_identity_in_output"
            )
            is not False
        ):
            raise OnboardingError(
                "successor_recovery_control_binding_invalid"
            )
    return document


def _require_control_accepted(
    result: dict[str, Any],
) -> None:
    if result.get(
        "accepted"
    ) is not True:
        code = str(
            result.get(
                "code",
                "rejected",
            )
        )
        if (
            len(code) > 120
            or re.fullmatch(
                r"[A-Za-z0-9_.:-]+",
                code,
            )
            is None
        ):
            code = "rejected"
        raise OnboardingError(
            f"pairing_control_rejected:{code}"
        )


def _pairing_socket_absent(
    manager_id: str,
) -> None:
    script = (
        "import pathlib,sys;"
        "p=pathlib.Path("
        "'/run/greenhouse-manager/pairing.sock');"
        "sys.exit(1 if p.exists() else 0)"
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


def _wait_dynamic_open(
    manager_id: str,
    expected_broker_hash: str,
    *,
    timeout_s: float = 15.0,
) -> dict[str, Any]:
    deadline = (
        time.monotonic()
        + timeout_s
    )
    last_error = "unknown"
    while (
        time.monotonic()
        < deadline
    ):
        try:
            status = _window_control(
                manager_id,
                "status",
            )
            _require_control_accepted(
                status
            )
            if (
                status.get(
                    "pairing_window_state"
                )
                != "OPEN"
            ):
                raise OnboardingError(
                    "pairing_control_not_open"
                )
            if (
                status.get(
                    "broker_host_sha256"
                )
                != expected_broker_hash
            ):
                raise OnboardingError(
                    "pairing_control_broker_hash_mismatch"
                )
            if (
                _listener_count(
                    "udp",
                    PAIRING_UDP_PORT,
                )
                != 1
            ):
                raise OnboardingError(
                    "pairing_udp_listener_count_invalid"
                )
            if (
                _listener_count(
                    "tcp",
                    PAIRING_HTTP_PORT,
                )
                != 1
            ):
                raise OnboardingError(
                    "pairing_tcp_listener_count_invalid"
                )
            _pairing_health()
            _pairing_socket_ready(
                manager_id
            )
            _probe_manager_broker_tls(
                manager_id
            )
            return status
        except OnboardingError as error:
            last_error = str(error)
            time.sleep(0.25)
    raise OnboardingError(
        "dynamic_pairing_open_timeout:"
        f"{last_error}"
    )


def _wait_dynamic_closed(
    manager_id: str,
    *,
    timeout_s: float = 15.0,
) -> dict[str, Any]:
    deadline = (
        time.monotonic()
        + timeout_s
    )
    last_error = "unknown"
    while (
        time.monotonic()
        < deadline
    ):
        try:
            status = _window_control(
                manager_id,
                "status",
            )
            _require_control_accepted(
                status
            )
            if (
                status.get(
                    "pairing_window_state"
                )
                != "CLOSED"
            ):
                raise OnboardingError(
                    "pairing_control_not_closed"
                )
            if (
                _listener_count(
                    "udp",
                    PAIRING_UDP_PORT,
                )
                != 0
            ):
                raise OnboardingError(
                    "pairing_udp_listener_still_open"
                )
            if (
                _listener_count(
                    "tcp",
                    PAIRING_HTTP_PORT,
                )
                != 0
            ):
                raise OnboardingError(
                    "pairing_tcp_listener_still_open"
                )
            _pairing_socket_absent(
                manager_id
            )
            return status
        except OnboardingError as error:
            last_error = str(error)
            time.sleep(0.25)
    raise OnboardingError(
        "dynamic_pairing_close_timeout:"
        f"{last_error}"
    )


def _validate_runtime_continuity(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> None:
    for service in (
        "broker",
        "manager",
        "homeassistant",
    ):
        if (
            before[service]["id"]
            != after[service]["id"]
        ):
            raise OnboardingError(
                f"{service}_container_identity_changed"
            )
        if (
            after[service][
                "restart_count"
            ]
            != before[service][
                "restart_count"
            ]
        ):
            raise OnboardingError(
                f"{service}_restart_count_changed"
            )


def _authorization_id(
    value: str,
) -> str:
    if (
        not value.startswith(
            "N3W_T1_FIRST_PAIRING_"
        )
        or len(value) > 200
        or not (
            value
            .replace("_", "")
            .replace("-", "")
            .isalnum()
        )
    ):
        raise OnboardingError(
            "authorization_id_invalid"
        )
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
    if (
        TRANSACTION_PATH.exists()
        or TRANSACTION_PATH.is_symlink()
    ):
        raise OnboardingError(
            "onboarding_transaction_already_exists"
        )
    now = int(
        time.time()
    )
    document = {
        "schema": TRANSACTION_SCHEMA,
        "status": "CLAIMED",
        "authorization_id": (
            authorization_id
        ),
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "release_id": factory[
            "release_id"
        ],
        "host_instance_id": factory[
            "host_instance_id"
        ],
        "system_id": factory[
            "system_id"
        ],
        "peer_ip_sha256": (
            _sha256_text(
                peer_ip
            )
        ),
        "broker_host_sha256": (
            _sha256_text(
                broker_host
            )
        ),
        "window_seconds": (
            window_seconds
        ),
        "claimed_at_unix": now,
        "expires_at_unix": (
            now
            + window_seconds
        ),
        "baseline_container_ids": {
            service: baseline[
                service
            ]["id"]
            for service
            in sorted(
                EXPECTED_SERVICES
            )
        },
        "baseline_restart_counts": {
            service: baseline[
                service
            ][
                "restart_count"
            ]
            for service
            in sorted(
                EXPECTED_SERVICES
            )
        },
        "tool_sha256": (
            _sha256_file(
                Path(__file__)
                .resolve()
            )
        ),
    }
    _write_private_json(
        TRANSACTION_PATH,
        document,
    )
    return document


def _advance_transaction(
    **fields: Any,
) -> dict[str, Any]:
    document = _read_private_json(
        TRANSACTION_PATH
    )
    document.update(
        fields
    )
    document[
        "authorization_claimed"
    ] = True
    document[
        "authorization_consumed"
    ] = True
    document[
        "replay_allowed"
    ] = False
    _write_private_json(
        TRANSACTION_PATH,
        document,
    )
    return document


def _validate_legacy_transaction(
    document: dict[str, Any],
) -> dict[str, Any]:
    if (
        document.get("schema")
        != LEGACY_TRANSACTION_SCHEMA
        or document.get(
            "authorization_claimed"
        )
        is not True
        or document.get(
            "authorization_consumed"
        )
        is not True
        or document.get(
            "replay_allowed"
        )
        is not False
    ):
        raise OnboardingError(
            "legacy_onboarding_transaction_invalid"
        )
    authorization_id = (
        document.get(
            "authorization_id"
        )
    )
    if not isinstance(
        authorization_id,
        str,
    ):
        raise OnboardingError(
            "legacy_onboarding_transaction_invalid"
        )
    _authorization_id(
        authorization_id
    )
    status = document.get(
        "status"
    )
    if (
        not isinstance(status, str)
        or not status
    ):
        raise OnboardingError(
            "legacy_onboarding_transaction_invalid"
        )
    return document


def _transaction() -> dict[str, Any]:
    document = _read_private_json(
        TRANSACTION_PATH
    )
    if (
        document.get("schema")
        == LEGACY_TRANSACTION_SCHEMA
    ):
        return (
            _validate_legacy_transaction(
                document
            )
        )
    if (
        document.get("schema")
        != TRANSACTION_SCHEMA
        or document.get(
            "authorization_claimed"
        )
        is not True
        or document.get(
            "authorization_consumed"
        )
        is not True
        or document.get(
            "replay_allowed"
        )
        is not False
    ):
        raise OnboardingError(
            "onboarding_transaction_invalid"
        )

    if (
        "peer_ip" in document
        or "broker_host" in document
    ):
        raise OnboardingError(
            "onboarding_transaction_raw_locator_forbidden"
        )

    authorization_id = (
        document.get(
            "authorization_id"
        )
    )
    if not isinstance(
        authorization_id,
        str,
    ):
        raise OnboardingError(
            "onboarding_transaction_authorization_invalid"
        )
    _authorization_id(
        authorization_id
    )

    allowed_statuses = {
        "CLAIMED",
        "OPEN",
        "STOPPED_WATCHDOG_ARM_FAILED",
        "STOPPED_OPEN_FAILED",
        "OPEN_CLOSE_UNPROVEN",
        "CLOSED_PASS",
        "CLOSED_ABORTED",
        "CLOSED_FAIL_WINDOW_EXPIRED",
        "CLOSED_TIMEOUT",
        "CLOSED_TIMEOUT_CONTROL_UNAVAILABLE",
        "TIMEOUT_CLOSE_UNPROVEN",
    }
    status = document.get(
        "status"
    )
    if status not in allowed_statuses:
        raise OnboardingError(
            "onboarding_transaction_status_invalid"
        )

    for key in (
        "release_id",
        "host_instance_id",
        "system_id",
    ):
        if (
            not isinstance(
                document.get(key),
                str,
            )
            or not document[key]
        ):
            raise OnboardingError(
                "onboarding_transaction_binding_invalid:"
                f"{key}"
            )

    for key in (
        "peer_ip_sha256",
        "broker_host_sha256",
    ):
        value = document.get(
            key
        )
        if (
            not isinstance(
                value,
                str,
            )
            or re.fullmatch(
                r"[0-9a-f]{64}",
                value,
            )
            is None
        ):
            raise OnboardingError(
                "onboarding_transaction_locator_hash_invalid"
            )

    window_seconds = document.get(
        "window_seconds"
    )
    claimed_at = document.get(
        "claimed_at_unix"
    )
    opened_at = document.get(
        "opened_at_unix"
    )
    expires_at = document.get(
        "expires_at_unix"
    )
    if (
        not isinstance(
            window_seconds,
            int,
        )
        or isinstance(
            window_seconds,
            bool,
        )
        or not 180
        <= window_seconds
        <= 600
        or not isinstance(
            claimed_at,
            int,
        )
        or isinstance(
            claimed_at,
            bool,
        )
        or not isinstance(
            expires_at,
            int,
        )
        or isinstance(
            expires_at,
            bool,
        )
    ):
        raise OnboardingError(
            "onboarding_transaction_deadline_invalid"
        )
    deadline_base = claimed_at
    if opened_at is not None:
        if (
            not isinstance(
                opened_at,
                int,
            )
            or isinstance(
                opened_at,
                bool,
            )
            or opened_at
            < claimed_at
        ):
            raise OnboardingError(
                "onboarding_transaction_deadline_invalid"
            )
        deadline_base = opened_at
    if (
        expires_at
        != deadline_base
        + window_seconds
    ):
        raise OnboardingError(
            "onboarding_transaction_deadline_invalid"
        )

    baseline = document.get(
        "baseline_container_ids"
    )
    restarts = document.get(
        "baseline_restart_counts"
    )
    if (
        not isinstance(
            baseline,
            dict,
        )
        or set(baseline)
        != EXPECTED_SERVICES
        or any(
            not _is_container_id(
                value
            )
            for value
            in baseline.values()
        )
        or not isinstance(
            restarts,
            dict,
        )
        or set(restarts)
        != EXPECTED_SERVICES
        or any(
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
            or value < 0
            for value
            in restarts.values()
        )
    ):
        raise OnboardingError(
            "onboarding_transaction_container_binding_invalid"
        )

    tool_sha = document.get(
        "tool_sha256"
    )
    if (
        not isinstance(
            tool_sha,
            str,
        )
        or re.fullmatch(
            r"[0-9a-f]{64}",
            tool_sha,
        )
        is None
        or _sha256_file(
            Path(__file__).resolve()
        )
        != tool_sha
    ):
        raise OnboardingError(
            "onboarding_transaction_tool_binding_invalid"
        )

    if document.get(
        "watchdog_armed"
    ) is True:
        unit = document.get(
            "watchdog_unit"
        )
        auth_sha = document.get(
            "watchdog_authorization_sha256"
        )
        watchdog_tool_sha = (
            document.get(
                "watchdog_tool_sha256"
            )
        )
        if (
            not isinstance(
                unit,
                str,
            )
            or re.fullmatch(
                (
                    re.escape(
                        WATCHDOG_UNIT_PREFIX
                    )
                    + r"[0-9a-f]{16}"
                ),
                unit,
            )
            is None
            or unit
            != _watchdog_unit_name(
                authorization_id
            )
            or auth_sha
            != _sha256_text(
                authorization_id
            )
            or watchdog_tool_sha
            != tool_sha
        ):
            raise OnboardingError(
                "onboarding_transaction_watchdog_binding_invalid"
            )

    return document


def _predecessor_transaction() -> tuple[
    dict[str, Any],
    str,
]:
    payload = _read_private_bytes(
        TRANSACTION_PATH
    )
    predecessor_sha256 = hashlib.sha256(
        payload
    ).hexdigest()
    document = _read_private_json(
        TRANSACTION_PATH
    )

    if (
        document.get("schema")
        != TRANSACTION_SCHEMA
        or document.get(
            "authorization_claimed"
        )
        is not True
        or document.get(
            "authorization_consumed"
        )
        is not True
        or document.get(
            "replay_allowed"
        )
        is not False
        or document.get("status")
        != "OPEN"
    ):
        raise OnboardingError(
            "successor_predecessor_transaction_invalid"
        )

    if (
        "peer_ip" in document
        or "broker_host" in document
    ):
        raise OnboardingError(
            "successor_predecessor_raw_locator_forbidden"
        )

    authorization_id = document.get(
        "authorization_id"
    )
    if not isinstance(
        authorization_id,
        str,
    ):
        raise OnboardingError(
            "successor_predecessor_authorization_invalid"
        )
    _authorization_id(
        authorization_id
    )

    for key in (
        "release_id",
        "host_instance_id",
        "system_id",
    ):
        if (
            not isinstance(
                document.get(key),
                str,
            )
            or not document[key]
        ):
            raise OnboardingError(
                "successor_predecessor_binding_invalid"
            )

    for key in (
        "peer_ip_sha256",
        "broker_host_sha256",
        "tool_sha256",
    ):
        value = document.get(key)
        if (
            not isinstance(value, str)
            or re.fullmatch(
                r"[0-9a-f]{64}",
                value,
            )
            is None
        ):
            raise OnboardingError(
                "successor_predecessor_hash_invalid"
            )

    window_seconds = document.get(
        "window_seconds"
    )
    claimed_at = document.get(
        "claimed_at_unix"
    )
    opened_at = document.get(
        "opened_at_unix"
    )
    expires_at = document.get(
        "expires_at_unix"
    )
    if (
        not isinstance(
            window_seconds,
            int,
        )
        or isinstance(
            window_seconds,
            bool,
        )
        or not 180
        <= window_seconds
        <= 600
        or not isinstance(
            claimed_at,
            int,
        )
        or isinstance(
            claimed_at,
            bool,
        )
        or not isinstance(
            opened_at,
            int,
        )
        or isinstance(
            opened_at,
            bool,
        )
        or opened_at < claimed_at
        or not isinstance(
            expires_at,
            int,
        )
        or isinstance(
            expires_at,
            bool,
        )
        or expires_at
        != opened_at
        + window_seconds
        or int(time.time())
        <= expires_at
    ):
        raise OnboardingError(
            "successor_predecessor_deadline_invalid"
        )

    baseline = document.get(
        "baseline_container_ids"
    )
    restarts = document.get(
        "baseline_restart_counts"
    )
    if (
        not isinstance(
            baseline,
            dict,
        )
        or set(baseline)
        != EXPECTED_SERVICES
        or any(
            not _is_container_id(
                value
            )
            for value
            in baseline.values()
        )
        or not isinstance(
            restarts,
            dict,
        )
        or set(restarts)
        != EXPECTED_SERVICES
        or any(
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
            or value < 0
            for value
            in restarts.values()
        )
    ):
        raise OnboardingError(
            "successor_predecessor_container_binding_invalid"
        )

    if document.get(
        "watchdog_armed"
    ) is True:
        unit = document.get(
            "watchdog_unit"
        )
        auth_sha = document.get(
            "watchdog_authorization_sha256"
        )
        watchdog_tool_sha = document.get(
            "watchdog_tool_sha256"
        )
        if (
            not isinstance(
                unit,
                str,
            )
            or unit
            != _watchdog_unit_name(
                authorization_id
            )
            or auth_sha
            != _sha256_text(
                authorization_id
            )
            or watchdog_tool_sha
            != document[
                "tool_sha256"
            ]
        ):
            raise OnboardingError(
                "successor_predecessor_watchdog_binding_invalid"
            )

    return (
        document,
        predecessor_sha256,
    )


def _claim_successor_recovery(
    *,
    authorization_id: str,
    predecessor: dict[str, Any],
    predecessor_sha256: str,
    factory: dict[str, Any],
    baseline: dict[str, dict[str, Any]],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if (
        SUCCESSOR_RECOVERY_PATH.exists()
        or SUCCESSOR_RECOVERY_PATH.is_symlink()
    ):
        raise OnboardingError(
            "successor_recovery_record_already_exists"
        )
    document = {
        "schema": SUCCESSOR_RECOVERY_SCHEMA,
        "status": "CLAIMED",
        "authorization_id": (
            authorization_id
        ),
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "predecessor_release_id": (
            predecessor[
                "release_id"
            ]
        ),
        "recovery_release_id": (
            factory[
                "release_id"
            ]
        ),
        "host_instance_id": factory[
            "host_instance_id"
        ],
        "system_id": factory[
            "system_id"
        ],
        "predecessor_transaction_sha256": (
            predecessor_sha256
        ),
        "predecessor_authorization_sha256": (
            _sha256_text(
                str(
                    predecessor[
                        "authorization_id"
                    ]
                )
            )
        ),
        "predecessor_tool_sha256": (
            predecessor[
                "tool_sha256"
            ]
        ),
        "hardware_id_sha256": (
            candidate[
                "hardware_id_sha256"
            ]
        ),
        "pairing_id_sha256": (
            candidate[
                "pairing_id_sha256"
            ]
        ),
        "predecessor_baseline_container_ids": dict(
            predecessor[
                "baseline_container_ids"
            ]
        ),
        "predecessor_baseline_restart_counts": dict(
            predecessor[
                "baseline_restart_counts"
            ]
        ),
        "baseline_container_ids": {
            service: baseline[
                service
            ]["id"]
            for service
            in sorted(
                EXPECTED_SERVICES
            )
        },
        "baseline_restart_counts": {
            service: baseline[
                service
            ][
                "restart_count"
            ]
            for service
            in sorted(
                EXPECTED_SERVICES
            )
        },
        "claimed_at_unix": int(
            time.time()
        ),
        "tool_sha256": _sha256_file(
            Path(__file__).resolve()
        ),
    }
    _write_private_json(
        SUCCESSOR_RECOVERY_PATH,
        document,
    )
    return document


def _advance_successor_recovery(
    **fields: Any,
) -> dict[str, Any]:
    document = _read_private_json(
        SUCCESSOR_RECOVERY_PATH
    )
    document.update(fields)
    document[
        "authorization_claimed"
    ] = True
    document[
        "authorization_consumed"
    ] = True
    document[
        "replay_allowed"
    ] = False
    _write_private_json(
        SUCCESSOR_RECOVERY_PATH,
        document,
    )
    return document


def _successor_recovery_record() -> dict[str, Any]:
    document = _read_private_json(
        SUCCESSOR_RECOVERY_PATH
    )
    if (
        document.get("schema")
        != SUCCESSOR_RECOVERY_SCHEMA
        or document.get(
            "authorization_claimed"
        )
        is not True
        or document.get(
            "authorization_consumed"
        )
        is not True
        or document.get(
            "replay_allowed"
        )
        is not False
        or document.get(
            "status"
        )
        not in {
            "CLAIMED",
            "STOPPED_RECOVERY_UNPROVEN",
            "STOPPED_POSTCHECK_FAILED",
            "STOPPED_ARCHIVE_FAILED",
            "CLOSED_PASS",
        }
    ):
        raise OnboardingError(
            "successor_recovery_record_invalid"
        )

    authorization_id = document.get(
        "authorization_id"
    )
    if not isinstance(
        authorization_id,
        str,
    ):
        raise OnboardingError(
            "successor_recovery_authorization_invalid"
        )
    _authorization_id(
        authorization_id
    )

    for key in (
        "predecessor_release_id",
        "recovery_release_id",
        "host_instance_id",
        "system_id",
    ):
        if (
            not isinstance(
                document.get(key),
                str,
            )
            or not document[key]
        ):
            raise OnboardingError(
                "successor_recovery_binding_invalid"
            )

    for key in (
        "predecessor_transaction_sha256",
        "predecessor_authorization_sha256",
        "predecessor_tool_sha256",
        "hardware_id_sha256",
        "pairing_id_sha256",
        "tool_sha256",
    ):
        value = document.get(key)
        if (
            not isinstance(value, str)
            or re.fullmatch(
                r"[0-9a-f]{64}",
                value,
            )
            is None
        ):
            raise OnboardingError(
                "successor_recovery_hash_invalid"
            )

    if document[
        "tool_sha256"
    ] != _sha256_file(
        Path(__file__).resolve()
    ):
        raise OnboardingError(
            "successor_recovery_tool_binding_invalid"
        )

    ids = document.get(
        "baseline_container_ids"
    )
    restarts = document.get(
        "baseline_restart_counts"
    )
    if (
        not isinstance(ids, dict)
        or set(ids)
        != EXPECTED_SERVICES
        or any(
            not _is_container_id(
                value
            )
            for value
            in ids.values()
        )
        or not isinstance(
            restarts,
            dict,
        )
        or set(restarts)
        != EXPECTED_SERVICES
        or any(
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
            or value < 0
            for value
            in restarts.values()
        )
    ):
        raise OnboardingError(
            "successor_recovery_container_binding_invalid"
        )

    predecessor_ids = document.get(
        "predecessor_baseline_container_ids"
    )
    predecessor_restarts = document.get(
        "predecessor_baseline_restart_counts"
    )
    if (
        not isinstance(
            predecessor_ids,
            dict,
        )
        or set(
            predecessor_ids
        )
        != EXPECTED_SERVICES
        or any(
            not _is_container_id(
                value
            )
            for value
            in predecessor_ids.values()
        )
        or not isinstance(
            predecessor_restarts,
            dict,
        )
        or set(
            predecessor_restarts
        )
        != EXPECTED_SERVICES
        or any(
            not isinstance(
                value,
                int,
            )
            or isinstance(
                value,
                bool,
            )
            or value < 0
            for value
            in predecessor_restarts.values()
        )
    ):
        raise OnboardingError(
            "successor_recovery_predecessor_container_binding_invalid"
        )

    if (
        document.get("status")
        == "CLOSED_PASS"
    ):
        if (
            document.get(
                "manager_recovery_accepted"
            )
            is not True
            or document.get(
                "postcheck_passed"
            )
            is not True
            or document.get(
                "predecessor_archived"
            )
            is not True
            or document.get(
                "predecessor_archive_sha256"
            )
            != document[
                "predecessor_transaction_sha256"
            ]
            or document.get(
                "pairing_exposure_closed"
            )
            is not True
            or document.get(
                "manager_container_unchanged"
            )
            is not True
            or document.get(
                "broker_continuity"
            )
            is not True
            or document.get(
                "homeassistant_continuity"
            )
            is not True
        ):
            raise OnboardingError(
                "successor_recovery_closure_invalid"
            )
        archive_path = (
            TRANSACTION_ARCHIVE_ROOT
            / (
                "FIRST_PAIRING_ONBOARDING."
                + document[
                    "predecessor_transaction_sha256"
                ]
                + ".json"
            )
        )
        if (
            hashlib.sha256(
                _read_private_bytes(
                    archive_path
                )
            ).hexdigest()
            != document[
                "predecessor_transaction_sha256"
            ]
        ):
            raise OnboardingError(
                "successor_recovery_archive_invalid"
            )
        if (
            TRANSACTION_PATH.exists()
            or TRANSACTION_PATH.is_symlink()
        ):
            raise OnboardingError(
                "successor_recovery_predecessor_not_archived"
            )

    return document


def _baseline_from_transaction(
    transaction: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    ids = transaction.get(
        "baseline_container_ids"
    )
    restarts = transaction.get(
        "baseline_restart_counts"
    )
    if (
        not isinstance(ids, dict)
        or not isinstance(
            restarts,
            dict,
        )
    ):
        raise OnboardingError(
            "baseline_container_binding_missing"
        )
    return {
        service: {
            "id": ids[service],
            "restart_count": (
                restarts[service]
            ),
        }
        for service
        in EXPECTED_SERVICES
    }


def _public_runtime(
    snapshot: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "manager_running": True,
        "manager_restart_count": (
            snapshot["manager"][
                "restart_count"
            ]
        ),
        "manager_network_mode": (
            snapshot["manager"][
                "network_mode"
            ]
        ),
        "broker_running": True,
        "broker_restart_count": (
            snapshot["broker"][
                "restart_count"
            ]
        ),
        "homeassistant_running": True,
        "homeassistant_restart_count": (
            snapshot[
                "homeassistant"
            ][
                "restart_count"
            ]
        ),
    }


def inspect() -> dict[str, Any]:
    _require_root()
    _require_file(
        COMPOSE_TARGET
    )
    _require_file(
        COMPOSE_ENV
    )
    _validate_factory_compose()
    factory = (
        _validate_factory_marker()
    )
    runtime = _runtime_snapshot()
    _validate_factory_runtime_configuration(
        runtime
    )
    manager_id = runtime[
        "manager"
    ]["id"]
    control = _window_control(
        manager_id,
        "status",
    )
    _require_control_accepted(
        control
    )
    udp_count = _listener_count(
        "udp",
        PAIRING_UDP_PORT,
    )
    tcp_count = _listener_count(
        "tcp",
        PAIRING_HTTP_PORT,
    )
    if (
        control.get(
            "pairing_window_state"
        )
        == "CLOSED"
        and (
            udp_count != 0
            or tcp_count != 0
        )
    ):
        raise OnboardingError(
            "pairing_control_listener_state_mismatch"
        )
    if (
        control.get(
            "pairing_window_state"
        )
        == "OPEN"
        and (
            udp_count != 1
            or tcp_count != 1
        )
    ):
        raise OnboardingError(
            "pairing_control_listener_state_mismatch"
        )

    counts = _db_counts()
    transaction: (
        dict[str, Any]
        | None
    ) = None
    if TRANSACTION_PATH.is_symlink():
        raise OnboardingError(
            "onboarding_transaction_symlink_forbidden"
        )
    if TRANSACTION_PATH.exists():
        transaction = _transaction()

    successor_recovery: (
        dict[str, Any]
        | None
    ) = None
    if SUCCESSOR_RECOVERY_PATH.is_symlink():
        raise OnboardingError(
            "successor_recovery_symlink_forbidden"
        )
    if SUCCESSOR_RECOVERY_PATH.exists():
        successor_recovery = (
            _successor_recovery_record()
        )

    if transaction is None:
        if (
            control.get(
                "pairing_window_state"
            )
            != "CLOSED"
        ):
            raise OnboardingError(
                "unowned_pairing_window_present"
            )
    elif (
        transaction.get("schema")
        == TRANSACTION_SCHEMA
        and transaction.get(
            "status"
        )
        == "OPEN"
    ):
        baseline = (
            _baseline_from_transaction(
                transaction
            )
        )
        _validate_runtime_continuity(
            baseline,
            runtime,
        )
        if (
            control.get(
                "pairing_window_state"
            )
            != "OPEN"
            and int(time.time())
            <= int(
                transaction[
                    "expires_at_unix"
                ]
            )
        ):
            raise OnboardingError(
                "transaction_runtime_state_mismatch"
            )

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "inspect",
        "factory_accepted": True,
        "factory_release_sha256": (
            _sha256_text(
                str(
                    factory[
                        "release_id"
                    ]
                )
            )
        ),
        "database_counts": counts,
        "security_counts": (
            _security_state_counts()
        ),
        "transaction_present": (
            transaction is not None
        ),
        "successor_recovery_present": (
            successor_recovery
            is not None
        ),
        "successor_recovery_state": (
            successor_recovery.get(
                "status"
            )
            if successor_recovery
            is not None
            else None
        ),
        "legacy_transaction": (
            transaction is not None
            and transaction.get(
                "schema"
            )
            == LEGACY_TRANSACTION_SCHEMA
        ),
        "mutation": False,
        "pairing_udp_listener_count": (
            udp_count
        ),
        "pairing_http_listener_count": (
            tcp_count
        ),
        "pairing_window_state": (
            control.get(
                "pairing_window_state"
            )
        ),
        "broker_host_sha256": (
            control.get(
                "broker_host_sha256"
            )
        ),
        "raw_locator_in_output": False,
    }
    report.update(
        _public_runtime(
            runtime
        )
    )
    if transaction is None:
        report[
            "authorization_reusable"
        ] = None
    else:
        report[
            "authorization_reusable"
        ] = False
        report[
            "transaction_state"
        ] = transaction.get(
            "status"
        )
        if (
            transaction.get("schema")
            == TRANSACTION_SCHEMA
        ):
            report[
                "window_expired"
            ] = (
                int(time.time())
                > int(
                    transaction[
                        "expires_at_unix"
                    ]
                )
            )
    return report


def _successor_recovery_preflight() -> dict[str, Any]:
    _require_root()
    _require_file(
        COMPOSE_TARGET
    )
    _require_file(
        COMPOSE_ENV
    )
    _validate_factory_compose()
    factory = _validate_factory_marker()

    if (
        SUCCESSOR_RECOVERY_PATH.exists()
        or SUCCESSOR_RECOVERY_PATH.is_symlink()
    ):
        raise OnboardingError(
            "successor_recovery_record_already_exists"
        )

    predecessor, predecessor_sha256 = (
        _predecessor_transaction()
    )
    if (
        predecessor[
            "host_instance_id"
        ]
        != factory[
            "host_instance_id"
        ]
        or predecessor[
            "system_id"
        ]
        != factory[
            "system_id"
        ]
    ):
        raise OnboardingError(
            "successor_recovery_host_binding_changed"
        )
    if (
        predecessor[
            "release_id"
        ]
        == factory[
            "release_id"
        ]
    ):
        raise OnboardingError(
            "successor_recovery_repaired_release_not_advanced"
        )

    unit = predecessor.get(
        "watchdog_unit"
    )
    if isinstance(
        unit,
        str,
    ) and (
        _systemctl_is_active(
            f"{unit}.timer"
        )
        or _systemctl_is_active(
            f"{unit}.service"
        )
    ):
        raise OnboardingError(
            "successor_predecessor_watchdog_still_active"
        )

    baseline = _runtime_snapshot()
    _validate_factory_runtime(
        baseline
    )
    manager_id = baseline[
        "manager"
    ]["id"]
    _require_successor_recovery_capability(
        manager_id
    )

    control = _window_control(
        manager_id,
        "status",
    )
    _require_control_accepted(
        control
    )
    if control.get(
        "pairing_window_state"
    ) != "CLOSED":
        raise OnboardingError(
            "successor_recovery_requires_closed_window"
        )
    _pairing_socket_absent(
        manager_id
    )

    counts = _db_counts()
    security_counts = (
        _security_state_counts()
    )
    if any(
        value != 0
        for value
        in security_counts.values()
    ):
        raise OnboardingError(
            "successor_recovery_security_state_not_clean"
        )

    candidate = (
        _successor_recovery_candidate()
    )

    return {
        "factory": factory,
        "predecessor": predecessor,
        "predecessor_sha256": (
            predecessor_sha256
        ),
        "baseline": baseline,
        "manager_id": manager_id,
        "counts": counts,
        "security_counts": (
            security_counts
        ),
        "candidate": candidate,
    }


def inspect_successor_recovery() -> dict[str, Any]:
    preflight = (
        _successor_recovery_preflight()
    )
    factory = preflight[
        "factory"
    ]
    predecessor = preflight[
        "predecessor"
    ]
    baseline = preflight[
        "baseline"
    ]
    candidate = preflight[
        "candidate"
    ]

    report = {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": (
            "successor-inspect"
        ),
        "successor_recovery_eligible": True,
        "mutation": False,
        "authorization_consumed": False,
        "predecessor_transaction_sha256": (
            preflight[
                "predecessor_sha256"
            ]
        ),
        "predecessor_release_sha256": (
            _sha256_text(
                str(
                    predecessor[
                        "release_id"
                    ]
                )
            )
        ),
        "recovery_release_sha256": (
            _sha256_text(
                str(
                    factory[
                        "release_id"
                    ]
                )
            )
        ),
        "hardware_id_sha256": (
            candidate[
                "hardware_id_sha256"
            ]
        ),
        "pairing_id_sha256": (
            candidate[
                "pairing_id_sha256"
            ]
        ),
        "database_counts": (
            preflight[
                "counts"
            ]
        ),
        "security_counts": (
            preflight[
                "security_counts"
            ]
        ),
        "pairing_window_state": (
            "CLOSED"
        ),
        "pairing_udp_listener_count": 0,
        "pairing_http_listener_count": 0,
        "raw_locator_in_output": False,
    }
    report.update(
        _public_runtime(
            baseline
        )
    )
    return report


def recover_successor(
    *,
    authorization_id: str,
    confirmation: str,
) -> dict[str, Any]:
    _require_root()
    if (
        confirmation
        != SUCCESSOR_RECOVERY_CONFIRMATION
    ):
        raise OnboardingError(
            "successor_recovery_confirmation_invalid"
        )
    authorization_id = _authorization_id(
        authorization_id
    )

    preflight = (
        _successor_recovery_preflight()
    )
    factory = preflight[
        "factory"
    ]
    predecessor = preflight[
        "predecessor"
    ]
    predecessor_sha256 = (
        preflight[
            "predecessor_sha256"
        ]
    )
    baseline = preflight[
        "baseline"
    ]
    manager_id = preflight[
        "manager_id"
    ]
    candidate = preflight[
        "candidate"
    ]

    recovery = (
        _claim_successor_recovery(
            authorization_id=(
                authorization_id
            ),
            predecessor=predecessor,
            predecessor_sha256=(
                predecessor_sha256
            ),
            factory=factory,
            baseline=baseline,
            candidate=candidate,
        )
    )
    _ensure_private_directory(
        TRANSACTION_ARCHIVE_ROOT
    )

    try:
        result = (
            _recover_expired_first_control(
                manager_id,
                hardware_id_sha256=(
                    recovery[
                        "hardware_id_sha256"
                    ]
                ),
                pairing_id_sha256=(
                    recovery[
                        "pairing_id_sha256"
                    ]
                ),
            )
        )
        _require_control_accepted(
            result
        )
    except OPERATION_ERRORS as error:
        _advance_successor_recovery(
            status=(
                "STOPPED_RECOVERY_UNPROVEN"
            ),
            failure_type=(
                type(error).__name__
            ),
            recovery_result_proven=False,
        )
        raise OnboardingError(
            "successor_recovery_manager_result_unproven"
        ) from error

    try:
        after = _runtime_snapshot()
        _validate_runtime_continuity(
            baseline,
            after,
        )
        _validate_factory_runtime(
            after
        )
        closed = _window_control(
            manager_id,
            "status",
        )
        _require_control_accepted(
            closed
        )
        if closed.get(
            "pairing_window_state"
        ) != "CLOSED":
            raise OnboardingError(
                "successor_recovery_window_not_closed"
            )
        _pairing_socket_absent(
            manager_id
        )

        post_counts = _db_counts()
        post_security = (
            _security_state_counts()
        )
        _require_successor_recovered_state(
            post_counts,
            post_security,
            recovery,
        )
    except OPERATION_ERRORS as error:
        _advance_successor_recovery(
            status=(
                "STOPPED_POSTCHECK_FAILED"
            ),
            failure_type=(
                type(error).__name__
            ),
            manager_recovery_accepted=True,
            postcheck_passed=False,
        )
        raise OnboardingError(
            "successor_recovery_postcheck_failed"
        ) from error

    try:
        archive_path = (
            _archive_predecessor_transaction(
                predecessor_sha256
            )
        )
    except OPERATION_ERRORS as error:
        _advance_successor_recovery(
            status=(
                "STOPPED_ARCHIVE_FAILED"
            ),
            failure_type=(
                type(error).__name__
            ),
            manager_recovery_accepted=True,
            postcheck_passed=True,
            predecessor_archived=False,
        )
        raise OnboardingError(
            "successor_recovery_archive_failed"
        ) from error

    final = _advance_successor_recovery(
        status="CLOSED_PASS",
        closed_at_unix=int(
            time.time()
        ),
        manager_recovery_accepted=True,
        postcheck_passed=True,
        predecessor_archived=True,
        predecessor_archive_sha256=(
            _sha256_file(
                archive_path
            )
        ),
        final_database_counts=(
            post_counts
        ),
        final_security_counts=(
            post_security
        ),
        manager_container_unchanged=True,
        broker_continuity=True,
        homeassistant_continuity=True,
        pairing_exposure_closed=True,
    )
    _successor_recovery_record()

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": (
            "successor-recover"
        ),
        "authorization_consumed": True,
        "replay_allowed": False,
        "predecessor_archived": True,
        "predecessor_transaction_sha256": (
            final[
                "predecessor_transaction_sha256"
            ]
        ),
        "predecessor_release_sha256": (
            _sha256_text(
                str(
                    final[
                        "predecessor_release_id"
                    ]
                )
            )
        ),
        "recovery_release_sha256": (
            _sha256_text(
                str(
                    final[
                        "recovery_release_id"
                    ]
                )
            )
        ),
        "hardware_id_sha256": (
            final[
                "hardware_id_sha256"
            ]
        ),
        "pairing_id_sha256": (
            final[
                "pairing_id_sha256"
            ]
        ),
        "database_counts": (
            post_counts
        ),
        "security_counts": (
            post_security
        ),
        "pairing_window_state": (
            "CLOSED"
        ),
        "manager_recreated": False,
        "manager_container_unchanged": True,
        "broker_container_unchanged": True,
        "homeassistant_container_unchanged": True,
        "raw_locator_in_output": False,
    }


def _close_after_failed_open(
    *,
    transaction: dict[str, Any],
    baseline: dict[str, dict[str, Any]],
    manager_id: str,
    failure: Exception,
) -> None:
    close_failure: (
        Exception
        | None
    ) = None
    try:
        result = _window_control(
            manager_id,
            "close",
        )
        _require_control_accepted(
            result
        )
        _wait_dynamic_closed(
            manager_id
        )
        after = _runtime_snapshot()
        _validate_runtime_continuity(
            baseline,
            after,
        )
        _validate_factory_runtime(
            after
        )
    except OPERATION_ERRORS as error:
        close_failure = error

    if close_failure is None:
        stopped = _advance_transaction(
            status="STOPPED_OPEN_FAILED",
            failure_type=(
                type(failure).__name__
            ),
            pairing_exposure_closed=True,
        )
        if stopped.get(
            "watchdog_armed"
        ) is True:
            try:
                _cancel_watchdog(
                    stopped
                )
            except OPERATION_ERRORS:
                pass
        raise OnboardingError(
            "open_failed:"
            f"{type(failure).__name__}:"
            "dynamic_close_PASS"
        ) from failure

    _advance_transaction(
        status="OPEN_CLOSE_UNPROVEN",
        failure_type=(
            type(failure).__name__
        ),
        close_failure_type=(
            type(
                close_failure
            ).__name__
        ),
        pairing_exposure_closed=False,
        manager_deadline_remains_primary=True,
    )
    raise OnboardingError(
        "open_failed:"
        f"{type(failure).__name__}:"
        "dynamic_close_UNPROVEN"
    ) from close_failure


def open_window(
    *,
    authorization_id: str,
    peer_ip: str,
    confirmation: str,
    window_seconds: int,
) -> dict[str, Any]:
    _require_root()
    if (
        confirmation
        != OPEN_CONFIRMATION
    ):
        raise OnboardingError(
            "open_confirmation_invalid"
        )
    if (
        not 180
        <= window_seconds
        <= 600
    ):
        raise OnboardingError(
            "window_seconds_invalid"
        )
    authorization_id = (
        _authorization_id(
            authorization_id
        )
    )
    _require_file(
        COMPOSE_TARGET
    )
    _require_file(
        COMPOSE_ENV
    )
    _require_file(
        CA_CERT
    )
    _validate_factory_compose()
    factory = (
        _validate_factory_marker()
    )
    baseline = _runtime_snapshot()
    _validate_factory_runtime(
        baseline
    )
    counts = _db_counts()
    security_counts = (
        _security_state_counts()
    )
    _require_first_pair_admission(
        counts,
        security_counts,
        factory,
    )
    broker_host = (
        _resolve_route_selected_broker(
            baseline[
                "manager"
            ]["id"],
            peer_ip,
        )
    )
    _probe_external_broker_tls(
        broker_host
    )
    transaction = (
        _claim_transaction(
            authorization_id=(
                authorization_id
            ),
            factory=factory,
            peer_ip=peer_ip,
            broker_host=(
                broker_host
            ),
            baseline=baseline,
            window_seconds=(
                window_seconds
            ),
        )
    )
    transaction = _transaction()
    manager_id = baseline[
        "manager"
    ]["id"]

    try:
        result = _window_control(
            manager_id,
            "open",
            peer_ip=peer_ip,
            window_seconds=(
                window_seconds
            ),
        )
        _require_control_accepted(
            result
        )
        if (
            result.get(
                "broker_host_sha256"
            )
            != transaction[
                "broker_host_sha256"
            ]
        ):
            raise OnboardingError(
                "pairing_control_broker_hash_mismatch"
            )
        _wait_dynamic_open(
            manager_id,
            transaction[
                "broker_host_sha256"
            ],
        )
        after = _runtime_snapshot()
        _validate_runtime_continuity(
            baseline,
            after,
        )
        _validate_factory_runtime_configuration(
            after
        )
    except OPERATION_ERRORS as error:
        _close_after_failed_open(
            transaction=transaction,
            baseline=baseline,
            manager_id=manager_id,
            failure=error,
        )
        raise AssertionError(
            "unreachable"
        )

    opened_at = int(
        time.time()
    )
    transaction = (
        _advance_transaction(
            status="OPEN",
            opened_at_unix=(
                opened_at
            ),
            expires_at_unix=(
                opened_at
                + window_seconds
            ),
            manager_container_unchanged=(
                True
            ),
            broker_continuity=True,
            homeassistant_continuity=True,
            pairing_udp_listener_count=1,
            pairing_http_listener_count=1,
            pairing_health="PASS",
            pairing_socket="PASS",
            manager_broker_tls="PASS",
            external_broker_tls="PASS",
        )
    )

    try:
        transaction = (
            _arm_watchdog(
                transaction
            )
        )
    except OPERATION_ERRORS as error:
        _close_after_failed_open(
            transaction=transaction,
            baseline=baseline,
            manager_id=manager_id,
            failure=error,
        )
        raise AssertionError(
            "unreachable"
        )

    if not _watchdog_is_active(
        transaction
    ):
        _close_after_failed_open(
            transaction=transaction,
            baseline=baseline,
            manager_id=manager_id,
            failure=OnboardingError(
                "watchdog_lost_before_open_acceptance"
            ),
        )

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "open",
        "authorization_consumed": True,
        "replay_allowed": False,
        "pairing_window_state": "OPEN",
        "broker_host_sha256": (
            transaction[
                "broker_host_sha256"
            ]
        ),
        "window_seconds": (
            window_seconds
        ),
        "watchdog_active": True,
        "manager_recreated": False,
        "manager_container_unchanged": True,
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


def close_window(
    *,
    authorization_id: str,
    confirmation: str,
    outcome: str,
) -> dict[str, Any]:
    _require_root()
    if (
        confirmation
        != CLOSE_CONFIRMATION
    ):
        raise OnboardingError(
            "close_confirmation_invalid"
        )
    authorization_id = (
        _authorization_id(
            authorization_id
        )
    )
    transaction = _transaction()
    if (
        transaction.get("schema")
        != TRANSACTION_SCHEMA
    ):
        raise OnboardingError(
            "legacy_transaction_requires_separate_recovery"
        )
    if (
        transaction.get(
            "authorization_id"
        )
        != authorization_id
    ):
        raise OnboardingError(
            "close_authorization_mismatch"
        )
    if (
        transaction.get(
            "status"
        )
        != "OPEN"
    ):
        raise OnboardingError(
            "pairing_window_not_open"
        )
    if outcome not in {
        "success",
        "abort",
    }:
        raise OnboardingError(
            "close_outcome_invalid"
        )

    baseline = (
        _baseline_from_transaction(
            transaction
        )
    )
    before = _runtime_snapshot()
    _validate_runtime_continuity(
        baseline,
        before,
    )
    _validate_factory_runtime_configuration(
        before
    )
    manager_id = before[
        "manager"
    ]["id"]
    control = _window_control(
        manager_id,
        "status",
    )
    _require_control_accepted(
        control
    )
    if (
        control.get(
            "pairing_window_state"
        )
        != "OPEN"
    ):
        raise OnboardingError(
            "pairing_window_not_open"
        )
    if (
        control.get(
            "broker_host_sha256"
        )
        != transaction[
            "broker_host_sha256"
        ]
    ):
        raise OnboardingError(
            "pairing_control_broker_hash_mismatch"
        )

    watchdog_active = (
        _watchdog_is_active(
            transaction
        )
    )
    success_evidence: (
        dict[str, Any]
        | None
    ) = None
    if outcome == "success":
        expected_system_id = (
            transaction.get(
                "system_id"
            )
        )
        if (
            not isinstance(
                expected_system_id,
                str,
            )
            or not expected_system_id
        ):
            raise OnboardingError(
                "onboarding_transaction_system_id_invalid"
            )
        success_evidence = (
            _first_pair_success_evidence(
                expected_system_id
            )
        )
        counts = dict(
            success_evidence[
                "database_counts"
            ]
        )
        security_counts = dict(
            success_evidence[
                "security_counts"
            ]
        )
    else:
        counts = _db_counts()
        security_counts = (
            _security_state_counts()
        )

    expired = (
        int(time.time())
        > int(
            transaction[
                "expires_at_unix"
            ]
        )
    )

    close_result = _window_control(
        manager_id,
        "close",
    )
    _require_control_accepted(
        close_result
    )
    _wait_dynamic_closed(
        manager_id
    )

    after = _runtime_snapshot()
    _validate_runtime_continuity(
        baseline,
        after,
    )
    _validate_factory_runtime(
        after
    )
    post_counts = _db_counts()
    post_security_counts = (
        _security_state_counts()
    )
    if post_counts != counts:
        raise OnboardingError(
            "manager_database_counts_changed_during_close"
        )
    if (
        post_security_counts
        != security_counts
    ):
        raise OnboardingError(
            "security_state_counts_changed_during_close"
        )

    watchdog_cancel_error = (
        _cancel_watchdog(
            transaction
        )
    )

    terminal = "CLOSED_ABORTED"
    result_status = "PASS"
    if outcome == "success":
        if expired:
            terminal = (
                "CLOSED_FAIL_WINDOW_EXPIRED"
            )
            result_status = "FAIL"
        else:
            terminal = "CLOSED_PASS"

    _advance_transaction(
        status=terminal,
        closed_at_unix=(
            int(time.time())
        ),
        close_outcome=outcome,
        window_expired=expired,
        final_database_counts=(
            post_counts
        ),
        final_security_counts=(
            post_security_counts
        ),
        success_evidence=(
            success_evidence
        ),
        manager_container_unchanged=True,
        broker_continuity=True,
        homeassistant_continuity=True,
        factory_pairing_disabled=True,
        factory_broker_placeholder_restored=True,
        watchdog_active_before_close=(
            watchdog_active
        ),
        watchdog_cancel_error_type=(
            watchdog_cancel_error
        ),
    )

    return {
        "schema": SCHEMA,
        "status": result_status,
        "operation": "close",
        "authorization_consumed": True,
        "replay_allowed": False,
        "pairing_window_state": (
            terminal
        ),
        "close_outcome": outcome,
        "window_expired": expired,
        "watchdog_active_before_close": (
            watchdog_active
        ),
        "watchdog_cancel_error_type": (
            watchdog_cancel_error
        ),
        "database_counts": (
            post_counts
        ),
        "security_counts": (
            post_security_counts
        ),
        "success_evidence": (
            success_evidence
        ),
        "manager_factory_state_observed": True,
        "manager_recreated": False,
        "manager_container_unchanged": True,
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
    if (
        re.fullmatch(
            r"[0-9a-f]{64}",
            authorization_sha256,
        )
        is None
    ):
        raise OnboardingError(
            "watchdog_authorization_hash_invalid"
        )

    transaction = _transaction()
    if (
        transaction.get("schema")
        != TRANSACTION_SCHEMA
    ):
        raise OnboardingError(
            "legacy_transaction_requires_separate_recovery"
        )
    authorization_id = (
        transaction.get(
            "authorization_id"
        )
    )
    if (
        not isinstance(
            authorization_id,
            str,
        )
        or _sha256_text(
            authorization_id
        )
        != authorization_sha256
    ):
        raise OnboardingError(
            "watchdog_authorization_binding_mismatch"
        )

    status = transaction.get(
        "status"
    )
    if _watchdog_terminal_status(
        status
    ):
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "expire",
            "pairing_window_state": (
                status
            ),
            "mutation": False,
            "already_terminal": True,
            "raw_locator_in_output": False,
        }
    if status not in {
        "OPEN",
        "OPEN_CLOSE_UNPROVEN",
    }:
        raise OnboardingError(
            "watchdog_transaction_state_invalid"
        )
    if (
        transaction.get(
            "watchdog_armed"
        )
        is not True
    ):
        raise OnboardingError(
            "watchdog_not_bound"
        )
    if (
        int(time.time())
        < int(
            transaction[
                "expires_at_unix"
            ]
        )
    ):
        raise OnboardingError(
            "watchdog_deadline_not_reached"
        )

    baseline = (
        _baseline_from_transaction(
            transaction
        )
    )
    runtime = _runtime_snapshot()
    _validate_runtime_continuity(
        baseline,
        runtime,
    )
    _validate_factory_runtime_configuration(
        runtime
    )
    manager_id = runtime[
        "manager"
    ]["id"]

    control_error: (
        Exception
        | None
    ) = None
    try:
        control = _window_control(
            manager_id,
            "status",
        )
        _require_control_accepted(
            control
        )
        state = control.get(
            "pairing_window_state"
        )
        if state == "OPEN":
            close_result = (
                _window_control(
                    manager_id,
                    "close",
                )
            )
            _require_control_accepted(
                close_result
            )
        elif state not in {
            "CLOSED",
            "CLOSING",
        }:
            raise OnboardingError(
                "pairing_control_timeout_state_invalid"
            )
        _wait_dynamic_closed(
            manager_id
        )
    except OPERATION_ERRORS as error:
        control_error = error

    udp_count = _listener_count(
        "udp",
        PAIRING_UDP_PORT,
    )
    tcp_count = _listener_count(
        "tcp",
        PAIRING_HTTP_PORT,
    )
    if control_error is not None:
        if (
            udp_count == 0
            and tcp_count == 0
        ):
            terminal = (
                "CLOSED_TIMEOUT_CONTROL_UNAVAILABLE"
            )
            _advance_transaction(
                status=terminal,
                timeout_at_unix=(
                    int(time.time())
                ),
                timeout_control_failure_type=(
                    type(
                        control_error
                    ).__name__
                ),
                pairing_exposure_closed=True,
                manager_recreated=False,
            )
            return {
                "schema": SCHEMA,
                "status": "FAIL",
                "operation": "expire",
                "pairing_window_state": (
                    terminal
                ),
                "authorization_consumed": True,
                "replay_allowed": False,
                "pairing_exposure_closed": True,
                "manager_recreated": False,
                "pairing_udp_listener_count": 0,
                "pairing_http_listener_count": 0,
                "raw_locator_in_output": False,
            }
        _advance_transaction(
            status="TIMEOUT_CLOSE_UNPROVEN",
            timeout_at_unix=(
                int(time.time())
            ),
            timeout_control_failure_type=(
                type(
                    control_error
                ).__name__
            ),
            pairing_exposure_closed=False,
            manager_recreated=False,
        )
        raise OnboardingError(
            "timeout_pairing_exposure_unproven"
        ) from control_error

    after = _runtime_snapshot()
    _validate_runtime_continuity(
        baseline,
        after,
    )
    _validate_factory_runtime(
        after
    )
    post_counts = _db_counts()
    post_security_counts = (
        _security_state_counts()
    )
    terminal = "CLOSED_TIMEOUT"
    _advance_transaction(
        status=terminal,
        timeout_at_unix=(
            int(time.time())
        ),
        final_database_counts=(
            post_counts
        ),
        final_security_counts=(
            post_security_counts
        ),
        pairing_exposure_closed=True,
        manager_recreated=False,
        factory_pairing_disabled=True,
        factory_broker_placeholder_restored=True,
    )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "expire",
        "pairing_window_state": (
            terminal
        ),
        "authorization_consumed": True,
        "replay_allowed": False,
        "pairing_exposure_closed": True,
        "manager_recreated": False,
        "factory_pairing_disabled": True,
        "factory_broker_placeholder_restored": True,
        "pairing_udp_listener_count": 0,
        "pairing_http_listener_count": 0,
        "raw_locator_in_output": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=(
            "n3w-t1-first-pairing-onboarding"
        ),
    )
    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True,
        )
    )

    subparsers.add_parser(
        "inspect"
    )
    subparsers.add_parser(
        "successor-inspect"
    )

    open_command = (
        subparsers.add_parser(
            "open"
        )
    )
    open_command.add_argument(
        "--authorization-id",
        required=True,
    )
    open_command.add_argument(
        "--peer-ip",
        required=True,
    )
    open_command.add_argument(
        "--confirm",
        required=True,
    )
    open_command.add_argument(
        "--window-seconds",
        type=int,
        default=300,
    )

    successor_recovery_command = (
        subparsers.add_parser(
            "successor-recover"
        )
    )
    successor_recovery_command.add_argument(
        "--authorization-id",
        required=True,
    )
    successor_recovery_command.add_argument(
        "--confirm",
        required=True,
    )

    expire_command = (
        subparsers.add_parser(
            "expire"
        )
    )
    expire_command.add_argument(
        "--authorization-sha256",
        required=True,
    )

    close_command = (
        subparsers.add_parser(
            "close"
        )
    )
    close_command.add_argument(
        "--authorization-id",
        required=True,
    )
    close_command.add_argument(
        "--confirm",
        required=True,
    )
    close_command.add_argument(
        "--outcome",
        choices=(
            "success",
            "abort",
        ),
        required=True,
    )

    return parser


def main(
    argv: Sequence[str]
    | None = None,
) -> int:
    args = _parser().parse_args(
        argv
    )
    try:
        if args.command == "inspect":
            report = inspect()
        elif (
            args.command
            == "successor-inspect"
        ):
            report = (
                inspect_successor_recovery()
            )
        elif args.command == "expire":
            with _exclusive_lock(
                blocking=True
            ):
                report = (
                    expire_window(
                        authorization_sha256=(
                            args.authorization_sha256
                        ),
                    )
                )
        else:
            with _exclusive_lock():
                if (
                    args.command
                    == "open"
                ):
                    report = (
                        open_window(
                            authorization_id=(
                                args.authorization_id
                            ),
                            peer_ip=(
                                args.peer_ip
                            ),
                            confirmation=(
                                args.confirm
                            ),
                            window_seconds=(
                                args.window_seconds
                            ),
                        )
                    )
                elif (
                    args.command
                    == "successor-recover"
                ):
                    report = (
                        recover_successor(
                            authorization_id=(
                                args.authorization_id
                            ),
                            confirmation=(
                                args.confirm
                            ),
                        )
                    )
                else:
                    report = (
                        close_window(
                            authorization_id=(
                                args.authorization_id
                            ),
                            confirmation=(
                                args.confirm
                            ),
                            outcome=(
                                args.outcome
                            ),
                        )
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
            "mutation_state": (
                "UNKNOWN_IF_POSTCLAIM"
                if (
                    TRANSACTION_PATH
                    .exists()
                    or SUCCESSOR_RECOVERY_PATH
                    .exists()
                )
                else "NONE"
            ),
            "authorization_reusable": (
                False
                if (
                    TRANSACTION_PATH
                    .exists()
                    or SUCCESSOR_RECOVERY_PATH
                    .exists()
                )
                else None
            ),
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
    return (
        0
        if report.get("status")
        == "PASS"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
