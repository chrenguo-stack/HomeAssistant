#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import n3w_t1_fresh_product_staging_host as staging_host

SCHEMA = "gh.n3w-t1-core-updater-ha-storage-policy-readonly/1"
PROJECT = "n3wfc4"
SERVICES = ("broker", "manager", "homeassistant")
UNITS = (
    "n3wfc4-broker-activation.service",
    "n3wfc4-services-activation.service",
)
EXTRA_PATHS = (
    "/var/lib/n3wfc4-homeassistant",
    "/var/lib/greenhouse-manager",
    "/var/lib/n3wfc4-broker",
    "/var/lib/n3w-t1-core-updater",
    "/var/log",
    "/var/cache/apt",
)


class ProbeError(RuntimeError):
    pass


def run_text(argv: list[str], *, timeout: int = 120) -> str:
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProbeError("command_transport_error:" + Path(argv[0]).name) from error
    if completed.returncode != 0:
        raise ProbeError("command_failed:" + Path(argv[0]).name)
    return completed.stdout.strip()


def path_usage(path: str) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {
            "present": False,
            "apparent_bytes": 0,
            "allocated_bytes": 0,
        }
    apparent = int(
        run_text(["du", "-s", "-x", "-B1", "--apparent-size", "--", path]).split()[0]
    )
    allocated = int(
        run_text(["du", "-s", "-x", "-B1", "--", path]).split()[0]
    )
    return {
        "present": True,
        "apparent_bytes": apparent,
        "allocated_bytes": allocated,
    }


def filesystem(path: str) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    statvfs = os.statvfs(path)
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "block_size": statvfs.f_frsize,
        "total_inodes": statvfs.f_files,
        "free_inodes": statvfs.f_favail,
    }


def storage_authority() -> dict[str, Any]:
    raw = run_text([sys.executable, "-c", staging_host._remote_storage_probe_script()])
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProbeError("storage_authority_json_invalid") from error
    if not isinstance(value, dict):
        raise ProbeError("storage_authority_shape_invalid")
    required = (
        "staging_root",
        "docker_root",
        "image_store_backend",
        "image_store_root",
        "staging_device",
        "docker_device",
        "image_store_device",
        "staging_free_bytes",
        "docker_free_bytes",
        "image_store_free_bytes",
    )
    if any(key not in value for key in required):
        raise ProbeError("storage_authority_incomplete")
    return value


def unit_snapshot() -> dict[str, Any]:
    output: dict[str, Any] = {}
    for unit in UNITS:
        raw = run_text(
            [
                "systemctl",
                "show",
                unit,
                "--property=ActiveState,SubState,NRestarts,ExecMainStartTimestampMonotonic",
            ]
        )
        record: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                record[key] = value
        output[unit] = record
    return output


def project_container_ids() -> dict[str, str]:
    raw = run_text(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={PROJECT}",
            "--format",
            '{{.ID}}\t{{.Label "com.docker.compose.service"}}',
        ]
    )
    found: dict[str, list[str]] = {service: [] for service in SERVICES}
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise ProbeError("container_listing_invalid")
        container_id, service = parts
        if service in found:
            found[service].append(container_id)
    if any(len(found[service]) != 1 for service in SERVICES):
        raise ProbeError("container_identity_invalid")
    return {service: found[service][0] for service in SERVICES}


def inspect_json(argv: list[str]) -> dict[str, Any]:
    raw = run_text(argv)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProbeError("docker_inspect_json_invalid") from error
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise ProbeError("docker_inspect_shape_invalid")
    return value[0]


def container_report(container_id: str, service: str) -> dict[str, Any]:
    document = inspect_json(["docker", "container", "inspect", "--size", container_id])
    config = document.get("Config") or {}
    state = document.get("State") or {}
    host_config = document.get("HostConfig") or {}
    mounts = document.get("Mounts") or []
    if not isinstance(mounts, list):
        raise ProbeError("container_mounts_invalid")

    writable_binds: list[dict[str, Any]] = []
    for mount in mounts:
        if (
            not isinstance(mount, dict)
            or mount.get("Type") != "bind"
            or mount.get("RW") is not True
        ):
            continue
        source = mount.get("Source")
        destination = mount.get("Destination")
        if not isinstance(source, str) or not source.startswith("/"):
            raise ProbeError("container_bind_source_invalid")
        writable_binds.append(
            {
                "destination": destination,
                "usage": path_usage(source),
            }
        )

    image_ref = config.get("Image")
    if not isinstance(image_ref, str) or not image_ref:
        raise ProbeError("container_image_ref_invalid")
    image = inspect_json(["docker", "image", "inspect", image_ref])
    rootfs = image.get("RootFS") or {}
    layers = rootfs.get("Layers") or []
    if not isinstance(layers, list):
        layers = []

    log_path = document.get("LogPath")
    log_bytes = 0
    if isinstance(log_path, str) and log_path:
        try:
            log_bytes = os.stat(log_path, follow_symlinks=False).st_size
        except FileNotFoundError:
            log_bytes = 0

    return {
        "service": service,
        "container_id": document.get("Id"),
        "container_image_ref": image_ref,
        "container_image_id": document.get("Image"),
        "container_running": state.get("Running"),
        "container_started_at": state.get("StartedAt"),
        "container_restart_count": document.get("RestartCount"),
        "container_size_rw_bytes": document.get("SizeRw"),
        "container_size_rootfs_bytes": document.get("SizeRootFs"),
        "image_id": image.get("Id"),
        "image_size_bytes": image.get("Size"),
        "image_os": image.get("Os"),
        "image_architecture": image.get("Architecture"),
        "image_layer_count": len(layers),
        "log_type": (host_config.get("LogConfig") or {}).get("Type"),
        "log_bytes": log_bytes,
        "writable_binds": writable_binds,
    }


def docker_system_df() -> list[dict[str, str]]:
    raw = run_text(["docker", "system", "df", "--format", "{{json .}}"])
    rows: list[dict[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ProbeError("docker_system_df_json_invalid") from error
        if not isinstance(row, dict):
            raise ProbeError("docker_system_df_shape_invalid")
        rows.append({str(key): str(value) for key, value in row.items()})
    return rows


def runtime_snapshot() -> dict[str, Any]:
    ids = project_container_ids()
    return {
        "units": unit_snapshot(),
        "containers": {
            service: container_report(ids[service], service)
            for service in SERVICES
        },
    }


def main() -> int:
    try:
        if os.geteuid() != 0:
            raise ProbeError("root_required")
        authority = storage_authority()
        before = runtime_snapshot()
        filesystems = {
            "root": filesystem("/"),
            "staging": filesystem(str(authority["staging_root"])),
            "docker": filesystem(str(authority["docker_root"])),
            "image_store": filesystem(str(authority["image_store_root"])),
        }
        extra = {path: path_usage(path) for path in EXTRA_PATHS}
        docker_df = docker_system_df()
        after = runtime_snapshot()
        if before != after:
            raise ProbeError("runtime_changed_during_readonly_probe")

        result = {
            "schema": SCHEMA,
            "status": "PASS",
            "operation": "readonly_storage_policy_baseline",
            "mutation": False,
            "persistent_t1_file_write": False,
            "temporary_scratch_write": True,
            "service_restart": False,
            "image_load": False,
            "updater_apply": False,
            "updater_rollback": False,
            "board_access": False,
            "storage_authority": authority,
            "filesystems": filesystems,
            "runtime": before,
            "extra_path_usage": extra,
            "docker_system_df": docker_df,
            "runtime_state_stable": True,
        }
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        reason = str(error)
        if (
            not reason
            or len(reason) > 160
            or "/" in reason
            or "\\" in reason
            or "@" in reason
        ):
            reason = type(error).__name__
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "operation": "readonly_storage_policy_baseline",
                    "mutation": False,
                    "reason": reason,
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
