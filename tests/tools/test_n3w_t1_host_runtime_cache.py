from __future__ import annotations

from pathlib import Path

import pytest

from tools import n3w_t1_host_runtime_cache as cache

DOCKER_VERSION = "29.1.3-0ubuntu4.1"
COMPOSE_VERSION = "2.40.3+ds1-0ubuntu1"


class FakeRunner:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir
        self.commands: list[tuple[str, ...]] = []

    def run(self, argv, **_kwargs):
        command = tuple(str(item) for item in argv)
        self.commands.append(command)

        if command == ("dpkg", "--print-architecture"):
            return "arm64"
        if command == ("apt-cache", "policy", "docker.io"):
            return f"Candidate: {DOCKER_VERSION}"
        if command == ("apt-cache", "policy", "docker-compose-v2"):
            return f"Candidate: {COMPOSE_VERSION}"
        if command[:2] == ("dpkg-query", "-W"):
            return ""
        if command[:2] == ("apt-get", "update"):
            return ""
        if command[:2] == ("apt-get", "--download-only"):
            assert self.cache_dir is not None
            packages = self.cache_dir / "packages"
            packages.mkdir(parents=True, exist_ok=True)
            (packages / "docker.io_test_arm64.deb").write_bytes(b"docker")
            (packages / "docker-compose-v2_test_arm64.deb").write_bytes(b"compose")
            (packages / "containerd_test_arm64.deb").write_bytes(b"containerd")
            return ""
        if command[:2] == ("dpkg-deb", "-f"):
            name = Path(command[2]).name
            field = command[3]
            metadata = {
                "docker.io_test_arm64.deb": {
                    "Package": "docker.io",
                    "Version": DOCKER_VERSION,
                    "Architecture": "arm64",
                },
                "docker-compose-v2_test_arm64.deb": {
                    "Package": "docker-compose-v2",
                    "Version": COMPOSE_VERSION,
                    "Architecture": "arm64",
                },
                "containerd_test_arm64.deb": {
                    "Package": "containerd",
                    "Version": "2.1.4-0ubuntu1",
                    "Architecture": "arm64",
                },
            }
            return metadata[name][field]
        if command[:3] == ("apt-get", "--no-download", "--no-remove"):
            return ""
        if command == ("systemctl", "enable", "docker"):
            return ""
        if command == ("systemctl", "start", "docker"):
            return ""
        return ""


@pytest.fixture
def host_contract():
    return {
        "os_id": "ubuntu",
        "os_version": "26.04",
        "os_codename": "resolute",
        "armbian_version": "26.05.0",
        "armbian_board": "S912-Phicomm-T1",
        "package_architecture": "arm64",
    }


@pytest.fixture
def patch_host(monkeypatch: pytest.MonkeyPatch, host_contract):
    monkeypatch.setattr(cache.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cache, "_host_contract", lambda _runner: dict(host_contract))
    monkeypatch.setattr(
        cache,
        "_validate_apt_source_policy",
        lambda: dict(cache.APT_SOURCE_POLICY),
    )
    monkeypatch.setattr(cache, "_assert_fresh_docker_absent", lambda _runner: None)


def acquire_bundle(
    tmp_path: Path,
    patch_host,
) -> tuple[Path, FakeRunner, dict]:
    cache_dir = tmp_path / "bundle"
    runner = FakeRunner(cache_dir)
    report = cache.acquire_cache(cache_dir, runner)
    return cache_dir, runner, report


def test_acquire_downloads_once_and_writes_exact_manifest(
    tmp_path: Path,
    patch_host,
) -> None:
    cache_dir, runner, report = acquire_bundle(tmp_path, patch_host)

    assert report["status"] == "PASS"
    assert report["phase"] == "acquire"
    assert report["network_download_performed"] is True
    assert report["package_count"] == 3
    assert len(report["bundle_id"]) == 64
    assert (cache_dir / "manifest.json").is_file()
    assert (cache_dir / "manifest.sha256").read_text().strip() == report["bundle_id"]

    download_commands = [
        command
        for command in runner.commands
        if command[:2] == ("apt-get", "--download-only")
    ]
    assert len(download_commands) == 1
    command = download_commands[0]
    assert "--no-remove" in command
    assert f"docker.io={DOCKER_VERSION}" in command
    assert f"docker-compose-v2={COMPOSE_VERSION}" in command
    assert not any(
        item[:3] == ("apt-get", "--no-download", "--no-remove")
        for item in runner.commands
    )


def test_verify_rejects_missing_package_member(
    tmp_path: Path,
    patch_host,
) -> None:
    cache_dir, _, _ = acquire_bundle(tmp_path, patch_host)
    (cache_dir / "packages" / "containerd_test_arm64.deb").unlink()

    with pytest.raises(
        cache.HostRuntimeCacheError,
        match="cache_package_member_set_mismatch",
    ):
        cache.verify_cache(cache_dir, FakeRunner(cache_dir))


def test_verify_rejects_hash_mismatch(
    tmp_path: Path,
    patch_host,
) -> None:
    cache_dir, _, _ = acquire_bundle(tmp_path, patch_host)
    target = cache_dir / "packages" / "containerd_test_arm64.deb"
    target.write_bytes(target.read_bytes() + b"tampered")

    with pytest.raises(
        cache.HostRuntimeCacheError,
        match="cache_package_sha256_mismatch:containerd_test_arm64.deb",
    ):
        cache.verify_cache(cache_dir, FakeRunner(cache_dir))


def test_verify_archive_is_portable_after_mac_copy(
    tmp_path: Path,
    patch_host,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir, _, acquired = acquire_bundle(tmp_path, patch_host)

    def host_probe_must_not_run(_runner):
        raise AssertionError("portable archive verification must not probe T1 host")

    def apt_probe_must_not_run():
        raise AssertionError("portable archive verification must not inspect APT sources")

    monkeypatch.setattr(cache, "_host_contract", host_probe_must_not_run)
    monkeypatch.setattr(cache, "_validate_apt_source_policy", apt_probe_must_not_run)

    report = cache.verify_archive(cache_dir)

    assert report["status"] == "PASS"
    assert report["phase"] == "verify-archive"
    assert report["bundle_id"] == acquired["bundle_id"]
    assert report["package_count"] == acquired["package_count"]
    assert report["total_bytes"] == acquired["total_bytes"]
    assert report["network_download_performed"] is False


def test_verify_archive_rejects_extra_package_member(
    tmp_path: Path,
    patch_host,
) -> None:
    cache_dir, _, _ = acquire_bundle(tmp_path, patch_host)
    (cache_dir / "packages" / "unexpected_test_arm64.deb").write_bytes(b"unexpected")

    with pytest.raises(
        cache.HostRuntimeCacheError,
        match="cache_package_member_set_mismatch",
    ):
        cache.verify_archive(cache_dir)


def test_verify_rejects_host_contract_drift(
    tmp_path: Path,
    patch_host,
    monkeypatch: pytest.MonkeyPatch,
    host_contract,
) -> None:
    cache_dir, _, _ = acquire_bundle(tmp_path, patch_host)
    changed = dict(host_contract)
    changed["os_codename"] = "future"
    monkeypatch.setattr(cache, "_host_contract", lambda _runner: changed)

    with pytest.raises(
        cache.HostRuntimeCacheError,
        match="cache_host_contract_mismatch",
    ):
        cache.verify_cache(cache_dir, FakeRunner(cache_dir))


def test_install_uses_cache_only_and_never_updates_apt(
    tmp_path: Path,
    patch_host,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir, _, _ = acquire_bundle(tmp_path, patch_host)
    checks = iter(
        (
            {"status": "MISSING"},
            {
                "status": "PASS",
                "docker_version": "29.1.3",
                "compose_version": "2.40.3",
                "package_versions": {
                    "docker.io": DOCKER_VERSION,
                    "docker-compose-v2": COMPOSE_VERSION,
                },
            },
        )
    )
    monkeypatch.setattr(cache.baseline, "_check", lambda _runner: next(checks))
    runner = FakeRunner(cache_dir)

    report = cache.install_cache(cache_dir, runner)

    assert report["status"] == "PASS"
    assert report["installed"] is True
    assert report["cache_only_install"] is True
    assert report["network_download_performed"] is False

    install_commands = [
        command
        for command in runner.commands
        if command[:3] == ("apt-get", "--no-download", "--no-remove")
    ]
    assert len(install_commands) == 1
    command = install_commands[0]
    assert "install" in command
    assert all(
        str(cache_dir / "packages") in item
        for item in command
        if item.endswith(".deb")
    )
    assert not any(
        command[:2] == ("apt-get", "update")
        or command[:2] == ("apt-get", "--download-only")
        for command in runner.commands
    )


def test_install_rejects_postinstall_requested_version_drift(
    tmp_path: Path,
    patch_host,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir, _, _ = acquire_bundle(tmp_path, patch_host)
    checks = iter(
        (
            {"status": "MISSING"},
            {
                "status": "PASS",
                "docker_version": "29.1.3",
                "compose_version": "2.40.3",
                "package_versions": {
                    "docker.io": "WRONG",
                    "docker-compose-v2": COMPOSE_VERSION,
                },
            },
        )
    )
    monkeypatch.setattr(cache.baseline, "_check", lambda _runner: next(checks))

    with pytest.raises(
        cache.HostRuntimeCacheError,
        match="postinstall_package_version_mismatch",
    ):
        cache.install_cache(cache_dir, FakeRunner(cache_dir))


def test_self_check_proves_no_network_fallback_or_product_activation() -> None:
    report = cache.self_check()

    assert report["status"] == "PASS"
    assert report["violations"] == []
    assert report["cache_only_install_guard"] is True
    assert report["production_service_start"] is False
    assert report["board_access"] is False
