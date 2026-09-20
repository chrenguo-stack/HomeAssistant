from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA="n3w.kf096.pr437-177468e.disconnect-context-t1-forensic-r2/1"
PRODUCT_SOURCE_HEAD="177468e290a207f2fb7f6c554aedf60b61373b4d"
APPLICATION_SHA256="74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"
BOARD_B_NODE_ID_SHA256="dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
CANONICAL_ANCHOR="2026-09-20T14:35:06.070Z"
PRIOR_EXACT_DISCONNECT="2026-09-20T14:35:30.732623821Z"
LOG_WINDOW_START="2026-09-20T14:34:00Z"
LOG_WINDOW_END="2026-09-20T14:40:00Z"
MANAGER_CONTAINER="greenhouse-manager"
BROKER_SERVICE="broker"
BROKER_PROJECT="n3wfc4"
ISO_RE=re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\b")
CLIENT_DISC_RE=re.compile(r"\bclient\s+(\S+)\s+disconnected\b",re.I)
NEW_CLIENT_RE=re.compile(r"\bnew client connected\b.*\bas\s+(\S+)",re.I)

class StopExecution(RuntimeError): pass

def sha256_text(v:str)->str:
    return hashlib.sha256(v.encode()).hexdigest()

def run(args:list[str],redact:set[str]|None=None)->str:
    p=subprocess.run(args,text=True,capture_output=True,check=False)
    out=(p.stdout or "")+(p.stderr or "")
    if p.returncode:
        safe=["<REDACTED>" if x in (redact or set()) else x for x in args]
        tail=(out.strip().splitlines() or [f"rc={p.returncode}"])[-1]
        raise StopExecution(f"command failed: {' '.join(safe)} :: {tail}")
    return out

def remote(target:str,cmd:str)->str:
    return run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=10","-o","ConnectionAttempts=1",target,cmd],{target})

def parse_iso(v:str)->dt.datetime:
    x=dt.datetime.fromisoformat(v.replace("Z","+00:00"))
    if x.tzinfo is None: raise StopExecution("naive timestamp")
    return x.astimezone(dt.timezone.utc)

def line_ts(line:str)->dt.datetime|None:
    m=ISO_RE.search(line)
    if not m: return None
    try: return parse_iso(m.group(0))
    except Exception: return None

def manager_state(target:str)->dict[str,object]:
    fmt="{{.State.Running}}\t{{.RestartCount}}\t{{.State.StartedAt}}"
    raw=remote(target,"docker inspect --format "+shlex.quote(fmt)+" "+shlex.quote(MANAGER_CONTAINER)).strip()
    p=raw.split("\t")
    if len(p)!=3: raise StopExecution("cannot parse manager state")
    return {"running":p[0].lower()=="true","restart_count":int(p[1]),"started_at":p[2]}

def private_runtime(target:str)->dict[str,str]:
    code=r'''
import hashlib,json,os,sqlite3,sys
want="dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59"
path=os.environ.get("GH_N3W_REPLAY_DB_PATH"); sid=os.environ.get("GH_SYSTEM_ID")
mcid=os.environ.get("GH_MQTT_CLIENT_ID"); port=os.environ.get("GH_MQTT_PORT")
if not all((path,sid,mcid,port)):
 print(json.dumps({"status":"STOP"})); sys.exit(0)
db=sqlite3.connect("file:"+path+"?mode=ro",uri=True); db.row_factory=sqlite3.Row
rows=db.execute("SELECT node_id,seq,last_source,updated_at FROM n3w_canonical_cursors").fetchall()
m=[dict(r) for r in rows if hashlib.sha256(r["node_id"].encode()).hexdigest()==want]
if len(m)!=1:
 print(json.dumps({"status":"BAD","count":len(m)})); sys.exit(0)
r=m[0]
print(json.dumps({"status":"FOUND","node_id":r["node_id"],"system_id":sid,"manager_client_id":mcid,"mqtt_port":port,"seq":r["seq"],"last_source":r["last_source"],"updated_at":r["updated_at"]},separators=(",",":")))
'''
    raw=remote(target,f"docker exec {shlex.quote(MANAGER_CONTAINER)} python -c {shlex.quote(code)}").strip()
    obj=json.loads(raw)
    if obj.get("status")!="FOUND": raise StopExecution(f"runtime resolver status={obj.get('status')}")
    if sha256_text(str(obj["node_id"]))!=BOARD_B_NODE_ID_SHA256: raise StopExecution("node hash mismatch")
    return {k:str(v) for k,v in obj.items() if k!="status"}

def manager_socket_now(target:str)->dict[str,object]:
    code=r'''
import json,os,re,time
port=int(os.environ["GH_MQTT_PORT"]); rx=re.compile(r"^socket:\[(\d+)\]$")
def sample():
 owned=set()
 for n in os.listdir("/proc/1/fd"):
  try:t=os.readlink("/proc/1/fd/"+n)
  except OSError:continue
  m=rx.match(t)
  if m:owned.add(m.group(1))
 found=set()
 for p in ("/proc/1/net/tcp","/proc/1/net/tcp6"):
  try:ls=open(p,encoding="ascii").read().splitlines()[1:]
  except OSError:continue
  for line in ls:
   f=line.split()
   if len(f)<10 or f[3]!="01":continue
   try:rport=int(f[2].rsplit(":",1)[1],16)
   except ValueError:continue
   if rport==port and f[9] in owned:found.add(f[9])
 return found
s=[]
for i in range(3):
 s.append(sample())
 if i<2:time.sleep(1)
print(json.dumps({"counts":[len(x) for x in s],"stable":bool(s[0] and s[0]&s[1]&s[2])},separators=(",",":")))
'''
    return json.loads(remote(target,f"docker exec {shlex.quote(MANAGER_CONTAINER)} python -c {shlex.quote(code)}").strip())

def inventory(target:str)->list[dict[str,Any]]:
    ids=[x for x in remote(target,"docker ps -aq --no-trunc").splitlines() if x.strip()]
    if not ids: raise StopExecution("no docker containers")
    obj=json.loads(remote(target,"docker inspect "+" ".join(shlex.quote(x) for x in ids)))
    return [x for x in obj if isinstance(x,dict)]

def broker(target:str)->tuple[str,dict[str,object]]:
    ms=[]
    for x in inventory(target):
        cfg=x.get("Config") if isinstance(x.get("Config"),dict) else {}
        labels=cfg.get("Labels") if isinstance(cfg.get("Labels"),dict) else {}
        st=x.get("State") if isinstance(x.get("State"),dict) else {}
        if labels.get("com.docker.compose.service")==BROKER_SERVICE and labels.get("com.docker.compose.project")==BROKER_PROJECT and st.get("Running") is True:
            ms.append(x)
    if len(ms)!=1: raise StopExecution(f"broker count={len(ms)}")
    x=ms[0]; st=x["State"]; bid=str(x["Id"])
    return bid,{"running":True,"restart_count":int(x.get("RestartCount") or 0),"started_at":str(st.get("StartedAt") or "")}

def error_category(line:str)->str|None:
    s=line.casefold()
    if not any(k in s for k in ("error","failed","failure","denied","authoris","authentic")): return None
    if any(k in s for k in ("ssl","tls","openssl","certificate","handshake")): return "TLS_SSL"
    if any(k in s for k in ("not authorised","not authorized","acl","authentication","bad user name","password","denied")): return "AUTH_ACL"
    if any(k in s for k in ("protocol","malformed","packet")): return "PROTOCOL"
    if any(k in s for k in ("socket","network","connection","broken pipe","reset by peer","timed out","timeout")): return "SOCKET_NETWORK"
    if any(k in s for k in ("memory","resource","too many","file descriptor")): return "RESOURCE"
    if any(k in s for k in ("config","listener","bind","address already in use","persistence")): return "BROKER_RUNTIME"
    return "OTHER_ERROR"

def analyze(logs:str,board_id:str,manager_id:str)->dict[str,object]:
    center=parse_iso(PRIOR_EXACT_DISCONNECT)
    board_disc=[]; board_conn_after=[]; board_conn_before=[]
    manager_disc=[]; manager_conn=[]
    other_disc=set(); other_conn=set()
    err=Counter(); err_ts=[]; d5=d30=e5=e30=0
    for line in logs.splitlines():
        low=line.casefold(); ts=line_ts(line)
        # Robust exact Board-B detector: same semantics as the previous successful gate.
        if ("client "+board_id.casefold()) in low and "disconnected" in low:
            board_disc.append(ts.isoformat().replace("+00:00","Z") if ts else "UNKNOWN")
        m=NEW_CLIENT_RE.search(line)
        if m:
            cid=m.group(1).rstrip(".,:;)")
            if cid==board_id:
                (board_conn_after if ts and ts>center else board_conn_before).append(ts.isoformat().replace("+00:00","Z") if ts else "UNKNOWN")
            elif cid==manager_id: manager_conn.append(ts.isoformat().replace("+00:00","Z") if ts else "UNKNOWN")
            else: other_conn.add(cid)
        m=CLIENT_DISC_RE.search(line)
        if m:
            cid=m.group(1).rstrip(".,:;)")
            if cid==manager_id: manager_disc.append(ts.isoformat().replace("+00:00","Z") if ts else "UNKNOWN")
            elif cid!=board_id:
                other_disc.add(cid)
                if ts:
                    delta=abs((ts-center).total_seconds())
                    d5+=delta<=5; d30+=delta<=30
        cat=error_category(line)
        if cat:
            err[cat]+=1
            if ts:
                err_ts.append(ts.isoformat().replace("+00:00","Z"))
                delta=abs((ts-center).total_seconds())
                e5+=delta<=5; e30+=delta<=30
    return {
      "prior_exact_disconnect_authority":True,
      "exact_disconnect_reobserved":bool(board_disc),
      "exact_disconnect_reobserved_count":len(board_disc),
      "exact_disconnect_timestamps":board_disc,
      "board_connection_before_count":len(board_conn_before),
      "board_connection_after_count":len(board_conn_after),
      "board_connection_after_timestamps":board_conn_after,
      "manager_disconnect_count":len(manager_disc),
      "manager_connection_count":len(manager_conn),
      "other_unique_disconnect_client_count":len(other_disc),
      "other_unique_connect_client_count":len(other_conn),
      "other_disconnect_count_within_5s":d5,
      "other_disconnect_count_within_30s":d30,
      "mass_disconnect_near_event":bool(d5>=2 or d30>=3),
      "generic_error_categories":dict(sorted(err.items())),
      "generic_error_timestamps":err_ts,
      "generic_error_count_within_5s":e5,
      "generic_error_count_within_30s":e30,
      "broker_error_cluster_near_event":bool(e5>=1 or e30>=2),
    }

def dump(path:Path,obj:dict[str,object])->None:
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8"); path.chmod(0o600)

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--t1-target",required=True); ap.add_argument("--output",required=True); a=ap.parse_args()
    out=Path(a.output)
    result={"schema":SCHEMA,"status":"STOP","product_source_head":PRODUCT_SOURCE_HEAD,"application_sha256":APPLICATION_SHA256,
      "board_access":False,"board_reset":False,"board_flash_write":False,"product_nvs_write":False,"application_serial_open":False,
      "mqtt_test_publish":False,"mqtt_extra_subscriber":False,"t1_access":"SSH_READ_ONLY","t1_mutation":False}
    try:
        ms=manager_state(a.t1_target)
        if not ms["running"]: raise StopExecution("manager not running")
        priv=private_runtime(a.t1_target)
        if priv["updated_at"]!=CANONICAL_ANCHOR or priv["seq"]!="49" or priv["last_source"]!="direct": raise StopExecution("canonical anchor changed")
        sock=manager_socket_now(a.t1_target)
        bid,bs=broker(a.t1_target)
        logs=remote(a.t1_target,"docker logs --timestamps --since "+shlex.quote(LOG_WINDOW_START)+" --until "+shlex.quote(LOG_WINDOW_END)+" "+shlex.quote(bid)+" 2>&1")
        an=analyze(logs,priv["node_id"],priv["manager_client_id"])
        if an["mass_disconnect_near_event"]: cls="BROKER_WIDE_CLIENT_CHURN_NEAR_BOARD_B_DISCONNECT"
        elif an["broker_error_cluster_near_event"]: cls="BROKER_ERROR_CLUSTER_NEAR_BOARD_B_DISCONNECT"
        elif an["manager_disconnect_count"]>0: cls="MANAGER_AND_BOARD_B_SESSION_LOSS_IN_WINDOW"
        elif an["board_connection_after_count"]>0: cls="BOARD_B_RECONNECT_OBSERVED_AFTER_DISCONNECT"
        else: cls="BOARD_B_ISOLATED_DISCONNECT_NO_RECONNECT_LOG_OBSERVED"
        result.update({"status":"PASS","manager":ms,"manager_socket_now":sock,"broker":bs,"analysis":an,"classification":cls,
                       "window_start":LOG_WINDOW_START,"window_end":LOG_WINDOW_END,
                       "broker_publish_visibility":"NOT_AVAILABLE_AT_NOTICE_WARNING_ERROR_LOG_LEVEL"})
        dump(out,result)
        print("DISCONNECT_CONTEXT_T1_FORENSIC_R2=PASS")
        print(f"T1_MANAGER_RUNNING={str(ms['running']).lower()}")
        print(f"MANAGER_RESTART_COUNT={ms['restart_count']}")
        print("MANAGER_MQTT_SOCKET_SAMPLE_COUNTS="+json.dumps(sock["counts"],separators=(",",":")))
        print("MANAGER_MQTT_SOCKET_STABLE_NOW="+str(sock["stable"]).lower())
        print(f"BROKER_RUNNING={str(bs['running']).lower()}")
        print(f"BROKER_RESTART_COUNT={bs['restart_count']}")
        print("PRIOR_EXACT_DISCONNECT_AUTHORITY=true")
        print("EXACT_DISCONNECT_REOBSERVED="+str(an["exact_disconnect_reobserved"]).lower())
        print(f"BOARD_B_CONNECTION_AFTER_DISCONNECT_COUNT={an['board_connection_after_count']}")
        print(f"MANAGER_DISCONNECT_COUNT_IN_WINDOW={an['manager_disconnect_count']}")
        print(f"OTHER_DISCONNECT_COUNT_WITHIN_5S={an['other_disconnect_count_within_5s']}")
        print(f"OTHER_DISCONNECT_COUNT_WITHIN_30S={an['other_disconnect_count_within_30s']}")
        print("MASS_DISCONNECT_NEAR_EVENT="+str(an["mass_disconnect_near_event"]).lower())
        print("GENERIC_ERROR_CATEGORIES="+json.dumps(an["generic_error_categories"],sort_keys=True,separators=(",",":")))
        print(f"GENERIC_ERROR_COUNT_WITHIN_5S={an['generic_error_count_within_5s']}")
        print(f"GENERIC_ERROR_COUNT_WITHIN_30S={an['generic_error_count_within_30s']}")
        print("BROKER_ERROR_CLUSTER_NEAR_EVENT="+str(an["broker_error_cluster_near_event"]).lower())
        print(f"DISCONNECT_CONTEXT_CLASSIFICATION={cls}")
        print("BROKER_PUBLISH_VISIBILITY=NOT_AVAILABLE_AT_NOTICE_WARNING_ERROR_LOG_LEVEL")
        print("BOARD_ACCESS=false"); print("BOARD_RESET=false"); print("BOARD_FLASH_WRITE=false"); print("PRODUCT_NVS_WRITE=false")
        print("APPLICATION_SERIAL_OPEN=false"); print("MQTT_TEST_PUBLISH=false"); print("MQTT_EXTRA_SUBSCRIBER=false"); print("T1_MUTATION=false")
        return 0
    except Exception as exc:
        result["stop_reason"]=f"{type(exc).__name__}: {exc}"; dump(out,result)
        print(f"STOP={exc}",file=sys.stderr)
        print("BOARD_ACCESS=false",file=sys.stderr); print("BOARD_RESET=false",file=sys.stderr); print("BOARD_FLASH_WRITE=false",file=sys.stderr)
        print("PRODUCT_NVS_WRITE=false",file=sys.stderr); print("APPLICATION_SERIAL_OPEN=false",file=sys.stderr); print("MQTT_TEST_PUBLISH=false",file=sys.stderr)
        print("MQTT_EXTRA_SUBSCRIBER=false",file=sys.stderr); print("T1_MUTATION=false",file=sys.stderr)
        return 2

if __name__=="__main__": raise SystemExit(main())
