#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from n3w_t1_ssh_transport import SSHTransport

SCHEMA = "gh.n3w-t1-core-updater-ha-p5-residue-readonly/1"
GATE_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_P5_ATTEMPT03_RESIDUE_READONLY_20261105_01"
CONFIRMATION = "READONLY HA P5 ATTEMPT03 RESIDUE CLASSIFY: YES"
PROJECT = "n3wfc4"
SERVICE = "homeassistant"
SERVICES_UNIT = "n3wfc4-services-activation.service"
PREDECESSOR_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
TARGET_IMAGE = "local/n3w-homeassistant:2026.10.4-5881590f"
TARGET_MANIFEST_BLOB = "6966b4fe4d7620ccc436643cc840da9ae95e6010"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

REMOTE_PROBE = r"""
import json
import subprocess

PROJECT = "n3wfc4"
SERVICE = "homeassistant"
UNIT = "n3wfc4-services-activation.service"
PREDECESSOR = "local/n3w-homeassistant:2026.10.0-0c73235a"
TARGET = "local/n3w-homeassistant:2026.10.4-5881590f"

def run(argv, check=True):
    result = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=60,
    )
    if check and result.returncode:
        raise RuntimeError("command_failed:" + argv[0])
    return result

unit = run(["systemctl", "is-active", UNIT], check=False).stdout.strip()
raw_ids = run([
    "docker", "ps", "-aq", "--no-trunc",
    "--filter", "label=com.docker.compose.project=" + PROJECT,
    "--filter", "label=com.docker.compose.service=" + SERVICE,
]).stdout.splitlines()
containers = []
for raw in raw_ids:
    container_id = raw.strip()
    if not container_id:
        continue
    docs = json.loads(run(["docker", "inspect", container_id]).stdout)
    if not isinstance(docs, list) or len(docs) != 1:
        raise RuntimeError("inspect_shape_invalid")
    item = docs[0]
    state = item.get("State") or {}
    config = item.get("Config") or {}
    labels = config.get("Labels") or {}
    containers.append({
        "container_id": item.get("Id"),
        "name": item.get("Name"),
        "image_ref": config.get("Image"),
        "image_id": item.get("Image"),
        "status": state.get("Status"),
        "running": state.get("Running"),
        "exit_code": state.get("ExitCode"),
        "started_at": state.get("StartedAt"),
        "finished_at": state.get("FinishedAt"),
        "project": labels.get("com.docker.compose.project"),
        "service": labels.get("com.docker.compose.service"),
        "replace": labels.get("com.docker.compose.replace", ""),
    })

def image(reference):
    docs = json.loads(run(["docker", "image", "inspect", reference]).stdout)
    if not isinstance(docs, list) or len(docs) != 1:
        raise RuntimeError("image_shape_invalid")
    item = docs[0]
    return {
        "reference": reference,
        "image_id": item.get("Id"),
        "os": item.get("Os"),
        "architecture": item.get("Architecture"),
    }

print(json.dumps({
    "unit_state": unit,
    "containers": containers,
    "predecessor_image": image(PREDECESSOR),
    "target_image": image(TARGET),
}, sort_keys=True, separators=(",", ":")))
"""

class StopExecution(RuntimeError):
    pass

def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

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

def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("json_invalid") from error
    if not isinstance(value, dict):
        raise StopExecution("json_shape_invalid")
    return value

def validate_source(expected_head: str) -> dict[str, Any]:
    if SHA40.fullmatch(expected_head) is None:
        raise StopExecution("expected_source_head_invalid")
    if git_text("rev-parse", "HEAD") != expected_head:
        raise StopExecution("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("tracked_worktree_dirty")
    manifest = read_json(MANIFEST_PATH)
    if manifest.get("schema") != "gh.n3w-t1-core-updater-ha-p5-residue-readonly-package/1":
        raise StopExecution("manifest_schema_invalid")
    if manifest.get("gate_id") != GATE_ID:
        raise StopExecution("manifest_gate_invalid")
    if manifest.get("t1_mutation") is not False or manifest.get("board_access") is not False:
        raise StopExecution("manifest_readonly_invalid")
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
    if bindings.get("infra/n3w-t1/upgrades/homeassistant-2026.10.4.json") != TARGET_MANIFEST_BLOB:
        raise StopExecution("target_manifest_blob_drift")
    return {
        "exact_source_head": expected_head,
        "target_manifest_blob_sha": TARGET_MANIFEST_BLOB,
    }

def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    repo = REPO_ROOT.resolve()
    if root == repo or repo in root.parents:
        raise StopExecution("evidence_root_inside_repository")
    if root.exists():
        if (
            root.is_symlink()
            or not root.is_dir()
            or root.stat().st_uid != os.geteuid()
            or stat.S_IMODE(root.stat().st_mode) != 0o700
            or any(root.iterdir())
        ):
            raise StopExecution("evidence_root_invalid")
    else:
        root.mkdir(parents=True, mode=0o700)
        os.chmod(root, 0o700)
    return root

def write_private(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, payload.encode())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)

def classify_remote(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("unit_state") != "active":
        raise StopExecution("services_unit_not_active")
    containers = document.get("containers")
    if not isinstance(containers, list):
        raise StopExecution("container_report_invalid")
    for item in containers:
        if not isinstance(item, dict):
            raise StopExecution("container_report_invalid")
        if item.get("project") != PROJECT or item.get("service") != SERVICE:
            raise StopExecution("container_scope_invalid")
        container_id = item.get("container_id")
        image_id = item.get("image_id")
        if not isinstance(container_id, str) or len(container_id) != 64:
            raise StopExecution("container_id_invalid")
        if not isinstance(image_id, str) or not image_id.startswith("sha256:"):
            raise StopExecution("container_image_id_invalid")

    running = [item for item in containers if item.get("running") is True]
    residue = [item for item in containers if item.get("running") is False]
    if len(running) != 1:
        raise StopExecution("running_homeassistant_container_count_invalid")
    if len(residue) != 1:
        raise StopExecution("homeassistant_residue_count_invalid")

    current = running[0]
    stale = residue[0]
    predecessor_image = document.get("predecessor_image")
    target_image = document.get("target_image")
    if not isinstance(predecessor_image, dict) or not isinstance(target_image, dict):
        raise StopExecution("image_report_invalid")

    if (
        current.get("image_ref") != PREDECESSOR_IMAGE
        or current.get("status") != "running"
        or current.get("image_id") != predecessor_image.get("image_id")
    ):
        raise StopExecution("running_predecessor_invalid")
    if (
        stale.get("image_ref") != TARGET_IMAGE
        or stale.get("status") != "created"
        or stale.get("exit_code") != 0
        or stale.get("replace") != "homeassistant-1"
        or stale.get("image_id") != target_image.get("image_id")
    ):
        raise StopExecution("attempt03_residue_identity_invalid")
    if stale.get("started_at") not in {"0001-01-01T00:00:00Z", ""}:
        raise StopExecution("attempt03_residue_started")
    for image in (predecessor_image, target_image):
        if image.get("os") != "linux" or image.get("architecture") not in {"arm64", "aarch64"}:
            raise StopExecution("image_platform_invalid")

    raw_id = stale["container_id"]
    return {
        "classification": "ATTEMPT03_TARGET_RECREATE_CREATED_RESIDUE",
        "residue_container_id": raw_id,
        "residue_container_id_sha256": sha256_text(raw_id),
        "residue_image_ref": TARGET_IMAGE,
        "residue_image_id": stale["image_id"],
        "running_predecessor_image_ref": PREDECESSOR_IMAGE,
        "running_predecessor_image_id": current["image_id"],
        "target_image_prestate": "PRESENT_AND_EXACT_CANDIDATE",
        "cleanup_required_before_reapply": True,
    }

def validate_target(target: str) -> None:
    if (
        not target
        or target.strip() != target
        or any(character.isspace() for character in target)
        or target.startswith("-")
    ):
        raise StopExecution("t1_target_invalid")

def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise StopExecution("readonly_confirmation_invalid")
    validate_target(args.target)
    source = validate_source(args.expected_source_head)
    evidence = prepare_evidence_root(args.evidence_root)
    transport = SSHTransport(
        target=args.target,
        known_hosts=args.known_hosts,
        expected_host_key_sha256=args.expected_host_key_sha256,
    )
    started = False
    try:
        transport.start_epoch()
        started = True
        result = transport.run_remote(
            ["python3", "-c", REMOTE_PROBE],
            timeout=180,
            check=True,
        )
        try:
            remote = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise StopExecution("remote_json_invalid") from error
        if not isinstance(remote, dict):
            raise StopExecution("remote_json_shape_invalid")
        classification = classify_remote(remote)
        write_private(evidence / "remote-report.json", remote)
        write_private(evidence / "classification-private.json", classification)
        public = {
            "schema": SCHEMA,
            "gate_id": GATE_ID,
            "status": "PASS",
            "operation": "readonly_residue_classification",
            "mutation": False,
            "source_authority": source,
            "classification": classification["classification"],
            "residue_container_id_sha256": classification["residue_container_id_sha256"],
            "residue_image_ref": classification["residue_image_ref"],
            "running_predecessor_image_ref": classification["running_predecessor_image_ref"],
            "target_image_prestate": classification["target_image_prestate"],
            "cleanup_required_before_reapply": True,
            "board_access": False,
        }
        write_private(evidence / "result.json", public)
        return public
    finally:
        if started:
            transport.close_epoch()

def main() -> int:
    parser = argparse.ArgumentParser(prog="n3w-ha-p5-attempt03-residue-readonly")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-source-head", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
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
        print(json.dumps({"schema": SCHEMA, "status": "STOP", "reason": reason, "mutation": False}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
