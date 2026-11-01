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
from pathlib import Path, PurePosixPath
from typing import Any

from n3w_t1_production_v2_contract import (
    RELEASE_INPUT_ARTIFACT_PATHS,
    REQUIRED_RELEASE_ARTIFACTS,
    RELEASE_SCHEMA,
    canonical_json_bytes,
    canonical_sha256,
    validate_release,
)

INPUT_SCHEMA = "gh.n3w-t1-production-v2-release-inputs/1"
PROFILE_SCHEMA = "gh.n3w-t1-production-v2-release-profile/1"
TRANSPORT_SCHEMA = "gh.n3w-t1-f5-v2-transport-contract/1"
MAC_TOOLS_SCHEMA = "gh.n3w-t1-f5-v2-mac-tools/1"
IMAGE_SET_SCHEMA = "gh.n3w-t1-f5-v2-image-set/1"
F4_PACKAGE_SCHEMA = "gh.n3w-t1-f4-activation-package/1"
REBOOT_PACKAGE_SCHEMA = "gh.n3w-t1-f4-reboot-successor-control-package/1"
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")

F3_FILES = frozenset(
    {
        "runtime-payload.tar.gz",
        "runtime-payload.sha256",
        "payload-manifest.sha256",
        "capacity-contract.json",
        "capacity-contract.sha256",
        "homeassistant-arm64.tar",
        "greenhouse-manager-arm64.tar",
        "broker-arm64.tar",
        "executor.sha256",
        "host-wrapper.py",
        "host-wrapper.sha256",
        "host-baseline.py",
        "host-baseline.sha256",
    }
)
F3_IMAGE_FILES = (
    "broker-arm64.tar",
    "greenhouse-manager-arm64.tar",
    "homeassistant-arm64.tar",
)
F3_PAYLOAD_FILES = tuple(sorted(F3_FILES.difference(F3_IMAGE_FILES)))
F4_FILES = frozenset(
    {
        "n3w-t1-f4-control-package.tar",
        "n3w-t1-f4-control-package.tar.sha256",
        "build-report.json",
    }
)
REBOOT_FILES = frozenset(
    {
        "n3w-t1-f4-reboot-successor-control.tar",
        "n3w-t1-f4-reboot-successor-control.tar.sha256",
        "reboot-successor-build-report.json",
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


class ReleaseInputsBuildError(RuntimeError):
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
        raise ReleaseInputsBuildError("git_source_query_failed")
    return completed.stdout.strip()


def _regular(path: Path, error_code: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ReleaseInputsBuildError(error_code)
    return path


def _directory(path: Path, error_code: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise ReleaseInputsBuildError(error_code)
    return path


def _read_json(path: Path, error_code: str) -> dict[str, Any]:
    _regular(path, error_code)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseInputsBuildError(error_code) from error
    if not isinstance(value, dict):
        raise ReleaseInputsBuildError(error_code)
    return value


def _sidecar(path: Path, error_code: str) -> str:
    _regular(path, error_code)
    lines = path.read_text(encoding="ascii").strip().splitlines()
    if len(lines) != 1:
        raise ReleaseInputsBuildError(error_code)
    fields = lines[0].split()
    if not fields or len(fields) > 2 or SHA256_RE.fullmatch(fields[0]) is None:
        raise ReleaseInputsBuildError(error_code)
    return fields[0]


def _verify_source(
    repository: Path,
    source_head: str,
    source_tree: str,
    *,
    production_authority: bool,
) -> None:
    if GIT_SHA_RE.fullmatch(source_head) is None:
        raise ReleaseInputsBuildError("source_head_invalid")
    if GIT_SHA_RE.fullmatch(source_tree) is None:
        raise ReleaseInputsBuildError("source_tree_invalid")
    if _git(repository, "rev-parse", "HEAD") != source_head:
        raise ReleaseInputsBuildError("source_head_not_exact_checkout")
    if _git(repository, "rev-parse", "HEAD^{tree}") != source_tree:
        raise ReleaseInputsBuildError("source_tree_not_exact_checkout")
    if production_authority and _git(repository, "rev-parse", "origin/main") != source_head:
        raise ReleaseInputsBuildError("production_source_not_exact_merged_main")


def _exact_directory_set(root: Path, expected: frozenset[str], error_code: str) -> None:
    _directory(root, error_code)
    actual = {item.name for item in root.iterdir()}
    if actual != expected:
        raise ReleaseInputsBuildError(error_code)
    for item in root.iterdir():
        _regular(item, error_code)


def _normalize_tar_name(value: str, error_code: str) -> str:
    if not isinstance(value, str) or not value or "\\x00" in value or "\\" in value:
        raise ReleaseInputsBuildError(error_code)
    if value.startswith("/"):
        raise ReleaseInputsBuildError(error_code)
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
        raise ReleaseInputsBuildError(error_code)
    return normalized


def _tar_member_bytes(path: Path, member_name: str, error_code: str) -> bytes:
    _regular(path, error_code)
    matches: list[bytes] = []
    try:
        with tarfile.open(path, "r:*") as bundle:
            for member in bundle.getmembers():
                normalized = _normalize_tar_name(member.name, error_code)
                if not normalized:
                    if member.isdir():
                        continue
                    raise ReleaseInputsBuildError(error_code)
                if member.issym() or member.islnk():
                    raise ReleaseInputsBuildError(error_code)
                if not member.isfile() and not member.isdir():
                    raise ReleaseInputsBuildError(error_code)
                if member.isfile() and normalized == member_name:
                    stream = bundle.extractfile(member)
                    if stream is None:
                        raise ReleaseInputsBuildError(error_code)
                    matches.append(stream.read())
    except tarfile.TarError as error:
        raise ReleaseInputsBuildError(error_code) from error
    if len(matches) != 1:
        raise ReleaseInputsBuildError(error_code)
    return matches[0]


def _tar_json_member(path: Path, member_name: str, error_code: str) -> dict[str, Any]:
    try:
        value = json.loads(
            _tar_member_bytes(path, member_name, error_code).decode("utf-8")
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseInputsBuildError(error_code) from error
    if not isinstance(value, dict):
        raise ReleaseInputsBuildError(error_code)
    return value


def _tar_index(
    path: Path,
    error_code: str,
) -> tuple[dict[str, bytes], set[str]]:
    _regular(path, error_code)
    regular: dict[str, bytes] = {}
    directories: set[str] = set()
    seen: set[str] = set()
    try:
        with tarfile.open(path, "r:*") as bundle:
            for member in bundle.getmembers():
                normalized = _normalize_tar_name(member.name, error_code)
                if not normalized:
                    if member.isdir():
                        continue
                    raise ReleaseInputsBuildError(error_code)
                if normalized in seen:
                    raise ReleaseInputsBuildError(error_code)
                seen.add(normalized)
                if member.issym() or member.islnk():
                    raise ReleaseInputsBuildError(error_code)
                if member.isdir():
                    directories.add(normalized)
                    continue
                if not member.isfile():
                    raise ReleaseInputsBuildError(error_code)
                stream = bundle.extractfile(member)
                if stream is None:
                    raise ReleaseInputsBuildError(error_code)
                regular[normalized] = stream.read()
    except tarfile.TarError as error:
        raise ReleaseInputsBuildError(error_code) from error
    return regular, directories


def _expected_parent_directories(names: set[str]) -> set[str]:
    directories: set[str] = set()
    for name in names:
        parent = PurePosixPath(name).parent
        while parent.as_posix() != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _load_profile(path: Path) -> dict[str, Any]:
    value = _read_json(path, "release_profile_invalid")
    if set(value) != {
        "schema",
        "os_contract",
        "packages",
        "apt_source_policy",
        "public_evidence_fields",
    }:
        raise ReleaseInputsBuildError("release_profile_keys_invalid")
    if value["schema"] != PROFILE_SCHEMA:
        raise ReleaseInputsBuildError("release_profile_schema_invalid")
    return value


def _verify_f3(root: Path, source_head: str) -> tuple[dict[str, Any], dict[str, Any]]:
    _exact_directory_set(root, F3_FILES, "f3_artifact_set_invalid")
    runtime = root / "runtime-payload.tar.gz"
    if _sha256(runtime) != _sidecar(
        root / "runtime-payload.sha256",
        "f3_runtime_sidecar_invalid",
    ):
        raise ReleaseInputsBuildError("f3_runtime_payload_sha256_mismatch")
    capacity_path = root / "capacity-contract.json"
    if _sha256(capacity_path) != _sidecar(
        root / "capacity-contract.sha256",
        "f3_capacity_sidecar_invalid",
    ):
        raise ReleaseInputsBuildError("f3_capacity_sha256_mismatch")
    manifest_bytes = _tar_member_bytes(
        runtime,
        "payload-manifest.json",
        "f3_payload_manifest_invalid",
    )
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseInputsBuildError("f3_payload_manifest_invalid") from error
    if not isinstance(manifest, dict):
        raise ReleaseInputsBuildError("f3_payload_manifest_invalid")
    if hashlib.sha256(manifest_bytes).hexdigest() != _sidecar(
        root / "payload-manifest.sha256",
        "f3_payload_manifest_sidecar_invalid",
    ):
        raise ReleaseInputsBuildError("f3_payload_manifest_sha256_mismatch")
    executor_bytes = _tar_member_bytes(
        runtime,
        "tools/n3w_t1_fresh_product_bootstrap.py",
        "f3_executor_invalid",
    )
    if hashlib.sha256(executor_bytes).hexdigest() != _sidecar(
        root / "executor.sha256",
        "f3_executor_sidecar_invalid",
    ):
        raise ReleaseInputsBuildError("f3_executor_sha256_mismatch")
    for name in ("host-wrapper.py", "host-baseline.py"):
        path = root / name
        sidecar = root / name.replace(".py", ".sha256")
        if _sha256(path) != _sidecar(sidecar, f"f3_{name}_sidecar_invalid"):
            raise ReleaseInputsBuildError(f"f3_{name}_sha256_mismatch")
    capacity = _read_json(capacity_path, "f3_capacity_contract_invalid")
    if manifest.get("source_head") != source_head:
        raise ReleaseInputsBuildError("f3_source_head_mismatch")
    if capacity.get("source_head") != source_head:
        raise ReleaseInputsBuildError("f3_capacity_source_head_mismatch")
    transport = manifest.get("transport")
    images = manifest.get("images")
    if not isinstance(transport, dict) or transport.get("schema") != "gh.n3w-t1-fresh-transport/2":
        raise ReleaseInputsBuildError("f3_transport_contract_invalid")
    if not isinstance(images, dict) or set(images) != {"manager", "broker", "homeassistant"}:
        raise ReleaseInputsBuildError("f3_image_contract_invalid")
    if capacity.get("schema") != "gh.n3w-t1-fresh-capacity/1":
        raise ReleaseInputsBuildError("f3_capacity_schema_invalid")
    if capacity.get("images") != transport.get("images"):
        raise ReleaseInputsBuildError("f3_capacity_transport_mismatch")
    if manifest.get("secret_values_included") is not False:
        raise ReleaseInputsBuildError("f3_secret_boundary_invalid")
    if manifest.get("production_service_start") is not False:
        raise ReleaseInputsBuildError("f3_service_start_boundary_invalid")
    if manifest.get("board_access") is not False:
        raise ReleaseInputsBuildError("f3_board_boundary_invalid")
    expected_image_files = set()
    for record in images.values():
        if not isinstance(record, dict):
            raise ReleaseInputsBuildError("f3_image_record_invalid")
        name = record.get("artifact_file")
        if name not in F3_IMAGE_FILES:
            raise ReleaseInputsBuildError("f3_image_file_invalid")
        expected_image_files.add(name)
        image_path = root / name
        if image_path.stat().st_size != record.get("tar_size_bytes"):
            raise ReleaseInputsBuildError("f3_image_size_mismatch")
        if _sha256(image_path) != record.get("tar_sha256"):
            raise ReleaseInputsBuildError("f3_image_sha256_mismatch")
    if expected_image_files != set(F3_IMAGE_FILES):
        raise ReleaseInputsBuildError("f3_image_set_invalid")
    return manifest, capacity


def _verify_control(
    root: Path,
    source_head: str,
    *,
    expected_files: frozenset[str],
    tar_name: str,
    sidecar_name: str,
    report_name: str,
    manifest_member: str,
    error_prefix: str,
) -> None:
    _exact_directory_set(root, expected_files, f"{error_prefix}_artifact_set_invalid")
    archive = root / tar_name
    if _sha256(archive) != _sidecar(
        root / sidecar_name,
        f"{error_prefix}_sidecar_invalid",
    ):
        raise ReleaseInputsBuildError(f"{error_prefix}_tar_sha256_mismatch")

    report = _read_json(root / report_name, f"{error_prefix}_report_invalid")
    if error_prefix == "f4_control":
        expected_schema = F4_PACKAGE_SCHEMA
        report_keys = {
            "status",
            "source_head",
            "file_count",
            "manifest_sha256",
            "secret_values_included",
            "production_service_start",
            "board_access",
        }
        manifest_keys = {
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
    elif error_prefix == "reboot_control":
        expected_schema = REBOOT_PACKAGE_SCHEMA
        report_keys = {
            "status",
            "source_head",
            "manifest_sha256",
            "file_count",
            "secret_values_included",
            "live_runtime_mutation",
            "reboot_executed",
            "board_access",
        }
        manifest_keys = {
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
        raise ReleaseInputsBuildError(f"{error_prefix}_contract_unknown")

    if set(report) != report_keys:
        raise ReleaseInputsBuildError(f"{error_prefix}_report_keys_invalid")
    if report.get("status") != "PASS" or report.get("source_head") != source_head:
        raise ReleaseInputsBuildError(f"{error_prefix}_report_binding_invalid")
    if (
        not isinstance(report.get("file_count"), int)
        or isinstance(report.get("file_count"), bool)
        or report["file_count"] < 0
    ):
        raise ReleaseInputsBuildError(f"{error_prefix}_report_file_count_invalid")
    if SHA256_RE.fullmatch(str(report.get("manifest_sha256", ""))) is None:
        raise ReleaseInputsBuildError(f"{error_prefix}_report_manifest_sha256_invalid")
    for key, expected in boundary.items():
        if report.get(key) is not expected:
            raise ReleaseInputsBuildError(f"{error_prefix}_report_boundary_invalid")

    regular, directories = _tar_index(
        archive,
        f"{error_prefix}_tar_member_invalid",
    )
    manifest_bytes = regular.get(manifest_member)
    if manifest_bytes is None:
        raise ReleaseInputsBuildError(f"{error_prefix}_manifest_missing")
    if hashlib.sha256(manifest_bytes).hexdigest() != report["manifest_sha256"]:
        raise ReleaseInputsBuildError(f"{error_prefix}_manifest_sha256_mismatch")
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseInputsBuildError(f"{error_prefix}_manifest_invalid") from error
    if not isinstance(manifest, dict) or set(manifest) != manifest_keys:
        raise ReleaseInputsBuildError(f"{error_prefix}_manifest_keys_invalid")
    if (
        manifest.get("schema") != expected_schema
        or manifest.get("source_head") != source_head
    ):
        raise ReleaseInputsBuildError(f"{error_prefix}_manifest_binding_invalid")
    for key, expected in boundary.items():
        if manifest.get(key) is not expected:
            raise ReleaseInputsBuildError(f"{error_prefix}_manifest_boundary_invalid")

    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != report["file_count"]:
        raise ReleaseInputsBuildError(f"{error_prefix}_manifest_files_invalid")
    prefix = PurePosixPath(manifest_member).parent.as_posix()
    expected_regular = {manifest_member}
    seen_paths: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"path", "sha256", "size"}:
            raise ReleaseInputsBuildError(f"{error_prefix}_manifest_file_record_invalid")
        relative = _normalize_tar_name(
            str(record.get("path", "")),
            f"{error_prefix}_manifest_file_path_invalid",
        )
        if not relative or relative in seen_paths:
            raise ReleaseInputsBuildError(f"{error_prefix}_manifest_file_path_invalid")
        seen_paths.add(relative)
        digest = record.get("sha256")
        size = record.get("size")
        if SHA256_RE.fullmatch(str(digest or "")) is None:
            raise ReleaseInputsBuildError(f"{error_prefix}_manifest_file_sha256_invalid")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ReleaseInputsBuildError(f"{error_prefix}_manifest_file_size_invalid")
        member_name = f"{prefix}/{relative}"
        payload = regular.get(member_name)
        if payload is None:
            raise ReleaseInputsBuildError(f"{error_prefix}_manifest_file_missing")
        if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
            raise ReleaseInputsBuildError(f"{error_prefix}_manifest_file_binding_invalid")
        expected_regular.add(member_name)

    if set(regular) != expected_regular:
        raise ReleaseInputsBuildError(f"{error_prefix}_inner_file_set_invalid")
    if directories != _expected_parent_directories(expected_regular):
        raise ReleaseInputsBuildError(f"{error_prefix}_inner_member_set_invalid")


def _write_tar(
    destination: Path,
    entries: list[tuple[str, Path]],
    extra_json: tuple[str, dict[str, Any]] | None = None,
) -> None:
    with tarfile.open(destination, "w", format=tarfile.GNU_FORMAT) as bundle:
        if extra_json is not None:
            name, value = extra_json
            payload = canonical_json_bytes(value)
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            import io

            bundle.addfile(info, io.BytesIO(payload))
        for name, path in sorted(entries, key=lambda item: item[0]):
            _regular(path, "tar_source_invalid")
            info = tarfile.TarInfo(name)
            info.size = path.stat().st_size
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            with path.open("rb") as stream:
                bundle.addfile(info, stream)


def _materialize_mac_tools(
    repository: Path,
    destination: Path,
    source_head: str,
) -> None:
    records = []
    entries = []
    for relative in MAC_TOOL_FILES:
        path = repository / relative
        _regular(path, f"mac_tool_invalid:{relative}")
        records.append(
            {
                "path": relative,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
        entries.append((relative, path))
    manifest = {
        "schema": MAC_TOOLS_SCHEMA,
        "source_head": source_head,
        "files": records,
    }
    _write_tar(destination, entries, ("manifest.json", manifest))


def _build_material(
    profile: dict[str, Any],
    source_head: str,
    source_tree: str,
    artifact_records: dict[str, dict[str, Any]],
    capacity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": INPUT_SCHEMA,
        "source_head": source_head,
        "source_tree": source_tree,
        "os_contract": profile["os_contract"],
        "packages": profile["packages"],
        "apt_source_policy": profile["apt_source_policy"],
        "artifacts": artifact_records,
        "capacity": {
            "minimum_post_peak_free_bytes": capacity[
                "minimum_post_peak_free_bytes"
            ]
        },
        "public_evidence_fields": profile["public_evidence_fields"],
    }


def verify_inputs_directory(destination: Path) -> dict[str, Any]:
    _directory(destination, "release_inputs_directory_invalid")
    if {item.name for item in destination.iterdir()} != {
        "release-inputs.json",
        "artifacts",
    }:
        raise ReleaseInputsBuildError("release_inputs_root_set_invalid")

    document_path = destination / "release-inputs.json"
    document = _read_json(
        document_path,
        "release_inputs_json_invalid",
    )
    if document_path.read_bytes() != canonical_json_bytes(document):
        raise ReleaseInputsBuildError("release_inputs_json_not_canonical")
    if set(document) != {
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
        raise ReleaseInputsBuildError("release_inputs_keys_invalid")
    if document.get("schema") != INPUT_SCHEMA:
        raise ReleaseInputsBuildError("release_inputs_schema_invalid")

    artifacts = document.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(REQUIRED_RELEASE_ARTIFACTS):
        raise ReleaseInputsBuildError("release_inputs_artifact_set_invalid")

    artifact_root = destination / "artifacts"
    _directory(artifact_root, "release_inputs_artifact_directory_invalid")
    expected_names = {
        Path(relative).name for relative in RELEASE_INPUT_ARTIFACT_PATHS.values()
    }
    if {item.name for item in artifact_root.iterdir()} != expected_names:
        raise ReleaseInputsBuildError("release_inputs_physical_artifact_set_invalid")

    release_records: dict[str, dict[str, Any]] = {}
    for name in sorted(REQUIRED_RELEASE_ARTIFACTS):
        record = artifacts.get(name)
        if not isinstance(record, dict) or set(record) != {
            "path",
            "sha256",
            "size_bytes",
        }:
            raise ReleaseInputsBuildError(
                f"release_inputs_artifact_record_invalid:{name}"
            )
        relative = record.get("path")
        expected_relative = RELEASE_INPUT_ARTIFACT_PATHS[name]
        if relative != expected_relative:
            raise ReleaseInputsBuildError(
                f"release_inputs_artifact_path_invalid:{name}"
            )
        digest = record.get("sha256")
        size = record.get("size_bytes")
        if SHA256_RE.fullmatch(str(digest or "")) is None:
            raise ReleaseInputsBuildError(
                f"release_inputs_artifact_sha256_invalid:{name}"
            )
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ReleaseInputsBuildError(
                f"release_inputs_artifact_size_invalid:{name}"
            )

        unresolved = destination / expected_relative
        current = unresolved
        while current != destination:
            if current.is_symlink():
                raise ReleaseInputsBuildError(
                    f"release_inputs_artifact_symlink:{name}"
                )
            current = current.parent
        if not unresolved.is_file():
            raise ReleaseInputsBuildError(
                f"release_inputs_artifact_missing:{name}"
            )
        if unresolved.stat().st_size != size or _sha256(unresolved) != digest:
            raise ReleaseInputsBuildError(
                f"release_inputs_artifact_binding_mismatch:{name}"
            )
        release_records[name] = {
            "sha256": digest,
            "size_bytes": size,
        }

    material = {
        "schema": RELEASE_SCHEMA,
        "source_head": document["source_head"],
        "source_tree": document["source_tree"],
        "os_contract": document["os_contract"],
        "packages": document["packages"],
        "apt_source_policy": document["apt_source_policy"],
        "artifacts": release_records,
        "capacity": document["capacity"],
        "public_evidence_fields": document["public_evidence_fields"],
    }
    release_id = canonical_sha256(material)
    validate_release({"release_id": release_id, **material})
    return {
        "status": "PASS",
        "source_head": document["source_head"],
        "source_tree": document["source_tree"],
        "artifact_count": len(release_records),
        "release_input_sha256": _sha256(document_path),
        "component_binding_sha256": canonical_sha256(artifacts),
        "secret_values_included": False,
        "t1_access": False,
        "board_access": False,
    }


def build_inputs(
    repository: Path,
    profile_path: Path,
    f3_root: Path,
    f4_root: Path,
    reboot_root: Path,
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
        raise ReleaseInputsBuildError("destination_already_exists")
    profile = _load_profile(profile_path)
    manifest, capacity = _verify_f3(f3_root, source_head)
    _verify_control(
        f4_root,
        source_head,
        expected_files=F4_FILES,
        tar_name="n3w-t1-f4-control-package.tar",
        sidecar_name="n3w-t1-f4-control-package.tar.sha256",
        report_name="build-report.json",
        manifest_member="f4-package/f4-package-manifest.json",
        error_prefix="f4_control",
    )
    _verify_control(
        reboot_root,
        source_head,
        expected_files=REBOOT_FILES,
        tar_name="n3w-t1-f4-reboot-successor-control.tar",
        sidecar_name="n3w-t1-f4-reboot-successor-control.tar.sha256",
        report_name="reboot-successor-build-report.json",
        manifest_member="reboot-successor-control/reboot-successor-manifest.json",
        error_prefix="reboot_control",
    )
    artifacts = destination / "artifacts"
    artifacts.mkdir(parents=True, mode=0o700)
    try:
        f3_payload = artifacts / "f3-payload.tar"
        _write_tar(
            f3_payload,
            [(name, f3_root / name) for name in F3_PAYLOAD_FILES],
        )
        image_records = []
        for name in F3_IMAGE_FILES:
            path = f3_root / name
            image_records.append(
                {
                    "path": name,
                    "sha256": _sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            )
        f3_image = artifacts / "f3-images.tar"
        _write_tar(
            f3_image,
            [(name, f3_root / name) for name in F3_IMAGE_FILES],
            (
                "image-set.json",
                {
                    "schema": IMAGE_SET_SCHEMA,
                    "source_head": source_head,
                    "files": image_records,
                },
            ),
        )
        f4_control = artifacts / "f4-control.tar"
        shutil.copyfile(f4_root / "n3w-t1-f4-control-package.tar", f4_control)
        reboot_control = artifacts / "reboot-control.tar"
        shutil.copyfile(
            reboot_root / "n3w-t1-f4-reboot-successor-control.tar",
            reboot_control,
        )
        v2_mac_tools = artifacts / "v2-mac-tools.tar"
        _materialize_mac_tools(repository, v2_mac_tools, source_head)
        transport_contract = artifacts / "transport-contract.json"
        transport_contract.write_bytes(
            canonical_json_bytes(
                {
                    "schema": TRANSPORT_SCHEMA,
                    "source_head": source_head,
                    "transport": manifest["transport"],
                    "capacity": capacity,
                }
            )
        )
        artifact_records: dict[str, dict[str, Any]] = {}
        for name, relative in RELEASE_INPUT_ARTIFACT_PATHS.items():
            artifact_path = destination / relative
            _regular(artifact_path, f"release_input_artifact_invalid:{name}")
            artifact_records[name] = {
                "path": relative,
                "sha256": _sha256(artifact_path),
                "size_bytes": artifact_path.stat().st_size,
            }
        material = _build_material(
            profile,
            source_head,
            source_tree,
            artifact_records,
            capacity,
        )
        (destination / "release-inputs.json").write_bytes(
            canonical_json_bytes(material)
        )
        verified = verify_inputs_directory(destination)
        return {
            **verified,
            "production_authority": production_authority,
        }
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--repository", type=Path, default=Path.cwd())
    build.add_argument("--profile", type=Path, required=True)
    build.add_argument("--f3-dir", type=Path, required=True)
    build.add_argument("--f4-dir", type=Path, required=True)
    build.add_argument("--reboot-dir", type=Path, required=True)
    build.add_argument("--destination", type=Path, required=True)
    build.add_argument("--source-head", required=True)
    build.add_argument("--source-tree", required=True)
    build.add_argument("--production-authority", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("--destination", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "build":
            report = build_inputs(
                args.repository,
                args.profile,
                args.f3_dir,
                args.f4_dir,
                args.reboot_dir,
                args.destination,
                source_head=args.source_head,
                source_tree=args.source_tree,
                production_authority=args.production_authority,
            )
        else:
            report = verify_inputs_directory(args.destination)
    except (
        OSError,
        KeyError,
        ValueError,
        tarfile.TarError,
        ReleaseInputsBuildError,
        RuntimeError,
    ) as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": str(error)[:300],
                    "production_authority": False,
                    "t1_access": False,
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
