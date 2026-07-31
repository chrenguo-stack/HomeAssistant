#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,os,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DEC=ROOT/'docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g08-physical-execution-decision-20260731-v1.json'
PENDING=ROOT/'docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g08-physical-execution-authorized-pending-20260731-v1.json'
DRIVER=ROOT/'tools/h3_n2_stage2d9r_g3r_d2_17_g08_physical_execution_decision_driver_20260731_v1.py'
ENTRY=ROOT/'tools/h3_n2_stage2d9r_g3r_d2_17_g08_physical_runtime_identity_adapter_entry_20260731_v1.py'
ADAPTER=ROOT/'tools/h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1.py'
def canon(v):
 import hashlib; return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def main():
 d=json.loads(DEC.read_text()); b=d.pop('decision_binding_sha256'); assert b=='d83cf9a4195680f1a362eaa88be82f1f03af14797d032a43dc2d28bf75b8e194'==canon(d)
 p=json.loads(PENDING.read_text()); a=p.pop('authorized_pending_binding_sha256'); assert a=='17d7691bd1d3e67a08f4c1fbe88e7c1674d297139237ff6d4e665b1f1a465a60'==canon(p)
 assert p['authorization_claimed'] is False and p['authorization_consumed'] is False
 ex=Path(os.environ['D2_17_EXECUTION_ROOT']).resolve(); c=subprocess.run([os.sys.executable,'-B',str(DRIVER),'--self-test-execution-root',str(ex),'--self-test-adapter',str(ADAPTER),'--self-test-entry',str(ENTRY)],text=True,capture_output=True); print(c.stdout,end=''); print(c.stderr,end='',file=os.sys.stderr); assert c.returncode==0
 public='\n'.join(x.read_text() for x in (DEC,PENDING,DRIVER,ENTRY));
 for bad in ('/Users/','BEGIN PRIVATE KEY'): assert bad not in public
 return 0
if __name__=='__main__': raise SystemExit(main())
