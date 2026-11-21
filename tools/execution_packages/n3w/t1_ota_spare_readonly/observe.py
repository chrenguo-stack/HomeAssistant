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


SOURCE_HEAD = "84da7cd68e2f65fb011c32db1c3683b76a48112b"
MANIFEST_SHA256 = "9cfad52a76670474cb328d3d22c0a7d4985f38f3e79fbe68e82a6b6550c8fa48"
PACKAGE_SHA256 = "f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84"


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
    from n3w_t1_core_updater_ha_mounted_media import _command_json, _device_number, _mount_device
    from n3w_t1_core_updater_ha_recovery_startup import RECOVERY_ARCHIVE, RECOVERY_STARTUP_UNIT, RECOVERY_TIMER
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
        snapshot = host._observe_running_base_v2()
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

    before = observe("transactions_before", transactions)
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
    after = observe("transactions_after", transactions)
    report["transactions"] = after
    report["transactions_stable"] = before is not None and before == after
    report["recovery_units"] = {
        unit: observe(unit, lambda: host._systemctl("is-active", unit))
        for unit in (IPC_SOCKET_UNIT, RECOVERY_STARTUP_UNIT, RECOVERY_TIMER)
    }
    report["recovery_package_present"] = Path(RECOVERY_ARCHIVE).is_file() and not Path(RECOVERY_ARCHIVE).is_symlink()
    report["status"] = "R7_OBSERVATION_COLLECTED"
    report["errors"] = errors
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_spare() if "PACKAGE_ON_SPARE" in globals() else run_operator())
