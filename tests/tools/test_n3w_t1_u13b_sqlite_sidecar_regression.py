from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from n3w_t1_core_updater_ha_backup import ProtectedHaDataBackupProvider
from n3w_t1_core_updater_ha_ipc import _public_code
from n3w_t1_core_updater_v2_common import UpdaterV2Error


def test_public_code_preserves_stable_prefix_before_private_detail() -> None:
    error = UpdaterV2Error(
        "ha_data_backup_archive_verify_failed:"
        "./home-assistant_v2.db-shm: Mod time differs"
    )
    assert _public_code(error) == "ha_data_backup_archive_verify_failed"
    assert _public_code(UpdaterV2Error("detail with spaces")) == "ota_host_rejected"


@pytest.mark.skipif(
    shutil.which("openssl") is None or shutil.which("tar") is None,
    reason="openssl/tar unavailable",
)
def test_restore_preserves_exact_sqlite_sidecar_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "ha"
    source.mkdir(mode=0o700)
    (source / "configuration.yaml").write_text(
        "default_config:\n",
        encoding="utf-8",
    )
    shm = source / "home-assistant_v2.db-shm"
    wal = source / "home-assistant_v2.db-wal"
    shm.write_bytes(b"stable-shm")
    wal.write_bytes(b"")
    shm_times = (1_700_000_000_000_000_000, 1_700_000_001_000_000_000)
    wal_times = (1_700_000_002_000_000_000, 1_700_000_003_000_000_000)
    os.utime(shm, ns=shm_times)
    os.utime(wal, ns=wal_times)

    root_key = tmp_path / "system-root.key"
    root_key.write_bytes(os.urandom(32))
    root_key.chmod(0o600)
    destination = tmp_path / "backup"
    destination.mkdir(mode=0o700)

    provider = ProtectedHaDataBackupProvider(
        ha_data_root=source,
        system_root_key=root_key,
        product_config=source / "configuration.yaml",
    )
    transaction_id = "a" * 64
    record = provider.create_consistent_backup(
        transaction_id_sha256=transaction_id,
        destination_root=destination,
    )

    (source / "configuration.yaml").write_text(
        "target-state:\n",
        encoding="utf-8",
    )

    def perturb_sidecar_metadata() -> None:
        current = shm.stat()
        os.utime(
            shm,
            ns=(current.st_atime_ns, current.st_mtime_ns + 5_000_000_000),
        )

    monkeypatch.setattr(provider, "_verify_sqlite", perturb_sidecar_metadata)

    assert provider.restore_preupgrade_backup(
        record,
        transaction_id_sha256=transaction_id,
        source_root=destination,
    ) == record

    assert shm.stat().st_mtime_ns == shm_times[1]
    assert wal.stat().st_mtime_ns == wal_times[1]
    assert provider.verify_restored_preupgrade_backup_readonly(
        record,
        transaction_id_sha256=transaction_id,
        source_root=destination,
    ) == record
