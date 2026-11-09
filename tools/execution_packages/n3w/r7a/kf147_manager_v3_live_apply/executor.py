#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
MANIFEST_PATH = PACKAGE_DIR / "manifest.json"
REMOTE_APPLY_PATH = PACKAGE_DIR / "remote_apply.py"
SSH_TRANSPORT_PATH = REPO_ROOT / "tools/n3w_t1_ssh_transport.py"
REPOSITORY = "chrenguo-stack/HomeAssistant"
GATE_ID = "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_MANAGER_IPC_V3_IMAGE_ONLY_LIVE_APPLY_20261109_01"
CONFIRMATION = "EXECUTE KF147 MANAGER IPC V3 IMAGE ONLY LIVE APPLY: YES"
REMOTE_DIR = "/var/tmp/n3w-kf147-manager-v3-live-20261109-01"
EXPECTED_MANAGER_SHA = "9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5"
EXPECTED_MANAGER_SIZE = 62957568
EXPECTED_TARGET = "local/greenhouse-manager:fresh-44e7d7472714"
EXPECTED_IMAGE_ID = "sha256:fd5104d610645347fe47137dbb24121851fa8a48530df3e3c905704607c5e3d4"
EXPECTED_SOURCE_HEAD = "44e7d74727147975de88e85c4b18ba3f7493fd76"
SSH_TRANSPORT_BLOB = "5bc28b30e696bd3d0f5ae4c98fd81b8f8679aaa7"

REMOTE_STREAM_WRITE = r"""
import os
import sys

path = sys.argv[1]
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
flags |= getattr(os, "O_NOFOLLOW", 0)
fd = os.open(path, flags, 0o600)
with os.fdopen(fd, "wb", closefd=True) as output:
    while True:
        block = sys.stdin.buffer.read(1024 * 1024)
        if not block:
            break
        output.write(block)
    output.flush()
    os.fsync(output.fileno())
directory = os.open(os.path.dirname(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
try:
    os.fsync(directory)
finally:
    os.close(directory)
"""


class Stop(RuntimeError):
    pass


def run(argv: list[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and p.returncode != 0:
        raise Stop(f"local_command_failed:{Path(argv[0]).name}:{p.returncode}")
    return p


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_text(*args: str) -> str:
    return run(["git", "-C", str(REPO_ROOT), *args], timeout=30).stdout.strip()


def read_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stop("manifest_invalid")
    return value


def write_private(path: Path, value: Any) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())


def evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise Stop("evidence_root_invalid")
        os.chmod(root, 0o700)
    else:
        root.mkdir(parents=True, mode=0o700)
    if root.stat().st_uid != os.geteuid() or stat.S_IMODE(root.stat().st_mode) != 0o700:
        raise Stop("evidence_root_metadata_invalid")
    return root


def load_transport() -> type:
    if git_text("hash-object", str(SSH_TRANSPORT_PATH)) != SSH_TRANSPORT_BLOB:
        raise Stop("ssh_transport_binding_invalid")
    spec = importlib.util.spec_from_file_location("n3w_t1_ssh_transport", SSH_TRANSPORT_PATH)
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport


def verify_local(args: argparse.Namespace) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", args.expected_package_commit or "") is None:
        raise Stop("expected_package_commit_invalid")
    if git_text("rev-parse", "HEAD") != args.expected_package_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    manifest = read_manifest()
    if manifest.get("schema") != "gh.n3w-t1-kf147-manager-v3-live-executor/1":
        raise Stop("manifest_schema_invalid")
    if manifest.get("gate_id") != GATE_ID or manifest.get("authorization_id") != GATE_ID:
        raise Stop("manifest_gate_invalid")
    if manifest.get("live_execution_authorized") is not True:
        raise Stop("live_execution_not_authorized")
    authority = manifest.get("package_authority")
    if not isinstance(authority, dict):
        raise Stop("package_authority_missing")
    for key in ("workflow_run_id", "artifact_id", "artifact_name", "artifact_digest"):
        if not authority.get(key):
            raise Stop("package_authority_incomplete")
    if manifest.get("target", {}).get("manager_image") != EXPECTED_TARGET:
        raise Stop("manifest_target_invalid")
    return manifest


def verify_artifact(manifest: dict[str, Any], work: Path) -> tuple[Path, dict[str, Any]]:
    a = manifest["package_authority"]
    meta = json.loads(run([
        "gh", "api", f"repos/{REPOSITORY}/actions/artifacts/{a['artifact_id']}"
    ], timeout=60).stdout)
    if (
        meta.get("id") != a["artifact_id"]
        or meta.get("name") != a["artifact_name"]
        or meta.get("digest") != a["artifact_digest"]
        or meta.get("expired") is not False
        or meta.get("workflow_run", {}).get("id") != a["workflow_run_id"]
    ):
        raise Stop("artifact_metadata_mismatch")
    package = work / "package"
    package.mkdir()
    run([
        "gh", "run", "download", str(a["workflow_run_id"]), "-R", REPOSITORY,
        "-n", a["artifact_name"], "-D", str(package),
    ], timeout=900)
    if {p.name for p in package.iterdir()} != {"greenhouse-manager-arm64.tar", "manager-live-binding.json"}:
        raise Stop("artifact_file_set_invalid")
    tar = package / "greenhouse-manager-arm64.tar"
    binding = json.loads((package / "manager-live-binding.json").read_text(encoding="utf-8"))
    if (
        tar.stat().st_size != EXPECTED_MANAGER_SIZE
        or sha_file(tar) != EXPECTED_MANAGER_SHA
        or binding.get("source_head") != EXPECTED_SOURCE_HEAD
        or binding.get("target_manager") != EXPECTED_TARGET
        or binding.get("target_image_id") != EXPECTED_IMAGE_ID
        or binding.get("manager_tar_sha256") != EXPECTED_MANAGER_SHA
        or binding.get("manager_only") is not True
        or binding.get("usb_mutation") is not False
    ):
        raise Stop("artifact_binding_invalid")
    return package, {"metadata": meta, "binding": binding}


def child_ssh_argv(transport: Any, command: str) -> tuple[str, ...]:
    transport.assert_master()
    return (
        "ssh",
        "-n",
        "-F",
        "/dev/null",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={transport.known_hosts}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "HashKnownHosts=no",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "IdentityAgent=none",
        "-o",
        "ControlMaster=no",
        "-o",
        "ControlPersist=no",
        "-o",
        f"ControlPath={transport.control_path}",
        "-o",
        "BatchMode=yes",
        "-o",
        "PubkeyAuthentication=no",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "KbdInteractiveAuthentication=no",
        "-o",
        "PreferredAuthentications=none",
        "-o",
        "ProxyCommand=/usr/bin/false",
        transport.target,
        command,
    )


def stream_file_over_ssh(
    source: Path,
    transport: Any,
    remote_path: str,
    *,
    timeout: int,
) -> None:
    if source.is_symlink() or not source.is_file():
        raise Stop("stream_source_invalid")
    allowed = {
        f"{REMOTE_DIR}/remote_apply.py",
        f"{REMOTE_DIR}/greenhouse-manager-arm64.tar",
    }
    if remote_path not in allowed:
        raise Stop("stream_remote_path_invalid")
    command = shlex.join(("python3", "-c", REMOTE_STREAM_WRITE, remote_path))
    try:
        with source.open("rb") as stream:
            completed = subprocess.run(
                child_ssh_argv(transport, command),
                stdin=stream,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
    except subprocess.TimeoutExpired as error:
        raise Stop("command_timeout:ssh-stream") from error
    except OSError as error:
        raise Stop("command_transport_error:ssh-stream") from error
    if completed.returncode != 0:
        raise Stop(f"command_failed:ssh-stream:{completed.returncode}")


def parse_json_output(payload: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise Stop(f"{label}_json_invalid") from error
    if not isinstance(value, dict):
        raise Stop(f"{label}_shape_invalid")
    return value


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.authorization_id != GATE_ID or args.confirm != CONFIRMATION:
        raise Stop("authorization_or_confirmation_invalid")
    manifest = verify_local(args)
    root = evidence_root(args.evidence_root)
    result: dict[str, Any] = {
        "schema": "gh.n3w-t1-kf147-manager-v3-live-execution-result/1",
        "status": "STOP",
        "authorization_id": GATE_ID,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "t1_access": False,
        "remote_staging": False,
        "live_apply_invoked": False,
        "usb_mutation": False,
        "u2_plus": False,
        "merge": False,
        "first_failed_operation": None,
    }
    work = Path(tempfile.mkdtemp(prefix="n3w-kf147-manager-v3."))
    transport = None
    try:
        package, authority = verify_artifact(manifest, work)
        write_private(root / "package_authority.json", authority)
        transport_type = load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True
        if transport.run_remote(["test", "-e", REMOTE_DIR], check=False, timeout=30).returncode == 0:
            raise Stop("remote_staging_already_exists")
        transport.run_remote([
            "install", "-d", "-m", "0700", "-o", "root", "-g", "root", REMOTE_DIR
        ], timeout=60)
        stream_file_over_ssh(
            REMOTE_APPLY_PATH,
            transport,
            f"{REMOTE_DIR}/remote_apply.py",
            timeout=120,
        )
        stream_file_over_ssh(
            package / "greenhouse-manager-arm64.tar",
            transport,
            f"{REMOTE_DIR}/greenhouse-manager-arm64.tar",
            timeout=900,
        )
        result["remote_staging"] = True
        remote_sha = transport.run_remote([
            "sha256sum", f"{REMOTE_DIR}/greenhouse-manager-arm64.tar"
        ], timeout=120).stdout.split()[0]
        if remote_sha != EXPECTED_MANAGER_SHA:
            raise Stop("remote_tar_sha256_mismatch")
        pre = parse_json_output(
            transport.run_remote([
                "python3", "-B", f"{REMOTE_DIR}/remote_apply.py", "--preflight"
            ], timeout=180).stdout,
            "preflight",
        )
        if pre.get("status") != "PASS":
            raise Stop("remote_preflight_stop")
        write_private(root / "preflight.json", pre)
        result["live_apply_invoked"] = True
        remote = transport.run_remote([
            "python3", "-B", f"{REMOTE_DIR}/remote_apply.py",
            "--execute",
            "--manager-tar", f"{REMOTE_DIR}/greenhouse-manager-arm64.tar",
            "--authorization-id", GATE_ID,
            "--confirm", CONFIRMATION,
        ], timeout=1200, check=False)
        post = parse_json_output(remote.stdout, "execute")
        write_private(root / "remote_result.json", post)
        result["authorization_claimed"] = bool(post.get("authorization_claimed"))
        result["authorization_consumed"] = bool(post.get("authorization_consumed"))
        result["remote_returncode"] = remote.returncode
        if remote.returncode != 0 or post.get("status") != "PASS":
            result["first_failed_operation"] = post.get("first_failed_operation") or post.get("reason") or "remote_apply_failed"
            result["rollback"] = post.get("rollback")
            return result
        result.update({
            "status": "PASS",
            "manager_image": post.get("manager_image"),
            "manager_image_id": post.get("manager_image_id"),
            "manager_ipc_v3_support": post.get("manager_ipc_v3_support"),
            "homeassistant_image_mutation": post.get("homeassistant_image_mutation"),
            "homeassistant_container_recreated": post.get("homeassistant_container_recreated"),
            "broker_mutation": post.get("broker_mutation"),
            "u1_transaction_preserved": post.get("u1_transaction_preserved"),
            "prepare_candidate_preserved": post.get("prepare_candidate_preserved"),
            "rollback_required": post.get("rollback_required"),
        })
        return result
    except Exception as error:
        result["first_failed_operation"] = f"{type(error).__name__}:{str(error)[:240]}"
        return result
    finally:
        if transport is not None:
            try:
                closed = transport.close_epoch()
                result["ssh_master_cleanup"] = closed.get("session_closed") is True
            except Exception:
                result["ssh_master_cleanup"] = False
        try:
            write_private(root / "closure.json", result)
        except Exception:
            pass


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true")
    p.add_argument("--expected-package-commit")
    p.add_argument("--authorization-id")
    p.add_argument("--execution-id")
    p.add_argument("--evidence-root", type=Path)
    p.add_argument("--t1-ssh-target")
    p.add_argument("--known-hosts", type=Path)
    p.add_argument("--expected-host-key-sha256")
    p.add_argument("--confirm", default="")
    args = p.parse_args()
    required = [
        args.expected_package_commit, args.authorization_id, args.execution_id,
        args.evidence_root, args.t1_ssh_target, args.known_hosts,
        args.expected_host_key_sha256,
    ]
    if not args.execute or any(v is None for v in required):
        print(json.dumps({"status": "STOP", "reason": "execution_arguments_missing"}))
        return 2
    result = execute(args)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
