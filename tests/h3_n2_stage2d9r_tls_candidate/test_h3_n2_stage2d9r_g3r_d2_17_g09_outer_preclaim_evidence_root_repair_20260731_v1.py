#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g09_outer_preclaim_evidence_root_repair_20260731_v1.py"
FAILURE = ROOT / "docs/failures/h3-n2-stage2d9r-g3r-d2-17-g09-preclaim-evidence-root-binding-failure-20260731-v1.json"
REPAIR = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g09-outer-preclaim-evidence-root-repair-20260731-v1.json"
ADAPTER = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1.py"

spec = importlib.util.spec_from_file_location("g09_root_repair", TOOL)
assert spec and spec.loader
repair_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair_module)


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def reproduce_exact_unbound_configure_failure(execution: Path) -> dict:
    sys.path.insert(0, str(execution))
    sys.path.insert(0, str(ADAPTER.parent))
    old_env = dict(os.environ)
    fake_serial = types.ModuleType("serial")
    fake_serial.Serial = type("Serial", (), {})
    previous_serial = sys.modules.get("serial")
    sys.modules["serial"] = fake_serial
    try:
        os.environ.update({
            "PYTHONDONTWRITEBYTECODE": "1",
            "GH_D2_17_DELIVERY_PROFILE": "private-package",
            "GH_D2_17_OUTER_PACKAGE_ROOT": str(execution),
            "GH_D2_17_LAUNCHER_PACKAGE_ROOT": str(execution),
            "GH_D2_13_LAUNCHER_PACKAGE_ROOT": str(execution),
            "GH_D2_14_LAUNCHER_PACKAGE_ROOT": str(execution),
            "GH_D2_15_LAUNCHER_PACKAGE_ROOT": str(execution),
            "GH_D2_16_LAUNCHER_PACKAGE_ROOT": str(execution),
        })
        import h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1 as frozen
        import h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1 as contract
        import h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1 as adapter

        frozen.bind_complete_chain()
        d2_11 = frozen._bound_d2_11()
        adapter.install_runtime_identity_adapter(
            d2_11,
            contract,
            {"execution_identity_sha256": "9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c"},
        )
        try:
            d2_11.configure_core()
        except Exception as exc:
            return {"exception_class": type(exc).__name__, "exception_code": str(exc)}
        raise AssertionError("EXPECTED_UNBOUND_CONFIGURE_FAILURE")
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        if previous_serial is None:
            sys.modules.pop("serial", None)
        else:
            sys.modules["serial"] = previous_serial


def validate_repaired_path() -> dict:
    calls: list[str] = []

    class FakeContract:
        @staticmethod
        def validate_execution_identity(*_args, **_kwargs):
            calls.append("identity")

        @staticmethod
        def validate_authorization_contract(*_args, **_kwargs):
            calls.append("authorization")

    def base_validate(*_args, **_kwargs):
        calls.append("base")
        return {"status": "PASS"}

    def forbidden_configure():
        raise AssertionError("CONFIGURE_CORE_MUST_NOT_BE_CALLED")

    core = SimpleNamespace(
        __file__=str(ROOT / "synthetic_core.py"),
        validate_private_metadata=lambda _home: calls.append("private"),
    )
    d2_11 = SimpleNamespace(
        core=core,
        _BASE_VALIDATE_AUTHORIZATION=base_validate,
        configure_core=forbidden_configure,
    )
    result = repair_module.validate_outer_preclaim_without_unbound_configure(
        d2_11=d2_11,
        d2_17_contract=FakeContract,
        authorization_path=ROOT / "synthetic-authorization.json",
        authorization={"authorization_record_sha256": "a" * 64},
        request={"request_binding_sha256": "b" * 64},
        identity={"execution_identity_sha256": "c" * 64},
        package_root=ROOT,
        python_path=Path(sys.executable),
        openssl_path=Path("/bin/true"),
        esptool_path=Path("/bin/true"),
        mosquitto_path=Path("/bin/true"),
        now=datetime.now(timezone.utc),
        home=ROOT,
    )
    assert calls == ["identity", "authorization", "private", "base"], calls
    assert result["configured_core_called"] is False
    return result


def main() -> int:
    failure = load(FAILURE)
    repair = load(REPAIR)
    repair_module.verify_self_binding(
        failure,
        "failure_disposition_binding_sha256",
        "3430906e3b3fb7890e2bade085e5c7adb949444005fe421698c640a0913d35f0",
    )
    repair_module.verify_self_binding(
        repair,
        "repair_decision_binding_sha256",
        "c5bdee9fb5f14120087dc8377a46e959c4030a2b73dc1f753f3326d157172720",
    )
    assert failure["authorization_claimed"] is False
    assert failure["authorization_consumed"] is False
    assert failure["all_physical_operation_flags_false"] is True
    assert repair["next_gate"] == "D1-H3N2-STAGE2D9R-G3R-D2-17-G10-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01"

    execution = Path(os.environ["D2_17_EXECUTION_ROOT"]).resolve(strict=True)
    reproduced = reproduce_exact_unbound_configure_failure(execution)
    assert reproduced == {
        "exception_class": "ExecutionError",
        "exception_code": "PREPARE_EVIDENCE_ROOT_NOT_BOUND",
    }, reproduced
    repaired = validate_repaired_path()

    public_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (FAILURE, REPAIR, TOOL)
    )
    for forbidden in ("/Users/", "ActiveTestRuns", "BEGIN PRIVATE KEY", "D2_17_AUTHORIZATION.json"):
        assert forbidden not in public_text, forbidden

    print(json.dumps({
        "status": "PASS",
        "terminal_record_sha256": "f48c08cba7bbe10f4a769dc838c4fdd6571470c7c93d1b24fa02acf3b820ba85",
        "failure_disposition_binding_sha256": failure["failure_disposition_binding_sha256"],
        "repair_decision_binding_sha256": repair["repair_decision_binding_sha256"],
        "reproduced_exception_class": reproduced["exception_class"],
        "reproduced_exception_code": reproduced["exception_code"],
        "configured_core_called_by_repair": repaired["configured_core_called"],
        "authorization_claimed": False,
        "authorization_consumed": False,
        "all_physical_operation_flags_false": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
