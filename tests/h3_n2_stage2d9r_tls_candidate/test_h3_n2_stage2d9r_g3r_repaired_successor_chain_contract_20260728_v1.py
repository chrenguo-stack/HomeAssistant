#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_repaired_successor_chain_contract_20260728_v1.py"
SPEC = importlib.util.spec_from_file_location("repaired_successor_contract", TOOL)
assert SPEC is not None and SPEC.loader is not None
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


def fresh_digest(name: str) -> str:
    return hashlib.sha256(("tlsvalid03:" + name).encode("utf-8")).hexdigest()


class RepairedSuccessorContractTests(unittest.TestCase):
    def test_source_contract_is_inert_and_exactly_layered(self) -> None:
        value = contract.source_contract()
        self.assertEqual(
            value["decision_id"],
            "D1-H3N2-STAGE2D9R-G3R-REPAIRED-SUCCESSOR-CHAIN-20260728-01",
        )
        self.assertEqual(value["base_pull_request"], 185)
        self.assertEqual(
            value["base_head_sha"], "662bd9027595a7dcfaaaedb977691b13b3fec74b"
        )
        self.assertEqual(value["run_suffix"], "tlsvalid03")
        self.assertFalse(value["repair_source_binding_is_final_execution_binding"])
        self.assertTrue(value["new_final_execution_binding_required"])
        self.assertEqual(tuple(value["gate_order"]), contract.GATE_ORDER)
        for key in (
            "authorization_created",
            "authorization_claimed",
            "authorization_consumed",
            "secret_generation",
            "private_material_created",
            "board_operation",
            "usb_enumeration",
            "serial_enumeration",
            "serial_open",
            "esptool_invoked",
            "flash_operation",
            "physical_nvs_operation",
            "network_operation",
            "broker_started",
            "prepare_executed",
            "verify_executed",
            "activate_executed",
            "cleanup_executed",
            "ready_authorized",
            "merge_authorized",
            "release_authorized",
            "tag_authorized",
            "deployment_authorized",
            "replay_permitted",
            "automatic_retry_permitted",
            "private_values_included",
            "private_paths_included",
            "secret_values_included",
        ):
            self.assertIs(value[key], False, key)

    def test_private_inventory_requires_exact_mode_and_new_digests(self) -> None:
        materials = {
            name: {
                "relative_path": name,
                "mode": "0600",
                "sha256": fresh_digest(name),
            }
            for name in contract.REQUIRED_PRIVATE_FILES
        }
        observed = contract.validate_private_inventory(materials)
        self.assertRegex(observed, r"^[0-9a-f]{64}$")
        bad = {name: dict(metadata) for name, metadata in materials.items()}
        bad[contract.REQUIRED_PRIVATE_FILES[0]]["mode"] = "0644"
        with self.assertRaisesRegex(contract.ContractError, "PRIVATE_MODE_MISMATCH"):
            contract.validate_private_inventory(bad)

    def test_retired_digest_reuse_fails_closed(self) -> None:
        retired = next(iter(contract.RETIRED_DIGESTS))
        with self.assertRaisesRegex(contract.ContractError, "RETIRED_REUSE"):
            contract.validate_sha256(retired, "TEST_DIGEST")

    def test_final_binding_is_deterministic_and_sensitive(self) -> None:
        bindings = {
            key: fresh_digest(key) for key in contract.FINAL_EXECUTION_DIGEST_FIELDS
        }
        payload = contract.build_final_execution_payload(
            source_sha="a" * 40,
            digest_bindings=bindings,
            immutable_build_count=2,
            immutable_builds_byte_identical=True,
        )
        short_a, full_a = contract.derive_final_execution_binding(payload)
        short_b, full_b = contract.derive_final_execution_binding(dict(payload))
        self.assertEqual((short_a, full_a), (short_b, full_b))
        self.assertEqual(short_a, full_a[:40])
        changed = dict(payload)
        changed_bindings = dict(payload["bindings"])
        changed_bindings["candidate_digest_sha256"] = fresh_digest("candidate-changed")
        changed["bindings"] = changed_bindings
        self.assertNotEqual(
            contract.derive_final_execution_binding(changed), (short_a, full_a)
        )

    def test_final_binding_rejects_repair_base_as_final_source(self) -> None:
        bindings = {
            key: fresh_digest(key) for key in contract.FINAL_EXECUTION_DIGEST_FIELDS
        }
        with self.assertRaisesRegex(
            contract.ContractError, "FINAL_SOURCE_MUST_EXTEND_REPAIR_BASE"
        ):
            contract.build_final_execution_payload(
                source_sha=contract.BASE_HEAD_SHA,
                digest_bindings=bindings,
                immutable_build_count=2,
                immutable_builds_byte_identical=True,
            )

    def test_gate_order_is_not_reorderable(self) -> None:
        contract.validate_gate_sequence(contract.GATE_ORDER)
        with self.assertRaisesRegex(contract.ContractError, "GATE_ORDER_MISMATCH"):
            contract.validate_gate_sequence(tuple(reversed(contract.GATE_ORDER)))

    def test_cli_only_emits_public_source_contract(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(TOOL), "--source-sha", "b" * 40],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        value = json.loads(completed.stdout)
        self.assertEqual(value["contract_source_sha"], "b" * 40)
        self.assertFalse(value["secret_generation"])
        self.assertNotIn("mqtt-password.hex", completed.stderr)


if __name__ == "__main__":
    unittest.main()
