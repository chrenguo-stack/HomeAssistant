from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import h3_n2_stage2d9r_g3r_repaired_immutable_recovery_pipeline_20260728_v1 as pipeline
import h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1 as chain


PUBLIC_DIR = (
    ROOT
    / "tests/h3_n2_stage2d9r_tls_candidate/public_repaired_tlsvalid03"
)
BINDING = (
    ROOT
    / "tests/h3_n2_stage2d9r_tls_candidate/"
    "stage2d9r_g3r_repaired_immutable_build_binding_20260728_v1.json"
)
PARTITION = (
    ROOT
    / "firmware/esphome_rc/board_lab/h3_profile_isolated_device_g3_prepare/"
    "stage2d9_g3_partitions_20260722_v65.csv"
)
HOST_CONTROLLER = (
    ROOT / "tools/h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py"
)
SOURCE_SHA = "1111111111111111111111111111111111111111"
ENV_A = "a" * 64
ENV_B = "b" * 64
ENV_C = "c" * 64
WORKFLOW = "d" * 64


class RepairedImmutableRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fake_build(self, name: str) -> Path:
        root = self.root / name / "nested"
        root.mkdir(parents=True)
        (root / "bootloader.bin").write_bytes(b"BOOT" + b"\x00" * 100)
        (root / "partitions.bin").write_bytes(b"PART" + b"\x01" * 100)
        (root / "firmware.bin").write_bytes(b"APP" + b"\x02" * 1000)
        return root.parent

    def immutable_args(self, lane: str, build: Path, output: Path) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            source_sha=SOURCE_SHA,
            python_environment_sha256=ENV_A,
            openssl_environment_sha256=ENV_B,
            esphome_environment_sha256=ENV_C,
            workflow_sha256=WORKFLOW,
            public_dir=PUBLIC_DIR,
            binding=BINDING,
            partition_csv=PARTITION,
            host_controller=HOST_CONTROLLER,
            build_root=build,
            output_dir=output,
            lane=lane,
        )

    def build_full_fixture(self) -> tuple[Path, Path, Path]:
        build_a = self.fake_build("build-a")
        build_b = self.fake_build("build-b")
        immutable_a = self.root / "immutable-a"
        immutable_b = self.root / "immutable-b"
        pipeline.build_immutable(self.immutable_args("a", build_a, immutable_a))
        pipeline.build_immutable(self.immutable_args("b", build_b, immutable_b))
        immutable_freeze = self.root / "immutable-freeze"
        pipeline.freeze_immutable(
            types.SimpleNamespace(
                source_sha=SOURCE_SHA,
                build_a=immutable_a,
                build_b=immutable_b,
                output_dir=immutable_freeze,
            )
        )
        recovery_a = self.root / "recovery-a"
        recovery_b = self.root / "recovery-b"
        for lane, output in (("a", recovery_a), ("b", recovery_b)):
            pipeline.build_recovery(
                types.SimpleNamespace(
                    source_sha=SOURCE_SHA,
                    public_dir=PUBLIC_DIR,
                    binding=BINDING,
                    immutable_freeze=immutable_freeze,
                    output_dir=output,
                    lane=lane,
                )
            )
        return immutable_freeze, recovery_a, recovery_b

    def test_public_u1_evidence_and_binding(self) -> None:
        result, descriptor, acceptance, binding = pipeline.public_inputs(
            PUBLIC_DIR, BINDING
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(acceptance["private_material_u1_consumed_pass"])
        self.assertFalse(acceptance["replay_permitted"])
        self.assertFalse(descriptor["final_execution_binding_ready"])
        payload = binding["binding_payload"]
        observed = hashlib.sha256(pipeline.canonical_json_bytes(payload)).hexdigest()
        self.assertEqual(observed, binding["immutable_build_binding_sha256"])
        self.assertEqual(observed[:40], binding["immutable_build_binding"])

    def test_two_clean_immutable_builds_are_byte_identical(self) -> None:
        immutable_freeze, _, _ = self.build_full_fixture()
        manifest = json.loads(
            (immutable_freeze / "immutable-freeze-manifest.json").read_text()
        )
        self.assertEqual(
            manifest["state"], "REPAIRED_IMMUTABLE_REPRODUCIBLE_AND_FROZEN"
        )
        self.assertEqual(manifest["clean_build_count"], 2)
        self.assertTrue(manifest["payloads_byte_identical"])
        self.assertFalse(manifest["execution_authorized"])

    def test_locked_recovery_scope_is_partition_only(self) -> None:
        _, recovery_a, recovery_b = self.build_full_fixture()
        self.assertEqual(
            (recovery_a / pipeline.RECOVERY_TAR_NAME).read_bytes(),
            (recovery_b / pipeline.RECOVERY_TAR_NAME).read_bytes(),
        )
        members = pipeline.tar_members(recovery_a / pipeline.RECOVERY_TAR_NAME)
        descriptor = json.loads(members["locked-recovery-descriptor.json"])
        plan = json.loads(members["locked-recovery-plan.json"])
        self.assertEqual(descriptor["scope"], "TEST_PARTITION_ONLY")
        self.assertEqual(
            descriptor["partition"]["expected_erased_sha256"],
            chain.ERASED_PARTITION_SHA256,
        )
        self.assertEqual(
            [item["operation"] for item in plan["ordered_operations"]],
            ["READ_FLASH_REGION", "ERASE_FLASH_REGION", "READ_FLASH_REGION"],
        )
        self.assertIn("ERASE_ALL_FLASH", plan["forbidden_operations"])
        self.assertFalse(plan["recovery_authorized"])

    def test_final_binding_is_derived_but_execution_remains_unauthorized(self) -> None:
        immutable_freeze, recovery_a, recovery_b = self.build_full_fixture()
        output = self.root / "final"
        pipeline.freeze_recovery(
            types.SimpleNamespace(
                source_sha=SOURCE_SHA,
                public_dir=PUBLIC_DIR,
                binding=BINDING,
                host_controller=HOST_CONTROLLER,
                immutable_freeze=immutable_freeze,
                build_a=recovery_a,
                build_b=recovery_b,
                output_dir=output,
            )
        )
        manifest = json.loads(
            (output / "immutable-recovery-freeze-manifest.json").read_text()
        )
        binding = json.loads((output / "final-execution-binding.json").read_text())
        self.assertEqual(
            manifest["state"],
            "REPAIRED_IMMUTABLE_RECOVERY_FROZEN_FINAL_BINDING_READY",
        )
        self.assertEqual(len(manifest["final_execution_binding"]), 40)
        self.assertEqual(len(manifest["final_execution_binding_sha256"]), 64)
        self.assertEqual(
            manifest["final_execution_binding_sha256"],
            binding["final_execution_binding_sha256"],
        )
        self.assertEqual(manifest["next_gate"], "BASELINE_READONLY_GATE")
        self.assertFalse(manifest["execution_authorized"])
        self.assertFalse(manifest["board_operation_authorized"])

    def test_pipeline_has_no_live_operation_dependencies(self) -> None:
        text = (
            ROOT
            / "tools/h3_n2_stage2d9r_g3r_repaired_immutable_recovery_pipeline_20260728_v1.py"
        ).read_text()
        for forbidden in (
            "import serial",
            "import socket",
            "import esptool",
            "subprocess.run",
            "os.system",
            "write_flash",
            "erase_flash",
        ):
            self.assertNotIn(forbidden, text)

    def test_retired_repair_image_cannot_be_final_immutable(self) -> None:
        digest_bindings = {name: "1" * 64 for name in chain.FINAL_EXECUTION_DIGEST_FIELDS}
        digest_bindings["immutable_merged_image_sha256"] = chain.REPAIR_MERGED_IMAGE_SHA256
        with self.assertRaises(chain.ContractError):
            chain.build_final_execution_payload(
                source_sha=SOURCE_SHA,
                digest_bindings=digest_bindings,
                immutable_build_count=2,
                immutable_builds_byte_identical=True,
            )


if __name__ == "__main__":
    unittest.main()
