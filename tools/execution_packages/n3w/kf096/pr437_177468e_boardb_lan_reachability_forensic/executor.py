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

SCHEMA="n3w.kf096.pr437-177468e.boardb-lan-reachability-forensic/1"
PRODUCT_SOURCE_HEAD="177468e290a207f2fb7f6c554aedf60b61373b4d"
APPLICATION_SHA256="74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
BOARD_B_NODE_ID_SHA256="dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
CANONICAL_ANCHOR_SEQ=49
CANONICAL_ANCHOR_UPDATED_AT="2026-09-20T14:35:06.070Z"
EXACT_CLIENT_DISCONNECT="2026-09-20T14:35:30.732623821Z"
BROKER_LOG_SEARCH_START="2026-09-20T14:25:00Z"

MANAGER_CONTAINER="greenhouse-manager"
BROKER_SERVICE="broker"
BROKER_PROJECT="n3wfc4"

NEW_CLIENT_RE=re.compile(r"New client connected from\s+(.+?)\s+as\s+(\S+)",re.I)
TIMESTAMP_RE=re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
PING_SUMMARY_RE=re.compile(r"(\d+)\s+packets transmitted,\s+(\d+)\s+(?:packets )?received",re.I)


class StopExecution(RuntimeError):
    pass


def sha256_text(value:str)->str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(args:list[str], *, redact:set[str]|None=None)->str:
    p=subprocess.run(args,text=True,capture_output=True,check=False)
    out=(p.stdout or "")+(p.stderr or "")
    if p.returncode!=0:
        safe=["<REDACTED>" if x in (redact or set()) else x for x in args]
        tail=(out.strip().splitlines() or [f"rc={p.returncode}"])[-1]
        raise StopExecution(f"command failed: {' '.join(safe)} :: {tail}")
    return out


def remote(target:str,command:str)->str:
    return run(
        ["ssh","-o","BatchMode=yes","-o","ConnectTimeout=10","-o","ConnectionAttempts=1",target,command],
        redact={target},
    )


def parse_iso(value:str)->dt.datetime:
    parsed=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if parsed.tzinfo is None:
        raise StopExecution("timestamp is not timezone-aware")
    return parsed.astimezone(dt.timezone.utc)


def line_time(line:str)->dt.datetime|None:
    m=TIMESTAMP_RE.search(line)
    if not m:
        return None
    try:
        return parse_iso(m.group(0))
    except Exception:
        return None


def manager_state(target:str)->dict[str,object]:
    fmt="{{.State.Running}}\t{{.RestartCount}}\t{{.State.StartedAt}}"
    raw=remote(target,"docker inspect --format "+shlex.quote(fmt)+" "+shlex.quote(MANAGER_CONTAINER)).strip()
    parts=raw.split("\t")
    if len(parts)!=3:
        raise StopExecution("unable to parse Manager state")
    return {
        "running":parts[0].strip().lower()=="true",
        "restart_count":int(parts[1]),
        "started_at":parts[2].strip(),
    }


def manager_private_binding(target:str)->dict[str,str]:
    code=r'''
import hashlib,json,os,sqlite3,sys
want="dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
replay_path=os.environ.get("GH_N3W_REPLAY_DB_PATH")
pairing_path=os.environ.get("GH_PAIRING_DB_PATH")
if not replay_path or not pairing_path:
 print(json.dumps({"status":"STOP","reason":"required database path missing"})); sys.exit(0)

replay=sqlite3.connect("file:"+replay_path+"?mode=ro",uri=True); replay.row_factory=sqlite3.Row
rows=replay.execute("SELECT node_id,boot_session_hex,seq,last_source,updated_at FROM n3w_canonical_cursors").fetchall()
matches=[dict(r) for r in rows if hashlib.sha256(r["node_id"].encode()).hexdigest()==want]
if len(matches)!=1:
 print(json.dumps({"status":"BAD","count":len(matches)})); sys.exit(0)
c=matches[0]

pairing=sqlite3.connect("file:"+pairing_path+"?mode=ro",uri=True); pairing.row_factory=sqlite3.Row
r=pairing.execute("SELECT hardware_id FROM registrations WHERE node_id=?",(c["node_id"],)).fetchone()
if r is None:
 print(json.dumps({"status":"STOP","reason":"registration missing"})); sys.exit(0)

print(json.dumps({
 "status":"FOUND",
 "node_id":c["node_id"],
 "hardware_id":r["hardware_id"],
 "boot_session_hex":c["boot_session_hex"],
 "seq":c["seq"],
 "last_source":c["last_source"],
 "updated_at":c["updated_at"],
},separators=(",",":")))
'''
    raw=remote(target,f"docker exec {shlex.quote(MANAGER_CONTAINER)} python -c {shlex.quote(code)}").strip()
    obj=json.loads(raw)
    if obj.get("status")!="FOUND":
        raise StopExecution(f"private binding status={obj.get('status')}")
    node_id=str(obj["node_id"])
    if sha256_text(node_id)!=BOARD_B_NODE_ID_SHA256:
        raise StopExecution("resolved node_id does not match frozen Board B hash")
    hardware_id=str(obj["hardware_id"])
    m=re.fullmatch(r"ghw-[a-z0-9]+-([0-9a-fA-F]{12})",hardware_id)
    if m is None:
        raise StopExecution("hardware_id does not expose expected normalized MAC suffix")
    return {
        "node_id":node_id,
        "hardware_id":hardware_id,
        "hardware_mac_hex":m.group(1).lower(),
        "boot_session_hex":str(obj["boot_session_hex"]),
        "seq":str(obj["seq"]),
        "last_source":str(obj["last_source"]),
        "updated_at":str(obj["updated_at"]),
    }


def inventory(target:str)->list[dict[str,Any]]:
    ids=[x.strip() for x in remote(target,"docker ps -aq --no-trunc").splitlines() if x.strip()]
    if not ids:
        raise StopExecution("Docker container inventory is empty")
    value=json.loads(remote(target,"docker inspect "+" ".join(shlex.quote(x) for x in ids)))
    if not isinstance(value,list):
        raise StopExecution("Docker inspect root is not a list")
    return [x for x in value if isinstance(x,dict)]


def select_broker(target:str)->tuple[str,dict[str,object]]:
    matches=[]
    for item in inventory(target):
        cfg=item.get("Config") if isinstance(item.get("Config"),dict) else {}
        labels=cfg.get("Labels") if isinstance(cfg.get("Labels"),dict) else {}
        st=item.get("State") if isinstance(item.get("State"),dict) else {}
        if (
            labels.get("com.docker.compose.service")==BROKER_SERVICE
            and labels.get("com.docker.compose.project")==BROKER_PROJECT
            and st.get("Running") is True
        ):
            matches.append(item)
    if len(matches)!=1:
        raise StopExecution(f"running authoritative Broker count={len(matches)}, expected 1")
    item=matches[0]
    st=item.get("State") if isinstance(item.get("State"),dict) else {}
    return str(item["Id"]),{
        "running":True,
        "restart_count":int(item.get("RestartCount") or 0),
        "started_at":str(st.get("StartedAt") or ""),
    }


def parse_peer_ip(peer:str)->str|None:
    value=peer.strip()
    candidates=[value]
    if value.startswith("[") and "]:" in value:
        candidates.insert(0,value[1:value.index("]:")])
    elif ":" in value:
        candidates.insert(0,value.rsplit(":",1)[0])
    for candidate in candidates:
        candidate=candidate.strip("[]")
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None


def broker_connection_history(target:str,broker_id:str,node_id:str)->dict[str,object]:
    logs=remote(
        target,
        "docker logs --timestamps --since "
        +shlex.quote(BROKER_LOG_SEARCH_START)+" "+shlex.quote(broker_id)+" 2>&1"
    )
    disconnect=parse_iso(EXACT_CLIENT_DISCONNECT)
    connect_events=[]
    disconnect_count_after=0
    connect_count_after=0
    for line in logs.splitlines():
        if node_id not in line:
            continue
        low=line.casefold()
        ts=line_time(line)
        m=NEW_CLIENT_RE.search(line)
        if m and m.group(2).rstrip(".,:;")==node_id:
            ip=parse_peer_ip(m.group(1))
            connect_events.append({"time":ts,"ip":ip})
            if ts and ts>disconnect:
                connect_count_after+=1
        if ("client "+node_id.casefold()) in low and "disconnected" in low and ts and ts>disconnect:
            disconnect_count_after+=1
    pre=[e for e in connect_events if e["time"] is not None and e["time"]<=disconnect and e["ip"]]
    last_pre=max(pre,key=lambda e:e["time"]) if pre else None
    return {
        "last_pre_disconnect_ip":None if last_pre is None else last_pre["ip"],
        "last_pre_disconnect_connect_at":None if last_pre is None else last_pre["time"].isoformat().replace("+00:00","Z"),
        "late_connect_count":connect_count_after,
        "late_disconnect_count":disconnect_count_after,
    }


def remote_shell_capture(target:str,command:str)->tuple[int,str]:
    marker="__N3W_RC__="
    wrapped="set +e; "+command+"; rc=$?; printf '\\n"+marker+"%s\\n' \"$rc\"; exit 0"
    out=remote(target,"sh -c "+shlex.quote(wrapped))
    rc=None
    clean=[]
    for line in out.splitlines():
        if line.startswith(marker):
            try: rc=int(line[len(marker):])
            except ValueError: pass
        else:
            clean.append(line)
    if rc is None:
        raise StopExecution("remote command return marker missing")
    return rc,"\n".join(clean)


def route_probe(target:str,ip:str)->dict[str,object]:
    rc,out=remote_shell_capture(target,"ip route get "+shlex.quote(ip))
    via=bool(re.search(r"\bvia\b",out))
    dev_match=re.search(r"\bdev\s+(\S+)",out)
    return {
        "route_command_rc":rc,
        "route_present":rc==0,
        "direct_l2_route":rc==0 and not via,
        "route_interface_sha256":sha256_text(dev_match.group(1)) if dev_match else None,
    }


def neigh_state(target:str,ip:str)->dict[str,object]:
    rc,out=remote_shell_capture(target,"ip neigh show to "+shlex.quote(ip))
    state=None
    lladdr=None
    if rc==0 and out.strip():
        parts=out.strip().split()
        for token in ("REACHABLE","STALE","DELAY","PROBE","FAILED","INCOMPLETE","NOARP","PERMANENT"):
            if token in parts:
                state=token
                break
        if "lladdr" in parts:
            idx=parts.index("lladdr")
            if idx+1<len(parts):
                lladdr=parts[idx+1]
    return {"rc":rc,"state":state,"lladdr":lladdr}


def normalize_mac(value:str|None)->str|None:
    if not value:
        return None
    compact=re.sub(r"[^0-9a-fA-F]","",value).lower()
    return compact if len(compact)==12 else None


def ping_probe(target:str,ip:str)->dict[str,object]:
    rc,out=remote_shell_capture(target,"ping -n -c 4 -W 1 "+shlex.quote(ip))
    tx=rx=None
    m=PING_SUMMARY_RE.search(out)
    if m:
        tx=int(m.group(1)); rx=int(m.group(2))
    return {
        "command_rc":rc,
        "packets_transmitted":tx,
        "packets_received":rx,
        "reachable":bool(rx is not None and rx>0),
    }


def write_json(path:Path,payload:dict[str,object])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    path.chmod(0o600)


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--t1-target",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    output=Path(args.output)

    result:dict[str,object]={
        "schema":SCHEMA,
        "status":"STOP",
        "product_source_head":PRODUCT_SOURCE_HEAD,
        "application_sha256":APPLICATION_SHA256,
        "board_b_node_id_sha256":BOARD_B_NODE_ID_SHA256,
        "board_access":False,
        "board_reset":False,
        "board_flash_write":False,
        "product_nvs_write":False,
        "application_serial_open":False,
        "t1_mutation":False,
        "network_probe":"ICMP_ONLY",
        "mqtt_test_publish":False,
        "mqtt_extra_subscriber":False,
    }

    try:
        manager=manager_state(args.t1_target)
        if not manager["running"]:
            raise StopExecution("Manager is not running")
        private=manager_private_binding(args.t1_target)
        broker_id,broker=select_broker(args.t1_target)
        history=broker_connection_history(args.t1_target,broker_id,private["node_id"])

        current_seq=int(private["seq"])
        current_source=private["last_source"]
        current_updated=private["updated_at"]
        canonical_advanced=(
            current_seq>CANONICAL_ANCHOR_SEQ
            or current_updated!=CANONICAL_ANCHOR_UPDATED_AT
        )

        ip=history["last_pre_disconnect_ip"]
        network:dict[str,object]={"source_ip_authority_found":ip is not None}
        if ip is not None:
            route=route_probe(args.t1_target,str(ip))
            before=neigh_state(args.t1_target,str(ip))
            ping=ping_probe(args.t1_target,str(ip))
            after=neigh_state(args.t1_target,str(ip))
            expected_mac=private["hardware_mac_hex"]
            before_mac=normalize_mac(before.get("lladdr") if isinstance(before,dict) else None)
            after_mac=normalize_mac(after.get("lladdr") if isinstance(after,dict) else None)
            neighbor_mac_match=None
            if route["direct_l2_route"] and after_mac is not None:
                neighbor_mac_match=after_mac==expected_mac

            network.update({
                "source_ip_sha256":sha256_text(str(ip)),
                "last_pre_disconnect_connect_at":history["last_pre_disconnect_connect_at"],
                "route":route,
                "neighbor_state_before":before.get("state"),
                "neighbor_state_after":after.get("state"),
                "neighbor_mac_match_board_b":neighbor_mac_match,
                "ping":ping,
            })

        late_connect_count=int(history["late_connect_count"])
        if canonical_advanced:
            classification="CANONICAL_RECOVERY_OBSERVED"
        elif late_connect_count>0:
            classification="LATE_MQTT_RECONNECT_CANONICAL_STILL_STALE"
        elif ip is None:
            classification="NO_PRIOR_SOURCE_IP_AUTHORITY"
        else:
            ping=network.get("ping")
            reachable=bool(isinstance(ping,dict) and ping.get("reachable"))
            mac_match=network.get("neighbor_mac_match_board_b")
            if reachable and mac_match is True:
                classification="BOARD_B_LAN_REACHABLE_MQTT_RECONNECT_NOT_OBSERVED"
            elif reachable:
                classification="SOURCE_IP_REACHABLE_BUT_BOARD_B_L2_IDENTITY_UNPROVEN"
            else:
                classification="BOARD_B_LAN_UNREACHABLE_OR_NONRESPONSIVE_MQTT_RECONNECT_NOT_OBSERVED"

        public_binding={
            "boot_session_sha256":sha256_text(private["boot_session_hex"]),
            "seq":current_seq,
            "last_source":current_source,
            "updated_at":current_updated,
            "canonical_advanced":canonical_advanced,
            "hardware_id_sha256":sha256_text(private["hardware_id"]),
        }

        result.update({
            "status":"PASS",
            "manager":manager,
            "broker":broker,
            "current_canonical":public_binding,
            "broker_history":{
                "late_connect_count":late_connect_count,
                "late_disconnect_count":int(history["late_disconnect_count"]),
            },
            "network":network,
            "classification":classification,
        })
        write_json(output,result)

        print("BOARD_B_LAN_REACHABILITY_FORENSIC=PASS")
        print(f"T1_MANAGER_RUNNING={str(manager['running']).lower()}")
        print(f"MANAGER_RESTART_COUNT={manager['restart_count']}")
        print(f"BROKER_RUNNING={str(broker['running']).lower()}")
        print(f"BROKER_RESTART_COUNT={broker['restart_count']}")
        print(f"CURRENT_CANONICAL_SEQ={current_seq}")
        print(f"CURRENT_CANONICAL_SOURCE={current_source}")
        print(f"CURRENT_CANONICAL_UPDATED_AT={current_updated}")
        print(f"CURRENT_CANONICAL_ADVANCED={str(canonical_advanced).lower()}")
        print(f"BOARD_B_LATE_BROKER_CONNECT_COUNT={late_connect_count}")
        print(f"SOURCE_IP_AUTHORITY_FOUND={str(ip is not None).lower()}")
        if ip is not None:
            route=network["route"]; ping=network["ping"]
            assert isinstance(route,dict) and isinstance(ping,dict)
            print(f"DIRECT_L2_ROUTE={str(route['direct_l2_route']).lower()}")
            print(f"PING_PACKETS_TRANSMITTED={ping['packets_transmitted']}")
            print(f"PING_PACKETS_RECEIVED={ping['packets_received']}")
            print(f"PING_REACHABLE={str(ping['reachable']).lower()}")
            match=network["neighbor_mac_match_board_b"]
            print(
                "NEIGHBOR_MAC_MATCH_BOARD_B="
                +("UNKNOWN" if match is None else str(match).lower())
            )
            print(
                "NEIGHBOR_STATE_AFTER="
                +str(network["neighbor_state_after"] or "NONE")
            )
        print(f"LAN_REACHABILITY_CLASSIFICATION={classification}")
        print("NETWORK_PROBE=ICMP_ONLY")
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
        result["stop_reason"]=f"{type(exc).__name__}: {exc}"
        write_json(output,result)
        print(f"STOP={exc}",file=sys.stderr)
        print("BOARD_ACCESS=false",file=sys.stderr)
        print("BOARD_RESET=false",file=sys.stderr)
        print("BOARD_FLASH_WRITE=false",file=sys.stderr)
        print("PRODUCT_NVS_WRITE=false",file=sys.stderr)
        print("APPLICATION_SERIAL_OPEN=false",file=sys.stderr)
        print("MQTT_TEST_PUBLISH=false",file=sys.stderr)
        print("MQTT_EXTRA_SUBSCRIBER=false",file=sys.stderr)
        print("T1_MUTATION=false",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
