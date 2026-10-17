#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

SCHEMA = "gh.n3w-t1-fresh-host-baseline/1"
TARGET_OS_ID = "ubuntu"
TARGET_OS_VERSION = "26.04"
TARGET_OS_CODENAME = "resolute"
PACKAGES = ("docker.io", "docker-compose-v2")
PRODUCTION_PHASE = "HOST_BASELINE"
PRODUCTION_CONTEXT_SCHEMA = "gh.n3w-t1-production-phase-context/1"
PRODUCTION_CLAIM_SCHEMA = "gh.n3w-t1-host-baseline-production-claim/1"
PRODUCTION_COMPLETE_SCHEMA = "gh.n3w-t1-host-baseline-production-complete/1"
PRODUCTION_EXECUTION_LEDGER_ROOT = Path(
    "/var/lib/n3w-t1-host-baseline-production-executions"
)


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


def execute_install(runner: Runner | None = None) -> dict[str, object]:
    if os.geteuid() != 0:
        raise FreshHostBaselineError("root_required")
    release = _os_release()
    _validate_target_host(release)
    active = runner or Runner()
    before = _check(active)
    if before["status"] == "PASS":
        return {
            **before,
            "installed": False,
            "package_source": "ubuntu_apt",
            "package_versions": before.get("package_versions", {}),
        }
    active.run(("apt-get", "update"), timeout=900.0)
    versions = {
        package: _candidate(active.run(("apt-cache", "policy", package)), package)
        for package in PACKAGES
    }
    environment = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    active.run(
        (
            "apt-get",
            "install",
            "-y",
            *(f"{package}={versions[package]}" for package in PACKAGES),
        ),
        timeout=1800.0,
        env=environment,
    )
    active.run(("systemctl", "enable", "docker"))
    active.run(("systemctl", "start", "docker"))
    report = _check(active)
    if report["status"] != "PASS":
        raise FreshHostBaselineError("postinstall_baseline_not_ready")
    return {
        **report,
        "installed": True,
        "package_source": "ubuntu_apt",
        "package_versions": versions,
    }



def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_new_json(path: Path, document: dict[str, object]) -> None:
    if path.exists() or path.is_symlink():
        raise FreshHostBaselineError("production_execution_record_exists")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise FreshHostBaselineError("production_execution_root_invalid")
    os.chmod(path.parent, 0o700)
    metadata = path.parent.stat()
    if (
        metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise FreshHostBaselineError("production_execution_root_invalid")
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _production_paths(
    context: dict[str, object],
) -> tuple[Path, Path]:
    digest = hashlib.sha256(
        (
            str(context["run_id"])
            + "\n"
            + str(context["phase"])
            + "\n"
            + str(context["claim_sha256"])
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    return (
        PRODUCTION_EXECUTION_LEDGER_ROOT / f"{digest}.claim.json",
        PRODUCTION_EXECUTION_LEDGER_ROOT / f"{digest}.complete.json",
    )


def _load_production_context(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise FreshHostBaselineError("production_phase_context_missing")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FreshHostBaselineError("production_phase_context_invalid") from error
    binding = document.get("binding") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("schema") != PRODUCTION_CONTEXT_SCHEMA
        or document.get("phase") != PRODUCTION_PHASE
        or re.fullmatch(r"[0-9a-f]{64}", str(document.get("run_id"))) is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(document.get("claim_sha256")),
        )
        is None
        or not isinstance(binding, dict)
        or re.fullmatch(
            r"[0-9a-f]{40}",
            str(binding.get("source_head")),
        )
        is None
        or re.fullmatch(
            r"[0-9a-f]{64}",
            str(binding.get("release_id")),
        )
        is None
        or document.get("authorization_consumed") is not True
        or document.get("replay_allowed") is not False
        or document.get("board_access") is not False
    ):
        raise FreshHostBaselineError("production_phase_context_invalid")
    try:
        from n3w_t1_production_authority import validate_phase_context
    except ImportError as error:
        raise FreshHostBaselineError(
            "production_authority_dependency_missing"
        ) from error
    validated = validate_phase_context(
        document,
        required_phase=PRODUCTION_PHASE,
    )
    if (
        validated.get("status") != "PASS"
        or validated.get("claim_sha256") != document["claim_sha256"]
    ):
        raise FreshHostBaselineError(
            "production_phase_context_not_authorized"
        )
    return document


def _load_approved_release(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise FreshHostBaselineError("approved_release_missing")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FreshHostBaselineError("approved_release_invalid") from error
    try:
        from n3w_t1_production_contract import validate_release
    except ImportError as error:
        raise FreshHostBaselineError(
            "production_contract_dependency_missing"
        ) from error
    try:
        return validate_release(document)
    except Exception as error:
        raise FreshHostBaselineError("approved_release_invalid") from error


def _approved_environment(
    release: dict[str, object],
    context: dict[str, object],
) -> dict[str, object]:
    binding = context["binding"]
    environment = release.get("environment")
    if (
        not isinstance(binding, dict)
        or release.get("release_id") != binding.get("release_id")
        or release.get("source_head") != binding.get("source_head")
        or not isinstance(environment, dict)
        or environment.get("package_source") != "ubuntu_apt"
    ):
        raise FreshHostBaselineError("approved_release_binding_invalid")
    return environment


def _validate_approved_host(environment: dict[str, object]) -> None:
    release = _os_release()
    os_policy = environment.get("os")
    if not isinstance(os_policy, dict):
        raise FreshHostBaselineError("approved_os_policy_invalid")
    if (
        release.get("ID") != os_policy.get("id")
        or release.get("VERSION_ID") != os_policy.get("version")
        or release.get("VERSION_CODENAME") != os_policy.get("codename")
        or platform.machine() not in {"aarch64", "arm64"}
        or environment.get("architecture") not in {"aarch64", "arm64"}
    ):
        raise FreshHostBaselineError("approved_host_environment_mismatch")


def _installed_versions(runner: Runner) -> dict[str, str | None]:
    return {
        package: _installed_package_version(runner, package)
        for package in PACKAGES
    }


def _approved_versions_available(
    runner: Runner,
    approved: dict[str, str],
) -> None:
    for package, version in approved.items():
        output = runner.run(
            ("apt-cache", "madison", package),
            allowed=frozenset({0}),
        )
        versions = {
            fields[1].strip()
            for line in output.splitlines()
            if len(fields := line.split("|")) >= 3
        }
        if version not in versions:
            raise FreshHostBaselineError(
                f"approved_package_version_unavailable:{package}"
            )


def execute_production_install(
    production_phase_context: Path,
    approved_release: Path,
    runner: Runner | None = None,
) -> dict[str, object]:
    if os.geteuid() != 0:
        raise FreshHostBaselineError("root_required")
    context = _load_production_context(production_phase_context)
    release = _load_approved_release(approved_release)
    environment = _approved_environment(release, context)
    _validate_approved_host(environment)
    packages = environment.get("packages")
    if (
        not isinstance(packages, dict)
        or set(packages) != set(PACKAGES)
        or not all(isinstance(value, str) and value for value in packages.values())
    ):
        raise FreshHostBaselineError("approved_package_policy_invalid")
    approved_versions = {
        package: str(packages[package])
        for package in PACKAGES
    }
    claim_path, complete_path = _production_paths(context)
    if (
        claim_path.exists()
        or claim_path.is_symlink()
        or complete_path.exists()
        or complete_path.is_symlink()
    ):
        raise FreshHostBaselineError("production_execution_already_consumed")
    claim = {
        "schema": PRODUCTION_CLAIM_SCHEMA,
        "run_id": context["run_id"],
        "phase": PRODUCTION_PHASE,
        "phase_claim_sha256": context["claim_sha256"],
        "release_id": release["release_id"],
        "source_head": release["source_head"],
        "approved_package_source": "ubuntu_apt",
        "approved_package_versions": approved_versions,
        "authorization_consumed": True,
        "replay_allowed": False,
        "board_access": False,
    }
    _write_new_json(claim_path, claim)
    active = runner or Runner()
    try:
        installed_before = _installed_versions(active)
        wrong = {
            package: version
            for package, version in installed_before.items()
            if version is not None and version != approved_versions[package]
        }
        if wrong:
            raise FreshHostBaselineError("installed_package_version_drift")
        install_required = any(
            installed_before[package] is None for package in PACKAGES
        )
        if install_required:
            active.run(("apt-get", "update"), timeout=900.0)
            _approved_versions_available(active, approved_versions)
            environment_vars = {
                **os.environ,
                "DEBIAN_FRONTEND": "noninteractive",
            }
            active.run(
                (
                    "apt-get",
                    "install",
                    "-y",
                    *(
                        f"{package}={approved_versions[package]}"
                        for package in PACKAGES
                    ),
                ),
                timeout=1800.0,
                env=environment_vars,
            )
            active.run(("systemctl", "enable", "docker"))
            active.run(("systemctl", "start", "docker"))
        installed_after = _installed_versions(active)
        if installed_after != approved_versions:
            raise FreshHostBaselineError(
                "approved_package_version_postcheck_failed"
            )
        report = _check(active)
        if (
            report.get("status") != "PASS"
            or report.get("package_versions") != approved_versions
            or report.get("production_service_start") is not False
        ):
            raise FreshHostBaselineError(
                "production_host_baseline_postcheck_failed"
            )
        result = {
            **report,
            "status": "PASS",
            "production_run_id": context["run_id"],
            "production_phase": PRODUCTION_PHASE,
            "approved_release_id": release["release_id"],
            "approved_package_source": "ubuntu_apt",
            "approved_package_versions": approved_versions,
            "installed": install_required,
            "authorization_consumed": True,
            "replay_allowed": False,
            "board_access": False,
        }
        complete = {
            "schema": PRODUCTION_COMPLETE_SCHEMA,
            "run_id": context["run_id"],
            "phase": PRODUCTION_PHASE,
            "phase_claim_sha256": context["claim_sha256"],
            "claim_record_sha256": _sha256_file(claim_path),
            "result_sha256": hashlib.sha256(
                json.dumps(
                    result,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "authorization_consumed": True,
            "replay_allowed": False,
            "board_access": False,
        }
        _write_new_json(complete_path, complete)
        return result
    except Exception as error:
        raise FreshHostBaselineError(
            "production_host_baseline_claimed:" + str(error)[:240]
        ) from error


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
    parser.add_argument(
        "--phase",
        choices=("self-check", "check", "install", "production-install"),
        required=True,
    )
    parser.add_argument("--production-phase-context", type=Path)
    parser.add_argument("--approved-release", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.phase == "self-check":
            result = self_check()
        elif args.phase == "check":
            result = _check(Runner())
        elif args.phase == "install":
            result = execute_install()
        else:
            if (
                args.production_phase_context is None
                or args.approved_release is None
            ):
                raise FreshHostBaselineError(
                    "production_install_arguments_missing"
                )
            result = execute_production_install(
                args.production_phase_context,
                args.approved_release,
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
