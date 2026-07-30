"""D2-16 full inherited authorization preflight contract."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
from pathlib import Path
from typing import Any
import h3_n2_stage2d9r_g3r_d2_16_contract_base_20260730_v1 as b
for _n in dir(b):
 if not _n.startswith("_"):globals()[_n]=getattr(b,_n)
IMMUTABLE_ARTIFACT_ID=8716016864; IMMUTABLE_ARCHIVE_SHA256="71ee1c2bfe951e1e4db833ad4efb96e436ba6c6a0729d52caf641b2294f2d456"; IMMUTABLE_MERGED_SHA256="d984c0d7cef9a54a543912d32fd0ceb1e32ecbc0bab7a98a94732531160934e3"
RECOVERY_ARTIFACT_ID=8716016864; RECOVERY_ARCHIVE_SHA256=IMMUTABLE_ARCHIVE_SHA256; RECOVERY_DESCRIPTOR_SHA256="ef38564bac785172efbc6d60488bdafb095a2c8699e23e38e0f91291c50610b9"
PRIVATE_PACKAGE_SHA256="d2749c4a173876282275e476a577a7e4a27440429b31592c379bdedd1d3bfa0f"; PREPARE_COMMAND_SHA256="022577c2ee88c57ab45533f53a5630f7eb94e142985533cdc1a8166de0d3317f"; VERIFY_COMMAND_SHA256="9d5aad5eb2eedd6ba8460df80af3653dc68c8e24cd12a6bcd69e5460436050d7"
CANDIDATE_DIGEST_SHA256="73b58ea30e4355d90afa4a9bc9331968537d6318db046f562212c5b836670b15"; CA_PEM_SHA256="e9abe88df80f21311ea9ea4977b78f531380a37564490c1108fabeae8cc5bc5a"; BUILD_BINDING="4051f5d541898cef742f35aeec757e7fc479f383"
LEGACY_EXACT_FIELD_NAMES=("immutable_artifact_id","immutable_artifact_archive_sha256","immutable_payload_tar_sha256","immutable_merged_image_sha256","recovery_artifact_id","recovery_artifact_archive_sha256","recovery_payload_tar_sha256","recovery_descriptor_sha256","private_package_sha256","prepare_command_sha256","verify_command_sha256","candidate_digest_sha256","ca_pem_sha256","build_binding","execution_script_sha256","python_executable_sha256","openssl_executable_sha256","esptool_executable_sha256","mosquitto_executable_sha256")
LEGACY_HEX_FIELD_NAMES=("request_binding_sha256","execution_package_sha256","execution_launcher_sha256","execution_marker_name_sha256","board_identity_sha256","serial_identity_sha256","baseline_state_sha256")
LEGACY_FIELD_SET_SHA256=hashlib.sha256("\n".join((*LEGACY_EXACT_FIELD_NAMES,*LEGACY_HEX_FIELD_NAMES)).encode()).hexdigest(); b.LEGACY_FIELD_SET_SHA256=LEGACY_FIELD_SET_SHA256

def legacy_authorization_exact_fields(*,root:Path,execution_script_path:Path,python_path:Path,openssl_path:Path,esptool_path:Path,mosquitto_path:Path)->dict[str,Any]:
 p=validate_execution_package(root)
 return {"immutable_artifact_id":IMMUTABLE_ARTIFACT_ID,"immutable_artifact_archive_sha256":IMMUTABLE_ARCHIVE_SHA256,"immutable_payload_tar_sha256":IMMUTABLE_PAYLOAD_TAR_SHA256,"immutable_merged_image_sha256":IMMUTABLE_MERGED_SHA256,"recovery_artifact_id":RECOVERY_ARTIFACT_ID,"recovery_artifact_archive_sha256":RECOVERY_ARCHIVE_SHA256,"recovery_payload_tar_sha256":RECOVERY_PAYLOAD_TAR_SHA256,"recovery_descriptor_sha256":RECOVERY_DESCRIPTOR_SHA256,"private_package_sha256":PRIVATE_PACKAGE_SHA256,"prepare_command_sha256":PREPARE_COMMAND_SHA256,"verify_command_sha256":VERIFY_COMMAND_SHA256,"candidate_digest_sha256":CANDIDATE_DIGEST_SHA256,"ca_pem_sha256":CA_PEM_SHA256,"build_binding":BUILD_BINDING,"execution_script_sha256":sha256_file(execution_script_path),"python_executable_sha256":sha256_file(python_path),"openssl_executable_sha256":sha256_file(openssl_path),"esptool_executable_sha256":sha256_file(esptool_path),"mosquitto_executable_sha256":sha256_file(mosquitto_path),"execution_package_sha256":p["package_sha256"]}

def authorization_template(*,request:dict[str,Any],root:Path,issued_at:datetime,expires_at:datetime,execution_script_path:Path,python_path:Path,openssl_path:Path,esptool_path:Path,mosquitto_path:Path,board_identity_sha256:str,serial_identity_sha256:str,baseline_state_sha256:str,extras:dict[str,Any]|None=None)->dict[str,Any]:
 validate_physical_request(request,root); issued=issued_at.astimezone(timezone.utc); expires=expires_at.astimezone(timezone.utc);require(issued<expires and (expires-issued).total_seconds()<=7200,"AUTHORIZATION_WINDOW_INVALID")
 for x in (board_identity_sha256,serial_identity_sha256,baseline_state_sha256):require(HEX64.fullmatch(x) is not None,"AUTHORIZATION_IDENTITY_DIGEST_INVALID")
 p=validate_execution_package(root);v={"schema":AUTH_SCHEMA,"stage":STAGE,"decision_id":DECISION_ID,"d2_request_id":D2_REQUEST_ID,"source_sha":request["source_sha"],"request_binding_sha256":request["request_binding_sha256"],"execution_closure_sha256":p["closure"]["execution_closure_sha256"],"execution_package_sha256":p["package_sha256"],"execution_wrapper_sha256":request["execution_wrapper_sha256"],"execution_launcher_sha256":request["execution_launcher_sha256"],"execution_contract_sha256":request["execution_contract_sha256"],"execution_marker_name_sha256":hashlib.sha256(D2_REQUEST_ID.encode()).hexdigest(),"board_identity_sha256":board_identity_sha256,"serial_identity_sha256":serial_identity_sha256,"baseline_state_sha256":baseline_state_sha256,"issued_at":issued.isoformat().replace("+00:00","Z"),"expires_at":expires.isoformat().replace("+00:00","Z"),"authorized":True,"authorization_created":True,"authorization_claimed":False,"authorization_consumed":False,"one_shot":True,"prepare_max_count":1,"verify_max_count":1,"locked_recovery_authorized":True,"locked_recovery_max_count":1,"locked_recovery_scope":"TEST_PARTITION_ONLY","replay_permitted":False,"automatic_retry_permitted":False,"activate_authorized":False,"cleanup_authorized":False,"production_operation_authorized":False,"full_inherited_authorization_preflight_required":True,"legacy_authorization_field_set_sha256":LEGACY_FIELD_SET_SHA256}
 v.update(legacy_authorization_exact_fields(root=root,execution_script_path=execution_script_path,python_path=python_path,openssl_path=openssl_path,esptool_path=esptool_path,mosquitto_path=mosquitto_path))
 if extras:
  for k,x in extras.items():require(k not in v and k!="authorization_record_sha256","AUTHORIZATION_EXTRA_COLLISION");v[k]=x
 v["authorization_record_sha256"]=canonical_sha256(v);return v

def validate_authorization_contract(a:dict[str,Any],r:dict[str,Any],root:Path,*,now:datetime|None=None)->dict[str,Any]:
 validate_physical_request(r,root);p=validate_execution_package(root);fixed={"schema":AUTH_SCHEMA,"stage":STAGE,"decision_id":DECISION_ID,"d2_request_id":D2_REQUEST_ID,"source_sha":r["source_sha"],"request_binding_sha256":r["request_binding_sha256"],"execution_closure_sha256":p["closure"]["execution_closure_sha256"],"execution_package_sha256":p["package_sha256"],"execution_wrapper_sha256":r["execution_wrapper_sha256"],"execution_launcher_sha256":r["execution_launcher_sha256"],"execution_contract_sha256":r["execution_contract_sha256"],"execution_marker_name_sha256":hashlib.sha256(D2_REQUEST_ID.encode()).hexdigest(),"authorized":True,"authorization_created":True,"authorization_claimed":False,"authorization_consumed":False,"one_shot":True,"prepare_max_count":1,"verify_max_count":1,"locked_recovery_authorized":True,"locked_recovery_max_count":1,"locked_recovery_scope":"TEST_PARTITION_ONLY","replay_permitted":False,"automatic_retry_permitted":False,"activate_authorized":False,"cleanup_authorized":False,"production_operation_authorized":False,"full_inherited_authorization_preflight_required":True,"legacy_authorization_field_set_sha256":LEGACY_FIELD_SET_SHA256}
 for k,x in fixed.items():require(a.get(k)==x,"AUTHORIZATION_"+k.upper()+"_MISMATCH")
 for k in ("board_identity_sha256","serial_identity_sha256","baseline_state_sha256"):require(isinstance(a.get(k),str) and HEX64.fullmatch(a[k]) is not None,"AUTHORIZATION_"+k.upper()+"_INVALID")
 try:issued=datetime.fromisoformat(str(a.get("issued_at")).replace("Z","+00:00")).astimezone(timezone.utc);expires=datetime.fromisoformat(str(a.get("expires_at")).replace("Z","+00:00")).astimezone(timezone.utc)
 except Exception as e:raise ContractError("AUTHORIZATION_TIME_INVALID") from e
 cur=(now or datetime.now(timezone.utc)).astimezone(timezone.utc);require(issued<=cur<=expires and 0<(expires-issued).total_seconds()<=7200,"AUTHORIZATION_NOT_CURRENT")
 q=dict(a);d=q.pop("authorization_record_sha256",None);require(isinstance(d,str) and canonical_sha256(q)==d,"AUTHORIZATION_BINDING_MISMATCH");return a

def validate_full_inherited_authorization(a:dict[str,Any],r:dict[str,Any],root:Path,*,execution_script_path:Path,python_path:Path,openssl_path:Path,esptool_path:Path,mosquitto_path:Path,now:datetime|None=None)->dict[str,Any]:
 validate_authorization_contract(a,r,root,now=now); exact=legacy_authorization_exact_fields(root=root,execution_script_path=execution_script_path,python_path=python_path,openssl_path=openssl_path,esptool_path=esptool_path,mosquitto_path=mosquitto_path)
 for k,x in exact.items():require(a.get(k)==x,"AUTHORIZATION_"+k.upper()+"_MISMATCH")
 for k in LEGACY_HEX_FIELD_NAMES:require(isinstance(a.get(k),str) and HEX64.fullmatch(a[k]) is not None,"AUTHORIZATION_"+k.upper()+"_INVALID")
 return a

def __getattr__(name:str)->Any:return getattr(b.upstream,name)
