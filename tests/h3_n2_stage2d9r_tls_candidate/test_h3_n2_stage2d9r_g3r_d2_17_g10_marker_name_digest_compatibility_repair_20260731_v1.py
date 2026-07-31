from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from h3_n2_stage2d9r_g3r_d2_17_g10_marker_name_digest_compatibility_repair_20260731_v1 import (
    MarkerDigestCompatibilityError,
    install_runtime_marker_digest_adapter,
    marker_contract,
    patch_core_marker_digest,
)


class FakeCore:
    @staticmethod
    def sha256_bytes(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()


class FakeD211:
    def __init__(self) -> None:
        self.core = FakeCore()
        self.configure_calls = 0
        self.handoff = SimpleNamespace(configure_core=None)

    def configure_core(self):
        self.configure_calls += 1
        return self.core


class TestMarkerDigestCompatibilityRepair(unittest.TestCase):
    def test_00_exact_frozen_executor_contract_mismatch_is_real(self):
        execution = Path(os.environ["D2_17_EXECUTION_ROOT"]).resolve(strict=True)
        sys.path.insert(0, str(execution))
        import h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1 as frozen

        frozen.bind_complete_chain()
        d2_11 = frozen._bound_d2_11()
        request_id = frozen.contract.D2_REQUEST_ID
        contract = marker_contract(request_id)
        authorization_value = hashlib.sha256(request_id.encode()).hexdigest()
        marker_name = d2_11.core.sha256_bytes(request_id.encode()) + ".json"
        inherited_value = d2_11.core.sha256_bytes(marker_name.encode())
        self.assertEqual(authorization_value, contract["authorization_marker_digest_sha256"])
        self.assertEqual(marker_name, contract["marker_name"])
        self.assertEqual(inherited_value, contract["inherited_marker_name_digest_sha256"])
        self.assertNotEqual(inherited_value, authorization_value)

    def test_10_exact_core_patch_changes_only_marker_filename_digest(self):
        execution = Path(os.environ["D2_17_EXECUTION_ROOT"]).resolve(strict=True)
        sys.path.insert(0, str(execution))
        import h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1 as frozen

        frozen.bind_complete_chain()
        core = frozen._bound_d2_11().core
        request_id = frozen.contract.D2_REQUEST_ID
        contract = marker_contract(request_id)
        unrelated = b"unrelated-payload"
        before_unrelated = core.sha256_bytes(unrelated)
        first = patch_core_marker_digest(core, request_id)
        second = patch_core_marker_digest(core, request_id)
        self.assertFalse(first["idempotent_recheck"])
        self.assertTrue(second["idempotent_recheck"])
        self.assertEqual(core.sha256_bytes(unrelated), before_unrelated)
        self.assertEqual(
            core.sha256_bytes(request_id.encode()),
            contract["authorization_marker_digest_sha256"],
        )
        self.assertEqual(
            core.sha256_bytes(contract["marker_name"].encode()),
            contract["authorization_marker_digest_sha256"],
        )

    def test_20_runtime_install_is_idempotent_and_binding_locked(self):
        module = FakeD211()
        first = install_runtime_marker_digest_adapter(module, "request-a")
        second = install_runtime_marker_digest_adapter(module, "request-a")
        self.assertFalse(first["idempotent_recheck"])
        self.assertTrue(second["idempotent_recheck"])
        core = module.configure_core()
        contract = marker_contract("request-a")
        self.assertEqual(
            core.sha256_bytes(contract["marker_name"].encode()),
            contract["authorization_marker_digest_sha256"],
        )
        self.assertIs(module.handoff.configure_core, module.configure_core)
        with self.assertRaisesRegex(
            MarkerDigestCompatibilityError,
            "RUNTIME_MARKER_DIGEST_ADAPTER_BINDING_DRIFT",
        ):
            install_runtime_marker_digest_adapter(module, "request-b")

    def test_30_invalid_core_and_source_are_fail_closed_and_host_only(self):
        with self.assertRaisesRegex(
            MarkerDigestCompatibilityError, "CORE_SHA256_BYTES_MISSING"
        ):
            patch_core_marker_digest(object(), "request")
        path = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g10_marker_name_digest_compatibility_repair_20260731_v1.py"
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", text)
        tree = ast.parse(text)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        for forbidden in ("serial", "subprocess", "socket", "esptool", "mosquitto"):
            self.assertNotIn(forbidden, imported)
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        for forbidden in ("run", "Popen", "system", "flash_firmware", "baseline"):
            self.assertNotIn(forbidden, called)


if __name__ == "__main__":
    unittest.main()
