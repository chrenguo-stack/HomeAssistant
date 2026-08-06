from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


def load_module() -> ModuleType:
    path = Path(__file__).parents[1] / "c06_fault_matrix_evidence.py"
    spec = importlib.util.spec_from_file_location("c06_fault_matrix_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load C06 fault-matrix evidence module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


class C06FaultMatrixEvidenceTests(unittest.TestCase):
    def arguments(self, root: Path) -> argparse.Namespace:
        return argparse.Namespace(
            input_dir=str(root),
            output=str(root / "report.json"),
            authorization="D1-C06B3-test",
            source_ref="feature/test",
            source_sha="a" * 40,
            base_ref="feature/base",
            base_sha="b" * 40,
            execution_exit_code=0,
            exact_base_verified=True,
            base_ancestor_verified=True,
            authorized_file_boundary_verified=True,
        )

    def write_documents(self, root: Path) -> None:
        documents = {
            "execution.json": {"status": "passed"},
            "images.json": {},
            "prepare.json": {},
            "manager-db-init.json": {},
            "observer-ready.json": {},
            "mqtt-capture.json": {},
            "initial.json": {},
            "fault-seed.json": {
                "revision": 2,
                "state": "pending",
                "attempts": 0,
            },
            "fault-retry.json": {
                "revision": 2,
                "state": "retry",
                "attempts": 1,
                "retry_fail_closed": True,
            },
            "fault-recovery.json": {
                "revision": 2,
                "manager_job_state": "completed",
                "target_ledger_state": "verified",
                "recorder_readback_exact": True,
                "durable_retry_reconciled": True,
            },
            "fault-broker-restart.json": {
                "broker_restarted": True,
                "mqtt_clients_reconnected": True,
                "same_revision_idempotent_status": "verified",
                "projection_hash_exact": True,
                "result_qos": 1,
                "result_retain": False,
            },
            "cleanup.json": {
                "cleanup_complete": True,
                "remaining_test_containers": 0,
                "remaining_test_volumes": 0,
                "remaining_test_networks": 0,
                "host_ports_published": 0,
            },
        }
        for name, document in documents.items():
            document.update(
                {
                    "production_state_modified": False,
                    "production_services_modified": False,
                    "secret_values_included": False,
                }
            )
            (root / name).write_text(json.dumps(document), encoding="utf-8")

    def test_passes_only_with_complete_safe_fault_closure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_documents(root)
            report = MODULE.build_report(self.arguments(root))
        self.assertEqual(report["status"], "passed")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["missing_evidence_files"], [])

    def test_fails_closed_when_retry_or_cleanup_is_not_proven(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_documents(root)
            (root / "fault-retry.json").write_text(
                json.dumps({"state": "completed", "secret_values_included": False}),
                encoding="utf-8",
            )
            (root / "cleanup.json").unlink()
            report = MODULE.build_report(self.arguments(root))
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["checks"]["homeassistant_outage_produced_retry"])
        self.assertIn("cleanup.json", report["missing_evidence_files"])


if __name__ == "__main__":
    unittest.main()
