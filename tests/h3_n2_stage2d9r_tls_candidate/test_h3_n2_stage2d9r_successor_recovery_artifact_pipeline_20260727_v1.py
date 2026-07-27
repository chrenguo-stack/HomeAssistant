#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PACK = load(
    "pack",
    ROOT / "tools" / "h3_n2_stage2d9r_successor_recovery_artifact_packager_20260727_v1.py",
)
FREEZE = load(
    "freeze",
    ROOT / "tools" / "h3_n2_stage2d9r_successor_recovery_artifact_freeze_20260727_v1.py",
)
SOURCE = "a" * 40


class PipelineTests(unittest.TestCase):
    def fixtures(self, root: Path) -> tuple[Path, Path, Path, Path]:
        root.mkdir(parents=True, exist_ok=True)
        acceptance = {
            "schema": PACK.IMMUTABLE_ACCEPTANCE_SCHEMA,
            "stage": PACK.STAGE,
            "state": "IMMUTABLE_BUILD_REPRODUCIBLE_AND_FROZEN",
            "source_sha": PACK.IMMUTABLE_SOURCE_SHA,
            "build_binding": PACK.BUILD_BINDING,
            "canonical_artifact": {
                "artifact_id": PACK.IMMUTABLE_ARTIFACT_ID,
                "name": PACK.IMMUTABLE_ARTIFACT_NAME,
                "github_digest_sha256": PACK.IMMUTABLE_ARCHIVE_SHA256,
                "payload_tar_sha256": PACK.IMMUTABLE_PAYLOAD_TAR_SHA256,
            },
            "firmware": {
                "application_sha256": PACK.APPLICATION_SHA256,
                "merged_image_sha256": PACK.MERGED_IMAGE_SHA256,
                "partition_table_bin_sha256": PACK.PARTITION_TABLE_BIN_SHA256,
            },
            "candidate_bindings": {
                "unlock_digest_sha256": PACK.UNLOCK_DIGEST,
                "ca_pem_sha256": PACK.CA_PEM_SHA256,
                "candidate_digest_sha256": PACK.CANDIDATE_DIGEST,
                "broker_certificate_der_sha256": PACK.BROKER_DER_SHA256,
                "broker_spki_sha256": PACK.BROKER_SPKI_SHA256,
            },
            "disposition": {
                "immutable_build_accepted": True,
                "canonical_artifact_frozen": True,
                "d2_authorized": False,
                "physical_execution_authorized": False,
            },
            "protected_boundaries": {
                "board_operation_authorized": False,
                "serial_operation_authorized": False,
                "flash_operation_authorized": False,
            },
        }
        template = {
            "schema": "gh.h3.n2.stage2d9r-test-partition-recovery-manifest/1",
            "state": "LOCKED_TEMPLATE",
            "source_sha": "<SOURCE_SHA40>",
            "partition": {
                "label": "gh2d8_p2d9",
                "namespace": "gh2d8_s2d9",
                "address": 0x400000,
                "size_bytes": PACK.ERASED_SIZE,
                "expected_erased_byte": 0xFF,
                "expected_erased_sha256": PACK.ERASED_SHA256,
            },
            "recovery_authorized": False,
            "board_operation_authorized": False,
            "serial_operation_authorized": False,
            "flash_operation_authorized": False,
            "physical_nvs_operation_authorized": False,
        }
        acceptance_path = root / "acceptance.json"
        template_path = root / "template.json"
        acceptance_path.write_text(json.dumps(acceptance), encoding="utf-8")
        template_path.write_text(json.dumps(template), encoding="utf-8")
        contract = root / "contract.md"
        contract.write_text("This document is a source/review contract.\n", encoding="utf-8")
        gate = root / "gate.py"
        gate.write_text("# source-only validation gate\n", encoding="utf-8")
        return acceptance_path, template_path, contract, gate

    def build(self, root: Path, lane: str, run_id: int) -> Path:
        acceptance, template, contract, gate = self.fixtures(root / f"inputs-{lane}")
        out = root / f"build-{lane}"
        PACK.package(
            immutable_acceptance_path=acceptance,
            recovery_template_path=template,
            recovery_contract_path=contract,
            recovery_gate_path=gate,
            output_dir=out,
            source_sha=SOURCE,
            lane=lane,
            artifact_name=f"artifact-{lane}",
            run_id=run_id,
        )
        return out

    def test_two_builds_are_reproducible_and_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_a = self.build(root, "a", 1)
            build_b = self.build(root, "b", 2)
            self.assertEqual(
                (build_a / PACK.PAYLOAD_NAME).read_bytes(),
                (build_b / PACK.PAYLOAD_NAME).read_bytes(),
            )
            frozen = root / "frozen"
            manifest = FREEZE.freeze(build_a, build_b, frozen, SOURCE)
            self.assertEqual(manifest["clean_build_count"], 2)
            self.assertTrue(manifest["payloads_byte_identical"])
            self.assertFalse(manifest["recovery_authorized"])
            self.assertTrue((frozen / "SHA256SUMS").is_file())

    def test_tampered_payload_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_a = self.build(root, "a", 1)
            build_b = self.build(root, "b", 2)
            with (build_b / PACK.PAYLOAD_NAME).open("ab") as handle:
                handle.write(b"x")
            with self.assertRaises(FREEZE.FreezeError):
                FREEZE.freeze(build_a, build_b, root / "frozen", SOURCE)

    def test_immutable_authorization_expansion_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            acceptance, template, contract, gate = self.fixtures(root)
            value = json.loads(acceptance.read_text())
            value["disposition"]["d2_authorized"] = True
            acceptance.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(
                PACK.RecoveryPackagingError, "IMMUTABLE_D2_AUTHORIZED"
            ):
                PACK.package(
                    immutable_acceptance_path=acceptance,
                    recovery_template_path=template,
                    recovery_contract_path=contract,
                    recovery_gate_path=gate,
                    output_dir=root / "out",
                    source_sha=SOURCE,
                    lane="a",
                    artifact_name="a",
                    run_id=1,
                )

    def test_payload_has_no_private_or_authorization_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = self.build(root, "a", 1)
            data = (out / PACK.PAYLOAD_NAME).read_bytes()
            for forbidden in (
                b"BEGIN PRIVATE KEY",
                b"/Users/",
                b"/dev/",
                b"authorized\": true",
                b"mqtt-password.hex",
                b"persistence-key.hex",
                b"unlock-token.hex",
            ):
                self.assertNotIn(forbidden, data)


if __name__ == "__main__":
    unittest.main()
