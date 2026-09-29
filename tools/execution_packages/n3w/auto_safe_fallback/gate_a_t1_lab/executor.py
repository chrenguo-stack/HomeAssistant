#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_PREFLIGHT = "n3w.auto-safe-fallback.gate-a-t1-lab-preflight/1"
SCHEMA_ACTIVE = "n3w.auto-safe-fallback.gate-a-t1-lab-active/1"
BUNDLE_SCHEMA = "n3w.auto-safe-fallback.gate-a-private-build/1"
PROFILE_SCHEMA = "n3w.auto-safe-fallback.gate-a-private-lab-profile/1"

APPLICATION_SIZE = 1140352
APPLICATION_SHA256 = "77b0fd6a98c3e837d3543eebdd30b86354790847d0c78cdab7e96f0d7d66a8ad"
OTADATA_SIZE = 8192
OTADATA_SHA256 = "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
CA_CERT_SHA256 = "66ca928aaab07eaef6aebf0a7dec9b8a0e0fac9a9d719f4e1354ea575eed0a66"
SERVER_CERT_SHA256 = "c33bdac940da24cff4de772ff0478f0f069a3ab956dc03b1557738c4f640af4e"
SERVER_KEY_SHA256 = "29ee45ca617fb5e4e854081e77a9ae4c468c3b07fb1d206cb0d61d86d8cbee61"
SOURCE_HEAD = "8210cf7b53e9ec934d145f1c15e9619579c923be"
SOURCE_TREE = "5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c"
TARGET_BLOB = "7279271d469958940c2b51aa4a80602078470891"
PATCH_BLOB = "49570a83ead08158d4d99c385740fa6d646b5e3d"
BROKER_PORT = 18883
TLS_SERVER_NAME = "n3w-gate-a.invalid"
CONTAINER_NAME = "n3w-gate-a-77b0fd6a"
REMOTE_ROOT = "/run/n3w-gate-a-77b0fd6a"
ACTIVATE_CONFIRMATION = "N3W_GATE_A_T1_LAB_MUTATION_AUTHORIZED"
CLEANUP_CONFIRMATION = "N3W_GATE_A_T1_LAB_CLEANUP_AUTHORIZED"
PREFLIGHT_MAX_AGE_SECONDS = 900


class StopExecution(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def private_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def require_private_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise StopExecution(f"private file is missing or unsafe: {path.name}")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise StopExecution(f"private file is group/world accessible: {path.name}")


def validate_bundle(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise StopExecution("private bundle directory is missing or unsafe")
    if stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise StopExecution("private bundle directory mode must be 0700")

    manifest_path = root / "manifest.json"
    profile_path = root / "lab/profile.json"
    app = root / "artifact/firmware.bin"
    ota = root / "artifact/ota_data_initial.bin"
    ca = root / "lab/ca.crt"
    cert = root / "lab/server.crt"
    key = root / "lab/server.key"
    for path in (manifest_path, profile_path, app, ota, ca, cert, key):
        require_private_file(path)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("private bundle JSON is unreadable") from exc

    if manifest.get("schema") != BUNDLE_SCHEMA or manifest.get("status") != "PASS":
        raise StopExecution("private build manifest is not PASS")
    source = manifest.get("source")
    firmware = manifest.get("firmware")
    lab = manifest.get("lab")
    boundary = manifest.get("execution_boundary")
    if not all(isinstance(value, dict) for value in (source, firmware, lab, boundary)):
        raise StopExecution("private build manifest is incomplete")
    if source.get("head") != SOURCE_HEAD or source.get("tree") != SOURCE_TREE:
        raise StopExecution("private build source binding drifted")
    if source.get("target_blob") != TARGET_BLOB or source.get("patch_blob") != PATCH_BLOB:
        raise StopExecution("private build blob binding drifted")
    if firmware.get("application_size") != APPLICATION_SIZE or firmware.get("application_sha256") != APPLICATION_SHA256:
        raise StopExecution("private application manifest binding drifted")
    if firmware.get("otadata_size") != OTADATA_SIZE or firmware.get("otadata_sha256") != OTADATA_SHA256:
        raise StopExecution("private otadata manifest binding drifted")
    if lab.get("broker_port") != BROKER_PORT or lab.get("tls_server_name") != TLS_SERVER_NAME:
        raise StopExecution("private lab endpoint binding drifted")
    if lab.get("ca_cert_sha256") != CA_CERT_SHA256:
        raise StopExecution("private CA manifest binding drifted")
    if lab.get("server_cert_sha256") != SERVER_CERT_SHA256:
        raise StopExecution("private server certificate binding drifted")
    if lab.get("server_key_sha256") != SERVER_KEY_SHA256:
        raise StopExecution("private server key manifest binding drifted")
    if any(boundary.get(key_name) is not False for key_name in (
        "board_access",
        "board_flash",
        "t1_mutation",
        "production_broker_mutation",
        "manager_mutation",
        "dynsec_mutation",
        "product_nvs_write",
    )):
        raise StopExecution("private build execution boundary drifted")

    if app.stat().st_size != APPLICATION_SIZE or sha256_file(app) != APPLICATION_SHA256:
        raise StopExecution("private application file binding mismatch")
    if ota.stat().st_size != OTADATA_SIZE or sha256_file(ota) != OTADATA_SHA256:
        raise StopExecution("private otadata file binding mismatch")
    if sha256_file(ca) != CA_CERT_SHA256:
        raise StopExecution("private CA file binding mismatch")
    if sha256_file(cert) != SERVER_CERT_SHA256:
        raise StopExecution("private server certificate file binding mismatch")
    if sha256_file(key) != SERVER_KEY_SHA256:
        raise StopExecution("private server key file binding mismatch")

    if profile.get("schema") != PROFILE_SCHEMA:
        raise StopExecution("private lab profile schema mismatch")
    if str(profile.get("broker_port")) != str(BROKER_PORT):
        raise StopExecution("private lab profile port mismatch")
    if profile.get("tls_server_name") != TLS_SERVER_NAME:
        raise StopExecution("private lab profile TLS name mismatch")
    username = profile.get("mqtt_username")
    password = profile.get("mqtt_password")
    client_id = profile.get("mqtt_client_id")
    if not isinstance(username, str) or not username.startswith("gate_a_"):
        raise StopExecution("private lab username is invalid")
    if not isinstance(password, str) or len(password) < 24:
        raise StopExecution("private lab password is invalid")
    if not isinstance(client_id, str) or not client_id.startswith("gate-a-"):
        raise StopExecution("private lab client id is invalid")

    raw_app = app.read_bytes()
    for label, value in (("username", username), ("password", password), ("client_id", client_id), ("tls_name", TLS_SERVER_NAME)):
        if value.encode("utf-8") not in raw_app:
            raise StopExecution(f"private firmware/profile {label} binding not observed")

    for field in ("restore_host", "live_alias", "blackhole_ip", "interface"):
        if not isinstance(profile.get(field), str) or not profile[field]:
            raise StopExecution(f"private lab profile field missing: {field}")
    try:
        prefixlen = int(profile.get("prefixlen"))
        restore = ipaddress.ip_interface(f"{profile['restore_host']}/{prefixlen}")
        live = ipaddress.ip_address(profile["live_alias"])
        blackhole = ipaddress.ip_address(profile["blackhole_ip"])
    except (TypeError, ValueError) as exc:
        raise StopExecution("private lab profile address binding is invalid") from exc
    if restore.version != 4 or live.version != 4 or blackhole.version != 4:
        raise StopExecution("Gate A T1 lab requires IPv4")
    if live not in restore.network or blackhole not in restore.network:
        raise StopExecution("Gate A T1 lab candidates left restore subnet")
    if len({str(restore.ip), str(live), str(blackhole)}) != 3:
        raise StopExecution("Gate A T1 lab addresses are not distinct")

    return {
        "root": root,
        "manifest": manifest,
        "profile": profile,
        "profile_sha256": sha256_file(profile_path),
        "app": app,
        "ota": ota,
        "ca": ca,
        "cert": cert,
        "key": key,
    }


def validate_target(target: str) -> None:
    if not target or target.strip() != target or any(ch.isspace() for ch in target):
        raise StopExecution("T1 SSH target is empty or contains whitespace")
    if any(marker in target.casefold() for marker in ("placeholder", "<", ">")):
        raise StopExecution("T1 SSH target looks like a placeholder")


def ssh_base(target: str) -> list[str]:
    return [
        "ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=2", target,
    ]


def scp_base() -> list[str]:
    return [
        "scp", "-q", "-p", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1",
    ]


def run_capture(argv: list[str], timeout: int = 60) -> str:
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StopExecution(f"command timed out after {timeout}s") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise StopExecution(f"command failed rc={result.returncode}: {detail[:600]}")
    return result.stdout


def remote_python(target: str, source: str, args: list[str], timeout: int = 60) -> str:
    payload = base64.b64encode(source.encode("utf-8")).decode("ascii")
    args_payload = base64.b64encode(
        json.dumps(args, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    launcher = (
        "import base64,json,sys;"
        "sys.argv=['remote']+json.loads(base64.b64decode(" + repr(args_payload) + "));"
        "exec(base64.b64decode(" + repr(payload) + "))"
    )
    remote_command = "python3 -c " + shlex.quote(launcher)
    return run_capture(ssh_base(target) + [remote_command], timeout=timeout)


REMOTE_PREFLIGHT = r"""
import ipaddress
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time

profile = json.loads(sys.argv[1])
container_name = sys.argv[2]


def run(argv, timeout=10):
    p = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def load_json(argv):
    rc, out, err = run(argv)
    if rc != 0:
        raise RuntimeError(err[:300])
    return json.loads(out)


def arp_claimed(dev, local_mac, candidate):
    packet = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0806))
    packet.bind((dev, 0))
    packet.settimeout(0.35)
    src = bytes.fromhex(local_mac.replace(":", ""))
    dst = b"\xff" * 6
    target = socket.inet_aton(candidate)
    frame = (
        dst + src + b"\x08\x06" + struct.pack("!HHBBH", 1, 0x0800, 6, 4, 1)
        + src + b"\x00\x00\x00\x00" + b"\x00" * 6 + target
    )
    try:
        for _ in range(2):
            packet.send(frame)
            end = time.monotonic() + 0.35
            while time.monotonic() < end:
                try:
                    data = packet.recv(2048)
                except socket.timeout:
                    break
                if len(data) >= 42 and data[12:14] == b"\x08\x06" and data[20:22] == b"\x00\x02" and data[28:32] == target:
                    return True
        return False
    finally:
        packet.close()


if os.geteuid() != 0:
    raise RuntimeError("root SSH required")

dev = profile["interface"]
current_ip = profile["restore_host"]
prefixlen = int(profile["prefixlen"])
live = profile["live_alias"]
blackhole = profile["blackhole_ip"]
port = int(profile["broker_port"])

addr = load_json(["ip", "-j", "-4", "addr", "show", "dev", dev])
globals4 = [
    item for item in addr[0].get("addr_info", [])
    if item.get("family") == "inet" and item.get("scope") == "global"
]
if not any(item.get("local") == current_ip and int(item.get("prefixlen")) == prefixlen for item in globals4):
    raise RuntimeError("restore host/interface binding drifted")
if any(item.get("local") in {live, blackhole} for item in globals4):
    raise RuntimeError("Gate A candidate already assigned")

rc, ss_out, ss_err = run(["ss", "-H", "-ltn4"])
if rc != 0:
    raise RuntimeError("listener probe failed: " + ss_err[:200])
listeners = [line.split() for line in ss_out.splitlines() if line.strip()]
if any(len(parts) >= 4 and parts[3].endswith(":" + str(port)) for parts in listeners):
    raise RuntimeError("Gate A port is already listening")
wildcard_8883 = any(
    len(parts) >= 4 and parts[3].endswith(":8883")
    and (parts[3].startswith("0.0.0.0:") or parts[3].startswith("*:"))
    for parts in listeners
)
if not wildcard_8883:
    raise RuntimeError("production wildcard 8883 not observed")

rc, broker_out, _ = run([
    "docker", "ps", "--filter", "label=com.docker.compose.project=n3wfc4",
    "--filter", "label=com.docker.compose.service=broker", "--format", "{{.ID}}"
])
broker_ids = [x for x in broker_out.splitlines() if x.strip()] if rc == 0 else []
if len(broker_ids) != 1:
    raise RuntimeError("production Broker ownership not unique")
broker_id = broker_ids[0]
broker_doc = load_json(["docker", "inspect", broker_id])[0]
if broker_doc.get("State", {}).get("Running") is not True:
    raise RuntimeError("production Broker is not running")
broker_image_id = broker_doc.get("Image")
broker_restart_count = int(broker_doc.get("RestartCount", 0))
if not isinstance(broker_image_id, str) or not broker_image_id.startswith("sha256:"):
    raise RuntimeError("production Broker image ID unavailable")

manager_doc = load_json(["docker", "inspect", "greenhouse-manager"])[0]
if manager_doc.get("State", {}).get("Running") is not True:
    raise RuntimeError("Manager is not running")
manager_restart_count = int(manager_doc.get("RestartCount", 0))

rc, existing, _ = run(["docker", "ps", "-a", "--filter", "name=^/" + container_name + "$", "--format", "{{.ID}}"])
if rc != 0 or existing.strip():
    raise RuntimeError("Gate A lab container already exists")

local_mac = open(f"/sys/class/net/{dev}/address", "r", encoding="ascii").read().strip()
if arp_claimed(dev, local_mac, live):
    raise RuntimeError("live alias is now claimed on LAN")
if arp_claimed(dev, local_mac, blackhole):
    raise RuntimeError("blackhole address is now claimed on LAN")

print(json.dumps({
    "status": "PASS",
    "broker_image_id": broker_image_id,
    "broker_restart_count": broker_restart_count,
    "manager_restart_count": manager_restart_count,
    "wildcard_8883": True,
    "port_free": True,
    "live_alias_unassigned": True,
    "blackhole_unassigned": True,
    "docker_available": True,
}, sort_keys=True))
"""


def parse_single_json(raw: str) -> dict[str, Any]:
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise StopExecution("remote probe returned unexpected output")
    try:
        doc = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise StopExecution("remote probe output is not JSON") from exc
    if not isinstance(doc, dict):
        raise StopExecution("remote probe output is invalid")
    return doc


def run_preflight(args: argparse.Namespace) -> int:
    validate_target(args.t1)
    bundle = validate_bundle(Path(args.bundle))
    profile = bundle["profile"]
    public_profile = {
        "interface": profile["interface"],
        "restore_host": profile["restore_host"],
        "prefixlen": profile["prefixlen"],
        "live_alias": profile["live_alias"],
        "blackhole_ip": profile["blackhole_ip"],
        "broker_port": profile["broker_port"],
    }
    raw = remote_python(
        args.t1,
        REMOTE_PREFLIGHT,
        [json.dumps(public_profile, separators=(",", ":")), CONTAINER_NAME],
        timeout=60,
    )
    remote = parse_single_json(raw)
    if remote.get("status") != "PASS":
        raise StopExecution("T1 lab read-only preflight did not PASS")
    payload = {
        "schema": SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "t1_target_sha256": sha256_bytes(args.t1.encode("utf-8")),
        "profile_sha256": bundle["profile_sha256"],
        "application_sha256": APPLICATION_SHA256,
        "broker_image_id": remote.get("broker_image_id"),
        "broker_restart_count": remote.get("broker_restart_count"),
        "manager_restart_count": remote.get("manager_restart_count"),
        "wildcard_8883": remote.get("wildcard_8883"),
        "port_free": remote.get("port_free"),
        "live_alias_unassigned": remote.get("live_alias_unassigned"),
        "blackhole_unassigned": remote.get("blackhole_unassigned"),
        "t1_mutation": False,
        "production_broker_mutation": False,
        "manager_mutation": False,
        "board_access": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
    }
    private_json(Path(args.output), payload)
    print("GATE_A_T1_LAB_PREFLIGHT=PASS")
    print("PORT_18883_FREE=true")
    print("LIVE_ALIAS_UNASSIGNED=true")
    print("BLACKHOLE_UNASSIGNED=true")
    print(f"BROKER_RESTART_COUNT={remote['broker_restart_count']}")
    print(f"MANAGER_RESTART_COUNT={remote['manager_restart_count']}")
    print("T1_MUTATION=false")
    print("PRODUCTION_BROKER_MUTATION=false")
    print("BOARD_ACCESS=false")
    return 0


def load_preflight(path: Path, target: str, bundle: dict[str, Any]) -> dict[str, Any]:
    require_private_file(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("T1 lab preflight is unreadable") from exc
    if doc.get("schema") != SCHEMA_PREFLIGHT or doc.get("status") != "PASS":
        raise StopExecution("T1 lab preflight is not PASS")
    if doc.get("t1_target_sha256") != sha256_bytes(target.encode("utf-8")):
        raise StopExecution("T1 SSH target changed since preflight")
    if doc.get("profile_sha256") != bundle["profile_sha256"]:
        raise StopExecution("private profile changed since preflight")
    if doc.get("application_sha256") != APPLICATION_SHA256:
        raise StopExecution("application binding drifted")
    if doc.get("authorization_claimed") is not False or doc.get("authorization_consumed") is not False:
        raise StopExecution("T1 lab authorization is already claimed")
    if doc.get("replay_permitted") is not False:
        raise StopExecution("T1 lab replay policy is invalid")
    raw = doc.get("created_at")
    if not isinstance(raw, str):
        raise StopExecution("T1 lab preflight timestamp missing")
    try:
        created = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise StopExecution("T1 lab preflight timestamp invalid") from exc
    age = (utc_now() - created.astimezone(dt.timezone.utc)).total_seconds()
    if age < -30 or age > PREFLIGHT_MAX_AGE_SECONDS:
        raise StopExecution("T1 lab preflight is stale")
    return doc


def claim_preflight(path: Path, target: str, bundle: dict[str, Any]) -> dict[str, Any]:
    doc = load_preflight(path, target, bundle)
    claimed = path.with_name("claimed-" + path.name)
    if claimed.exists() or claimed.is_symlink():
        raise StopExecution("T1 lab preflight already claimed")
    try:
        inode = path.stat().st_ino
        os.link(path, claimed, follow_symlinks=False)
        path.unlink()
    except OSError as exc:
        claimed.unlink(missing_ok=True)
        raise StopExecution("T1 lab preflight claim failed") from exc
    if claimed.stat().st_ino != inode:
        raise StopExecution("T1 lab preflight claim inode mismatch")
    doc["authorization_claimed"] = True
    doc["authorization_consumed"] = True
    doc["consumed_at"] = utc_now().isoformat()
    private_json(claimed, doc)
    return doc


REMOTE_PREPARE = r"""
import os
import shutil
import sys
root = sys.argv[1]
if os.geteuid() != 0:
    raise SystemExit("root SSH required")
if root != "/run/n3w-gate-a-77b0fd6a":
    raise SystemExit("unexpected remote lab root")
if os.path.exists(root):
    raise SystemExit("remote lab root already exists")
os.makedirs(root, mode=0o700)
os.chmod(root, 0o700)
"""


REMOTE_ABORT = r"""
import json
import os
import shutil
import subprocess
import sys

root, container_name, app_hash = sys.argv[1:4]


def run(argv):
    return subprocess.run(argv, text=True, capture_output=True, check=False, timeout=30)


if os.geteuid() != 0:
    raise RuntimeError("root SSH required")
if root != "/run/n3w-gate-a-77b0fd6a":
    raise RuntimeError("unexpected remote lab root")

p = run(["docker", "inspect", container_name])
if p.returncode == 0:
    doc = json.loads(p.stdout)[0]
    labels = doc.get("Config", {}).get("Labels", {}) or {}
    if labels.get("gh.n3w.gate-a") == "1" and labels.get("gh.n3w.gate-a.bundle") == app_hash:
        run(["docker", "rm", "-f", container_name])

profile_path = os.path.join(root, "profile.json")
if os.path.isfile(profile_path):
    try:
        with open(profile_path, "r", encoding="utf-8") as handle:
            profile = json.load(handle)
        p = run(["ip", "-j", "-4", "addr", "show", "dev", profile["interface"]])
        if p.returncode == 0:
            doc = json.loads(p.stdout)
            if any(
                x.get("local") == profile["live_alias"]
                and int(x.get("prefixlen")) == int(profile["prefixlen"])
                for x in doc[0].get("addr_info", [])
            ):
                run([
                    "ip", "addr", "del",
                    profile["live_alias"] + "/" + str(profile["prefixlen"]),
                    "dev", profile["interface"],
                ])
    except Exception:
        pass

if os.path.isdir(root):
    shutil.rmtree(root, ignore_errors=True)
"""


REMOTE_ACTIVATE = r"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time

root, container_name, expected_image_id, expected_broker_restarts, expected_manager_restarts, app_hash = sys.argv[1:7]
expected_broker_restarts = int(expected_broker_restarts)
expected_manager_restarts = int(expected_manager_restarts)


def run(argv, timeout=30, check=True):
    p = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError("command failed: " + " ".join(argv[:3]) + ": " + (p.stderr or p.stdout)[:250])
    return p


def inspect(name):
    p = run(["docker", "inspect", name])
    return json.loads(p.stdout)[0]


def port_open(port):
    p = run(["ss", "-H", "-ltn4"], check=True)
    return any(line.split()[3].endswith(":" + str(port)) for line in p.stdout.splitlines() if len(line.split()) >= 4)


def remove_alias(profile):
    p = run(["ip", "-j", "-4", "addr", "show", "dev", profile["interface"]], check=False)
    if p.returncode != 0:
        return
    try:
        doc = json.loads(p.stdout)
    except Exception:
        return
    if any(x.get("local") == profile["live_alias"] and int(x.get("prefixlen")) == int(profile["prefixlen"]) for x in doc[0].get("addr_info", [])):
        run(["ip", "addr", "del", profile["live_alias"] + "/" + str(profile["prefixlen"]), "dev", profile["interface"]], check=False)


if os.geteuid() != 0:
    raise RuntimeError("root SSH required")
profile_path = os.path.join(root, "profile.json")
with open(profile_path, "r", encoding="utf-8") as handle:
    profile = json.load(handle)
if int(profile["broker_port"]) != 18883 or profile["tls_server_name"] != "n3w-gate-a.invalid":
    raise RuntimeError("lab profile endpoint drifted")

broker_ids = run([
    "docker", "ps", "--filter", "label=com.docker.compose.project=n3wfc4",
    "--filter", "label=com.docker.compose.service=broker", "--format", "{{.ID}}"
]).stdout.splitlines()
if len([x for x in broker_ids if x.strip()]) != 1:
    raise RuntimeError("production Broker ownership drifted")
broker = inspect(broker_ids[0].strip())
manager = inspect("greenhouse-manager")
if broker.get("Image") != expected_image_id:
    raise RuntimeError("production Broker image drifted")
if int(broker.get("RestartCount", 0)) != expected_broker_restarts:
    raise RuntimeError("production Broker restart count drifted")
if int(manager.get("RestartCount", 0)) != expected_manager_restarts:
    raise RuntimeError("Manager restart count drifted")
if port_open(18883):
    raise RuntimeError("lab port became occupied")

for name in ("ca.crt", "server.crt", "server.key", "passwd", "mosquitto.conf", "profile.json"):
    path = os.path.join(root, name)
    if not os.path.isfile(path):
        raise RuntimeError("lab file missing: " + name)
    os.chmod(path, 0o600)

try:
    run([
        "docker", "run", "--rm", "--network", "none", "--user", "0:0",
        "-v", root + ":/lab", "--entrypoint", "mosquitto_passwd",
        expected_image_id, "-U", "/lab/passwd"
    ], timeout=60)
    with open(os.path.join(root, "passwd"), "r", encoding="utf-8") as handle:
        hashed = handle.read()
    if profile["mqtt_password"] in hashed:
        raise RuntimeError("MQTT password remained plaintext")

    run([
        "docker", "run", "-d", "--rm", "--name", container_name,
        "--network", "host", "--read-only",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=4m",
        "--label", "gh.n3w.gate-a=1",
        "--label", "gh.n3w.gate-a.bundle=" + app_hash,
        "-v", root + ":/lab:ro",
        "--entrypoint", "mosquitto", expected_image_id,
        "-c", "/lab/mosquitto.conf"
    ], timeout=60)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not port_open(18883):
        time.sleep(0.25)
    if not port_open(18883):
        raise RuntimeError("lab Broker listener did not become ready")

    addr = json.loads(run(["ip", "-j", "-4", "addr", "show", "dev", profile["interface"]]).stdout)
    if any(x.get("local") in {profile["live_alias"], profile["blackhole_ip"]} for x in addr[0].get("addr_info", [])):
        raise RuntimeError("candidate address became assigned before alias add")
    run([
        "ip", "addr", "add",
        profile["live_alias"] + "/" + str(profile["prefixlen"]),
        "dev", profile["interface"],
        "label", profile["interface"] + ":gatea"
    ])
    if not port_open(18883):
        raise RuntimeError("lab Broker listener disappeared after alias add")

    broker_after = inspect(broker_ids[0].strip())
    manager_after = inspect("greenhouse-manager")
    if broker_after.get("State", {}).get("Running") is not True or int(broker_after.get("RestartCount", 0)) != expected_broker_restarts:
        raise RuntimeError("production Broker continuity failed")
    if manager_after.get("State", {}).get("Running") is not True or int(manager_after.get("RestartCount", 0)) != expected_manager_restarts:
        raise RuntimeError("Manager continuity failed")
    print(json.dumps({
        "status": "PASS",
        "container_running": True,
        "alias_active": True,
        "port_18883_listening": True,
        "broker_restart_count": expected_broker_restarts,
        "manager_restart_count": expected_manager_restarts,
    }, sort_keys=True))
except Exception:
    run(["docker", "rm", "-f", container_name], check=False)
    remove_alias(profile)
    shutil.rmtree(root, ignore_errors=True)
    raise
"""


REMOTE_CLEANUP = r"""
import json
import os
import shutil
import subprocess
import sys

root, container_name, app_hash, expected_broker_restarts, expected_manager_restarts = sys.argv[1:6]
expected_broker_restarts = int(expected_broker_restarts)
expected_manager_restarts = int(expected_manager_restarts)


def run(argv, check=True):
    p = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=30)
    if check and p.returncode != 0:
        raise RuntimeError("command failed")
    return p


def inspect(name):
    p = run(["docker", "inspect", name])
    return json.loads(p.stdout)[0]


if os.geteuid() != 0:
    raise RuntimeError("root SSH required")
profile_path = os.path.join(root, "profile.json")
if not os.path.isfile(profile_path):
    raise RuntimeError("lab profile missing; refusing unbound cleanup")
with open(profile_path, "r", encoding="utf-8") as handle:
    profile = json.load(handle)

p = run(["docker", "inspect", container_name], check=False)
if p.returncode == 0:
    doc = json.loads(p.stdout)[0]
    labels = doc.get("Config", {}).get("Labels", {}) or {}
    if labels.get("gh.n3w.gate-a") != "1" or labels.get("gh.n3w.gate-a.bundle") != app_hash:
        raise RuntimeError("refusing to remove unbound container")
    run(["docker", "rm", "-f", container_name])

addr = json.loads(run(["ip", "-j", "-4", "addr", "show", "dev", profile["interface"]]).stdout)
if any(x.get("local") == profile["live_alias"] and int(x.get("prefixlen")) == int(profile["prefixlen"]) for x in addr[0].get("addr_info", [])):
    run(["ip", "addr", "del", profile["live_alias"] + "/" + str(profile["prefixlen"]), "dev", profile["interface"]])

shutil.rmtree(root)

broker_ids = run([
    "docker", "ps", "--filter", "label=com.docker.compose.project=n3wfc4",
    "--filter", "label=com.docker.compose.service=broker", "--format", "{{.ID}}"
]).stdout.splitlines()
if len([x for x in broker_ids if x.strip()]) != 1:
    raise RuntimeError("production Broker ownership drifted after cleanup")
broker = inspect(broker_ids[0].strip())
manager = inspect("greenhouse-manager")
if broker.get("State", {}).get("Running") is not True or int(broker.get("RestartCount", 0)) != expected_broker_restarts:
    raise RuntimeError("production Broker continuity failed after cleanup")
if manager.get("State", {}).get("Running") is not True or int(manager.get("RestartCount", 0)) != expected_manager_restarts:
    raise RuntimeError("Manager continuity failed after cleanup")

ss_out = run(["ss", "-H", "-ltn4"]).stdout
if any(len(line.split()) >= 4 and line.split()[3].endswith(":18883") for line in ss_out.splitlines()):
    raise RuntimeError("lab port still listening after cleanup")

print(json.dumps({
    "status": "PASS",
    "container_running": False,
    "alias_active": False,
    "port_18883_listening": False,
    "remote_root_removed": True,
    "broker_restart_count": expected_broker_restarts,
    "manager_restart_count": expected_manager_restarts,
}, sort_keys=True))
"""


def make_staging(bundle: dict[str, Any]) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    holder = tempfile.TemporaryDirectory(prefix="n3w-gate-a-t1-lab-")
    root = Path(holder.name)
    os.chmod(root, 0o700)
    profile = bundle["profile"]
    shutil.copy2(bundle["ca"], root / "ca.crt")
    shutil.copy2(bundle["cert"], root / "server.crt")
    shutil.copy2(bundle["key"], root / "server.key")
    shutil.copy2(bundle["root"] / "lab/profile.json", root / "profile.json")
    config = "\n".join((
        "listener 18883 0.0.0.0",
        "allow_anonymous false",
        "persistence false",
        "connection_messages true",
        "log_dest stdout",
        "log_type all",
        "password_file /lab/passwd",
        "certfile /lab/server.crt",
        "keyfile /lab/server.key",
        "require_certificate false",
        "",
    ))
    (root / "mosquitto.conf").write_text(config, encoding="utf-8")
    (root / "passwd").write_text(f"{profile['mqtt_username']}:{profile['mqtt_password']}\n", encoding="utf-8")
    for item in root.iterdir():
        os.chmod(item, 0o600)
    return holder, root


def copy_staging(target: str, root: Path) -> None:
    for name in ("ca.crt", "server.crt", "server.key", "profile.json", "mosquitto.conf", "passwd"):
        run_capture(scp_base() + [str(root / name), f"{target}:{REMOTE_ROOT}/{name}"], timeout=30)


def run_activate(args: argparse.Namespace) -> int:
    if args.confirm != ACTIVATE_CONFIRMATION:
        raise StopExecution("T1 lab activation confirmation token mismatch")
    validate_target(args.t1)
    bundle = validate_bundle(Path(args.bundle))
    preflight_path = Path(args.preflight)
    preflight = load_preflight(preflight_path, args.t1, bundle)
    claim_preflight(preflight_path, args.t1, bundle)

    holder, staging = make_staging(bundle)
    mutation_started = False
    try:
        remote_python(args.t1, REMOTE_PREPARE, [REMOTE_ROOT], timeout=30)
        mutation_started = True
        copy_staging(args.t1, staging)
        raw = remote_python(
            args.t1,
            REMOTE_ACTIVATE,
            [
                REMOTE_ROOT,
                CONTAINER_NAME,
                str(preflight["broker_image_id"]),
                str(preflight["broker_restart_count"]),
                str(preflight["manager_restart_count"]),
                APPLICATION_SHA256,
            ],
            timeout=120,
        )
    except Exception:
        if mutation_started:
            try:
                remote_python(
                    args.t1,
                    REMOTE_ABORT,
                    [REMOTE_ROOT, CONTAINER_NAME, APPLICATION_SHA256],
                    timeout=60,
                )
            except Exception:
                pass
        raise
    finally:
        holder.cleanup()
    remote = parse_single_json(raw)
    if remote.get("status") != "PASS":
        raise StopExecution("T1 lab activation did not PASS")
    state = {
        "schema": SCHEMA_ACTIVE,
        "status": "PASS",
        "created_at": utc_now().isoformat(),
        "t1_target_sha256": sha256_bytes(args.t1.encode("utf-8")),
        "profile_sha256": bundle["profile_sha256"],
        "application_sha256": APPLICATION_SHA256,
        "container_name_sha256": sha256_bytes(CONTAINER_NAME.encode("utf-8")),
        "broker_image_id": preflight["broker_image_id"],
        "broker_restart_count": preflight["broker_restart_count"],
        "manager_restart_count": preflight["manager_restart_count"],
        "remote_root_sha256": sha256_bytes(REMOTE_ROOT.encode("utf-8")),
        "container_running": True,
        "alias_active": True,
        "port_18883_listening": True,
        "production_broker_mutation": False,
        "manager_mutation": False,
        "board_access": False,
    }
    private_json(Path(args.output), state)
    print("GATE_A_T1_LAB_ACTIVATION=PASS")
    print("ISOLATED_BROKER_18883=true")
    print("LIVE_ALIAS_ACTIVE=true")
    print(f"BROKER_RESTART_COUNT={preflight['broker_restart_count']}")
    print(f"MANAGER_RESTART_COUNT={preflight['manager_restart_count']}")
    print("PRODUCTION_BROKER_MUTATION=false")
    print("MANAGER_MUTATION=false")
    print("BOARD_ACCESS=false")
    return 0


def load_active(path: Path, target: str, bundle: dict[str, Any]) -> dict[str, Any]:
    require_private_file(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StopExecution("T1 lab active state is unreadable") from exc
    if doc.get("schema") != SCHEMA_ACTIVE or doc.get("status") != "PASS":
        raise StopExecution("T1 lab active state is not PASS")
    if doc.get("t1_target_sha256") != sha256_bytes(target.encode("utf-8")):
        raise StopExecution("T1 target changed since activation")
    if doc.get("profile_sha256") != bundle["profile_sha256"]:
        raise StopExecution("private profile changed since activation")
    if doc.get("application_sha256") != APPLICATION_SHA256:
        raise StopExecution("application binding drifted")
    if doc.get("container_running") is not True or doc.get("alias_active") is not True:
        raise StopExecution("T1 lab active state is incomplete")
    return doc


def run_cleanup(args: argparse.Namespace) -> int:
    if args.confirm != CLEANUP_CONFIRMATION:
        raise StopExecution("T1 lab cleanup confirmation token mismatch")
    validate_target(args.t1)
    bundle = validate_bundle(Path(args.bundle))
    state = load_active(Path(args.state), args.t1, bundle)
    raw = remote_python(
        args.t1,
        REMOTE_CLEANUP,
        [
            REMOTE_ROOT,
            CONTAINER_NAME,
            APPLICATION_SHA256,
            str(state["broker_restart_count"]),
            str(state["manager_restart_count"]),
        ],
        timeout=90,
    )
    remote = parse_single_json(raw)
    if remote.get("status") != "PASS":
        raise StopExecution("T1 lab cleanup did not PASS")
    print("GATE_A_T1_LAB_CLEANUP=PASS")
    print("ISOLATED_BROKER_18883=false")
    print("LIVE_ALIAS_ACTIVE=false")
    print("REMOTE_PRIVATE_LAB_REMOVED=true")
    print(f"BROKER_RESTART_COUNT={state['broker_restart_count']}")
    print(f"MANAGER_RESTART_COUNT={state['manager_restart_count']}")
    print("PRODUCTION_BROKER_MUTATION=false")
    print("MANAGER_MUTATION=false")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("preflight")
    pre.add_argument("--t1", required=True)
    pre.add_argument("--bundle", required=True)
    pre.add_argument("--output", required=True)
    pre.set_defaults(func=run_preflight)

    act = sub.add_parser("activate")
    act.add_argument("--t1", required=True)
    act.add_argument("--bundle", required=True)
    act.add_argument("--preflight", required=True)
    act.add_argument("--output", required=True)
    act.add_argument("--confirm", required=True)
    act.set_defaults(func=run_activate)

    clean = sub.add_parser("cleanup")
    clean.add_argument("--t1", required=True)
    clean.add_argument("--bundle", required=True)
    clean.add_argument("--state", required=True)
    clean.add_argument("--confirm", required=True)
    clean.set_defaults(func=run_cleanup)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        return int(args.func(args))
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
