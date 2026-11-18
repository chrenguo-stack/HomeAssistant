#!/usr/bin/env python3
"""P3 U9 live-authorization claim. Stops before U10 or destructive cutover."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

import check_ha_backup
import executor as recovery
import ha_backup
import install_intent
import preflight
import recovery_admission as u8
import u6_preflight
import u6_recovery

SCHEMA = "gh.n3w-t1-u13b-p3-u9-live-authorization/1"
AUTHORIZATION_ID = "N3W_T1_CORE_UPDATER_HOMEASSISTANT_USB_P3_U9_20261118_01"
GRANT_FILE = "u9_live_authorization_grant.json"
U8 = "U8_RECOVERY_ADMISSION_COMPLETE"
U9 = "U9_LIVE_AUTHORIZATION_CLAIMED"
U8_SHA = "c9210a75ba4496b42fd080ca4ef261cf669a56452f99531066f921a5fcbe4908"
U8_RECEIPT_SHA = "8340d0b4a5be925c954932113b8c593668e83b5f60d1271714f2ce91d521a63a"
RECOVERY_MANIFEST_SHA = "d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3"
PASS = "P3_U9_LIVE_AUTHORIZATION_CLAIM_PASS"
PREFLIGHT_PASS = "P3_U9_READONLY_PREFLIGHT_PASS"
STATUS_PASS = "P3_U9_DURABLE_PASS_VERIFIED"
require = recovery.require


def ledger_root():
    return recovery.STATE / "u13b-p3-u9-live-authorization-20261118-01"


def read_ledger_object(path):
    recovery.private_path(path.parent, directory=True)
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_NONBLOCK,
    )
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(
            stat.S_ISREG(info.st_mode)
            and info.st_uid == 0
            and not info.st_mode & 0o022,
            "u9_ledger_file_metadata_invalid",
        )
        limit = 256 * 1024
        data = stream.read(limit + 1)
        require(
            0 < len(data) <= limit and len(data) == info.st_size,
            "u9_ledger_record_size_invalid",
        )

    def reject_duplicates(pairs):
        value = dict(pairs)
        require(
            len(value) == len(pairs),
            "u9_ledger_record_duplicate_field",
        )
        return value

    value = json.loads(data, object_pairs_hook=reject_duplicates)
    require(isinstance(value, dict), "u9_ledger_record_invalid")
    return value


def binding(plan):
    return {
        "schema": SCHEMA,
        "authorization_id": AUTHORIZATION_ID,
        "candidate_commit": plan["candidate_commit"],
        "u8_transaction_sha256": U8_SHA,
        "u8_receipt_sha256": U8_RECEIPT_SHA,
        "recovery_content_manifest_sha256": RECOVERY_MANIFEST_SHA,
        "target_archive_sha256": plan["target"]["target_archive_sha256"],
        "maximum_phase": U9,
    }


def validate_grant(plan):
    grant = plan.get("grant")
    require(isinstance(grant, dict), "u9_grant_required")
    expected = {**binding(plan), "authorized": True}
    require(
        set(grant) == set(expected) | {"expires_at_unix"}
        and grant["authorized"] is True
        and all(grant[key] == value for key, value in expected.items()),
        "u9_grant_binding_drift",
    )
    require(
        type(grant["expires_at_unix"]) is int
        and grant["expires_at_unix"] > time.time(),
        "u9_grant_expired",
    )


def attach_grant(plan, root, script, head):
    def git(*args):
        return recovery.run(
            "u9_grant_git", ["git", "-C", str(root), *args]
        ).decode().strip()

    path = str(script.with_name(GRANT_FILE).relative_to(root))
    require(
        git("diff-tree", "--no-commit-id", "--name-status", "-r", head)
        == "A\t" + path,
        "u9_separate_grant_commit_required",
    )
    plan["candidate_commit"] = git("rev-parse", head + "^")
    plan["grant"] = json.loads(git("show", f"{head}:{path}"))
    validate_grant(plan)


def state_bytes(document):
    return (
        json.dumps(document, sort_keys=True, indent=2) + "\n"
    ).encode()


def verify_u8(plan, result):
    u8_result = {}
    u8.inspect(plan, u8_result)
    require(
        u8_result.get("status") == u8.STATUS_PASS,
        "u9_u8_durable_status_not_pass",
    )
    require(
        u8_result.get("transaction_phase") == U8
        and u8_result.get("transaction_sha256") == U8_SHA
        and u8_result.get("recovery_content_manifest_sha256")
        == RECOVERY_MANIFEST_SHA
        and u8_result.get("application_services_stopped") is True
        and u8_result.get("broker_continuity_verified") is True
        and u8_result.get("backup_verified") is True
        and u8_result.get("usb_metadata_matches") is True,
        "u9_u8_durable_binding_drift",
    )

    from n3w_t1_core_updater_ha_usb_state import (
        validate_transaction_document,
    )

    tx_path = recovery.STATE / preflight.TX_NAME
    raw = preflight.read_private(tx_path)
    require(
        install_intent.digest_bytes(raw) == U8_SHA,
        "u9_u8_transaction_digest_drift",
    )
    tx = validate_transaction_document(json.loads(raw))
    require(
        tx["phase"] == U8
        and tx["status"] == "ACTIVE"
        and tx["recovery_content_manifest_sha256"]
        == RECOVERY_MANIFEST_SHA
        and tx["authorization_claimed"] is False
        and tx["authorization_consumed"] is False
        and tx["authorization_id_sha256"] is None,
        "u9_u8_product_authorization_state_invalid",
    )

    original = preflight.bind_ledger(plan)
    broker = u8.bind_u7_ledger(plan)
    pid, daemon = preflight.service_binding()
    mount, media = preflight.bind_media(tx, pid, include_fingerprint=True)
    fingerprint = media["session_fingerprint"]
    require(
        isinstance(fingerprint, str)
        and re.fullmatch(r"[0-9a-f]{64}", fingerprint),
        "u9_usb_session_fingerprint_invalid",
    )
    preflight.bind_mirror(
        mount, tx, manifest_fingerprint=fingerprint
    )
    owner = ha_backup.verify_quiesced(original, broker)
    u6_preflight.image_binding(tx)
    require(
        preflight.installed_binding(plan, tx)[
            "installed_matches_prior_reference"
        ]
        is True,
        "u9_installed_sources_drift",
    )
    archives = u8.archive_snapshot(mount)
    require(
        preflight.read_private(tx_path) == raw
        and preflight.service_binding() == (pid, daemon)
        and preflight.bind_media(
            tx, pid, include_fingerprint=True
        )
        == (mount, media),
        "u9_u8_binding_changed",
    )
    result.update(
        stage="u8_verified_for_u9",
        transaction_phase=U8,
        transaction_sha256=U8_SHA,
        recovery_content_manifest_sha256=RECOVERY_MANIFEST_SHA,
        application_owner=owner,
        application_services_stopped=True,
        broker_continuity_verified=True,
        backup_verified=True,
        usb_metadata_matches=True,
    )
    return {
        "tx": tx,
        "raw": raw,
        "tx_path": tx_path,
        "mount": mount,
        "media": media,
        "fingerprint": fingerprint,
        "pid": pid,
        "daemon": daemon,
        "original": original,
        "broker": broker,
        "owner": owner,
        "archives": archives,
    }


def device_from(snapshot):
    from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia

    tx = snapshot["tx"]
    media = snapshot["media"]
    return PreparedUsbMedia(
        "/dev/block/" + media["device"],
        media["session_fingerprint"],
        tx["usb_filesystem_uuid"],
        tx["usb_measured_usable_bytes"],
        str(snapshot["mount"]),
    ).validate()


def check_continuity(plan, snapshot, tx):
    require(
        u8.archive_snapshot(snapshot["mount"]) == snapshot["archives"],
        "u9_recovery_artifacts_changed",
    )
    require(
        ha_backup.verify_quiesced(
            snapshot["original"], snapshot["broker"]
        )
        == snapshot["owner"],
        "u9_application_owner_changed",
    )
    u6_preflight.image_binding(tx)
    require(
        preflight.installed_binding(plan, tx)[
            "installed_matches_prior_reference"
        ]
        is True,
        "u9_installed_sources_changed",
    )
    require(
        preflight.service_binding()
        == (snapshot["pid"], snapshot["daemon"]),
        "u9_ota_service_changed",
    )
    require(
        preflight.bind_media(
            tx,
            snapshot["pid"],
            include_fingerprint=True,
        )
        == (snapshot["mount"], snapshot["media"]),
        "u9_usb_binding_changed",
    )


def projected_u9(tx):
    from n3w_t1_core_updater_ha_usb import (
        claim_live_authorization,
        destructive_cutover_allowed,
    )

    claimed = claim_live_authorization(tx, AUTHORIZATION_ID)
    require(
        claimed["phase"] == U9
        and claimed["authorization_claimed"] is True
        and claimed["authorization_consumed"] is True
        and isinstance(claimed["authorization_id_sha256"], str)
        and re.fullmatch(
            r"[0-9a-f]{64}", claimed["authorization_id_sha256"]
        )
        and destructive_cutover_allowed(claimed) is True,
        "u9_product_projection_invalid",
    )
    return claimed


def preflight_only(plan, result):
    require(not os.path.lexists(ledger_root()), "u9_ledger_exists")
    snapshot = verify_u8(plan, result)
    projected = projected_u9(snapshot["tx"])
    require(
        projected["phase"] == U9
        and snapshot["tx"]["phase"] == U8,
        "u9_preflight_projection_invalid",
    )
    result.update(
        status=PREFLIGHT_PASS,
        stage="u8_verified_for_u9",
        read_only=True,
        u9_transition=False,
        u10_plus=False,
        destructive_cutover=False,
        predecessor_image_delete=False,
        target_image_load=False,
        service_mutation=False,
        authorization_claimed=False,
        authorization_consumed=False,
    )


def execute(plan, result):
    validate_grant(plan)
    require(not os.path.lexists(ledger_root()), "u9_ledger_exists_never_replay")
    snapshot = verify_u8(plan, result)

    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    store = HaUsbStateStore(recovery.STATE)
    tx = snapshot["tx"]
    with store.lock():
        result["stage"] = "final_preclaim_binding"
        require(
            not os.path.lexists(ledger_root()),
            "u9_ledger_exists_never_replay",
        )
        require(
            preflight.read_private(store.path) == snapshot["raw"],
            "u9_u8_transaction_changed_before_claim",
        )
        check_continuity(plan, snapshot, tx)
        preflight.bind_mirror(
            snapshot["mount"],
            tx,
            manifest_fingerprint=snapshot["fingerprint"],
        )
        claimed = projected_u9(tx)
        validate_grant(plan)

        ledger = ledger_root()
        ledger.mkdir(mode=0o700)
        recovery.sync_dir(ledger.parent)
        recovery.write_once(
            ledger / "claim.json",
            {
                **binding(plan),
                "claimed": True,
                "consumed": True,
                "replay_permitted": False,
                "write_session_fingerprint": snapshot["fingerprint"],
            },
        )
        result.update(
            authorization_claimed=True,
            authorization_consumed=True,
        )
        try:
            backend = recovery.recovery_backend(
                plan, staged_archive=None, identity=None
            )
            device = device_from(snapshot)

            result["stage"] = "persist_usb_u9"
            require(
                preflight.read_private(store.path) == snapshot["raw"],
                "u9_host_changed_before_usb_write",
            )
            backend.sync_transaction_metadata(claimed, device)
            preflight.bind_mirror(
                snapshot["mount"],
                claimed,
                manifest_fingerprint=snapshot["fingerprint"],
            )
            result["usb_u9_verified"] = True

            result["stage"] = "persist_host_u9"
            require(
                preflight.read_private(store.path) == snapshot["raw"],
                "u9_host_changed_before_host_write",
            )
            store.write(claimed)

            result["stage"] = "verify_u9_and_stop"
            raw = state_bytes(claimed)
            require(
                preflight.read_private(store.path) == raw,
                "u9_host_transaction_mismatch",
            )
            check_continuity(plan, snapshot, claimed)
            preflight.bind_mirror(
                snapshot["mount"],
                claimed,
                manifest_fingerprint=snapshot["fingerprint"],
            )
            result.update(
                status=PASS,
                stage="u9_verified",
                transaction_phase=U9,
                transaction_sha256=install_intent.digest_bytes(raw),
                recovery_content_manifest_sha256=RECOVERY_MANIFEST_SHA,
                u9_transition=True,
                u10_plus=False,
                destructive_cutover=False,
                predecessor_image_delete=False,
                target_image_load=False,
                service_mutation=False,
                application_services_stopped=True,
                broker_continuity_verified=True,
                backup_verified=True,
                usb_metadata_matches=True,
            )
            recovery.write_once(ledger / "success.json", result)
        except Exception as error:
            result.update(
                status="STOP_POSTCLAIM",
                reason=recovery.safe_reason(error),
                read_only_status_required=True,
                u10_plus=False,
                destructive_cutover=False,
                predecessor_image_delete=False,
                target_image_load=False,
                service_mutation=False,
            )
            recovery.write_once(ledger / "failure.json", result)
            raise


def inspect(plan, result):
    ledger = ledger_root()
    require(os.path.lexists(ledger), "u9_ledger_absent")
    recovery.private_path(ledger, directory=True)
    claim = read_ledger_object(ledger / "claim.json")
    candidate = claim.get("candidate_commit", "")
    fingerprint = claim.get("write_session_fingerprint", "")
    require(
        re.fullmatch(r"[0-9a-f]{40}", candidate)
        and re.fullmatch(r"[0-9a-f]{64}", fingerprint)
        and claim
        == {
            **binding({**plan, "candidate_commit": candidate}),
            "claimed": True,
            "consumed": True,
            "replay_permitted": False,
            "write_session_fingerprint": fingerprint,
        },
        "u9_claim_ledger_drift",
    )
    result.update(
        authorization_claimed=True,
        authorization_consumed=True,
    )

    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document

    tx_path = recovery.STATE / preflight.TX_NAME
    raw = preflight.read_private(tx_path)
    tx = validate_transaction_document(json.loads(raw))
    sha = install_intent.digest_bytes(raw)
    result.update(
        stage="observe_host_and_usb",
        transaction_phase=tx["phase"],
        transaction_sha256=sha,
    )
    require(tx["phase"] in {U8, U9}, "u9_status_outside_boundary")

    original = preflight.bind_ledger(plan)
    broker = u8.bind_u7_ledger(plan)
    pid, daemon = preflight.service_binding()
    mount, media = preflight.bind_media(
        tx, pid, include_fingerprint=True
    )
    expected_fingerprint = fingerprint if tx["phase"] == U9 else None
    preflight.bind_mirror(
        mount, tx, manifest_fingerprint=expected_fingerprint
    )
    owner = ha_backup.verify_quiesced(original, broker)
    u6_preflight.image_binding(tx)
    require(
        preflight.installed_binding(plan, tx)[
            "installed_matches_prior_reference"
        ]
        is True,
        "u9_status_installed_sources_drift",
    )
    require(
        preflight.read_private(tx_path) == raw
        and preflight.service_binding() == (pid, daemon),
        "u9_status_binding_changed",
    )

    success_path = ledger / "success.json"
    failure_present = os.path.lexists(ledger / "failure.json")
    if not os.path.lexists(success_path):
        result.update(
            status="P3_U9_NO_DURABLE_PASS",
            failure_receipt_present=failure_present,
            application_owner=owner,
            application_services_stopped=True,
            broker_continuity_verified=True,
        )
        return

    success = read_ledger_object(success_path)
    require(
        not failure_present
        and tx["phase"] == U9
        and tx["authorization_claimed"] is True
        and tx["authorization_consumed"] is True
        and success.get("status") == PASS
        and success.get("transaction_phase") == U9
        and success.get("transaction_sha256") == sha
        and success.get("u10_plus") is False,
        "u9_durable_success_drift",
    )
    result.update(
        status=STATUS_PASS,
        stage="durable_u9_verified",
        application_owner=owner,
        application_services_stopped=True,
        broker_continuity_verified=True,
        backup_verified=True,
        usb_metadata_matches=True,
        recovery_content_manifest_sha256=RECOVERY_MANIFEST_SHA,
        u10_plus=False,
        destructive_cutover=False,
        predecessor_image_delete=False,
        target_image_load=False,
        service_mutation=False,
    )


MODES = {
    "execute": execute,
    "preflight": preflight_only,
    "status": inspect,
}
PASS_FOR_MODE = {
    "execute": PASS,
    "preflight": PREFLIGHT_PASS,
    "status": STATUS_PASS,
}


def remote_main(mode, encoded):
    os.umask(0o077)
    result = {
        "schema": SCHEMA,
        "status": "STOP",
        "read_only": mode != "execute",
        "u9_transition": False,
        "u10_plus": False,
        "replay_permitted": False,
        "authorization_claimed": None,
        "authorization_consumed": None,
        "destructive_cutover": False,
        "predecessor_image_delete": False,
        "target_image_load": False,
        "service_mutation": False,
    }
    try:
        require(os.geteuid() == 0, "target_root_required")
        MODES[mode](
            json.loads(base64.b64decode(encoded, validate=True)),
            result,
        )
    except Exception as error:
        if result["status"] != "STOP_POSTCLAIM":
            result.update(
                status="STOP",
                reason=recovery.safe_reason(error),
            )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == PASS_FOR_MODE[mode] else 2


def local_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument(
        "--mode",
        choices=["source-check", *MODES],
        default="source-check",
    )
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()

    script = Path(__file__).resolve()
    root = script.parents[5]
    plan = install_intent.build_plan(root, args.expected_commit)
    bootstrap = u6_recovery.make_bootstrap(
        script,
        extra_modules=(
            ("u6_recovery", u6_recovery),
            ("check_ha_backup", check_ha_backup),
            ("ha_backup", ha_backup),
            ("recovery_admission", u8),
        ),
    )
    if args.mode == "source-check":
        print(
            json.dumps(
                {
                    "status": "SOURCE_CHECK_PASS",
                    "authorization_id": AUTHORIZATION_ID,
                    "u9_grant_present": script.with_name(GRANT_FILE).is_file(),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.mode == "execute":
        attach_grant(plan, root, script, args.expected_commit)
    require(
        all(
            (
                args.t1_ssh_target,
                args.known_hosts,
                args.expected_host_key_sha256,
                args.evidence_root,
            )
        ),
        "missing_operator_connection_inputs",
    )
    os.umask(0o077)
    sys.path.insert(0, str(root / "tools"))
    from n3w_t1_ssh_transport import SSHTransport

    transport = SSHTransport(
        target=args.t1_ssh_target,
        known_hosts=args.known_hosts,
        expected_host_key_sha256=args.expected_host_key_sha256,
    )
    args.evidence_root.mkdir(mode=0o700)
    data = base64.b64encode(json.dumps(plan).encode()).decode()
    transport.start_epoch()
    try:
        try:
            completed = transport.run_remote(
                [
                    "python3",
                    "-I",
                    "-B",
                    "-c",
                    bootstrap,
                    "--remote",
                    args.mode,
                    data,
                ],
                timeout=1800,
                check=False,
            )
            require(
                completed.returncode in (0, 2),
                "u9_transport_failed",
            )
            receipt = json.loads(completed.stdout)
            passed = PASS_FOR_MODE[args.mode]
            require(
                receipt.get("schema") == SCHEMA
                and receipt.get("replay_permitted") is False
                and receipt.get("u10_plus") is False
                and receipt.get("read_only")
                is (args.mode != "execute")
                and (receipt.get("status") == passed)
                == (completed.returncode == 0),
                "u9_receipt_invalid",
            )
            rc = completed.returncode
        except Exception as error:
            receipt = {
                "schema": SCHEMA,
                "status": "STOP_UNKNOWN",
                "reason": recovery.safe_reason(error),
                "replay_permitted": False,
                "read_only_status_required": True,
            }
            rc = 2
        recovery.write_once(
            args.evidence_root / "p3-u9-result.json",
            receipt,
        )
        print(json.dumps(receipt, sort_keys=True))
        return rc
    finally:
        transport.close_epoch()


if __name__ == "__main__":
    try:
        if (
            len(sys.argv) == 4
            and sys.argv[1] == "--remote"
            and sys.argv[2] in MODES
        ):
            raise SystemExit(remote_main(sys.argv[2], sys.argv[3]))
        raise SystemExit(local_main())
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "STOP",
                    "reason": recovery.safe_reason(error),
                    "replay_permitted": False,
                },
                sort_keys=True,
            )
        )
        raise SystemExit(2) from None
