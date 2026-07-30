from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repair_execution_binding_contract_20260730_v1 as contract
import h3_n2_stage2d9r_g3r_d2_14_payload_extraction_ownership_repaired_physical_d2_wrapper_20260730_v1 as wrapper


class D214ExtractionOwnershipTests(unittest.TestCase):
    def roots(self, base: Path) -> tuple[Path, Path, list[str]]:
        immutable = base / "immutable"
        recovery = base / "recovery"
        immutable.mkdir(mode=0o700)
        recovery.mkdir(mode=0o700)
        os.chmod(immutable, 0o700)
        os.chmod(recovery, 0o700)
        argv = ["--immutable-root", str(immutable), "--recovery-root", str(recovery)]
        return immutable, recovery, argv

    def test_empty_roots_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            immutable, recovery, argv = self.roots(Path(temporary))
            self.assertEqual(wrapper.verify_empty_payload_roots(argv), (immutable.resolve(), recovery.resolve()))

    def test_preextracted_immutable_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            immutable, _, argv = self.roots(Path(temporary))
            (immutable / "application.bin").write_bytes(b"not permitted")
            with self.assertRaisesRegex(wrapper.ExtractionOwnershipError, "IMMUTABLE_PAYLOAD_ROOT_NOT_EMPTY"):
                wrapper.verify_empty_payload_roots(argv)

    def test_tar_copy_inside_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            immutable, _, argv = self.roots(Path(temporary))
            (immutable / contract.IMMUTABLE_PAYLOAD_FILE).write_bytes(b"not permitted")
            with self.assertRaisesRegex(wrapper.ExtractionOwnershipError, "IMMUTABLE_PAYLOAD_ROOT_NOT_EMPTY"):
                wrapper.verify_empty_payload_roots(argv)

    def test_recovery_root_is_independently_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, recovery, argv = self.roots(Path(temporary))
            (recovery / "locked-recovery-plan.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(wrapper.ExtractionOwnershipError, "RECOVERY_PAYLOAD_ROOT_NOT_EMPTY"):
                wrapper.verify_empty_payload_roots(argv)

    def test_role_collision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "payload"
            root.mkdir(mode=0o700)
            os.chmod(root, 0o700)
            argv = ["--immutable-root", str(root), "--recovery-root", str(root)]
            with self.assertRaisesRegex(wrapper.ExtractionOwnershipError, "PAYLOAD_ROOT_ROLE_COLLISION"):
                wrapper.verify_empty_payload_roots(argv)

    def test_authorization_created_preclaim_failure_is_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            auth = base / "authorization.json"
            auth.write_text('{"authorized":true}\n', encoding="utf-8")
            result = base / "result.json"
            state = base / "state"
            argv = [
                "--authorization-record", str(auth),
                "--result-output", str(result),
                "--state-root", str(state),
            ]
            value = wrapper.write_preclaim_ownership_failure(argv, "IMMUTABLE_PAYLOAD_ROOT_NOT_EMPTY")
            self.assertEqual(value["terminal_state"], "CONSUMED_FAILED_PRECLAIM")
            self.assertTrue(value["authorization_consumed"])
            self.assertFalse(value["authorization_claimed"])
            self.assertFalse(value["board_operation"])
            self.assertTrue(result.is_file())
            marker = state / (wrapper.hashlib.sha256(contract.D2_REQUEST_ID.encode()).hexdigest() + ".json")
            self.assertTrue(marker.is_file())
            stored = json.loads(marker.read_text(encoding="utf-8"))
            self.assertEqual(stored["failure_stage"], "PAYLOAD_EXTRACTION_OWNERSHIP")
            self.assertFalse(stored["replay_permitted"])

    def test_decision_binds_consumed_d2_13(self) -> None:
        decision = Path(__file__).resolve().parents[2] / "docs" / "decisions" / contract.DECISION_FILE
        value = contract.validate_decision(decision)
        self.assertTrue(value["predecessor_authorization_consumed"])
        self.assertFalse(value["predecessor_replay_permitted"])
        self.assertTrue(value["inner_payload_extraction_single_owner"])


if __name__ == "__main__":
    unittest.main()
