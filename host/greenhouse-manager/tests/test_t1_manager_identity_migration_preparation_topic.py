from __future__ import annotations

from pathlib import Path

import pytest

from greenhouse_manager.t1_manager_identity_migration_preparation import (
    prepare_manager_identity_migration,
)


def test_manager_preparation_rejects_non_greenhouse_topic(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="gh namespace"):
        prepare_manager_identity_migration(
            tmp_path / "postactivation",
            tmp_path / "stage",
            tmp_path / "output",
            expected_retained_topic="other/topic",
        )
