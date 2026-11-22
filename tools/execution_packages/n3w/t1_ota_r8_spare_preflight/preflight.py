import argparse
import base64
import hashlib
import json
import os
import platform
import re
import stat
import subprocess
import sys
from pathlib import Path


SOURCE_HEAD = "eac5794afbeef265dee0f5f60d5e5223de111e35"
MANIFEST_SHA256 = "f3dd26c2074c721e45d37f134cf9f90a1e269370b11eaf992e1f892b9053cd6c"
PACKAGE_SHA256 = "823a4522a34aae926913e8980fb9442af457084ff4243c74419ccdd66ff6a4e7"
CLEAN_REFERENCE_SOURCE = "24382caae4a1f5d459297f86e8d18f10a848ca64"
PROVISION_UNIT = "n3wfc4-provision-resume.service"
EXPECTED_CURRENT_IMAGE = "local/n3w-homeassistant:2026.10.4-5881590f"
EXPECTED_PREDECESSOR_IMAGE = "local/n3w-homeassistant:2026.10.0-0c73235a"


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def read_package(directory):
    manifest_bytes = (directory / "manifest.json").read_bytes()
    if digest(manifest_bytes) != MANIFEST_SHA256:
        raise ValueError("recovery_manifest_sha256_mismatch")
    manifest = json.loads(manifest_bytes)
    if manifest["source_head"] != SOURCE_HEAD or len(manifest["files"]) != 11:
        raise ValueError("recovery_manifest_binding_mismatch")
    for name, expected in manifest["files"].items():
        if digest((directory / name).read_bytes()) != expected:
            raise ValueError("recovery_package_file_sha256_mismatch")
    package = (directory / "ha-recovery.pyz").read_bytes()
    if digest(package) != PACKAGE_SHA256:
        raise ValueError("recovery_updater_sha256_mismatch")
    return package



def recovery_material_documents(document):
    prepared = document.get("prepared_image_materials")
    if isinstance(prepared, dict) and set(prepared) == {"target", "predecessor"}:
        return prepared["target"], prepared["predecessor"], "prepared_image_materials"
    installed = document.get("install_recovery_materials")
    if (
        isinstance(installed, dict)
        and isinstance(installed.get("target"), dict)
        and isinstance(installed.get("predecessor"), dict)
    ):
        return (
            installed["target"],
            installed["predecessor"],
            "install_recovery_materials_legacy",
        )
    raise ValueError("recovery_material_records_unavailable")


def run_operator():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh", required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--usb-mount", default="")
    args = parser.parse_args()
    if args.usb_mount and not args.usb_mount.startswith("/"):
        parser.error("use an absolute path for the already-mounted USB filesystem")
    try:
        encoded = base64.b64encode(read_package(args.package)).decode("ascii")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    source = Path(__file__).read_text(encoding="utf-8")
    payload = f"PACKAGE_ON_SPARE = {encoded!r}\nUSB_MOUNT = {args.usb_mount!r}\n{source}"
    command = (
        'if [ "$(id -u)" -eq 0 ]; then exec /usr/bin/python3 -I -B -; '
        'else exec sudo -n /usr/bin/python3 -I -B -; fi'
    )
    return subprocess.run(
        [
            "ssh", "-o", "StrictHostKeyChecking=yes", "-o", "ForwardAgent=no",
            "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=10",
            "-o", "RequestTTY=no", "--", args.ssh, command,
        ],
        input=payload, text=True, check=False,
    ).returncode


def space(path):
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("storage_root_not_directory")
    filesystem = os.statvfs(path)
    return {
        "total_bytes": filesystem.f_blocks * filesystem.f_frsize,
        "available_bytes": filesystem.f_bavail * filesystem.f_frsize,
        "read_only": bool(filesystem.f_flag & os.ST_RDONLY),
    }


def read_reference_record(path, mode):
    if path.resolve(strict=True) != path:
        raise ValueError("clean_reference_record_path_invalid")
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != mode
            or info.st_uid != 0 or info.st_nlink != 1 or info.st_size > 1024 * 1024):
        raise ValueError("clean_reference_record_metadata_invalid")
    report = json.loads(path.read_bytes())
    if not isinstance(report, dict):
        raise ValueError("clean_reference_record_json_invalid")
    return report


def has_clean_reference_records(state_root=Path("/var/lib"), release_path=Path(
    "/opt/HomeAssistant/infra/n3w-t1/production/fresh-release.json"
)):
    legacy = state_root / "n3w-t1-provisioning"
    if legacy.is_symlink() or any((legacy / name).exists() or (legacy / name).is_symlink()
                                 for name in ("transaction.json", "FIRSTBOOT_COMPLETE.json")):
        return False
    try:
        release = read_reference_record(release_path, 0o644)
        identity = read_reference_record(state_root / "greenhouse-manager/identity/INITIALIZED.json", 0o600)
        if (release.get("schema") != "gh.n3w-t1-fresh-release/1"
                or release.get("release_id") != CLEAN_REFERENCE_SOURCE
                or release.get("source_head") != CLEAN_REFERENCE_SOURCE
                or release.get("explicit_provisioning_required") is not True
                or identity.get("schema") != "gh.h0h1.system-initialization/1"):
            return False
        marker_digest = identity.pop("manifest_sha256", None)
        if marker_digest != digest(json.dumps(
            identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")):
            return False
        for phase, stage, control, flag in (
            ("r2a", "RUNTIME_STARTED", "abeb6c31147bcf249361dcec7e9536eaed6106a6", "runtime_started"),
            ("r2b", "REBOOT_ACCEPTED", "e15c64ac8f0f5f482a6c8538072031734002a559", "reboot_acceptance_passed"),
        ):
            record = read_reference_record(
                state_root / f"n3w-t1-clean-reference-{phase}/transaction.json", 0o600
            )
            if (record.get("schema") != f"gh.n3w-t1-clean-reference-{phase}-transaction/1"
                    or record.get("product_source_head") != CLEAN_REFERENCE_SOURCE
                    or record.get("control_plane_head") != control or record.get("stage") != stage
                    or record.get("authorization_claimed") is not True
                    or record.get("authorization_consumed") is not True
                    or record.get("authorization_replay_allowed") is not False
                    or record.get(flag) is not True):
                return False
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def observe_running_snapshot(host, clean_reference, admission, updater_error):
    try:
        snapshot = host._observe_running_base_v2()
    except updater_error as error:
        reason = str(error)
        admission.update(status="BLOCKED", reason=reason.partition(":")[0])
        if not clean_reference or reason not in {
            f"relevant_failed_units:{PROVISION_UNIT}", f"unit_health_invalid:{PROVISION_UNIT}",
        }:
            raise
        services = host._running_project_services_v2()
        return {
            "compose_render": host.render_compose(),
            "runtime": {name: host._runtime(name) for name in services},
            "listeners": host._listener_snapshot(),
        }
    admission.update(status="RUNNING_BASELINE_PASS")
    return snapshot


def run_spare():
    report = {"source_head": SOURCE_HEAD, "architecture": platform.machine()}
    if os.geteuid() != 0 or sys.platform != "linux" or report["architecture"] not in {"aarch64", "arm64"} or sys.version_info < (3, 11):
        report["status"] = "R7_UNSUPPORTED_OBSERVER_ENVIRONMENT"
        print(json.dumps(report, sort_keys=True))
        return 2
    package = base64.b64decode(PACKAGE_ON_SPARE, validate=True)
    if digest(package) != PACKAGE_SHA256:
        raise SystemExit("recovery_updater_sha256_mismatch")
    descriptor = os.memfd_create("n3w-readonly")
    with os.fdopen(os.dup(descriptor), "wb") as stream:
        stream.write(package)
    sys.path.insert(0, f"/proc/self/fd/{descriptor}")
    try:
        return observe_spare(report)
    finally:
        os.close(descriptor)


def observe_spare(report):
    from n3w_t1_core_updater_common import UpdaterError
    from n3w_t1_core_updater_ha_ipc import IPC_SOCKET_UNIT, ha_image_version
    from n3w_t1_core_updater_ha_backup import (
        ProtectedHaDataBackup, backup_record_from_document,
    )
    from n3w_t1_core_updater_ha_mounted_media import (
        _command_json, _device_number, _mount_device, _open_transaction_directory,
        _verify_archive, bound_usb_device,
    )
    from n3w_t1_core_updater_ha_recovery import (
        ImageRecoveryRecord, validate_image_recovery_record,
    )
    from n3w_t1_core_updater_ha_recovery_startup import (
        RECOVERY_ARCHIVE, RECOVERY_STARTUP_UNIT, RECOVERY_TIMER,
    )
    from n3w_t1_core_updater_ha_usb_media import validate_filesystem_uuid
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
    from n3w_t1_core_updater_host import EXPECTED_LISTENERS, LocalHost
    from n3w_t1_core_updater_v2_common import TERMINAL_TX_V2, UpdaterV2Error, canonical
    from n3w_t1_core_updater_v2_state import V2StateStore

    for variable in ("DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY"):
        os.environ.pop(variable, None)
    os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    host = LocalHost()
    errors = {}
    storage_paths = {"root": Path("/")}
    clean_reference = has_clean_reference_records()
    admission = {"status": "NOT_OBSERVED"}

    def observe(name, action):
        try:
            return action()
        except (UpdaterError, UpdaterV2Error, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            reason = str(error).partition(":")[0]
            errors[name] = reason if re.fullmatch(r"[a-z][a-z0-9_]{2,95}", reason) else type(error).__name__
            return None

    def transactions():
        store = V2StateStore()
        records = (store.read(), store.read_legacy(), HaUsbStateStore().read())
        return {
            name: None if record is None else {
                "status": record["status"] if record.get("status") in TERMINAL_TX_V2 else "NONTERMINAL",
                "sha256": digest(canonical(record)),
            }
            for name, record in zip(("stack", "legacy_manager", "homeassistant_usb"), records)
        }

    def runtime():
        snapshot = observe_running_snapshot(host, clean_reference, admission, UpdaterError)
        compose = snapshot["compose_render"]
        bindings, modes = host._image_binding_authority_v2(compose)
        fields = ("image_ref", "image_id", "platform", "restart_count", "runtime_contract_sha256")
        observed = {
            name: {key: info[key] for key in fields}
            for name, info in snapshot["runtime"].items()
        }
        for name, component, target in (
            ("ha_data", "homeassistant", "/config"),
            ("manager_data", "manager", "/var/lib/greenhouse-manager/manager"),
            ("manager_replay", "manager", "/var/lib/greenhouse-manager/n3w"),
            ("broker_data", "broker", "/mosquitto/data"),
        ):
            mounts = [
                mount for mount in compose["services"][component].get("volumes", [])
                if mount.get("target") == target and mount.get("type") == "bind"
            ]
            if len(mounts) == 1 and Path(mounts[0]["source"]).is_absolute():
                storage_paths[name] = Path(mounts[0]["source"])
        return {
            "diagnostic_only": admission["status"] == "BLOCKED",
            "services": observed, "binding_modes": modes,
            "references_match_compose": all(observed[name]["image_ref"] == ref for name, ref in bindings.items()),
            "listeners_match": snapshot["listeners"] == EXPECTED_LISTENERS,
            "homeassistant_version": ha_image_version(observed["homeassistant"]["image_ref"]),
        }

    def docker_root():
        path = Path(host._run(("docker", "info", "--format", "{{.DockerRootDir}}")).stdout.decode().strip())
        if not path.is_absolute():
            raise ValueError("docker_root_path_invalid")
        storage_paths["docker"] = path
        return space(path)

    def usb():
        if not USB_MOUNT:
            return {"status": "NOT_REQUESTED"}
        if not {"root", "docker", "ha_data", "manager_data", "manager_replay", "broker_data"} <= storage_paths.keys():
            return {"status": "PROTECTED_STORAGE_UNRESOLVED"}
        mount = Path(USB_MOUNT)
        if mount.resolve(strict=True) != mount:
            raise ValueError("usb_mount_path_invalid")
        rows = _command_json("findmnt", "--json", "--mountpoint", str(mount), "--output", "UUID").get("filesystems")
        if not isinstance(rows, list) or len(rows) != 1:
            return {"status": "EXISTING_MOUNT_UNAVAILABLE"}
        filesystem_uuid = validate_filesystem_uuid(rows[0].get("uuid"))
        protected = {_device_number(path.stat().st_dev) for path in storage_paths.values()}
        device = _mount_device(mount, filesystem_uuid, protected, allow_read_only=True)
        measured = space(mount)
        if _device_number(mount.stat().st_dev) != device:
            raise ValueError("usb_mount_changed")
        return {
            "status": "OBSERVED", "filesystem": "ext4",
            "uuid_sha256": digest(filesystem_uuid.encode()), **measured,
        }


    def image_inventory():
        result = {}
        for label, reference in (
            ("current_2026_10_4", EXPECTED_CURRENT_IMAGE),
            ("predecessor_2026_10_0", EXPECTED_PREDECESSOR_IMAGE),
        ):
            document = host._image_document(reference)
            if document is None:
                result[label] = {"reference": reference, "present": False}
                continue
            result[label] = {
                "reference": reference,
                "present": True,
                "image_id": document.get("Id"),
                "repo_tags": document.get("RepoTags"),
                "repo_digests": document.get("RepoDigests"),
                "architecture": document.get("Architecture"),
                "os": document.get("Os"),
                "size_bytes": document.get("Size"),
            }
        return result

    def bound_usb_inventory():
        store = HaUsbStateStore()
        current = store.read()
        if current is None:
            return {"status": "NO_HA_USB_TRANSACTION"}
        expected_uuid = current.get("usb_filesystem_uuid")
        if not isinstance(expected_uuid, str) or not expected_uuid:
            return {"status": "TRANSACTION_HAS_NO_USB_UUID"}
        row = bound_usb_device(expected_uuid.lower(), store.root)
        result = {
            "status": "BOUND_USB_NOT_PRESENT" if row is None else "BOUND_USB_PRESENT",
            "uuid_sha256": digest(expected_uuid.lower().encode()),
            "transaction_status": current.get("status"),
            "transaction_phase": current.get("phase"),
            "transaction_sha256": digest(canonical(current)),
        }
        if row is None:
            return result
        result.update({
            "device": row.get("name"),
            "device_type": row.get("type"),
            "transport": row.get("tran"),
            "major_minor": row.get("maj:min"),
            "filesystem": row.get("fstype"),
        })
        mounted = subprocess.run(
            [
                "findmnt", "--list", "--json", "--source", f"UUID={expected_uuid}",
                "--output", "TARGET,FSTYPE,OPTIONS",
            ],
            capture_output=True, check=False, timeout=10,
        )
        if mounted.returncode == 1:
            result["mounts"] = []
        elif mounted.returncode:
            raise ValueError("bound_usb_mount_discovery_failed")
        else:
            value = json.loads(mounted.stdout)
            rows = value.get("filesystems") if isinstance(value, dict) else None
            if not isinstance(rows, list):
                raise ValueError("bound_usb_mount_discovery_invalid")
            result["mounts"] = rows
        return result

    def rollback_materials():
        store = HaUsbStateStore()
        current = store.read()
        if current is None:
            return {"status": "NO_HA_USB_TRANSACTION"}
        expected_uuid = current.get("usb_filesystem_uuid")
        if not isinstance(expected_uuid, str) or not expected_uuid:
            return {"status": "TRANSACTION_HAS_NO_USB_UUID"}
        row = bound_usb_device(expected_uuid.lower(), store.root)
        if row is None:
            return {"status": "BOUND_USB_NOT_PRESENT"}
        mounted = subprocess.run(
            [
                "findmnt", "--list", "--json", "--source", f"UUID={expected_uuid}",
                "--output", "TARGET,FSTYPE,OPTIONS",
            ],
            capture_output=True, check=False, timeout=10,
        )
        if mounted.returncode == 1:
            return {"status": "BOUND_USB_PRESENT_UNMOUNTED"}
        if mounted.returncode:
            raise ValueError("rollback_material_mount_discovery_failed")
        value = json.loads(mounted.stdout)
        rows = value.get("filesystems") if isinstance(value, dict) else None
        if not isinstance(rows, list) or len(rows) != 1:
            raise ValueError("rollback_material_mount_not_unique")
        target = rows[0].get("target")
        if not isinstance(target, str) or not Path(target).is_absolute():
            raise ValueError("rollback_material_mount_target_invalid")
        mountpoint = Path(target)
        target_document, predecessor_document, record_source = recovery_material_documents(current)
        try:
            prepared_target = validate_image_recovery_record(
                ImageRecoveryRecord(**target_document),
                expected_kind="target",
                expected_image_ref=current["target_image_ref"],
                expected_archive_sha256=current["target_archive_sha256"],
            )
            predecessor = validate_image_recovery_record(
                ImageRecoveryRecord(**predecessor_document),
                expected_kind="predecessor",
                expected_image_ref=current["current_image_ref"],
            )
        except TypeError as error:
            raise ValueError("recovery_material_record_invalid") from error
        if prepared_target.archive_size_bytes != current["target_archive_size"]:
            raise ValueError("recovery_target_size_drift")
        portable = current.get("current_image_identity", {}).get("portable_identity_sha256")
        if portable is not None and portable != predecessor.portable_identity_sha256:
            raise ValueError("recovery_predecessor_portable_identity_drift")
        if predecessor.image_ref != EXPECTED_CURRENT_IMAGE:
            return {
                "status": "PREDECESSOR_RECORD_NOT_CURRENT_2026_10_4",
                "record_source": record_source,
                "predecessor": predecessor.public(),
            }
        materials = current.get("install_recovery_materials")
        if not isinstance(materials, dict) or "backup" not in materials:
            return {
                "status": "CURRENT_IMAGE_ARCHIVE_VERIFIED_DATA_BACKUP_UNAVAILABLE",
                "record_source": record_source,
                "predecessor": predecessor.public(),
            }
        backup = backup_record_from_document(materials["backup"])
        with _open_transaction_directory(
            mountpoint, store.root, current, allow_read_only=True
        ) as (_, directory):
            _verify_archive(directory, "predecessor.tar", predecessor)
            backup_directory = os.open(
                "ha-backup", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=directory,
            )
            try:
                metadata = os.fstat(backup_directory)
                if (
                    metadata.st_dev != os.fstat(directory).st_dev
                    or metadata.st_uid != os.geteuid()
                    or stat.S_IMODE(metadata.st_mode) != 0o700
                ):
                    raise ValueError("recovery_backup_directory_invalid")
                verified_backup = ProtectedHaDataBackup(
                    work_root=store.root
                ).verify(
                    backup_directory,
                    current["transaction_id_sha256"],
                    backup,
                )
            finally:
                os.close(backup_directory)
        if store.read() != current:
            raise ValueError("recovery_material_transaction_changed")
        return {
            "status": "CURRENT_2026_10_4_ROLLBACK_MATERIALS_VERIFIED",
            "record_source": record_source,
            "predecessor": predecessor.public(),
            "backup": {
                "archive_sha256": verified_backup.archive_sha256,
                "archive_size_bytes": verified_backup.archive_size_bytes,
                "manifest_sha256": verified_backup.manifest_sha256,
                "verified": verified_backup.verified,
                "fsynced": verified_backup.fsynced,
                "consistent_preupgrade_point": verified_backup.consistent_preupgrade_point,
                "storage_integrity_verified": verified_backup.storage_integrity_verified,
                "confidentiality_protected": verified_backup.confidentiality_protected,
                "authenticity_protected": verified_backup.authenticity_protected,
            },
            "target_record": prepared_target.public(),
        }

    before = observe("transactions_before", transactions)
    report["clean_reference_records_match"] = clean_reference
    report["ota_running_baseline"] = admission
    report["runtime"] = observe("runtime", runtime)
    report["http_status"] = observe("ha_http", lambda: host._homeassistant_http_status(allow_unavailable=True))
    report["mqtt_authenticated"] = {
        name: observe(f"mqtt_{name}", lambda: host._mqtt_authenticated(name))
        for name in ("manager", "homeassistant")
    }
    report["storage"] = {"docker": observe("docker_space", docker_root)}
    report["storage"].update({
        name: observe(f"space_{name}", lambda: space(path))
        for name, path in storage_paths.items() if name != "docker"
    })
    report["usb"] = observe("usb", usb)
    report["images"] = observe("images", image_inventory)
    report["bound_usb"] = observe("bound_usb", bound_usb_inventory)
    report["rollback_materials"] = observe("rollback_materials", rollback_materials)
    root_space = report.get("storage", {}).get("root")
    report["capacity_policy"] = {
        "decision_point": "AFTER_RELEASE_BEFORE_NEXT_IMPORT",
        "pre_release_available_bytes": (
            root_space.get("available_bytes") if isinstance(root_space, dict) else None
        ),
        "post_release_available_bytes": None,
        "capacity_decision": "DEFER_UNTIL_POST_RELEASE_MEASUREMENT",
    }
    after = observe("transactions_after", transactions)
    report["transactions"] = after
    report["transactions_stable"] = before is not None and before == after
    report["recovery_units"] = {
        unit: observe(unit, lambda: host._systemctl("is-active", unit))
        for unit in (IPC_SOCKET_UNIT, RECOVERY_STARTUP_UNIT, RECOVERY_TIMER)
    }
    report["recovery_package_present"] = Path(RECOVERY_ARCHIVE).is_file() and not Path(RECOVERY_ARCHIVE).is_symlink()
    report["status"] = "R8_SPARE_READONLY_PREFLIGHT_COLLECTED"
    report["errors"] = errors
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_spare() if "PACKAGE_ON_SPARE" in globals() else run_operator())
