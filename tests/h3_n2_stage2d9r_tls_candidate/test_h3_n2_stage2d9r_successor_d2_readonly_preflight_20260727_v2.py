#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_readonly_preflight_20260727_v2.py"
SPEC = importlib.util.spec_from_file_location("stage2d9r_d2_preflight_v2_test", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
D = "b" * 64
SOURCE = "a" * 40
RECOVERY_ACCEPTANCE = ROOT / "docs" / "acceptance" / "h3-n2-stage2d9r-successor-locked-recovery-artifact-l1-v1.json"
EXECUTION_ACCEPTANCE = ROOT / "docs" / "acceptance" / "h3-n2-stage2d9r-successor-d2-execution-package-l1-v1.json"


class PreflightV2Tests(unittest.TestCase):
    def state_files(self, root: Path) -> tuple[Path, Path]:
        recovery = root / "recovery-state.json"
        execution = root / "execution-state.json"
        recovery.write_text(json.dumps({
            "schema": MODULE.RECOVERY_STATE_SCHEMA,
            "id": MODULE.RECOVERY_ARTIFACT_ID,
            "digest_sha256": MODULE.RECOVERY_ARTIFACT_DIGEST,
            "source_sha": MODULE.RECOVERY_SOURCE_SHA,
            "expired": False,
            "accessible": True,
        }), encoding="utf-8")
        execution.write_text(json.dumps({
            "schema": MODULE.EXECUTION_STATE_SCHEMA,
            "id": MODULE.EXECUTION_ARTIFACT_ID,
            "digest_sha256": MODULE.EXECUTION_ARTIFACT_DIGEST,
            "source_sha": MODULE.EXECUTION_SOURCE_SHA,
            "expired": False,
            "accessible": True,
        }), encoding="utf-8")
        return recovery, execution

    def args(self, root: Path) -> SimpleNamespace:
        recovery_state, execution_state = self.state_files(root)
        return SimpleNamespace(
            recovery_acceptance=RECOVERY_ACCEPTANCE,
            execution_acceptance=EXECUTION_ACCEPTANCE,
            recovery_artifact_state=recovery_state,
            execution_artifact_state=execution_state,
            execution_package_sha256=MODULE.EXECUTION_PACKAGE_SHA256,
            execution_script_sha256=MODULE.EXECUTION_SCRIPT_SHA256,
            execution_launcher_sha256=MODULE.EXECUTION_LAUNCHER_SHA256,
            execution_marker_name_sha256=MODULE.EXECUTION_MARKER_NAME_SHA256,
            locked_recovery_package_sha256=MODULE.RECOVERY_PAYLOAD_SHA256,
            review_artifact_id=1,
            review_artifact_digest_sha256=D,
            public_preflight_artifact_id=2,
            public_preflight_artifact_digest_sha256=D,
            board_identity_sha256=D,
            serial_identity_sha256=D,
            baseline_state_sha256=D,
            issued_at="2026-07-27T00:00:00Z",
            expires_at="2026-07-27T02:00:00Z",
        )

    def test_frozen_acceptance_records_validate(self) -> None:
        recovery = MODULE.validate_recovery_acceptance(
            json.loads(RECOVERY_ACCEPTANCE.read_text())
        )
        execution = MODULE.validate_execution_acceptance(
            json.loads(EXECUTION_ACCEPTANCE.read_text())
        )
        self.assertEqual(recovery["id"], MODULE.RECOVERY_ARTIFACT_ID)
        self.assertEqual(execution["id"], MODULE.EXECUTION_ARTIFACT_ID)
        self.assertEqual(
            execution["execution_package_sha256"],
            MODULE.EXECUTION_PACKAGE_SHA256,
        )

    def test_arbitrary_execution_digest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            args = self.args(Path(td))
            args.execution_package_sha256 = D
            with self.assertRaisesRegex(
                MODULE.PreflightV2Error, "EXACT_EXECUTION_PACKAGE_SHA256_MISMATCH"
            ):
                MODULE.validate_exact_arguments(args)

    def test_expired_recovery_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            args = self.args(root)
            value = json.loads(args.recovery_artifact_state.read_text())
            value["expired"] = True
            args.recovery_artifact_state.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.PreflightV2Error, "RECOVERY_ARTIFACT_STATE_EXPIRED"
            ):
                MODULE.validate_frozen_artifact_state(
                    MODULE.load_json(args.recovery_artifact_state),
                    schema=MODULE.RECOVERY_STATE_SCHEMA,
                    artifact_id=MODULE.RECOVERY_ARTIFACT_ID,
                    digest=MODULE.RECOVERY_ARTIFACT_DIGEST,
                    source_sha=MODULE.RECOVERY_SOURCE_SHA,
                    prefix="RECOVERY_ARTIFACT",
                )

    def test_augmented_preflight_rebuilds_unauthorized_exact_request(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            args = self.args(Path(td))
            original = MODULE.V1.run
            MODULE.V1.run = lambda _args: {
                "preflight": {
                    "schema": "gh.h3.n2.stage2d9r-successor-d2-read-only-preflight-result/1",
                    "repository_state": {
                        "source_sha": SOURCE,
                        "main_sha": MODULE.V1.CONTRACT.EXPECTED_MAIN_SHA,
                    },
                    "review_binding_sha256": D,
                    "u1_02": {"consumed_marker_sha256": D},
                    "preflight_result_sha256": D,
                    "authorization_created": False,
                    "authorization_claimed": False,
                    "board_operation": False,
                    "serial_operation": False,
                    "flash_operation": False,
                },
                "exact_request": {"discarded_v1": True},
            }
            try:
                result = MODULE.run(args)
            finally:
                MODULE.V1.run = original
            preflight = result["preflight"]
            request = result["exact_request"]
            self.assertEqual(
                preflight["schema"],
                "gh.h3.n2.stage2d9r-successor-d2-read-only-preflight-result/2",
            )
            self.assertFalse(
                preflight["arbitrary_recovery_or_execution_digest_accepted"]
            )
            self.assertEqual(
                request["private_preflight_result_sha256"],
                preflight["preflight_result_sha256"],
            )
            self.assertEqual(
                request["execution_package_sha256"],
                MODULE.EXECUTION_PACKAGE_SHA256,
            )
            self.assertEqual(
                request["locked_recovery_package_sha256"],
                MODULE.RECOVERY_PAYLOAD_SHA256,
            )
            self.assertFalse(request["authorized"])

    def test_acceptance_authorization_expansion_fails(self) -> None:
        value = json.loads(EXECUTION_ACCEPTANCE.read_text())
        value["protected_boundaries"]["execution_authorized"] = True
        with self.assertRaisesRegex(
            MODULE.PreflightV2Error, "EXECUTION_ACCEPTANCE_BOUNDARY_EXPANDED"
        ):
            MODULE.validate_execution_acceptance(value)


if __name__ == "__main__":
    unittest.main()
