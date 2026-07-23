from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
GEN_PATH = ROOT / "tools/h3_n2_stage2d9r_private_command_material_generator_20260724_v1.py"
GATE_PATH = ROOT / "tools/h3_n2_stage2d9r_private_command_material_gate_20260724_v1.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = load("command_gen", GEN_PATH)
gate = load("command_gate", GATE_PATH)


class CommandMaterialTests(unittest.TestCase):
    def make_auth(self, home: Path, source: str, binding: str, generator_sha: str, python_sha: str) -> dict:
        now = datetime.now(timezone.utc)
        record = {
            "schema": gen.AUTH_SCHEMA,
            "stage": gen.STAGE,
            "authorization_id": "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-TEST-01",
            "operation": gen.AUTH_OPERATION,
            "authorized": True,
            "one_shot": True,
            "replay_permitted": False,
            "test_run_suffix": gen.RUN_SUFFIX,
            "custody_root_selection_rule": gen.CUSTODY_RULE,
            "source_sha": source,
            "implementation_binding": binding,
            "generator_sha256": generator_sha,
            "python_executable_sha256": python_sha,
            "custody_root_digest_sha256": gen.sha256_bytes(str(gen.default_root(home)).encode()),
            "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        }
        record["record_sha256"] = gen.authorization_digest(record)
        return record

    def test_probe_is_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            generator = GEN_PATH.resolve()
            data = gen.probe_summary(generator, home)
            self.assertFalse(data["custody_root_exists"])
            self.assertFalse(data["secret_values_included"])
            self.assertFalse(data["board_operation"])

    def test_valid_generation_and_gate(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            source = "1" * 40
            binding = "2" * 40
            generator_sha = gen.sha256_file(GEN_PATH)
            python_sha = gen.sha256_file(Path(gen.sys.executable).resolve())
            auth = self.make_auth(home, source, binding, generator_sha, python_sha)
            auth_path = home / "auth.json"
            auth_path.write_text(json.dumps(auth))
            with (
                mock.patch.object(gen.secrets, "token_hex", return_value="ab" * 32),
                mock.patch.object(gen, "validate_root", return_value=None),
            ):
                result = gen.execute(auth_path, source, binding, None, GEN_PATH.resolve(), home)
            self.assertEqual(result["status"], "PASS")
            root = gen.default_root(home)
            private = json.loads((root / gen.PRIVATE_DESCRIPTOR).read_text())
            public = json.loads((root / gen.PUBLIC_DESCRIPTOR).read_text())
            with mock.patch.object(gate, "private_path", return_value=True):
                gate.validate(private, public)
            self.assertEqual(public["unlock_digest_sha256"], hashlib.sha256(bytes.fromhex("ab" * 32)).hexdigest())
            self.assertNotIn("ab" * 32, json.dumps(private))
            self.assertNotIn("ab" * 32, json.dumps(public))
            marker = gen.default_marker(home, auth["authorization_id"])
            self.assertEqual(json.loads(marker.read_text())["status"], "CONSUMED")

    def test_source_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            source = "1" * 40
            binding = "2" * 40
            record = self.make_auth(home, source, binding, gen.sha256_file(GEN_PATH), gen.sha256_file(Path(gen.sys.executable).resolve()))
            with self.assertRaises(gen.GenerationError):
                gen.validate_authorization(record, "3" * 40, binding, record["generator_sha256"], record["python_executable_sha256"], home, datetime.now(timezone.utc))

    def test_binding_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            source = "1" * 40
            binding = "2" * 40
            record = self.make_auth(home, source, binding, gen.sha256_file(GEN_PATH), gen.sha256_file(Path(gen.sys.executable).resolve()))
            with self.assertRaises(gen.GenerationError):
                gen.validate_authorization(record, source, "3" * 40, record["generator_sha256"], record["python_executable_sha256"], home, datetime.now(timezone.utc))

    def test_expired_authorization_fails(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            source = "1" * 40
            binding = "2" * 40
            record = self.make_auth(home, source, binding, gen.sha256_file(GEN_PATH), gen.sha256_file(Path(gen.sys.executable).resolve()))
            old = datetime.now(timezone.utc) - timedelta(hours=3)
            record["issued_at"] = old.isoformat().replace("+00:00", "Z")
            record["expires_at"] = (old + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
            record["record_sha256"] = gen.authorization_digest(record)
            with self.assertRaises(gen.GenerationError):
                gen.validate_authorization(record, source, binding, record["generator_sha256"], record["python_executable_sha256"], home, datetime.now(timezone.utc))

    def test_existing_root_fails(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            root = gen.default_root(home)
            root.mkdir(parents=True)
            with self.assertRaises(gen.GenerationError):
                gen.validate_root(root, home, None)

    def test_consumed_marker_fails(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            source = "1" * 40
            binding = "2" * 40
            record = self.make_auth(home, source, binding, gen.sha256_file(GEN_PATH), gen.sha256_file(Path(gen.sys.executable).resolve()))
            marker = gen.default_marker(home, record["authorization_id"])
            marker.parent.mkdir(parents=True)
            marker.write_text("{}")
            with self.assertRaises(gen.GenerationError):
                gen.validate_authorization(record, source, binding, record["generator_sha256"], record["python_executable_sha256"], home, datetime.now(timezone.utc))

    def test_gate_rejects_zero_digest(self):
        private = {
            "schema": gate.PRIVATE_SCHEMA, "state": gate.STATE,
            "source_sha": "1"*40, "implementation_binding": "2"*40,
            "generator_sha256": "3"*64, "python_executable_sha256": "4"*64,
            "public_descriptor_sha256": "5"*64, "test_run_suffix": "tlsvalid01",
            "custody_root": "/Users/example/private", "custody_root_mode": "0700",
            "unlock_token": {"relative_path": "unlock-token.hex", "mode": "0600", "file_sha256": "6"*64, "unlock_digest_sha256": "0"*64},
            "authorization": {"authorization_id": "U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-X", "operation": "GENERATE_PRIVATE_COMMAND_MATERIAL", "authorized": True, "consumed": True, "one_shot": True, "replay_permitted": False, "record_sha256": "7"*64},
        }
        for key in gate.FALSE_PRIVATE:
            private[key] = False
        public = {
            "schema": gate.PUBLIC_SCHEMA, "state": gate.STATE,
            "source_sha": "1"*40, "implementation_binding": "2"*40,
            "test_run_suffix": "tlsvalid01", "unlock_digest_sha256": "0"*64,
            "private_material_package_sha256": "8"*64,
        }
        for key in gate.FALSE_PUBLIC:
            public[key] = False
        with self.assertRaises(gate.GateError):
            gate.validate(private, public)


if __name__ == "__main__":
    unittest.main()
