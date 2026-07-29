#!/usr/bin/env python3
"""Fail-closed source contract for the D2-11 bytecode repair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

DECISION_ID = (
    "D1-H3N2-STAGE2D9R-G3R-D2-11-PYTHON-BYTECODE-"
    "SELF-CONTAMINATION-REPAIR-20260729-01"
)
BASE_PR = 208
BASE_HEAD_SHA = "34286f73e710dca63c6348f0fc6457496cb1c493"
BASE_BRANCH = (
    "fix/h3-n2-stage2d9r-g3r-d2-11-prepare-transport-pacing-"
    "successor-execution-binding-20260729-v1"
)
MAIN_SHA_AT_REPAIR = "64c6b093c3ba6a8476c9392c8d106394b2542fb5"
PR208_ARTIFACT_ID = 8726419477
PR208_ARTIFACT_SHA256 = (
    "60dc9f3c3ef96c896bd810e1912488395fed9857dee6a8933e6c55cd6c3b8583"
)
PR208_REVIEW_BINDING_SHA256 = (
    "18880cf228f161cee2174d43c90b9cb9df7d08dc543d9a7322ab0170f9190a14"
)
FAILED_D2_REQUEST_ID = (
    "D2-H3N2-STAGE2D9R-G3R-PREPARE-TRANSPORT-PACING-"
    "PHYSICAL-20260729-11"
)
ROOT_CAUSE = (
    "D2_11_CONTRACT_CHECK_SELF_CONTAMINATES_FROZEN_PACKAGE_"
    "WITH_PYTHON_BYTECODE"
)
REPAIRED_LAUNCHER_FILE = (
    "run_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_"
    "repair_20260729_v1.sh"
)
REPAIRED_WRAPPER_FILE = (
    "h3_n2_stage2d9r_g3r_d2_11_python_bytecode_self_contamination_"
    "repair_wrapper_20260729_v1.py"
)
CONTRACT_FILE = Path(__file__).name
OLD_WRAPPER_MODULE = (
    "h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_"
    "physical_d2_wrapper_20260729_v1"
)
OLD_CONTRACT_MODULE = (
    "h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_"
    "execution_binding_contract_20260729_v1"
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
STABLE_LEAF = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


class RepairContractError(RuntimeError):
    """Stable source-repair contract failure."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RepairContractError(code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_contract_leaf(exc: BaseException) -> str:
    """Return only a controlled contract leaf, never raw exception text."""
    candidate = exc.args[0] if len(exc.args) == 1 else None
    if isinstance(candidate, str) and STABLE_LEAF.fullmatch(candidate):
        return candidate
    return type(exc).__name__


def source_status() -> dict[str, Any]:
    return {
        "schema": (
            "gh.h3.n2.stage2d9r-g3r-d2-11-python-bytecode-"
            "self-contamination-repair-source/1"
        ),
        "status": "SOURCE_ONLY_D2_12_REBIND_REQUIRED",
        "decision_id": DECISION_ID,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "root_cause": ROOT_CAUSE,
        "failed_d2_request_id": FAILED_D2_REQUEST_ID,
        "failed_private_package_state": "PRECLAIM_CONTRACT_FAILED",
        "failed_authorization_claimed": False,
        "failed_authorization_consumed": False,
        "failed_authorization_reuse_permitted": False,
        "failed_package_replay_permitted": False,
        "d2_12_request_created": False,
        "d2_12_authorization_created": False,
        "d2_12_execution_package_created": False,
        "physical_execute_enabled": False,
        "bytecode_write_disabled_before_python": True,
        "private_outer_runner_must_disable_bytecode": True,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "replay_permitted": False,
    }


def validate_decision(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), "DECISION_FILE_INVALID")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "DECISION_NOT_MAPPING")
    supplied = value.pop("decision_binding_sha256", None)
    require(
        isinstance(supplied, str)
        and HEX64.fullmatch(supplied) is not None
        and canonical_sha256(value) == supplied,
        "DECISION_BINDING_MISMATCH",
    )
    exact = {
        "decision_id": DECISION_ID,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "root_cause": ROOT_CAUSE,
        "failed_d2_request_id": FAILED_D2_REQUEST_ID,
        "failed_private_package_state": "PRECLAIM_CONTRACT_FAILED",
        "failed_authorization_claimed": False,
        "failed_authorization_consumed": False,
        "failed_authorization_reuse_permitted": False,
        "failed_package_replay_permitted": False,
        "d2_12_request_created": False,
        "d2_12_authorization_created": False,
        "d2_12_execution_package_created": False,
        "physical_execute_enabled": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "replay_permitted": False,
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "DECISION_" + key.upper())
    value["decision_binding_sha256"] = supplied
    return value


def validate_launcher(path: Path) -> None:
    require(path.is_file() and not path.is_symlink(), "LAUNCHER_FILE_INVALID")
    text = path.read_text(encoding="utf-8")
    assignment = text.find("PYTHONDONTWRITEBYTECODE=1")
    exported = text.find("export PYTHONDONTWRITEBYTECODE")
    python_bin = text.find("PYTHON_BIN=")
    first_exec = text.find('exec "$PYTHON_BIN"')
    require(
        min(assignment, exported, python_bin, first_exec) >= 0,
        "LAUNCHER_BYTECODE_GUARD_MISSING",
    )
    require(
        assignment < exported < python_bin < first_exec,
        "LAUNCHER_BYTECODE_GUARD_ORDER_INVALID",
    )
    require(
        "PYTHONDONTWRITEBYTECODE=0" not in text,
        "LAUNCHER_BYTECODE_GUARD_OVERRIDDEN",
    )


def validate_review_source(root: Path) -> dict[str, Any]:
    require(root.is_dir() and not root.is_symlink(), "SOURCE_ROOT_INVALID")
    decision = validate_decision(
        root
        / "docs/decisions/"
        "h3-n2-stage2d9r-g3r-d2-11-python-bytecode-"
        "self-contamination-repair-20260729-v1.json"
    )
    validate_launcher(root / "tools" / REPAIRED_LAUNCHER_FILE)
    wrapper = root / "tools" / REPAIRED_WRAPPER_FILE
    require(
        wrapper.is_file() and not wrapper.is_symlink(),
        "REPAIRED_WRAPPER_INVALID",
    )
    return {
        "decision_binding_sha256": decision["decision_binding_sha256"],
        "launcher_sha256": sha256_file(
            root / "tools" / REPAIRED_LAUNCHER_FILE
        ),
        "wrapper_sha256": sha256_file(wrapper),
        "contract_sha256": sha256_file(root / "tools" / CONTRACT_FILE),
    }
