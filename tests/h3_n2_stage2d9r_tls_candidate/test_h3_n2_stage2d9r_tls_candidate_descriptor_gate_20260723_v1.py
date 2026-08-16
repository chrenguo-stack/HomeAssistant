#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_tls_candidate_descriptor_gate_20260723_v1.py"
FIXTURE = Path(__file__).with_name("stage2d9r_tls_candidate_descriptor_20260723_v1.json")

spec = importlib.util.spec_from_file_location("stage2d9r_gate", TOOL)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Stage2D9RTlsDescriptorGateTest(unittest.TestCase):
    def locked(self) -> dict:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def frozen(self) -> dict:
        data = self.locked()
        data["state"] = module.FROZEN
        for index, key in enumerate(module.HASH_FIELDS, start=1):
            data["public_material"][key] = f"{index:x}" * 64
        data["public_material"]["certificate_not_before"] = "2026-07-23T00:00:00Z"
        data["public_material"]["certificate_not_after"] = "2026-08-22T00:00:00Z"
        for key in module.PROOF_FLAGS:
            data["offline_proofs"][key] = True
        return data

    def assert_invalid(self, data: dict, message: str) -> None:
        with self.assertRaisesRegex(module.DescriptorError, message):
            module.validate(data)

    def test_locked_fixture_passes(self) -> None:
        self.assertEqual(module.validate(self.locked(), module.LOCKED), module.LOCKED)

    def test_frozen_fixture_passes(self) -> None:
        self.assertEqual(module.validate(self.frozen(), module.FROZEN), module.FROZEN)

    def test_hostname_and_san_are_exact(self) -> None:
        data = self.locked()
        data["broker_tls_server_name"] = "localhost"
        self.assert_invalid(data, "broker_tls_server_name mismatch")
        data = self.locked()
        data["dns_san"] = ["stage2d9r.local", "localhost"]
        self.assert_invalid(data, "dns_san mismatch")

    def test_tls_bypass_and_alias_are_denied(self) -> None:
        for key in ("tls_verification_bypass_allowed", "alias_resolution_allowed"):
            data = self.locked()
            data[key] = True
            self.assert_invalid(data, f"{key} must be false")

    def test_all_execution_boundaries_are_locked(self) -> None:
        for key in module.FALSE_FLAGS[:7]:
            data = self.locked()
            data[key] = True
            self.assert_invalid(data, f"{key} must be false")

    def test_locked_state_rejects_material_hashes(self) -> None:
        data = self.locked()
        data["public_material"]["ca_pem_sha256"] = "a" * 64
        self.assert_invalid(data, "ca_pem_sha256 must be null while locked")

    def test_frozen_state_requires_every_hash(self) -> None:
        for key in module.HASH_FIELDS:
            data = self.frozen()
            data["public_material"][key] = None
            self.assert_invalid(data, f"{key} must be lowercase sha256")

    def test_frozen_state_requires_offline_tls_proofs(self) -> None:
        for key in module.PROOF_FLAGS:
            data = self.frozen()
            data["offline_proofs"][key] = False
            self.assert_invalid(data, f"{key} must be true when frozen")

    def test_frozen_state_rejects_invalid_validity_interval(self) -> None:
        data = self.frozen()
        data["public_material"]["certificate_not_after"] = "2026-07-22T00:00:00Z"
        self.assert_invalid(data, "certificate validity interval is invalid")

    def test_private_material_cannot_enter_public_descriptor(self) -> None:
        for key in ("private_key_included", "mqtt_password_included"):
            data = self.frozen()
            data["public_material"][key] = True
            self.assert_invalid(data, f"{key} must be false")

    def test_input_is_not_mutated(self) -> None:
        data = self.frozen()
        original = deepcopy(data)
        module.validate(data)
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
