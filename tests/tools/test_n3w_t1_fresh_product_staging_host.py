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
AUTHORIZATION_ID = "N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_08"


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


def test_artifact_download_timeout_enters_integrity_checked_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    work = tmp_path / "work"
    work.mkdir()
    source_zip = tmp_path / "source.zip"

    import zipfile

    with zipfile.ZipFile(source_zip, "w") as bundle:
        for name in sorted(tool.ARTIFACT_OUTER_FILES):
            bundle.writestr(name, name.encode())

    artifact_sha = tool._sha256_file(source_zip)
    monkeypatch.setattr(tool, "_artifact_metadata", lambda **_kwargs: {})

    class Result:
        def __init__(self, stdout=""):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    def fake_run(command, **_kwargs):
        command = tuple(command)
        if command[:3] == ("gh", "run", "download"):
            raise tool.subprocess.TimeoutExpired(command, 900)
        if command == ("gh", "auth", "token"):
            return Result("test-token\n")
        if command and command[0] == "curl" and "-D" in command:
            headers = Path(command[command.index("-D") + 1])
            headers.write_text(
                "HTTP/1.1 302 Found\n"
                "Location: https://blob.example.invalid/artifact\n\n",
                encoding="utf-8",
            )
            return Result()
        if command and command[0] == "curl" and "-o" in command:
            destination = Path(command[command.index("-o") + 1])
            destination.write_bytes(source_zip.read_bytes())
            return Result()
        raise AssertionError(command)

    monkeypatch.setattr(tool, "_run", fake_run)

    tool._download_artifact(
        work,
        run_id="1",
        artifact_name="artifact",
        artifact_id=123,
        artifact_zip_sha256=artifact_sha,
    )

    assert {path.name for path in work.iterdir()} == tool.ARTIFACT_OUTER_FILES


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

    assert sum(1 for call in calls if call and call[0] == "scp") == 1
    assert all("docker load" not in " ".join(call) for call in calls)



def test_cli_exposes_preflight_and_apply_with_explicit_authorization() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'choices=("preflight", "apply")' in source
    assert 'parser.add_argument("--authorization-id")' in source
    assert 'parser.add_argument("--artifact-id", type=int, required=True)' in source
    assert 'parser.add_argument("--artifact-zip-sha256", required=True)' in source
    assert "artifact_zip_sha256_mismatch" in source
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
                    "authorization_id": AUTHORIZATION_ID,
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
    assert report["public_product_staged"] is True


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
