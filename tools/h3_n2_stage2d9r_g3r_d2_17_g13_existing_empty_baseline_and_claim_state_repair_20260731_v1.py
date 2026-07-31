#!/usr/bin/env python3
"""Host-only G13 repair for baseline work-directory compatibility and claim state."""
from __future__ import annotations

import ast
import os
import stat
from pathlib import Path
from typing import Any, Callable


class RepairError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RepairError(code)


def inherited_error_code(exc: BaseException) -> str:
    if exc.args and isinstance(exc.args[0], str) and exc.args[0]:
        return exc.args[0]
    return type(exc).__name__


def prepare_baseline_work_directory(work: Path) -> dict[str, Any]:
    path = Path(work)
    created = False
    if path.exists() or path.is_symlink():
        require(not path.is_symlink(), "G13_BASELINE_WORK_DIRECTORY_SYMLINK")
        require(path.is_dir(), "G13_BASELINE_WORK_DIRECTORY_NOT_DIRECTORY")
        mode = stat.S_IMODE(path.stat().st_mode)
        require(mode == 0o700, "G13_BASELINE_WORK_DIRECTORY_MODE_DRIFT")
        require(not any(path.iterdir()), "G13_BASELINE_WORK_DIRECTORY_NOT_EMPTY")
    else:
        path.mkdir(parents=True, mode=0o700)
        os.chmod(path, 0o700)
        created = True
    require(path.is_dir() and not path.is_symlink(),
            "G13_BASELINE_WORK_DIRECTORY_INVALID")
    require(stat.S_IMODE(path.stat().st_mode) == 0o700,
            "G13_BASELINE_WORK_DIRECTORY_MODE_DRIFT")
    return {
        "ready": True,
        "created": created,
        "existing_empty_directory_accepted": not created,
        "mode": "0700",
    }


def install_baseline_work_directory_compatibility_repair(core: Any) -> dict[str, Any]:
    candidate: Callable[..., Any] = core.baseline
    if getattr(candidate, "_g13_baseline_compatibility_repaired", False):
        return {"installed": True, "idempotent": True, "physical_operation": False}
    original: Callable[..., Any] = getattr(candidate, "_g12_original_baseline", candidate)

    def repaired(selected: Any, esptool_path: Path, work: Path,
                 authorization: dict[str, Any]) -> Any:
        try:
            prepare_baseline_work_directory(Path(work))
        except RepairError as exc:
            raise core.ExecutionError(str(exc)) from exc
        return original(selected, esptool_path, Path(work), authorization)

    repaired._g13_baseline_compatibility_repaired = True  # type: ignore[attr-defined]
    repaired._g13_original_baseline = original  # type: ignore[attr-defined]
    core.baseline = repaired
    return {
        "installed": True,
        "idempotent": False,
        "accepts_missing_directory": True,
        "accepts_existing_empty_real_0700_directory": True,
        "bypasses_g12_incompatible_wrapper": original is not candidate,
        "physical_operation": False,
    }


def derive_authorization_state(result: dict[str, Any], marker: dict[str, Any]) -> dict[str, bool]:
    status = marker.get("status")
    consumed_status = status in {"CONSUMED_PASS", "CONSUMED_FAILED"}
    claimed_status = status in {"CLAIMED", "CONSUMED_PASS", "CONSUMED_FAILED"}
    consumed = bool(result.get("authorization_consumed") or
                    marker.get("authorization_consumed") or consumed_status)
    claimed = bool(result.get("authorization_claimed") or
                   marker.get("authorization_claimed") or claimed_status or consumed)
    return {"authorization_claimed": claimed, "authorization_consumed": consumed}


def inspect_frozen_executor_source(source: str) -> dict[str, bool]:
    ast.parse(source)
    temporary = source.find("tempfile.TemporaryDirectory")
    work = source.find("work = Path(td)")
    chmod = source.find("os.chmod(work, 0o700)")
    baseline = source.find("baseline(selected, esptool_path, work, authorization)")
    claim = source.find("claim(marker, authorization)")
    return {
        "uses_existing_temporary_directory": min(temporary, work, chmod, baseline) >= 0
        and temporary < work < chmod < baseline,
        "claim_precedes_inherited_baseline": claim >= 0 and baseline >= 0 and claim < baseline,
    }
