#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_readonly_preflight_20260727_v1.py"
SPEC = importlib.util.spec_from_file_location("preflight", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = "a" * 40
D = "b" * 64

def write_json(path: Path, value: object, mode: int = 0o600) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.chmod(path, mode)

class PreflightTests(unittest.TestCase):
    def fixture(self, temp: Path) -> SimpleNamespace:
        contract = MODULE.CONTRACT.build_contract(SOURCE)
        review = {
            "schema": "gh.h3.n2.stage2d9r-successor-d2-review-binding/1",
            "stage": MODULE.CONTRACT.STAGE,
            "d2_request_id": MODULE.CONTRACT.D2_REQUEST_ID,
            "source_sha": SOURCE,
            "main_sha": MODULE.CONTRACT.EXPECTED_MAIN_SHA,
            "base_source_sha": MODULE.CONTRACT.BASE_SOURCE_SHA,
            "contract_binding_sha256": contract["contract_binding_sha256"],
            "review_binding_sha256": D,
            "exact_authorization_request_included": False,
            "authorization_record_included": False,
            "execution_launcher_included": False,
            "private_content_included": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "physical_nvs_operation": False,
            "network_operation": False,
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "production_operation": False,
        }
        repository = {
            "schema": "gh.h3.n2.stage2d9r-successor-d2-repository-state/1",
            "repository": MODULE.CONTRACT.REPOSITORY,
            "main_sha": MODULE.CONTRACT.EXPECTED_MAIN_SHA,
            "pull_request_180": {
                "state": "open", "draft": True, "merged": False, "mergeable": True,
                "head_sha": SOURCE, "base_sha": MODULE.CONTRACT.BASE_SOURCE_SHA,
            },
            "pull_request_176": {
                "state": "open", "draft": True, "merged": False, "mergeable": True,
                "head_sha": MODULE.CONTRACT.BASE_SOURCE_SHA,
            },
            "current_head_ci": {"total": 19, "completed_success": 19, "pending": 0, "failed": 0},
        }
        review_artifact = {
            "schema": "gh.h3.n2.stage2d9r-successor-d2-review-artifact-state/1",
            "id": 100, "digest_sha256": D, "source_sha": SOURCE,
            "expired": False, "accessible": True,
        }
        public_artifact = {
            "schema": "gh.h3.n2.stage2d9r-successor-d2-public-preflight-artifact-state/1",
            "id": 101, "digest_sha256": D, "source_sha": SOURCE,
            "expired": False, "accessible": True,
        }
        host = {
            "schema": "gh.h3.n2.stage2d9r-successor-host-artifact-custody-preauth-probe/1",
            "result": "PASS_READ_ONLY_PREAUTH",
            "python_executable_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["python_executable_sha256"],
            "immutable_artifact": {
                "source_sha": MODULE.CONTRACT.PUBLIC_BINDINGS["immutable_artifact_source_sha"],
                "build_binding": MODULE.CONTRACT.PUBLIC_BINDINGS["immutable_build_binding"],
                "payload_tar_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["immutable_payload_tar_sha256"],
                "application_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["immutable_application_sha256"],
                "merged_image_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["immutable_merged_image_sha256"],
                "candidate_digest_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["candidate_digest_sha256"],
                "ca_pem_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["ca_pem_sha256"],
            },
            "successor_private_custody": {
                "authorization_status": "CONSUMED",
                "private_descriptor_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["private_descriptor_sha256"],
                "private_package_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["private_package_sha256"],
                "public_descriptor_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["public_descriptor_sha256"],
                "candidate_digest_sha256": MODULE.CONTRACT.PUBLIC_BINDINGS["candidate_digest_sha256"],
                "private_material_content_read": False,
                "private_paths_included": False,
                "secret_values_included": False,
                "marker_modified": False,
            },
            "authorization_created": False,
            "authorization_claimed": False,
            "authorization_consumed_by_probe": False,
            "private_material_content_read": False,
            "private_paths_included": False,
            "secret_values_included": False,
            "repository_required": False,
            "network_operation": False,
            "broker_started": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "physical_nvs_operation": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "production_operation": False,
        }
        paths = {}
        for name, value in {
            "review": review,
            "repository": repository,
            "review_artifact": review_artifact,
            "public_artifact": public_artifact,
            "host": host,
        }.items():
            path = temp / f"{name}.json"
            write_json(path, value)
            paths[name] = path

        auth = temp / "authorization.json"
        result = temp / "result.json"
        auth.write_bytes(b'{"safe":"authorization"}\n')
        result.write_bytes(b'{"safe":"result"}\n')
        os.chmod(auth, 0o600)
        os.chmod(result, 0o600)
        MODULE.U1_02_RECORD_SHA256 = hashlib.sha256(auth.read_bytes()).hexdigest()
        MODULE.U1_02_RESULT_SHA256 = hashlib.sha256(result.read_bytes()).hexdigest()
        marker = temp / "consumed.json"
        write_json(marker, {
            "authorization_id": MODULE.CONTRACT.U1_02_ID,
            "status": "CONSUMED_PASS",
            "authorization_record_sha256": MODULE.U1_02_RECORD_SHA256,
            "result_sha256": MODULE.U1_02_RESULT_SHA256,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "secret_values_included": False,
            "private_paths_included": False,
        })
        home = temp / "home"
        home.mkdir()
        MODULE.EXPECTED_CUSTODY_ROOT_DIGEST = hashlib.sha256(
            str((home.resolve() / MODULE.CUSTODY_RELATIVE).resolve(strict=False)).encode()
        ).hexdigest()
        return SimpleNamespace(
            review_binding=paths["review"],
            repository_state=paths["repository"],
            review_artifact_state=paths["review_artifact"],
            review_artifact_id=100,
            review_artifact_digest_sha256=D,
            public_preflight_artifact_state=paths["public_artifact"],
            public_preflight_artifact_id=101,
            public_preflight_artifact_digest_sha256=D,
            host_probe_result=paths["host"],
            home=home,
            u1_02_authorization_record=auth,
            u1_02_result=result,
            u1_02_consumed_marker=marker,
            openssl_executable_sha256=MODULE.CONTRACT.PUBLIC_BINDINGS["openssl_executable_sha256"],
            board_identity_sha256=D,
            serial_identity_sha256=D,
            baseline_state_sha256=D,
            execution_package_sha256=D,
            execution_script_sha256=D,
            execution_launcher_sha256=D,
            execution_marker_name_sha256=D,
            locked_recovery_package_sha256=D,
            issued_at="2026-07-27T00:00:00Z",
            expires_at="2026-07-27T02:00:00Z",
        )

    def test_read_only_preflight_builds_unauthorized_exact_request(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            args = self.fixture(Path(td))
            result = MODULE.run(args)
            self.assertEqual(result["preflight"]["result"], "PASS_READ_ONLY_D2_PREFLIGHT")
            self.assertFalse(result["preflight"]["board_operation"])
            self.assertFalse(result["preflight"]["serial_operation"])
            self.assertFalse(result["exact_request"]["authorized"])
            self.assertEqual(result["exact_request"]["prepare_max_count"], 1)
            self.assertEqual(result["exact_request"]["verify_max_count"], 1)
            self.assertEqual(result["exact_request"]["isolated_broker_start_max_count"], 1)
            self.assertEqual(result["exact_request"]["baseline_state_sha256"], D)

    def test_ci_failure_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            args = self.fixture(Path(td))
            state = json.loads(args.repository_state.read_text())
            state["current_head_ci"]["failed"] = 1
            write_json(args.repository_state, state)
            with self.assertRaisesRegex(MODULE.PreflightError, "CI_NOT_TERMINAL_SUCCESS"):
                MODULE.run(args)

    def test_marker_replay_expansion_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            args = self.fixture(Path(td))
            marker = json.loads(args.u1_02_consumed_marker.read_text())
            marker["replay_permitted"] = True
            write_json(args.u1_02_consumed_marker, marker)
            with self.assertRaisesRegex(MODULE.PreflightError, "U1_02_MARKER_REPLAY_EXPANDED"):
                MODULE.run(args)

    def test_openssl_toolchain_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            args = self.fixture(Path(td))
            args.openssl_executable_sha256 = D
            with self.assertRaisesRegex(MODULE.PreflightError, "OPENSSL_TOOLCHAIN_MISMATCH"):
                MODULE.run(args)

    def test_live_board_identifier_format_required_without_live_access(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            args = self.fixture(Path(td))
            args.board_identity_sha256 = "bad"
            with self.assertRaisesRegex(MODULE.PreflightError, "BOARD_IDENTITY_SHA256_INVALID"):
                MODULE.run(args)

if __name__ == "__main__":
    unittest.main()
