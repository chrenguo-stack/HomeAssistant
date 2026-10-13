from __future__ import annotations

import json
from pathlib import Path

import pytest

from n3w_t1_golden_master_common import (
    GoldenMasterCommonError,
    authorization_record_path,
    claim_authorization,
    load_authorization_record,
    public_tree_sha256,
)


def test_authorization_ledger_is_one_shot(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    record = claim_authorization(
        ledger,
        authorization_id="AUTH-1",
        operation="BUILD",
        source_head="a" * 40,
        payload_manifest_sha256="b" * 64,
        release_id="release-1",
    )

    assert record["operation"] == "BUILD"
    assert load_authorization_record(ledger, "AUTH-1") == record
    path = authorization_record_path(ledger, "AUTH-1")
    assert path.stat().st_mode & 0o777 == 0o600
    assert ledger.stat().st_mode & 0o777 == 0o700

    with pytest.raises(
        GoldenMasterCommonError,
        match="authorization_already_consumed",
    ):
        claim_authorization(
            ledger,
            authorization_id="AUTH-1",
            operation="BUILD",
            source_head="a" * 40,
            payload_manifest_sha256="b" * 64,
            release_id="release-1",
        )


def test_public_tree_hash_rejects_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "target"
    target.write_text("x", encoding="utf-8")
    (root / "link").symlink_to(target)

    with pytest.raises(
        GoldenMasterCommonError,
        match="public_tree_symlink_forbidden",
    ):
        public_tree_sha256(root)


def test_authorization_record_tamper_fails_closed(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    claim_authorization(
        ledger,
        authorization_id="AUTH-2",
        operation="SEAL",
        source_head="a" * 40,
        payload_manifest_sha256="b" * 64,
        release_id="release-2",
    )
    path = authorization_record_path(ledger, "AUTH-2")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["source_head"] = "bad"
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(
        GoldenMasterCommonError,
        match="authorization_record_invalid",
    ):
        load_authorization_record(ledger, "AUTH-2")
