#!/usr/bin/env python3
"""Require two clean Stage2D9 G3 builds to be byte-identical."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FIXED_BUILD_EPOCH = 1784678400
FIXED_BUILD_TIME_STR = "2026-07-22 00:00:00 +0000"
ROLES = ("g3", "recovery")
FILES = ("bootloader.bin", "partitions.bin", "firmware.bin")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-root", required=True)
    parser.add_argument("--second-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    first_root = Path(args.first_root).resolve()
    second_root = Path(args.second_root).resolve()
    roles: dict[str, dict[str, dict[str, int | str | bool]]] = {}

    for role in ROLES:
        role_results: dict[str, dict[str, int | str | bool]] = {}
        for filename in FILES:
            first = first_root / role / filename
            second = second_root / role / filename
            require(first.is_file(), f"first build missing {role}/{filename}")
            require(second.is_file(), f"second build missing {role}/{filename}")
            first_digest = sha256(first)
            second_digest = sha256(second)
            require(
                first_digest == second_digest,
                f"non-reproducible binary: {role}/{filename}",
            )
            role_results[filename] = {
                "byte_identical": True,
                "sha256": first_digest,
                "size": first.stat().st_size,
            }
        firmware = (first_root / role / "firmware.bin").read_bytes()
        require(
            FIXED_BUILD_TIME_STR.encode("ascii") in firmware,
            f"fixed build timestamp missing from {role}/firmware.bin",
        )
        role_results["fixed_build_time"] = {
            "present": True,
            "value": FIXED_BUILD_TIME_STR,
        }
        roles[role] = role_results

    report = {
        "schema": "gh.h3.n2.stage2d9-g3-reproducibility/1",
        "status": "pass",
        "gate": "LOCKED",
        "clean_build_count": 2,
        "fixed_build_epoch": FIXED_BUILD_EPOCH,
        "fixed_build_time": FIXED_BUILD_TIME_STR,
        "byte_identical": True,
        "roles": roles,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
