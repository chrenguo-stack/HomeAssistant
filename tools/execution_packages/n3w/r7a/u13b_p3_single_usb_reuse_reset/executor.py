from __future__ import annotations

import argparse
import base64
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
SSH_TRANSPORT_SOURCE = ROOT / "tools" / "n3w_t1_ssh_transport.py"

GATE_ID = "N3W_T1_U13B_P3_SINGLE_USB_REUSE_RESET_20261118_01"
MANIFEST_SCHEMA = "gh.n3w-t1-u13b-p3-single-usb-reuse-reset-manifest/1"
RESULT_SCHEMA = "gh.n3w-t1-u13b-p3-single-usb-reuse-reset/1"


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
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stop("module_load_failed:" + path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_manifest(expected_commit: str, *, require_authorized: bool) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        value.get("schema") != MANIFEST_SCHEMA
        or value.get("gate_id") != GATE_ID
        or value.get("destructive_usb_reset_authorized") is not require_authorized
        or value.get("transaction_mutation_authorized") is not False
        or value.get("service_mutation_authorized") is not False
        or value.get("image_mutation_authorized") is not False
        or value.get("ha_data_mutation_authorized") is not False
        or value.get("p3_live_execution_authorized") is not False
    ):
        raise Stop("manifest_gate_invalid")
    for relative, blob in value["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return value


def prepare_evidence_root(path: Path) -> Path:
    path = path.expanduser()
    if path.exists() or path.is_symlink():
        raise Stop("evidence_root_exists")
    path.mkdir(parents=True, mode=0o700)
    os.chmod(path, 0o700)
    meta = path.stat()
    if meta.st_uid != os.geteuid() or stat.S_IMODE(meta.st_mode) != 0o700:
        raise Stop("evidence_root_metadata_invalid")
    return path


def write_private_json(path: Path, value: Any) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)


REMOTE_SCRIPT = r"""
import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

TOOLS = Path("/opt/HomeAssistant/tools")
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
from n3w_t1_core_updater_ha_usb_media import classify_candidate
from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

STATE_ROOT = Path("/var/lib/n3w-t1-core-updater")
HA_CONTAINER = "n3wfc4-homeassistant-1"


def run(argv, *, timeout=30, check=True):
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode:
        raise RuntimeError(
            "command_failed:" + os.path.basename(argv[0]) + ":" + str(completed.returncode)
        )
    return completed


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def docker_inspect(name):
    completed = run(["docker", "inspect", "--type", "container", name])
    value = json.loads(completed.stdout)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise RuntimeError("docker_inspect_invalid:" + name)
    return value[0]


def partition_info(locator):
    completed = run(
        [
            "lsblk",
            "--json",
            "--paths",
            "--tree",
            "--output",
            "PATH,TYPE,UUID,MOUNTPOINTS,PKNAME",
            locator,
        ]
    )
    document = json.loads(completed.stdout)
    roots = document.get("blockdevices")
    if not isinstance(roots, list):
        raise RuntimeError("single_usb_partition_inventory_invalid")
    nodes = []
    stack = [item for item in roots if isinstance(item, dict)]
    while stack:
        item = stack.pop()
        nodes.append(item)
        children = item.get("children")
        if isinstance(children, list):
            stack.extend(child for child in children if isinstance(child, dict))
    parts = [
        item
        for item in nodes
        if item.get("type") == "part" and isinstance(item.get("path"), str)
    ]
    if len(parts) != 1:
        raise RuntimeError("single_usb_partition_shape_invalid:" + str(len(parts)))
    return parts[0]


def uuid_for(path):
    completed = run(["blkid", "-s", "UUID", "-o", "value", path], check=False)
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip().lower()
    return value or None


def mount_target_for(path):
    completed = run(
        ["findmnt", "--noheadings", "--output", "TARGET", "--source", path],
        check=False,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def main():
    plan = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
    expected = plan["expected_terminal_u13a"]
    media = plan["expected_historical_media"]

    store = HaUsbStateStore(STATE_ROOT)
    transaction = store.read()
    if transaction is None:
        raise RuntimeError("single_usb_transaction_missing")
    if (
        transaction.get("phase") != "U13A_COMMITTED"
        or transaction.get("status") != "COMMITTED"
        or transaction.get("recovery_required") is not False
        or transaction.get("transaction_id_sha256") != expected["transaction_id_sha256"]
        or transaction.get("usb_filesystem_uuid") != expected["filesystem_uuid"]
        or sha_file(store.path) != expected["transaction_sha256"]
    ):
        raise RuntimeError("single_usb_terminal_u13a_drift")

    ha = docker_inspect(HA_CONTAINER)
    config = ha.get("Config")
    state = ha.get("State")
    if (
        not isinstance(config, dict)
        or config.get("Image") != expected["target_image"]
        or ha.get("Image") != expected["target_runtime_image_id"]
        or not isinstance(state, dict)
        or state.get("Status") != "running"
    ):
        raise RuntimeError("single_usb_homeassistant_runtime_drift")

    backend = SubprocessPrepareBackend()
    candidates = backend.inventory()
    if len(candidates) != 1:
        raise RuntimeError("single_usb_candidate_count_invalid:" + str(len(candidates)))
    candidate = candidates[0]
    if (
        candidate.public_fingerprint != media["public_fingerprint"]
        or candidate.display_model.strip() != media["display_model"]
        or candidate.display_capacity_bytes != media["display_capacity_bytes"]
        or candidate.removable is not True
        or candidate.mass_storage is not True
        or candidate.read_only is True
        or candidate.is_root_device is True
    ):
        raise RuntimeError("single_usb_candidate_identity_drift")

    reasons = classify_candidate(candidate.as_media_candidate())
    if tuple(reasons) != ("production_mount",):
        raise RuntimeError("single_usb_pre_reset_eligibility_drift:" + ",".join(reasons))

    partition = partition_info(candidate.locator)
    partition_path = partition["path"]
    observed_uuid = uuid_for(partition_path)
    if observed_uuid != expected["filesystem_uuid"].lower():
        raise RuntimeError("single_usb_historical_uuid_drift")
    mount_target = mount_target_for(partition_path)
    if mount_target != media["mount_target"]:
        raise RuntimeError("single_usb_historical_mount_drift")

    run(["umount", media["mount_target"]])
    if mount_target_for(partition_path) is not None:
        raise RuntimeError("single_usb_unmount_failed")

    after_unmount = SubprocessPrepareBackend().inventory()
    if len(after_unmount) != 1:
        raise RuntimeError("single_usb_post_unmount_candidate_count_invalid")
    candidate2 = after_unmount[0]
    if candidate2.public_fingerprint != media["public_fingerprint"]:
        raise RuntimeError("single_usb_post_unmount_identity_drift")
    if classify_candidate(candidate2.as_media_candidate()):
        raise RuntimeError("single_usb_post_unmount_not_eligible")

    if uuid_for(partition_path) != expected["filesystem_uuid"].lower():
        raise RuntimeError("single_usb_uuid_changed_before_reset")

    run(["wipefs", "--all", "--force", partition_path])
    run(["udevadm", "settle"])
    if uuid_for(partition_path) is not None:
        raise RuntimeError("single_usb_historical_uuid_still_present")
    if mount_target_for(partition_path) is not None:
        raise RuntimeError("single_usb_post_reset_mounted")

    final_candidates = SubprocessPrepareBackend().inventory()
    if len(final_candidates) != 1:
        raise RuntimeError("single_usb_post_reset_candidate_count_invalid")
    final = final_candidates[0]
    if (
        final.public_fingerprint != media["public_fingerprint"]
        or classify_candidate(final.as_media_candidate())
    ):
        raise RuntimeError("single_usb_post_reset_candidate_not_ready")

    result = {
        "schema": "gh.n3w-t1-u13b-p3-single-usb-reuse-reset-remote/1",
        "status": "P3_SINGLE_USB_REUSE_RESET_PASS",
        "t1_access": True,
        "destructive_usb_reset": True,
        "historical_filesystem_uuid_removed": True,
        "historical_filesystem_uuid": expected["filesystem_uuid"],
        "candidate_public_fingerprint": final.public_fingerprint,
        "candidate_locator": final.locator,
        "candidate_display_model": final.display_model.strip(),
        "candidate_display_capacity_bytes": final.display_capacity_bytes,
        "transaction_mutation": False,
        "usb_mutation": True,
        "service_mutation": False,
        "image_mutation": False,
        "ha_data_mutation": False,
        "authorization_claim": False,
        "p3_live_execution": False,
        "board_access": False,
        "merge": False,
    }
    print(json.dumps(result, sort_keys=True))


try:
    main()
except Exception as error:
    print(
        json.dumps(
            {
                "schema": "gh.n3w-t1-u13b-p3-single-usb-reuse-reset-remote/1",
                "status": "STOP",
                "reason": type(error).__name__ + ":" + str(error)[:300],
                "t1_access": True,
                "destructive_usb_reset": False,
                "transaction_mutation": False,
                "usb_mutation": False,
                "service_mutation": False,
                "image_mutation": False,
                "ha_data_mutation": False,
                "authorization_claim": False,
                "p3_live_execution": False,
                "board_access": False,
                "merge": False,
            },
            sort_keys=True,
        )
    )
    raise SystemExit(2)
"""


def remote_reset(
    *,
    manifest: dict[str, Any],
    t1_ssh_target: str,
    known_hosts: Path,
    expected_host_key_sha256: str,
    access_state: dict[str, Any],
) -> dict[str, Any]:
    transport_type = load_module(
        SSH_TRANSPORT_SOURCE,
        "n3w_u13b_p3_single_usb_reuse_transport",
    ).SSHTransport
    transport = transport_type(
        target=t1_ssh_target,
        known_hosts=known_hosts.expanduser(),
        expected_host_key_sha256=expected_host_key_sha256,
    )
    payload = base64.b64encode(
        json.dumps(
            {
                "expected_terminal_u13a": manifest["expected_terminal_u13a"],
                "expected_historical_media": manifest["expected_historical_media"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    completed = None
    remote_error = None
    transport.start_epoch()
    access_state["t1_access"] = True
    try:
        completed = transport.run_remote(
            ["python3", "-B", "-c", REMOTE_SCRIPT, payload],
            timeout=180,
            check=False,
        )
    except Exception as error:
        remote_error = error
    try:
        transport.close_epoch()
    except Exception as cleanup_error:
        if remote_error is None:
            raise Stop(
                "ssh_master_cleanup_failed:"
                + type(cleanup_error).__name__
                + ":"
                + str(cleanup_error)[:160]
            ) from cleanup_error
    if remote_error is not None:
        raise remote_error
    if completed is None:
        raise Stop("remote_result_missing")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise Stop("remote_stdout_empty")
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise Stop("remote_result_invalid") from error
    if completed.returncode != 0 or value.get("status") != "P3_SINGLE_USB_REUSE_RESET_PASS":
        raise Stop("remote_reset_failed:" + str(value.get("reason", "unknown"))[:220])
    return value


def source_check(manifest: dict[str, Any]) -> dict[str, Any]:
    media = manifest["expected_historical_media"]
    if media["filesystem_uuid"] != manifest["expected_terminal_u13a"]["filesystem_uuid"]:
        raise Stop("historical_media_uuid_binding_drift")
    return {
        "schema": RESULT_SCHEMA,
        "gate_id": GATE_ID,
        "status": "P3_SINGLE_USB_REUSE_RESET_SOURCE_READY",
        "destructive_usb_reset_authorized": True,
        "historical_media_public_fingerprint": media["public_fingerprint"],
        "historical_media_filesystem_uuid": media["filesystem_uuid"],
        "transaction_mutation_authorized": False,
        "service_mutation_authorized": False,
        "image_mutation_authorized": False,
        "ha_data_mutation_authorized": False,
        "p3_live_execution_authorized": False,
        "merge": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument(
        "--mode",
        choices=("source-check", "execute-reset"),
        default="source-check",
    )
    parser.add_argument("--execution-id")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "gate_id": GATE_ID,
        "status": "STOP",
        "t1_access": False,
        "destructive_usb_reset": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "ha_data_mutation": False,
        "authorization_claim": False,
        "p3_live_execution": False,
        "board_access": False,
        "merge": False,
    }
    try:
        execute = args.mode == "execute-reset"
        manifest = read_manifest(
            args.expected_package_commit,
            require_authorized=True if execute else True,
        )
        if not execute:
            result.update(source_check(manifest))
            print(json.dumps(result, sort_keys=True))
            return 0
        if not all(
            (
                args.execution_id,
                args.evidence_root,
                args.t1_ssh_target,
                args.known_hosts,
                args.expected_host_key_sha256,
            )
        ):
            raise Stop("execute_reset_arguments_missing")
        evidence = prepare_evidence_root(args.evidence_root)
        value = remote_reset(
            manifest=manifest,
            t1_ssh_target=args.t1_ssh_target,
            known_hosts=args.known_hosts,
            expected_host_key_sha256=args.expected_host_key_sha256,
            access_state=result,
        )
        result.update(value)
        write_private_json(evidence / "single_usb_reuse_reset_result.json", result)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:300]
        print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
