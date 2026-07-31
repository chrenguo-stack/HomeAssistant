#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g12_preclaim_baseline_directory_and_error_code_repair_20260731_v1.py"
ACCEPTANCE = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g11-forensic-r2-root-cause-acceptance-20260731-v1.json"
PENDING = ROOT / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g12-private-package-static-check-authorization-pending-20260731-v1.json"


def canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load_module():
    spec = importlib.util.spec_from_file_location("g12_repair", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_binding(path: Path, field: str, expected: str) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    observed = value.pop(field)
    assert observed == expected
    assert canonical(value) == expected
    return value


def main() -> None:
    acceptance = verify_binding(
        ACCEPTANCE,
        "acceptance_binding_sha256",
        "74e96be6894ab6c744cbb4b74c3111d21ba0624b9b3f8f4a538951a16f6a0fe7",
    )
    pending = verify_binding(
        PENDING,
        "pending_binding_sha256",
        "741fb6de67f9dd0722835827e249c49d0498d1b2b1966c118efd1f183c54e8a6",
    )
    assert acceptance["root_cause"] == "BASELINE_OUTPUT_PARENT_DIRECTORY_NOT_CREATED_BEFORE_READ_FLASH"
    assert acceptance["authorization_claimed"] is False
    assert acceptance["authorization_consumed"] is False
    assert acceptance["preclaim_baseline_directory_present"] is False
    assert acceptance["baseline_partition_present"] is False
    assert pending["next_package_generation"] == "G12"
    assert pending["g12_private_package_created"] is False
    assert pending["g12_authorization_created"] is False

    repair = load_module()
    defective_source = '''\ndef baseline(selected, esptool_path, work, authorization):\n    partition = work / "baseline-test-partition.bin"\n    run_process(esptool_command(esptool_path, selected.device, "read_flash", "0x0", "0x1000", str(partition)), timeout=45, code="BASELINE_PARTITION_READ_FAILED")\n    return {"status": "PASS"}\n'''
    classification = repair.inspect_baseline_source(defective_source)
    assert classification == {
        "baseline_constructs_partition_under_work_directory": True,
        "baseline_invokes_read_flash_to_partition_path": True,
        "baseline_creates_work_directory_before_read_flash": False,
    }

    class InheritedExecutionError(RuntimeError):
        pass

    assert repair.inherited_error_code(InheritedExecutionError("BASELINE_PARTITION_READ_FAILED")) == "BASELINE_PARTITION_READ_FAILED"
    assert repair.inherited_error_code(InheritedExecutionError()) == "InheritedExecutionError"

    class FakeCore:
        calls = 0

        @staticmethod
        def baseline(selected, esptool_path, work, authorization):
            FakeCore.calls += 1
            assert work.is_dir()
            assert not work.is_symlink()
            assert stat.S_IMODE(work.stat().st_mode) == 0o700
            return {"status": "PASS", "physical_operation": False}

    installed = repair.install_baseline_work_directory_repair(FakeCore)
    assert installed["installed"] is True
    assert installed["physical_operation"] is False

    with tempfile.TemporaryDirectory(prefix="g12-baseline-repair-") as td:
        root = Path(td)
        work = root / "preclaim-baseline"
        result = FakeCore.baseline(None, Path("/bin/false"), work, {})
        assert result["status"] == "PASS"
        assert FakeCore.calls == 1
        try:
            FakeCore.baseline(None, Path("/bin/false"), work, {})
        except repair.RepairError as exc:
            assert str(exc) == "G12_BASELINE_WORK_DIRECTORY_ALREADY_EXISTS"
        else:
            raise AssertionError("existing work directory was not rejected")

    print(json.dumps({
        "status": "PASS",
        "root_cause": acceptance["root_cause"],
        "acceptance_binding_sha256": "74e96be6894ab6c744cbb4b74c3111d21ba0624b9b3f8f4a538951a16f6a0fe7",
        "pending_binding_sha256": "741fb6de67f9dd0722835827e249c49d0498d1b2b1966c118efd1f183c54e8a6",
        "directory_repair_installed": True,
        "inherited_subcode_preserved": True,
        "physical_operation": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
