from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_production_stack_staging_host.py"


def load_tool():
    name = "n3w_t1_production_stack_staging_host"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_host_transport_does_not_use_shell_pipeline_status() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "PIPESTATUS" not in source
    assert "pipestatus" not in source
    assert '("ssh", "-n"' in source


def test_remote_temp_uses_root_backed_var_tmp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = tuple(command)
        captured["kwargs"] = kwargs

        class Result:
            returncode = 0
            stdout = "/var/tmp/n3w-staging-preflight.ABC123\n"
            stderr = ""

        return Result()

    monkeypatch.setattr(tool, "_run", fake_run)

    path = tool._remote_mktemp("root@example", "n3w-staging-preflight")

    assert path == "/var/tmp/n3w-staging-preflight.ABC123"
    assert captured["command"][:3] == ("ssh", "-n", "root@example")
    assert "mktemp -d /var/tmp/n3w-staging-preflight.XXXXXX" in captured["command"][3]
    assert "mktemp -d /tmp/" not in captured["command"][3]
    assert captured["kwargs"]["timeout"] == 60


def test_verify_artifact_accepts_exact_sidecars(tmp_path: Path) -> None:
    tool = load_tool()
    archive = tmp_path / "payload-archive.tar.gz"
    archive.write_bytes(b"archive")
    archive_sha = tool._sha256_file(archive)

    (tmp_path / "executor.sha256").write_text("a" * 64 + "\n", encoding="utf-8")
    (tmp_path / "payload-manifest.sha256").write_text(
        "b" * 64 + "\n",
        encoding="utf-8",
    )

    tool._verify_artifact(
        tmp_path,
        archive_sha256=archive_sha,
        executor_sha256="a" * 64,
        manifest_sha256="b" * 64,
    )


def test_remote_executor_apply_carries_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = tuple(command)
        captured["kwargs"] = kwargs

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(tool, "_run", fake_run)

    tool._invoke_remote_executor(
        "root@example",
        "/tmp/payload",
        phase="apply",
        executor_sha256="c" * 64,
        authorization_id="AUTH-1",
    )

    command = captured["command"]
    assert command[:3] == ("ssh", "-n", "root@example")
    assert "--phase apply" in command[3]
    assert "--authorization-id AUTH-1" in command[3]
    assert captured["kwargs"]["check"] is False


def test_remote_executor_apply_requires_authorization() -> None:
    tool = load_tool()

    with pytest.raises(tool.HostTransportError, match="authorization_id_required"):
        tool._invoke_remote_executor(
            "root@example",
            "/tmp/payload",
            phase="apply",
            executor_sha256="c" * 64,
            authorization_id=None,
        )


def test_remote_payload_verification_streams_and_releases_archive() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "archive.read_bytes()" not in source
    assert "stream.read(1024*1024)" in source
    assert "archive.unlink()" in source
