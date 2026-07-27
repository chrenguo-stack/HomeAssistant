#!/usr/bin/env python3
"""V2 repair: remove the self-referential package-set field before freezing."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

V1_PATH = Path(__file__).with_name(
    "h3_n2_stage2d9r_successor_d2_execution_packager_20260727_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage2d9r_execution_packager_v1", V1_PATH)
assert SPEC and SPEC.loader
V1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V1)

_ORIGINAL_BUILD_FILES = V1.build_files


def build_files(executor: Path, contract: Path, source_sha: str):
    files, descriptor = _ORIGINAL_BUILD_FILES(executor, contract, source_sha)
    descriptor.pop("package_set_sha256", None)
    files[V1.DESCRIPTOR_NAME] = json.dumps(
        descriptor, indent=2, sort_keys=True, ensure_ascii=False
    ).encode("utf-8") + b"\n"
    files["SHA256SUMS"] = "".join(
        f"{V1.sha256_bytes(files[name])}  {name}\n"
        for name in sorted(files)
        if name != "SHA256SUMS"
    ).encode("utf-8")
    return files, descriptor


V1.build_files = build_files

if __name__ == "__main__":
    raise SystemExit(V1.main())
