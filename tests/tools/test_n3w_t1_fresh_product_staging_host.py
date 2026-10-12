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


def test_cli_exposes_preflight_and_apply_with_explicit_authorization() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'choices=("preflight", "apply")' in source
    assert 'parser.add_argument("--authorization-id")' in source
    assert "authorization_id_mismatch" in source
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


def _run_apply_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    process_lines: list[str],
    process_returncode: int,
    run_results: list[object],
) -> tuple[int, dict[str, object]]:
    tool = load_tool()
    work = tmp_path / "work"
    work.mkdir()
    archive = work / "payload.tar.gz"
    archive.write_bytes(b"x")
    authorization = "N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_01"

    monkeypatch.setattr(tool.tempfile, "mkdtemp", lambda **_kwargs: str(work))
    monkeypatch.setattr(tool, "_download_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tool, "_verify_outer_artifact", lambda *_args, **_kwargs: archive)
    monkeypatch.setattr(
        tool,
        "_read_payload_manifest",
        lambda *_args, **_kwargs: {
            "authorization_id": authorization,
            **manifest(),
        },
    )
    monkeypatch.setattr(
        tool,
        "_remote_storage_report",
        lambda *_args, **_kwargs: {"staging_free_bytes": 8 * 1024 * 1024 * 1024},
    )
    monkeypatch.setattr(
        tool,
        "_plan_transport",
        lambda *_args, **_kwargs: tool.TransportPlan(
            archive_size_bytes=1,
            payload_uncompressed_bytes=1,
            extraction_peak_bytes=2,
            image_load_peak_bytes=2,
            required_peak_bytes=2,
            minimum_post_peak_free_bytes=5 * 1024 * 1024 * 1024,
            required_free_bytes=5 * 1024 * 1024 * 1024 + 2,
            remote_free_bytes=8 * 1024 * 1024 * 1024,
            free_after_estimated_peak_bytes=8 * 1024 * 1024 * 1024 - 2,
            image_load_order=("homeassistant", "manager", "broker"),
            capacity_pass=True,
        ),
    )
    monkeypatch.setattr(
        tool,
        "_remote_mktemp",
        lambda *_args, **_kwargs: "/var/tmp/n3w-fresh-bootstrap.test",
    )
    monkeypatch.setattr(
        tool,
        "_remote_prepare_payload",
        lambda *_args, **_kwargs: None,
    )

    class FakeProcess:
        stdout = iter(process_lines)

        def wait(self):
            return process_returncode

    monkeypatch.setattr(tool.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess())

    outcomes = iter(run_results)

    def fake_run(*_args, **_kwargs):
        value = next(outcomes)
        if isinstance(value, str) and value.startswith("ERROR:"):
            raise tool.FreshHostTransportError(value.removeprefix("ERROR:"))
        return value

    monkeypatch.setattr(tool, "_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(TOOL),
            "--t1",
            "root@example",
            "--phase",
            "apply",
            "--run-id",
            "1",
            "--artifact-name",
            "artifact",
            "--archive-sha256",
            "0" * 64,
            "--manifest-sha256",
            "1" * 64,
            "--authorization-id",
            authorization,
        ],
    )

    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    rc = tool.main()
    documents = [
        json.loads(line)
        for line in output.getvalue().splitlines()
        if line.startswith("{")
    ]
    return rc, documents[-1]


def test_marker_probe_failure_after_claim_is_consumed_no_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    rc, report = _run_apply_main(
        monkeypatch,
        tmp_path,
        process_lines=[
            json.dumps(
                {
                    "event": "authorization_claimed",
                    "authorization_id": tool.AUTHORIZATION_ID,
                },
                separators=(",", ":"),
            )
            + "\n"
        ],
        process_returncode=1,
        run_results=["ERROR:marker_probe_unreachable"],
    )

    assert rc == 2
    assert report["status"] == "STOP_PARTIAL"
    assert report["authorization_claimed"] is True
    assert report["authorization_consumed"] is True
    assert report["replay_allowed"] is False


def test_marker_probe_failure_without_claim_is_unknown_and_consumed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    rc, report = _run_apply_main(
        monkeypatch,
        tmp_path,
        process_lines=[],
        process_returncode=255,
        run_results=["ERROR:marker_probe_unreachable"],
    )

    assert rc == 2
    assert report["status"] == "STOP_UNKNOWN"
    assert report["authorization_claimed"] is None
    assert report["authorization_consumed"] is True
    assert report["replay_allowed"] is False


def test_postsuccess_cleanup_failure_preserves_consumed_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()

    class Result:
        returncode = 0

    rc, report = _run_apply_main(
        monkeypatch,
        tmp_path,
        process_lines=[
            json.dumps(
                {
                    "event": "authorization_claimed",
                    "authorization_id": tool.AUTHORIZATION_ID,
                },
                separators=(",", ":"),
            )
            + "\n"
        ],
        process_returncode=0,
        run_results=[
            Result(),
            "ERROR:cleanup_unreachable",
        ],
    )

    assert rc == 2
    assert report["status"] == "STOP_POSTSUCCESS_CLEANUP"
    assert report["apply_result"] == "PASS"
    assert report["authorization_claimed"] is True
    assert report["authorization_consumed"] is True
    assert report["replay_allowed"] is False
    assert report["fresh_product_staged"] is True


def test_preclaim_failure_does_not_claim_and_does_not_fake_cleanup_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()

    class MarkerAbsent:
        returncode = 1

    class CleanupFailed:
        returncode = 255

    rc, report = _run_apply_main(
        monkeypatch,
        tmp_path,
        process_lines=[],
        process_returncode=1,
        run_results=[MarkerAbsent(), CleanupFailed()],
    )

    assert rc == 1
    assert report["status"] == "STOP_PRECLAIM"
    assert report["authorization_claimed"] is False
    assert report["authorization_consumed"] is False
    assert report["remote_payload_removed"] is False
    assert report["remote_payload_preserved"] is True
