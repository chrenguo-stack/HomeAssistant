from __future__ import annotations

import json
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

from .t1_manager_identity_migration_execution_preparation_constants import (
    ROLLBACK_SCHEMA,
    ManagerIdentityExecutionPreparationError,
)
from .t1_manager_identity_migration_execution_preparation_io import (
    private_file,
    sha_stream,
)


def verify_rollback_archive(path: Path) -> dict[str, Any]:
    private_file(path, "fresh rollback archive")
    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getmembers()
        if any(
            not member.isfile()
            or PurePosixPath(member.name).is_absolute()
            or ".." in PurePosixPath(member.name).parts
            for member in members
        ):
            raise ManagerIdentityExecutionPreparationError(
                "fresh rollback archive contains an unsafe member"
            )
        by_name = {member.name: member for member in members}
        manifest_member = by_name.get("rollback-manifest.json")
        if manifest_member is None:
            raise ManagerIdentityExecutionPreparationError(
                "fresh rollback archive manifest is missing"
            )
        stream = archive.extractfile(manifest_member)
        if stream is None:
            raise ManagerIdentityExecutionPreparationError(
                "fresh rollback archive manifest cannot be read"
            )
        try:
            manifest = json.load(stream)
        except json.JSONDecodeError as error:
            raise ManagerIdentityExecutionPreparationError(
                "fresh rollback archive manifest is invalid"
            ) from error
        if not isinstance(manifest, dict) or manifest.get("schema") != ROLLBACK_SCHEMA:
            raise ManagerIdentityExecutionPreparationError(
                "fresh rollback archive schema is invalid"
            )
        if (
            manifest.get("manager_only") is not True
            or manifest.get("preserve_anonymous") is not True
            or manifest.get("anonymous_closure_enabled") is not False
        ):
            raise ManagerIdentityExecutionPreparationError(
                "fresh rollback archive safety binding is invalid"
            )
        files = manifest.get("files")
        if not isinstance(files, list):
            raise ManagerIdentityExecutionPreparationError(
                "fresh rollback archive inventory is missing"
            )
        expected: dict[str, dict[str, Any]] = {}
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get("archive_path"), str):
                raise ManagerIdentityExecutionPreparationError(
                    "fresh rollback archive inventory is invalid"
                )
            expected[item["archive_path"]] = item
        if set(by_name) != set(expected) | {"rollback-manifest.json"}:
            raise ManagerIdentityExecutionPreparationError(
                "fresh rollback archive inventory does not match"
            )
        for name, item in expected.items():
            member = by_name[name]
            stream = archive.extractfile(member)
            if stream is None or sha_stream(stream) != item.get("sha256"):
                raise ManagerIdentityExecutionPreparationError(
                    f"fresh rollback archive hash verification failed: {name}"
                )
            if (
                member.size != item.get("size")
                or member.mode & 0o777 != item.get("mode")
                or member.uid != item.get("uid")
                or member.gid != item.get("gid")
            ):
                raise ManagerIdentityExecutionPreparationError(
                    f"fresh rollback archive metadata verification failed: {name}"
                )
    return manifest
