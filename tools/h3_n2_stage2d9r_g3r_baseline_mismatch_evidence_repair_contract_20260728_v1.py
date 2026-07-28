#!/usr/bin/env python3
"""Source-only contract for Stage2D9R G3R baseline evidence repair."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, re
from pathlib import Path
from typing import Any, Mapping

SCHEMA="gh.h3.n2.stage2d9r-g3r-baseline-mismatch-evidence-repair-contract/1"
REVIEW_SCHEMA="gh.h3.n2.stage2d9r-g3r-baseline-mismatch-evidence-repair-review/1"
PREDECESSOR_DISPOSITION_SCHEMA="gh.h3.n2.stage2d9r-g3r-predecessor-terminal-disposition/1"
INVALIDATION_SCHEMA="gh.h3.n2.stage2d9r-g3r-invalidated-physical-request/1"
DIAGNOSTIC_REQUEST_SCHEMA="gh.h3.n2.stage2d9r-g3r-baseline-diagnostic-request/1"
DIAGNOSTIC_AUTH_SCHEMA="gh.h3.n2.stage2d9r-g3r-baseline-diagnostic-authorization/1"
DIAGNOSTIC_RESULT_SCHEMA="gh.h3.n2.stage2d9r-g3r-baseline-diagnostic-result/1"
DIAGNOSTIC_MARKER_SCHEMA="gh.h3.n2.stage2d9r-g3r-baseline-diagnostic-marker/1"
BASELINE_EVIDENCE_SCHEMA="gh.h3.n2.stage2d9r-g3r-baseline-evidence/2"
STAGE="H3/N2 Stage 2D-9R G3R baseline mismatch evidence repair"
DECISION_ID="D1-H3N2-STAGE2D9R-G3R-BASELINE-MISMATCH-EVIDENCE-REPAIR-20260728-01"
BASE_PR=195
BASE_BRANCH="fix/h3-n2-stage2d9r-g3r-execution-closure-binding-20260728-v1"
BASE_HEAD_SHA="1fd6bc19246481835c1e836f5daaefcaf6c97836"
REPOSITORY_HEAD_AT_REPAIR="64c6b093c3ba6a8476c9392c8d106394b2542fb5"
UPSTREAM_ARTIFACT_ID=8691052910
UPSTREAM_ARTIFACT_SHA256="75d62dd96f98fdfb48d4fdcc296ce4a93fb8d7f798ab9a30c3e3b4391aad0bed"
UPSTREAM_REVIEW_BINDING_SHA256="3bf6f69ca37e4a4037054e581274bf73057f04ad980c1685edfbeca091ec4ea7"
UPSTREAM_EXECUTION_CLOSURE_SHA256="d74b1b1995d35d76075b52c68f2e61f7ec67306a1615c01bfdcbaa6679d44275"
UPSTREAM_EXECUTION_PACKAGE_SHA256="f3349fbd5a09509c20c66b525e50811150168c5375ef4b7a3518f30523829292"
PREDECESSOR_REQUEST_ID="D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-03"
PREDECESSOR_AUTHORIZATION_RECORD_SHA256="e99382018c416e7fb87c99c7815ee1d366b2880a14fa36285637978d3b3e9e9b"
PREDECESSOR_REQUEST_BINDING_SHA256="7e92211923ff4f37229a1e608393cbd1f9d3367cfcbaf82b203319277499cee1"
PREDECESSOR_TERMINAL_RESULT_SHA256="008bff95619c4779f3ddca35492fae140ac067f9fd1f5443758c19534f254668"
EXPECTED_BASELINE_STATE_SHA256="0735d98c7b4e2a698b42d39bdded1dd04f97b9441270e8bc03be347d369c8793"
BOARD_IDENTITY_SHA256="2607b7df80b8b636548a8d9d97c0a6b4e4ead57e9a2cc6fcb7f93643617242f8"
SERIAL_IDENTITY_SHA256="b6dba7ee0db02feba166935ae8ec2bbd946dbf66926e5421cfa1c1c8b8a4f2c3"
H4_AUTHORIZATION_ID="H4-H3N2-STAGE2D9R-G3R-EXECUTION-CLOSURE-BINDING-20260728-01"
H4_RESULT_SHA256="5ae7d046181710ab2746c1c04bc45ea94f5097cb24b2ba78f415f2417b35c7ad"
H4_RESULT_FILE_SHA256="86c5987d395001dbab6fd1d4f995ba87880fca557dff0cad0ad27fa77be27b80"
INVALIDATED_REQUEST_ID="D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-04"
INVALIDATED_REQUEST_BINDING_SHA256="1058abf2c944ac5303c688b2b220ad208f22a920a984e44424b5ce5ab238d292"
INVALIDATED_REQUEST_FILE_SHA256="e0709092909226b9581d0ce92953126b52aa72968f698d417115a0d48b1e4f3b"
INVALIDATED_REQUEST_STATE="INVALIDATED_BY_PREDECESSOR_TERMINAL_STATE_DRIFT_BEFORE_PHYSICAL_AUTHORIZATION"
FUTURE_DIAGNOSTIC_AUTHORIZATION_ID="B1-H3N2-STAGE2D9R-G3R-BASELINE-EVIDENCE-DIAGNOSTIC-READONLY-20260728-01"
FUTURE_DIAGNOSTIC_OPERATION="READONLY_CAPTURE_BASELINE_EVIDENCE_V2"
FUTURE_PHYSICAL_REQUEST_ID="D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-05"
HEX40=re.compile(r"^[0-9a-f]{40}$"); HEX64=re.compile(r"^[0-9a-f]{64}$")
FALSE_BOUNDARY={k:False for k in (
 "authorized authorization_created authorization_claimed authorization_consumed board_operation usb_enumeration serial_operation esptool_operation flash_operation physical_nvs_operation network_operation broker_started prepare_executed verify_executed activate_executed cleanup_executed ready merge release tag deployment private_values_included private_paths_included secret_values_included").split()}

class ContractError(RuntimeError): pass
def require(ok:bool,code:str)->None:
    if not ok: raise ContractError(code)
def canonical_json_bytes(v:object)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def canonical_json_sha256(v:object)->str:return hashlib.sha256(canonical_json_bytes(v)).hexdigest()
def sha256_bytes(v:bytes)->str:return hashlib.sha256(v).hexdigest()
def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()
def validate_sha40(v:object,c:str)->str:require(isinstance(v,str) and HEX40.fullmatch(v) is not None,c);return v
def validate_sha256(v:object,c:str)->str:require(isinstance(v,str) and HEX64.fullmatch(v) is not None,c);return v
def utc(v:object,c:str)->datetime:
    require(isinstance(v,str),c)
    try:x=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as e:raise ContractError(c) from e
    require(x.tzinfo is not None,c);return x.astimezone(timezone.utc)

def expected_predecessor_result()->dict[str,Any]:
    v={"activate_executed":False,"authorization_record_sha256":PREDECESSOR_AUTHORIZATION_RECORD_SHA256,
    "baseline_state_sha256":EXPECTED_BASELINE_STATE_SHA256,"board_identity_sha256":BOARD_IDENTITY_SHA256,
    "broker_log_sha256":None,"candidate_digest_sha256":"73b58ea30e4355d90afa4a9bc9331968537d6318db046f562212c5b836670b15",
    "cleanup_executed":False,"d2_request_id":PREDECESSOR_REQUEST_ID,"failure_code":"BASELINE_STATE_MISMATCH",
    "flash_sha256":None,"immutable_artifact_archive_sha256":"83eb3cd85e04835eb412dfe9288c3f3445c0b5aefa23dec21532a8500e8fe5b8",
    "immutable_artifact_id":8676269782,"main_sha":REPOSITORY_HEAD_AT_REPAIR,"observed_baseline_sha256":None,
    "prepare_count":0,"prepare_result_sha256":None,"private_paths_included":False,"production_operation":False,
    "recovery_artifact_archive_sha256":"83eb3cd85e04835eb412dfe9288c3f3445c0b5aefa23dec21532a8500e8fe5b8",
    "recovery_artifact_id":8676269782,"recovery_attempted":False,"recovery_succeeded":False,
    "request_binding_sha256":PREDECESSOR_REQUEST_BINDING_SHA256,
    "schema":"gh.h3.n2.stage2d9r-g3r-main-drift-rebound-physical-d2-result/1","secret_values_included":False,
    "serial_identity_sha256":SERIAL_IDENTITY_SHA256,"source_sha":"b69371b13b6af139b4607a2150f25f440bb251c7",
    "stage":"H3/N2 Stage 2D-9R G3R main-drift successor rebind","status":"CONSUMED_FAILED",
    "terminal_state":"CONSUMED_FAILED","verify_count":0,"verify_result_sha256":None}
    v["terminal_result_sha256"]=canonical_json_sha256(v)
    require(v["terminal_result_sha256"]==PREDECESSOR_TERMINAL_RESULT_SHA256,"INTERNAL_PREDECESSOR_DIGEST_MISMATCH")
    return v

def validate_predecessor_result(v:Mapping[str,Any])->dict[str,Any]:
    e=expected_predecessor_result();require(dict(v)==e,"PREDECESSOR_RESULT_MISMATCH");return dict(v)
def _validate_bound(v:Mapping[str,Any],required:Mapping[str,Any],digest_key:str,code:str)->dict[str,Any]:
    for k,x in required.items():require(v.get(k)==x,f"{code}_{k.upper()}_MISMATCH")
    w=dict(v);sup=w.pop(digest_key,None);require(sup==canonical_json_sha256(w),f"{code}_CANONICAL_DIGEST_MISMATCH");return dict(v)
def validate_h4_result(v:Mapping[str,Any])->dict[str,Any]:
    return _validate_bound(v,{"schema":"gh.h3.n2.stage2d9r-g3r-execution-closure-host-preflight-result/1",
    "authorization_id":H4_AUTHORIZATION_ID,"status":"CONSUMED_PASS","host_preflight_result_sha256":H4_RESULT_SHA256,
    "new_physical_d2_request_id":INVALIDATED_REQUEST_ID,"physical_request_authorized":False,"authorization_consumed":True,
    "one_shot":True,"replay_permitted":False,"automatic_retry_permitted":False,"board_operation":False,
    "usb_enumeration":False,"serial_operation":False,"esptool_operation":False,"flash_operation":False,
    "physical_nvs_operation":False,"network_operation":False,"broker_started":False,"prepare_executed":False,
    "verify_executed":False,"execution_closure_sha256":UPSTREAM_EXECUTION_CLOSURE_SHA256,
    "execution_package_sha256":UPSTREAM_EXECUTION_PACKAGE_SHA256,"source_sha":BASE_HEAD_SHA},"host_preflight_result_sha256","H4_RESULT")
def validate_request_04(v:Mapping[str,Any])->dict[str,Any]:
    return _validate_bound(v,{"schema":"gh.h3.n2.stage2d9r-g3r-execution-closure-bound-physical-d2-request/1",
    "d2_request_id":INVALIDATED_REQUEST_ID,"request_binding_sha256":INVALIDATED_REQUEST_BINDING_SHA256,
    "host_preflight_result_sha256":H4_RESULT_SHA256,"authorized":False,"authorization_created":False,
    "authorization_claimed":False,"authorization_consumed":False,"expires_at":None,"issued_at":None,
    "previous_request_id":PREDECESSOR_REQUEST_ID,"previous_request_state":"SUPERSEDED_BY_EXECUTION_CLOSURE_POLICY_BEFORE_AUTHORIZATION",
    "previous_request_reuse_permitted":False,"execution_closure_sha256":UPSTREAM_EXECUTION_CLOSURE_SHA256,
    "execution_package_sha256":UPSTREAM_EXECUTION_PACKAGE_SHA256,"source_sha":BASE_HEAD_SHA},"request_binding_sha256","REQUEST04")

def predecessor_disposition()->dict[str,Any]:
    return {"schema":PREDECESSOR_DISPOSITION_SCHEMA,"state":"CONSUMED_FAILED","d2_request_id":PREDECESSOR_REQUEST_ID,
    "failure_code":"BASELINE_STATE_MISMATCH","authorization_record_sha256":PREDECESSOR_AUTHORIZATION_RECORD_SHA256,
    "request_binding_sha256":PREDECESSOR_REQUEST_BINDING_SHA256,"terminal_result_sha256":PREDECESSOR_TERMINAL_RESULT_SHA256,
    "expected_baseline_state_sha256":EXPECTED_BASELINE_STATE_SHA256,"observed_baseline_sha256":None,
    "observed_baseline_missing_is_evidence_defect":True,"flash_operation_occurred":False,"prepare_count":0,"verify_count":0,
    "broker_started":False,"recovery_attempted":False,"recovery_succeeded":False,"authorization_consumed":True,
    "one_shot":True,"replay_permitted":False,"automatic_retry_permitted":False,"request_reuse_permitted":False}
def invalidated_request_04_disposition()->dict[str,Any]:
    return {"schema":INVALIDATION_SCHEMA,"state":INVALIDATED_REQUEST_STATE,"d2_request_id":INVALIDATED_REQUEST_ID,
    "request_binding_sha256":INVALIDATED_REQUEST_BINDING_SHA256,"request_file_sha256":INVALIDATED_REQUEST_FILE_SHA256,
    "host_authorization_id":H4_AUTHORIZATION_ID,"host_preflight_result_sha256":H4_RESULT_SHA256,
    "reason":"REQUEST_BOUND_TO_FALSE_PREDECESSOR_STATE_AFTER_PARALLEL_DIALOG_EXECUTION",
    "actual_predecessor_request_id":PREDECESSOR_REQUEST_ID,"actual_predecessor_state":"CONSUMED_FAILED",
    "actual_predecessor_failure_code":"BASELINE_STATE_MISMATCH","physical_authorization_created":False,
    "physical_authorization_claimed":False,"physical_authorization_consumed":False,"physical_execution_occurred":False,
    "request_reuse_permitted":False,"replay_permitted":False,"automatic_retry_permitted":False,**FALSE_BOUNDARY}

def build_baseline_evidence(*,board_identity_sha256:str,serial_identity_sha256:str,chip_id_output_sha256:str,
 flash_id_output_sha256:str,test_partition_sha256:str,test_partition_size:int,
 expected_legacy_baseline_sha256:str=EXPECTED_BASELINE_STATE_SHA256)->dict[str,Any]:
    for x,c in ((board_identity_sha256,"BOARD"),(serial_identity_sha256,"SERIAL"),(chip_id_output_sha256,"CHIP"),
                (flash_id_output_sha256,"FLASH"),(test_partition_sha256,"PARTITION"),(expected_legacy_baseline_sha256,"EXPECTED")):
        validate_sha256(x,"BASELINE_"+c+"_INVALID")
    require(isinstance(test_partition_size,int) and test_partition_size>0,"BASELINE_PARTITION_SIZE_INVALID")
    legacy={"schema":"gh.h3.n2.stage2d9r-successor-board-baseline/1","board_identity_sha256":board_identity_sha256,
    "serial_identity_sha256":serial_identity_sha256,"chip_id_output_sha256":chip_id_output_sha256,
    "flash_id_output_sha256":flash_id_output_sha256,"test_partition_sha256":test_partition_sha256,
    "test_partition_size":test_partition_size}; observed=canonical_json_sha256(legacy)
    return {"schema":BASELINE_EVIDENCE_SCHEMA,"policy_version":2,"expected_legacy_baseline_sha256":expected_legacy_baseline_sha256,
    "observed_legacy_baseline_sha256":observed,"legacy_baseline_matches":observed==expected_legacy_baseline_sha256,
    **{k:v for k,v in legacy.items() if k!="schema"},"raw_chip_output_included":False,"raw_flash_output_included":False,
    "before_destructive_operation":True}

def source_contract(source_sha:str)->dict[str,Any]:
    validate_sha40(source_sha,"SOURCE_SHA_INVALID");require(source_sha!=BASE_HEAD_SHA,"SOURCE_MUST_LAYER_ABOVE_PR195")
    return {"schema":SCHEMA,"state":"BASELINE_MISMATCH_EVIDENCE_REPAIR_SOURCE_FROZEN_UNAUTHORIZED","stage":STAGE,
    "decision_id":DECISION_ID,"source_sha":source_sha,"base_pr":BASE_PR,"base_branch":BASE_BRANCH,"base_head_sha":BASE_HEAD_SHA,
    "repository_head_sha_at_repair":REPOSITORY_HEAD_AT_REPAIR,"repository_head_role":"AUDIT_ONLY","repository_head_enforced":False,
    "predecessor_request_id":PREDECESSOR_REQUEST_ID,"predecessor_state":"CONSUMED_FAILED",
    "predecessor_failure_code":"BASELINE_STATE_MISMATCH","predecessor_terminal_result_sha256":PREDECESSOR_TERMINAL_RESULT_SHA256,
    "invalidated_request_id":INVALIDATED_REQUEST_ID,"invalidated_request_binding_sha256":INVALIDATED_REQUEST_BINDING_SHA256,
    "invalidated_request_state":INVALIDATED_REQUEST_STATE,"baseline_evidence_policy_version":2,
    "future_diagnostic_authorization_id":FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,"future_physical_request_id":FUTURE_PHYSICAL_REQUEST_ID,
    "future_physical_request_created":False,"next_gate":"EXACT_READONLY_BASELINE_DIAGNOSTIC_AUTHORIZATION",**FALSE_BOUNDARY}
def build_diagnostic_request_draft(source_sha:str,review_binding_sha256:str)->dict[str,Any]:
    validate_sha40(source_sha,"SOURCE_SHA_INVALID");validate_sha256(review_binding_sha256,"REVIEW_BINDING_SHA256_INVALID")
    return {"schema":DIAGNOSTIC_REQUEST_SCHEMA,"state":"BASELINE_DIAGNOSTIC_REQUEST_AWAITING_EXACT_AUTHORIZATION",
    "stage":STAGE,"decision_id":DECISION_ID,"authorization_id":FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,
    "operation":FUTURE_DIAGNOSTIC_OPERATION,"source_sha":source_sha,"review_binding_sha256":review_binding_sha256,
    "predecessor_terminal_result_sha256":PREDECESSOR_TERMINAL_RESULT_SHA256,"h4_result_sha256":H4_RESULT_SHA256,
    "invalidated_request_binding_sha256":INVALIDATED_REQUEST_BINDING_SHA256,"expected_board_identity_sha256":BOARD_IDENTITY_SHA256,
    "expected_serial_identity_sha256":SERIAL_IDENTITY_SHA256,"expected_legacy_baseline_sha256":EXPECTED_BASELINE_STATE_SHA256,
    "read_operations":["CHIP_ID","FLASH_ID","READ_TEST_PARTITION"],"test_partition_address":"0x400000",
    "test_partition_size":"0x10000","future_physical_request_id":FUTURE_PHYSICAL_REQUEST_ID,
    "future_physical_request_created":False,"issued_at":None,"expires_at":None,"one_shot":True,
    "replay_permitted":False,"automatic_retry_permitted":False,**FALSE_BOUNDARY}
def validate_diagnostic_authorization(v:Mapping[str,Any],*,source_sha:str,review_binding_sha256:str,
 diagnostic_script_sha256:str,python_executable_sha256:str,esptool_executable_sha256:str,now:datetime|None=None)->dict[str,Any]:
    exact={"schema":DIAGNOSTIC_AUTH_SCHEMA,"authorization_id":FUTURE_DIAGNOSTIC_AUTHORIZATION_ID,
    "operation":FUTURE_DIAGNOSTIC_OPERATION,"authorized":True,"one_shot":True,"replay_permitted":False,
    "automatic_retry_permitted":False,"source_sha":source_sha,"review_binding_sha256":review_binding_sha256,
    "predecessor_terminal_result_sha256":PREDECESSOR_TERMINAL_RESULT_SHA256,"h4_result_sha256":H4_RESULT_SHA256,
    "invalidated_request_binding_sha256":INVALIDATED_REQUEST_BINDING_SHA256,"expected_board_identity_sha256":BOARD_IDENTITY_SHA256,
    "expected_serial_identity_sha256":SERIAL_IDENTITY_SHA256,"expected_legacy_baseline_sha256":EXPECTED_BASELINE_STATE_SHA256,
    "diagnostic_script_sha256":diagnostic_script_sha256,"python_executable_sha256":python_executable_sha256,
    "esptool_executable_sha256":esptool_executable_sha256,"board_operation_authorized":True,"usb_enumeration_authorized":True,
    "esptool_readonly_authorized":True,"serial_open_authorized":False,"flash_write_authorized":False,
    "flash_erase_authorized":False,"physical_nvs_operation_authorized":False,"network_operation_authorized":False,
    "broker_operation_authorized":False,"prepare_authorized":False,"verify_authorized":False,"activate_authorized":False,
    "cleanup_authorized":False,"future_physical_request_created":False}
    for k,x in exact.items():require(v.get(k)==x,"DIAGNOSTIC_AUTH_"+k.upper()+"_MISMATCH")
    issued=utc(v.get("issued_at"),"DIAGNOSTIC_AUTH_ISSUED_AT_INVALID");expires=utc(v.get("expires_at"),"DIAGNOSTIC_AUTH_EXPIRES_AT_INVALID")
    current=now or datetime.now(timezone.utc);require(issued<=current<=expires,"DIAGNOSTIC_AUTH_NOT_CURRENT")
    require((expires-issued).total_seconds()<=3600,"DIAGNOSTIC_AUTH_WINDOW_TOO_LONG")
    w=dict(v);sup=w.pop("authorization_record_sha256",None);require(sup==canonical_json_sha256(w),"DIAGNOSTIC_AUTH_RECORD_DIGEST_MISMATCH")
    return dict(v)

if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--source-sha",required=True);a=p.parse_args();print(json.dumps(source_contract(a.source_sha),sort_keys=True))
