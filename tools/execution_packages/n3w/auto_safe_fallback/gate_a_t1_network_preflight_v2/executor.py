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
import stat
import subprocess
import sys
from pathlib import Path

SCHEMA = "n3w.auto-safe-fallback.gate-a-t1-network-preflight-v2/1"

REMOTE = r"""
import ipaddress
import json
import os
import re
import socket
import struct
import subprocess
import time


def run(argv, timeout=10):
    p = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def load_json(argv):
    rc, out, err = run(argv)
    if rc != 0:
        raise RuntimeError((err or out)[:300])
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

routes = load_json(["ip", "-j", "-4", "route", "show", "default"])
routes = [r for r in routes if r.get("dev")]
if len(routes) != 1:
    raise RuntimeError("expected exactly one IPv4 default route")
dev = routes[0]["dev"]
gateway = routes[0].get("gateway")

addr = load_json(["ip", "-j", "-4", "addr", "show", "dev", dev])
if len(addr) != 1:
    raise RuntimeError("unexpected interface address document")
globals4 = [
    x for x in addr[0].get("addr_info", [])
    if x.get("family") == "inet" and x.get("scope") == "global" and x.get("local")
]
if len(globals4) != 1:
    raise RuntimeError("expected exactly one global IPv4 on default-route interface")
current_ip = globals4[0]["local"]
prefixlen = int(globals4[0]["prefixlen"])
network = ipaddress.ip_interface(f"{current_ip}/{prefixlen}").network
if network.num_addresses < 8:
    raise RuntimeError("LAN subnet is too small")

rc, ss_out, ss_err = run(["ss", "-H", "-ltn4"])
if rc != 0:
    raise RuntimeError("listener probe failed: " + ss_err[:200])
listeners = [line.split() for line in ss_out.splitlines() if line.strip()]
wildcard_8883 = any(
    len(parts) >= 4 and parts[3].endswith(":8883")
    and (parts[3].startswith("0.0.0.0:") or parts[3].startswith("*:"))
    for parts in listeners
)
port_18883_free = not any(
    len(parts) >= 4 and parts[3].endswith(":18883") for parts in listeners
)

broker_ids_rc, broker_ids_out, _ = run([
    "docker", "ps", "--filter", "label=com.docker.compose.project=n3wfc4",
    "--filter", "label=com.docker.compose.service=broker", "--format", "{{.ID}}"
])
broker_ids = [x for x in broker_ids_out.splitlines() if x.strip()] if broker_ids_rc == 0 else []
if len(broker_ids) != 1:
    raise RuntimeError("production Broker ownership not unique")
broker = load_json(["docker", "inspect", broker_ids[0]])[0]
manager = load_json(["docker", "inspect", "greenhouse-manager"])[0]
if broker.get("State", {}).get("Running") is not True:
    raise RuntimeError("production Broker is not running")
if manager.get("State", {}).get("Running") is not True:
    raise RuntimeError("Manager is not running")
image_id = broker.get("Image")
if not isinstance(image_id, str) or not image_id.startswith("sha256:"):
    raise RuntimeError("production Broker image ID unavailable")

mac = open(f"/sys/class/net/{dev}/address", "r", encoding="ascii").read().strip()
if not re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", mac):
    raise RuntimeError("interface MAC unavailable")

first = int(network.network_address) + 1
last = int(network.broadcast_address) - 1
values = list(range(last, max(first - 1, last - 64), -1))
values += [v for v in range(first, min(last + 1, first + 64)) if v not in values]
skip = {current_ip}
if gateway:
    skip.add(gateway)
available = []
for value in values:
    candidate = str(ipaddress.ip_address(value))
    if candidate in skip:
        continue
    if not arp_claimed(dev, mac, candidate):
        available.append(candidate)
    if len(available) == 2:
        break
if len(available) != 2:
    raise RuntimeError("could not prove two unused same-subnet IPv4 candidates")

print(json.dumps({
    "status": "PASS",
    "interface": dev,
    "current_ip": current_ip,
    "prefixlen": prefixlen,
    "gateway_present": bool(gateway),
    "wildcard_8883": wildcard_8883,
    "port_18883_free": port_18883_free,
    "live_alias": available[0],
    "blackhole_ip": available[1],
    "broker_image_id": image_id,
    "broker_restart_count": int(broker.get("RestartCount", 0)),
    "manager_restart_count": int(manager.get("RestartCount", 0)),
}, sort_keys=True))
"""


class StopExecution(RuntimeError):
    pass


def validate_target(target: str) -> None:
    if not target or target.strip() != target or any(ch.isspace() for ch in target):
        raise StopExecution("T1 SSH target is empty or contains whitespace")
    if any(x in target.casefold() for x in ("placeholder", "<", ">")):
        raise StopExecution("T1 SSH target looks like a placeholder")


def ssh_base(target: str) -> list[str]:
    return [
        "ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=2", target,
    ]


def run_capture(argv: list[str], timeout: int = 60) -> str:
    try:
        p = subprocess.run(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise StopExecution(f"command timed out after {timeout}s") from exc
    if p.returncode != 0:
        detail = (p.stderr or p.stdout).strip()
        raise StopExecution(f"command failed rc={p.returncode}: {detail[:600]}")
    return p.stdout


def remote_python(target: str) -> str:
    payload = base64.b64encode(REMOTE.encode("utf-8")).decode("ascii")
    launcher = "import base64;exec(base64.b64decode(" + repr(payload) + "))"
    cmd = "python3 -c " + shlex.quote(launcher)
    return run_capture(ssh_base(target) + [cmd], timeout=45)


def private_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def parse(raw: str) -> dict[str, object]:
    lines = [x for x in raw.splitlines() if x.strip()]
    if len(lines) != 1:
        raise StopExecution("T1 probe returned unexpected output")
    try:
        doc = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise StopExecution("T1 probe output is not JSON") from exc
    if doc.get("status") != "PASS":
        raise StopExecution("T1 probe did not PASS")
    if doc.get("wildcard_8883") is not True or doc.get("port_18883_free") is not True:
        raise StopExecution("Broker listener boundary is not ready")
    for key in ("current_ip", "live_alias", "blackhole_ip", "interface", "broker_image_id"):
        if not isinstance(doc.get(key), str) or not doc.get(key):
            raise StopExecution(f"missing field: {key}")
    try:
        net = ipaddress.ip_interface(f"{doc['current_ip']}/{int(doc['prefixlen'])}").network
        live = ipaddress.ip_address(str(doc["live_alias"]))
        black = ipaddress.ip_address(str(doc["blackhole_ip"]))
    except (TypeError, ValueError) as exc:
        raise StopExecution("invalid IPv4 binding") from exc
    if live not in net or black not in net:
        raise StopExecution("candidate left current subnet")
    if len({str(doc["current_ip"]), str(live), str(black)}) != 3:
        raise StopExecution("addresses are not distinct")
    return doc


def main_run(args: argparse.Namespace) -> int:
    validate_target(args.t1)
    remote = parse(remote_python(args.t1))
    payload = {
        "schema": SCHEMA,
        "status": "PASS",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "t1_target_sha256": hashlib.sha256(args.t1.encode("utf-8")).hexdigest(),
        "t1": remote,
        "board_access": False,
        "board_flash": False,
        "t1_mutation": False,
        "production_broker_mutation": False,
        "manager_mutation": False,
    }
    private_json(Path(args.output), payload)
    print("GATE_A_T1_NETWORK_PREFLIGHT_V2=PASS")
    print(f"T1_INTERFACE={remote['interface']}")
    print(f"T1_CURRENT_IP={remote['current_ip']}")
    print(f"T1_PREFIXLEN={remote['prefixlen']}")
    print(f"LIVE_ALIAS={remote['live_alias']}")
    print(f"BLACKHOLE_IP={remote['blackhole_ip']}")
    print(f"BROKER_RESTART_COUNT={remote['broker_restart_count']}")
    print(f"MANAGER_RESTART_COUNT={remote['manager_restart_count']}")
    print("PORT_18883_FREE=true")
    print("BROKER_IPV4_WILDCARD_8883=true")
    print("T1_MUTATION=false")
    print("BOARD_ACCESS=false")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--t1", required=True)
    p.add_argument("--output", required=True)
    return p


def main() -> int:
    try:
        return main_run(parser().parse_args())
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
