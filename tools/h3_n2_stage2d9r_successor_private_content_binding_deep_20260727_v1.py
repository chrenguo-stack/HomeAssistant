#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
import h3_n2_stage2d9r_private_execution_material_successor_contract_20260725_v1 as contract
import h3_n2_stage2d9r_prepare_command_protocol_20260723_v1 as protocol
import h3_n2_stage2d9r_successor_private_content_binding_common_20260727_v1 as c

def secret(p:Path,code:str)->tuple[str,bytes]:
 c.req(p.is_file() and not p.is_symlink() and c.mode(p)=='0600',code+'_FILE_INVALID');b=p.read_bytes()
 try:v=b.decode('ascii').strip()
 except UnicodeDecodeError as x:raise c.BindingError(code+'_FORMAT_INVALID') from x
 c.req(c.HEX64.fullmatch(v) is not None and v!='0'*64,code+'_FORMAT_INVALID');return v,b

def config(root:Path)->str:
 return '\n'.join(('per_listener_settings true',f'listener {contract.PORT} 127.0.0.1','protocol mqtt','allow_anonymous false',f'password_file {root/"mosquitto.password"}',f'acl_file {root/"mosquitto.stage2d9r.acl"}',f'cafile {root/"root-ca.cert.pem"}',f'certfile {root/"broker.cert.pem"}',f'keyfile {root/"broker.key.pem"}','require_certificate false','tls_version tlsv1.2','persistence false','connection_messages true','log_type all',''))

def verify(home:Path,openssl:Path)->dict[str,Any]:
 r=c.root(home);priv=c.exact_json(r/'private-custody-descriptor.json',c.E['privdesc']);pub=c.exact_json(r/'public-descriptor.redacted.json',c.E['pubdesc']);c.public_descriptor(pub);c.generation_marker(home)
 mats=priv.get('materials');c.req(isinstance(mats,dict) and set(mats)==set(contract.REQUIRED_PRIVATE_FILES),'PRIVATE_INVENTORY_MISMATCH');norm={}
 for n in contract.REQUIRED_PRIVATE_FILES:
  m=mats.get(n);p=r/n;c.req(isinstance(m,dict) and p.is_file() and not p.is_symlink() and c.mode(p)=='0600','PRIVATE_FILE_INVALID');d=c.hf(p);c.req(m=={'relative_path':n,'mode':'0600','sha256':d},'PRIVATE_METADATA_BINDING_MISMATCH');norm[n]=dict(m)
 package=contract.private_material_digest(norm);c.req(package==c.E['package'] and priv.get('private_package_sha256')==package,'PRIVATE_PACKAGE_MISMATCH')
 password,praw=secret(r/'mqtt-password.hex','MQTT_PASSWORD');key,kraw=secret(r/'persistence-key.hex','PERSISTENCE_KEY');unlock,uraw=secret(r/'unlock-token.hex','UNLOCK_TOKEN')
 c.req(c.hb(password.encode())==c.E['password'],'PASSWORD_DIGEST_MISMATCH');c.req(c.hb(kraw)==c.E['persist_file'],'PERSISTENCE_FILE_DIGEST_MISMATCH');unlock_digest=c.hb(bytes.fromhex(unlock));c.req(unlock_digest==c.E['unlock'],'UNLOCK_DIGEST_MISMATCH')
 c.req(contract.verify_mosquitto_sha512_pbkdf2(password,(r/'mosquitto.password').read_text('ascii').strip()),'PASSWORD_DATABASE_CROSS_BINDING_FAILED')
 root_key,root_cert,broker_key,broker_cert,chain=(r/'root-ca.key.pem',r/'root-ca.cert.pem',r/'broker.key.pem',r/'broker.cert.pem',r/'broker.fullchain.pem');ca=root_cert.read_text('ascii')
 c.req(c.hf(root_cert)==c.E['ca'],'CA_DIGEST_MISMATCH');der=c.run_ssl(openssl,['x509','-in',str(broker_cert),'-outform','DER']);c.req(c.hb(der)==c.E['broker_der'],'BROKER_DER_MISMATCH')
 c.req(c.spki_key(openssl,root_key)==c.spki_cert(openssl,root_cert),'ROOT_KEY_CERT_MISMATCH');bspki=c.spki_cert(openssl,broker_cert);c.req(c.spki_key(openssl,broker_key)==bspki and c.hb(bspki)==c.E['broker_spki'],'BROKER_KEY_CERT_MISMATCH')
 c.run_ssl(openssl,['verify','-CAfile',str(root_cert),'-verify_hostname',contract.HOST,str(broker_cert)]);c.req(chain.read_bytes()==broker_cert.read_bytes()+root_cert.read_bytes(),'FULLCHAIN_MISMATCH')
 candidate=contract.candidate_digest(password,ca);c.req(candidate==c.E['candidate'],'CANDIDATE_DIGEST_MISMATCH');prepare,verify_cmd,rendered=contract.render_commands(unlock,key,password,ca);c.req(rendered==candidate,'COMMAND_CANDIDATE_MISMATCH')
 c.req((r/'prepare-command.txt').read_bytes()==prepare.encode() and c.hb(prepare.encode())==c.E['prepare'],'PREPARE_COMMAND_MISMATCH');c.req((r/'verify-command.txt').read_bytes()==verify_cmd.encode() and c.hb(verify_cmd.encode())==c.E['verify'],'VERIFY_COMMAND_MISMATCH')
 c.req(protocol.render_prepare(contract.RUN_SUFFIX,unlock,key,password,ca)+'\n'==prepare,'PREPARE_RENDER_MISMATCH');c.req(protocol.render_verify(contract.RUN_SUFFIX,unlock,key,candidate)+'\n'==verify_cmd,'VERIFY_RENDER_MISMATCH');pp=protocol.parse_prepare(prepare,unlock_digest);pv=protocol.parse_verify(verify_cmd,unlock_digest);c.req(pp.candidate_digest==candidate and pp.authorization_digest==password and pv.candidate_digest==candidate,'COMMAND_PARSE_MISMATCH')
 c.req((r/'mosquitto.stage2d9r.conf').read_text()==config(r),'BROKER_CONFIG_MISMATCH');c.req((r/'mosquitto.stage2d9r.acl').read_text()=='user stage2d9r-test\ntopic readwrite gh-test/gh-test-run-tlsvalid02/node/#\n','BROKER_ACL_MISMATCH')
 c.req(priv.get('schema')=='gh.h3.n2.stage2d9r-private-execution-material-successor-custody/1' and priv.get('stage')==c.STAGE and priv.get('state')=='SUCCESSOR_EXECUTION_MATERIAL_FROZEN','PRIVATE_DESCRIPTOR_IDENTITY_MISMATCH')
 c.req(priv.get('source_sha')==c.E['gsource'] and priv.get('run_suffix')==contract.RUN_SUFFIX and priv.get('custody_root')==str(r) and priv.get('custody_root_mode')=='0700','PRIVATE_DESCRIPTOR_SOURCE_MISMATCH')
 for k,e in {'generator_sha256':'generator','contract_sha256':'contract','protocol_sha256':'protocol','python_executable_sha256':'python','openssl_executable_sha256':'openssl','mosquitto_passwd_executable_sha256':'passwd_tool'}.items():c.req(priv.get(k)==c.E[e],'PRIVATE_DESCRIPTOR_'+k.upper()+'_MISMATCH')
 c.req(priv.get('authorization')=={'authorization_id':c.E['gaid'],'record_sha256':c.E['grec'],'one_shot':True,'replay_permitted':False,'automatic_retry_permitted':False,'consumed':True},'PRIVATE_AUTHORIZATION_MISMATCH');proofs=priv.get('offline_proofs');c.req(isinstance(proofs,dict) and proofs and all(v is True for v in proofs.values()),'OFFLINE_PROOFS_INVALID')
 for k in ('private_values_included','raw_private_values_in_descriptor','board_operation_authorized','network_operation_authorized','broker_start_authorized','flash_operation_authorized','physical_nvs_operation_authorized','prepare_authorized','verify_authorized','activate_authorized','cleanup_authorized','production_operation_authorized'):c.req(priv.get(k) is False,'PRIVATE_FLAG_'+k.upper()+'_MISMATCH')
 password=key=unlock='0'*64;praw=kraw=uraw=b''
 return {'schema':'gh.h3.n2.stage2d9r-successor-private-content-binding-result/1','stage':c.STAGE,'status':'PASS','private_package_sha256':package,'private_descriptor_sha256':c.E['privdesc'],'public_descriptor_sha256':c.E['pubdesc'],'candidate_digest_sha256':candidate,'unlock_digest_sha256':unlock_digest,'ca_pem_sha256':c.E['ca'],'broker_certificate_der_sha256':c.E['broker_der'],'broker_spki_sha256':c.E['broker_spki'],'password_database_matches_preimage':True,'persistence_key_bound':True,'unlock_token_bound':True,'prepare_command_reconstructable':True,'verify_command_reconstructable':True,'certificate_chain_valid':True,'hostname_valid':True,'root_ca_private_key_matches_certificate':True,'broker_private_key_matches_certificate':True,'private_material_modes_valid':True,'generation_marker_record_cross_binding_valid':True,'private_values_included':False,'private_paths_included':False,'secret_values_included':False,'board_operation':False,'serial_operation':False,'flash_operation':False,'physical_nvs_operation':False,'network_operation':False,'broker_started':False,'prepare_executed':False,'verify_executed':False,'activate_executed':False,'cleanup_executed':False,'production_operation':False}
