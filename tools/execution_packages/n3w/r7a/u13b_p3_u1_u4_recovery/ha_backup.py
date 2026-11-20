"""Run one authorized P3 data backup, stopping at a verified U7."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import check_ha_backup
import executor as recovery
import install_intent
import preflight
import u6_preflight
import u6_recovery

SCHEMA = "gh.n3w-t1-u13b-p3-u7-ha-data-backup/1"
AUTHORIZATION_ID = "N3W_T1_U13B_P3_U7_HA_DATA_BACKUP_20261118_01"
PREFLIGHT_SHA = "fe70384df1773fc98db3668a148c355bc5373f46c00bb3520b367bdb936674a3"
GRANT_FILE = "ha_backup_grant.json"
U7 = "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
PASS = "P3_U7_HA_DATA_BACKUP_PASS"
STATUS_PASS = "P3_U7_DURABLE_PASS_VERIFIED"
POSTCLAIM_VERIFIED = "P3_U7_POSTCLAIM_EVIDENCE_VERIFIED"
POSTCLAIM_CANDIDATE = "879f951e543a585a0c35aa0b1677557b741f62f9"
POSTCLAIM_FAILURE_SHA = "f467552cac646061585bb9a8b84e2100222bab425ab96f23a6b902eaed74587b"
require = recovery.require


def ledger_root():
    return recovery.STATE / "u13b-p3-u7-ha-data-backup-20261118-01"


def binding(plan):
    return {
        "schema": SCHEMA, "authorization_id": AUTHORIZATION_ID, "candidate_commit": plan["candidate_commit"],
        "preflight_receipt_sha256": PREFLIGHT_SHA, "u6_transaction_sha256": check_ha_backup.U6_SHA,
        "target_archive_sha256": plan["target"]["target_archive_sha256"], "maximum_phase": U7,
    }


def validate_grant(plan):
    grant = plan.get("grant")
    require(isinstance(grant, dict), "u7_grant_required")
    expected = {**binding(plan), "authorized": True}
    require(set(grant) == set(expected) | {"expires_at_unix"} and grant["authorized"] is True
            and all(grant[key] == value for key, value in expected.items()), "u7_grant_binding_drift")
    require(type(grant["expires_at_unix"]) is int and grant["expires_at_unix"] > time.time(),
            "u7_grant_expired")


def attach_grant(plan, root, script, head):
    def git(*args):
        return recovery.run("u7_grant_git", ["git", "-C", str(root), *args]).decode().strip()

    path = str(script.with_name(GRANT_FILE).relative_to(root))
    require(git("diff-tree", "--no-commit-id", "--name-status", "-r", head) == "A\t" + path,
            "u7_separate_grant_commit_required")
    plan["candidate_commit"] = git("rev-parse", head + "^")
    plan["grant"] = json.loads(git("show", f"{head}:{path}"))
    validate_grant(plan)


def bound_backend(plan, snapshot):
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend

    mounted = u6_recovery.bound_backend(plan, snapshot)

    class BackupBackend(SubprocessPrepareBackend):
        def resolve_transaction_media(self, transaction, *, write_required):
            return mounted.resolve_transaction_media(transaction, write_required=write_required)

        def verify_prepared_predecessor(self, *, transaction, media):
            record = super().verify_prepared_predecessor(transaction=transaction, media=media)
            require(record.public() == snapshot["predecessor"], "u7_predecessor_authority_drift")
            return record

    return BackupBackend(policy_provider=mounted.policy_provider)


def check_entry(plan, snapshot, tx_path):
    before = snapshot["transaction"]
    u6_recovery.check_binding(plan, snapshot, before)
    require(install_intent.archive_stat(snapshot["old_path"]) == snapshot["old_stat"],
            "u7_predecessor_archive_changed")
    check_ha_backup.require_empty_backup_dir(snapshot["mount"])
    check_ha_backup.verify_capacity(plan, before, snapshot["mount"], snapshot["usb_binding"], snapshot["predecessor"])
    require(install_intent.digest_bytes(preflight.read_private(tx_path)) == check_ha_backup.U6_SHA,
            "u7_u6_transaction_changed")


def verify_quiesced(claim, broker_unit):
    from n3w_t1_core_updater_host import BROKER_UNIT, SERVICES_UNIT

    owner = dict(line.split("=", 1) for line in recovery.run("inspect_quiesced_owner", [
        "systemctl", "show", SERVICES_UNIT, "-p", "ActiveState,SubState,Result,MainPID,NRestarts,ExecMainStatus",
    ]).decode().splitlines() if "=" in line)
    require(owner.get("MainPID") == "0" and owner.get("NRestarts") == "0"
            and (owner.get("ActiveState"), owner.get("SubState"), owner.get("Result")) in {
                ("inactive", "dead", "success"), ("failed", "failed", "exit-code"),
            }, "u7_application_owner_not_quiesced")
    for role, name in recovery.PEERS.items():
        items = json.loads(recovery.run("inspect_quiesced_runtime", [
            "docker", "inspect", "--type", "container", name,
        ]))
        require(isinstance(items, list) and len(items) == 1, "u7_runtime_inspect_invalid")
        item = items[0]
        expected = {**claim["peers"][role]}
        if role != "broker":
            expected["state"] = "exited"
        require({
            "container_id": item["Id"], "image_ref": item["Config"]["Image"],
            "runtime_image_id": item["Image"], "state": item["State"]["Status"],
            "restart_count": item["RestartCount"],
        } == expected, f"u7_runtime_postcondition:{role}")
    require(u6_preflight.owner_units((BROKER_UNIT,))[BROKER_UNIT] == broker_unit, "u7_broker_owner_changed")
    return owner


def verify_backup_files(mount, tx):
    from n3w_t1_core_updater_ha_backup import BACKUP_ARCHIVE_NAME, BACKUP_METADATA_NAME, backup_record_from_document

    record = backup_record_from_document(tx["ha_data_backup_identity"])
    destination = mount / "n3w-update" / "ha-data"
    recovery.private_path(destination, directory=True)
    metadata = preflight.read_private(destination / BACKUP_METADATA_NAME)
    require(preflight.read_private(destination / BACKUP_ARCHIVE_NAME, size=record.archive_size_bytes)
            == record.archive_sha256, "u7_ciphertext_digest_drift")
    return install_intent.digest_bytes(metadata)


def verify_u7_transaction(before, after, predecessor, backup):
    require(after == {
        **before, "phase": U7, "updated_at_unix": after["updated_at_unix"],
        "predecessor_recovery_verified": True, "predecessor_recovery_identity": predecessor,
        "ha_data_backup_verified": True, "ha_data_backup_identity": backup,
    } and after["updated_at_unix"] >= before["updated_at_unix"], "u7_transaction_projection_drift")


def execute(plan, result):
    validate_grant(plan)
    require(os.geteuid() == 0, "target_root_required")
    os.umask(0o077)
    ledger = ledger_root()
    require(not os.path.lexists(ledger), "u7_ledger_exists_never_replay")
    result["stage"] = "fresh_u6_preflight"
    fresh = {}
    snapshot = check_ha_backup.inspect(plan, fresh)
    require(fresh.get("status") == check_ha_backup.PASS, "u7_fresh_preflight_not_pass")

    from n3w_t1_core_updater_ha_backup import ProtectedHaDataBackupProvider
    from n3w_t1_core_updater_ha_install import HaUsbU7BackupController
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
    from n3w_t1_core_updater_host import BROKER_UNIT, LocalHost

    store = HaUsbStateStore(recovery.STATE)
    before = snapshot["transaction"]
    backend = bound_backend(plan, snapshot)
    claim = snapshot["original_claim"]
    broker = snapshot["owner_units"][BROKER_UNIT]

    class RuntimeOwner:
        def __init__(self):
            self.host = LocalHost()

        def quiesce_homeassistant_for_backup(self):
            check_entry(plan, snapshot, store.path)
            result["service_stop_attempted"] = True
            return self.host.quiesce_homeassistant_for_backup()

        def resume_homeassistant_after_backup_failure(self):
            if result["service_stop_attempted"]:
                result["service_resume_attempted"] = True
                self.host.resume_homeassistant_after_backup_failure()
                result["service_resume_verified_by_product"] = True

    with store.lock():
        result["stage"] = "final_preclaim_binding"
        require(not os.path.lexists(ledger), "u7_ledger_exists_never_replay")
        check_entry(plan, snapshot, store.path)
        validate_grant(plan)
        ledger.mkdir(mode=0o700)
        recovery.sync_dir(ledger.parent)
        recovery.write_once(ledger / "claim.json", {
            **binding(plan), "claimed": True, "consumed": True, "replay_permitted": False,
            "broker_owner": broker,
        })
        result.update(authorization_claimed=True, authorization_consumed=True)

        try:
            result["stage"] = "product_u7_backup"
            completed = HaUsbU7BackupController(
                transaction_store=store, backend=backend, runtime_owner=RuntimeOwner(),
                backup_provider=ProtectedHaDataBackupProvider(),
            ).prepare_or_resume()
            require(completed.resumed_from_u7 is False and completed.services_left_quiesced is True,
                    "u7_product_completion_drift")

            result["stage"] = "verify_u7_and_stop"
            tx = store.read()
            raw = preflight.read_private(store.path)
            backup = completed.backup.public()
            require(tx == completed.transaction and raw == install_intent.state_bytes(tx),
                    "u7_host_transaction_mismatch")
            verify_u7_transaction(before, tx, snapshot["predecessor"], backup)
            metadata_sha = verify_backup_files(snapshot["mount"], tx)
            pid, daemon = preflight.service_binding()
            require(daemon == snapshot["daemon"] and preflight.bind_media(tx, pid)
                    == (snapshot["mount"], snapshot["usb_binding"]), "u7_ota_or_usb_binding_changed")
            for prefix in ("target", "old"):
                require(install_intent.archive_stat(snapshot[f"{prefix}_path"]) == snapshot[f"{prefix}_stat"],
                        "u7_image_archive_changed")
            require(preflight.installed_binding(plan, tx) == snapshot["runtime_admission"],
                    "u7_installed_sources_drift")
            u6_preflight.image_binding(tx)
            preflight.bind_mirror(snapshot["mount"], tx)
            verify_quiesced(claim, broker)
            require(preflight.read_private(store.path) == raw, "u7_transaction_changed_after_backup")
            result.update(status=PASS, stage="u7_verified", transaction_phase=U7,
                          transaction_sha256=install_intent.digest_bytes(raw), backup=backup,
                          backup_metadata_sha256=metadata_sha, usb_metadata_matches=True,
                          application_services_stopped=True, broker_continuity_verified=True)
            recovery.write_once(ledger / "success.json", result)
        except Exception as error:
            result.update(status="STOP_POSTCLAIM", reason=recovery.safe_reason(error), read_only_status_required=True)
            recovery.write_once(ledger / "failure.json", result)
            raise


def verify_postclaim(plan, result, tx, mount, claim, broker):
    from n3w_t1_core_updater_ha_backup import (
        BACKUP_ARCHIVE_NAME, BACKUP_METADATA_NAME, ProtectedHaDataBackupProvider, backup_record_from_document,
    )

    require(tx["status"] == "ACTIVE" and tx["phase"] == U7
            and tx["ha_data_backup_verified"] is True and tx["predecessor_recovery_verified"] is True
            and tx["authorization_claimed"] is False and tx["authorization_consumed"] is False
            and tx["authorization_id_sha256"] is None and tx["recovery_content_manifest_sha256"] is None,
            "u7_postclaim_transaction_incomplete")
    predecessor = check_ha_backup.bind_u6_receipt(plan)
    target = plan["target"]
    require(tx["predecessor_recovery_identity"] == predecessor
            and tx["target_manifest_identity"]["release_identity"] == plan["release"]
            and tx["target_manifest_identity"]["target_manifest_sha256"] == plan["target_manifest_sha256"]
            and tx["target_archive_sha256"] == target["target_archive_sha256"]
            and tx["target_archive_size"] == target["target_archive_size_bytes"]
            and tx["target_image_ref"] == target["target_image_ref"]
            and tx["current_image_ref"] == target["expected_predecessor_image_ref"]
            and tx["current_image_identity"]["runtime_image_id"] == plan["predecessor_runtime_id"]
            and tx["usb_device_identity_public_fingerprint"] == plan["usb"]["public_fingerprint"]
            and tx["usb_filesystem_uuid"] != plan["historical_uuid"], "u7_postclaim_transaction_binding_drift")

    result["stage"] = "verify_quiesced_services"
    owner = verify_quiesced(claim, broker)
    result["application_owner"] = owner
    result["stage"] = "verify_existing_recovery_artifacts"
    target_path = mount / "n3w-update" / "target" / "homeassistant-arm64.tar.gz"
    old_path = mount / "n3w-update" / "predecessor" / "homeassistant-predecessor.tar.gz"
    backup_dir = mount / "n3w-update" / "ha-data"
    archive_path = backup_dir / BACKUP_ARCHIVE_NAME
    metadata_path = backup_dir / BACKUP_METADATA_NAME
    for path in (target_path.parent, backup_dir):
        recovery.private_path(path, directory=True)
    for path in (archive_path, metadata_path):
        recovery.private_path(path)
    files = (target_path, old_path, archive_path, metadata_path)
    initial_stats = [install_intent.archive_stat(path) for path in files]
    require(preflight.read_private(target_path, size=tx["target_archive_size"]) == tx["target_archive_sha256"],
            "u7_postclaim_target_digest_drift")
    u6_recovery.verify_archive(mount, tx, predecessor)

    result["stage"] = "verify_existing_protected_backup"
    record = backup_record_from_document(tx["ha_data_backup_identity"])
    provider = ProtectedHaDataBackupProvider()
    transaction_id = tx["transaction_id_sha256"]
    verified = provider.verify_backup(record, transaction_id_sha256=transaction_id, destination_root=backup_dir)
    require(verified == record, "u7_postclaim_backup_identity_drift")
    passphrase, _ = provider._keys(transaction_id)
    provider._compare_with_quiesced_source(archive_path=archive_path, passphrase=passphrase)
    require([install_intent.archive_stat(path) for path in files] == initial_stats
            and verify_quiesced(claim, broker) == owner, "u7_postclaim_artifacts_or_services_changed")
    u6_preflight.image_binding(tx)
    require(preflight.installed_binding(plan, tx)["installed_matches_prior_reference"] is True,
            "u7_installed_sources_drift")
    return record.public(), install_intent.digest_bytes(preflight.read_private(metadata_path))


def inspect(plan, result):
    require(os.geteuid() == 0, "target_root_required")
    ledger = ledger_root()
    if not os.path.lexists(ledger):
        result["status"] = "P3_U7_LEDGER_ABSENT"
        return
    recovery.private_path(ledger, directory=True)
    grant_claim = preflight.read_object(ledger / "claim.json")
    candidate = grant_claim.get("candidate_commit", "")
    broker = grant_claim.get("broker_owner")
    require(isinstance(candidate, str) and re.fullmatch(r"[0-9a-f]{40}", candidate) and grant_claim == {
        **binding({**plan, "candidate_commit": candidate}),
        "claimed": True, "consumed": True, "replay_permitted": False, "broker_owner": broker,
    } and isinstance(broker, dict), "u7_claim_ledger_drift")
    result.update(authorization_claimed=True, authorization_consumed=True)
    claim = preflight.bind_ledger(plan)

    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document

    tx_path = recovery.STATE / preflight.TX_NAME
    raw = preflight.read_private(tx_path)
    tx = validate_transaction_document(json.loads(raw))
    sha = install_intent.digest_bytes(raw)
    result.update(stage="observe_host_and_usb", transaction_phase=tx["phase"], transaction_sha256=sha)
    require(tx["phase"] in {u6_recovery.U6, U7}, "u7_status_outside_boundary")
    pid, daemon = preflight.service_binding()
    mount, media = preflight.bind_media(tx, pid)
    require(media["session_fingerprint_matches"] is True, "p3_usb_session_drift")
    preflight.bind_mirror(mount, tx)
    result["usb_metadata_matches"] = True
    success_path = ledger / "success.json"
    failure_path = ledger / "failure.json"
    if not os.path.lexists(success_path):
        failure_present = os.path.lexists(failure_path)
        result["failure_receipt_present"] = failure_present
        if not failure_present or candidate != POSTCLAIM_CANDIDATE:
            result["status"] = "P3_U7_NO_DURABLE_PASS"
            return
        failure = preflight.read_private(failure_path)
        if install_intent.digest_bytes(failure) != POSTCLAIM_FAILURE_SHA:
            result["status"] = "P3_U7_NO_DURABLE_PASS"
            return
        result["original_failure_receipt_sha256"] = POSTCLAIM_FAILURE_SHA
        backup, metadata_sha = verify_postclaim(plan, result, tx, mount, claim, broker)
        require(preflight.service_binding() == (pid, daemon)
                and preflight.bind_media(tx, pid) == (mount, media)
                and preflight.read_private(tx_path) == raw
                and preflight.read_private(failure_path) == failure
                and not os.path.lexists(success_path), "u7_postclaim_binding_changed")
        preflight.bind_mirror(mount, tx)
        result.update(status=POSTCLAIM_VERIFIED, stage="u7_postclaim_evidence_verified",
                      backup=backup, backup_metadata_sha256=metadata_sha, backup_matches_quiesced_source=True,
                      application_services_stopped=True, broker_running_same_container=True,
                      original_success_receipt_present=False)
        return
    success = preflight.read_object(success_path)
    require(not os.path.lexists(failure_path) and success.get("status") == PASS
            and success.get("transaction_phase") == tx["phase"] == U7 and success.get("transaction_sha256") == sha
            and tx["ha_data_backup_verified"] is True and success.get("backup") == tx["ha_data_backup_identity"]
            and success.get("backup_metadata_sha256") == verify_backup_files(mount, tx),
            "u7_durable_success_drift")
    require(tx["predecessor_recovery_identity"] == check_ha_backup.bind_u6_receipt(plan),
            "u7_predecessor_authority_drift")
    verify_quiesced(claim, broker)
    require(preflight.read_private(tx_path) == raw and preflight.bind_media(tx, pid) == (mount, media),
            "u7_status_binding_changed")
    preflight.bind_mirror(mount, tx)
    result.update(status=STATUS_PASS, stage="durable_u7_verified", backup=success["backup"],
                  application_services_stopped=True, broker_running_same_container=True)


def remote_main(mode, encoded):
    result = {"schema": SCHEMA, "status": "STOP", "read_only": mode == "status", "u8_plus": False,
              "authorization_claimed": None, "authorization_consumed": None, "replay_permitted": False,
              "service_stop_attempted": False, "service_resume_attempted": False}
    try:
        plan = json.loads(base64.b64decode(encoded, validate=True))
        (execute if mode == "execute" else inspect)(plan, result)
    except Exception as error:
        if result["status"] != "STOP_POSTCLAIM":
            result.update(status="STOP", reason=recovery.safe_reason(error))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {PASS, STATUS_PASS, POSTCLAIM_VERIFIED} else 2


def local_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--mode", choices=("source-check", "execute", "status"), default="source-check")
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()

    script = Path(__file__).resolve()
    root = script.parents[5]
    plan = install_intent.build_plan(root, args.expected_commit)
    bootstrap = u6_recovery.make_bootstrap(
        script, extra_modules=(("u6_recovery", u6_recovery), ("check_ha_backup", check_ha_backup)),
    )
    if args.mode == "source-check":
        print(json.dumps({"status": "SOURCE_CHECK_PASS", "u7_grant_present": script.with_name(GRANT_FILE).is_file()}))
        return 0
    if args.mode == "execute":
        attach_grant(plan, root, script, args.expected_commit)
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
        try:
            completed = transport.run_remote(
                ["python3", "-I", "-B", "-c", bootstrap, "--remote", args.mode, data],
                timeout=5400 if args.mode == "execute" else 1200, check=False,
            )
            require(completed.returncode in (0, 2), "u7_transport_failed")
            receipt = json.loads(completed.stdout)
            passed = {PASS} if args.mode == "execute" else {STATUS_PASS, POSTCLAIM_VERIFIED}
            require(receipt.get("schema") == SCHEMA and receipt.get("replay_permitted") is False
                    and receipt.get("u8_plus") is False and receipt.get("read_only") is (args.mode == "status")
                    and (receipt.get("status") in passed) == (completed.returncode == 0), "u7_receipt_invalid")
            rc = completed.returncode
        except Exception as error:
            receipt = {"schema": SCHEMA, "status": "STOP_UNKNOWN", "reason": recovery.safe_reason(error),
                       "replay_permitted": False, "read_only_status_required": True}
            rc = 2
        recovery.write_once(args.evidence_root / "p3-u7-backup-result.json", receipt)
        print(json.dumps(receipt, sort_keys=True))
        return rc
    finally:
        transport.close_epoch()


if __name__ == "__main__":
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "--remote" and sys.argv[2] in {"execute", "status"}:
            raise SystemExit(remote_main(sys.argv[2], sys.argv[3]))
        raise SystemExit(local_main())
    except Exception as error:
        print(json.dumps({"status": "STOP", "reason": recovery.safe_reason(error)}, sort_keys=True))
        raise SystemExit(2) from None
