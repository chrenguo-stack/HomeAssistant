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
AUTHORIZATION_ID = "N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_LIVE_APPLY_R3_20261014_01"


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
    reserve = 5 * 1024 * 1024 * 1024
    images = {
        "homeassistant": {
            "path": "incoming/homeassistant-arm64.tar",
            "artifact_file": "homeassistant-arm64.tar",
            "tar_sha256": "a" * 64,
            "tar_size_bytes": 1000,
            "loaded_size_bytes": 1400,
            "required_free_bytes": reserve + 2400,
            "image_ref": "local/ha:test",
        },
        "manager": {
            "path": "incoming/greenhouse-manager-arm64.tar",
            "artifact_file": "greenhouse-manager-arm64.tar",
            "tar_sha256": "b" * 64,
            "tar_size_bytes": 200,
            "loaded_size_bytes": 250,
            "required_free_bytes": reserve + 450,
            "image_ref": "local/manager:test",
        },
        "broker": {
            "path": "incoming/broker-arm64.tar",
            "artifact_file": "broker-arm64.tar",
            "tar_sha256": "c" * 64,
            "tar_size_bytes": 100,
            "loaded_size_bytes": 120,
            "required_free_bytes": reserve + 220,
            "image_ref": "local/broker:test",
        },
    }
    return {
        "source_head": "d" * 40,
        "images": {
            label: {
                **record,
                "image": record["image_ref"],
            }
            for label, record in images.items()
        },
        "files": [],
        "transport": {
            "schema": "gh.n3w-t1-fresh-transport/2",
            "remote_staging_root": "/var/tmp",
            "minimum_post_peak_free_bytes": reserve,
            "runtime_payload_uncompressed_bytes": 1500,
            "image_load_order": ["homeassistant", "manager", "broker"],
            "images": images,
        },
    }


def capacity() -> dict[str, object]:
    m = manifest()
    return {
        "schema": "gh.n3w-t1-fresh-capacity/1",
        "source_head": m["source_head"],
        "minimum_post_peak_free_bytes": 5 * 1024 * 1024 * 1024,
        "image_load_order": ["homeassistant", "manager", "broker"],
        "images": m["transport"]["images"],
    }


def test_transport_plan_keeps_five_gib_after_worst_step() -> None:
    tool = load_tool()
    remote_free = 8 * 1024 * 1024 * 1024
    plan = tool._plan_transport(
        manifest(),
        archive_size_bytes=500,
        remote_free_bytes=remote_free,
        capacity=capacity(),
    )

    assert plan.runtime_extraction_peak_bytes == 2000
    assert plan.worst_image_required_free_bytes == (
        5 * 1024 * 1024 * 1024 + 2400
    )
    assert plan.remote_staged_image_count_max == 1
    assert plan.capacity_pass is True


def test_transport_plan_fails_without_worst_image_envelope() -> None:
    tool = load_tool()
    required = 5 * 1024 * 1024 * 1024 + 2400

    plan = tool._plan_transport(
        manifest(),
        archive_size_bytes=500,
        remote_free_bytes=required - 1,
        capacity=capacity(),
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
                "image_store_backend": "containerd",
                "image_store_root": "/var/lib/containerd",
                "image_store_root_source": "containerd_default_root",
                "staging_device": 1,
                "docker_device": 1,
                "image_store_device": 1,
                "staging_free_bytes": 10_000_000_000,
                "docker_free_bytes": 10_000_000_000,
                "image_store_free_bytes": 10_000_000_000,
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
                "image_store_backend": "containerd",
                "image_store_root": "/var/lib/containerd",
                "image_store_root_source": "containerd_default_root",
                "staging_device": 1,
                "docker_device": 2,
                "image_store_device": 2,
                "staging_free_bytes": 10_000_000_000,
                "docker_free_bytes": 10_000_000_000,
                "image_store_free_bytes": 10_000_000_000,
                "staging_fstype": "ext4",
            }
        )
        stderr = ""

    monkeypatch.setattr(tool, "_run", lambda *_args, **_kwargs: Result())

    with pytest.raises(
        tool.FreshHostTransportError,
        match="staging_docker_image_store_filesystems_differ",
    ):
        tool._remote_storage_report("root@example")


def test_remote_storage_rejects_unresolved_containerd_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()

    class Result:
        returncode = 0
        stdout = json.dumps(
            {
                "staging_root": "/var/tmp",
                "docker_root": "/var/lib/docker",
                "image_store_backend": "containerd",
                "image_store_root": "/var/lib/containerd",
                "image_store_root_source": "guessed_fallback",
                "staging_device": 1,
                "docker_device": 1,
                "image_store_device": 1,
                "staging_free_bytes": 10_000_000_000,
                "docker_free_bytes": 10_000_000_000,
                "image_store_free_bytes": 10_000_000_000,
                "staging_fstype": "ext4",
            }
        )
        stderr = ""

    monkeypatch.setattr(tool, "_run", lambda *_args, **_kwargs: Result())

    with pytest.raises(
        tool.FreshHostTransportError,
        match="containerd_root_authority_unresolved",
    ):
        tool._remote_storage_report("root@example")


def test_storage_probe_rejects_containerd_imports_by_contract() -> None:
    tool = load_tool()
    script = tool._remote_storage_probe_script()

    assert '"containerd_imports_unsupported"' in script
    assert 'config.get("imports")' in script


def test_storage_probe_requires_active_containerd_authority() -> None:
    tool = load_tool()
    script = tool._remote_storage_probe_script()

    compile(script, "<n3w-storage-probe>", "exec")
    assert '"/var/lib/containerd"' in script
    assert '"containerd_service_not_running"' in script
    assert '"containerd_address_mismatch"' in script
    assert '"image_store_root_unresolved"' in script
    assert "containerd_probe" not in script


def _storage_probe_fixture(
    tmp_path: Path,
    *,
    containerd_config: str,
) -> tuple[dict[str, str], object, object]:
    tool = load_tool()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_root = tmp_path / "docker-root"
    image_root = tmp_path / "image-store"
    docker_root.mkdir()
    image_root.mkdir()
    config_path = tmp_path / "containerd.toml"
    config_path.write_text(containerd_config, encoding="utf-8")
    socket_path = tmp_path / "containerd.sock"
    process_stub = tmp_path / "process_stub.py"
    process_stub.write_text(
        "import time\ntime.sleep(60)\n",
        encoding="utf-8",
    )

    dockerd = tool.subprocess.Popen(
        (
            sys.executable,
            str(process_stub),
            f"--containerd={socket_path}",
        )
    )
    containerd = tool.subprocess.Popen(
        (
            sys.executable,
            str(process_stub),
            f"--config={config_path}",
            f"--address={socket_path}",
        )
    )

    def write_executable(name: str, body: str) -> None:
        path = bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    docker_info = json.dumps(
        {
            "DockerRootDir": str(docker_root),
            "DriverStatus": [
                ["driver-type", "io.containerd.snapshotter.v1"],
            ],
        }
    )
    write_executable(
        "docker",
        "#!/bin/sh\n"
        "if [ \"$1\" = info ]; then\n"
        f"  printf '%s\\n' {json.dumps(docker_info)}\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n",
    )
    write_executable(
        "systemctl",
        "#!/bin/sh\n"
        "case \"$2\" in\n"
        f"  docker) printf '%s\\n' {dockerd.pid} ;;\n"
        f"  containerd) printf '%s\\n' {containerd.pid} ;;\n"
        "  *) exit 2 ;;\n"
        "esac\n",
    )
    write_executable(
        "findmnt",
        "#!/bin/sh\nprintf '%s\\n' ext4\n",
    )

    env = dict(__import__("os").environ)
    env["PATH"] = str(bin_dir) + __import__("os").pathsep + env["PATH"]
    return env, dockerd, containerd


def _stop_probe_processes(*processes: object) -> None:
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except Exception:
            process.kill()
            process.wait(timeout=5)


def test_generated_storage_probe_uses_direct_containerd_root(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    image_root = tmp_path / "image-store"
    config = (
        'version = 2\n'
        f'root = "{image_root}"\n'
        '[grpc]\n'
        f'address = "{tmp_path / "containerd.sock"}"\n'
    )
    env, dockerd, containerd = _storage_probe_fixture(
        tmp_path,
        containerd_config=config,
    )
    try:
        completed = tool.subprocess.run(
            (sys.executable, "-c", tool._remote_storage_probe_script()),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        _stop_probe_processes(dockerd, containerd)

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["image_store_backend"] == "containerd"
    assert report["image_store_root"] == str(image_root.resolve())
    assert report["image_store_root_source"] == "containerd_config_root"


def test_generated_storage_probe_rejects_containerd_imports(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    base_root = tmp_path / "image-store"
    override_root = tmp_path / "override-store"
    imported = tmp_path / "override.toml"
    override_root.mkdir()
    imported.write_text(
        f'root = "{override_root}"\n',
        encoding="utf-8",
    )
    config = (
        'version = 2\n'
        f'root = "{base_root}"\n'
        f'imports = ["{imported}"]\n'
        '[grpc]\n'
        f'address = "{tmp_path / "containerd.sock"}"\n'
    )
    env, dockerd, containerd = _storage_probe_fixture(
        tmp_path,
        containerd_config=config,
    )
    try:
        completed = tool.subprocess.run(
            (sys.executable, "-c", tool._remote_storage_probe_script()),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        _stop_probe_processes(dockerd, containerd)

    assert completed.returncode != 0
    assert "containerd_imports_unsupported" in completed.stderr


def _write_artifact_zip(tool, path: Path) -> str:
    import zipfile

    with zipfile.ZipFile(path, "w") as bundle:
        for name in sorted(tool.ARTIFACT_OUTER_FILES):
            bundle.writestr(name, name.encode())
    return tool._sha256_file(path)


def _write_cache_entry(
    tool,
    cache_root: Path,
    source_zip: Path,
    *,
    run_id: str,
    artifact_name: str,
    artifact_id: int,
    artifact_sha: str,
) -> Path:
    entry = cache_root / str(artifact_id) / artifact_sha
    entry.mkdir(parents=True)
    (entry / "artifact.zip").write_bytes(source_zip.read_bytes())
    binding = tool._artifact_cache_binding(
        run_id=run_id,
        artifact_name=artifact_name,
        artifact_id=artifact_id,
        artifact_zip_sha256=artifact_sha,
    )
    (entry / "binding.json").write_text(
        json.dumps(binding, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return entry


def test_exact_artifact_cache_hit_skips_github_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    source_zip = tmp_path / "source.zip"
    artifact_sha = _write_artifact_zip(tool, source_zip)
    cache_root = tmp_path / "cache"
    _write_cache_entry(
        tool,
        cache_root,
        source_zip,
        run_id="1",
        artifact_name="artifact",
        artifact_id=123,
        artifact_sha=artifact_sha,
    )
    work = tmp_path / "work"
    work.mkdir()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("github access forbidden on exact cache hit")

    monkeypatch.setattr(tool, "_artifact_metadata", forbidden)
    monkeypatch.setattr(tool, "_download_remote_artifact_zip", forbidden)

    status = tool._download_artifact(
        work,
        run_id="1",
        artifact_name="artifact",
        artifact_id=123,
        artifact_zip_sha256=artifact_sha,
        cache_root=cache_root,
    )

    assert status == "HIT"
    assert {path.name for path in work.iterdir()} == tool.ARTIFACT_OUTER_FILES


def test_exact_artifact_cache_sha_mismatch_fails_closed_without_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    source_zip = tmp_path / "source.zip"
    artifact_sha = _write_artifact_zip(tool, source_zip)
    cache_root = tmp_path / "cache"
    entry = _write_cache_entry(
        tool,
        cache_root,
        source_zip,
        run_id="1",
        artifact_name="artifact",
        artifact_id=123,
        artifact_sha=artifact_sha,
    )
    (entry / "artifact.zip").write_bytes(b"corrupt")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("invalid cache must not be hidden by download")

    monkeypatch.setattr(tool, "_artifact_metadata", forbidden)
    monkeypatch.setattr(tool, "_download_remote_artifact_zip", forbidden)

    with pytest.raises(
        tool.FreshHostTransportError,
        match="artifact_cache_zip_sha256_mismatch",
    ):
        tool._download_artifact(
            tmp_path / "work",
            run_id="1",
            artifact_name="artifact",
            artifact_id=123,
            artifact_zip_sha256=artifact_sha,
            cache_root=cache_root,
        )


def test_exact_artifact_cache_binding_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    source_zip = tmp_path / "source.zip"
    artifact_sha = _write_artifact_zip(tool, source_zip)
    cache_root = tmp_path / "cache"
    entry = _write_cache_entry(
        tool,
        cache_root,
        source_zip,
        run_id="1",
        artifact_name="artifact",
        artifact_id=123,
        artifact_sha=artifact_sha,
    )
    binding = json.loads((entry / "binding.json").read_text(encoding="utf-8"))
    binding["run_id"] = "different"
    (entry / "binding.json").write_text(
        json.dumps(binding, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("binding mismatch must not trigger download")

    monkeypatch.setattr(tool, "_artifact_metadata", forbidden)
    monkeypatch.setattr(tool, "_download_remote_artifact_zip", forbidden)

    with pytest.raises(
        tool.FreshHostTransportError,
        match="artifact_cache_binding_mismatch",
    ):
        tool._download_artifact(
            tmp_path / "work",
            run_id="1",
            artifact_name="artifact",
            artifact_id=123,
            artifact_zip_sha256=artifact_sha,
            cache_root=cache_root,
        )


def test_artifact_metadata_uses_ipv4_http1_curl_with_bounded_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    calls: list[tuple[str, ...]] = []

    class Result:
        def __init__(self, stdout: str) -> None:
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    document = {
        "id": 123,
        "name": "artifact",
        "expired": False,
        "digest": "sha256:" + "a" * 64,
        "workflow_run": {"id": 456},
    }

    def fake_run(command, **_kwargs):
        call = tuple(command)
        calls.append(call)
        if call[:3] == ("gh", "auth", "token"):
            return Result("token\n")
        if call and call[0] == "curl":
            return Result(json.dumps(document))
        raise AssertionError(call)

    monkeypatch.setattr(tool, "_run", fake_run)

    result = tool._artifact_metadata(
        run_id="456",
        artifact_name="artifact",
        artifact_id=123,
        artifact_zip_sha256="a" * 64,
    )

    assert result == document
    assert len(calls) == 2
    assert calls[0] == ("gh", "auth", "token")
    curl = calls[1]
    assert curl[0] == "curl"
    assert "-4" in curl
    assert "--http1.1" in curl
    assert "--retry" in curl
    assert "3" in curl
    assert "--retry-all-errors" in curl
    assert "--connect-timeout" in curl
    assert "--max-time" in curl
    assert not any(part == "api" for part in curl)


def test_exact_artifact_cache_miss_populates_then_hits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    source_zip = tmp_path / "source.zip"
    artifact_sha = _write_artifact_zip(tool, source_zip)
    cache_root = tmp_path / "cache"
    metadata_calls: list[object] = []
    download_calls: list[object] = []

    monkeypatch.setattr(
        tool,
        "_artifact_metadata",
        lambda **kwargs: metadata_calls.append(kwargs) or {},
    )

    def fake_download(destination: Path, *, artifact_id: int) -> None:
        download_calls.append(artifact_id)
        destination.write_bytes(source_zip.read_bytes())

    monkeypatch.setattr(tool, "_download_remote_artifact_zip", fake_download)

    first_work = tmp_path / "first"
    first_work.mkdir()
    first = tool._download_artifact(
        first_work,
        run_id="1",
        artifact_name="artifact",
        artifact_id=123,
        artifact_zip_sha256=artifact_sha,
        cache_root=cache_root,
    )

    assert first == "MISS_POPULATED"
    assert len(metadata_calls) == 1
    assert download_calls == [123]
    entry = cache_root / "123" / artifact_sha
    assert {path.name for path in entry.iterdir()} == tool.ARTIFACT_CACHE_FILES
    assert tool._sha256_file(entry / "artifact.zip") == artifact_sha

    def forbidden(*_args, **_kwargs):
        raise AssertionError("second exact use must be cache-only")

    monkeypatch.setattr(tool, "_artifact_metadata", forbidden)
    monkeypatch.setattr(tool, "_download_remote_artifact_zip", forbidden)
    second_work = tmp_path / "second"
    second_work.mkdir()
    second = tool._download_artifact(
        second_work,
        run_id="1",
        artifact_name="artifact",
        artifact_id=123,
        artifact_zip_sha256=artifact_sha,
        cache_root=cache_root,
    )

    assert second == "HIT"
    assert {path.name for path in second_work.iterdir()} == tool.ARTIFACT_OUTER_FILES


def test_transfer_requested_image_is_capacity_gated_and_single_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    work = tmp_path / "work"
    work.mkdir()
    local = work / "homeassistant-arm64.tar"
    local.write_bytes(b"x" * 1000)
    m = manifest()
    m["transport"]["images"]["homeassistant"]["tar_sha256"] = tool._sha256_file(local)
    m["images"]["homeassistant"]["tar_sha256"] = tool._sha256_file(local)
    c = capacity()
    c["images"]["homeassistant"]["tar_sha256"] = tool._sha256_file(local)

    calls: list[tuple[str, ...]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        tool,
        "_remote_free_bytes",
        lambda _t1: 8 * 1024 * 1024 * 1024,
    )

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        return Result()

    monkeypatch.setattr(tool, "_run", fake_run)
    tool._transfer_requested_image(
        "root@example",
        "/var/tmp/payload",
        work,
        m,
        c,
        "homeassistant",
    )

    scp_indexes = [
        index
        for index, call in enumerate(calls)
        if call and call[0] == "scp"
    ]
    assert len(scp_indexes) == 1
    scp_index = scp_indexes[0]
    remote_transfer = "/var/tmp/payload.image-homeassistant.part"
    remote_tar = "/var/tmp/payload/incoming/homeassistant-arm64.tar"
    assert calls[scp_index][-1] == f"root@example:{remote_transfer}"
    assert remote_tar not in calls[scp_index][-1]

    verify_index = next(
        index
        for index, call in enumerate(calls)
        if call
        and call[0] == "ssh"
        and remote_transfer in call[-1]
        and "hashlib" in call[-1]
    )
    publish_index = next(
        index
        for index, call in enumerate(calls)
        if call
        and call[0] == "ssh"
        and remote_transfer in call[-1]
        and remote_tar in call[-1]
        and "os.rename" in call[-1]
    )
    assert scp_index < verify_index < publish_index
    assert all("docker load" not in " ".join(call) for call in calls)



def test_cli_exposes_preflight_and_apply_with_explicit_authorization() -> None:
    tool = load_tool()
    source = TOOL.read_text(encoding="utf-8")

    assert 'choices=("preflight", "apply")' in source
    assert 'parser.add_argument("--authorization-id")' in source
    assert 'parser.add_argument("--artifact-id", type=int, required=True)' in source
    assert 'parser.add_argument("--artifact-zip-sha256", required=True)' in source
    assert '"--artifact-cache-root"' in source
    assert "DEFAULT_ARTIFACT_CACHE_ROOT" in source
    assert tool.DEFAULT_ARTIFACT_CACHE_ROOT == "~/Documents/N3W/exact-artifacts"
    assert "artifact_zip_sha256_mismatch" in source
    assert source.count('"--retry-all-errors"') >= 3
    assert "timeout=7200" in source
    assert "authorization_id_mismatch" in source
    assert '"docker_mutation": False' in source


def _write_payload_archive(path: Path, *, link: bool) -> str:
    manifest = json.dumps(
        {
            "transport": {
                "schema": "gh.n3w-t1-fresh-transport/2",
                "remote_staging_root": "/var/tmp",
                "minimum_post_peak_free_bytes": 5 * 1024 * 1024 * 1024,
                "runtime_payload_uncompressed_bytes": 1,
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


def test_remote_payload_extract_script_compiles_and_executes(tmp_path: Path) -> None:
    tool = load_tool()
    script = tool._remote_payload_extract_script()
    compile(script, "<n3w-remote-payload>", "exec")

    remote = tmp_path / "remote"
    remote.mkdir()
    archive = remote / "runtime-payload.tar.gz"
    manifest_sha = _write_payload_archive(archive, link=False)
    archive_sha = tool._sha256_file(archive)

    completed = tool.subprocess.run(
        (
            sys.executable,
            "-c",
            script,
            str(remote),
            archive_sha,
            manifest_sha,
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert not archive.exists()
    assert (remote / "payload-manifest.json").is_file()


def test_remote_payload_extract_script_rejects_symlink(tmp_path: Path) -> None:
    tool = load_tool()
    script = tool._remote_payload_extract_script()

    remote = tmp_path / "remote"
    remote.mkdir()
    archive = remote / "runtime-payload.tar.gz"
    manifest_sha = _write_payload_archive(archive, link=True)
    archive_sha = tool._sha256_file(archive)

    completed = tool.subprocess.run(
        (
            sys.executable,
            "-c",
            script,
            str(remote),
            archive_sha,
            manifest_sha,
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "payload_link_member_forbidden" in completed.stderr
    assert not (remote / "payload-manifest.json").exists()


def test_payload_reader_rejects_symlink_member(tmp_path: Path) -> None:
    tool = load_tool()
    archive = tmp_path / "runtime-payload.tar.gz"
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
    claim_failure: bool = False,
    claim_record_state: bool | None = False,
) -> tuple[int, dict[str, object]]:
    tool = load_tool()
    work = tmp_path / "work"
    work.mkdir()
    archive = work / "runtime-payload.tar.gz"
    archive.write_bytes(b"x")
    authorization = AUTHORIZATION_ID

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
        lambda *_args, **_kwargs: {
            "staging_free_bytes": 8 * 1024 * 1024 * 1024,
            "docker_free_bytes": 8 * 1024 * 1024 * 1024,
            "image_store_free_bytes": 8 * 1024 * 1024 * 1024,
        },
    )
    monkeypatch.setattr(tool, "_capacity_contract", lambda *_args, **_kwargs: capacity())
    monkeypatch.setattr(
        tool,
        "_remote_baseline_report",
        lambda *_args, **_kwargs: {
            "status": "PASS",
            "docker_active": True,
            "production_service_start": False,
        },
    )
    if claim_failure:
        def fail_claim(*_args, **_kwargs):
            raise tool.FreshHostTransportError("authorization_claim_failed")
        monkeypatch.setattr(tool, "_remote_claim_authorization", fail_claim)
        monkeypatch.setattr(
            tool,
            "_remote_authorization_record_state",
            lambda *_args, **_kwargs: claim_record_state,
        )
    else:
        monkeypatch.setattr(
            tool,
            "_remote_claim_authorization",
            lambda *_args, **_kwargs: None,
        )
    monkeypatch.setattr(tool, "_verify_image_artifacts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        tool,
        "_remote_free_bytes",
        lambda *_args, **_kwargs: 8 * 1024 * 1024 * 1024,
    )
    monkeypatch.setattr(
        tool,
        "_transfer_requested_image",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        tool,
        "_plan_transport",
        lambda *_args, **_kwargs: tool.TransportPlan(
            runtime_archive_size_bytes=1,
            runtime_payload_uncompressed_bytes=1,
            runtime_extraction_peak_bytes=2,
            worst_image_required_free_bytes=5 * 1024 * 1024 * 1024 + 2,
            minimum_post_peak_free_bytes=5 * 1024 * 1024 * 1024,
            remote_free_bytes=8 * 1024 * 1024 * 1024,
            image_load_order=("homeassistant", "manager", "broker"),
            remote_staged_image_count_max=1,
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
            "--artifact-id",
            "123",
            "--artifact-zip-sha256",
            "2" * 64,
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
                    "authorization_id": AUTHORIZATION_ID,
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


def test_marker_probe_failure_after_durable_preclaim_is_partial(
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
    assert report["status"] == "STOP_PARTIAL"
    assert report["authorization_claimed"] is True
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
                    "authorization_id": AUTHORIZATION_ID,
                },
                separators=(",", ":"),
            )
            + "\n",
            *[
                json.dumps(
                    {"event": event, "label": label, **(
                        {"staged_tar_deleted": True}
                        if event == "image_loaded"
                        else {}
                    )},
                    separators=(",", ":"),
                )
                + "\n"
                for label in ("homeassistant", "manager", "broker")
                for event in ("image_requested", "image_loaded")
            ],
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
    assert report["public_product_staged"] is True


def test_claim_failure_remains_preclaim_and_replayable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()

    rc, report = _run_apply_main(
        monkeypatch,
        tmp_path,
        process_lines=[],
        process_returncode=1,
        run_results=[],
        claim_failure=True,
    )

    assert rc == 2
    assert report["status"] == "STOP_PRECLAIM"
    assert report["authorization_claimed"] is False
    assert report["authorization_consumed"] is False
    assert report["payload_transfer"] is True
    assert report["docker_mutation"] is False
    assert report["remote_payload_preserved"] is True


def test_claim_failure_with_durable_record_is_consumed_no_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rc, report = _run_apply_main(
        monkeypatch,
        tmp_path,
        process_lines=[],
        process_returncode=1,
        run_results=[],
        claim_failure=True,
        claim_record_state=True,
    )

    assert rc == 2
    assert report["status"] == "STOP_PARTIAL"
    assert report["authorization_claimed"] is True
    assert report["authorization_consumed"] is True
    assert report["replay_allowed"] is False
    assert report["remote_payload_preserved"] is True


def test_claim_failure_with_unknown_record_state_is_consumed_no_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rc, report = _run_apply_main(
        monkeypatch,
        tmp_path,
        process_lines=[],
        process_returncode=1,
        run_results=[],
        claim_failure=True,
        claim_record_state=None,
    )

    assert rc == 2
    assert report["status"] == "STOP_UNKNOWN"
    assert report["authorization_claimed"] is None
    assert report["authorization_consumed"] is True
    assert report["replay_allowed"] is False
    assert report["remote_payload_preserved"] is True


def test_remote_apply_process_is_stopped_and_reaped_on_host_error() -> None:
    tool = load_tool()
    calls: list[object] = []

    class Process:
        def poll(self):
            calls.append("poll")
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            return 0

        def kill(self):
            calls.append("kill")

    tool._stop_remote_apply_process(Process())

    assert calls == ["poll", "terminate", ("wait", 10)]
    source = TOOL.read_text(encoding="utf-8")
    assert (
        "except Exception:\n"
        "            _stop_remote_apply_process(process)\n"
        "            raise"
    ) in source


def test_remote_apply_process_is_killed_if_terminate_does_not_finish() -> None:
    tool = load_tool()
    calls: list[object] = []
    waits = 0

    class Process:
        def poll(self):
            calls.append("poll")
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout=None):
            nonlocal waits
            waits += 1
            calls.append(("wait", timeout))
            if waits == 1:
                raise tool.subprocess.TimeoutExpired("ssh", timeout)
            return 0

        def kill(self):
            calls.append("kill")

    tool._stop_remote_apply_process(Process())

    assert calls == [
        "poll",
        "terminate",
        ("wait", 10),
        "kill",
        ("wait", 10),
    ]


def test_prebaseline_capacity_is_checked_before_authorization_claim() -> None:
    source = TOOL.read_text(encoding="utf-8")
    baseline_index = source.index(
        'baseline = _remote_baseline_report(args.t1, baseline_tool, "check")'
    )
    prebaseline_index = source.index(
        '"remote_capacity_insufficient_prebaseline"'
    )
    claim_index = source.index(
        "_remote_claim_authorization(args.t1, remote_dir, authorization)"
    )

    assert baseline_index < prebaseline_index < claim_index
    assert '"capacity_admission": "PREBASELINE_ROOT_PASS"' in source
    assert '"transport": prebaseline_plan.to_dict()' in source



def test_production_mode_requires_managed_transport(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    monkeypatch.delenv("N3W_T1_SSH_MANAGED_REQUIRED", raising=False)
    with pytest.raises(
        tool.FreshHostTransportError,
        match="managed_ssh_transport_required",
    ):
        tool.execute_production(
            t1="root@t1.local",
            production_release=tmp_path / "release.json",
            production_f3_artifact=tmp_path / "artifact.zip",
            production_phase_context=tmp_path / "context.json",
        )


def test_production_context_binds_f3_phase_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    release = {
        "release_id": "1" * 64,
        "source_head": "a" * 40,
    }
    context = {
        "schema": "gh.n3w-t1-production-phase-context/1",
        "phase": "F3_DEPLOY",
        "binding": {
            "source_head": "a" * 40,
            "release_id": "1" * 64,
            "artifact_sha256": "2" * 64,
        },
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }
    path = tmp_path / "context.json"
    path.write_text(json.dumps(context), encoding="utf-8")

    contract = type(
        "Contract",
        (),
        {"phase_artifact_sha256": staticmethod(lambda _r, _p: "2" * 64)},
    )
    monkeypatch.setitem(
        sys.modules,
        "n3w_t1_production_contract",
        contract,
    )
    assert tool._load_production_context_for_f3(path, release) == context


def test_production_baseline_requires_exact_release_versions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    release = {
        "environment": {
            "packages": {
                "docker.io": "1.0",
                "docker-compose-v2": "2.0",
            }
        }
    }
    monkeypatch.setattr(
        tool,
        "_remote_baseline_report",
        lambda *_args, **_kwargs: {
            "status": "PASS",
            "package_versions": {
                "docker.io": "later",
                "docker-compose-v2": "2.0",
            },
        },
    )
    with pytest.raises(
        tool.FreshHostTransportError,
        match="production_host_baseline_not_ready",
    ):
        tool._production_baseline_ready(
            "root@t1.local",
            tmp_path,
            release,
        )
