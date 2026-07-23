#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_private_pki_custody_gate_20260723_v1.py"
TEMPLATE = Path(__file__).with_name(
    "stage2d9r_private_pki_custody_descriptor_20260723_v1.json.template"
)
spec = importlib.util.spec_from_file_location("stage2d9r_custody", TOOL)
assert spec is not None and spec.loader is not None
custody = importlib.util.module_from_spec(spec)
spec.loader.exec_module(custody)


class Stage2D9RPrivatePkiCustodyGateTest(unittest.TestCase):
    def locked(self) -> dict:
        return json.loads(TEMPLATE.read_text(encoding="utf-8"))

    def frozen(self) -> dict:
        data = self.locked()
        data["state"] = custody.FROZEN
        data["source_sha"] = "1" * 40
        data["generator_sha256"] = "2" * 64
        data["openssl_executable_sha256"] = "3" * 64
        data["openssl_version"] = "OpenSSL 3.0.13"
        data["custody_root"] = "/private/var/greenhouse-stage2d9r/private-pki-v1"
        data["package_sha256"] = "4" * 64
        data["public_descriptor_sha256"] = "5" * 64
        data["candidate_digest_sha256"] = "6" * 64
        data["authorization"] = {
            "authorization_id": "U1-H3N2-STAGE2D9R-PKI-20260723-01",
            "operation": "GENERATE_PRIVATE_TEST_PKI",
            "one_shot": True,
            "replay_permitted": False,
            "authorized": True,
            "consumed": True,
            "record_sha256": "7" * 64,
        }
        for index, name in enumerate(custody.MATERIALS, start=8):
            data["materials"][name]["sha256"] = f"{index:x}"[-1] * 64
        for key in custody.PROOFS:
            data["offline_proofs"][key] = True
        return data

    def assert_invalid(self, data: dict, message: str) -> None:
        with self.assertRaisesRegex(custody.CustodyError, message):
            custody.validate(data)

    def test_locked_template_passes(self) -> None:
        self.assertEqual(custody.validate(self.locked(), custody.LOCKED), custody.LOCKED)

    def test_frozen_descriptor_passes(self) -> None:
        self.assertEqual(custody.validate(self.frozen(), custody.FROZEN), custody.FROZEN)

    def test_exact_host_and_san_are_required(self) -> None:
        for key, value, message in (
            ("broker_host", "localhost", "broker_host mismatch"),
            ("broker_tls_server_name", "localhost", "TLS server name mismatch"),
            ("dns_san", ["stage2d9r.local", "localhost"], "DNS SAN mismatch"),
        ):
            data = self.locked()
            data[key] = value
            self.assert_invalid(data, message)

    def test_every_execution_boundary_remains_false(self) -> None:
        for key in custody.FALSE_FLAGS:
            data = self.locked()
            data[key] = True
            self.assert_invalid(data, f"{key} must be false")

    def test_material_set_paths_and_modes_are_exact(self) -> None:
        data = self.locked()
        del data["materials"]["broker_full_chain"]
        self.assert_invalid(data, "material set mismatch")
        data = self.locked()
        data["materials"]["broker_private_key"]["relative_path"] = "other.key"
        self.assert_invalid(data, "broker_private_key relative path mismatch")
        data = self.locked()
        data["materials"]["broker_private_key"]["mode"] = "0644"
        self.assert_invalid(data, "broker_private_key mode mismatch")

    def test_locked_template_cannot_claim_authorization_or_proofs(self) -> None:
        data = self.locked()
        data["authorization"]["authorized"] = True
        self.assert_invalid(data, "locked template must not be authorized")
        data = self.locked()
        data["offline_proofs"]["hostname_valid"] = True
        self.assert_invalid(data, "hostname_valid must be false while locked")

    def test_frozen_descriptor_requires_absolute_private_root(self) -> None:
        for value in ("relative/private", "/private/../shared"):
            data = self.frozen()
            data["custody_root"] = value
            self.assert_invalid(data, "custody_root must be an absolute private path")
        data = self.frozen()
        data["custody_root"] = "<ABSOLUTE_PATH>"
        self.assert_invalid(data, "frozen descriptor has placeholders")

    def test_frozen_descriptor_requires_authorization_consumption(self) -> None:
        for key, value, message in (
            ("authorization_id", "D2-wrong-kind", "authorization id invalid"),
            ("authorized", False, "frozen PKI must record generation authorization"),
            ("consumed", False, "frozen PKI must record consumed authorization"),
            ("record_sha256", "bad", "authorization record digest invalid"),
        ):
            data = self.frozen()
            data["authorization"][key] = value
            self.assert_invalid(data, message)

    def test_frozen_descriptor_requires_all_hashes_and_proofs(self) -> None:
        data = self.frozen()
        data["package_sha256"] = "bad"
        self.assert_invalid(data, "package_sha256 invalid")
        data = self.frozen()
        data["materials"]["root_ca_private_key"]["sha256"] = "bad"
        self.assert_invalid(data, "root_ca_private_key sha256 invalid")
        data = self.frozen()
        data["offline_proofs"]["certificate_chain_valid"] = False
        self.assert_invalid(data, "certificate_chain_valid must be true when frozen")

    def test_private_values_are_never_embedded_in_descriptor(self) -> None:
        data = self.frozen()
        data["private_values_included"] = True
        self.assert_invalid(data, "descriptor must not include private values")
        data = self.frozen()
        data["raw_private_keys_in_descriptor"] = True
        self.assert_invalid(data, "raw_private_keys_in_descriptor must be false")

    def test_validation_does_not_mutate_input(self) -> None:
        data = self.frozen()
        original = deepcopy(data)
        custody.validate(data)
        self.assertEqual(data, original)


if __name__ == "__main__":
    unittest.main()
