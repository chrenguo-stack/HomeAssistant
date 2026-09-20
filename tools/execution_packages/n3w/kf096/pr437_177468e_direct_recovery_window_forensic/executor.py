from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "n3w.kf096.pr437-177468e.direct-recovery-window-forensic/1"

PRODUCT_SOURCE_HEAD = "177468e290a207f2fb7f6c554aedf60b61373b4d"
APPLICATION_SHA256 = "74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
BOARD_B_NODE_ID_SHA256 = "dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"

CANONICAL_ANCHOR_SEQ = 49
CANONICAL_ANCHOR_UPDATED_AT = "2026-09-20T14:35:06.070Z"
EXACT_CLIENT_DISCONNECT = "2026-09-20T14:35:30.732623821Z"
BROKER_LOG_SEARCH_START = "2026-09-20T14:25:00Z"

MANAGER_CONTAINER = "greenhouse-manager"
BROKER_SERVICE = "broker"
BROKER_PROJECT = "n3wfc4"

OBSERVATION_SECONDS = 150
SAMPLE_INTERVAL_SECONDS = 5

NEW_CLIENT_RE = re.compile(r"New client connected from\s+(.+?)\s+as\s+(\S+)", re.I)


class StopExecution(RuntimeError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(args: list[str], *, redact: set[str] | None = None) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        safe = ["<REDACTED>" if item in (redact or set()) else item for item in args]
        tail = (output.strip().splitlines() or [f"rc={proc.returncode}"])[-1]
        raise StopExecution(f"command failed: {' '.join(safe)} :: {tail}")
    return output


def remote(target: str, command: str) -> str:
    return run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ConnectionAttempts=1",
            target,
            command,
        ],
        redact={target},
    )


def manager_state(target: str) -> dict[str, object]:
    fmt = "{{.State.Running}}\\t{{.RestartCount}}\\t{{.State.StartedAt}}"
    raw = remote(
        target,
        "docker inspect --format "
        + shlex.quote(fmt)
        + f" {shlex.quote(MANAGER_CONTAINER)}",
    ).strip()
    parts = raw.split("\\t")
    if len(parts) != 3:
        raise StopExecution("unable to parse Manager state")
    return {
        "running": parts[0].lower() == "true",
        "restart_count": int(parts[1]),
        "started_at": parts[2],
    }


def private_binding(target: str) -> dict[str, str]:
    code = r'''
import hashlib,json,os,sqlite3,sys
want="dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
rp=os.environ.get("GH_N3W_REPLAY_DB_PATH")
pp=os.environ.get("GH_PAIRING_DB_PATH")
if not rp or not pp:
 print(json.dumps({"status":"STOP","reason":"db path missing"})); sys.exit(0)
rdb=sqlite3.connect("file:"+rp+"?mode=ro",uri=True); rdb.row_factory=sqlite3.Row
rows=rdb.execute("SELECT node_id,boot_session_hex,seq,last_source,updated_at FROM n3w_canonical_cursors").fetchall()
m=[dict(r) for r in rows if hashlib.sha256(r["node_id"].encode()).hexdigest()==want]
if len(m)!=1:
 print(json.dumps({"status":"BAD","count":len(m)})); sys.exit(0)
c=m[0]
pdb=sqlite3.connect("file:"+pp+"?mode=ro",uri=True); pdb.row_factory=sqlite3.Row
reg=pdb.execute("SELECT hardware_id FROM registrations WHERE node_id=?",(c["node_id"],)).fetchone()
if reg is None:
 print(json.dumps({"status":"STOP","reason":"registration missing"})); sys.exit(0)
print(json.dumps({
 "status":"FOUND",
 "node_id":c["node_id"],
 "hardware_id":reg["hardware_id"],
 "boot_session_hex":c["boot_session_hex"],
 "seq":c["seq"],
 "last_source":c["last_source"],
 "updated_at":c["updated_at"],
},separators=(",",":")))
'''
    raw = remote(
        target,
        f"docker exec {shlex.quote(MANAGER_CONTAINER)} python -c {shlex.quote(code)}",
    ).strip()
    obj = json.loads(raw)
    if obj.get("status") != "FOUND":
        raise StopExecution(f"private binding status={obj.get('status')}")
    node_id = str(obj["node_id"])
    if sha256_text(node_id) != BOARD_B_NODE_ID_SHA256:
        raise StopExecution("resolved node_id hash mismatch")
    hw = str(obj["hardware_id"])
    m = re.fullmatch(r"ghw-[a-z0-9]+-([0-9a-fA-F]{12})", hw)
    if m is None:
        raise StopExecution("hardware_id MAC suffix unavailable")
    return {
        "node_id": node_id,
        "hardware_id": hw,
        "hardware_mac_hex": m.group(1).lower(),
        "boot_session_hex": str(obj["boot_session_hex"]),
        "seq": str(obj["seq"]),
        "last_source": str(obj["last_source"]),
        "updated_at": str(obj["updated_at"]),
    }


def inventory(target: str) -> list[dict[str, Any]]:
    ids = [x.strip() for x in remote(target, "docker ps -aq --no-trunc").splitlines() if x.strip()]
    value = json.loads(
        remote(target, "docker inspect " + " ".join(shlex.quote(x) for x in ids))
    )
    return [x for x in value if isinstance(x, dict)]


def select_broker(target: str) -> tuple[str, dict[str, object]]:
    matches = []
    for item in inventory(target):
        cfg = item.get("Config") if isinstance(item.get("Config"), dict) else {}
        labels = cfg.get("Labels") if isinstance(cfg.get("Labels"), dict) else {}
        st = item.get("State") if isinstance(item.get("State"), dict) else {}
        if (
            labels.get("com.docker.compose.service") == BROKER_SERVICE
            and labels.get("com.docker.compose.project") == BROKER_PROJECT
            and st.get("Running") is True
        ):
            matches.append(item)
    if len(matches) != 1:
        raise StopExecution(f"running authoritative Broker count={len(matches)}")
    item = matches[0]
    st = item["State"]
    return str(item["Id"]), {
        "running": True,
        "restart_count": int(item.get("RestartCount") or 0),
        "started_at": str(st.get("StartedAt") or ""),
    }


def parse_peer_ip(peer: str) -> str | None:
    value = peer.strip()
    candidates = [value]
    if value.startswith("[") and "]:" in value:
        candidates.insert(0, value[1:value.index("]:")])
    elif ":" in value:
        candidates.insert(0, value.rsplit(":", 1)[0])
    for candidate in candidates:
        candidate = candidate.strip("[]")
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None


def broker_logs(target: str, broker_id: str, since: str) -> str:
    return remote(
        target,
        "docker logs --timestamps --since "
        + shlex.quote(since)
        + " "
        + shlex.quote(broker_id)
        + " 2>&1",
    )


def find_last_pre_disconnect_ip(logs: str, node_id: str) -> str | None:
    cutoff = dt.datetime.fromisoformat(EXACT_CLIENT_DISCONNECT.replace("Z", "+00:00"))
    found: list[tuple[dt.datetime, str]] = []
    ts_re = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
    for line in logs.splitlines():
        if node_id not in line:
            continue
        m = NEW_CLIENT_RE.search(line)
        if not m or m.group(2).rstrip(".,:;") != node_id:
            continue
        tsm = ts_re.search(line)
        if tsm is None:
            continue
        stamp = dt.datetime.fromisoformat(tsm.group(0).replace("Z", "+00:00"))
        if stamp > cutoff:
            continue
        ip = parse_peer_ip(m.group(1))
        if ip is not None:
            found.append((stamp, ip))
    return max(found, key=lambda item: item[0])[1] if found else None


def count_late_connects(logs: str, node_id: str) -> int:
    cutoff = dt.datetime.fromisoformat(EXACT_CLIENT_DISCONNECT.replace("Z", "+00:00"))
    ts_re = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
    count = 0
    for line in logs.splitlines():
        if node_id not in line:
            continue
        m = NEW_CLIENT_RE.search(line)
        if not m or m.group(2).rstrip(".,:;") != node_id:
            continue
        tsm = ts_re.search(line)
        if tsm is None:
            continue
        stamp = dt.datetime.fromisoformat(tsm.group(0).replace("Z", "+00:00"))
        if stamp > cutoff:
            count += 1
    return count


def run_remote_window(target: str, ip: str, expected_mac_hex: str) -> dict[str, object]:
    code = r'''
import json,os,re,subprocess,time
ip=os.environ["N3W_PRIVATE_IP"]
expected=os.environ["N3W_EXPECTED_MAC"]
duration=int(os.environ["N3W_DURATION"])
interval=int(os.environ["N3W_INTERVAL"])
mac_rx=re.compile(r"\blladdr\s+([0-9a-fA-F:]{17})\b")
start=time.monotonic()
samples=0
ping_success=0
mac_match_count=0
neighbor_states={}
first_success_s=None
last_success_s=None
while True:
    elapsed=time.monotonic()-start
    if elapsed>duration:
        break
    p=subprocess.run(["ping","-n","-c","1","-W","1",ip],capture_output=True,text=True,check=False)
    samples+=1
    if p.returncode==0:
        ping_success+=1
        if first_success_s is None:first_success_s=round(elapsed,3)
        last_success_s=round(elapsed,3)
    n=subprocess.run(["ip","neigh","show","to",ip],capture_output=True,text=True,check=False)
    text=n.stdout.strip()
    state="NONE"
    for token in ("REACHABLE","STALE","DELAY","PROBE","FAILED","INCOMPLETE","NOARP","PERMANENT"):
        if token in text.split():
            state=token; break
    neighbor_states[state]=neighbor_states.get(state,0)+1
    m=mac_rx.search(text)
    if m:
        compact=re.sub(r"[^0-9a-fA-F]","",m.group(1)).lower()
        if compact==expected:
            mac_match_count+=1
    remaining=duration-(time.monotonic()-start)
    if remaining<=0:break
    time.sleep(min(interval,remaining))
print(json.dumps({
 "samples":samples,
 "ping_success_count":ping_success,
 "neighbor_mac_match_count":mac_match_count,
 "neighbor_states":neighbor_states,
 "first_ping_success_elapsed_s":first_success_s,
 "last_ping_success_elapsed_s":last_success_s,
},separators=(",",":")))
'''
    env_assign = (
        "N3W_PRIVATE_IP=" + shlex.quote(ip) + " "
        + "N3W_EXPECTED_MAC=" + shlex.quote(expected_mac_hex) + " "
        + f"N3W_DURATION={OBSERVATION_SECONDS} "
        + f"N3W_INTERVAL={SAMPLE_INTERVAL_SECONDS} "
    )
    raw = remote(
        target,
        env_assign
        + f"python3 -c {shlex.quote(code)}",
    ).strip()
    return json.loads(raw)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1-target", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    result: dict[str, object] = {
        "schema": SCHEMA,
        "status": "STOP",
        "product_source_head": PRODUCT_SOURCE_HEAD,
        "application_sha256": APPLICATION_SHA256,
        "observation_seconds": OBSERVATION_SECONDS,
        "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
        "board_access": False,
        "board_reset": False,
        "board_flash_write": False,
        "product_nvs_write": False,
        "application_serial_open": False,
        "mqtt_test_publish": False,
        "mqtt_extra_subscriber": False,
        "t1_mutation": False,
        "network_probe": "ICMP_ONLY",
    }

    try:
        manager_before = manager_state(args.t1_target)
        if not manager_before["running"]:
            raise StopExecution("Manager is not running")
        before = private_binding(args.t1_target)
        broker_id, broker_before = select_broker(args.t1_target)
        prior_logs = broker_logs(args.t1_target, broker_id, BROKER_LOG_SEARCH_START)
        source_ip = find_last_pre_disconnect_ip(prior_logs, before["node_id"])
        if source_ip is None:
            raise StopExecution("prior Board B source IP authority unavailable")

        window = run_remote_window(
            args.t1_target, source_ip, before["hardware_mac_hex"]
        )

        after = private_binding(args.t1_target)
        manager_after = manager_state(args.t1_target)
        broker_id_after, broker_after = select_broker(args.t1_target)
        if broker_id_after != broker_id:
            raise StopExecution("authoritative Broker container changed during window")

        post_logs = broker_logs(args.t1_target, broker_id, BROKER_LOG_SEARCH_START)
        late_connects = count_late_connects(post_logs, after["node_id"])

        canonical_advanced = (
            int(after["seq"]) > CANONICAL_ANCHOR_SEQ
            or after["updated_at"] != CANONICAL_ANCHOR_UPDATED_AT
        )
        manager_continuity = (
            manager_before["running"]
            and manager_after["running"]
            and manager_before["restart_count"] == manager_after["restart_count"]
            and manager_before["started_at"] == manager_after["started_at"]
        )
        broker_continuity = (
            broker_before["running"]
            and broker_after["running"]
            and broker_before["restart_count"] == broker_after["restart_count"]
            and broker_before["started_at"] == broker_after["started_at"]
        )

        ping_success = int(window.get("ping_success_count", 0))
        mac_match_count = int(window.get("neighbor_mac_match_count", 0))

        if canonical_advanced:
            classification = "CANONICAL_RECOVERY_OBSERVED_DURING_WINDOW"
        elif late_connects > 0:
            classification = "MQTT_RECONNECT_OBSERVED_CANONICAL_STILL_STALE"
        elif ping_success > 0 and mac_match_count > 0:
            classification = "BOARD_B_PERIODIC_LAN_WINDOW_OBSERVED_MQTT_NOT_RECOVERED"
        elif ping_success > 0:
            classification = "PRIOR_SOURCE_IP_PERIODIC_RESPONSE_IDENTITY_UNPROVEN"
        else:
            classification = "NO_BOARD_B_LAN_RESPONSE_ACROSS_150S_WINDOW"

        safe_before = {
            "seq": int(before["seq"]),
            "last_source": before["last_source"],
            "updated_at": before["updated_at"],
            "boot_session_sha256": sha256_text(before["boot_session_hex"]),
        }
        safe_after = {
            "seq": int(after["seq"]),
            "last_source": after["last_source"],
            "updated_at": after["updated_at"],
            "boot_session_sha256": sha256_text(after["boot_session_hex"]),
        }

        result.update(
            {
                "status": "PASS",
                "manager_continuity": manager_continuity,
                "broker_continuity": broker_continuity,
                "canonical_before": safe_before,
                "canonical_after": safe_after,
                "canonical_advanced": canonical_advanced,
                "source_ip_sha256": sha256_text(source_ip),
                "window": window,
                "late_broker_connect_count": late_connects,
                "classification": classification,
            }
        )
        write_json(output, result)

        print("DIRECT_RECOVERY_WINDOW_FORENSIC=PASS")
        print(f"OBSERVATION_SECONDS={OBSERVATION_SECONDS}")
        print(f"SAMPLE_INTERVAL_SECONDS={SAMPLE_INTERVAL_SECONDS}")
        print(f"MANAGER_CONTINUITY={str(manager_continuity).lower()}")
        print(f"BROKER_CONTINUITY={str(broker_continuity).lower()}")
        print(f"CANONICAL_SEQ_BEFORE={safe_before['seq']}")
        print(f"CANONICAL_SEQ_AFTER={safe_after['seq']}")
        print(f"CANONICAL_ADVANCED={str(canonical_advanced).lower()}")
        print(f"LATE_BROKER_CONNECT_COUNT={late_connects}")
        print(f"PING_SAMPLE_COUNT={window['samples']}")
        print(f"PING_SUCCESS_COUNT={window['ping_success_count']}")
        print(f"NEIGHBOR_MAC_MATCH_COUNT={window['neighbor_mac_match_count']}")
        print(
            "NEIGHBOR_STATES="
            + json.dumps(window["neighbor_states"], sort_keys=True, separators=(",", ":"))
        )
        print(f"DIRECT_RECOVERY_WINDOW_CLASSIFICATION={classification}")
        print("BOARD_ACCESS=false")
        print("BOARD_RESET=false")
        print("BOARD_FLASH_WRITE=false")
        print("PRODUCT_NVS_WRITE=false")
        print("APPLICATION_SERIAL_OPEN=false")
        print("MQTT_TEST_PUBLISH=false")
        print("MQTT_EXTRA_SUBSCRIBER=false")
        print("T1_MUTATION=false")
        return 0

    except Exception as exc:
        result["stop_reason"] = f"{type(exc).__name__}: {exc}"
        write_json(output, result)
        print(f"STOP={exc}", file=sys.stderr)
        print("BOARD_ACCESS=false", file=sys.stderr)
        print("BOARD_RESET=false", file=sys.stderr)
        print("BOARD_FLASH_WRITE=false", file=sys.stderr)
        print("PRODUCT_NVS_WRITE=false", file=sys.stderr)
        print("APPLICATION_SERIAL_OPEN=false", file=sys.stderr)
        print("MQTT_TEST_PUBLISH=false", file=sys.stderr)
        print("MQTT_EXTRA_SUBSCRIBER=false", file=sys.stderr)
        print("T1_MUTATION=false", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
