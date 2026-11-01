from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

try:
    from . import n3w_t1_fresh_host_baseline as baseline
except ImportError:
    import n3w_t1_fresh_host_baseline as baseline

SCHEMA = "gh.n3w-t1-host-runtime-cache/1"
REPORT_SCHEMA = "gh.n3w-t1-host-runtime-cache-report/1"
PACKAGES = ("docker.io", "docker-compose-v2")
TARGET_ARMBIAN_VERSION = "26.05.0"
TARGET_ARMBIAN_BOARD = "S912-Phicomm-T1"
APT_SOURCE_POLICY = {
    "host": "ports.ubuntu.com",
    "suite": "resolute",
    "component": "universe",
    "architecture": "arm64",
}


class HostRuntimeCacheError(RuntimeError):
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
            raise HostRuntimeCacheError(
                f"command_failed:{Path(argv[0]).name}:{completed.returncode}:{reason[:400]}"
            )
        return completed.stdout.strip()


def _assignments(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _apt_source_text() -> str:
    paths = [Path("/etc/apt/sources.list")]
    root = Path("/etc/apt/sources.list.d")
    if root.is_dir():
        paths.extend(sorted(path for path in root.iterdir() if path.is_file()))
    lines: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if line:
                lines.append(line.casefold())
    return "\n".join(lines)


def _validate_apt_source_policy() -> dict[str, str]:
    source = _apt_source_text()
    for key in ("host", "suite", "component"):
        if APT_SOURCE_POLICY[key].casefold() not in source:
            raise HostRuntimeCacheError(f"apt_source_policy_mismatch:{key}")
    return dict(APT_SOURCE_POLICY)


def _host_contract(runner: Runner) -> dict[str, str]:
    release = baseline._os_release()
    baseline._validate_target_host(release)
    armbian_path = Path("/etc/armbian-release")
    if not armbian_path.is_file():
        raise HostRuntimeCacheError("armbian_release_missing")
    armbian = _assignments(armbian_path)
    if armbian.get("VERSION") != TARGET_ARMBIAN_VERSION:
        raise HostRuntimeCacheError("armbian_version_invalid")
    if armbian.get("BOARD") != TARGET_ARMBIAN_BOARD:
        raise HostRuntimeCacheError("armbian_board_invalid")
    package_architecture = runner.run(("dpkg", "--print-architecture"))
    if package_architecture != "arm64":
        raise HostRuntimeCacheError("package_architecture_invalid")
    if platform.machine() not in {"aarch64", "arm64"}:
        raise HostRuntimeCacheError("kernel_architecture_invalid")
    return {
        "os_id": release.get("ID", ""),
        "os_version": release.get("VERSION_ID", ""),
        "os_codename": release.get("VERSION_CODENAME", ""),
        "armbian_version": armbian.get("VERSION", ""),
        "armbian_board": armbian.get("BOARD", ""),
        "package_architecture": package_architecture,
    }


def _canonical_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_field(runner: Runner, path: Path, field: str) -> str:
    value = runner.run(("dpkg-deb", "-f", str(path), field))
    if not value:
        raise HostRuntimeCacheError(f"package_metadata_missing:{path.name}:{field}")
    return value.strip()


def _package_members(packages_dir: Path, runner: Runner) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    for path in sorted(packages_dir.glob("*.deb")):
        package = _package_field(runner, path, "Package")
        version = _package_field(runner, path, "Version")
        architecture = _package_field(runner, path, "Architecture")
        if architecture not in {"arm64", "all"}:
            raise HostRuntimeCacheError(
                f"package_architecture_unexpected:{path.name}:{architecture}"
            )
        members.append(
            {
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
                "package": package,
                "version": version,
                "architecture": architecture,
            }
        )
    if not members:
        raise HostRuntimeCacheError("package_bundle_empty")
    return members


def _validate_requested_members(
    members: list[dict[str, Any]],
    requested: dict[str, str],
) -> None:
    by_package: dict[str, set[str]] = {}
    for member in members:
        by_package.setdefault(str(member["package"]), set()).add(str(member["version"]))
    for package, version in requested.items():
        if version not in by_package.get(package, set()):
            raise HostRuntimeCacheError(
                f"requested_package_missing_from_bundle:{package}:{version}"
            )


def _write_manifest(
    cache_dir: Path,
    *,
    host_contract: dict[str, str],
    requested: dict[str, str],
    members: list[dict[str, Any]],
    apt_source_policy: dict[str, str],
) -> tuple[dict[str, Any], str]:
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "host_contract": host_contract,
        "apt_source_policy": apt_source_policy,
        "requested_packages": dict(sorted(requested.items())),
        "package_members": sorted(members, key=lambda item: str(item["filename"])),
    }
    canonical = _canonical_bytes(manifest)
    bundle_id = _sha256_bytes(canonical)
    (cache_dir / "manifest.json").write_bytes(canonical + b"\n")
    (cache_dir / "manifest.sha256").write_text(bundle_id + "\n", encoding="utf-8")
    return manifest, bundle_id


def _load_manifest(cache_dir: Path) -> tuple[dict[str, Any], str]:
    manifest_path = cache_dir / "manifest.json"
    digest_path = cache_dir / "manifest.sha256"
    if not manifest_path.is_file() or not digest_path.is_file():
        raise HostRuntimeCacheError("cache_manifest_missing")
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise HostRuntimeCacheError("cache_manifest_invalid") from error
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise HostRuntimeCacheError("cache_manifest_schema_invalid")
    bundle_id = _sha256_bytes(_canonical_bytes(document))
    recorded = digest_path.read_text(encoding="utf-8").strip()
    if recorded != bundle_id:
        raise HostRuntimeCacheError("cache_manifest_digest_mismatch")
    return document, bundle_id


def verify_archive(cache_dir: Path) -> dict[str, Any]:
    cache_dir = cache_dir.resolve()
    document, bundle_id = _load_manifest(cache_dir)
    requested = document.get("requested_packages")
    if not isinstance(requested, dict) or set(requested) != set(PACKAGES):
        raise HostRuntimeCacheError("cache_requested_packages_invalid")
    if any(not isinstance(value, str) or not value for value in requested.values()):
        raise HostRuntimeCacheError("cache_requested_package_version_invalid")
    members = document.get("package_members")
    if not isinstance(members, list) or not members:
        raise HostRuntimeCacheError("cache_package_members_invalid")

    normalized: list[dict[str, Any]] = []
    names: set[str] = set()
    for member in members:
        if not isinstance(member, dict):
            raise HostRuntimeCacheError("cache_package_member_invalid")
        filename = member.get("filename")
        size_bytes = member.get("size_bytes")
        sha256 = member.get("sha256")
        package = member.get("package")
        version = member.get("version")
        architecture = member.get("architecture")
        if (
            not isinstance(filename, str)
            or not filename
            or Path(filename).name != filename
            or not filename.endswith(".deb")
        ):
            raise HostRuntimeCacheError("cache_package_filename_invalid")
        if filename in names:
            raise HostRuntimeCacheError("cache_package_filename_duplicate")
        names.add(filename)
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise HostRuntimeCacheError(f"cache_package_size_invalid:{filename}")
        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
        ):
            raise HostRuntimeCacheError(f"cache_package_sha256_invalid:{filename}")
        if not isinstance(package, str) or not package:
            raise HostRuntimeCacheError(f"cache_package_name_invalid:{filename}")
        if not isinstance(version, str) or not version:
            raise HostRuntimeCacheError(f"cache_package_version_invalid:{filename}")
        if not isinstance(architecture, str) or not architecture:
            raise HostRuntimeCacheError(f"cache_package_architecture_invalid:{filename}")
        normalized.append(
            {
                "filename": filename,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "package": package,
                "version": version,
                "architecture": architecture,
            }
        )

    packages_dir = cache_dir / "packages"
    actual_paths = sorted(packages_dir.glob("*.deb"))
    actual_names = {path.name for path in actual_paths}
    if names != actual_names:
        raise HostRuntimeCacheError("cache_package_member_set_mismatch")
    for member in normalized:
        path = packages_dir / str(member["filename"])
        if path.stat().st_size != member["size_bytes"]:
            raise HostRuntimeCacheError(
                f"cache_package_size_mismatch:{member['filename']}"
            )
        if _sha256_file(path) != member["sha256"]:
            raise HostRuntimeCacheError(
                f"cache_package_sha256_mismatch:{member['filename']}"
            )
    _validate_requested_members(normalized, requested)
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "phase": "verify-archive",
        "bundle_id": bundle_id,
        "cache_dir": str(cache_dir),
        "package_count": len(normalized),
        "total_bytes": sum(int(item["size_bytes"]) for item in normalized),
        "requested_packages": dict(sorted(requested.items())),
        "network_download_performed": False,
        "cache_only_install": False,
        "production_service_start": False,
        "board_access": False,
    }


def _assert_fresh_docker_absent(runner: Runner) -> None:
    if shutil.which("docker") is not None:
        raise HostRuntimeCacheError("docker_command_already_present")
    for package in PACKAGES:
        if baseline._installed_package_version(runner, package) is not None:
            raise HostRuntimeCacheError(f"package_already_installed:{package}")
    for path in (
        Path("/var/lib/docker"),
        Path("/var/lib/containerd"),
        Path("/var/run/docker.sock"),
    ):
        if path.exists() or path.is_symlink():
            raise HostRuntimeCacheError(f"docker_runtime_residue:{path}")


def acquire_cache(
    cache_dir: Path,
    runner: Runner | None = None,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise HostRuntimeCacheError("root_required")
    active = runner or Runner()
    host = _host_contract(active)
    apt_policy = _validate_apt_source_policy()
    _assert_fresh_docker_absent(active)
    cache_dir = cache_dir.resolve()
    if cache_dir.exists() and any(cache_dir.iterdir()):
        raise HostRuntimeCacheError("cache_dir_not_empty")
    packages_dir = cache_dir / "packages"
    partial_dir = packages_dir / "partial"
    partial_dir.mkdir(parents=True, exist_ok=True)

    active.run(("apt-get", "update"), timeout=900.0)
    requested = {
        package: baseline._candidate(
            active.run(("apt-cache", "policy", package)),
            package,
        )
        for package in PACKAGES
    }
    environment = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    active.run(
        (
            "apt-get",
            "--download-only",
            "--yes",
            "--no-remove",
            "-o",
            f"Dir::Cache::archives={packages_dir}",
            "-o",
            "APT::Keep-Downloaded-Packages=true",
            "install",
            *(f"{package}={requested[package]}" for package in PACKAGES),
        ),
        timeout=1800.0,
        env=environment,
    )
    shutil.rmtree(partial_dir, ignore_errors=True)
    lock_path = packages_dir / "lock"
    if lock_path.exists() or lock_path.is_symlink():
        lock_path.unlink()

    members = _package_members(packages_dir, active)
    _validate_requested_members(members, requested)
    manifest, bundle_id = _write_manifest(
        cache_dir,
        host_contract=host,
        requested=requested,
        members=members,
        apt_source_policy=apt_policy,
    )
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "phase": "acquire",
        "bundle_id": bundle_id,
        "cache_dir": str(cache_dir),
        "package_count": len(members),
        "total_bytes": sum(int(item["size_bytes"]) for item in members),
        "requested_packages": manifest["requested_packages"],
        "network_download_performed": True,
        "cache_only_install": False,
        "production_service_start": False,
        "board_access": False,
    }


def verify_cache(
    cache_dir: Path,
    runner: Runner | None = None,
) -> dict[str, Any]:
    active = runner or Runner()
    cache_dir = cache_dir.resolve()
    archive = verify_archive(cache_dir)
    document, bundle_id = _load_manifest(cache_dir)
    host = _host_contract(active)
    if document.get("host_contract") != host:
        raise HostRuntimeCacheError("cache_host_contract_mismatch")
    apt_policy = _validate_apt_source_policy()
    if document.get("apt_source_policy") != apt_policy:
        raise HostRuntimeCacheError("cache_apt_source_policy_mismatch")
    requested = dict(document["requested_packages"])
    members = list(document["package_members"])
    packages_dir = cache_dir / "packages"
    observed_members = _package_members(packages_dir, active)
    if observed_members != sorted(
        members,
        key=lambda item: str(item["filename"]),
    ):
        raise HostRuntimeCacheError("cache_package_member_integrity_mismatch")
    _validate_requested_members(observed_members, requested)
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "phase": "verify",
        "bundle_id": bundle_id,
        "cache_dir": str(cache_dir),
        "package_count": archive["package_count"],
        "total_bytes": archive["total_bytes"],
        "requested_packages": dict(sorted(requested.items())),
        "network_download_performed": False,
        "cache_only_install": False,
        "production_service_start": False,
        "board_access": False,
    }


def install_cache(
    cache_dir: Path,
    runner: Runner | None = None,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise HostRuntimeCacheError("root_required")
    active = runner or Runner()
    verified = verify_cache(cache_dir, active)
    document, bundle_id = _load_manifest(cache_dir.resolve())
    requested = {
        str(key): str(value)
        for key, value in dict(document["requested_packages"]).items()
    }

    before = baseline._check(active)
    if before.get("status") == "PASS":
        if before.get("package_versions") != requested:
            raise HostRuntimeCacheError("installed_package_version_mismatch")
        return {
            **verified,
            "phase": "install",
            "installed": False,
            "cache_only_install": True,
            "network_download_performed": False,
        }

    packages_dir = cache_dir.resolve() / "packages"
    package_paths = [str(path) for path in sorted(packages_dir.glob("*.deb"))]
    if not package_paths:
        raise HostRuntimeCacheError("cache_package_files_missing")
    environment = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    active.run(
        (
            "apt-get",
            "--no-download",
            "--no-remove",
            "install",
            "-y",
            *package_paths,
        ),
        timeout=1800.0,
        env=environment,
    )
    active.run(("systemctl", "enable", "docker"))
    active.run(("systemctl", "start", "docker"))

    report = baseline._check(active)
    if report.get("status") != "PASS":
        raise HostRuntimeCacheError("postinstall_baseline_not_ready")
    if report.get("package_versions") != requested:
        raise HostRuntimeCacheError("postinstall_package_version_mismatch")
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "phase": "install",
        "bundle_id": bundle_id,
        "cache_dir": str(cache_dir.resolve()),
        "package_count": verified["package_count"],
        "total_bytes": verified["total_bytes"],
        "requested_packages": requested,
        "docker_version": report.get("docker_version"),
        "compose_version": report.get("compose_version"),
        "installed": True,
        "cache_only_install": True,
        "network_download_performed": False,
        "production_service_start": False,
        "board_access": False,
    }


def self_check() -> dict[str, Any]:
    install_source = inspect.getsource(install_cache)
    executable_source = Path(__file__).read_text(encoding="utf-8").split(
        "\ndef self_check(", 1
    )[0]
    violations: list[str] = []
    if "--no-download" not in install_source:
        violations.append("cache_install_missing_no_download")
    if '"apt-get", "update"' in install_source:
        violations.append("cache_install_contains_apt_update")
    for forbidden in (
        "get.docker.com",
        "docker-ce",
        "n3wfc4-broker-activation.service",
        "n3wfc4-services-activation.service",
        "docker compose up",
        "armbian-install",
    ):
        if forbidden in executable_source:
            violations.append(f"forbidden_source_token:{forbidden}")
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS" if not violations else "STOP",
        "phase": "self-check",
        "violations": violations,
        "cache_only_install_guard": "--no-download" in install_source,
        "production_service_start": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("self-check", "acquire", "verify-archive", "verify", "install"),
        required=True,
    )
    parser.add_argument("--cache-dir")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.phase == "self-check":
            result = self_check()
        else:
            if not args.cache_dir:
                raise HostRuntimeCacheError("cache_dir_required")
            cache_dir = Path(args.cache_dir)
            if args.phase == "acquire":
                result = acquire_cache(cache_dir)
            elif args.phase == "verify-archive":
                result = verify_archive(cache_dir)
            elif args.phase == "verify":
                result = verify_cache(cache_dir)
            else:
                result = install_cache(cache_dir)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result.get("status") == "PASS" else 2
    except (
        HostRuntimeCacheError,
        baseline.FreshHostBaselineError,
        OSError,
        subprocess.TimeoutExpired,
    ) as error:
        print(
            json.dumps(
                {
                    "schema": REPORT_SCHEMA,
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
