#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_BOARD_B_HARDWARE_ID_SHA256 = "3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee"
EXPECTED_PARTITION_TABLE_SHA256 = "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0xC00
SCHEMA = "n3w.auto-safe-fallback.gate-a-readonly-preflight/1"

MAC_RE = re.compile(r"\bMAC:\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b")
FLASH_8MB_RE = re.compile(r"Detected flash size:\s*8\s*MB\b", re.I)
SECURE_BOOT_DISABLED_RE = re.compile(r"Secure Boot:\s*Disabled\b", re.I)
FLASH_ENCRYPTION_DISABLED_RE = re.compile(r"Flash Encryption:\s*Disabled\b", re.I)

REMOTE_PROBE = r"""
import ipaddress
import json
import os
import socket
import struct
import subprocess
import sys
import time


def run(argv, timeout=10):
    result = subprocess.run(
        argv,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def load_json(argv):
    rc, out, err = run(argv)
    if rc != 0:
        raise RuntimeError("command failed: " + " ".join(argv) + ": " + err[:300])
    return json.loads(out)


def arp_claimed(dev, local_mac, candidate):
    packet = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0806))
    packet.bind((dev, 0))
    packet.settimeout(0.35)
    src = bytes.fromhex(local_mac.replace(":", ""))
    dst = b"\xff" * 6
    target = socket.inet_aton(candidate)
    frame = (
        dst
        + src
        + b"\x08\x06"
        + struct.pack("!HHBBH", 1, 0x0800, 6, 4, 1)
        + src
        + b"\x00\x00\x00\x00"
        + b"\x00" * 6
        + target
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
                if len(data) < 42 or data[12:14] != b"\x08\x06":
                    continue
                if data[20:22] != b"\x00\x02":
                    continue
                if data[28:32] == target:
                    return True
        return False
    finally:
        packet.close()


if os.geteuid() != 0:
    raise RuntimeError("T1 read-only preflight requires root SSH")

routes = load_json(["ip", "-j", "-4", "route", "show", "default"])
usable_routes = [r for r in routes if r.get("dev")]
if not usable_routes:
    raise RuntimeError("no IPv4 default route")
route = usable_routes[0]
dev = route["dev"]
gateway = route.get("gateway")

addr_doc = load_json(["ip", "-j", "-4", "addr", "show", "dev", dev])
if len(addr_doc) != 1:
    raise RuntimeError("unexpected interface address document")
globals4 = [
    item
    for item in addr_doc[0].get("addr_info", [])
    if item.get("family") == "inet"
    and item.get("scope") == "global"
    and item.get("local")
    and isinstance(item.get("prefixlen"), int)
]
if len(globals4) != 1:
    raise RuntimeError("expected exactly one global IPv4 on default-route interface")
current_ip = globals4[0]["local"]
prefixlen = globals4[0]["prefixlen"]
interface = ipaddress.ip_interface(f"{current_ip}/{prefixlen}")
network = interface.network
if network.num_addresses < 8:
    raise RuntimeError("LAN subnet is too small for bounded Gate A candidate selection")

rc, ss_out, ss_err = run(["ss", "-H", "-ltn4"])
if rc != 0:
    raise RuntimeError("ss listener probe failed: " + ss_err[:300])
listener_lines = [line.split() for line in ss_out.splitlines() if line.strip()]
wildcard_8883 = any(
    len(parts) >= 4
    and parts[3].endswith(":8883")
    and (parts[3].startswith("0.0.0.0:") or parts[3].startswith("*:"))
    for parts in listener_lines
)

rc, broker_out, _ = run(
    [
        "docker",
        "ps",
        "--filter",
        "label=com.docker.compose.project=n3wfc4",
        "--filter",
        "label=com.docker.compose.service=broker",
        "--format",
        "{{.ID}}",
    ]
)
broker_ids = [line for line in broker_out.splitlines() if line.strip()] if rc == 0 else []
broker_running = len(broker_ids) == 1

rc, manager_out, _ = run(
    ["docker", "inspect", "-f", "{{.State.Running}} {{.RestartCount}}", "greenhouse-manager"]
)
manager_running = False
manager_restart_count = None
if rc == 0:
    parts = manager_out.strip().split()
    if len(parts) == 2:
        manager_running = parts[0].lower() == "true"
        try:
            manager_restart_count = int(parts[1])
        except ValueError:
            manager_restart_count = None

mac_path = f"/sys/class/net/{dev}/address"
local_mac = open(mac_path, "r", encoding="ascii").read().strip()
if not re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", local_mac):
    raise RuntimeError("unable to read interface MAC")

first = int(network.network_address) + 1
last = int(network.broadcast_address) - 1
candidate_ints = []
for value in range(last, max(first - 1, last - 64), -1):
    candidate_ints.append(value)
for value in range(first, min(last + 1, first + 64)):
    if value not in candidate_ints:
        candidate_ints.append(value)

skip = {current_ip}
if gateway:
    skip.add(gateway)

available = []
for value in candidate_ints:
    candidate = str(ipaddress.ip_address(value))
    if candidate in skip:
        continue
    if not arp_claimed(dev, local_mac, candidate):
        available.append(candidate)
    if len(available) == 2:
        break

if len(available) != 2:
    raise RuntimeError("could not prove two unused same-subnet IPv4 candidates")

result = {
    "t1_root": True,
    "interface": dev,
    "current_ip": current_ip,
    "prefixlen": prefixlen,
    "gateway": gateway,
    "wildcard_8883": wildcard_8883,
    "broker_running": broker_running,
    "manager_running": manager_running,
    "manager_restart_count": manager_restart_count,
    "live_alias": available[0],
    "blackhole_ip": available[1],
}
print(json.dumps(result, sort_keys=True))
"""


class StopExecution(RuntimeError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hardware_id_sha256(raw_mac: str) -> str:
    compact = raw_mac.replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{12}", compact):
        raise StopExecution("invalid ROM MAC")
    return sha256_text("ghw-c6-" + compact)


def validate_ssh_target(target: str) -> None:
    if not target or target.strip() != target or any(ch.isspace() for ch in target):
        raise StopExecution("T1 SSH target is empty or contains whitespace")
    if any(marker in target.casefold() for marker in ("placeholder", "<", ">")):
        raise StopExecution("T1 SSH target looks like a placeholder")


def ssh_argv(target: str) -> list[str]:
    payload = base64.b64encode(REMOTE_PROBE.encode("utf-8")).decode("ascii")
    remote = (
        "python3 -c "
        + repr("import base64;exec(base64.b64decode(" + repr(payload) + "))")
    )
    return [
        "ssh",
        "-n",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        target,
        remote,
    ]


def run_capture(argv: list[str], timeout: int) -> str:
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StopExecution(f"command timed out after {timeout}s") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise StopExecution(f"command failed rc={completed.returncode}: {detail[:800]}")
    return completed.stdout


def parse_remote_result(raw: str) -> dict[str, object]:
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise StopExecution("T1 probe returned unexpected output")
    try:
        doc = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise StopExecution("T1 probe output is not JSON") from exc
    required = {
        "t1_root",
        "interface",
        "current_ip",
        "prefixlen",
        "wildcard_8883",
        "broker_running",
        "manager_running",
        "manager_restart_count",
        "live_alias",
        "blackhole_ip",
    }
    if not required.issubset(doc):
        raise StopExecution("T1 probe JSON is incomplete")
    if doc["t1_root"] is not True:
        raise StopExecution("T1 root authority not proven")
    if doc["wildcard_8883"] is not True:
        raise StopExecution("IPv4 wildcard TCP/8883 listener not proven")
    if doc["broker_running"] is not True:
        raise StopExecution("Broker runtime not proven healthy")
    if doc["manager_running"] is not True:
        raise StopExecution("Manager runtime not proven healthy")
    if not isinstance(doc["manager_restart_count"], int):
        raise StopExecution("Manager restart count unavailable")
    for key in ("current_ip", "live_alias", "blackhole_ip"):
        if not isinstance(doc[key], str) or not doc[key]:
            raise StopExecution(f"{key} missing")
    if len({doc["current_ip"], doc["live_alias"], doc["blackhole_ip"]}) != 3:
        raise StopExecution("T1 address candidates are not distinct")
    return doc


def esptool_base(port: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "esptool",
        "--chip",
        "esp32c6",
        "--port",
        port,
        "--no-stub",
    ]


def probe_board(port: str) -> dict[str, object]:
    if not port or any(ch.isspace() for ch in port):
        raise StopExecution("serial port is empty or contains whitespace")

    security = run_capture(
        esptool_base(port) + ["--after", "hard-reset", "get-security-info"],
        30,
    )
    mac = MAC_RE.search(security)
    if mac is None:
        raise StopExecution("Board ROM MAC not observed")
    identity = hardware_id_sha256(mac.group(1))
    if identity != EXPECTED_BOARD_B_HARDWARE_ID_SHA256:
        raise StopExecution("connected board is not frozen Board B")
    if SECURE_BOOT_DISABLED_RE.search(security) is None:
        raise StopExecution("Secure Boot disabled state not proven")
    if FLASH_ENCRYPTION_DISABLED_RE.search(security) is None:
        raise StopExecution("Flash Encryption disabled state not proven")

    flash = run_capture(
        esptool_base(port) + ["--after", "hard-reset", "flash-id"],
        30,
    )
    if FLASH_8MB_RE.search(flash) is None:
        raise StopExecution("8MB flash not proven")

    with tempfile.TemporaryDirectory(prefix="n3w-gate-a-preflight-") as td:
        partition = Path(td) / "partition.bin"
        run_capture(
            esptool_base(port)
            + [
                "--after",
                "hard-reset",
                "read-flash",
                hex(PARTITION_TABLE_OFFSET),
                hex(PARTITION_TABLE_SIZE),
                str(partition),
            ],
            45,
        )
        if not partition.is_file() or partition.stat().st_size != PARTITION_TABLE_SIZE:
            raise StopExecution("partition table readback size mismatch")
        digest = hashlib.sha256(partition.read_bytes()).hexdigest()
    if digest != EXPECTED_PARTITION_TABLE_SHA256:
        raise StopExecution("partition table binding mismatch")

    return {
        "hardware_id_sha256": identity,
        "port_sha256": sha256_text(port),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_sha256": digest,
        "board_reset_may_occur": True,
        "flash_write": False,
        "persistent_mutation": False,
    }


def write_private_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def run(args: argparse.Namespace) -> int:
    validate_ssh_target(args.t1)
    t1 = parse_remote_result(run_capture(ssh_argv(args.t1), 40))
    board = probe_board(args.port)
    payload = {
        "schema": SCHEMA,
        "status": "PASS",
        "t1": t1,
        "board": board,
        "rollback_artifact": {
            "artifact_id": 10959875986,
            "artifact_name": "n3w-kf099-c578bcb-boardb-exact-source",
            "archive_sha256": "56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb",
            "application_sha256": "d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60",
            "otadata_sha256": "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f",
        },
        "t1_mutation": False,
        "board_flash": False,
        "persistent_mutation": False,
    }
    write_private_json(Path(args.output), payload)
    print("GATE_A_READONLY_PREFLIGHT=PASS")
    print(f"T1_INTERFACE={t1['interface']}")
    print(f"T1_CURRENT_IP={t1['current_ip']}")
    print(f"T1_PREFIXLEN={t1['prefixlen']}")
    print(f"LIVE_ALIAS={t1['live_alias']}")
    print(f"BLACKHOLE_IP={t1['blackhole_ip']}")
    print(f"MANAGER_RESTART_COUNT={t1['manager_restart_count']}")
    print("BROKER_IPV4_WILDCARD_8883=true")
    print(f"BOARD_B_HARDWARE_ID_SHA256={board['hardware_id_sha256']}")
    print(f"PARTITION_TABLE_SHA256={board['partition_table_sha256']}")
    print("BOARD_FLASH=false")
    print("T1_MUTATION=false")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1", required=True)
    parser.add_argument("--port", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main() -> int:
    try:
        return run(build_parser().parse_args())
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
