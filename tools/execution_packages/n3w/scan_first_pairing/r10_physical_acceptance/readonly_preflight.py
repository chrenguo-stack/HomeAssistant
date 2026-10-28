#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

SCHEMA = "gh.n3w.scan-first-pair.r10-readonly-preflight/1"
R9_SOURCE_HEAD = "e299c937a7b89bb8a7b9a7432186ba46a416cd44"
R9_BUILD_HEAD = "d6c3e09464c7bcb8e30bdcbbc7a1cdc8fbcec303"
R9_ARTIFACT_ID = 12783234959
R9_ARTIFACT_NAME = "n3w-scan-first-pair-r9-e299c937-exact-source"
OUTER_SHA256 = "6b31001da3a4dff44f8c8cf605b885bcafcfd084d35969351938aa4904cc9995"
INNER_NAME = "n3w-scan-first-pair-r9-e299c937-exact-source.zip"
INNER_SHA256 = "b30bede249c90d4a50c9d3d779219bf9bf84a91960ec2a67332ef895e6a07dc1"
INNER_SIDECAR = INNER_NAME + ".sha256"
MANIFEST_SHA256 = "8db79ea5c7ac3b3c4b97a7852bf39447ff2f14d45880d4c5a0d8e4d5805cdf05"

EXPECTED_MEMBERS = {
    "MANIFEST.txt": (2782, MANIFEST_SHA256),
    "bootloader.bin": (22576, "1f107afc1cbfe6ae993f450a38f41dff33e672ed8c8f69b5a2cc1a15194e7ad3"),
    "firmware.bin": (1460144, "fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be"),
    "firmware.factory.bin": (1525680, "b734c343b3caf725c3991e6dc408b471a607f0c10cfe641346a78228b65c3bbf"),
    "firmware.ota.bin": (1460144, "fe11f5a81ce83e97fc0834114486a9cace26624977f9c4e0104c71687f4cc7be"),
    "flash_args": (167, "5dc4c4f6d568812713266e2604197cf4b68f87f49f8c6e9f7d28c84390faf713"),
    "ota_data_initial.bin": (8192, "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"),
    "partitions.bin": (3072, "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"),
}
EXPECTED_MANIFEST = {
    "BINDING_SCHEMA": "N3W_SCAN_TRIGGERED_FIRST_PAIRING_R9_EXACT_ARTIFACT_V1",
    "SOURCE_HEAD": R9_SOURCE_HEAD,
    "SOURCE_TREE": "e6e8290bdea3d9b09a70c598b4c3a9f5551540a7",
    "TARGET_CONFIG": "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml",
    "TARGET_BLOB_SHA": "176ef5a2839ba8d58b4675c5f5097eba5c662236",
    "TELEMETRY_PACKAGE_BLOB_SHA": "ce16f2389d146f9b25e95cbb628547e11ce36bd6",
    "TRANSPORT_PACKAGE_BLOB_SHA": "aa8dfa7e6be2ded398b8e90ab74a571e6a1b1ee2",
    "DISPLAY_PACKAGE_BLOB_SHA": "35bb9e4b839b298b0b478ff30675b51671f61bb4",
    "PRODUCT_COMPONENT_BLOB_SHA": "64073f3d33beaa04679c6d637fb4fca5b519652f",
    "REGISTRATION_PORTAL_BLOB_SHA": "e0333f30e4af5862e97edf5ac16b4ee941ae0508",
    "TLS_BOOTSTRAP_TRANSPORT_BLOB_SHA": "30a176c4b8ed66aa1d7c9adaa2576d8798fb3032",
    "PAIRING_CLIENT_BLOB_SHA": "d5768aed73c76f2764b8619f877d952b3da7f83e",
    "PAIRING_NVS_BLOB_SHA": "059380bdccfb12204ccf8cadaff2ea87422ba926",
    "R8_MANAGER_E2E_TEST_BLOB_SHA": "14b284c5114db901722ff068124ed1f4700982f0",
    "R8_SAFETY_CONTRACT_BLOB_SHA": "d617a3a3ad834b78ad924d4b55abbb715cbbc141",
    "FONT_FETCH_SCRIPT_BLOB_SHA": "d752a50acf6131919bf99e29889020e3fc1fb4e0",
    "PYTHON_VERSION": "3.11",
    "ESPHOME_VERSION": "2026.4.3",
    "ESP_IDF_VERSION": "5.5.4",
    "WORKFLOW_TRIGGER_SHA": R9_BUILD_HEAD,
    "WORKFLOW_RUN_ID": "40612774339",
    "R4_CONTRACT": "PASS",
    "R5_CONTRACT": "PASS",
    "R6_CONTRACT": "PASS",
    "R7_CONTRACT": "PASS",
    "R8_SAFETY_CONTRACT": "PASS",
    "R8_MANAGER_E2E": "PASS",
    "BINARY_DEHARNESS_PROOF": "PASS",
    "REGISTRATION_BINARY_POSITIVE_CONTROLS": "PASS",
    "HARDWARE_SPI_BUILD_BINDING": "PASS",
}

BOOTLOADER_OFFSET = 0x000000
PARTITION_OFFSET = 0x008000
OTADATA_OFFSET = 0x009000
PHY_OFFSET = 0x00B000
APP0_OFFSET = 0x010000
APP1_OFFSET = 0x3D0000
NVS_OFFSET = 0x790000
PHY_SIZE = 0x1000
SLOT_SIZE = 0x3C0000
NVS_SIZE = 0x70000
FACTORY_SIZE = EXPECTED_MEMBERS["firmware.factory.bin"][0]
FLASH_SECTOR_SIZE = 0x1000
FACTORY_ERASE_SPAN = ((FACTORY_SIZE + FLASH_SECTOR_SIZE - 1) // FLASH_SECTOR_SIZE) * FLASH_SECTOR_SIZE
APP_SIZE = EXPECTED_MEMBERS["firmware.bin"][0]
FLASH_SIZE_TEXT = "8MB"
PREFLIGHT_CONFIRMATION = "R10 READONLY PREFLIGHT: YES"

MAC_RE = re.compile(r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")
ESPTOOL_VERSION_RE = re.compile(r"\besptool(?:\.py)?\s+v?(\d+)\.(\d+)\.(\d+)\b", re.I)
FLASH_8MB_RE = re.compile(r"Detected flash size:\s*8\s*MB\b", re.I)
SECURE_BOOT_DISABLED_RE = re.compile(r"Secure Boot:\s*Disabled\b", re.I)
FLASH_ENCRYPTION_DISABLED_RE = re.compile(r"Flash Encryption:\s*Disabled\b", re.I)

T1_PROBE = r'''
import hashlib
import ipaddress
import json
import os
import sqlite3
import subprocess
from pathlib import Path

def run(argv, timeout=20):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)
    except Exception as exc:
        return {"rc": 127, "out": "", "err": type(exc).__name__}
    return {"rc": p.returncode, "out": p.stdout.strip(), "err": p.stderr.strip()[:160]}

def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def service(name):
    active = run(["systemctl", "is-active", name])
    load = run(["systemctl", "show", "-p", "LoadState", "--value", name])
    result = run(["systemctl", "show", "-p", "Result", "--value", name])
    return {
        "active": active["out"] if active["rc"] == 0 else "inactive",
        "load_state": load["out"] if load["rc"] == 0 else None,
        "result": result["out"] if result["rc"] == 0 else None,
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
        "image": str(config.get("Image") or ""),
        "restart_count": int(doc.get("RestartCount") or 0),
        "started_at": str(state.get("StartedAt") or ""),
        "pairing_disabled": env.get("GH_N3W_PRODUCT_PAIRING_ENABLED") == "false" if service_name == "manager" else None,
        "runtime_enabled": env.get("GH_N3W_RUNTIME_ENABLED") == "true" if service_name == "manager" else None,
        "advertised_host_auto": env.get("GH_N3W_PAIRING_ADVERTISED_HOST") == "auto" if service_name == "manager" else None,
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
        if not fields:
            continue
        local = fields[3] if len(fields) > 3 else ""
        if local.endswith(needle):
            count += 1
    return count

def trusted_lan():
    path = Path("/run/n3wfc4-trusted-lan/state.json")
    try:
        if not path.is_file() or path.is_symlink():
            return {"ok": False}
        doc = json.loads(path.read_text(encoding="utf-8"))
        subnet = ipaddress.ip_network(str(doc.get("subnet")), strict=True)
        ok = (
            doc.get("schema") == "gh.trusted-product-lan/1"
            and doc.get("available") is True
            and doc.get("interface") == "eth0"
            and isinstance(subnet, ipaddress.IPv4Network)
            and subnet.is_private
        )
        return {
            "ok": ok,
            "interface": doc.get("interface"),
            "subnet_sha256": sha(str(subnet)),
            "available": doc.get("available") is True,
        }
    except Exception:
        return {"ok": False}

def manager_exec(manager_id, code):
    return run(["docker", "exec", manager_id, "python3", "-B", "-c", code])

manager_query = container("manager")
broker_query = container("broker")
ha_query = container("homeassistant")

manager_id_query = run([
    "docker", "ps",
    "--filter", "label=com.docker.compose.project=n3wfc4",
    "--filter", "label=com.docker.compose.service=manager",
    "-q",
])
manager_ids = [line.strip() for line in manager_id_query["out"].splitlines() if line.strip()]
manager_id = manager_ids[0] if len(manager_ids) == 1 else ""

capabilities = {"ok": False}
db = {"ok": False}
window = {"ok": False}
if manager_id:
    cap_code = r"""
import json
from greenhouse_manager.runtime.n3w_first_registration_transaction import FIRST_REGISTRATION_TTL_SECONDS, FirstRegistrationTransactionService
from greenhouse_manager.runtime.n3w_registration_runtime import RegistrationNetworkRuntime
from greenhouse_manager.runtime.n3w_dynamic_pairing_window import DynamicPairingWindowController
print(json.dumps({
  "ttl_1800": FIRST_REGISTRATION_TTL_SECONDS == 1800,
  "transaction_service": FirstRegistrationTransactionService is not None,
  "registration_runtime": RegistrationNetworkRuntime is not None,
  "identity_bound_window": hasattr(DynamicPairingWindowController, "open_first_registration"),
}, sort_keys=True))
"""
    c = manager_exec(manager_id, cap_code)
    if c["rc"] == 0:
        try:
            raw = json.loads(c["out"])
            capabilities = {
                "ok": all(raw.values()),
                "ttl_1800": raw.get("ttl_1800") is True,
                "transaction_service": raw.get("transaction_service") is True,
                "registration_runtime": raw.get("registration_runtime") is True,
                "identity_bound_window": raw.get("identity_bound_window") is True,
            }
        except Exception:
            pass

    db_code = r"""
import json, sqlite3
path="/var/lib/greenhouse-manager/manager/manager-state.sqlite3"
con=sqlite3.connect("file:"+path+"?mode=ro&immutable=1", uri=True)
con.row_factory=sqlite3.Row
tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
need={"first_registration_attempts","registrations","pairing_sessions","registration_events","node_id_leases"}
if not need.issubset(tables):
    raise SystemExit(3)
by_state={r["state"]:r["n"] for r in con.execute("SELECT state,COUNT(*) n FROM first_registration_attempts GROUP BY state")}
unresolved=con.execute("""SELECT COUNT(*) FROM first_registration_attempts
WHERE state='ACTIVE' OR (state IN ('EXPIRED','RESTART_INVALIDATED') AND cleanup_state!='COMPLETE')""").fetchone()[0]
current_regs=con.execute("SELECT COUNT(*) FROM registrations WHERE retired_at IS NULL").fetchone()[0]
print(json.dumps({
 "tables_ok":True,
 "first_registration_by_state":by_state,
 "unresolved_first_registration":unresolved,
 "current_registration_count":current_regs,
},sort_keys=True))
"""
    d = manager_exec(manager_id, db_code)
    if d["rc"] == 0:
        try:
            raw = json.loads(d["out"])
            db = {"ok": raw.get("tables_ok") is True, **raw}
        except Exception:
            pass

    w = run(["docker", "exec", manager_id, "greenhouse-manager-pairing", "window-status"])
    if w["rc"] == 0:
        try:
            raw = json.loads(w["out"])
            window = {
                "ok": raw.get("accepted") is True,
                "state": raw.get("pairing_window_state"),
                "raw_locator_in_output": raw.get("raw_locator_in_output"),
            }
        except Exception:
            pass

report = {
    "schema": "gh.n3w.r10-t1-readonly/1",
    "status": "PASS",
    "services": {
        "broker_activation": service("n3wfc4-broker-activation.service"),
        "services_activation": service("n3wfc4-services-activation.service"),
        "broker_guard": service("n3wfc4-broker-ingress-guard.service"),
        "registration_guard": service("n3wfc4-registration-ingress-guard.service"),
    },
    "containers": {
        "broker": broker_query,
        "manager": manager_query,
        "homeassistant": ha_query,
    },
    "trusted_lan": trusted_lan(),
    "listeners": {
        "47110_tcp": listener_count("tcp", 47110),
        "47111_udp": listener_count("udp", 47111),
        "47112_tcp": listener_count("tcp", 47112),
    },
    "manager_capabilities": capabilities,
    "database": db,
    "pairing_window": window,
    "mutation": False,
    "container_recreate": False,
    "service_restart": False,
    "file_write": False,
}
print(json.dumps(report, sort_keys=True, separators=(",", ":")))
'''

class StopExecution(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line:
            continue
        if "=" not in line:
            raise StopExecution("artifact_manifest_non_key_value")
        key, value = line.split("=", 1)
        if not key or key in out:
            raise StopExecution("artifact_manifest_duplicate_or_empty_key")
        out[key] = value
    return out


def validate_artifact(outer_path: Path, extract_root: Path) -> dict[str, Path]:
    if not outer_path.is_file() or outer_path.is_symlink():
        raise StopExecution("artifact_outer_missing_or_unsafe")
    if outer_path.stat().st_size != 4484150:
        raise StopExecution("artifact_outer_size_mismatch")
    if sha256_file(outer_path) != OUTER_SHA256:
        raise StopExecution("artifact_outer_sha256_mismatch")
    with zipfile.ZipFile(outer_path, "r") as outer:
        names = [n for n in outer.namelist() if not n.endswith("/")]
        if names != [INNER_NAME, INNER_SIDECAR]:
            raise StopExecution("artifact_outer_member_set_mismatch")
        inner_bytes = outer.read(INNER_NAME)
        sidecar = outer.read(INNER_SIDECAR).decode("utf-8")
    if sha256_bytes(inner_bytes) != INNER_SHA256:
        raise StopExecution("artifact_inner_sha256_mismatch")
    expected_sidecar = f"{INNER_SHA256}  {INNER_NAME}\n"
    if sidecar != expected_sidecar:
        raise StopExecution("artifact_inner_sidecar_mismatch")
    inner_path = extract_root / INNER_NAME
    inner_path.parent.mkdir(parents=True, exist_ok=True)
    inner_path.write_bytes(inner_bytes)
    files_root = extract_root / "release"
    files_root.mkdir()
    with zipfile.ZipFile(inner_path, "r") as inner:
        names = [n for n in inner.namelist() if not n.endswith("/")]
        if set(names) != set(EXPECTED_MEMBERS) or len(names) != len(EXPECTED_MEMBERS):
            raise StopExecution("artifact_release_member_set_mismatch")
        for info in inner.infolist():
            if info.is_dir():
                continue
            if info.date_time != (1980, 1, 1, 0, 0, 0):
                raise StopExecution("artifact_release_timestamp_mismatch")
            if info.compress_type != zipfile.ZIP_STORED:
                raise StopExecution("artifact_release_compression_mismatch")
            data = inner.read(info.filename)
            size, digest = EXPECTED_MEMBERS[info.filename]
            if len(data) != size or sha256_bytes(data) != digest:
                raise StopExecution(f"artifact_member_mismatch:{info.filename}")
            target = files_root / info.filename
            target.write_bytes(data)
    manifest = parse_manifest((files_root / "MANIFEST.txt").read_text(encoding="utf-8"))
    for key, value in EXPECTED_MANIFEST.items():
        if manifest.get(key) != value:
            raise StopExecution(f"artifact_manifest_binding_mismatch:{key}")
    for name, (size, digest) in EXPECTED_MEMBERS.items():
        key = name.upper().replace(".", "_") + "_SHA256"
        size_key = name.upper().replace(".", "_") + "_SIZE"
        if name == "MANIFEST.txt":
            continue
        if manifest.get(key) != digest or manifest.get(size_key) != str(size):
            raise StopExecution(f"artifact_manifest_member_mismatch:{name}")
    return {name: files_root / name for name in EXPECTED_MEMBERS}


def run_capture(
    argv: list[str] | tuple[str, ...],
    *,
    input_bytes: bytes | None = None,
    timeout: int = 180,
    port: str | None = None,
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
        cmd = " ".join("<PORT>" if port and a == port else a for a in argv)
        raise StopExecution(f"command_failed:{Path(argv[0]).name}:{p.returncode}:{cmd}")
    return p


def esptool_base() -> list[str]:
    return [sys.executable, "-m", "esptool"]


def verify_esptool() -> str:
    p = run_capture(esptool_base() + ["version"])
    text = (p.stdout + p.stderr).decode("utf-8", "replace")
    m = ESPTOOL_VERSION_RE.search(text)
    if not m:
        raise StopExecution("esptool_version_unparseable")
    version = tuple(map(int, m.groups()))
    if version[0] != 5:
        raise StopExecution("esptool_major_must_be_5")
    return ".".join(map(str, version))


def verify_factory_image(path: Path) -> None:
    p = run_capture(esptool_base() + ["--chip", "esp32c6", "image-info", str(path)])
    text = (p.stdout + p.stderr).decode("utf-8", "replace").upper()
    if "ESP32-C6" not in text:
        raise StopExecution("factory_image_not_esp32c6")


def validate_target(target: str) -> None:
    if (
        not target
        or target.strip() != target
        or any(c.isspace() for c in target)
        or target.startswith("-")
        or any(x in target.casefold() for x in ("placeholder", "example", "<", ">"))
    ):
        raise StopExecution("t1_target_invalid")


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
    p = run_capture(argv, input_bytes=T1_PROBE.encode("utf-8"), timeout=150)
    try:
        doc = json.loads(p.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("t1_probe_json_invalid") from exc
    if not isinstance(doc, dict) or doc.get("status") != "PASS":
        raise StopExecution("t1_probe_invalid")
    return doc


def accept_t1(doc: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for name in ("broker_activation", "services_activation", "broker_guard", "registration_guard"):
        record = doc.get("services", {}).get(name, {})
        if record.get("active") != "active" or record.get("load_state") != "loaded":
            failures.append(f"service:{name}")
    for name in ("broker", "manager", "homeassistant"):
        record = doc.get("containers", {}).get(name, {})
        if record.get("ok") is not True or record.get("count") != 1:
            failures.append(f"container:{name}")
    manager = doc.get("containers", {}).get("manager", {})
    if manager.get("pairing_disabled") is not True:
        failures.append("manager:durable_pairing_not_disabled")
    if manager.get("runtime_enabled") is not True:
        failures.append("manager:n3w_runtime_disabled")
    if manager.get("advertised_host_auto") is not True:
        failures.append("manager:advertised_host_not_auto")
    if doc.get("trusted_lan", {}).get("ok") is not True:
        failures.append("trusted_lan")
    listeners = doc.get("listeners", {})
    if listeners.get("47110_tcp") != 1:
        failures.append("listener:47110")
    if listeners.get("47111_udp") != 1:
        failures.append("listener:47111")
    if listeners.get("47112_tcp") != 0:
        failures.append("listener:47112_not_idle_closed")
    if doc.get("manager_capabilities", {}).get("ok") is not True:
        failures.append("manager:scan_first_registration_capability")
    database = doc.get("database", {})
    if database.get("ok") is not True:
        failures.append("manager:database_schema")
    if database.get("unresolved_first_registration") != 0:
        failures.append("manager:predecessor_unresolved")
    window = doc.get("pairing_window", {})
    if window.get("ok") is not True or window.get("state") != "CLOSED":
        failures.append("manager:pairing_window_not_closed")
    if window.get("raw_locator_in_output") is not False:
        failures.append("manager:window_output_not_public_safe")
    return failures


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


def write_private_bytes(path: Path, data: bytes) -> None:
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise StopExecution("private_write_short")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def write_private_json(path: Path, doc: Any) -> None:
    write_private_bytes(path, (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def hardware_hash_from_mac(mac: str) -> str:
    compact = mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("rom_mac_invalid")
    hardware_id = "ghw-c6-" + compact
    return sha256_bytes(hardware_id.encode("utf-8"))


def board_security(port: str) -> dict[str, Any]:
    if not port or any(c.isspace() for c in port):
        raise StopExecution("serial_port_invalid")
    p = run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port,
            "--before", "default-reset", "--after", "no-reset", "--no-stub",
            "get-security-info",
        ],
        timeout=60,
        port=port,
    )
    text = (p.stdout + p.stderr).decode("utf-8", "replace")
    if "ESP32-C6" not in text.upper():
        raise StopExecution("board_not_esp32c6")
    m = MAC_RE.search(text)
    if not m:
        raise StopExecution("board_rom_mac_missing")
    if SECURE_BOOT_DISABLED_RE.search(text) is None:
        raise StopExecution("secure_boot_not_disabled")
    if FLASH_ENCRYPTION_DISABLED_RE.search(text) is None:
        raise StopExecution("flash_encryption_not_disabled")
    flash = run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port,
            "--before", "no-reset", "--after", "no-reset", "--no-stub",
            "flash-id",
        ],
        timeout=60,
        port=port,
    )
    flash_text = (flash.stdout + flash.stderr).decode("utf-8", "replace")
    if FLASH_8MB_RE.search(flash_text) is None:
        raise StopExecution("flash_size_not_8mb")
    return {
        "hardware_id_sha256": hardware_hash_from_mac(m.group(1)),
        "port_sha256": sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": FLASH_SIZE_TEXT,
        "secure_boot": False,
        "flash_encryption": False,
    }


def read_rom_region(port: str, offset: int, size: int, destination: Path) -> str:
    p = run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port,
            "--before", "no-reset", "--after", "no-reset", "--no-stub",
            "read-flash", "--flash-size", FLASH_SIZE_TEXT,
            hex(offset), hex(size), str(destination),
        ],
        timeout=180,
        port=port,
    )
    del p
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash_readback_size_mismatch")
    destination.chmod(0o600)
    return sha256_file(destination)


def read_stub_start(port: str, offset: int, size: int, destination: Path) -> str:
    run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port, "--baud", "460800",
            "--before", "no-reset", "--after", "no-reset-stub",
            "read-flash", hex(offset), hex(size), str(destination),
        ],
        timeout=240,
        port=port,
    )
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash_readback_size_mismatch")
    destination.chmod(0o600)
    return sha256_file(destination)


def read_stub_continue(port: str, offset: int, size: int, destination: Path) -> str:
    run_capture(
        esptool_base() + [
            "--chip", "esp32c6", "--port", port, "--baud", "460800",
            "--before", "no-reset-no-sync", "--after", "no-reset-stub",
            "read-flash", hex(offset), hex(size), str(destination),
        ],
        timeout=360,
        port=port,
    )
    if not destination.is_file() or destination.stat().st_size != size:
        raise StopExecution("flash_readback_size_mismatch")
    destination.chmod(0o600)
    return sha256_file(destination)


def board_probe(port: str, files: dict[str, Path], root: Path) -> dict[str, Any]:
    security = board_security(port)

    partition_path = root / "partition-table-current.bin"
    partition_sha = read_rom_region(
        port,
        PARTITION_OFFSET,
        EXPECTED_MEMBERS["partitions.bin"][0],
        partition_path,
    )
    if partition_sha != EXPECTED_MEMBERS["partitions.bin"][1]:
        raise StopExecution("current_partition_table_not_r9_compatible")

    factory_backup = root / "factory-erase-span-prewrite.bin"
    app1_backup = root / "app1-full-slot-prewrite.bin"
    nvs_backup = root / "nvs-prewrite.bin"

    factory_erase_span_sha = read_stub_start(port, 0, FACTORY_ERASE_SPAN, factory_backup)
    app1_sha = read_stub_continue(port, APP1_OFFSET, SLOT_SIZE, app1_backup)
    nvs_sha = read_stub_continue(port, NVS_OFFSET, NVS_SIZE, nvs_backup)

    factory_erase_span_data = factory_backup.read_bytes()
    factory_data = factory_erase_span_data[:FACTORY_SIZE]
    factory_sha = sha256_bytes(factory_data)
    app1_data = app1_backup.read_bytes()
    expected_app = files["firmware.bin"].read_bytes()
    expected_factory = files["firmware.factory.bin"].read_bytes()

    phy = factory_data[PHY_OFFSET:PHY_OFFSET + PHY_SIZE]
    app0 = factory_data[APP0_OFFSET:APP0_OFFSET + APP_SIZE]
    app1 = app1_data[:APP_SIZE]

    phy_all_ff = phy == b"\xff" * PHY_SIZE
    app0_matches = sha256_bytes(app0) == EXPECTED_MEMBERS["firmware.bin"][1]
    app1_matches = sha256_bytes(app1) == EXPECTED_MEMBERS["firmware.bin"][1]
    direct_factory_route_eligible = phy_all_ff and app1_matches

    return {
        **security,
        "partition_table_sha256": partition_sha,
        "factory_covered_range_sha256": factory_sha,
        "factory_erase_span_size": FACTORY_ERASE_SPAN,
        "factory_erase_span_sha256": factory_erase_span_sha,
        "app1_full_slot_sha256": app1_sha,
        "nvs_sha256": nvs_sha,
        "phy_sha256": sha256_bytes(phy),
        "phy_all_ff": phy_all_ff,
        "app0_r9_application_match": app0_matches,
        "app1_r9_application_match": app1_matches,
        "direct_factory_route_eligible": direct_factory_route_eligible,
        "factory_image_phy_all_ff": expected_factory[PHY_OFFSET:PHY_OFFSET + PHY_SIZE] == b"\xff" * PHY_SIZE,
        "application_started_after_preflight": False,
        "backup_files_private": True,
    }


def public_t1_summary(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "services": doc.get("services"),
        "containers": doc.get("containers"),
        "trusted_lan": doc.get("trusted_lan"),
        "listeners": doc.get("listeners"),
        "manager_capabilities": doc.get("manager_capabilities"),
        "database": doc.get("database"),
        "pairing_window": doc.get("pairing_window"),
    }


def run_preflight(args: argparse.Namespace) -> int:
    if args.confirm != PREFLIGHT_CONFIRMATION:
        raise StopExecution("preflight_confirmation_invalid")
    root = evidence_root(Path(args.evidence_dir))
    with tempfile.TemporaryDirectory(prefix="n3w-r10-artifact-") as td:
        files = validate_artifact(Path(args.artifact_zip), Path(td))
        esptool_version = verify_esptool()
        verify_factory_image(files["firmware.factory.bin"])
        t1 = t1_probe(args.t1)
        t1_failures = accept_t1(t1)
        if t1_failures:
            write_private_json(root / "t1-readonly.json", t1)
            raise StopExecution("t1_preflight_failed:" + ",".join(t1_failures))
        board = board_probe(args.port, files, root)

    result = {
        "schema": SCHEMA,
        "status": "PASS" if board["direct_factory_route_eligible"] else "STOP_ROUTE_REVIEW_REQUIRED",
        "created_at": utc_now(),
        "authorization": {
            "gate": "N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_PHYSICAL_ACCEPTANCE_EXECUTION_20261028_01",
            "physical_authorization_granted": True,
            "write_authorization_consumed": False,
            "flash_write": False,
            "nvs_write": False,
            "t1_mutation": False,
        },
        "artifact": {
            "source_head": R9_SOURCE_HEAD,
            "build_head": R9_BUILD_HEAD,
            "artifact_id": R9_ARTIFACT_ID,
            "artifact_name": R9_ARTIFACT_NAME,
            "outer_sha256": OUTER_SHA256,
            "inner_sha256": INNER_SHA256,
            "factory_sha256": EXPECTED_MEMBERS["firmware.factory.bin"][1],
            "firmware_sha256": EXPECTED_MEMBERS["firmware.bin"][1],
            "partition_sha256": EXPECTED_MEMBERS["partitions.bin"][1],
        },
        "esptool_version": esptool_version,
        "t1_target_sha256": sha256_bytes(args.t1.encode("utf-8")),
        "t1": public_t1_summary(t1),
        "board": board,
        "write_route": {
            "direct_factory_route_eligible": board["direct_factory_route_eligible"],
            "reason_if_not_eligible": (
                None
                if board["direct_factory_route_eligible"]
                else "R9 factory would not normalize current PHY/app1 state; review a protected normalized R9 route before mutation"
            ),
            "flat_flash_args_allowed": False,
            "full_flash_erase_allowed": False,
            "nvs_erase_allowed": False,
        },
        "private_evidence": {
            "directory_sha256": sha256_bytes(str(root).encode("utf-8")),
            "raw_board_backups_published": False,
            "raw_t1_locator_published": False,
        },
    }
    write_private_json(root / "result.json", result)
    write_private_json(root / "t1-readonly.json", t1)

    print("R10_READONLY_PREFLIGHT=" + result["status"])
    print("T1_PREFLIGHT=PASS")
    print("BOARD_PREFLIGHT=PASS")
    print("ARTIFACT_BINDING=PASS")
    print("HARDWARE_ID_SHA256=" + str(board["hardware_id_sha256"]))
    print("PHY_ALL_FF=" + str(board["phy_all_ff"]).lower())
    print("APP0_R9_MATCH=" + str(board["app0_r9_application_match"]).lower())
    print("APP1_R9_MATCH=" + str(board["app1_r9_application_match"]).lower())
    print("DIRECT_FACTORY_ROUTE_ELIGIBLE=" + str(board["direct_factory_route_eligible"]).lower())
    print("FLASH_WRITE=false")
    print("NVS_WRITE=false")
    print("T1_MUTATION=false")
    print("WRITE_AUTHORIZATION_CONSUMED=false")
    if not board["direct_factory_route_eligible"]:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--t1", required=True)
    pre.add_argument("--port", required=True)
    pre.add_argument("--artifact-zip", required=True)
    pre.add_argument("--evidence-dir", required=True)
    pre.add_argument("--confirm", required=True)
    pre.set_defaults(func=run_preflight)
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except StopExecution as exc:
        print("STOP=" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
