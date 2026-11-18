"""U6-only P3 predecessor recovery from the verified U5 transaction."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import zlib
from pathlib import Path

import executor as recovery
import install_intent
import preflight
import u6_preflight

SCHEMA = "gh.n3w-t1-u13b-p3-u6-predecessor-recovery/1"
AUTHORIZATION_ID = "N3W_T1_U13B_P3_U6_PREDECESSOR_RECOVERY_20261118_01"
PREFLIGHT_SHA = "e9472f04e73e01c46556ce08c8d8d8fa7c1bf905ccb9a52e520eaae70f73f7fb"
GRANT_FILE = "u6_recovery_grant.json"
U6 = "U6_PREDECESSOR_RECOVERY_PREPARING"
IPC_U6 = "PREDECESSOR_RECOVERY_PREPARING"
PASS = "P3_U6_PREDECESSOR_RECOVERY_PASS"
require = recovery.require


def ledger_root():
    return recovery.STATE / "u13b-p3-u6-predecessor-recovery-20261118-01"


def binding(plan):
    return {
        "schema": SCHEMA, "authorization_id": AUTHORIZATION_ID,
        "candidate_commit": plan["candidate_commit"], "preflight_receipt_sha256": PREFLIGHT_SHA,
        "u5_transaction_sha256": u6_preflight.U5_SHA,
        "target_archive_sha256": plan["target"]["target_archive_sha256"], "maximum_phase": U6,
    }


def validate_grant(plan):
    grant = plan.get("grant")
    require(isinstance(grant, dict), "u6_grant_required")
    expected = binding(plan)
    require(set(grant) == set(expected) | {"authorized", "expires_at_unix"}
            and grant["authorized"] is True
            and all(grant[key] == value for key, value in expected.items()), "u6_grant_binding_drift")
    require(type(grant["expires_at_unix"]) is int and grant["expires_at_unix"] > time.time(),
            "u6_grant_expired")


def attach_grant(plan, root, script, head):
    def git(*args):
        return recovery.run("u6_grant_git", ["git", "-C", str(root), *args]).decode().strip()

    path = str(script.with_name(GRANT_FILE).relative_to(root))
    require(git("diff-tree", "--no-commit-id", "--name-status", "-r", head) == "A\t" + path,
            "u6_separate_grant_commit_required")
    plan["candidate_commit"] = git("rev-parse", head + "^")
    plan["grant"] = json.loads(git("show", f"{head}:{path}"))
    validate_grant(plan)


def bound_backend(plan, snapshot):
    from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend

    class AlreadyMountedBackend(SubprocessPrepareBackend):
        def resolve_transaction_media(self, transaction, *, write_required):
            require(write_required and transaction == snapshot["transaction"], "u6_controller_entry_drift")
            pid, _ = preflight.service_binding()
            mount, media = preflight.bind_media(transaction, pid)
            require((mount, media) == (snapshot["mount"], snapshot["usb_binding"]), "u6_mount_drift")
            return PreparedUsbMedia(
                "/dev/block/" + media["device"], transaction["usb_device_identity_public_fingerprint"],
                transaction["usb_filesystem_uuid"], transaction["usb_measured_usable_bytes"], str(mount),
            ).validate()

    provider = recovery.recovery_backend(plan, staged_archive=None, identity=None).policy_provider
    return AlreadyMountedBackend(policy_provider=provider)


def validate_u6_transition(before, after):
    projected = {
        **before, "phase": U6, "updated_at_unix": after["updated_at_unix"],
    }
    require(after == projected and after["updated_at_unix"] >= before["updated_at_unix"],
            "u6_transaction_projection_drift")


def check_binding(plan, snapshot, tx):
    install_intent.check_continuity(
        plan, snapshot["original_claim"], snapshot, tx, snapshot["target_path"], snapshot["target_stat"],
    )
    require(u6_preflight.owner_units() == snapshot["owner_units"], "u6_owner_unit_changed")
    u6_preflight.image_binding(tx)
    preflight.bind_mirror(snapshot["mount"], tx)


def verify_archive(mount, tx, predecessor):
    from n3w_t1_core_updater_ha_recovery import image_recovery_record_from_document

    record = image_recovery_record_from_document(
        predecessor, expected_kind="predecessor", expected_image_ref=tx["current_image_ref"],
    )
    path = mount / "n3w-update" / "predecessor" / "homeassistant-predecessor.tar.gz"
    recovery.private_path(path.parent, directory=True)
    require(preflight.read_private(path, size=record.archive_size_bytes) == record.archive_sha256,
            "u6_predecessor_archive_digest_drift")


def execute(plan, result):
    validate_grant(plan)
    require(os.geteuid() == 0, "target_root_required")
    os.umask(0o077)
    ledger = ledger_root()
    require(not os.path.lexists(ledger), "u6_ledger_exists_never_replay")
    result["stage"] = "fresh_u5_preflight"
    fresh = {}
    snapshot = u6_preflight.inspect(plan, fresh)
    require(fresh["status"] == u6_preflight.PASS, "u6_fresh_preflight_not_pass")

    from n3w_t1_core_updater_ha_install import HaUsbU6PredecessorController
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    store = HaUsbStateStore(recovery.STATE)
    before = snapshot["transaction"]
    backend = bound_backend(plan, snapshot)
    with store.lock():
        result["stage"] = "final_preclaim_binding"
        require(not os.path.lexists(ledger), "u6_ledger_exists_never_replay")
        require(install_intent.digest_bytes(preflight.read_private(store.path)) == u6_preflight.U5_SHA,
                "u6_u5_digest_changed_before_claim")
        check_binding(plan, snapshot, before)
        u6_preflight.require_empty_recovery_dirs(snapshot["mount"])
        u6_preflight.validate_capacity(snapshot["mount"], before, plan)
        validate_grant(plan)

        result["stage"] = "claim_u6_only"
        ledger.mkdir(mode=0o700)
        recovery.sync_dir(ledger.parent)
        recovery.write_once(ledger / "claim.json", {
            **binding(plan), "claimed": True, "consumed": True, "replay_permitted": False,
        })
        result.update(authorization_claimed=True, authorization_consumed=True)

        try:
            result["stage"] = "product_u6_predecessor_recovery"
            controller = HaUsbU6PredecessorController(transaction_store=store, backend=backend)
            completed = controller.prepare_or_resume()
            require(completed.resumed_from_u6 is False, "u6_unexpected_resume")

            result["stage"] = "verify_u6_postcondition"
            raw = preflight.read_private(store.path)
            tx = store.read()
            require(tx == completed.transaction and raw == install_intent.state_bytes(tx),
                    "u6_host_transaction_mismatch")
            validate_u6_transition(before, tx)
            check_binding(plan, snapshot, tx)
            predecessor = completed.predecessor.public()
            verify_archive(snapshot["mount"], tx, predecessor)
            phase = preflight.ipc_status(snapshot["original_claim"]["peers"]["manager"]["container_id"],
                                         plan["predecessor_version"], expected_phase=IPC_U6)
            require(preflight.read_private(store.path) == raw, "u6_host_changed_after_ipc")
            preflight.bind_mirror(snapshot["mount"], tx)
            result.update(status=PASS, stage="u6_verified", transaction_phase=U6,
                          transaction_sha256=install_intent.digest_bytes(raw), ipc_phase=phase,
                          usb_metadata_matches=True, predecessor=predecessor, runtime_continuity_verified=True)
            recovery.write_once(ledger / "success.json", result)
        except Exception as error:
            result.update(status="STOP_POSTCLAIM", reason=recovery.safe_reason(error), read_only_status_required=True)
            recovery.write_once(ledger / "failure.json", result)
            raise


def inspect(plan, result):
    require(os.geteuid() == 0, "target_root_required")
    ledger = ledger_root()
    require(os.path.lexists(ledger), "u6_ledger_absent")
    recovery.private_path(ledger, directory=True)
    claim = preflight.read_object(ledger / "claim.json")
    require(claim == {
        **binding({**plan, "candidate_commit": claim.get("candidate_commit")}),
        "claimed": True, "consumed": True, "replay_permitted": False,
    } and re.fullmatch(r"[0-9a-f]{40}", claim.get("candidate_commit", "")), "u6_claim_ledger_drift")
    result.update(authorization_claimed=True, authorization_consumed=True)
    preflight.bind_ledger(plan)

    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document

    path = recovery.STATE / preflight.TX_NAME
    raw = preflight.read_private(path)
    tx = validate_transaction_document(json.loads(raw))
    sha = install_intent.digest_bytes(raw)
    result.update(stage="observe_host_and_usb", transaction_phase=tx["phase"], transaction_sha256=sha)
    require(tx["phase"] in {install_intent.U5, U6}, "u6_status_outside_boundary")
    pid, _ = preflight.service_binding()
    mount, _ = preflight.bind_media(tx, pid)
    preflight.bind_mirror(mount, tx)
    result["usb_metadata_matches"] = True
    success_path = ledger / "success.json"
    if not os.path.lexists(success_path):
        result.update(status="P3_U6_NO_DURABLE_PASS", failure_receipt_present=(ledger / "failure.json").is_file())
        return
    success = preflight.read_object(success_path)
    require(success.get("status") == PASS and success.get("transaction_phase") == tx["phase"] == U6
            and success.get("transaction_sha256") == sha, "u6_durable_success_drift")
    verify_archive(mount, tx, success["predecessor"])
    require(preflight.read_private(path) == raw, "u6_state_changed_during_status")
    preflight.bind_mirror(mount, tx)
    result.update(status="P3_U6_DURABLE_PASS_VERIFIED", stage="durable_u6_verified",
                  predecessor=success["predecessor"])


def remote_main(mode, encoded):
    result = {"schema": SCHEMA, "status": "STOP", "read_only": mode == "status", "u7_plus": False,
              "authorization_claimed": None, "authorization_consumed": None, "replay_permitted": False}
    try:
        plan = json.loads(base64.b64decode(encoded, validate=True))
        (execute if mode == "execute" else inspect)(plan, result)
    except Exception as error:
        result.update(status="STOP_POSTCLAIM" if result["authorization_claimed"] else "STOP",
                      reason=recovery.safe_reason(error))
        if result["authorization_claimed"] is not True and not os.path.lexists(ledger_root()):
            result.update(authorization_claimed=False, authorization_consumed=False)
        if mode == "execute" and result["authorization_claimed"] is not False:
            result["read_only_status_required"] = True
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["status"] in {PASS, "P3_U6_DURABLE_PASS_VERIFIED"} else 2


def make_bootstrap(script):
    modules = {
        name: Path(module.__file__).read_text()
        for name, module in (("executor", recovery), ("preflight", preflight), ("install_intent", install_intent),
                             ("u6_preflight", u6_preflight))
    }
    modules["__main__"] = script.read_text()
    source = base64.b64encode(zlib.compress(json.dumps(modules).encode())).decode()
    bootstrap = (
        "import base64,json,sys,types,zlib\n"
        f"for name,source in json.loads(zlib.decompress(base64.b64decode({source!r}))).items():\n"
        "    module = sys.modules['__main__'] if name == '__main__' else types.ModuleType(name)\n"
        "    sys.modules[name] = module\n"
        "    exec(compile(source, name, 'exec'), module.__dict__)\n"
    )
    compile(bootstrap, "<u6-recovery-bootstrap>", "exec")
    return bootstrap


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
    bootstrap = make_bootstrap(script)
    if args.mode == "source-check":
        print(json.dumps({"status": "SOURCE_CHECK_PASS", "u6_grant_present": script.with_name(GRANT_FILE).is_file()}))
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
                timeout=5400 if args.mode == "execute" else 600, check=False,
            )
            require(completed.returncode in (0, 2), "u6_transport_failed")
            receipt = json.loads(completed.stdout)
            pass_status = PASS if args.mode == "execute" else "P3_U6_DURABLE_PASS_VERIFIED"
            require(receipt.get("schema") == SCHEMA and receipt.get("replay_permitted") is False
                    and receipt.get("u7_plus") is False and receipt.get("read_only") is (args.mode == "status")
                    and (receipt.get("status") == pass_status) == (completed.returncode == 0), "u6_receipt_invalid")
            rc = completed.returncode
        except Exception as error:
            receipt = {"schema": SCHEMA, "status": "STOP_UNKNOWN", "reason": recovery.safe_reason(error),
                       "replay_permitted": False, "read_only_status_required": True}
            rc = 2
        recovery.write_once(args.evidence_root / "p3-u6-recovery-result.json", receipt)
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
