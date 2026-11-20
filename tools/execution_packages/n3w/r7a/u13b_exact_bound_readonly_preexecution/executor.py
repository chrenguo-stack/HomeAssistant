from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
P1_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u13b_real_t1_readonly_binding_preflight"
    / "executor.py"
)

GATE_ID = "N3W_T1_U13B_P2_EXACT_BOUND_READONLY_PREEXECUTION_PACKAGE_20261117_01"
MANIFEST_SCHEMA = "gh.n3w-t1-u13b-p2-exact-bound-readonly-preexecution-manifest/1"
RESULT_SCHEMA = "gh.n3w-t1-u13b-p2-exact-bound-readonly-preexecution/1"
SAFE_STOP_STATUS = "U13B_READONLY_PREEXECUTION_OUTSIDE_DOMAIN_SAFE_STOP"


class Stop(RuntimeError):
    pass


def git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("git_command_failed:" + args[0])
    return completed.stdout.strip()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stop("module_load_failed:" + path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_manifest(expected_commit: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        document.get("schema") != MANIFEST_SCHEMA
        or document.get("gate_id") != GATE_ID
        or document.get("read_only_preexecution") is not True
        or type(document.get("real_t1_readonly_execution_authorized")) is not bool
        or document.get("u13b_live_execution_authorized") is not False
        or document.get("new_clean_ota_mutation_authorized") is not False
        or document.get("controlled_rollback_mutation_authorized") is not False
    ):
        raise Stop("manifest_gate_invalid")
    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


def verify_fresh_binding(
    observed: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    required_false = (
        "current_probe_transaction_mutation",
        "current_probe_usb_mutation",
        "current_probe_service_mutation",
        "current_probe_image_mutation",
        "current_probe_ha_data_mutation",
        "current_probe_authorization_claim",
        "current_probe_u13a_transition",
        "current_probe_u13b_transition",
    )
    if (
        observed.get("status") != "U13B_REAL_T1_READONLY_BINDING_PASS"
        or observed.get("read_only") is not True
        or observed.get("fresh_binding") is not True
        or observed.get("expected_terminal_u13a") is not True
        or observed.get("rollback_eligible") is not False
        or observed.get("historical_transaction_phase") != expected["phase"]
        or observed.get("historical_transaction_status") != expected["status"]
        or observed.get("historical_transaction_sha256")
        != expected["transaction_sha256"]
        or observed.get("historical_usb_phase_sha256")
        != expected["usb_metadata_sha256"]["phase"]
        or observed.get("historical_u13a_authorization_claimed") is not True
        or observed.get("historical_u13a_authorization_consumed") is not True
        or observed.get("historical_u13a_replay_permitted") is not False
        or any(observed.get(name) is not False for name in required_false)
    ):
        raise Stop("fresh_p1_binding_drift")


def classify_bound_state(expected: dict[str, Any]) -> dict[str, Any]:
    if (
        expected.get("phase") != "U13A_COMMITTED"
        or expected.get("status") != "COMMITTED"
        or expected.get("recovery_required") is not False
    ):
        raise Stop("bound_state_not_terminal_u13a")
    return {
        "status": SAFE_STOP_STATUS,
        "outside_u13b_rollback_domain": True,
        "expected_safe_stop": True,
        "rollback_eligible": False,
        "new_clean_ota_required": True,
        "read_only": True,
        "current_probe_transaction_mutation": False,
        "current_probe_usb_mutation": False,
        "current_probe_service_mutation": False,
        "current_probe_image_mutation": False,
        "current_probe_ha_data_mutation": False,
        "current_probe_authorization_claim": False,
        "current_probe_u13a_transition": False,
        "current_probe_u13b_transition": False,
        "u13b_live_execution_authorized": False,
        "new_clean_ota_mutation_authorized": False,
        "controlled_rollback_mutation_authorized": False,
        "board_access": False,
        "merge": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "gate_id": GATE_ID,
        "status": "STOP",
        "t1_access": False,
        "read_only": True,
        "expected_safe_stop": False,
        "rollback_eligible": False,
        "new_clean_ota_required": True,
        "current_probe_transaction_mutation": False,
        "current_probe_usb_mutation": False,
        "current_probe_service_mutation": False,
        "current_probe_image_mutation": False,
        "current_probe_ha_data_mutation": False,
        "current_probe_authorization_claim": False,
        "current_probe_u13a_transition": False,
        "current_probe_u13b_transition": False,
        "u13b_live_execution_authorized": False,
        "new_clean_ota_mutation_authorized": False,
        "controlled_rollback_mutation_authorized": False,
        "board_access": False,
        "merge": False,
    }
    return_code = 2
    evidence: Path | None = None
    try:
        manifest = read_manifest(args.expected_package_commit)
        if manifest["real_t1_readonly_execution_authorized"] is not True:
            raise Stop("real_t1_readonly_execution_not_authorized")

        p1 = load_module(P1_EXECUTOR, "n3w_u13b_p2_p1_binding")
        evidence = p1.prepare_evidence_root(args.evidence_root)
        _, observed = p1.run_status_only(
            execution_id=args.execution_id + "-fresh-binding",
            evidence_root=evidence,
            t1_ssh_target=args.t1_ssh_target,
            known_hosts=args.known_hosts,
            expected_host_key_sha256=args.expected_host_key_sha256,
            expected_terminal=manifest["p1_expected_terminal"],
            access_state=result,
        )
        verify_fresh_binding(observed, manifest["fresh_binding"])
        result.update(classify_bound_state(manifest["fresh_binding"]))
        result["t1_access"] = True
        result["fresh_binding_revalidated"] = True
        result["bound_transaction_sha256"] = manifest["fresh_binding"][
            "transaction_sha256"
        ]
        result["bound_transaction_id_sha256"] = manifest["fresh_binding"][
            "transaction_id_sha256"
        ]
        result["bound_filesystem_uuid"] = manifest["fresh_binding"][
            "filesystem_uuid"
        ]
        result["local_evidence_write"] = True
        return_code = 2
    except Exception as error:
        result.update(
            status="STOP",
            reason=type(error).__name__ + ":" + str(error)[:300],
        )
    finally:
        if evidence is not None:
            try:
                p1.write_private_json(evidence / "p2_result.json", result)
            except Exception as error:
                result.update(
                    status="STOP_POSTSUCCESS_LOCAL",
                    reason=type(error).__name__ + ":" + str(error)[:220],
                )
                return_code = 2

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
