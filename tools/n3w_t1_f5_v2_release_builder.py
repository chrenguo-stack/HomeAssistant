#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from n3w_t1_production_v2_contract import (
    RELEASE_INPUT_ARTIFACT_PATHS,
    RELEASE_SCHEMA,
    REQUIRED_RELEASE_ARTIFACTS,
    canonical_json_bytes,
    canonical_sha256,
    validate_release,
)

INPUT_SCHEMA = "gh.n3w-t1-production-v2-release-inputs/1"
MANIFEST_NAME = "release.json"
SHA_NAME = "release.sha256"
ARTIFACT_DIR = "artifacts"
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
FINAL_ARTIFACT_NAME_PREFIX = "n3w-t1-f5-v2-exact-production-release-"
FINAL_TAR_NAME = "n3w-t1-f5-v2-release.tar.gz"
FINAL_TAR_SHA_NAME = "n3w-t1-f5-v2-release.tar.gz.sha256"
FINAL_OUTER_FILES = frozenset({FINAL_TAR_NAME, FINAL_TAR_SHA_NAME})
RELEASE_ROOT_NAME = "n3w-t1-f5-v2-release"
LOCAL_BINDING_SCHEMA = "gh.n3w-t1-f5-v2-local-release-binding/1"
MAC_TOOLS_SCHEMA = "gh.n3w-t1-f5-v2-mac-tools/1"
F4_PACKAGE_SCHEMA = "gh.n3w-t1-f4-activation-package/1"
REBOOT_PACKAGE_SCHEMA = "gh.n3w-t1-f4-reboot-successor-control-package/1"
IMAGE_SET_SCHEMA = "gh.n3w-t1-f5-v2-image-set/1"
TRANSPORT_SCHEMA = "gh.n3w-t1-f5-v2-transport-contract/1"

F3_PAYLOAD_FILES = frozenset(
    {
        "runtime-payload.tar.gz",
        "runtime-payload.sha256",
        "payload-manifest.sha256",
        "capacity-contract.json",
        "capacity-contract.sha256",
        "executor.sha256",
        "host-wrapper.py",
        "host-wrapper.sha256",
        "host-baseline.py",
        "host-baseline.sha256",
    }
)
F3_IMAGE_FILES = frozenset(
    {
        "broker-arm64.tar",
        "greenhouse-manager-arm64.tar",
        "homeassistant-arm64.tar",
        "image-set.json",
    }
)
MAC_TOOL_FILES = (
    "tools/n3w_t1_device_provisioning_host.py",
    "tools/n3w_t1_f4_activation_host.py",
    "tools/n3w_t1_f4_certificate_runtime_guard.py",
    "tools/n3w_t1_f4_reboot_authority.py",
    "tools/n3w_t1_f4_reboot_verify.py",
    "tools/n3w_t1_failure_forensics.py",
    "tools/n3w_t1_fresh_armbian_qualification.py",
    "tools/n3w_t1_fresh_host_baseline.py",
    "tools/n3w_t1_fresh_product_bootstrap.py",
    "tools/n3w_t1_fresh_product_staging_host.py",
    "tools/n3w_t1_post_reboot_acceptance.py",
    "tools/n3w_t1_production_marker.py",
    "tools/n3w_t1_production_v2.py",
    "tools/n3w_t1_production_v2_contract.py",
    "tools/n3w_t1_production_v2_executor.py",
    "tools/n3w_t1_f5_v2_release_builder.py",
    "tools/n3w_t1_ssh_transport.py",
)


class ReleaseBuildError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repository), *args),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ReleaseBuildError("git_source_query_failed")
    return completed.stdout.strip()


def _verify_source(
    repository: Path,
    source_head: str,
    source_tree: str,
    *,
    production_authority: bool,
) -> None:
    if GIT_SHA_RE.fullmatch(source_head) is None:
        raise ReleaseBuildError("source_head_invalid")
    if GIT_SHA_RE.fullmatch(source_tree) is None:
        raise ReleaseBuildError("source_tree_invalid")
    if _git(repository, "rev-parse", "HEAD") != source_head:
        raise ReleaseBuildError("source_head_not_exact_checkout")
    if _git(repository, "rev-parse", "HEAD^{tree}") != source_tree:
        raise ReleaseBuildError("source_tree_not_exact_checkout")
    if production_authority:
        if _git(repository, "rev-parse", "origin/main") != source_head:
            raise ReleaseBuildError("production_source_not_exact_merged_main")


def _load_inputs(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReleaseBuildError("release_inputs_invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseBuildError("release_inputs_json_invalid") from error
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "source_head",
        "source_tree",
        "os_contract",
        "packages",
        "apt_source_policy",
        "artifacts",
        "capacity",
        "public_evidence_fields",
    }:
        raise ReleaseBuildError("release_inputs_keys_invalid")
    if value.get("schema") != INPUT_SCHEMA:
        raise ReleaseBuildError("release_inputs_schema_invalid")
    if GIT_SHA_RE.fullmatch(str(value.get("source_head", ""))) is None:
        raise ReleaseBuildError("release_inputs_source_head_invalid")
    if GIT_SHA_RE.fullmatch(str(value.get("source_tree", ""))) is None:
        raise ReleaseBuildError("release_inputs_source_tree_invalid")
    artifacts = value.get("artifacts")
    if (
        not isinstance(artifacts, dict)
        or set(artifacts) != set(REQUIRED_RELEASE_ARTIFACTS)
    ):
        raise ReleaseBuildError("release_inputs_artifact_set_invalid")
    for name in sorted(REQUIRED_RELEASE_ARTIFACTS):
        record = artifacts.get(name)
        if not isinstance(record, dict) or set(record) != {
            "path",
            "sha256",
            "size_bytes",
        }:
            raise ReleaseBuildError(f"release_inputs_artifact_record_invalid:{name}")
        if record.get("path") != RELEASE_INPUT_ARTIFACT_PATHS[name]:
            raise ReleaseBuildError(f"release_inputs_artifact_path_invalid:{name}")
        if SHA256_RE.fullmatch(str(record.get("sha256", ""))) is None:
            raise ReleaseBuildError(f"release_inputs_artifact_sha256_invalid:{name}")
        size = record.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ReleaseBuildError(f"release_inputs_artifact_size_invalid:{name}")
    return value


def _artifact_source(
    root: Path,
    record: dict[str, Any],
    name: str,
) -> Path:
    relative = record["path"]
    if relative != RELEASE_INPUT_ARTIFACT_PATHS[name]:
        raise ReleaseBuildError(f"artifact_path_invalid:{name}")
    unresolved = root / relative
    current = unresolved
    while current != root:
        if current.is_symlink():
            raise ReleaseBuildError(f"artifact_source_symlink:{name}")
        current = current.parent
    candidate = unresolved.resolve()
    root_resolved = root.resolve()
    if candidate == root_resolved or root_resolved not in candidate.parents:
        raise ReleaseBuildError(f"artifact_path_escape:{name}")
    if not candidate.is_file():
        raise ReleaseBuildError(f"artifact_source_invalid:{name}")
    if (
        candidate.stat().st_size != record["size_bytes"]
        or _sha256(candidate) != record["sha256"]
    ):
        raise ReleaseBuildError(f"artifact_input_binding_mismatch:{name}")
    return candidate


def build_release(
    repository: Path,
    inputs_path: Path,
    destination: Path,
    *,
    source_head: str,
    source_tree: str,
    production_authority: bool = False,
) -> dict[str, Any]:
    repository = repository.resolve()
    _verify_source(
        repository,
        source_head,
        source_tree,
        production_authority=production_authority,
    )
    if destination.exists() or destination.is_symlink():
        raise ReleaseBuildError("destination_already_exists")
    inputs = _load_inputs(inputs_path)
    if inputs["source_head"] != source_head:
        raise ReleaseBuildError("release_inputs_source_head_mismatch")
    if inputs["source_tree"] != source_tree:
        raise ReleaseBuildError("release_inputs_source_tree_mismatch")
    input_root = inputs_path.parent
    if input_root.is_symlink() or not input_root.is_dir():
        raise ReleaseBuildError("release_inputs_root_invalid")

    destination.mkdir(parents=True, mode=0o700)
    artifacts_dir = destination / ARTIFACT_DIR
    artifacts_dir.mkdir(mode=0o700)
    records: dict[str, dict[str, Any]] = {}
    try:
        for name in sorted(inputs["artifacts"]):
            if not isinstance(name, str) or not name or "/" in name or "\\" in name:
                raise ReleaseBuildError("artifact_name_invalid")
            input_record = inputs["artifacts"][name]
            source = _artifact_source(input_root, input_record, name)
            target = artifacts_dir / name
            shutil.copyfile(source, target)
            if (
                target.stat().st_size != input_record["size_bytes"]
                or _sha256(target) != input_record["sha256"]
            ):
                raise ReleaseBuildError(f"artifact_copy_binding_mismatch:{name}")
            records[name] = {
                "sha256": input_record["sha256"],
                "size_bytes": input_record["size_bytes"],
            }

        material = {
            "schema": RELEASE_SCHEMA,
            "source_head": source_head,
            "source_tree": source_tree,
            "os_contract": inputs["os_contract"],
            "packages": inputs["packages"],
            "apt_source_policy": inputs["apt_source_policy"],
            "artifacts": records,
            "capacity": inputs["capacity"],
            "public_evidence_fields": inputs["public_evidence_fields"],
        }
        release_id = canonical_sha256(material)
        release = validate_release({"release_id": release_id, **material})
        manifest = destination / MANIFEST_NAME
        manifest.write_bytes(canonical_json_bytes(release))
        release_sha256 = _sha256(manifest)
        (destination / SHA_NAME).write_text(
            release_sha256 + "\n",
            encoding="ascii",
        )
        verify_release_directory(destination)
        return {
            "status": "PASS",
            "release_id": release_id,
            "release_sha256": release_sha256,
            "source_head": source_head,
            "source_tree": source_tree,
            "artifact_count": len(records),
            "production_authority": production_authority,
            "secret_values_included": False,
            "board_access": False,
        }
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def verify_release_directory(destination: Path) -> dict[str, Any]:
    if destination.is_symlink() or not destination.is_dir():
        raise ReleaseBuildError("release_directory_invalid")
    if {item.name for item in destination.iterdir()} != {
        MANIFEST_NAME,
        SHA_NAME,
        ARTIFACT_DIR,
    }:
        raise ReleaseBuildError("release_root_set_invalid")

    manifest = destination / MANIFEST_NAME
    sidecar = destination / SHA_NAME
    if (
        manifest.is_symlink()
        or not manifest.is_file()
        or sidecar.is_symlink()
        or not sidecar.is_file()
    ):
        raise ReleaseBuildError("release_manifest_missing")
    try:
        raw_release = json.loads(manifest.read_text(encoding="utf-8"))
        release = validate_release(raw_release)
    except Exception as error:
        raise ReleaseBuildError("release_manifest_invalid") from error
    if manifest.read_bytes() != canonical_json_bytes(release):
        raise ReleaseBuildError("release_manifest_not_canonical")

    lines = sidecar.read_text(encoding="ascii").strip().splitlines()
    if len(lines) != 1 or SHA256_RE.fullmatch(lines[0]) is None:
        raise ReleaseBuildError("release_manifest_sidecar_invalid")
    expected_sha = lines[0]
    if expected_sha != _sha256(manifest):
        raise ReleaseBuildError("release_manifest_sha256_mismatch")

    artifacts_dir = destination / ARTIFACT_DIR
    if artifacts_dir.is_symlink() or not artifacts_dir.is_dir():
        raise ReleaseBuildError("release_artifact_directory_invalid")
    if {path.name for path in artifacts_dir.iterdir()} != set(REQUIRED_RELEASE_ARTIFACTS):
        raise ReleaseBuildError("release_artifact_set_invalid")
    for name in sorted(REQUIRED_RELEASE_ARTIFACTS):
        record = release["artifacts"][name]
        path = artifacts_dir / name
        if path.is_symlink() or not path.is_file():
            raise ReleaseBuildError(f"release_artifact_invalid:{name}")
        if (
            path.stat().st_size != record["size_bytes"]
            or _sha256(path) != record["sha256"]
        ):
            raise ReleaseBuildError(f"release_artifact_binding_invalid:{name}")
    return {
        "status": "PASS",
        "release_id": release["release_id"],
        "release_sha256": expected_sha,
        "source_head": release["source_head"],
        "source_tree": release["source_tree"],
        "artifact_count": len(release["artifacts"]),
        "secret_values_included": False,
        "board_access": False,
    }


def _normalize_archive_name(value: str, error_code: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise ReleaseBuildError(error_code)
    if value.startswith("/"):
        raise ReleaseBuildError(error_code)
    normalized = value
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in {"", "."}:
        return ""
    path = PurePosixPath(normalized)
    if (
        any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != normalized
    ):
        raise ReleaseBuildError(error_code)
    return normalized


def _expected_parent_directories(names: set[str]) -> set[str]:
    directories: set[str] = set()
    for name in names:
        parent = PurePosixPath(name).parent
        while parent.as_posix() != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _scan_tar(
    archive: Path,
    error_code: str,
) -> tuple[dict[str, str], set[str]]:
    if archive.is_symlink() or not archive.is_file():
        raise ReleaseBuildError(error_code)
    regular: dict[str, str] = {}
    directories: set[str] = set()
    seen: set[str] = set()
    try:
        with tarfile.open(archive, "r:*") as bundle:
            for member in bundle.getmembers():
                normalized = _normalize_archive_name(member.name, error_code)
                if not normalized:
                    if member.isdir():
                        continue
                    raise ReleaseBuildError(error_code)
                if normalized in seen:
                    raise ReleaseBuildError(error_code)
                seen.add(normalized)
                if member.issym() or member.islnk():
                    raise ReleaseBuildError(error_code)
                if member.isdir():
                    directories.add(normalized)
                elif member.isfile():
                    regular[normalized] = member.name
                else:
                    raise ReleaseBuildError(error_code)
    except tarfile.TarError as error:
        raise ReleaseBuildError(error_code) from error
    return regular, directories


def _tar_member_bytes(
    archive: Path,
    original_name: str,
    error_code: str,
    *,
    maximum: int = 4 * 1024 * 1024,
) -> bytes:
    try:
        with tarfile.open(archive, "r:*") as bundle:
            member = bundle.getmember(original_name)
            if not member.isfile() or member.size > maximum:
                raise ReleaseBuildError(error_code)
            stream = bundle.extractfile(member)
            if stream is None:
                raise ReleaseBuildError(error_code)
            return stream.read()
    except (KeyError, tarfile.TarError) as error:
        raise ReleaseBuildError(error_code) from error


def _tar_member_sha256(
    archive: Path,
    original_name: str,
    error_code: str,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    try:
        with tarfile.open(archive, "r:*") as bundle:
            member = bundle.getmember(original_name)
            if not member.isfile():
                raise ReleaseBuildError(error_code)
            stream = bundle.extractfile(member)
            if stream is None:
                raise ReleaseBuildError(error_code)
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            return digest.hexdigest(), member.size
    except (KeyError, tarfile.TarError) as error:
        raise ReleaseBuildError(error_code) from error


def _verify_exact_tar_file_set(
    archive: Path,
    expected_files: set[str],
    error_code: str,
    *,
    expected_directories: set[str] | None = None,
) -> dict[str, str]:
    regular, directories = _scan_tar(archive, error_code)
    if set(regular) != expected_files:
        raise ReleaseBuildError(f"{error_code}_file_set")
    if directories != (expected_directories or set()):
        raise ReleaseBuildError(f"{error_code}_directory_set")
    return regular


def _verify_nested_control_archive(
    archive: Path,
    *,
    source_head: str,
    root_name: str,
    manifest_name: str,
    schema: str,
    reboot: bool,
) -> None:
    error_prefix = "local_reboot_control" if reboot else "local_f4_control"
    regular, directories = _scan_tar(archive, f"{error_prefix}_member_invalid")
    manifest_member = f"{root_name}/{manifest_name}"
    original = regular.get(manifest_member)
    if original is None:
        raise ReleaseBuildError(f"{error_prefix}_manifest_missing")
    try:
        manifest = json.loads(
            _tar_member_bytes(
                archive,
                original,
                f"{error_prefix}_manifest_invalid",
            ).decode("utf-8")
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseBuildError(f"{error_prefix}_manifest_invalid") from error
    if not isinstance(manifest, dict):
        raise ReleaseBuildError(f"{error_prefix}_manifest_invalid")
    if reboot:
        expected_keys = {
            "schema",
            "source_head",
            "files",
            "secret_values_included",
            "live_runtime_mutation",
            "reboot_executed",
            "board_access",
        }
        boundary = {
            "secret_values_included": False,
            "live_runtime_mutation": False,
            "reboot_executed": False,
            "board_access": False,
        }
    else:
        expected_keys = {
            "schema",
            "source_head",
            "files",
            "secret_values_included",
            "production_service_start",
            "board_access",
        }
        boundary = {
            "secret_values_included": False,
            "production_service_start": False,
            "board_access": False,
        }
    if set(manifest) != expected_keys:
        raise ReleaseBuildError(f"{error_prefix}_manifest_keys_invalid")
    if manifest.get("schema") != schema or manifest.get("source_head") != source_head:
        raise ReleaseBuildError(f"{error_prefix}_manifest_binding_invalid")
    for key, expected in boundary.items():
        if manifest.get(key) is not expected:
            raise ReleaseBuildError(f"{error_prefix}_boundary_invalid")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise ReleaseBuildError(f"{error_prefix}_files_invalid")
    expected_regular = {manifest_member}
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"path", "sha256", "size"}:
            raise ReleaseBuildError(f"{error_prefix}_record_invalid")
        relative = _normalize_archive_name(
            str(record.get("path", "")),
            f"{error_prefix}_path_invalid",
        )
        if not relative or relative in seen:
            raise ReleaseBuildError(f"{error_prefix}_path_invalid")
        seen.add(relative)
        digest = record.get("sha256")
        size = record.get("size")
        if SHA256_RE.fullmatch(str(digest or "")) is None:
            raise ReleaseBuildError(f"{error_prefix}_sha256_invalid")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ReleaseBuildError(f"{error_prefix}_size_invalid")
        member_name = f"{root_name}/{relative}"
        member_original = regular.get(member_name)
        if member_original is None:
            raise ReleaseBuildError(f"{error_prefix}_file_missing")
        actual_sha, actual_size = _tar_member_sha256(
            archive,
            member_original,
            f"{error_prefix}_file_unreadable",
        )
        if actual_size != size or actual_sha != digest:
            raise ReleaseBuildError(f"{error_prefix}_file_binding_invalid")
        expected_regular.add(member_name)
    if set(regular) != expected_regular:
        raise ReleaseBuildError(f"{error_prefix}_file_set_invalid")
    if directories != _expected_parent_directories(expected_regular):
        raise ReleaseBuildError(f"{error_prefix}_directory_set_invalid")


def _verify_mac_tools_archive(
    repository: Path,
    archive: Path,
    source_head: str,
) -> None:
    expected_regular = {"manifest.json", *MAC_TOOL_FILES}
    regular = _verify_exact_tar_file_set(
        archive,
        set(expected_regular),
        "local_mac_tools_member_invalid",
    )
    manifest_original = regular["manifest.json"]
    try:
        manifest = json.loads(
            _tar_member_bytes(
                archive,
                manifest_original,
                "local_mac_tools_manifest_invalid",
            ).decode("utf-8")
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseBuildError("local_mac_tools_manifest_invalid") from error
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"schema", "source_head", "files"}
        or manifest.get("schema") != MAC_TOOLS_SCHEMA
        or manifest.get("source_head") != source_head
    ):
        raise ReleaseBuildError("local_mac_tools_manifest_invalid")
    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != len(MAC_TOOL_FILES):
        raise ReleaseBuildError("local_mac_tools_record_set_invalid")
    by_path: dict[str, dict[str, Any]] = {}
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "sha256", "size_bytes"}
            or record.get("path") in by_path
        ):
            raise ReleaseBuildError("local_mac_tools_record_invalid")
        by_path[str(record["path"])] = record
    if set(by_path) != set(MAC_TOOL_FILES):
        raise ReleaseBuildError("local_mac_tools_record_set_invalid")
    for relative in MAC_TOOL_FILES:
        record = by_path[relative]
        if SHA256_RE.fullmatch(str(record.get("sha256", ""))) is None:
            raise ReleaseBuildError("local_mac_tools_record_invalid")
        size = record.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ReleaseBuildError("local_mac_tools_record_invalid")
        member_sha, member_size = _tar_member_sha256(
            archive,
            regular[relative],
            "local_mac_tools_member_unreadable",
        )
        source = repository / relative
        if source.is_symlink() or not source.is_file():
            raise ReleaseBuildError("local_mac_tools_repository_source_invalid")
        if (
            member_sha != record["sha256"]
            or member_size != size
            or source.stat().st_size != size
            or _sha256(source) != record["sha256"]
        ):
            raise ReleaseBuildError("local_mac_tools_source_binding_mismatch")


def _safe_extract_final_artifact_zip(
    archive: Path,
    destination: Path,
) -> None:
    if archive.is_symlink() or not archive.is_file():
        raise ReleaseBuildError("local_artifact_zip_invalid")
    try:
        with zipfile.ZipFile(archive) as bundle:
            infos = bundle.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)) or set(names) != set(FINAL_OUTER_FILES):
                raise ReleaseBuildError("local_artifact_zip_file_set_invalid")
            for item in infos:
                normalized = _normalize_archive_name(
                    item.filename,
                    "local_artifact_zip_member_invalid",
                )
                mode = (item.external_attr >> 16) & 0o170000
                if (
                    normalized != item.filename
                    or "/" in normalized
                    or item.is_dir()
                    or mode == 0o120000
                ):
                    raise ReleaseBuildError("local_artifact_zip_member_invalid")
                target = destination / normalized
                if target.exists() or target.is_symlink():
                    raise ReleaseBuildError("local_artifact_zip_collision")
                with bundle.open(item) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
    except zipfile.BadZipFile as error:
        raise ReleaseBuildError("local_artifact_zip_invalid") from error


def _safe_extract_release_tar(
    archive: Path,
    destination: Path,
) -> Path:
    regular, directories = _scan_tar(archive, "local_release_tar_member_invalid")
    expected_regular = {
        f"{RELEASE_ROOT_NAME}/{MANIFEST_NAME}",
        f"{RELEASE_ROOT_NAME}/{SHA_NAME}",
        *{
            f"{RELEASE_ROOT_NAME}/{ARTIFACT_DIR}/{name}"
            for name in REQUIRED_RELEASE_ARTIFACTS
        },
    }
    if set(regular) != expected_regular:
        raise ReleaseBuildError("local_release_tar_file_set_invalid")
    if directories != _expected_parent_directories(expected_regular):
        raise ReleaseBuildError("local_release_tar_directory_set_invalid")

    release_root = destination / RELEASE_ROOT_NAME
    artifacts_root = release_root / ARTIFACT_DIR
    artifacts_root.mkdir(parents=True, mode=0o700)
    try:
        with tarfile.open(archive, "r:*") as bundle:
            for normalized, original in regular.items():
                member = bundle.getmember(original)
                stream = bundle.extractfile(member)
                if stream is None:
                    raise ReleaseBuildError("local_release_tar_member_unreadable")
                relative = PurePosixPath(normalized).relative_to(RELEASE_ROOT_NAME)
                target = release_root.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink():
                    raise ReleaseBuildError("local_release_tar_collision")
                with target.open("xb") as output:
                    shutil.copyfileobj(stream, output, length=1024 * 1024)
    except tarfile.TarError as error:
        raise ReleaseBuildError("local_release_tar_invalid") from error
    return release_root


def _parse_sha_sidecar(path: Path, error_code: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise ReleaseBuildError(error_code)
    lines = path.read_text(encoding="ascii").strip().splitlines()
    if len(lines) != 1:
        raise ReleaseBuildError(error_code)
    fields = lines[0].split()
    if not fields or SHA256_RE.fullmatch(fields[0]) is None:
        raise ReleaseBuildError(error_code)
    return fields[0]


def verify_release_bundle(
    repository: Path,
    artifact_zip: Path,
    *,
    expected_artifact_sha256: str,
    artifact_name: str,
    artifact_id: int,
    run_id: int,
    run_attempt: int,
    source_head: str,
    source_tree: str,
    binding_json: Path | None = None,
) -> dict[str, Any]:
    repository = repository.resolve()
    _verify_source(
        repository,
        source_head,
        source_tree,
        production_authority=True,
    )
    if SHA256_RE.fullmatch(expected_artifact_sha256) is None:
        raise ReleaseBuildError("local_artifact_digest_invalid")
    if artifact_name != FINAL_ARTIFACT_NAME_PREFIX + source_head:
        raise ReleaseBuildError("local_artifact_name_invalid")
    if (
        not isinstance(artifact_id, int)
        or artifact_id <= 0
        or not isinstance(run_id, int)
        or run_id <= 0
        or not isinstance(run_attempt, int)
        or run_attempt <= 0
    ):
        raise ReleaseBuildError("local_artifact_identity_invalid")
    if _sha256(artifact_zip) != expected_artifact_sha256:
        raise ReleaseBuildError("local_artifact_zip_sha256_mismatch")

    with tempfile.TemporaryDirectory(prefix="n3w-f5-v2-local-release-") as temp:
        root = Path(temp)
        outer = root / "outer"
        outer.mkdir(mode=0o700)
        _safe_extract_final_artifact_zip(artifact_zip, outer)
        release_tar = outer / FINAL_TAR_NAME
        if _sha256(release_tar) != _parse_sha_sidecar(
            outer / FINAL_TAR_SHA_NAME,
            "local_release_tar_sidecar_invalid",
        ):
            raise ReleaseBuildError("local_release_tar_sha256_mismatch")

        extracted = root / "release"
        extracted.mkdir(mode=0o700)
        release_root = _safe_extract_release_tar(release_tar, extracted)
        verified = verify_release_directory(release_root)
        if (
            verified["source_head"] != source_head
            or verified["source_tree"] != source_tree
        ):
            raise ReleaseBuildError("local_release_source_binding_mismatch")

        artifacts = release_root / ARTIFACT_DIR
        _verify_exact_tar_file_set(
            artifacts / "f3_payload",
            set(F3_PAYLOAD_FILES),
            "local_f3_payload_member_invalid",
        )
        _verify_exact_tar_file_set(
            artifacts / "f3_image",
            set(F3_IMAGE_FILES),
            "local_f3_image_member_invalid",
        )
        _verify_nested_control_archive(
            artifacts / "f4_control",
            source_head=source_head,
            root_name="f4-package",
            manifest_name="f4-package-manifest.json",
            schema=F4_PACKAGE_SCHEMA,
            reboot=False,
        )
        _verify_nested_control_archive(
            artifacts / "reboot_control",
            source_head=source_head,
            root_name="reboot-successor-control",
            manifest_name="reboot-successor-manifest.json",
            schema=REBOOT_PACKAGE_SCHEMA,
            reboot=True,
        )
        _verify_mac_tools_archive(
            repository,
            artifacts / "v2_mac_tools",
            source_head,
        )
        transport_path = artifacts / "transport_contract"
        try:
            transport = json.loads(transport_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ReleaseBuildError("local_transport_contract_invalid") from error
        if (
            not isinstance(transport, dict)
            or set(transport) != {"schema", "source_head", "transport", "capacity"}
            or transport.get("schema") != TRANSPORT_SCHEMA
            or transport.get("source_head") != source_head
        ):
            raise ReleaseBuildError("local_transport_contract_invalid")

        binding = {
            "schema": LOCAL_BINDING_SCHEMA,
            "repository": "chrenguo-stack/HomeAssistant",
            "workflow_path": ".github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml",
            "run_id": run_id,
            "run_attempt": run_attempt,
            "artifact_id": artifact_id,
            "artifact_name": artifact_name,
            "artifact_zip_sha256": expected_artifact_sha256,
            "release_id": verified["release_id"],
            "release_sha256": verified["release_sha256"],
            "source_head": source_head,
            "source_tree": source_tree,
        }

    if binding_json is not None:
        if binding_json.exists() or binding_json.is_symlink():
            raise ReleaseBuildError("local_binding_destination_exists")
        parent = binding_json.parent
        if parent.is_symlink() or not parent.is_dir():
            raise ReleaseBuildError("local_binding_parent_invalid")
        binding_json.write_bytes(canonical_json_bytes(binding))

    return {
        "status": "PASS",
        **binding,
        "secret_values_included": False,
        "t1_access": False,
        "board_access": False,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--repository", type=Path, default=Path.cwd())
    build.add_argument("--inputs-json", type=Path, required=True)
    build.add_argument("--destination", type=Path, required=True)
    build.add_argument("--source-head", required=True)
    build.add_argument("--source-tree", required=True)
    build.add_argument("--production-authority", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("--destination", type=Path, required=True)
    verify_bundle = commands.add_parser("verify-bundle")
    verify_bundle.add_argument("--repository", type=Path, default=Path.cwd())
    verify_bundle.add_argument("--artifact-zip", type=Path, required=True)
    verify_bundle.add_argument("--expected-artifact-sha256", required=True)
    verify_bundle.add_argument("--artifact-name", required=True)
    verify_bundle.add_argument("--artifact-id", type=int, required=True)
    verify_bundle.add_argument("--run-id", type=int, required=True)
    verify_bundle.add_argument("--run-attempt", type=int, required=True)
    verify_bundle.add_argument("--source-head", required=True)
    verify_bundle.add_argument("--source-tree", required=True)
    verify_bundle.add_argument("--binding-json", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "build":
            report = build_release(
                args.repository,
                args.inputs_json,
                args.destination,
                source_head=args.source_head,
                source_tree=args.source_tree,
                production_authority=args.production_authority,
            )
        elif args.command == "verify":
            report = verify_release_directory(args.destination)
        else:
            report = verify_release_bundle(
                args.repository,
                args.artifact_zip,
                expected_artifact_sha256=args.expected_artifact_sha256,
                artifact_name=args.artifact_name,
                artifact_id=args.artifact_id,
                run_id=args.run_id,
                run_attempt=args.run_attempt,
                source_head=args.source_head,
                source_tree=args.source_tree,
                binding_json=args.binding_json,
            )
    except (OSError, ReleaseBuildError, RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": str(error)[:300],
                    "production_authority": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
