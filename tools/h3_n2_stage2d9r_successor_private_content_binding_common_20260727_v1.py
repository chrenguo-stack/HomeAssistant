#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone
import hashlib,json,os,re,stat,subprocess
from pathlib import Path
from typing import Any
import h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1 as contract
import h3_n2_stage2d9r_prepare_command_protocol_20260723_v1 as protocol
STAGE=contract.STAGE
AUTH_SCHEMA="gh.h3.n2.stage2d9r-successor-private-content-binding-u1-authorization/1"
AUTH_OPERATION="VERIFY_SUCCESSOR_PRIVATE_CONTENT_BINDINGS_READ_ONLY"
AUTH_PREFIX="U1-H3N2-STAGE2D9R-SUCCESSOR-PRIVATE-CONTENT-BINDING-"
AUTH_REL=Path('.local/state/greenhouse-stage2d9r/authorizations')
ROOT_REL=Path('.local/state/greenhouse-stage2d9r/private-execution-material-tlsvalid02')
HEX64=re.compile(r'^[0-9a-f]{64}$')
E={
'gaid':'U1-H3N2-STAGE2D9R-PRIVATE-EXECUTION-MATERIAL-20260725-01','grec':'99d5f8cf5a0a12d921497ce04b7dc95161fc77ee79e79ddf50d6cb2535473817','gmark':'428231f9e0e6a26c39701427b3e32531e18d08b54e341736b1189a78a06848a5','gsource':'0cd9eeb5fd567d47a29bddee83159ac9570aa3dd','privdesc':'49236148741cccac301bbe45c900912e472e72ab8da8cb894645fb3916852fc8','package':'7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb','pubdesc':'7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6','password':'4fa67359f2ab36950652c28c88f5eff3f83a8c1c598d83100bf9871a23e33b9c','persist_file':'661a5cf28173d481ddb8bc4e239fb5aced6e67ec574a79c774f238dbb4d0b882','unlock':'727db669e17634b6d66fc1d8bd4f4d9e4e4e196401806c9b56c7eed6b8a7d9e9','ca':'9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096','broker_der':'4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9','broker_spki':'0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e','candidate':'a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2','prepare':'294df853b85fd86ae31ae05dc68b44fa3deac0cbffdbb8c24f62ca8175ef641f','verify':'53965a7dc1ec4265cc21eee11a03a22e0bc20ff6c8e3ffa56f42b4043da8c347','python':'4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a','openssl':'04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973','generator':'38f7609030fcbeb33b2000bc3db0af3179dac0ed993484f2b22d0990f7720abd','contract':'95c33d9d1cbb051e23621264a51c1b77bf674c0d403e2e813d1936ab9f9dbfb0','protocol':'2520c292151b240827083272673df82441fd68b4e022ab0320311866d2bd4f18','passwd_tool':'d6fdc23fa4bb09198bf74925207aa2b69b1455970e31fefc6157dfe4be2b07ee','artifact_id':8638796771,'artifact_source':'ac1d2a7a92323988c9cd946a3e018e4f1ba9463b','artifact_tar':'14e882f550ca92d14cf6776e518eb083b7344683b5534487bd28e95d93b29747','application':'a75e440c90aa5f050ac55086d1f1c614f113a7b66bd31ffc748fee95b9d26e1b','merged':'925ae87831a259d5a477fba9dde009b4d6a218e43735638521d4a10a38fe95bf','build':'742f663333837366a42da92b984a3b05c643f571'}
FALSE=('execution_authorized','board_operation_authorized','serial_operation_authorized','flash_operation_authorized','physical_nvs_operation_authorized','network_operation_authorized','broker_start_authorized','prepare_authorized','verify_authorized','activate_authorized','cleanup_authorized','production_operation_authorized')
class BindingError(RuntimeError):pass
def req(v:bool,c:str)->None:
 if not v:raise BindingError(c)
def hb(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def hf(p:Path)->str:return hb(p.read_bytes())
def cj(v:object)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def ch(v:object)->str:return hb(cj(v))
def mode(p:Path)->str:return f'{stat.S_IMODE(p.stat().st_mode):04o}'
def utc(v:object,n:str)->datetime:
 req(isinstance(v,str) and v.endswith('Z'),n.upper()+'_INVALID')
 try:r=datetime.fromisoformat(v[:-1]+'+00:00')
 except ValueError as x:raise BindingError(n.upper()+'_INVALID') from x
 return r.astimezone(timezone.utc)
def root(home:Path)->Path:return (home.resolve(strict=True)/ROOT_REL).resolve(strict=False)
def marker(home:Path,aid:str)->Path:return (home.resolve(strict=True)/AUTH_REL/(re.sub(r'[^A-Za-z0-9_.-]','_',aid)+'.consumed.json')).resolve(strict=False)
def exact_json(p:Path,d:str)->dict[str,Any]:
 req(p.is_file() and not p.is_symlink() and mode(p)=='0600','JSON_FILE_INVALID')
 b=p.read_bytes();req(hb(b)==d,'JSON_DIGEST_MISMATCH');v=json.loads(b);req(isinstance(v,dict),'JSON_OBJECT_REQUIRED');return v
def generation_marker(home:Path)->dict[str,Any]:
 v=exact_json(marker(home,E['gaid']),E['gmark'])
 req(v.get('authorization_id')==E['gaid'] and v.get('status')=='CONSUMED','GENERATION_MARKER_STATE_MISMATCH')
 req(v.get('record_sha256')==E['grec'] and v.get('public_descriptor_sha256')==E['pubdesc'],'GENERATION_MARKER_BINDING_MISMATCH')
 req(v.get('one_shot') is True and v.get('replay_permitted') is False and v.get('automatic_retry_permitted') is False and v.get('secret_values_included') is False,'GENERATION_MARKER_FLAGS_MISMATCH');return v
def public_descriptor(v:dict[str,Any])->None:
 req(v.get('schema')==contract.PUBLIC_SCHEMA and v.get('stage')==STAGE and v.get('state')=='SUCCESSOR_EXECUTION_MATERIAL_FROZEN','PUBLIC_DESCRIPTOR_IDENTITY_MISMATCH')
 req(v.get('source_sha')==E['gsource'] and v.get('run_suffix')==contract.RUN_SUFFIX,'PUBLIC_DESCRIPTOR_SOURCE_MISMATCH')
 req(v.get('broker_host')==contract.HOST and v.get('broker_port')==contract.PORT and v.get('broker_tls_server_name')==contract.HOST and v.get('mqtt_username')==contract.MQTT_USERNAME,'PUBLIC_DESCRIPTOR_BROKER_MISMATCH')
 keys={'mqtt_password_sha256':'password','persistence_key_file_sha256':'persist_file','unlock_digest_sha256':'unlock','ca_pem_sha256':'ca','broker_certificate_der_sha256':'broker_der','broker_spki_sha256':'broker_spki','candidate_digest_sha256':'candidate','prepare_command_sha256':'prepare','verify_command_sha256':'verify','private_package_sha256':'package'}
 for k,e in keys.items():req(v.get(k)==E[e],'PUBLIC_'+k.upper()+'_MISMATCH')
 for k in ('private_values_included','private_paths_included','secret_values_included',*FALSE):req(v.get(k) is False,'PUBLIC_'+k.upper()+'_MISMATCH')
def run_ssl(o:Path,a:list[str],data:bytes|None=None)->bytes:
 p=subprocess.run([str(o),*a],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,env={'PATH':str(o.parent),'LC_ALL':'C'});req(p.returncode==0,'OFFLINE_CRYPTOGRAPHIC_CHECK_FAILED');return p.stdout
def spki_cert(o:Path,p:Path)->bytes:return run_ssl(o,['pkey','-pubin','-outform','DER'],run_ssl(o,['x509','-in',str(p),'-pubkey','-noout']))
def spki_key(o:Path,p:Path)->bytes:return run_ssl(o,['pkey','-in',str(p),'-pubout','-outform','DER'])
def write_json(p:Path,v:dict[str,Any],replace:bool=False)->None:
 p.parent.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(p.parent,0o700);req(mode(p.parent)=='0700','AUTH_DIRECTORY_MODE_MISMATCH');b=json.dumps(v,indent=2,sort_keys=True).encode()+b'\n'
 if replace:
  t=p.with_name(p.name+'.new');req(not t.exists(),'AUTH_TEMP_EXISTS');f=os.open(t,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(f,b);os.fsync(f);os.close(f);os.replace(t,p)
 else:
  flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|(getattr(os,'O_NOFOLLOW',0));f=os.open(p,flags,0o600);os.write(f,b);os.fsync(f);os.close(f)
 os.chmod(p,0o600);req(mode(p)=='0600','AUTH_MARKER_MODE_MISMATCH')
def finish(p:Path,status:str,result:str|None,code:str|None)->None:
 v=json.loads(p.read_text());v.update(status=status,consumed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),result_sha256=result,failure_code=code,secret_values_included=False);write_json(p,v,True)
