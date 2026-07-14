from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from greenhouse_manager.t1_manager_identity_migration_execution_preparation import (
    ManagerIdentityExecutionPreparationError,
)
from greenhouse_manager.t1_manager_identity_migration_execution_preparation_rollback import (
    verify_rollback_archive,
)


def _archive(tmp_path: Path, **overrides: object) -> Path:
    manifest: dict[str, object] = {
        "schema": "gh.m2.t1-manager-identity-fresh-rollback/1",
        "manager_only": True,
        "preserve_anonymous": True,
        "anonymous_closure_enabled": False,
        "files": [],
    }
    manifest.update(overrides)
    path = tmp_path / "fresh-manager-rollback.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        payload = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
        info = tarfile.TarInfo("rollback-manifest.json")
        info.size = len(payload)
        info.mode = 0o600
        archive.addfile(info, io.BytesIO(payload))
    path.chmod(0o600)
    return path


def test_accepts_required_rollback_safety_binding(tmp_path: Path) -> None:
    manifest = verify_rollback_archive(_archive(tmp_path))

    assert manifest["manager_only"] is True
    assert manifest["preserve_anonymous"] is True
    assert manifest["anonymous_closure_enabled"] is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"manager_only": False},
        {"preserve_anonymous": False},
        {"anonymous_closure_enabled": True},
    ],
)
def test_rejects_contradictory_rollback_safety_binding(
    tmp_path: Path,
    overrides: dict[str, object],
) -> None:
    with pytest.raises(
        ManagerIdentityExecutionPreparationError,
        match="safety binding is invalid",
    ):
        verify_rollback_archive(_archive(tmp_path, **overrides))
