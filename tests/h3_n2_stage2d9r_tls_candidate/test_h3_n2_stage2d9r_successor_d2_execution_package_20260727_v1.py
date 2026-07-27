#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "a" * 40


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PACK = load(
    "stage2d9r_successor_d2_packager_v2_test",
    ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_execution_packager_20260727_v2.py",
)
FREEZE = load(
    "stage2d9r_successor_d2_freeze_test",
    ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_execution_freeze_20260727_v1.py",
)
EXECUTOR = load(
    "stage2d9r_successor_d2_executor_test",
    ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py",
)
EXECUTOR_PATH = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py"
CONTRACT_PATH = ROOT / "docs" / "development" / "h3-n2-stage2d9r-successor-d2-execution-package-contract-20260727-v1.md"


class ExecutionPackageTests(unittest.TestCase):
    def build(self, root: Path, lane: str, run_id: int) -> Path:
        output = root / f"build-{lane}"
        PACK.V1.package(
            executor=EXECUTOR_PATH,
            contract=CONTRACT_PATH,
            output_dir=output,
            source_sha=SOURCE,
            lane=lane,
            artifact_name=f"stage2d9r-successor-d2-build-{lane}-v1",
            run_id=run_id,
        )
        return output

    def extract_payload(self, build: Path, output: Path) -> None:
        output.mkdir(mode=0o700)
        with tarfile.open(build / PACK.V1.PAYLOAD_NAME, "r") as archive:
            members = archive.getmembers()
            self.assertEqual({member.name for member in members}, FREEZE.EXPECTED_MEMBERS)
            archive.extractall(output, filter="data")
        for path in output.iterdir():
            os.chmod(path, 0o600)

    def test_two_clean_builds_freeze_byte_identically(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_a = self.build(root, "a", 1)
            build_b = self.build(root, "b", 2)
            self.assertEqual(
                (build_a / PACK.V1.PAYLOAD_NAME).read_bytes(),
                (build_b / PACK.V1.PAYLOAD_NAME).read_bytes(),
            )
            frozen = root / "frozen"
            result = FREEZE.freeze(build_a, build_b, frozen, SOURCE)
            self.assertEqual(result["state"], "D2_EXECUTION_PACKAGE_REPRODUCIBLE_AND_FROZEN")
            self.assertEqual(result["clean_build_count"], 2)
            self.assertTrue(result["payloads_byte_identical"])
            self.assertFalse(result["execution_authorized"])
            self.assertFalse(result["board_operation"])
            self.assertFalse(result["serial_operation"])
            self.assertFalse(result["flash_operation"])

    def test_finished_package_digest_matches_executor_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build = self.build(root, "a", 1)
            extracted = root / "extracted"
            self.extract_payload(build, extracted)
            record = json.loads((build / "build-record.json").read_text())
            observed = EXECUTOR.canonical_package_digest(extracted)
            self.assertEqual(observed, record["execution_package_sha256"])
            descriptor = json.loads(
                (extracted / "EXECUTION_PACKAGE_DESCRIPTOR.json").read_text()
            )
            self.assertEqual(
                descriptor["executor_sha256"],
                EXECUTOR.sha256_file(EXECUTOR_PATH),
            )
            self.assertNotIn("package_set_sha256", descriptor)

    def test_tampered_payload_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_a = self.build(root, "a", 1)
            build_b = self.build(root, "b", 2)
            with (build_b / PACK.V1.PAYLOAD_NAME).open("ab") as handle:
                handle.write(b"tamper")
            with self.assertRaises(FREEZE.FreezeError):
                FREEZE.freeze(build_a, build_b, root / "frozen", SOURCE)

    def test_public_package_contains_no_authorization_or_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build = self.build(root, "a", 1)
            payload = (build / PACK.V1.PAYLOAD_NAME).read_bytes()
            for forbidden in (
                b'"authorized": true',
                b"BEGIN PRIVATE KEY",
                b"BEGIN RSA PRIVATE KEY",
                b"BEGIN EC PRIVATE KEY",
                b"/Users/",
                b"/dev/cu.",
                b"/dev/tty.",
            ):
                self.assertNotIn(forbidden, payload)

    def test_unauthorized_record_fails_before_physical_selection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            authorization = root / "authorization.json"
            authorization.write_text(json.dumps({
                "schema": EXECUTOR.AUTH_SCHEMA,
                "stage": EXECUTOR.STAGE,
                "d2_request_id": EXECUTOR.D2_REQUEST_ID,
                "authorized": False,
            }), encoding="utf-8")
            os.chmod(authorization, 0o600)
            with self.assertRaisesRegex(
                EXECUTOR.ExecutionError, "AUTHORIZATION_NOT_GRANTED"
            ):
                EXECUTOR.validate_authorization(
                    authorization,
                    package_root=root,
                    python_path=Path(sys.executable),
                    openssl_path=Path(sys.executable),
                    esptool_path=Path(sys.executable),
                    mosquitto_path=Path(sys.executable),
                )

    def test_serial_identity_hashes_are_redacted_digests(self) -> None:
        identity = EXECUTOR.SerialIdentity(
            device="/dev/example",
            vid=0x303A,
            pid=0x1001,
            serial_number="example-serial",
            manufacturer="Espressif",
            product="USB JTAG/serial debug unit",
            location="1-2",
            hwid="USB VID:PID=303A:1001",
        )
        board = EXECUTOR.canonical_sha256(identity.board_binding())
        serial = EXECUTOR.canonical_sha256(identity.serial_binding())
        self.assertRegex(board, r"^[0-9a-f]{64}$")
        self.assertRegex(serial, r"^[0-9a-f]{64}$")
        self.assertNotEqual(board, serial)


if __name__ == "__main__":
    unittest.main()
