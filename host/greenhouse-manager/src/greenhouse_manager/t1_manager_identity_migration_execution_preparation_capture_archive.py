from __future__ import annotations

import os
import shutil
import tarfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_execution_preparation_capture_inventory import (
    _metadata,
)
from .t1_manager_identity_migration_execution_preparation_common import (
    ROLLBACK_SCHEMA,
    ManagerIdentityExecutionPreparationError,
    canonical,
    verify_rollback_archive,
    write_json,
)


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uname = ""
    info.gname = ""
    return info


def _create_rollback(
    archive_path: Path,
    manifest_path: Path,
    inventory: list[dict[str, object]],
    runtime: Mapping[str, Any],
    gate: Mapping[str, Any],
    preparation: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    files = [
        {
            "archive_path": item["archive_path"],
            "source_path": item["source_path"],
            "kind": item["kind"],
            "mode": item["mode"],
            "uid": item["uid"],
            "gid": item["gid"],
            "size": item["size"],
            "sha256": item["sha256"],
        }
        for item in inventory
    ]
    compose = runtime.get("compose")
    if not isinstance(compose, dict):
        raise ManagerIdentityExecutionPreparationError(
            "manager Compose binding is incomplete"
        )
    rollback = {
        "schema": ROLLBACK_SCHEMA,
        "created_at": created_at,
        "classification": "sensitive-local-manager-fresh-rollback",
        "manager_only": True,
        "restart_scope": ["greenhouse-manager"],
        "forbidden_service_changes": ["mosquitto", "homeassistant", "node"],
        "current_services_modified": False,
        "compose_project": compose["project"],
        "compose_working_directory": compose["working_dir"],
        "manager_secret_root": runtime["target_secret_root"],
        "manager_password_target": runtime["target_password_file"],
        "manager_password_target_absent": True,
        "driver_contract_sha256": gate["driver_contract_sha256"],
        "adapter_contract_sha256": gate["adapter_contract_sha256"],
        "runtime_binding_sha256": gate["runtime_binding_sha256"],
        "live_binding_sha256": gate["live_binding_sha256"],
        "preparation_manifest_sha256": preparation["manifest_sha256"],
        "files": files,
    }
    write_json(manifest_path, rollback)
    staging = manifest_path.parent / ".rollback-staging"
    staging.mkdir(mode=0o700)
    try:
        manifest_copy = staging / "rollback-manifest.json"
        shutil.copyfile(manifest_path, manifest_copy)
        manifest_copy.chmod(0o600)
        copied: list[tuple[Path, str]] = []
        for item in inventory:
            source = Path(str(item["source_path"]))
            target = staging / str(item["archive_path"])
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(source, target)
            os.chmod(target, int(item["mode"]))
            if os.geteuid() == 0:
                os.chown(target, int(item["uid"]), int(item["gid"]))
            if _metadata(target)["sha256"] != item["sha256"]:
                raise ManagerIdentityExecutionPreparationError(
                    "manager rollback source changed during capture"
                )
            copied.append((target, str(item["archive_path"])))
        descriptor = os.open(
            archive_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as raw, tarfile.open(
            fileobj=raw,
            mode="w:gz",
        ) as archive:
            archive.add(
                manifest_copy,
                arcname="rollback-manifest.json",
                recursive=False,
                filter=_tar_filter,
            )
            for target, arcname in copied:
                archive.add(
                    target,
                    arcname=arcname,
                    recursive=False,
                    filter=_tar_filter,
                )
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    if canonical(verify_rollback_archive(archive_path)) != canonical(rollback):
        raise ManagerIdentityExecutionPreparationError(
            "fresh manager rollback archive verification failed"
        )
    return rollback
