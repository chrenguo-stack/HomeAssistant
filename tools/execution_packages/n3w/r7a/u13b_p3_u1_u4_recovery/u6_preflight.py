"""Read-only entry to U6 for the exact P3 transaction verified at U5."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import executor as recovery
import install_intent
import preflight

SCHEMA = "gh.n3w-t1-u13b-p3-u6-readonly-preflight/1"
U5_SHA = "53141824bb5bd89f0911e217900ad50acee44cf6ef0ead891e867042a89dfe12"
U5_RECEIPT_SHA = "cfef0e884513b93defb184bee46b46bb17268ab789a3b9abdbf3656604ea9577"
U5_CANDIDATE = "63e2c470eace97bfb15c0e7ff9ad7380e6884668"
IPC_PHASE = "INSTALL_REQUESTED_REVALIDATING"
PASS = "P3_U6_READONLY_PREFLIGHT_PASS"
require = recovery.require


def bind_u5_receipt():
    root = install_intent.ledger_root()
    recovery.private_path(root, directory=True)
    claim = preflight.read_object(root / "claim.json")
    require(claim == {
        "schema": install_intent.SCHEMA,
        "authorization_id": install_intent.AUTHORIZATION_ID,
        "candidate_commit": U5_CANDIDATE,
        "preflight_receipt_sha256": install_intent.PREFLIGHT_SHA,
        "u4_transaction_sha256": preflight.U4_SHA,
        "u5_transaction_sha256": U5_SHA,
        "claimed": True, "consumed": True, "replay_permitted": False,
    }, "u5_install_intent_claim_drift")
    receipt = preflight.read_private(root / "result.json")
    require(install_intent.digest_bytes(receipt) == U5_RECEIPT_SHA, "u5_install_intent_receipt_drift")


def bind_u5_transaction(plan, raw):
    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document

    require(install_intent.digest_bytes(raw) == U5_SHA, "u5_transaction_digest_drift")
    tx = validate_transaction_document(json.loads(raw))
    target = plan["target"]
    require(
        tx["phase"] == install_intent.U5 and tx["status"] == "ACTIVE"
        and tx["target_artifact_verified"] is True and tx["usb_capacity_verified"] is True
        and tx["authorization_claimed"] is False and tx["authorization_consumed"] is False
        and tx["authorization_id_sha256"] is None
        and tx.get("predecessor_recovery_identity") is None and tx.get("ha_data_backup_identity") is None
        and tx.get("recovery_content_manifest_sha256") is None
        and tx["target_manifest_identity"] == {
            "release_identity": plan["release"], "target_manifest_sha256": plan["target_manifest_sha256"],
            "target_image_ref": target["target_image_ref"], "target_archive_sha256": target["target_archive_sha256"],
        }
        and tx["target_image_ref"] == target["target_image_ref"]
        and tx["target_archive_sha256"] == target["target_archive_sha256"]
        and tx["target_archive_size"] == target["target_archive_size_bytes"]
        and tx["current_image_ref"] == target["expected_predecessor_image_ref"]
        and tx["current_image_identity"] == {
            "runtime_image_id": plan["predecessor_runtime_id"], "platform": "linux/arm64",
        }
        and tx["usb_filesystem_uuid"] != plan["historical_uuid"]
        and tx["usb_device_identity_public_fingerprint"] == plan["usb"]["public_fingerprint"],
        "u5_transaction_binding_drift",
    )
    return tx


def owner_units():
    records = {}
    for unit in ("n3wfc4-services-activation.service", "n3wfc4-broker-activation.service"):
        keys = ("ActiveState", "SubState", "Result", "InvocationID", "NRestarts")
        value = recovery.run("inspect_owner_unit", ["systemctl", "show", unit, "-p", ",".join(keys)])
        fields = dict(line.split("=", 1) for line in value.decode().splitlines() if "=" in line)
        require(fields.get("ActiveState") == "active" and fields.get("SubState") == "running"
                and fields.get("Result") == "success" and fields.get("NRestarts") == "0"
                and bool(fields.get("InvocationID")), "runtime_owner_unit_unhealthy")
        records[unit] = fields
    return records


def image_binding(tx):
    from n3w_t1_core_updater_host import LocalHost

    image = tx["current_image_ref"]
    require(LocalHost().component_binding_v2("homeassistant") == image, "ha_predecessor_compose_binding_drift")
    values = json.loads(recovery.run("inspect_predecessor_image", ["docker", "image", "inspect", image]))
    require(len(values) == 1 and values[0].get("Id") == tx["current_image_identity"]["runtime_image_id"]
            and values[0].get("Os") == "linux" and values[0].get("Architecture") == "arm64",
            "ha_predecessor_image_identity_drift")
    target = recovery.run("list_target_image", [
        "docker", "image", "ls", "-q", "--filter", "reference=" + tx["target_image_ref"],
    ])
    require(not target.strip(), "u6_target_image_already_present")


def require_empty_recovery_dirs(mount):
    for name in ("predecessor", "ha-data"):
        path = mount / "n3w-update" / name
        if os.path.lexists(path):
            recovery.private_path(path, directory=True)
            require(next(path.iterdir(), None) is None, f"unexpected_u6_residue:{name}")


def validate_capacity(mount, tx, plan):
    from n3w_t1_core_updater_ha_capacity import compute_install_revalidation, validate_install_revalidation
    from n3w_t1_core_updater_ha_prepare_host import DEFAULT_HA_DATA_ROOT, SubprocessPrepareBackend, measure_ha_data_tree

    free = SubprocessPrepareBackend._filesystem_space(mount)[1]
    evidence = compute_install_revalidation(
        target_artifact_bytes=tx["target_archive_size"],
        predecessor_recovery_budget_bytes=plan["predecessor_recovery_budget_bytes"],
        ha_data_measured_bytes=measure_ha_data_tree(DEFAULT_HA_DATA_ROOT),
        observed_usb_free_bytes=free,
    )
    return validate_install_revalidation(evidence, expected_target_artifact_bytes=tx["target_archive_size"])


def inspect(plan, result):
    require(os.geteuid() == 0, "target_root_required")
    result["stage"] = "bind_durable_u5"
    claim = preflight.bind_ledger(plan)
    bind_u5_receipt()
    tx_path = recovery.STATE / preflight.TX_NAME
    before = preflight.read_private(tx_path)
    tx = bind_u5_transaction(plan, before)

    result["stage"] = "bind_runtime_usb_and_u5_mirror"
    recovery.check_peers(claim)
    units = owner_units()
    pid, daemon = preflight.service_binding()
    deployed = preflight.installed_binding(plan, tx)
    require(deployed["installed_matches_prior_reference"] is True, "installed_sources_drift")
    image_binding(tx)
    mount, media = preflight.bind_media(tx, pid)
    require(media["session_fingerprint_matches"] is True, "p3_usb_session_drift")
    preflight.bind_mirror(mount, tx)
    require_empty_recovery_dirs(mount)

    result["stage"] = "verify_target_and_capacity"
    target = mount / "n3w-update" / "target" / "homeassistant-arm64.tar.gz"
    recovery.private_path(target.parent, directory=True)
    identity = install_intent.archive_stat(target)
    require(preflight.read_private(target, size=tx["target_archive_size"]) == tx["target_archive_sha256"],
            "u6_target_archive_drift")
    capacity = validate_capacity(mount, tx, plan)
    phase = preflight.ipc_status(claim["peers"]["manager"]["container_id"],
                                 plan["predecessor_version"], expected_phase=IPC_PHASE)

    result["stage"] = "verify_readonly_continuity"
    install_intent.check_continuity(
        plan, claim, {"daemon": daemon, "usb_binding": media, "runtime_admission": deployed}, tx, target, identity,
    )
    image_binding(tx)
    require(preflight.read_private(tx_path) == before and owner_units() == units, "u6_preflight_state_drift")
    preflight.bind_mirror(mount, tx)
    require_empty_recovery_dirs(mount)
    result.update(status=PASS, stage="u5_verified_for_u6", transaction_phase=tx["phase"],
                  transaction_sha256=U5_SHA, u5_receipt_sha256=U5_RECEIPT_SHA, usb_metadata_matches=True,
                  target_archive_sha256=tx["target_archive_sha256"], capacity_pass=True,
                  usb_free_bytes=capacity.observed_usb_free_bytes,
                  usb_required_remaining_bytes=capacity.required_remaining_bytes,
                  ipc_phase=phase, predecessor_binding_verified=True, runtime_continuity_verified=True)


def remote_main(encoded):
    result = {"schema": SCHEMA, "status": "STOP", "read_only": True, "u6_transition": False}
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
    parts = ["import base64, sys, types"]
    for name, module in (("executor", recovery), ("preflight", preflight), ("install_intent", install_intent)):
        payload = base64.b64encode(Path(module.__file__).read_bytes()).decode()
        parts.append(f"sys.modules[{name!r}] = types.ModuleType({name!r})")
        parts.append(f"exec(compile(base64.b64decode({payload!r}), {name!r}, 'exec'), sys.modules[{name!r}].__dict__)")
    payload = base64.b64encode(script.read_bytes()).decode()
    parts.append(f"exec(compile(base64.b64decode({payload!r}), '<u6-preflight>', 'exec'))")
    bootstrap = "\n".join(parts)
    compile(bootstrap, "<u6-preflight-bootstrap>", "exec")
    if args.mode == "source-check":
        print(json.dumps({"status": "SOURCE_CHECK_PASS", "u5_transaction_sha256": U5_SHA}))
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
            ["python3", "-I", "-B", "-c", bootstrap, "--remote", data], timeout=600, check=False,
        )
        require(completed.returncode in (0, 2), "u6_preflight_transport_failed")
        result = json.loads(completed.stdout)
        require(result.get("schema") == SCHEMA and result.get("read_only") is True and result.get("u6_transition") is False
                and result.get("status") == (PASS if completed.returncode == 0 else "STOP"), "u6_preflight_receipt_invalid")
        recovery.write_once(args.evidence_root / "p3-u6-readonly-result.json", result)
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
