from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from greenhouse_manager.t1_manager_identity_migration_authorization import (
    ManagerIdentityMigrationAuthorizationError,
    _reject_output,
    create_manager_identity_migration_authorization,
)


def test_protected_output_is_rejected_without_creating_directory(
    tmp_path: Path,
) -> None:
    preparation = tmp_path / "greenhouse-manager-migration-preparation-test"
    compose = tmp_path / "compose"
    secret = tmp_path / "secrets"
    for path in (preparation, compose, secret):
        path.mkdir(mode=0o700)
    output = secret / "greenhouse-m2-manager-authorizations-forbidden"

    with pytest.raises(
        ManagerIdentityMigrationAuthorizationError,
        match="overlaps",
    ):
        _reject_output(output, preparation, (compose, secret))

    assert not output.exists()


def test_create_checks_output_overlap_before_private_directory_creation() -> None:
    source = inspect.getsource(create_manager_identity_migration_authorization)
    reject = source.index("_reject_output(requested_output")
    create = source.index("_private_output_directory(requested_output)")
    assert reject < create
