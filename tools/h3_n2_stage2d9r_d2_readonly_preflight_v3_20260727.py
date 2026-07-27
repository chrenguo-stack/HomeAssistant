#!/usr/bin/env python3
"""V3 read-only D2 preflight adapter.

V3 preserves the frozen V2 public, recovery and execution checks, replaces the
retired-original-file U1 check with durable marker-only consumed evidence, and
binds the output of the separately authorized read-only board-baseline gate.
It performs no board, serial, Flash, NVS, network or Broker work.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import stat
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V2_PATH = ROOT / "tools" / "h3_n2_stage2d9r_successor_d2_readonly_preflight_20260727_v2.py"
MARKER_PATH = ROOT / "tools" / "h3_n2_stage2d9r_consumed_marker_evidence_20260727_v1.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{name.upper()}_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V2 = load_module("stage2d9r_d2_preflight_v2_for_v3", V2_PATH)
MARKER = load_module("stage2d9r_consumed_marker_evidence_for_v3", MARKER_PATH)
HEX64 = V2.V1.HEX64
BASELINE_RESULT_SCHEMA = (
    "gh.h3.n2.stage2d9r-successor-board-baseline-readonly-result/1"
)
BASELINE_AUTHORIZATION_ID = (
    "D2-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-20260727-01"
)


class PreflightV3Error(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PreflightV3Error(code)


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def load_json_0600(path: Path, code: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), code)
    require(file_mode(path) == "0600", code)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), code)
    return value


def validate_baseline_result(path: Path) -> dict[str, Any]:
    value = load_json_0600(path, "BASELINE_RESULT_INVALID")
    require(value.get("schema") == BASELINE_RESULT_SCHEMA,
            "BASELINE_RESULT_SCHEMA_MISMATCH")
    require(value.get("authorization_id") == BASELINE_AUTHORIZATION_ID,
            "BASELINE_RESULT_AUTHORIZATION_ID_MISMATCH")
    require(value.get("status") == "CONSUMED_PASS",
            "BASELINE_RESULT_STATUS_MISMATCH")
    require(value.get("authorization_consumed") is True,
            "BASELINE_RESULT_NOT_CONSUMED")
    require(value.get("one_shot") is True,
            "BASELINE_RESULT_NOT_ONE_SHOT")
    require(value.get("replay_permitted") is False,
            "BASELINE_RESULT_REPLAY_EXPANDED")
    require(value.get("automatic_retry_permitted") is False,
            "BASELINE_RESULT_RETRY_EXPANDED")
    for key in (
        "board_identity_sha256",
        "serial_identity_sha256",
        "baseline_state_sha256",
        "chip_id_output_sha256",
        "flash_id_output_sha256",
        "test_partition_sha256",
        "result_sha256",
    ):
        require(
            isinstance(value.get(key), str)
            and HEX64.fullmatch(value[key]) is not None,
            f"BASELINE_RESULT_{key.upper()}_INVALID",
        )
    require(value.get("test_partition_size") == 0x10000,
            "BASELINE_RESULT_PARTITION_SIZE_MISMATCH")
    for key in (
        "board_write_operation",
        "flash_erase_operation",
        "flash_write_operation",
        "flash_verify_operation",
        "physical_nvs_operation",
        "network_operation",
        "broker_started",
        "prepare_executed",
        "verify_executed",
        "activate_executed",
        "cleanup_executed",
        "secret_values_included",
        "private_paths_included",
    ):
        require(value.get(key) is False,
                f"BASELINE_RESULT_BOUNDARY_EXPANDED_{key.upper()}")
    without_digest = dict(value)
    observed = without_digest.pop("result_sha256")
    require(
        observed == V2.V1.sha256_bytes(
            json.dumps(
                without_digest,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ),
        "BASELINE_RESULT_DIGEST_MISMATCH",
    )
    return {
        "authorization_id": BASELINE_AUTHORIZATION_ID,
        "result_sha256": observed,
        "board_identity_sha256": value["board_identity_sha256"],
        "serial_identity_sha256": value["serial_identity_sha256"],
        "baseline_state_sha256": value["baseline_state_sha256"],
        "test_partition_sha256": value["test_partition_sha256"],
        "test_partition_size": value["test_partition_size"],
        "status": "CONSUMED_PASS",
        "replay_permitted": False,
    }


def marker_adapter(
    authorization_record: Path | None,
    result_path: Path | None,
    consumed_marker: Path,
) -> dict[str, Any]:
    return MARKER.validate_consumed_evidence(
        marker=consumed_marker,
        authorization_id=V2.V1.CONTRACT.U1_02_ID,
        authorization_record_sha256=V2.V1.U1_02_RECORD_SHA256,
        result_sha256=V2.V1.U1_02_RESULT_SHA256,
        authorization_record=authorization_record,
        result=result_path,
    )


def rebuild_request(
    args: argparse.Namespace,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    contract = V2.V1.CONTRACT.build_contract(
        preflight["repository_state"]["source_sha"],
        preflight["repository_state"]["main_sha"],
    )
    u1 = preflight["u1_02"]
    return V2.V1.CONTRACT.build_exact_authorization_request(
        contract,
        review_artifact_id=args.review_artifact_id,
        review_artifact_digest_sha256=args.review_artifact_digest_sha256,
        review_binding_sha256=preflight["review_binding_sha256"],
        public_preflight_artifact_id=args.public_preflight_artifact_id,
        public_preflight_artifact_digest_sha256=args.public_preflight_artifact_digest_sha256,
        private_preflight_result_sha256=preflight["preflight_result_sha256"],
        u1_02_consumed_marker_sha256=u1["consumed_marker_sha256"],
        board_identity_sha256=args.board_identity_sha256,
        serial_identity_sha256=args.serial_identity_sha256,
        baseline_state_sha256=args.baseline_state_sha256,
        execution_package_sha256=V2.EXECUTION_PACKAGE_SHA256,
        execution_script_sha256=V2.EXECUTION_SCRIPT_SHA256,
        execution_launcher_sha256=V2.EXECUTION_LAUNCHER_SHA256,
        execution_marker_name_sha256=V2.EXECUTION_MARKER_NAME_SHA256,
        locked_recovery_package_sha256=V2.RECOVERY_PAYLOAD_SHA256,
        issued_at=args.issued_at,
        expires_at=args.expires_at,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    baseline = validate_baseline_result(args.baseline_readonly_result)
    args.board_identity_sha256 = baseline["board_identity_sha256"]
    args.serial_identity_sha256 = baseline["serial_identity_sha256"]
    args.baseline_state_sha256 = baseline["baseline_state_sha256"]

    original = V2.V1.validate_u1_02
    V2.V1.validate_u1_02 = marker_adapter
    try:
        base = V2.run(args)
    finally:
        V2.V1.validate_u1_02 = original

    preflight = dict(base["preflight"])
    preflight.pop("preflight_result_sha256", None)
    preflight["schema"] = (
        "gh.h3.n2.stage2d9r-successor-d2-read-only-preflight-result/3"
    )
    preflight["u1_consumed_evidence_policy"] = {
        "marker_only_fallback_permitted": True,
        "original_files_reconstructed": False,
        "authorization_replayed": False,
        "evidence_mode": preflight["u1_02"]["evidence_mode"],
    }
    preflight["baseline_readonly_gate"] = baseline
    preflight["board_or_serial_access_during_d2_preflight"] = False
    preflight["preflight_result_sha256"] = V2.V1.sha256_bytes(
        json.dumps(
            preflight,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    )
    exact_request = rebuild_request(args, preflight)
    require(exact_request.get("authorized") is False,
            "V3_EXACT_REQUEST_AUTHORIZATION_EXPANDED")
    return {"preflight": preflight, "exact_request": exact_request}


def parser() -> argparse.ArgumentParser:
    value = V2.parser()
    for action in value._actions:
        if action.dest in (
            "u1_02_authorization_record",
            "u1_02_result",
            "board_identity_sha256",
            "serial_identity_sha256",
            "baseline_state_sha256",
        ):
            action.required = False
            action.default = None
    value.add_argument(
        "--baseline-readonly-result",
        type=Path,
        required=True,
    )
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        result = run(args)
        V2.V1.write_json_exclusive(args.preflight_output, result["preflight"])
        V2.V1.write_json_exclusive(args.request_output, result["exact_request"])
    except Exception as exc:
        if isinstance(
            exc,
            (
                PreflightV3Error,
                V2.PreflightV2Error,
                V2.V1.PreflightError,
                MARKER.ConsumedEvidenceError,
            ),
        ) and exc.args:
            code = exc.args[0]
        else:
            code = type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "preflight_result_sha256": result["preflight"][
                    "preflight_result_sha256"
                ],
                "request_binding_sha256": result["exact_request"][
                    "request_binding_sha256"
                ],
                "authorized": False,
                "authorization_created": False,
                "authorization_claimed": False,
                "marker_only_consumed_evidence": (
                    result["preflight"]["u1_02"]["evidence_mode"]
                    == "CONSUMED_MARKER_ONLY"
                ),
                "board_operation": False,
                "serial_operation": False,
                "flash_operation": False,
                "physical_nvs_operation": False,
                "network_operation": False,
                "broker_started": False,
                "prepare_executed": False,
                "verify_executed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
