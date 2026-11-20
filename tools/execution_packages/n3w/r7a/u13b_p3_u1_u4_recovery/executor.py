from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

BASE_COMMIT = "cddadc5bff1a00d4392de33680a5b0ad0acace1e"
BASE_PACKAGE = "tools/execution_packages/n3w/r7a/u13b_p3_live_to_u11/manifest.json"
BASE_TREE_MANIFEST_BLOB = "86af0c73d7919b2f1bcc61106737853f18919863"
RECOVERY_ID = "N3W_T1_U13B_P3_U1_TO_U4_USB_RECOVERY_20261118_01"
CONFIRMATION = "EXECUTE P3 U1 TO U4 USB RECOVERY: YES"
U1_SHA256 = "f5fb674156bb8b97a1841db3a96c39a80b5e69bf59a786a127702c4a2e7bfa1d"
STATE = Path("/var/lib/n3w-t1-core-updater")
RECOVERY_ROOT = STATE / "u13b-p3-u1-u4-recovery-20261118-01"
PEERS = {
    "homeassistant": "n3wfc4-homeassistant-1",
    "manager": "n3wfc4-manager-1",
    "broker": "n3wfc4-broker-1",
}


class Stop(RuntimeError):
    pass


def require(condition, reason):
    if not condition:
        raise Stop(reason)


def run(stage, arguments, *, input_bytes=None, timeout=60):
    try:
        completed = subprocess.run(
            arguments, input=input_bytes, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout, check=False,
        )
    except FileNotFoundError:
        raise Stop(f"{stage}:missing") from None
    except subprocess.TimeoutExpired:
        raise Stop(f"{stage}:timeout") from None
    if completed.returncode:
        raise Stop(f"{stage}:exit_{completed.returncode}")
    return completed.stdout


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def private_path(path, *, directory=False):
    info = path.lstat()
    matches = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    require(matches and info.st_uid == 0 and not info.st_mode & 0o077,
            "private_path_invalid")


def read_record(path):
    private_path(path)
    require(path.stat().st_size <= 2 * 1024 * 1024, "record_too_large")
    return json.loads(path.read_bytes())


def sync_dir(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_once(path, document):
    with path.open("xb") as stream:
        stream.write((json.dumps(document, sort_keys=True) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
    sync_dir(path.parent)


def load_frozen_tools(path, expected):
    private_path(path, directory=True)
    require({item.name for item in path.iterdir()} == set(expected),
            "frozen_tools_file_set_drift")
    for name, sha256 in expected.items():
        require(Path(name).name == name, "frozen_tool_name_invalid")
        item = path / name
        private_path(item)
        require(digest(item) == sha256, "frozen_tool_digest_drift")
    sys.path.insert(0, str(path))


def disk_signatures(path):
    data = json.loads(run("list_usb_signatures", [
        "wipefs", "--json", "--output", "TYPE,OFFSET", path,
    ]))
    require(isinstance(data.get("signatures"), list), "signature_inventory_invalid")
    return data["signatures"]


def device_unused(path):
    require(stat.S_ISBLK(Path(path).lstat().st_mode), "usb_block_device_invalid")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_EXCL | os.O_NOFOLLOW)
    except OSError as error:
        raise Stop(f"usb_exclusive_probe:errno_{error.errno}") from None
    os.close(descriptor)


def check_peers(claim):
    for role, name in PEERS.items():
        items = json.loads(run("inspect_runtime", ["docker", "inspect", "--type", "container", name]))
        require(isinstance(items, list) and len(items) == 1, "runtime_inspect_invalid")
        item = items[0]
        current = {
            "container_id": item["Id"],
            "image_ref": item["Config"]["Image"],
            "runtime_image_id": item["Image"],
            "state": item["State"]["Status"],
            "restart_count": item["RestartCount"],
        }
        require(current["state"] == "running" and current == claim["peers"][role],
                f"runtime_drift:{role}")


def ota_daemon():
    state = dict(line.split("=", 1) for line in run("inspect_ota_daemon", [
        "systemctl", "show", "n3w-t1-ha-ota.service",
        "--property=ActiveState,InvocationID,ExecMainStartTimestampMonotonic",
    ]).decode().splitlines() if "=" in line)
    started_us = int(state["ExecMainStartTimestampMonotonic"])
    require(state["ActiveState"] == "active" and bool(state["InvocationID"])
            and 0 < started_us <= time.monotonic() * 1_000_000,
            "ota_daemon_runtime_invalid")
    return state, time.time() - time.monotonic() + started_us / 1_000_000


def select_usb(backend, public):
    from n3w_t1_core_updater_ha_usb_media import classify_candidate

    candidates = backend.inventory()
    require(len(candidates) == 1, "usb_inventory_not_single")
    candidate = candidates[0]
    require(candidate.public() == public and not classify_candidate(candidate.as_media_candidate()),
            "usb_identity_or_eligibility_drift")
    return candidate


def verify_blank_media(backend, public):
    candidate = select_usb(backend, public)
    disk = candidate.locator
    device_unused(disk)
    require(not disk_signatures(disk), "on_disk_partition_table_or_signature_present")
    rows = json.loads(run("read_kernel_partitions", [
        "lsblk", "--list", "--json", "--paths", "--output", "PATH,TYPE", disk,
    ]))["blockdevices"]
    parts = [item["path"] for item in rows if item["type"] == "part"]
    require(len(parts) <= 1 and all(row["type"] in {"disk", "part"} for row in rows),
            "usb_kernel_topology_unexpected")
    if parts:
        device_unused(parts[0])
        require(not disk_signatures(parts[0]), "kernel_partition_signature_present")
    return candidate


def verify_partition_layout(disk, partition):
    table = json.loads(run("read_new_gpt", ["sfdisk", "--json", disk]))["partitiontable"]
    parts = table["partitions"]
    require(table["label"] == "gpt" and table["unit"] == "sectors"
            and len(parts) == 1 and parts[0]["node"] == partition,
            "new_gpt_identity_drift")
    row = parts[0]
    sector_size = int(run("read_logical_sector_size", ["blockdev", "--getss", disk]))
    sysfs = Path("/sys/class/block") / Path(partition).name
    start_bytes = int((sysfs / "start").read_text()) * 512
    size_bytes = int((sysfs / "size").read_text()) * 512
    require(row["start"] * sector_size == start_bytes
            and row["size"] * sector_size == size_bytes and size_bytes > 0
            and sysfs.resolve().parent.name == Path(disk).name,
            "kernel_partition_extent_drift")


def create_gpt(backend, public, disk):
    run("create_gpt", [
        "sfdisk", "--lock=yes", "--wipe", "never", "--wipe-partitions", "never", disk,
    ], input_bytes=b"label: gpt\n,;\n", timeout=90)
    run("settle_partition_events", ["udevadm", "settle", "--timeout=25"])
    require(select_usb(backend, public).locator == disk, "usb_locator_drift")
    partition = backend._partition(disk)
    verify_partition_layout(disk, partition)
    device_unused(partition)
    require(not disk_signatures(partition), "new_partition_has_existing_signature")
    return partition


def recovery_backend(plan, staged_archive, identity):
    from n3w_t1_core_updater_ha_capacity import CapacityPolicy
    from n3w_t1_core_updater_ha_prepare_host import HostReleasePolicy, SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
    from n3w_t1_core_updater_v2_common import canonical, sha256_bytes

    class PolicyProvider:
        def load(self, transaction):
            target = plan["target"]
            release = plan["release"]
            require(
                transaction["target_manifest_identity"]["release_identity"] == release
                and transaction["target_image_ref"] == target["target_image_ref"]
                and transaction["current_image_ref"] == target["expected_predecessor_image_ref"]
                and transaction["target_archive_sha256"] == target["target_archive_sha256"]
                and transaction["target_archive_size"] == target["target_archive_size_bytes"],
                "staged_policy_binding_drift",
            )
            return HostReleasePolicy(
                release_identity=release,
                artifact_url=f"https://ota.hahub.top/n3w/homeassistant/releases/{release}/homeassistant-arm64.tar.gz",
                target_archive_sha256=target["target_archive_sha256"],
                target_archive_size_bytes=target["target_archive_size_bytes"],
                expected_predecessor_image_ref=target["expected_predecessor_image_ref"],
                predecessor_recovery_budget_bytes=plan["predecessor_recovery_budget_bytes"],
                capacity_policy=CapacityPolicy.frozen(),
            ).validate()

    class StagedBackend(SubprocessPrepareBackend):
        def prepare_target(self, *, transaction, media):
            self._require_bound_media(media)
            policy = self.policy_provider.load(transaction)
            directory = Path(media.mount_path) / "n3w-update" / "target"
            require(not directory.is_symlink(), "target_directory_symlink")
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            private_path(directory, directory=True)
            destination = directory / "homeassistant-arm64.tar.gz"
            require(not destination.exists() and not destination.is_symlink(),
                    "target_archive_already_present")
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".recovery-target-",
                                             delete=False) as temp:
                temporary = Path(temp.name)
                try:
                    with staged_archive.open("rb") as source:
                        shutil.copyfileobj(source, temp, length=1024 * 1024)
                    temp.flush()
                    os.fsync(temp.fileno())
                    require(temporary.stat().st_size == policy.target_archive_size_bytes
                            and digest(temporary) == policy.target_archive_sha256,
                            "copied_target_archive_mismatch")
                    os.replace(temporary, destination)
                    sync_dir(directory)
                finally:
                    temporary.unlink(missing_ok=True)
            self._require_bound_media(media)
            return ImageRecoveryRecord(
                kind="target", image_ref=transaction["target_image_ref"],
                archive_sha256=policy.target_archive_sha256,
                archive_size_bytes=policy.target_archive_size_bytes,
                portable_identity_sha256=sha256_bytes(canonical(identity.to_dict())),
                platform="linux/arm64", verified=True, fsynced=True,
            )

    return StagedBackend(policy_provider=PolicyProvider())


def require_u1(store, prepare_store, plan):
    transaction = store.read()
    require(transaction is not None and digest(store.path) == U1_SHA256
            and transaction["phase"] == "U1_PREPARE_REQUESTED"
            and transaction["status"] == "ACTIVE", "active_u1_transaction_drift")
    prepare = prepare_store.read()
    require(prepare is not None
            and prepare["transaction_id_sha256"] == transaction["transaction_id_sha256"]
            and prepare["confirmation_consumed"] is True
            and prepare["confirmation_required"] is False
            and prepare["candidate"] == plan["usb"], "u1_prepare_confirmation_drift")
    return transaction


def recover(plan, result):
    original = STATE / plan["original_root"]
    private_path(STATE, directory=True)
    private_path(original, directory=True)
    require(not RECOVERY_ROOT.exists() and not RECOVERY_ROOT.is_symlink(),
            "recovery_attempt_already_started")
    claim = read_record(original / "authorization_claim.json")
    failure = read_record(original / "failure.json")
    progress = read_record(original / "progress.json")
    require(claim.get("execution_id") == plan["original_execution_id"]
            and claim.get("authorization_id") == plan["original_authorization_id"]
            and claim.get("consumed") is True and claim.get("claimed") is True
            and claim.get("replay_permitted") is False
            and failure.get("status") == "STOP_POSTCLAIM"
            and failure.get("transaction_phase") == "U1_PREPARE_REQUESTED"
            and failure.get("authorization_consumed") is True
            and progress.get("phase") == "fresh_usb_format_and_target_prepare"
            and not (original / "success.json").exists(),
            "original_consumed_ledger_drift")

    load_frozen_tools(original / "exact-tools", plan["tools_sha256"])
    from n3w_t1_core_updater_ha_prepare import (
        HaUsbPrepareController, PrepareStateStore, PreparedUsbMedia,
        capacity_inputs_from_snapshot, validate_capacity_snapshot,
    )
    from n3w_t1_core_updater_ha_prepare_host import _require_private_directory
    from n3w_t1_core_updater_ha_usb import record_media_bound
    from n3w_t1_core_updater_ha_usb_media import (
        FORMAT_CONFIRMATION, USB_LABEL, assess_capacity, authorize_destructive_format,
        validate_filesystem_uuid,
    )
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
    from n3w_t1_portable_image_identity import parse_image_archive

    store = HaUsbStateStore(STATE)
    prepare_store = PrepareStateStore(STATE)
    transaction = require_u1(store, prepare_store, plan)
    require(failure.get("transaction_id_sha256") == transaction["transaction_id_sha256"],
            "failed_transaction_id_drift")
    staged_directory = original / "staging"
    private_path(staged_directory, directory=True)
    staged = staged_directory / "homeassistant-arm64.tar.gz"
    private_path(staged)
    target = plan["target"]
    result["stage"] = "verify_staged_image"
    identity = parse_image_archive(
        staged, expected_archive_sha256=target["target_archive_sha256"],
        expected_archive_size_bytes=target["target_archive_size_bytes"],
        expected_tag=target["target_image_ref"], platform_os="linux",
        platform_architecture="arm64",
    )
    require(identity.config_semantics_sha256 == target["target_config_semantics_sha256"]
            and identity.rootfs_diff_ids_sha256 == target["target_rootfs_diff_ids_sha256"],
            "target_portable_identity_drift")
    backend = recovery_backend(plan, staged, identity)

    with store.lock():
        result["stage"] = "final_readonly_preflight"
        transaction = require_u1(store, prepare_store, plan)
        check_peers(claim)
        daemon, started_at = ota_daemon()
        require(started_at <= progress["updated_at_unix"], "ota_daemon_restarted_after_stop")
        policy = backend.policy_provider.load(transaction)
        before = validate_capacity_snapshot(
            backend.capacity_snapshot(transaction, calculated_at_unix=int(time.time()))
        )
        candidate = verify_blank_media(backend, plan["usb"])
        require(candidate.display_capacity_bytes >= before["usb_required_bytes"],
                "usb_raw_capacity_insufficient")
        mount_path = backend.runtime_root / "media" / transaction["transaction_id_sha256"][:16]
        require(not mount_path.exists() and not mount_path.is_symlink(), "mount_path_residue")

        result["stage"] = "claim_recovery_authorization"
        RECOVERY_ROOT.mkdir(mode=0o700)
        sync_dir(STATE)
        result["recovery_started"] = True
        write_once(RECOVERY_ROOT / "authorization_claim.json", {
            "authorization_id": RECOVERY_ID, "consumed": True, "replay_permitted": False,
            "original_execution_id": plan["original_execution_id"],
            "u1_sha256": U1_SHA256,
        })
        disk = candidate.locator
        result["stage"] = "create_gpt"
        partition = create_gpt(backend, plan["usb"], disk)
        result["stage"] = "create_ext4"
        run("create_ext4", ["mkfs.ext4", "-L", USB_LABEL, partition], timeout=180)
        run("settle_filesystem_events", ["udevadm", "settle", "--timeout=25"])
        result["stage"] = "verify_new_filesystem"
        fields = dict(line.split("=", 1) for line in run(
            "verify_ext4", ["blkid", "-p", "-o", "export", partition]
        ).decode().splitlines() if "=" in line)
        uuid = validate_filesystem_uuid(fields.get("UUID", "").lower())
        require(fields.get("TYPE") == "ext4" and fields.get("LABEL") == USB_LABEL
                and uuid != plan["historical_uuid"], "new_filesystem_identity_drift")
        require_u1(store, prepare_store, plan)
        check_peers(claim)
        require(ota_daemon()[0] == daemon, "ota_daemon_changed_during_recovery")

        result["stage"] = "mount_and_verify_capacity"
        _require_private_directory(backend.runtime_root, allow_group_read_execute=True)
        _require_private_directory(mount_path.parent, create=True)
        _require_private_directory(mount_path, create=True)
        run("mount_ext4", ["mount", "-o", "nodev,nosuid,noexec", partition, str(mount_path)])
        backend._self_test(mount_path)
        measured, _ = backend._filesystem_space(mount_path)
        media = PreparedUsbMedia(disk, candidate.public_fingerprint, uuid, measured, str(mount_path))
        backend._require_bound_media(media.validate())
        capacity = assess_capacity(measured, capacity_inputs_from_snapshot(
            validate_capacity_snapshot(backend.capacity_snapshot(
                transaction, calculated_at_unix=int(time.time())
            ))
        ))
        require(capacity.capacity_pass is True, "formatted_usb_capacity_insufficient")
        format_authorization = authorize_destructive_format(
            candidate.as_media_candidate(), FORMAT_CONFIRMATION
        )

        result["stage"] = "bind_u2"
        u2 = record_media_bound(
            require_u1(store, prepare_store, plan),
            format_authorization=format_authorization,
            filesystem_uuid=uuid,
            measured_usable_bytes=measured,
            capacity_report=capacity,
        )
        store.write(u2)
        backend.sync_transaction_metadata(u2, media)
        result["stage"] = "prepare_staged_target"
        HaUsbPrepareController(
            transaction_store=store, prepare_store=prepare_store, backend=backend
        ).resume_prepare()
        current = store.read()
        require(current is not None and current["phase"] == "U4_READY_TO_INSTALL"
                and current["status"] == "ACTIVE"
                and current["transaction_id_sha256"] == transaction["transaction_id_sha256"]
                and current["usb_filesystem_uuid"] == uuid
                and current["target_archive_sha256"] == policy.target_archive_sha256,
                "u4_postcondition_drift")
        check_peers(claim)
        require(ota_daemon()[0] == daemon, "ota_daemon_changed_during_recovery")
        result.update(
            stage="u4_verified", status="U4_RECOVERY_PASS",
            transaction_phase=current["phase"], transaction_sha256=digest(store.path),
            target_archive_sha256=policy.target_archive_sha256,
            new_filesystem_uuid_verified=True, runtime_containers_unchanged=True,
            stop_before_u5=True,
        )


def status_result():
    if not RECOVERY_ROOT.exists():
        return {"status": "RECOVERY_NOT_STARTED", "replay_permitted": False}
    private_path(RECOVERY_ROOT, directory=True)
    terminal = RECOVERY_ROOT / "result.json"
    if terminal.exists():
        return read_record(terminal)
    return {"status": "RECOVERY_IN_PROGRESS_OR_INTERRUPTED",
            "replay_permitted": False, "recovery_started": True}


def safe_reason(error):
    reason = str(error)
    if isinstance(error, OSError) and error.errno is not None:
        return f"{type(error).__name__}:errno_{error.errno}"
    return reason if re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9:-]{0,150}", reason) else type(error).__name__


def remote_main(mode, encoded):
    os.umask(0o077)
    if mode == "status":
        result = status_result()
    else:
        result = {
            "status": "STOP", "stage": "verify_original_stop",
            "recovery_started": False, "replay_permitted": False,
        }
        try:
            require(os.geteuid() == 0, "target_root_required")
            recover(json.loads(base64.b64decode(encoded, validate=True)), result)
        except Exception as error:
            result["reason"] = safe_reason(error)
        if result["recovery_started"]:
            write_once(RECOVERY_ROOT / "result.json", result)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if mode == "status" or result["status"] == "U4_RECOVERY_PASS" else 2


def local_plan(root, expected_commit):
    def git(*arguments):
        return run("git_source_check", ["git", "-C", str(root), *arguments])

    require(re.fullmatch(r"[a-f0-9]{40}", expected_commit) is not None
            and git("rev-parse", "HEAD").decode().strip() == expected_commit,
            "recovery_commit_mismatch")
    require(not git("status", "--porcelain", "--untracked-files=no"),
            "recovery_worktree_dirty")
    require(git("rev-parse", f"{BASE_COMMIT}:{BASE_PACKAGE}").decode().strip()
            == BASE_TREE_MANIFEST_BLOB, "original_manifest_binding_drift")
    manifest = json.loads(git("show", f"{BASE_COMMIT}:{BASE_PACKAGE}"))
    source_hashes = {}
    for path, oid in manifest["product_source_authority"].items():
        require(git("rev-parse", f"{BASE_COMMIT}:{path}").decode().strip() == oid,
                "original_product_blob_drift")
        name = Path(path).name
        require(name not in source_hashes, "original_product_name_collision")
        source_hashes[name] = hashlib.sha256(git("show", f"{BASE_COMMIT}:{path}")).hexdigest()
    execution_id = manifest["authorized_execution_id"]
    reuse = manifest["embedded_preflight_manifest"]["single_usb_reuse_after_reset"]
    return {
        "original_root": Path(manifest["state_root_prefix"] + execution_id).name,
        "original_execution_id": execution_id,
        "original_authorization_id": manifest["authorization_id"],
        "tools_sha256": source_hashes,
        "release": manifest["acceptance_release_identity"],
        "target": manifest["acceptance_target"],
        "predecessor_recovery_budget_bytes": manifest["predecessor_recovery_budget_bytes"],
        "historical_uuid": reuse["historical_filesystem_uuid"],
        "usb": {
            "public_fingerprint": reuse["expected_public_fingerprint"],
            "display_model": "Extreme",
            "display_capacity_bytes": 32017047552,
        },
    }


def local_main():
    parser = argparse.ArgumentParser(description="Recover the exact P3 U1 transaction through U4.")
    parser.add_argument("--mode", choices=("source-check", "execute", "status"), default="source-check")
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--confirm")
    args = parser.parse_args()
    script = Path(__file__).resolve()
    root = script.parents[5]
    plan = local_plan(root, args.expected_commit)
    encoded_source = base64.b64encode(script.read_bytes()).decode("ascii")
    if args.mode == "source-check":
        compile(base64.b64decode(encoded_source), script.name, "exec")
        print(json.dumps({"status": "SOURCE_CHECK_PASS", "authorization_id": RECOVERY_ID}))
        return 0
    require(all((args.t1_ssh_target, args.known_hosts, args.expected_host_key_sha256, args.evidence_root)),
            "missing_operator_connection_inputs")
    require(args.mode != "execute" or args.confirm == CONFIRMATION, "recovery_confirmation_mismatch")
    args.evidence_root.mkdir(mode=0o700)
    sys.path.insert(0, str(root / "tools"))
    from n3w_t1_ssh_transport import SSHTransport

    transport = SSHTransport(target=args.t1_ssh_target, known_hosts=args.known_hosts,
                             expected_host_key_sha256=args.expected_host_key_sha256)
    data = base64.b64encode(json.dumps(plan).encode()).decode("ascii")
    remote = f"import base64; exec(compile(base64.b64decode({encoded_source!r}),'<recovery>','exec'))"
    done = threading.Event()

    def heartbeat():
        while not done.wait(30):
            print("T1 recovery command still running; waiting for the remote receipt.", file=sys.stderr)

    transport.start_epoch()
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        completed = transport.run_remote(
            ["python3", "-I", "-B", "-c", remote, "--remote", args.mode, data],
            timeout=3600, check=False,
        )
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        write_once(args.evidence_root / "recovery-result.json", result)
        print(json.dumps(result, sort_keys=True))
        return completed.returncode
    finally:
        done.set()
        transport.close_epoch()


if __name__ == "__main__":
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "--remote":
            raise SystemExit(remote_main(sys.argv[2], sys.argv[3]))
        raise SystemExit(local_main())
    except Exception as error:
        print(json.dumps({"status": "STOP", "reason": safe_reason(error),
                          "replay_permitted": False}, sort_keys=True))
        raise SystemExit(2) from None
