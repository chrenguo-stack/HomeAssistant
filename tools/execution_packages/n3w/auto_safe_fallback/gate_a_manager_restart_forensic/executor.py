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
    args_payload = base64.b64encode(json.dumps(args, separators=(",", ":")).encode("utf-8")).decode("ascii")
    launcher = (
        "import base64,json,sys;"
        "sys.argv=['remote']+json.loads(base64.b64decode(" + repr(args_payload) + "));"
        "exec(base64.b64decode(" + repr(payload) + "))"
    )
    remote_command = "python3 -c " + shlex.quote(launcher)
    ssh = [
        "ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1", "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=2", target, remote_command,
    ]
    return run_capture(ssh, timeout=timeout)


REMOTE_FORENSIC = r"""
import json
import os
import subprocess
import time


def run(argv, timeout=30):
    p = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def inspect(name):
    rc, out, err = run(["docker", "inspect", name])
    if rc != 0:
        raise RuntimeError((err or out)[:250])
    doc = json.loads(out)
    if len(doc) != 1:
        raise RuntimeError("unexpected docker inspect cardinality")
    return doc[0]


if os.geteuid() != 0:
    raise RuntimeError("root SSH required")

manager = inspect("greenhouse-manager")
broker_ids_rc, broker_ids_out, _ = run([
    "docker", "ps", "--filter", "label=com.docker.compose.project=n3wfc4",
    "--filter", "label=com.docker.compose.service=broker", "--format", "{{.ID}}"
])
broker_ids = [x for x in broker_ids_out.splitlines() if x.strip()] if broker_ids_rc == 0 else []
if len(broker_ids) != 1:
    raise RuntimeError("production Broker ownership not unique")
broker = inspect(broker_ids[0])

rc, events_out, _ = run([
    "docker", "events", "--since", "72h", "--until", "0s",
    "--filter", "container=greenhouse-manager", "--format", "{{json .}}"
], timeout=40)
if rc != 0:
    raise RuntimeError("docker events query failed")

events = []
for line in events_out.splitlines():
    if not line.strip():
        continue
    try:
        event = json.loads(line)
    except Exception:
        continue
    action = str(event.get("Action") or "")
    if action not in {"start", "die", "restart", "stop", "kill", "oom", "destroy", "create"}:
        continue
    attrs = event.get("Actor", {}).get("Attributes", {}) or {}
    record = {
        "action": action,
        "time": int(event.get("time") or 0),
    }
    if "exitCode" in attrs:
        record["exit_code"] = str(attrs.get("exitCode"))
    if "signal" in attrs:
        record["signal"] = str(attrs.get("signal"))
    events.append(record)

events = events[-20:]

try:
    with open("/proc/uptime", "r", encoding="utf-8") as handle:
        host_uptime_seconds = int(float(handle.read().split()[0]))
except Exception:
    host_uptime_seconds = -1

state = manager.get("State", {}) or {}
manager_error = str(state.get("Error") or "")
if len(manager_error) > 160:
    manager_error = manager_error[:160]

print(json.dumps({
    "status": "PASS",
    "host_uptime_seconds": host_uptime_seconds,
    "manager_running": state.get("Running") is True,
    "manager_restart_count": int(manager.get("RestartCount", 0)),
    "manager_started_at": str(state.get("StartedAt") or ""),
    "manager_finished_at": str(state.get("FinishedAt") or ""),
    "manager_oom_killed": state.get("OOMKilled") is True,
    "manager_current_exit_code": int(state.get("ExitCode", 0)),
    "manager_state_error": manager_error,
    "manager_restart_policy": str((manager.get("HostConfig", {}).get("RestartPolicy", {}) or {}).get("Name") or ""),
    "manager_events_72h": events,
    "broker_running": (broker.get("State", {}) or {}).get("Running") is True,
    "broker_restart_count": int(broker.get("RestartCount", 0)),
    "broker_started_at": str((broker.get("State", {}) or {}).get("StartedAt") or ""),
}, sort_keys=True))
"""


def parse_single_json(raw: str) -> dict[str, object]:
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise StopExecution("remote forensic returned unexpected output")
    try:
        value = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise StopExecution("remote forensic returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise StopExecution("remote forensic returned non-object JSON")
    return value


def run_forensic(args: argparse.Namespace) -> int:
    validate_target(args.t1)
    remote = parse_single_json(remote_python(args.t1, REMOTE_FORENSIC, [], timeout=60))
    if remote.get("status") != "PASS":
        raise StopExecution("Manager restart forensic did not PASS")
    if remote.get("manager_running") is not True or remote.get("broker_running") is not True:
        raise StopExecution("production runtime is not currently healthy")
    print("GATE_A_MANAGER_RESTART_FORENSIC=PASS")
    print(f"HOST_UPTIME_SECONDS={remote.get('host_uptime_seconds')}")
    print(f"MANAGER_RESTART_COUNT={remote.get('manager_restart_count')}")
    print(f"MANAGER_STARTED_AT={remote.get('manager_started_at')}")
    print(f"MANAGER_FINISHED_AT={remote.get('manager_finished_at')}")
    print(f"MANAGER_OOM_KILLED={str(bool(remote.get('manager_oom_killed'))).lower()}")
    print(f"MANAGER_CURRENT_EXIT_CODE={remote.get('manager_current_exit_code')}")
    print(f"MANAGER_STATE_ERROR={remote.get('manager_state_error')}")
    print(f"MANAGER_RESTART_POLICY={remote.get('manager_restart_policy')}")
    print("MANAGER_EVENTS_72H=" + json.dumps(remote.get("manager_events_72h", []), separators=(",", ":"), sort_keys=True))
    print(f"BROKER_RESTART_COUNT={remote.get('broker_restart_count')}")
    print(f"BROKER_STARTED_AT={remote.get('broker_started_at')}")
    print("T1_MUTATION=false")
    print("BOARD_ACCESS=false")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1", required=True)
    args = parser.parse_args()
    try:
        return run_forensic(args)
    except StopExecution as exc:
        print(f"STOP={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
