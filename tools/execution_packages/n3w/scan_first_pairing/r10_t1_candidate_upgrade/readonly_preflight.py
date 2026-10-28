#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w.r10-t1-candidate-upgrade-readonly-preflight/1"
CURRENT_SOURCE_HEAD = "03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6"
TARGET_SOURCE_HEAD = "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
CURRENT_MANAGER_IMAGE = "local/greenhouse-manager:fresh-03dab2bd04e7"
TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-e299c937a7b8"
EXPECTED_BROKER_IMAGE = "local/n3w-mosquitto:2.1.2-3184566d"
EXPECTED_HA_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024
CONFIRMATION = "R10 T1 CANDIDATE READONLY PREFLIGHT: YES"

EXPECTED_CURRENT_BLOBS = {
    "compose": "ce864b1964bdca10c4d16a8a7824b34b358ad119",
    "installed_services_unit": "e25f4553177c009bbe019c5cd8a9ddd3b0c07e46",
    "runtime_services_unit": "b070303a53b16b15aa108d3e9a2e952a7bc02d08",
    "dispatcher": "f733f5a1cfc936f77d1fabc383ccf262264e33d2",
}
EXPECTED_TARGET_BLOBS = {
    "compose": "c9038251d9ba1b05a472edda14b287470690815a",
    "installed_services_unit": "3485b6c2f9341fda2fcbd2c82c83077ad78cf42c",
    "runtime_services_unit": "ee7c4151e79368e6daca5d6bd1359a846397fc95",
    "dispatcher": "3d6f32455fffd6f604f83a6c12e298bc395945e0",
    "registration_unit": "d8f1a3c6d757284c72b8348773d0bc09f6904b35",
    "registration_guard": "ef5077b6bc80c73bc8d3f35cf7a33a198ce918c7",
    "trusted_lan_authority": "ea964cd2b9b9380785f3aee5e8d6383180be4ee0",
}

EXPECTED_COMPOSE_FILE = "/etc/n3wfc4/docker-compose.yml"
EXPECTED_COMPOSE_ENV_FILE = "/etc/n3wfc4/docker-compose.env"
EXPECTED_COMPOSE_PROJECT = "n3wfc4"

T1_PROBE = r'''
import hashlib
import ipaddress
import json
import os
import shutil
import sqlite3
import stat
import subprocess
from pathlib import Path

CURRENT_MANAGER_IMAGE = "local/greenhouse-manager:fresh-03dab2bd04e7"
TARGET_MANAGER_IMAGE = "local/greenhouse-manager:fresh-e299c937a7b8"

def run(argv, timeout=30):
    try:
        p = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except Exception as exc:
        return {"rc": 127, "out": "", "err": type(exc).__name__}
    return {
        "rc": p.returncode,
        "out": p.stdout.strip(),
        "err": p.stderr.strip()[:160],
    }

def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def git_blob_bytes(data):
    h = hashlib.sha1()
    h.update(("blob " + str(len(data)) + "\0").encode("ascii"))
    h.update(data)
    return h.hexdigest()

def file_state(raw_path):
    path = Path(raw_path)
    try:
        st = path.lstat()
    except FileNotFoundError:
        return {"exists": False}
    if stat.S_ISLNK(st.st_mode):
        return {"exists": True, "symlink": True}
    if not stat.S_ISREG(st.st_mode):
        return {
            "exists": True,
            "symlink": False,
            "regular": False,
            "mode": stat.S_IMODE(st.st_mode),
            "uid": st.st_uid,
            "gid": st.st_gid,
        }
    try:
        data = path.read_bytes()
    except OSError:
        return {
            "exists": True,
            "symlink": False,
            "regular": True,
            "readable": False,
            "mode": stat.S_IMODE(st.st_mode),
            "uid": st.st_uid,
            "gid": st.st_gid,
        }
    return {
        "exists": True,
        "symlink": False,
        "regular": True,
        "readable": True,
        "size": len(data),
        "mode": stat.S_IMODE(st.st_mode),
        "uid": st.st_uid,
        "gid": st.st_gid,
        "git_blob_sha1": git_blob_bytes(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }

def parse_env_file(raw_path):
    path = Path(raw_path)
    if not path.is_file() or path.is_symlink():
        return {"ok": False}
    values = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {"ok": False}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            return {"ok": False}
        key, value = line.split("=", 1)
        if not key:
            return {"ok": False}
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return {"ok": True, "values": values}

def service(name):
    active = run(["systemctl", "is-active", name])
    show = run([
        "systemctl", "show", name,
        "-p", "LoadState",
        "-p", "Result",
        "-p", "DropInPaths",
    ])
    props = {}
    if show["rc"] == 0:
        for line in show["out"].splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v
    return {
        "active": active["out"] if active["out"] else "inactive",
        "load_state": props.get("LoadState"),
        "result": props.get("Result"),
        "drop_in_paths_empty": not bool(props.get("DropInPaths")),
    }

def container(service_name):
    q = run([
        "docker", "ps",
        "--filter", "label=com.docker.compose.project=n3wfc4",
        "--filter", "label=com.docker.compose.service=" + service_name,
        "-q",
    ])
    ids = [line.strip() for line in q["out"].splitlines() if line.strip()]
    if q["rc"] != 0 or len(ids) != 1:
        return {"ok": False, "count": len(ids)}
    cid = ids[0]
    i = run(["docker", "inspect", cid])
    if i["rc"] != 0:
        return {"ok": False, "count": 1}
    try:
        doc = json.loads(i["out"])[0]
    except Exception:
        return {"ok": False, "count": 1}
    state = doc.get("State") or {}
    config = doc.get("Config") or {}
    env = {}
    for item in config.get("Env") or []:
        if "=" in item:
            k, v = item.split("=", 1)
            env[k] = v
    return {
        "ok": bool(state.get("Running")),
        "count": 1,
        "id_sha256": sha(str(doc.get("Id") or cid)),
        "image_id_sha256": sha(str(doc.get("Image") or "")),
        "image": str(config.get("Image") or ""),
        "restart_count": int(doc.get("RestartCount") or 0),
        "started_at": str(state.get("StartedAt") or ""),
        "manager_pairing_disabled": (
            env.get("GH_N3W_PRODUCT_PAIRING_ENABLED") == "false"
            if service_name == "manager" else None
        ),
        "manager_runtime_enabled": (
            env.get("GH_N3W_RUNTIME_ENABLED") == "true"
            if service_name == "manager" else None
        ),
        "manager_advertised_host_auto": (
            env.get("GH_N3W_PAIRING_ADVERTISED_HOST") == "auto"
            if service_name == "manager" else None
        ),
    }

def listener_count(protocol, port):
    args = ["ss", "-H", "-ln" + ("t" if protocol == "tcp" else "u")]
    p = run(args)
    if p["rc"] != 0:
        return -1
    needle = ":" + str(port)
    count = 0
    for line in p["out"].splitlines():
        fields = line.split()
        if len(fields) > 3 and fields[3].endswith(needle):
            count += 1
    return count

def pairing_window(manager_id):
    if not manager_id:
        return {"ok": False}
    p = run([
        "docker", "exec", manager_id,
        "greenhouse-manager-pairing", "window-status",
    ])
    if p["rc"] != 0:
        return {"ok": False}
    try:
        raw = json.loads(p["out"])
    except Exception:
        return {"ok": False}
    return {
        "ok": raw.get("accepted") is True,
        "state": raw.get("pairing_window_state"),
        "raw_locator_in_output": raw.get("raw_locator_in_output"),
    }

def manager_container_id():
    q = run([
        "docker", "ps",
        "--filter", "label=com.docker.compose.project=n3wfc4",
        "--filter", "label=com.docker.compose.service=manager",
        "-q",
    ])
    ids = [line.strip() for line in q["out"].splitlines() if line.strip()]
    return ids[0] if q["rc"] == 0 and len(ids) == 1 else ""

def networkmanager_eth0():
    state = run(["nmcli", "-g", "GENERAL.STATE", "device", "show", "eth0"])
    addresses = run(["nmcli", "-g", "IP4.ADDRESS", "device", "show", "eth0"])
    if state["rc"] != 0 or addresses["rc"] != 0:
        return {"ok": False}
    nets = set()
    try:
        for line in addresses["out"].splitlines():
            value = line.strip()
            if not value:
                continue
            interface = ipaddress.ip_interface(value)
            if not isinstance(interface, ipaddress.IPv4Interface):
                return {"ok": False}
            ip = interface.ip
            network = interface.network
            if (
                ip.is_unspecified
                or ip.is_loopback
                or ip.is_multicast
                or ip.is_link_local
                or network.prefixlen == 0
            ):
                return {"ok": False}
            nets.add(str(network))
    except ValueError:
        return {"ok": False}
    if len(nets) != 1:
        return {"ok": False}
    network = next(iter(nets))
    return {
        "ok": state["out"].startswith("100"),
        "connected": state["out"].startswith("100"),
        "subnet_sha256": sha(network),
    }

def database():
    path = Path("/var/lib/greenhouse-manager/manager/manager-state.sqlite3")
    try:
        st = path.lstat()
    except FileNotFoundError:
        return {"ok": False, "reason": "missing"}
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return {"ok": False, "reason": "unsafe"}
    try:
        con = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True, timeout=5)
        con.execute("PRAGMA query_only=ON")
        integrity_row = con.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "invalid"
        tables = sorted(
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        )
        registration_count = None
        if "registrations" in tables:
            registration_count = int(
                con.execute(
                    "SELECT COUNT(*) FROM registrations WHERE retired_at IS NULL"
                ).fetchone()[0]
            )
        con.close()
    except sqlite3.Error:
        return {"ok": False, "reason": "sqlite_error"}
    return {
        "ok": integrity == "ok",
        "integrity": integrity,
        "table_names": tables,
        "table_names_sha256": sha("\n".join(tables)),
        "registrations_table_present": "registrations" in tables,
        "first_registration_table_present": (
            "first_registration_attempts" in tables
        ),
        "current_registration_count": registration_count,
        "mode": stat.S_IMODE(st.st_mode),
        "uid": st.st_uid,
        "gid": st.st_gid,
    }

def image_present(ref):
    p = run(["docker", "image", "inspect", ref])
    if p["rc"] != 0:
        return {"present": False}
    try:
        doc = json.loads(p["out"])[0]
    except Exception:
        return {"present": True, "valid": False}
    return {
        "present": True,
        "valid": True,
        "image_id_sha256": sha(str(doc.get("Id") or "")),
        "architecture": str(doc.get("Architecture") or ""),
        "os": str(doc.get("Os") or ""),
    }

def version_info():
    docker = run(["docker", "--version"])
    compose = run(["docker", "compose", "version", "--short"])
    systemd = run(["systemd", "--version"])
    return {
        "docker": docker["out"] if docker["rc"] == 0 else None,
        "compose": compose["out"] if compose["rc"] == 0 else None,
        "systemd": (
            systemd["out"].splitlines()[0]
            if systemd["rc"] == 0 and systemd["out"]
            else None
        ),
    }

activation_env = parse_env_file("/etc/n3wfc4/broker-activation.env")
activation_values = activation_env.get("values") or {}
compose_path = activation_values.get("N3WFC4_COMPOSE_FILE", "")
compose_env_path = activation_values.get("N3WFC4_COMPOSE_ENV_FILE", "")
compose_project = activation_values.get("N3WFC4_COMPOSE_PROJECT_NAME", "")
compose_env = parse_env_file(compose_env_path) if compose_env_path else {"ok": False}
compose_values = compose_env.get("values") or {}

manager = container("manager")
broker = container("broker")
homeassistant = container("homeassistant")
manager_id = manager_container_id()

files = {
    "live_compose": file_state(compose_path) if compose_path else {"exists": False},
    "compose_env": file_state(compose_env_path) if compose_env_path else {"exists": False},
    "services_unit": file_state("/etc/systemd/system/n3wfc4-services-activation.service"),
    "dispatcher": file_state("/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard"),
    "registration_unit": file_state("/etc/systemd/system/n3wfc4-registration-ingress-guard.service"),
    "registration_guard": file_state("/usr/local/sbin/n3w-registration-ingress-guard"),
    "trusted_lan_authority": file_state("/usr/local/sbin/n3w-trusted-product-lan-authority"),
    "registration_certificate": file_state("/etc/n3wfc4/registration-tls/bootstrap.pem"),
    "registration_private_key": file_state("/etc/n3wfc4/registration-tls/bootstrap.key"),
    "runtime_compose": file_state("/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.yml"),
    "runtime_services_unit": file_state("/opt/HomeAssistant/infra/n3w-t1/systemd/n3wfc4-services-activation.service"),
    "runtime_dispatcher": file_state("/opt/HomeAssistant/infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard"),
    "runtime_registration_unit": file_state("/opt/HomeAssistant/infra/n3w-t1/systemd/n3wfc4-registration-ingress-guard.service"),
    "runtime_registration_guard": file_state("/opt/HomeAssistant/tools/n3w_registration_ingress_guard.py"),
    "runtime_trusted_lan_authority": file_state("/opt/HomeAssistant/tools/n3w_trusted_product_lan_authority.py"),
    "trusted_lan_state": file_state("/run/n3wfc4-trusted-lan/state.json"),
}

report = {
    "schema": "gh.n3w.r10-t1-candidate-live-readonly/1",
    "services": {
        "broker_activation": service("n3wfc4-broker-activation.service"),
        "services_activation": service("n3wfc4-services-activation.service"),
        "broker_guard": service("n3wfc4-broker-ingress-guard.service"),
        "registration_guard": service("n3wfc4-registration-ingress-guard.service"),
    },
    "containers": {
        "broker": broker,
        "manager": manager,
        "homeassistant": homeassistant,
    },
    "activation": {
        "env_ok": activation_env.get("ok") is True,
        "compose_file": compose_path,
        "compose_env_file": compose_env_path,
        "compose_project": compose_project,
        "compose_env_ok": compose_env.get("ok") is True,
        "manager_image": compose_values.get("GH_MANAGER_IMAGE"),
    },
    "files": files,
    "listeners": {
        "47110_tcp": listener_count("tcp", 47110),
        "47111_udp": listener_count("udp", 47111),
        "47112_tcp": listener_count("tcp", 47112),
    },
    "pairing_window": pairing_window(manager_id),
    "networkmanager": networkmanager_eth0(),
    "database": database(),
    "candidate_image": image_present(TARGET_MANAGER_IMAGE),
    "versions": version_info(),
    "root_free_bytes": shutil.disk_usage("/").free,
    "mutation": False,
    "service_stop_start": False,
    "container_recreate": False,
    "file_write": False,
    "board_access": False,
}
print(json.dumps(report, sort_keys=True, separators=(",", ":")))
'''

class StopExecution(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_root(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.exists():
        if (
            path.is_symlink()
            or not path.is_dir()
            or path.stat().st_uid != os.geteuid()
            or stat.S_IMODE(path.stat().st_mode) != 0o700
            or any(path.iterdir())
        ):
            raise StopExecution("evidence_dir_must_be_empty_mode_0700_owned")
    else:
        path.mkdir(parents=True, mode=0o700)
    return path


def write_private_json(path: Path, doc: Any) -> None:
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise StopExecution("private_write_short")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def validate_target(target: str) -> None:
    if (
        not target
        or target.strip() != target
        or any(c.isspace() for c in target)
        or target.startswith("-")
        or any(x in target.casefold() for x in ("placeholder", "example", "<", ">"))
    ):
        raise StopExecution("t1_target_invalid")


def run_capture(
    argv: list[str] | tuple[str, ...],
    *,
    input_bytes: bytes | None = None,
    timeout: int = 180,
) -> subprocess.CompletedProcess[bytes]:
    try:
        p = subprocess.run(
            argv,
            input=input_bytes,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StopExecution("command_timeout") from exc
    except OSError as exc:
        raise StopExecution("command_transport_error") from exc
    if p.returncode != 0:
        raise StopExecution(
            f"command_failed:{Path(argv[0]).name}:{p.returncode}"
        )
    return p


def t1_probe(target: str) -> dict[str, Any]:
    validate_target(target)
    argv = (
        "ssh",
        "-o", "BatchMode=no",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "NumberOfPasswordPrompts=1",
        "-o", "PreferredAuthentications=publickey,password",
        "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1",
        "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=2",
        target,
        "python3 -B -",
    )
    p = run_capture(
        argv,
        input_bytes=T1_PROBE.encode("utf-8"),
        timeout=180,
    )
    try:
        doc = json.loads(p.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("t1_probe_json_invalid") from exc
    if not isinstance(doc, dict):
        raise StopExecution("t1_probe_invalid")
    return doc


def _blob(doc: dict[str, Any], name: str) -> str | None:
    value = doc.get("files", {}).get(name, {})
    return value.get("git_blob_sha1") if isinstance(value, dict) else None


def _absent(doc: dict[str, Any], name: str) -> bool:
    value = doc.get("files", {}).get(name, {})
    return isinstance(value, dict) and value.get("exists") is False


def accept_t1(doc: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    services = doc.get("services", {})
    for name in ("broker_activation", "services_activation", "broker_guard"):
        record = services.get(name, {})
        if record.get("active") != "active" or record.get("load_state") != "loaded":
            failures.append(f"service:{name}")
        if record.get("drop_in_paths_empty") is not True:
            failures.append(f"service:{name}:dropin")
    registration = services.get("registration_guard", {})
    if (
        registration.get("load_state") != "not-found"
        or registration.get("active") == "active"
    ):
        failures.append("service:registration_guard_predecessor_not_absent")

    containers = doc.get("containers", {})
    for name in ("broker", "manager", "homeassistant"):
        record = containers.get(name, {})
        if record.get("ok") is not True or record.get("count") != 1:
            failures.append(f"container:{name}")
    if containers.get("manager", {}).get("image") != CURRENT_MANAGER_IMAGE:
        failures.append("manager:image_not_expected_predecessor")
    if containers.get("broker", {}).get("image") != EXPECTED_BROKER_IMAGE:
        failures.append("broker:image_drift")
    if containers.get("homeassistant", {}).get("image") != EXPECTED_HA_IMAGE:
        failures.append("homeassistant:image_drift")
    manager = containers.get("manager", {})
    if manager.get("manager_pairing_disabled") is not True:
        failures.append("manager:durable_pairing_not_disabled")
    if manager.get("manager_runtime_enabled") is not True:
        failures.append("manager:n3w_runtime_disabled")
    if manager.get("manager_advertised_host_auto") is not True:
        failures.append("manager:advertised_host_not_auto")

    activation = doc.get("activation", {})
    if activation.get("env_ok") is not True or activation.get("compose_env_ok") is not True:
        failures.append("activation:env_invalid")
    if activation.get("compose_file") != EXPECTED_COMPOSE_FILE:
        failures.append("activation:compose_path_drift")
    if activation.get("compose_env_file") != EXPECTED_COMPOSE_ENV_FILE:
        failures.append("activation:compose_env_path_drift")
    if activation.get("compose_project") != EXPECTED_COMPOSE_PROJECT:
        failures.append("activation:project_drift")
    if activation.get("manager_image") != CURRENT_MANAGER_IMAGE:
        failures.append("activation:manager_image_drift")

    if _blob(doc, "live_compose") != EXPECTED_CURRENT_BLOBS["compose"]:
        failures.append("file:live_compose_drift")
    if (
        _blob(doc, "services_unit")
        != EXPECTED_CURRENT_BLOBS["installed_services_unit"]
    ):
        failures.append("file:installed_services_unit_drift")
    if _blob(doc, "dispatcher") != EXPECTED_CURRENT_BLOBS["dispatcher"]:
        failures.append("file:dispatcher_drift")
    if _blob(doc, "runtime_compose") != EXPECTED_CURRENT_BLOBS["compose"]:
        failures.append("runtime_source:compose_drift")
    if (
        _blob(doc, "runtime_services_unit")
        != EXPECTED_CURRENT_BLOBS["runtime_services_unit"]
    ):
        failures.append("runtime_source:services_unit_drift")
    if _blob(doc, "runtime_dispatcher") != EXPECTED_CURRENT_BLOBS["dispatcher"]:
        failures.append("runtime_source:dispatcher_drift")

    for name in (
        "registration_unit",
        "registration_guard",
        "trusted_lan_authority",
        "registration_certificate",
        "registration_private_key",
        "runtime_registration_unit",
        "runtime_registration_guard",
        "runtime_trusted_lan_authority",
        "trusted_lan_state",
    ):
        if not _absent(doc, name):
            failures.append(f"predecessor_residue:{name}")

    listeners = doc.get("listeners", {})
    if listeners.get("47110_tcp") != 0:
        failures.append("listener:47110_predecessor_not_closed")
    if listeners.get("47111_udp") != 0:
        failures.append("listener:47111_predecessor_not_closed")
    if listeners.get("47112_tcp") != 0:
        failures.append("listener:47112_not_closed")

    window = doc.get("pairing_window", {})
    if window.get("ok") is not True or window.get("state") != "CLOSED":
        failures.append("pairing_window:not_closed")
    if window.get("raw_locator_in_output") is not False:
        failures.append("pairing_window:not_public_safe")

    if doc.get("networkmanager", {}).get("ok") is not True:
        failures.append("networkmanager:trusted_product_lan_not_unique")

    database = doc.get("database", {})
    if database.get("ok") is not True or database.get("integrity") != "ok":
        failures.append("database:integrity")
    if database.get("registrations_table_present") is not True:
        failures.append("database:registrations_missing")
    if database.get("first_registration_table_present") is not False:
        failures.append("database:first_registration_predecessor_not_absent")

    if doc.get("candidate_image", {}).get("present") is not False:
        failures.append("candidate_image:preexisting")

    free = doc.get("root_free_bytes")
    if not isinstance(free, int) or free < MIN_FREE_BYTES:
        failures.append("storage:free_space")

    return failures


def public_summary(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "services": doc.get("services"),
        "containers": doc.get("containers"),
        "activation": {
            "env_ok": doc.get("activation", {}).get("env_ok"),
            "compose_env_ok": doc.get("activation", {}).get("compose_env_ok"),
            "compose_project": doc.get("activation", {}).get("compose_project"),
            "manager_image": doc.get("activation", {}).get("manager_image"),
        },
        "listeners": doc.get("listeners"),
        "pairing_window": doc.get("pairing_window"),
        "networkmanager": doc.get("networkmanager"),
        "database": doc.get("database"),
        "candidate_image": doc.get("candidate_image"),
        "versions": doc.get("versions"),
        "root_free_bytes": doc.get("root_free_bytes"),
        "runtime_file_blobs": {
            name: _blob(doc, name)
            for name in (
                "live_compose",
                "services_unit",
                "dispatcher",
                "runtime_compose",
                "runtime_services_unit",
                "runtime_dispatcher",
            )
        },
        "predecessor_absence": {
            name: _absent(doc, name)
            for name in (
                "registration_unit",
                "registration_guard",
                "trusted_lan_authority",
                "registration_certificate",
                "registration_private_key",
                "runtime_registration_unit",
                "runtime_registration_guard",
                "runtime_trusted_lan_authority",
                "trusted_lan_state",
            )
        },
    }


def run_preflight(args: argparse.Namespace) -> int:
    if args.confirm != CONFIRMATION:
        raise StopExecution("preflight_confirmation_invalid")
    root = evidence_root(Path(args.evidence_dir))
    doc = t1_probe(args.t1)
    write_private_json(root / "t1-candidate-readonly.json", doc)
    failures = accept_t1(doc)

    result = {
        "schema": SCHEMA,
        "status": "PASS" if not failures else "STOP",
        "current_source_head": CURRENT_SOURCE_HEAD,
        "target_source_head": TARGET_SOURCE_HEAD,
        "current_manager_image": CURRENT_MANAGER_IMAGE,
        "target_manager_image": TARGET_MANAGER_IMAGE,
        "target_file_blobs": EXPECTED_TARGET_BLOBS,
        "t1_target_sha256": sha256_bytes(args.t1.encode("utf-8")),
        "failures": failures,
        "t1": public_summary(doc),
        "authorization": {
            "t1_mutation": False,
            "service_stop_start": False,
            "container_recreate": False,
            "board_access": False,
            "upgrade_authorization_consumed": False,
        },
    }
    write_private_json(root / "result.json", result)

    if failures:
        print("R10_T1_CANDIDATE_PREFLIGHT=STOP")
        print("FAILURES=" + ",".join(failures))
        print("T1_MUTATION=false")
        print("SERVICE_STOP_START=false")
        print("BOARD_ACCESS=false")
        print("UPGRADE_AUTHORIZATION_CONSUMED=false")
        return 2

    database = doc.get("database", {})
    print("R10_T1_CANDIDATE_PREFLIGHT=PASS")
    print("CURRENT_MANAGER_SOURCE=" + CURRENT_SOURCE_HEAD)
    print("TARGET_MANAGER_SOURCE=" + TARGET_SOURCE_HEAD)
    print("CURRENT_MANAGER_IMAGE=" + CURRENT_MANAGER_IMAGE)
    print("TARGET_MANAGER_IMAGE=" + TARGET_MANAGER_IMAGE)
    print("NETWORKMANAGER_TRUSTED_LAN_SOURCE=PASS")
    print("DATABASE_INTEGRITY=PASS")
    print(
        "FIRST_REGISTRATION_TABLE_PRESENT="
        + str(database.get("first_registration_table_present")).lower()
    )
    print(
        "CURRENT_REGISTRATION_COUNT="
        + str(database.get("current_registration_count"))
    )
    print("CANDIDATE_IMAGE_PREEXISTING=false")
    print("ROOT_FREE_BYTES=" + str(doc.get("root_free_bytes")))
    print("T1_MUTATION=false")
    print("SERVICE_STOP_START=false")
    print("BOARD_ACCESS=false")
    print("UPGRADE_AUTHORIZATION_CONSUMED=false")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--t1", required=True)
    pre.add_argument("--evidence-dir", required=True)
    pre.add_argument("--confirm", required=True)
    pre.set_defaults(func=run_preflight)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except StopExecution as exc:
        print("STOP=" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
