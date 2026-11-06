#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import stat
import subprocess
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"

GATE_ID = (
    "N3W_T1_CORE_UPDATER_HOMEASSISTANT_RUNTIME_TEMPLATE_"
    "CONVERGENCE_READONLY_PREFLIGHT_20261105_01"
)
SCHEMA = "gh.n3w-t1-core-updater-ha-template-readonly-preflight-execution/1"
INSPECT_SCHEMA = "gh.n3w-t1-core-updater-ha-template-convergence/1"
INSPECTOR_RELATIVE = "tools/n3w_t1_core_updater_ha_template_convergence.py"
AUTHORITY_RELATIVE = "infra/n3w-t1/production/t1-core-stack-current.json"
AUTHORITY_PARENT_HEAD = "ead524a3e2102454e0a49b467aaa37ee4afc803a"
EXPECTED_INSPECTOR_BLOB = "9e8ad6ced381e6b4fa9ec146b4f143769c316ceb"
EXPECTED_AUTHORITY_BLOB = "07ceb3b352f21d925127caa71304cc3b29827fdb"
EXPECTED_HA_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"
CONFIRMATION = "READONLY HA TEMPLATE CONVERGENCE PREFLIGHT: YES"
STABLE_HASH_FIELDS = (
    "current_compose_sha256",
    "current_env_sha256",
    "candidate_compose_sha256",
    "candidate_env_sha256",
    "current_render_sha256",
    "candidate_render_sha256",
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


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


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution(f"json_invalid:{path.name}") from error
    if not isinstance(value, dict):
        raise StopExecution(f"json_shape_invalid:{path.name}")
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
    if git_text("rev-parse", f"{expected_head}:{INSPECTOR_RELATIVE}") != EXPECTED_INSPECTOR_BLOB:
        raise StopExecution("inspector_blob_mismatch")
    if git_text("rev-parse", f"{expected_head}:{AUTHORITY_RELATIVE}") != EXPECTED_AUTHORITY_BLOB:
        raise StopExecution("authority_blob_mismatch")
    ancestor = run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "merge-base",
            "--is-ancestor",
            AUTHORITY_PARENT_HEAD,
            expected_head,
        ],
        timeout=30,
        check=False,
    )
    if ancestor.returncode != 0:
        raise StopExecution("authority_parent_not_ancestor")

    manifest = read_json(MANIFEST_PATH)
    if manifest.get("gate_id") != GATE_ID:
        raise StopExecution("manifest_gate_mismatch")
    source = manifest.get("source_binding")
    if not isinstance(source, dict):
        raise StopExecution("manifest_source_binding_invalid")
    if (
        source.get("authority_parent_head") != AUTHORITY_PARENT_HEAD
        or source.get("inspector_blob_sha") != EXPECTED_INSPECTOR_BLOB
        or source.get("current_authority_blob_sha") != EXPECTED_AUTHORITY_BLOB
    ):
        raise StopExecution("manifest_source_binding_mismatch")
    return {
        "expected_source_head": expected_head,
        "authority_parent_head": AUTHORITY_PARENT_HEAD,
        "inspector_blob_sha": EXPECTED_INSPECTOR_BLOB,
        "current_authority_blob_sha": EXPECTED_AUTHORITY_BLOB,
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


def inspector_source() -> bytes:
    path = REPO_ROOT / INSPECTOR_RELATIVE
    if path.is_symlink() or not path.is_file():
        raise StopExecution("inspector_source_invalid")
    return path.read_bytes()


def ssh_inspect(target: str, source: bytes) -> dict[str, Any]:
    validate_target(target)
    remote_command = " ".join(
        shlex.quote(item)
        for item in (
            "sudo",
            "-n",
            "python3",
            "-B",
            "-",
            "inspect",
            "--expected-homeassistant-image",
            EXPECTED_HA_IMAGE,
        )
    )
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
        input_bytes=source,
        timeout=180,
        check=False,
    )
    try:
        document = json.loads(result.stdout.decode())
    except (UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("remote_report_json_invalid") from error
    if not isinstance(document, dict):
        raise StopExecution("remote_report_shape_invalid")
    if result.returncode not in (0, 2):
        raise StopExecution(f"remote_inspector_exit_invalid:{result.returncode}")
    return document


def require_pass(document: dict[str, Any]) -> None:
    if (
        document.get("schema") != INSPECT_SCHEMA
        or document.get("status") != "PASS"
        or document.get("operation") != "inspect"
        or document.get("mutation") is not False
        or document.get("expected_homeassistant_image") != EXPECTED_HA_IMAGE
        or document.get("current_binding_mode") != "legacy_static"
        or document.get("candidate_binding_mode") != "dynamic"
        or document.get("render_semantically_equal") is not True
        or document.get("product_path_write") is not False
        or document.get("service_restart") is not False
    ):
        raise StopExecution("ha_template_convergence_report_invalid")
    for field in STABLE_HASH_FIELDS:
        value = document.get(field)
        if not isinstance(value, str) or SHA256.fullmatch(value) is None:
            raise StopExecution(f"ha_template_hash_invalid:{field}")


def compare_runs(first: dict[str, Any], second: dict[str, Any]) -> None:
    for field in STABLE_HASH_FIELDS:
        if first[field] != second[field]:
            raise StopExecution(f"ha_template_readonly_stability_drift:{field}")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise StopExecution("readonly_confirmation_invalid")
    validate_target(args.target)
    source_authority = validate_source(args.expected_source_head)
    evidence = prepare_evidence_root(args.evidence_root)
    source = inspector_source()

    first = ssh_inspect(args.target, source)
    write_private(evidence / "inspection-1.json", first)
    require_pass(first)

    second = ssh_inspect(args.target, source)
    write_private(evidence / "inspection-2.json", second)
    require_pass(second)
    compare_runs(first, second)

    result = {
        "schema": SCHEMA,
        "gate_id": GATE_ID,
        "status": "PASS",
        "operation": "readonly_preflight",
        "mutation": False,
        "persistent_t1_file_write": False,
        "temporary_scratch_write": True,
        "service_restart": False,
        "image_load": False,
        "updater_apply": False,
        "updater_rollback": False,
        "board_access": False,
        "expected_homeassistant_image": EXPECTED_HA_IMAGE,
        "current_binding_mode": "legacy_static",
        "candidate_binding_mode": "dynamic",
        "render_semantically_equal": True,
        "double_read_stable": True,
        "source_authority": source_authority,
        "current_compose_sha256": first["current_compose_sha256"],
        "current_env_sha256": first["current_env_sha256"],
        "candidate_compose_sha256": first["candidate_compose_sha256"],
        "candidate_env_sha256": first["candidate_env_sha256"],
        "current_render_sha256": first["current_render_sha256"],
        "candidate_render_sha256": first["candidate_render_sha256"],
        "raw_target_public_output": False,
        "private_evidence_files": [
            "inspection-1.json",
            "inspection-2.json",
        ],
    }
    write_private(evidence / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="n3w-t1-core-updater-ha-template-readonly-preflight"
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
