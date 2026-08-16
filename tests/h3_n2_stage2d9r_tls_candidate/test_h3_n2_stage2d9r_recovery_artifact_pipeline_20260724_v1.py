#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGER = ROOT / "tools/h3_n2_stage2d9r_recovery_artifact_packager_20260724_v1.py"
FREEZER = ROOT / "tools/h3_n2_stage2d9r_recovery_artifact_freeze_20260724_v1.py"
GATE = ROOT / "tools/h3_n2_stage2d9r_recovery_artifact_manifest_gate_20260724_v1.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packager = load("stage2d9r_recovery_packager", PACKAGER)
freezer = load("stage2d9r_recovery_freezer", FREEZER)
gate = load("stage2d9r_recovery_artifact_gate", GATE)


class Stage2D9RRecoveryArtifactPipelineTest(unittest.TestCase):
    source_sha = "a" * 40

    def write_inputs(self, root: Path) -> dict[str, Path]:
        immutable = {
            "schema": "gh.h3.n2.stage2d9r-immutable-build-manifest/1",
            "state": "BUILD_FROZEN",
            "source_sha": packager.IMMUTABLE_SOURCE_SHA,
            "build_binding": packager.BUILD_BINDING,
            "artifact": {
                "artifact_id": packager.IMMUTABLE_ARTIFACT_ID,
                "artifact_name": packager.IMMUTABLE_ARTIFACT_NAME,
                "artifact_sha256": packager.IMMUTABLE_ARTIFACT_SHA256,
            },
            "firmware": {
                "application_sha256": packager.APPLICATION_SHA256,
                "merged_image_sha256": packager.MERGED_IMAGE_SHA256,
            },
            "candidate_bindings": {
                "unlock_digest_sha256": packager.UNLOCK_DIGEST,
                "ca_pem_sha256": packager.CA_PEM_SHA256,
                "candidate_digest_sha256": packager.CANDIDATE_DIGEST,
            },
            "partition": {
                "address": 0x400000,
                "size_bytes": 65536,
                "table_sha256": packager.PARTITION_TABLE_SHA256,
            },
        }
        template = {
            "schema": "gh.h3.n2.stage2d9r-test-partition-recovery-manifest/1",
            "stage": "H3/N2 Stage 2D-9R G3R",
            "state": "LOCKED_TEMPLATE",
            "source_sha": "<SOURCE_SHA40>",
            "partition": {
                "label": "gh2d8_p2d9",
                "namespace": "gh2d8_s2d9",
                "address": 0x400000,
                "size_bytes": 65536,
                "expected_erased_byte": 0xFF,
                "expected_erased_sha256": packager.ERASED_SHA256,
            },
            "recovery_authorized": False,
            "board_operation_authorized": False,
            "serial_operation_authorized": False,
            "flash_operation_authorized": False,
        }
        paths = {
            "immutable": root / "immutable.json",
            "template": root / "template.json",
            "contract": root / "contract.md",
            "recovery_gate": root / "recovery_gate.py",
        }
        paths["immutable"].write_text(
            json.dumps(immutable, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        paths["template"].write_text(
            json.dumps(template, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        paths["contract"].write_text(
            "This document is a source/review contract.\nNo operation is authorized.\n",
            encoding="utf-8",
        )
        paths["recovery_gate"].write_text(
            "# source-only validation gate\nSTATE = 'LOCKED_TEMPLATE'\n",
            encoding="utf-8",
        )
        return paths

    def run_build(
        self, workspace: Path, lane: str, run_id: int, artifact_name: str
    ) -> Path:
        inputs_root = workspace / f"inputs-{lane}"
        inputs_root.mkdir(parents=True)
        inputs = self.write_inputs(inputs_root)
        output = workspace / f"build-{lane}"
        cp = subprocess.run(
            [
                sys.executable,
                str(PACKAGER),
                "--immutable-manifest", str(inputs["immutable"]),
                "--recovery-template", str(inputs["template"]),
                "--recovery-contract", str(inputs["contract"]),
                "--recovery-gate", str(inputs["recovery_gate"]),
                "--output-dir", str(output),
                "--lane", lane,
                "--artifact-name", artifact_name,
                "--source-sha", self.source_sha,
                "--run-id", str(run_id),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn("STAGE2D9R_LOCKED_RECOVERY_CLEAN_BUILD=PASS", cp.stdout)
        return output

    def test_two_clean_build_payloads_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            a = self.run_build(
                workspace, "a", 101, "stage2d9r-g3r-recovery-locked-v1"
            )
            b = self.run_build(
                workspace, "b", 102, "stage2d9r-g3r-recovery-repro-v1"
            )
            a_tar = (a / "stage2d9r-g3r-recovery-payload-v1.tar").read_bytes()
            b_tar = (b / "stage2d9r-g3r-recovery-payload-v1.tar").read_bytes()
            self.assertEqual(a_tar, b_tar)
            self.assertEqual(
                hashlib.sha256(a_tar).hexdigest(),
                hashlib.sha256(b_tar).hexdigest(),
            )
            self.assertNotEqual(
                (a / "build-record.json").read_bytes(),
                (b / "build-record.json").read_bytes(),
            )

    def test_payload_is_locked_public_only_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            build = self.run_build(
                Path(td), "a", 201, "stage2d9r-g3r-recovery-locked-v1"
            )
            tar_path = build / "stage2d9r-g3r-recovery-payload-v1.tar"
            descriptor, sums = freezer.inspect_payload(tar_path)
            self.assertEqual(descriptor["state"], "RECOVERY_ARTIFACT_LOCKED")
            self.assertFalse(descriptor["recovery_authorized"])
            self.assertFalse(descriptor["execution_authorized"])
            self.assertFalse(descriptor["board_operation_authorized"])
            self.assertFalse(descriptor["network_operation_authorized"])
            self.assertEqual(
                sums["test-partition-erased.bin"], packager.ERASED_SHA256
            )
            with tarfile.open(tar_path, "r") as archive:
                erased = archive.extractfile("test-partition-erased.bin")
                self.assertIsNotNone(erased)
                assert erased is not None
                self.assertEqual(erased.read(), b"\xff" * 65536)

    def test_bad_immutable_binding_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputs_root = root / "inputs"
            inputs_root.mkdir()
            paths = self.write_inputs(inputs_root)
            data = json.loads(paths["immutable"].read_text(encoding="utf-8"))
            data["artifact"]["artifact_sha256"] = "0" * 64
            paths["immutable"].write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(
                packager.RecoveryPackagingError,
                "immutable artifact digest mismatch",
            ):
                packager.build_payload(
                    immutable_manifest_path=paths["immutable"],
                    recovery_template_path=paths["template"],
                    recovery_contract_path=paths["contract"],
                    recovery_gate_path=paths["recovery_gate"],
                    source_sha=self.source_sha,
                )

    def test_freeze_manifest_passes_gate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            a = self.run_build(
                workspace, "a", 301, "stage2d9r-g3r-recovery-locked-v1"
            )
            b = self.run_build(
                workspace, "b", 302, "stage2d9r-g3r-recovery-repro-v1"
            )
            output = workspace / "freeze"
            cp = subprocess.run(
                [
                    sys.executable,
                    str(FREEZER),
                    "--build-a", str(a),
                    "--build-b", str(b),
                    "--run-a", "301",
                    "--run-b", "302",
                    "--artifact-a-id", "401",
                    "--artifact-b-id", "402",
                    "--source-sha", self.source_sha,
                    "--output-dir", str(output),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            manifest_path = (
                output / "stage2d9r_recovery_artifact_manifest_20260724_v1.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            gate.validate(manifest)
            self.assertEqual(manifest["build_run_ids"], [301, 302])
            self.assertTrue(manifest["reproducibility"]["payloads_byte_identical"])
            self.assertFalse(manifest["recovery_authorized"])

    def test_freeze_rejects_non_identical_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            a = self.run_build(
                workspace, "a", 501, "stage2d9r-g3r-recovery-locked-v1"
            )
            b = self.run_build(
                workspace, "b", 502, "stage2d9r-g3r-recovery-repro-v1"
            )
            tar_path = b / "stage2d9r-g3r-recovery-payload-v1.tar"
            tar_path.write_bytes(tar_path.read_bytes() + b"x")
            cp = subprocess.run(
                [
                    sys.executable,
                    str(FREEZER),
                    "--build-a", str(a),
                    "--build-b", str(b),
                    "--run-a", "501",
                    "--run-b", "502",
                    "--artifact-a-id", "601",
                    "--artifact-b-id", "602",
                    "--source-sha", self.source_sha,
                    "--output-dir", str(workspace / "freeze"),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn(
                "independent recovery payloads are not byte-identical",
                cp.stderr + cp.stdout,
            )

    def test_manifest_gate_rejects_authorization_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            a = self.run_build(
                workspace, "a", 701, "stage2d9r-g3r-recovery-locked-v1"
            )
            b = self.run_build(
                workspace, "b", 702, "stage2d9r-g3r-recovery-repro-v1"
            )
            output = workspace / "freeze"
            subprocess.run(
                [
                    sys.executable, str(FREEZER),
                    "--build-a", str(a), "--build-b", str(b),
                    "--run-a", "701", "--run-b", "702",
                    "--artifact-a-id", "801", "--artifact-b-id", "802",
                    "--source-sha", self.source_sha,
                    "--output-dir", str(output),
                ],
                check=True,
                capture_output=True,
            )
            path = output / "stage2d9r_recovery_artifact_manifest_20260724_v1.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["recovery_authorized"] = True
            copy = json.loads(json.dumps(data))
            copy["artifact"].pop("manifest_sha256")
            data["artifact"]["manifest_sha256"] = hashlib.sha256(json.dumps(
                copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()).hexdigest()
            with self.assertRaisesRegex(
                gate.RecoveryArtifactGateError,
                "recovery_authorized must be false",
            ):
                gate.validate(data)


if __name__ == "__main__":
    unittest.main()
