from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
BASE_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u6_source_activation_r25" / "executor.py"
)
GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U10_READONLY_PREFLIGHT_R37_20261116_01"
)
MANIFEST_SCHEMA = "gh.n3w-t1-u10-r37-readonly-preflight-manifest/1"
LOCAL_RESULT_SCHEMA = "gh.n3w-t1-u10-r37-local-result/1"
REMOTE_TIMEOUT_SECONDS = 1500


class Stop(RuntimeError):
    pass


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stop("module_load_failed:" + path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_base():
    return load_module(BASE_EXECUTOR, "n3w_r37_base")


REMOTE_SCRIPT = r"""
import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

TX = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
HOST_UNIT = "n3w-t1-ha-ota.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
TOOLS_ROOT = Path("/opt/HomeAssistant/tools")
PROJECT = "n3wfc4"


class Stop(RuntimeError):
    pass


def run(argv, *, timeout=60, check=True):
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        raise Stop("command_failed:" + Path(argv[0]).name + ":" + str(completed.returncode))
    return completed


def sha_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + path.name)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + path.name)
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise Stop("required_file_metadata_invalid:" + path.name)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("required_json_invalid:" + path.name) from error
    if not isinstance(value, dict):
        raise Stop("required_object_invalid:" + path.name)
    return value


def require_unit(unit, *, active):
    value = run(["systemctl", "is-active", unit], check=False).stdout.strip()
    if active and value != "active":
        raise Stop("unit_not_active:" + unit)
    if not active and value not in {"inactive", "failed"}:
        raise Stop("unit_not_quiesced:" + unit)
    return value


def docker_inspect(container_id):
    completed = run(["docker", "inspect", container_id], timeout=45)
    try:
        value = json.loads(completed.stdout)
    except Exception as error:
        raise Stop("docker_inspect_invalid") from error
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise Stop("docker_inspect_shape_invalid")
    return value[0]


def all_container_documents():
    completed = run(["docker", "ps", "-aq", "--no-trunc"], check=False)
    if completed.returncode != 0:
        raise Stop("container_inventory_failed")
    result = {}
    for raw in completed.stdout.splitlines():
        container_id = raw.strip()
        if container_id:
            result[container_id] = docker_inspect(container_id)
    return result


def verify_installed_sources(plan):
    observed = {}
    for raw_path, expected in plan["installed_source_sha256"].items():
        digest = sha_file(raw_path)
        if digest != expected:
            raise Stop("installed_source_drift:" + Path(raw_path).name)
        observed[Path(raw_path).name] = digest
    return observed


def import_product():
    tools = str(TOOLS_ROOT)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_backup import ProtectedHaDataBackupProvider, backup_record_from_document
    from n3w_t1_core_updater_ha_capacity import CapacityPolicy, ceil_ratio_ppm, compute_recovery_admission_capacity, round_up
    from n3w_t1_core_updater_ha_recovery import image_recovery_record_from_document
    from n3w_t1_core_updater_ha_usb import destructive_cutover_allowed
    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document
    return {
        "ProtectedHaDataBackupProvider": ProtectedHaDataBackupProvider,
        "backup_record_from_document": backup_record_from_document,
        "CapacityPolicy": CapacityPolicy,
        "ceil_ratio_ppm": ceil_ratio_ppm,
        "compute_recovery_admission_capacity": compute_recovery_admission_capacity,
        "round_up": round_up,
        "image_recovery_record_from_document": image_recovery_record_from_document,
        "destructive_cutover_allowed": destructive_cutover_allowed,
        "validate_transaction_document": validate_transaction_document,
    }


def verify_transaction_u9(plan, product):
    transaction = read_object(TX)
    product["validate_transaction_document"](transaction)
    if (
        sha_file(TX) != plan["transaction_sha256"]
        or transaction.get("phase") != "U9_LIVE_AUTHORIZATION_CLAIMED"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256") != plan["transaction_id_sha256"]
        or transaction.get("current_image_ref") != plan["predecessor_image"]
        or transaction.get("target_image_ref") != plan["target_image"]
        or transaction.get("target_archive_sha256") != plan["target_archive_sha256"]
        or transaction.get("target_archive_size") != plan["target_archive_size_bytes"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not True
        or transaction.get("predecessor_recovery_identity") != plan["predecessor_identity"]
        or transaction.get("ha_data_backup_verified") is not True
        or transaction.get("ha_data_backup_identity") != plan["backup_identity"]
        or transaction.get("production_prestate_verified") is not True
        or transaction.get("usb_capacity_verified") is not True
        or transaction.get("recovery_content_manifest_sha256") != plan["recovery_content_manifest_sha256"]
        or transaction.get("usb_filesystem_uuid") != plan["filesystem_uuid"]
        or transaction.get("authorization_claimed") is not True
        or transaction.get("authorization_consumed") is not True
        or transaction.get("authorization_id_sha256") != plan["authorization_id_sha256"]
    ):
        raise Stop("u10_r37_u9_transaction_invalid")
    if product["destructive_cutover_allowed"](transaction) is not True:
        raise Stop("u10_r37_destructive_successor_not_eligible")
    return transaction


def verify_no_replay(root, *, gate_id, authorization_id, execution_id, success):
    root = Path(root)
    claim = read_object(root / "authorization_claim.json")
    terminal = read_object(root / ("success.json" if success else "failure.json"))
    if (
        claim.get("gate_id") != gate_id
        or claim.get("authorization_id") != authorization_id
        or claim.get("execution_id") != execution_id
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
        or terminal.get("authorization_claimed") is not True
        or terminal.get("authorization_consumed") is not True
        or terminal.get("replay_permitted") is not False
    ):
        raise Stop("u10_r37_no_replay_ledger_invalid")
    if success:
        if (
            terminal.get("status") != "U9_R36_LIVE_AUTHORIZATION_CLAIM_PASS"
            or terminal.get("u10_plus") is not False
            or terminal.get("destructive_cutover") is not False
            or terminal.get("predecessor_image_delete") is not False
            or terminal.get("target_image_load") is not False
            or terminal.get("service_mutation") is not False
        ):
            raise Stop("u10_r37_r36_terminal_invalid")
    else:
        if (
            terminal.get("status") != "STOP_POSTCLAIM"
            or terminal.get("transaction_mutation") is not False
            or terminal.get("usb_mutation") is not False
            or terminal.get("u9_transition") is not False
            or terminal.get("u10_plus") is not False
        ):
            raise Stop("u10_r37_r35_terminal_invalid")
    return {"claimed": True, "consumed": True, "replay_permitted": False}


def require_bound_mount(plan):
    completed = run(
        ["findmnt", "--noheadings", "--output", "SOURCE,TARGET,FSTYPE,OPTIONS", "--target", plan["mount_target"]],
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("u10_r37_media_not_mounted")
    fields = completed.stdout.strip().split(None, 3)
    if len(fields) != 4:
        raise Stop("u10_r37_mount_probe_invalid")
    source, target, fstype, options = fields
    option_set = set(options.split(","))
    if (
        not source.startswith("/dev/")
        or target != plan["mount_target"]
        or fstype != "ext4"
        or "rw" not in option_set
        or not {"nodev", "nosuid", "noexec"}.issubset(option_set)
    ):
        raise Stop("u10_r37_bound_mount_invalid")
    uuid = run(["blkid", "-s", "UUID", "-o", "value", source]).stdout.strip()
    if uuid != plan["filesystem_uuid"]:
        raise Stop("u10_r37_bound_uuid_drift")
    return {"source_kind": "block_device", "filesystem_uuid": uuid, "target": target}


def verify_usb_mirror_u9(plan, transaction):
    root = Path(plan["mount_target"]) / "n3w-update" / "transaction"
    manifest = read_object(root / "manifest.json")
    phase = read_object(root / "phase.json")
    authority = read_object(root / "content-authority.json")
    checksums = read_object(root / "checksums.json")
    fingerprint = manifest.get("usb_device_identity_public_fingerprint")
    if not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise Stop("u10_r37_session_fingerprint_invalid")
    if (
        manifest.get("transaction_id_sha256") != transaction["transaction_id_sha256"]
        or manifest.get("usb_filesystem_uuid") != transaction["usb_filesystem_uuid"]
        or phase.get("transaction_id_sha256") != transaction["transaction_id_sha256"]
        or phase.get("phase") != "U9_LIVE_AUTHORIZATION_CLAIMED"
        or phase.get("target_artifact_verified") is not True
        or phase.get("usb_capacity_verified") is not True
        or authority.get("transaction_id_sha256") != transaction["transaction_id_sha256"]
        or authority.get("target_artifact_identity") != transaction["target_artifact_identity"]
        or authority.get("predecessor_recovery_identity") != transaction["predecessor_recovery_identity"]
        or authority.get("ha_data_backup_identity") != transaction["ha_data_backup_identity"]
        or authority.get("recovery_content_manifest_sha256") != transaction["recovery_content_manifest_sha256"]
        or checksums.get("target_archive_sha256") != transaction["target_archive_sha256"]
        or checksums.get("target_archive_size_bytes") != transaction["target_archive_size"]
    ):
        raise Stop("u10_r37_usb_mirror_invalid")
    return {
        "exact": True,
        "session_public_fingerprint_cross_session_authority": False,
        "sha256": {
            "manifest": sha_file(root / "manifest.json"),
            "phase": sha_file(root / "phase.json"),
            "content_authority": sha_file(root / "content-authority.json"),
            "checksums": sha_file(root / "checksums.json"),
        },
    }


def verify_archive(path, expected_sha256, expected_size):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("u10_r37_archive_invalid:" + path.name)
    if path.stat().st_size != expected_size:
        raise Stop("u10_r37_archive_size_drift:" + path.name)
    digest = sha_file(path)
    if digest != expected_sha256:
        raise Stop("u10_r37_archive_hash_drift:" + path.name)
    return {"sha256": digest, "size_bytes": expected_size}


def verify_recovery_assets_and_capacity(plan, transaction, product):
    mount = Path(plan["mount_target"])
    target = product["image_recovery_record_from_document"](
        transaction["target_artifact_identity"],
        expected_kind="target",
        expected_image_ref=plan["target_image"],
        expected_archive_sha256=plan["target_archive_sha256"],
    )
    predecessor = product["image_recovery_record_from_document"](
        transaction["predecessor_recovery_identity"],
        expected_kind="predecessor",
        expected_image_ref=plan["predecessor_image"],
        expected_archive_sha256=plan["predecessor_identity"]["archive_sha256"],
    )
    backup = product["backup_record_from_document"](transaction["ha_data_backup_identity"])
    if (
        target.public() != transaction["target_artifact_identity"]
        or predecessor.public() != plan["predecessor_identity"]
        or backup.public() != plan["backup_identity"]
    ):
        raise Stop("u10_r37_recovery_identity_drift")
    target_archive = verify_archive(
        mount / "n3w-update" / "target" / "homeassistant-arm64.tar.gz",
        target.archive_sha256,
        target.archive_size_bytes,
    )
    predecessor_archive = verify_archive(
        mount / "n3w-update" / "predecessor" / "homeassistant-predecessor.tar.gz",
        predecessor.archive_sha256,
        predecessor.archive_size_bytes,
    )
    provider = product["ProtectedHaDataBackupProvider"]()
    verified_backup = provider.verify_backup(
        backup,
        transaction_id_sha256=transaction["transaction_id_sha256"],
        destination_root=mount / "n3w-update" / "ha-data",
    )
    if verified_backup.public() != plan["backup_identity"]:
        raise Stop("u10_r37_backup_identity_drift")
    policy = product["CapacityPolicy"].frozen()
    working = product["round_up"](
        max(
            policy.transaction_working_floor_bytes,
            product["ceil_ratio_ppm"](
                target.archive_size_bytes,
                policy.transaction_working_target_ratio_ppm,
            ),
        ),
        policy.round_up_quantum_bytes,
    )
    statvfs = os.statvfs(mount)
    free_bytes = statvfs.f_bavail * statvfs.f_frsize
    capacity = product["compute_recovery_admission_capacity"](
        target_archive_bytes=target.archive_size_bytes,
        predecessor_archive_bytes=predecessor.archive_size_bytes,
        ha_backup_archive_bytes=backup.archive_size_bytes,
        transaction_working_budget_bytes=working,
        observed_usb_free_bytes=free_bytes,
        policy=policy,
    )
    if capacity.capacity_pass is not True:
        raise Stop("u10_r37_recovery_capacity_not_verified")
    return {
        "target_archive": target_archive,
        "predecessor_archive": predecessor_archive,
        "backup_verified": True,
        "observed_usb_free_bytes": capacity.observed_usb_free_bytes,
        "required_free_after_recovery_assets_bytes": capacity.required_free_after_recovery_assets_bytes,
        "capacity_pass": True,
    }


def verify_runtime_and_release_candidate(plan):
    require_unit(HOST_UNIT, active=True)
    services_owner = require_unit(SERVICES_UNIT, active=False)
    require_unit(BROKER_UNIT, active=True)
    documents = all_container_documents()
    expected = plan["containers"]
    for service in ("broker", "manager", "homeassistant"):
        container_id = expected[service]["container_id"]
        item = documents.get(container_id)
        if item is None:
            raise Stop("u10_r37_expected_container_missing:" + service)
        state = item.get("State")
        config = item.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            not isinstance(state, dict)
            or not isinstance(config, dict)
            or not isinstance(labels, dict)
            or labels.get("com.docker.compose.project") != PROJECT
            or labels.get("com.docker.compose.service") != service
            or item.get("Image") != expected[service]["runtime_image_id"]
            or config.get("Image") != expected[service]["image"]
            or item.get("RestartCount") != 0
        ):
            raise Stop("u10_r37_container_identity_drift:" + service)
    broker = documents[expected["broker"]["container_id"]]
    manager = documents[expected["manager"]["container_id"]]
    homeassistant = documents[expected["homeassistant"]["container_id"]]
    if broker["State"].get("Status") != "running":
        raise Stop("u10_r37_broker_not_running")
    if manager["State"].get("Status") == "running":
        raise Stop("u10_r37_manager_not_quiesced")
    if homeassistant["State"].get("Status") != "exited":
        raise Stop("u10_r37_homeassistant_not_exactly_exited")
    predecessor_id = plan["predecessor_runtime_image_id"]
    users = sorted(
        container_id for container_id, item in documents.items()
        if item.get("Image") == predecessor_id
    )
    expected_ha_id = expected["homeassistant"]["container_id"]
    if users != [expected_ha_id]:
        raise Stop("u10_r37_predecessor_container_allowlist_invalid")
    predecessor = run(["docker", "image", "inspect", plan["predecessor_image"]], timeout=45, check=False)
    if predecessor.returncode != 0:
        raise Stop("u10_r37_predecessor_image_missing")
    try:
        predecessor_doc = json.loads(predecessor.stdout)
    except Exception as error:
        raise Stop("u10_r37_predecessor_image_invalid") from error
    if (
        not isinstance(predecessor_doc, list)
        or len(predecessor_doc) != 1
        or predecessor_doc[0].get("Id") != predecessor_id
    ):
        raise Stop("u10_r37_predecessor_image_identity_drift")
    target = run(["docker", "image", "inspect", plan["target_image"]], timeout=45, check=False)
    if target.returncode == 0:
        raise Stop("u10_r37_target_internal_image_present")
    return {
        "services_owner_state": services_owner,
        "broker_running": True,
        "manager_quiesced": True,
        "homeassistant_exited": True,
        "predecessor_runtime_release_allowlist": [expected_ha_id],
        "predecessor_image_release_allowlist": [predecessor_id],
        "target_internal_image_absent": True,
        "manager_broker_release_forbidden": True,
    }


def run_readonly(plan):
    product = import_product()
    source_hashes = verify_installed_sources(plan)
    transaction = verify_transaction_u9(plan, product)
    r35 = verify_no_replay(
        plan["r35_state_root"],
        gate_id=plan["r35_gate_id"],
        authorization_id=plan["r35_authorization_id"],
        execution_id=plan["r35_execution_id"],
        success=False,
    )
    r36 = verify_no_replay(
        plan["r36_state_root"],
        gate_id=plan["r36_gate_id"],
        authorization_id=plan["r36_authorization_id"],
        execution_id=plan["r36_execution_id"],
        success=True,
    )
    mount = require_bound_mount(plan)
    mirror = verify_usb_mirror_u9(plan, transaction)
    recovery = verify_recovery_assets_and_capacity(plan, transaction, product)
    runtime = verify_runtime_and_release_candidate(plan)
    return {
        "schema": "gh.n3w-t1-u10-r37-readonly-preflight/1",
        "status": "U10_R37_READONLY_PREFLIGHT_PASS",
        "read_only": True,
        "source_hash_count": len(source_hashes),
        "transaction_phase": transaction["phase"],
        "transaction_sha256": sha_file(TX),
        "r35": r35,
        "r36": r36,
        "mount": mount,
        "mirror": mirror,
        "recovery": recovery,
        "runtime": runtime,
        "u10_readonly_eligible": True,
        "u10_destructive_execution_authorized": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "predecessor_runtime_delete": False,
        "predecessor_image_delete": False,
        "target_image_load": False,
        "service_mutation": False,
        "u10_transition": False,
        "u11_plus": False,
        "board_access": False,
        "merge": False,
    }


def main():
    try:
        mode = sys.argv[1]
        plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U10_READONLY_PREFLIGHT_R37_20261116_01"
        ):
            raise Stop("gate_id_invalid")
        if mode != "preflight":
            raise Stop("mode_invalid")
        result = run_readonly(plan)
    except Exception as error:
        result = {
            "schema": "gh.n3w-t1-u10-r37-readonly-preflight/1",
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "read_only": True,
            "u10_readonly_eligible": False,
            "u10_destructive_execution_authorized": False,
            "transaction_mutation": False,
            "usb_mutation": False,
            "predecessor_runtime_delete": False,
            "predecessor_image_delete": False,
            "target_image_load": False,
            "service_mutation": False,
            "u10_transition": False,
            "u11_plus": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "U10_R37_READONLY_PREFLIGHT_PASS" else 2


raise SystemExit(main())
"""


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


def read_manifest(expected_commit: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    readonly_authorized = document.get(
        "real_t1_readonly_execution_authorized"
    )
    if (
        document.get("schema") != MANIFEST_SCHEMA
        or document.get("gate_id") != GATE_ID
        or document.get("read_only_preflight") is not True
        or type(readonly_authorized) is not bool
        or document.get("live_execution_authorized") is not False
        or document.get("authorization_state")
        != {
            "granted": readonly_authorized,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("manifest_gate_invalid")
    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


def remote_preflight(transport, plan):
    payload = base64.b64encode(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    completed = transport.run_remote(
        ["python3", "-B", "-c", REMOTE_SCRIPT, "preflight", payload],
        timeout=REMOTE_TIMEOUT_SECONDS,
        check=False,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    try:
        result = json.loads(lines[-1]) if lines else {}
    except Exception:
        result = {}
    if not isinstance(result, dict) or not result:
        result = {"status": "STOP", "reason": "remote_result_invalid"}
    return completed, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    args = parser.parse_args()
    result: dict[str, Any] = {
        "schema": LOCAL_RESULT_SCHEMA,
        "status": "STOP",
        "read_only": True,
        "t1_access": False,
        "remote_readonly_preflight_invoked": False,
        "u10_destructive_execution_authorized": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "predecessor_runtime_delete": False,
        "predecessor_image_delete": False,
        "target_image_load": False,
        "service_mutation": False,
        "u10_transition": False,
        "u11_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    return_code = 2
    base = load_base()
    try:
        manifest = read_manifest(args.expected_package_commit)
        if manifest["real_t1_readonly_execution_authorized"] is not True:
            raise Stop("r37_real_t1_readonly_execution_not_authorized")
        evidence = base.prepare_evidence_root(args.evidence_root)
        plan = dict(manifest["expected_u9_entry"])
        plan.update(
            {
                "gate_id": GATE_ID,
                "r35_state_root": manifest["r35_state_root"],
                "r36_state_root": manifest["r36_state_root"],
                "mount_target": manifest["mount_target"],
                "installed_source_sha256": manifest["installed_source_sha256"],
            }
        )
        transport_type = base.load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True
        result["remote_readonly_preflight_invoked"] = True
        remote_transport, remote = remote_preflight(transport, plan)
        result["remote_returncode"] = remote_transport.returncode
        result.update(remote)
        base.write_remote_evidence(evidence, "preflight_remote", remote_transport)
        base.write_private_json(evidence / "preflight.json", remote)
        return_code = 0 if remote.get("status") == "U10_R37_READONLY_PREFLIGHT_PASS" else 2
    except Exception as error:
        result.update(status="STOP", reason=type(error).__name__ + ":" + str(error)[:300])
        return_code = 2
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception as cleanup_error:
                result["ssh_master_cleanup"] = False
                result["ssh_master_cleanup_error"] = type(cleanup_error).__name__ + ":" + str(cleanup_error)[:180]
                if return_code == 0:
                    result["status"] = "STOP_POSTSUCCESS_LOCAL"
                    return_code = 2
        try:
            if "evidence" in locals():
                base.write_private_json(evidence / "local_result.json", result)
        except Exception:
            if return_code == 0:
                result["status"] = "STOP_POSTSUCCESS_LOCAL"
                return_code = 2
    print(json.dumps(result, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
