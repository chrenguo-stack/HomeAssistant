#!/usr/bin/env python3
"""Future one-shot read-only baseline diagnostic; inert without exact B1 auth."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, stat, subprocess, sys, tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_repair_contract_20260728_v1 as contract
ADDR=0x400000; SIZE=0x10000
class ProbeError(RuntimeError):pass
def require(ok:bool,code:str)->None:
    if not ok:raise ProbeError(code)
def mode(p:Path)->str:return f"{stat.S_IMODE(p.stat().st_mode):04o}"
def read_json(p:Path,code:str)->dict[str,Any]:
    require(p.is_file() and not p.is_symlink() and mode(p)=="0600",code)
    try:v=json.loads(p.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as e:raise ProbeError(code) from e
    require(isinstance(v,dict),code);return v
def write_json(p:Path,v:Mapping[str,Any],replace:bool=False)->None:
    p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(p.parent,0o700)
    target=p.with_name(p.name+".tmp") if replace else p
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|(getattr(os,"O_NOFOLLOW",0))
    fd=os.open(target,flags,0o600)
    try:
        with os.fdopen(fd,"wb",closefd=False) as f:
            f.write(json.dumps(v,sort_keys=True,indent=2).encode()+b"\n");f.flush();os.fsync(f.fileno())
    finally:os.close(fd)
    if replace:os.replace(target,p)
    os.chmod(p,0o600)
def executable(value:str|None,name:str)->Path:
    candidate=value or shutil.which(name);require(candidate is not None,name.upper()+"_UNAVAILABLE")
    p=Path(candidate).expanduser().resolve(strict=True);require(p.is_file() and not p.is_symlink() and os.access(p,os.X_OK),name.upper()+"_INVALID");return p
@dataclass(frozen=True)
class Identity:
    device:str;vid:int;pid:int;serial_number:str;manufacturer:str;product:str;location:str;hwid:str
    def board_binding(self)->dict[str,Any]:return {"schema":"gh.h3.n2.stage2d9r-successor-board-identity/1","vid":self.vid,"pid":self.pid,"serial_number":self.serial_number,"manufacturer":self.manufacturer,"product":self.product,"location":self.location}
    def serial_binding(self)->dict[str,Any]:return {"schema":"gh.h3.n2.stage2d9r-successor-serial-identity/1","device":self.device,"vid":self.vid,"pid":self.pid,"serial_number":self.serial_number,"location":self.location,"hwid":self.hwid}
def enumerate_serial()->list[Identity]:
    try:from serial.tools import list_ports # type: ignore
    except ImportError as e:raise ProbeError("PYSERIAL_UNAVAILABLE") from e
    out=[]
    for p in list_ports.comports():
        if p.vid is None or p.pid is None:continue
        text=" ".join(filter(None,[p.manufacturer,p.product,p.description,p.hwid])).lower()
        if not any(x in text for x in ("espressif","esp32","usb jtag","usb serial")):continue
        out.append(Identity(str(p.device or ""),int(p.vid),int(p.pid),str(p.serial_number or ""),str(p.manufacturer or ""),str(p.product or p.description or ""),str(p.location or ""),str(p.hwid or "")))
    return out
def run(cmd:list[str],timeout:float,code:str)->subprocess.CompletedProcess[str]:
    cp=subprocess.run(cmd,check=False,text=True,capture_output=True,timeout=timeout,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"});require(cp.returncode==0,code);return cp
def cmd(tool:Path,port:str,*args:str)->list[str]:return [str(tool),"--chip","esp32c6","--port",port,*args]
def marker_path(root:Path)->Path:return root/(hashlib.sha256(contract.FUTURE_DIAGNOSTIC_AUTHORIZATION_ID.encode()).hexdigest()+".json")
def claim(marker:Path,auth:Mapping[str,Any])->None:
    require(not marker.exists(),"AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED")
    write_json(marker,{"schema":contract.DIAGNOSTIC_MARKER_SCHEMA,"authorization_id":contract.FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,"status":"CLAIMED","authorization_record_sha256":auth["authorization_record_sha256"],"one_shot":True,"replay_permitted":False,"automatic_retry_permitted":False,"flash_write":False,"flash_erase":False,"serial_open":False,"network_operation":False,"broker_started":False})
def finish(marker:Path,status:str,digest:str,failure:str|None)->None:
    write_json(marker,{"schema":contract.DIAGNOSTIC_MARKER_SCHEMA,"authorization_id":contract.FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,"status":status,"terminal_result_sha256":digest,"failure_code":failure,"one_shot":True,"replay_permitted":False,"automatic_retry_permitted":False,"flash_write":False,"flash_erase":False,"serial_open":False,"network_operation":False,"broker_started":False},True)
def execute(a:argparse.Namespace)->dict[str,Any]:
    source=contract.validate_sha40(a.source_sha,"SOURCE_SHA_INVALID");review=contract.validate_sha256(a.review_binding_sha256,"REVIEW_BINDING_INVALID")
    predecessor=read_json(a.predecessor_result.expanduser().resolve(strict=True),"PREDECESSOR_RESULT_INVALID")
    h4=read_json(a.h4_result.expanduser().resolve(strict=True),"H4_RESULT_INVALID")
    req=read_json(a.request_04.expanduser().resolve(strict=True),"REQUEST04_INVALID")
    contract.validate_predecessor_result(predecessor);contract.validate_h4_result(h4);contract.validate_request_04(req)
    python=Path(sys.executable).resolve(strict=True);tool=executable(a.esptool,"esptool");script=Path(__file__).resolve(strict=True)
    auth=read_json(a.authorization.expanduser().resolve(strict=True),"AUTHORIZATION_INVALID")
    auth=contract.validate_diagnostic_authorization(auth,source_sha=source,review_binding_sha256=review,diagnostic_script_sha256=contract.sha256_file(script),python_executable_sha256=contract.sha256_file(python),esptool_executable_sha256=contract.sha256_file(tool))
    state=a.state_root.expanduser().resolve(strict=True);require(state.is_dir() and not state.is_symlink() and mode(state)=="0700","STATE_ROOT_INVALID")
    marker=marker_path(state);claim(marker,auth)
    try:
        candidates=enumerate_serial();require(len(candidates)==1,"SERIAL_CANDIDATE_COUNT_NOT_ONE");selected=candidates[0]
        board=contract.canonical_json_sha256(selected.board_binding());serial=contract.canonical_json_sha256(selected.serial_binding())
        require(board==contract.BOARD_IDENTITY_SHA256,"BOARD_IDENTITY_MISMATCH");require(serial==contract.SERIAL_IDENTITY_SHA256,"SERIAL_IDENTITY_MISMATCH")
        with tempfile.TemporaryDirectory(prefix="stage2d9r-baseline-diagnostic-") as td:
            chip=run(cmd(tool,selected.device,"chip_id"),30,"DIAGNOSTIC_CHIP_ID_FAILED")
            flash=run(cmd(tool,selected.device,"flash_id"),30,"DIAGNOSTIC_FLASH_ID_FAILED")
            partition=Path(td)/"test-partition.bin";run(cmd(tool,selected.device,"read_flash",hex(ADDR),hex(SIZE),str(partition)),45,"DIAGNOSTIC_PARTITION_READ_FAILED")
            require(partition.is_file() and partition.stat().st_size==SIZE,"DIAGNOSTIC_PARTITION_SIZE_MISMATCH")
            evidence=contract.build_baseline_evidence(board_identity_sha256=board,serial_identity_sha256=serial,chip_id_output_sha256=contract.sha256_bytes(chip.stdout.encode()),flash_id_output_sha256=contract.sha256_bytes(flash.stdout.encode()),test_partition_sha256=contract.sha256_file(partition),test_partition_size=SIZE)
        result={"schema":contract.DIAGNOSTIC_RESULT_SCHEMA,"state":"READONLY_BASELINE_EVIDENCE_CAPTURED_AWAITING_ACCEPTANCE_DECISION","status":"CONSUMED_PASS","authorization_id":contract.FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,"source_sha":source,"review_binding_sha256":review,"predecessor_terminal_result_sha256":contract.PREDECESSOR_TERMINAL_RESULT_SHA256,"invalidated_request_binding_sha256":contract.INVALIDATED_REQUEST_BINDING_SHA256,"baseline_evidence":evidence,"future_physical_request_id":contract.FUTURE_PHYSICAL_REQUEST_ID,"future_physical_request_created":False,"authorization_consumed":True,"one_shot":True,"replay_permitted":False,"automatic_retry_permitted":False,"board_operation":True,"usb_enumeration":True,"esptool_readonly_operation":True,"serial_open":False,"flash_write":False,"flash_erase":False,"physical_nvs_operation":False,"network_operation":False,"broker_started":False,"prepare_executed":False,"verify_executed":False,"activate_executed":False,"cleanup_executed":False,"private_values_included":False,"private_paths_included":False,"secret_values_included":False,"completed_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}
        result["diagnostic_result_sha256"]=contract.canonical_json_sha256(result);write_json(a.result_output.expanduser(),result);finish(marker,"CONSUMED_PASS",result["diagnostic_result_sha256"],None);return result
    except Exception as e:
        failure=str(e.args[0]) if e.args else type(e).__name__;result={"schema":contract.DIAGNOSTIC_RESULT_SCHEMA,"status":"CONSUMED_FAILED","authorization_id":contract.FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,"failure_code":failure,"authorization_consumed":True,"one_shot":True,"replay_permitted":False,"automatic_retry_permitted":False,"flash_write":False,"flash_erase":False,"serial_open":False,"network_operation":False,"broker_started":False};result["diagnostic_result_sha256"]=contract.canonical_json_sha256(result);write_json(a.result_output.expanduser(),result);finish(marker,"CONSUMED_FAILED",result["diagnostic_result_sha256"],failure);raise
def main()->int:
    if len(sys.argv)==1:
        print(json.dumps({"status":"SOURCE_ONLY_REQUIRES_EXACT_READONLY_BASELINE_DIAGNOSTIC_AUTHORIZATION","authorization_id":contract.FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,"authorization_created":False,"board_operation":False,"usb_enumeration":False,"serial_open":False,"esptool_operation":False,"flash_write":False,"flash_erase":False,"network_operation":False,"broker_started":False},sort_keys=True));return 0
    p=argparse.ArgumentParser();p.add_argument("--source-sha",required=True);p.add_argument("--review-binding-sha256",required=True);p.add_argument("--authorization",type=Path,required=True);p.add_argument("--predecessor-result",type=Path,required=True);p.add_argument("--h4-result",type=Path,required=True);p.add_argument("--request-04",type=Path,required=True);p.add_argument("--state-root",type=Path,required=True);p.add_argument("--result-output",type=Path,required=True);p.add_argument("--esptool");a=p.parse_args()
    try:r=execute(a)
    except Exception as e:
        code=e.args[0] if isinstance(e,(ProbeError,contract.ContractError)) and e.args else type(e).__name__;print(json.dumps({"status":"FAIL","failure_code":str(code),"flash_write":False,"flash_erase":False,"serial_open":False,"network_operation":False,"broker_started":False},sort_keys=True));return 2
    print(json.dumps({"status":r["status"],"diagnostic_result_sha256":r["diagnostic_result_sha256"],"legacy_baseline_matches":r["baseline_evidence"]["legacy_baseline_matches"],"future_physical_request_created":False,"flash_write":False,"flash_erase":False,"network_operation":False},sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
