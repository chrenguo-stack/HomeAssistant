from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
P1_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_real_t1_readonly_binding_preflight" / "executor.py"
)
SSH_TRANSPORT_SOURCE = ROOT / "tools" / "n3w_t1_ssh_transport.py"

GATE_ID = "N3W_T1_U13B_P3_FRESH_REAL_T1_READONLY_PREFLIGHT_20261117_01"
MANIFEST_SCHEMA = "gh.n3w-t1-u13b-p3-fresh-readonly-preflight-manifest/1"
RESULT_SCHEMA = "gh.n3w-t1-u13b-p3-fresh-readonly-preflight/1"


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


def read_manifest(
    expected_commit: str,
    *,
    require_authorized: bool | None,
) -> dict[str, Any]:
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
        or (
            require_authorized is not None
            and document.get("real_t1_readonly_execution_authorized")
            is not require_authorized
        )
        or document.get("new_clean_ota_mutation_authorized") is not False
        or document.get("u13b_live_execution_authorized") is not False
        or document.get("controlled_rollback_mutation_authorized") is not False
    ):
        raise Stop("manifest_gate_invalid")
    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


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
    if path.exists() or path.is_symlink():
        raise Stop("evidence_path_exists:" + path.name)
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
import stat
import subprocess
import sys
from pathlib import Path

TOOLS = Path("/opt/HomeAssistant/tools")
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
from n3w_t1_core_updater_ha_usb_media import classify_candidate
from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
from n3w_t1_core_updater_v2_common import TERMINAL_TX_V2
from n3w_t1_core_updater_v2_state import V2StateStore

STATE_ROOT = Path("/var/lib/n3w-t1-core-updater")
HA_CONTAINER = "n3wfc4-homeassistant-1"


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def docker_inspect(name):
    completed = subprocess.run(
        ["docker", "inspect", "--type", "container", name],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError("docker_inspect_failed:" + name)
    value = json.loads(completed.stdout)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise RuntimeError("docker_inspect_invalid:" + name)
    return value[0]


def filesystem_uuids_for_candidate(locator):
    completed = subprocess.run(
        [
            "lsblk",
            "--json",
            "--paths",
            "--tree",
            "--output",
            "PATH,TYPE,UUID",
            locator,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError("p3_preflight_usb_uuid_inventory_failed:" + locator)
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("p3_preflight_usb_uuid_inventory_invalid:" + locator) from error
    roots = document.get("blockdevices")
    if not isinstance(roots, list):
        raise RuntimeError("p3_preflight_usb_uuid_inventory_invalid:" + locator)

    observed = set()
    stack = [item for item in roots if isinstance(item, dict)]
    while stack:
        item = stack.pop()
        value = item.get("uuid")
        if isinstance(value, str) and value.strip():
            observed.add(value.strip().lower())
        children = item.get("children")
        if isinstance(children, list):
            stack.extend(child for child in children if isinstance(child, dict))
    return observed


def main():
    plan = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
    reuse = plan.get("single_usb_reuse_after_reset") or {}
    ha_store = HaUsbStateStore(STATE_ROOT)
    transaction = ha_store.read()
    if transaction is None:
        raise RuntimeError("p3_preflight_transaction_missing")
    expected = plan["expected_terminal_u13a"]
    tx_path = ha_store.path
    if (
        transaction.get("phase") != "U13A_COMMITTED"
        or transaction.get("status") != "COMMITTED"
        or transaction.get("recovery_required") is not False
        or transaction.get("transaction_id_sha256") != expected["transaction_id_sha256"]
        or transaction.get("usb_filesystem_uuid") != expected["filesystem_uuid"]
        or sha_file(tx_path) != expected["transaction_sha256"]
    ):
        raise RuntimeError("p3_preflight_terminal_u13a_drift")

    generic_store = V2StateStore(STATE_ROOT)
    generic = generic_store.read()
    legacy = generic_store.read_legacy()
    if generic is not None and generic.get("status") not in TERMINAL_TX_V2:
        raise RuntimeError("p3_preflight_generic_transaction_active")
    if legacy is not None and legacy.get("status") not in {"COMMITTED", "ROLLED_BACK"}:
        raise RuntimeError("p3_preflight_legacy_transaction_active")

    history = ha_store.history
    history_ok = True
    history_count = 0
    if history.exists() or history.is_symlink():
        if history.is_symlink() or not history.is_dir():
            raise RuntimeError("p3_preflight_history_invalid")
        meta = history.stat()
        if meta.st_uid != os.geteuid() or stat.S_IMODE(meta.st_mode) & 0o077:
            raise RuntimeError("p3_preflight_history_metadata_invalid")
        history_count = sum(1 for item in history.iterdir() if item.is_file())

    ha = docker_inspect(HA_CONTAINER)
    config = ha.get("Config")
    current_ref = config.get("Image") if isinstance(config, dict) else None
    runtime_id = ha.get("Image")
    state = ha.get("State")
    if (
        current_ref != expected["target_image"]
        or runtime_id != expected["target_runtime_image_id"]
        or not isinstance(state, dict)
        or state.get("Status") != "running"
    ):
        raise RuntimeError("p3_preflight_homeassistant_runtime_drift")

    old_fingerprint = transaction.get("usb_device_identity_public_fingerprint")
    if (
        not isinstance(old_fingerprint, str)
        or len(old_fingerprint) != 64
        or any(ch not in "0123456789abcdef" for ch in old_fingerprint)
    ):
        raise RuntimeError("p3_preflight_historical_usb_fingerprint_invalid")

    old_filesystem_uuid = expected["filesystem_uuid"].lower()
    reuse_authorized = reuse.get("authorized") is True
    expected_reuse_fingerprint = reuse.get("expected_public_fingerprint")
    backend = SubprocessPrepareBackend()
    fresh = []
    for candidate in backend.inventory():
        reasons = classify_candidate(candidate.as_media_candidate())
        observed_filesystem_uuids = filesystem_uuids_for_candidate(
            candidate.locator
        )
        if reuse_authorized:
            eligible_identity = (
                candidate.public_fingerprint == expected_reuse_fingerprint
                and old_filesystem_uuid not in observed_filesystem_uuids
            )
        else:
            eligible_identity = (
                candidate.public_fingerprint != old_fingerprint
                and old_filesystem_uuid not in observed_filesystem_uuids
            )
        if not reasons and eligible_identity:
            fresh.append(candidate.public())

    if len(fresh) != 1:
        raise RuntimeError(
            "p3_preflight_fresh_usb_candidate_count_invalid:" + str(len(fresh))
        )

    result = {
        "schema": "gh.n3w-t1-u13b-p3-fresh-readonly-remote/1",
        "status": "P3_FRESH_REAL_T1_READONLY_PREFLIGHT_PASS",
        "read_only": True,
        "prepare_new_admissible": True,
        "historical_transaction_phase": transaction["phase"],
        "historical_transaction_status": transaction["status"],
        "historical_transaction_sha256": expected["transaction_sha256"],
        "historical_transaction_id_sha256": transaction["transaction_id_sha256"],
        "historical_usb_filesystem_uuid": transaction["usb_filesystem_uuid"],
        "historical_usb_public_fingerprint": old_fingerprint,
        "generic_transaction_status": None if generic is None else generic.get("status"),
        "legacy_transaction_status": None if legacy is None else legacy.get("status"),
        "history_private": history_ok,
        "history_file_count": history_count,
        "current_homeassistant_image": current_ref,
        "current_homeassistant_runtime_image_id": runtime_id,
        "fresh_usb_candidate_count": 1,
        "fresh_usb_candidate": fresh[0],
        "old_usb_reuse_forbidden": not reuse_authorized,
        "single_usb_reuse_after_reset": reuse_authorized,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "ha_data_mutation": False,
        "authorization_claim": False,
        "u13_transition": False,
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
                "schema": "gh.n3w-t1-u13b-p3-fresh-readonly-remote/1",
                "status": "STOP",
                "reason": type(error).__name__ + ":" + str(error)[:300],
                "read_only": True,
                "transaction_mutation": False,
                "usb_mutation": False,
                "service_mutation": False,
                "image_mutation": False,
                "ha_data_mutation": False,
                "authorization_claim": False,
                "u13_transition": False,
                "board_access": False,
                "merge": False,
            },
            sort_keys=True,
        )
    )
    raise SystemExit(2)
"""


def remote_probe(
    *,
    manifest: dict[str, Any],
    t1_ssh_target: str,
    known_hosts: Path,
    expected_host_key_sha256: str,
    access_state: dict[str, Any],
) -> dict[str, Any]:
    transport_type = load_module(
        SSH_TRANSPORT_SOURCE,
        "n3w_u13b_p3_readonly_transport",
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
                "single_usb_reuse_after_reset": manifest.get(
                    "single_usb_reuse_after_reset"
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    remote_error = None
    completed = None
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
    if completed.returncode != 0 or value.get("status") != "P3_FRESH_REAL_T1_READONLY_PREFLIGHT_PASS":
        raise Stop("remote_preflight_failed:" + str(value.get("reason", "unknown"))[:220])
    return value


def run_readonly(
    *,
    manifest: dict[str, Any],
    execution_id: str,
    evidence_root: Path,
    t1_ssh_target: str,
    known_hosts: Path,
    expected_host_key_sha256: str,
    access_state: dict[str, Any],
) -> dict[str, Any]:
    reuse = manifest.get("single_usb_reuse_after_reset") or {}
    reuse_authorized = reuse.get("authorized") is True
    if reuse_authorized:
        binding = {
            "status": "POST_RESET_HOST_TERMINAL_REVALIDATION",
            "fresh_binding": True,
            "historical_transaction_sha256": manifest[
                "expected_terminal_u13a"
            ]["transaction_sha256"],
        }
    else:
        p1 = load_module(P1_EXECUTOR, "n3w_u13b_p3_p1_binding")
        _, binding = p1.run_status_only(
            execution_id=execution_id + "-terminal-binding",
            evidence_root=evidence_root,
            t1_ssh_target=t1_ssh_target,
            known_hosts=known_hosts,
            expected_host_key_sha256=expected_host_key_sha256,
            expected_terminal=manifest["expected_terminal_u13a"],
            access_state=access_state,
        )
    probe = remote_probe(
        manifest=manifest,
        t1_ssh_target=t1_ssh_target,
        known_hosts=known_hosts,
        expected_host_key_sha256=expected_host_key_sha256,
        access_state=access_state,
    )
    if (
        binding.get("status") != "U13B_REAL_T1_READONLY_BINDING_PASS"
        or binding.get("fresh_binding") is not True
        or probe.get("prepare_new_admissible") is not True
        or probe.get("fresh_usb_candidate_count") != 1
        or (
            reuse_authorized
            and probe.get("single_usb_reuse_after_reset") is not True
        )
        or (
            not reuse_authorized
            and probe.get("old_usb_reuse_forbidden") is not True
        )
    ):
        raise Stop("p3_fresh_readonly_composite_drift")
    result = {
        "schema": RESULT_SCHEMA,
        "gate_id": GATE_ID,
        "status": "P3_FRESH_REAL_T1_READONLY_PREFLIGHT_PASS",
        "t1_access": True,
        "read_only": True,
        "fresh_terminal_binding": True,
        "prepare_new_admissible": True,
        "fresh_usb_candidate_count": 1,
        "fresh_usb_candidate": probe["fresh_usb_candidate"],
        "historical_usb_public_fingerprint": probe[
            "historical_usb_public_fingerprint"
        ],
        "single_usb_reuse_after_reset": probe.get(
            "single_usb_reuse_after_reset", False
        ),
        "historical_transaction_sha256": binding[
            "historical_transaction_sha256"
        ],
        "historical_transaction_id_sha256": probe[
            "historical_transaction_id_sha256"
        ],
        "historical_usb_filesystem_uuid": probe[
            "historical_usb_filesystem_uuid"
        ],
        "current_homeassistant_image": probe["current_homeassistant_image"],
        "current_homeassistant_runtime_image_id": probe[
            "current_homeassistant_runtime_image_id"
        ],
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "ha_data_mutation": False,
        "authorization_claim": False,
        "u13_transition": False,
        "new_clean_ota_mutation_authorized": False,
        "u13b_live_execution_authorized": False,
        "controlled_rollback_mutation_authorized": False,
        "board_access": False,
        "merge": False,
    }
    write_private_json(evidence_root / "p3_fresh_readonly_result.json", result)
    return result


def source_check(manifest: dict[str, Any]) -> dict[str, Any]:
    target = manifest["acceptance_target"]
    reuse = manifest.get("single_usb_reuse_after_reset")
    if (
        not isinstance(reuse, dict)
        or reuse.get("authorized") is not True
        or reuse.get("reset_gate_id")
        != "N3W_T1_U13B_P3_SINGLE_USB_REUSE_RESET_20261118_01"
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(reuse.get("expected_public_fingerprint", "")),
        ) is None
        or reuse.get("historical_filesystem_uuid")
        != manifest["expected_terminal_u13a"]["filesystem_uuid"]
        or reuse.get("require_historical_uuid_absent") is not True
    ):
        raise Stop("single_usb_reuse_contract_invalid")
    if target["target_image_ref"] == target["expected_predecessor_image_ref"]:
        raise Stop("target_not_distinct")
    return {
        "schema": RESULT_SCHEMA,
        "gate_id": GATE_ID,
        "status": "P3_FRESH_READONLY_PREFLIGHT_SOURCE_READY",
        "read_only": True,
        "real_t1_readonly_execution_authorized": manifest[
            "real_t1_readonly_execution_authorized"
        ],
        "target_image_ref": target["target_image_ref"],
        "expected_predecessor_image_ref": target[
            "expected_predecessor_image_ref"
        ],
        "old_usb_reuse_forbidden": not bool(
            manifest.get("single_usb_reuse_after_reset", {}).get("authorized")
        ),
        "single_usb_reuse_after_reset": bool(
            manifest.get("single_usb_reuse_after_reset", {}).get("authorized")
        ),
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "ha_data_mutation": False,
        "authorization_claim": False,
        "board_access": False,
        "merge": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument(
        "--mode",
        choices=("source-check", "execute-readonly"),
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
        "read_only": True,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "ha_data_mutation": False,
        "authorization_claim": False,
        "board_access": False,
        "merge": False,
    }
    try:
        execute = args.mode == "execute-readonly"
        manifest = read_manifest(
            args.expected_package_commit,
            require_authorized=True if execute else None,
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
            raise Stop("execute_readonly_arguments_missing")
        evidence = prepare_evidence_root(args.evidence_root)
        result.update(
            run_readonly(
                manifest=manifest,
                execution_id=args.execution_id,
                evidence_root=evidence,
                t1_ssh_target=args.t1_ssh_target,
                known_hosts=args.known_hosts,
                expected_host_key_sha256=args.expected_host_key_sha256,
                access_state=result,
            )
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:300]
        print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
