#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-manager-repaired-release-rollout/1"
TRANSACTION_SCHEMA = "gh.n3w-t1-manager-repaired-release-rollout-transaction/1"
COMPOSE_PROJECT = "n3wfc4"
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
EXPECTED_COMPOSE = Path("/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.yml")
PROVISIONING_ROOT = Path("/var/lib/n3w-t1-provisioning")
FACTORY_ACCEPTED = PROVISIONING_ROOT / "FACTORY_ACCEPTED.json"
PREDECESSOR_ONBOARDING = PROVISIONING_ROOT / "FIRST_PAIRING_ONBOARDING.json"
SUCCESSOR_RECOVERY = PROVISIONING_ROOT / "FIRST_PAIRING_SUCCESSOR_RECOVERY.json"
TRANSACTION = PROVISIONING_ROOT / "MANAGER_REPAIRED_RELEASE_ROLLOUT.json"
ENV_BACKUP = PROVISIONING_ROOT / "MANAGER_REPAIRED_RELEASE_ROLLOUT.env.backup"
MANAGER_DB = Path("/var/lib/greenhouse-manager/manager/manager-state.sqlite3")
CREDENTIAL_DB = Path("/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3")
APPLICATION_KEY_DB = Path("/var/lib/greenhouse-manager/n3w/relay-authorization.sqlite3")
PEER_TRUST_DB = Path("/var/lib/greenhouse-manager/n3w/system-peer-trust.sqlite3")
PAIRING_UDP_PORT = 47111
PAIRING_HTTP_PORT = 47112
EXPECTED_SERVICES = ("broker", "manager", "homeassistant")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
AUTH_RE = re.compile(r"N3W_T1_[A-Za-z0-9_.:-]{8,160}")
CONFIG_KEYS = (
    "Entrypoint",
    "Cmd",
    "User",
    "Env",
    "WorkingDir",
    "Labels",
    "Healthcheck",
    "StopSignal",
    "Volumes",
    "ExposedPorts",
)


class RolloutError(RuntimeError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(value)
    ).hexdigest()


def _normalized_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)
    return digest.hexdigest()


def _run(
    argv: tuple[str, ...],
    *,
    timeout: float = 60.0,
    allowed: frozenset[int] = frozenset({0}),
) -> str:
    completed = subprocess.run(
        argv,
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode not in allowed:
        detail = (
            completed.stderr.strip()
            or completed.stdout.strip()
        )
        raise RolloutError(
            "command_failed:"
            + argv[0]
            + ":"
            + str(completed.returncode)
            + ":detail_sha256="
            + (
                _sha_text(detail)
                if detail
                else "none"
            )
        )
    return completed.stdout


def _require_root() -> None:
    if os.geteuid() != 0:
        raise RolloutError("root_required")


def _require_regular(
    path: Path,
    *,
    mode: int | None = None,
) -> None:
    if path.is_symlink() or not path.is_file():
        raise RolloutError(
            "file_invalid:" + path.name
        )
    if mode is not None:
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) != mode:
            raise RolloutError(
                "file_mode_invalid:" + path.name
            )


def _read_json(path: Path) -> dict[str, Any]:
    _require_regular(path)
    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        raise RolloutError(
            "json_invalid:" + path.name
        ) from error
    if not isinstance(value, dict):
        raise RolloutError(
            "json_invalid:" + path.name
        )
    return value


def _atomic_private_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    parent = path.parent
    if (
        parent.is_symlink()
        or not parent.is_dir()
    ):
        raise RolloutError(
            "private_parent_invalid"
        )
    descriptor, raw = tempfile.mkstemp(
        prefix=path.name + ".",
        dir=parent,
    )
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(
            descriptor,
            "wb",
            closefd=True,
        ) as stream:
            stream.write(_canonical_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(
            parent,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_private_bytes(
    path: Path,
    payload: bytes,
) -> None:
    parent = path.parent
    if (
        parent.is_symlink()
        or not parent.is_dir()
    ):
        raise RolloutError(
            "private_parent_invalid"
        )
    descriptor, raw = tempfile.mkstemp(
        prefix=path.name + ".",
        dir=parent,
    )
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(
            descriptor,
            "wb",
            closefd=True,
        ) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(
            parent,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _service_id(service: str) -> str:
    output = _run(
        (
            "docker",
            "ps",
            "-q",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project="
            + COMPOSE_PROJECT,
            "--filter",
            "label=com.docker.compose.service="
            + service,
        )
    )
    values = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]
    if (
        len(values) != 1
        or re.fullmatch(
            r"[0-9a-f]{64}",
            values[0],
        )
        is None
    ):
        raise RolloutError(
            service
            + "_container_identity_invalid"
        )
    return values[0]


def _docker_inspect(
    identity: str,
) -> dict[str, Any]:
    try:
        value = json.loads(
            _run(
                (
                    "docker",
                    "inspect",
                    identity,
                )
            )
        )
    except json.JSONDecodeError as error:
        raise RolloutError(
            "docker_inspect_invalid"
        ) from error
    if (
        not isinstance(value, list)
        or len(value) != 1
        or not isinstance(value[0], dict)
    ):
        raise RolloutError(
            "docker_inspect_invalid"
        )
    return value[0]


def _mount_binding(
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    result = []
    for item in document.get("Mounts") or []:
        if not isinstance(item, dict):
            raise RolloutError(
                "container_mount_invalid"
            )
        result.append(
            {
                "type": str(
                    item.get("Type", "")
                ),
                "source": str(
                    item.get("Source", "")
                ),
                "destination": str(
                    item.get("Destination", "")
                ),
                "rw": bool(
                    item.get("RW", False)
                ),
                "propagation": str(
                    item.get(
                        "Propagation",
                        "",
                    )
                ),
            }
        )
    return sorted(
        result,
        key=lambda item: (
            item["destination"],
            item["source"],
        ),
    )


def _container_snapshot(
    service: str,
) -> dict[str, Any]:
    identity = _service_id(service)
    document = _docker_inspect(identity)
    config = document.get("Config")
    state = document.get("State")
    host = document.get("HostConfig")
    if (
        not isinstance(config, dict)
        or not isinstance(state, dict)
        or not isinstance(host, dict)
        or state.get("Running") is not True
    ):
        raise RolloutError(
            service
            + "_container_runtime_invalid"
        )
    labels = config.get("Labels")
    if (
        not isinstance(labels, dict)
        or labels.get(
            "com.docker.compose.project"
        )
        != COMPOSE_PROJECT
        or labels.get(
            "com.docker.compose.service"
        )
        != service
    ):
        raise RolloutError(
            service
            + "_compose_binding_invalid"
        )
    mounts = _mount_binding(document)
    result = {
        "id": identity,
        "id_sha256": _sha_text(identity),
        "image_ref": str(
            config.get("Image", "")
        ),
        "image_ref_sha256": _sha_text(
            str(config.get("Image", ""))
        ),
        "image_id": str(
            document.get("Image", "")
        ),
        "image_id_sha256": _sha_text(
            str(document.get("Image", ""))
        ),
        "restart_count": int(
            document.get("RestartCount", 0)
        ),
        "started_at": str(
            state.get("StartedAt", "")
        ),
        "network_mode": str(
            host.get("NetworkMode", "")
        ),
        "user": str(
            config.get("User", "")
        ),
        "readonly_rootfs": bool(
            host.get("ReadonlyRootfs", False)
        ),
        "tmpfs_sha256": _canonical_sha(
            host.get("Tmpfs") or {}
        ),
        "cap_drop_sha256": _canonical_sha(
            sorted(host.get("CapDrop") or [])
        ),
        "security_opt_sha256": _canonical_sha(
            sorted(
                host.get("SecurityOpt") or []
            )
        ),
        "mount_binding_sha256": (
            _canonical_sha(mounts)
        ),
    }
    if service == "manager":
        if (
            result["network_mode"] != "host"
            or result["user"]
            not in {"999:999", "greenhouse"}
            or result["readonly_rootfs"]
            is not True
        ):
            raise RolloutError(
                "manager_runtime_contract_invalid"
            )
        config_files = str(
            labels.get(
                "com.docker.compose.project.config_files",
                "",
            )
        )
        working_dir = str(
            labels.get(
                "com.docker.compose.project.working_dir",
                "",
            )
        )
        if "," in config_files:
            raise RolloutError(
                "manager_compose_file_set_invalid"
            )
        compose = Path(config_files)
        if (
            not compose.is_absolute()
            or compose.resolve()
            != EXPECTED_COMPOSE
            or Path(working_dir).resolve()
            != EXPECTED_COMPOSE.parent
        ):
            raise RolloutError(
                "manager_compose_path_invalid"
            )
        result["compose_path"] = str(
            compose.resolve()
        )
    return result


def _runtime_snapshot() -> dict[str, Any]:
    return {
        service: _container_snapshot(service)
        for service in EXPECTED_SERVICES
    }


def _parse_env(
    payload: bytes,
) -> tuple[str, str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeError as error:
        raise RolloutError(
            "compose_env_encoding_invalid"
        ) from error
    lines = text.splitlines(
        keepends=True
    )
    matches = [
        line
        for line in lines
        if line.startswith(
            "GH_MANAGER_IMAGE="
        )
    ]
    if len(matches) != 1:
        raise RolloutError(
            "manager_image_env_binding_invalid"
        )
    value = matches[0].split(
        "=",
        1,
    )[1].rstrip("\r\n")
    if (
        not value
        or any(
            character.isspace()
            for character in value
        )
    ):
        raise RolloutError(
            "manager_image_env_value_invalid"
        )
    remainder = b"".join(
        line.encode("utf-8")
        for line in lines
        if not line.startswith(
            "GH_MANAGER_IMAGE="
        )
    )
    return value, hashlib.sha256(
        remainder
    ).hexdigest()


def _replace_manager_image(
    payload: bytes,
    image: str,
) -> bytes:
    old, _ = _parse_env(payload)
    if old == image:
        raise RolloutError(
            "manager_image_already_selected"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeError as error:
        raise RolloutError(
            "compose_env_encoding_invalid"
        ) from error
    output = []
    replaced = 0
    for line in text.splitlines(
        keepends=True
    ):
        if line.startswith(
            "GH_MANAGER_IMAGE="
        ):
            newline = (
                "\r\n"
                if line.endswith("\r\n")
                else "\n"
                if line.endswith("\n")
                else ""
            )
            output.append(
                "GH_MANAGER_IMAGE="
                + image
                + newline
            )
            replaced += 1
        else:
            output.append(line)
    if replaced != 1:
        raise RolloutError(
            "manager_image_env_replace_invalid"
        )
    result = "".join(output).encode(
        "utf-8"
    )
    _, before = _parse_env(payload)
    selected, after = _parse_env(result)
    if (
        selected != image
        or before != after
    ):
        raise RolloutError(
            "manager_image_env_scope_drift"
        )
    return result


def _render_compose() -> dict[str, Any]:
    try:
        value = json.loads(
            _run(
                (
                    "docker",
                    "compose",
                    "--env-file",
                    str(COMPOSE_ENV),
                    "-f",
                    str(EXPECTED_COMPOSE),
                    "--profile",
                    "*",
                    "config",
                    "--format",
                    "json",
                ),
                timeout=60,
            )
        )
    except json.JSONDecodeError as error:
        raise RolloutError(
            "compose_render_invalid"
        ) from error
    if not isinstance(value, dict):
        raise RolloutError(
            "compose_render_invalid"
        )
    services = value.get("services")
    if (
        not isinstance(services, dict)
        or not isinstance(
            services.get("manager"),
            dict,
        )
    ):
        raise RolloutError(
            "compose_manager_missing"
        )
    return value


def _normalized_compose(
    document: dict[str, Any],
) -> tuple[str, str]:
    value = deepcopy(document)
    manager = value["services"]["manager"]
    image = str(
        manager.get("image", "")
    )
    manager["image"] = (
        "<GH_MANAGER_IMAGE>"
    )
    return image, _canonical_sha(value)


def _listener_count(
    protocol: str,
    port: int,
) -> int:
    if protocol == "udp":
        output = _run(
            (
                "ss",
                "-H",
                "-lun",
                "sport = :" + str(port),
            )
        )
    elif protocol == "tcp":
        output = _run(
            (
                "ss",
                "-H",
                "-ltn",
                "sport = :" + str(port),
            )
        )
    else:
        raise RolloutError(
            "listener_protocol_invalid"
        )
    return sum(
        1
        for line in output.splitlines()
        if line.strip()
    )


def _pairing_status(
    manager_id: str,
) -> dict[str, Any]:
    try:
        value = json.loads(
            _run(
                (
                    "docker",
                    "exec",
                    manager_id,
                    "greenhouse-manager-pairing",
                    "window-status",
                ),
                timeout=20,
                allowed=frozenset({0, 2}),
            )
        )
    except json.JSONDecodeError as error:
        raise RolloutError(
            "pairing_control_response_invalid"
        ) from error
    if (
        not isinstance(value, dict)
        or value.get("accepted")
        is not True
        or value.get(
            "pairing_window_state"
        )
        != "CLOSED"
        or value.get(
            "raw_locator_in_output"
        )
        is not False
    ):
        raise RolloutError(
            "pairing_window_not_closed"
        )
    return value


def _pairing_socket_absent(
    manager_id: str,
) -> None:
    source = (
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
            source,
        ),
        timeout=15,
    )


def _probe_manager_tls(
    manager_id: str,
) -> None:
    source = (
        "import socket,ssl;"
        "c=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);"
        "c.check_hostname=True;"
        "c.verify_mode=ssl.CERT_REQUIRED;"
        "c.load_verify_locations("
        "cafile='/run/n3w/tls/ca.pem');"
        "r=socket.create_connection(('armbian',8883),5);"
        "s=c.wrap_socket(r,server_hostname='armbian');"
        "s.close()"
    )
    _run(
        (
            "docker",
            "exec",
            manager_id,
            "python",
            "-c",
            source,
        ),
        timeout=15,
    )


def _read_only_db(
    path: Path,
) -> sqlite3.Connection:
    _require_regular(path)
    try:
        connection = sqlite3.connect(
            "file:" + str(path) + "?mode=ro",
            uri=True,
        )
    except sqlite3.Error as error:
        raise RolloutError(
            "database_open_failed:"
            + path.name
        ) from error
    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA query_only=ON"
    )
    return connection


def _table_fingerprint(
    connection: sqlite3.Connection,
    table: str,
) -> dict[str, Any]:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if exists is None:
        raise RolloutError(
            "manager_table_missing:" + table
        )
    columns = [
        str(row["name"])
        for row in connection.execute(
            "PRAGMA table_info(" + table + ")"
        ).fetchall()
    ]
    rows = [
        [row[column] for column in columns]
        for row in connection.execute(
            "SELECT * FROM "
            + table
            + " ORDER BY rowid"
        ).fetchall()
    ]
    return {
        "columns": columns,
        "rows": rows,
    }


def _manager_state() -> dict[str, Any]:
    connection = _read_only_db(
        MANAGER_DB
    )
    try:
        current = connection.execute(
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
                    THEN 1 ELSE 0
                END AS expired_by_clock
            FROM registrations AS r
            JOIN pairing_sessions AS s
              ON s.pairing_id =
                 r.current_pairing_id
            """
        ).fetchall()
        if len(current) != 1:
            raise RolloutError(
                "rollout_registration_shape_invalid"
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
            or row["node_id"] is not None
            or row[
                "logical_location_id"
            ]
            is not None
        ):
            raise RolloutError(
                "rollout_current_identity_invalid"
            )
        state = str(row["state"])
        if state == "pending":
            if int(
                row["expired_by_clock"]
            ) != 1:
                raise RolloutError(
                    "rollout_pending_not_expired"
                )
        elif (
            state != "expired"
            or row["reason"] != "expired"
        ):
            raise RolloutError(
                "rollout_current_state_invalid"
            )

        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(DISTINCT hardware_id)
                    AS hardware_count,
                SUM(
                    CASE WHEN state='approved'
                    THEN 1 ELSE 0 END
                ) AS approved_count,
                SUM(
                    CASE WHEN state='pending'
                    THEN 1 ELSE 0 END
                ) AS pending_count
            FROM pairing_sessions
            """
        ).fetchone()
        if (
            summary is None
            or int(summary["total"]) < 1
            or int(
                summary["hardware_count"]
            ) != 1
            or int(
                summary["approved_count"]
                or 0
            ) != 0
            or int(
                summary["pending_count"]
                or 0
            )
            != (
                1
                if state == "pending"
                else 0
            )
        ):
            raise RolloutError(
                "rollout_pairing_history_invalid"
            )

        zero_queries = {
            "node_id_leases":
                "SELECT COUNT(*) "
                "FROM node_id_leases",
            "registration_node_history":
                "SELECT COUNT(*) "
                "FROM registration_node_history",
            "retirement_outbox":
                "SELECT COUNT(*) "
                "FROM retirement_outbox",
            "assigned_events":
                "SELECT COUNT(*) "
                "FROM registration_events "
                "WHERE node_id IS NOT NULL "
                "OR logical_location_id IS NOT NULL",
        }
        zero_counts = {
            name: int(
                connection.execute(
                    query
                ).fetchone()[0]
            )
            for name, query
            in zero_queries.items()
        }
        if any(
            value != 0
            for value in zero_counts.values()
        ):
            raise RolloutError(
                "rollout_prior_identity_state_present"
            )

        tables = (
            "registrations",
            "pairing_sessions",
            "registration_events",
            "node_id_leases",
            "registration_node_history",
            "retirement_outbox",
        )
        logical = {
            table: _table_fingerprint(
                connection,
                table,
            )
            for table in tables
        }
        counts = {
            table: len(
                logical[table]["rows"]
            )
            for table in tables
        }
    finally:
        connection.close()

    return {
        "state_sha256": _canonical_sha(
            logical
        ),
        "counts": counts,
        "hardware_id_sha256": _sha_text(
            str(row["hardware_id"])
        ),
        "pairing_id_sha256": _sha_text(
            str(row["pairing_id"])
        ),
        "current_state": state,
        "current_expired_by_clock": True,
    }


def _optional_count(
    path: Path,
    table: str,
) -> int:
    if path.is_symlink():
        raise RolloutError(
            "optional_database_symlink:"
            + path.name
        )
    if not path.exists():
        return 0
    connection = _read_only_db(path)
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists is None:
            raise RolloutError(
                "optional_database_table_missing:"
                + path.name
            )
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM "
                + table
            ).fetchone()[0]
        )
    finally:
        connection.close()


def _security_counts() -> dict[str, int]:
    credentials = _optional_count(
        CREDENTIAL_DB,
        "credential_assignments",
    )
    peer_trust = _optional_count(
        PEER_TRUST_DB,
        "n3w_system_peer_trust",
    )
    keys = _read_only_db(
        APPLICATION_KEY_DB
    )
    try:
        active_nodes = int(
            keys.execute(
                "SELECT COUNT(*) "
                "FROM n3w_relay_nodes "
                "WHERE active=1"
            ).fetchone()[0]
        )
        epochs = int(
            keys.execute(
                "SELECT COUNT(*) "
                "FROM n3w_relay_key_epochs"
            ).fetchone()[0]
        )
    finally:
        keys.close()
    result = {
        "credential_assignments":
            credentials,
        "peer_trust_records":
            peer_trust,
        "application_key_active_nodes":
            active_nodes,
        "application_key_epochs":
            epochs,
    }
    if any(
        value != 0
        for value in result.values()
    ):
        raise RolloutError(
            "rollout_security_state_not_clean"
        )
    return result


def _factory_identity() -> dict[str, str]:
    value = _read_json(
        FACTORY_ACCEPTED
    )
    if (
        value.get("schema")
        != "gh.n3w.t1-factory-accepted/1"
        or value.get("status") != "PASS"
        or value.get(
            "factory_accepted"
        )
        is not True
    ):
        raise RolloutError(
            "factory_acceptance_invalid"
        )
    result = {}
    for key in (
        "host_instance_id",
        "system_id",
    ):
        observed = value.get(key)
        if (
            not isinstance(observed, str)
            or not observed
        ):
            raise RolloutError(
                "factory_identity_invalid"
            )
        result[
            key + "_sha256"
        ] = _sha_text(observed)
    return result


def _compose_state(
    runtime: dict[str, Any],
) -> dict[str, Any]:
    _require_regular(COMPOSE_ENV)
    _require_regular(EXPECTED_COMPOSE)
    metadata = COMPOSE_ENV.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(
            metadata.st_mode
        )
        != 0o600
        or metadata.st_nlink != 1
    ):
        raise RolloutError(
            "compose_env_metadata_invalid"
        )
    env_bytes = COMPOSE_ENV.read_bytes()
    manager_image, excluding = (
        _parse_env(env_bytes)
    )
    if (
        runtime["manager"]["image_ref"]
        != manager_image
    ):
        raise RolloutError(
            "manager_runtime_env_image_drift"
        )
    rendered = _render_compose()
    rendered_image, normalized = (
        _normalized_compose(rendered)
    )
    if rendered_image != manager_image:
        raise RolloutError(
            "manager_rendered_image_drift"
        )
    return {
        "compose_sha256": _sha_file(
            EXPECTED_COMPOSE
        ),
        "env_sha256": hashlib.sha256(
            env_bytes
        ).hexdigest(),
        "env_excluding_manager_sha256":
            excluding,
        "manager_image": manager_image,
        "manager_image_sha256":
            _sha_text(manager_image),
        "normalized_render_sha256":
            normalized,
    }


def _exposure_state(
    manager_id: str,
) -> dict[str, Any]:
    status = _pairing_status(
        manager_id
    )
    udp = _listener_count(
        "udp",
        PAIRING_UDP_PORT,
    )
    tcp = _listener_count(
        "tcp",
        PAIRING_HTTP_PORT,
    )
    if udp != 0 or tcp != 0:
        raise RolloutError(
            "pairing_listener_present"
        )
    _pairing_socket_absent(
        manager_id
    )
    _probe_manager_tls(
        manager_id
    )
    return {
        "pairing_window_state":
            "CLOSED",
        "udp_listener_count": udp,
        "tcp_listener_count": tcp,
        "raw_locator_in_output": False,
        "control_code": str(
            status.get("code", "")
        ),
    }


def _inspect_state() -> dict[str, Any]:
    _require_root()
    runtime = _runtime_snapshot()
    compose = _compose_state(
        runtime
    )
    manager_state = _manager_state()
    security = _security_counts()
    factory = _factory_identity()
    exposure = _exposure_state(
        runtime["manager"]["id"]
    )
    private = {
        "schema": SCHEMA,
        "factory": factory,
        "compose": compose,
        "runtime": runtime,
        "manager_state": manager_state,
        "security_counts": security,
        "exposure": exposure,
    }
    return {
        "private": private,
        "baseline_sha256":
            _canonical_sha(private),
    }


def _public_inspect(
    inspected: dict[str, Any],
) -> dict[str, Any]:
    value = inspected["private"]
    runtime = value["runtime"]
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "inspect",
        "mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "baseline_sha256":
            inspected["baseline_sha256"],
        "host_instance_id_sha256":
            value["factory"][
                "host_instance_id_sha256"
            ],
        "system_id_sha256":
            value["factory"][
                "system_id_sha256"
            ],
        "compose_sha256":
            value["compose"][
                "compose_sha256"
            ],
        "compose_env_sha256":
            value["compose"][
                "env_sha256"
            ],
        "manager_image_sha256":
            value["compose"][
                "manager_image_sha256"
            ],
        "broker_container_id_sha256":
            runtime["broker"][
                "id_sha256"
            ],
        "manager_container_id_sha256":
            runtime["manager"][
                "id_sha256"
            ],
        "homeassistant_container_id_sha256":
            runtime["homeassistant"][
                "id_sha256"
            ],
        "broker_restart_count":
            runtime["broker"][
                "restart_count"
            ],
        "manager_restart_count":
            runtime["manager"][
                "restart_count"
            ],
        "homeassistant_restart_count":
            runtime["homeassistant"][
                "restart_count"
            ],
        "pairing_state_sha256":
            value["manager_state"][
                "state_sha256"
            ],
        "hardware_id_sha256":
            value["manager_state"][
                "hardware_id_sha256"
            ],
        "pairing_id_sha256":
            value["manager_state"][
                "pairing_id_sha256"
            ],
        "current_pairing_state":
            value["manager_state"][
                "current_state"
            ],
        "security_counts":
            value["security_counts"],
        "pairing_window_state":
            "CLOSED",
        "pairing_udp_listener_count": 0,
        "pairing_http_listener_count": 0,
        "raw_locator_in_output": False,
        "board_access": False,
    }


def _validate_sha(
    value: str,
    name: str,
    *,
    git: bool = False,
) -> str:
    pattern = (
        GIT_SHA_RE
        if git
        else SHA256_RE
    )
    if pattern.fullmatch(value) is None:
        raise RolloutError(
            name + "_invalid"
        )
    return value


def _stage_path(
    authorization_id: str,
) -> Path:
    return Path(
        "/var/tmp/n3w-manager-rollout-"
        + _sha_text(
            authorization_id
        )[:16]
    )


def _reject_authorization_reuse(
    authorization_id: str,
) -> None:
    if PREDECESSOR_ONBOARDING.exists():
        value = _read_json(
            PREDECESSOR_ONBOARDING
        )
        if (
            value.get(
                "authorization_id"
            )
            == authorization_id
        ):
            raise RolloutError(
                "rollout_authorization_reused"
            )
    if SUCCESSOR_RECOVERY.exists():
        raise RolloutError(
            "successor_recovery_already_started"
        )


def claim(args: argparse.Namespace) -> dict[str, Any]:
    _require_root()
    if (
        not AUTH_RE.fullmatch(
            args.authorization_id
        )
    ):
        raise RolloutError(
            "authorization_id_invalid"
        )
    if (
        TRANSACTION.exists()
        or TRANSACTION.is_symlink()
        or ENV_BACKUP.exists()
        or ENV_BACKUP.is_symlink()
    ):
        raise RolloutError(
            "rollout_transaction_already_exists"
        )
    _reject_authorization_reuse(
        args.authorization_id
    )
    baseline = _inspect_state()
    if (
        baseline["baseline_sha256"]
        != args.baseline_sha256
    ):
        raise RolloutError(
            "rollout_baseline_changed"
        )
    stage = _stage_path(
        args.authorization_id
    )
    if stage.exists() or stage.is_symlink():
        raise RolloutError(
            "rollout_stage_collision"
        )

    for value, name in (
        (
            args.release_id,
            "release_id",
        ),
        (
            args.release_sha256,
            "release_sha256",
        ),
        (
            args.manager_tar_sha256,
            "manager_tar_sha256",
        ),
        (
            args.rootfs_layers_sha256,
            "rootfs_layers_sha256",
        ),
        (
            args.config_contract_sha256,
            "config_contract_sha256",
        ),
        (
            args.host_tool_sha256,
            "host_tool_sha256",
        ),
        (
            args.remote_tool_sha256,
            "remote_tool_sha256",
        ),
    ):
        _validate_sha(value, name)
    _validate_sha(
        args.source_head,
        "source_head",
        git=True,
    )
    if (
        not args.new_image
        or any(
            character.isspace()
            for character in args.new_image
        )
        or not args.image_id.startswith(
            "sha256:"
        )
        or SHA256_RE.fullmatch(
            args.image_id[7:]
        )
        is None
    ):
        raise RolloutError(
            "new_manager_image_identity_invalid"
        )

    document = {
        "schema": TRANSACTION_SCHEMA,
        "status": "CLAIMED",
        "authorization_id":
            args.authorization_id,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "claimed_at_unix": int(
            time.time()
        ),
        "baseline_sha256":
            args.baseline_sha256,
        "baseline": baseline["private"],
        "release_id": args.release_id,
        "release_sha256":
            args.release_sha256,
        "source_head": args.source_head,
        "new_image": args.new_image,
        "image_id": args.image_id,
        "manager_tar_sha256":
            args.manager_tar_sha256,
        "rootfs_layers_sha256":
            args.rootfs_layers_sha256,
        "config_contract_sha256":
            args.config_contract_sha256,
        "host_tool_sha256":
            args.host_tool_sha256,
        "remote_tool_sha256":
            args.remote_tool_sha256,
    }
    _atomic_private_json(
        TRANSACTION,
        document,
    )
    stage.mkdir(mode=0o700)
    metadata = stage.stat()
    if (
        metadata.st_uid != 0
        or stat.S_IMODE(
            metadata.st_mode
        )
        != 0o700
    ):
        raise RolloutError(
            "rollout_stage_metadata_invalid"
        )
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "claim",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "stage_path": str(stage),
        "baseline_sha256":
            args.baseline_sha256,
        "raw_locator_in_output": False,
        "board_access": False,
    }


def _transaction() -> dict[str, Any]:
    _require_regular(
        TRANSACTION,
        mode=0o600,
    )
    value = _read_json(TRANSACTION)
    if (
        value.get("schema")
        != TRANSACTION_SCHEMA
        or value.get(
            "authorization_claimed"
        )
        is not True
        or value.get(
            "authorization_consumed"
        )
        is not True
        or value.get(
            "replay_allowed"
        )
        is not False
    ):
        raise RolloutError(
            "rollout_transaction_invalid"
        )
    return value


def _advance(
    value: dict[str, Any],
    **fields: Any,
) -> dict[str, Any]:
    updated = dict(value)
    updated.update(fields)
    updated[
        "authorization_claimed"
    ] = True
    updated[
        "authorization_consumed"
    ] = True
    updated[
        "replay_allowed"
    ] = False
    _atomic_private_json(
        TRANSACTION,
        updated,
    )
    return updated


def _config_contract(
    config: Any,
) -> dict[str, Any]:
    value = (
        config
        if isinstance(config, dict)
        else {}
    )
    result: dict[str, Any] = {}
    sequence = {
        "Entrypoint",
        "Cmd",
        "Env",
    }
    strings = {
        "User",
        "WorkingDir",
        "StopSignal",
    }
    mappings = {
        "Labels",
        "Healthcheck",
        "Volumes",
        "ExposedPorts",
    }
    for key in CONFIG_KEYS:
        observed = value.get(key)
        if (
            key in sequence
            and observed is None
        ):
            observed = []
        elif (
            key in strings
            and observed is None
        ):
            observed = ""
        elif (
            key in mappings
            and observed is None
        ):
            observed = {}
        result[key] = observed
    return result


def _verify_loaded_image(
    transaction: dict[str, Any],
) -> None:
    document = _docker_inspect(
        transaction["new_image"]
    )
    if (
        document.get("Architecture")
        != "arm64"
        or document.get("Os") != "linux"
    ):
        raise RolloutError(
            "loaded_manager_platform_invalid"
        )
    rootfs = document.get("RootFS")
    layers = (
        rootfs.get("Layers")
        if isinstance(rootfs, dict)
        else None
    )
    if (
        not isinstance(layers, list)
        or not layers
        or _normalized_sha(layers)
        != transaction[
            "rootfs_layers_sha256"
        ]
    ):
        raise RolloutError(
            "loaded_manager_rootfs_invalid"
        )
    config_hash = _normalized_sha(
        _config_contract(
            document.get("Config")
        )
    )
    if (
        config_hash
        != transaction[
            "config_contract_sha256"
        ]
    ):
        raise RolloutError(
            "loaded_manager_config_invalid"
        )


def _compose_command(
    *arguments: str,
) -> tuple[str, ...]:
    return (
        "docker",
        "compose",
        "--env-file",
        str(COMPOSE_ENV),
        "-f",
        str(EXPECTED_COMPOSE),
        "--profile",
        "*",
        *arguments,
    )


def _wait_manager(
    expected_image: str,
    *,
    timeout: float = 45.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = "unknown"
    while time.monotonic() < deadline:
        try:
            current = _container_snapshot(
                "manager"
            )
            if (
                current["image_ref"]
                != expected_image
            ):
                raise RolloutError(
                    "manager_image_not_converged"
                )
            _pairing_status(
                current["id"]
            )
            _pairing_socket_absent(
                current["id"]
            )
            _probe_manager_tls(
                current["id"]
            )
            return current
        except RolloutError as error:
            last = str(error)
            time.sleep(0.5)
    raise RolloutError(
        "manager_runtime_convergence_timeout:"
        + _sha_text(last)
    )


def _recovery_capability(
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
        raise RolloutError(
            "manager_recovery_capability_unproven"
        )


def _continuity(
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    for service in (
        "broker",
        "homeassistant",
    ):
        for key in (
            "id",
            "image_id",
            "image_ref",
            "restart_count",
            "started_at",
        ):
            if (
                before["runtime"][service][key]
                != after["runtime"][service][key]
            ):
                raise RolloutError(
                    service
                    + "_continuity_changed"
                )
    if (
        before["manager_state"][
            "state_sha256"
        ]
        != after["manager_state"][
            "state_sha256"
        ]
        or before["security_counts"]
        != after["security_counts"]
        or before["manager_state"][
            "hardware_id_sha256"
        ]
        != after["manager_state"][
            "hardware_id_sha256"
        ]
        or before["manager_state"][
            "pairing_id_sha256"
        ]
        != after["manager_state"][
            "pairing_id_sha256"
        ]
    ):
        raise RolloutError(
            "manager_logical_state_changed"
        )


def _restore_env(
    baseline: dict[str, Any],
) -> dict[str, Any]:
    _require_regular(
        ENV_BACKUP,
        mode=0o600,
    )
    old_bytes = ENV_BACKUP.read_bytes()
    if (
        hashlib.sha256(
            old_bytes
        ).hexdigest()
        != baseline["compose"][
            "env_sha256"
        ]
    ):
        raise RolloutError(
            "rollback_env_backup_invalid"
        )
    _write_private_bytes(
        COMPOSE_ENV,
        old_bytes,
    )
    restored = _render_compose()
    image, normalized = (
        _normalized_compose(restored)
    )
    if (
        image
        != baseline["compose"][
            "manager_image"
        ]
        or normalized
        != baseline["compose"][
            "normalized_render_sha256"
        ]
    ):
        raise RolloutError(
            "rollback_compose_binding_invalid"
        )
    _run(
        _compose_command(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "manager",
        ),
        timeout=120,
    )
    manager = _wait_manager(image)
    after = _inspect_state()["private"]
    _continuity(
        baseline,
        after,
    )
    return manager


def commit() -> dict[str, Any]:
    _require_root()
    transaction = _transaction()
    if transaction.get("status") != "CLAIMED":
        raise RolloutError(
            "rollout_commit_state_invalid"
        )
    baseline = transaction["baseline"]
    current = _inspect_state()
    if (
        current["baseline_sha256"]
        != transaction[
            "baseline_sha256"
        ]
    ):
        _advance(
            transaction,
            status=(
                "STOPPED_PRECUTOVER_BASELINE_DRIFT"
            ),
            closed_at_unix=int(
                time.time()
            ),
        )
        raise RolloutError(
            "rollout_baseline_changed_after_claim"
        )

    stage = _stage_path(
        transaction[
            "authorization_id"
        ]
    )
    image_tar = (
        stage
        / "greenhouse-manager-arm64.tar"
    )
    try:
        _require_regular(image_tar)
        if (
            _sha_file(image_tar)
            != transaction[
                "manager_tar_sha256"
            ]
        ):
            raise RolloutError(
                "manager_tar_sha256_mismatch"
            )

        _run(
            (
                "docker",
                "load",
                "-i",
                str(image_tar),
            ),
            timeout=1800,
        )
        _verify_loaded_image(
            transaction
        )

        current = _inspect_state()
        if (
            current["baseline_sha256"]
            != transaction[
                "baseline_sha256"
            ]
        ):
            raise RolloutError(
                "rollout_baseline_changed_before_cutover"
            )

        old_env = COMPOSE_ENV.read_bytes()
        if (
            hashlib.sha256(
                old_env
            ).hexdigest()
            != baseline["compose"][
                "env_sha256"
            ]
        ):
            raise RolloutError(
                "compose_env_changed_before_cutover"
            )
        if (
            ENV_BACKUP.exists()
            or ENV_BACKUP.is_symlink()
        ):
            raise RolloutError(
                "rollout_env_backup_collision"
            )
        _write_private_bytes(
            ENV_BACKUP,
            old_env,
        )

        new_env = _replace_manager_image(
            old_env,
            transaction["new_image"],
        )
        transaction = _advance(
            transaction,
            status="CUTOVER_STARTED",
            env_switched=False,
        )
        _write_private_bytes(
            COMPOSE_ENV,
            new_env,
        )
        transaction = _advance(
            transaction,
            status="CUTOVER_STARTED",
            env_switched=True,
        )
        rendered = _render_compose()
        image, normalized = (
            _normalized_compose(rendered)
        )
        if (
            image
            != transaction["new_image"]
            or normalized
            != baseline["compose"][
                "normalized_render_sha256"
            ]
        ):
            raise RolloutError(
                "rollout_compose_delta_invalid"
            )

        _run(
            _compose_command(
                "up",
                "-d",
                "--no-deps",
                "--force-recreate",
                "manager",
            ),
            timeout=120,
        )
        manager = _wait_manager(
            transaction["new_image"]
        )
        _recovery_capability(
            manager["id"]
        )
        after = _inspect_state()[
            "private"
        ]
        _continuity(
            baseline,
            after,
        )
        if (
            after["compose"][
                "manager_image"
            ]
            != transaction[
                "new_image"
            ]
            or after["manager_state"][
                "state_sha256"
            ]
            != baseline[
                "manager_state"
            ]["state_sha256"]
        ):
            raise RolloutError(
                "rollout_postcheck_invalid"
            )

        transaction = _advance(
            transaction,
            status="CLOSED_PASS",
            closed_at_unix=int(
                time.time()
            ),
            new_manager_container_id_sha256=(
                after["runtime"][
                    "manager"
                ]["id_sha256"]
            ),
            broker_continuity=True,
            homeassistant_continuity=True,
            manager_state_unchanged=True,
            pairing_exposure_closed=True,
            recovery_capability_present=True,
        )
        cleanup_complete = True
        try:
            if ENV_BACKUP.exists():
                ENV_BACKUP.unlink()
            shutil.rmtree(stage)
        except OSError:
            cleanup_complete = False
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "commit",
            "transaction_state":
                transaction["status"],
            "authorization_consumed": True,
            "replay_allowed": False,
            "new_manager_container_id_sha256":
                transaction[
                    "new_manager_container_id_sha256"
                ],
            "broker_continuity": True,
            "homeassistant_continuity": True,
            "manager_state_unchanged": True,
            "pairing_window_state":
                "CLOSED",
            "recovery_capability_present":
                True,
            "cleanup_complete":
                cleanup_complete,
            "raw_locator_in_output": False,
            "board_access": False,
        }
    except Exception as error:
        active = _transaction()
        if active.get(
            "status"
        ) == "CUTOVER_STARTED":
            try:
                restored = _restore_env(
                    baseline
                )
                _advance(
                    active,
                    status=(
                        "ROLLED_BACK_FAILURE"
                    ),
                    closed_at_unix=int(
                        time.time()
                    ),
                    failure_type=(
                        type(error).__name__
                    ),
                    rollback_manager_id_sha256=(
                        restored[
                            "id_sha256"
                        ]
                    ),
                    rollback_proven=True,
                )
            except Exception as rollback_error:
                _advance(
                    active,
                    status=(
                        "STOPPED_ROLLBACK_UNPROVEN"
                    ),
                    closed_at_unix=int(
                        time.time()
                    ),
                    failure_type=(
                        type(error).__name__
                    ),
                    rollback_failure_type=(
                        type(
                            rollback_error
                        ).__name__
                    ),
                    rollback_proven=False,
                )
                raise RolloutError(
                    "rollout_failure_rollback_unproven"
                ) from rollback_error
            raise RolloutError(
                "rollout_failure_rolled_back"
            ) from error

        _advance(
            active,
            status="STOPPED_PRECUTOVER_FAILED",
            closed_at_unix=int(
                time.time()
            ),
            failure_type=(
                type(error).__name__
            ),
        )
        shutil.rmtree(
            stage,
            ignore_errors=True,
        )
        raise


def transaction_status() -> dict[str, Any]:
    _require_root()
    if not TRANSACTION.exists():
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "status",
            "transaction_present": False,
            "transaction_state": "ABSENT",
            "authorization_consumed": False,
            "replay_allowed": None,
            "raw_locator_in_output": False,
            "board_access": False,
        }
    value = _transaction()
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "operation": "status",
        "transaction_present": True,
        "transaction_state": str(
            value.get("status", "UNKNOWN")
        ),
        "authorization_consumed": True,
        "replay_allowed": False,
        "raw_locator_in_output": False,
        "board_access": False,
    }


def abort(reason_sha256: str) -> dict[str, Any]:
    _require_root()
    _validate_sha(
        reason_sha256,
        "reason_sha256",
    )
    transaction = _transaction()
    if transaction.get("status") != "CLAIMED":
        raise RolloutError(
            "rollout_abort_state_invalid"
        )
    stage = _stage_path(
        transaction[
            "authorization_id"
        ]
    )
    shutil.rmtree(
        stage,
        ignore_errors=True,
    )
    _advance(
        transaction,
        status="STOPPED_TRANSFER_FAILED",
        closed_at_unix=int(
            time.time()
        ),
        failure_detail_sha256=reason_sha256,
    )
    return {
        "schema": SCHEMA,
        "status": "STOP",
        "operation": "abort",
        "transaction_state": "STOPPED_TRANSFER_FAILED",
        "authorization_consumed": True,
        "replay_allowed": False,
        "raw_locator_in_output": False,
        "board_access": False,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(
        dest="command",
        required=True,
    )
    commands.add_parser("inspect")

    claim_command = commands.add_parser(
        "claim"
    )
    claim_command.add_argument(
        "--authorization-id",
        required=True,
    )
    claim_command.add_argument(
        "--baseline-sha256",
        required=True,
    )
    claim_command.add_argument(
        "--release-id",
        required=True,
    )
    claim_command.add_argument(
        "--release-sha256",
        required=True,
    )
    claim_command.add_argument(
        "--source-head",
        required=True,
    )
    claim_command.add_argument(
        "--new-image",
        required=True,
    )
    claim_command.add_argument(
        "--image-id",
        required=True,
    )
    claim_command.add_argument(
        "--manager-tar-sha256",
        required=True,
    )
    claim_command.add_argument(
        "--rootfs-layers-sha256",
        required=True,
    )
    claim_command.add_argument(
        "--config-contract-sha256",
        required=True,
    )
    claim_command.add_argument(
        "--host-tool-sha256",
        required=True,
    )
    claim_command.add_argument(
        "--remote-tool-sha256",
        required=True,
    )

    commands.add_parser("commit")
    commands.add_parser("status")
    abort_command = commands.add_parser(
        "abort"
    )
    abort_command.add_argument(
        "--reason-sha256",
        required=True,
    )
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "inspect":
            report = _public_inspect(
                _inspect_state()
            )
        elif args.command == "claim":
            report = claim(args)
        elif args.command == "commit":
            report = commit()
        elif args.command == "status":
            report = transaction_status()
        else:
            report = abort(
                args.reason_sha256
            )
    except (
        OSError,
        RolloutError,
        RuntimeError,
        sqlite3.Error,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error": str(error),
                    "raw_locator_in_output": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(
        json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
