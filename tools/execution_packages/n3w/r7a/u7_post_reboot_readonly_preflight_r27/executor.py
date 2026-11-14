#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
SSH_TRANSPORT_PATH = ROOT / "tools" / "n3w_t1_ssh_transport.py"
GATE_ID = (
    "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
    "U7_POST_REBOOT_READONLY_PREFLIGHT_R27_20261114_01"
)


class Stop(RuntimeError):
    pass


REMOTE_SCRIPT = r'''
import hashlib
import json
import os
import re
import stat
import subprocess
import base64
import sys
import time
from pathlib import Path

TX_PATH = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
R26_ROOT = Path(
    "/var/lib/n3w-t1-core-updater/"
    "u6-r26-predecessor-recovery-20261114-01"
)
HOST_UNIT = "n3w-t1-ha-ota.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
BROKER_UNIT = "n3wfc4-broker-activation.service"
HA_DATA_ROOT = Path("/var/lib/n3wfc4-homeassistant")
SYSTEM_ROOT_KEY = Path(
    "/var/lib/greenhouse-manager/identity/system-root.key"
)
PRODUCT_HA_CONFIG = Path(
    "/opt/HomeAssistant/infra/n3w-t1/production/"
    "homeassistant-configuration.yaml"
)
EXTERNAL_DB_RE = re.compile(rb"(?m)^[ \t]*db_url[ \t]*:")


class Stop(RuntimeError):
    pass


def run(argv, *, timeout=60, check=True, input_bytes=None):
    completed = subprocess.run(
        argv,
        stdin=(
            subprocess.PIPE
            if input_bytes is not None
            else subprocess.DEVNULL
        ),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        raise Stop(
            "command_failed:"
            + Path(argv[0]).name
            + ":"
            + str(completed.returncode)
        )
    return completed


def text(completed):
    return completed.stdout.decode("utf-8", errors="strict").strip()


def sha_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + str(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + str(path))
    payload = path.read_bytes()
    header = ("blob " + str(len(payload)) + "\0").encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def read_private_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Stop("required_file_invalid:" + str(path))
    meta = path.stat()
    if meta.st_uid != 0 or stat.S_IMODE(meta.st_mode) & 0o077:
        raise Stop("required_file_metadata_invalid:" + str(path))
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise Stop("required_json_invalid:" + str(path)) from error
    if not isinstance(value, dict):
        raise Stop("required_object_invalid:" + str(path))
    return value


def service_state(unit):
    completed = run(
        [
            "systemctl",
            "show",
            unit,
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "MainPID",
            "-p",
            "NRestarts",
            "-p",
            "Result",
        ],
        timeout=30,
        check=False,
    )
    result = {"returncode": completed.returncode}
    if completed.returncode == 0:
        for line in text(completed).splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key] = value
    return result


def require_healthy_units():
    units = {
        "host": service_state(HOST_UNIT),
        "services_owner": service_state(SERVICES_UNIT),
        "broker_owner": service_state(BROKER_UNIT),
    }
    for name, observed in units.items():
        if (
            observed.get("returncode") != 0
            or observed.get("ActiveState") != "active"
            or observed.get("SubState") != "running"
            or observed.get("Result") != "success"
            or not str(observed.get("NRestarts", "")).isdigit()
        ):
            raise Stop("unit_not_healthy:" + name)
    return units


def docker_view(expected):
    ids = [
        value.strip()
        for value in text(
            run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    "ancestor=" + expected["image"],
                    "--format",
                    "{{.ID}}",
                ],
                timeout=45,
            )
        ).splitlines()
        if value.strip()
    ]
    if len(ids) != 1:
        raise Stop("container_cardinality_invalid:" + expected["image"])
    documents = json.loads(
        text(run(["docker", "inspect", ids[0]], timeout=45))
    )
    if not isinstance(documents, list) or len(documents) != 1:
        raise Stop("container_inspect_invalid:" + expected["image"])
    item = documents[0]
    state = item.get("State") if isinstance(item.get("State"), dict) else {}
    config = item.get("Config") if isinstance(item.get("Config"), dict) else {}
    observed = {
        "container_id": item.get("Id"),
        "runtime_image_id": item.get("Image"),
        "configured_image_ref": config.get("Image"),
        "status": state.get("Status"),
        "restart_count": item.get("RestartCount"),
    }
    if (
        observed["runtime_image_id"] != expected["runtime_image_id"]
        or observed["configured_image_ref"] != expected["image"]
        or observed["status"] != "running"
        or type(observed["restart_count"]) is not int
        or observed["restart_count"] < 0
    ):
        raise Stop("container_runtime_drift:" + expected["image"])
    return observed


def ipc_status(manager_id):
    probe = r"""import json,socket
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
s.settimeout(10)
s.connect("/run/n3w/t1-ota/ha-ota.sock")
s.sendall(json.dumps({"schema":"gh.n3w-t1-ha-ota-ipc-request/1","operation":"status"},sort_keys=True,separators=(",",":")).encode()+b"\n")
s.shutdown(socket.SHUT_WR)
print(s.recv(8192).decode().strip())"""
    completed = run(
        [
            "docker",
            "exec",
            "-u",
            "999:999",
            manager_id,
            "python3",
            "-c",
            probe,
        ],
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("ipc_status_unavailable:" + str(completed.returncode))
    try:
        value = json.loads(text(completed))
    except json.JSONDecodeError as error:
        raise Stop("ipc_status_invalid") from error
    if (
        not isinstance(value, dict)
        or value.get("accepted") is not True
        or value.get("phase") != "PREDECESSOR_RECOVERY_PREPARING"
        or value.get("error_code") is not None
        or value.get("installed_version") != "2026.10.0"
    ):
        raise Stop("ipc_not_u6_ready")
    return value


def verify_transaction(plan):
    transaction = read_private_json(TX_PATH)
    if (
        transaction.get("phase") != "U6_PREDECESSOR_RECOVERY_PREPARING"
        or transaction.get("status") != "ACTIVE"
        or transaction.get("transaction_id_sha256")
        != plan["transaction_id_sha256"]
        or sha_file(TX_PATH) != plan["transaction_sha256"]
        or transaction.get("target_artifact_verified") is not True
        or transaction.get("predecessor_recovery_verified") is not True
        or transaction.get("ha_data_backup_verified") is not False
        or transaction.get("ha_data_backup_identity") is not None
        or transaction.get("authorization_claimed") is not False
        or transaction.get("authorization_consumed") is not False
        or transaction.get("authorization_id_sha256") is not None
    ):
        raise Stop("u7_u6_transaction_invalid")
    predecessor = transaction.get("predecessor_recovery_identity")
    if predecessor != plan["predecessor_identity"]:
        raise Stop("u7_predecessor_identity_drift")
    return transaction


def verify_r26_terminal(plan):
    claim = read_private_json(R26_ROOT / "authorization_claim.json")
    success = read_private_json(R26_ROOT / "success.json")
    if (
        claim.get("authorization_id") != plan["r26_gate_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
    ):
        raise Stop("r26_claim_invalid")
    if (
        success.get("status") != "U6_R26_PREDECESSOR_RECOVERY_PASS"
        or success.get("authorization_claimed") is not True
        or success.get("authorization_consumed") is not True
        or success.get("replay_permitted") is not False
        or success.get("u6_transition") is not True
        or success.get("u7_plus") is not False
    ):
        raise Stop("r26_success_invalid")
    uptime = float(Path("/proc/uptime").read_text().split()[0])
    boot_started = time.time() - uptime
    success_predates_boot = (
        (R26_ROOT / "success.json").stat().st_mtime < boot_started
    )
    if not success_predates_boot:
        raise Stop("post_reboot_epoch_not_proven")
    return {
        "claim_consumed_no_replay": True,
        "success_status": success.get("status"),
        "success_predates_current_boot": True,
        "current_boot_id_sha256": hashlib.sha256(
            Path("/proc/sys/kernel/random/boot_id")
            .read_text(encoding="utf-8")
            .strip()
            .encode("ascii")
        ).hexdigest(),
        "uptime_seconds": int(uptime),
    }


def verify_installed_u6_sources(plan):
    observed = {}
    for path, expected in plan["installed_u6_source_sha256"].items():
        digest = sha_file(path)
        if digest != expected:
            raise Stop("installed_u6_source_drift:" + Path(path).name)
        observed[path] = digest
    host_path = Path("/opt/HomeAssistant/tools/n3w_t1_core_updater_host.py")
    host_git_blob = git_blob_sha(host_path)
    if host_git_blob != plan["installed_host_git_blob_sha1"]:
        raise Stop("installed_u6_source_drift:n3w_t1_core_updater_host.py")
    observed[str(host_path)] = sha_file(host_path)
    return observed


def flatten(nodes):
    out = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        out.append(node)
        children = node.get("children")
        if isinstance(children, list):
            out.extend(flatten(children))
    return out


def boolish(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return False


def mountpoints(node):
    raw = node.get("mountpoints")
    if isinstance(raw, list):
        return tuple(
            str(value).strip()
            for value in raw
            if isinstance(value, str) and value.strip()
        )
    raw = node.get("mountpoint")
    if isinstance(raw, str) and raw.strip():
        return (raw.strip(),)
    return ()


def discover_media():
    root_mm = text(
        run(["findmnt", "--noheadings", "--output", "MAJ:MIN", "/"])
    )
    document = json.loads(
        text(
            run(
                [
                    "lsblk",
                    "--json",
                    "--bytes",
                    "--paths",
                    "--tree",
                    "--output",
                    "PATH,TYPE,RM,RO,TRAN,MOUNTPOINTS,MAJ:MIN",
                ],
                timeout=30,
            )
        )
    )
    matches = []
    for disk in document.get("blockdevices", []):
        if not isinstance(disk, dict) or disk.get("type") != "disk":
            continue
        if (
            str(disk.get("tran") or "").strip().lower() != "usb"
            or not boolish(disk.get("rm"))
            or boolish(disk.get("ro"))
        ):
            continue
        descendants = flatten([disk])
        if root_mm in {
            str(item.get("maj:min") or "").strip()
            for item in descendants
        }:
            continue
        partitions = [
            item for item in descendants
            if item.get("type") == "part"
            and isinstance(item.get("path"), str)
        ]
        if len(partitions) != 1:
            continue
        partition = str(partitions[0]["path"])
        fstype = run(
            ["blkid", "-s", "TYPE", "-o", "value", partition],
            check=False,
        )
        label = run(
            ["blkid", "-s", "LABEL", "-o", "value", partition],
            check=False,
        )
        if (
            fstype.returncode != 0
            or label.returncode != 0
            or text(fstype) != "ext4"
            or text(label) != "N3W-UPDATE"
        ):
            continue
        points = {
            point
            for item in descendants
            for point in mountpoints(item)
        }
        matches.append(
            {
                "partition": partition,
                "mountpoints": sorted(points),
            }
        )
    if len(matches) != 1:
        raise Stop("content_authority_media_cardinality_invalid")
    return matches[0]


def inspect_media(plan, transaction):
    media = discover_media()
    expected = plan["expected_mount_target"]
    points = media["mountpoints"]
    mounted_by_us = False
    mount_path = None
    runtime_root = Path("/run/n3w-t1-u7-r27")
    temp_path = runtime_root / plan["transaction_id_sha256"][:16]
    try:
        if points:
            if points != [expected]:
                raise Stop("usb_mounted_elsewhere")
            mount_path = Path(expected)
        else:
            if runtime_root.exists():
                if runtime_root.is_symlink() or not runtime_root.is_dir():
                    raise Stop("u7_runtime_mount_root_invalid")
            else:
                runtime_root.mkdir(mode=0o700)
            if temp_path.exists():
                if temp_path.is_symlink() or not temp_path.is_dir():
                    raise Stop("u7_runtime_mount_path_invalid")
            else:
                temp_path.mkdir(mode=0o700)
            run(
                [
                    "mount",
                    "-o",
                    "ro,noload,nodev,nosuid,noexec",
                    media["partition"],
                    str(temp_path),
                ],
                timeout=60,
            )
            mounted_by_us = True
            mount_path = temp_path

        fstype = text(
            run(
                [
                    "findmnt",
                    "--noheadings",
                    "--output",
                    "FSTYPE",
                    "--target",
                    str(mount_path),
                ]
            )
        )
        options = {
            value.strip()
            for value in text(
                run(
                    [
                        "findmnt",
                        "--noheadings",
                        "--output",
                        "OPTIONS",
                        "--target",
                        str(mount_path),
                    ]
                )
            ).split(",")
            if value.strip()
        }
        if (
            fstype != "ext4"
            or not {"nodev", "nosuid", "noexec"}.issubset(options)
            or (
                mounted_by_us
                and (
                    "ro" not in options
                    or not {"noload", "norecovery"}.intersection(options)
                )
            )
        ):
            raise Stop("u7_mount_contract_invalid")

        update = mount_path / "n3w-update"
        phase = read_private_json(update / "transaction" / "phase.json")
        content = read_private_json(
            update / "transaction" / "content-authority.json"
        )
        if (
            phase.get("transaction_id_sha256")
            != plan["transaction_id_sha256"]
            or phase.get("phase")
            != "U6_PREDECESSOR_RECOVERY_PREPARING"
            or phase.get("target_artifact_verified") is not True
            or phase.get("usb_capacity_verified") is not True
            or content.get("transaction_id_sha256")
            != plan["transaction_id_sha256"]
            or content.get("target_artifact_identity")
            != transaction.get("target_artifact_identity")
            or content.get("predecessor_recovery_identity")
            != plan["predecessor_identity"]
            or content.get("ha_data_backup_identity") is not None
            or content.get("recovery_content_manifest_sha256") is not None
        ):
            raise Stop("u7_usb_content_authority_drift")

        target = update / "target" / "homeassistant-arm64.tar.gz"
        predecessor = (
            update / "predecessor" / "homeassistant-predecessor.tar.gz"
        )
        if (
            target.stat().st_size != plan["target_archive_size_bytes"]
            or sha_file(target) != plan["target_archive_sha256"]
            or predecessor.stat().st_size
            != plan["predecessor_identity"]["archive_size_bytes"]
            or sha_file(predecessor)
            != plan["predecessor_identity"]["archive_sha256"]
        ):
            raise Stop("u7_recovery_asset_drift")

        ha_data = update / "ha-data"
        if ha_data.exists() or ha_data.is_symlink():
            if ha_data.is_symlink() or not ha_data.is_dir():
                raise Stop("u7_backup_residue_invalid")
            if any(ha_data.iterdir()):
                raise Stop("u7_backup_residue_present")

        statvfs = os.statvfs(mount_path)
        free_bytes = statvfs.f_bavail * statvfs.f_frsize
        total_bytes = statvfs.f_blocks * statvfs.f_frsize
        return {
            "filesystem_type": fstype,
            "content_authority_exact": True,
            "target_exact": True,
            "predecessor_exact": True,
            "ha_backup_residue_absent": True,
            "observed_free_bytes": free_bytes,
            "observed_total_bytes": total_bytes,
            "mount_was_already_present": not mounted_by_us,
            "readonly_mount_attempted": mounted_by_us,
            "physical_identity_used_as_business_authority": False,
        }
    finally:
        if mounted_by_us:
            cleanup_error = None
            try:
                run(["umount", str(temp_path)], timeout=60)
            except Exception as error:
                cleanup_error = error
            try:
                temp_path.rmdir()
                if runtime_root.exists() and not any(runtime_root.iterdir()):
                    runtime_root.rmdir()
            except OSError as error:
                if cleanup_error is None:
                    cleanup_error = error
            if cleanup_error is not None:
                raise Stop(
                    "readonly_mount_restore_failed:"
                    + type(cleanup_error).__name__
                ) from cleanup_error


def scan_ha_data():
    root = HA_DATA_ROOT
    if root.is_symlink() or not root.is_dir():
        raise Stop("ha_data_root_invalid")
    resolved_root = root.resolve(strict=True)
    meta = root.stat()
    measured = 0
    yaml_paths = []
    file_count = 0
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in names + files:
            path = base / name
            entry = path.lstat()
            if stat.S_ISLNK(entry.st_mode):
                try:
                    path.resolve(strict=True).relative_to(resolved_root)
                except (OSError, ValueError) as error:
                    raise Stop("ha_data_external_symlink_unsupported") from error
            elif stat.S_ISDIR(entry.st_mode):
                pass
            elif stat.S_ISREG(entry.st_mode):
                measured += entry.st_size
                file_count += 1
                if path.suffix.lower() in {".yaml", ".yml"}:
                    yaml_paths.append(path)
            else:
                raise Stop("ha_data_special_file_unsupported")

    if PRODUCT_HA_CONFIG.exists():
        if PRODUCT_HA_CONFIG.is_symlink() or not PRODUCT_HA_CONFIG.is_file():
            raise Stop("product_ha_config_invalid")
        yaml_paths.append(PRODUCT_HA_CONFIG)

    for path in yaml_paths:
        if EXTERNAL_DB_RE.search(path.read_bytes()):
            raise Stop("ha_external_recorder_unsupported")

    sqlite_path = root / "home-assistant_v2.db"
    sqlite_result = "NOT_PRESENT"
    if sqlite_path.exists():
        if sqlite_path.is_symlink() or not sqlite_path.is_file():
            raise Stop("ha_sqlite_invalid")
        sqlite_result = "DEFERRED_UNTIL_QUIESCE"

    return {
        "measured_regular_file_bytes": measured,
        "regular_file_count": file_count,
        "root_uid": meta.st_uid,
        "root_gid": meta.st_gid,
        "root_mode": oct(stat.S_IMODE(meta.st_mode)),
        "external_recorder_detected": False,
        "special_file_detected": False,
        "external_symlink_detected": False,
        "sqlite_quick_check": sqlite_result,
    }


def verify_root_key_metadata():
    path = SYSTEM_ROOT_KEY
    if path.is_symlink() or not path.is_file():
        raise Stop("system_root_key_invalid")
    meta = path.stat()
    if (
        meta.st_uid != 0
        or stat.S_IMODE(meta.st_mode) != 0o600
        or meta.st_size != 32
    ):
        raise Stop("system_root_key_metadata_invalid")
    return {
        "present": True,
        "owner_root": True,
        "mode_0600": True,
        "size_bytes": 32,
        "key_bytes_read": False,
    }


def tool_capabilities():
    openssl = text(run(["openssl", "version"], timeout=30))
    help_probe = run(["openssl", "enc", "-help"], timeout=30, check=False)
    openssl_help = (
        help_probe.stdout.decode("utf-8", errors="replace")
        + "\n"
        + help_probe.stderr.decode("utf-8", errors="replace")
    )
    cipher_probe = run(["openssl", "enc", "-list"], timeout=30, check=False)
    cipher_list = (
        cipher_probe.stdout.decode("utf-8", errors="replace")
        + "\n"
        + cipher_probe.stderr.decode("utf-8", errors="replace")
    )
    if (
        not all(
            value in openssl_help
            for value in ("-pbkdf2", "-iter", "-md")
        )
        or "aes-256-ctr" not in cipher_list
    ):
        raise Stop("openssl_backup_capability_missing")
    tar_version = text(run(["tar", "--version"], timeout=30))
    if "GNU tar" not in tar_version:
        raise Stop("gnu_tar_required")
    tar_help = text(run(["tar", "--help"], timeout=30))
    if not all(
        value in tar_help
        for value in (
            "--numeric-owner",
            "--one-file-system",
            "--quoting-style",
            "--full-time",
            "--utc",
        )
    ):
        raise Stop("gnu_tar_backup_capability_missing")
    return {
        "openssl_available": True,
        "openssl_version": openssl.splitlines()[0][:120],
        "aes_256_ctr_pbkdf2_sha256_supported": True,
        "gnu_tar_available": True,
        "gnu_tar_version": tar_version.splitlines()[0][:120],
        "required_tar_flags_supported": True,
    }


def capacity_view(plan, ha_data, media):
    sys.path.insert(0, "/opt/HomeAssistant/tools")
    try:
        import n3w_t1_core_updater_ha_capacity as capacity
    except Exception as error:
        raise Stop("capacity_module_import_failed") from error
    breakdown = capacity.compute_capacity(
        target_artifact_bytes=plan["target_archive_size_bytes"],
        predecessor_recovery_budget_bytes=(
            plan["predecessor_identity"]["archive_size_bytes"]
        ),
        ha_data_measured_bytes=ha_data["measured_regular_file_bytes"],
    )
    required_remaining = (
        breakdown.ha_data_backup_budget_bytes
        + breakdown.transaction_working_budget_bytes
        + breakdown.removable_reserve_bytes
    )
    free = media["observed_free_bytes"]
    if free < required_remaining:
        raise Stop("u7_current_usb_capacity_insufficient")
    return {
        "ha_data_backup_budget_bytes": (
            breakdown.ha_data_backup_budget_bytes
        ),
        "transaction_working_budget_bytes": (
            breakdown.transaction_working_budget_bytes
        ),
        "removable_reserve_bytes": breakdown.removable_reserve_bytes,
        "required_remaining_bytes": required_remaining,
        "observed_usb_free_bytes": free,
        "capacity_pass": True,
    }


def main():
    try:
        plan = json.loads(
            base64.b64decode(sys.argv[1]).decode("utf-8")
        )
        if plan.get("gate_id") != (
            "N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_"
            "U7_POST_REBOOT_READONLY_PREFLIGHT_R27_20261114_01"
        ):
            raise Stop("gate_id_invalid")

        transaction = verify_transaction(plan)
        r26 = verify_r26_terminal(plan)
        sources = verify_installed_u6_sources(plan)
        units = require_healthy_units()
        containers = {
            name: docker_view(expected)
            for name, expected in plan["containers"].items()
        }
        ipc = ipc_status(containers["manager"]["container_id"])
        ha_data = scan_ha_data()
        root_key = verify_root_key_metadata()
        tools = tool_capabilities()
        media = inspect_media(plan, transaction)
        capacity = capacity_view(plan, ha_data, media)

        result = {
            "schema": "gh.n3w-t1-u7-r27-post-reboot-readonly-preflight/1",
            "status": "PASS",
            "read_only": True,
            "post_reboot_baseline_observed": True,
            "u6_transaction_exact": True,
            "r26_consumed_no_replay": True,
            "u7_source_activation_required": True,
            "u7_source_activation_eligible": True,
            "u7_live_execution_eligible": False,
            "live_mutation_authorized": False,
            "service_stop": False,
            "usb_data_mutation": False,
            "transaction_mutation": False,
            "u7_transition": False,
            "u8_plus": False,
            "board_access": False,
            "merge": False,
            "r26": r26,
            "sources": sources,
            "units": units,
            "containers": containers,
            "ipc": ipc,
            "ha_data": ha_data,
            "system_root_key_metadata": root_key,
            "tool_capabilities": tools,
            "media": media,
            "capacity": capacity,
        }
    except Exception as error:
        result = {
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:240],
            "read_only": True,
            "live_mutation_authorized": False,
            "service_stop": False,
            "usb_data_mutation": False,
            "transaction_mutation": False,
            "u7_transition": False,
            "u8_plus": False,
        }

    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


raise SystemExit(main())
'''


def git_text(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("local_git_failed")
    return completed.stdout.strip()


def read_manifest(expected_commit: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        document.get("gate_id") != GATE_ID
        or document.get("live_execution_authorized") is not False
        or document.get("authorization_state")
        != {
            "granted": False,
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


def prepare_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise Stop("evidence_root_invalid")
        os.chmod(root, 0o700)
    else:
        root.mkdir(parents=True, mode=0o700)
    if (
        root.stat().st_uid != os.geteuid()
        or stat.S_IMODE(root.stat().st_mode) != 0o700
    ):
        raise Stop("evidence_root_metadata_invalid")
    return root


def write_private(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def load_transport():
    spec = importlib.util.spec_from_file_location(
        "n3w_u7_r27_transport",
        SSH_TRANSPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise Stop("ssh_transport_import_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SSHTransport


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--t1-ssh-target", required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--expected-host-key-sha256", required=True)
    parser.add_argument("--preflight-only", action="store_true", required=True)
    args = parser.parse_args()

    result: dict[str, Any] = {
        "schema": "gh.n3w-t1-u7-r27-post-reboot-readonly-preflight-local/1",
        "status": "STOP",
        "read_only_preflight": True,
        "t1_access": False,
        "live_execution_authorized": False,
        "source_deployment": False,
        "service_stop": False,
        "service_restart": False,
        "usb_data_mutation": False,
        "transaction_mutation": False,
        "u7_transition": False,
        "u8_plus": False,
        "board_access": False,
        "merge": False,
    }
    transport = None
    try:
        plan = read_manifest(args.expected_package_commit)
        evidence = prepare_evidence_root(args.evidence_root)
        transport_type = load_transport()
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        result["t1_access"] = True

        payload = base64.b64encode(
            json.dumps(
                plan,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii")
        completed = transport.run_remote(
            ["python3", "-B", "-c", REMOTE_SCRIPT, payload],
            timeout=3600,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        write_private(evidence / "remote_stdout.txt", stdout.encode())
        write_private(evidence / "remote_stderr.txt", stderr.encode())

        try:
            remote = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise Stop("remote_result_json_invalid") from error
        write_private(
            evidence / "result.json",
            (json.dumps(remote, sort_keys=True, indent=2) + "\n").encode(),
        )
        summary = {
            "gate_id": GATE_ID,
            "execution_id": args.execution_id,
            "expected_package_commit": args.expected_package_commit,
            "transport_returncode": completed.returncode,
            "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
            "status": remote.get("status"),
            "read_only": remote.get("read_only"),
            "u7_source_activation_required": remote.get(
                "u7_source_activation_required"
            ),
            "u7_source_activation_eligible": remote.get(
                "u7_source_activation_eligible"
            ),
            "u7_live_execution_eligible": remote.get(
                "u7_live_execution_eligible"
            ),
        }
        write_private(
            evidence / "summary.json",
            (json.dumps(summary, sort_keys=True, indent=2) + "\n").encode(),
        )
        if completed.returncode != 0 or remote.get("status") != "PASS":
            result["reason"] = remote.get("reason", "remote_preflight_stop")
            return_code = 2
        else:
            result.update(remote)
            result["t1_access"] = True
            return_code = 0
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:240]
        return_code = 2
    finally:
        if transport is not None:
            try:
                transport.close_epoch()
                result["ssh_master_cleanup"] = True
            except Exception:
                result["ssh_master_cleanup"] = False

    print(json.dumps(result, sort_keys=True))
    return return_code

raise SystemExit(main())
