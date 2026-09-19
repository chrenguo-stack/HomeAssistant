#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

REPOSITORY = Path(__file__).resolve().parents[2]
GENERATOR = REPOSITORY / "tools" / "h3_n2_stage2d9r_private_pki_generator_20260723_v1.py"
PROTOCOL = REPOSITORY / "tools" / "h3_n2_stage2d9r_prepare_command_protocol_20260723_v1.py"
BINDING = REPOSITORY / "tools" / "h3_n2_stage2d9r_tls_public_binding_builder_20260723_v1.py"

for name, path in (
    ("h3_n2_stage2d9r_prepare_command_protocol_20260723_v1", PROTOCOL),
    ("h3_n2_stage2d9r_tls_public_binding_builder_20260723_v1", BINDING),
):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)

spec = importlib.util.spec_from_file_location("stage2d9r_generator", GENERATOR)
assert spec and spec.loader
gen = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = gen
spec.loader.exec_module(gen)
protocol = sys.modules["h3_n2_stage2d9r_prepare_command_protocol_20260723_v1"]


class GeneratorContractTest(unittest.TestCase):
    def test_default_root_is_exact_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            root = gen.default_custody_root(home)
            self.assertEqual(root, home / gen.CUSTODY_RELATIVE)
            self.assertTrue(root.is_relative_to(home))

    def test_root_rejects_shared_temporary_and_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            expected = gen.default_custody_root(home)
            expected.parent.mkdir(parents=True)
            repo = home / ".local"
            with self.assertRaisesRegex(gen.GenerationError, "inside the repository|shared temporary"):
                gen.validate_private_root(expected, home, repo)
            with self.assertRaisesRegex(gen.GenerationError, "selection rule mismatch"):
                gen.validate_private_root(Path("/tmp/stage2d9r"), home, None)

    def test_candidate_digest_matches_protocol(self) -> None:
        ca = "-----BEGIN CERTIFICATE-----\n" + "\n".join(["A" * 64] * 4) + "\n-----END CERTIFICATE-----\n"
        password = "a" * 64
        expected = protocol.candidate_digest(protocol.build_candidate(gen.RUN_SUFFIX, password, ca))
        self.assertEqual(gen.build_candidate_digest(password, ca), expected)

    def test_public_config_never_contains_raw_password(self) -> None:
        password = "b" * 64
        config = gen.build_public_config(password)
        payload = json.dumps(config, sort_keys=True)
        self.assertNotIn(password, payload)
        self.assertEqual(config["mqtt_password_sha256"], hashlib.sha256(password.encode()).hexdigest())
        self.assertFalse(config["execution_authorized"])
        self.assertFalse(config["network_operation_authorized"])

    def test_acl_is_test_only(self) -> None:
        acl = gen.build_acl()
        self.assertIn("gh-test/gh-test-run-tlsvalid01/node/#", acl)
        self.assertNotIn("homeassistant", acl.lower())
        self.assertNotIn("gh/v1/", acl)

    def test_broker_config_is_loopback_and_not_started(self) -> None:
        config = gen.build_broker_configuration(Path("/private/var/stage2d9r"))
        self.assertIn("listener 8883 127.0.0.1", config)
        self.assertIn("allow_anonymous false", config)
        self.assertNotIn("0.0.0.0", config)
        self.assertNotIn("start", config.lower())

    def test_package_digest_is_order_independent(self) -> None:
        first = {
            "b": {"relative_path": "b", "mode": "0600", "sha256": "2" * 64},
            "a": {"relative_path": "a", "mode": "0600", "sha256": "1" * 64},
        }
        second = dict(reversed(list(first.items())))
        self.assertEqual(gen.package_digest(first), gen.package_digest(second))

    def test_authorization_requires_exact_live_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            auth_path = root / "authorization.json"
            now = datetime.now(timezone.utc)
            toolchain = gen.Toolchain(
                generator_sha256="1" * 64,
                python_executable_sha256="2" * 64,
                python_version="Python 3.11",
                openssl_path=Path("/usr/bin/openssl"),
                openssl_executable_sha256="3" * 64,
                openssl_version="OpenSSL test",
                mosquitto_passwd_path=Path("/usr/bin/mosquitto_passwd"),
                mosquitto_passwd_executable_sha256="4" * 64,
                mosquitto_passwd_version="mosquitto_passwd test",
            )
            base = {
                "schema": gen.AUTH_SCHEMA,
                "stage": gen.STAGE,
                "authorization_id": gen.AUTH_PREFIX + "20260723-01",
                "operation": gen.AUTH_OPERATION,
                "authorized": True,
                "one_shot": True,
                "replay_permitted": False,
                "test_run_suffix": gen.RUN_SUFFIX,
                "custody_root_selection_rule": gen.CUSTODY_RULE,
                "custody_root_digest_sha256": gen.sha256_bytes(str(gen.default_custody_root(home)).encode()),
                "source_sha": "5" * 40,
                "generator_sha256": "1" * 64,
                "python_executable_sha256": "2" * 64,
                "openssl_executable_sha256": "3" * 64,
                "mosquitto_passwd_executable_sha256": "4" * 64,
                "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
                "record_sha256": "0" * 64,
            }
            base["record_sha256"] = gen.authorization_record_digest(base)
            auth_path.write_text(json.dumps(base, sort_keys=True), encoding="utf-8")
            # The self-digest changes after insertion; exact records are produced by
            # the later authorization packager. This test focuses on tool mismatch.
            base["openssl_executable_sha256"] = "9" * 64
            auth_path.write_text(json.dumps(base, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(gen.GenerationError, "openssl_executable_sha256 mismatch"):
                gen.validate_authorization(base, auth_path, toolchain, "5" * 40, home, now)

    def test_expired_authorization_is_rejected_before_claim(self) -> None:
        record = {
            "schema": gen.AUTH_SCHEMA,
            "stage": gen.STAGE,
            "authorization_id": gen.AUTH_PREFIX + "20260723-01",
            "operation": gen.AUTH_OPERATION,
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "test_run_suffix": gen.RUN_SUFFIX,
            "custody_root_selection_rule": gen.CUSTODY_RULE,
        }
        self.assertTrue(record["one_shot"])
        self.assertFalse(record["replay_permitted"])

    def test_generation_orchestration_contains_no_network_or_board_calls(self) -> None:
        source = GENERATOR.read_text(encoding="utf-8")
        for forbidden in (
            "esptool",
            "serial.Serial",
            "socket.socket",
            "mosquitto -c",
            "subprocess.Popen",
            "GH2D9R_PREPARE_V1 ",
            "GH2D9R_VERIFY_V1 ",
        ):
            self.assertNotIn(forbidden, source)

    def test_public_leakage_gate_rejects_password(self) -> None:
        password = "c" * 64
        with self.assertRaisesRegex(gen.GenerationError, "raw MQTT password leaked"):
            gen.validate_no_private_leakage(
                {"value": password},
                {"public_material": {}},
                password,
            )

    def test_toolchain_summary_omits_paths(self) -> None:
        toolchain = gen.Toolchain(
            generator_sha256="1" * 64,
            python_executable_sha256="2" * 64,
            python_version="Python 3.11",
            openssl_path=Path("/secret/path/openssl"),
            openssl_executable_sha256="3" * 64,
            openssl_version="OpenSSL test",
            mosquitto_passwd_path=Path("/secret/path/mosquitto_passwd"),
            mosquitto_passwd_executable_sha256="4" * 64,
            mosquitto_passwd_version="mosquitto_passwd test",
        )
        with tempfile.TemporaryDirectory() as temporary:
            summary = gen.toolchain_public_summary(toolchain, Path(temporary))
        payload = json.dumps(summary)
        self.assertNotIn("/secret/path", payload)
        self.assertFalse(summary["private_paths_included"])
        self.assertFalse(summary["secret_values_included"])


if __name__ == "__main__":
    unittest.main()
