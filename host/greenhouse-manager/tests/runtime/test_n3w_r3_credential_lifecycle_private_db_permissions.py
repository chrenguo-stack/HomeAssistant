from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from greenhouse_manager.runtime.credential_lifecycle import (
    CredentialLifecycleStore,
)
from greenhouse_manager.runtime.n3w_simplified_product_runtime import (
    SimplifiedProductRuntimeError,
    _ensure_private_database,
)


def test_manager_created_credential_db_passes_private_pairing_gate(
    tmp_path: Path,
) -> None:
    database = tmp_path / "credential-lifecycle.sqlite3"

    previous_umask = os.umask(0)
    try:
        with CredentialLifecycleStore(database):
            pass
    finally:
        os.umask(previous_umask)

    assert stat.S_IMODE(database.stat().st_mode) == 0o600

    _ensure_private_database(database)


def test_existing_non_private_credential_db_is_not_silently_normalized(
    tmp_path: Path,
) -> None:
    database = tmp_path / "credential-lifecycle.sqlite3"
    database.touch()
    os.chmod(database, 0o644)

    with CredentialLifecycleStore(database):
        pass

    assert stat.S_IMODE(database.stat().st_mode) == 0o644

    with pytest.raises(
        SimplifiedProductRuntimeError,
        match="private_database_permissions_invalid",
    ):
        _ensure_private_database(database)
