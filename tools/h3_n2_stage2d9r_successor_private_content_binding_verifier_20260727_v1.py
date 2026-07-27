#!/usr/bin/env python3
"""Metadata-only by default; exact one-shot U1 required for private-content read."""
from __future__ import annotations
import argparse,json,os,shutil,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Any
import h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1 as contract
import h3_n2_stage2d9r_prepare_command_protocol_20260723_v1 as protocol
import h3_n2_stage2d9r_successor_private_content_binding_common_20260727_v1 as c
import h3_n2_stage2d9r_successor_private_content_binding_deep_20260727_v1 as deep

def binding_digest(v:dict[str,Any])->str:
 x=dict(v);x.pop('review_binding_sha256',None);return c.ch(x)
def load_binding(p:Path)->dict[str,Any]:
 v=json.loads(p.read_text());c.req(isinstance(v,dict) and v.get('schema')=='gh.h3.n2.stage2d9r-successor-private-content-binding-u1-review/1' and v.get('stage')==c.STAGE,'REVIEW_BINDING_INVALID');c.req(v.get('review_binding_sha256')==binding_digest(v),'REVIEW_BINDING_DIGEST_MISMATCH');return v
def openssl_path(explicit:Path|None)->Path:
 s=str(explicit) if explicit else shutil.which('openssl');c.req(s is not None,'OPENSSL_UNAVAILABLE');p=Path(s).expanduser().resolve(strict=True);c.req(p.is_file() and os.access(p,os.X_OK),'OPENSSL_INVALID');return p
def metadata(binding:dict[str,Any],home:Path,openssl:Path)->dict[str,Any]:
 r=c.root(home);c.req(r.is_dir() and not r.is_symlink() and c.mode(r)=='0700','CUSTODY_ROOT_INVALID');priv=c.exact_json(r/'private-custody-descriptor.json',c.E['privdesc']);pub=c.exact_json(r/'public-descriptor.redacted.json',c.E['pubdesc']);c.public_descriptor(pub);m=priv.get('materials');c.req(isinstance(m,dict) and set(m)==set(contract.REQUIRED_PRIVATE_FILES),'PRIVATE_INVENTORY_MISMATCH')
 for n in contract.REQUIRED_PRIVATE_FILES:
  x=m.get(n);p=r/n;c.req(isinstance(x,dict) and x.get('relative_path')==n and x.get('mode')=='0600' and c.HEX64.fullmatch(str(x.get('sha256'))) is not None,'PRIVATE_METADATA_INVALID');c.req(p.is_file() and not p.is_symlink() and c.mode(p)=='0600','PRIVATE_FILE_METADATA_INVALID')
 c.generation_marker(home);aid=binding.get('u1_request_id');c.req(isinstance(aid,str) and aid.startswith(c.AUTH_PREFIX),'REQUEST_ID_INVALID');c.req(not c.marker(home,aid).exists(),'TARGET_MARKER_EXISTS');py=Path(sys.executable).resolve(strict=True);c.req(c.hf(py)==c.E['python'] and c.hf(openssl)==c.E['openssl'],'TOOLCHAIN_DIGEST_MISMATCH')
 return {'schema':'gh.h3.n2.stage2d9r-successor-private-content-binding-probe/1','stage':c.STAGE,'result':'PASS_METADATA_ONLY','u1_request_id':aid,'custody_root_digest_sha256':c.hb(str(r).encode()),'private_descriptor_sha256':c.E['privdesc'],'public_descriptor_sha256':c.E['pubdesc'],'private_package_sha256':c.E['package'],'generation_marker_sha256':c.E['gmark'],'generation_record_sha256':c.E['grec'],'python_executable_sha256':c.E['python'],'openssl_executable_sha256':c.E['openssl'],'target_marker_exists':False,'private_material_content_read':False,'authorization_created':False,'authorization_claimed':False,'authorization_consumed':False,'private_paths_included':False,'secret_values_included':False,'board_operation':False,'serial_operation':False,'flash_operation':False,'physical_nvs_operation':False,'network_operation':False,'broker_started':False,'prepare_executed':False,'verify_executed':False,'activate_executed':False,'cleanup_executed':False,'production_operation':False}
def auth_digest(v:dict[str,Any])->str:
 x=dict(v);x.pop('record_sha256',None);return c.ch(x)
def validate_auth(v:dict[str,Any],binding:dict[str,Any],home:Path,hashes:dict[str,str],now:datetime|None=None)->tuple[str,Path,str]:
 c.req(v.get('schema')==c.AUTH_SCHEMA and v.get('stage')==c.STAGE and v.get('operation')==c.AUTH_OPERATION,'AUTH_IDENTITY_MISMATCH');aid=v.get('authorization_id');c.req(isinstance(aid,str) and aid.startswith(c.AUTH_PREFIX),'AUTH_ID_INVALID')
 c.req(v.get('authorized') is True and v.get('one_shot') is True and v.get('replay_permitted') is False and v.get('automatic_retry_permitted') is False,'AUTH_FLAGS_MISMATCH')
 expected={'source_sha':binding.get('source_sha'),'review_binding_sha256':binding.get('review_binding_sha256'),'verifier_sha256':hashes['verifier'],'common_sha256':hashes['common'],'deep_verifier_sha256':hashes['deep'],'contract_sha256':hashes['contract'],'protocol_sha256':hashes['protocol'],'python_executable_sha256':hashes['python'],'openssl_executable_sha256':hashes['openssl'],'custody_root_digest_sha256':c.hb(str(c.root(home)).encode()),'private_descriptor_sha256':c.E['privdesc'],'public_descriptor_sha256':c.E['pubdesc'],'private_package_sha256':c.E['package'],'generation_marker_sha256':c.E['gmark'],'generation_record_sha256':c.E['grec'],'immutable_artifact_id':c.E['artifact_id'],'immutable_payload_tar_sha256':c.E['artifact_tar']}
 for k,e in expected.items():c.req(v.get(k)==e,'AUTH_'+k.upper()+'_MISMATCH')
 issued,expires=c.utc(v.get('issued_at'),'issued_at'),c.utc(v.get('expires_at'),'expires_at');c.req(expires-issued==timedelta(hours=2),'AUTH_INTERVAL_MUST_EQUAL_TWO_HOURS');t=now or datetime.now(timezone.utc);c.req(issued<=t<=expires,'AUTH_NOT_CURRENT');d=auth_digest(v);c.req(v.get('record_sha256')==d,'AUTH_RECORD_DIGEST_MISMATCH');p=c.marker(home,aid);c.req(not p.exists(),'AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED');return aid,p,d
def claim(p:Path,aid:str,d:str)->None:c.write_json(p,{'schema':'gh.h3.n2.stage2d9r-successor-private-content-binding-u1-consumption/1','authorization_id':aid,'status':'CLAIMED','record_sha256':d,'claimed_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'one_shot':True,'replay_permitted':False,'automatic_retry_permitted':False,'secret_values_included':False})
def hashes(openssl:Path)->dict[str,str]:
 here=Path(__file__).resolve(strict=True);return {'verifier':c.hf(here),'common':c.hf(Path(c.__file__).resolve(strict=True)),'deep':c.hf(Path(deep.__file__).resolve(strict=True)),'contract':c.hf(Path(contract.__file__).resolve(strict=True)),'protocol':c.hf(Path(protocol.__file__).resolve(strict=True)),'python':c.hf(Path(sys.executable).resolve(strict=True)),'openssl':c.hf(openssl)}
def execute(binding:dict[str,Any],auth:Path,home:Path,openssl:Path)->dict[str,Any]:
 h=hashes(openssl);v=json.loads(auth.read_text());aid,p,d=validate_auth(v,binding,home,h);metadata(binding,home,openssl);claim(p,aid,d)
 try:
  result=deep.verify(home,openssl);rd=c.ch(result);c.finish(p,'CONSUMED',rd,None);return {**result,'authorization_id':aid,'authorization_record_sha256':d,'result_sha256':rd,'authorization_consumed':True,'replay_permitted':False,'automatic_retry_permitted':False}
 except Exception as x:
  code=x.args[0] if isinstance(x,(c.BindingError,contract.ContractError,protocol.CommandError)) and x.args else type(x).__name__
  if p.exists():c.finish(p,'CONSUMED_FAILED',None,str(code))
  raise
def main()->int:
 a=argparse.ArgumentParser();a.add_argument('--review-binding',type=Path,required=True);a.add_argument('--probe-state',action='store_true');a.add_argument('--execute',action='store_true');a.add_argument('--authorization-record',type=Path);a.add_argument('--home',type=Path,default=Path.home());a.add_argument('--openssl',type=Path);x=a.parse_args()
 try:
  b=load_binding(x.review_binding.resolve(strict=True));o=openssl_path(x.openssl);home=x.home.expanduser().resolve(strict=True);c.req(x.probe_state^x.execute,'EXACTLY_ONE_OPERATION_REQUIRED')
  if x.probe_state:r=metadata(b,home,o);print('STAGE2D9R_SUCCESSOR_PRIVATE_CONTENT_BINDING_PROBE=PASS')
  else:c.req(x.authorization_record is not None,'AUTHORIZATION_RECORD_REQUIRED');r=execute(b,x.authorization_record.resolve(strict=True),home,o);print('STAGE2D9R_SUCCESSOR_PRIVATE_CONTENT_BINDING=PASS')
  print(json.dumps(r,sort_keys=True));return 0
 except Exception as z:
  code=z.args[0] if isinstance(z,(c.BindingError,contract.ContractError,protocol.CommandError)) and z.args else type(z).__name__;print('STAGE2D9R_SUCCESSOR_PRIVATE_CONTENT_BINDING=FAIL');print('FAILURE_CODE='+str(code))
  for k in ('PRIVATE_PATHS_INCLUDED','SECRET_VALUES_INCLUDED','NETWORK_OPERATION','BROKER_STARTED','BOARD_OPERATION','SERIAL_OPERATION','FLASH_OPERATION','PHYSICAL_NVS_OPERATION','PREPARE_EXECUTED','VERIFY_EXECUTED'):print(k+'=false')
  return 2
if __name__=='__main__':raise SystemExit(main())
