from __future__ import annotations

import pytest

from tools import n3w_t1_fresh_host_baseline as baseline


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(self, argv, **_kwargs):
        command = tuple(argv)
        self.commands.append(command)
        if command == ("apt-cache", "policy", "docker.io"):
            return "Candidate: 28.2.2-0ubuntu1"
        if command == ("apt-cache", "policy", "docker-compose-v2"):
            return "Candidate: 2.38.2-0ubuntu1"
        if command == ("systemctl", "is-active", "docker"):
            return "active"
        if command[:3] == ("docker", "version", "--format"):
            return "28.2.2"
        if command == ("docker", "compose", "version", "--short"):
            return "2.38.2"
        return ""


def test_candidate_requires_real_version() -> None:
    assert baseline._candidate("Candidate: 1.2.3\n", "x") == "1.2.3"
    with pytest.raises(
        baseline.FreshHostBaselineError,
        match="package_candidate_missing:x",
    ):
        baseline._candidate("Candidate: (none)\n", "x")


def test_install_pins_resolved_ubuntu_package_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(baseline.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        baseline,
        "_os_release",
        lambda: {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
        },
    )
    monkeypatch.setattr(baseline.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(baseline.shutil, "which", lambda _name: "/usr/bin/docker")
    runner = FakeRunner()

    report = baseline.execute_install(runner)

    assert report["status"] == "PASS"
    assert report["package_source"] == "ubuntu_apt"
    assert (
        "apt-get",
        "install",
        "-y",
        "docker.io=28.2.2-0ubuntu1",
        "docker-compose-v2=2.38.2-0ubuntu1",
    ) in runner.commands
    assert ("systemctl", "enable", "docker") in runner.commands
    assert ("systemctl", "start", "docker") in runner.commands
    assert all("n3wfc4" not in " ".join(command) for command in runner.commands)


def test_self_check_has_no_product_activation_authority() -> None:
    report = baseline.self_check()
    assert report["status"] == "PASS"
    assert report["forbidden_operations"] == []
    assert report["production_service_start"] is False


def test_check_reports_missing_when_docker_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        baseline,
        "_os_release",
        lambda: {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
        },
    )
    monkeypatch.setattr(baseline.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(baseline.shutil, "which", lambda _name: None)

    report = baseline._check(FakeRunner())

    assert report["status"] == "MISSING"
    assert report["docker_active"] is False
    assert report["docker_version"] is None
