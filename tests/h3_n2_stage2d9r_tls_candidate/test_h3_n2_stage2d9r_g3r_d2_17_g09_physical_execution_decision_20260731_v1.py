#!/usr/bin/env python3
from __future__ import annotations
import json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DEC=ROOT/'docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g09-physical-execution-decision-20260731-v1.json'
PENDING=ROOT/'docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g09-physical-execution-authorized-pending-20260731-v1.json'
DRIVER=ROOT/'tools/h3_n2_stage2d9r_g3r_d2_17_g09_physical_execution_decision_driver_20260731_v1.py'
ENTRY=ROOT/'tools/h3_n2_stage2d9r_g3r_d2_17_g09_physical_runtime_identity_adapter_entry_20260731_v1.py'
ADAPTER=ROOT/'tools/h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1.py'
def canon(v):
 import hashlib; return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def main():
 d=json.loads(DEC.read_text()); b=d.pop('decision_binding_sha256'); assert b=='fbf5119c858135a89c3c446c6a97ab692b65c1a51d79593d91d0c7be584b8449'==canon(d)
 p=json.loads(PENDING.read_text()); a=p.pop('authorized_pending_binding_sha256'); assert a=='50fbf12bdc8c6154deb3b6f205c603f85512910410d14f79e877f797bd636639'==canon(p)
 assert p['authorization_claimed'] is False and p['authorization_consumed'] is False
 assert d['authorization_state_namespace']=='G09_PHYSICAL_RUNTIME_LOCAL' and d['authorization_state_isolated_from_g07'] is True
 assert p['authorization_state_namespace']=='G09_PHYSICAL_RUNTIME_LOCAL' and p['authorization_state_isolated_from_g07'] is True
 assert d['g08_expired_disposition_binding_sha256']=='ad6dcc2ab884a358ae07d90ed157b27f5943757c85898a5440cf06f5b2c12795'
 assert d['g09_reauthorization_pending_binding_sha256']=='e504021fb44ae1dd3973582cb23b0b59c4d23339c3064fc7cf1c7e28756367c7'
 ex=Path(os.environ['D2_17_EXECUTION_ROOT']).resolve(); c=subprocess.run([os.sys.executable,'-B',str(DRIVER),'--self-test-execution-root',str(ex),'--self-test-adapter',str(ADAPTER),'--self-test-entry',str(ENTRY)],text=True,capture_output=True); print(c.stdout,end=''); print(c.stderr,end='',file=os.sys.stderr); assert c.returncode==0
 public='\n'.join(x.read_text() for x in (DEC,PENDING,DRIVER,ENTRY));
 for bad in ('/Users/','BEGIN PRIVATE KEY'): assert bad not in public
 return 0
if __name__=='__main__': raise SystemExit(main())
