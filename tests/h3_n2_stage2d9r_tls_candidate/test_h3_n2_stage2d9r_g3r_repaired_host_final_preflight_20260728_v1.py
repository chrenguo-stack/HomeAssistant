from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_repaired_host_final_preflight_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_repaired_host_final_preflight_packager_20260728_v1 as packager


class HostFinalPreflightTests(unittest.TestCase):
    def test_source_contract_dual_main_and_no_authority(self) -> None:
        value = contract.source_contract("1" * 40)
        self.assertEqual(value["base_pr"], 188)
        self.assertEqual(
            value["baseline_original_main_sha"],
            "c16da1a2d4d8300198b0603359eea349a034e2ea",
        )
        self.assertEqual(
            value["accepted_current_main_sha"],
            "0229002cc5037f83bc77426f439bdb9e6d63318c",
        )
        self.assertTrue(value["main_tree_zero_net_change"])
        for key in (
            "authorized",
            "board_operation",
            "usb_enumeration",
            "serial_operation",
            "esptool_operation",
            "flash_operation",
            "network_operation",
            "broker_started",
            "prepare_executed",
            "verify_executed",
        ):
            self.assertFalse(value[key], key)

    def test_request_template_and_finalization_remain_unauthorized(self) -> None:
        template = contract.build_request_template(
            source_sha="1" * 40,
            review_binding_sha256="2" * 64,
            execution_package_sha256="3" * 64,
            execution_wrapper_sha256="4" * 64,
            execution_launcher_sha256="5" * 64,
            repaired_host_controller_sha256="6" * 64,
        )
        self.assertIsNone(template["host_preflight_result_sha256"])
        self.assertFalse(template["authorized"])
        toolchain = {
            "python_executable_sha256": "7" * 64,
            "openssl_executable_sha256": "8" * 64,
            "esptool_executable_sha256": "9" * 64,
            "esptool_module_sha256": "a" * 64,
            "pyserial_module_sha256": "b" * 64,
            "mosquitto_executable_sha256": "c" * 64,
        }
        request = contract.finalize_request(
            template,
            host_preflight_result_sha256="d" * 64,
            toolchain=toolchain,
            issued_at="2026-07-28T05:00:00Z",
            expires_at="2026-07-28T07:00:00Z",
        )
        self.assertEqual(len(request["request_binding_sha256"]), 64)
        self.assertFalse(request["authorized"])
        self.assertEqual(request["host_final_preflight_source_sha"], "1" * 40)
        self.assertEqual(request["immutable_source_sha"], contract.BASE_HEAD_SHA)
        self.assertEqual(
            request["execution_script_sha256"],
            request["execution_wrapper_sha256"],
        )
        self.assertEqual(
            request["execution_marker_name_sha256"],
            contract.PHYSICAL_D2_MARKER_NAME_SHA256,
        )
        self.assertEqual(request["prepare_max_count"], 1)
        self.assertEqual(request["verify_max_count"], 1)
        self.assertEqual(request["locked_recovery_max_count"], 1)
        self.assertEqual(request["locked_recovery_scope"], "TEST_PARTITION_ONLY")
        self.assertFalse(request["locked_recovery_authorized"])

    def test_baseline_public_archive_reconstructs_exactly(self) -> None:
        archive, acceptance = packager.reconstruct_baseline(ROOT)
        self.assertEqual(
            hashlib.sha256(archive).hexdigest(),
            contract.BASELINE_PUBLIC_ARCHIVE_SHA256,
        )
        self.assertEqual(
            acceptance["result_sha256"], contract.BASELINE_RESULT_SHA256
        )
        self.assertEqual(
            acceptance["main_sha"], contract.BASELINE_ORIGINAL_MAIN_SHA
        )
        self.assertTrue(acceptance["authorization_consumed"])
        self.assertFalse(acceptance["replay_permitted"])

    def test_host_probe_has_no_board_or_network_implementation(self) -> None:
        text = (
            TOOLS
            / "h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_20260728_v1.py"
        ).read_text()
        for forbidden in (
            "list_ports.comports",
            "serial.Serial",
            "import socket",
            "socket.socket",
            "esptool.main",
            "subprocess.Popen",
        ):
            self.assertNotIn(forbidden, text)

    def test_repaired_locked_recovery_is_read_erase_read_only(self) -> None:
        path = (
            TOOLS
            / "h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py"
        )
        tree = ast.parse(path.read_text())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "locked_recovery"
        )
        strings = [
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        self.assertIn("erase_region", strings)
        self.assertIn("read_flash", strings)
        self.assertNotIn("write_flash", strings)
        self.assertEqual(strings.count("erase_region"), 1)
        self.assertEqual(strings.count("read_flash"), 2)

    def test_real_immutable_zip_and_two_deterministic_packages(self) -> None:
        artifact_value = os.environ.get("STAGE2D9R_REPAIRED_IMMUTABLE_ZIP")
        if not artifact_value:
            self.skipTest("canonical immutable Artifact ZIP not supplied")
        artifact = Path(artifact_value).resolve(strict=True)
        files = packager.validate_immutable_zip(artifact)
        self.assertEqual(
            hashlib.sha256(
                files["stage2d9r-g3r-repaired-immutable-payload-v1.tar"]
            ).hexdigest(),
            contract.IMMUTABLE_PAYLOAD_SHA256,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            shutil.copytree(ROOT, root)
            for name in (
                "h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py",
                "h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py",
                "h3_n2_stage2d9r_g3r_repaired_private_material_contract_20260728_v1.py",
                "h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1.py",
                "h3_n2_stage2d9r_prepare_command_protocol_20260723_v1.py",
            ):
                target = root / "tools" / name
                if not target.exists():
                    target.write_text("# deterministic test placeholder\n")
            out_a = Path(td) / "out-a"
            out_b = Path(td) / "out-b"
            result_a = packager.build(root, artifact, out_a, "1" * 40)
            result_b = packager.build(root, artifact, out_b, "1" * 40)
            self.assertEqual(result_a, result_b)
            self.assertEqual(
                (out_a / packager.REVIEW_ARCHIVE_NAME).read_bytes(),
                (out_b / packager.REVIEW_ARCHIVE_NAME).read_bytes(),
            )
            with tarfile.open(out_a / packager.REVIEW_ARCHIVE_NAME, "r") as tf:
                for member in tf.getmembers():
                    self.assertTrue(member.isfile())
                    self.assertEqual(member.mode, 0o644)
                    self.assertEqual(member.uid, 0)
                    self.assertEqual(member.gid, 0)
                    self.assertEqual(member.mtime, 0)
            binding = json.loads(
                (out_a / packager.BINDING_FILE).read_text()
            )
            self.assertFalse(binding["authorized"])
            self.assertFalse(binding["host_preflight_executed"])
            self.assertEqual(
                binding["accepted_current_main_sha"],
                contract.ACCEPTED_CURRENT_MAIN_SHA,
            )


if __name__ == "__main__":
    unittest.main()
