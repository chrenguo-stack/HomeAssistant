"""One-shot P3 U4-to-U5 intent. A separate reviewed grant is required to write."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import executor as recovery
import preflight

AUTHORIZATION_ID = "N3W_T1_U13B_P3_U4_TO_U5_INSTALL_INTENT_20261118_01"
U5 = "U5_INSTALL_REQUESTED_REVALIDATING"
PREFLIGHT_SHA = "99ceecf381c58cbd32439f37f0b9ca90f220a835b10040b302728fbc9f3bc70a"
SCHEMA = "gh.n3w-t1-u13b-p3-u4-u5-install-intent/1"
LEDGER_NAME = "u13b-p3-u4-u5-install-intent-20261118-01"
GRANT_FILE = "install_intent_grant.json"
TARGET_MANIFEST = "infra/n3w-t1/upgrades/homeassistant-2026.10.4-u13b-same-version-acceptance.json"
TARGET_MANIFEST_BLOB = "d22a38aa3b34590cda3df39a8fb48cf61a01ec59"
require = recovery.require


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def ledger_root():
    return recovery.STATE / LEDGER_NAME


def validate_grant(grant, plan):
    require(isinstance(grant, dict), "install_grant_required")
    expected = {
        "schema": SCHEMA,
        "authorization_id": AUTHORIZATION_ID,
        "authorized": True,
        "candidate_commit": plan["candidate_commit"],
        "preflight_receipt_sha256": PREFLIGHT_SHA,
        "u4_transaction_sha256": preflight.U4_SHA,
        "target_archive_sha256": plan["target"]["target_archive_sha256"],
        "maximum_phase": U5,
    }
    require(set(grant) == set(expected) | {"expires_at_unix"}
            and grant["authorized"] is True
            and all(grant[key] == value for key, value in expected.items()), "install_grant_binding_invalid")
    require(type(grant["expires_at_unix"]) is int and grant["expires_at_unix"] > time.time(),
            "install_grant_expired")


def state_bytes(document):
    return (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()


def verify_archive(path, tx, target):
    from n3w_t1_core_updater_ha_recovery import image_recovery_record_from_document
    from n3w_t1_core_updater_v2_common import canonical
    from n3w_t1_portable_image_identity import parse_image_archive

    recovery.private_path(path.parent, directory=True)
    recovery.private_path(path)
    identity = parse_image_archive(
        path, expected_archive_sha256=tx["target_archive_sha256"],
        expected_archive_size_bytes=tx["target_archive_size"], expected_tag=tx["target_image_ref"],
        platform_os="linux", platform_architecture="arm64",
    )
    record = image_recovery_record_from_document(
        tx["target_artifact_identity"], expected_kind="target",
        expected_image_ref=tx["target_image_ref"],
    )
    require(record.portable_identity_sha256 == digest_bytes(canonical(identity.to_dict()))
            and identity.config_semantics_sha256 == target["target_config_semantics_sha256"]
            and identity.rootfs_diff_ids_sha256 == target["target_rootfs_diff_ids_sha256"],
            "prepared_target_portable_identity_drift")
    return record


def archive_stat(path):
    info = path.lstat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def check_continuity(plan, claim, receipt, tx, path, identity):
    pid, daemon = preflight.service_binding()
    require(daemon == receipt["daemon"], "ota_service_changed")
    mount, actual = preflight.bind_media(tx, pid)
    require(actual == receipt["usb_binding"] and path.parent.parent.parent == mount
            and archive_stat(path) == identity, "usb_or_archive_changed")
    require(preflight.installed_binding(plan, tx) == receipt["runtime_admission"], "installed_source_changed")
    recovery.check_peers(claim)


def persist_intent(store, backend, media, before, u5, mount, result):
    require(preflight.read_private(store.path) == before, "host_u4_changed_before_usb_write")
    result["stage"] = "persist_usb_u5"
    backend.sync_transaction_metadata(u5, media)
    preflight.bind_mirror(mount, u5)
    require(preflight.read_private(store.path) == before, "host_u4_changed_before_host_write")
    result["stage"] = "persist_host_u5"
    store.write(u5)
    result["stage"] = "verify_u5_postcondition"
    require(preflight.read_private(store.path) == state_bytes(u5), "host_u5_not_exact")
    preflight.bind_mirror(mount, u5)


def execute(plan, result):
    validate_grant(plan.get("grant"), plan)
    require(os.geteuid() == 0, "target_root_required")
    os.umask(0o077)
    ledger = ledger_root()
    require(not os.path.lexists(ledger), "install_ledger_exists_never_replay")
    result["stage"] = "fresh_preflight"
    receipt = preflight.initial_receipt()
    preflight.preflight(plan, receipt)
    raw_receipt = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    require(digest_bytes(raw_receipt) == PREFLIGHT_SHA, "archived_preflight_snapshot_drift")
    deployment = receipt["runtime_admission"]
    require(deployment["installed_matches_prior_reference"] is True
            and deployment["approved_manifest_matches_transaction"] is False
            and deployment["fixed_release_policy_matches_transaction"] is False
            and receipt["usb_binding"]["session_fingerprint_matches"] is True,
            "p3_manual_intent_preconditions_drift")

    from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_usb import request_install
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    store = HaUsbStateStore(recovery.STATE)
    before = preflight.read_private(store.path)
    tx = preflight.bind_transaction(plan, before)
    require(tx["target_manifest_identity"] == {
        "release_identity": plan["release"], "target_manifest_sha256": plan["target_manifest_sha256"],
        "target_image_ref": plan["target"]["target_image_ref"],
        "target_archive_sha256": plan["target"]["target_archive_sha256"],
    }, "p3_target_acceptance_manifest_drift")
    mount = Path(receipt["usb_binding"]["mountpoint"])
    path = mount / "n3w-update" / "target" / "homeassistant-arm64.tar.gz"
    identity = archive_stat(path)
    result["stage"] = "revalidate_frozen_p3_archive"
    record = verify_archive(path, tx, plan["target"])
    claim = preflight.read_object(recovery.STATE / plan["original_root"] / "authorization_claim.json")
    media = PreparedUsbMedia(
        "/dev/block/" + receipt["usb_binding"]["device"], tx["usb_device_identity_public_fingerprint"],
        tx["usb_filesystem_uuid"], tx["usb_measured_usable_bytes"], str(mount),
    ).validate()
    with store.lock():
        result["stage"] = "final_u4_binding"
        require(not os.path.lexists(ledger), "install_ledger_exists_never_replay")
        check_continuity(plan, claim, receipt, tx, path, identity)
        require(preflight.read_private(store.path) == before, "host_u4_changed_before_claim")
        preflight.bind_mirror(mount, tx)
        u5 = request_install(tx, target=record)
        require(u5["phase"] == U5 and u5["target_artifact_identity"] == tx["target_artifact_identity"],
                "install_intent_projection_drift")
        validate_grant(plan["grant"], plan)
        result["stage"] = "claim"
        ledger.mkdir(mode=0o700)
        recovery.sync_dir(recovery.STATE)
        recovery.write_once(ledger / "claim.json", {
            "schema": SCHEMA, "authorization_id": AUTHORIZATION_ID,
            "candidate_commit": plan["candidate_commit"], "preflight_receipt_sha256": PREFLIGHT_SHA,
            "u4_transaction_sha256": preflight.U4_SHA, "u5_transaction_sha256": digest_bytes(state_bytes(u5)),
            "claimed": True, "consumed": True, "replay_permitted": False,
        })
        result.update(authorization_claimed=True, authorization_consumed=True)
        persist_intent(store, SubprocessPrepareBackend(), media, before, u5, mount, result)
        check_continuity(plan, claim, receipt, u5, path, identity)
        preflight.ipc_status(claim["peers"]["manager"]["container_id"], plan["predecessor_version"],
                             expected_phase="INSTALL_REQUESTED_REVALIDATING")
        require(preflight.read_private(store.path) == state_bytes(u5), "host_u5_changed_after_ipc")
        preflight.bind_mirror(mount, u5)
        result.update(status="P3_U5_INSTALL_INTENT_PASS", stage="u5_verified",
                      transaction_phase=U5, transaction_sha256=digest_bytes(state_bytes(u5)),
                      usb_metadata_matches=True, ipc_phase="INSTALL_REQUESTED_REVALIDATING")
        recovery.write_once(ledger / "result.json", result)


def inspect(plan, result):
    require(os.geteuid() == 0, "target_root_required")
    result["stage"] = "inspect_install_ledger"
    ledger = ledger_root()
    if not os.path.lexists(ledger):
        result["status"] = "P3_U5_NO_CLAIM_LEDGER"
        return
    recovery.private_path(ledger, directory=True)
    result["authorization_claimed"] = None
    result["authorization_consumed"] = None
    claim = preflight.read_object(ledger / "claim.json")
    require(claim.get("schema") == SCHEMA and claim.get("authorization_id") == AUTHORIZATION_ID
            and claim.get("claimed") is True and claim.get("consumed") is True
            and claim.get("replay_permitted") is False and claim.get("preflight_receipt_sha256") == PREFLIGHT_SHA
            and claim.get("u4_transaction_sha256") == preflight.U4_SHA
            and re.fullmatch(r"[0-9a-f]{64}", claim.get("u5_transaction_sha256", "")),
            "install_claim_invalid")
    result.update(authorization_claimed=True, authorization_consumed=True)
    preflight.bind_ledger(plan)

    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document

    result["stage"] = "inspect_persistent_transaction"
    tx_path = recovery.STATE / preflight.TX_NAME
    before = preflight.read_private(tx_path)
    sha = digest_bytes(before)
    result["transaction_sha256"] = sha
    tx = validate_transaction_document(json.loads(before))
    result["transaction_phase"] = tx["phase"]
    require((tx["phase"], sha) in {(preflight.U4, preflight.U4_SHA), (U5, claim["u5_transaction_sha256"])},
            "observed_host_transaction_drift")
    pid, _ = preflight.service_binding()
    mount, _ = preflight.bind_media(tx, pid)
    result["stage"] = "inspect_usb_mirror"
    mirror_root = mount / "n3w-update" / "transaction"
    for directory in (mirror_root.parent, mirror_root):
        recovery.private_path(directory, directory=True)
    mirror = preflight.read_object(mirror_root / "host-transaction.json")
    result["usb_mirror_phase"] = mirror.get("phase")
    if tx["phase"] == preflight.U4 and digest_bytes(state_bytes(mirror)) == claim["u5_transaction_sha256"]:
        preflight.bind_mirror(mount, mirror)
        require(preflight.read_private(tx_path) == before, "host_changed_during_readonly_status")
        result["status"] = "STOP_USB_U5_HOST_U4"
        return
    preflight.bind_mirror(mount, tx)
    require(preflight.read_private(tx_path) == before, "host_changed_during_readonly_status")
    result.update(usb_metadata_matches=True, stage="status_verified",
                  status="P3_U5_BOTH_U5_VERIFIED" if tx["phase"] == U5 else "P3_U5_BOTH_U4_OBSERVED_NO_REPLAY")


def remote_main(mode, encoded):
    result = {"schema": SCHEMA, "status": "STOP", "read_only": mode == "status",
              "authorization_claimed": False, "authorization_consumed": False,
              "replay_permitted": False, "u6_plus": False}
    try:
        plan = json.loads(base64.b64decode(encoded, validate=True))
        (execute if mode == "execute" else inspect)(plan, result)
    except Exception as error:
        result["status"] = "STOP"
        result["reason"] = recovery.safe_reason(error)
        if mode == "execute" and os.path.lexists(ledger_root()) and result["authorization_claimed"] is False:
            result.update(authorization_claimed=None, authorization_consumed=None)
        if mode == "execute" and result["authorization_claimed"] is not False:
            result["read_only_status_required"] = True
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"].startswith("STOP") else 0


def attach_grant(plan, root, script, execution_head):
    def git(*args):
        return recovery.run("install_grant_git", ["git", "-C", str(root), *args]).decode().strip()

    grant_path = str(script.with_name(GRANT_FILE).relative_to(root))
    require(git("diff-tree", "--no-commit-id", "--name-status", "-r", execution_head) == "A\t" + grant_path,
            "a_separate_grant_commit_is_required")
    plan["candidate_commit"] = git("rev-parse", execution_head + "^")
    plan["grant"] = json.loads(git("show", f"{execution_head}:{grant_path}"))
    validate_grant(plan["grant"], plan)


def build_plan(root, expected_commit):
    plan = preflight.build_plan(expected_commit)
    ref = f"{recovery.BASE_COMMIT}:{TARGET_MANIFEST}"
    git = ["git", "-C", str(root)]
    oid = recovery.run("acceptance_manifest_binding", [*git, "rev-parse", ref]).decode().strip()
    require(oid == TARGET_MANIFEST_BLOB, "acceptance_manifest_blob_drift")
    document = json.loads(recovery.run("read_acceptance_manifest", [*git, "show", ref]))
    for key in ("target_image_ref", "target_archive_sha256", "expected_predecessor_image_ref", "artifact_identity"):
        require(document[key] == plan["target"][key], "acceptance_manifest_target_drift")
    plan["target_manifest_sha256"] = digest_bytes(json.dumps(document, sort_keys=True, separators=(",", ":")).encode())
    return plan


def local_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--mode", choices=("source-check", "status", "execute"), default="source-check")
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()

    script = Path(__file__).resolve()
    root = script.parents[5]
    plan = build_plan(root, args.expected_commit)
    parts = ["import base64, sys, types"]
    for name, path in (("executor", Path(recovery.__file__)), ("preflight", Path(preflight.__file__))):
        encoded = base64.b64encode(path.read_bytes()).decode()
        parts.append(f"sys.modules[{name!r}] = types.ModuleType({name!r})")
        parts.append(f"exec(compile(base64.b64decode({encoded!r}), {name!r}, 'exec'), sys.modules[{name!r}].__dict__)")
    encoded = base64.b64encode(script.read_bytes()).decode()
    parts.append(f"exec(compile(base64.b64decode({encoded!r}), '<install-intent>', 'exec'))")
    bootstrap = "\n".join(parts)
    compile(bootstrap, "<install-intent-bootstrap>", "exec")
    if args.mode == "source-check":
        print(json.dumps({"status": "SOURCE_CHECK_PASS", "authorization_id": AUTHORIZATION_ID,
                          "grant_file_present": script.with_name(GRANT_FILE).is_file()}))
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
            require(completed.returncode in (0, 2), "install_transport_failed")
            result = json.loads(completed.stdout)
            require(result.get("schema") == SCHEMA and result.get("replay_permitted") is False,
                    "install_receipt_invalid")
        except Exception as error:
            result = {"schema": SCHEMA, "status": "STOP_UNKNOWN", "reason": recovery.safe_reason(error),
                      "replay_permitted": False, "read_only_status_required": True}
            recovery.write_once(args.evidence_root / "install-intent-result.json", result)
            print(json.dumps(result, sort_keys=True))
            return 2
        recovery.write_once(args.evidence_root / "install-intent-result.json", result)
        print(json.dumps(result, sort_keys=True))
        return completed.returncode
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
