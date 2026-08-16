#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILDER_PATH = ROOT / "tools" / "h3_n2_stage2d9r_tls_public_binding_builder_20260723_v1.py"
GATE_PATH = ROOT / "tools" / "h3_n2_stage2d9r_tls_candidate_descriptor_gate_20260723_v1.py"
CONFIG_PATH = Path(__file__).with_name(
    "stage2d9r_isolated_broker_public_config_20260723_v1.json"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load_module("stage2d9r_binding_builder", BUILDER_PATH)
gate = load_module("stage2d9r_descriptor_gate", GATE_PATH)


def run(*args: str) -> None:
    subprocess.run(
        ["openssl", *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class Stage2D9RTlsPublicBindingBuilderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="stage2d9r-pki-test-")
        cls.root = Path(cls.temp.name)
        cls.ca_key = cls.root / "ca.key"
        cls.ca_pem = cls.root / "ca.pem"
        cls.leaf_key = cls.root / "leaf.key"
        cls.leaf_csr = cls.root / "leaf.csr"
        cls.leaf_pem = cls.root / "leaf.pem"
        cls.wrong_leaf_pem = cls.root / "wrong-leaf.pem"
        cls.client_leaf_pem = cls.root / "client-leaf.pem"

        run(
            "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30",
            "-subj", "/CN=Stage2D9R Test Root CA",
            "-addext", "basicConstraints=critical,CA:TRUE",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign",
            "-keyout", str(cls.ca_key), "-out", str(cls.ca_pem),
        )
        run(
            "req", "-newkey", "rsa:2048", "-nodes",
            "-subj", "/CN=stage2d9r.local",
            "-keyout", str(cls.leaf_key), "-out", str(cls.leaf_csr),
        )
        cls._sign_leaf(cls.leaf_pem, "stage2d9r.local", "serverAuth")
        cls._sign_leaf(cls.wrong_leaf_pem, "wrong.local", "serverAuth")
        cls._sign_leaf(cls.client_leaf_pem, "stage2d9r.local", "clientAuth")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    @classmethod
    def _sign_leaf(cls, output: Path, san: str, eku: str) -> None:
        extension = cls.root / f"{output.stem}.ext"
        extension.write_text(
            "\n".join(
                [
                    "basicConstraints=critical,CA:FALSE",
                    "keyUsage=critical,digitalSignature,keyEncipherment",
                    f"extendedKeyUsage={eku}",
                    f"subjectAltName=DNS:{san}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        run(
            "x509", "-req", "-days", "30",
            "-in", str(cls.leaf_csr),
            "-CA", str(cls.ca_pem), "-CAkey", str(cls.ca_key),
            "-CAcreateserial", "-extfile", str(extension),
            "-out", str(output),
        )

    def config(self) -> dict:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def build(self, cert: Path | None = None, config: dict | None = None) -> dict:
        return builder.build_descriptor(
            self.ca_pem,
            cert or self.leaf_pem,
            config or self.config(),
            "8" * 64,
            "9" * 64,
            now=datetime.now(timezone.utc),
        )

    def assert_binding_error(self, callable_, message: str) -> None:
        with self.assertRaisesRegex(builder.BindingError, message):
            callable_()

    def test_valid_public_material_builds_frozen_descriptor(self) -> None:
        descriptor = self.build()
        self.assertEqual(descriptor["state"], gate.FROZEN)
        self.assertEqual(gate.validate(descriptor, gate.FROZEN), gate.FROZEN)
        self.assertFalse(descriptor["private_values_included"])
        self.assertFalse(descriptor["execution_authorized"])
        self.assertFalse(descriptor["network_operation_authorized"])

    def test_exact_hostname_and_san_are_required(self) -> None:
        self.assert_binding_error(
            lambda: self.build(self.wrong_leaf_pem),
            "broker DNS SAN is not the exact frozen hostname",
        )

    def test_server_auth_eku_is_required(self) -> None:
        self.assert_binding_error(
            lambda: self.build(self.client_leaf_pem),
            "broker leaf serverAuth EKU is missing",
        )

    def test_invalid_ca_pem_fails_closed(self) -> None:
        invalid = self.root / "invalid-ca.pem"
        invalid.write_text("not-a-certificate\n", encoding="utf-8")
        self.assert_binding_error(
            lambda: builder.build_descriptor(
                invalid,
                self.leaf_pem,
                self.config(),
                "8" * 64,
                "9" * 64,
            ),
            "openssl validation failed",
        )

    def test_raw_password_key_is_rejected(self) -> None:
        config = self.config()
        config["mqtt_password"] = "must-not-enter-public-config"
        self.assert_binding_error(
            lambda: self.build(config=config),
            "broker config contains forbidden key mqtt_password",
        )

    def test_non_test_topic_root_is_rejected(self) -> None:
        config = self.config()
        config["test_topic_root"] = "gh/v1/production"
        self.assert_binding_error(
            lambda: self.build(config=config),
            "broker config test_topic_root is outside gh-test",
        )

    def test_private_package_and_candidate_hashes_are_required(self) -> None:
        for private_hash, candidate_hash, message in (
            ("bad", "9" * 64, "private package sha256 is invalid"),
            ("8" * 64, "bad", "candidate digest sha256 is invalid"),
        ):
            self.assert_binding_error(
                lambda p=private_hash, c=candidate_hash: builder.build_descriptor(
                    self.ca_pem,
                    self.leaf_pem,
                    self.config(),
                    p,
                    c,
                ),
                message,
            )

    def test_public_config_is_not_mutated(self) -> None:
        config = self.config()
        original = deepcopy(config)
        self.build(config=config)
        self.assertEqual(config, original)

    def test_output_contains_hashes_not_private_material(self) -> None:
        descriptor = self.build()
        encoded = json.dumps(descriptor, sort_keys=True)
        self.assertNotIn("BEGIN PRIVATE KEY", encoded)
        self.assertNotIn("must-not-enter-public-config", encoded)
        for key in gate.HASH_FIELDS:
            self.assertRegex(descriptor["public_material"][key], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
