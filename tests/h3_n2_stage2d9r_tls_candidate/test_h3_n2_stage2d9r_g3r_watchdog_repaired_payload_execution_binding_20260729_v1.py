#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

contract = importlib.import_module(
    "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
    "execution_binding_contract_20260729_v1"
)
wrapper = importlib.import_module(
    "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
    "physical_d2_wrapper_20260729_v1"
)


class WatchdogRepairedPayloadExecutionBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        upstream = os.environ.get("PR203_REVIEW_ARTIFACT")
        watchdog = os.environ.get("PR204_WATCHDOG_REVIEW_ARTIFACT")
        if not upstream or not watchdog:
            raise unittest.SkipTest(
                "PR203_REVIEW_ARTIFACT and PR204_WATCHDOG_REVIEW_ARTIFACT required"
            )
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / "review"
        subprocess.run(
            [
                sys.executable,
                str(
                    TOOLS
                    / (
                        "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
                        "execution_binding_packager_20260729_v1.py"
                    )
                ),
                "--source-root",
                str(ROOT),
                "--upstream-artifact",
                upstream,
                "--watchdog-artifact",
                watchdog,
                "--source-sha",
                "a" * 40,
                "--output",
                str(cls.output),
            ],
            check=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
        )
        cls.package = (
            cls.output
            / "watchdog-repaired-payload-physical-d2-execution-package"
        )
        cls.request_path = cls.output / "PHYSICAL_D2_REQUEST_10.json"
        cls.request = json.loads(cls.request_path.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_01_exact_base_main_and_artifact_bindings(self):
        self.assertEqual(contract.BASE_PR, 204)
        self.assertEqual(
            contract.BASE_HEAD_SHA,
            "8d76634adb171c6492e51a5ebd855bcd52bcf073",
        )
        self.assertEqual(
            contract.MAIN_SHA_AT_BINDING,
            "64c6b093c3ba6a8476c9392c8d106394b2542fb5",
        )
        self.assertEqual(
            contract.README_BLOB_SHA_AT_BINDING,
            "23ccbd3d31c0333924af6d4791f4dde24d1b1b89",
        )
        self.assertEqual(contract.PR204_ARTIFACT_ID, 8716016864)

    def test_02_predecessor_09_is_terminal_and_nonreplayable(self):
        disposition = json.loads(
            (self.output / "D2_09_TERMINAL_DISPOSITION.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(disposition["status"], "CONSUMED_FAILED")
        self.assertEqual(
            disposition["terminal_state"], "LOCKED_RECOVERY_COMPLETED"
        )
        self.assertEqual(
            disposition["failure_code"], "PREPARE_RESULT_TIMEOUT"
        )
        self.assertEqual(disposition["prepare_count"], 1)
        self.assertEqual(disposition["verify_count"], 0)
        self.assertFalse(disposition["replay_permitted"])
        self.assertFalse(disposition["automatic_retry_permitted"])

    def test_03_new_payloads_and_final_binding_are_exact(self):
        package = contract.validate_execution_package(self.package)
        self.assertEqual(
            contract.sha256_file(
                self.package / contract.IMMUTABLE_TAR_FILE
            ),
            contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
        )
        self.assertEqual(
            contract.sha256_file(
                self.package / contract.RECOVERY_TAR_FILE
            ),
            contract.RECOVERY_PAYLOAD_TAR_SHA256,
        )
        final = contract.validate_final_execution_binding(
            self.package / contract.FINAL_BINDING_FILE
        )
        self.assertEqual(
            final["final_execution_binding_sha256"],
            contract.FINAL_EXECUTION_BINDING_SHA256,
        )
        self.assertNotEqual(
            package["closure"]["execution_closure_sha256"],
            contract.PR203_EXECUTION_CLOSURE_SHA256,
        )

    def test_04_old_payload_and_final_binding_are_explicitly_rejected(self):
        with self.assertRaisesRegex(
            contract.ContractError,
            "OLD_IMMUTABLE_PAYLOAD_PERMANENTLY_REJECTED",
        ):
            contract.require_new_payload_digest(
                contract.OLD_IMMUTABLE_PAYLOAD_TAR_SHA256,
                contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
                contract.OLD_IMMUTABLE_PAYLOAD_TAR_SHA256,
                "IMMUTABLE",
            )
        old = json.loads(
            (self.package / contract.FINAL_BINDING_FILE).read_text(
                encoding="utf-8"
            )
        )
        old["final_execution_binding"] = (
            contract.OLD_FINAL_EXECUTION_BINDING
        )
        old["final_execution_binding_sha256"] = (
            contract.OLD_FINAL_EXECUTION_BINDING_SHA256
        )
        with self.assertRaisesRegex(
            contract.ContractError,
            "OLD_FINAL_EXECUTION_BINDING_PERMANENTLY_REJECTED",
        ):
            contract.validate_final_execution_binding_value(old)

    def test_05_request_10_is_new_and_unauthorized(self):
        value = contract.validate_physical_request(
            self.request, self.package
        )
        self.assertTrue(value["d2_request_id"].endswith("-10"))
        self.assertEqual(value["predecessor_request_id"], contract.D2_09_ID)
        self.assertFalse(value["authorized"])
        self.assertFalse(value["authorization_created"])
        self.assertFalse(value["authorization_claimed"])
        self.assertFalse(value["authorization_consumed"])
        self.assertFalse(value["physical_execution_started"])

    def test_06_readme_only_repository_drift_is_audit_only(self):
        drifted = dict(self.request)
        drifted["repository_head_sha"] = "f" * 40
        drifted["non_execution_drift_files"] = ["README.md"]
        drifted.pop("request_binding_sha256")
        drifted["request_binding_sha256"] = contract.canonical_sha256(
            drifted
        )
        validated = contract.validate_physical_request(
            drifted, self.package
        )
        self.assertEqual(validated["repository_head_role"], "AUDIT_ONLY")
        self.assertFalse(validated["repository_head_enforced"])

    def test_07_execution_closure_tamper_fails_closed(self):
        copy_root = Path(self.temp.name) / "tampered"
        shutil.copytree(self.package, copy_root)
        target = copy_root / (
            "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
            "physical_d2_wrapper_20260729_v1.py"
        )
        target.write_text(
            target.read_text(encoding="utf-8") + "\n# tamper\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            contract.ContractError,
            "EXECUTION_CLOSURE_MEMBER_DIGEST_MISMATCH",
        ):
            contract.validate_execution_closure(copy_root)

    def test_08_synthetic_authorization_contract_only_does_not_claim(self):
        now = datetime.now(timezone.utc)
        authorization = {
            **contract.authorization_contract_required(
                self.request, self.package
            ),
            "repository_head_sha": contract.MAIN_SHA_AT_BINDING,
            "non_execution_drift_files": ["README.md"],
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "locked_recovery_authorized": True,
            "activate_authorized": False,
            "cleanup_authorized": False,
            "production_operation_authorized": False,
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(minutes=30))
            .isoformat()
            .replace("+00:00", "Z"),
        }
        for key in (
            "python_executable_sha256",
            "openssl_executable_sha256",
            "esptool_executable_sha256",
            "mosquitto_executable_sha256",
            "execution_marker_name_sha256",
            "board_identity_sha256",
            "serial_identity_sha256",
            "baseline_state_sha256",
            "private_package_sha256",
            "prepare_command_sha256",
            "verify_command_sha256",
            "candidate_digest_sha256",
            "ca_pem_sha256",
        ):
            authorization[key] = "b" * 64
        authorization["authorization_record_sha256"] = (
            contract.canonical_sha256(authorization)
        )
        validated = contract.validate_authorization_contract(
            authorization,
            self.request,
            self.package,
            now=now,
        )
        self.assertTrue(validated["authorized"])
        self.assertFalse(self.request["authorization_created"])

    def test_09_source_entrypoints_are_inert(self):
        for name in (
            (
                "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
                "execution_binding_contract_20260729_v1.py"
            ),
            (
                "h3_n2_stage2d9r_g3r_watchdog_repaired_payload_"
                "physical_d2_wrapper_20260729_v1.py"
            ),
        ):
            result = subprocess.run(
                [sys.executable, str(TOOLS / name)],
                check=True,
                capture_output=True,
                text=True,
            )
            value = json.loads(result.stdout)
            self.assertFalse(
                value.get(
                    "physical_authorization_created",
                    value.get("authorization_created"),
                )
            )
            self.assertFalse(value["board_operation"])
            self.assertFalse(value["network_operation"])

    def test_10_no_authorization_file_is_packaged(self):
        names = {
            path.relative_to(self.output).as_posix().lower()
            for path in self.output.rglob("*")
            if path.is_file()
        }
        self.assertFalse(
            any(
                "authorization" in name and name.endswith(".json")
                for name in names
            )
        )

    def test_11_repaired_handoff_accepts_only_new_payload_bytes(self):
        wrapper._prime_core()
        immutable_members = {
            "SHA256SUMS",
            "application.bin",
            "bootloader.bin",
            "firmware-payload.json",
            "merged-image.bin",
            "partition-table.bin",
        }
        recovery_members = {
            "SHA256SUMS",
            "erased-test-partition.bin",
            "locked-recovery-descriptor.json",
            "locked-recovery-plan.json",
        }
        with tempfile.TemporaryDirectory() as td:
            immutable_root = Path(td) / "immutable"
            recovery_root = Path(td) / "recovery"
            immutable_root.mkdir(mode=0o700)
            recovery_root.mkdir(mode=0o700)
            wrapper.handoff.safe_extract_payload(
                self.package / contract.IMMUTABLE_TAR_FILE,
                immutable_root,
                expected_tar_sha256=contract.IMMUTABLE_PAYLOAD_TAR_SHA256,
                expected_members=immutable_members,
                code="IMMUTABLE_PAYLOAD_INVALID",
            )
            wrapper.handoff.safe_extract_payload(
                self.package / contract.RECOVERY_TAR_FILE,
                recovery_root,
                expected_tar_sha256=contract.RECOVERY_PAYLOAD_TAR_SHA256,
                expected_members=recovery_members,
                code="RECOVERY_PAYLOAD_INVALID",
            )
            wrapper.handoff._BOUND_TARS = (
                self.package / contract.IMMUTABLE_TAR_FILE,
                self.package / contract.RECOVERY_TAR_FILE,
            )
            merged, erased = wrapper.handoff.validate_public_inputs(
                immutable_root, recovery_root
            )
            self.assertEqual(
                contract.sha256_file(merged),
                contract.IMMUTABLE_MERGED_IMAGE_SHA256,
            )
            self.assertEqual(erased.stat().st_size, 0x10000)


if __name__ == "__main__":
    unittest.main()
