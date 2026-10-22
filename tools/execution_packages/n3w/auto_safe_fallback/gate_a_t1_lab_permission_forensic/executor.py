#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import shlex
import subprocess
import sys


class StopExecution(RuntimeError):
    pass


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
        raise StopExecution(f"command failed rc={result.returncode}: {detail[:500]}")
    return result.stdout


def remote_python(target: str, source: str, timeout: int = 60) -> str:
    payload = base64.b64encode(source.encode("utf-8")).decode("ascii")
    launcher = "import base64;exec(base64.b64decode(" + repr(payload) + "))"
    remote_command = "python3 -c " + shlex.quote(launcher)
    return run_capture(ssh_base(target) + [remote_command], timeout=timeout)


REMOTE_FORENSIC = r'''
import json
import os
import re
import subprocess


def run(argv, timeout=15):
    p = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def load_json(argv):
    rc, out, err = run(argv)
    if rc != 0:
        raise RuntimeError((err or out)[:250])
    return json.loads(out)


def parse_effective_id(status_text, field):
    match = re.search(r"^" + re.escape(field) + r":\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", status_text, re.M)
    if match is None:
        raise RuntimeError(field + " not found in Broker PID1 status")
    values = [int(value) for value in match.groups()]
    if len(set(values)) != 1:
        raise RuntimeError(field + " values are not stable")
    return values[0]


if os.geteuid() != 0:
    raise RuntimeError("root SSH required")

rc, broker_out, _ = run([
    "docker", "ps", "--filter", "label=com.docker.compose.project=n3wfc4",
    "--filter", "label=com.docker.compose.service=broker", "--format", "{{.ID}}"
])
broker_ids = [value for value in broker_out.splitlines() if value.strip()] if rc == 0 else []
if len(broker_ids) != 1:
    raise RuntimeError("production Broker ownership not unique")
broker_id = broker_ids[0]
broker = load_json(["docker", "inspect", broker_id])[0]
manager = load_json(["docker", "inspect", "greenhouse-manager"])[0]
if broker.get("State", {}).get("Running") is not True:
    raise RuntimeError("production Broker is not running")
if manager.get("State", {}).get("Running") is not True:
    raise RuntimeError("Manager is not running")
image_id = broker.get("Image")
if not isinstance(image_id, str) or not image_id.startswith("sha256:"):
    raise RuntimeError("production Broker image ID unavailable")
image = load_json(["docker", "image", "inspect", image_id])[0]

rc, status_out, status_err = run(["docker", "exec", broker_id, "cat", "/proc/1/status"])
if rc != 0:
    raise RuntimeError("Broker PID1 status unavailable: " + status_err[:200])
pid1_uid = parse_effective_id(status_out, "Uid")
pid1_gid = parse_effective_id(status_out, "Gid")

rc, passwd_out, passwd_err = run(["docker", "exec", broker_id, "cat", "/etc/passwd"])
if rc != 0:
    raise RuntimeError("Broker passwd database unavailable: " + passwd_err[:200])
mosquitto_rows = [line for line in passwd_out.splitlines() if line.startswith("mosquitto:")]
if len(mosquitto_rows) != 1:
    raise RuntimeError("mosquitto account is not unique")
parts = mosquitto_rows[0].split(":")
if len(parts) < 7:
    raise RuntimeError("mosquitto account row is malformed")
mosquitto_uid = int(parts[2])
mosquitto_gid = int(parts[3])

image_labels = image.get("Config", {}).get("Labels", {}) or {}
image_version = str(image_labels.get("org.opencontainers.image.version") or "")
image_title = str(image_labels.get("org.opencontainers.image.title") or "")
image_ref = str(broker.get("Config", {}).get("Image") or "")
process_path = str(broker.get("Path") or "")

print(json.dumps({
    "status": "PASS",
    "broker_running": True,
    "broker_restart_count": int(broker.get("RestartCount", 0)),
    "manager_running": True,
    "manager_restart_count": int(manager.get("RestartCount", 0)),
    "broker_container_user_config": str(broker.get("Config", {}).get("User") or ""),
    "broker_image_user_config": str(image.get("Config", {}).get("User") or ""),
    "broker_pid1_uid": pid1_uid,
    "broker_pid1_gid": pid1_gid,
    "mosquitto_account_uid": mosquitto_uid,
    "mosquitto_account_gid": mosquitto_gid,
    "broker_process_is_mosquitto_account": pid1_uid == mosquitto_uid and pid1_gid == mosquitto_gid,
    "broker_image_title": image_title,
    "broker_image_version": image_version,
    "broker_image_ref": image_ref,
    "broker_process_path": process_path,
}, sort_keys=True))
'''


def run_forensic(args: argparse.Namespace) -> int:
    validate_target(args.t1)
    raw = remote_python(args.t1, REMOTE_FORENSIC, timeout=45)
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise StopExecution("permission forensic returned unexpected output")
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise StopExecution("permission forensic output is not JSON") from exc
    if result.get("status") != "PASS":
        raise StopExecution("permission forensic did not PASS")
    if result.get("broker_running") is not True or result.get("manager_running") is not True:
        raise StopExecution("production runtime continuity is not healthy")

    print("GATE_A_T1_LAB_PERMISSION_FORENSIC=PASS")
    print(f"BROKER_IMAGE_TITLE={result.get('broker_image_title')}")
    print(f"BROKER_IMAGE_VERSION={result.get('broker_image_version')}")
    print(f"BROKER_IMAGE_REF={result.get('broker_image_ref')}")
    print(f"BROKER_PROCESS_PATH={result.get('broker_process_path')}")
    print(f"BROKER_CONTAINER_USER_CONFIG={result.get('broker_container_user_config')}")
    print(f"BROKER_IMAGE_USER_CONFIG={result.get('broker_image_user_config')}")
    print(f"BROKER_PID1_UID={result.get('broker_pid1_uid')}")
    print(f"BROKER_PID1_GID={result.get('broker_pid1_gid')}")
    print(f"MOSQUITTO_ACCOUNT_UID={result.get('mosquitto_account_uid')}")
    print(f"MOSQUITTO_ACCOUNT_GID={result.get('mosquitto_account_gid')}")
    print(f"BROKER_PROCESS_IS_MOSQUITTO_ACCOUNT={str(bool(result.get('broker_process_is_mosquitto_account'))).lower()}")
    print(f"BROKER_RESTART_COUNT={result.get('broker_restart_count')}")
    print(f"MANAGER_RESTART_COUNT={result.get('manager_restart_count')}")
    print("PERSISTENT_T1_MUTATION=false")
    print("BOARD_ACCESS=false")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--t1", required=True)
    p.set_defaults(func=run_forensic)
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
