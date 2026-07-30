from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

CONTRACT = "h3_n2_stage2d9r_g3r_d2_15_contract_compatibility_install_preflight_repair_execution_binding_contract_20260730_v1"
WRAPPER = "h3_n2_stage2d9r_g3r_d2_15_contract_compatibility_install_preflight_repaired_physical_d2_wrapper_20260730_v1"
D2_14_CONTRACT = "h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repair_execution_binding_contract_20260730_v1"
D2_14_WRAPPER = "h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repaired_physical_d2_wrapper_20260730_v1"


class D215ContractCompatibilityTests(unittest.TestCase):
    def test_decision_and_compatibility_symbol(self) -> None:
        contract = importlib.import_module(CONTRACT)
        decision = ROOT / "docs/decisions" / contract.DECISION_FILE
        value = contract.validate_decision(decision)
        self.assertEqual(value["base_pr"], 213)
        self.assertTrue(callable(contract.canonical_package_digest))
        self.assertEqual(contract.D2_14_RETURN_CODE, 1)
        self.assertFalse(contract.D2_14_RESULT_FILE_PRESENT)

    def test_d2_14_missing_symbol_reproduces_host_install_failure(self) -> None:
        script = f"""
import importlib
old_contract=importlib.import_module({D2_14_CONTRACT!r})
old_wrapper=importlib.import_module({D2_14_WRAPPER!r})
assert not hasattr(old_contract, 'canonical_package_digest')
old_wrapper.contract=old_contract
old_wrapper.bind_predecessor()
d2_11=old_wrapper.predecessor.predecessor.upstream
d2_11.install()
"""
        run = subprocess.run(
            [sys.executable, "-B", "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
        self.assertEqual(run.returncode, 1)
        self.assertEqual(run.stdout, "")
        self.assertIn("AttributeError", run.stderr)
        self.assertIn("canonical_package_digest", run.stderr)

    def test_source_status_is_public_and_unauthorized(self) -> None:
        wrapper = importlib.import_module(WRAPPER)
        value = wrapper.source_status()
        self.assertEqual(value["status"], "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_15_AUTHORIZATION")
        self.assertTrue(value["canonical_package_digest_exported"])
        self.assertFalse(value["physical_authorization_created"])
        self.assertFalse(value["board_operation"])

    def test_preclaim_unhandled_exception_gets_result_and_marker(self) -> None:
        wrapper = importlib.import_module(WRAPPER)
        contract = importlib.import_module(CONTRACT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            auth = root / "authorization.json"
            auth.write_text("{}\n", encoding="utf-8")
            result = root / "result.json"
            state = root / "state"
            original = wrapper.predecessor.main
            wrapper.predecessor.main = lambda: (_ for _ in ()).throw(AttributeError("boom"))
            old_argv = sys.argv
            try:
                sys.argv = [
                    "wrapper", "execute",
                    "--authorization-record", str(auth),
                    "--result-output", str(result),
                    "--state-root", str(state),
                ]
                rc = wrapper.main()
            finally:
                wrapper.predecessor.main = original
                sys.argv = old_argv
            self.assertEqual(rc, 2)
            value = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(value["failure_stage"], "HOST_INSTALL_PREFLIGHT")
            self.assertEqual(value["failure_code"], "AttributeError")
            self.assertTrue(value["authorization_consumed"])
            self.assertFalse(value["board_operation"])
            marker = state / (wrapper.hashlib.sha256(contract.D2_REQUEST_ID.encode()).hexdigest() + ".json")
            self.assertTrue(marker.is_file())


if __name__ == "__main__":
    unittest.main()
