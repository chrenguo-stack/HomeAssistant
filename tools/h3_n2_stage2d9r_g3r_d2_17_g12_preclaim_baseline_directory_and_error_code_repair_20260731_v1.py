#!/usr/bin/env python3
"""Host-only G12 repair helpers for baseline work-directory creation and error codes."""
from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any, Callable


class RepairError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RepairError(code)


def inherited_error_code(exc: BaseException) -> str:
    """Preserve an inherited string subcode before falling back to the class name."""
    if exc.args and isinstance(exc.args[0], str) and exc.args[0]:
        return exc.args[0]
    return type(exc).__name__


def install_baseline_work_directory_repair(core: Any) -> dict[str, Any]:
    """Wrap ``core.baseline`` and create its output parent exactly once."""
    original: Callable[..., Any] = core.baseline
    require(not getattr(original, "_g12_baseline_directory_repaired", False),
            "G12_BASELINE_REPAIR_ALREADY_INSTALLED")

    def repaired(selected: Any, esptool_path: Path, work: Path,
                 authorization: dict[str, Any]) -> Any:
        work = Path(work)
        require(not work.exists(), "G12_BASELINE_WORK_DIRECTORY_ALREADY_EXISTS")
        work.mkdir(parents=True, mode=0o700)
        os.chmod(work, 0o700)
        require(work.is_dir() and not work.is_symlink(),
                "G12_BASELINE_WORK_DIRECTORY_INVALID")
        return original(selected, esptool_path, work, authorization)

    repaired._g12_baseline_directory_repaired = True  # type: ignore[attr-defined]
    repaired._g12_original_baseline = original  # type: ignore[attr-defined]
    core.baseline = repaired
    return {
        "installed": True,
        "creates_work_directory_before_inherited_baseline": True,
        "exclusive_reuse_rejected": True,
        "mode": "0700",
        "physical_operation": False,
    }


def inspect_baseline_source(source: str) -> dict[str, bool]:
    """Statically classify the inherited baseline directory defect."""
    tree = ast.parse(source)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "baseline"]
    require(len(functions) == 1, "BASELINE_FUNCTION_NOT_UNIQUE")
    fn = functions[0]

    creates_work = False
    constructs_partition = False
    invokes_read_flash = False
    read_flash_index: int | None = None
    mkdir_index: int | None = None

    for index, node in enumerate(ast.walk(fn)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "mkdir":
                creates_work = True
                mkdir_index = index if mkdir_index is None else min(mkdir_index, index)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "partition":
                    constructs_partition = True
        if isinstance(node, ast.Constant) and node.value == "read_flash":
            invokes_read_flash = True
            read_flash_index = index if read_flash_index is None else min(read_flash_index, index)

    return {
        "baseline_constructs_partition_under_work_directory": constructs_partition,
        "baseline_invokes_read_flash_to_partition_path": invokes_read_flash,
        "baseline_creates_work_directory_before_read_flash": bool(
            creates_work and mkdir_index is not None and read_flash_index is not None
            and mkdir_index < read_flash_index
        ),
    }
