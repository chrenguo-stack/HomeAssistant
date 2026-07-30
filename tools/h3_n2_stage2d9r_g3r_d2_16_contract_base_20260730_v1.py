"""Shared D2-16 public package/request contract."""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
from typing import Any
import h3_n2_stage2d9r_g3r_d2_15_contract_compatibility_install_preflight_repair_execution_binding_contract_20260730_v1 as upstream
DECISION_ID="D1-H3N2-STAGE2D9R-G3R-D2-16-FULL-INHERITED-AUTHORIZATION-PREFLIGHT-REPAIR-20260730-01"
STAGE="H3/N2 Stage 2D-9R G3R D2-16 full-inherited-authorization-preflight-repaired successor"
D2_REQUEST_ID="D2-H3N2-STAGE2D9R-G3R-FULL-INHERITED-AUTHORIZATION-PREFLIGHT-REPAIRED-PHYSICAL-20260730-16"
REQUEST_SCHEMA="gh.h3.n2.stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repaired-physical-request/1"
AUTH_SCHEMA="gh.h3.n2.stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repaired-physical-authorization/1"
RESULT_SCHEMA=AUTH_SCHEMA.replace("authorization","result"); MARKER_SCHEMA=AUTH_SCHEMA.replace("authorization","marker")
PRE_RESULT_SCHEMA=AUTH_SCHEMA.replace("authorization","preclaim-result"); PRE_MARKER_SCHEMA=AUTH_SCHEMA.replace("authorization","preclaim-marker")
PACKAGE_BINDING_SCHEMA="gh.h3.n2.stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repaired-execution-package/1"
CLOSURE_SCHEMA="gh.h3.n2.stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repaired-execution-closure-manifest/1"
BASE_PR=214; BASE_HEAD_SHA="822935928134efe833a5f3c3179de0d0028e6deb"; BASE_BRANCH="fix/h3-n2-stage2d9r-g3r-d2-15-contract-compatibility-install-preflight-repair-20260730-v1"
MAIN_SHA_AT_BINDING="64c6b093c3ba6a8476c9392c8d106394b2542fb5"; PR214_ARTIFACT_ID=8747207488
PR214_ARTIFACT_SHA256="891760469a6b29e6e312cbde21bbb0fbb73fd0856cf1d507cda4094313dda091"; PR214_REVIEW_BINDING_SHA256="dea0a4e5eea6c1e0a1deb12c7f9cfb33402bbf5033aa1abf074bd24fb07329f0"
D2_15_ID=upstream.D2_REQUEST_ID; D2_15_TERMINAL_STATE="CONSUMED_FAILED_PRECLAIM"; D2_15_FAILURE_CODE="AUTHORIZATION_STAGE_MISMATCH"; D2_15_FAILURE_STAGE="PRECLAIM"
D2_15_TERMINAL_RESULT_SHA256="11cd9d80be3a27080e3c018d69f1e7a0ae838c52be902e6bd4d8a8411c07078c"; D2_15_STDOUT_SHA256="794060de1caa3c80ff797194349b620141dda077dd7456efe60588b1c633502c"; D2_15_STDERR_SHA256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"; D2_15_RETURN_CODE=2
CLOSURE_FILE="EXECUTION_CLOSURE_MANIFEST.json"; PACKAGE_BINDING_FILE="EXECUTION_PACKAGE_BINDING.json"; SUMS_FILE="SHA256SUMS"; CONTROL_FILES={CLOSURE_FILE,PACKAGE_BINDING_FILE,SUMS_FILE}
WRAPPER_FILE="h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repaired_physical_d2_wrapper_20260730_v1.py"; LAUNCHER_FILE="run_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repaired_physical_d2_20260730_v1.sh"
CONTRACT_FILE="h3_n2_stage2d9r_g3r_d2_16_full_inherited_authorization_preflight_repair_execution_binding_contract_20260730_v1.py"; SUPPORT_FILE=Path(__file__).name
DECISION_FILE="h3-n2-stage2d9r-g3r-d2-16-full-inherited-authorization-preflight-repair-20260730-v1.json"; HEX40=re.compile(r"^[0-9a-f]{40}$"); HEX64=re.compile(r"^[0-9a-f]{64}$")
for _n in ("IMMUTABLE_BUILD_BINDING","APPLICATION_SHA256","IMMUTABLE_PAYLOAD_TAR_SHA256","RECOVERY_PAYLOAD_TAR_SHA256","IMMUTABLE_PAYLOAD_FILE","RECOVERY_PAYLOAD_FILE","FINAL_EXECUTION_BINDING","FINAL_EXECUTION_BINDING_SHA256","D2_10_ID","D2_10_TERMINAL_RESULT_SHA256","D2_10_TERMINAL_MARKER_SHA256"):
 globals()[_n]=getattr(upstream,_n)
class ContractError(RuntimeError): pass
def require(ok:bool,code:str)->None:
 if not ok: raise ContractError(code)
def canonical_sha256(v:object)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1048576),b""):h.update(x)
 return h.hexdigest()
def load_json(p:Path,code:str)->dict[str,Any]:
 require(p.is_file() and not p.is_symlink(),code)
 try:v=json.loads(p.read_text())
 except Exception as e:raise ContractError(code) from e
 require(isinstance(v,dict),code);return v
def validate_decision(p:Path)->dict[str,Any]:
 v=load_json(p,"DECISION_FILE_INVALID");d=v.pop("decision_binding_sha256",None);require(isinstance(d,str) and canonical_sha256(v)==d,"DECISION_BINDING_MISMATCH")
 exact={"decision_id":DECISION_ID,"base_pr":BASE_PR,"base_head_sha":BASE_HEAD_SHA,"d2_request_id":D2_REQUEST_ID,"state":"FROZEN_UNAUTHORIZED_D2_16_FULL_INHERITED_AUTHORIZATION_PREFLIGHT_REPAIR","predecessor_request_id":D2_15_ID,"predecessor_terminal_state":D2_15_TERMINAL_STATE,"predecessor_failure_code":D2_15_FAILURE_CODE,"predecessor_failure_stage":D2_15_FAILURE_STAGE,"predecessor_authorization_claimed":False,"predecessor_authorization_consumed":True,"predecessor_board_operation":False,"predecessor_usb_enumeration":False,"predecessor_replay_permitted":False,"full_inherited_authorization_preflight_required":True,"host_only_base_validator_execution_required":True,"legacy_authorization_exact_fields_required":True,"real_shell_integration_required":True,"preclaim_failure_evidence_required":True,"physical_request_created":True,"physical_request_authorized":False,"physical_authorization_created":False,"board_operation":False,"usb_enumeration":False,"serial_operation":False,"esptool_operation":False,"flash_operation":False,"network_operation":False,"replay_permitted":False,"automatic_retry_permitted":False}
 for k,x in exact.items():require(v.get(k)==x,"DECISION_"+k.upper())
 v["decision_binding_sha256"]=d;return v
def package_set_digest(root:Path)->str:
 fs=[{"name":p.name,"sha256":sha256_file(p)} for p in sorted(root.iterdir(),key=lambda x:x.name) if p.is_file() and not p.is_symlink() and p.name not in {SUMS_FILE,PACKAGE_BINDING_FILE}]
 require(bool(fs),"PACKAGE_EMPTY");return canonical_sha256({"schema":"gh.h3.n2.stage2d9r-g3r-d2-16-package-set/1","files":fs})
def build_execution_closure_manifest(root:Path)->dict[str,Any]:
 v={"schema":CLOSURE_SCHEMA,"decision_id":DECISION_ID,"d2_request_id":D2_REQUEST_ID,"base_pr":BASE_PR,"base_head_sha":BASE_HEAD_SHA,"files":[{"name":p.name,"sha256":sha256_file(p)} for p in sorted(root.iterdir(),key=lambda x:x.name) if p.is_file() and not p.is_symlink() and p.name not in CONTROL_FILES]};v["execution_closure_sha256"]=canonical_sha256(v);return v
def _verify_sums(root:Path)->None:
 s=root/SUMS_FILE;require(s.is_file() and not s.is_symlink(),"PACKAGE_SUMS_INVALID");e={}
 for line in s.read_text().splitlines():
  d,n=line.split("  ",1);require(HEX64.fullmatch(d) is not None and n not in e and "/" not in n,"PACKAGE_SUMS_INVALID");e[n]=d
 o={p.name for p in root.iterdir() if p.is_file() and not p.is_symlink() and p!=s};require(set(e)==o,"PACKAGE_SUMS_COVERAGE_MISMATCH")
 for n,d in e.items():require(sha256_file(root/n)==d,"PACKAGE_DIGEST_MISMATCH")
def validate_execution_package(root:Path)->dict[str,Any]:
 require(root.is_dir() and not root.is_symlink(),"PACKAGE_ROOT_INVALID");require(all(p.is_file() and not p.is_symlink() for p in root.iterdir()),"PACKAGE_MEMBER_INVALID");_verify_sums(root)
 c=load_json(root/CLOSURE_FILE,"EXECUTION_CLOSURE_INVALID");d=c.pop("execution_closure_sha256",None);require(canonical_sha256(c)==d,"EXECUTION_CLOSURE_BINDING_MISMATCH");c["execution_closure_sha256"]=d;b=load_json(root/PACKAGE_BINDING_FILE,"EXECUTION_PACKAGE_BINDING_INVALID")
 require(b.get("schema")==PACKAGE_BINDING_SCHEMA and b.get("decision_id")==DECISION_ID and b.get("d2_request_id")==D2_REQUEST_ID,"EXECUTION_PACKAGE_ID_MISMATCH");require(b.get("base_pr")==BASE_PR and b.get("base_head_sha")==BASE_HEAD_SHA,"EXECUTION_PACKAGE_BASE_MISMATCH");require(b.get("pr214_artifact_id")==PR214_ARTIFACT_ID and b.get("pr214_artifact_sha256")==PR214_ARTIFACT_SHA256,"PR214_ARTIFACT_MISMATCH");require(b.get("execution_closure_sha256")==d,"EXECUTION_CLOSURE_DIGEST_MISMATCH");require(b.get("execution_package_sha256")==package_set_digest(root),"EXECUTION_PACKAGE_DIGEST_MISMATCH")
 for k,n in (("execution_wrapper_sha256",WRAPPER_FILE),("execution_launcher_sha256",LAUNCHER_FILE),("execution_contract_sha256",CONTRACT_FILE),("execution_support_sha256",SUPPORT_FILE)):require(b.get(k)==sha256_file(root/n),k.upper()+"_MISMATCH")
 return {"binding":b,"closure":c,"package_sha256":b["execution_package_sha256"]}
def canonical_package_digest(root:Path)->str:return str(validate_execution_package(root)["package_sha256"])
def request_template(root:Path,*,source_sha:str)->dict[str,Any]:
 require(HEX40.fullmatch(source_sha) is not None,"SOURCE_SHA_INVALID");p=validate_execution_package(root);b=p["binding"]
 v={"schema":REQUEST_SCHEMA,"state":"FROZEN_UNAUTHORIZED_AWAITING_EXACT_PHYSICAL_AUTHORIZATION","stage":STAGE,"decision_id":DECISION_ID,"d2_request_id":D2_REQUEST_ID,"source_sha":source_sha,"base_pr":BASE_PR,"base_head_sha":BASE_HEAD_SHA,"execution_closure_sha256":p["closure"]["execution_closure_sha256"],"execution_package_sha256":p["package_sha256"],"execution_wrapper_sha256":b["execution_wrapper_sha256"],"execution_launcher_sha256":b["execution_launcher_sha256"],"execution_contract_sha256":b["execution_contract_sha256"],"pr214_artifact_id":PR214_ARTIFACT_ID,"pr214_artifact_sha256":PR214_ARTIFACT_SHA256,"pr214_review_binding_sha256":PR214_REVIEW_BINDING_SHA256,"predecessor_request_id":D2_15_ID,"predecessor_terminal_state":D2_15_TERMINAL_STATE,"predecessor_failure_code":D2_15_FAILURE_CODE,"predecessor_failure_stage":D2_15_FAILURE_STAGE,"predecessor_authorization_claimed":False,"predecessor_authorization_consumed":True,"predecessor_board_operation":False,"predecessor_usb_enumeration":False,"full_inherited_authorization_preflight_required":True,"legacy_authorization_field_set_sha256":LEGACY_FIELD_SET_SHA256,"authorized":False,"authorization_created":False,"authorization_claimed":False,"authorization_consumed":False,"physical_request_authorized":False,"one_shot":True,"prepare_max_count":1,"verify_max_count":1,"locked_recovery_max_count":1,"locked_recovery_scope":"TEST_PARTITION_ONLY","replay_permitted":False,"automatic_retry_permitted":False,"activate_authorized":False,"cleanup_authorized":False,"production_operation_authorized":False,"board_operation":False,"usb_enumeration":False,"serial_operation":False,"esptool_operation":False,"flash_operation":False,"network_operation":False,"broker_started":False,"prepare_executed":False,"verify_executed":False,"physical_execution_started":False};v["request_binding_sha256"]=canonical_sha256(v);return v
def validate_physical_request(v:dict[str,Any],root:Path)->dict[str,Any]:require(v==request_template(root,source_sha=str(v.get("source_sha"))),"REQUEST_MISMATCH");return v
