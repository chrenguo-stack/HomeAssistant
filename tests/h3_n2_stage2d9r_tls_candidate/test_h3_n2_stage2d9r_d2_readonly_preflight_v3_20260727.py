#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_d2_readonly_preflight_v3_20260727.py"
SPEC = importlib.util.spec_from_file_location("stage2d9r_d2_preflight_v3_test", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

D = "b" * 64
SOURCE = "a" * 40


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


class D2ReadonlyPreflightV3Tests(unittest.TestCase):
    def baseline_result(self, root: Path) -> Path:
        value = {
            "schema": MODULE.BASELINE_RESULT_SCHEMA,
            "stage": MODULE.V2.V1.CONTRACT.STAGE,
            "d1_decision_id": (
                "D1-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-GATE-20260727-01"
            ),
            "authorization_id": MODULE.BASELINE_AUTHORIZATION_ID,
            "status": "CONSUMED_PASS",
            "board_identity_sha256": "1" * 64,
            "serial_identity_sha256": "2" * 64,
            "baseline_state_sha256": "3" * 64,
            "chip_id_output_sha256": "4" * 64,
            "flash_id_output_sha256": "5" * 64,
            "test_partition_sha256": "6" * 64,
            "test_partition_size": 0x10000,
            "allowed_operations_observed": [],
            "authorization_consumed": True,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "board_write_operation": False,
            "flash_erase_operation": False,
            "flash_write_operation": False,
            "flash_verify_operation": False,
            "physical_nvs_operation": False,
            "network_operation": False,
            "broker_started": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "secret_values_included": False,
            "private_paths_included": False,
        }
        value["result_sha256"] = MODULE.V2.V1.sha256_bytes(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        )
        path = root / "baseline.json"
        write_json(path, value)
        return path

    def marker(self, root: Path) -> Path:
        path = root / "u1-consumed.json"
        write_json(
            path,
            {
                "authorization_id": MODULE.V2.V1.CONTRACT.U1_02_ID,
                "status": "CONSUMED",
                "record_sha256": MODULE.V2.V1.U1_02_RECORD_SHA256,
                "execution_result_sha256": MODULE.V2.V1.U1_02_RESULT_SHA256,
                "one_shot": True,
                "replay_permitted": False,
                "automatic_retry_permitted": False,
                "secret_values_included": False,
                "private_paths_included": False,
            },
        )
        return path

    def test_marker_only_and_baseline_bind_v3_unauthorized_request(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            marker = self.marker(root)
            args = SimpleNamespace(
                baseline_readonly_result=self.baseline_result(root),
                u1_02_authorization_record=None,
                u1_02_result=None,
                u1_02_consumed_marker=marker,
                board_identity_sha256=None,
                serial_identity_sha256=None,
                baseline_state_sha256=None,
            )
            original_run = MODULE.V2.run
            original_rebuild = MODULE.rebuild_request

            def fake_v2_run(observed_args):
                u1 = MODULE.V2.V1.validate_u1_02(
                    observed_args.u1_02_authorization_record,
                    observed_args.u1_02_result,
                    observed_args.u1_02_consumed_marker,
                )
                return {
                    "preflight": {
                        "schema": "gh.h3.n2.stage2d9r-successor-d2-read-only-preflight-result/2",
                        "repository_state": {
                            "source_sha": SOURCE,
                            "main_sha": MODULE.V2.V1.CONTRACT.EXPECTED_MAIN_SHA,
                        },
                        "review_binding_sha256": D,
                        "u1_02": u1,
                        "preflight_result_sha256": D,
                    },
                    "exact_request": {"discarded": True},
                }

            MODULE.V2.run = fake_v2_run
            MODULE.rebuild_request = lambda _args, _preflight: {
                "authorized": False,
                "request_binding_sha256": D,
            }
            try:
                result = MODULE.run(args)
            finally:
                MODULE.V2.run = original_run
                MODULE.rebuild_request = original_rebuild

            self.assertEqual(
                result["preflight"]["schema"],
                "gh.h3.n2.stage2d9r-successor-d2-read-only-preflight-result/3",
            )
            self.assertEqual(
                result["preflight"]["u1_02"]["evidence_mode"],
                "CONSUMED_MARKER_ONLY",
            )
            self.assertEqual(args.board_identity_sha256, "1" * 64)
            self.assertEqual(args.serial_identity_sha256, "2" * 64)
            self.assertEqual(args.baseline_state_sha256, "3" * 64)
            self.assertFalse(result["exact_request"]["authorized"])

    def test_baseline_replay_expansion_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = self.baseline_result(Path(td))
            value = json.loads(path.read_text())
            value["replay_permitted"] = True
            value.pop("result_sha256")
            value["result_sha256"] = MODULE.V2.V1.sha256_bytes(
                json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            )
            write_json(path, value)
            with self.assertRaisesRegex(
                MODULE.PreflightV3Error,
                "BASELINE_RESULT_REPLAY_EXPANDED",
            ):
                MODULE.validate_baseline_result(path)


if __name__ == "__main__":
    unittest.main()
