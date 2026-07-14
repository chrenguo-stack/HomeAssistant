from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "check_public_repository_safety.py"
SPEC = importlib.util.spec_from_file_location("public_repository_safety", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PublicRepositorySafetyTests(unittest.TestCase):
    def test_allows_repository_examples(self) -> None:
        self.assertIsNone(
            MODULE.blocked_path_reason("host/greenhouse-manager/.env.example")
        )
        self.assertIsNone(MODULE.blocked_path_reason("infra/certs/ca.example.pem"))

    def test_rejects_runtime_and_private_material_paths(self) -> None:
        self.assertEqual(
            MODULE.blocked_path_reason("host/greenhouse-manager/.env"),
            "credential-file-path",
        )
        self.assertEqual(
            MODULE.blocked_path_reason("firmware/secrets.yaml"),
            "credential-file-path",
        )
        self.assertEqual(
            MODULE.blocked_path_reason("homeassistant/.storage/core.config"),
            "runtime-state-path",
        )
        self.assertEqual(
            MODULE.blocked_path_reason("infra/certs/manager.key"),
            "private-material-path",
        )
        self.assertEqual(
            MODULE.blocked_path_reason("evidence/production-run.tar.gz"),
            "runtime-state-path",
        )
        self.assertEqual(
            MODULE.blocked_path_reason("artifacts/private-backup.zip"),
            "private-material-path",
        )

    def test_reports_location_without_echoing_secret(self) -> None:
        token = b"ghp_" + (b"a" * 40)
        secret = b"prefix\n" + token + b"\nsuffix\n"
        findings = MODULE.scan_blob("fixture.txt", secret)
        rendered = "\n".join(item.render() for item in findings)
        self.assertIn("github-access-token: fixture.txt:2", rendered)
        self.assertNotIn(token.decode(), rendered)

    def test_rejects_real_environment_identifiers(self) -> None:
        private_ip = b"192." + b"168.50.25"
        home_path = b"/" + b"Users/example/project"
        data = b"host=" + private_ip + b"\npath=" + home_path + b"\n"
        findings = MODULE.scan_blob("deployment.md", data)
        self.assertEqual(
            {item.rule for item in findings},
            {"developer-home-path", "private-network-address"},
        )

    def test_allows_documentation_network(self) -> None:
        self.assertEqual(MODULE.scan_blob("deployment.md", b"host=192.0.2.10\n"), [])

    def test_rejects_nonempty_sensitive_config_values(self) -> None:
        env_key = b"GH_MQTT_" + b"PASSWORD"
        dotenv = env_key + b"=" + b"not-for-publication\n"
        yaml = b"password" + b": " + b"not-for-publication\n"
        self.assertEqual(
            {item.rule for item in MODULE.scan_blob("service.env.example", dotenv)},
            {"nonempty-sensitive-env-value"},
        )
        self.assertEqual(
            {item.rule for item in MODULE.scan_blob("service.yaml", yaml)},
            {"nonempty-sensitive-yaml-value"},
        )

    def test_allows_secret_references_and_password_file_paths(self) -> None:
        env_key = b"GH_MQTT_" + b"PASSWORD"
        dotenv = (
            env_key + b"=${" + env_key + b"}\n" + env_key + b"_FILE=/run/secrets/mqtt\n"
        )
        yaml = b"password" + b": !secret wifi_" + b"password\n"
        self.assertEqual(MODULE.scan_blob("service.env.example", dotenv), [])
        self.assertEqual(MODULE.scan_blob("service.yaml", yaml), [])
