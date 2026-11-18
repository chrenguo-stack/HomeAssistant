"""Revalidate P3 recovery material and persist only the U8 admission checkpoint."""

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
import ha_backup
import install_intent
import preflight
import u6_preflight
import u6_recovery

SCHEMA = "gh.n3w-t1-u13b-p3-u8-recovery-admission/1"
AUTHORIZATION_ID = "N3W_T1_U13B_P3_U8_RECOVERY_ADMISSION_20261118_01"
U7_SHA = "2f45f6eee5fa59d0dafe53cedc23c11d62de35e949fb645ea8fd74b3d8d861a2"
U7_RECEIPT_SHA = "27739cf29a883c4ee58d8cc6094099f4fd4e36a056dd94acfeb28d29bb203e73"
BACKUP_METADATA_SHA = "b0eb4545d5058f1fbb056f9032eef81ff755d24fe36a914f804392a20fcaf033"
GRANT_FILE = "recovery_admission_grant.json"
U8 = "U8_RECOVERY_ADMISSION_COMPLETE"
PASS = "P3_U8_RECOVERY_ADMISSION_PASS"
PREFLIGHT_PASS = "P3_U8_READONLY_PREFLIGHT_PASS"
STATUS_PASS = "P3_U8_DURABLE_PASS_VERIFIED"
require = recovery.require


def ledger_root():
    return recovery.STATE / "u13b-p3-u8-recovery-admission-20261118-01"


def binding(plan):
    return {
        "schema": SCHEMA, "authorization_id": AUTHORIZATION_ID, "candidate_commit": plan["candidate_commit"],
        "u7_transaction_sha256": U7_SHA, "u7_receipt_sha256": U7_RECEIPT_SHA,
        "target_archive_sha256": plan["target"]["target_archive_sha256"], "maximum_phase": U8,
    }


def validate_grant(plan):
    grant = plan.get("grant")
    require(isinstance(grant, dict), "u8_grant_required")
    expected = {**binding(plan), "authorized": True}
    require(set(grant) == set(expected) | {"expires_at_unix"} and grant["authorized"] is True
            and all(grant[key] == value for key, value in expected.items()), "u8_grant_binding_drift")
    require(type(grant["expires_at_unix"]) is int and grant["expires_at_unix"] > time.time(), "u8_grant_expired")


def attach_grant(plan, root, script, head):
    def git(*args):
        return recovery.run("u8_grant_git", ["git", "-C", str(root), *args]).decode().strip()

    path = str(script.with_name(GRANT_FILE).relative_to(root))
    require(git("diff-tree", "--no-commit-id", "--name-status", "-r", head) == "A\t" + path,
            "u8_separate_grant_commit_required")
    plan["candidate_commit"] = git("rev-parse", head + "^")
    plan["grant"] = json.loads(git("show", f"{head}:{path}"))
    validate_grant(plan)


def bind_u7_ledger(plan):
    ledger = ha_backup.ledger_root()
    recovery.private_path(ledger, directory=True)
    claim = preflight.read_object(ledger / "claim.json")
    broker = claim.get("broker_owner")
    expected = ha_backup.binding({**plan, "candidate_commit": ha_backup.POSTCLAIM_CANDIDATE})
    require(isinstance(broker, dict) and claim == {
        **expected, "claimed": True, "consumed": True, "replay_permitted": False, "broker_owner": broker,
    }, "u8_u7_claim_drift")
    raw = preflight.read_private(ledger / "failure.json")
    require(install_intent.digest_bytes(raw) == ha_backup.POSTCLAIM_FAILURE_SHA
            and not os.path.lexists(ledger / "success.json"), "u8_u7_terminal_receipt_drift")
    return broker


def archive_snapshot(mount):
    from n3w_t1_core_updater_ha_backup import BACKUP_ARCHIVE_NAME, BACKUP_METADATA_NAME

    paths = (
        mount / "n3w-update" / "target" / "homeassistant-arm64.tar.gz",
        mount / "n3w-update" / "predecessor" / "homeassistant-predecessor.tar.gz",
        mount / "n3w-update" / "ha-data" / BACKUP_ARCHIVE_NAME,
        mount / "n3w-update" / "ha-data" / BACKUP_METADATA_NAME,
    )
    return tuple(install_intent.archive_stat(path) for path in paths)


def build_admission(plan, tx, mount, media):
    from n3w_t1_core_updater_ha_backup import backup_record_from_document
    from n3w_t1_core_updater_ha_capacity import validate_recovery_admission_capacity
    from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
    from n3w_t1_core_updater_ha_recovery import image_recovery_record_from_document
    from n3w_t1_core_updater_ha_usb import record_recovery_admission
    from n3w_t1_core_updater_ha_usb_media import assess_capacity

    target = image_recovery_record_from_document(tx["target_artifact_identity"], expected_kind="target")
    predecessor = image_recovery_record_from_document(tx["predecessor_recovery_identity"], expected_kind="predecessor")
    backup = backup_record_from_document(tx["ha_data_backup_identity"])
    device = PreparedUsbMedia(
        "/dev/block/" + media["device"], media["session_fingerprint"], tx["usb_filesystem_uuid"],
        tx["usb_measured_usable_bytes"], str(mount),
    ).validate()
    backend = recovery.recovery_backend(plan, staged_archive=None, identity=None)
    capacity_report = assess_capacity(tx["usb_measured_usable_bytes"], backend.capacity_inputs(tx))
    remaining = validate_recovery_admission_capacity(
        backend.recovery_admission_capacity(tx, device, target=target, predecessor=predecessor, backup=backup),
        target_archive_bytes=target.archive_size_bytes, predecessor_archive_bytes=predecessor.archive_size_bytes,
        ha_backup_archive_bytes=backup.archive_size_bytes,
    )
    admitted = record_recovery_admission(
        tx, target=target, predecessor=predecessor, backup=backup, capacity_report=capacity_report,
        recovery_capacity=remaining, production_prestate_exact=True,
    )
    require(admitted == {
        **tx, "phase": U8, "updated_at_unix": admitted["updated_at_unix"], "production_prestate_verified": True,
        "recovery_content_manifest_sha256": admitted["recovery_content_manifest_sha256"],
    } and admitted["updated_at_unix"] >= tx["updated_at_unix"], "u8_transition_projection_drift")
    return backend, device, admitted, remaining


def check_continuity(plan, snapshot, tx):
    pid, daemon = preflight.service_binding()
    require(daemon == snapshot["daemon"] and preflight.bind_media(tx, pid, include_fingerprint=True)
            == (snapshot["mount"], snapshot["media"]), "u8_ota_or_usb_changed")
    require(archive_snapshot(snapshot["mount"]) == snapshot["archives"], "u8_recovery_artifacts_changed")
    require(ha_backup.verify_quiesced(snapshot["claim"], snapshot["broker"]) == snapshot["owner"],
            "u8_application_owner_changed")
    require(bind_u7_ledger(plan) == snapshot["broker"], "u8_u7_ledger_changed")
    require(preflight.installed_binding(plan, tx)["installed_matches_prior_reference"] is True,
            "u8_installed_sources_drift")
    u6_preflight.image_binding(tx)


def verify_prestate(plan, result):
    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document

    result["stage"] = "bind_durable_u7"
    original = preflight.bind_ledger(plan)
    broker = bind_u7_ledger(plan)
    tx_path = recovery.STATE / preflight.TX_NAME
    raw = preflight.read_private(tx_path)
    require(install_intent.digest_bytes(raw) == U7_SHA, "u8_u7_transaction_digest_drift")
    tx = validate_transaction_document(json.loads(raw))
    pid, daemon = preflight.service_binding()
    mount, media = preflight.bind_media(tx, pid, include_fingerprint=True)
    preflight.bind_mirror(mount, tx)
    archives = archive_snapshot(mount)
    backup, metadata_sha = ha_backup.verify_postclaim(plan, result, tx, mount, original, broker)
    require(backup == tx["ha_data_backup_identity"] and metadata_sha == BACKUP_METADATA_SHA,
            "u8_backup_differs_from_u7_receipt")
    snapshot = {
        "tx": tx, "raw": raw, "daemon": daemon, "mount": mount, "media": media, "archives": archives,
        "claim": original, "broker": broker, "owner": result["application_owner"],
    }
    check_continuity(plan, snapshot, tx)
    preflight.bind_mirror(mount, tx)
    require(preflight.read_private(tx_path) == raw, "u8_u7_transaction_changed")
    return snapshot


def preflight_only(plan, result):
    snapshot = verify_prestate(plan, result)
    tx = snapshot["tx"]
    result["stage"] = "verify_u8_recovery_capacity"
    _, _, admitted, capacity = build_admission(plan, tx, snapshot["mount"], snapshot["media"])
    check_continuity(plan, snapshot, tx)
    preflight.bind_mirror(snapshot["mount"], tx)
    require(preflight.read_private(recovery.STATE / preflight.TX_NAME) == snapshot["raw"], "u8_u7_transaction_changed")
    result.update(status=PREFLIGHT_PASS, stage="u7_verified_for_u8", transaction_phase=tx["phase"],
                  transaction_sha256=U7_SHA, u7_receipt_sha256=U7_RECEIPT_SHA,
                  recovery_content_manifest_sha256=admitted["recovery_content_manifest_sha256"],
                  usb_free_bytes=capacity.observed_usb_free_bytes,
                  usb_required_free_bytes=capacity.required_free_after_recovery_assets_bytes,
                  usb_metadata_matches=True, backup_verified=True, application_services_stopped=True,
                  broker_continuity_verified=True)


def execute(plan, result):
    validate_grant(plan)
    os.umask(0o077)
    ledger = ledger_root()
    require(not os.path.lexists(ledger), "u8_ledger_exists_never_replay")
    snapshot = verify_prestate(plan, result)

    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    store = HaUsbStateStore(recovery.STATE)
    tx = snapshot["tx"]
    mount = snapshot["mount"]
    fingerprint = snapshot["media"]["session_fingerprint"]
    with store.lock():
        result["stage"] = "final_preclaim_binding"
        require(not os.path.lexists(ledger), "u8_ledger_exists_never_replay")
        check_continuity(plan, snapshot, tx)
        preflight.bind_mirror(mount, tx)
        require(preflight.read_private(store.path) == snapshot["raw"], "u8_u7_transaction_changed")
        backend, device, admitted, _ = build_admission(plan, tx, mount, snapshot["media"])
        validate_grant(plan)
        ledger.mkdir(mode=0o700)
        recovery.sync_dir(ledger.parent)
        recovery.write_once(ledger / "claim.json", {
            **binding(plan), "claimed": True, "consumed": True, "replay_permitted": False,
            "write_session_fingerprint": fingerprint,
        })
        result.update(authorization_claimed=True, authorization_consumed=True)
        try:
            result["stage"] = "persist_usb_u8"
            require(preflight.read_private(store.path) == snapshot["raw"], "u8_host_changed_before_usb_write")
            backend.sync_transaction_metadata(admitted, device)
            preflight.bind_mirror(mount, admitted, manifest_fingerprint=fingerprint)
            result.update(usb_u8_verified=True, stage="persist_host_u8")
            require(preflight.read_private(store.path) == snapshot["raw"], "u8_host_changed_before_host_write")
            store.write(admitted)

            result.update(u8_transition=True, stage="verify_u8_and_stop")
            raw = install_intent.state_bytes(admitted)
            check_continuity(plan, snapshot, admitted)
            preflight.bind_mirror(mount, admitted, manifest_fingerprint=fingerprint)
            require(preflight.read_private(store.path) == raw, "u8_host_transaction_mismatch")
            result.update(status=PASS, stage="u8_verified", transaction_phase=U8,
                          transaction_sha256=install_intent.digest_bytes(raw),
                          recovery_content_manifest_sha256=admitted["recovery_content_manifest_sha256"],
                          usb_metadata_matches=True, backup_verified=True,
                          application_services_stopped=True, broker_continuity_verified=True)
            recovery.write_once(ledger / "success.json", result)
        except Exception as error:
            result.update(status="STOP_POSTCLAIM", reason=recovery.safe_reason(error), read_only_status_required=True)
            recovery.write_once(ledger / "failure.json", result)
            raise


def inspect(plan, result):
    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document

    ledger = ledger_root()
    require(os.path.lexists(ledger), "u8_ledger_absent")
    recovery.private_path(ledger, directory=True)
    claim = preflight.read_object(ledger / "claim.json")
    candidate = claim.get("candidate_commit", "")
    fingerprint = claim.get("write_session_fingerprint", "")
    require(re.fullmatch(r"[0-9a-f]{40}", candidate) and re.fullmatch(r"[0-9a-f]{64}", fingerprint)
            and claim == {
                **binding({**plan, "candidate_commit": candidate}), "claimed": True, "consumed": True,
                "replay_permitted": False, "write_session_fingerprint": fingerprint,
            }, "u8_claim_ledger_drift")
    result.update(authorization_claimed=True, authorization_consumed=True)
    original = preflight.bind_ledger(plan)
    broker = bind_u7_ledger(plan)
    tx_path = recovery.STATE / preflight.TX_NAME
    raw = preflight.read_private(tx_path)
    tx = validate_transaction_document(json.loads(raw))
    sha = install_intent.digest_bytes(raw)
    result.update(stage="observe_host_and_usb", transaction_phase=tx["phase"], transaction_sha256=sha)
    require(tx["phase"] in {ha_backup.U7, U8}, "u8_status_outside_boundary")
    pid, daemon = preflight.service_binding()
    mount, media = preflight.bind_media(tx, pid)
    expected = fingerprint if tx["phase"] == U8 else None
    preflight.bind_mirror(mount, tx, manifest_fingerprint=expected)
    result["usb_metadata_matches"] = True
    success_path = ledger / "success.json"
    failure_present = os.path.lexists(ledger / "failure.json")
    if not os.path.lexists(success_path):
        result.update(status="P3_U8_NO_DURABLE_PASS", failure_receipt_present=failure_present)
        return
    success = preflight.read_object(success_path)
    manifest = tx["recovery_content_manifest_sha256"]
    require(not failure_present and success.get("status") == PASS and success.get("transaction_phase") == tx["phase"] == U8
            and success.get("transaction_sha256") == sha and success.get("recovery_content_manifest_sha256") == manifest,
            "u8_durable_success_drift")
    require(ha_backup.verify_backup_files(mount, tx) == BACKUP_METADATA_SHA, "u8_backup_metadata_drift")
    ha_backup.verify_quiesced(original, broker)
    u6_preflight.image_binding(tx)
    require(preflight.read_private(tx_path) == raw and preflight.service_binding() == (pid, daemon)
            and preflight.bind_media(tx, pid) == (mount, media), "u8_status_binding_changed")
    preflight.bind_mirror(mount, tx, manifest_fingerprint=expected)
    result.update(status=STATUS_PASS, stage="durable_u8_verified", recovery_content_manifest_sha256=manifest,
                  application_services_stopped=True, broker_continuity_verified=True, backup_verified=True)


MODES = {"execute": execute, "preflight": preflight_only, "status": inspect}
PASS_FOR_MODE = {"execute": PASS, "preflight": PREFLIGHT_PASS, "status": STATUS_PASS}


def remote_main(mode, encoded):
    result = {"schema": SCHEMA, "status": "STOP", "read_only": mode != "execute",
              "u8_transition": False, "u9_plus": False, "replay_permitted": False,
              "authorization_claimed": None, "authorization_consumed": None}
    try:
        require(os.geteuid() == 0, "target_root_required")
        MODES[mode](json.loads(base64.b64decode(encoded, validate=True)), result)
    except Exception as error:
        if result["status"] != "STOP_POSTCLAIM":
            result.update(status="STOP", reason=recovery.safe_reason(error))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == PASS_FOR_MODE[mode] else 2


def local_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--mode", choices=["source-check", *MODES], default="source-check")
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()

    script = Path(__file__).resolve()
    root = script.parents[5]
    plan = install_intent.build_plan(root, args.expected_commit)
    bootstrap = u6_recovery.make_bootstrap(
        script, extra_modules=(("u6_recovery", u6_recovery), ("check_ha_backup", check_ha_backup), ("ha_backup", ha_backup)),
    )
    if args.mode == "source-check":
        print(json.dumps({"status": "SOURCE_CHECK_PASS", "u8_grant_present": script.with_name(GRANT_FILE).is_file()}))
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
                timeout=1800, check=False,
            )
            require(completed.returncode in (0, 2), "u8_transport_failed")
            receipt = json.loads(completed.stdout)
            passed = PASS_FOR_MODE[args.mode]
            require(receipt.get("schema") == SCHEMA and receipt.get("replay_permitted") is False
                    and receipt.get("u9_plus") is False and receipt.get("read_only") is (args.mode != "execute")
                    and (receipt.get("status") == passed) == (completed.returncode == 0), "u8_receipt_invalid")
            rc = completed.returncode
        except Exception as error:
            receipt = {"schema": SCHEMA, "status": "STOP_UNKNOWN", "reason": recovery.safe_reason(error),
                       "replay_permitted": False, "read_only_status_required": True}
            rc = 2
        recovery.write_once(args.evidence_root / "p3-u8-result.json", receipt)
        print(json.dumps(receipt, sort_keys=True))
        return rc
    finally:
        transport.close_epoch()


if __name__ == "__main__":
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "--remote" and sys.argv[2] in MODES:
            raise SystemExit(remote_main(sys.argv[2], sys.argv[3]))
        raise SystemExit(local_main())
    except Exception as error:
        print(json.dumps({"status": "STOP", "reason": recovery.safe_reason(error)}, sort_keys=True))
        raise SystemExit(2) from None
