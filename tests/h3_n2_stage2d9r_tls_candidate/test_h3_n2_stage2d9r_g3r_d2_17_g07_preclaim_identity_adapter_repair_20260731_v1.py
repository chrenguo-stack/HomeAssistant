from __future__ import annotations

import inspect
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1 import (
    IdentityAdapterRepairError,
    install_runtime_identity_adapter,
)


class FakeContract:
    def __init__(self) -> None:
        self.calls = []

    def validate_authorization_contract(
        self, authorization, request, identity, *, now=None
    ):
        self.calls.append((authorization, request, identity, now))
        if not isinstance(identity, dict):
            raise TypeError("identity must be a mapping")
        return authorization


class FakeCore:
    pass


class FakeD211:
    def __init__(self) -> None:
        self._BOUND_PHYSICAL_REQUEST = {"request_binding_sha256": "r" * 64}
        self.handoff = SimpleNamespace(configure_core=None)
        self.base_calls = []
        self.original_configure_calls = 0
        self._BASE_VALIDATE_AUTHORIZATION = self.base_validate
        self.configure_core = self.original_configure

    def base_validate(self, *args, **kwargs):
        self.base_calls.append((args, kwargs))
        return {"authorization_record_sha256": "a" * 64}

    def original_configure(self):
        self.original_configure_calls += 1
        core = FakeCore()
        core.validate_authorization = lambda *_a, **_k: None
        return core


class TestIdentityAdapterRepair(unittest.TestCase):
    def test_frozen_runtime_signature_mismatch_is_real(self):
        execution = Path(os.environ["D2_17_EXECUTION_ROOT"]).resolve(strict=True)
        sys.path.insert(0, str(execution))
        import h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1 as frozen

        frozen.bind_complete_chain()
        d2_11 = frozen._bound_d2_11()
        self.assertIs(d2_11.contract, frozen.contract)
        parameters = list(
            inspect.signature(
                d2_11.contract.validate_authorization_contract
            ).parameters
        )
        self.assertEqual(parameters[:3], ["authorization", "request", "identity"])
        source = inspect.getsource(d2_11.configure_core)
        self.assertIn("value, _BOUND_PHYSICAL_REQUEST, package_root", source)
        request = {"source_sha": "s" * 40, "request_binding_sha256": "r" * 64}
        with self.assertRaises(TypeError):
            d2_11.contract.validate_authorization_contract(
                {}, request, Path("/tmp/package")
            )

    def test_adapter_passes_identity_not_package_root(self):
        module = FakeD211()
        contract = FakeContract()
        identity = {
            "execution_identity_sha256": "9" * 64,
            "execution_package_sha256": "e" * 64,
        }
        report = install_runtime_identity_adapter(module, contract, identity)
        self.assertTrue(report["installed"])
        core = module.configure_core()
        now = object()
        authorization = core.validate_authorization(
            Path("authorization.json"),
            package_root=Path("/tmp/package"),
            now=now,
        )
        self.assertEqual(
            authorization["authorization_record_sha256"], "a" * 64
        )
        self.assertEqual(contract.calls[0][2], identity)
        self.assertIs(contract.calls[0][3], now)
        self.assertIs(module.handoff.configure_core, module.configure_core)

    def test_reinstall_is_idempotent_and_binding_locked(self):
        module = FakeD211()
        contract = FakeContract()
        identity = {"execution_identity_sha256": "1" * 64}
        first = install_runtime_identity_adapter(module, contract, identity)
        second = install_runtime_identity_adapter(module, contract, dict(identity))
        self.assertFalse(first["idempotent_recheck"])
        self.assertTrue(second["idempotent_recheck"])
        with self.assertRaisesRegex(
            IdentityAdapterRepairError,
            "RUNTIME_IDENTITY_ADAPTER_BINDING_DRIFT",
        ):
            install_runtime_identity_adapter(
                module,
                contract,
                {"execution_identity_sha256": "2" * 64},
            )

    def test_missing_request_and_invalid_identity_fail_closed(self):
        module = FakeD211()
        contract = FakeContract()
        with self.assertRaisesRegex(
            IdentityAdapterRepairError,
            "EXECUTION_IDENTITY_TYPE_INVALID",
        ):
            install_runtime_identity_adapter(
                module, contract, None
            )  # type: ignore[arg-type]
        install_runtime_identity_adapter(
            module,
            contract,
            {"execution_identity_sha256": "3" * 64},
        )
        module._BOUND_PHYSICAL_REQUEST = None
        with self.assertRaisesRegex(
            IdentityAdapterRepairError,
            "PHYSICAL_REQUEST_NOT_BOUND",
        ):
            module.configure_core().validate_authorization(
                Path("authorization.json"),
                package_root=Path("/tmp/package"),
            )

    def test_source_has_no_physical_or_private_path_operations(self):
        import ast

        path = (
            ROOT
            / "tools/h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1.py"
        )
        text = path.read_text()
        self.assertNotIn("/Users/", text)
        tree = ast.parse(text)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        for forbidden in (
            "serial",
            "subprocess",
            "socket",
            "esptool",
            "mosquitto",
        ):
            self.assertNotIn(forbidden, imported)
        called = {
            node.func.attr
            if isinstance(node.func, ast.Attribute)
            else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        for forbidden in (
            "chmod",
            "run",
            "Popen",
            "flash_firmware",
            "baseline",
        ):
            self.assertNotIn(forbidden, called)


if __name__ == "__main__":
    unittest.main()
