#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load(
    "prepare_evidence_execution_contract",
    "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_contract_20260729_v1.py",
)
recorder = load(
    "prepare_evidence_recorder_for_binding",
    "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1.py",
)


class PrepareTimeoutEvidenceExecutionBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = os.environ.get("PR200_REVIEW_ARTIFACT")
        cls.temp = None
        cls.package_root = None
        cls.request = None
        if cls.artifact:
            cls.temp = tempfile.TemporaryDirectory()
            output = Path(cls.temp.name) / "review"
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_packager_20260729_v1.py"),
                    "--source-root", str(ROOT),
                    "--upstream-artifact", cls.artifact,
                    "--source-sha", "2" * 40,
                    "--output", str(output),
                ],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            cls.package_root = output / "prepare-timeout-evidence-physical-d2-execution-package"
            cls.request = json.loads((output / "PHYSICAL_D2_REQUEST_07.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        if cls.temp:
            cls.temp.cleanup()

    def require_package(self):
        if self.package_root is None:
            self.skipTest("PR200_REVIEW_ARTIFACT not supplied")

    def test_01_successor_identity(self):
        self.assertTrue(contract.REQUEST_07_ID.endswith("-07"))
        self.assertEqual(contract.D2_06_STATUS, "CONSUMED_FAILED")
        self.assertEqual(contract.D2_06_FAILURE_CODE, "PREPARE_RESULT_TIMEOUT")

    def test_02_source_contract_inert(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS / "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_contract_20260729_v1.py")],
            check=True,
            capture_output=True,
            text=True,
        )
        value = json.loads(result.stdout)
        self.assertFalse(value["physical_request_created"])
        self.assertFalse(value["physical_authorization_created"])
        self.assertFalse(value["board_operation"])

    def test_03_classification_set_exact(self):
        self.assertEqual(
            contract.CLASSIFICATIONS,
            ("NO_RESULT", "SERIAL_RESET", "BROKER_DISCONNECT", "LATE_RESULT", "UNRECOGNIZED_RESULT"),
        )
        self.assertEqual(contract.LATE_RESULT_OBSERVATION_WINDOW_SECONDS, 5)

    def test_04_runtime_constructed_identifiers_redacted(self):
        private_address = ".".join(("192", "168", "7", "19"))
        hardware_id = ":".join(("aa", "bb", "cc", "dd", "ee", "ff"))
        raw = "peer=" + private_address + " mac=" + hardware_id + " password=synthetic"
        text = recorder.redact_text(raw)
        self.assertNotIn(private_address, text)
        self.assertNotIn(hardware_id, text)
        self.assertNotIn("synthetic", text)

    def test_05_package_validates(self):
        self.require_package()
        package = contract.validate_execution_package(self.package_root)
        self.assertRegex(package["package_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(package["evidence"]["persist_before_recovery"])

    def test_06_request_frozen_unauthorized(self):
        self.require_package()
        value = contract.validate_physical_request(self.request, self.package_root)
        self.assertFalse(value["authorized"])
        self.assertFalse(value["authorization_created"])
        self.assertFalse(value["physical_execution_started"])
        self.assertFalse(value["replay_permitted"])

    def test_07_payloads_unchanged(self):
        self.require_package()
        self.assertEqual(self.request["immutable_payload_tar_sha256"], contract.IMMUTABLE_PAYLOAD_TAR_SHA256)
        self.assertEqual(self.request["recovery_payload_tar_sha256"], contract.RECOVERY_PAYLOAD_TAR_SHA256)

    def _authorization(self) -> dict:
        assert self.request is not None and self.package_root is not None
        now = datetime(2026, 7, 29, 3, 0, tzinfo=timezone.utc)
        value = {
            **contract.authorization_contract_required(self.request, self.package_root),
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "activate_authorized": False,
            "cleanup_authorized": False,
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
        }
        value["authorization_record_sha256"] = contract.canonical_sha256(value)
        return value

    def test_08_valid_authorization_contract_passes(self):
        self.require_package()
        authorization = self._authorization()
        checked = contract.validate_authorization_contract(
            authorization,
            self.request,
            self.package_root,
            now=datetime(2026, 7, 29, 3, 10, tzinfo=timezone.utc),
        )
        self.assertTrue(checked["authorized"])

    def test_09_predecessor_authorization_rejected(self):
        self.require_package()
        authorization = self._authorization()
        authorization["d2_request_id"] = contract.D2_06_ID
        authorization.pop("authorization_record_sha256")
        authorization["authorization_record_sha256"] = contract.canonical_sha256(authorization)
        with self.assertRaises(contract.ContractError):
            contract.validate_authorization_contract(
                authorization,
                self.request,
                self.package_root,
                now=datetime(2026, 7, 29, 3, 10, tzinfo=timezone.utc),
            )

    def test_10_contract_check_is_local_only(self):
        self.require_package()
        authorization = self._authorization()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auth = root / "auth.json"
            result = root / "check.json"
            auth.write_text(json.dumps(authorization, sort_keys=True) + "\n", encoding="utf-8")
            os.chmod(auth, 0o600)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(self.package_root / "h3_n2_stage2d9r_g3r_prepare_timeout_evidence_physical_d2_wrapper_20260729_v1.py"),
                    "contract-check",
                    "--package-root", str(self.package_root),
                    "--physical-request", str(Path(self.package_root).parent / "PHYSICAL_D2_REQUEST_07.json"),
                    "--authorization-record", str(auth),
                    "--result-output", str(result),
                    "--now", "2026-07-29T03:10:00Z",
                ],
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            value = json.loads(completed.stdout)
            self.assertEqual(value["status"], "PASS")
            self.assertFalse(value["board_operation"])
            self.assertFalse(value["network_operation"])

    def test_11_no_physical_authorization_file(self):
        self.require_package()
        output = self.package_root.parent
        names = {path.name for path in output.rglob("*") if path.is_file()}
        self.assertFalse(any("AUTHORIZATION_07" in name or "authorization-07" in name for name in names))

    def test_12_evidence_sources_bound(self):
        self.require_package()
        binding = json.loads((self.package_root / "PREPARE_TIMEOUT_EVIDENCE_EXECUTION_PACKAGE_BINDING.json").read_text())
        for key in ("evidence_recorder_sha256", "evidence_overlay_sha256", "evidence_contract_sha256"):
            self.assertRegex(binding[key], r"^[0-9a-f]{64}$")

    def test_13_recovery_scope_remains_limited(self):
        self.require_package()
        self.assertEqual(self.request["locked_recovery_scope"], "TEST_PARTITION_ONLY")
        self.assertEqual(self.request["locked_recovery_max_count"], 1)

    def test_14_request_binding_recomputes(self):
        self.require_package()
        value = dict(self.request)
        observed = value.pop("request_binding_sha256")
        self.assertEqual(observed, contract.canonical_sha256(value))


if __name__ == "__main__":
    unittest.main()
