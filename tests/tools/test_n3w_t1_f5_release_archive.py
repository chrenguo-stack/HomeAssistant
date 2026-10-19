from __future__ import annotations

import hashlib
import json
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest

from tools import n3w_t1_f5_release_archive as archive


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _release_zip(
    path: Path,
    *,
    release_id: str,
    source_head: str,
    source_tree: str,
    builder_head: str,
) -> tuple[str, str, str]:
    release = {
        "schema": "gh.n3w-t1-production-release/1",
        "release_id": release_id,
        "source_head": source_head,
    }
    release_raw = (
        json.dumps(release, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    provenance = {
        "source_head": source_head,
        "source_tree": source_tree,
        "builder_head": builder_head,
    }
    provenance_raw = (
        json.dumps(provenance, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    payload = b"payload\n"
    preindex = {
        "approved-release.json": release_raw,
        "approved-release.sha256": (_sha(release_raw) + "\n").encode(),
        "release-provenance.json": provenance_raw,
        "payload.bin": payload,
    }
    records = [
        {"path": name, "sha256": _sha(raw), "size": len(raw)}
        for name, raw in sorted(preindex.items())
    ]
    index = {
        "schema": archive.INDEX_SCHEMA,
        "files": records,
    }
    index_raw = (json.dumps(index, sort_keys=True, indent=2) + "\n").encode()
    values = {
        **preindex,
        "release-file-index.json": index_raw,
        "release-file-index.sha256": (_sha(index_raw) + "\n").encode(),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name, raw in values.items():
            bundle.writestr(name, raw)
    return _sha(path.read_bytes()), _sha(release_raw), _sha(index_raw)


def _args(
    tmp_path: Path,
    *,
    artifact_sha: str,
    release_sha: str,
    index_sha: str,
) -> Namespace:
    return Namespace(
        run_id="39179587513",
        artifact_name="n3w-t1-f5-approved-release-" + "a" * 40,
        artifact_id=12156115228,
        artifact_zip_sha256=artifact_sha,
        release_id="1" * 64,
        release_sha256=release_sha,
        file_index_sha256=index_sha,
        source_head="a" * 40,
        source_tree="b" * 40,
        builder_head="c" * 40,
        archive_root=str(tmp_path / "archive"),
    )


def test_verify_release_zip_binds_full_index(tmp_path: Path) -> None:
    path = tmp_path / "release.zip"
    artifact_sha, release_sha, index_sha = _release_zip(
        path,
        release_id="1" * 64,
        source_head="a" * 40,
        source_tree="b" * 40,
        builder_head="c" * 40,
    )
    result = archive._verify_release_zip(
        path,
        release_id="1" * 64,
        release_sha256=release_sha,
        file_index_sha256=index_sha,
        source_head="a" * 40,
        source_tree="b" * 40,
        builder_head="c" * 40,
    )
    assert result["release_id"] == "1" * 64
    assert artifact_sha == archive._sha256_file(path)


def test_verify_release_zip_rejects_indexed_file_tamper(tmp_path: Path) -> None:
    path = tmp_path / "release.zip"
    _artifact_sha, release_sha, index_sha = _release_zip(
        path,
        release_id="1" * 64,
        source_head="a" * 40,
        source_tree="b" * 40,
        builder_head="c" * 40,
    )
    rewritten = tmp_path / "tampered.zip"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(
        rewritten,
        "w",
        compression=zipfile.ZIP_STORED,
    ) as target:
        for item in source.infolist():
            raw = source.read(item.filename)
            if item.filename == "payload.bin":
                raw = b"tampered\n"
            target.writestr(item.filename, raw)
    with pytest.raises(
        archive.ReleaseArchiveError,
        match="release_index_size_mismatch|release_index_file_sha256_mismatch",
    ):
        archive._verify_release_zip(
            rewritten,
            release_id="1" * 64,
            release_sha256=release_sha,
            file_index_sha256=index_sha,
            source_head="a" * 40,
            source_tree="b" * 40,
            builder_head="c" * 40,
        )


def test_archive_miss_populates_then_verify_is_network_free(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.zip"
    artifact_sha, release_sha, index_sha = _release_zip(
        source,
        release_id="1" * 64,
        source_head="a" * 40,
        source_tree="b" * 40,
        builder_head="c" * 40,
    )
    args = _args(
        tmp_path,
        artifact_sha=artifact_sha,
        release_sha=release_sha,
        index_sha=index_sha,
    )
    calls = {"metadata": 0, "download": 0}

    def metadata(**_kwargs):
        calls["metadata"] += 1
        return {}

    def download(destination, *, artifact_id):
        assert artifact_id == args.artifact_id
        calls["download"] += 1
        destination.write_bytes(source.read_bytes())

    monkeypatch.setattr(archive, "_artifact_metadata", metadata)
    monkeypatch.setattr(archive, "_download_artifact", download)
    first = archive.archive(args)
    assert first["archive_status"] == "MISS_POPULATED"
    assert calls == {"metadata": 1, "download": 1}

    monkeypatch.setattr(
        archive,
        "_artifact_metadata",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("network metadata must not be used")
        ),
    )
    monkeypatch.setattr(
        archive,
        "_download_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("network download must not be used")
        ),
    )
    second = archive.verify(args)
    assert second["archive_status"] == "VERIFY_ONLY"


def test_existing_corrupt_archive_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.zip"
    artifact_sha, release_sha, index_sha = _release_zip(
        source,
        release_id="1" * 64,
        source_head="a" * 40,
        source_tree="b" * 40,
        builder_head="c" * 40,
    )
    args = _args(
        tmp_path,
        artifact_sha=artifact_sha,
        release_sha=release_sha,
        index_sha=index_sha,
    )
    monkeypatch.setattr(archive, "_artifact_metadata", lambda **_kwargs: {})
    monkeypatch.setattr(
        archive,
        "_download_artifact",
        lambda destination, **_kwargs: destination.write_bytes(source.read_bytes()),
    )
    archive.archive(args)
    _root, _binding, entry = archive._arguments(args)
    (entry / "artifact.zip").write_bytes(b"broken")
    with pytest.raises(
        archive.ReleaseArchiveError,
        match="archive_zip_sha256_mismatch",
    ):
        archive.archive(args)
