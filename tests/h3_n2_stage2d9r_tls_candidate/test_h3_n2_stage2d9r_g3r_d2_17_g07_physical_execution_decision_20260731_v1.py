from __future__ import annotations
import hashlib,json,os
from pathlib import Path
import subprocess,sys,unittest
ROOT=Path(__file__).resolve().parents[2]
DRIVER=ROOT/"tools/h3_n2_stage2d9r_g3r_d2_17_g07_physical_execution_decision_driver_20260731_v1.py"
DECISION=ROOT/"docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g07-physical-execution-20260731-v1.json"
PENDING=ROOT/"docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g07-physical-execution-authorized-pending-20260731-v1.json"
LAUNCHER=ROOT/"tools/run_h3_n2_stage2d9r_g3r_d2_17_g07_physical_execution_decision_20260731_v1.sh"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
class TestG07PhysicalDecision(unittest.TestCase):
 def test_bindings(self):
  v=json.loads(DECISION.read_text()); binding=v.pop("decision_binding_sha256"); self.assertEqual(binding,canonical(v)); self.assertEqual(v["decision_driver_sha256"],sha(DRIVER)); self.assertEqual(v["decision_driver_assembled_sha256"],sha(DRIVER)); self.assertEqual(v["decision_launcher_sha256"],sha(LAUNCHER)); self.assertNotEqual(v["private_source_sha"],v["acceptance_source_sha"]); self.assertEqual(v["permission_independent_shell"],"/bin/sh"); self.assertEqual(v["decision_id"],"D1-H3N2-STAGE2D9R-G3R-D2-17-G07-PHYSICAL-EXECUTION-20260731-01")
  p=json.loads(PENDING.read_text()); pb=p.pop("acceptance_binding_sha256"); self.assertEqual(pb,canonical(p)); self.assertEqual(p["decision_binding_sha256"],binding); self.assertTrue(p["authorization_created"]); self.assertFalse(p["authorization_claimed"]); self.assertFalse(p["authorization_consumed"])
 def test_no_local_paths_or_package_mutation(self):
  text=DRIVER.read_text(); self.assertNotIn("/Users/",text); self.assertNotIn("chmod(execution_root",text); self.assertIn("def two_hop(",text); self.assertIn("return [str(shell), str(inner), *arguments]",text)
 def test_real_host_only_two_hop_self_test(self):
  execution=Path(os.environ["D2_17_G07_EXECUTION_ROOT"]).resolve(); cp=subprocess.run([sys.executable,"-B",str(DRIVER),"--self-test-execution-root",str(execution)],text=True,capture_output=True,check=False,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"}); self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr); v=json.loads(cp.stdout.strip().splitlines()[-1]); self.assertEqual(v["status"],"PASS"); self.assertTrue(v["permission_independent_two_hop_handoff"]); self.assertTrue(v["outer_mode_preserved"]); self.assertTrue(v["inner_mode_preserved"]); self.assertFalse(v["authorization_claimed"]); self.assertFalse(v["board_operation"])
 def test_launcher(self):
  t=LAUNCHER.read_text(); self.assertIn('if [ "$#" -ne 0 ]',t); self.assertIn('/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11',t)
if __name__=="__main__": unittest.main()
