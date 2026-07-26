from __future__ import annotations

from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_execution_preparation_common import (
    EXECUTION_RECORDS,
    ManagerIdentityExecutionPreparationError,
    private_file,
    safe_relative,
    sha_path,
)


def verify_execution_records(
    root: Path,
    manifest: dict[str, Any],
) -> dict[str, str]:
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation record inventory is missing"
        )
    observed: dict[str, str] = {}
    for item in records:
        if not isinstance(item, dict):
            raise ManagerIdentityExecutionPreparationError(
                "execution preparation record inventory is invalid"
            )
        relative = safe_relative(item.get("path"), "execution preparation record")
        name = relative.as_posix()
        if name in observed or name not in EXECUTION_RECORDS:
            raise ManagerIdentityExecutionPreparationError(
                "execution preparation record inventory is unexpected"
            )
        path = root.joinpath(*relative.parts)
        private_file(path, f"execution preparation record {name}")
        digest = sha_path(path)
        if (
            item.get("size") != path.stat().st_size
            or item.get("sha256") != digest
            or item.get("contains_secret") is not EXECUTION_RECORDS[name]
        ):
            raise ManagerIdentityExecutionPreparationError(
                f"execution preparation record verification failed: {name}"
            )
        observed[name] = digest
    if set(observed) != set(EXECUTION_RECORDS):
        raise ManagerIdentityExecutionPreparationError(
            "execution preparation record inventory is incomplete"
        )
    return observed


def verify_record_bindings(
    bindings: dict[str, Any],
    observed: dict[str, str],
) -> None:
    if bindings.get("fresh_rollback_archive_sha256") != observed[
        "fresh-manager-rollback.tar.gz"
    ]:
        raise ManagerIdentityExecutionPreparationError(
            "fresh rollback archive binding does not match"
        )
    if bindings.get("fresh_rollback_manifest_sha256") != observed[
        "fresh-rollback-manifest.json"
    ]:
        raise ManagerIdentityExecutionPreparationError(
            "fresh rollback manifest binding does not match"
        )
