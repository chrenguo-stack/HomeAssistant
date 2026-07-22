#!/usr/bin/env python3
"""Host fault matrix for Stage2D8 dedicated-board G2 artifact guards."""

from __future__ import annotations

import argparse
import importlib.util
import json
import struct
import tempfile
from pathlib import Path
from types import ModuleType

PARTITION_MAGIC = 0x50AA


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load_packager(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("stage2d8_g2_packager_v63", path)
    require(spec is not None and spec.loader is not None, "packager import spec failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def partition_entry(
    label: str, ptype: int, subtype: int, offset: int, size: int, flags: int
) -> bytes:
    encoded = label.encode("ascii")
    require(len(encoded) <= 15, "partition label too long")
    return struct.pack(
        "<HBBII16sI",
        PARTITION_MAGIC,
        ptype,
        subtype,
        offset,
        size,
        encoded.ljust(16, b"\0"),
        flags,
    )


def partition_image(
    *, readonly: bool = True, test_offset: int = 0x400000, extra: bool = False
) -> bytes:
    entries = [
        partition_entry("nvs", 0x01, 0x02, 0x9000, 0x6000, 0),
        partition_entry("phy_init", 0x01, 0x01, 0xF000, 0x1000, 0),
        partition_entry("factory", 0x00, 0x00, 0x10000, 0x3F0000, 0),
        partition_entry(
            "gh2d8_nvs",
            0x01,
            0x02,
            test_offset,
            0x10000,
            0x1 if readonly else 0,
        ),
    ]
    if extra:
        entries.append(
            partition_entry("unexpected", 0x01, 0x02, 0x410000, 0x1000, 0)
        )
    return b"".join(entries) + b"\xff" * 32


def expect_pass(name: str, operation) -> dict[str, str]:
    operation()
    return {"case": name, "expected": "pass", "observed": "pass"}


def expect_reject(name: str, operation) -> dict[str, str]:
    try:
        operation()
    except SystemExit as exc:
        return {
            "case": name,
            "expected": "reject",
            "observed": "reject",
            "reason": str(exc),
        }
    raise SystemExit(f"fault case unexpectedly passed: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packager", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    packager_path = Path(args.packager).resolve()
    require(packager_path.is_file(), "packager missing")
    packager = load_packager(packager_path)
    results: list[dict[str, str]] = []

    with tempfile.TemporaryDirectory(prefix="stage2d8-g2-v63-") as temporary:
        root = Path(temporary)

        valid_partitions = root / "valid-partitions.bin"
        valid_partitions.write_bytes(partition_image())
        results.append(
            expect_pass(
                "P01_VALID_FROZEN_PARTITION_TABLE",
                lambda: packager.verify_partition_table(valid_partitions),
            )
        )

        writable_partitions = root / "writable-test-partition.bin"
        writable_partitions.write_bytes(partition_image(readonly=False))
        results.append(
            expect_reject(
                "P02_TEST_PARTITION_READONLY_FLAG_MISSING",
                lambda: packager.verify_partition_table(writable_partitions),
            )
        )

        wrong_offset = root / "wrong-test-offset.bin"
        wrong_offset.write_bytes(partition_image(test_offset=0x410000))
        results.append(
            expect_reject(
                "P03_TEST_PARTITION_OFFSET_DRIFT",
                lambda: packager.verify_partition_table(wrong_offset),
            )
        )

        extra_partition = root / "extra-partition.bin"
        extra_partition.write_bytes(partition_image(extra=True))
        results.append(
            expect_reject(
                "P04_UNEXPECTED_PARTITION_PRESENT",
                lambda: packager.verify_partition_table(extra_partition),
            )
        )

        valid_seed = root / "valid-seed.bin"
        valid_prefix = b"gh2d8_seed\0format_version\0"
        valid_seed.write_bytes(
            valid_prefix + b"\xff" * (0x10000 - len(valid_prefix))
        )
        results.append(
            expect_pass(
                "N01_VALID_PRESEEDED_IMAGE",
                lambda: packager.verify_seed_image(valid_seed),
            )
        )

        short_seed = root / "short-seed.bin"
        short_seed.write_bytes(b"gh2d8_seed")
        results.append(
            expect_reject(
                "N02_SEED_SIZE_MISMATCH",
                lambda: packager.verify_seed_image(short_seed),
            )
        )

        missing_seed_namespace = root / "missing-seed-namespace.bin"
        missing_seed_namespace.write_bytes(b"\xff" * 0x10000)
        results.append(
            expect_reject(
                "N03_SEED_NAMESPACE_MISSING",
                lambda: packager.verify_seed_image(missing_seed_namespace),
            )
        )

        target_namespace_leak = root / "target-namespace-leak.bin"
        target_prefix = b"gh2d8_seed\0gh2d8_state\0"
        target_namespace_leak.write_bytes(
            target_prefix + b"\xff" * (0x10000 - len(target_prefix))
        )
        results.append(
            expect_reject(
                "N04_TARGET_NAMESPACE_PRECREATED",
                lambda: packager.verify_seed_image(target_namespace_leak),
            )
        )

    report = {
        "schema": "gh.h3.n2.stage2d8-g2-host-fault-matrix/1",
        "status": "pass",
        "gate": "LOCKED",
        "case_count": len(results),
        "cases": results,
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
