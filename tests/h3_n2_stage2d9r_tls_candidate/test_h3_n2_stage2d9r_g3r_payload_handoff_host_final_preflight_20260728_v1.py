from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
import sys
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_packager_20260728_v1 as packager


class PayloadHandoffHostFinalPreflightTests(unittest.TestCase):
    def test_source_contract_binds_pr190_and_consumed_old_d2(self) -> None:
        value = contract.source_contract("1" * 40)
        self.assertEqual(value["base_pr"], 190)
        self.assertEqual(value["base_head_sha"], "261f24dc7e01fe9eaaf0a607a2868cd4411286bf")
        self.assertEqual(value["payload_repair_artifact_id"], 8682468219)
        self.assertEqual(value["old_physical_d2_status"], "CONSUMED_FAILED")
        self.assertEqual(value["old_physical_d2_failure_code"], "IMMUTABLE_PAYLOAD_INVALID")
        self.assertFalse(value["old_physical_d2_replay_permitted"])
        for key in (
            "authorized", "authorization_created", "authorization_claimed",
            "authorization_consumed", "board_operation", "usb_enumeration",
            "serial_operation", "esptool_operation", "flash_operation",
            "network_operation", "broker_started", "prepare_executed", "verify_executed",
        ):
            self.assertFalse(value[key], key)

    def test_request_template_is_new_and_unauthorized(self) -> None:
        value = contract.build_request_template(
            source_sha="1" * 40,
            review_binding_sha256="2" * 64,
            execution_package_sha256="3" * 64,
            execution_wrapper_sha256="4" * 64,
            execution_launcher_sha256="5" * 64,
            repaired_host_controller_sha256="6" * 64,
        )
        self.assertEqual(value["d2_request_id"], contract.PHYSICAL_D2_REQUEST_ID)
        self.assertNotEqual(value["d2_request_id"], contract.OLD_PHYSICAL_D2_ID)
        self.assertEqual(value["payload_handoff_repair_source_sha"], contract.BASE_HEAD_SHA)
        self.assertEqual(value["payload_handoff_contract"], contract.PAYLOAD_HANDOFF_CONTRACT)
        self.assertEqual(value["preclaim_failure_contract"], contract.PRECLAIM_FAILURE_CONTRACT)
        self.assertIsNone(value["host_preflight_result_sha256"])
        self.assertFalse(value["authorized"])
        self.assertFalse(value["locked_recovery_authorized"])
        self.assertEqual(value["prepare_max_count"], 1)
        self.assertEqual(value["verify_max_count"], 1)

    def test_final_wrapper_only_rebinds_frozen_handoff(self) -> None:
        path = TOOLS / "h3_n2_stage2d9r_g3r_payload_handoff_final_physical_d2_wrapper_20260728_v1.py"
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        self.assertIn("h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1", text)
        self.assertIn("payload_handoff_repair_source_sha", text)
        self.assertNotIn("tarfile.open", text)
        self.assertNotIn('"write_flash"', text)
        self.assertNotIn('"erase_flash"', text)
        functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(functions, {"configure_core", "install", "main"})

    def test_host_probe_has_no_board_network_or_process_start_implementation(self) -> None:
        text = (TOOLS / "h3_n2_stage2d9r_g3r_payload_handoff_host_final_preflight_probe_20260728_v1.py").read_text(encoding="utf-8")
        for forbidden in (
            "list_ports.comports", "serial.Serial", "import socket", "socket.socket",
            "esptool.main", "subprocess.Popen",
        ):
            self.assertNotIn(forbidden, text)

    def test_real_repair_artifact_validates_exactly(self) -> None:
        value = os.environ.get("STAGE2D9R_PAYLOAD_REPAIR_ARTIFACT_ZIP")
        if not value:
            self.skipTest("exact repair Artifact ZIP not supplied")
        path = Path(value).resolve(strict=True)
        files = packager.validate_repair_artifact(path)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), contract.PAYLOAD_REPAIR_ARTIFACT_SHA256)
        binding = json.loads(files["PAYLOAD_HANDOFF_REPAIR_REVIEW_BINDING.json"])
        self.assertEqual(binding["source_sha"], contract.BASE_HEAD_SHA)
        self.assertEqual(binding["next_gate"], "NEW_HOST_ONLY_FINAL_PREFLIGHT_REVIEW_AND_EXACT_AUTHORIZATION")

    def test_final_shell_launcher_passes_tar_and_roots_as_separate_roles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "package"
            root.mkdir(mode=0o700)
            launcher = root / packager.FINAL_LAUNCHER
            launcher.write_bytes(packager.launcher_bytes())
            launcher.chmod(0o700)
            for name in (
                packager.FINAL_WRAPPER,
                "stage2d9r-g3r-repaired-immutable-payload-v1.tar",
                "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar",
            ):
                (root / name).write_bytes(b"placeholder")
            fake_bin = Path(td) / "bin"
            fake_bin.mkdir()
            capture = Path(td) / "args.txt"
            python = fake_bin / "python3"
            python.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$CAPTURE\"\n", encoding="utf-8")
            python.chmod(0o700)
            auth = Path(td) / "authorization.json"
            result = Path(td) / "result.json"
            auth.write_text("{}", encoding="utf-8")
            completed = subprocess.run(
                [str(launcher), str(auth), str(result)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""), "CAPTURE": str(capture), "TMPDIR": td},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            args = capture.read_text(encoding="utf-8").splitlines()
            self.assertTrue(args[0].endswith(packager.FINAL_WRAPPER))
            pairs = dict(zip(args[1::2], args[2::2]))
            self.assertIn("--immutable-payload-tar", pairs)
            self.assertIn("--immutable-root", pairs)
            self.assertIn("--recovery-payload-tar", pairs)
            self.assertIn("--recovery-root", pairs)
            self.assertNotEqual(Path(pairs["--immutable-payload-tar"]).parent, Path(pairs["--immutable-root"]))
            self.assertNotEqual(Path(pairs["--recovery-payload-tar"]).parent, Path(pairs["--recovery-root"]))

    def test_two_deterministic_review_packages(self) -> None:
        artifact_value = os.environ.get("STAGE2D9R_PAYLOAD_REPAIR_ARTIFACT_ZIP")
        if not artifact_value:
            self.skipTest("exact repair Artifact ZIP not supplied")
        artifact = Path(artifact_value).resolve(strict=True)
        with tempfile.TemporaryDirectory() as td:
            out_a = Path(td) / "a"
            out_b = Path(td) / "b"
            result_a = packager.build(ROOT, artifact, out_a, "1" * 40)
            result_b = packager.build(ROOT, artifact, out_b, "1" * 40)
            self.assertEqual(result_a, result_b)
            self.assertEqual((out_a / packager.REVIEW_ARCHIVE_NAME).read_bytes(), (out_b / packager.REVIEW_ARCHIVE_NAME).read_bytes())
            with tarfile.open(out_a / packager.REVIEW_ARCHIVE_NAME, "r") as archive:
                for member in archive.getmembers():
                    self.assertTrue(member.isfile())
                    self.assertEqual(member.mode, 0o644)
                    self.assertEqual(member.uid, 0)
                    self.assertEqual(member.gid, 0)
                    self.assertEqual(member.mtime, 0)
            binding = json.loads((out_a / packager.BINDING_FILE).read_text(encoding="utf-8"))
            request = json.loads((out_a / packager.REQUEST_FILE).read_text(encoding="utf-8"))
            self.assertFalse(binding["authorized"])
            self.assertFalse(binding["host_preflight_executed"])
            self.assertFalse(request["authorized"])
            self.assertEqual(request["payload_handoff_repair_source_sha"], contract.BASE_HEAD_SHA)


if __name__ == "__main__":
    unittest.main()
