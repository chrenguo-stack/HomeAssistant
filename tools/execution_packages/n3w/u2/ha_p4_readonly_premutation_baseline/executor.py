#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shlex
import stat
import subprocess
import tarfile
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"

GATE_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_P4_FRESH_READONLY_PREMUTATION_BASELINE_20261105_01"
SCHEMA = "gh.n3w-t1-core-updater-ha-p4-readonly-premutation-baseline-execution/1"
REMOTE_SCHEMA = "gh.n3w-t1-core-updater-ha-p4-readonly-premutation-baseline/1"
CONFIRMATION = "READONLY HA P4 PREMUTATION BASELINE: YES"
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_SOURCE_PATHS = frozenset(
    {
        "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json",
        "tools/n3w_t1_core_updater.py",
        "tools/n3w_t1_core_updater_common.py",
        "tools/n3w_t1_core_updater_core.py",
        "tools/n3w_t1_core_updater_host.py",
        "tools/n3w_t1_core_updater_state.py",
        "tools/n3w_t1_core_updater_a1_policy.py",
        "tools/n3w_t1_core_updater_components.py",
        "tools/n3w_t1_core_updater_v2.py",
        "tools/n3w_t1_core_updater_v2_common.py",
        "tools/n3w_t1_core_updater_v2_state.py",
        "tools/n3w_t1_portable_image_identity.py",
        "tools/execution_packages/n3w/u2/ha_p4_readonly_premutation_baseline/remote_probe.py",
    }
)

REMOTE_RUNNER = r"""
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

root = tempfile.mkdtemp(prefix="n3w-ha-p4-", dir="/tmp")
os.chmod(root, 0o700)
try:
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r:*") as archive:
        members = archive.getmembers()
        for member in members:
            if (
                member.name.startswith("/")
                or ".." in member.name.split("/")
                or "/" in member.name
                or member.issym()
                or member.islnk()
            ):
                raise RuntimeError("bundle_member_invalid")
        archive.extractall(root)
    result = subprocess.run(
        [sys.executable, "-B", "remote_probe.py"],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=300,
    )
    sys.stdout.buffer.write(result.stdout)
    sys.stdout.buffer.flush()
    raise SystemExit(result.returncode)
finally:
    shutil.rmtree(root, ignore_errors=True)
"""


class StopExecution(RuntimeError):
    pass


def run(
    argv: list[str],
    *,
    input_bytes: bytes | None = None,
    timeout: int = 180,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            argv,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise StopExecution("command_timeout") from error
    except OSError as error:
        raise StopExecution("command_transport_error") from error
    if check and result.returncode != 0:
        raise StopExecution(f"command_failed:{Path(argv[0]).name}:{result.returncode}")
    return result


def git_text(*args: str) -> str:
    result = run(["git", "-C", str(REPO_ROOT), *args], timeout=30)
    return result.stdout.decode().strip()


def read_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("manifest_invalid") from error
    if not isinstance(value, dict):
        raise StopExecution("manifest_shape_invalid")
    return value


def validate_target(target: str) -> None:
    if (
        not target
        or target.strip() != target
        or any(character.isspace() for character in target)
        or target.startswith("-")
        or any(mark in target.casefold() for mark in ("placeholder", "example", "<", ">"))
    ):
        raise StopExecution("t1_target_invalid")


def validate_source(expected_head: str) -> dict[str, Any]:
    if GIT_SHA.fullmatch(expected_head) is None:
        raise StopExecution("expected_source_head_invalid")
    if git_text("rev-parse", "HEAD") != expected_head:
        raise StopExecution("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("tracked_worktree_dirty")

    manifest = read_manifest()
    if manifest.get("schema") != "gh.n3w-t1-core-updater-ha-p4-readonly-premutation-baseline-execution-package/1":
        raise StopExecution("manifest_schema_invalid")
    if manifest.get("gate_id") != GATE_ID:
        raise StopExecution("manifest_gate_mismatch")
    parent = manifest.get("authority_parent_head")
    if parent != "bb845f5cca4f2fc3e4710d14b6176a043d2a4523":
        raise StopExecution("authority_parent_invalid")
    ancestor = run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", parent, expected_head],
        timeout=30,
        check=False,
    )
    if ancestor.returncode != 0:
        raise StopExecution("authority_parent_not_ancestor")

    bindings = manifest.get("source_binding")
    if not isinstance(bindings, dict) or set(bindings) != EXPECTED_SOURCE_PATHS:
        raise StopExecution("manifest_source_binding_invalid")
    for relative, expected_blob in bindings.items():
        if not isinstance(expected_blob, str) or GIT_SHA.fullmatch(expected_blob) is None:
            raise StopExecution("manifest_source_blob_invalid")
        actual = git_text("rev-parse", f"{expected_head}:{relative}")
        if actual != expected_blob:
            raise StopExecution(f"source_blob_mismatch:{Path(relative).name}")

    execution = manifest.get("execution_authority")
    if not isinstance(execution, dict) or execution.get("confirmation") != CONFIRMATION:
        raise StopExecution("manifest_execution_authority_invalid")
    required_false = (
        "t1_mutation",
        "persistent_t1_file_write",
        "service_restart",
        "image_load",
        "updater_apply",
        "updater_rollback",
        "credential_mutation",
        "board_access",
        "merge",
    )
    if any(execution.get(key) is not False for key in required_false):
        raise StopExecution("manifest_mutation_scope_invalid")
    if execution.get("t1_access") is not True or execution.get("temporary_scratch_write") is not True:
        raise StopExecution("manifest_readonly_scope_invalid")

    return {
        "exact_source_head": expected_head,
        "authority_parent_head": parent,
        "p3_executable_source_head": manifest.get("p3_executable_source_head"),
        "target_manifest_blob_sha": bindings[
            "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"
        ],
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
    return root


def write_private(path: Path, value: Any) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise StopExecution("evidence_write_short")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def bundle_source() -> bytes:
    manifest = read_manifest()
    bindings = manifest["source_binding"]
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for relative in sorted(bindings):
            path = REPO_ROOT / relative
            if path.is_symlink() or not path.is_file():
                raise StopExecution(f"bundle_source_invalid:{Path(relative).name}")
            if relative.endswith("/remote_probe.py"):
                name = "remote_probe.py"
            elif relative.endswith("homeassistant-2026.10.4.json"):
                name = "target.json"
            else:
                name = Path(relative).name
            payload = path.read_bytes()
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def ssh_probe(target: str, bundle: bytes) -> dict[str, Any]:
    validate_target(target)
    remote_command = "sudo -n python3 -c " + shlex.quote(REMOTE_RUNNER)
    result = run(
        [
            "ssh",
            "-o",
            "BatchMode=no",
            "-o",
            "NumberOfPasswordPrompts=1",
            "-o",
            "PreferredAuthentications=publickey,password",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ConnectionAttempts=1",
            "-o",
            "ServerAliveInterval=5",
            "-o",
            "ServerAliveCountMax=2",
            target,
            remote_command,
        ],
        input_bytes=bundle,
        timeout=420,
        check=False,
    )
    try:
        document = json.loads(result.stdout.decode())
    except (UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("remote_report_json_invalid") from error
    if not isinstance(document, dict):
        raise StopExecution("remote_report_shape_invalid")
    if result.returncode not in (0, 2):
        raise StopExecution(f"remote_probe_exit_invalid:{result.returncode}")
    return document


def require_remote_pass(document: dict[str, Any]) -> None:
    if (
        document.get("schema") != REMOTE_SCHEMA
        or document.get("status") != "PASS"
        or document.get("operation") != "readonly_premutation_baseline"
        or document.get("mutation") is not False
        or document.get("persistent_t1_file_write") is not False
        or document.get("temporary_scratch_write") is not True
        or document.get("service_restart") is not False
        or document.get("image_load") is not False
        or document.get("updater_apply") is not False
        or document.get("updater_rollback") is not False
        or document.get("component") != "homeassistant"
        or document.get("runtime_class") != "TARGET_BOUND_RUNNING"
        or document.get("health_state") != "HEALTHY"
        or document.get("recovery_required") is not False
        or document.get("baseline_double_read_stable") is not True
        or document.get("target_image_prestate") != "ABSENT"
        or document.get("target_archive_verified") is not False
        or document.get("template_convergence_planned") is not True
        or document.get("rollback_available") is not True
        or document.get("readonly_state_stable") is not True
    ):
        raise StopExecution("p4_remote_pass_contract_invalid")
    for field in (
        "baseline_sha256",
        "plan_sha256",
        "transaction_sha256",
        "product_snapshot_sha256",
        "state_snapshot_sha256",
        "service_snapshot_sha256",
    ):
        value = document.get(field)
        if not isinstance(value, str) or SHA256.fullmatch(value) is None:
            raise StopExecution(f"p4_remote_hash_invalid:{field}")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise StopExecution("readonly_confirmation_invalid")
    validate_target(args.target)
    source_authority = validate_source(args.expected_source_head)
    evidence = prepare_evidence_root(args.evidence_root)
    bundle = bundle_source()

    remote = ssh_probe(args.target, bundle)
    write_private(evidence / "remote-report.json", remote)
    require_remote_pass(remote)

    result = {
        "schema": SCHEMA,
        "gate_id": GATE_ID,
        "status": "PASS",
        "operation": "readonly_premutation_baseline",
        "t1_access": True,
        "mutation": False,
        "persistent_t1_file_write": False,
        "temporary_scratch_write": True,
        "service_restart": False,
        "image_load": False,
        "updater_apply": False,
        "updater_rollback": False,
        "board_access": False,
        "source_authority": source_authority,
        "runtime_class": remote["runtime_class"],
        "health_state": remote["health_state"],
        "recovery_required": remote["recovery_required"],
        "image_bindings": remote["image_bindings"],
        "image_binding_modes": remote["image_binding_modes"],
        "baseline_double_read_stable": remote["baseline_double_read_stable"],
        "baseline_sha256": remote["baseline_sha256"],
        "plan_sha256": remote["plan_sha256"],
        "transaction_sha256": remote["transaction_sha256"],
        "product_snapshot_sha256": remote["product_snapshot_sha256"],
        "state_snapshot_sha256": remote["state_snapshot_sha256"],
        "service_snapshot_sha256": remote["service_snapshot_sha256"],
        "target_image_prestate": remote["target_image_prestate"],
        "target_archive_verified": remote["target_archive_verified"],
        "template_convergence_planned": remote["template_convergence_planned"],
        "rollback_available": remote["rollback_available"],
        "readonly_state_stable": remote["readonly_state_stable"],
        "raw_target_public_output": False,
        "private_evidence_files": ["remote-report.json"],
    }
    write_private(evidence / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="n3w-t1-core-updater-ha-p4-readonly-premutation-baseline"
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-source-head", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()

    if not args.execute:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "gate_id": GATE_ID,
                    "status": "STOP",
                    "mutation": False,
                    "reason": "execute_flag_required",
                },
                sort_keys=True,
            )
        )
        return 2

    try:
        result = execute(args)
    except Exception as error:
        reason = str(error)
        if (
            not reason
            or len(reason) > 200
            or "/" in reason
            or "\\" in reason
            or "@" in reason
        ):
            reason = type(error).__name__
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "gate_id": GATE_ID,
                    "status": "STOP",
                    "mutation": False,
                    "reason": reason,
                },
                sort_keys=True,
            )
        )
        return 2

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
