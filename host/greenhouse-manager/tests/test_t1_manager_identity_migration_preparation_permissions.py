from __future__ import annotations

from pathlib import Path

import pytest

from greenhouse_manager.t1_manager_identity_migration_preparation import (
    ManagerIdentityMigrationPreparationError,
    _private_directory,
)


def test_private_directory_rejects_group_access(tmp_path: Path) -> None:
    path = tmp_path / "public"
    path.mkdir(mode=0o750)
    path.chmod(0o750)

    with pytest.raises(
        ManagerIdentityMigrationPreparationError,
        match="public",
    ):
        _private_directory(path, "test directory")
