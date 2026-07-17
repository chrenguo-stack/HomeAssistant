from __future__ import annotations

import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

from greenhouse_manager import private_mosquitto_builder as private
from greenhouse_manager.node_mqtt_board_lab_common import NodeMqttBoardLabError


def _executable(path: Path, body: str = "exit 0") -> Path:
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o700)
    return path


def _runner(
    command: list[str] | tuple[str, ...],
    *,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = list(command)
    if command[1:] == ["--version"]:
        return subprocess.CompletedProcess(command, 0, "cmake version 3.28.3\n", "")
    if command[1:] == ["-h"]:
        return subprocess.CompletedProcess(
            command,
            0,
            f"mosquitto version {private.PRIVATE_MOSQUITTO_VERSION}\n",
            "",
        )
    return subprocess.CompletedProcess(command, 0, "", "")


def _private_install(tmp_path: Path) -> Path:
    install = private.private_mosquitto_install_dir(tmp_path / "cache")
    bin_dir = install / "bin"
    bin_dir.mkdir(parents=True, mode=0o700)
    mosquitto = _executable(
        bin_dir / "mosquitto",
        f"echo 'mosquitto version {private.PRIVATE_MOSQUITTO_VERSION}'",
    )
    passwd = _executable(bin_dir / "mosquitto_passwd")
    marker = install / private.PRIVATE_MOSQUITTO_MARKER
    marker.write_text(private.PRIVATE_MOSQUITTO_VERSION + "\n", encoding="utf-8")
    marker.chmod(0o600)
    manifest = {
        "schema": private.PRIVATE_MOSQUITTO_MANIFEST_SCHEMA,
        "version": private.PRIVATE_MOSQUITTO_VERSION,
        "source_url": private.PRIVATE_MOSQUITTO_SOURCE_URL,
        "source_sha256": private.PRIVATE_MOSQUITTO_SOURCE_SHA256,
        "recipe": private.PRIVATE_MOSQUITTO_RECIPE,
        "platform": private._platform_key(),
        "install_dir": str(install),
        "mosquitto_bin": str(mosquitto),
        "mosquitto_passwd_bin": str(passwd),
        "mosquitto_sha256": private._sha256_file(mosquitto),
        "mosquitto_passwd_sha256": private._sha256_file(passwd),
        "cmake_version": "3.28.3",
        "cmake_options": list(private._build_options(install, None)),
        "websockets_enabled": False,
        "clients_built": False,
        "plugins_built": False,
        "documentation_built": False,
        "tls_enabled": True,
        "production_identity_used": False,
    }
    private._write_private_json(install / private.PRIVATE_MOSQUITTO_MANIFEST, manifest)
    return install


def test_private_plan_is_frozen_and_redacted(tmp_path: Path) -> None:
    cmake = _executable(tmp_path / "cmake")
    report = private.plan_private_mosquitto(
        tmp_path / "cache",
        cmake_bin=str(cmake),
        runner=_runner,
    )
    assert report["status"] == "private_mosquitto_plan_created"
    assert report["version"] == "2.0.21"
    assert report["source_sha256"] == private.PRIVATE_MOSQUITTO_SOURCE_SHA256
    assert report["websockets_enabled"] is False
    assert report["homebrew_mosquitto_required"] is False
    assert report["production_endpoint_used"] is False
    assert report["ready_for_live_apply"] is False
    assert str(tmp_path) not in json.dumps(report)


def test_private_recipe_disables_unneeded_components(tmp_path: Path) -> None:
    options = private._build_options(tmp_path / "stage", tmp_path / "openssl")
    assert "-DWITH_WEBSOCKETS=OFF" in options
    assert "-DWITH_CLIENTS=OFF" in options
    assert "-DWITH_PLUGINS=OFF" in options
    assert "-DDOCUMENTATION=OFF" in options
    assert "-DWITH_CJSON=OFF" in options
    assert "-DWITH_TLS=ON" in options
    assert any(option.startswith("-DOPENSSL_ROOT_DIR=") for option in options)


def test_private_source_archive_must_match_frozen_sha(tmp_path: Path) -> None:
    source = tmp_path / "source.tar.gz"
    source.write_bytes(b"not-the-frozen-source")
    with pytest.raises(NodeMqttBoardLabError, match="SHA-256 mismatch"):
        private._copy_source_archive(
            source,
            tmp_path / "copy.tar.gz",
            private._download,
        )


def test_private_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "malicious.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        payload = b"escape"
        member = tarfile.TarInfo("../escape")
        member.size = len(payload)
        bundle.addfile(member, io.BytesIO(payload))
    with pytest.raises(NodeMqttBoardLabError, match="path traversal"):
        private._extract_source(archive, tmp_path / "extract")


def test_private_manifest_binds_paths_hashes_and_version(tmp_path: Path) -> None:
    install = _private_install(tmp_path)
    manifest = install / private.PRIVATE_MOSQUITTO_MANIFEST
    mosquitto, passwd, document = private.load_private_mosquitto_manifest(
        manifest,
        runner=_runner,
    )
    assert Path(mosquitto).name == "mosquitto"
    assert Path(passwd).name == "mosquitto_passwd"
    assert document["websockets_enabled"] is False

    report = private.verify_private_mosquitto(manifest, runner=_runner)
    assert report["status"] == "private_mosquitto_verified"
    assert report["executables_verified"] is True
    assert report["manifest_private"] is True
    assert report["source_paths_included"] is False


def test_private_manifest_rejects_binary_tampering(tmp_path: Path) -> None:
    install = _private_install(tmp_path)
    manifest = install / private.PRIVATE_MOSQUITTO_MANIFEST
    (install / "bin" / "mosquitto").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(NodeMqttBoardLabError, match="binary SHA-256 mismatch"):
        private.load_private_mosquitto_manifest(manifest, runner=_runner)
