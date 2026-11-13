#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
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
TARGET_SOURCE = ROOT / "tools" / "n3w_t1_core_updater_ha_ipc.py"
GATE_ID = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF153_U5_IPC_SOURCE_ACTIVATION_R20_20261113_01"
CONFIRMATION = "EXECUTE KF153 R20 U5 IPC SOURCE ACTIVATION: YES"

class Stop(RuntimeError):
    pass

REMOTE_SCRIPT = r'''
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TX_PATH=Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
HOST_UNIT="n3w-t1-ha-ota.service"
SERVICES_UNIT="n3wfc4-services-activation.service"
BROKER_UNIT="n3wfc4-broker-activation.service"

class Stop(RuntimeError):
    pass

def run(argv, *, timeout=60, check=True):
    c=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout,check=False)
    if check and c.returncode!=0:
        raise Stop("command_failed:"+Path(argv[0]).name+":"+str(c.returncode))
    return c

def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def read_json(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file():
        raise Stop("required_file_invalid:"+str(p))
    m=p.stat()
    if m.st_uid!=0 or stat.S_IMODE(m.st_mode)&0o077:
        raise Stop("required_file_metadata_invalid:"+str(p))
    try:
        v=json.loads(p.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("required_json_invalid:"+str(p)) from error
    if not isinstance(v,dict):
        raise Stop("required_object_invalid:"+str(p))
    return v

def service_state(unit):
    c=run(["systemctl","show",unit,"-p","ActiveState","-p","SubState","-p","MainPID","-p","NRestarts","-p","Result"],timeout=30,check=False)
    r={}
    if c.returncode==0:
        for line in c.stdout.splitlines():
            if "=" in line:
                k,v=line.split("=",1); r[k]=v
    r["returncode"]=c.returncode
    return r

def wait_unit(unit,desired,timeout_seconds):
    deadline=time.monotonic()+timeout_seconds
    while time.monotonic()<deadline:
        value=run(["systemctl","is-active",unit],timeout=20,check=False).stdout.strip()
        if desired=="active" and value=="active": return
        if desired=="inactive" and value in {"inactive","failed"}: return
        time.sleep(1)
    raise Stop("unit_state_timeout:"+unit+":"+desired)

def docker_view(image):
    ids=[x.strip() for x in run(["docker","ps","-a","--filter","ancestor="+image,"--format","{{.ID}}"],timeout=45).stdout.splitlines() if x.strip()]
    if len(ids)!=1: raise Stop("container_cardinality_invalid:"+image)
    docs=json.loads(run(["docker","inspect",ids[0]],timeout=45).stdout)
    if not isinstance(docs,list) or len(docs)!=1: raise Stop("container_inspect_invalid:"+image)
    item=docs[0]; state=item.get("State") if isinstance(item.get("State"),dict) else {}
    return {"container_id":item.get("Id"),"runtime_image_id":item.get("Image"),"status":state.get("Status"),"exit_code":state.get("ExitCode"),"restart_count":item.get("RestartCount")}

def boolish(value):
    if isinstance(value,bool): return value
    if isinstance(value,int): return value!=0
    if isinstance(value,str): return value.strip().lower() in {"1","true","yes"}
    return False

def stable_fingerprint(node):
    serial=str(node.get("serial") or "").strip() or None
    wwn=str(node.get("wwn") or "").strip() or None
    if serial is None and wwn is None: raise Stop("usb_stable_identity_unavailable")
    payload=json.dumps({"serial":serial,"wwn":wwn,"model":str(node.get("model") or "").strip(),"size":node.get("size"),"transport":str(node.get("tran") or "").strip().lower()},sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(payload).hexdigest()

def lsblk_tree():
    c=run(["lsblk","--json","--bytes","--paths","--tree","--output","NAME,PATH,TYPE,RM,RO,SIZE,MODEL,SERIAL,WWN,TRAN,MOUNTPOINTS,MAJ:MIN"],timeout=30)
    d=json.loads(c.stdout); blocks=d.get("blockdevices")
    if not isinstance(blocks,list): raise Stop("usb_inventory_invalid")
    return [x for x in blocks if isinstance(x,dict)]

def usb_binding(plan, *, require_mounted):
    probe=run(["blkid","-t","UUID="+plan["usb_filesystem_uuid"],"-o","device"],timeout=30,check=False)
    matches=[x.strip() for x in probe.stdout.splitlines() if x.strip()] if probe.returncode==0 else []
    if len(matches)!=1: raise Stop("usb_uuid_cardinality_invalid")
    partition=matches[0]
    parent=run(["lsblk","--noheadings","--paths","--output","PKNAME",partition],timeout=30).stdout.strip()
    disks=[x for x in lsblk_tree() if x.get("type")=="disk" and x.get("path")==parent]
    if len(disks)!=1: raise Stop("usb_parent_invalid")
    disk=disks[0]
    if str(disk.get("tran") or "").strip().lower()!="usb" or not boolish(disk.get("rm")) or boolish(disk.get("ro")):
        raise Stop("usb_device_properties_invalid")
    if stable_fingerprint(disk)!=plan["usb_public_fingerprint"]:
        raise Stop("usb_public_fingerprint_mismatch")
    fs=run(["blkid","-s","TYPE","-o","value",partition],timeout=30).stdout.strip()
    label=run(["blkid","-s","LABEL","-o","value",partition],timeout=30).stdout.strip()
    if fs!="ext4" or label!="N3W-UPDATE": raise Stop("usb_filesystem_contract_invalid")
    mounted=run(["findmnt","--noheadings","--output","TARGET","--source",partition],timeout=30,check=False)
    targets=[x.strip() for x in mounted.stdout.splitlines() if x.strip()] if mounted.returncode==0 else []
    if require_mounted:
        if targets!=[plan["mount_target"]]: raise Stop("usb_mount_target_invalid")
        opts=run(["findmnt","--noheadings","--mountpoint",plan["mount_target"],"--output","OPTIONS"],timeout=30).stdout.strip()
        options={x.strip() for x in opts.split(",") if x.strip()}
        if not {"rw","nodev","nosuid","noexec"}.issubset(options) or {"ro","noload","norecovery"}.intersection(options):
            raise Stop("usb_mount_options_invalid")
        phase_path=Path(plan["mount_target"])/"n3w-update"/"transaction"/"phase.json"
        phase=read_json(phase_path)
        if phase.get("phase")!="U5_INSTALL_REQUESTED_REVALIDATING" or sha_file(phase_path)!=plan["usb_phase_sha256"]:
            raise Stop("usb_u5_phase_drift")
    else:
        if targets: raise Stop("usb_expected_unmounted")
    return {"partition":partition,"parent":parent,"mount_targets":targets,"public_fingerprint":plan["usb_public_fingerprint"]}

def verify_transaction(plan):
    tx=read_json(TX_PATH)
    if tx.get("phase")!="U5_INSTALL_REQUESTED_REVALIDATING" or tx.get("status")!="ACTIVE":
        raise Stop("u5_transaction_invalid")
    if tx.get("transaction_id_sha256")!=plan["transaction_id_sha256"]:
        raise Stop("transaction_id_drift")
    if tx.get("usb_filesystem_uuid")!=plan["usb_filesystem_uuid"] or tx.get("usb_device_identity_public_fingerprint")!=plan["usb_public_fingerprint"]:
        raise Stop("transaction_usb_binding_drift")
    if tx.get("authorization_claimed") is not False or tx.get("authorization_consumed") is not False:
        raise Stop("u9_authorization_state_drift")
    digest=sha_file(TX_PATH)
    if digest!=plan["transaction_sha256"]: raise Stop("u5_transaction_sha256_drift")
    return tx,digest

def verify_sources(plan, *, target):
    result={}
    for path, predecessor in plan["installed_source_sha256"].items():
        expected=plan["target_ipc_sha256"] if target and path==plan["ipc_remote_path"] else predecessor
        observed=sha_file(path)
        if observed!=expected: raise Stop(("target" if target else "predecessor")+"_source_drift:"+Path(path).name)
        result[path]=observed
    return result

def verify_runtime(plan, *, target_source, require_ipc):
    tx,tx_sha=verify_transaction(plan)
    media=usb_binding(plan,require_mounted=True)
    sources=verify_sources(plan,target=target_source)
    units={"host":service_state(HOST_UNIT),"services_owner":service_state(SERVICES_UNIT),"broker_owner":service_state(BROKER_UNIT)}
    for name in ("host","services_owner","broker_owner"):
        unit=units[name]
        if unit.get("ActiveState")!="active" or unit.get("SubState")!="running" or unit.get("Result")!="success" or unit.get("NRestarts")!="0":
            raise Stop("unit_not_healthy:"+name)
    containers={}
    for name,expected in plan["containers"].items():
        observed=docker_view(expected["image"])
        if observed["runtime_image_id"]!=expected["runtime_image_id"] or observed["restart_count"]!=0 or observed["status"]!="running":
            raise Stop("container_drift:"+name)
        containers[name]=observed
    ipc=None
    if require_ipc:
        manager_id=containers["manager"]["container_id"]
        probe=r"""import json,socket
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(15)
s.connect("/run/n3w/t1-ota/ha-ota.sock")
s.sendall(json.dumps({"schema":"gh.n3w-t1-ha-ota-ipc-request/1","operation":"status"},sort_keys=True,separators=(",",":")).encode()+b"\n")
s.shutdown(socket.SHUT_WR)
print(s.recv(8192).decode().strip())"""
        c=run(["docker","exec","-u","999:999",manager_id,"python3","-c",probe],timeout=30,check=False)
        if c.returncode!=0: raise Stop("ipc_status_unavailable:"+str(c.returncode))
        ipc=json.loads(c.stdout.strip())
        if not isinstance(ipc,dict) or ipc.get("accepted") is not True or ipc.get("phase")!="INSTALL_REQUESTED_REVALIDATING":
            raise Stop("ipc_not_u5")
    return {"transaction_sha256":tx_sha,"transaction_phase":tx["phase"],"usb":media,"sources":sources,"units":units,"containers":containers,"ipc":ipc}

def fsync_dir(path):
    fd=os.open(str(path),os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
    try: os.fsync(fd)
    finally: os.close(fd)

def durable_json(path,value):
    path=Path(path)
    payload=(json.dumps(value,sort_keys=True,indent=2)+"\n").encode()
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags,0o600)
    try:
        os.write(fd,payload); os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(path.parent)

def atomic_install(source,destination):
    source=Path(source); destination=Path(destination)
    if source.is_symlink() or not source.is_file(): raise Stop("staged_source_invalid")
    fd,raw=tempfile.mkstemp(prefix="."+destination.name+".",dir=destination.parent)
    temp=Path(raw)
    try:
        os.fchmod(fd,0o644)
        with os.fdopen(fd,"wb",closefd=True) as out:
            with source.open("rb") as inp: shutil.copyfileobj(inp,out)
            out.flush(); os.fsync(out.fileno())
        os.chown(temp,0,0)
        os.replace(temp,destination); fsync_dir(destination.parent)
    finally:
        temp.unlink(missing_ok=True)

def mount_exact(plan,partition):
    runtime=Path("/run/n3w-t1-ota")
    if runtime.is_symlink() or not runtime.is_dir(): raise Stop("runtime_root_invalid")
    media=runtime/"media"
    media.mkdir(mode=0o700,exist_ok=True)
    os.chmod(media,0o700); os.chown(media,0,0)
    target=Path(plan["mount_target"])
    target.mkdir(mode=0o700,exist_ok=True)
    os.chmod(target,0o700); os.chown(target,0,0)
    run(["mount","-o","nodev,nosuid,noexec",partition,str(target)],timeout=60)
    return usb_binding(plan,require_mounted=True)

def unmount_exact(plan):
    media=usb_binding(plan,require_mounted=True)
    run(["umount",plan["mount_target"]],timeout=60)
    usb_binding(plan,require_mounted=False)
    return media["partition"]

def rollback(plan,backup_dir):
    result={"attempted":True,"status":"STOP","errors":[]}
    try:
        run(["systemctl","stop",SERVICES_UNIT],timeout=150,check=False); wait_unit(SERVICES_UNIT,"inactive",90)
        probe=run(["blkid","-t","UUID="+plan["usb_filesystem_uuid"],"-o","device"],timeout=30,check=False)
        matches=[x.strip() for x in probe.stdout.splitlines() if x.strip()] if probe.returncode==0 else []
        if len(matches)!=1: raise Stop("rollback_usb_uuid_cardinality_invalid")
        partition=matches[0]
        current=run(["findmnt","--noheadings","--output","TARGET","--source",partition],timeout=30,check=False)
        if current.returncode==0 and current.stdout.strip():
            run(["umount",plan["mount_target"]],timeout=60,check=False)
        run(["systemctl","stop",HOST_UNIT],timeout=90,check=False); wait_unit(HOST_UNIT,"inactive",60)
        atomic_install(Path(backup_dir)/"ha_ipc.py",plan["ipc_remote_path"])
        verify_sources(plan,target=False)
        run(["systemctl","start",HOST_UNIT],timeout=90); wait_unit(HOST_UNIT,"active",60)
        mount_exact(plan,partition)
        run(["systemctl","start",SERVICES_UNIT],timeout=180); wait_unit(SERVICES_UNIT,"active",120)
        result["post"]=verify_runtime(plan,target_source=False,require_ipc=True)
        result["status"]="PASS"
    except Exception as error:
        result["errors"].append(type(error).__name__+":"+str(error)[:240])
    return result

def execute(plan,authorization,confirmation):
    if plan.get("live_execution_authorized") is not True or plan.get("authorization_state")!={"granted":True,"claimed":False,"consumed":False,"replay_permitted":False}:
        raise Stop("r20_not_authorized")
    if authorization!=plan["authorization_id"] or confirmation!=plan["confirmation"]:
        raise Stop("r20_authorization_invalid")
    state_root=Path(plan["state_root"]); stage_root=Path(plan["remote_staging_root"])
    if state_root.exists() or state_root.is_symlink(): raise Stop("r20_state_root_exists")
    staged=stage_root/"ha_ipc.py"
    if staged.is_symlink() or not staged.is_file() or stat.S_IMODE(staged.stat().st_mode)!=0o600 or sha_file(staged)!=plan["target_ipc_sha256"]:
        raise Stop("r20_staged_source_invalid")
    pre=verify_runtime(plan,target_source=False,require_ipc=False)
    backup_dir=stage_root/".preclaim-backup"
    backup_dir.mkdir(mode=0o700); os.chown(backup_dir,0,0)
    backup=backup_dir/"ha_ipc.py"; shutil.copyfile(plan["ipc_remote_path"],backup); os.chmod(backup,0o600); os.chown(backup,0,0)
    if sha_file(backup)!=plan["installed_source_sha256"][plan["ipc_remote_path"]]: raise Stop("r20_backup_drift")
    state_root.mkdir(mode=0o700); os.chown(state_root,0,0); fsync_dir(state_root.parent)
    durable_json(state_root/"preflight.json",pre)
    claim={"authorization_id":plan["authorization_id"],"claimed":True,"consumed":True,"replay_permitted":False}
    durable_json(state_root/"authorization_claim.json",claim)
    result={"schema":"gh.n3w-t1-kf153-r20-u5-ipc-source-activation/1","status":"STOP","authorization_claimed":True,"authorization_consumed":True,"replay_permitted":False,"host_source_mutation":False,"lifecycle_mutation_started":False,"usb_mount_mutation":False,"transaction_mutation":False,"usb_transaction_metadata_mutation":False,"host_daemon_restart":False,"services_owner_restart":False,"u6_plus":False,"rollback_required":False,"rollback":None,"board_access":False,"merge":False}
    try:
        postclaim=verify_runtime(plan,target_source=False,require_ipc=False)
        if postclaim["transaction_sha256"]!=pre["transaction_sha256"]: raise Stop("postclaim_transaction_drift")
        result["lifecycle_mutation_started"]=True
        run(["systemctl","stop",SERVICES_UNIT],timeout=150,check=False); wait_unit(SERVICES_UNIT,"inactive",90)
        partition=unmount_exact(plan); result["usb_mount_mutation"]=True
        run(["systemctl","stop",HOST_UNIT],timeout=90,check=False); wait_unit(HOST_UNIT,"inactive",60)
        _tx,stopped_sha=verify_transaction(plan)
        if stopped_sha!=pre["transaction_sha256"]: raise Stop("transaction_drift_after_stop")
        atomic_install(staged,plan["ipc_remote_path"]); result["host_source_mutation"]=True
        verify_sources(plan,target=True)
        run(["systemctl","start",HOST_UNIT],timeout=90); wait_unit(HOST_UNIT,"active",60); result["host_daemon_restart"]=True
        mount_exact(plan,partition)
        run(["systemctl","start",SERVICES_UNIT],timeout=180); wait_unit(SERVICES_UNIT,"active",120); result["services_owner_restart"]=True
        deadline=time.monotonic()+180; last=None
        while time.monotonic()<deadline:
            try:
                post=verify_runtime(plan,target_source=True,require_ipc=True); break
            except Stop as error:
                last=error; time.sleep(2)
        else:
            raise Stop("postactivation_runtime_timeout:"+(str(last) if last else "unknown"))
        if post["transaction_sha256"]!=pre["transaction_sha256"]: raise Stop("u5_transaction_drift_after_activation")
        result.update(status="KF153_R20_U5_IPC_SOURCE_ACTIVATION_PASS",source_activated=True,u5_preserved=True,ipc_recovered=True,post=post)
        shutil.rmtree(stage_root)
        return result
    except Exception as error:
        result["first_failed_operation"]=type(error).__name__+":"+str(error)[:240]
        result["rollback_required"]=bool(result["lifecycle_mutation_started"] or result["host_source_mutation"] or result["usb_mount_mutation"])
        if result["rollback_required"]:
            result["rollback"]=rollback(plan,backup_dir)
        try:
            durable_json(state_root/"failure.json",result)
        except Exception: pass
        return result

def main():
    mode=sys.argv[1]; plan=json.loads(base64.b64decode(sys.argv[2]).decode())
    try:
        if plan.get("gate_id")!="N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF153_U5_IPC_SOURCE_ACTIVATION_R20_20261113_01": raise Stop("gate_id_invalid")
        if mode=="preflight":
            if Path(plan["state_root"]).exists() or Path(plan["state_root"]).is_symlink():
                raise Stop("r20_state_root_residue")
            if Path(plan["remote_staging_root"]).exists() or Path(plan["remote_staging_root"]).is_symlink():
                raise Stop("r20_staging_root_residue")
            pre=verify_runtime(plan,target_source=False,require_ipc=False)
            result={"schema":"gh.n3w-t1-kf153-r20-u5-ipc-source-activation-preflight/1","status":"PASS","read_only":True,"activation_eligible":True,"live_execution_authorized":plan.get("live_execution_authorized") is True,"preflight":pre,"host_source_mutation":False,"usb_mount_mutation":False,"transaction_mutation":False,"usb_transaction_metadata_mutation":False,"service_restart":False,"u6_plus":False}
        elif mode=="execute":
            result=execute(plan,sys.argv[3],sys.argv[4])
        else: raise Stop("mode_invalid")
    except Exception as error:
        result={"status":"STOP","reason":type(error).__name__+":"+str(error)[:240]}
    print(json.dumps(result,sort_keys=True))
    return 0 if result.get("status") in {"PASS","KF153_R20_U5_IPC_SOURCE_ACTIVATION_PASS"} else 2

raise SystemExit(main())
'''

def git_text(*args):
    c=subprocess.run(["git",*args],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60,check=False)
    if c.returncode!=0: raise Stop("local_git_failed")
    return c.stdout.strip()

def sha_file(path: Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def read_manifest(expected_commit: str, *, execute: bool)->dict[str,Any]:
    if re.fullmatch(r"[0-9a-f]{40}",expected_commit or "") is None: raise Stop("expected_commit_invalid")
    if git_text("rev-parse","HEAD")!=expected_commit: raise Stop("local_head_mismatch")
    if git_text("status","--porcelain","--untracked-files=no"): raise Stop("tracked_worktree_dirty")
    d=json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if d.get("gate_id")!=GATE_ID or d.get("authorization_id")!=GATE_ID or d.get("confirmation")!=CONFIRMATION: raise Stop("manifest_gate_invalid")
    expected={"granted":True,"claimed":False,"consumed":False,"replay_permitted":False} if execute else {"granted":False,"claimed":False,"consumed":False,"replay_permitted":False}
    if d.get("authorization_state")!=expected: raise Stop("manifest_authorization_state_invalid")
    if d.get("live_execution_authorized") is not execute: raise Stop("manifest_execution_authority_invalid")
    for path,blob in d["package_source_authority"].items():
        if git_text("rev-parse","HEAD:"+path)!=blob: raise Stop("package_source_authority_drift:"+path)
    return d

def prepare_evidence_root(path: Path)->Path:
    root=path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()): raise Stop("evidence_root_invalid")
        os.chmod(root,0o700)
    else: root.mkdir(parents=True,mode=0o700)
    if root.stat().st_uid!=os.geteuid() or stat.S_IMODE(root.stat().st_mode)!=0o700: raise Stop("evidence_root_metadata_invalid")
    return root

def write_private_json(path: Path,value: Any)->None:
    payload=(json.dumps(value,sort_keys=True,indent=2)+"\n").encode()
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags,0o600)
    try:
        os.write(fd,payload); os.fsync(fd)
    finally:
        os.close(fd)

def write_private_text(path: Path,value: str)->None:
    payload=value.encode()
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags,0o600)
    try:
        os.write(fd,payload); os.fsync(fd)
    finally:
        os.close(fd)

def write_remote_evidence(evidence: Path,prefix: str,completed)->None:
    stdout=completed.stdout or ""
    stderr=completed.stderr or ""
    write_private_json(evidence/(prefix+"_transport.json"),{
        "returncode":completed.returncode,
        "stdout_length":len(stdout),
        "stderr_length":len(stderr),
        "stdout_sha256":hashlib.sha256(stdout.encode()).hexdigest(),
        "stderr_sha256":hashlib.sha256(stderr.encode()).hexdigest(),
    })
    write_private_text(evidence/(prefix+"_stdout.txt"),stdout)
    write_private_text(evidence/(prefix+"_stderr.txt"),stderr)

def load_transport():
    spec=importlib.util.spec_from_file_location("n3w_r20_transport",SSH_TRANSPORT_PATH)
    if spec is None or spec.loader is None: raise Stop("ssh_transport_import_invalid")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m.SSHTransport

def remote_mode(transport,mode,plan,*extra,timeout=300):
    payload=base64.b64encode(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).decode()
    c=transport.run_remote(["python3","-c",REMOTE_SCRIPT,mode,payload,*extra],timeout=timeout,check=False)
    try: result=json.loads(c.stdout)
    except Exception: result={"status":"STOP","reason":"remote_result_invalid"}
    return c,result

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--expected-package-commit",required=True); p.add_argument("--execution-id",required=True); p.add_argument("--evidence-root",type=Path,required=True)
    p.add_argument("--t1-ssh-target",required=True); p.add_argument("--known-hosts",type=Path,required=True); p.add_argument("--expected-host-key-sha256",required=True)
    g=p.add_mutually_exclusive_group(required=True); g.add_argument("--preflight-only",action="store_true"); g.add_argument("--execute",action="store_true")
    p.add_argument("--authorization-id",default=""); p.add_argument("--confirm",default="")
    args=p.parse_args()
    result={"schema":"gh.n3w-t1-kf153-r20-u5-ipc-source-activation-local-result/1","status":"STOP","read_only_preflight":bool(args.preflight_only),"t1_access":False,"remote_staging":False,"authorization_claimed":False,"authorization_consumed":False,"host_source_mutation":False,"usb_mount_mutation":False,"transaction_mutation":False,"usb_transaction_metadata_mutation":False,"u6_plus":False,"board_access":False,"merge":False}
    transport=None; rc=2
    try:
        manifest=read_manifest(args.expected_package_commit,execute=bool(args.execute))
        evidence=prepare_evidence_root(args.evidence_root)
        target_sha=sha_file(TARGET_SOURCE)
        plan=dict(manifest["expected_live_entry"])
        plan.update({"gate_id":GATE_ID,"authorization_id":manifest["authorization_id"],"confirmation":manifest["confirmation"],"live_execution_authorized":manifest["live_execution_authorized"],"authorization_state":manifest["authorization_state"],"state_root":manifest["state_root"],"remote_staging_root":manifest["remote_staging_root"],"ipc_remote_path":manifest["ipc_remote_path"],"target_ipc_sha256":target_sha})
        transport_type=load_transport(); transport=transport_type(target=args.t1_ssh_target,known_hosts=args.known_hosts.expanduser(),expected_host_key_sha256=args.expected_host_key_sha256); transport.start_epoch(); result["t1_access"]=True
        pre_transport,pre=remote_mode(transport,"preflight",plan,timeout=240)
        write_remote_evidence(evidence,"preflight_remote",pre_transport)
        write_private_json(evidence/"preflight.json",pre)
        if pre_transport.returncode!=0 or pre.get("status")!="PASS": raise Stop("r20_preflight_failed:"+str(pre.get("reason")))
        if args.preflight_only:
            result.update(pre); result["t1_access"]=True; rc=0
        else:
            if args.authorization_id!=GATE_ID or args.confirm!=CONFIRMATION: raise Stop("authorization_invalid")
            stage=manifest["remote_staging_root"]
            transport.run_remote(["install","-d","-m","0700",stage],timeout=30)
            remote_file=stage+"/ha_ipc.py"
            transport.scp_to(TARGET_SOURCE,remote_file,timeout=180)
            transport.run_remote(["chmod","0600",remote_file],timeout=30)
            result["remote_staging"]=True
            ex_transport,remote=remote_mode(transport,"execute",plan,args.authorization_id,args.confirm,timeout=600)
            write_remote_evidence(evidence,"execute_remote",ex_transport)
            result.update(remote); result["t1_access"]=True; result["remote_returncode"]=ex_transport.returncode
            rc=0 if ex_transport.returncode==0 and remote.get("status")=="KF153_R20_U5_IPC_SOURCE_ACTIVATION_PASS" else 2
    except Exception as error:
        result["reason"]=type(error).__name__+":"+str(error)[:240]
    finally:
        if transport is not None:
            try: transport.close_epoch(); result["ssh_master_cleanup"]=True
            except Exception: result["ssh_master_cleanup"]=False; rc=2
    print(json.dumps(result,sort_keys=True)); return rc

if __name__=="__main__": raise SystemExit(main())
