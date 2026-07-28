#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

import h3_n2_stage2d9r_g3r_execution_closure_binding_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_execution_closure_binding_packager_20260728_v1 as packager


class ExecutionClosureBindingTests(unittest.TestCase):
    def make_execution_root(self, repository_head: str = "a" * 40) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / "runtime.py").write_text("print('ok')\n", encoding="utf-8")
        (root / "launcher.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        manifest = contract.build_execution_closure_manifest(root)
        (root / contract.CLOSURE_MANIFEST_FILE).write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        binding = {
            "schema": contract.EXECUTION_BINDING_SCHEMA,
            "repository_head_sha_at_package_build": repository_head,
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "execution_closure_sha256": manifest["execution_closure_sha256"],
            "execution_closure_role": "BLOCKING",
        }
        (root / contract.EXECUTION_BINDING_FILE).write_text(
            json.dumps(binding, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        return root

    def host_authorization(self, review_binding: dict[str, object], repository_head: str) -> dict[str, object]:
        now = datetime.now(timezone.utc)
        value: dict[str, object] = {
            "schema": contract.HOST_AUTH_SCHEMA,
            "authorization_id": contract.FUTURE_HOST_AUTHORIZATION_ID,
            "operation": contract.HOST_AUTH_OPERATION,
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            "repository_head_sha": repository_head,
            "repository_head_role": "AUDIT_ONLY",
            "repository_head_enforced": False,
            "non_execution_drift_files": ["README.md"],
            "source_sha": review_binding["source_sha"],
            "base_pr": contract.BASE_PR,
            "base_head_sha": contract.BASE_HEAD_SHA,
            "review_binding_sha256": review_binding["review_binding_sha256"],
            "review_archive_sha256": "1" * 64,
            "execution_package_sha256": "2" * 64,
            "execution_closure_sha256": "3" * 64,
            "execution_closure_role": "BLOCKING",
            "execution_closure_policy_version": 1,
            "upstream_artifact_id": contract.UPSTREAM_ARTIFACT_ID,
            "upstream_artifact_sha256": contract.UPSTREAM_ARTIFACT_SHA256,
            "previous_request_id": contract.PREVIOUS_REQUEST_ID,
            "previous_request_state": contract.PREVIOUS_REQUEST_STATE,
            "new_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
        }
        for key in (
            "board_operation_authorized", "usb_enumeration_authorized", "serial_operation_authorized",
            "esptool_operation_authorized", "flash_operation_authorized", "physical_nvs_operation_authorized",
            "network_operation_authorized", "broker_operation_authorized", "prepare_authorized",
            "verify_authorized", "activate_authorized", "cleanup_authorized", "ready_authorized",
            "merge_authorized", "release_authorized", "tag_authorized", "deployment_authorized",
        ):
            value[key] = False
        value["authorization_record_sha256"] = contract.canonical_json_sha256(value)
        return value

    def test_01_source_contract_is_inert_and_head_is_audit_only(self) -> None:
        value = contract.source_contract("c" * 40)
        self.assertEqual(value["state"], "EXECUTION_CLOSURE_BINDING_SOURCE_FROZEN_UNAUTHORIZED")
        self.assertEqual(value["repository_head_role"], "AUDIT_ONLY")
        self.assertFalse(value["repository_head_enforced"])
        self.assertEqual(value["execution_closure_role"], "BLOCKING")
        self.assertFalse(value["authorized"])

    def test_02_execution_closure_validates(self) -> None:
        root = self.make_execution_root()
        value = contract.validate_execution_closure(root)
        self.assertEqual(value["manifest"]["execution_closure_role"], "BLOCKING")

    def test_03_repository_head_change_does_not_change_closure(self) -> None:
        first = self.make_execution_root("a" * 40)
        second = self.make_execution_root("b" * 40)
        first_value = contract.validate_execution_closure(first)
        second_value = contract.validate_execution_closure(second)
        self.assertEqual(
            first_value["manifest"]["execution_closure_sha256"],
            second_value["manifest"]["execution_closure_sha256"],
        )

    def test_04_runtime_tamper_is_rejected(self) -> None:
        root = self.make_execution_root()
        (root / "runtime.py").write_text("print('tampered')\n", encoding="utf-8")
        with self.assertRaisesRegex(contract.ContractError, "EXECUTION_CLOSURE_MEMBER_DIGEST_MISMATCH"):
            contract.validate_execution_closure(root)

    def test_05_extra_runtime_file_is_rejected(self) -> None:
        root = self.make_execution_root()
        (root / "unexpected.py").write_text("pass\n", encoding="utf-8")
        with self.assertRaisesRegex(contract.ContractError, "EXECUTION_CLOSURE_INVENTORY_MISMATCH"):
            contract.validate_execution_closure(root)

    def test_06_repository_head_can_drift_in_host_authorization(self) -> None:
        review = {"source_sha": "d" * 40, "review_binding_sha256": "e" * 64}
        auth = self.host_authorization(review, "f" * 40)
        validated = contract.validate_host_authorization(
            auth,
            review_binding=review,
            review_archive_sha256="1" * 64,
            execution_package_sha256="2" * 64,
            execution_closure_sha256="3" * 64,
        )
        self.assertEqual(validated["repository_head_sha"], "f" * 40)

    def test_07_repository_head_cannot_be_promoted_to_blocking(self) -> None:
        review = {"source_sha": "d" * 40, "review_binding_sha256": "e" * 64}
        auth = self.host_authorization(review, "f" * 40)
        auth["repository_head_enforced"] = True
        auth_without = dict(auth)
        auth_without.pop("authorization_record_sha256", None)
        auth["authorization_record_sha256"] = contract.canonical_json_sha256(auth_without)
        with self.assertRaisesRegex(contract.ContractError, "REPOSITORY_HEAD_ENFORCEMENT_INVALID"):
            contract.validate_host_authorization(
                auth,
                review_binding=review,
                review_archive_sha256="1" * 64,
                execution_package_sha256="2" * 64,
                execution_closure_sha256="3" * 64,
            )

    def test_08_request_stays_unauthorized_after_host_finalization(self) -> None:
        draft = contract.build_request_draft(
            source_sha="1" * 40,
            review_binding_sha256="2" * 64,
            execution_package_sha256="3" * 64,
            execution_closure_sha256="4" * 64,
            execution_wrapper_sha256="5" * 64,
            execution_launcher_sha256="6" * 64,
            previous_request_raw_sha256="7" * 64,
        )
        final = contract.finalize_request(draft, "8" * 64)
        self.assertFalse(final["authorized"])
        self.assertIsNotNone(final["request_binding_sha256"])
        self.assertIsNone(final["issued_at"])

    def test_09_previous_request_is_permanently_non_reusable(self) -> None:
        value = contract.previous_request_disposition("9" * 64)
        self.assertEqual(value["state"], contract.PREVIOUS_REQUEST_STATE)
        self.assertFalse(value["request_reuse_permitted"])
        self.assertFalse(value["physical_execution_occurred"])

    def test_10_wrapper_is_inert_without_authorization(self) -> None:
        wrapper = TOOLS / "h3_n2_stage2d9r_g3r_execution_closure_bound_final_physical_d2_wrapper_20260728_v1.py"
        completed = subprocess.run(
            [sys.executable, str(wrapper)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        value = json.loads(completed.stdout)
        self.assertEqual(value["repository_head_role"], "AUDIT_ONLY")
        self.assertFalse(value["repository_head_enforced"])
        self.assertFalse(value["board_operation"])
        self.assertFalse(value["network_operation"])

    def test_11_real_upstream_artifact_when_available(self) -> None:
        path = os.environ.get("STAGE2D9R_EXECUTION_CLOSURE_UPSTREAM_ARTIFACT_ZIP")
        if not path:
            self.skipTest("real upstream artifact not provided")
        files, previous_request_sha = packager.validate_upstream_artifact(Path(path))
        self.assertIn(packager.UPSTREAM_REVIEW_BINDING_FILE, files)
        self.assertRegex(previous_request_sha, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
