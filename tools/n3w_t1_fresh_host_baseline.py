#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

SCHEMA = "gh.n3w-t1-fresh-host-baseline/1"
TARGET_OS_ID = "ubuntu"
TARGET_OS_VERSION = "26.04"
TARGET_OS_CODENAME = "resolute"
PACKAGES = ("docker.io", "docker-compose-v2")


class FreshHostBaselineError(RuntimeError):
    pass


class Runner:
    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float = 300.0,
        allowed: frozenset[int] = frozenset({0}),
        env: dict[str, str] | None = None,
    ) -> str:
        completed = subprocess.run(
            tuple(argv),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
        )
        if completed.returncode not in allowed:
            reason = completed.stderr.strip() or completed.stdout.strip()
            raise FreshHostBaselineError(
                f"command_failed:{Path(argv[0]).name}:{completed.returncode}:{reason[:400]}"
            )
        return completed.stdout.strip()


def _os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key] = value.strip().strip('"')
    return result


def _validate_target_host(document: dict[str, str]) -> None:
    if document.get("ID") != TARGET_OS_ID:
        raise FreshHostBaselineError("target_os_id_invalid")
    if document.get("VERSION_ID") != TARGET_OS_VERSION:
        raise FreshHostBaselineError("target_os_version_invalid")
    if document.get("VERSION_CODENAME") != TARGET_OS_CODENAME:
        raise FreshHostBaselineError("target_os_codename_invalid")
    if platform.machine() not in {"aarch64", "arm64"}:
        raise FreshHostBaselineError("target_architecture_invalid")


def _candidate(policy: str, package: str) -> str:
    for line in policy.splitlines():
        stripped = line.strip()
        if stripped.startswith("Candidate:"):
            value = stripped.split(":", 1)[1].strip()
            if value and value != "(none)":
                return value
    raise FreshHostBaselineError(f"package_candidate_missing:{package}")


def _installed_package_version(runner: Runner, package: str) -> str | None:
    output = runner.run(
        (
            "dpkg-query",
            "-W",
            "-f=${Status}\t${Version}",
            package,
        ),
        allowed=frozenset({0, 1}),
    )
    if not output.startswith("install ok installed\t"):
        return None
    version = output.split("\t", 1)[1].strip()
    return version or None


def _check(runner: Runner) -> dict[str, object]:
    release = _os_release()
    _validate_target_host(release)
    if shutil.which("docker") is None:
        return {
            "schema": SCHEMA,
            "status": "MISSING",
            "os_id": release.get("ID"),
            "os_version": release.get("VERSION_ID"),
            "os_codename": release.get("VERSION_CODENAME"),
            "architecture": platform.machine(),
            "docker_active": False,
            "docker_version": None,
            "compose_version": None,
            "production_service_start": False,
            "board_access": False,
        }
    package_versions = {
        package: _installed_package_version(runner, package)
        for package in PACKAGES
    }
    if any(version is None for version in package_versions.values()):
        return {
            "schema": SCHEMA,
            "status": "MISSING",
            "os_id": release.get("ID"),
            "os_version": release.get("VERSION_ID"),
            "os_codename": release.get("VERSION_CODENAME"),
            "architecture": platform.machine(),
            "docker_active": False,
            "docker_version": None,
            "compose_version": None,
            "package_source": "ubuntu_apt_required",
            "package_versions": package_versions,
            "production_service_start": False,
            "board_access": False,
        }
    docker_state = runner.run(
        ("systemctl", "is-active", "docker"),
        allowed=frozenset({0, 3, 4}),
    )
    docker_version = runner.run(
        ("docker", "version", "--format", "{{.Server.Version}}"),
        allowed=frozenset({0}),
    )
    compose_version = runner.run(
        ("docker", "compose", "version", "--short"),
        allowed=frozenset({0}),
    )
    ready = docker_state == "active" and bool(docker_version) and bool(compose_version)
    return {
        "schema": SCHEMA,
        "status": "PASS" if ready else "MISSING",
        "os_id": release.get("ID"),
        "os_version": release.get("VERSION_ID"),
        "os_codename": release.get("VERSION_CODENAME"),
        "architecture": platform.machine(),
        "docker_active": docker_state == "active",
        "docker_version": docker_version or None,
        "compose_version": compose_version or None,
        "package_source": "ubuntu_apt",
        "package_versions": package_versions,
        "production_service_start": False,
        "board_access": False,
    }


def execute_install(
    expected_versions: dict[str, str],
    runner: Runner | None = None,
) -> dict[str, object]:
    if os.geteuid() != 0:
        raise FreshHostBaselineError("root_required")
    if set(expected_versions) != set(PACKAGES) or any(
        not isinstance(expected_versions[package], str)
        or not expected_versions[package].strip()
        for package in PACKAGES
    ):
        raise FreshHostBaselineError("approved_package_versions_invalid")
    release = _os_release()
    _validate_target_host(release)
    active = runner or Runner()
    before = _check(active)
    if before["status"] == "PASS":
        if before.get("package_versions") != expected_versions:
            raise FreshHostBaselineError("installed_package_version_mismatch")
        return {
            **before,
            "installed": False,
            "package_source": "ubuntu_apt",
            "package_versions": before.get("package_versions", {}),
        }
    active.run(("apt-get", "update"), timeout=900.0)
    candidates = {
        package: _candidate(active.run(("apt-cache", "policy", package)), package)
        for package in PACKAGES
    }
    for package in PACKAGES:
        if candidates[package] != expected_versions[package]:
            raise FreshHostBaselineError(
                f"package_candidate_version_mismatch:{package}"
            )
    environment = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    active.run(
        (
            "apt-get",
            "install",
            "-y",
            *(f"{package}={expected_versions[package]}" for package in PACKAGES),
        ),
        timeout=1800.0,
        env=environment,
    )
    active.run(("systemctl", "enable", "docker"))
    active.run(("systemctl", "start", "docker"))
    report = _check(active)
    if report["status"] != "PASS":
        raise FreshHostBaselineError("postinstall_baseline_not_ready")
    if report.get("package_versions") != expected_versions:
        raise FreshHostBaselineError("postinstall_package_version_mismatch")
    return {
        **report,
        "installed": True,
        "package_source": "ubuntu_apt",
        "package_versions": expected_versions,
    }


def self_check() -> dict[str, object]:
    source = Path(__file__).read_text(encoding="utf-8")
    forbidden = (
        "n3wfc4-broker-activation.service",
        "n3wfc4-services-activation.service",
        "docker compose up",
        "armbian-install",
    )
    executable = source.split("\ndef self_check(", 1)[0]
    found = [value for value in forbidden if value in executable]
    return {
        "schema": SCHEMA,
        "status": "PASS" if not found else "STOP",
        "package_names": list(PACKAGES),
        "forbidden_operations": found,
        "production_service_start": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("self-check", "check", "install"), required=True)
    parser.add_argument("--docker-io-package-version")
    parser.add_argument("--docker-compose-v2-package-version")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.phase == "self-check":
            result = self_check()
        elif args.phase == "check":
            result = _check(Runner())
        else:
            if not args.docker_io_package_version or not args.docker_compose_v2_package_version:
                raise FreshHostBaselineError("approved_package_versions_required")
            result = execute_install(
                {
                    "docker.io": args.docker_io_package_version,
                    "docker-compose-v2": args.docker_compose_v2_package_version,
                }
            )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result.get("status") in {"PASS", "MISSING"} else 2
    except (FreshHostBaselineError, OSError, subprocess.TimeoutExpired) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:400],
                    "production_service_start": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
