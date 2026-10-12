from __future__ import annotations

import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_fresh_product_staging_host.py"


def load_tool():
    name = "n3w_t1_fresh_product_staging_host"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def manifest() -> dict[str, object]:
    images = {
        "homeassistant": {
            "path": "artifact/homeassistant-arm64.tar",
            "tar_size_bytes": 1000,
            "loaded_size_bytes": 1400,
            "image_ref": "local/ha:test",
        },
        "manager": {
            "path": "artifact/greenhouse-manager-arm64.tar",
            "tar_size_bytes": 200,
            "loaded_size_bytes": 250,
            "image_ref": "local/manager:test",
        },
        "broker": {
            "path": "artifact/broker-arm64.tar",
            "tar_size_bytes": 100,
            "loaded_size_bytes": 120,
            "image_ref": "local/broker:test",
        },
    }
    return {
        "files": [
            {"path": record["path"], "size": record["tar_size_bytes"]}
            for record in images.values()
        ],
        "transport": {
            "schema": "gh.n3w-t1-fresh-transport/1",
            "remote_staging_root": "/var/tmp",
            "minimum_post_peak_free_bytes": 5 * 1024 * 1024 * 1024,
            "payload_uncompressed_bytes": 1500,
            "image_load_order": ["homeassistant", "manager", "broker"],
            "images": images,
        },
    }


def test_transport_plan_keeps_five_gib_after_worst_peak() -> None:
    tool = load_tool()
    remote_free = 8 * 1024 * 1024 * 1024
    plan = tool._plan_transport(
        manifest(),
        archive_size_bytes=500,
        remote_free_bytes=remote_free,
    )

    assert plan.extraction_peak_bytes == 2000
    assert plan.image_load_peak_bytes == 2900
    assert plan.required_peak_bytes == 2900
    assert plan.required_free_bytes == 2900 + 5 * 1024 * 1024 * 1024
    assert plan.capacity_pass is True


def test_transport_plan_fails_without_post_peak_reserve() -> None:
    tool = load_tool()
    required = 2900 + 5 * 1024 * 1024 * 1024

    plan = tool._plan_transport(
        manifest(),
        archive_size_bytes=500,
        remote_free_bytes=required - 1,
    )

    assert plan.capacity_pass is False


def test_remote_storage_rejects_tmpfs(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = load_tool()

    class Result:
        returncode = 0
        stdout = json.dumps(
            {
                "staging_root": "/var/tmp",
                "docker_root": "/var/lib/docker",
                "staging_device": 1,
                "docker_device": 1,
                "staging_free_bytes": 10_000_000_000,
                "docker_free_bytes": 10_000_000_000,
                "staging_fstype": "tmpfs",
            }
        )
        stderr = ""

    monkeypatch.setattr(tool, "_run", lambda *_args, **_kwargs: Result())

    with pytest.raises(
        tool.FreshHostTransportError,
        match="memory_filesystem",
    ):
        tool._remote_storage_report("root@example")


def test_remote_storage_rejects_different_docker_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()

    class Result:
        returncode = 0
        stdout = json.dumps(
            {
                "staging_root": "/var/tmp",
                "docker_root": "/var/lib/docker",
                "staging_device": 1,
                "docker_device": 2,
                "staging_free_bytes": 10_000_000_000,
                "docker_free_bytes": 10_000_000_000,
                "staging_fstype": "ext4",
            }
        )
        stderr = ""

    monkeypatch.setattr(tool, "_run", lambda *_args, **_kwargs: Result())

    with pytest.raises(
        tool.FreshHostTransportError,
        match="filesystems_differ",
    ):
        tool._remote_storage_report("root@example")


def test_sequential_load_releases_each_tar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    calls: list[tuple[str, ...]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        return Result()

    monkeypatch.setattr(tool, "_run", fake_run)
    tool._remote_load_images_sequentially(
        "root@example",
        "/var/tmp/payload",
        manifest(),
    )

    assert len(calls) == 6
    for index in range(0, 6, 2):
        assert "docker load --input" in calls[index][3]
        assert "rm -f" in calls[index + 1][3]
    assert all("docker pull" not in " ".join(call) for call in calls)


def test_cli_only_exposes_read_only_preflight() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'choices=("preflight",)' in source
    assert "authorization_claimed" in source
    assert '"docker_mutation": False' in source


def _write_payload_archive(path: Path, *, link: bool) -> str:
    manifest = json.dumps(
        {
            "transport": {
                "schema": "gh.n3w-t1-fresh-transport/1",
                "remote_staging_root": "/var/tmp",
                "minimum_post_peak_free_bytes": 5 * 1024 * 1024 * 1024,
                "payload_uncompressed_bytes": 1,
                "image_load_order": ["homeassistant", "manager", "broker"],
                "images": {},
            },
            "files": [],
        },
        sort_keys=True,
    ).encode()
    with tarfile.open(path, "w:gz") as bundle:
        info = tarfile.TarInfo("payload-manifest.json")
        info.size = len(manifest)
        bundle.addfile(info, io.BytesIO(manifest))
        if link:
            symlink = tarfile.TarInfo("unsafe-link")
            symlink.type = tarfile.SYMTYPE
            symlink.linkname = "/etc/passwd"
            bundle.addfile(symlink)
    import hashlib
    return hashlib.sha256(manifest).hexdigest()


def test_payload_reader_rejects_symlink_member(tmp_path: Path) -> None:
    tool = load_tool()
    archive = tmp_path / "payload.tar.gz"
    manifest_sha = _write_payload_archive(archive, link=True)

    with pytest.raises(
        tool.FreshHostTransportError,
        match="payload_link_member_forbidden",
    ):
        tool._read_payload_manifest(
            archive,
            manifest_sha256=manifest_sha,
        )


def test_fresh_compose_requires_explicit_manager_image() -> None:
    compose = (
        ROOT
        / "infra/n3w-t1/production/docker-compose.fresh.yml"
    ).read_text(encoding="utf-8")

    assert "${GH_MANAGER_IMAGE:?GH_MANAGER_IMAGE required}" in compose
    assert "local/greenhouse-manager:s20-511db028" not in compose
