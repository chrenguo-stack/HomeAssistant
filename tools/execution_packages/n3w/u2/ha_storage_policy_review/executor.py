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

GATE_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_STORAGE_POLICY_REVIEW_20261105_01"
SCHEMA = "gh.n3w-t1-core-updater-ha-storage-policy-review-execution/1"
REMOTE_SCHEMA = "gh.n3w-t1-core-updater-ha-storage-policy-readonly/1"
CONFIRMATION = "READONLY HA STORAGE POLICY BASELINE: YES"
PARENT_HEAD = "8310804a222676aba78334f3c0fd291da636242d"
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")

BUNDLE_PATHS = {
    "tools/execution_packages/n3w/u2/ha_storage_policy_review/remote_probe.py": "remote_probe.py",
    "tools/n3w_t1_fresh_product_staging_host.py": "n3w_t1_fresh_product_staging_host.py",
}

REMOTE_RUNNER = r"""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

SCHEMA = "gh.n3w-t1-core-updater-ha-storage-policy-readonly/1"
MAX_BUNDLE_BYTES = 4 * 1024 * 1024
root = None
try:
    bundle = sys.stdin.buffer.read(MAX_BUNDLE_BYTES + 1)
    if len(bundle) > MAX_BUNDLE_BYTES:
        raise RuntimeError("bundle_too_large")
    root = tempfile.mkdtemp(prefix="n3w-ha-storage-", dir="/tmp")
    os.chmod(root, 0o700)
    with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:*") as archive:
        members = archive.getmembers()
        for member in members:
            if (
                member.name.startswith("/")
                or ".." in member.name.split("/")
                or "/" in member.name
                or member.issym()
                or member.islnk()
                or not member.isfile()
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
except SystemExit:
    raise
except Exception as error:
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "status": "STOP",
                "operation": "readonly_storage_policy_baseline",
                "mutation": False,
                "reason": "remote_runner_" + type(error).__name__,
            },
            sort_keys=True,
        )
    )
    raise SystemExit(2)
finally:
    if root is not None:
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
    return run(["git", "-C", str(REPO_ROOT), *args], timeout=30).stdout.decode().strip()


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
    if manifest.get("schema") != "gh.n3w-t1-core-updater-ha-storage-policy-review-package/1":
        raise StopExecution("manifest_schema_invalid")
    if manifest.get("gate_id") != GATE_ID:
        raise StopExecution("manifest_gate_invalid")
    if manifest.get("authority_parent_head") != PARENT_HEAD:
        raise StopExecution("authority_parent_invalid")
    if manifest.get("p5_source_head") != PARENT_HEAD:
        raise StopExecution("p5_source_authority_invalid")
    if manifest.get("live_ha_apply_authorized") is not False:
        raise StopExecution("live_apply_must_remain_unauthorized")

    ancestor = run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", PARENT_HEAD, expected_head],
        timeout=30,
        check=False,
    )
    if ancestor.returncode != 0:
        raise StopExecution("authority_parent_not_ancestor")

    bindings = manifest.get("source_binding")
    if not isinstance(bindings, dict):
        raise StopExecution("source_binding_invalid")
    for relative, expected_blob in bindings.items():
        if not isinstance(relative, str) or not isinstance(expected_blob, str):
            raise StopExecution("source_binding_invalid")
        if GIT_SHA.fullmatch(expected_blob) is None:
            raise StopExecution("source_blob_invalid")
        actual = git_text("rev-parse", f"{expected_head}:{relative}")
        if actual != expected_blob:
            raise StopExecution(f"source_blob_mismatch:{Path(relative).name}")
    if any(relative not in bindings for relative in BUNDLE_PATHS):
        raise StopExecution("bundle_source_binding_missing")

    authority = manifest.get("execution_authority")
    if not isinstance(authority, dict) or authority.get("confirmation") != CONFIRMATION:
        raise StopExecution("execution_authority_invalid")
    for key in (
        "t1_mutation",
        "persistent_t1_file_write",
        "service_restart",
        "image_load",
        "updater_apply",
        "updater_rollback",
        "credential_mutation",
        "board_access",
        "merge",
    ):
        if authority.get(key) is not False:
            raise StopExecution("readonly_scope_invalid")
    if authority.get("t1_access") is not True or authority.get("temporary_scratch_write") is not True:
        raise StopExecution("readonly_scope_invalid")

    return {
        "exact_source_head": expected_head,
        "authority_parent_head": PARENT_HEAD,
        "p5_source_head": PARENT_HEAD,
        "target_manifest_blob_sha": bindings["infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"],
        "adr0009_blob_sha": bindings["docs/adr/0009-t1-golden-master-firstboot-production-lifecycle.md"],
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
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for relative, name in sorted(BUNDLE_PATHS.items()):
            path = REPO_ROOT / relative
            if path.is_symlink() or not path.is_file():
                raise StopExecution(f"bundle_source_invalid:{Path(relative).name}")
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
            "sudo -n python3 -c " + shlex.quote(REMOTE_RUNNER),
        ],
        input_bytes=bundle,
        timeout=420,
        check=False,
    )
    if result.returncode not in (0, 2):
        raise StopExecution(f"remote_transport_failed:{result.returncode}")
    try:
        document = json.loads(result.stdout.decode())
    except (UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("remote_report_json_invalid") from error
    if not isinstance(document, dict):
        raise StopExecution("remote_report_shape_invalid")
    if document.get("status") != "PASS":
        reason = document.get("reason")
        if not isinstance(reason, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", reason):
            reason = "remote_stop"
        raise StopExecution(f"remote_probe_stop:{reason}")
    return document


def integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StopExecution(f"remote_integer_invalid:{field}")
    return value


def summarize(remote: dict[str, Any]) -> dict[str, Any]:
    if (
        remote.get("schema") != REMOTE_SCHEMA
        or remote.get("operation") != "readonly_storage_policy_baseline"
        or remote.get("mutation") is not False
        or remote.get("persistent_t1_file_write") is not False
        or remote.get("service_restart") is not False
        or remote.get("image_load") is not False
        or remote.get("updater_apply") is not False
        or remote.get("updater_rollback") is not False
        or remote.get("runtime_state_stable") is not True
    ):
        raise StopExecution("remote_pass_contract_invalid")

    authority = remote.get("storage_authority")
    filesystems = remote.get("filesystems")
    runtime = remote.get("runtime")
    extra = remote.get("extra_path_usage")
    if not all(isinstance(value, dict) for value in (authority, filesystems, runtime, extra)):
        raise StopExecution("remote_shape_invalid")

    same_device = (
        authority.get("staging_device")
        == authority.get("docker_device")
        == authority.get("image_store_device")
    )
    free_values = [
        integer(authority.get("staging_free_bytes"), "staging_free_bytes"),
        integer(authority.get("docker_free_bytes"), "docker_free_bytes"),
        integer(authority.get("image_store_free_bytes"), "image_store_free_bytes"),
    ]
    containers = runtime.get("containers")
    if not isinstance(containers, dict) or set(containers) != {"broker", "manager", "homeassistant"}:
        raise StopExecution("runtime_containers_invalid")

    image_sizes: dict[str, int] = {}
    container_rw: dict[str, int] = {}
    writable_bind_allocated: dict[str, int] = {}
    for service, record in containers.items():
        if not isinstance(record, dict) or record.get("container_running") is not True:
            raise StopExecution(f"runtime_service_invalid:{service}")
        image_sizes[service] = integer(record.get("image_size_bytes"), f"{service}_image_size")
        container_rw[service] = integer(record.get("container_size_rw_bytes"), f"{service}_container_rw")
        binds = record.get("writable_binds")
        if not isinstance(binds, list):
            raise StopExecution(f"runtime_binds_invalid:{service}")
        total = 0
        for bind in binds:
            if not isinstance(bind, dict) or not isinstance(bind.get("usage"), dict):
                raise StopExecution(f"runtime_bind_invalid:{service}")
            total += integer(bind["usage"].get("allocated_bytes"), f"{service}_bind_allocated")
        writable_bind_allocated[service] = total

    product_paths = {}
    for path, record in extra.items():
        if not isinstance(record, dict):
            raise StopExecution("extra_path_invalid")
        product_paths[path] = {
            "present": record.get("present") is True,
            "allocated_bytes": integer(record.get("allocated_bytes"), "extra_allocated"),
            "apparent_bytes": integer(record.get("apparent_bytes"), "extra_apparent"),
        }

    root_fs = filesystems.get("root")
    if not isinstance(root_fs, dict):
        raise StopExecution("root_filesystem_invalid")

    return {
        "storage_backend": authority.get("image_store_backend"),
        "staging_docker_image_store_same_device": same_device,
        "filesystem_total_bytes": integer(root_fs.get("total_bytes"), "root_total"),
        "filesystem_used_bytes": integer(root_fs.get("used_bytes"), "root_used"),
        "filesystem_free_bytes": integer(root_fs.get("free_bytes"), "root_free"),
        "filesystem_total_inodes": integer(root_fs.get("total_inodes"), "root_inodes"),
        "filesystem_free_inodes": integer(root_fs.get("free_inodes"), "root_free_inodes"),
        "minimum_storage_authority_free_bytes": min(free_values),
        "current_image_size_bytes": image_sizes,
        "container_rw_bytes": container_rw,
        "writable_bind_allocated_bytes": writable_bind_allocated,
        "selected_path_usage": product_paths,
        "runtime_state_stable": True,
    }


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise StopExecution("readonly_confirmation_invalid")
    source = validate_source(args.expected_source_head)
    evidence = prepare_evidence_root(args.evidence_root)
    remote = ssh_probe(args.target, bundle_source())
    write_private(evidence / "remote-report.json", remote)
    summary = summarize(remote)
    result = {
        "schema": SCHEMA,
        "gate_id": GATE_ID,
        "status": "PASS",
        "operation": "readonly_storage_policy_baseline",
        "t1_access": True,
        "mutation": False,
        "persistent_t1_file_write": False,
        "temporary_scratch_write": True,
        "service_restart": False,
        "image_load": False,
        "updater_apply": False,
        "updater_rollback": False,
        "board_access": False,
        "live_ha_apply_authorized": False,
        "source_authority": source,
        **summary,
        "private_evidence_files": ["remote-report.json"],
    }
    write_private(evidence / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(prog="n3w-ha-storage-policy-review")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-source-head", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args()

    if not args.execute:
        print(json.dumps({
            "schema": SCHEMA,
            "gate_id": GATE_ID,
            "status": "STOP",
            "mutation": False,
            "reason": "execute_flag_required",
        }, sort_keys=True))
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
        print(json.dumps({
            "schema": SCHEMA,
            "gate_id": GATE_ID,
            "status": "STOP",
            "mutation": False,
            "reason": reason,
            "live_ha_apply_authorized": False,
        }, sort_keys=True))
        return 2

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
