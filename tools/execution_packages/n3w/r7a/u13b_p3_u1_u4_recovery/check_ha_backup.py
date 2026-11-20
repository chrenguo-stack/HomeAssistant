"""Check U7 backup readiness without stopping services or writing to T1."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import stat
import sys
from pathlib import Path

import executor as recovery
import install_intent
import preflight
import u6_preflight
import u6_recovery

SCHEMA = "gh.n3w-t1-u13b-p3-u7-readonly-preflight/1"
U6_SHA = "c63c215a3b68041c523a74b682725fc6ca42538a458e8357bf79fe27b20f27b8"
U6_RECEIPT_SHA = "8c08a06a1bfaa3a4c27dc9a064f3a0b0904f4d326fa04fd3e36bb0b4a7bf8b9a"
U6_CANDIDATE = "c8e77c76af5ea05445baf6f3d977903a91e860d3"
PASS = "P3_U7_READONLY_PREFLIGHT_PASS"
require = recovery.require


def bind_u6_receipt(plan):
    ledger = u6_recovery.ledger_root()
    recovery.private_path(ledger, directory=True)
    claim = preflight.read_object(ledger / "claim.json")
    require(claim == {
        **u6_recovery.binding({**plan, "candidate_commit": U6_CANDIDATE}),
        "claimed": True, "consumed": True, "replay_permitted": False,
    } and not os.path.lexists(ledger / "failure.json"), "u6_recovery_claim_drift")
    raw = preflight.read_private(ledger / "success.json")
    require(install_intent.digest_bytes(raw) == U6_RECEIPT_SHA, "u6_recovery_receipt_drift")
    receipt = json.loads(raw)
    require(receipt["status"] == u6_recovery.PASS and receipt["transaction_sha256"] == U6_SHA
            and receipt["transaction_phase"] == u6_recovery.U6 and receipt["u7_plus"] is False,
            "u6_recovery_receipt_binding_drift")
    return receipt["predecessor"]


def bind_u6_transaction(plan, raw):
    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document

    require(install_intent.digest_bytes(raw) == U6_SHA, "u6_transaction_digest_drift")
    tx = validate_transaction_document(json.loads(raw))
    target = plan["target"]
    require(
        tx["phase"] == u6_recovery.U6 and tx["status"] == "ACTIVE"
        and tx["authorization_claimed"] is False and tx["authorization_consumed"] is False
        and tx["authorization_id_sha256"] is None
        and tx["target_artifact_verified"] is True and tx["usb_capacity_verified"] is True
        and tx["predecessor_recovery_identity"] is None and tx["ha_data_backup_identity"] is None
        and tx["recovery_content_manifest_sha256"] is None
        and tx["target_manifest_identity"]["release_identity"] == plan["release"]
        and tx["target_manifest_identity"]["target_manifest_sha256"] == plan["target_manifest_sha256"]
        and tx["target_image_ref"] == target["target_image_ref"]
        and tx["target_archive_sha256"] == target["target_archive_sha256"]
        and tx["target_archive_size"] == target["target_archive_size_bytes"]
        and tx["current_image_ref"] == target["expected_predecessor_image_ref"]
        and tx["current_image_identity"]["runtime_image_id"] == plan["predecessor_runtime_id"]
        and tx["usb_filesystem_uuid"] != plan["historical_uuid"]
        and tx["usb_device_identity_public_fingerprint"] == plan["usb"]["public_fingerprint"],
        "u6_transaction_binding_drift",
    )
    return tx


def require_empty_backup_dir(mount):
    path = mount / "n3w-update" / "ha-data"
    if os.path.lexists(path):
        recovery.private_path(path, directory=True)
        require(next(path.iterdir(), None) is None, "unexpected_u7_backup_residue")


def backup_inputs(container_id):
    from n3w_t1_core_updater_ha_backup import ProtectedHaDataBackupProvider

    provider = ProtectedHaDataBackupProvider()
    mounts = json.loads(recovery.run("inspect_ha_config_mount", [
        "docker", "inspect", "--format", "{{json .Mounts}}", container_id,
    ]))
    config = [entry for entry in mounts if entry["Destination"] == "/config"]
    require(len(config) == 1 and config[0]["Type"] == "bind"
            and config[0]["Source"] == str(provider.ha_data_root) and config[0]["RW"] is True
            and all(entry["RW"] is False for entry in mounts if entry["Destination"].startswith("/config/")),
            "u7_ha_backup_bind_mount_drift")
    provider._validate_source_tree()
    database = provider.ha_data_root / "home-assistant_v2.db"
    if os.path.lexists(database):
        require(stat.S_ISREG(database.lstat().st_mode), "ha_data_backup_sqlite_invalid")

    key = provider.system_root_key
    parent_metadata = key.parent.lstat()
    key_metadata = key.lstat()
    require(stat.S_ISDIR(parent_metadata.st_mode) and not parent_metadata.st_mode & 0o022
            and stat.S_ISREG(key_metadata.st_mode) and stat.S_IMODE(key_metadata.st_mode) == 0o600
            and key_metadata.st_nlink == 1 and key_metadata.st_size == 32, "ha_data_backup_root_key_invalid")
    require(shutil.which(provider.openssl_binary) and shutil.which(provider.tar_binary),
            "u7_backup_host_tool_unavailable")


def verify_capacity(plan, tx, mount, media, predecessor):
    from n3w_t1_core_updater_ha_capacity import validate_backup_revalidation
    from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
    from n3w_t1_core_updater_ha_recovery import image_recovery_record_from_document

    record = image_recovery_record_from_document(
        predecessor, expected_kind="predecessor", expected_image_ref=tx["current_image_ref"],
    )
    device = PreparedUsbMedia(
        "/dev/block/" + media["device"], tx["usb_device_identity_public_fingerprint"],
        tx["usb_filesystem_uuid"], tx["usb_measured_usable_bytes"], str(mount),
    ).validate()
    backend = recovery.recovery_backend(plan, staged_archive=None, identity=None)
    capacity = backend.backup_capacity_revalidation(tx, device, predecessor=record)
    return validate_backup_revalidation(
        capacity, expected_target_artifact_bytes=tx["target_archive_size"],
        expected_predecessor_archive_bytes=record.archive_size_bytes,
    )


def inspect(plan, result):
    require(os.geteuid() == 0, "target_root_required")
    result["stage"] = "bind_durable_u6"
    claim = preflight.bind_ledger(plan)
    predecessor = bind_u6_receipt(plan)
    tx_path = recovery.STATE / preflight.TX_NAME
    before = preflight.read_private(tx_path)
    tx = bind_u6_transaction(plan, before)

    result["stage"] = "bind_runtime_usb_and_u6_mirror"
    recovery.check_peers(claim)
    units = u6_preflight.owner_units()
    pid, daemon = preflight.service_binding()
    installed = preflight.installed_binding(plan, tx)
    require(installed["installed_matches_prior_reference"] is True, "installed_sources_drift")
    u6_preflight.image_binding(tx)
    mount, media = preflight.bind_media(tx, pid)
    require(media["session_fingerprint_matches"] is True, "p3_usb_session_drift")
    preflight.bind_mirror(mount, tx)
    require_empty_backup_dir(mount)

    result["stage"] = "verify_archives_and_backup_inputs"
    target = mount / "n3w-update" / "target" / "homeassistant-arm64.tar.gz"
    old = mount / "n3w-update" / "predecessor" / "homeassistant-predecessor.tar.gz"
    recovery.private_path(target.parent, directory=True)
    recovery.private_path(old.parent, directory=True)
    target_stat = install_intent.archive_stat(target)
    old_stat = install_intent.archive_stat(old)
    require(preflight.read_private(target, size=tx["target_archive_size"]) == tx["target_archive_sha256"],
            "u7_target_archive_drift")
    u6_recovery.verify_archive(mount, tx, predecessor)
    backup_inputs(claim["peers"]["homeassistant"]["container_id"])
    capacity = verify_capacity(plan, tx, mount, media, predecessor)
    phase = preflight.ipc_status(claim["peers"]["manager"]["container_id"], plan["predecessor_version"],
                                 expected_phase=u6_recovery.IPC_U6)

    result["stage"] = "verify_readonly_continuity"
    snapshot = {"daemon": daemon, "usb_binding": media, "runtime_admission": installed}
    install_intent.check_continuity(plan, claim, snapshot, tx, target, target_stat)
    u6_preflight.image_binding(tx)
    preflight.bind_mirror(mount, tx)
    require_empty_backup_dir(mount)
    require(preflight.read_private(tx_path) == before and u6_preflight.owner_units() == units
            and install_intent.archive_stat(old) == old_stat, "u7_preflight_state_drift")

    result.update(status=PASS, stage="u6_verified_for_u7", transaction_phase=tx["phase"],
                  transaction_sha256=U6_SHA, u6_receipt_sha256=U6_RECEIPT_SHA, usb_metadata_matches=True,
                  target_archive_sha256=tx["target_archive_sha256"], predecessor_archive_sha256=predecessor["archive_sha256"],
                  ha_backup_inputs_verified=True, capacity_pass=True, usb_free_bytes=capacity.observed_usb_free_bytes,
                  usb_required_remaining_bytes=capacity.required_remaining_bytes, ipc_phase=phase,
                  runtime_continuity_verified=True)
    return {
        **snapshot, "transaction": tx, "original_claim": claim, "owner_units": units, "mount": mount,
        "target_path": target, "target_stat": target_stat, "old_path": old, "old_stat": old_stat,
        "predecessor": predecessor,
    }


def remote_main(encoded):
    result = {"schema": SCHEMA, "status": "STOP", "read_only": True, "u7_transition": False}
    try:
        inspect(json.loads(base64.b64decode(encoded, validate=True)), result)
    except Exception as error:
        result["reason"] = recovery.safe_reason(error)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == PASS else 2


def local_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--mode", choices=("source-check", "preflight"), default="source-check")
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()

    script = Path(__file__).resolve()
    root = script.parents[5]
    plan = install_intent.build_plan(root, args.expected_commit)
    bootstrap = u6_recovery.make_bootstrap(script, extra_modules=(("u6_recovery", u6_recovery),))
    if args.mode == "source-check":
        print(json.dumps({"status": "SOURCE_CHECK_PASS", "u6_transaction_sha256": U6_SHA}))
        return 0

    require(all((args.t1_ssh_target, args.known_hosts, args.expected_host_key_sha256, args.evidence_root)),
            "missing_operator_connection_inputs")
    os.umask(0o077)
    sys.path.insert(0, str(root / "tools"))
    from n3w_t1_ssh_transport import SSHTransport

    transport = SSHTransport(target=args.t1_ssh_target, known_hosts=args.known_hosts,
                             expected_host_key_sha256=args.expected_host_key_sha256)
    args.evidence_root.mkdir(mode=0o700)
    data = base64.b64encode(json.dumps(plan).encode()).decode()
    transport.start_epoch()
    try:
        completed = transport.run_remote(
            ["python3", "-I", "-B", "-c", bootstrap, "--remote", data], timeout=1200, check=False,
        )
        require(completed.returncode in (0, 2), "u7_preflight_transport_failed")
        result = json.loads(completed.stdout)
        require(result.get("schema") == SCHEMA and result.get("read_only") is True and result.get("u7_transition") is False
                and result.get("status") == (PASS if completed.returncode == 0 else "STOP"), "u7_preflight_receipt_invalid")
        recovery.write_once(args.evidence_root / "p3-u7-readonly-result.json", result)
        print(json.dumps(result, sort_keys=True))
        return completed.returncode
    finally:
        transport.close_epoch()


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--remote":
            raise SystemExit(remote_main(sys.argv[2]))
        raise SystemExit(local_main())
    except Exception as error:
        print(json.dumps({"status": "STOP", "reason": recovery.safe_reason(error)}, sort_keys=True))
        raise SystemExit(2) from None
