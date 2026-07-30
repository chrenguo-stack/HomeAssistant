from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from tools.h3_n2_stage2d9r_g3r_d2_17_permission_independent_shell_invoke_contract_20260730_v1 import (
    VerifiedShellInvokeError,
    build_command,
    run_verified_script,
)

ROOT = Path(__file__).resolve().parents[2]
FAILURE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g05-static-check-permission-failure-20260730-v1.json"
DECISION = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g05-canonical-outer-permission-independent-invoke-repair-20260730-v1.json"
OUTER_SHA256 = "2083652dfeedb93c71ac589300b155c1102fd6354dbeb31ecd588669a97b7994"


class TestPermissionIndependentShellInvoke(unittest.TestCase):
    def test_frozen_bindings(self) -> None:
        failure = json.loads(FAILURE.read_text(encoding="utf-8"))
        decision = json.loads(DECISION.read_text(encoding="utf-8"))
        self.assertEqual(failure["failure_code"], "PermissionError")
        self.assertFalse(failure["authorization_created"])
        self.assertFalse(failure["authorization_claimed"])
        self.assertFalse(failure["authorization_consumed"])
        self.assertTrue(failure["all_physical_operation_flags_false"])
        self.assertEqual(failure["canonical_outer_sha256"], OUTER_SHA256)
        self.assertEqual(failure["failure_disposition_binding_sha256"], "93365d68ad0ec7428a2d60642403d300239f6a36516f364768618457d5bc1659")
        self.assertEqual(decision["decision_binding_sha256"], "1d761b90e0678d35c52e5ec82d13866107abd780012944ce7e6788ef02b2ab68")
        self.assertEqual(decision["next_gate"], "D1-H3N2-STAGE2D9R-G3R-D2-17-G06-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260730-01")

    def test_mode_0600_executes_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g05 mode 0600 ") as raw:
            root = Path(raw)
            script = root / "outer script.sh"
            script.write_text(
                "#!/bin/sh\n"
                "python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' -- \"$@\"\n",
                encoding="utf-8",
            )
            os.chmod(script, 0o600)
            before = stat.S_IMODE(script.stat().st_mode)
            digest = hashlib.sha256(script.read_bytes()).hexdigest()
            cp = run_verified_script(
                script,
                digest,
                ["alpha beta", "", "gamma"],
                stdout=-1,
                stderr=-1,
            )
            self.assertEqual(cp.returncode, 0, cp.stderr.decode())
            self.assertEqual(json.loads(cp.stdout.decode().strip()), ["--", "alpha beta", "", "gamma"])
            self.assertEqual(stat.S_IMODE(script.stat().st_mode), before)

    def test_command_uses_shell_not_direct_exec(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            script = Path(raw) / "x.sh"
            script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(script, 0o600)
            digest = hashlib.sha256(script.read_bytes()).hexdigest()
            command = build_command(script, digest, ["a b", ""])
            self.assertEqual(Path(command[0]).resolve(), Path("/bin/sh").resolve())
            self.assertEqual(Path(command[1]), script.resolve())
            self.assertEqual(command[2:], ["a b", ""])

    def test_tamper_rejected_before_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            script = Path(raw) / "x.sh"
            script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(script, 0o600)
            digest = hashlib.sha256(script.read_bytes()).hexdigest()
            script.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
            with self.assertRaisesRegex(VerifiedShellInvokeError, "DIGEST_DRIFT"):
                build_command(script, digest, [])

    def test_symlink_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "target.sh"
            target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            link = root / "link.sh"
            link.symlink_to(target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            with self.assertRaisesRegex(VerifiedShellInvokeError, "NOT_REGULAR"):
                build_command(link, digest, [])


if __name__ == "__main__":
    unittest.main()
