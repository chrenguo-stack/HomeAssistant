#!/usr/bin/env python3
"""One-shot, offline export of Stage2D9R successor public certificates only."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, stat, subprocess, sys, tempfile, zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA="gh.h3.n2.stage2d9r-successor-public-pki-export-u1-authorization/1"
OP="EXPORT_SUCCESSOR_PUBLIC_PKI"
PREFIX="U1-H3N2-STAGE2D9R-PUBLIC-PKI-EXPORT-"
MARKER_SCHEMA="gh.h3.n2.stage2d9r-successor-public-pki-export-u1-consumption/1"
STAGE="H3/N2 Stage 2D-9R G3R successor"; HOST="stage2d9r.local"; RUN="tlsvalid02"
GEN_ID="U1-H3N2-STAGE2D9R-PRIVATE-EXECUTION-MATERIAL-20260725-01"
GEN_MARKER="428231f9e0e6a26c39701427b3e32531e18d08b54e341736b1189a78a06848a5"
DESC_ID="U1-H3N2-STAGE2D9R-PUBLIC-DESCRIPTOR-EXPORT-20260725-01"
DESC_MARKER="a0c6ded9e371764a702b64fad58bd990b27808bae4467015116f9b189c8deceb"
DESC_ZIP="77fcded756d3914964138909ca2b51c2a20c60be76eed758049ef6c84ce4d8d1"
DESC_SHA="7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6"
CAND="a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
CA_SHA="9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096"
LEAF_DER="4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9"
LEAF_SPKI="0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e"
ROOT=Path('.local/state/greenhouse-stage2d9r/private-execution-material-tlsvalid02')
AUTHS=Path('.local/state/greenhouse-stage2d9r/authorizations')
OUT="Stage2D9R_G3R_Successor_Public_PKI_Export_U1_01_20260725.zip"
HEX40=re.compile(r'^[0-9a-f]{40}$'); PEM=re.compile(rb'-----BEGIN CERTIFICATE-----\r?\n.*?-----END CERTIFICATE-----\r?\n?',re.S)

class E(RuntimeError): pass
def req(x,c):
    if not x: raise E(c)
def hb(b): return hashlib.sha256(b).hexdigest()
def hf(p): return hb(p.read_bytes())
def canon(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def mode(p): return f'{stat.S_IMODE(p.stat().st_mode):04o}'
def homepath(h,r): return (h.resolve(strict=True)/r).resolve(strict=False)
def mark(h,i): return homepath(h,AUTHS/(re.sub(r'[^A-Za-z0-9_.-]','_',i)+'.consumed.json'))
def out(h): return homepath(h,Path('Downloads')/OUT)
def recsha(r):
    x=dict(r); x.pop('record_sha256',None); return hb(canon(x))
def utc(v,n):
    req(isinstance(v,str) and v.endswith('Z'),n+'_INVALID')
    try: d=datetime.fromisoformat(v[:-1]+'+00:00')
    except ValueError as e: raise E(n+'_INVALID') from e
    return d.astimezone(timezone.utc)
def write(p,b):
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|(getattr(os,'O_NOFOLLOW',0))
    fd=os.open(p,flags,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False) as f: f.write(b); f.flush(); os.fsync(f.fileno())
    finally: os.close(fd)
    os.chmod(p,0o600); req(mode(p)=='0600','MODE_MISMATCH')
def replace(p,b):
    q=p.with_name(p.name+'.new'); req(not q.exists(),'TEMP_EXISTS'); write(q,b); os.replace(q,p); os.chmod(p,0o600)
def openssl(exe,*a,input=None):
    r=subprocess.run([str(exe),*a],input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,env={'PATH':str(exe.parent),'LC_ALL':'C'})
    req(r.returncode==0,'OPENSSL_FAILED'); return r.stdout
def blocks(b): return [x.replace(b'\r\n',b'\n').rstrip(b'\n')+b'\n' for x in PEM.findall(b)]
def dz(entries):
    with tempfile.TemporaryFile() as f:
        with zipfile.ZipFile(f,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for n in sorted(entries):
                i=zipfile.ZipInfo(n,(1980,1,1,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED; i.external_attr=0o600<<16; i.create_system=3; z.writestr(i,entries[n])
        f.seek(0); return f.read()

def marker_ok(p,sha): req(p.is_file() and not p.is_symlink(),'MARKER_MISSING'); req(hf(p)==sha,'MARKER_SHA_MISMATCH')
def descriptor_ok(b):
    req(hb(b)==DESC_SHA,'DESCRIPTOR_SHA_MISMATCH')
    try: v=json.loads(b)
    except Exception as e: raise E('DESCRIPTOR_JSON_INVALID') from e
    for k,x in {'schema':'gh.h3.n2.stage2d9r-private-execution-material-successor-public/1','stage':STAGE,'state':'SUCCESSOR_EXECUTION_MATERIAL_FROZEN','run_suffix':RUN,'broker_host':HOST,'broker_port':8883,'broker_tls_server_name':HOST,'candidate_digest_sha256':CAND,'ca_pem_sha256':CA_SHA,'broker_certificate_der_sha256':LEAF_DER,'broker_spki_sha256':LEAF_SPKI}.items(): req(v.get(k)==x,'DESCRIPTOR_'+k.upper()+'_MISMATCH')
    for k,x in v.items():
        if k.endswith('_authorized') or k in ('private_values_included','private_paths_included','secret_values_included'): req(x is False,'DESCRIPTOR_AUTHORIZATION_MISMATCH')
    req(not {'mqtt_password','persistence_key','unlock_token','private_key','password_database','prepare_command','verify_command','custody_root','private_path'}.intersection(v),'DESCRIPTOR_FORBIDDEN_KEY')
    return v

def auth_ok(r,source,es,ps,os_,h,now):
    for k,x in {'schema':SCHEMA,'stage':STAGE,'operation':OP,'authorized':True,'one_shot':True,'replay_permitted':False,'automatic_retry_permitted':False,'source_sha':source,'generation_marker_sha256':GEN_MARKER,'descriptor_export_marker_sha256':DESC_MARKER,'descriptor_export_zip_sha256':DESC_ZIP,'public_descriptor_sha256':DESC_SHA,'exporter_sha256':es,'python_executable_sha256':ps,'openssl_executable_sha256':os_,'output_target_digest_sha256':hb(str(out(h)).encode()),'output_target_exists':False}.items(): req(r.get(k)==x,'AUTH_'+k.upper()+'_MISMATCH')
    aid=r.get('authorization_id'); req(isinstance(aid,str) and aid.startswith(PREFIX),'AUTH_ID_INVALID')
    a,b=utc(r.get('issued_at'),'ISSUED_AT'),utc(r.get('expires_at'),'EXPIRES_AT'); req(b-a==timedelta(hours=2),'AUTH_INTERVAL_INVALID'); req(a<=now<=b,'AUTH_NOT_CURRENT'); req(r.get('record_sha256')==recsha(r),'AUTH_RECORD_SHA_MISMATCH')
    m=mark(h,aid); o=out(h); req(not m.exists(),'AUTH_ALREADY_USED'); req(not o.exists(),'OUTPUT_EXISTS'); req(o.parent.is_dir(),'OUTPUT_DIR_MISSING'); return aid,m,o

def claim(m,aid,rs):
    m.parent.mkdir(parents=True,exist_ok=True,mode=0o700); os.chmod(m.parent,0o700)
    write(m,(json.dumps({'schema':MARKER_SCHEMA,'authorization_id':aid,'status':'CLAIMED','record_sha256':rs,'claimed_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'one_shot':True,'replay_permitted':False,'automatic_retry_permitted':False,'secret_values_included':False},indent=2,sort_keys=True)+'\n').encode())
def finish(m,status,z=None,code=None):
    v=json.loads(m.read_text()); v.update(status=status,consumed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),export_zip_sha256=z,failure_code=code); replace(m,(json.dumps(v,indent=2,sort_keys=True)+'\n').encode())

def public_inputs(h,exe):
    marker_ok(mark(h,GEN_ID),GEN_MARKER); marker_ok(mark(h,DESC_ID),DESC_MARKER)
    r=homepath(h,ROOT); paths={n:r/n for n in ('root-ca.cert.pem','broker.cert.pem','broker.fullchain.pem','public-descriptor.redacted.json')}
    for p in paths.values(): req(p.is_file() and not p.is_symlink(),'PUBLIC_FILE_MISSING'); req(mode(p)=='0600','PUBLIC_FILE_MODE')
    d=paths['public-descriptor.redacted.json'].read_bytes(); descriptor_ok(d)
    ca=paths['root-ca.cert.pem'].read_bytes(); leaf=paths['broker.cert.pem'].read_bytes(); chain=paths['broker.fullchain.pem'].read_bytes(); req(hb(ca)==CA_SHA,'CA_SHA_MISMATCH')
    der=openssl(exe,'x509','-in',str(paths['broker.cert.pem']),'-outform','DER'); pub=openssl(exe,'x509','-in',str(paths['broker.cert.pem']),'-pubkey','-noout'); spki=openssl(exe,'pkey','-pubin','-outform','DER',input=pub)
    req(hb(der)==LEAF_DER,'LEAF_DER_MISMATCH'); req(hb(spki)==LEAF_SPKI,'LEAF_SPKI_MISMATCH'); openssl(exe,'verify','-CAfile',str(paths['root-ca.cert.pem']),'-purpose','sslserver','-verify_hostname',HOST,str(paths['broker.cert.pem']))
    cb,cc=blocks(leaf),blocks(ca); fc=blocks(chain); req(len(cb)==len(cc)==1 and len(fc)==2,'FULLCHAIN_COUNT'); req(fc[0]==cb[0] and fc[1]==cc[0],'FULLCHAIN_ORDER')
    s={'ca_pem_sha256':hb(ca),'ca_der_sha256':hb(openssl(exe,'x509','-in',str(paths['root-ca.cert.pem']),'-outform','DER')),'broker_pem_sha256':hb(leaf),'broker_der_sha256':hb(der),'broker_spki_sha256':hb(spki),'broker_fullchain_sha256':hb(chain),'public_descriptor_sha256':hb(d),'candidate_digest_sha256':CAND,'certificate_chain_valid':True,'broker_hostname_match':True}
    return s,{'root-ca.cert.pem':ca,'broker.cert.pem':leaf,'broker.fullchain.pem':chain,'public-descriptor.redacted.json':d}

def probe(h,me,exe):
    r=homepath(h,ROOT); o=out(h)
    return {'schema':'gh.h3.n2.stage2d9r-successor-public-pki-export-probe/1','stage':STAGE,'exporter_sha256':hf(me),'python_executable_sha256':hf(Path(sys.executable).resolve()),'openssl_executable_sha256':hf(exe),'generation_marker_sha256':hf(mark(h,GEN_ID)) if mark(h,GEN_ID).is_file() else None,'descriptor_export_marker_sha256':hf(mark(h,DESC_ID)) if mark(h,DESC_ID).is_file() else None,'public_root_exists':r.is_dir(),'root_ca_exists':(r/'root-ca.cert.pem').is_file(),'broker_certificate_exists':(r/'broker.cert.pem').is_file(),'broker_fullchain_exists':(r/'broker.fullchain.pem').is_file(),'public_descriptor_exists':(r/'public-descriptor.redacted.json').is_file(),'output_target_digest_sha256':hb(str(o).encode()),'output_target_exists':o.exists(),'public_content_read':False,'private_content_read':False,'private_paths_included':False,'secret_values_included':False,'authorization_claimed':False,'authorization_consumed':False,'board_operation':False,'serial_operation':False,'flash_operation':False,'physical_nvs_operation':False,'network_operation':False,'broker_started':False,'prepare_executed':False,'verify_executed':False}
def execute(ap,source,h,me,exe):
    req(HEX40.fullmatch(source) is not None,'SOURCE_SHA_INVALID'); es,ps,os_=hf(me),hf(Path(sys.executable).resolve()),hf(exe)
    try:r=json.loads(ap.read_text())
    except Exception as e:raise E('AUTH_RECORD_INVALID') from e
    aid,m,o=auth_ok(r,source,es,ps,os_,h,datetime.now(timezone.utc)); s,e=public_inputs(h,exe); rs=recsha(r); claim(m,aid,rs)
    try:
        b={'schema':'gh.h3.n2.stage2d9r-successor-public-pki-export/1','stage':STAGE,'state':'PUBLIC_PKI_EXPORTED','authorization_id':aid,'authorization_record_sha256':rs,'exporter_source_sha':source,'generation_marker_sha256':GEN_MARKER,'descriptor_export_marker_sha256':DESC_MARKER,'descriptor_export_zip_sha256':DESC_ZIP,**s,'private_content_included':False,'private_paths_included':False,'secret_values_included':False,'authorization_record_included':False,'board_operation':False,'serial_operation':False,'flash_operation':False,'physical_nvs_operation':False,'network_operation':False,'broker_started':False,'prepare_executed':False,'verify_executed':False,'activate_executed':False,'cleanup_executed':False,'production_operation':False}
        bb=(json.dumps(b,indent=2,sort_keys=True)+'\n').encode(); bs=hb(bb); e['public-pki-export-binding.json']=bb; e['SHA256SUMS']=b''.join(f'{hb(e[n])}  {n}\n'.encode() for n in sorted(e)); z=dz(e); write(o,z); zs=hb(z); finish(m,'CONSUMED',zs,None)
        return {'schema':'gh.h3.n2.stage2d9r-successor-public-pki-export-result/1','status':'PASS','authorization_id':aid,'source_sha':source,'export_zip_sha256':zs,'export_binding_sha256':bs,**s,'authorization_consumed':True,'replay_permitted':False,'automatic_retry_permitted':False,'private_content_included':False,'private_paths_included':False,'secret_values_included':False,'board_operation':False,'serial_operation':False,'flash_operation':False,'physical_nvs_operation':False,'network_operation':False,'broker_started':False,'prepare_executed':False,'verify_executed':False}
    except Exception as x:
        c=x.args[0] if isinstance(x,E) and x.args else type(x).__name__; finish(m,'CONSUMED_FAILED',None,str(c)); raise

def main():
    p=argparse.ArgumentParser(); p.add_argument('--execute',action='store_true'); p.add_argument('--authorization',type=Path); p.add_argument('--source-sha'); p.add_argument('--openssl',type=Path); a=p.parse_args(); me=Path(__file__).resolve()
    try:
        h=Path.home().resolve(); exe=Path(a.openssl or shutil.which('openssl') or '').resolve(strict=True)
        if a.execute: req(a.authorization is not None,'AUTH_REQUIRED'); req(a.source_sha is not None,'SOURCE_REQUIRED'); v=execute(a.authorization,a.source_sha,h,me,exe); print('STAGE2D9R_SUCCESSOR_PUBLIC_PKI_EXPORT=PASS')
        else:v=probe(h,me,exe); print('STAGE2D9R_SUCCESSOR_PUBLIC_PKI_EXPORT_PROBE=PASS')
        print(json.dumps(v,sort_keys=True)); return 0
    except Exception as x:
        c=x.args[0] if isinstance(x,E) and x.args else type(x).__name__; print('STAGE2D9R_SUCCESSOR_PUBLIC_PKI_EXPORT=FAIL'); print('FAILURE_CODE='+str(c)); print('PRIVATE_PATHS_INCLUDED=false\nSECRET_VALUES_INCLUDED=false\nBOARD_OPERATION=false\nSERIAL_OPERATION=false\nFLASH_OPERATION=false\nPHYSICAL_NVS_OPERATION=false\nNETWORK_OPERATION=false\nBROKER_STARTED=false\nPREPARE_EXECUTED=false\nVERIFY_EXECUTED=false'); return 2
if __name__=='__main__': raise SystemExit(main())
