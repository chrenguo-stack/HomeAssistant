#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime,timedelta,timezone
import importlib.util,sys,tempfile,types,unittest
from pathlib import Path
class ContractError(RuntimeError):pass
class CommandError(RuntimeError):pass
contract=types.ModuleType('h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1');contract.__file__=__file__;contract.STAGE='H3/N2 Stage 2D-9R G3R successor';contract.RUN_SUFFIX='tlsvalid02';contract.HOST='stage2d9r.local';contract.PORT=8883;contract.MQTT_USERNAME='stage2d9r-test';contract.PUBLIC_SCHEMA='gh.h3.n2.stage2d9r-private-execution-material-successor-public/1';contract.REQUIRED_PRIVATE_FILES=('a',);contract.ContractError=ContractError;contract.verify_mosquitto_sha512_pbkdf2=lambda *a:True;contract.private_material_digest=lambda *a:'0'*64;contract.candidate_digest=lambda *a:'0'*64;contract.render_commands=lambda *a:('p\n','v\n','0'*64)
protocol=types.ModuleType('h3_n2_stage2d9r_prepare_command_protocol_20260723_v1');protocol.__file__=__file__;protocol.CommandError=CommandError;protocol.render_prepare=lambda *a:'p';protocol.render_verify=lambda *a:'v';protocol.parse_prepare=lambda *a:types.SimpleNamespace(candidate_digest='0'*64,authorization_digest='0'*64);protocol.parse_verify=lambda *a:types.SimpleNamespace(candidate_digest='0'*64)
sys.modules[contract.__name__]=contract;sys.modules[protocol.__name__]=protocol
base=Path(__file__).resolve().parent
def locate(name:str)->Path:
 for p in (base/name,base.parent.parent/'tools'/name,base.parent/'tools'/name):
  if p.is_file():return p
 return base/name
def load(name:str,path:Path):
 s=importlib.util.spec_from_file_location(name,path);assert s and s.loader;m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
c=load('h3_n2_stage2d9r_successor_private_content_binding_common_20260727_v1',locate('h3_n2_stage2d9r_successor_private_content_binding_common_20260727_v1.py'))
deep=types.ModuleType('h3_n2_stage2d9r_successor_private_content_binding_deep_20260727_v1');deep.__file__=__file__;deep.verify=lambda *a:{};sys.modules[deep.__name__]=deep
v=load('verifier',locate('h3_n2_stage2d9r_successor_private_content_binding_verifier_20260727_v1.py'))
class T(unittest.TestCase):
 def pub(self):
  x={'schema':contract.PUBLIC_SCHEMA,'stage':contract.STAGE,'state':'SUCCESSOR_EXECUTION_MATERIAL_FROZEN','source_sha':c.E['gsource'],'run_suffix':contract.RUN_SUFFIX,'broker_host':contract.HOST,'broker_port':contract.PORT,'broker_tls_server_name':contract.HOST,'mqtt_username':contract.MQTT_USERNAME,'private_values_included':False,'private_paths_included':False,'secret_values_included':False}
  for k,e in {'mqtt_password_sha256':'password','persistence_key_file_sha256':'persist_file','unlock_digest_sha256':'unlock','ca_pem_sha256':'ca','broker_certificate_der_sha256':'broker_der','broker_spki_sha256':'broker_spki','candidate_digest_sha256':'candidate','prepare_command_sha256':'prepare','verify_command_sha256':'verify','private_package_sha256':'package'}.items():x[k]=c.E[e]
  for k in c.FALSE:x[k]=False
  return x
 def test_binding_digest(self):self.assertEqual(v.binding_digest({'a':1,'review_binding_sha256':'x'}),c.ch({'a':1}))
 def test_auth_digest(self):self.assertEqual(v.auth_digest({'a':1,'record_sha256':'x'}),c.ch({'a':1}))
 def test_utc(self):self.assertEqual(c.utc('2026-07-27T00:00:00Z','x').tzinfo,timezone.utc)
 def test_utc_rejects(self):
  with self.assertRaises(c.BindingError):c.utc('bad','x')
 def test_public(self):c.public_descriptor(self.pub())
 def test_public_expansion(self):
  x=self.pub();x['prepare_authorized']=True
  with self.assertRaises(c.BindingError):c.public_descriptor(x)
 def fixture(self,home:Path):
  b={'source_sha':'1'*40,'review_binding_sha256':'2'*64};t=datetime(2026,7,27,tzinfo=timezone.utc);h={k:str(i)*64 for i,k in enumerate(('verifier','common','deep','contract','protocol','python','openssl'),3)}
  r={'schema':c.AUTH_SCHEMA,'stage':c.STAGE,'authorization_id':c.AUTH_PREFIX+'20260727-01','operation':c.AUTH_OPERATION,'authorized':True,'one_shot':True,'replay_permitted':False,'automatic_retry_permitted':False,'source_sha':b['source_sha'],'review_binding_sha256':b['review_binding_sha256'],'custody_root_digest_sha256':c.hb(str(c.root(home)).encode()),'private_descriptor_sha256':c.E['privdesc'],'public_descriptor_sha256':c.E['pubdesc'],'private_package_sha256':c.E['package'],'generation_marker_sha256':c.E['gmark'],'generation_record_sha256':c.E['grec'],'immutable_artifact_id':c.E['artifact_id'],'immutable_payload_tar_sha256':c.E['artifact_tar'],'issued_at':t.isoformat().replace('+00:00','Z'),'expires_at':(t+timedelta(hours=2)).isoformat().replace('+00:00','Z')}
  r.update(verifier_sha256=h['verifier'],common_sha256=h['common'],deep_verifier_sha256=h['deep'],contract_sha256=h['contract'],protocol_sha256=h['protocol'],python_executable_sha256=h['python'],openssl_executable_sha256=h['openssl'])
  r['record_sha256']=v.auth_digest(r);return b,h,r
 def test_auth_exact_window(self):
  with tempfile.TemporaryDirectory() as d:
   home=Path(d).resolve();b,h,r=self.fixture(home);aid,p,digest=v.validate_auth(r,b,home,h,datetime(2026,7,27,1,tzinfo=timezone.utc));self.assertEqual(aid,r['authorization_id']);self.assertFalse(p.exists());self.assertEqual(digest,r['record_sha256'])
 def test_auth_rejects_window(self):
  with tempfile.TemporaryDirectory() as d:
   home=Path(d).resolve();b,h,r=self.fixture(home);r['expires_at']='2026-07-27T01:59:59Z';r['record_sha256']=v.auth_digest(r)
   with self.assertRaises(c.BindingError):v.validate_auth(r,b,home,h,datetime(2026,7,27,1,tzinfo=timezone.utc))
if __name__=='__main__':unittest.main()
