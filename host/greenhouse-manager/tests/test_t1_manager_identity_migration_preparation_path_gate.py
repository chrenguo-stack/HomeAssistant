from __future__ import annotations

from pathlib import Path

import pytest

from greenhouse_manager.t1_manager_identity_migration_preparation import (
    ManagerIdentityMigrationPreparationError,
    _reject_output,
)


def test_reject_output_inside_active_compose_or_secret_root(tmp_path: Path) -> None:
    compose = tmp_path / "compose"
    secret = tmp_path / "secrets"
    source = tmp_path / "source"
    for path in (compose, secret, source):
        path.mkdir()

    for output in (compose / "out", secret / "out", source / "out"):
        with pytest.raises(
            ManagerIdentityMigrationPreparationError,
            match="overlaps",
        ):
            _reject_output(
                output,
                active_roots=(compose, secret),
                source_roots=(source,),
            )
