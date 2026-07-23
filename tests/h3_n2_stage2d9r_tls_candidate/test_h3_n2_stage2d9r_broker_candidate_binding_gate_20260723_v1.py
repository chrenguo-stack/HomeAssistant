#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_broker_candidate_binding_gate_20260723_v1.py"
FIXTURE = Path(__file__).with_name(
    "stage2d9r_isolated_broker_public_config_20260723_v1.json"
)
spec = importlib.util.spec_from_file_location("stage2d9r_broker_binding", TOOL)
assert spec is not None and spec.loader is not None
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)


class Stage2D9RBrokerCandidateBindingGateTest(unittest.TestCase):
    def config(self) -> dict:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def assert_invalid(self, config: dict, message: str) -> None:
        with self.assertRaisesRegex(binding.BrokerBindingError, message):
            binding.validate(config)

    def test_fixture_matches_candidate_identity(self) -> None:
        self.assertEqual(binding.validate(self.config()), "tlsvalid01")

    def test_all_derived_identity_fields_are_exact(self) -> None:
        for key in (
            "system_id",
            "node_id",
            "broker_host",
            "broker_tls_server_name",
            "dns_san",
            "mqtt_username",
            "mqtt_client_id",
            "test_topic_root",
        ):
            config = self.config()
            config[key] = "wrong" if key != "dns_san" else ["wrong.local"]
            self.assert_invalid(config, f"{key} mismatch")

    def test_suffix_shape_is_exact(self) -> None:
        for suffix in ("short", "TLSVALID01", "tls-valid-01", "a" * 25):
            config = self.config()
            config["test_run_suffix"] = suffix
            self.assert_invalid(config, "test_run_suffix is invalid")

    def test_password_digest_is_hash_only(self) -> None:
        for value in (None, "raw-password", "A" * 64, "0" * 63):
            config = self.config()
            config["mqtt_password_sha256"] = value
            self.assert_invalid(config, "mqtt_password_sha256 is invalid")

    def test_secret_keys_are_rejected(self) -> None:
        for key in binding.FORBIDDEN_KEYS:
            config = self.config()
            config[key] = "secret"
            self.assert_invalid(config, f"forbidden key {key}")

    def test_execution_and_network_flags_are_false(self) -> None:
        for key in (
            "private_values_included",
            "execution_authorized",
            "network_operation_authorized",
        ):
            config = self.config()
            config[key] = True
            self.assert_invalid(config, f"{key} mismatch")

    def test_unexpected_fields_are_rejected(self) -> None:
        config = self.config()
        config["alias"] = "stage2d9-test-ca"
        self.assert_invalid(config, "unexpected keys: alias")

    def test_validation_does_not_mutate_input(self) -> None:
        config = self.config()
        original = deepcopy(config)
        binding.validate(config)
        self.assertEqual(config, original)


if __name__ == "__main__":
    unittest.main()
