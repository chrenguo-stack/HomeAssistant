from __future__ import annotations
import copy, importlib.util, json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
TOOL=ROOT/"tools/h3_n2_stage2d9r_g3r_d2_17_g07_target_mac_static_check_acceptance_contract_20260731_v1.py"
SPEC=importlib.util.spec_from_file_location("g07_acceptance",TOOL)
assert SPEC and SPEC.loader
mod=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(mod)

class TestG07Acceptance(unittest.TestCase):
    def setUp(self):
        self.a=json.loads((ROOT/"docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g07-target-mac-static-check-pass-20260731-v1.json").read_text())
        self.p=json.loads((ROOT/"docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g07-physical-execution-pending-20260731-v1.json").read_text())
    def test_exact(self):
        mod.verify_acceptance(copy.deepcopy(self.a)); mod.verify_pending(copy.deepcopy(self.p))
    def test_claim_tamper(self):
        v=copy.deepcopy(self.a); v["authorization_claimed"]=True
        with self.assertRaises(mod.G07AcceptanceError): mod.verify_acceptance(v)
    def test_tool_substitution(self):
        v=copy.deepcopy(self.a); v["target_tool_sha256"]["python"]=v["target_tool_sha256"]["openssl"]
        v["acceptance_binding_sha256"]=mod.canonical_sha256({k:x for k,x in v.items() if k!="acceptance_binding_sha256"})
        with self.assertRaisesRegex(mod.G07AcceptanceError,"ACCEPTANCE_BINDING_DRIFT"): mod.verify_acceptance(v)
    def test_pending_not_authorized(self):
        v=copy.deepcopy(self.p); v["physical_execution_authorized"]=True
        v["physical_pending_binding_sha256"]=mod.canonical_sha256({k:x for k,x in v.items() if k!="physical_pending_binding_sha256"})
        with self.assertRaisesRegex(mod.G07AcceptanceError,"PHYSICAL_PENDING_BINDING_DRIFT"): mod.verify_pending(v)
    def test_exact_bindings(self):
        self.assertEqual(mod.canonical_sha256({k:v for k,v in self.a.items() if k!="acceptance_binding_sha256"}),"0f2e281c6ed0669ebc6629aefdaeab7e5382b84d17372b75cf2ab434eaac643e")
        self.assertEqual(mod.canonical_sha256({k:v for k,v in self.p.items() if k!="physical_pending_binding_sha256"}),"597edc89d0cda2dfa4effb0345560d974953b209dc4084728bea4e704f3f6691")
if __name__=="__main__": unittest.main()
