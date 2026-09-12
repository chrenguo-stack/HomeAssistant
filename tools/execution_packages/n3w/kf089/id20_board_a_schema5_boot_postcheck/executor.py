#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

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


def main() -> int:
    if "--self-check" in sys.argv[1:]:
        if sys.argv[1:] != ["--self-check"]:
            raise SystemExit("--self-check cannot be combined with execution arguments")
        self_check()
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0
    return int(_load_impl().main())


if __name__ == "__main__":
    raise SystemExit(main())