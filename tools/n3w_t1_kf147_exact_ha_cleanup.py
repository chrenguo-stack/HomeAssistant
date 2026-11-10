#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any, Sequence

from n3w_t1_kf147_fresh_capacity import MUTABLE_RUNTIME_PROBE, validate_live_baseline
from n3w_t1_ssh_transport import SSHTransport

REPO_ROOT = Path(__file__).resolve().parents[1]
PRECLAIM_SCHEMA = "gh.n3w-t1-kf147-ha-image-cleanup-preclaim/1"
EXECUTION_SCHEMA = "gh.n3w-t1-kf147-ha-image-cleanup-execution/1"
AUTHORIZATION_ID = "N3W_T1_KF147_EXACT_HA_2026_10_4_IMAGE_CLEANUP_20261110_01"
CONFIRMATION = "EXECUTE KF147 EXACT HA 2026.10.4 IMAGE CLEANUP: YES"
TARGET_IMAGE_REF = "local/n3w-homeassistant:2026.10.4-5881590f"
TARGET_IMAGE_ID = "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"
RUNNING_HA_REF = "local/n3w-homeassistant:2026.10.0-0c73235a"
RUNNING_HA_ID = "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"
EXPECTED_U1_TRANSACTION_SHA256 = "6e1f0b5d262e346674b62ac79bf2ffbc1c63a8dd22379a0a82c952f0e3626b49"
TARGET_ARCHIVE_SHA256 = "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
TARGET_ARTIFACT_ID = 13391983948
TARGET_MANIFEST = REPO_ROOT / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"
TARGET_MANIFEST_BLOB = "6966b4fe4d7620ccc436643cc840da9ae95e6010"
POLICY_PATH = REPO_ROOT / "infra/n3w-t1/updater-releases/storage-image-lifecycle-policy.json"
AUTHORIZATION_MANIFEST = REPO_ROOT / "tools/execution_packages/n3w/r7a/kf147_ha_image_cleanup/manifest.json"

TARGET_PROBE = r'''\
import json
import shutil
import subprocess
import sys

TARGET_REF = "local/n3w-homeassistant:2026.10.4-5881590f"
TARGET_ID = "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"


def run(argv, check=True):
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=300,
    )
    if check and completed.returncode != 0:
        raise RuntimeError("command_failed:" + argv[0] + ":" + str(completed.returncode))
    return completed


def references():
    listed = run(["docker", "ps", "-aq", "--no-trunc"], check=False)
    if listed.returncode != 0:
        raise RuntimeError("container_list_failed")
    ids = sorted(set(listed.stdout.split()))
    if not ids:
        return []
    docs = json.loads(run(["docker", "container", "inspect", *ids]).stdout)
    result = []
    for item in docs:
        config = item.get("Config") or {}
        if item.get("Image") == TARGET_ID or config.get("Image") == TARGET_REF:
            result.append({
                "id": item.get("Id"),
                "name": item.get("Name"),
                "image_id": item.get("Image"),
                "image_ref": config.get("Image"),
                "running": (item.get("State") or {}).get("Running"),
            })
    return result


def image(expect_present):
    by_ref = run(["docker", "image", "inspect", TARGET_REF], check=False)
    by_id = run(["docker", "image", "inspect", TARGET_ID], check=False)
    if not expect_present:
        if by_ref.returncode == 0 or by_id.returncode == 0:
            raise RuntimeError("target_image_still_present")
        return {"present": False}
    if by_ref.returncode != 0 or by_id.returncode != 0:
        raise RuntimeError("target_image_missing")
    ref_docs = json.loads(by_ref.stdout)
    id_docs = json.loads(by_id.stdout)
    if len(ref_docs) != 1 or len(id_docs) != 1:
        raise RuntimeError("target_image_inspect_invalid")
    if ref_docs[0].get("Id") != TARGET_ID or id_docs[0].get("Id") != TARGET_ID:
        raise RuntimeError("target_image_id_drift")
    tags = ref_docs[0].get("RepoTags") or []
    if set(tags) != {TARGET_REF}:
        raise RuntimeError("target_image_tag_set_ambiguous")
    return {"present": True, "id": TARGET_ID, "repo_tags": tags, "size_bytes": ref_docs[0].get("Size")}


mode = sys.argv[1] if len(sys.argv) == 2 else ""
if mode not in {"present", "absent"}:
    raise SystemExit(64)
refs = references()
if refs:
    raise RuntimeError("target_container_reference_present")
print(json.dumps({
    "target": image(mode == "present"),
    "target_container_references": refs,
    "root_free_bytes": shutil.disk_usage("/").free,
}, sort_keys=True))
'''


class CleanupStop(RuntimeError):
    pass


def _run(argv: list[str]) -> str:
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=60,
    )
    if completed.returncode != 0:
        raise CleanupStop(f"local_command_failed:{Path(argv[0]).name}:{completed.returncode}")
    return completed.stdout.strip()


def _git(*args: str) -> str:
    return _run(["git", "-C", str(REPO_ROOT), *args])


def _read_json(path: Path, reason: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CleanupStop(reason)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CleanupStop(reason) from error
    if not isinstance(value, dict):
        raise CleanupStop(reason)
    return value


def verify_repository_authority(expected_commit: str, *, live: bool) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise CleanupStop("expected_package_commit_invalid")
    if _git("rev-parse", "HEAD") != expected_commit:
        raise CleanupStop("local_head_mismatch")
    if _git("status", "--porcelain", "--untracked-files=no"):
        raise CleanupStop("tracked_worktree_dirty")
    if _git("hash-object", str(TARGET_MANIFEST)) != TARGET_MANIFEST_BLOB:
        raise CleanupStop("target_manifest_blob_drift")

    target = _read_json(TARGET_MANIFEST, "target_manifest_invalid")
    if (
        target.get("schema") != "gh.n3w-t1-core-updater-target/2"
        or target.get("component") != "homeassistant"
        or target.get("target_image_ref") != TARGET_IMAGE_REF
        or target.get("expected_predecessor_image_ref") != RUNNING_HA_REF
        or target.get("target_archive_sha256") != TARGET_ARCHIVE_SHA256
        or target.get("artifact_identity", {}).get("artifact_id") != TARGET_ARTIFACT_ID
    ):
        raise CleanupStop("target_manifest_authority_drift")

    auth = _read_json(AUTHORIZATION_MANIFEST, "authorization_manifest_invalid")
    delete = auth.get("delete") or {}
    if (
        auth.get("schema") != "gh.n3w-t1-kf147-ha-image-cleanup-executor/1"
        or auth.get("gate_id") != AUTHORIZATION_ID
        or auth.get("authorization_id") != AUTHORIZATION_ID
        or auth.get("target", {}).get("image_ref") != TARGET_IMAGE_REF
        or auth.get("target", {}).get("image_id") != TARGET_IMAGE_ID
        or auth.get("target", {}).get("archive_sha256") != TARGET_ARCHIVE_SHA256
        or auth.get("target", {}).get("artifact_id") != TARGET_ARTIFACT_ID
        or auth.get("running_predecessor", {}).get("image_ref") != RUNNING_HA_REF
        or auth.get("running_predecessor", {}).get("image_id") != RUNNING_HA_ID
        or auth.get("u1_transaction_sha256") != EXPECTED_U1_TRANSACTION_SHA256
        or delete != {
            "exact_image_id_only": True,
            "force_allowed": False,
            "prune_allowed": False,
            "wildcard_allowed": False,
            "manager_predecessor_in_scope": False,
            "historical_var_tmp_packages_in_scope": False,
            "volume_cleanup_in_scope": False,
        }
    ):
        raise CleanupStop("authorization_manifest_scope_drift")
    if auth.get("live_execution_authorized") is not live:
        raise CleanupStop("live_execution_authorization_missing" if live else "preexecution_manifest_must_be_unauthorized")

    policy = _read_json(POLICY_PATH, "storage_policy_invalid")
    cleanup = policy.get("cleanup") or {}
    if (
        policy.get("broad_docker_prune_allowed") is not False
        or cleanup.get("exact_image_id_only") is not True
        or cleanup.get("require_no_container_reference") is not True
        or cleanup.get("require_target_and_peer_health_before_and_after") is not True
        or cleanup.get("retain_transaction_metadata") is not True
        or cleanup.get("wildcard_delete_allowed") is not False
        or cleanup.get("delete_by_age_allowed") is not False
        or cleanup.get("docker_system_prune_allowed") is not False
        or cleanup.get("docker_image_prune_all_allowed") is not False
    ):
        raise CleanupStop("storage_cleanup_policy_drift")
    return {
        "package_commit": expected_commit,
        "authorization_id": AUTHORIZATION_ID,
        "live_execution_authorized": live,
        "target_manifest_blob": TARGET_MANIFEST_BLOB,
        "target_archive_sha256": TARGET_ARCHIVE_SHA256,
        "target_artifact_id": TARGET_ARTIFACT_ID,
    }


def _root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise CleanupStop("evidence_root_invalid")
    else:
        root.mkdir(parents=True, mode=0o700)
    os.chmod(root, 0o700)
    metadata = root.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise CleanupStop("evidence_root_metadata_invalid")
    return root


def _write(path: Path, value: Any) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)


def _json(payload: str, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise CleanupStop(reason) from error
    if not isinstance(value, dict):
        raise CleanupStop(reason)
    return value


def _stable_runtime(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "units": report.get("units"),
        "containers": report.get("containers"),
        "transaction": report.get("transaction"),
        "prepare": report.get("prepare"),
    }


def capture(transport: SSHTransport, *, target_present: bool) -> dict[str, Any]:
    runtime = _json(
        transport.run_remote(["sudo", "-n", "python3", "-c", MUTABLE_RUNTIME_PROBE], timeout=300).stdout,
        "runtime_probe_invalid",
    )
    live = validate_live_baseline(runtime)
    if live.get("transaction_sha256") != EXPECTED_U1_TRANSACTION_SHA256:
        raise CleanupStop("u1_transaction_sha256_drift")
    target = _json(
        transport.run_remote(
            ["sudo", "-n", "python3", "-c", TARGET_PROBE, "present" if target_present else "absent"],
            timeout=300,
        ).stdout,
        "target_probe_invalid",
    )
    if target.get("target_container_references") != []:
        raise CleanupStop("target_container_reference_present")
    image = target.get("target")
    if not isinstance(image, dict):
        raise CleanupStop("target_probe_shape_invalid")
    if target_present:
        if image.get("present") is not True or image.get("id") != TARGET_IMAGE_ID or set(image.get("repo_tags") or []) != {TARGET_IMAGE_REF}:
            raise CleanupStop("target_image_authority_drift")
    elif image != {"present": False}:
        raise CleanupStop("target_image_still_present")
    return {"runtime": runtime, "live": live, "target": target}


def validate_pair(before: dict[str, Any], after: dict[str, Any], *, target_present: bool) -> dict[str, Any]:
    if _stable_runtime(before["runtime"]) != _stable_runtime(after["runtime"]):
        raise CleanupStop("runtime_or_u1_changed")
    if target_present and before["target"]["target"] != after["target"]["target"]:
        raise CleanupStop("target_authority_changed")
    return {
        "exact_target_ref": TARGET_IMAGE_REF,
        "exact_target_id": TARGET_IMAGE_ID,
        "target_container_reference_count": 0,
        "running_predecessor_exact": True,
        "three_service_runtime_stable": True,
        "u1_transaction_unchanged": True,
        "confirmation_unconsumed": True,
    }


def run_preclaim(args: argparse.Namespace) -> dict[str, Any]:
    authority = verify_repository_authority(args.expected_package_commit, live=False)
    root = _root(args.evidence_root)
    closure: dict[str, Any] = {
        "schema": PRECLAIM_SCHEMA,
        "status": "STOP",
        "execution_id": args.execution_id,
        "authorization": AUTHORIZATION_ID,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "live_runtime_mutation": False,
        "board_access": False,
    }
    transport = SSHTransport(target=args.t1_ssh_target, known_hosts=args.known_hosts.expanduser(), expected_host_key_sha256=args.expected_host_key_sha256)
    try:
        _write(root / "repository-authority.json", authority)
        transport.start_epoch()
        before = capture(transport, target_present=True)
        after = capture(transport, target_present=True)
        _write(root / "preclaim-before.json", before)
        _write(root / "preclaim-after.json", after)
        closure.update({"status": "PASS", **validate_pair(before, after, target_present=True)})
        return closure
    finally:
        try:
            transport.close_epoch()
        finally:
            _write(root / "closure.json", closure)


def run_execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.authorization_id != AUTHORIZATION_ID or args.confirm != CONFIRMATION:
        raise CleanupStop("authorization_or_confirmation_invalid")
    authority = verify_repository_authority(args.expected_package_commit, live=True)
    root = _root(args.evidence_root)
    closure: dict[str, Any] = {
        "schema": EXECUTION_SCHEMA,
        "status": "STOP",
        "execution_id": args.execution_id,
        "authorization": AUTHORIZATION_ID,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "live_runtime_mutation": False,
        "exact_target_delete_invoked": False,
        "board_access": False,
    }
    transport = SSHTransport(target=args.t1_ssh_target, known_hosts=args.known_hosts.expanduser(), expected_host_key_sha256=args.expected_host_key_sha256)
    try:
        _write(root / "repository-authority.json", authority)
        transport.start_epoch()
        before = capture(transport, target_present=True)
        _write(root / "predelete.json", before)
        closure["authorization_claimed"] = True
        closure["authorization_consumed"] = True
        _write(root / "authorization-claim.json", {
            "authorization": AUTHORIZATION_ID,
            "authorization_claimed": True,
            "authorization_consumed": True,
            "execution_id": args.execution_id,
            "target_ref": TARGET_IMAGE_REF,
            "target_id": TARGET_IMAGE_ID,
        })
        closure["exact_target_delete_invoked"] = True
        closure["live_runtime_mutation"] = True
        try:
            removed = transport.run_remote(["sudo", "-n", "docker", "image", "rm", TARGET_IMAGE_ID], timeout=600, check=False)
            if removed.returncode != 0:
                closure["reason"] = "exact_target_delete_failed_after_claim"
                return closure
            after = capture(transport, target_present=False)
            _write(root / "postdelete.json", after)
            validate_pair(before, after, target_present=False)
            closure.update({
                "status": "PASS",
                "exact_target_deleted": True,
                "target_ref": TARGET_IMAGE_REF,
                "target_id": TARGET_IMAGE_ID,
                "next_action": "FRESH_CAPACITY_PREFLIGHT_ONLY",
            })
            return closure
        except Exception as error:
            reason = str(error)
            if not reason or len(reason) > 180 or "/" in reason or "\\" in reason or "@" in reason:
                reason = type(error).__name__
            closure["reason"] = reason
            return closure
    finally:
        try:
            transport.close_epoch()
        finally:
            _write(root / "closure.json", closure)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="n3w-t1-kf147-exact-ha-cleanup")
    mode = command.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preclaim", action="store_true")
    mode.add_argument("--execute", action="store_true")
    command.add_argument("--expected-package-commit", required=True)
    command.add_argument("--execution-id", required=True)
    command.add_argument("--t1-ssh-target", required=True)
    command.add_argument("--known-hosts", type=Path, required=True)
    command.add_argument("--expected-host-key-sha256", required=True)
    command.add_argument("--evidence-root", type=Path, required=True)
    command.add_argument("--authorization-id", default="")
    command.add_argument("--confirm", default="")
    return command


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run_preclaim(args) if args.preclaim else run_execute(args)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("status") == "PASS" else 2
    except Exception as error:
        reason = str(error)
        if not reason or len(reason) > 200 or "/" in reason or "\\" in reason or "@" in reason:
            reason = type(error).__name__
        print(json.dumps({
            "status": "STOP",
            "reason": reason,
            "authorization": AUTHORIZATION_ID,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "live_runtime_mutation": False,
            "board_access": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
