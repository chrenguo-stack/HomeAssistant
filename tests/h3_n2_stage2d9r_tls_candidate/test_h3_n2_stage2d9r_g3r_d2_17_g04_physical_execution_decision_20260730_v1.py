from __future__ import annotations
import hashlib,json,os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DRIVER=ROOT/"tools/h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.py"
DECISION=ROOT/"docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g04-physical-execution-20260730-v1.json"
PENDING=ROOT/"docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g04-physical-execution-authorized-pending-20260730-v1.json"
LAUNCHER=ROOT/"tools/run_h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_20260730_v1.sh"
class TestG04PhysicalDecision(unittest.TestCase):
    def test_bindings(self):
        value=json.loads(DECISION.read_text())
        self.assertEqual(value["decision_id"],"D1-H3N2-STAGE2D9R-G3R-D2-17-G04-PHYSICAL-EXECUTION-20260730-01")
        self.assertEqual(value["base_head_sha"],"e58b934c7e00125bf7d7c5a75f6ee338dd5dbdd7")
        self.assertEqual(value["decision_driver_sha256"],hashlib.sha256(DRIVER.read_bytes()).hexdigest())
        self.assertEqual(value["decision_launcher_sha256"],hashlib.sha256(LAUNCHER.read_bytes()).hexdigest())
        self.assertEqual(value["terminal_record_digest_semantics"],"CANONICAL_JSON_WITH_TERMINAL_RECORD_SHA256_REMOVED")
        self.assertFalse(value["replay_permitted"])
        p=json.loads(PENDING.read_text()); self.assertTrue(p["authorization_created"]); self.assertFalse(p["authorization_claimed"]); self.assertFalse(p["authorization_consumed"])
    def test_semantic_terminal_code(self):
        text=DRIVER.read_text(); self.assertIn("TERMINAL_RECORD_SEMANTIC_DIGEST_DRIFT",text); self.assertNotIn("TERMINAL_FILE_DIGEST_DRIFT",text); self.assertNotIn("/Users/",text)
    def test_host_only_self_test(self):
        execution=Path(os.environ["D2_17_G04_EXECUTION_ROOT"]).resolve()
        cp=subprocess.run([sys.executable,"-B",str(DRIVER),"--self-test-execution-root",str(execution)],text=True,capture_output=True,check=False,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        value=json.loads(cp.stdout.strip().splitlines()[-1]); self.assertEqual(value["status"],"PASS"); self.assertTrue(value["terminal_formatting_independent"]); self.assertTrue(value["terminal_semantic_tamper_rejected"]); self.assertFalse(value["authorization_claimed"]); self.assertFalse(value["board_operation"])
    def test_launcher(self):
        text=LAUNCHER.read_text(); self.assertIn('if [ "$#" -ne 0 ]',text); self.assertIn('/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11',text)
if __name__=='__main__': unittest.main()
