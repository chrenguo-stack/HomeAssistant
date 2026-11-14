#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SSH_TRANSPORT_PATH = ROOT / "tools" / "n3w_t1_ssh_transport.py"

GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U7_POST_REBOOT_TRANSACTION_DIAGNOSTIC_R27D_20261114_01"
)

EXPECTED_TRANSACTION_SHA256 = (
    "7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe"
)
EXPECTED_TRANSACTION_ID_SHA256 = (
    "ca89774eb4254d0f861cc2aef136eee41e90fd6106559c0fd8d66e3ee00a3738"
)
EXPECTED_PHASE = "U6_PREDECESSOR_RECOVERY_PREPARING"
EXPECTED_STATUS = "ACTIVE"
EXPECTED_R26_GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U6_PREDECESSOR_RECOVERY_R26_20261114_01"
)

REMOTE_SCRIPT = r'''
import hashlib
import json
import stat
import time
from pathlib import Path

TX_PATH = Path(
    "/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json"
)
R26_ROOT = Path(
    "/var/lib/n3w-t1-core-updater/"
    "u6-r26-predecessor-recovery-20261114-01"
)


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def private_json(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("required_file_invalid:" + str(path))
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise RuntimeError("required_file_metadata_invalid:" + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("required_object_invalid:" + str(path))
    return value


def main(plan):
    transaction = private_json(TX_PATH)
    actual_sha = sha_file(TX_PATH)
    tx_meta = TX_PATH.stat()

    uptime = float(Path("/proc/uptime").read_text().split()[0])
    boot_started_unix = int(time.time() - uptime)

    predecessor = transaction.get("predecessor_recovery_identity")
    predecessor_sha = (
        canonical_sha(predecessor)
        if isinstance(predecessor, dict)
        else None
    )

    checks = {
        "phase_exact": (
            transaction.get("phase") == plan["expected_phase"]
        ),
        "status_exact": (
            transaction.get("status") == plan["expected_status"]
        ),
        "transaction_id_exact": (
            transaction.get("transaction_id_sha256")
            == plan["expected_transaction_id_sha256"]
        ),
        "transaction_file_sha256_exact": (
            actual_sha == plan["expected_transaction_sha256"]
        ),
        "target_artifact_verified_true": (
            transaction.get("target_artifact_verified") is True
        ),
        "predecessor_recovery_verified_true": (
            transaction.get("predecessor_recovery_verified") is True
        ),
        "ha_data_backup_verified_false": (
            transaction.get("ha_data_backup_verified") is False
        ),
        "ha_data_backup_identity_absent": (
            transaction.get("ha_data_backup_identity") is None
        ),
        "authorization_claimed_false": (
            transaction.get("authorization_claimed") is False
        ),
        "authorization_consumed_false": (
            transaction.get("authorization_consumed") is False
        ),
        "authorization_id_absent": (
            transaction.get("authorization_id_sha256") is None
        ),
        "recovery_required_false": (
            transaction.get("recovery_required") is False
        ),
        "failure_code_absent": (
            transaction.get("failure_code") is None
        ),
    }

    claim = private_json(R26_ROOT / "authorization_claim.json")
    success = private_json(R26_ROOT / "success.json")
    r26_checks = {
        "claim_gate_exact": (
            claim.get("authorization_id") == plan["expected_r26_gate_id"]
        ),
        "claim_claimed_true": claim.get("claimed") is True,
        "claim_consumed_true": claim.get("consumed") is True,
        "claim_replay_false": claim.get("replay_permitted") is False,
        "success_status_exact": (
            success.get("status")
            == "U6_R26_PREDECESSOR_RECOVERY_PASS"
        ),
        "success_claimed_true": (
            success.get("authorization_claimed") is True
        ),
        "success_consumed_true": (
            success.get("authorization_consumed") is True
        ),
        "success_replay_false": (
            success.get("replay_permitted") is False
        ),
    }

    result = {
        "schema": (
            "gh.n3w-t1-u7-r27d-transaction-readonly-diagnostic/1"
        ),
        "status": "PASS_DIAGNOSTIC",
        "read_only": True,
        "transaction_path": str(TX_PATH),
        "expected_transaction_sha256": (
            plan["expected_transaction_sha256"]
        ),
        "observed_transaction_sha256": actual_sha,
        "transaction_checks": checks,
        "transaction_all_r27_predicates_pass": all(checks.values()),
        "observed": {
            "phase": transaction.get("phase"),
            "status": transaction.get("status"),
            "transaction_id_sha256": (
                transaction.get("transaction_id_sha256")
            ),
            "target_artifact_verified": (
                transaction.get("target_artifact_verified")
            ),
            "predecessor_recovery_verified": (
                transaction.get("predecessor_recovery_verified")
            ),
            "ha_data_backup_verified": (
                transaction.get("ha_data_backup_verified")
            ),
            "ha_data_backup_identity_present": (
                transaction.get("ha_data_backup_identity") is not None
            ),
            "authorization_claimed": (
                transaction.get("authorization_claimed")
            ),
            "authorization_consumed": (
                transaction.get("authorization_consumed")
            ),
            "authorization_id_present": (
                transaction.get("authorization_id_sha256") is not None
            ),
            "recovery_required": (
                transaction.get("recovery_required")
            ),
            "failure_code": transaction.get("failure_code"),
            "created_at_unix": transaction.get("created_at_unix"),
            "updated_at_unix": transaction.get("updated_at_unix"),
            "predecessor_identity_present": isinstance(predecessor, dict),
            "predecessor_identity_canonical_sha256": predecessor_sha,
        },
        "timing": {
            "current_boot_uptime_seconds": int(uptime),
            "boot_started_unix": boot_started_unix,
            "transaction_mtime_unix": int(tx_meta.st_mtime),
            "transaction_predates_current_boot": (
                tx_meta.st_mtime < boot_started_unix
            ),
        },
        "r26_checks": r26_checks,
        "r26_all_terminal_predicates_pass": all(r26_checks.values()),
        "mutation": {
            "source_deployment": False,
            "service_stop": False,
            "service_restart": False,
            "usb_data_mutation": False,
            "transaction_mutation": False,
            "u7_transition": False,
            "u8_plus": False,
            "board_access": False,
        },
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    plan = json.loads(
        __import__("base64").b64decode(__import__("sys").argv[1])
        .decode("utf-8")
    )
    raise SystemExit(main(plan))
'''


class Stop(RuntimeError):
    pass


def git_text(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("local_git_failed")
    return completed.stdout.strip()


def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise Stop("evidence_root_invalid")
        os.chmod(root, 0o700)
    else:
        root.mkdir(parents=True, mode=0o700)
    if (
        root.stat().st_uid != os.geteuid()
        or stat.S_IMODE(root.stat().st_mode) != 0o700
    ):
        raise Stop("evidence_root_metadata_invalid")
    return root


def write_private(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def load_transport():
    spec = importlib.util.spec_from_file_location(
        "n3w_u7_r27d_transport",
        SSH_TRANSPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    parser.add_argument("--diagnostic-only", action="store_true", required=True)
    args = parser.parse_args()

    result = {
        "schema": (
            "gh.n3w-t1-u7-r27d-transaction-readonly-diagnostic-local/1"
        ),
        "status": "STOP",
        "read_only": True,
        "t1_access": False,
        "source_deployment": False,
        "service_stop": False,
        "service_restart": False,
        "usb_data_mutation": False,
        "transaction_mutation": False,
        "u7_transition": False,
        "u8_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    try:
        if git_text("rev-parse", "HEAD") != args.expected_package_commit:
            raise Stop("local_head_mismatch")
        if git_text("status", "--porcelain", "--untracked-files=no"):
            raise Stop("tracked_worktree_dirty")
        evidence = prepare_evidence_root(args.evidence_root)
        plan = {
            "gate_id": GATE_ID,
            "expected_transaction_sha256": EXPECTED_TRANSACTION_SHA256,
            "expected_transaction_id_sha256": (
                EXPECTED_TRANSACTION_ID_SHA256
            ),
            "expected_phase": EXPECTED_PHASE,
            "expected_status": EXPECTED_STATUS,
            "expected_r26_gate_id": EXPECTED_R26_GATE_ID,
        }

        transport_type = load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        payload = base64.b64encode(
            json.dumps(
                plan,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii")
        completed = transport.run_remote(
            ["python3", "-B", "-c", REMOTE_SCRIPT, payload],
            timeout=300,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        write_private(evidence / "remote_stdout.txt", stdout.encode())
        write_private(evidence / "remote_stderr.txt", stderr.encode())

        remote = json.loads(stdout)
        write_private(
            evidence / "result.json",
            (json.dumps(remote, sort_keys=True, indent=2) + "\n").encode(),
        )
        result.update(remote)
        result["t1_access"] = True
        result["execution_id"] = args.execution_id
        result["expected_package_commit"] = args.expected_package_commit
        result["ssh_master_cleanup"] = True
        return_code = (
            0
            if completed.returncode == 0
            and remote.get("status") == "PASS_DIAGNOSTIC"
            else 2
        )
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
        return_code = 2
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception:
                result["ssh_master_cleanup"] = False

    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
