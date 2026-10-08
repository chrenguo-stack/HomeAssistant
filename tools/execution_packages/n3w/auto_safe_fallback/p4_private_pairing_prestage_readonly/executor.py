from __future__ import annotations

import base64
import getpass
import hashlib
import ipaddress
import json
import os
import secrets
import socket
import subprocess
import sys
import uuid
from pathlib import Path

GATE = "N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_PAIRING_IPC_AND_SNAPSHOT_READONLY_PRESTAGE_20261008_01"
EXPECTED_TARGET_SHA = "2b149655aab07a3941fa76d0fd03e6b632e628077d5cddcf4eafa0e2c9e313fd"
CURRENT_CLEAN_CANDIDATE_SHA = "4b004ce3931dda3dda770c1ecfc9b0d4b7a88377d2c4f876185b82c056a2a4cc"

PREVIOUS_MANAGER_CONTAINER_ID_SHA = "7b3c2a4de642e8a57da9d3f1652c9c35a27533c16f056736ecc89e289463bccc"
PREVIOUS_BROKER_CONTAINER_ID_SHA = "54a343cf903f5c73fd5b646c233e59cf0313b25d3f2caa55061fc64bc30741cd"
PREVIOUS_SNAPSHOT_SHA = "81a4601421d0f85a6295a8d901fa91692e61c27306c36bc673796f856bbd1e0c"
EXPECTED_MANAGER_STARTED_AT = "2026-10-06T15:08:36.478286093Z"
EXPECTED_BROKER_STARTED_AT = "2026-10-06T05:01:47.110364692Z"
EXPECTED_T1_ADDRESS_SHA256 = "6257bd5c713a053e9efa4c9b036119a068dba2ddb8145e8288e89ad470822338"
EXPECTED_TLS_BINDING_SHA256 = "aae921c576258b264b60658bac022d5bcf81c3a3f641c50ba422df271f7a0947"
EXPECTED_TLS_CA_SHA256 = "11ff133cdab8bf5f3093f6b488f8fa7e2579a1b5e383d066b1a1da56ad5dae9f"
EXPECTED_TLS_LEAF_SHA256 = "8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb"
EXPECTED_PREBOOT_IDENTITY_COUNT = 5


class StopExecution(RuntimeError):
    pass


def sha_text(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def finish(payload: dict[str, object], code: int = 0) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


def main() -> int:
    out: dict[str, object] = {
        "P4_PRIVATE_PRESTAGE_PASS": False,
        "MANAGER_PAIRING_CLI_PRESENT": False,
        "MANAGER_PAIRING_UDS_SECURE": False,
        "MANAGER_PAIRING_TTL_POLICY_PASS": False,
        "PREBOOT_SNAPSHOT_PRIVATE_FILE_PASS": False,
        "P4_FIRST_NORMAL_BOOT_AUTHORIZATION_GRANTED": False,
        "P4_SETUP_SECRET_IMPORT_AUTHORIZATION_GRANTED": False,
        "P4_SETUP_SECRET_IMPORTED": False,
        "P4_PRODUCT_NORMAL_BOOT_STARTED": False,
        "STAGE": "P4_PRIVATE_PAIRING_IPC_AND_SNAPSHOT_READONLY_PRESTAGE",
        "AUTHORIZATION_GRANTED": True,
        "AUTHORIZATION_CLAIMED": False,
        "AUTHORIZATION_CONSUMED": False,
        "PREDECESSOR_AUTHORIZATION_REPLAY": False,
        "CURRENT_CLEAN_CANDIDATE_SILICON_BINDING_SHA256": CURRENT_CLEAN_CANDIDATE_SHA,
        "T1_ACCESSED": False,
        "DOCKER_CLI_PRESENT": False,
        "DOCKER_DAEMON_ACCESSIBLE": False,
        "MANAGER_CONTAINER_RUNNING": False,
        "BROKER_CONTAINER_RUNNING": False,
        "BROKER_RUNTIME_BINDING_UNIQUE": False,
        "PAIRING_ADVERTISED_HOST_MODE_AUTO": False,
        "REAL_T1_ADDRESS_MATCH": False,
        "NODE_CREDENTIAL_BROKER_HOST_MATCH": False,
        "MANAGER_HOST_NETWORK": False,
        "MANAGER_PORTS_EMPTY": False,
        "UDP_47111_LISTENING": False,
        "TCP_47112_LISTENING": False,
        "TCP_8883_LISTENING": False,
        "BROKER_TCP_TLS_A_8883": False,
        "DB_MOUNT_RESOLUTION_PASS": False,
        "IDENTITY_SNAPSHOT_STABLE": False,
        "MANAGER_PREBOOT_SNAPSHOT_CREATED": False,
        "P4_PREBOOT_READONLY_BASELINE_PASS": False,
        "EXTERNAL_DISCOVERY_ATTEMPTED": False,
        "EXTERNAL_DISCOVERY_PASS": False,
        "MANAGER_DISCOVERY_AUTO_SOURCE_A": False,
        "P4_PREBOOT_PASS": False,
        "READY_FOR_P4_AUTHORIZATION": False,
        "P4_AUTHORIZATION_GRANTED": False,
        "P4_AUTHORIZATION_CLAIMED": False,
        "P4_AUTHORIZATION_CONSUMED": False,
        "BOARD_ACCESS": False,
        "BOARD_WRITE": False,
        "PRODUCT_FIRMWARE_NORMAL_BOOT_STARTED_BY_THIS_GATE": False,
        "P4_FIRST_NORMAL_BOOT_EXECUTED": False,
        "P3_WRITE_ONLY_OFFLINE_R2_CLOSED_PASS": True,
        "P4_FIRST_BOOT_AUTHORIZATION_GRANTED": False,
        "MANAGER_BROKER_PREBOOT_CONTINUITY_PASS": False,
        "T1_CONFIGURATION_MUTATION": False,
        "MANAGER_DB_WRITE": False,
        "MANAGER_REPLAY_MUTATION": False,
        "MANAGER_HIGH_WATER_CLEAR": False,
        "MANAGER_RESTART": False,
        "BROKER_RESTART": False,
        "AUTO_RETRY": False,
        "AUTO_P4": False,
        "STOP": True,
    }

    target = getpass.getpass("请输入此前验证成功的 root@T1地址：").strip()

    try:
        user, host = target.split("@", 1)
        address = ipaddress.IPv4Address(host)
    except ValueError:
        out["ERROR"] = "INVALID_TARGET"
        return finish(out, 2)

    if user != "root" or not address.is_private or address.is_loopback:
        out["ERROR"] = "TARGET_NOT_ALLOWED"
        return finish(out, 2)

    if sha_text(target) != EXPECTED_TARGET_SHA:
        out["ERROR"] = "TARGET_CHANGED"
        return finish(out, 2)

    frozen_snapshot = (
        Path.home()
        / "N3W_PRIVATE_EVIDENCE"
        / "N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PREBOOT_RUNTIME_CONTINUITY_READONLY_20261008_01"
        / "manager_preboot_identity_snapshot.json"
    )
    try:
        info = frozen_snapshot.lstat()
        import stat
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("PRIVATE_SNAPSHOT_MODE_UNSAFE")
        if info.st_uid != os.getuid():
            raise ValueError("PRIVATE_SNAPSHOT_OWNER_MISMATCH")
        if frozen_snapshot.parent.is_symlink() or frozen_snapshot.is_symlink():
            raise ValueError("PRIVATE_SNAPSHOT_SYMLINK")
        snapshot_content = frozen_snapshot.read_bytes()
        if hashlib.sha256(snapshot_content).hexdigest() != PREVIOUS_SNAPSHOT_SHA:
            raise ValueError("PRIVATE_PREBOOT_SNAPSHOT_HASH_MISMATCH")
        snapshot_doc = json.loads(snapshot_content)
        if (
            snapshot_doc.get("schema") != "n3w.kf050.runtime-identity-snapshot/1"
            or snapshot_doc.get("hardware_id_count") != EXPECTED_PREBOOT_IDENTITY_COUNT
            or len(snapshot_doc.get("hardware_id_sha256", [])) != EXPECTED_PREBOOT_IDENTITY_COUNT
            or len(set(snapshot_doc.get("hardware_id_sha256", []))) != EXPECTED_PREBOOT_IDENTITY_COUNT
        ):
            raise ValueError("PRIVATE_PREBOOT_SNAPSHOT_SCHEMA_MISMATCH")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        out["ERROR"] = str(error) if isinstance(error, ValueError) else "PRIVATE_PREBOOT_SNAPSHOT_INVALID"
        return finish(out, 2)
    out["PREBOOT_SNAPSHOT_PRIVATE_FILE_PASS"] = True

    root = Path.home() / "N3W_PRIVATE_EVIDENCE" / GATE
    if root.exists() or root.is_symlink():
        out["ERROR"] = "PRIVATE_EVIDENCE_ALREADY_EXISTS"
        return finish(out, 2)

    root.mkdir(parents=True, mode=0o700)
    os.chmod(root, 0o700)

    remote = r"""
import hashlib
import ipaddress
import json
import shutil
import socket
import ssl
import sqlite3
import subprocess
import time
from pathlib import Path, PurePosixPath

class Stop(Exception):
    pass

def require(value, code):
    if not value:
        raise Stop(code)

def run(args, code):
    p = subprocess.run(args, text=True, capture_output=True)
    if p.returncode != 0:
        raise Stop(code)
    return p.stdout

def inspect_container(value, code):
    raw = run(["docker", "inspect", "--type", "container", value], code)
    try:
        docs = json.loads(raw)
    except json.JSONDecodeError:
        raise Stop(code + "_INVALID_JSON")
    require(
        isinstance(docs, list) and len(docs) == 1 and isinstance(docs[0], dict),
        code + "_AMBIGUOUS",
    )
    return docs[0]

def env_map(doc):
    cfg = doc.get("Config")
    require(isinstance(cfg, dict), "MANAGER_CONFIG_MISSING")
    raw = cfg.get("Env")
    require(isinstance(raw, list), "MANAGER_ENV_MISSING")
    result = {}
    for item in raw:
        if isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result

def resolve_host_path(doc, container_path):
    requested = PurePosixPath(container_path)
    require(requested.is_absolute(), "DATABASE_PATH_NOT_ABSOLUTE")
    mounts = doc.get("Mounts")
    require(isinstance(mounts, list), "MANAGER_MOUNTS_MISSING")
    matches = []
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        source = mount.get("Source")
        destination = mount.get("Destination")
        if not isinstance(source, str) or not isinstance(destination, str):
            continue
        try:
            relative = requested.relative_to(PurePosixPath(destination))
        except ValueError:
            continue
        matches.append(Path(source).joinpath(*relative.parts))
    require(len(matches) == 1, "DATABASE_MOUNT_RESOLUTION_AMBIGUOUS")
    path = matches[0]
    require(path.is_file() and not path.is_symlink(), "DATABASE_FILE_MISSING_OR_UNSAFE")
    return path

def ro_connection(path):
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection

def require_tables(connection, names):
    present = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    require(set(names) <= present, "REQUIRED_DATABASE_TABLE_MISSING")

def table_hardware_ids(connection, table):
    result = set()
    rows = connection.execute(
        f"SELECT DISTINCT hardware_id FROM {table} WHERE hardware_id IS NOT NULL"
    ).fetchall()
    for row in rows:
        value = row["hardware_id"]
        if isinstance(value, str) and value:
            result.add(value)
    return result

def build_snapshot(registration, credential):
    registration_tables = {
        "registrations",
        "pairing_sessions",
        "registration_events",
        "registration_node_history",
        "node_id_leases",
        "retirement_outbox",
    }
    values = set()
    with ro_connection(registration) as connection:
        require_tables(connection, registration_tables)
        for table in sorted(registration_tables):
            values.update(table_hardware_ids(connection, table))
    with ro_connection(credential) as connection:
        require_tables(connection, {"credential_assignments"})
        values.update(table_hardware_ids(connection, "credential_assignments"))
    hashes = sorted(
        hashlib.sha256(value.encode("utf-8")).hexdigest()
        for value in values
    )
    return {
        "schema": "n3w.kf050.runtime-identity-snapshot/1",
        "hardware_id_sha256": hashes,
        "hardware_id_count": len(hashes),
        "read_only": True,
        "manager_mutation": False,
        "manager_replay_mutation": False,
    }

def port_listening(text, port):
    target = str(port)
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        if local.rsplit(":", 1)[-1] == target:
            return True
    return False

try:
    require(shutil.which("docker") is not None, "DOCKER_CLI_NOT_FOUND")
    run(["docker", "version", "--format", "{{.Server.Version}}"], "DOCKER_DAEMON_NOT_ACCESSIBLE")

    manager = inspect_container("greenhouse-manager", "MANAGER_INSPECT_FAILED")

    broker_ids = [
        line.strip()
        for line in run(
            [
                "docker", "ps", "-q", "--no-trunc",
                "--filter", "label=com.docker.compose.project=n3wfc4",
                "--filter", "label=com.docker.compose.service=broker",
            ],
            "BROKER_SELECTOR_FAILED",
        ).splitlines()
        if line.strip()
    ]
    require(len(broker_ids) == 1, "BROKER_RUNTIME_BINDING_NOT_UNIQUE")
    broker = inspect_container(broker_ids[0], "BROKER_INSPECT_FAILED")

    manager_state = manager.get("State")
    broker_state = broker.get("State")
    require(
        isinstance(manager_state, dict) and manager_state.get("Running") is True,
        "MANAGER_NOT_RUNNING",
    )
    require(
        isinstance(broker_state, dict) and broker_state.get("Running") is True,
        "BROKER_NOT_RUNNING",
    )

    broker_cfg = broker.get("Config")
    require(isinstance(broker_cfg, dict), "BROKER_CONFIG_MISSING")
    broker_labels = broker_cfg.get("Labels")
    require(isinstance(broker_labels, dict), "BROKER_LABELS_MISSING")
    require(
        broker_labels.get("com.docker.compose.project") == "n3wfc4",
        "BROKER_PROJECT_MISMATCH",
    )
    require(
        broker_labels.get("com.docker.compose.service") == "broker",
        "BROKER_SERVICE_MISMATCH",
    )

    broker_name = str(broker.get("Name") or "").lstrip("/")
    require(bool(broker_name), "BROKER_NAME_MISSING")

    env = env_map(manager)
    advertised_host = env.get(
        "GH_N3W_PAIRING_ADVERTISED_HOST",
        "greenhouse-manager.local",
    )
    require(advertised_host == "auto", "PAIRING_ADVERTISED_HOST_NOT_AUTO")

    ipc_path = env.get(
        "GH_N3W_PAIRING_SOCKET_PATH",
        "/run/greenhouse-manager/pairing.sock",
    )
    require(ipc_path.startswith("/"), "PAIRING_IPC_PATH_NOT_ABSOLUTE")
    ipc_probe = '''import json, os, shutil, stat
from pathlib import Path
p = Path(os.environ.get("GH_N3W_PAIRING_SOCKET_PATH", "/run/greenhouse-manager/pairing.sock"))
parent = p.parent
safe = p.is_absolute() and not p.is_symlink() and not parent.is_symlink()
if safe:
    try:
        a = p.stat()
        b = parent.stat()
        safe = (
            stat.S_ISSOCK(a.st_mode)
            and stat.S_IMODE(a.st_mode) == 0o600
            and stat.S_ISDIR(b.st_mode)
            and stat.S_IMODE(b.st_mode) == 0o700
        )
    except OSError:
        safe = False
print(json.dumps({"uds_secure": bool(safe), "cli_present": bool(shutil.which("greenhouse-manager-pairing"))}))
'''
    raw_ipc = run(
        ["docker", "exec", "greenhouse-manager", "python3", "-c", ipc_probe],
        "MANAGER_IPC_READONLY_INSPECT_FAILED",
    )
    try:
        ipc_result = json.loads(raw_ipc)
    except (ValueError, TypeError):
        raise Stop("MANAGER_IPC_PROBE_INVALID_JSON")
    require(ipc_result.get("uds_secure") is True, "MANAGER_PAIRING_SOCKET_NOT_SECURE")
    require(ipc_result.get("cli_present") is True, "MANAGER_PAIRING_CLI_NOT_FOUND")
    ttl_raw = env.get("GH_PAIRING_PENDING_TTL_S", "120")
    try:
        ttl = int(ttl_raw)
    except (TypeError, ValueError):
        raise Stop("MANAGER_PAIRING_PENDING_TTL_INVALID")
    require(90 <= ttl <= 600, "MANAGER_PAIRING_PENDING_TTL_UNSAFE_FOR_PRESTAGE")

    broker_host = env.get("GH_N3W_NODE_BROKER_HOST", "mqtt.greenhouse.local")
    broker_port = int(env.get("GH_N3W_NODE_BROKER_PORT", "8883"))
    tls_server_name = env.get(
        "GH_N3W_NODE_BROKER_TLS_SERVER_NAME",
        "mqtt.greenhouse.local",
    )
    ca_file = env.get("GH_N3W_NODE_BROKER_CA_FILE")
    pairing_udp_port = int(env.get("GH_N3W_PAIRING_UDP_PORT", "47111"))
    pairing_http_port = int(env.get("GH_N3W_PAIRING_HTTP_PORT", "47112"))

    require(broker_port == 8883, "BROKER_PORT_NOT_8883")
    require(pairing_udp_port == 47111, "PAIRING_UDP_PORT_NOT_47111")
    require(pairing_http_port == 47112, "PAIRING_HTTP_PORT_NOT_47112")
    require(isinstance(ca_file, str) and bool(ca_file), "BROKER_CA_NOT_CONFIGURED")

    try:
        broker_ip = str(ipaddress.IPv4Address(broker_host))
    except ValueError:
        raise Stop("BROKER_HOST_NOT_IPV4")

    raw_addresses = run(
        ["ip", "-j", "-4", "addr", "show", "scope", "global"],
        "T1_IPV4_READ_FAILED",
    )
    try:
        address_doc = json.loads(raw_addresses)
    except json.JSONDecodeError:
        raise Stop("T1_IPV4_JSON_INVALID")

    global_ipv4 = set()
    for interface in address_doc:
        if not isinstance(interface, dict):
            continue
        for info in interface.get("addr_info", []):
            if (
                isinstance(info, dict)
                and info.get("family") == "inet"
                and info.get("scope") == "global"
                and isinstance(info.get("local"), str)
            ):
                global_ipv4.add(info["local"])
    require(broker_ip in global_ipv4, "BROKER_HOST_NOT_CURRENT_T1_IPV4")

    manager_host_config = manager.get("HostConfig")
    require(isinstance(manager_host_config, dict), "MANAGER_HOST_CONFIG_MISSING")
    network_mode = manager_host_config.get("NetworkMode")
    port_bindings = manager_host_config.get("PortBindings")
    require(network_mode == "host", "MANAGER_NOT_HOST_NETWORK")
    require(port_bindings in (None, {}), "MANAGER_PORT_BINDINGS_NOT_EMPTY")

    udp_listeners = run(["ss", "-H", "-lun"], "UDP_LISTENER_READ_FAILED")
    tcp_listeners = run(["ss", "-H", "-ltn"], "TCP_LISTENER_READ_FAILED")
    udp_47111 = port_listening(udp_listeners, 47111)
    tcp_47112 = port_listening(tcp_listeners, 47112)
    tcp_8883 = port_listening(tcp_listeners, 8883)
    require(udp_47111, "UDP_47111_NOT_LISTENING")
    require(tcp_47112, "TCP_47112_NOT_LISTENING")
    require(tcp_8883, "TCP_8883_NOT_LISTENING")

    ca_pem = run(
        ["docker", "exec", "greenhouse-manager", "cat", ca_file],
        "BROKER_CA_READ_FAILED",
    )
    require(
        "-----BEGIN CERTIFICATE-----" in ca_pem
        and "-----END CERTIFICATE-----" in ca_pem,
        "BROKER_CA_PEM_INVALID",
    )

    tls_context = ssl.create_default_context()
    tls_context.check_hostname = True
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.load_verify_locations(cadata=ca_pem)
    with socket.create_connection((broker_ip, 8883), timeout=6) as raw_socket:
        with tls_context.wrap_socket(
            raw_socket,
            server_hostname=tls_server_name,
        ) as tls_socket:
            leaf_certificate = tls_socket.getpeercert(binary_form=True)
    require(
        isinstance(leaf_certificate, bytes) and len(leaf_certificate) > 0,
        "BROKER_TLS_PEER_CERT_MISSING",
    )

    registration_container = env.get(
        "GH_PAIRING_DB_PATH",
        "/var/lib/greenhouse-manager/registration.sqlite3",
    )
    credential_container = env.get(
        "GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH",
        "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3",
    )
    replay_container = env.get(
        "GH_N3W_REPLAY_DB_PATH",
        "/var/lib/greenhouse-manager/n3w/replay.sqlite3",
    )

    registration = resolve_host_path(manager, registration_container)
    credential = resolve_host_path(manager, credential_container)
    replay = resolve_host_path(manager, replay_container)

    with ro_connection(replay) as connection:
        require_tables(connection, {"n3w_replay_state"})

    snapshot_1 = build_snapshot(registration, credential)
    time.sleep(0.35)
    snapshot_2 = build_snapshot(registration, credential)
    require(snapshot_1 == snapshot_2, "IDENTITY_SNAPSHOT_UNSTABLE")

    manager_cfg = manager.get("Config")
    require(isinstance(manager_cfg, dict), "MANAGER_CONFIG_MISSING")
    manager_image_ref = str(manager_cfg.get("Image") or "")
    broker_image_ref = str(broker_cfg.get("Image") or "")
    manager_image_id = str(manager.get("Image") or "")
    broker_image_id = str(broker.get("Image") or "")
    require(bool(manager_image_ref) and bool(manager_image_id), "MANAGER_IMAGE_BINDING_MISSING")
    require(bool(broker_image_ref) and bool(broker_image_id), "BROKER_IMAGE_BINDING_MISSING")

    manager_labels = manager_cfg.get("Labels")
    if not isinstance(manager_labels, dict):
        manager_labels = {}
    manager_revision = manager_labels.get("org.opencontainers.image.revision") or ""

    result = {
        "ok": True,
        "docker_cli_present": True,
        "docker_daemon_accessible": True,
        "manager": {
            "name": "greenhouse-manager",
            "id": manager.get("Id"),
            "image_ref": manager_image_ref,
            "image_id": manager_image_id,
            "image_revision": manager_revision,
            "running": True,
            "started_at": manager_state.get("StartedAt"),
            "restart_count": manager.get("RestartCount"),
            "network_mode": network_mode,
            "ports_empty": port_bindings in (None, {}),
        },
        "broker": {
            "name": broker_name,
            "id": broker.get("Id"),
            "image_ref": broker_image_ref,
            "image_id": broker_image_id,
            "running": True,
            "started_at": broker_state.get("StartedAt"),
            "restart_count": broker.get("RestartCount"),
            "compose_project": broker_labels.get("com.docker.compose.project"),
            "compose_service": broker_labels.get("com.docker.compose.service"),
        },
        "pairing_advertised_host": advertised_host,
        "broker_host": broker_ip,
        "broker_port": broker_port,
        "tls_server_name": tls_server_name,
        "pairing_udp_port": pairing_udp_port,
        "pairing_http_port": pairing_http_port,
        "global_ipv4": sorted(global_ipv4),
        "udp_47111": udp_47111,
        "tcp_47112": tcp_47112,
        "tcp_8883": tcp_8883,
        "tls_ca_sha256": hashlib.sha256(ca_pem.encode("utf-8")).hexdigest(),
        "tls_leaf_sha256": hashlib.sha256(leaf_certificate).hexdigest(),
        "registration_host_path": str(registration),
        "credential_host_path": str(credential),
        "replay_host_path": str(replay),
        "snapshot": snapshot_1,
        "snapshot_stable": True,
        "manager_pairing_uds_secure": ipc_result.get("uds_secure") is True,
        "manager_pairing_cli_present": ipc_result.get("cli_present") is True,
        "manager_pairing_pending_ttl_s": ttl,
        "db_read_only": True,
        "manager_mutation": False,
        "manager_replay_mutation": False,
    }
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0)

except Stop as error:
    print(json.dumps({"ok": False, "error": str(error), "read_only": True}, sort_keys=True))
    raise SystemExit(2)
except Exception:
    print(json.dumps({"ok": False, "error": "UNEXPECTED_READONLY_PROBE_FAILURE", "read_only": True}, sort_keys=True))
    raise SystemExit(2)
"""

    opts = [
        "-o", "CanonicalizeHostname=no",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "BatchMode=no",
        "-o", "NumberOfPasswordPrompts=1",
        "-o", "ConnectTimeout=8",
        "-o", "ConnectionAttempts=1",
        "-o", "ControlMaster=no",
        "-o", "ControlPath=none",
        "-o", "ControlPersist=no",
        "-o", "ClearAllForwardings=yes",
        "-o", "PermitLocalCommand=no",
        "-o", "RequestTTY=no",
    ]

    out["AUTHORIZATION_CLAIMED"] = True
    out["AUTHORIZATION_CONSUMED"] = True

    try:
        p = subprocess.run(
            ["ssh", "-T", *opts, target, "python3", "-"],
            input=remote,
            text=True,
            capture_output=True,
            timeout=150,
        )
    except subprocess.TimeoutExpired:
        out["ERROR"] = "P4_PREBOOT_T1_TIMEOUT"
        return finish(out, 2)

    out["T1_ACCESSED"] = True
    out["SSH_RETURN_CODE"] = p.returncode
    out["SSH_STDERR_SHA256"] = sha_text(p.stderr or "")

    stdout_path = root / "remote.stdout.json"
    stderr_path = root / "remote.stderr.txt"
    stdout_path.write_text(p.stdout or "", encoding="utf-8")
    stderr_path.write_text(p.stderr or "", encoding="utf-8")
    os.chmod(stdout_path, 0o600)
    os.chmod(stderr_path, 0o600)

    if p.returncode != 0:
        try:
            remote_result = json.loads((p.stdout or "").strip())
            out["ERROR"] = remote_result.get("error", "P4_PREBOOT_REMOTE_FAILED")
        except Exception:
            out["ERROR"] = "P4_PREBOOT_REMOTE_FAILED"
        return finish(out, 2)

    try:
        data = json.loads((p.stdout or "").strip())
    except json.JSONDecodeError:
        out["ERROR"] = "P4_PREBOOT_REMOTE_JSON_INVALID"
        return finish(out, 2)

    if data.get("ok") is not True:
        out["ERROR"] = data.get("error", "P4_PREBOOT_REMOTE_BASELINE_FAILED")
        return finish(out, 2)

    manager = data.get("manager")
    broker = data.get("broker")
    if not isinstance(manager, dict) or not isinstance(broker, dict):
        out["ERROR"] = "P4_PREBOOT_RUNTIME_RESULT_INVALID"
        return finish(out, 2)

    out["DOCKER_CLI_PRESENT"] = data.get("docker_cli_present") is True
    out["DOCKER_DAEMON_ACCESSIBLE"] = data.get("docker_daemon_accessible") is True
    out["MANAGER_CONTAINER_RUNNING"] = manager.get("running") is True
    out["BROKER_CONTAINER_RUNNING"] = broker.get("running") is True
    out["BROKER_RUNTIME_BINDING_UNIQUE"] = (
        broker.get("compose_project") == "n3wfc4"
        and broker.get("compose_service") == "broker"
    )
    out["BROKER_CONTAINER_NAME"] = broker.get("name")
    out["MANAGER_CONTAINER_NAME"] = manager.get("name")
    out["MANAGER_IMAGE_REF"] = manager.get("image_ref")
    out["BROKER_IMAGE_REF"] = broker.get("image_ref")

    manager_container_sha = sha_text(manager.get("id"))
    broker_container_sha = sha_text(broker.get("id"))
    out["MANAGER_CONTAINER_ID_SHA256"] = manager_container_sha
    out["BROKER_CONTAINER_ID_SHA256"] = broker_container_sha
    out["MANAGER_CONTAINER_CONTINUITY_FROM_PRIOR_P2"] = (
        manager_container_sha == PREVIOUS_MANAGER_CONTAINER_ID_SHA
    )
    out["BROKER_CONTAINER_CONTINUITY_FROM_PRIOR_P2"] = (
        broker_container_sha == PREVIOUS_BROKER_CONTAINER_ID_SHA
    )

    out["MANAGER_IMAGE_ID_SHA256"] = sha_text(manager.get("image_id"))
    out["BROKER_IMAGE_ID_SHA256"] = sha_text(broker.get("image_id"))
    out["MANAGER_STARTED_AT"] = manager.get("started_at")
    out["MANAGER_RESTART_COUNT"] = manager.get("restart_count")
    out["BROKER_STARTED_AT"] = broker.get("started_at")
    out["BROKER_RESTART_COUNT"] = broker.get("restart_count")

    revision = manager.get("image_revision")
    out["MANAGER_IMAGE_REVISION_PRESENT"] = bool(revision)
    if revision:
        out["MANAGER_IMAGE_REVISION_SHA256"] = sha_text(revision)

    out["PAIRING_ADVERTISED_HOST_MODE_AUTO"] = (
        data.get("pairing_advertised_host") == "auto"
    )
    out["MANAGER_HOST_NETWORK"] = manager.get("network_mode") == "host"
    out["MANAGER_PORTS_EMPTY"] = manager.get("ports_empty") is True
    out["UDP_47111_LISTENING"] = data.get("udp_47111") is True
    out["TCP_47112_LISTENING"] = data.get("tcp_47112") is True
    out["TCP_8883_LISTENING"] = data.get("tcp_8883") is True

    if data.get("broker_host") != host:
        out["ERROR"] = "BROKER_HOST_NOT_EXPLICIT_T1_ADDRESS"
        return finish(out, 2)
    if host not in data.get("global_ipv4", []):
        out["ERROR"] = "EXPLICIT_T1_NOT_CURRENT_GLOBAL_IPV4"
        return finish(out, 2)

    out["REAL_T1_ADDRESS_MATCH"] = True
    out["NODE_CREDENTIAL_BROKER_HOST_MATCH"] = True
    out["T1_ADDRESS_SHA256"] = sha_text(host)
    out["BROKER_TCP_TLS_A_8883"] = True
    out["TLS_CA_SHA256"] = data.get("tls_ca_sha256")
    out["TLS_LEAF_CERT_SHA256"] = data.get("tls_leaf_sha256")

    tls_binding = json.dumps(
        {
            "ca_sha256": data.get("tls_ca_sha256"),
            "server_name": data.get("tls_server_name"),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    out["TLS_CA_AND_SERVER_NAME_SHA256"] = hashlib.sha256(tls_binding).hexdigest()

    db_paths = [
        data.get("registration_host_path"),
        data.get("credential_host_path"),
        data.get("replay_host_path"),
    ]
    if not all(isinstance(value, str) and value for value in db_paths):
        out["ERROR"] = "DB_MOUNT_BINDING_INVALID"
        return finish(out, 2)

    out["REGISTRATION_DB_HOST_PATH_SHA256"] = sha_text(db_paths[0])
    out["CREDENTIAL_DB_HOST_PATH_SHA256"] = sha_text(db_paths[1])
    out["REPLAY_DB_HOST_PATH_SHA256"] = sha_text(db_paths[2])
    out["DB_MOUNT_RESOLUTION_PASS"] = True

    snapshot = data.get("snapshot")
    if not isinstance(snapshot, dict):
        out["ERROR"] = "PREBOOT_SNAPSHOT_MISSING"
        return finish(out, 2)

    snapshot_valid = (
        snapshot.get("schema") == "n3w.kf050.runtime-identity-snapshot/1"
        and snapshot.get("read_only") is True
        and snapshot.get("manager_mutation") is False
        and snapshot.get("manager_replay_mutation") is False
        and isinstance(snapshot.get("hardware_id_sha256"), list)
        and snapshot.get("hardware_id_count")
        == len(snapshot.get("hardware_id_sha256"))
    )
    if not snapshot_valid:
        out["ERROR"] = "PREBOOT_SNAPSHOT_CONTRACT_INVALID"
        return finish(out, 2)
    if data.get("snapshot_stable") is not True:
        out["ERROR"] = "PREBOOT_SNAPSHOT_NOT_STABLE"
        return finish(out, 2)

    snapshot_bytes = (
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    snapshot_path = root / "manager_preboot_identity_snapshot.json"
    snapshot_path.write_bytes(snapshot_bytes)
    os.chmod(snapshot_path, 0o600)

    snapshot_sha = hashlib.sha256(snapshot_bytes).hexdigest()
    out["IDENTITY_SNAPSHOT_STABLE"] = True
    out["MANAGER_PREBOOT_SNAPSHOT_CREATED"] = True
    out["MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SCHEMA"] = snapshot.get("schema")
    out["MANAGER_PREBOOT_IDENTITY_COUNT"] = snapshot.get("hardware_id_count")
    out["MANAGER_PREBOOT_IDENTITY_SNAPSHOT_SHA256"] = snapshot_sha
    out["PREBOOT_IDENTITY_SNAPSHOT_CONTINUITY_FROM_PRIOR_P2"] = (
        snapshot_sha == PREVIOUS_SNAPSHOT_SHA
    )

    continuity = (
        ("MANAGER_CONTAINER_ID_DRIFT", out["MANAGER_CONTAINER_CONTINUITY_FROM_PRIOR_P2"]),
        ("BROKER_CONTAINER_ID_DRIFT", out["BROKER_CONTAINER_CONTINUITY_FROM_PRIOR_P2"]),
        ("MANAGER_STARTED_AT_DRIFT", out["MANAGER_STARTED_AT"] == EXPECTED_MANAGER_STARTED_AT),
        ("BROKER_STARTED_AT_DRIFT", out["BROKER_STARTED_AT"] == EXPECTED_BROKER_STARTED_AT),
        ("MANAGER_RESTART_COUNT_DRIFT", out["MANAGER_RESTART_COUNT"] == 0),
        ("BROKER_RESTART_COUNT_DRIFT", out["BROKER_RESTART_COUNT"] == 0),
        ("T1_ADDRESS_SHA256_DRIFT", out["T1_ADDRESS_SHA256"] == EXPECTED_T1_ADDRESS_SHA256),
        ("TLS_CA_SHA256_DRIFT", out["TLS_CA_SHA256"] == EXPECTED_TLS_CA_SHA256),
        ("TLS_LEAF_SHA256_DRIFT", out["TLS_LEAF_CERT_SHA256"] == EXPECTED_TLS_LEAF_SHA256),
        ("TLS_BINDING_SHA256_DRIFT", out["TLS_CA_AND_SERVER_NAME_SHA256"] == EXPECTED_TLS_BINDING_SHA256),
        ("PREBOOT_SNAPSHOT_DRIFT", out["PREBOOT_IDENTITY_SNAPSHOT_CONTINUITY_FROM_PRIOR_P2"]),
        ("PREBOOT_IDENTITY_COUNT_DRIFT", out["MANAGER_PREBOOT_IDENTITY_COUNT"] == EXPECTED_PREBOOT_IDENTITY_COUNT),
    )
    for error_code, is_valid in continuity:
        if not is_valid:
            out["ERROR"] = error_code
            return finish(out, 2)
    out["MANAGER_BROKER_PREBOOT_CONTINUITY_PASS"] = True

    baseline_checks = [
        out["DOCKER_CLI_PRESENT"],
        out["DOCKER_DAEMON_ACCESSIBLE"],
        out["MANAGER_CONTAINER_RUNNING"],
        out["BROKER_CONTAINER_RUNNING"],
        out["BROKER_RUNTIME_BINDING_UNIQUE"],
        out["PAIRING_ADVERTISED_HOST_MODE_AUTO"],
        out["REAL_T1_ADDRESS_MATCH"],
        out["NODE_CREDENTIAL_BROKER_HOST_MATCH"],
        out["MANAGER_HOST_NETWORK"],
        out["MANAGER_PORTS_EMPTY"],
        out["UDP_47111_LISTENING"],
        out["TCP_47112_LISTENING"],
        out["TCP_8883_LISTENING"],
        out["BROKER_TCP_TLS_A_8883"],
        out["DB_MOUNT_RESOLUTION_PASS"],
        out["IDENTITY_SNAPSHOT_STABLE"],
        out["MANAGER_PREBOOT_SNAPSHOT_CREATED"],
    ]
    if not all(baseline_checks):
        out["ERROR"] = "P4_PREBOOT_BASELINE_PREDICATE_FAILED"
        return finish(out, 2)

    out["P4_PREBOOT_READONLY_BASELINE_PASS"] = True
    out["MANAGER_PAIRING_UDS_SECURE"] = data.get("manager_pairing_uds_secure") is True
    out["MANAGER_PAIRING_CLI_PRESENT"] = data.get("manager_pairing_cli_present") is True
    out["MANAGER_PAIRING_TTL_POLICY_PASS"] = isinstance(data.get("manager_pairing_pending_ttl_s"), int) and 90 <= data["manager_pairing_pending_ttl_s"] <= 600
    out["MANAGER_PAIRING_PENDING_TTL_S"] = data.get("manager_pairing_pending_ttl_s")
    if not (out["MANAGER_PAIRING_UDS_SECURE"] and out["MANAGER_PAIRING_CLI_PRESENT"] and out["MANAGER_PAIRING_TTL_POLICY_PASS"]):
        out["ERROR"] = "MANAGER_PAIRING_IPC_PRESTAGE_FAILED"
        return finish(out, 2)

    request_id = str(uuid.uuid4())
    nonce = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
    hardware_id = "p2-refreeze-probe-" + secrets.token_hex(8)
    query = {
        "schema": "gh.discovery.query/1",
        "request_id": request_id,
        "nonce": nonce,
        "hardware_id": hardware_id,
        "protocols": ["gh-n3w-simple-pairing/1"],
    }
    payload = json.dumps(
        query,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    out["EXTERNAL_DISCOVERY_ATTEMPTED"] = True
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(6)
        sock.sendto(payload, (host, int(data.get("pairing_udp_port"))))
        response_bytes, response_source = sock.recvfrom(4096)
    except socket.timeout:
        out["ERROR"] = "EXTERNAL_DISCOVERY_TIMEOUT"
        return finish(out, 2)
    finally:
        sock.close()

    discovery_path = root / "external_discovery_response.private.json"
    discovery_path.write_bytes(response_bytes)
    os.chmod(discovery_path, 0o600)

    try:
        response = json.loads(response_bytes.decode("utf-8"))
    except Exception:
        out["ERROR"] = "EXTERNAL_DISCOVERY_INVALID_JSON"
        return finish(out, 2)

    candidate = response.get("candidate")
    if not isinstance(candidate, dict):
        out["ERROR"] = "EXTERNAL_DISCOVERY_CANDIDATE_MISSING"
        return finish(out, 2)

    discovery_pass = (
        response_source[0] == host
        and response.get("schema") == "gh.discovery.response/1"
        and response.get("request_id") == request_id
        and response.get("nonce") == nonce
        and candidate.get("schema") == "gh.manager.candidate/1"
        and candidate.get("host") == host
        and candidate.get("protocol") == "gh-n3w-simple-pairing/1"
        and candidate.get("port") == int(data.get("pairing_http_port"))
    )
    if not discovery_pass:
        out["ERROR"] = "EXTERNAL_DISCOVERY_RESPONSE_MISMATCH"
        return finish(out, 2)

    out["EXTERNAL_DISCOVERY_RESPONSE_SOURCE_MATCH"] = True
    out["EXTERNAL_DISCOVERY_CANDIDATE_HOST_MATCH"] = True
    out["EXTERNAL_DISCOVERY_PASS"] = True
    out["MANAGER_DISCOVERY_AUTO_SOURCE_A"] = True
    out["P4_PREBOOT_PASS"] = True
    out["P4_PRIVATE_PRESTAGE_PASS"] = True
    out["READY_FOR_P4_AUTHORIZATION"] = True

    return finish(out, 0)


if __name__ == "__main__":
    raise SystemExit(main())