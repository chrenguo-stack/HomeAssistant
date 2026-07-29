#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_packager_20260729_v1 as packager


def build_authorization(package_root: Path, request: dict, now: datetime, tool: Path) -> dict:
    wrapper = package_root / contract.OVERLAY_WRAPPER_FILE
    value = {
        **contract.authorization_contract_required(request, package_root),
        "authorized": True,
        "one_shot": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=30)).isoformat(),
        "immutable_artifact_id": contract.IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_archive_sha256": contract.IMMUTABLE_ARCHIVE_SHA256,
        "immutable_payload_tar_sha256": contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
        "immutable_merged_image_sha256": contract.IMMUTABLE_MERGED_SHA256,
        "recovery_artifact_id": contract.IMMUTABLE_ARTIFACT_ID,
        "recovery_artifact_archive_sha256": contract.IMMUTABLE_ARCHIVE_SHA256,
        "recovery_payload_tar_sha256": contract.RECOVERY_PAYLOAD_TAR_SHA256,
        "recovery_descriptor_sha256": contract.RECOVERY_DESCRIPTOR_SHA256,
        "private_package_sha256": contract.PRIVATE_PACKAGE_SHA256,
        "prepare_command_sha256": contract.PREPARE_COMMAND_SHA256,
        "verify_command_sha256": contract.VERIFY_COMMAND_SHA256,
        "candidate_digest_sha256": contract.CANDIDATE_DIGEST_SHA256,
        "ca_pem_sha256": contract.CA_PEM_SHA256,
        "build_binding": contract.BUILD_BINDING,
        "execution_script_sha256": contract.sha256_file(wrapper),
        "python_executable_sha256": contract.sha256_file(Path(sys.executable).resolve()),
        "openssl_executable_sha256": contract.sha256_file(tool),
        "esptool_executable_sha256": contract.sha256_file(tool),
        "mosquitto_executable_sha256": contract.sha256_file(tool),
        "execution_marker_name_sha256": contract.marker_name_sha256(),
        "prepare_max_count": 1,
        "verify_max_count": 1,
        "locked_recovery_max_count": 1,
        "locked_recovery_authorized": True,
        "activate_authorized": False,
        "cleanup_authorized": False,
        "production_operation_authorized": False,
    }
    value["authorization_record_sha256"] = contract.canonical_json_sha256(value)
    return value


@unittest.skipUnless(os.environ.get("STAGE2D9R_OVERLAY_UPSTREAM_ARTIFACT_ZIP"), "real upstream Artifact not supplied")
class PhysicalExecutionOverlayBindingRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.output = cls.root / "review"
        artifact = Path(os.environ["STAGE2D9R_OVERLAY_UPSTREAM_ARTIFACT_ZIP"])
        cls.result = packager.build(ROOT, artifact, cls.output, "a" * 40, "64c6b093c3ba6a8476c9392c8d106394b2542fb5")
        cls.package = cls.output / packager.EXECUTION_PACKAGE_DIR
        cls.request_path = cls.output / contract.PHYSICAL_REQUEST_FILE
        cls.request = json.loads(cls.request_path.read_text())
        cls.now = datetime.now(timezone.utc)
        cls.tool = cls.root / "fake-tool-for-contract-tests"
        cls.tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(cls.tool, 0o700)
        cls.auth = build_authorization(cls.package, cls.request, cls.now, cls.tool)
        cls.auth_path = cls.root / "valid-auth.json"
        cls.auth_path.write_text(json.dumps(cls.auth, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.chmod(cls.auth_path, 0o600)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_request_05_is_permanently_invalidated_before_authorization(self) -> None:
        value = contract.request_05_invalidation_disposition()
        self.assertEqual(value["state"], contract.REQUEST_05_INVALID_STATE)
        self.assertFalse(value["authorization_created"])
        self.assertFalse(value["replay_permitted"])

    def test_request_06_is_exact_and_unauthorized(self) -> None:
        self.assertEqual(self.request["d2_request_id"], contract.REQUEST_06_ID)
        self.assertEqual(self.request["baseline_state_sha256"], contract.CORRECTED_BASELINE_SHA256)
        self.assertEqual(self.request["predecessor_05_state"], contract.REQUEST_05_INVALID_STATE)
        self.assertFalse(self.request["authorized"])
        self.assertFalse(self.request["physical_request_authorized"])
        contract.validate_physical_request(self.request, self.package)

    def test_execution_package_differs_from_incompatible_upstream(self) -> None:
        self.assertNotEqual(self.result["execution_package_sha256"], contract.UPSTREAM_EXECUTION_PACKAGE_SHA256)
        self.assertEqual(contract.canonical_package_digest(self.package), self.result["execution_package_sha256"])

    def test_immutable_and_recovery_payload_bytes_are_unchanged(self) -> None:
        self.assertEqual(contract.sha256_file(self.package / "stage2d9r-g3r-repaired-immutable-payload-v1.tar"), contract.IMMUTABLE_PAYLOAD_TAR_SHA256)
        self.assertEqual(contract.sha256_file(self.package / "stage2d9r-g3r-repaired-locked-recovery-payload-v1.tar"), contract.RECOVERY_PAYLOAD_TAR_SHA256)

    def test_overlay_wrapper_and_launcher_are_bound_to_request_06(self) -> None:
        overlay = contract.validate_execution_overlay(self.package)
        self.assertEqual(overlay["binding"]["physical_request_id"], contract.REQUEST_06_ID)
        wrapper_text = (self.package / contract.OVERLAY_WRAPPER_FILE).read_text()
        launcher_text = (self.package / contract.OVERLAY_LAUNCHER_FILE).read_text()
        self.assertIn("REQUEST_06_ID", wrapper_text)
        self.assertIn("contract-check|execute", launcher_text)

    def test_contract_only_valid_authorization_passes(self) -> None:
        validated = contract.validate_authorization_contract(self.auth, self.request, self.package, now=self.now)
        self.assertEqual(validated["d2_request_id"], contract.REQUEST_06_ID)

    def test_full_core_authorization_validator_accepts_request_06(self) -> None:
        sys.path.insert(0, str(self.package))
        try:
            wrapper = importlib.import_module("h3_n2_stage2d9r_g3r_corrected_baseline_physical_d2_overlay_wrapper_20260729_v1")
            wrapper._BOUND_PHYSICAL_REQUEST = self.request
            wrapper.repaired.repair.install_repaired_handshake = lambda _core: None
            configured = wrapper.configure_core()
            validated = configured.validate_authorization(
                self.auth_path,
                package_root=self.package,
                python_path=Path(sys.executable).resolve(),
                openssl_path=self.tool,
                esptool_path=self.tool,
                mosquitto_path=self.tool,
                now=self.now,
            )
            self.assertEqual(validated["baseline_state_sha256"], contract.CORRECTED_BASELINE_SHA256)
        finally:
            sys.path.pop(0)

    def test_old_request_05_authorization_is_rejected(self) -> None:
        value = dict(self.auth)
        value["d2_request_id"] = contract.REQUEST_05_ID
        value.pop("authorization_record_sha256")
        value["authorization_record_sha256"] = contract.canonical_json_sha256(value)
        with self.assertRaisesRegex(contract.ContractError, "AUTHORIZATION_D2_REQUEST_ID_MISMATCH"):
            contract.validate_authorization_contract(value, self.request, self.package, now=self.now)

    def test_old_request_04_authorization_is_rejected(self) -> None:
        value = dict(self.auth)
        value["d2_request_id"] = contract.PREDECESSOR_04_ID
        value.pop("authorization_record_sha256")
        value["authorization_record_sha256"] = contract.canonical_json_sha256(value)
        with self.assertRaisesRegex(contract.ContractError, "AUTHORIZATION_D2_REQUEST_ID_MISMATCH"):
            contract.validate_authorization_contract(value, self.request, self.package, now=self.now)

    def test_real_shell_contract_integration(self) -> None:
        script = ROOT / "tests/h3_n2_stage2d9r_tls_candidate/test_h3_n2_stage2d9r_g3r_physical_execution_overlay_shell_20260729_v1.sh"
        env = {
            **os.environ,
            "STAGE2D9R_OVERLAY_PACKAGE_ROOT": str(self.package),
            "STAGE2D9R_OVERLAY_REQUEST": str(self.request_path),
            "STAGE2D9R_OVERLAY_VALID_AUTH": str(self.auth_path),
        }
        completed = subprocess.run(["sh", str(script)], text=True, capture_output=True, env=env, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("SHELL_INTEGRATION_PASS", completed.stdout)

    def test_package_build_is_deterministic(self) -> None:
        second = self.root / "review-second"
        artifact = Path(os.environ["STAGE2D9R_OVERLAY_UPSTREAM_ARTIFACT_ZIP"])
        second_result = packager.build(ROOT, artifact, second, "a" * 40, "64c6b093c3ba6a8476c9392c8d106394b2542fb5")
        self.assertEqual(self.result["archive_sha256"], second_result["archive_sha256"])
        self.assertEqual(packager.recursive_files(self.output), packager.recursive_files(second))

    def test_no_physical_authorization_is_created(self) -> None:
        self.assertTrue((self.output / contract.PHYSICAL_REQUEST_FILE).is_file())
        self.assertFalse((self.output / "physical-d2-authorization-06.json").exists())
        self.assertFalse(self.request["authorization_created"])
        self.assertFalse(self.request["authorization_claimed"])
        self.assertFalse(self.request["authorization_consumed"])


if __name__ == "__main__":
    unittest.main()
