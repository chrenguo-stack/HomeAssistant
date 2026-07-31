#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def load(rel):return json.loads((ROOT/rel).read_text(encoding="utf-8"))
def sha(rel):return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
def main():
 d=load("docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g11-physical-execution-decision-20260731-v1.json");x=dict(d);b=x.pop("decision_binding_sha256");assert canonical(x)==b=='13afe6dcd3e1a8e76768dfc4e54a4405f2363def719fc538e95816adcc59d6a3'
 a=load("docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g11-physical-execution-authorized-pending-20260731-v1.json");x=dict(a);b=x.pop("authorized_pending_binding_sha256");assert canonical(x)==b=='5fe50a9f721d11658d2b2469c4c43629c8038c65498c59a0ebcc6960f6604346'
 assert d["runtime_entry_sha256"]==sha("tools/h3_n2_stage2d9r_g3r_d2_17_g11_physical_runtime_adapter_entry_20260731_v1.py")
 assert d["decision_driver_sha256"]==sha("tools/h3_n2_stage2d9r_g3r_d2_17_g11_physical_execution_decision_driver_20260731_v1.py")
 assert d["decision_launcher_sha256"]==sha("tools/run_h3_n2_stage2d9r_g3r_d2_17_g11_physical_execution_decision_20260731_v1.sh")
 assert d["decision_marker_finalizer_sha256"]==sha("tools/h3_n2_stage2d9r_g3r_d2_17_g11_physical_decision_marker_finalizer_20260731_v1.py")
 assert a["authorization_claimed"] is False and a["authorization_consumed"] is False
 if len(sys.argv)==6:
  cmd=[sys.executable,"-B",str(ROOT/"tools/h3_n2_stage2d9r_g3r_d2_17_g11_physical_execution_decision_driver_20260731_v1.py"),"--self-test-execution-root",sys.argv[1],"--self-test-request",sys.argv[2],"--self-test-identity-adapter",sys.argv[3],"--self-test-marker-adapter",sys.argv[4],"--self-test-entry",sys.argv[5]]
  cp=subprocess.run(cmd,text=True,capture_output=True,check=False);print(cp.stdout,end="");print(cp.stderr,end="",file=sys.stderr);assert cp.returncode==0
 print(json.dumps({"status":"PASS","decision_binding_sha256":'13afe6dcd3e1a8e76768dfc4e54a4405f2363def719fc538e95816adcc59d6a3',"authorized_pending_binding_sha256":'5fe50a9f721d11658d2b2469c4c43629c8038c65498c59a0ebcc6960f6604346',"physical_operation":False},sort_keys=True))
if __name__=="__main__":main()
