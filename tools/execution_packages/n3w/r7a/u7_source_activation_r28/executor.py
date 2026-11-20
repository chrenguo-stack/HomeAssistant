#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
BASE_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u6_source_activation_r25" / "executor.py"
)
GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U7_SOURCE_ACTIVATION_R28_20261114_01"
)
CONFIRMATION = "EXECUTE U7 R28 SOURCE ACTIVATION: YES"
TARGETS = {
    "backup": ROOT / "tools" / "n3w_t1_core_updater_ha_backup.py",
    "usb": ROOT / "tools" / "n3w_t1_core_updater_ha_usb.py",
    "install": ROOT / "tools" / "n3w_t1_core_updater_ha_install.py",
    "host": ROOT / "tools" / "n3w_t1_core_updater_host.py",
}


class Stop(RuntimeError):
    pass


def load_base():
    spec = importlib.util.spec_from_file_location("n3w_r28_base", BASE_EXECUTOR)
    if spec is None or spec.loader is None:
        raise Stop("base_executor_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REMOTE_SCRIPT = r'''
import hashlib,json,os,shutil,stat,subprocess,sys,tempfile
from pathlib import Path
TX=Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
R26=Path("/var/lib/n3w-t1-core-updater/u6-r26-predecessor-recovery-20261114-01")
HOST="n3w-t1-ha-ota.service"; SERVICES="n3wfc4-services-activation.service"; BROKER="n3wfc4-broker-activation.service"
class Stop(RuntimeError): pass

def run(a,timeout=60,check=True,env=None):
 c=subprocess.run(a,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout,check=False,env=env)
 if check and c.returncode: raise Stop("command_failed:"+Path(a[0]).name+":"+str(c.returncode))
 return c

def sha(p):
 p=Path(p)
 if p.is_symlink() or not p.is_file(): raise Stop("required_file_invalid:"+str(p))
 d=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""): d.update(b)
 return d.hexdigest()

def obj(p):
 p=Path(p)
 if p.is_symlink() or not p.is_file(): raise Stop("required_file_invalid:"+str(p))
 m=p.stat()
 if m.st_uid!=0 or stat.S_IMODE(m.st_mode)&0o077: raise Stop("required_file_metadata_invalid:"+str(p))
 try:v=json.loads(p.read_text())
 except Exception as e: raise Stop("required_json_invalid:"+str(p)) from e
 if not isinstance(v,dict): raise Stop("required_object_invalid:"+str(p))
 return v

def fsyncdir(p):
 fd=os.open(str(p),os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
 try:os.fsync(fd)
 finally:os.close(fd)

def durable(p,v):
 p=Path(p); data=(json.dumps(v,sort_keys=True,indent=2)+"\n").encode()
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
 try:os.write(fd,data);os.fsync(fd)
 finally:os.close(fd)
 fsyncdir(p.parent)

def install(src,dst):
 src=Path(src);dst=Path(dst)
 if src.is_symlink() or not src.is_file(): raise Stop("staged_source_invalid:"+src.name)
 fd,raw=tempfile.mkstemp(prefix="."+dst.name+".",dir=dst.parent);tmp=Path(raw)
 try:
  os.fchmod(fd,0o644)
  with os.fdopen(fd,"wb",closefd=True) as out,src.open("rb") as inp:
   shutil.copyfileobj(inp,out);out.flush();os.fsync(out.fileno())
  os.chown(tmp,0,0);os.replace(tmp,dst);fsyncdir(dst.parent)
 finally:tmp.unlink(missing_ok=True)

def unit(name):
 c=run(["systemctl","show",name,"-p","ActiveState","-p","SubState","-p","MainPID","-p","NRestarts","-p","Result"],30,False)
 r={"returncode":c.returncode}
 if not c.returncode:
  for line in c.stdout.splitlines():
   if "=" in line:k,v=line.split("=",1);r[k]=v
 return r

def container(e):
 ids=[x for x in run(["docker","ps","-a","--filter","ancestor="+e["image"],"--format","{{.ID}}"],45).stdout.splitlines() if x]
 if len(ids)!=1:raise Stop("container_cardinality_invalid:"+e["image"])
 x=json.loads(run(["docker","inspect",ids[0]],45).stdout)[0];s=x.get("State",{});c=x.get("Config",{})
 r={"container_id":x.get("Id"),"runtime_image_id":x.get("Image"),"configured_image_ref":c.get("Image"),"status":s.get("Status"),"restart_count":x.get("RestartCount")}
 if r["runtime_image_id"]!=e["runtime_image_id"] or r["configured_image_ref"]!=e["image"] or r["status"]!="running" or type(r["restart_count"]) is not int or r["restart_count"]<0:raise Stop("container_runtime_drift:"+e["image"])
 return r

def ipc(mid):
 q="import json,socket;s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(10);s.connect('/run/n3w/t1-ota/ha-ota.sock');s.sendall(json.dumps({'schema':'gh.n3w-t1-ha-ota-ipc-request/1','operation':'status'},sort_keys=True,separators=(',',':')).encode()+b'\\n');s.shutdown(socket.SHUT_WR);print(s.recv(8192).decode().strip())"
 c=run(["docker","exec","-u","999:999",mid,"python3","-c",q],30,False)
 if c.returncode:raise Stop("ipc_status_unavailable:"+str(c.returncode))
 try:v=json.loads(c.stdout.strip())
 except Exception as e:raise Stop("ipc_status_invalid") from e
 if not isinstance(v,dict) or v.get("accepted") is not True or v.get("phase")!="PREDECESSOR_RECOVERY_PREPARING" or v.get("error_code") is not None or v.get("installed_version")!="2026.10.0":raise Stop("ipc_not_u6_ready")
 return v

def transaction(p):
 t=obj(TX)
 if t.get("phase")!="U6_PREDECESSOR_RECOVERY_PREPARING" or t.get("status")!="ACTIVE" or t.get("transaction_id_sha256")!=p["transaction_id_sha256"] or sha(TX)!=p["transaction_sha256"] or t.get("target_artifact_verified") is not True or t.get("predecessor_recovery_verified") is not False or t.get("predecessor_recovery_identity") is not None or t.get("ha_data_backup_verified") is not False or t.get("ha_data_backup_identity") is not None or t.get("authorization_claimed") is not False or t.get("authorization_consumed") is not False or t.get("authorization_id_sha256") is not None:raise Stop("u7_u6_transaction_invalid")

def r26(p):
 c=obj(R26/"authorization_claim.json");s=obj(R26/"success.json")
 if c.get("authorization_id")!=p["r26_gate_id"] or c.get("claimed") is not True or c.get("consumed") is not True or c.get("replay_permitted") is not False:raise Stop("r26_claim_invalid")
 post=s.get("post")
 if s.get("status")!="U6_R26_PREDECESSOR_RECOVERY_PASS" or s.get("authorization_claimed") is not True or s.get("authorization_consumed") is not True or s.get("replay_permitted") is not False or s.get("u6_transition") is not True or s.get("u7_plus") is not False or not isinstance(post,dict) or post.get("transaction_phase")!="U6_PREDECESSOR_RECOVERY_PREPARING" or post.get("transaction_sha256")!=p["transaction_sha256"] or post.get("predecessor")!=p["predecessor_identity"]:raise Stop("r26_success_invalid")
 return {"claim_consumed_no_replay":True,"predecessor_authority_exact":True}

def sources(p,target):
 out={}
 for path,expected in p["unchanged_source_sha256"].items():
  d=sha(path)
  if d!=expected:raise Stop("unchanged_u6_source_drift:"+Path(path).name)
  out[path]=d
 for k,path in p["remote_paths"].items():
  q=Path(path);old=p["predecessor_sha256"].get(path)
  if target:
   d=sha(q)
   if d!=p["target_sha256"][k]:raise Stop("target_source_drift:"+k)
   out[path]=d
  elif old is None:
   if q.exists() or q.is_symlink():raise Stop("pre_u7_source_not_absent:"+k)
   out[path]="ABSENT_PRE_U7"
  else:
   d=sha(q)
   if d!=old:raise Stop("installed_u6_source_drift:"+k)
   out[path]=d
 return out

def runtime(p):
 u={"host":unit(HOST),"services_owner":unit(SERVICES),"broker_owner":unit(BROKER)}
 for n,x in u.items():
  if x.get("returncode")!=0 or x.get("ActiveState")!="active" or x.get("SubState")!="running" or x.get("Result")!="success" or not str(x.get("NRestarts","")).isdigit():raise Stop("unit_not_healthy:"+n)
 c={n:container(e) for n,e in p["containers"].items()};return {"units":u,"containers":c,"ipc":ipc(c["manager"]["container_id"])}

def pre(p,target=False):
 transaction(p); rr=r26(p); ss=sources(p,target); rt=runtime(p);return {"transaction_sha256":sha(TX),"r26":rr,"sources":ss,**rt}

def importable():
 q="import sys;sys.path.insert(0,'/opt/HomeAssistant/tools');import n3w_t1_core_updater_ha_backup;import n3w_t1_core_updater_ha_usb;import n3w_t1_core_updater_ha_install;import n3w_t1_core_updater_host;print('PASS')"
 e=dict(os.environ);e["PYTHONDONTWRITEBYTECODE"]="1";c=run(["python3","-B","-c",q],90,False,e)
 if c.returncode or c.stdout.strip()!="PASS":raise Stop("activated_source_import_failed")

def rollback(p,b):
 r={"attempted":True,"status":"STOP","errors":[]}
 try:
  for k,path in p["remote_paths"].items():
   d=Path(path);old=p["predecessor_sha256"].get(path)
   if old is None:
    if d.exists() or d.is_symlink():
     if d.is_symlink() or not d.is_file():raise Stop("rollback_target_path_invalid:"+k)
     d.unlink();fsyncdir(d.parent)
   else:
    q=Path(b)/(k+".py")
    if sha(q)!=old:raise Stop("rollback_backup_drift:"+k)
    install(q,d)
  r["post"]=pre(p,False);r["status"]="PASS"
 except Exception as e:r["errors"].append(type(e).__name__+":"+str(e)[:240])
 return r

def execute(p,aid,confirm):
 if p.get("live_execution_authorized") is not True or p.get("authorization_state")!={"granted":True,"claimed":False,"consumed":False,"replay_permitted":False}:raise Stop("r28_not_authorized")
 if aid!=p["authorization_id"] or confirm!=p["confirmation"]:raise Stop("r28_authorization_invalid")
 state=Path(p["state_root"]);stage=Path(p["remote_staging_root"])
 if state.exists() or state.is_symlink():raise Stop("r28_state_root_exists")
 if stage.is_symlink() or not stage.is_dir() or stage.stat().st_uid!=0 or stat.S_IMODE(stage.stat().st_mode)!=0o700:raise Stop("r28_staging_root_invalid")
 for k in p["remote_paths"]:
  q=stage/(k+".py")
  if q.is_symlink() or not q.is_file() or sha(q)!=p["target_sha256"][k]:raise Stop("r28_staged_source_invalid:"+k)
 before=pre(p,False);backup=stage/".preclaim-backup";backup.mkdir(mode=0o700);os.chown(backup,0,0)
 for k,path in p["remote_paths"].items():
  old=p["predecessor_sha256"].get(path)
  if old is not None:
   q=backup/(k+".py");shutil.copyfile(path,q);os.chmod(q,0o600);os.chown(q,0,0)
   if sha(q)!=old:raise Stop("r28_backup_drift:"+k)
 state.mkdir(mode=0o700);os.chown(state,0,0);fsyncdir(state.parent);durable(state/"preflight.json",before)
 result={"schema":"gh.n3w-t1-u7-r28-source-activation/1","status":"STOP","authorization_claimed":False,"authorization_consumed":False,"replay_permitted":False,"authorization_claim_persistence_unknown":False,"host_source_mutation":False,"activated_source_file_count":0,"service_stop":False,"service_restart":False,"transaction_mutation":False,"usb_mutation":False,"u7_transition":False,"u8_plus":False,"rollback_required":False,"rollback":None,"board_access":False,"merge":False}
 claim={"authorization_id":p["authorization_id"],"claimed":True,"consumed":True,"replay_permitted":False}
 try:durable(state/"authorization_claim.json",claim)
 except Exception as e:
  result.update(status="STOP_UNKNOWN",reason="authorization_claim_persistence_unknown:"+type(e).__name__+":"+str(e)[:180],authorization_claimed=True,authorization_consumed=True,replay_permitted=False,authorization_claim_persistence_unknown=True);return result
 result.update(authorization_claimed=True,authorization_consumed=True,replay_permitted=False)
 try:
  pc=pre(p,False)
  if pc["transaction_sha256"]!=before["transaction_sha256"]:raise Stop("postclaim_transaction_drift")
  for n in ("host","services_owner","broker_owner"):
   if pc["units"][n]["MainPID"]!=before["units"][n]["MainPID"]:raise Stop("unit_pid_drift_before_activation:"+n)
  result["host_source_mutation"]=True
  for k,dst in p["remote_paths"].items():install(stage/(k+".py"),dst);result["activated_source_file_count"]+=1
  importable();after=pre(p,True)
  if after["transaction_sha256"]!=before["transaction_sha256"]:raise Stop("u6_transaction_drift_after_activation")
  for n in ("host","services_owner","broker_owner"):
   if after["units"][n]["MainPID"]!=before["units"][n]["MainPID"]:raise Stop("unit_pid_drift_after_activation:"+n)
  result.update(status="U7_R28_SOURCE_ACTIVATION_PASS",source_activated=True,u6_preserved=True,import_validation=True,post=after)
  durable(state/"success.json",result)
  try:shutil.rmtree(stage)
  except Exception as e:
   result["completed_remote_status"]=result["status"];result["status"]="STOP_POSTSUCCESS_CLEANUP";result["postsuccess_cleanup_error"]=type(e).__name__+":"+str(e)[:240];result["rollback_required"]=False
  return result
 except Exception as e:
  result["first_failed_operation"]=type(e).__name__+":"+str(e)[:240];result["rollback_required"]=bool(result["host_source_mutation"])
  if result["rollback_required"]:result["rollback"]=rollback(p,backup)
  try:durable(state/"failure.json",result)
  except Exception:pass
  return result

def main():
 mode=sys.argv[1];p=json.loads(__import__('base64').b64decode(sys.argv[2]).decode())
 try:
  if p.get("gate_id")!="N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U7_SOURCE_ACTIVATION_R28_20261114_01":raise Stop("gate_id_invalid")
  if mode=="preflight":
   if Path(p["state_root"]).exists() or Path(p["state_root"]).is_symlink():raise Stop("r28_state_root_residue")
   if Path(p["remote_staging_root"]).exists() or Path(p["remote_staging_root"]).is_symlink():raise Stop("r28_staging_root_residue")
   result={"schema":"gh.n3w-t1-u7-r28-source-activation-preflight/1","status":"PASS","read_only":True,"source_activation_eligible":True,"live_execution_authorized":p.get("live_execution_authorized") is True,"preflight":pre(p,False),"host_source_mutation":False,"service_stop":False,"service_restart":False,"transaction_mutation":False,"usb_mutation":False,"u7_transition":False,"u8_plus":False}
  elif mode=="execute":result=execute(p,sys.argv[3],sys.argv[4])
  else:raise Stop("mode_invalid")
 except Exception as e:result={"status":"STOP","reason":type(e).__name__+":"+str(e)[:240],"authorization_claimed":False,"authorization_consumed":False,"replay_permitted":False}
 print(json.dumps(result,sort_keys=True));return 0 if result.get("status") in {"PASS","U7_R28_SOURCE_ACTIVATION_PASS"} else 2
raise SystemExit(main())
'''


def git_text(*args: str) -> str:
    base = load_base()
    return base.git_text(*args)


def sha_file(path: Path) -> str:
    return load_base().sha_file(path)


def read_manifest(expected_commit: str, *, execute: bool) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    d = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if d.get("gate_id") != GATE_ID or d.get("authorization_id") != GATE_ID or d.get("confirmation") != CONFIRMATION:
        raise Stop("manifest_gate_invalid")
    expected = {"granted":execute,"claimed":False,"consumed":False,"replay_permitted":False}
    if d.get("authorization_state") != expected or d.get("live_execution_authorized") is not execute:
        raise Stop("manifest_authorization_state_invalid")
    for relative, blob in d["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return d


def remote_mode(transport, mode, plan, *extra, timeout=300):
    payload = base64.b64encode(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).decode()
    c = transport.run_remote(["python3","-B","-c",REMOTE_SCRIPT,mode,payload,*extra],timeout=timeout,check=False)
    try:r=json.loads(c.stdout)
    except Exception:r={"status":"STOP","reason":"remote_result_invalid"}
    return c,r


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument("--expected-package-commit",required=True);p.add_argument("--execution-id",required=True);p.add_argument("--evidence-root",type=Path,required=True);p.add_argument("--t1-ssh-target",required=True);p.add_argument("--known-hosts",type=Path,required=True);p.add_argument("--expected-host-key-sha256",required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument("--preflight-only",action="store_true");g.add_argument("--execute",action="store_true");p.add_argument("--authorization-id",default="");p.add_argument("--confirm",default="");a=p.parse_args()
    result={"schema":"gh.n3w-t1-u7-r28-source-activation-local-result/1","status":"STOP","read_only_preflight":bool(a.preflight_only),"t1_access":False,"remote_staging":False,"remote_execute_invoked":False,"remote_execute_result_observed":False,"authorization_claimed":False,"authorization_consumed":False,"replay_permitted":False,"host_source_mutation":False,"service_stop":False,"service_restart":False,"transaction_mutation":False,"usb_mutation":False,"u7_transition":False,"u8_plus":False,"board_access":False,"merge":False};transport=None;rc=2
    base=load_base()
    try:
        m=read_manifest(a.expected_package_commit,execute=bool(a.execute));ev=base.prepare_evidence_root(a.evidence_root);plan=dict(m["expected_live_entry"]);plan.update({"gate_id":GATE_ID,"authorization_id":m["authorization_id"],"confirmation":m["confirmation"],"live_execution_authorized":m["live_execution_authorized"],"authorization_state":m["authorization_state"],"state_root":m["state_root"],"remote_staging_root":m["remote_staging_root"],"remote_paths":m["remote_paths"],"predecessor_sha256":m["predecessor_sha256"],"unchanged_source_sha256":m["unchanged_source_sha256"],"target_sha256":{k:sha_file(v) for k,v in TARGETS.items()}})
        t=base.load_transport();transport=t(target=a.t1_ssh_target,known_hosts=a.known_hosts.expanduser(),expected_host_key_sha256=a.expected_host_key_sha256);transport.start_epoch();result["t1_access"]=True
        ct,preflight=remote_mode(transport,"preflight",plan,timeout=240);base.write_remote_evidence(ev,"preflight_remote",ct);base.write_private_json(ev/"preflight.json",preflight)
        if ct.returncode or preflight.get("status")!="PASS":raise Stop("r28_preflight_failed:"+str(preflight.get("reason")))
        if a.preflight_only:result.update(preflight);result["t1_access"]=True;rc=0
        else:
            if a.authorization_id!=GATE_ID or a.confirm!=CONFIRMATION:raise Stop("authorization_invalid")
            stage=m["remote_staging_root"];transport.run_remote(["install","-d","-m","0700",stage],timeout=30)
            for k,src in TARGETS.items():transport.scp_to(src,stage+"/"+k+".py",timeout=180)
            transport.run_remote(["chmod","0600",*[stage+"/"+k+".py" for k in TARGETS]],timeout=30);result["remote_staging"]=True;result["remote_execute_invoked"]=True
            try:ce,remote=remote_mode(transport,"execute",plan,a.authorization_id,a.confirm,timeout=600)
            except Exception:result.update(status="STOP_UNKNOWN",authorization_claimed=True,authorization_consumed=True,replay_permitted=False,remote_execute_result_observed=False);raise
            result["remote_returncode"]=ce.returncode
            if not all(k in remote for k in ("authorization_claimed","authorization_consumed","replay_permitted")):result.update(status="STOP_UNKNOWN",reason="remote_execute_claim_state_unknown",authorization_claimed=True,authorization_consumed=True,replay_permitted=False,remote_execute_result_observed=False)
            else:result.update(remote);result["remote_execute_result_observed"]=True
            result["t1_access"]=True;base.write_remote_evidence(ev,"execute_remote",ce);rc=0 if ce.returncode==0 and result.get("status")=="U7_R28_SOURCE_ACTIVATION_PASS" else 2
    except Exception as e:
        if result.get("status") in {"PASS","U7_R28_SOURCE_ACTIVATION_PASS"}:result["completed_remote_status"]=result["status"];result["status"]="STOP_POSTSUCCESS_LOCAL"
        result["reason"]=type(e).__name__+":"+str(e)[:240]
    finally:
        if transport is not None:
            try:transport.close_epoch();result["ssh_master_cleanup"]=True
            except Exception as e:result["ssh_master_cleanup"]=False;result["ssh_master_cleanup_error"]=type(e).__name__+":"+str(e)[:240];rc=2
    print(json.dumps(result,sort_keys=True));return rc


if __name__ == "__main__": raise SystemExit(main())
