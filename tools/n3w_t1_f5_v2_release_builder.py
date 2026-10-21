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
        else:
            report = verify_release_directory(args.destination)
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
