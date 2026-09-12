#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
IMPL_PATH = PACKAGE_DIR / "executor_impl.py"


def _load_impl():
    spec = importlib.util.spec_from_file_location("id20_executor_impl", IMPL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("ID20 implementation module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _assert_no_flash_mutation_call_sites() -> None:
    tree = ast.parse(IMPL_PATH.read_text(encoding="utf-8"), filename=str(IMPL_PATH))
    prohibited = {
        "flash_" + "begin",
        "flash_" + "block",
        "flash_" + "finish",
        "write_" + "flash",
        "erase_" + "flash",
        "erase_" + "region",
        "write_" + "mem",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in prohibited:
            raise RuntimeError(f"prohibited physical mutation call site found: {node.func.attr}")


def self_check() -> None:
    impl = _load_impl()
    impl.self_check()
    _assert_no_flash_mutation_call_sites()


def _argument_value(argv: list[str], name: str) -> str | None:
    prefix = name + "="
    for index, value in enumerate(argv):
        if value == name:
            return argv[index + 1] if index + 1 < len(argv) else None
        if value.startswith(prefix):
            return value[len(prefix):]
    return None


def _operator_interlock_completed(value: dict[str, Any]) -> bool:
    try:
        elapsed = float(value.get("observed_elapsed_seconds", -1))
        minimum = float(value.get("minimum_elapsed_seconds", -1))
    except (TypeError, ValueError):
        return False
    return (
        value.get("token_match") is True
        and value.get("single_normal_boot_attested") is True
        and value.get("fresh_rom_reentry_attested") is True
        and elapsed >= minimum >= 0
    )


def _repair_closure_evidence(impl: Any, root: Path) -> dict[str, Any] | None:
    closure_path = root / "closure.json"
    if not closure_path.is_file():
        return None
    closure = json.loads(closure_path.read_text(encoding="utf-8"))
    interlock_path = root / "operator_interlock.json"
    interlock: dict[str, Any] = {}
    if interlock_path.is_file():
        loaded = json.loads(interlock_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            interlock = loaded

    completed = _operator_interlock_completed(interlock)
    postcheck_pass = closure.get("boot_postcheck_result") == "PASS"
    closure["single_normal_boot_attested"] = completed
    closure["fresh_rom_reentry_attested"] = completed
    closure["application_booted"] = completed
    closure["schema5_application_boot_proven"] = postcheck_pass
    impl.id18.write_json(closure_path, closure)
    impl.id18.write_json(
        root / "evidence_manifest.json",
        {
            "schema_version": 1,
            "execution_id": closure.get("execution_id"),
            "authorization": closure.get("authorization"),
            "files": impl.evidence_manifest(root),
        },
    )
    return closure


def main() -> int:
    if "--self-check" in sys.argv[1:]:
        if sys.argv[1:] != ["--self-check"]:
            raise SystemExit("--self-check cannot be combined with execution arguments")
        self_check()
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0

    impl = _load_impl()
    evidence_arg = _argument_value(sys.argv[1:], "--evidence-root")

    real_print = print

    def _filtered_impl_print(*args: Any, **kwargs: Any) -> None:
        if kwargs.get("file") is sys.stderr:
            real_print(*args, **kwargs)

    impl.print = _filtered_impl_print
    rc = int(impl.main())

    repaired = None
    if evidence_arg:
        repaired = _repair_closure_evidence(impl, Path(evidence_arg).expanduser().resolve())
    if repaired is not None:
        real_print(json.dumps(repaired, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
