#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_main_drift_successor_rebind_contract_20260728_v1 as contract
import h3_n2_stage2d9r_g3r_main_drift_successor_rebind_packager_20260728_v1 as packager
import h3_n2_stage2d9r_g3r_main_drift_successor_rebind_probe_20260728_v1 as probe

SOURCE_SHA = "7" * 40


class MainDriftSuccessorRebindTests(unittest.TestCase):
    def upstream_artifact(self) -> Path:
        value = os.environ.get("STAGE2D9R_MAIN_DRIFT_UPSTREAM_ARTIFACT_ZIP")
        if not value:
            self.skipTest("exact upstream Artifact not supplied")
        return Path(value).resolve(strict=True)

    def evidence(self) -> tuple[Path, Path]:
        h2 = os.environ.get("STAGE2D9R_H2_RESULT_JSON")
        old = os.environ.get("STAGE2D9R_OLD_REQUEST_JSON")
        if not h2 or not old:
            self.skipTest("exact operator-host public evidence not supplied")
        return Path(h2).resolve(strict=True), Path(old).resolve(strict=True)

    def test_01_source_contract_freezes_accepted_drift(self) -> None:
        value = contract.source_contract(SOURCE_SHA)
        self.assertEqual(value["state"], "MAIN_DRIFT_SUCCESSOR_REBIND_SOURCE_FROZEN_UNAUTHORIZED")
        self.assertEqual(value["base_pr"], 193)
        self.assertEqual(value["base_head_sha"], contract.BASE_HEAD_SHA)
        self.assertEqual(value["previous_accepted_main_sha"], contract.PREVIOUS_ACCEPTED_MAIN_SHA)
        self.assertEqual(value["accepted_current_main_sha"], contract.ACCEPTED_CURRENT_MAIN_SHA)
        self.assertEqual(value["main_drift_changed_files"], ["README.md"])
        self.assertEqual(value["h2_status"], "CONSUMED_PASS")
        self.assertFalse(value["h2_replay_permitted"])
        self.assertFalse(value["authorized"])
        self.assertFalse(value["board_operation"])

    def test_02_old_request_is_permanently_stale_before_authorization(self) -> None:
        value = contract.stale_request_disposition()
        self.assertEqual(value["d2_request_id"], contract.OLD_PHYSICAL_D2_REQUEST_ID)
        self.assertEqual(value["state"], "STALE_MAIN_DRIFT_BEFORE_AUTHORIZATION")
        self.assertFalse(value["authorization_created"])
        self.assertFalse(value["authorization_claimed"])
        self.assertFalse(value["authorization_consumed"])
        self.assertFalse(value["request_reuse_permitted"])
        self.assertFalse(value["physical_execution_occurred"])

    def test_03_new_request_draft_is_unauthorized_and_uses_03_identity(self) -> None:
        value = contract.build_request_draft(
            source_sha=SOURCE_SHA,
            review_binding_sha256="1" * 64,
            execution_package_sha256="2" * 64,
            execution_wrapper_sha256="3" * 64,
            execution_launcher_sha256="4" * 64,
        )
        self.assertEqual(value["d2_request_id"], contract.NEW_PHYSICAL_D2_REQUEST_ID)
        self.assertEqual(value["previous_request_state"], contract.OLD_PHYSICAL_D2_REQUEST_STATE)
        self.assertEqual(value["main_sha"], contract.ACCEPTED_CURRENT_MAIN_SHA)
        self.assertIsNone(value["host_rebind_result_sha256"])
        self.assertIsNone(value["request_binding_sha256"])
        self.assertFalse(value["authorized"])

    def test_04_wrapper_only_rebinds_main_and_request_identity(self) -> None:
        text = (TOOLS / packager.NEW_WRAPPER).read_text(encoding="utf-8")
        self.assertIn("physical_payload_handoff_repair_wrapper", text)
        self.assertIn("NEW_PHYSICAL_D2_REQUEST_ID", text)
        self.assertIn("ACCEPTED_CURRENT_MAIN_SHA", text)
        self.assertIn("PREVIOUS_REQUEST", text.upper())
        self.assertNotIn("write_flash", text)
        self.assertNotIn("erase_flash", text)
        self.assertNotIn("list_ports", text)
        self.assertNotIn("serial.Serial", text)

    def test_05_launcher_preserves_tar_and_extraction_root_role_separation(self) -> None:
        text = packager.launcher_bytes().decode("utf-8")
        self.assertIn(f'--immutable-payload-tar "$PKG/{packager.IMMUTABLE_TAR}"', text)
        self.assertIn('--immutable-root "$IMM"', text)
        self.assertIn(f'--recovery-payload-tar "$PKG/{packager.RECOVERY_TAR}"', text)
        self.assertIn('--recovery-root "$REC"', text)
        self.assertIn(packager.NEW_WRAPPER, text)
        self.assertNotEqual(packager.IMMUTABLE_TAR, "immutable-extracted")
        self.assertNotEqual(packager.RECOVERY_TAR, "recovery-extracted")

    def test_06_host_probe_has_no_physical_or_network_implementation(self) -> None:
        text = (TOOLS / packager.HOST_PROBE).read_text(encoding="utf-8")
        for token in (
            "list_ports.comports", "serial.Serial", "import serial", "import socket",
            "subprocess.Popen", "subprocess.run", "esptool.main", "write_flash",
            "erase_flash", "mosquitto", "GH2D9R_PREPARE", "GH2D9R_VERIFY",
        ):
            self.assertNotIn(token, text)

    def test_07_exact_upstream_artifact_and_deterministic_two_lane_packages(self) -> None:
        artifact = self.upstream_artifact()
        packager.validate_upstream_artifact(artifact)
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a"
            b = Path(tmp) / "b"
            ra = packager.build(ROOT, artifact, a, SOURCE_SHA)
            rb = packager.build(ROOT, artifact, b, SOURCE_SHA)
            self.assertEqual(ra, rb)
            files_a = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
            files_b = {p.relative_to(b).as_posix(): p.read_bytes() for p in b.rglob("*") if p.is_file()}
            self.assertEqual(files_a, files_b)
            self.assertEqual(
                (a / packager.EXECUTION_DIR / packager.IMMUTABLE_TAR).read_bytes(),
                (b / packager.EXECUTION_DIR / packager.IMMUTABLE_TAR).read_bytes(),
            )
            self.assertEqual(
                (a / packager.EXECUTION_DIR / packager.RECOVERY_TAR).read_bytes(),
                (b / packager.EXECUTION_DIR / packager.RECOVERY_TAR).read_bytes(),
            )

    def test_08_exact_h2_and_old_request_public_evidence(self) -> None:
        h2_path, old_path = self.evidence()
        self.assertEqual(packager.sha256_file(h2_path), contract.H2_RESULT_RAW_SHA256)
        self.assertEqual(packager.sha256_file(old_path), contract.OLD_REQUEST_RAW_SHA256)
        h2 = contract.validate_h2_result(json.loads(h2_path.read_text(encoding="utf-8")))
        old = contract.validate_old_request(json.loads(old_path.read_text(encoding="utf-8")))
        self.assertEqual(h2["status"], "CONSUMED_PASS")
        self.assertFalse(h2["replay_permitted"])
        self.assertFalse(old["authorization_created"])
        self.assertEqual(old["request_binding_sha256"], contract.OLD_REQUEST_BINDING_SHA256)

    def test_09_authorized_host_only_rebind_emits_unauthorized_03_request_and_rejects_replay(self) -> None:
        artifact = self.upstream_artifact()
        h2_source, old_source = self.evidence()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package"
            packager.build(ROOT, artifact, package, SOURCE_SHA)
            binding, _draft, digests = probe.validate_package(package)
            h2 = root / "h2.json"
            old = root / "old.json"
            shutil.copyfile(h2_source, h2)
            shutil.copyfile(old_source, old)
            os.chmod(h2, 0o600)
            os.chmod(old, 0o600)
            state = root / "state"
            state.mkdir(mode=0o700)
            now = datetime.now(timezone.utc).replace(microsecond=0)
            authorization = {
                "schema": contract.AUTH_SCHEMA,
                "authorization_id": contract.FUTURE_HOST_REBIND_AUTHORIZATION_ID,
                "operation": probe.AUTH_OPERATION,
                "authorized": True,
                "one_shot": True,
                "replay_permitted": False,
                "automatic_retry_permitted": False,
                "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
                "source_sha": SOURCE_SHA,
                "base_pr": contract.BASE_PR,
                "base_head_sha": contract.BASE_HEAD_SHA,
                "previous_accepted_main_sha": contract.PREVIOUS_ACCEPTED_MAIN_SHA,
                "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
                "main_drift_commit_sha": contract.MAIN_DRIFT_COMMIT_SHA,
                "review_binding_sha256": binding["review_binding_sha256"],
                "review_archive_sha256": digests["review_archive_sha256"],
                "execution_package_sha256": digests["execution_package_sha256"],
                "h2_authorization_id": contract.H2_AUTHORIZATION_ID,
                "h2_result_raw_sha256": contract.H2_RESULT_RAW_SHA256,
                "h2_result_sha256": contract.H2_RESULT_CANONICAL_SHA256,
                "old_request_id": contract.OLD_PHYSICAL_D2_REQUEST_ID,
                "old_request_raw_sha256": contract.OLD_REQUEST_RAW_SHA256,
                "old_request_binding_sha256": contract.OLD_REQUEST_BINDING_SHA256,
                "new_physical_d2_request_id": contract.NEW_PHYSICAL_D2_REQUEST_ID,
                "board_operation_authorized": False,
                "usb_enumeration_authorized": False,
                "serial_operation_authorized": False,
                "esptool_operation_authorized": False,
                "flash_operation_authorized": False,
                "physical_nvs_operation_authorized": False,
                "network_operation_authorized": False,
                "broker_operation_authorized": False,
                "prepare_authorized": False,
                "verify_authorized": False,
                "activate_authorized": False,
                "cleanup_authorized": False,
                "ready_authorized": False,
                "merge_authorized": False,
                "release_authorized": False,
                "tag_authorized": False,
                "deployment_authorized": False,
            }
            authorization["authorization_record_sha256"] = contract.canonical_json_sha256(authorization)
            auth_path = root / "authorization.json"
            auth_path.write_text(json.dumps(authorization, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            os.chmod(auth_path, 0o600)
            args = type("Args", (), {
                "package_root": package,
                "authorization": auth_path,
                "h2_result": h2,
                "old_request": old,
                "state_root": state,
                "result_output": root / "result.json",
                "request_output": root / "request.json",
            })()
            result, request = probe.execute(args)
            self.assertEqual(result["status"], "CONSUMED_PASS")
            self.assertEqual(request["d2_request_id"], contract.NEW_PHYSICAL_D2_REQUEST_ID)
            self.assertEqual(request["main_sha"], contract.ACCEPTED_CURRENT_MAIN_SHA)
            self.assertEqual(request["previous_request_state"], contract.OLD_PHYSICAL_D2_REQUEST_STATE)
            self.assertFalse(request["authorized"])
            self.assertFalse(request["authorization_created"])
            marker = json.loads(probe.marker_path(state).read_text(encoding="utf-8"))
            self.assertEqual(marker["status"], "CONSUMED_PASS")
            with self.assertRaisesRegex(probe.ProbeError, "AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED"):
                probe.execute(args)


if __name__ == "__main__":
    unittest.main()
