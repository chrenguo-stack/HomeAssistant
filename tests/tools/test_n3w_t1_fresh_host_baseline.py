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
        if command == (
            "dpkg-query",
            "-W",
            "-f=${Status}\t${Version}",
            "docker.io",
        ):
            return "install ok installed\t28.2.2-0ubuntu1"
        if command == (
            "dpkg-query",
            "-W",
            "-f=${Status}\t${Version}",
            "docker-compose-v2",
        ):
            return "install ok installed\t2.38.2-0ubuntu1"
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
    checks = iter(
        (
            {"status": "MISSING"},
            {
                "status": "PASS",
                "docker_active": True,
                "docker_version": "28.2.2",
                "compose_version": "2.38.2",
                "production_service_start": False,
                "board_access": False,
            },
        )
    )
    monkeypatch.setattr(baseline, "_check", lambda _runner: next(checks))
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


def test_install_is_idempotent_when_approved_baseline_is_ready(
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
    assert report["installed"] is False
    assert all(command[0] != "apt-get" for command in runner.commands)


def test_check_rejects_unapproved_docker_package_source(
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
    monkeypatch.setattr(baseline.shutil, "which", lambda _name: "/usr/bin/docker")

    class UnknownPackageRunner(FakeRunner):
        def run(self, argv, **kwargs):
            if tuple(argv)[:2] == ("dpkg-query", "-W"):
                return ""
            return super().run(argv, **kwargs)

    report = baseline._check(UnknownPackageRunner())

    assert report["status"] == "MISSING"
    assert report["package_source"] == "ubuntu_apt_required"



def test_production_install_uses_only_approved_versions_after_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    context = {
        "schema": baseline.PRODUCTION_CONTEXT_SCHEMA,
        "run_id": "1" * 64,
        "phase": baseline.PRODUCTION_PHASE,
        "claim_sha256": "2" * 64,
        "plan_sha256": "3" * 64,
        "binding": {
            "source_head": "a" * 40,
            "release_id": "4" * 64,
            "artifact_sha256": "5" * 64,
            "predecessor_sha256": None,
            "target_binding_sha256": "6" * 64,
        },
        "binding_sha256": "7" * 64,
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }
    release = {
        "release_id": "4" * 64,
        "source_head": "a" * 40,
        "environment": {
            "os": {
                "id": "ubuntu",
                "version": "26.04",
                "codename": "resolute",
            },
            "architecture": "aarch64",
            "package_source": "ubuntu_apt",
            "packages": {
                "docker.io": "28.2.2-0ubuntu1",
                "docker-compose-v2": "2.37.1+ds1-1",
            },
        },
    }
    context_path = tmp_path / "context.json"
    release_path = tmp_path / "release.json"
    context_path.write_text("{}", encoding="utf-8")
    release_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(baseline.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        baseline,
        "PRODUCTION_EXECUTION_LEDGER_ROOT",
        tmp_path / "ledger",
    )
    monkeypatch.setattr(
        baseline,
        "_load_production_context",
        lambda _path: context,
    )
    monkeypatch.setattr(
        baseline,
        "_load_approved_release",
        lambda _path: release,
    )
    monkeypatch.setattr(
        baseline,
        "_validate_approved_host",
        lambda _environment: None,
    )
    installed = iter(
        (
            {"docker.io": None, "docker-compose-v2": None},
            {
                "docker.io": "28.2.2-0ubuntu1",
                "docker-compose-v2": "2.37.1+ds1-1",
            },
        )
    )
    monkeypatch.setattr(
        baseline,
        "_installed_versions",
        lambda _runner: next(installed),
    )
    monkeypatch.setattr(
        baseline,
        "_check",
        lambda _runner: {
            "status": "PASS",
            "package_versions": {
                "docker.io": "28.2.2-0ubuntu1",
                "docker-compose-v2": "2.37.1+ds1-1",
            },
            "production_service_start": False,
            "board_access": False,
        },
    )

    class ProductionRunner(FakeRunner):
        def run(self, argv, **kwargs):
            command = tuple(argv)
            self.commands.append(command)
            if command == ("apt-cache", "madison", "docker.io"):
                return "docker.io | 28.2.2-0ubuntu1 | repo"
            if command == ("apt-cache", "madison", "docker-compose-v2"):
                return "docker-compose-v2 | 2.37.1+ds1-1 | repo"
            return ""

    runner = ProductionRunner()
    report = baseline.execute_production_install(
        context_path,
        release_path,
        runner,
    )

    assert report["status"] == "PASS"
    assert report["authorization_consumed"] is True
    assert report["replay_allowed"] is False
    assert (
        "apt-get",
        "install",
        "-y",
        "docker.io=28.2.2-0ubuntu1",
        "docker-compose-v2=2.37.1+ds1-1",
    ) in runner.commands
    claim_path, complete_path = baseline._production_paths(context)
    assert claim_path.is_file()
    assert complete_path.is_file()


def test_production_install_rejects_installed_version_drift_after_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    context = {
        "schema": baseline.PRODUCTION_CONTEXT_SCHEMA,
        "run_id": "1" * 64,
        "phase": baseline.PRODUCTION_PHASE,
        "claim_sha256": "2" * 64,
        "binding": {
            "source_head": "a" * 40,
            "release_id": "4" * 64,
        },
    }
    release = {
        "release_id": "4" * 64,
        "source_head": "a" * 40,
        "environment": {
            "os": {
                "id": "ubuntu",
                "version": "26.04",
                "codename": "resolute",
            },
            "architecture": "aarch64",
            "package_source": "ubuntu_apt",
            "packages": {
                "docker.io": "28.2.2-0ubuntu1",
                "docker-compose-v2": "2.37.1+ds1-1",
            },
        },
    }
    monkeypatch.setattr(baseline.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        baseline,
        "PRODUCTION_EXECUTION_LEDGER_ROOT",
        tmp_path / "ledger",
    )
    monkeypatch.setattr(
        baseline,
        "_load_production_context",
        lambda _path: context,
    )
    monkeypatch.setattr(
        baseline,
        "_load_approved_release",
        lambda _path: release,
    )
    monkeypatch.setattr(
        baseline,
        "_validate_approved_host",
        lambda _environment: None,
    )
    monkeypatch.setattr(
        baseline,
        "_installed_versions",
        lambda _runner: {
            "docker.io": "99.0-unapproved",
            "docker-compose-v2": None,
        },
    )

    with pytest.raises(
        baseline.FreshHostBaselineError,
        match="production_host_baseline_claimed:installed_package_version_drift",
    ):
        baseline.execute_production_install(
            tmp_path / "context.json",
            tmp_path / "release.json",
            FakeRunner(),
        )
    claim_path, complete_path = baseline._production_paths(context)
    assert claim_path.is_file()
    assert not complete_path.exists()
