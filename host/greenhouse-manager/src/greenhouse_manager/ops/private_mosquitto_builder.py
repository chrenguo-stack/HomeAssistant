from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .node_mqtt_board_lab_common import (
    NodeMqttBoardLabError,
    _canonical_json,
    _fingerprint,
    _require,
)

PRIVATE_MOSQUITTO_VERSION = "2.0.21"
PRIVATE_MOSQUITTO_SOURCE_URL = (
    "https://mosquitto.org/files/source/mosquitto-2.0.21.tar.gz"
)
PRIVATE_MOSQUITTO_SOURCE_SHA256 = (
    "7ad5e84caeb8d2bb6ed0c04614b2a7042def961af82d87f688ba33db857b899d"
)
PRIVATE_MOSQUITTO_CONFIRMATION = "M2-NONPRODUCTION-PRIVATE-MOSQUITTO"
PRIVATE_MOSQUITTO_MANIFEST_SCHEMA = "gh.m2.private-mosquitto-manifest/1"
PRIVATE_MOSQUITTO_REPORT_SCHEMA = "gh.m2.private-mosquitto-report/1"
PRIVATE_MOSQUITTO_RECIPE = "cmake-minimal-no-websockets/1"
PRIVATE_MOSQUITTO_MARKER = ".gh-private-mosquitto"
PRIVATE_MOSQUITTO_MANIFEST = "manifest.json"
MAX_SOURCE_BYTES = 16 * 1024 * 1024


class Runner(Protocol):
    def __call__(
        self,
        command: Sequence[str],
        *,
        check: bool = True,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]: ...


class Downloader(Protocol):
    def __call__(self, url: str, destination: Path) -> None: ...


def _run(
    command: Sequence[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=check,
        text=True,
        capture_output=True,
        cwd=cwd,
    )


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "greenhouse-manager-private-mosquitto/1"},
    )
    total = 0
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response, destination.open(
        "wb"
    ) as stream:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            _require(
                total <= MAX_SOURCE_BYTES,
                "private Mosquitto source archive exceeds size limit",
            )
            digest.update(chunk)
            stream.write(chunk)
    _require(total > 0, "private Mosquitto source archive is empty")
    _require(
        digest.hexdigest() == PRIVATE_MOSQUITTO_SOURCE_SHA256,
        "private Mosquitto source archive SHA-256 mismatch",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _platform_key() -> str:
    system = platform.system().strip().lower()
    machine = platform.machine().strip().lower()
    aliases = {"amd64": "x86_64", "aarch64": "arm64"}
    machine = aliases.get(machine, machine)
    _require(
        system in {"darwin", "linux"},
        "private Mosquitto builder supports macOS and Linux only",
    )
    _require(
        machine in {"x86_64", "arm64"},
        "private Mosquitto builder architecture is unsupported",
    )
    return f"{system}-{machine}"


def private_mosquitto_install_dir(cache_root: str | Path) -> Path:
    root = Path(cache_root).expanduser().resolve()
    _require(root != Path("/"), "private Mosquitto cache root cannot be filesystem root")
    _require(len(root.parts) >= 3, "private Mosquitto cache root is too broad")
    return root / PRIVATE_MOSQUITTO_VERSION / _platform_key()


def private_mosquitto_manifest_path(cache_root: str | Path) -> Path:
    return private_mosquitto_install_dir(cache_root) / PRIVATE_MOSQUITTO_MANIFEST


def _resolve_executable(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        resolved = candidate.resolve()
        _require(resolved.is_file(), f"required executable is missing: {candidate.name}")
        _require(
            os.access(resolved, os.X_OK),
            f"required executable is not executable: {candidate.name}",
        )
        return str(resolved)
    located = shutil.which(value)
    _require(located is not None, f"required executable is unavailable: {value}")
    return str(Path(located).resolve())


def _cmake_version(cmake_bin: str, runner: Runner) -> str:
    result = runner((cmake_bin, "--version"), check=False)
    _require(result.returncode == 0, "cmake version probe failed")
    first = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
    prefix = "cmake version "
    _require(first.startswith(prefix), "cmake version output is invalid")
    version = first.removeprefix(prefix).strip()
    parts = version.split(".")
    _require(
        len(parts) >= 2 and all(part.isdigit() for part in parts[:2]),
        "cmake version is invalid",
    )
    _require(
        (int(parts[0]), int(parts[1])) >= (3, 18),
        "cmake 3.18 or newer is required",
    )
    return version


def _base_report(
    *,
    status: str,
    cache_root: Path,
    cmake_version: str | None,
) -> dict[str, object]:
    return {
        "schema": PRIVATE_MOSQUITTO_REPORT_SCHEMA,
        "status": status,
        "version": PRIVATE_MOSQUITTO_VERSION,
        "source_url": PRIVATE_MOSQUITTO_SOURCE_URL,
        "source_sha256": PRIVATE_MOSQUITTO_SOURCE_SHA256,
        "recipe": PRIVATE_MOSQUITTO_RECIPE,
        "platform": _platform_key(),
        "cache_root_fingerprint": _fingerprint(str(cache_root)),
        "cmake_version": cmake_version,
        "websockets_enabled": False,
        "clients_built": False,
        "plugins_built": False,
        "documentation_built": False,
        "tls_enabled": True,
        "homebrew_mosquitto_required": False,
        "homebrew_service_action_invoked": False,
        "production_endpoint_used": False,
        "production_identity_used": False,
        "production_execution_invoked": False,
        "current_services_modified": False,
        "homeassistant_storage_read": False,
        "node_credentials_delivered": False,
        "anonymous_closure_enabled": False,
        "secret_values_included": False,
        "source_paths_included": False,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
        "ready_for_node_credential_generation": False,
        "real_board_runtime_fault_matrix_complete": False,
    }


def plan_private_mosquitto(
    cache_root: str | Path,
    *,
    cmake_bin: str = "cmake",
    openssl_root: str | Path | None = None,
    runner: Runner = _run,
) -> dict[str, object]:
    root = Path(cache_root).expanduser().resolve()
    install_dir = private_mosquitto_install_dir(root)
    resolved_cmake = _resolve_executable(cmake_bin)
    version = _cmake_version(resolved_cmake, runner)
    if openssl_root is not None:
        resolved_openssl = Path(openssl_root).expanduser().resolve()
        _require(resolved_openssl.is_dir(), "OpenSSL root directory is missing")
    report = _base_report(
        status="private_mosquitto_plan_created",
        cache_root=root,
        cmake_version=version,
    )
    report.update(
        {
            "install_fingerprint": _fingerprint(str(install_dir)),
            "existing_install": install_dir.exists(),
            "explicit_nonproduction_confirmation_required": True,
            "source_archive_can_be_reused": True,
        }
    )
    return report


def _copy_source_archive(
    source_archive: Path | None,
    destination: Path,
    downloader: Downloader,
) -> None:
    if source_archive is None:
        downloader(PRIVATE_MOSQUITTO_SOURCE_URL, destination)
        return
    resolved = source_archive.expanduser().resolve()
    _require(resolved.is_file(), "private Mosquitto source archive is missing")
    _require(
        resolved.stat().st_size <= MAX_SOURCE_BYTES,
        "private Mosquitto source archive exceeds size limit",
    )
    _require(
        _sha256_file(resolved) == PRIVATE_MOSQUITTO_SOURCE_SHA256,
        "private Mosquitto source archive SHA-256 mismatch",
    )
    shutil.copyfile(resolved, destination)


def _validate_member(member: tarfile.TarInfo) -> None:
    name = PurePosixPath(member.name)
    _require(
        not name.is_absolute(),
        "private Mosquitto archive contains an absolute path",
    )
    _require(
        ".." not in name.parts,
        "private Mosquitto archive contains path traversal",
    )
    _require(
        member.isfile() or member.isdir(),
        "private Mosquitto archive contains unsupported entry type",
    )


def _extract_source(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive, mode="r:gz") as bundle:
        members = bundle.getmembers()
        _require(members, "private Mosquitto source archive contains no files")
        for member in members:
            _validate_member(member)
        bundle.extractall(destination, members=members)
    source_root = destination / f"mosquitto-{PRIVATE_MOSQUITTO_VERSION}"
    _require(source_root.is_dir(), "private Mosquitto source root is missing")
    cmake_file = source_root / "CMakeLists.txt"
    _require(cmake_file.is_file(), "private Mosquitto CMakeLists.txt is missing")
    _require(
        f"set (VERSION {PRIVATE_MOSQUITTO_VERSION})"
        in cmake_file.read_text(encoding="utf-8"),
        "private Mosquitto source version does not match the frozen version",
    )
    return source_root


def _build_options(stage: Path, openssl_root: Path | None) -> tuple[str, ...]:
    options = [
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={stage}",
        "-DWITH_WEBSOCKETS=OFF",
        "-DWITH_CLIENTS=OFF",
        "-DWITH_PLUGINS=OFF",
        "-DDOCUMENTATION=OFF",
        "-DWITH_CJSON=OFF",
        "-DWITH_SRV=OFF",
        "-DWITH_DLT=OFF",
        "-DWITH_STATIC_LIBRARIES=OFF",
        "-DWITH_TLS=ON",
        "-DWITH_TLS_PSK=ON",
        "-DWITH_APPS=ON",
    ]
    if openssl_root is not None:
        options.append(f"-DOPENSSL_ROOT_DIR={openssl_root}")
    return tuple(options)


def _write_private_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(_canonical_json(value) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _verify_version(binary: Path, runner: Runner) -> str:
    result = runner((str(binary), "-h"), check=False)
    encoded = f"{result.stdout}\n{result.stderr}"
    marker = f"mosquitto version {PRIVATE_MOSQUITTO_VERSION}"
    _require(
        marker.lower() in encoded.lower(),
        "private Mosquitto binary version mismatch",
    )
    return PRIVATE_MOSQUITTO_VERSION


def _manifest_document(
    *,
    install_dir: Path,
    mosquitto_sha256: str,
    passwd_sha256: str,
    cmake_version: str,
    cmake_options: Sequence[str],
) -> dict[str, object]:
    return {
        "schema": PRIVATE_MOSQUITTO_MANIFEST_SCHEMA,
        "version": PRIVATE_MOSQUITTO_VERSION,
        "source_url": PRIVATE_MOSQUITTO_SOURCE_URL,
        "source_sha256": PRIVATE_MOSQUITTO_SOURCE_SHA256,
        "recipe": PRIVATE_MOSQUITTO_RECIPE,
        "platform": _platform_key(),
        "install_dir": str(install_dir),
        "mosquitto_bin": str(install_dir / "bin" / "mosquitto"),
        "mosquitto_passwd_bin": str(install_dir / "bin" / "mosquitto_passwd"),
        "mosquitto_sha256": mosquitto_sha256,
        "mosquitto_passwd_sha256": passwd_sha256,
        "cmake_version": cmake_version,
        "cmake_options": list(cmake_options),
        "websockets_enabled": False,
        "clients_built": False,
        "plugins_built": False,
        "documentation_built": False,
        "tls_enabled": True,
        "production_identity_used": False,
    }


def load_private_mosquitto_manifest(
    manifest_path: str | Path,
    *,
    runner: Runner = _run,
) -> tuple[str, str, dict[str, object]]:
    path = Path(manifest_path).expanduser().resolve()
    _require(path.is_file(), "private Mosquitto manifest is missing")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NodeMqttBoardLabError("private Mosquitto manifest is invalid") from error
    _require(
        isinstance(document, dict),
        "private Mosquitto manifest root must be an object",
    )
    _require(
        document.get("schema") == PRIVATE_MOSQUITTO_MANIFEST_SCHEMA,
        "private Mosquitto manifest schema mismatch",
    )
    _require(
        document.get("version") == PRIVATE_MOSQUITTO_VERSION,
        "private Mosquitto manifest version mismatch",
    )
    _require(
        document.get("source_sha256") == PRIVATE_MOSQUITTO_SOURCE_SHA256,
        "private Mosquitto source binding mismatch",
    )
    _require(
        document.get("recipe") == PRIVATE_MOSQUITTO_RECIPE,
        "private Mosquitto recipe binding mismatch",
    )
    _require(
        document.get("platform") == _platform_key(),
        "private Mosquitto platform binding mismatch",
    )
    _require(
        document.get("websockets_enabled") is False,
        "private Mosquitto websockets must remain disabled",
    )
    _require(
        document.get("production_identity_used") is False,
        "private Mosquitto manifest used a production identity",
    )

    install_dir_raw = document.get("install_dir")
    mosquitto_raw = document.get("mosquitto_bin")
    passwd_raw = document.get("mosquitto_passwd_bin")
    _require(
        isinstance(install_dir_raw, str),
        "private Mosquitto install path is missing",
    )
    _require(
        isinstance(mosquitto_raw, str),
        "private Mosquitto binary path is missing",
    )
    _require(
        isinstance(passwd_raw, str),
        "private mosquitto_passwd path is missing",
    )
    install_dir = Path(install_dir_raw).resolve()
    _require(
        path.parent == install_dir,
        "private Mosquitto manifest directory binding mismatch",
    )
    marker = install_dir / PRIVATE_MOSQUITTO_MARKER
    _require(marker.is_file(), "private Mosquitto marker is missing")
    _require(
        marker.read_text(encoding="utf-8").strip() == PRIVATE_MOSQUITTO_VERSION,
        "private Mosquitto marker mismatch",
    )

    mosquitto_bin = Path(mosquitto_raw).resolve()
    passwd_bin = Path(passwd_raw).resolve()
    for binary in (mosquitto_bin, passwd_bin):
        _require(
            binary.parent == install_dir / "bin",
            "private Mosquitto binary escaped install directory",
        )
        _require(
            binary.is_file() and os.access(binary, os.X_OK),
            "private Mosquitto executable is unavailable",
        )
    _require(
        _sha256_file(mosquitto_bin) == document.get("mosquitto_sha256"),
        "private Mosquitto binary SHA-256 mismatch",
    )
    _require(
        _sha256_file(passwd_bin) == document.get("mosquitto_passwd_sha256"),
        "private mosquitto_passwd SHA-256 mismatch",
    )
    _verify_version(mosquitto_bin, runner)
    return str(mosquitto_bin), str(passwd_bin), dict(document)


def verify_private_mosquitto(
    manifest_path: str | Path,
    *,
    runner: Runner = _run,
) -> dict[str, object]:
    path = Path(manifest_path).expanduser().resolve()
    _, _, document = load_private_mosquitto_manifest(path, runner=runner)
    report = _base_report(
        status="private_mosquitto_verified",
        cache_root=path.parents[2],
        cmake_version=str(document["cmake_version"]),
    )
    report.update(
        {
            "install_fingerprint": _fingerprint(str(path.parent)),
            "mosquitto_sha256": document["mosquitto_sha256"],
            "mosquitto_passwd_sha256": document["mosquitto_passwd_sha256"],
            "manifest_private": path.stat().st_mode & 0o777 == 0o600,
            "executables_verified": True,
        }
    )
    return report


def build_private_mosquitto(
    cache_root: str | Path,
    *,
    confirmation: str,
    source_archive: str | Path | None = None,
    cmake_bin: str = "cmake",
    openssl_root: str | Path | None = None,
    jobs: int = 2,
    runner: Runner = _run,
    downloader: Downloader = _download,
) -> dict[str, object]:
    _require(
        confirmation == PRIVATE_MOSQUITTO_CONFIRMATION,
        "private Mosquitto confirmation mismatch",
    )
    _require(
        1 <= jobs <= 32,
        "private Mosquitto build jobs must be between 1 and 32",
    )
    root = Path(cache_root).expanduser().resolve()
    install_dir = private_mosquitto_install_dir(root)
    resolved_cmake = _resolve_executable(cmake_bin)
    cmake_version = _cmake_version(resolved_cmake, runner)
    resolved_openssl = None
    if openssl_root is not None:
        resolved_openssl = Path(openssl_root).expanduser().resolve()
        _require(
            resolved_openssl.is_dir(),
            "OpenSSL root directory is missing",
        )

    if install_dir.exists():
        report = verify_private_mosquitto(
            install_dir / PRIVATE_MOSQUITTO_MANIFEST,
            runner=runner,
        )
        report["status"] = "private_mosquitto_reused"
        return report

    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    version_root = install_dir.parent
    version_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    version_root.chmod(0o700)
    work_root = Path(
        tempfile.mkdtemp(
            prefix=f".{_platform_key()}-build-",
            dir=version_root,
        )
    )
    work_root.chmod(0o700)
    try:
        archive = work_root / f"mosquitto-{PRIVATE_MOSQUITTO_VERSION}.tar.gz"
        _copy_source_archive(
            None if source_archive is None else Path(source_archive),
            archive,
            downloader,
        )
        _require(
            _sha256_file(archive) == PRIVATE_MOSQUITTO_SOURCE_SHA256,
            "private Mosquitto source archive SHA-256 mismatch",
        )
        source_parent = work_root / "source"
        source_parent.mkdir(mode=0o700)
        source_root = _extract_source(archive, source_parent)
        build_dir = work_root / "build"
        stage = work_root / "stage"
        stage_bin = stage / "bin"
        stage_bin.mkdir(parents=True, mode=0o700)
        options = _build_options(stage, resolved_openssl)
        runner(
            (
                resolved_cmake,
                "-S",
                str(source_root),
                "-B",
                str(build_dir),
                *options,
            ),
            cwd=work_root,
        )
        runner(
            (
                resolved_cmake,
                "--build",
                str(build_dir),
                "--target",
                "mosquitto",
                "mosquitto_passwd",
                "--parallel",
                str(jobs),
            ),
            cwd=work_root,
        )
        built_mosquitto = build_dir / "src" / "mosquitto"
        built_passwd = (
            build_dir / "apps" / "mosquitto_passwd" / "mosquitto_passwd"
        )
        for binary in (built_mosquitto, built_passwd):
            _require(
                binary.is_file() and os.access(binary, os.X_OK),
                "private Mosquitto build output is missing",
            )
        staged_mosquitto = stage_bin / "mosquitto"
        staged_passwd = stage_bin / "mosquitto_passwd"
        shutil.copy2(built_mosquitto, staged_mosquitto)
        shutil.copy2(built_passwd, staged_passwd)
        staged_mosquitto.chmod(0o700)
        staged_passwd.chmod(0o700)
        _verify_version(staged_mosquitto, runner)

        cache_text = (build_dir / "CMakeCache.txt").read_text(encoding="utf-8")
        for expected in (
            "WITH_WEBSOCKETS:BOOL=OFF",
            "WITH_CLIENTS:BOOL=OFF",
            "WITH_PLUGINS:BOOL=OFF",
            "DOCUMENTATION:BOOL=OFF",
            "WITH_TLS:BOOL=ON",
        ):
            _require(
                expected in cache_text,
                f"private Mosquitto CMake contract missing: {expected}",
            )

        marker = stage / PRIVATE_MOSQUITTO_MARKER
        marker.write_text(PRIVATE_MOSQUITTO_VERSION + "\n", encoding="utf-8")
        marker.chmod(0o600)
        manifest = _manifest_document(
            install_dir=install_dir,
            mosquitto_sha256=_sha256_file(staged_mosquitto),
            passwd_sha256=_sha256_file(staged_passwd),
            cmake_version=cmake_version,
            cmake_options=options,
        )
        _write_private_json(stage / PRIVATE_MOSQUITTO_MANIFEST, manifest)
        _require(
            not install_dir.exists(),
            "private Mosquitto install appeared during build",
        )
        stage.rename(install_dir)
        report = verify_private_mosquitto(
            install_dir / PRIVATE_MOSQUITTO_MANIFEST,
            runner=runner,
        )
        report["status"] = "private_mosquitto_built"
        report["source_archive_reused"] = source_archive is not None
        return report
    finally:
        if work_root.exists():
            shutil.rmtree(work_root)
