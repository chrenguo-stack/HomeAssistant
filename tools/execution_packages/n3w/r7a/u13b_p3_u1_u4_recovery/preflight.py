"""Inspect this P3 U4 transaction and its mounted media without sending INSTALL."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

import executor as recovery

U4 = "U4_READY_TO_INSTALL"
U4_SHA = "00167d489d785af6a458cd09826b9293dc29ec6c85b02ac75772017633d6f154"
RECOVERY_BLOB = "deb0f1536b4e884993cb2b72b60df4b43623b27f"
SCHEMA = "gh.n3w-t1-u13b-p3-u5-readonly-preflight/1"
RUNTIME = Path("/run/n3w-t1-ota")
INSTALLED = Path("/opt/HomeAssistant/tools")
APPROVED = Path("/etc/n3w-t1-ota/approved-homeassistant.json")
TX_NAME = "homeassistant-usb-upgrade.json"
require = recovery.require
run = recovery.run


def read_private(path, *, size=None):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o077,
                "private_file_metadata_invalid")
        if size is None:
            limit = 256 * 1024
            data = stream.read(limit + 1)
            require(0 < len(data) <= limit and len(data) == info.st_size, "private_record_size_invalid")
            return data
        require(info.st_size == size, "target_archive_size_drift")
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_object(path):
    def reject_duplicates(pairs):
        value = dict(pairs)
        require(len(value) == len(pairs), "private_record_duplicate_field")
        return value

    value = json.loads(read_private(path), object_pairs_hook=reject_duplicates)
    require(isinstance(value, dict), "private_record_invalid")
    return value


def bind_ledger(plan):
    original = recovery.STATE / plan["original_root"]
    for path in (recovery.STATE, original, recovery.RECOVERY_ROOT):
        recovery.private_path(path, directory=True)
    original_claim = read_object(original / "authorization_claim.json")
    require(original_claim.get("authorization_id") == plan["original_authorization_id"]
            and original_claim.get("execution_id") == plan["original_execution_id"]
            and original_claim.get("claimed") is True
            and original_claim.get("consumed") is True
            and original_claim.get("replay_permitted") is False,
            "original_ledger_drift")
    claim = read_object(recovery.RECOVERY_ROOT / "authorization_claim.json")
    terminal = read_object(recovery.RECOVERY_ROOT / "result.json")
    require(claim == {
        "authorization_id": recovery.RECOVERY_ID, "consumed": True, "replay_permitted": False,
        "original_execution_id": plan["original_execution_id"], "u1_sha256": recovery.U1_SHA256,
    }, "recovery_claim_drift")
    require(terminal.get("status") == "U4_RECOVERY_PASS"
            and terminal.get("transaction_phase") == U4
            and terminal.get("transaction_sha256") == U4_SHA
            and terminal.get("target_archive_sha256") == plan["target"]["target_archive_sha256"]
            and terminal.get("new_filesystem_uuid_verified") is True
            and terminal.get("runtime_containers_unchanged") is True
            and terminal.get("stop_before_u5") is True
            and terminal.get("replay_permitted") is False, "recovery_receipt_drift")
    recovery.load_frozen_tools(original / "exact-tools", plan["tools_sha256"])
    return original_claim


def bind_transaction(plan, raw):
    from n3w_t1_core_updater_ha_usb_state import validate_transaction_document
    from n3w_t1_core_updater_ha_usb_media import validate_filesystem_uuid

    require(hashlib.sha256(raw).hexdigest() == U4_SHA, "u4_transaction_sha256_drift")
    tx = validate_transaction_document(json.loads(raw))
    target = plan["target"]
    require(tx["phase"] == U4 and tx["status"] == "ACTIVE"
            and tx["target_artifact_verified"] is True and tx["usb_capacity_verified"] is True
            and tx["authorization_claimed"] is False and tx["authorization_consumed"] is False
            and tx["target_manifest_identity"]["release_identity"] == plan["release"]
            and tx["target_image_ref"] == target["target_image_ref"]
            and tx["target_archive_sha256"] == target["target_archive_sha256"]
            and tx["target_archive_size"] == target["target_archive_size_bytes"]
            and tx["current_image_ref"] == target["expected_predecessor_image_ref"]
            and tx["current_image_identity"]["runtime_image_id"] == plan["predecessor_runtime_id"]
            and tx["usb_device_identity_public_fingerprint"] == plan["usb"]["public_fingerprint"],
            "u4_transaction_binding_drift")
    require(validate_filesystem_uuid(tx["usb_filesystem_uuid"]) != plan["historical_uuid"],
            "historical_u13a_uuid_present_in_transaction")
    return tx


def mount_entry(pid, device, mountpoint):
    entries = []
    for line in Path(f"/proc/{pid}/mountinfo").read_text().splitlines():
        head, tail = line.split(" - ", 1)
        left, right = head.split(), tail.split()
        if left[2] == device or left[4] == str(mountpoint):
            entries.append((left, right))
    require(len(entries) == 1, "usb_mount_missing_or_ambiguous")
    left, right = entries[0]
    options = set(left[5].split(","))
    super_options = set(right[2].split(","))
    require(left[2] == device and left[3] == "/" and left[4] == str(mountpoint)
            and right[0] == "ext4" and {"rw", "nodev", "nosuid", "noexec"} <= options
            and "rw" in super_options and not {"ro", "noload", "norecovery"} & (options | super_options),
            "usb_mount_identity_or_options_drift")
    return {"id": left[0], "options": sorted(options), "super_options": sorted(super_options)}


def bind_media(tx, daemon_pid, *, include_fingerprint=False):
    from n3w_t1_core_updater_ha_prepare_host import (
        SubprocessPrepareBackend, _boolish, _flatten_blocks, _stable_fingerprint,
    )
    from n3w_t1_core_updater_ha_usb_media import USB_LABEL

    uuid = tx["usb_filesystem_uuid"]
    partitions = run("lookup_usb_uuid", [
        "blkid", "-c", "/dev/null", "-t", f"UUID={uuid}", "-o", "device",
    ]).decode().splitlines()
    require(len(partitions) == 1 and re.fullmatch(r"/dev/[A-Za-z0-9._+-]+", partitions[0]),
            "usb_uuid_device_invalid")
    partition = partitions[0]
    info = Path(partition).stat()
    require(stat.S_ISBLK(info.st_mode), "usb_partition_not_block")
    device = f"{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}"
    fs = dict(line.split("=", 1) for line in run("probe_usb_filesystem", [
        "blkid", "-p", "-o", "export", partition,
    ]).decode().splitlines() if "=" in line)
    require((fs.get("UUID"), fs.get("TYPE"), fs.get("LABEL")) == (uuid, "ext4", USB_LABEL),
            "usb_filesystem_identity_drift")
    parent = run("lookup_usb_parent", ["lsblk", "-npo", "PKNAME", partition]).decode().strip()
    roots = SubprocessPrepareBackend()._lsblk()
    disks = [item for item in roots if item.get("type") == "disk" and item.get("path") == parent]
    require(len(disks) == 1, "usb_parent_not_unique")
    disk = disks[0]
    children = _flatten_blocks([disk])
    matching = [item for item in children if item.get("type") == "part"
                and item.get("path") == partition and item.get("maj:min") == device]
    require(len(matching) == 1 and disk.get("tran") == "usb" and _boolish(disk.get("rm"))
            and not _boolish(disk.get("ro")) and not _boolish(matching[0].get("ro")),
            "usb_parent_or_partition_identity_drift")
    root_dev = run("lookup_root_device", ["findmnt", "-no", "MAJ:MIN", "/"]).decode().strip()
    require(root_dev and root_dev not in {item.get("maj:min") for item in children}, "usb_is_root_device")
    mountpoint = RUNTIME / "media" / tx["transaction_id_sha256"][:16]
    local = mount_entry("self", device, mountpoint)
    daemon = mount_entry(daemon_pid, device, mountpoint)
    require(mountpoint.is_dir() and mountpoint.resolve() == mountpoint
            and mountpoint.stat().st_dev == info.st_rdev, "usb_mount_path_drift")
    fingerprint = _stable_fingerprint(disk)
    return mountpoint, {
        "filesystem_uuid": uuid, "mountpoint": str(mountpoint), "device": device,
        "preflight_mount": local, "daemon_mount": daemon,
        "session_fingerprint_matches": fingerprint == tx["usb_device_identity_public_fingerprint"],
        **({"session_fingerprint": fingerprint} if include_fingerprint else {}),
    }


def bind_mirror(mountpoint, tx, *, manifest_fingerprint=None):
    from n3w_t1_core_updater_ha_usb_state import (
        USB_TX_CHECKSUM_SCHEMA, USB_TX_CONTENT_AUTHORITY_SCHEMA, USB_TX_MANIFEST_SCHEMA, USB_TX_PHASE_SCHEMA,
    )

    base = mountpoint / "n3w-update"
    directory = base / "transaction"
    for path in (base, directory):
        recovery.private_path(path, directory=True)
    release = tx["target_manifest_identity"]["release_identity"]
    target = {"target_archive_sha256": tx["target_archive_sha256"],
              "target_archive_size_bytes": tx["target_archive_size"]}
    tx_id = {"transaction_id_sha256": tx["transaction_id_sha256"]}
    expected = {
        "manifest": {
            "schema": USB_TX_MANIFEST_SCHEMA, **tx_id, **target, "release_identity": release,
            "target_image_ref": tx["target_image_ref"], "usb_filesystem_uuid": tx["usb_filesystem_uuid"],
            "usb_device_identity_public_fingerprint": (
                tx["usb_device_identity_public_fingerprint"] if manifest_fingerprint is None else manifest_fingerprint
            ),
        },
        "checksums": {"schema": USB_TX_CHECKSUM_SCHEMA, **target},
        "phase": {"schema": USB_TX_PHASE_SCHEMA, **tx_id, "phase": tx["phase"],
                  "target_artifact_verified": True, "usb_capacity_verified": True},
        "content-authority": {
            "schema": USB_TX_CONTENT_AUTHORITY_SCHEMA, **tx_id, "release_identity": release,
            **{key: tx.get(key) for key in ("target_artifact_identity", "predecessor_recovery_identity",
                                           "ha_data_backup_identity", "recovery_content_manifest_sha256")},
        },
        "host-transaction": tx,
    }
    for name, document in expected.items():
        observed = read_object(directory / f"{name}.json")
        require(json.dumps(observed, sort_keys=True) == json.dumps(document, sort_keys=True),
                f"usb_metadata_drift:{name}")


def service_binding():
    daemon, _ = recovery.ota_daemon()
    fields = dict(line.split("=", 1) for line in run("inspect_ota_service", [
        "systemctl", "show", "n3w-t1-ha-ota.service", "-p", "MainPID", "-p", "SubState",
        "-p", "Result", "-p", "InvocationID", "-p", "NRestarts",
    ]).decode().splitlines() if "=" in line)
    pid = int(fields["MainPID"])
    require(pid > 0 and fields["SubState"] == "running" and fields["Result"] == "success"
            and fields["InvocationID"] == daemon["InvocationID"], "ota_service_process_drift")
    script = str(INSTALLED / "n3w_t1_core_updater_ha_daemon.py").encode()
    require(script in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\x00"),
            "ota_service_exec_binding_drift")
    return pid, {**daemon, **fields}


STATUS_PROBE = """import json, socket
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.settimeout(30)
    client.connect("/run/n3w/t1-ota/ha-ota.sock")
    client.sendall(b'{"schema":"gh.n3w-t1-ha-ota-ipc-request/1","operation":"status"}\\n')
    client.shutdown(socket.SHUT_WR)
    with client.makefile("rb") as stream:
        print(json.dumps(json.loads(stream.readline(8193))))
"""


def ipc_status(manager, version, *, expected_phase="READY_TO_INSTALL"):
    reply = json.loads(run("manager_ota_ipc_status", [
        "docker", "exec", "-u", "999:999", manager, "python3", "-IB", "-c", STATUS_PROBE,
    ], timeout=45))
    require(reply.get("schema") in {"gh.n3w-t1-ha-ota-ipc-response/2", "gh.n3w-t1-ha-ota-ipc-response/3"}
            and reply.get("accepted") is True and reply.get("code") == "status"
            and reply.get("phase") == expected_phase and reply.get("error_code") is None
            and reply.get("installed_version") == version, "ota_ipc_not_ready")
    return reply["phase"]


def installed_binding(plan, tx):
    from n3w_t1_core_updater_ha_daemon import _validated_manifest
    from n3w_t1_core_updater_ha_prepare_host import FixedHostReleasePolicyProvider
    from n3w_t1_core_updater_v2_common import canonical

    # Compare disk files against both the historical deployed baseline and the P3 bundle.
    hashes = {}
    for name in plan["runtime_sources"]:
        path = INSTALLED / name
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
                "installed_ota_source_metadata_invalid")
        hashes[name] = recovery.digest(path)
    try:
        manifest = _validated_manifest(APPROVED)
        target = manifest["target"]
        admission_matches = (
            manifest.get("release_identity") == plan["release"]
            and manifest.get("target_archive_size_bytes") == tx["target_archive_size"]
            and target.get("expected_predecessor_image_ref") == tx["current_image_ref"]
            and hashlib.sha256(canonical(target)).hexdigest()
            == tx["target_manifest_identity"]["target_manifest_sha256"]
        )
    except (OSError, ValueError, RuntimeError) as error:
        admission_matches = False
        approval_error = recovery.safe_reason(error)
    else:
        approval_error = None if admission_matches else "approved_manifest_transaction_drift"
    try:
        FixedHostReleasePolicyProvider().load(tx)
    except (OSError, ValueError, RuntimeError) as error:
        release_policy_error = recovery.safe_reason(error)
    else:
        release_policy_error = None
    return {
        "installed_source_sha256": hashes,
        "installed_matches_p3_bundle": all(hashes[k] == plan["tools_sha256"][k] for k in hashes),
        "installed_matches_prior_reference": all(hashes[k] == v for k, v in plan["prior_source_hashes"].items()),
        "approved_manifest_matches_transaction": admission_matches,
        "approved_manifest_check_error": approval_error,
        "fixed_release_policy_matches_transaction": release_policy_error is None,
        "fixed_release_policy_check_error": release_policy_error,
    }


def preflight(plan, result):
    require(os.geteuid() == 0, "target_root_required")
    result["stage"] = "ledger"
    claim = bind_ledger(plan)
    result["stage"] = "host_transaction"
    tx_path = recovery.STATE / TX_NAME
    raw = read_private(tx_path)
    tx = bind_transaction(plan, raw)
    result["stage"] = "runtime_baseline"
    recovery.check_peers(claim)
    require(claim["peers"]["homeassistant"]["image_ref"] == tx["current_image_ref"]
            and claim["peers"]["homeassistant"]["runtime_image_id"] == plan["predecessor_runtime_id"],
            "p3_ha_predecessor_runtime_drift")
    daemon_pid, daemon = service_binding()
    deployment = installed_binding(plan, tx)
    result["stage"] = "usb_mount_and_transaction_mirror"
    mountpoint, media = bind_media(tx, daemon_pid)
    bind_mirror(mountpoint, tx)
    result["stage"] = "target_archive"
    target_dir = mountpoint / "n3w-update" / "target"
    recovery.private_path(target_dir, directory=True)
    target = target_dir / "homeassistant-arm64.tar.gz"
    size = tx["target_archive_size"]
    require(read_private(target, size=size) == tx["target_archive_sha256"], "target_archive_sha256_drift")
    result["stage"] = "ipc_status_and_snapshot_continuity"
    phase = ipc_status(claim["peers"]["manager"]["container_id"], plan["predecessor_version"])
    require(service_binding() == (daemon_pid, daemon), "ota_service_changed_during_preflight")
    recovery.check_peers(claim)
    require(read_private(tx_path) == raw and bind_media(tx, daemon_pid) == (mountpoint, media),
            "transaction_or_mount_changed_during_preflight")
    bind_mirror(mountpoint, tx)
    require(installed_binding(plan, tx) == deployment, "installed_source_changed_during_preflight")
    result.update(
        status="P3_U5_READONLY_PREFLIGHT_PASS", stage="u4_verified", transaction_phase=U4,
        transaction_sha256=U4_SHA, target_archive_sha256=tx["target_archive_sha256"],
        target_archive_size_bytes=size, usb_metadata_matches=True, usb_binding=media, daemon=daemon,
        ipc_phase=phase, runtime_containers_match_p3_claim=True, runtime_admission=deployment,
    )


def initial_receipt():
    return {"schema": SCHEMA, "status": "STOP", "read_only": True, "u5_transition": False,
            "authorization_claimed": False, "authorization_consumed": False}


def remote_main(encoded):
    result = initial_receipt()
    try:
        preflight(json.loads(base64.b64decode(encoded, validate=True)), result)
    except Exception as error:
        result["reason"] = recovery.safe_reason(error)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "P3_U5_READONLY_PREFLIGHT_PASS" else 2


def build_plan(expected_commit):
    script = Path(__file__).resolve()
    root = script.parents[5]
    plan = recovery.local_plan(root, expected_commit)
    recovery_script = Path(recovery.__file__).resolve()
    require(recovery.run("recovery_source_binding", [
        "git", "-C", str(root), "hash-object", str(recovery_script),
    ]).decode().strip() == RECOVERY_BLOB, "p3_recovery_source_drift")
    original = root / recovery.BASE_PACKAGE
    live = json.loads(run("p3_original_manifest", [
        "git", "-C", str(root), "show", f"{recovery.BASE_COMMIT}:{original.relative_to(root)}",
    ]))
    plan["predecessor_runtime_id"] = live["expected_terminal_u13a"]["target_runtime_image_id"]
    plan["predecessor_version"] = "2026.10.4"
    prior_path = script.parent.parent / "u11_target_install_readonly_preflight_r39" / "manifest.json"
    prior = json.loads(prior_path.read_bytes())["installed_source_sha256"]
    plan["prior_source_hashes"] = {Path(path).name: sha for path, sha in prior.items()}
    plan["runtime_sources"] = sorted({
        *plan["prior_source_hashes"], "n3w_t1_core_updater_ha_daemon.py",
    })
    return plan


def local_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--mode", choices=("source-check", "read-only"), default="source-check")
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--evidence-root", type=Path)
    args = parser.parse_args()
    script = Path(__file__).resolve()
    root = script.parents[5]
    plan = build_plan(args.expected_commit)
    recovery_script = Path(recovery.__file__).resolve()
    sources = [base64.b64encode(path.read_bytes()).decode("ascii") for path in (recovery_script, script)]
    bootstrap = (
        "import base64, sys, types\n"
        "recovery = types.ModuleType('executor'); sys.modules['executor'] = recovery\n"
        f"exec(compile(base64.b64decode({sources[0]!r}), '<recovery>', 'exec'), recovery.__dict__)\n"
        f"exec(compile(base64.b64decode({sources[1]!r}), '<preflight>', 'exec'))\n"
    )
    compile(bootstrap, "<preflight-bootstrap>", "exec")
    if args.mode == "source-check":
        print(json.dumps({"status": "SOURCE_CHECK_PASS", "transaction_sha256": U4_SHA}))
        return 0

    require(all((args.t1_ssh_target, args.known_hosts, args.expected_host_key_sha256, args.evidence_root)),
            "missing_operator_connection_inputs")
    os.umask(0o077)
    sys.path.insert(0, str(root / "tools"))
    from n3w_t1_ssh_transport import SSHTransport

    transport = SSHTransport(target=args.t1_ssh_target, known_hosts=args.known_hosts,
                             expected_host_key_sha256=args.expected_host_key_sha256)
    args.evidence_root.mkdir(mode=0o700)
    encoded = base64.b64encode(json.dumps(plan).encode()).decode("ascii")
    transport.start_epoch()
    try:
        completed = transport.run_remote(
            ["python3", "-I", "-B", "-c", bootstrap, "--remote", encoded], timeout=600, check=False,
        )
        require(completed.returncode in (0, 2), "preflight_ssh_failed")
        result = json.loads(completed.stdout)
        require(result.get("schema") == SCHEMA and result.get("read_only") is True
                and result.get("u5_transition") is False
                and result.get("authorization_claimed") is False
                and (result.get("status") == "P3_U5_READONLY_PREFLIGHT_PASS") == (completed.returncode == 0),
                "preflight_receipt_invalid")
        recovery.write_once(args.evidence_root / "p3-u5-readonly-result.json", result)
        public = {key: result[key] for key in (
            "status", "stage", "reason", "transaction_phase", "transaction_sha256", "target_archive_sha256",
            "usb_metadata_matches", "ipc_phase", "runtime_containers_match_p3_claim",
        ) if key in result}
        if "runtime_admission" in result:
            public.update({key: value for key, value in result["runtime_admission"].items()
                           if key != "installed_source_sha256"})
            public["session_fingerprint_matches"] = result["usb_binding"]["session_fingerprint_matches"]
        print(json.dumps(public, sort_keys=True))
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
