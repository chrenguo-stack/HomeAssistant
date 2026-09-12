#!/usr/bin/env python3
"""Physical entry point for KF-089 ID18.

The direct-ROM implementation lives in executor_impl.py. This wrapper owns the
static self-check so the implementation can be scanned by AST for prohibited
call sites without embedding a self-referential forbidden source literal.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
IMPL_PATH = PACKAGE_DIR / "executor_impl.py"


def _load_impl():
    spec = importlib.util.spec_from_file_location("id18_executor_impl", IMPL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("ID18 implementation module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _assert_no_prohibited_call_sites() -> None:
    tree = ast.parse(IMPL_PATH.read_text(encoding="utf-8"), filename=str(IMPL_PATH))
    prohibited_attributes = {"write_" + "flash", "flash_" + "finish"}
    observed_low_level = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        if name in prohibited_attributes:
            raise RuntimeError(f"prohibited esptool call site found: {name}")
        if name in {"flash_begin", "flash_block", "flash_md5sum"}:
            observed_low_level.add(name)
    required = {"flash_begin", "flash_block", "flash_md5sum"}
    if not required.issubset(observed_low_level):
        raise RuntimeError("required direct-ROM call sites are incomplete")


def self_check() -> None:
    impl = _load_impl()
    impl.load_manifest(PACKAGE_DIR)
    impl.assert_read_only_argv(impl.build_read_mac_command("/dev/example"))
    for offset, size in (
        (impl.PARTITION_TABLE_OFFSET, impl.PARTITION_TABLE_SIZE),
        (impl.OTADATA_OFFSET, impl.OTADATA_SIZE),
        (impl.APP0_OFFSET, impl.SCHEMA5_FIRMWARE_SIZE),
        (impl.APP1_OFFSET, impl.SCHEMA5_FIRMWARE_SIZE),
    ):
        impl.assert_read_only_argv(
            impl.build_read_flash_command(
                "/dev/example", offset, size, Path("/tmp/id18-readback.bin")
            )
        )
    if impl.SCHEMA5_FIRMWARE_SIZE > impl.APP0_PARTITION_SIZE:
        raise RuntimeError("Schema-v5 image does not fit app0")
    if impl.EXPECTED_FLASH_WRITE_SIZE != 0x400:
        raise RuntimeError("unexpected frozen direct-ROM block size")
    _assert_no_prohibited_call_sites()


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
