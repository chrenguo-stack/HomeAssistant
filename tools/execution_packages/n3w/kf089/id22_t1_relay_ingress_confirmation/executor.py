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
    spec = importlib.util.spec_from_file_location("id22_executor_impl", IMPL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("ID22 implementation module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _assert_no_mutation_call_sites() -> None:
    tree = ast.parse(IMPL_PATH.read_text(encoding="utf-8"), filename=str(IMPL_PATH))
    prohibited_attrs = {
        "flash_begin",
        "flash_block",
        "flash_finish",
        "write_flash",
        "erase_flash",
        "erase_region",
        "write_mem",
    }
    prohibited_tokens = {
        "docker restart",
        "docker start",
        "docker stop",
        "docker rm",
        "docker exec",
        "docker compose up",
        "docker compose down",
        "mosquitto_pub",
        "mosquitto_sub",
    }
    source = IMPL_PATH.read_text(encoding="utf-8")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in prohibited_attrs:
            raise RuntimeError(f"prohibited mutation call site found: {node.func.attr}")
    lowered = source.lower()
    for token in prohibited_tokens:
        if token in lowered:
            raise RuntimeError(f"prohibited T1/MQTT mutation token found: {token}")


def self_check() -> None:
    impl = _load_impl()
    impl.self_check()
    _assert_no_mutation_call_sites()


def main() -> int:
    if "--self-check" in sys.argv[1:]:
        if sys.argv[1:] != ["--self-check"]:
            raise SystemExit("--self-check cannot be combined with execution arguments")
        self_check()
        print(json.dumps({"self_check": "PASS"}, sort_keys=True))
        return 0
    impl = _load_impl()
    return int(impl.main())


if __name__ == "__main__":
    raise SystemExit(main())
