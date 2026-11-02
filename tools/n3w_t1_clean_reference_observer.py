#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import socket
import sqlite3
import stat
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w-t1-clean-reference-observation/1"
PRODUCT_SOURCE_HEAD = "24382caae4a1f5d459297f86e8d18f10a848ca64"
R2A_CONTROL_HEAD = "abeb6c31147bcf249361dcec7e9536eaed6106a6"
R2B_CONTROL_HEAD = "e15c64ac8f0f5f482a6c8538072031734002a559"

R2A_TRANSACTION = Path("/var/lib/n3w-t1-clean-reference-r2a/transaction.json")
R2B_TRANSACTION = Path("/var/lib/n3w-t1-clean-reference-r2b/transaction.json")
RELEASE = Path("/opt/HomeAssistant/infra/n3w-t1/production/fresh-release.json")
COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")

EXPECTED_SERVICES = ("broker", "homeassistant", "manager")

CONFIG_FILES = (
    Path("/etc/n3wfc4/docker-compose.yml"),
    Path("/opt/HomeAssistant/infra/n3w-t1/broker/mosquitto.conf"),
    Path("/opt/HomeAssistant/infra/n3w-t1/production/homeassistant-configuration.yaml"),
)

UNIT_FILES = (
    Path("/etc/systemd/system/n3wfc4-provision-resume.service"),
    Path("/etc/systemd/system/n3wfc4-broker-ingress-guard.service"),
    Path("/etc/systemd/system/n3wfc4-registration-ingress-guard.service"),
    Path("/etc/systemd/system/n3wfc4-broker-activation.service"),
    Path("/etc/systemd/system/n3wfc4-services-activation.service"),
    Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service"),
    Path("/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer"),
)

PERSISTENT_DIRS = (
    Path("/var/lib/greenhouse-manager/manager"),
    Path("/var/lib/greenhouse-manager/n3w"),
    Path("/var/lib/n3wfc4-broker"),
    Path("/var/lib/n3wfc4-homeassistant"),
)

SQLITE_DATABASES = (
    Path("/var/lib/greenhouse-manager/manager/manager-state.sqlite3"),
    Path("/var/lib/greenhouse-manager/n3w/replay.sqlite3"),
    Path("/var/lib/greenhouse-manager/n3w/relay-authorization.sqlite3"),
)

PUBLIC_CERTIFICATES = (
    Path("/etc/n3wfc4/tls/ca.pem"),
    Path("/etc/n3wfc4/tls/server.pem"),
    Path("/var/lib/greenhouse-manager/identity/system-ca.pem"),
)

CUSTOM_COMPONENT = Path(
    "/opt/HomeAssistant/infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap"
)

DYNSEC = Path("/var/lib/n3wfc4-broker/dynamic-security.json")
HA_STORAGE = Path("/var/lib/n3wfc4-homeassistant/.storage")

BROKER_UNIT = "n3wfc4-broker-activation.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
CERT_SERVICE = "n3wfc4-broker-certificate-lifecycle.service"
CERT_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"
PROVISION_UNIT = "n3wfc4-provision-resume.service"
GUARD_UNIT = "n3wfc4-broker-ingress-guard.service"
REGISTRATION_GUARD_UNIT = "n3wfc4-registration-ingress-guard.service"

SOCKET_SCRIPT = r"""
import glob, json, os, socket, struct, sys
port = int(sys.argv[1])
rows = {}
for path, family in (("/proc/net/tcp", socket.AF_INET), ("/proc/net/tcp6", socket.AF_INET6)):
    try:
        lines = open(path, encoding="ascii").read().splitlines()[1:]
    except OSError:
        continue
    for row in lines:
        fields = row.split()
        if len(fields) < 10 or fields[3] != "01":
            continue
        try:
            remote_port = int(fields[2].split(":")[1], 16)
        except (IndexError, ValueError):
            continue
        if remote_port == port:
            rows[fields[9]] = fields[1:4]
owned = set()
for fd in glob.glob("/proc/[0-9]*/fd/*"):
    try:
        link = os.readlink(fd)
        inode = link[8:-1] if link.startswith("socket:[") else ""
        if inode not in rows:
            continue
        pid = fd.split("/")[2]
        start = open("/proc/" + pid + "/stat", encoding="ascii").read().rsplit(")", 1)[1].split()[19]
        owned.add((inode, pid, start, *rows[inode]))
    except (OSError, IndexError):
        continue
print(json.dumps({
    "count": len({row[0] for row in owned}),
    "fingerprint": __import__("hashlib").sha256(
        json.dumps(sorted(owned), separators=(",", ":")).encode()
    ).hexdigest(),
}, sort_keys=True))
"""


class ObservationError(RuntimeError):
    pass


def _run(
    argv: tuple[str, ...],
    *,
    timeout: float = 60.0,
    allowed: frozenset[int] = frozenset({0}),
) -> str:
    completed = subprocess.run(
        argv,
        check=False,
        text=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode not in allowed:
        reason = completed.stderr.strip() or completed.stdout.strip()
        raise ObservationError(
            f"command_failed:{Path(argv[0]).name}:{completed.returncode}:{reason[:240]}"
        )
    return completed.stdout


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ObservationError(f"file_invalid:{path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_file(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ObservationError(f"json_invalid:{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ObservationError(f"json_invalid:{path}") from error
    if not isinstance(value, dict):
        raise ObservationError(f"json_document_invalid:{path}")
    return value


def _path_metadata(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.exists():
        raise ObservationError(f"path_invalid:{path}")
    item = path.stat()
    return {
        "uid": item.st_uid,
        "gid": item.st_gid,
        "mode": format(stat.S_IMODE(item.st_mode), "04o"),
        "type": "directory" if path.is_dir() else "file",
    }


def _tree_hash(root: Path) -> str:
    if root.is_symlink() or not root.is_dir():
        raise ObservationError(f"tree_invalid:{root}")
    rows: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ObservationError(f"tree_symlink_forbidden:{path}")
        if path.is_file():
            rows.append((path.relative_to(root).as_posix(), _sha256_file(path)))
    return _canonical_sha(rows)


def _tree_stats(root: Path) -> dict[str, int]:
    if root.is_symlink() or not root.is_dir():
        raise ObservationError(f"tree_invalid:{root}")
    files = 0
    directories = 1
    total_bytes = 0
    symlinks = 0
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(current)
        for name in list(dirnames):
            path = base / name
            if path.is_symlink():
                symlinks += 1
                dirnames.remove(name)
            else:
                directories += 1
        for name in filenames:
            path = base / name
            if path.is_symlink():
                symlinks += 1
                continue
            try:
                item = path.stat()
            except OSError:
                continue
            if stat.S_ISREG(item.st_mode):
                files += 1
                total_bytes += item.st_size
    return {
        "file_count": files,
        "directory_count": directories,
        "total_bytes": total_bytes,
        "symlink_count": symlinks,
    }


def _sqlite_snapshot(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ObservationError(f"sqlite_invalid:{path}")
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=5,
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if quick is None or quick[0] != "ok":
            raise ObservationError(f"sqlite_quick_check_failed:{path.name}")
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        records = [
            (str(row[0]), str(row[1] or ""))
            for row in connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts: dict[str, int] = {}
        for table, _sql in records:
            safe = table.replace('"', '""')
            counts[table] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{safe}"').fetchone()[0]
            )
        return {
            "quick_check": "ok",
            "user_version": user_version,
            "schema_sha256": _canonical_sha(records),
            "table_count": len(records),
            "row_counts": counts,
            "file_bytes": path.stat().st_size,
            "wal_bytes": (
                Path(str(path) + "-wal").stat().st_size
                if Path(str(path) + "-wal").is_file()
                else 0
            ),
        }
    finally:
        connection.close()


def _ha_storage_count(filename: str, key: str) -> dict[str, Any]:
    path = HA_STORAGE / filename
    if not path.exists():
        return {"present": False, "count": 0, "version": None}
    document = _json_file(path)
    data = document.get("data")
    if not isinstance(data, dict):
        raise ObservationError(f"ha_storage_data_invalid:{filename}")
    collection = data.get(key, [])
    if not isinstance(collection, list):
        raise ObservationError(f"ha_storage_collection_invalid:{filename}")
    return {
        "present": True,
        "count": len(collection),
        "version": document.get("version"),
    }


def _dynsec_snapshot() -> dict[str, Any]:
    document = _json_file(DYNSEC)
    result: dict[str, Any] = {
        "top_level_keys_sha256": _canonical_sha(sorted(document)),
    }
    for key in ("clients", "groups", "roles"):
        value = document.get(key, [])
        if isinstance(value, list):
            result[f"{key}_count"] = len(value)
        elif isinstance(value, dict):
            result[f"{key}_count"] = len(value)
        else:
            raise ObservationError(f"dynsec_collection_invalid:{key}")
    return result


def _container(service: str) -> dict[str, Any]:
    output = _run(
        (
            "docker",
            "ps",
            "--filter",
            "label=com.docker.compose.project=n3wfc4",
            "--filter",
            f"label=com.docker.compose.service={service}",
            "--format",
            "{{.ID}}",
        ),
        timeout=30,
    )
    ids = [line.strip() for line in output.splitlines() if line.strip()]
    if len(ids) != 1:
        raise ObservationError(f"service_container_not_unique:{service}")
    try:
        records = json.loads(_run(("docker", "inspect", ids[0]), timeout=30))
    except json.JSONDecodeError as error:
        raise ObservationError(f"container_inspect_invalid:{service}") from error
    if not isinstance(records, list) or len(records) != 1:
        raise ObservationError(f"container_inspect_invalid:{service}")
    item = records[0]
    state = item.get("State")
    config = item.get("Config")
    host = item.get("HostConfig")
    mounts = item.get("Mounts")
    if not all(isinstance(value, dict) for value in (state, config, host)):
        raise ObservationError(f"container_contract_invalid:{service}")
    if not isinstance(mounts, list):
        raise ObservationError(f"container_mounts_invalid:{service}")
    if state.get("Running") is not True:
        raise ObservationError(f"service_not_running:{service}")
    mount_contract = sorted(
        (
            {
                "type": row.get("Type"),
                "source": row.get("Source"),
                "destination": row.get("Destination"),
                "rw": row.get("RW"),
            }
            for row in mounts
            if isinstance(row, dict)
        ),
        key=lambda row: (
            str(row.get("destination")),
            str(row.get("type")),
            str(row.get("source")),
            str(row.get("rw")),
        ),
    )
    port_bindings = host.get("PortBindings") or {}
    stable_contract = {
        "image": config.get("Image"),
        "user": config.get("User"),
        "network_mode": host.get("NetworkMode"),
        "readonly_rootfs": host.get("ReadonlyRootfs"),
        "restart_policy": host.get("RestartPolicy"),
        "cap_drop": sorted(host.get("CapDrop") or []),
        "security_opt": sorted(host.get("SecurityOpt") or []),
        "mounts": mount_contract,
        "port_bindings": port_bindings,
    }
    image = str(config.get("Image") or "")
    if not image:
        raise ObservationError(f"container_image_missing:{service}")
    try:
        image_records = json.loads(_run(("docker", "image", "inspect", image), timeout=30))
    except json.JSONDecodeError as error:
        raise ObservationError(f"image_inspect_invalid:{service}") from error
    if not isinstance(image_records, list) or len(image_records) != 1:
        raise ObservationError(f"image_inspect_invalid:{service}")
    image_item = image_records[0]
    return {
        "stable": {
            "image": image,
            "platform": f"{image_item.get('Os')}/{image_item.get('Architecture')}",
            "runtime_contract_sha256": _canonical_sha(stable_contract),
        },
        "runtime": {
            "container_id_sha256": hashlib.sha256(
                str(item.get("Id") or "").encode()
            ).hexdigest(),
            "started_at": state.get("StartedAt"),
            "restart_count": item.get("RestartCount"),
        },
        "_id": str(item.get("Id") or ""),
    }


def _service_socket(container_id: str, port: int) -> dict[str, Any]:
    try:
        result = json.loads(
            _run(
                (
                    "docker",
                    "exec",
                    container_id,
                    "python3",
                    "-c",
                    SOCKET_SCRIPT,
                    str(port),
                ),
                timeout=20,
            )
        )
    except json.JSONDecodeError as error:
        raise ObservationError("socket_probe_invalid") from error
    count = result.get("count")
    fingerprint = result.get("fingerprint")
    if (
        type(count) is not int
        or count < 0
        or not isinstance(fingerprint, str)
        or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
    ):
        raise ObservationError("socket_probe_invalid")
    return {"count": count, "fingerprint": fingerprint}


def _broker_current_auth(
    broker_id: str,
    broker_started_at: str,
    service: str,
) -> dict[str, Any]:
    identity = _json_file(
        Path("/opt/greenhouse-secrets/mqtt") / service / "identity.json"
    )
    client_id = identity.get("client_id")
    username = identity.get("username")
    if not all(
        isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]+", value)
        for value in (client_id, username)
    ):
        raise ObservationError(f"runtime_identity_invalid:{service}")
    logs = _run(
        (
            "docker",
            "logs",
            "--timestamps",
            "--since",
            broker_started_at,
            "--tail",
            "10000",
            broker_id,
        ),
        timeout=30,
    )
    lines = logs.splitlines()
    if len(lines) >= 10000:
        raise ObservationError("broker_log_coverage_insufficient")
    connected = re.compile(
        r"New client connected from .+ as "
        + re.escape(client_id)
        + r" \(p5, c[01], k[0-9]+, u'"
        + re.escape(username)
        + r"'\)\."
    )
    any_connection = re.compile(
        r"New client connected from .+ as "
        + re.escape(client_id)
        + r" \("
    )
    terminal = re.compile(
        r"(?:Client|client) "
        + re.escape(client_id)
        + r"(?: \[[^\]\r\n]+\] disconnected(?:\.|:)"
        + r"| disconnected\b| closed its connection\b"
        + r"| already connected, closing old connection\b"
        + r"| has exceeded timeout, disconnecting\b)"
    )
    current = False
    auth_event_count = 0
    for line in lines:
        if any_connection.search(line):
            if connected.search(line) is None:
                raise ObservationError(
                    f"broker_authenticated_identity_mismatch:{service}"
                )
            current = True
            auth_event_count += 1
            continue
        if terminal.search(line):
            current = False
    if not current:
        raise ObservationError(f"broker_current_session_not_authenticated:{service}")
    return {
        "current_authenticated": True,
        "identity_sha256": _canonical_sha([username, client_id]),
        "authenticated_event_count": auth_event_count,
    }


def _ha_http_status() -> int:
    connection = http.client.HTTPConnection("127.0.0.1", 8123, timeout=5)
    try:
        connection.request("GET", "/api/")
        response = connection.getresponse()
        response.read(1024)
        if response.status not in {200, 401}:
            raise ObservationError(
                f"homeassistant_http_status_invalid:{response.status}"
            )
        return int(response.status)
    finally:
        connection.close()


def _unit_state(unit: str) -> dict[str, str]:
    active = _run(
        ("systemctl", "is-active", unit),
        timeout=15,
        allowed=frozenset({0, 3, 4}),
    ).strip() or "unknown"
    enabled = _run(
        ("systemctl", "is-enabled", unit),
        timeout=15,
        allowed=frozenset({0, 1, 3, 4}),
    ).strip() or "unknown"
    return {"active": active, "enabled": enabled}


def _validate_authorities() -> dict[str, str]:
    release = _json_file(RELEASE)
    if (
        release.get("schema") != "gh.n3w-t1-fresh-release/1"
        or release.get("source_head") != PRODUCT_SOURCE_HEAD
    ):
        raise ObservationError("release_authority_invalid")
    r2a = _json_file(R2A_TRANSACTION)
    if (
        r2a.get("schema") != "gh.n3w-t1-clean-reference-r2a-transaction/1"
        or r2a.get("stage") != "RUNTIME_STARTED"
        or r2a.get("control_plane_head") != R2A_CONTROL_HEAD
        or r2a.get("authorization_consumed") is not True
        or r2a.get("authorization_replay_allowed") is not False
    ):
        raise ObservationError("r2a_authority_invalid")
    r2b = _json_file(R2B_TRANSACTION)
    if (
        r2b.get("schema") != "gh.n3w-t1-clean-reference-r2b-transaction/1"
        or r2b.get("stage") != "REBOOT_ACCEPTED"
        or r2b.get("control_plane_head") != R2B_CONTROL_HEAD
        or r2b.get("authorization_consumed") is not True
        or r2b.get("authorization_replay_allowed") is not False
        or r2b.get("reboot_acceptance_passed") is not True
    ):
        raise ObservationError("r2b_authority_invalid")
    return {
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "r2a_control_head": R2A_CONTROL_HEAD,
        "r2b_control_head": R2B_CONTROL_HEAD,
        "r2a_transaction_sha256": _sha256_file(R2A_TRANSACTION),
        "r2b_transaction_sha256": _sha256_file(R2B_TRANSACTION),
    }


def collect(reference_label: str) -> dict[str, Any]:
    if reference_label not in {"R2", "R3"}:
        raise ObservationError("reference_label_invalid")
    authorities = _validate_authorities()

    project_services = frozenset(
        line.strip()
        for line in _run(
            (
                "docker",
                "compose",
                "--project-name",
                "n3wfc4",
                "--env-file",
                str(COMPOSE_ENV),
                "-f",
                str(COMPOSE),
                "--profile",
                "application",
                "ps",
                "--status",
                "running",
                "--services",
            ),
            timeout=30,
        ).splitlines()
        if line.strip()
    )
    if project_services != frozenset(EXPECTED_SERVICES):
        raise ObservationError("runtime_service_set_invalid")

    containers = {name: _container(name) for name in EXPECTED_SERVICES}
    broker_id = containers["broker"]["_id"]
    broker_started_at = str(
        json.loads(_run(("docker", "inspect", broker_id), timeout=30))[0]["State"]["StartedAt"]
    )

    manager_socket = _service_socket(containers["manager"]["_id"], 8883)
    ha_socket = _service_socket(containers["homeassistant"]["_id"], 1883)
    if manager_socket["count"] != 1:
        raise ObservationError("manager_mqtt_socket_count_invalid")
    if ha_socket["count"] < 1:
        raise ObservationError("homeassistant_mqtt_socket_missing")

    manager_auth = _broker_current_auth(
        broker_id, broker_started_at, "manager"
    )
    ha_auth = _broker_current_auth(
        broker_id, broker_started_at, "homeassistant"
    )

    system_state = _run(
        ("systemctl", "is-system-running"),
        timeout=15,
        allowed=frozenset({0, 1}),
    ).strip()
    failed_text = _run(
        ("systemctl", "--failed", "--no-legend", "--plain"),
        timeout=20,
    ).strip()
    failed_units = [
        line.split()[0]
        for line in failed_text.splitlines()
        if line.strip()
    ]

    units = {
        unit: _unit_state(unit)
        for unit in (
            PROVISION_UNIT,
            GUARD_UNIT,
            REGISTRATION_GUARD_UNIT,
            BROKER_UNIT,
            SERVICES_UNIT,
            CERT_SERVICE,
            CERT_TIMER,
        )
    }

    for unit in (
        PROVISION_UNIT,
        GUARD_UNIT,
        REGISTRATION_GUARD_UNIT,
        BROKER_UNIT,
        SERVICES_UNIT,
        CERT_TIMER,
    ):
        if units[unit] != {"active": "active", "enabled": "enabled"}:
            raise ObservationError(f"unit_health_invalid:{unit}")
    if units[CERT_SERVICE]["active"] != "inactive":
        raise ObservationError("certificate_service_not_quiescent")

    config_hashes = {
        str(path): _sha256_file(path)
        for path in CONFIG_FILES
    }
    unit_hashes = {
        str(path): _sha256_file(path)
        for path in UNIT_FILES
    }
    cert_hashes = {
        str(path): _sha256_file(path)
        for path in PUBLIC_CERTIFICATES
    }
    persistent_metadata = {
        str(path): _path_metadata(path)
        for path in PERSISTENT_DIRS
    }

    sqlite = {
        str(path): _sqlite_snapshot(path)
        for path in SQLITE_DATABASES
    }
    sqlite_stable = {
        path: {
            "quick_check": value["quick_check"],
            "user_version": value["user_version"],
            "schema_sha256": value["schema_sha256"],
            "table_count": value["table_count"],
        }
        for path, value in sqlite.items()
    }
    sqlite_runtime = {
        path: {
            "row_counts": value["row_counts"],
            "file_bytes": value["file_bytes"],
            "wal_bytes": value["wal_bytes"],
        }
        for path, value in sqlite.items()
    }

    dynsec = _dynsec_snapshot()
    ha_entities = _ha_storage_count("core.entity_registry", "entities")
    ha_devices = _ha_storage_count("core.device_registry", "devices")
    ha_entries = _ha_storage_count("core.config_entries", "entries")

    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
        encoding="ascii"
    ).strip()
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        boot_id,
    ) is None:
        raise ObservationError("boot_id_invalid")

    stable_contracts = {
        "authority": authorities,
        "component_identity": {
            name: containers[name]["stable"]
            for name in EXPECTED_SERVICES
        },
        "fixed_config_sha256": config_hashes,
        "custom_component_tree_sha256": _tree_hash(CUSTOM_COMPONENT),
        "systemd_unit_sha256": unit_hashes,
        "persistent_path_metadata": persistent_metadata,
        "sqlite_schema": sqlite_stable,
        "public_certificate_sha256": cert_hashes,
        "dynsec_top_level_keys_sha256": dynsec["top_level_keys_sha256"],
    }

    health = {
        "system_state": system_state,
        "failed_unit_count": len(failed_units),
        "failed_units": failed_units,
        "systemd_units": units,
        "runtime_services": list(EXPECTED_SERVICES),
        "manager_current_authenticated": manager_auth["current_authenticated"],
        "homeassistant_current_authenticated": ha_auth["current_authenticated"],
        "manager_mqtt_socket_count": manager_socket["count"],
        "homeassistant_mqtt_socket_count": ha_socket["count"],
        "homeassistant_http_status": _ha_http_status(),
    }
    health["overall_pass"] = (
        system_state == "running"
        and not failed_units
        and health["manager_current_authenticated"] is True
        and health["homeassistant_current_authenticated"] is True
        and health["manager_mqtt_socket_count"] == 1
        and health["homeassistant_mqtt_socket_count"] >= 1
        and health["homeassistant_http_status"] in {200, 401}
    )
    if health["overall_pass"] is not True:
        raise ObservationError("runtime_health_not_pass")

    runtime_observations = {
        "boot_id_sha256": hashlib.sha256(boot_id.encode()).hexdigest(),
        "containers": {
            name: containers[name]["runtime"]
            for name in EXPECTED_SERVICES
        },
        "mqtt_session": {
            "manager": {
                **manager_socket,
                "authenticated_event_count": manager_auth[
                    "authenticated_event_count"
                ],
                "identity_sha256": manager_auth["identity_sha256"],
            },
            "homeassistant": {
                **ha_socket,
                "authenticated_event_count": ha_auth[
                    "authenticated_event_count"
                ],
                "identity_sha256": ha_auth["identity_sha256"],
            },
        },
        "sqlite": sqlite_runtime,
        "persistent_tree_stats": {
            str(path): _tree_stats(path)
            for path in PERSISTENT_DIRS
        },
        "dynsec_counts": {
            "clients": dynsec["clients_count"],
            "groups": dynsec["groups_count"],
            "roles": dynsec["roles_count"],
        },
        "homeassistant_registry_counts": {
            "entities": ha_entities,
            "devices": ha_devices,
            "config_entries": ha_entries,
        },
    }

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "reference_label": reference_label,
        "stable_contracts": stable_contracts,
        "health": health,
        "runtime_observations": runtime_observations,
        "read_only": True,
        "network_mutation": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-label", choices=("R2", "R3"), required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = collect(args.reference_label)
    except (
        ObservationError,
        OSError,
        sqlite3.Error,
        subprocess.SubprocessError,
        ValueError,
        KeyError,
        TypeError,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:300],
                    "read_only": True,
                    "network_mutation": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
