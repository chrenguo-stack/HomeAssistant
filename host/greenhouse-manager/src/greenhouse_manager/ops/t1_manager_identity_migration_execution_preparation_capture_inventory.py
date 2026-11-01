from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .t1_manager_identity_migration_execution_preparation_common import (
    ManagerIdentityExecutionPreparationError,
    sha_path,
)


def _absolute_file(value: object, label: str) -> Path:
    if not isinstance(value, str):
        raise ManagerIdentityExecutionPreparationError(f"{label} is missing")
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ManagerIdentityExecutionPreparationError(f"{label} is missing or unsafe")
    return path.resolve()


def _absolute_target(value: object, label: str) -> Path:
    if not isinstance(value, str):
        raise ManagerIdentityExecutionPreparationError(f"{label} is missing")
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise ManagerIdentityExecutionPreparationError(f"{label} is unsafe")
    return path.resolve()


def _metadata(path: Path) -> dict[str, object]:
    info = path.stat()
    return {
        "source_path": str(path),
        "mode": info.st_mode & 0o777,
        "uid": info.st_uid,
        "gid": info.st_gid,
        "size": info.st_size,
        "sha256": sha_path(path),
    }


def _source_inventory(
    runtime: Mapping[str, Any],
) -> tuple[list[dict[str, object]], tuple[Path, ...]]:
    compose = runtime.get("compose")
    if not isinstance(compose, dict):
        raise ManagerIdentityExecutionPreparationError(
            "manager Compose binding is incomplete"
        )
    raw_files = compose.get("config_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ManagerIdentityExecutionPreparationError(
            "manager Compose file inventory is missing"
        )
    inventory: list[dict[str, object]] = []
    protected: list[Path] = []
    for index, saved in enumerate(raw_files):
        if not isinstance(saved, dict):
            raise ManagerIdentityExecutionPreparationError(
                "manager Compose file binding is invalid"
            )
        source = _absolute_file(saved.get("path"), "manager Compose file")
        current = _metadata(source)
        if any(
            current.get(field) != saved.get(field)
            for field in ("mode", "uid", "gid", "size", "sha256")
        ):
            raise ManagerIdentityExecutionPreparationError(
                "manager Compose file metadata drifted after live gate"
            )
        inventory.append(
            {
                **current,
                "archive_path": f"compose/config/{index:03d}{source.suffix or '.file'}",
                "kind": "compose_config",
            }
        )
        protected.append(source)
    environment = compose.get("environment")
    if environment is not None:
        if not isinstance(environment, dict):
            raise ManagerIdentityExecutionPreparationError(
                "manager Compose environment binding is invalid"
            )
        source = _absolute_file(
            environment.get("path"),
            "manager Compose environment",
        )
        current = _metadata(source)
        if any(
            current.get(field) != environment.get(field)
            for field in ("mode", "uid", "gid", "size", "sha256")
        ):
            raise ManagerIdentityExecutionPreparationError(
                "manager Compose environment metadata drifted after live gate"
            )
        inventory.append(
            {
                **current,
                "archive_path": "compose/environment/.env",
                "kind": "compose_environment",
            }
        )
        protected.append(source)
    secret_root = _absolute_target(
        runtime.get("target_secret_root"),
        "manager secret root",
    )
    password = _absolute_target(
        runtime.get("target_password_file"),
        "manager password target",
    )
    if not password.is_relative_to(secret_root):
        raise ManagerIdentityExecutionPreparationError(
            "manager password target escaped the secret root"
        )
    if password.exists() or password.is_symlink():
        raise ManagerIdentityExecutionPreparationError(
            "manager password target became active before rollback capture"
        )
    if secret_root.exists() and (
        not secret_root.is_dir() or secret_root.stat().st_mode & 0o077
    ):
        raise ManagerIdentityExecutionPreparationError(
            "manager secret root is not private"
        )
    working_dir = compose.get("working_dir")
    if not isinstance(working_dir, str):
        raise ManagerIdentityExecutionPreparationError(
            "manager Compose working directory is missing"
        )
    protected.extend((Path(working_dir).resolve(), secret_root, password))
    return inventory, tuple(protected)


def _reject_overlap(output: Path, protected: Sequence[Path]) -> None:
    for item in protected:
        resolved = item.resolve()
        if (
            output == resolved
            or output.is_relative_to(resolved)
            or resolved.is_relative_to(output)
        ):
            raise ManagerIdentityExecutionPreparationError(
                "execution preparation output overlaps a protected path"
            )
