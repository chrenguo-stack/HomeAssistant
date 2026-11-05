#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
READONLY_EXECUTOR_PATH = REPO_ROOT / "tools/execution_packages/n3w/u2/ha_p5_attempt03_residue_readonly/executor.py"
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from n3w_t1_ssh_transport import SSHTransport

SCHEMA = "gh.n3w-t1-core-updater-ha-p5-residue-cleanup/1"
GATE_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_ATTEMPT03_RESIDUE_CLEANUP_20261105_01"
CONFIRMATION = "EXECUTE HA P5 ATTEMPT03 RESIDUE CLEANUP: YES"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

class StopExecution(RuntimeError):
    pass

def load_readonly():
    spec = importlib.util.spec_from_file_location("ha_p5_residue_readonly", READONLY_EXECUTOR_PATH)
    if spec is None or spec.loader is None:
        raise StopExecution("readonly_executor_load_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        raise StopExecution("git_command_failed")
    return result.stdout.strip()

def read_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("manifest_invalid") from error
    if not isinstance(value, dict):
        raise StopExecution("manifest_invalid")
    return value

def validate_source(expected_head: str) -> dict[str, Any]:
    if SHA40.fullmatch(expected_head) is None:
        raise StopExecution("expected_source_head_invalid")
    if git_text("rev-parse", "HEAD") != expected_head:
        raise StopExecution("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("tracked_worktree_dirty")
    manifest = read_manifest()
    if manifest.get("schema") != "gh.n3w-t1-core-updater-ha-p5-residue-cleanup-package/1":
        raise StopExecution("manifest_schema_invalid")
    if manifest.get("gate_id") != GATE_ID:
        raise StopExecution("manifest_gate_invalid")
    bindings = manifest.get("source_binding")
    if not isinstance(bindings, dict):
        raise StopExecution("manifest_source_binding_invalid")
    for relative, expected_blob in bindings.items():
        if not isinstance(relative, str) or not isinstance(expected_blob, str):
            raise StopExecution("manifest_source_binding_invalid")
        if SHA40.fullmatch(expected_blob) is None:
            raise StopExecution("manifest_source_blob_invalid")
        if git_text("rev-parse", f"{expected_head}:{relative}") != expected_blob:
            raise StopExecution(f"source_blob_mismatch:{Path(relative).name}")
    return manifest

def execute(args: argparse.Namespace) -> dict[str, Any]:
    manifest = validate_source(args.expected_source_head)
    if manifest.get("live_cleanup_authorized") is not True:
        raise StopExecution("live_cleanup_not_authorized")
    authorization_id = manifest.get("authorization_id")
    expected_hash = manifest.get("expected_residue_container_id_sha256")
    if not isinstance(authorization_id, str) or not authorization_id:
        raise StopExecution("cleanup_authorization_missing")
    if not isinstance(expected_hash, str) or SHA256.fullmatch(expected_hash) is None:
        raise StopExecution("expected_residue_hash_missing")
    if args.authorization_id != authorization_id:
        raise StopExecution("cleanup_authorization_id_mismatch")
    if args.confirm != CONFIRMATION:
        raise StopExecution("cleanup_confirmation_invalid")

    readonly = load_readonly()
    readonly.validate_target(args.target)
    transport = SSHTransport(
        target=args.target,
        known_hosts=args.known_hosts,
        expected_host_key_sha256=args.expected_host_key_sha256,
    )
    started = False
    try:
        transport.start_epoch()
        started = True
        before_result = transport.run_remote(["python3", "-c", readonly.REMOTE_PROBE], timeout=180, check=True)
        before = json.loads(before_result.stdout)
        classification = readonly.classify_remote(before)
        if classification["residue_container_id_sha256"] != expected_hash:
            raise StopExecution("residue_hash_drift")
        raw_id = classification["residue_container_id"]
        removed = transport.run_remote(["docker", "rm", raw_id], timeout=120, check=True)
        if removed.stdout.strip() != raw_id:
            raise StopExecution("docker_rm_result_invalid")
        after_result = transport.run_remote(["python3", "-c", readonly.REMOTE_PROBE], timeout=180, check=True)
        after = json.loads(after_result.stdout)
        containers = after.get("containers")
        if not isinstance(containers, list):
            raise StopExecution("post_cleanup_container_report_invalid")
        running = [item for item in containers if isinstance(item, dict) and item.get("running") is True]
        residue = [item for item in containers if isinstance(item, dict) and item.get("running") is False]
        if len(running) != 1 or residue:
            raise StopExecution("post_cleanup_container_state_invalid")
        current = running[0]
        if current.get("image_ref") != readonly.PREDECESSOR_IMAGE:
            raise StopExecution("post_cleanup_predecessor_invalid")
        target_image = after.get("target_image")
        if not isinstance(target_image, dict) or target_image.get("reference") != readonly.TARGET_IMAGE:
            raise StopExecution("post_cleanup_target_image_missing")
        return {
            "schema": SCHEMA,
            "gate_id": GATE_ID,
            "status": "PASS",
            "operation": "bounded_residue_cleanup",
            "mutation": True,
            "authorization_id": authorization_id,
            "residue_container_id_sha256": expected_hash,
            "removed_container_count": 1,
            "running_predecessor_image_ref": readonly.PREDECESSOR_IMAGE,
            "target_image_retained": True,
            "board_access": False,
        }
    finally:
        if started:
            transport.close_epoch()

def main() -> int:
    parser = argparse.ArgumentParser(prog="n3w-ha-p5-attempt03-residue-cleanup")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-source-head", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"schema": SCHEMA, "status": "STOP", "reason": "execute_flag_required"}, sort_keys=True))
        return 2
    try:
        result = execute(args)
    except Exception as error:
        reason = str(error)
        if not reason or len(reason) > 200 or "/" in reason or "\\" in reason or "@" in reason:
            reason = type(error).__name__
        print(json.dumps({"schema": SCHEMA, "status": "STOP", "reason": reason}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
