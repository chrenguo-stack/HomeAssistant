from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "n3w_ota_guard_identity_contract_repair.py"
)
spec = importlib.util.spec_from_file_location("n3w_ota_guard_identity_contract_repair", MODULE_PATH)
assert spec and spec.loader
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


def example_mac(last_octet: str) -> str:
    return ":".join(("02", "00", "00", "00", "00", last_octet))


def example_eui64(last_octet: str) -> str:
    return ":".join(("02", "00", "00", "ff", "fe", "00", "00", last_octet))


def forensic_shape(base_mac: str) -> str:
    eui64 = example_eui64(base_mac.split(":")[-1])
    return "\n".join(
        (
            "esptool v5.2.0",
            f"MAC: {eui64}",
            f"BASE MAC: {base_mac}",
            "MAC_EXT: ff:fe",
            "Read MAC command:",
            f"MAC: {eui64}",
            f"BASE MAC: {base_mac}",
            "MAC_EXT: ff:fe",
            "",
        )
    )


class IdentityContractRepairTests(unittest.TestCase):
    def test_01_reviewed_base_git_blob_is_exact(self):
        self.assertEqual(r.verify_reviewed_base_binding(), r.EXPECTED_BASE_GIT_BLOB)

    def test_02_old_parser_reproduces_eui64_false_positive(self):
        base_mac = example_mac("41")
        output = forensic_shape(base_mac)
        with self.assertRaisesRegex(r.base.GuardError, "exactly one"):
            r.base.verify_identity_output(output, base_mac)

    def test_03_repair_accepts_duplicate_same_exact_base_mac_lines(self):
        base_mac = example_mac("42")
        observed, count = r.extract_authoritative_base_mac(forensic_shape(base_mac))
        self.assertEqual(observed, base_mac)
        self.assertEqual(count, 2)

    def test_04_repair_rejects_two_distinct_exact_base_mac_values(self):
        first = example_mac("43")
        second = example_mac("44")
        output = f"BASE MAC: {first}\nBASE MAC: {second}\n"
        with self.assertRaisesRegex(r.base.GuardError, "multiple distinct exact BASE MAC"):
            r.extract_authoritative_base_mac(output)

    def test_05_repair_rejects_generic_mac_without_exact_base_label(self):
        base_mac = example_mac("45")
        output = f"MAC: {base_mac}\n"
        with self.assertRaisesRegex(r.base.GuardError, "no exact BASE MAC line"):
            r.extract_authoritative_base_mac(output)

    def test_06_repair_ignores_six_octet_prefix_inside_eui64(self):
        base_mac = example_mac("46")
        eui64 = example_eui64("46")
        observed, _count = r.extract_authoritative_base_mac(
            f"MAC: {eui64}\nBASE MAC: {base_mac}\n"
        )
        self.assertEqual(observed, base_mac)
        self.assertNotEqual(observed, ":".join(eui64.split(":")[:6]))

    def test_07_runner_preserves_raw_evidence_and_canonicalizes_only_return_value(self):
        base_mac = example_mac("47")
        raw = forensic_shape(base_mac)
        completed = subprocess.CompletedProcess(
            args=["python", "esptool.py"], returncode=0, stdout=raw, stderr=""
        )
        with tempfile.TemporaryDirectory() as td:
            store = r.base.EvidenceStore(Path(td) / "ev")
            with mock.patch.object(r.base, "run_read_command", return_value=completed):
                result = r.identity_contract_runner(
                    ["python", "esptool.py"], store, "rom_identity_read"
                )
            self.assertEqual(result.stdout, f"BASE MAC: {base_mac}\n")
            record = json.loads(
                (store.root / "rom-identity-contract-repair.json").read_text()
            )
            self.assertTrue(record["raw_stdout_preserved"])
            self.assertEqual(record["authoritative_line_occurrence_count"], 2)
            self.assertEqual(record["authoritative_distinct_value_count"], 1)
            self.assertTrue(record["eui64_substring_candidates_ignored"])

    def test_08_non_identity_runner_result_is_unmodified(self):
        completed = subprocess.CompletedProcess(
            args=["python", "esptool.py"], returncode=0, stdout="unchanged", stderr=""
        )
        with tempfile.TemporaryDirectory() as td:
            store = r.base.EvidenceStore(Path(td) / "ev")
            with mock.patch.object(r.base, "run_read_command", return_value=completed):
                result = r.identity_contract_runner(
                    ["python", "esptool.py"], store, "app0_existing_read"
                )
            self.assertIs(result, completed)
            self.assertFalse((store.root / "rom-identity-contract-repair.json").exists())

    def test_09_host_only_replay_accepts_old_private_stdout_shape(self):
        base_mac = example_mac("48")
        with tempfile.TemporaryDirectory() as td:
            evidence = Path(td) / "rom_identity_read.stdout.txt"
            evidence.write_text(forensic_shape(base_mac))
            occurrences, distinct = r.replay_identity_evidence(str(evidence), base_mac)
            self.assertEqual((occurrences, distinct), (2, 1))

    def test_10_host_only_replay_rejects_expected_identity_mismatch(self):
        observed = example_mac("49")
        expected = example_mac("50")
        with tempfile.TemporaryDirectory() as td:
            evidence = Path(td) / "rom_identity_read.stdout.txt"
            evidence.write_text(forensic_shape(observed))
            with self.assertRaisesRegex(r.base.GuardError, "does not match expected"):
                r.replay_identity_evidence(str(evidence), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
