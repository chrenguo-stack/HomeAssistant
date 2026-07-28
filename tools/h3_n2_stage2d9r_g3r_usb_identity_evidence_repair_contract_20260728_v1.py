#!/usr/bin/env python3
"""USB identity evidence repair contract; source-only until exact B2 authorization."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, re
from pathlib import Path
from typing import Any, Mapping

SCHEMA="gh.h3.n2.stage2d9r-g3r-usb-identity-evidence-repair-contract/1"
REVIEW_SCHEMA="gh.h3.n2.stage2d9r-g3r-usb-identity-evidence-repair-review/1"
B1_DISPOSITION_SCHEMA="gh.h3.n2.stage2d9r-g3r-b1-terminal-disposition/1"
OPERATOR_REPORT_SCHEMA="gh.h3.n2.stage2d9r-g3r-operator-usb-port-change-report/1"
B2_REQUEST_SCHEMA="gh.h3.n2.stage2d9r-g3r-usb-baseline-diagnostic-request/1"
B2_AUTH_SCHEMA="gh.h3.n2.stage2d9r-g3r-usb-baseline-diagnostic-authorization/1"
B2_RESULT_SCHEMA="gh.h3.n2.stage2d9r-g3r-usb-baseline-diagnostic-result/1"
B2_MARKER_SCHEMA="gh.h3.n2.stage2d9r-g3r-usb-baseline-diagnostic-marker/1"
TRANSPORT_EVIDENCE_SCHEMA="gh.h3.n2.stage2d9r-g3r-usb-transport-evidence/2"
BASELINE_EVIDENCE_SCHEMA="gh.h3.n2.stage2d9r-g3r-path-neutral-baseline-evidence/3"
STAGE="H3/N2 Stage 2D-9R G3R USB identity evidence repair"
DECISION_ID="D1-H3N2-STAGE2D9R-G3R-USB-IDENTITY-EVIDENCE-REPAIR-20260728-01"
BASE_PR=196
BASE_BRANCH="fix/h3-n2-stage2d9r-g3r-baseline-mismatch-evidence-repair-20260728-v1"
BASE_HEAD_SHA="3b44bc48cdee79efcb77500c855362b1690d8877"
REPOSITORY_HEAD_AT_REPAIR="64c6b093c3ba6a8476c9392c8d106394b2542fb5"
UPSTREAM_ARTIFACT_ID=8694673276
UPSTREAM_ARTIFACT_SHA256="15ff1968b1fabdf6cfd967830db35d2f690cf785586486ed69a92ad6b8403782"
UPSTREAM_REVIEW_BINDING_SHA256="07cd1b14c8e19dd2bc58304bd74ba4a7b2fecfa56fef7f5d26abb8781eab12fd"
UPSTREAM_INNER_TAR_SHA256="28d3531522337ec2b9d59a6039994ca673f2666376a107ba55cedf903514e095"
B1_AUTHORIZATION_ID="B1-H3N2-STAGE2D9R-G3R-BASELINE-EVIDENCE-DIAGNOSTIC-READONLY-20260728-01"
B1_AUTHORIZATION_RECORD_SHA256="1e5a9236f33af37b97128c9247b34128d5c50fb928195467d3bf5a16a5eabb9a"
B1_AUTHORIZATION_FILE_SHA256="acdc805c66f81dbc2bd50ad60f57e12441c9b3710f5f8e128acdb610717120bc"
B1_RESULT_SHA256="27cab5ab00dd55a1cac8aa2c1284f8b1c90b553073179eb8fdfb4918f1360eae"
B1_RESULT_FILE_SHA256="473130f500b8e5b0eb5624a583adbc35c87c6f48ab331ddd8a54143c034c1700"
B1_MARKER_FILE_SHA256="8a1365cbc94b743ca1f7b34f51f620fbd67c9fbdbd8175c745d50e577090f936"
B1_FAILURE_CODE="BOARD_IDENTITY_MISMATCH"
EXPECTED_LEGACY_BOARD_IDENTITY_SHA256="2607b7df80b8b636548a8d9d97c0a6b4e4ead57e9a2cc6fcb7f93643617242f8"
EXPECTED_LEGACY_SERIAL_IDENTITY_SHA256="b6dba7ee0db02feba166935ae8ec2bbd946dbf66926e5421cfa1c1c8b8a4f2c3"
EXPECTED_LEGACY_BASELINE_SHA256="0735d98c7b4e2a698b42d39bdded1dd04f97b9441270e8bc03be347d369c8793"
OPERATOR_REPORT_ID="OPERATOR-REPORT-H3N2-STAGE2D9R-G3R-USB-PORT-CHANGED-20260728-01"
OPERATOR_REPORT_EVIDENCE_ROLE="EXPLANATORY_NOT_CRYPTOGRAPHIC_PROOF"
FUTURE_B2_AUTHORIZATION_ID="B2-H3N2-STAGE2D9R-G3R-USB-IDENTITY-AND-BASELINE-DIAGNOSTIC-READONLY-20260728-01"
FUTURE_B2_OPERATION="READONLY_CAPTURE_USB_TRANSPORT_AND_PATH_NEUTRAL_BASELINE_V3"
FUTURE_PHYSICAL_REQUEST_ID="D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-05"
HEX40=re.compile(r"^[0-9a-f]{40}$"); HEX64=re.compile(r"^[0-9a-f]{64}$")
MAC=re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])")
FALSE_BOUNDARY={k:False for k in ("authorized authorization_created authorization_claimed authorization_consumed board_operation usb_enumeration serial_open esptool_operation flash_write flash_erase physical_nvs_operation network_operation broker_started prepare_executed verify_executed activate_executed cleanup_executed ready merge release tag deployment private_values_included private_paths_included secret_values_included future_physical_request_created").split()}

class ContractError(RuntimeError): pass
def require(ok:bool,code:str)->None:
    if not ok: raise ContractError(code)
def canonical_json_bytes(v:object)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def canonical_json_sha256(v:object)->str:return hashlib.sha256(canonical_json_bytes(v)).hexdigest()
def sha256_bytes(v:bytes)->str:return hashlib.sha256(v).hexdigest()
def sha256_text(v:str)->str:return sha256_bytes(v.encode())
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

def expected_b1_result()->dict[str,Any]:
    v={"authorization_consumed":True,"authorization_id":B1_AUTHORIZATION_ID,"automatic_retry_permitted":False,"broker_started":False,"diagnostic_result_sha256":B1_RESULT_SHA256,"failure_code":B1_FAILURE_CODE,"flash_erase":False,"flash_write":False,"network_operation":False,"one_shot":True,"replay_permitted":False,"schema":"gh.h3.n2.stage2d9r-g3r-baseline-diagnostic-result/1","serial_open":False,"status":"CONSUMED_FAILED"}
    w=dict(v);sup=w.pop("diagnostic_result_sha256");require(sup==canonical_json_sha256(w),"INTERNAL_B1_RESULT_DIGEST_MISMATCH");return v
def validate_b1_result(v:Mapping[str,Any])->dict[str,Any]:require(dict(v)==expected_b1_result(),"B1_RESULT_MISMATCH");return dict(v)
def b1_disposition()->dict[str,Any]:
    return {"schema":B1_DISPOSITION_SCHEMA,"authorization_id":B1_AUTHORIZATION_ID,"status":"CONSUMED_FAILED","failure_code":B1_FAILURE_CODE,"authorization_record_sha256":B1_AUTHORIZATION_RECORD_SHA256,"authorization_file_sha256":B1_AUTHORIZATION_FILE_SHA256,"diagnostic_result_sha256":B1_RESULT_SHA256,"result_file_sha256":B1_RESULT_FILE_SHA256,"marker_file_sha256":B1_MARKER_FILE_SHA256,"authorization_consumed":True,"one_shot":True,"replay_permitted":False,"automatic_retry_permitted":False,"esptool_command_executed":False,"flash_write":False,"flash_erase":False,"serial_open":False,"network_operation":False,"future_physical_request_created":False}
def operator_usb_port_change_report()->dict[str,Any]:
    return {"schema":OPERATOR_REPORT_SCHEMA,"report_id":OPERATOR_REPORT_ID,"reported_usb_port_changed":True,"reported_same_test_board":True,"evidence_role":OPERATOR_REPORT_EVIDENCE_ROLE,"consistent_with_legacy_board_hash_mismatch":True,"cryptographically_proves_same_hardware":False,"accepted_as_reason_to_separate_transport_path_from_hardware_identity":True}
def _h(v:object)->str:return sha256_text(str(v if v is not None else ""))

def build_transport_evidence(i:Mapping[str,Any])->dict[str,Any]:
    for k in ("device","vid","pid","serial_number","manufacturer","product","location","hwid"):require(k in i,"TRANSPORT_IDENTITY_FIELD_MISSING")
    require(isinstance(i["vid"],int) and isinstance(i["pid"],int),"TRANSPORT_VID_PID_INVALID")
    board={"schema":"gh.h3.n2.stage2d9r-successor-board-identity/1","vid":i["vid"],"pid":i["pid"],"serial_number":str(i["serial_number"]),"manufacturer":str(i["manufacturer"]),"product":str(i["product"]),"location":str(i["location"])}
    serial={"schema":"gh.h3.n2.stage2d9r-successor-serial-identity/1","device":str(i["device"]),"vid":i["vid"],"pid":i["pid"],"serial_number":str(i["serial_number"]),"location":str(i["location"]),"hwid":str(i["hwid"])}
    neutral={"schema":"gh.h3.n2.stage2d9r-g3r-path-neutral-usb-identity/1","vid":i["vid"],"pid":i["pid"],"serial_number_sha256":_h(i["serial_number"]),"manufacturer_sha256":_h(i["manufacturer"]),"product_sha256":_h(i["product"])}
    return {"schema":TRANSPORT_EVIDENCE_SCHEMA,"policy_version":2,"vid":i["vid"],"pid":i["pid"],"legacy_board_identity_sha256":canonical_json_sha256(board),"legacy_serial_identity_sha256":canonical_json_sha256(serial),"path_neutral_usb_identity_sha256":canonical_json_sha256(neutral),"serial_number_sha256":_h(i["serial_number"]),"manufacturer_sha256":_h(i["manufacturer"]),"product_sha256":_h(i["product"]),"device_path_sha256":_h(i["device"]),"location_sha256":_h(i["location"]),"hwid_sha256":_h(i["hwid"]),"transport_path_is_audit_only":True,"location_is_hardware_identity":False,"raw_device_path_included":False,"raw_location_included":False,"captured_before_identity_comparison":True}
def extract_chip_mac_sha256(stdout:str)->tuple[str|None,int]:
    xs=sorted({m.group(0).lower() for m in MAC.finditer(stdout)});return (sha256_text(xs[0]),1) if len(xs)==1 else (None,len(xs))

def build_path_neutral_baseline_evidence(*,transport_evidence:Mapping[str,Any],chip_id_output_sha256:str,flash_id_output_sha256:str,test_partition_sha256:str,test_partition_size:int,chip_mac_sha256:str|None,chip_mac_candidate_count:int)->dict[str,Any]:
    for v,c in ((transport_evidence.get("legacy_board_identity_sha256"),"BOARD"),(transport_evidence.get("legacy_serial_identity_sha256"),"SERIAL"),(transport_evidence.get("path_neutral_usb_identity_sha256"),"USB"),(chip_id_output_sha256,"CHIP"),(flash_id_output_sha256,"FLASH"),(test_partition_sha256,"PARTITION")):validate_sha256(v,"BASELINE_"+c+"_INVALID")
    if chip_mac_sha256 is not None:validate_sha256(chip_mac_sha256,"BASELINE_CHIP_MAC_INVALID")
    require(isinstance(chip_mac_candidate_count,int) and chip_mac_candidate_count>=0,"BASELINE_CHIP_MAC_COUNT_INVALID");require(test_partition_size==0x10000,"BASELINE_PARTITION_SIZE_INVALID")
    legacy={"schema":"gh.h3.n2.stage2d9r-successor-board-baseline/1","board_identity_sha256":transport_evidence["legacy_board_identity_sha256"],"serial_identity_sha256":transport_evidence["legacy_serial_identity_sha256"],"chip_id_output_sha256":chip_id_output_sha256,"flash_id_output_sha256":flash_id_output_sha256,"test_partition_sha256":test_partition_sha256,"test_partition_size":test_partition_size}
    neutral={"schema":"gh.h3.n2.stage2d9r-g3r-path-neutral-board-baseline/1","path_neutral_usb_identity_sha256":transport_evidence["path_neutral_usb_identity_sha256"],"chip_mac_sha256":chip_mac_sha256,"chip_id_output_sha256":chip_id_output_sha256,"flash_id_output_sha256":flash_id_output_sha256,"test_partition_sha256":test_partition_sha256,"test_partition_size":test_partition_size}
    observed=canonical_json_sha256(legacy)
    return {"schema":BASELINE_EVIDENCE_SCHEMA,"policy_version":3,"transport_evidence":dict(transport_evidence),"expected_legacy_board_identity_sha256":EXPECTED_LEGACY_BOARD_IDENTITY_SHA256,"expected_legacy_serial_identity_sha256":EXPECTED_LEGACY_SERIAL_IDENTITY_SHA256,"expected_legacy_baseline_sha256":EXPECTED_LEGACY_BASELINE_SHA256,"observed_legacy_baseline_sha256":observed,"legacy_board_identity_matches":transport_evidence["legacy_board_identity_sha256"]==EXPECTED_LEGACY_BOARD_IDENTITY_SHA256,"legacy_serial_identity_matches":transport_evidence["legacy_serial_identity_sha256"]==EXPECTED_LEGACY_SERIAL_IDENTITY_SHA256,"legacy_baseline_matches":observed==EXPECTED_LEGACY_BASELINE_SHA256,"observed_path_neutral_baseline_sha256":canonical_json_sha256(neutral),"chip_mac_sha256":chip_mac_sha256,"chip_mac_candidate_count":chip_mac_candidate_count,"chip_id_output_sha256":chip_id_output_sha256,"flash_id_output_sha256":flash_id_output_sha256,"test_partition_sha256":test_partition_sha256,"test_partition_size":test_partition_size,"raw_chip_output_included":False,"raw_flash_output_included":False,"before_destructive_operation":True}

def source_contract(source_sha:str)->dict[str,Any]:
    validate_sha40(source_sha,"SOURCE_SHA_INVALID");require(source_sha!=BASE_HEAD_SHA,"SOURCE_MUST_LAYER_ABOVE_PR196")
    return {"schema":SCHEMA,"state":"USB_IDENTITY_EVIDENCE_REPAIR_SOURCE_FROZEN_UNAUTHORIZED","stage":STAGE,"decision_id":DECISION_ID,"source_sha":source_sha,"base_pr":BASE_PR,"base_branch":BASE_BRANCH,"base_head_sha":BASE_HEAD_SHA,"repository_head_sha_at_repair":REPOSITORY_HEAD_AT_REPAIR,"repository_head_role":"AUDIT_ONLY","repository_head_enforced":False,"b1_authorization_id":B1_AUTHORIZATION_ID,"b1_state":"CONSUMED_FAILED","b1_failure_code":B1_FAILURE_CODE,"b1_result_sha256":B1_RESULT_SHA256,"operator_reported_usb_port_changed":True,"operator_report_evidence_role":OPERATOR_REPORT_EVIDENCE_ROLE,"transport_location_role":"AUDIT_ONLY","stable_hardware_identity_status":"NOT_YET_ACCEPTED","future_b2_authorization_id":FUTURE_B2_AUTHORIZATION_ID,"future_physical_request_id":FUTURE_PHYSICAL_REQUEST_ID,"future_physical_request_created":False,"next_gate":"EXACT_READONLY_USB_AND_BASELINE_DIAGNOSTIC_AUTHORIZATION",**FALSE_BOUNDARY}
def build_b2_request_draft(source_sha:str,review_binding_sha256:str)->dict[str,Any]:
    validate_sha40(source_sha,"SOURCE_SHA_INVALID");validate_sha256(review_binding_sha256,"REVIEW_BINDING_INVALID")
    return {"schema":B2_REQUEST_SCHEMA,"state":"USB_AND_BASELINE_DIAGNOSTIC_REQUEST_AWAITING_EXACT_AUTHORIZATION","stage":STAGE,"decision_id":DECISION_ID,"authorization_id":FUTURE_B2_AUTHORIZATION_ID,"operation":FUTURE_B2_OPERATION,"source_sha":source_sha,"review_binding_sha256":review_binding_sha256,"upstream_artifact_id":UPSTREAM_ARTIFACT_ID,"upstream_artifact_sha256":UPSTREAM_ARTIFACT_SHA256,"b1_authorization_id":B1_AUTHORIZATION_ID,"b1_result_sha256":B1_RESULT_SHA256,"b1_failure_code":B1_FAILURE_CODE,"operator_report_id":OPERATOR_REPORT_ID,"operator_reported_usb_port_changed":True,"legacy_board_identity_is_blocking":False,"legacy_serial_identity_is_blocking":False,"transport_observation_must_be_saved_before_comparison":True,"read_operations":["CHIP_ID","FLASH_ID","READ_TEST_PARTITION"],"test_partition_address":"0x400000","test_partition_size":"0x10000","future_physical_request_id":FUTURE_PHYSICAL_REQUEST_ID,"future_physical_request_created":False,"issued_at":None,"expires_at":None,"one_shot":True,"replay_permitted":False,"automatic_retry_permitted":False,**FALSE_BOUNDARY}
def validate_b2_authorization(v:Mapping[str,Any],*,source_sha:str,review_binding_sha256:str,diagnostic_script_sha256:str,python_executable_sha256:str,esptool_executable_sha256:str,now:datetime|None=None)->dict[str,Any]:
    exact={"schema":B2_AUTH_SCHEMA,"authorization_id":FUTURE_B2_AUTHORIZATION_ID,"operation":FUTURE_B2_OPERATION,"authorized":True,"one_shot":True,"replay_permitted":False,"automatic_retry_permitted":False,"source_sha":source_sha,"review_binding_sha256":review_binding_sha256,"upstream_artifact_id":UPSTREAM_ARTIFACT_ID,"upstream_artifact_sha256":UPSTREAM_ARTIFACT_SHA256,"b1_authorization_id":B1_AUTHORIZATION_ID,"b1_result_sha256":B1_RESULT_SHA256,"b1_failure_code":B1_FAILURE_CODE,"operator_report_id":OPERATOR_REPORT_ID,"operator_reported_usb_port_changed":True,"diagnostic_script_sha256":diagnostic_script_sha256,"python_executable_sha256":python_executable_sha256,"esptool_executable_sha256":esptool_executable_sha256,"board_operation_authorized":True,"usb_enumeration_authorized":True,"esptool_readonly_authorized":True,"serial_open_authorized":False,"flash_write_authorized":False,"flash_erase_authorized":False,"physical_nvs_operation_authorized":False,"network_operation_authorized":False,"broker_operation_authorized":False,"prepare_authorized":False,"verify_authorized":False,"activate_authorized":False,"cleanup_authorized":False,"legacy_board_identity_is_blocking":False,"legacy_serial_identity_is_blocking":False,"future_physical_request_created":False}
    for k,x in exact.items():require(v.get(k)==x,"B2_AUTH_"+k.upper()+"_MISMATCH")
    issued=utc(v.get("issued_at"),"B2_AUTH_ISSUED_AT_INVALID");expires=utc(v.get("expires_at"),"B2_AUTH_EXPIRES_AT_INVALID");current=now or datetime.now(timezone.utc);require(issued<=current<=expires,"B2_AUTH_NOT_CURRENT");require((expires-issued).total_seconds()<=3600,"B2_AUTH_WINDOW_TOO_LONG")
    w=dict(v);sup=w.pop("authorization_record_sha256",None);require(sup==canonical_json_sha256(w),"B2_AUTH_RECORD_DIGEST_MISMATCH");return dict(v)

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--source-sha",required=True);a=p.parse_args();print(json.dumps(source_contract(a.source_sha),sort_keys=True))
