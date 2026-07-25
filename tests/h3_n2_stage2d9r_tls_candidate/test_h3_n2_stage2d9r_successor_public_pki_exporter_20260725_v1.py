#!/usr/bin/env python3
from datetime import datetime,timedelta,timezone
import hashlib,importlib.util,json,shutil,subprocess,tempfile,unittest,zipfile
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'tools'/'h3_n2_stage2d9r_successor_public_pki_exporter_20260725_v1.py'; S=importlib.util.spec_from_file_location('m',P); M=importlib.util.module_from_spec(S); S.loader.exec_module(M)
def desc(**x):
 v={'schema':'gh.h3.n2.stage2d9r-private-execution-material-successor-public/1','stage':M.STAGE,'state':'SUCCESSOR_EXECUTION_MATERIAL_FROZEN','run_suffix':M.RUN,'broker_host':M.HOST,'broker_port':8883,'broker_tls_server_name':M.HOST,'candidate_digest_sha256':M.CAND,'ca_pem_sha256':M.CA_SHA,'broker_certificate_der_sha256':M.LEAF_DER,'broker_spki_sha256':M.LEAF_SPKI}
 for k in ('execution_authorized','board_operation_authorized','network_operation_authorized','private_values_included','private_paths_included','secret_values_included'):v[k]=False
 v.update(x);return v
def db(v=None):return (json.dumps(v or desc(),indent=2,sort_keys=True)+'\n').encode()
class T(unittest.TestCase):
 def test_descriptor_and_forbidden(self):
  d=db(); old=M.DESC_SHA;M.DESC_SHA=hashlib.sha256(d).hexdigest()
  try:self.assertEqual(M.descriptor_ok(d)['candidate_digest_sha256'],M.CAND)
  finally:M.DESC_SHA=old
  d=db(desc(mqtt_password='x'));old=M.DESC_SHA;M.DESC_SHA=hashlib.sha256(d).hexdigest()
  try:
   with self.assertRaisesRegex(M.E,'DESCRIPTOR_FORBIDDEN_KEY'):M.descriptor_ok(d)
  finally:M.DESC_SHA=old
 def test_zip_reproducible(self):
  z=M.dz({'b':b'b','a':b'a'});self.assertEqual(z,M.dz({'a':b'a','b':b'b'}))
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x.zip';p.write_bytes(z)
   with zipfile.ZipFile(p) as q:self.assertEqual(q.namelist(),['a','b']);self.assertTrue(all(((i.external_attr>>16)&0o777)==0o600 for i in q.infolist()))
 def test_auth_interval(self):
  with tempfile.TemporaryDirectory() as t:
   h=Path(t);(h/'Downloads').mkdir();now=datetime.now(timezone.utc);r={'schema':M.SCHEMA,'stage':M.STAGE,'operation':M.OP,'authorized':True,'one_shot':True,'replay_permitted':False,'automatic_retry_permitted':False,'source_sha':'a'*40,'generation_marker_sha256':M.GEN_MARKER,'descriptor_export_marker_sha256':M.DESC_MARKER,'descriptor_export_zip_sha256':M.DESC_ZIP,'public_descriptor_sha256':M.DESC_SHA,'exporter_sha256':'b'*64,'python_executable_sha256':'c'*64,'openssl_executable_sha256':'d'*64,'output_target_digest_sha256':M.hb(str(M.out(h)).encode()),'output_target_exists':False,'authorization_id':M.PREFIX+'T','issued_at':(now-timedelta(minutes=1)).isoformat().replace('+00:00','Z'),'expires_at':(now+timedelta(minutes=59)).isoformat().replace('+00:00','Z')};r['record_sha256']=M.recsha(r)
   with self.assertRaisesRegex(M.E,'AUTH_INTERVAL_INVALID'):M.auth_ok(r,'a'*40,'b'*64,'c'*64,'d'*64,h,now)
 def test_certificate_chain(self):
  o=Path(shutil.which('openssl') or '');self.assertTrue(o.is_file())
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);ca=r/'ca.pem';cak=r/'ca.key';leaf=r/'leaf.pem';leafk=r/'leaf.key';csr=r/'leaf.csr';ext=r/'ext';fc=r/'fc.pem'
   subprocess.run([str(o),'req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(cak),'-out',str(ca),'-days','2','-subj','/CN=CA','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   subprocess.run([str(o),'req','-newkey','rsa:2048','-nodes','-keyout',str(leafk),'-out',str(csr),'-subj','/CN=stage2d9r.local','-addext','subjectAltName=DNS:stage2d9r.local'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   ext.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:stage2d9r.local\n')
   subprocess.run([str(o),'x509','-req','-in',str(csr),'-CA',str(ca),'-CAkey',str(cak),'-CAcreateserial','-out',str(leaf),'-days','2','-extfile',str(ext)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   fc.write_bytes(leaf.read_bytes()+ca.read_bytes());[p.chmod(0o600) for p in (ca,leaf,fc)]
   der=M.openssl(o,'x509','-in',str(leaf),'-outform','DER');pub=M.openssl(o,'x509','-in',str(leaf),'-pubkey','-noout');spki=M.openssl(o,'pkey','-pubin','-outform','DER',input=pub)
   old=(M.CA_SHA,M.LEAF_DER,M.LEAF_SPKI,M.DESC_SHA);M.CA_SHA=hashlib.sha256(ca.read_bytes()).hexdigest();M.LEAF_DER=hashlib.sha256(der).hexdigest();M.LEAF_SPKI=hashlib.sha256(spki).hexdigest();d=db(desc(ca_pem_sha256=M.CA_SHA,broker_certificate_der_sha256=M.LEAF_DER,broker_spki_sha256=M.LEAF_SPKI));M.DESC_SHA=hashlib.sha256(d).hexdigest()
   home=r/'home';root=home/M.ROOT;root.mkdir(parents=True);[(root/n).write_bytes(b) for n,b in [('root-ca.cert.pem',ca.read_bytes()),('broker.cert.pem',leaf.read_bytes()),('broker.fullchain.pem',fc.read_bytes()),('public-descriptor.redacted.json',d)]];[(root/n).chmod(0o600) for n in ('root-ca.cert.pem','broker.cert.pem','broker.fullchain.pem','public-descriptor.redacted.json')]
   a=home/M.AUTHS;a.mkdir(parents=True);(a/(M.GEN_ID+'.consumed.json')).write_text('x');(a/(M.DESC_ID+'.consumed.json')).write_text('y')
   try:
    M.GEN_MARKER=M.hf(a/(M.GEN_ID+'.consumed.json'));M.DESC_MARKER=M.hf(a/(M.DESC_ID+'.consumed.json'));s,e=M.public_inputs(home,o);self.assertTrue(s['certificate_chain_valid']);self.assertEqual(len(e),4)
   finally:M.CA_SHA,M.LEAF_DER,M.LEAF_SPKI,M.DESC_SHA=old
 def test_no_secret_reads(self):
  s=P.read_text()
  for x in ('socket.socket','serial.Serial','esptool','mqtt-password.hex','persistence-key.hex','unlock-token.hex','root-ca.key.pem','broker.key.pem','mosquitto.password','prepare-command.txt','verify-command.txt','private-custody-descriptor.json'):self.assertNotIn(x,s)
if __name__=='__main__':unittest.main()
