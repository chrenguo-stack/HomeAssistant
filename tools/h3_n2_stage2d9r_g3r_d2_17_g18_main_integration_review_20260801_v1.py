#!/usr/bin/env python3
"""Validate the add-only D2-17 G18 final-closure main integration."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_MAIN_SHA = "6525e8a81c140853e2b0de0eba78ad1227ca7305"
HISTORICAL_FINAL_HEAD = "570279e5df22c9092dad670dc9a6bf762589471c"
EXPECTED_TERMINAL_SHA256 = "30b3a16744b1127df04133c34efa661ce4cd05cc576635a180e079e8b380c855"
EXPECTED_CLOSURE_BINDING = "cb7f9924941a51874af9945434d3623eb850de7b06b6b2493f0acf2bf823bf78"
EXPECTED_CHANGED_PATHS = (
    ".github/workflows/h3-n2-stage2d9r-g3r-d2-17-g18-main-integration-review-ci-v1.yml",
    "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g18-main-integration-inventory-20260801-v1.json",
    "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g18-target-mac-host-only-closure-pass-20260801-v1.json",
    "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-final-closure-20260801-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-d2-17-g18-main-integration-strategy-20260801-v1.md",
    "docs/development/h3-n2-stage2d9r-g3r-d2-17-g18-pass-final-closure-contract-20260801-v1.md",
    "tools/h3_n2_stage2d9r_g3r_d2_17_g18_main_integration_review_20260801_v1.py",
)
IMPORTED_PATHS = (
    "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g18-target-mac-host-only-closure-pass-20260801-v1.json",
    "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-final-closure-20260801-v1.json",
    "docs/development/h3-n2-stage2d9r-g3r-d2-17-g18-pass-final-closure-contract-20260801-v1.md",
)
TERMINAL_PATH = ROOT / IMPORTED_PATHS[0]
DECISION_PATH = ROOT / IMPORTED_PATHS[1]
INVENTORY_PATH = ROOT / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g18-main-integration-inventory-20260801-v1.json"


class ReviewError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewError(code)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON_OBJECT_REQUIRED:{path}")
    return value


def canonical_digest_without(value: dict[str, Any], field: str) -> str:
    copy = dict(value)
    copy.pop(field, None)
    payload = json.dumps(copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def verify_terminal(terminal: dict[str, Any]) -> None:
    require(terminal.get("schema") == "gh.h3.n2.stage2d9r-g3r-d2-17-g18-target-mac-host-only-closure-terminal/1", "TERMINAL_SCHEMA_DRIFT")
    require(terminal.get("status") == "PASS", "TERMINAL_STATUS_NOT_PASS")
    require(terminal.get("terminal_state") == "D2_17_TARGET_MAC_HOST_ONLY_CLOSURE_RECONSTRUCTED_CONSUMED_PASS", "TERMINAL_STATE_DRIFT")
    require(terminal.get("physical_execution_outcome") == "CONSUMED_PASS", "PHYSICAL_OUTCOME_DRIFT")
    require(terminal.get("d2_17_closure_complete") is True, "CLOSURE_NOT_COMPLETE")
    require(terminal.get("authorization_created") is True, "AUTHORIZATION_NOT_CREATED")
    require(terminal.get("authorization_claimed") is True, "AUTHORIZATION_NOT_CLAIMED")
    require(terminal.get("authorization_consumed") is True, "AUTHORIZATION_NOT_CONSUMED")
    require(terminal.get("g16_terminal_semantic_binding_valid") is True, "G16_SEMANTIC_BINDING_INVALID")
    require(terminal.get("g16_runtime_read") is True, "G16_RUNTIME_NOT_READ")
    require(terminal.get("g16_runtime_mutated") is False, "G16_RUNTIME_MUTATED")
    require(terminal.get("g14_runtime_accessed") is False, "G14_RUNTIME_ACCESSED")
    require(terminal.get("g15_runtime_accessed") is False, "G15_RUNTIME_ACCESSED")
    require(terminal.get("physical_rerun_required") is False, "PHYSICAL_RERUN_REQUIRED")
    require(terminal.get("physical_rerun_authorized") is False, "PHYSICAL_RERUN_AUTHORIZED")
    require(terminal.get("replay_permitted") is False, "REPLAY_PERMITTED")
    require(terminal.get("automatic_retry_permitted") is False, "AUTOMATIC_RETRY_PERMITTED")
    false_fields = (
        "board_operation", "usb_enumeration", "serial_operation", "esptool_operation",
        "flash_operation", "physical_nvs_operation", "network_operation", "broker_started",
        "prepare_executed", "verify_executed", "recovery_executed", "activate_executed",
        "cleanup_executed", "ready", "merge", "release", "tag", "deployment",
        "private_paths_included", "raw_logs_included", "command_material_included",
        "secret_values_included",
    )
    for field in false_fields:
        require(terminal.get(field) is False, f"FORBIDDEN_TERMINAL_FLAG:{field}")
    require(terminal.get("terminal_record_sha256") == EXPECTED_TERMINAL_SHA256, "TERMINAL_BINDING_VALUE_DRIFT")
    require(canonical_digest_without(terminal, "terminal_record_sha256") == EXPECTED_TERMINAL_SHA256, "TERMINAL_SELF_BINDING_INVALID")


def verify_decision(decision: dict[str, Any], terminal: dict[str, Any]) -> None:
    require(decision.get("schema") == "gh.h3.n2.stage2d9r-g3r-d2-17-final-closure/1", "DECISION_SCHEMA_DRIFT")
    require(decision.get("state") == "CLOSED", "DECISION_NOT_CLOSED")
    require(decision.get("g18_status") == terminal.get("status"), "DECISION_STATUS_MISMATCH")
    require(decision.get("g18_terminal_state") == terminal.get("terminal_state"), "DECISION_STATE_MISMATCH")
    require(decision.get("g18_terminal_record_sha256") == terminal.get("terminal_record_sha256"), "DECISION_TERMINAL_MISMATCH")
    require(decision.get("physical_execution_outcome") == terminal.get("physical_execution_outcome"), "DECISION_OUTCOME_MISMATCH")
    require(decision.get("authorization_record_sha256") == terminal.get("authorization_record_sha256"), "AUTHORIZATION_RECORD_MISMATCH")
    require(decision.get("authorization_marker_sha256") == terminal.get("authorization_marker_sha256"), "AUTHORIZATION_MARKER_MISMATCH")
    require(decision.get("g16_terminal_record_sha256") == terminal.get("g16_terminal_record_sha256"), "G16_TERMINAL_MISMATCH")
    require(decision.get("g17_terminal_record_sha256") == terminal.get("g17_terminal_record_sha256"), "G17_TERMINAL_MISMATCH")
    require(decision.get("reconstructed_physical_terminal_record_sha256") == terminal.get("reconstructed_physical_terminal_record_sha256"), "RECONSTRUCTED_TERMINAL_MISMATCH")
    require(decision.get("closure_binding_sha256") == EXPECTED_CLOSURE_BINDING, "CLOSURE_BINDING_DRIFT")
    for field in (
        "physical_rerun_required", "physical_rerun_authorized", "replay_permitted",
        "automatic_retry_permitted", "ready_authorized", "merge_authorized",
        "release_authorized", "tag_authorized", "deployment_authorized",
    ):
        require(decision.get(field) is False, f"FORBIDDEN_DECISION_FLAG:{field}")


def verify_inventory(inventory: dict[str, Any]) -> None:
    require(inventory.get("decision_id") == "D1-H3N2-STAGE2D9R-G3R-D2-17-G18-FINAL-CLOSURE-MAIN-INTEGRATION-STRATEGY-AND-CONSOLIDATED-PR-AUTHORIZATION-20260801-01", "INTEGRATION_DECISION_DRIFT")
    require(inventory.get("base_main_sha") == BASE_MAIN_SHA, "BASE_MAIN_SHA_DRIFT")
    require(inventory.get("historical_final_closure_head_sha") == HISTORICAL_FINAL_HEAD, "FINAL_HEAD_DRIFT")
    require(inventory.get("integration_mode") == "CONTENT_ADDRESSED_FINAL_CLOSURE_ARCHIVE_ONLY", "INTEGRATION_MODE_DRIFT")
    require(inventory.get("dependency_inventory_complete_for_imported_scope") is True, "DEPENDENCY_INVENTORY_INCOMPLETE")
    require(inventory.get("full_historical_stack_imported") is False, "HISTORICAL_STACK_IMPORTED")
    require(tuple(inventory.get("imported_paths", ())) == IMPORTED_PATHS, "IMPORTED_PATH_SET_DRIFT")
    require(inventory.get("g18_terminal_record_sha256") == EXPECTED_TERMINAL_SHA256, "INVENTORY_TERMINAL_DRIFT")
    require(inventory.get("closure_binding_sha256") == EXPECTED_CLOSURE_BINDING, "INVENTORY_CLOSURE_BINDING_DRIFT")
    chain = inventory.get("chain")
    require(isinstance(chain, list) and [entry.get("pr") for entry in chain] == list(range(250, 259)), "CHAIN_PR_SEQUENCE_DRIFT")
    for left, right in zip(chain, chain[1:]):
        require(left.get("head_sha") == right.get("base_sha"), "CHAIN_SHA_DISCONTINUITY")
    require(chain[-1].get("head_sha") == HISTORICAL_FINAL_HEAD, "CHAIN_FINAL_HEAD_DRIFT")
    require(chain[-1].get("imported") is True, "FINAL_SOURCE_NOT_IMPORTED")
    require(all(entry.get("imported") is False for entry in chain[:-1]), "RETIRED_CHAIN_IMPORTED")
    source_blobs = inventory.get("source_blob_sha1")
    require(isinstance(source_blobs, dict), "SOURCE_BLOB_MAP_INVALID")
    for relative in IMPORTED_PATHS:
        require(git_blob_sha1(ROOT / relative) == source_blobs.get(relative), f"SOURCE_BLOB_DRIFT:{relative}")
    for field in (
        "physical_rerun_required", "physical_rerun_authorized", "replay_permitted",
        "automatic_retry_permitted", "board_operation", "usb_enumeration",
        "serial_operation", "esptool_operation", "flash_operation",
        "physical_nvs_operation", "network_operation", "broker_started",
        "prepare_executed", "verify_executed", "recovery_executed",
        "activate_executed", "cleanup_executed", "ready_authorized",
        "merge_authorized", "release_authorized", "tag_authorized",
        "deployment_authorized", "secret_values_included",
    ):
        require(inventory.get(field) is False, f"FORBIDDEN_INVENTORY_FLAG:{field}")


def verify_git_boundary() -> str:
    head = git_output("rev-parse", "HEAD")
    merge_base = git_output("merge-base", BASE_MAIN_SHA, head)
    require(merge_base == BASE_MAIN_SHA, "BRANCH_NOT_BASED_ON_EXACT_MAIN")
    changed = tuple(sorted(line for line in git_output("diff", "--name-only", f"{BASE_MAIN_SHA}..{head}").splitlines() if line))
    require(changed == tuple(sorted(EXPECTED_CHANGED_PATHS)), "CHANGED_PATH_SET_DRIFT")
    for relative in EXPECTED_CHANGED_PATHS:
        path = ROOT / relative
        require(path.is_file() and not path.is_symlink(), f"INTEGRATION_FILE_INVALID:{relative}")
    for path in ROOT.rglob("*.pyc"):
        require(False, f"PYTHON_BYTECODE_PRESENT:{path.relative_to(ROOT)}")
    return head


def write_artifact(output: Path, head: str) -> None:
    require(not output.exists(), "ARTIFACT_DIR_ALREADY_EXISTS")
    output.mkdir(parents=True, mode=0o700)
    for relative in EXPECTED_CHANGED_PATHS:
        source = ROOT / relative
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (output / "SOURCE_SHA").write_text(head + "\n", encoding="utf-8")
    (output / "BASE_MAIN_SHA").write_text(BASE_MAIN_SHA + "\n", encoding="utf-8")
    (output / "HISTORICAL_FINAL_CLOSURE_HEAD_SHA").write_text(HISTORICAL_FINAL_HEAD + "\n", encoding="utf-8")
    summary = {
        "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g18-main-integration-review/1",
        "status": "PASS",
        "source_sha": head,
        "base_main_sha": BASE_MAIN_SHA,
        "historical_final_closure_head_sha": HISTORICAL_FINAL_HEAD,
        "g18_terminal_record_sha256": EXPECTED_TERMINAL_SHA256,
        "closure_binding_sha256": EXPECTED_CLOSURE_BINDING,
        "changed_file_count": len(EXPECTED_CHANGED_PATHS),
        "private_runtime_accessed": False,
        "physical_operation": False,
        "ready_authorized": False,
        "merge_authorized": False,
        "release_authorized": False,
        "tag_authorized": False,
        "deployment_authorized": False,
    }
    (output / "REVIEW_SUMMARY.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    entries = []
    for path in sorted(p for p in output.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        entries.append(f"{sha256_file(path)}  {path.relative_to(output).as_posix()}")
    (output / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        terminal = load_json(TERMINAL_PATH)
        decision = load_json(DECISION_PATH)
        inventory = load_json(INVENTORY_PATH)
        verify_terminal(terminal)
        verify_decision(decision, terminal)
        verify_inventory(inventory)
        head = verify_git_boundary()
        write_artifact(args.artifact_dir, head)
        print(json.dumps({
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g18-main-integration-review/1",
            "status": "PASS",
            "source_sha": head,
            "base_main_sha": BASE_MAIN_SHA,
            "changed_file_count": len(EXPECTED_CHANGED_PATHS),
            "g18_terminal_record_sha256": EXPECTED_TERMINAL_SHA256,
            "closure_binding_sha256": EXPECTED_CLOSURE_BINDING,
            "physical_operation": False,
            "private_runtime_accessed": False,
            "ready_authorized": False,
            "merge_authorized": False,
        }, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], str) else type(exc).__name__
        print(json.dumps({
            "schema": "gh.h3.n2.stage2d9r-g3r-d2-17-g18-main-integration-review/1",
            "status": "FAIL",
            "failure_code": code,
            "physical_operation": False,
            "private_runtime_accessed": False,
            "ready_authorized": False,
            "merge_authorized": False,
        }, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
