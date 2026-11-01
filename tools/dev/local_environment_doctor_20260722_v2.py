#!/usr/bin/env python3
"""Run the local environment audit with isolated ESPHome CLI support.

ESPHome is intentionally allowed to live in a dedicated pipx environment rather
than the project's general Python virtual environment. This wrapper keeps every
V1 audit boundary intact and changes only the ESPHome provenance check.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence


BASE_PATH = Path(__file__).resolve().with_name(
    "local_environment_doctor_20260722_v1.py"
)
SCRIPT_SCHEMA = "gh.dev.local-environment-doctor/2"


def load_base_module():
    specification = importlib.util.spec_from_file_location(
        "local_environment_doctor_20260722_v1_base", BASE_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"unable to load {BASE_PATH}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


BASE = load_base_module()
ORIGINAL_CHECK_PYTHON = BASE.check_python


def check_python(
    policy: dict[str, Any],
    results: list[Any],
    venv: Path,
) -> None:
    """Accept either an in-venv ESPHome package or an exact isolated CLI."""

    start = len(results)
    ORIGINAL_CHECK_PYTHON(policy, results, venv)
    generated = results[start:]
    esphome_result = next(
        (item for item in generated if item.code == "python.package.esphome"),
        None,
    )

    if esphome_result is None or esphome_result.status != "FAIL":
        return

    results.remove(esphome_result)
    executable = shutil.which("esphome")
    expected_text = str(policy["tooling"]["expected_versions"]["esphome"])
    expected_version = BASE.parse_version(expected_text)

    if not executable:
        BASE.add(
            results,
            "FAIL",
            "tool.esphome",
            "ESPHome is unavailable both in the configured virtual environment and as an isolated CLI.",
            expected=expected_text,
        )
        return

    rc, output = BASE.run_text([executable, "version"], timeout=15)
    actual_version = BASE.parse_version(output)
    version_ok = rc == 0 and actual_version == expected_version
    resolved = Path(executable).expanduser().resolve()
    normalized = str(resolved).replace("\\", "/")
    deployment = (
        "pipx"
        if "/.local/pipx/venvs/esphome/" in normalized
        else "isolated-cli"
    )

    BASE.add(
        results,
        "PASS" if version_ok else "FAIL",
        "tool.esphome",
        f"ESPHome isolated CLI reports {output or 'no version output'}.",
        executable=executable,
        resolved_executable=str(resolved),
        deployment=deployment,
        expected=expected_text,
    )
    if version_ok:
        BASE.add(
            results,
            "INFO",
            "python.package.esphome_isolation",
            "ESPHome is intentionally isolated from the general project virtual environment.",
            deployment=deployment,
            virtual_environment=str(venv),
        )


def main(argv: Sequence[str] | None = None) -> int:
    original_check = BASE.check_python
    original_schema = BASE.SCRIPT_SCHEMA
    BASE.check_python = check_python
    BASE.SCRIPT_SCHEMA = SCRIPT_SCHEMA
    try:
        return BASE.main(argv)
    finally:
        BASE.check_python = original_check
        BASE.SCRIPT_SCHEMA = original_schema


if __name__ == "__main__":
    raise SystemExit(main())
