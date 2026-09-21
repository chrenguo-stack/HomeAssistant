#!/usr/bin/env python3
"""Fail closed if an N3-W production firmware contains retired lab harness code."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

FORBIDDEN = (
    "Phase4PhysicalHarness",
    "N3wLabDiagnostics",
    "N3wRtcBreadcrumb",
    "n3w_phase4_physical_harness",
    "n3w_lab_diagnostics",
    "n3w_rtc_breadcrumb",
    "n3w_rtc_breadcrumb_",
    "gh_n3w_diag",
    "N3W_DIAG_DISCOVERY",
    "PHASE4_LAB_TELEMETRY",
    "phase4_source_harness",
    "phase4_lab_diagnostics",
)

POSITIVE_ELF = (
    "GreenhouseN3wCore",
    "SimpleProductComponent",
)

POSITIVE_BINARY = (
    "gh.telemetry/1",
    "air_temperature_c",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exactly_one(root: Path, name: str) -> Path:
    matches = sorted(root.rglob(name))
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one {name}, found {len(matches)}")
    return matches[0]


def printable_strings(data: bytes, minimum: int = 4) -> str:
    chunks: list[str] = []
    current = bytearray()
    for value in data:
        if 0x20 <= value <= 0x7E:
            current.append(value)
        else:
            if len(current) >= minimum:
                chunks.append(current.decode("ascii"))
            current.clear()
    if len(current) >= minimum:
        chunks.append(current.decode("ascii"))
    return "\n".join(chunks)


def find_nm() -> str:
    direct = shutil.which("riscv32-esp-elf-nm")
    if direct:
        return direct
    home = Path.home()
    candidates = sorted(
        home.glob(".platformio/packages/**/bin/riscv32-esp-elf-nm")
    )
    if candidates:
        return str(candidates[0])
    fallback = shutil.which("nm")
    if fallback:
        return fallback
    raise SystemExit("no nm executable found")


def assert_absent(label: str, text: str) -> None:
    hits = [marker for marker in FORBIDDEN if marker in text]
    if hits:
        raise SystemExit(
            f"{label}: forbidden lab marker(s) present: {', '.join(hits)}"
        )


def assert_present(label: str, text: str, markers: tuple[str, ...]) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise SystemExit(
            f"{label}: positive control missing: {', '.join(missing)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-root", type=Path, required=True)
    args = parser.parse_args()

    build_root = args.build_root.resolve()
    firmware_bin = exactly_one(build_root, "firmware.bin")
    firmware_elf = exactly_one(build_root, "firmware.elf")
    firmware_map = exactly_one(build_root, "firmware.map")

    nm = find_nm()
    nm_result = subprocess.run(
        [nm, "-C", str(firmware_elf)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if nm_result.returncode != 0:
        raise SystemExit(
            f"nm failed rc={nm_result.returncode}: {nm_result.stderr.strip()}"
        )

    elf_symbols = nm_result.stdout
    map_text = firmware_map.read_text(encoding="utf-8", errors="replace")
    binary_text = printable_strings(firmware_bin.read_bytes())

    assert_absent("firmware.elf symbols", elf_symbols)
    assert_absent("firmware.map", map_text)
    assert_absent("firmware.bin strings", binary_text)

    assert_present("firmware.elf symbols", elf_symbols, POSITIVE_ELF)
    assert_present("firmware.bin strings", binary_text, POSITIVE_BINARY)

    print("N3W_PRODUCTION_BINARY_DEHARNESS_PROOF=PASS")
    print(f"FIRMWARE_BIN={firmware_bin}")
    print(f"FIRMWARE_BYTES={firmware_bin.stat().st_size}")
    print(f"FIRMWARE_SHA256={sha256(firmware_bin)}")
    print(f"ELF_POSITIVE_CONTROLS={','.join(POSITIVE_ELF)}")
    print(f"BINARY_POSITIVE_CONTROLS={','.join(POSITIVE_BINARY)}")
    print(f"FORBIDDEN_MARKER_COUNT={len(FORBIDDEN)}")
    print("PHASE4_HARNESS_PRESENT=false")
    print("LAB_DIAGNOSTICS_PRESENT=false")
    print("RTC_BREADCRUMB_PRESENT=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
