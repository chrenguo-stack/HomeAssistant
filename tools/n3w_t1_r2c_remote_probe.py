from __future__ import annotations

import argparse
import json
import os
import re
import time
from typing import Any

from n3w_t1_r2c_collectors import collect_e1, collect_e2, collect_e3, collect_e4
from n3w_t1_r2c_collectors_e5_e9 import (
    collect_e5,
    collect_e6,
    collect_e7,
    collect_e8,
    collect_e9,
)
from n3w_t1_r2c_evidence_schema import REQUIREMENT_FIELDS, validate_report
from n3w_t1_r2c_readonly_commands import (
    COMMAND_TIMEOUT_SECONDS,
    ReadonlyCommandError,
    run_contract_command,
)

PROBE_SCHEMA = "gh.n3w.t1-r2c-readonly-probe/1"
MAX_PRIVATE_REPORT_BYTES = 8 * 1024 * 1024
TOTAL_REMOTE_BUDGET_SECONDS = 120.0
BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
HEX40_RE = re.compile(r"[0-9a-f]{40}\Z")
HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")


class ProbeError(RuntimeError):
    pass


class BudgetRunner:
    def __init__(self, deadline: float) -> None:
        self.deadline = deadline
        self.exhausted = False

    def __call__(self, command_id: str, **kwargs: Any):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.exhausted = True
            raise ReadonlyCommandError("remote_total_budget_exhausted")
        requested = kwargs.pop("timeout_seconds", COMMAND_TIMEOUT_SECONDS)
        kwargs["timeout_seconds"] = min(float(requested), remaining)
        try:
            return run_contract_command(command_id, **kwargs)
        finally:
            if time.monotonic() >= self.deadline:
                self.exhausted = True


def _empty_requirement(
    requirement_id: str,
    *,
    status: str = "NOT_EXECUTED",
    reason_code: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "complete": False,
        "reason_code": reason_code,
        "method_ids": [],
        "provenance": [],
        "fields": {
            name: {"value": None, "status": status}
            for name in REQUIREMENT_FIELDS[requirement_id]
        },
    }


def _root_path(root: str, relative: str) -> str:
    if root == "/":
        return "/" + relative
    return os.path.join(root, relative)


def _read_boot_id(root: str) -> str:
    path = _root_path(root, "proc/sys/kernel/random/boot_id")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ProbeError("STOP_BOOT_ID_UNAVAILABLE") from error
    try:
        data = os.read(descriptor, 129)
        if len(data) > 128:
            raise ProbeError("STOP_BOOT_ID_INVALID")
    finally:
        os.close(descriptor)
    try:
        value = data.decode("ascii").strip().lower()
    except UnicodeDecodeError as error:
        raise ProbeError("STOP_BOOT_ID_INVALID") from error
    if BOOT_ID_RE.fullmatch(value) is None:
        raise ProbeError("STOP_BOOT_ID_INVALID")
    return value


def _reason_codes(requirements: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(
        {
            envelope["reason_code"]
            for envelope in requirements.values()
            if envelope.get("reason_code")
        }
    )


def _collect(
    requirement_id: str,
    collector,
    *,
    root: str,
    runner: BudgetRunner,
) -> dict[str, Any]:
    if runner.exhausted or time.monotonic() >= runner.deadline:
        runner.exhausted = True
        return _empty_requirement(
            requirement_id,
            status="ERROR",
            reason_code="STOP_TRUNCATED",
        )
    if requirement_id == "E3":
        return collector(root)
    return collector(root, runner=runner)


def collect_report(
    *,
    root: str,
    execution_id: str,
    source_head: str,
    probe_sha256: str,
    contract_sha256: str,
    grant_id: str,
    target_binding_token_sha256: str,
) -> dict[str, Any]:
    if TOKEN_RE.fullmatch(execution_id) is None:
        raise ProbeError("execution_id_invalid")
    if TOKEN_RE.fullmatch(grant_id) is None:
        raise ProbeError("grant_id_invalid")
    if HEX40_RE.fullmatch(source_head) is None:
        raise ProbeError("source_head_invalid")
    if HEX64_RE.fullmatch(probe_sha256) is None:
        raise ProbeError("probe_sha256_invalid")
    if HEX64_RE.fullmatch(contract_sha256) is None:
        raise ProbeError("contract_sha256_invalid")
    if HEX64_RE.fullmatch(target_binding_token_sha256) is None:
        raise ProbeError("target_binding_token_invalid")

    deadline = time.monotonic() + TOTAL_REMOTE_BUDGET_SECONDS
    runner = BudgetRunner(deadline)
    boot_before = _read_boot_id(root)
    requirements: dict[str, dict[str, Any]] = {}

    collectors = (
        ("E1", collect_e1),
        ("E2", collect_e2),
        ("E3", collect_e3),
        ("E4", collect_e4),
        ("E5", collect_e5),
        ("E6", collect_e6),
        ("E7", collect_e7),
        ("E8", collect_e8),
        ("E9", collect_e9),
    )

    for index, (requirement_id, collector) in enumerate(collectors):
        requirements[requirement_id] = _collect(
            requirement_id,
            collector,
            root=root,
            runner=runner,
        )
        if (
            requirement_id == "E1"
            and requirements[requirement_id].get("reason_code")
            == "STOP_TARGET_DRIFT"
        ):
            for remaining_id, _ in collectors[index + 1 :]:
                requirements[remaining_id] = _empty_requirement(
                    remaining_id,
                    reason_code="STOP_TARGET_DRIFT",
                )
            break
        if runner.exhausted:
            for remaining_id, _ in collectors[index + 1 :]:
                requirements[remaining_id] = _empty_requirement(
                    remaining_id,
                    status="ERROR",
                    reason_code="STOP_TRUNCATED",
                )
            break

    for requirement_id in REQUIREMENT_FIELDS:
        requirements.setdefault(
            requirement_id,
            _empty_requirement(requirement_id),
        )

    boot_after = _read_boot_id(root)
    same_boot = boot_before == boot_after
    stop_reasons = _reason_codes(requirements)
    if not same_boot:
        stop_reasons = sorted(set(stop_reasons) | {"STOP_TARGET_CHANGED"})
    if runner.exhausted:
        stop_reasons = sorted(set(stop_reasons) | {"STOP_TRUNCATED"})

    all_complete = all(
        requirements[requirement_id]["complete"]
        for requirement_id in REQUIREMENT_FIELDS
    )
    any_error = any(
        requirements[requirement_id]["status"] == "ERROR"
        for requirement_id in REQUIREMENT_FIELDS
    )
    if same_boot and all_complete and not stop_reasons:
        capture_status = "COMPLETE"
    elif any_error:
        capture_status = "FAILED"
    else:
        capture_status = "INCOMPLETE"

    e1 = requirements["E1"]
    platform_expected = (
        e1.get("status") == "OBSERVED"
        and e1.get("reason_code") != "STOP_TARGET_DRIFT"
    )
    report = {
        "schema": "gh.n3w.t1-r2c-readonly-evidence/1",
        "execution_id": execution_id,
        "source_head": source_head,
        "probe_sha256": probe_sha256,
        "contract_sha256": contract_sha256,
        "authorization": {
            "grant_id": grant_id,
            "granted": True,
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
        },
        "target_binding": {
            "binding_token_sha256": target_binding_token_sha256,
            "strict_host_key_checking_required": True,
            "same_boot": same_boot,
            "platform_expected": platform_expected,
        },
        "requirements": requirements,
        "capture_status": capture_status,
        "static_review_status": "NOT_EXECUTED",
        "stop_reasons": stop_reasons,
        "boundaries": {
            "t1_access": True,
            "intentional_target_write": False,
            "service_mutation": False,
            "board_access": False,
            "merge": False,
        },
        "os_identity_semantics_proven": False,
        "controlled_clone_boot_required": True,
        "disk_capture_ready": False,
        "public_projection_review": "NOT_REVIEWED",
    }
    validate_report(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--probe-sha256", required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--grant-id", required=True)
    parser.add_argument("--target-binding-token-sha256", required=True)
    args = parser.parse_args()
    try:
        report = collect_report(
            root=args.root,
            execution_id=args.execution_id,
            source_head=args.source_head,
            probe_sha256=args.probe_sha256,
            contract_sha256=args.contract_sha256,
            grant_id=args.grant_id,
            target_binding_token_sha256=args.target_binding_token_sha256,
        )
        encoded = (
            json.dumps(
                {"schema": PROBE_SCHEMA, "status": "PASS", "report": report},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        if len(encoded) > MAX_PRIVATE_REPORT_BYTES:
            raise ProbeError("STOP_TRUNCATED")
    except ProbeError as error:
        print(
            json.dumps(
                {
                    "schema": PROBE_SCHEMA,
                    "status": "STOP",
                    "error_code": str(error),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(encoded.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
