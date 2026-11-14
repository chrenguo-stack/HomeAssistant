#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
SSH_TRANSPORT_PATH = ROOT / "tools" / "n3w_t1_ssh_transport.py"
GATE_ID = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF153_POST_R18_IPC_TIMEOUT_READONLY_FORENSIC_R19_20261113_01"

class Stop(RuntimeError):
    pass

REMOTE_SCRIPT = r'''
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
R18_STATE_ROOT = Path("/var/lib/n3w-t1-core-updater/kf152-r18-u4-u5-install-intent-20261113-01")
HOST_UNIT = "n3w-t1-ha-ota.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"

def run(argv, *, timeout=60, check=True):
    completed = subprocess.run(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, timeout=timeout, check=False
    )
    if check and completed.returncode != 0:
        raise RuntimeError("command_failed:" + Path(argv[0]).name + ":" + str(completed.returncode))
    return completed

def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def read_json(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        return None
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return value if isinstance(value, dict) else None

def unit_state(name):
    c = run(
        ["systemctl","show",name,"-p","ActiveState","-p","SubState",
         "-p","MainPID","-p","NRestarts","-p","Result"],
        timeout=30, check=False
    )
    result={"returncode":c.returncode}
    if c.returncode == 0:
        for line in c.stdout.splitlines():
            if "=" in line:
                k,v=line.split("=",1)
                result[k]=v
    return result

def container_view(image):
    ids=[x.strip() for x in run(
        ["docker","ps","-a","--filter","ancestor="+image,"--format","{{.ID}}"],
        timeout=45,check=False
    ).stdout.splitlines() if x.strip()]
    if len(ids) != 1:
        return {"cardinality":len(ids)}
    c=run(["docker","inspect",ids[0]],timeout=45,check=False)
    if c.returncode != 0:
        return {"container_id":ids[0],"inspect_returncode":c.returncode}
    try:
        docs=json.loads(c.stdout)
    except Exception:
        return {"container_id":ids[0],"inspect_invalid":True}
    if not isinstance(docs,list) or len(docs)!=1:
        return {"container_id":ids[0],"inspect_invalid":True}
    item=docs[0]
    state=item.get("State") if isinstance(item.get("State"),dict) else {}
    return {
        "container_id":item.get("Id"),
        "runtime_image_id":item.get("Image"),
        "status":state.get("Status"),
        "exit_code":state.get("ExitCode"),
        "restart_count":item.get("RestartCount"),
    }

def boolish(value):
    if isinstance(value,bool): return value
    if isinstance(value,int): return value != 0
    if isinstance(value,str): return value.strip().lower() in {"1","true","yes"}
    return False

def stable_fingerprint(node):
    serial=str(node.get("serial") or "").strip() or None
    wwn=str(node.get("wwn") or "").strip() or None
    if serial is None and wwn is None:
        return None
    payload=json.dumps({
        "serial":serial,
        "wwn":wwn,
        "model":str(node.get("model") or "").strip(),
        "size":node.get("size"),
        "transport":str(node.get("tran") or "").strip().lower(),
    },sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(payload).hexdigest()

def usb_view(plan):
    result={
        "filesystem_uuid":plan["usb_filesystem_uuid"],
        "public_fingerprint_expected":plan["usb_public_fingerprint"],
        "mount_state":"UNKNOWN",
        "usb_transaction_phase":None,
    }
    c=run(["blkid","-t","UUID="+plan["usb_filesystem_uuid"],"-o","device"],timeout=30,check=False)
    matches=[x.strip() for x in c.stdout.splitlines() if x.strip()] if c.returncode==0 else []
    result["uuid_match_count"]=len(matches)
    if len(matches)!=1:
        return result
    partition=matches[0]
    result["partition"]=partition
    p=run(["lsblk","--noheadings","--paths","--output","PKNAME",partition],timeout=30,check=False)
    parent=p.stdout.strip() if p.returncode==0 else ""
    result["parent"]=parent or None
    t=run([
        "lsblk","--json","--bytes","--paths","--tree","--output",
        "NAME,PATH,TYPE,RM,RO,SIZE,MODEL,SERIAL,WWN,TRAN,MOUNTPOINTS,MAJ:MIN"
    ],timeout=30,check=False)
    try:
        blocks=json.loads(t.stdout).get("blockdevices",[]) if t.returncode==0 else []
    except Exception:
        blocks=[]
    disks=[x for x in blocks if isinstance(x,dict) and x.get("type")=="disk" and x.get("path")==parent]
    if len(disks)==1:
        disk=disks[0]
        result["public_fingerprint_observed"]=stable_fingerprint(disk)
        result["identity_matches"]=(
            result["public_fingerprint_observed"]==plan["usb_public_fingerprint"]
            and str(disk.get("tran") or "").strip().lower()=="usb"
            and boolish(disk.get("rm")) and not boolish(disk.get("ro"))
        )
    m=run(["findmnt","--noheadings","--output","TARGET","--source",partition],timeout=30,check=False)
    targets=[x.strip() for x in m.stdout.splitlines() if x.strip()] if m.returncode==0 else []
    if not targets:
        result["mount_state"]="UNMOUNTED"
        return result
    result["mount_state"]="MOUNTED" if len(targets)==1 else "AMBIGUOUS"
    result["mount_targets"]=targets
    if len(targets)!=1:
        return result
    target=targets[0]
    result["mount_target"]=target
    result["mount_target_expected"]=target==plan["mount_target"]
    o=run(["findmnt","--noheadings","--mountpoint",target,"--output","FSTYPE,OPTIONS"],timeout=30,check=False)
    result["mount_contract"]=o.stdout.strip() if o.returncode==0 else None
    phase_path=Path(target)/"n3w-update"/"transaction"/"phase.json"
    phase=read_json(phase_path)
    if isinstance(phase,dict):
        result["usb_transaction_phase"]=phase.get("phase")
        result["usb_phase_sha256"]=sha_file(phase_path)
    return result

def state_root_view():
    result={"exists":R18_STATE_ROOT.is_dir()}
    if not result["exists"]:
        return result
    for name in ("authorization_claim.json","preflight.json","postclaim.json","install_response.json","failure.json","result.json"):
        path=R18_STATE_ROOT/name
        value=read_json(path)
        result[name]={
            "exists":value is not None,
            "sha256":sha_file(path) if value is not None else None,
            "status":value.get("status") if isinstance(value,dict) else None,
            "reason":value.get("reason") if isinstance(value,dict) else None,
            "observed_transaction_phase":value.get("observed_transaction_phase") if isinstance(value,dict) else None,
            "observed_usb_transaction_phase":value.get("observed_usb_transaction_phase") if isinstance(value,dict) else None,
        }
    claim=read_json(R18_STATE_ROOT/"authorization_claim.json")
    result["claim"]={
        "claimed":claim.get("claimed") if isinstance(claim,dict) else None,
        "consumed":claim.get("consumed") if isinstance(claim,dict) else None,
        "replay_permitted":claim.get("replay_permitted") if isinstance(claim,dict) else None,
    }
    return result

def ipc_status_probe(manager_id):
    probe=r"""import json,socket
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(15)
s.connect("/run/n3w/t1-ota/ha-ota.sock")
s.sendall(json.dumps({"schema":"gh.n3w-t1-ha-ota-ipc-request/1","operation":"status"},sort_keys=True,separators=(",",":")).encode()+b"\n")
s.shutdown(socket.SHUT_WR)
print(s.recv(8192).decode().strip())"""
    c=run(["docker","exec","-u","999:999",manager_id,"python3","-c",probe],timeout=30,check=False)
    result={"returncode":c.returncode,"stderr":c.stderr.strip()[:1200],"stdout":c.stdout.strip()[:2400]}
    if c.returncode==0:
        try:
            value=json.loads(c.stdout.strip())
        except Exception:
            value=None
        result["decoded"]=value if isinstance(value,dict) else None
    return result

def journal_markers():
    c=run(["journalctl","-u",HOST_UNIT,"--no-pager","-n","300"],timeout=30,check=False)
    text=c.stdout if c.returncode==0 else ""
    pattern=re.compile(r"(BrokenPipe|Timeout|timed out|Traceback|ConnectionReset|broken pipe|socket)",re.IGNORECASE)
    lines=[line[-500:] for line in text.splitlines() if pattern.search(line)]
    return {
        "returncode":c.returncode,
        "sha256":hashlib.sha256(text.encode()).hexdigest(),
        "markers":lines[-30:],
        "broken_pipe_seen":any("brokenpipe" in x.lower() or "broken pipe" in x.lower() for x in lines),
        "timeout_seen":any("timeout" in x.lower() or "timed out" in x.lower() for x in lines),
        "traceback_seen":any("traceback" in x.lower() for x in lines),
    }

def classify(tx_phase,usb):
    usb_phase=usb.get("usb_transaction_phase")
    mount_state=usb.get("mount_state")
    if tx_phase=="U5_INSTALL_REQUESTED_REVALIDATING" and usb_phase=="U5_INSTALL_REQUESTED_REVALIDATING":
        return "DELAYED_U5_TRANSITION_COMPLETE"
    if tx_phase=="U5_INSTALL_REQUESTED_REVALIDATING" and usb_phase!="U5_INSTALL_REQUESTED_REVALIDATING":
        return "HOST_U5_USB_NOT_PROVEN_U5"
    if tx_phase=="U4_READY_TO_INSTALL" and mount_state=="UNMOUNTED":
        return "U4_UNCHANGED_UNMOUNTED"
    if tx_phase=="U4_READY_TO_INSTALL" and mount_state=="MOUNTED":
        return "U4_WITH_MEDIA_REOPENED"
    return "OTHER_OR_AMBIGUOUS"

def main():
    plan=json.loads(sys.argv[1])
    tx_before=read_json(TX_PATH)
    tx_before_sha=sha_file(TX_PATH) if tx_before is not None else None
    usb_before=usb_view(plan)
    units_before={"host":unit_state(HOST_UNIT),"services_owner":unit_state(SERVICES_UNIT),"broker_owner":unit_state(BROKER_UNIT)}
    containers={k:container_view(v["image"]) for k,v in plan["containers"].items()}
    residue=state_root_view()
    manager_id=containers.get("manager",{}).get("container_id")
    ipc=ipc_status_probe(manager_id) if isinstance(manager_id,str) and manager_id else {"returncode":None,"reason":"manager_unavailable"}
    journal=journal_markers()
    tx_after=read_json(TX_PATH)
    tx_after_sha=sha_file(TX_PATH) if tx_after is not None else None
    usb_after=usb_view(plan)
    units_after={"host":unit_state(HOST_UNIT),"services_owner":unit_state(SERVICES_UNIT),"broker_owner":unit_state(BROKER_UNIT)}
    phase=tx_after.get("phase") if isinstance(tx_after,dict) else None
    print(json.dumps({
        "schema":"gh.n3w-t1-kf153-r19-post-r18-ipc-timeout-readonly-forensic/1",
        "status":"PASS",
        "read_only":True,
        "forensic_complete":True,
        "classification":classify(phase,usb_after),
        "transaction_before":{"phase":tx_before.get("phase") if isinstance(tx_before,dict) else None,"sha256":tx_before_sha},
        "transaction_after":{"phase":phase,"sha256":tx_after_sha},
        "transaction_unchanged_during_forensic":tx_before_sha==tx_after_sha,
        "usb_before":usb_before,
        "usb_after":usb_after,
        "units_before":units_before,
        "units_after":units_after,
        "containers":containers,
        "r18_state_root":residue,
        "ipc_status_probe":ipc,
        "journal":journal,
        "host_mutation":False,
        "transaction_mutation":False,
        "usb_mutation":False,
        "service_restart":False,
        "manager_mutation":False,
        "homeassistant_mutation":False,
        "broker_mutation":False,
        "u6_plus":False,
        "board_access":False,
        "merge":False,
    },sort_keys=True))
    return 0

raise SystemExit(main())
'''

def git_text(*arguments: str) -> str:
    c=subprocess.run(["git",*arguments],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60,check=False)
    if c.returncode!=0:
        raise Stop("local_git_failed")
    return c.stdout.strip()

def read_manifest(expected_commit: str) -> dict[str,Any]:
    if re.fullmatch(r"[0-9a-f]{40}",expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse","HEAD")!=expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status","--porcelain","--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    d=json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if d.get("gate_id")!=GATE_ID:
        raise Stop("manifest_gate_invalid")
    if d.get("live_execution_authorized") is not False:
        raise Stop("forensic_must_be_ungranted")
    if d.get("authorization_state")!={"granted":False,"claimed":False,"consumed":False,"replay_permitted":False}:
        raise Stop("manifest_authorization_state_invalid")
    for relative,blob in d["package_source_authority"].items():
        if git_text("rev-parse","HEAD:"+relative)!=blob:
            raise Stop("package_source_authority_drift:"+relative)
    return d

def prepare_evidence_root(path: Path) -> Path:
    root=path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise Stop("evidence_root_invalid")
        os.chmod(root,0o700)
    else:
        root.mkdir(parents=True,mode=0o700)
    metadata=root.stat()
    if metadata.st_uid!=os.geteuid() or stat.S_IMODE(metadata.st_mode)!=0o700:
        raise Stop("evidence_root_metadata_invalid")
    return root

def write_private(path: Path,value:Any)->None:
    payload=(json.dumps(value,sort_keys=True,indent=2)+"\n").encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb",closefd=True) as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())

def load_transport():
    spec=importlib.util.spec_from_file_location("n3w_kf153_r19_transport",SSH_TRANSPORT_PATH)
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.SSHTransport

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit",required=True)
    parser.add_argument("--execution-id",required=True)
    parser.add_argument("--evidence-root",type=Path,required=True)
    parser.add_argument("--t1-ssh-target",required=True)
    parser.add_argument("--known-hosts",type=Path,required=True)
    parser.add_argument("--expected-host-key-sha256",required=True)
    parser.add_argument("--preflight-only",action="store_true",required=True)
    args=parser.parse_args()
    result={"schema":"gh.n3w-t1-kf153-r19-post-r18-ipc-timeout-readonly-forensic-local-result/1","status":"STOP","read_only":True,"t1_access":False,"host_mutation":False,"transaction_mutation":False,"usb_mutation":False,"service_restart":False,"manager_mutation":False,"homeassistant_mutation":False,"broker_mutation":False,"u6_plus":False,"board_access":False,"merge":False}
    transport=None; rc=2
    try:
        if re.fullmatch(r"[A-Za-z0-9._-]{1,160}",args.execution_id) is None:
            raise Stop("execution_id_invalid")
        manifest=read_manifest(args.expected_package_commit)
        evidence=prepare_evidence_root(args.evidence_root)
        transport_type=load_transport()
        transport=transport_type(target=args.t1_ssh_target,known_hosts=args.known_hosts.expanduser(),expected_host_key_sha256=args.expected_host_key_sha256)
        transport.start_epoch(); result["t1_access"]=True
        payload=json.dumps(manifest["expected_live_entry"],sort_keys=True,separators=(",",":"))
        c=transport.run_remote(["python3","-c",REMOTE_SCRIPT,payload],timeout=180,check=False)
        write_private(evidence/"remote_transport.json",{"returncode":c.returncode,"stdout_length":len(c.stdout),"stderr_length":len(c.stderr)})
        write_private(evidence/"remote_stdout.json",{"stdout":c.stdout})
        write_private(evidence/"remote_stderr.json",{"stderr":c.stderr})
        if c.returncode!=0:
            raise Stop("remote_forensic_failed:"+str(c.returncode))
        remote=json.loads(c.stdout)
        write_private(evidence/"result.json",remote)
        if remote.get("status")!="PASS" or remote.get("read_only") is not True:
            raise Stop("remote_forensic_invalid")
        result.update(remote); result["t1_access"]=True; rc=0
    except Exception as error:
        result["reason"]=type(error).__name__+":"+str(error)[:240]
    finally:
        if transport is not None:
            try:
                transport.close_epoch(); result["ssh_master_cleanup"]=True
            except Exception:
                result["ssh_master_cleanup"]=False; rc=2
    print(json.dumps(result,sort_keys=True))
    return rc

if __name__=="__main__":
    raise SystemExit(main())
