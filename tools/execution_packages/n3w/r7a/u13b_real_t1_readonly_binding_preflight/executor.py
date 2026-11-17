from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
U13A_STATUS_EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u13a_live_commit"
    / "executor.py"
)

GATE_ID = "N3W_T1_U13B_REAL_T1_READONLY_BINDING_PREFLIGHT_20261117_01"
MANIFEST_SCHEMA = "gh.n3w-t1-u13b-real-t1-readonly-binding-preflight-manifest/1"
RESULT_SCHEMA = "gh.n3w-t1-u13b-real-t1-readonly-binding-preflight/1"


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
        or document.get("read_only_preflight") is not True
        or document.get("real_t1_readonly_execution_authorized") is not True
        or document.get("u13b_live_execution_authorized") is not False
        or document.get("new_clean_ota_mutation_authorized") is not False
        or document.get("controlled_rollback_mutation_authorized") is not False
    ):
        raise Stop("manifest_gate_invalid")
    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    repo = ROOT.resolve()
    if root == repo or repo in root.parents:
        raise Stop("evidence_root_inside_repository")
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise Stop("evidence_root_not_empty_private_directory")
    else:
        root.mkdir(parents=True, mode=0o700)
    os.chmod(root, 0o700)
    return root


def parse_last_json(stdout: str) -> dict[str, Any]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise Stop("delegated_status_result_missing")
    try:
        value = json.loads(lines[-1])
    except Exception as error:
        raise Stop("delegated_status_result_invalid_json") from error
    if not isinstance(value, dict):
        raise Stop("delegated_status_result_invalid")
    return value


def normalize_status(
    delegated: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    post = delegated.get("post")
    if not isinstance(post, dict):
        raise Stop("delegated_terminal_post_missing")
    mirror = post.get("usb_mirror")
    mirror_hashes = mirror.get("sha256") if isinstance(mirror, dict) else None
    runtime = post.get("runtime")
    if not isinstance(runtime, dict):
        raise Stop("delegated_terminal_runtime_missing")
    if (
        delegated.get("status") != "U13A_LIVE_COMMIT_PASS_RECONCILED"
        or delegated.get("terminal") is not True
        or delegated.get("reconciled_from_durable_u13a") is not True
        or delegated.get("replay_permitted") is not False
        or delegated.get("u13b_transition") is not False
        or post.get("transaction_phase") != expected["transaction_phase"]
        or post.get("transaction_status") != expected["transaction_status"]
        or post.get("recovery_required") is not False
        or post.get("transaction_sha256") != expected["transaction_sha256"]
        or runtime.get("target_runtime_image_id")
        != expected["target_runtime_image_id"]
        or mirror.get("exact") is not True
        or not isinstance(mirror_hashes, dict)
        or not isinstance(mirror_hashes.get("phase"), str)
    ):
        raise Stop("delegated_terminal_binding_drift")

    return {
        "schema": RESULT_SCHEMA,
        "status": "U13B_REAL_T1_READONLY_BINDING_PASS",
        "gate_id": GATE_ID,
        "t1_access": True,
        "read_only": True,
        "fresh_binding": True,
        "historical_transaction_phase": post["transaction_phase"],
        "historical_transaction_status": post["transaction_status"],
        "historical_transaction_sha256": post["transaction_sha256"],
        "historical_usb_phase_sha256": mirror_hashes["phase"],
        "historical_u13a_authorization_claimed": (
            delegated.get("authorization_claimed") is True
        ),
        "historical_u13a_authorization_consumed": (
            delegated.get("authorization_consumed") is True
        ),
        "historical_u13a_replay_permitted": False,
        "historical_u13a_terminal_transition_previously_occurred": True,
        "historical_u13a_transaction_was_mutated": True,
        "historical_u13a_usb_metadata_was_mutated": True,
        "delegated_status_reported_transaction_mutation": bool(
            delegated.get("transaction_mutation")
        ),
        "delegated_status_reported_usb_mutation": bool(
            delegated.get("usb_mutation")
        ),
        "current_probe_transaction_mutation": False,
        "current_probe_usb_mutation": False,
        "current_probe_service_mutation": False,
        "current_probe_image_mutation": False,
        "current_probe_ha_data_mutation": False,
        "current_probe_authorization_claim": False,
        "current_probe_u13a_transition": False,
        "current_probe_u13b_transition": False,
        "rollback_eligible": False,
        "expected_terminal_u13a": True,
        "new_clean_ota_required": True,
        "u13b_live_execution_authorized": False,
        "new_clean_ota_mutation_authorized": False,
        "controlled_rollback_mutation_authorized": False,
        "board_access": False,
        "merge": False,
    }


def run_status_only(
    *,
    expected_commit: str,
    execution_id: str,
    evidence_root: Path,
    t1_ssh_target: str,
    known_hosts: Path,
    expected_host_key_sha256: str,
    expected_terminal: dict[str, Any],
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    delegated_root = evidence_root / "u13a-terminal-status"
    command = [
        sys.executable,
        str(U13A_STATUS_EXECUTOR),
        "--expected-package-commit",
        expected_commit,
        "--execution-id",
        execution_id + "-u13a-terminal-status",
        "--evidence-root",
        str(delegated_root),
        "--t1-ssh-target",
        t1_ssh_target,
        "--known-hosts",
        str(known_hosts.expanduser()),
        "--expected-host-key-sha256",
        expected_host_key_sha256,
        "--status-only",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=300,
        check=False,
    )
    delegated = parse_last_json(completed.stdout)
    if completed.returncode != 0:
        reason = delegated.get("reason", "delegated_status_nonzero")
        raise Stop("delegated_u13a_status_failed:" + str(reason)[:220])
    return completed, normalize_status(delegated, expected_terminal)


def write_private_json(path: Path, value: dict[str, Any]) -> None:
    raw = json.dumps(value, sort_keys=True, indent=2) + "\n"
    path.write_text(raw, encoding="utf-8")
    os.chmod(path, 0o600)


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
        "status": "STOP",
        "gate_id": GATE_ID,
        "t1_access": False,
        "read_only": True,
        "fresh_binding": False,
        "current_probe_transaction_mutation": False,
        "current_probe_usb_mutation": False,
        "current_probe_service_mutation": False,
        "current_probe_image_mutation": False,
        "current_probe_ha_data_mutation": False,
        "current_probe_authorization_claim": False,
        "current_probe_u13a_transition": False,
        "current_probe_u13b_transition": False,
        "rollback_eligible": False,
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
        evidence = prepare_evidence_root(args.evidence_root)
        _, normalized = run_status_only(
            expected_commit=args.expected_package_commit,
            execution_id=args.execution_id,
            evidence_root=evidence,
            t1_ssh_target=args.t1_ssh_target,
            known_hosts=args.known_hosts,
            expected_host_key_sha256=args.expected_host_key_sha256,
            expected_terminal=manifest["expected_terminal_u13a"],
        )
        result.update(normalized)
        result["local_evidence_write"] = True
        return_code = 0
    except Exception as error:
        result.update(
            status="STOP",
            reason=type(error).__name__ + ":" + str(error)[:300],
        )
    finally:
        if evidence is not None:
            try:
                write_private_json(evidence / "binding_result.json", result)
            except Exception as error:
                if return_code == 0:
                    result.update(
                        status="STOP_POSTSUCCESS_LOCAL",
                        reason=type(error).__name__ + ":" + str(error)[:220],
                    )
                    return_code = 2

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
