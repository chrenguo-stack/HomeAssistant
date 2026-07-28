#!/usr/bin/env python3
"""Install baseline-mismatch evidence capture into the frozen physical executor.

The installer does not authorize execution. A future exact physical wrapper may
install it before invoking the frozen executor. When the legacy baseline digest
mismatches, the observed hash-only component set is retained in terminal
public evidence before any destructive operation begins.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import h3_n2_stage2d9r_g3r_baseline_mismatch_evidence_repair_contract_20260728_v1 as contract

_LAST_BASELINE_EVIDENCE: dict[str, Any] | None = None


def last_baseline_evidence() -> dict[str, Any] | None:
    return dict(_LAST_BASELINE_EVIDENCE) if _LAST_BASELINE_EVIDENCE is not None else None


def clear_last_baseline_evidence() -> None:
    global _LAST_BASELINE_EVIDENCE
    _LAST_BASELINE_EVIDENCE = None


def install(core: Any) -> Any:
    """Patch a compatible frozen executor module and return it."""
    clear_last_baseline_evidence()
    original_result_object = core.result_object

    def repaired_baseline(
        selected: Any,
        esptool_path: Path,
        work: Path,
        authorization: dict[str, Any],
    ) -> dict[str, Any]:
        global _LAST_BASELINE_EVIDENCE
        chip = core.run_process(
            core.esptool_command(esptool_path, selected.device, "chip_id"),
            timeout=30,
            code="BASELINE_CHIP_ID_FAILED",
        )
        flash = core.run_process(
            core.esptool_command(esptool_path, selected.device, "flash_id"),
            timeout=30,
            code="BASELINE_FLASH_ID_FAILED",
        )
        partition = work / "baseline-test-partition.bin"
        core.run_process(
            core.esptool_command(
                esptool_path,
                selected.device,
                "read_flash",
                hex(core.TEST_PARTITION_ADDRESS),
                hex(core.TEST_PARTITION_SIZE),
                str(partition),
            ),
            timeout=45,
            code="BASELINE_PARTITION_READ_FAILED",
        )
        evidence = contract.build_baseline_evidence(
            board_identity_sha256=core.canonical_sha256(selected.board_binding()),
            serial_identity_sha256=core.canonical_sha256(selected.serial_binding()),
            chip_id_output_sha256=core.sha256_bytes(chip.stdout.encode("utf-8")),
            flash_id_output_sha256=core.sha256_bytes(flash.stdout.encode("utf-8")),
            test_partition_sha256=core.sha256_file(partition),
            test_partition_size=partition.stat().st_size,
            expected_legacy_baseline_sha256=authorization["baseline_state_sha256"],
        )
        _LAST_BASELINE_EVIDENCE = evidence
        legacy = {
            "schema": "gh.h3.n2.stage2d9r-successor-board-baseline/1",
            "board_identity_sha256": evidence["board_identity_sha256"],
            "serial_identity_sha256": evidence["serial_identity_sha256"],
            "chip_id_output_sha256": evidence["chip_id_output_sha256"],
            "flash_id_output_sha256": evidence["flash_id_output_sha256"],
            "test_partition_sha256": evidence["test_partition_sha256"],
            "test_partition_size": evidence["test_partition_size"],
        }
        core.require(
            evidence["legacy_baseline_matches"] is True,
            "BASELINE_STATE_MISMATCH",
        )
        return legacy

    def repaired_result_object(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = original_result_object(*args, **kwargs)
        evidence = last_baseline_evidence()
        value.pop("terminal_result_sha256", None)
        value["baseline_evidence_policy_version"] = 2
        value["observed_baseline_evidence"] = evidence
        if evidence is not None:
            value["observed_baseline_sha256"] = evidence[
                "observed_legacy_baseline_sha256"
            ]
            value["baseline_mismatch_before_destructive_operation"] = (
                value.get("failure_code") == "BASELINE_STATE_MISMATCH"
                and value.get("flash_sha256") is None
                and value.get("prepare_count") == 0
                and value.get("verify_count") == 0
            )
        else:
            value["baseline_mismatch_before_destructive_operation"] = False
        value["terminal_result_sha256"] = core.canonical_sha256(value)
        return value

    core.baseline = repaired_baseline
    core.result_object = repaired_result_object
    return core


if __name__ == "__main__":
    import json
    print(json.dumps({
        "status": "SOURCE_ONLY_BASELINE_EVIDENCE_CAPTURE_INERT",
        "decision_id": contract.DECISION_ID,
        "baseline_evidence_policy_version": 2,
        "authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "physical_nvs_operation": False,
        "network_operation": False,
        "broker_started": False,
        "prepare_executed": False,
        "verify_executed": False,
    }, sort_keys=True))
