#!/usr/bin/env python3
"""P3 U10 predecessor-capacity-release read-only preflight. No execute mode."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

import check_ha_backup
import executor as recovery
import ha_backup
import install_intent
import preflight
import recovery_admission as u8
import u6_preflight
import u6_recovery
import u9_live_authorization as u9

SCHEMA = "gh.n3w-t1-u13b-p3-u10-readonly-preflight/1"
PASS = "P3_U10_READONLY_PREFLIGHT_PASS"
U9 = "U9_LIVE_AUTHORIZATION_CLAIMED"
U10 = "U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED"
U9_SHA = "2b3812af093c1f73a95744413e238f1ca3763407241f889c0646b9495e35a84b"
RECOVERY_MANIFEST_SHA = "d534be84e38817b10eab8a2f8a47c6dae3fd0946da9eba1e1d7f12090e23e9d3"
require = recovery.require


def read_container(container_id):
    values = json.loads(
        recovery.run(
            "u10_inspect_container",
            ["docker", "inspect", container_id],
        )
    )
    require(
        isinstance(values, list)
        and len(values) == 1
        and isinstance(values[0], dict),
        "u10_container_inspect_invalid",
    )
    return values[0]


def verify_release_candidate(original, tx):
    predecessor_id = tx["current_image_identity"]["runtime_image_id"]
    expected_ha = original["peers"]["homeassistant"]["container_id"]
    ids = [
        line.strip()
        for line in recovery.run(
            "u10_list_containers",
            ["docker", "ps", "-aq", "--no-trunc"],
        )
        .decode()
        .splitlines()
        if line.strip()
    ]
    users = []
    for container_id in ids:
        item = read_container(container_id)
        if item.get("Image") == predecessor_id:
            users.append(container_id)

    require(
        users == [expected_ha],
        "u10_predecessor_runtime_user_allowlist_invalid",
    )
    homeassistant = read_container(expected_ha)
    require(
        homeassistant.get("Image") == predecessor_id
        and homeassistant.get("State", {}).get("Status") == "exited"
        and homeassistant.get("RestartCount") == 0,
        "u10_homeassistant_release_candidate_invalid",
    )
    u6_preflight.image_binding(tx)
    return {
        "homeassistant_container_id": expected_ha,
        "predecessor_runtime_image_id": predecessor_id,
        "predecessor_runtime_users": users,
        "homeassistant_exited": True,
        "target_internal_image_absent": True,
    }


def verify_recovery_assets(tx, mount):
    from n3w_t1_core_updater_ha_backup import (
        ProtectedHaDataBackupProvider,
        backup_record_from_document,
    )
    from n3w_t1_core_updater_ha_capacity import (
        CapacityPolicy,
        ceil_ratio_ppm,
        compute_recovery_admission_capacity,
        round_up,
    )
    from n3w_t1_core_updater_ha_recovery import (
        image_recovery_record_from_document,
    )

    target = image_recovery_record_from_document(
        tx["target_artifact_identity"],
        expected_kind="target",
        expected_image_ref=tx["target_image_ref"],
        expected_archive_sha256=tx["target_archive_sha256"],
    )
    predecessor = image_recovery_record_from_document(
        tx["predecessor_recovery_identity"],
        expected_kind="predecessor",
        expected_image_ref=tx["current_image_ref"],
    )
    backup = backup_record_from_document(tx["ha_data_backup_identity"])

    target_path = (
        mount / "n3w-update" / "target" / "homeassistant-arm64.tar.gz"
    )
    predecessor_path = (
        mount
        / "n3w-update"
        / "predecessor"
        / "homeassistant-predecessor.tar.gz"
    )
    require(
        preflight.read_private(
            target_path, size=target.archive_size_bytes
        )
        == target.archive_sha256,
        "u10_target_recovery_archive_drift",
    )
    require(
        preflight.read_private(
            predecessor_path, size=predecessor.archive_size_bytes
        )
        == predecessor.archive_sha256,
        "u10_predecessor_recovery_archive_drift",
    )
    verified_backup = ProtectedHaDataBackupProvider().verify_backup(
        backup,
        transaction_id_sha256=tx["transaction_id_sha256"],
        destination_root=mount / "n3w-update" / "ha-data",
    )
    require(
        verified_backup.public() == tx["ha_data_backup_identity"],
        "u10_backup_identity_drift",
    )

    policy = CapacityPolicy.frozen()
    working = round_up(
        max(
            policy.transaction_working_floor_bytes,
            ceil_ratio_ppm(
                target.archive_size_bytes,
                policy.transaction_working_target_ratio_ppm,
            ),
        ),
        policy.round_up_quantum_bytes,
    )
    filesystem = os.statvfs(mount)
    free_bytes = filesystem.f_bavail * filesystem.f_frsize
    capacity = compute_recovery_admission_capacity(
        target_archive_bytes=target.archive_size_bytes,
        predecessor_archive_bytes=predecessor.archive_size_bytes,
        ha_backup_archive_bytes=backup.archive_size_bytes,
        transaction_working_budget_bytes=working,
        observed_usb_free_bytes=free_bytes,
        policy=policy,
    )
    require(
        capacity.capacity_pass is True,
        "u10_recovery_capacity_not_verified",
    )
    return {
        "target_archive_sha256": target.archive_sha256,
        "predecessor_archive_sha256": predecessor.archive_sha256,
        "backup_archive_sha256": backup.archive_sha256,
        "backup_verified": True,
        "observed_usb_free_bytes": capacity.observed_usb_free_bytes,
        "required_free_after_recovery_assets_bytes": (
            capacity.required_free_after_recovery_assets_bytes
        ),
        "capacity_pass": True,
    }


def project_u10(tx):
    from n3w_t1_core_updater_ha_usb import (
        destructive_cutover_allowed,
        record_predecessor_capacity_released,
    )

    require(
        destructive_cutover_allowed(tx) is True,
        "u10_destructive_successor_not_eligible",
    )
    projected = record_predecessor_capacity_released(
        tx,
        predecessor_runtime_released=True,
        predecessor_image_released=True,
        target_internal_image_absent=True,
    )
    require(
        tx["phase"] == U9
        and projected["phase"] == U10
        and destructive_cutover_allowed(projected) is True,
        "u10_projection_invalid",
    )
    return projected


def inspect(plan, result):
    result["stage"] = "bind_durable_u9"
    u9_result = {}
    u9.inspect(plan, u9_result)
    require(
        u9_result.get("status") == u9.STATUS_PASS
        and u9_result.get("transaction_phase") == U9
        and u9_result.get("transaction_sha256") == U9_SHA
        and u9_result.get("u10_plus") is False,
        "u10_u9_durable_status_invalid",
    )

    from n3w_t1_core_updater_ha_usb import destructive_cutover_allowed
    from n3w_t1_core_updater_ha_usb_state import (
        validate_transaction_document,
    )

    tx_path = recovery.STATE / preflight.TX_NAME
    raw = preflight.read_private(tx_path)
    require(
        install_intent.digest_bytes(raw) == U9_SHA,
        "u10_u9_transaction_digest_drift",
    )
    tx = validate_transaction_document(json.loads(raw))
    require(
        tx["phase"] == U9
        and tx["status"] == "ACTIVE"
        and tx["authorization_claimed"] is True
        and tx["authorization_consumed"] is True
        and isinstance(tx["authorization_id_sha256"], str)
        and re.fullmatch(r"[0-9a-f]{64}", tx["authorization_id_sha256"])
        and tx["recovery_content_manifest_sha256"]
        == RECOVERY_MANIFEST_SHA
        and destructive_cutover_allowed(tx) is True,
        "u10_u9_transaction_invalid",
    )

    original = preflight.bind_ledger(plan)
    broker = u8.bind_u7_ledger(plan)
    pid, daemon = preflight.service_binding()
    mount, media = preflight.bind_media(
        tx, pid, include_fingerprint=True
    )
    preflight.bind_mirror(
        mount,
        tx,
        manifest_fingerprint=media["session_fingerprint"],
    )
    owner = ha_backup.verify_quiesced(original, broker)
    deployment = preflight.installed_binding(plan, tx)
    require(
        deployment["installed_matches_prior_reference"] is True,
        "u10_installed_sources_drift",
    )
    before_archives = u8.archive_snapshot(mount)

    result["stage"] = "verify_u10_release_candidate"
    release = verify_release_candidate(original, tx)
    assets = verify_recovery_assets(tx, mount)
    projected = project_u10(tx)

    result["stage"] = "verify_readonly_continuity"
    require(
        preflight.read_private(tx_path) == raw
        and preflight.service_binding() == (pid, daemon)
        and preflight.bind_media(
            tx, pid, include_fingerprint=True
        )
        == (mount, media)
        and u8.archive_snapshot(mount) == before_archives
        and ha_backup.verify_quiesced(original, broker) == owner,
        "u10_readonly_state_changed",
    )
    preflight.bind_mirror(
        mount,
        tx,
        manifest_fingerprint=media["session_fingerprint"],
    )
    verify_release_candidate(original, tx)

    result.update(
        status=PASS,
        stage="u9_verified_for_u10",
        transaction_phase=U9,
        transaction_sha256=U9_SHA,
        recovery_content_manifest_sha256=RECOVERY_MANIFEST_SHA,
        read_only=True,
        authorization_claimed=True,
        authorization_consumed=True,
        replay_permitted=False,
        destructive_cutover=False,
        destructive_cutover_eligible=True,
        projected_phase=projected["phase"],
        u10_transition=False,
        u11_plus=False,
        predecessor_runtime_delete=False,
        predecessor_image_delete=False,
        target_image_load=False,
        service_mutation=False,
        application_owner=owner,
        application_services_stopped=True,
        broker_continuity_verified=True,
        usb_metadata_matches=True,
        release_candidate=release,
        recovery_assets=assets,
    )


def remote_main(encoded):
    result = {
        "schema": SCHEMA,
        "status": "STOP",
        "read_only": True,
        "authorization_claimed": None,
        "authorization_consumed": None,
        "replay_permitted": False,
        "destructive_cutover": False,
        "destructive_cutover_eligible": False,
        "u10_transition": False,
        "u11_plus": False,
        "predecessor_runtime_delete": False,
        "predecessor_image_delete": False,
        "target_image_load": False,
        "service_mutation": False,
    }
    try:
        require(os.geteuid() == 0, "target_root_required")
        inspect(
            json.loads(base64.b64decode(encoded, validate=True)),
            result,
        )
    except Exception as error:
        result.update(
            status="STOP",
            reason=recovery.safe_reason(error),
        )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == PASS else 2


def local_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument(
        "--mode",
        choices=("source-check", "preflight"),
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
            ("u9_live_authorization", u9),
        ),
    )
    if args.mode == "source-check":
        print(
            json.dumps(
                {
                    "status": "SOURCE_CHECK_PASS",
                    "u9_transaction_sha256": U9_SHA,
                    "execute_mode_present": False,
                },
                sort_keys=True,
            )
        )
        return 0

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
                    data,
                ],
                timeout=2400,
                check=False,
            )
            require(
                completed.returncode in (0, 2),
                "u10_preflight_transport_failed",
            )
            receipt = json.loads(completed.stdout)
            require(
                receipt.get("schema") == SCHEMA
                and receipt.get("read_only") is True
                and receipt.get("u10_transition") is False
                and receipt.get("u11_plus") is False
                and receipt.get("destructive_cutover") is False
                and (receipt.get("status") == PASS)
                == (completed.returncode == 0),
                "u10_preflight_receipt_invalid",
            )
            rc = completed.returncode
        except Exception as error:
            receipt = {
                "schema": SCHEMA,
                "status": "STOP_UNKNOWN",
                "reason": recovery.safe_reason(error),
                "read_only": True,
                "replay_permitted": False,
                "u10_transition": False,
                "u11_plus": False,
                "destructive_cutover": False,
            }
            rc = 2
        recovery.write_once(
            args.evidence_root / "p3-u10-preflight-result.json",
            receipt,
        )
        print(json.dumps(receipt, sort_keys=True))
        return rc
    finally:
        transport.close_epoch()


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--remote":
            raise SystemExit(remote_main(sys.argv[2]))
        raise SystemExit(local_main())
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "STOP",
                    "reason": recovery.safe_reason(error),
                    "read_only": True,
                    "replay_permitted": False,
                    "u10_transition": False,
                    "u11_plus": False,
                    "destructive_cutover": False,
                },
                sort_keys=True,
            )
        )
        raise SystemExit(2) from None
