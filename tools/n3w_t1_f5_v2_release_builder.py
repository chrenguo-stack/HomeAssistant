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
from pathlib import Path
from typing import Any

from n3w_t1_production_v2_contract import (
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
    return value


def _artifact_source(root: Path, relative: Any, name: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or relative.strip() != relative
        or os.path.isabs(relative)
    ):
        raise ReleaseBuildError(f"artifact_path_invalid:{name}")
    unresolved = root / relative
    if unresolved.is_symlink():
        raise ReleaseBuildError(f"artifact_source_symlink:{name}")
    candidate = unresolved.resolve()
    root_resolved = root.resolve()
    if candidate == root_resolved or root_resolved not in candidate.parents:
        raise ReleaseBuildError(f"artifact_path_escape:{name}")
    current = unresolved
    while current != root:
        if current.is_symlink():
            raise ReleaseBuildError(f"artifact_source_symlink:{name}")
        current = current.parent
    if not candidate.is_file():
        raise ReleaseBuildError(f"artifact_source_invalid:{name}")
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
    input_root = inputs_path.resolve().parent

    destination.mkdir(parents=True, mode=0o700)
    artifacts_dir = destination / ARTIFACT_DIR
    artifacts_dir.mkdir(mode=0o700)
    records: dict[str, dict[str, Any]] = {}
    try:
        for name in sorted(inputs["artifacts"]):
            if not isinstance(name, str) or not name or "/" in name or "\\" in name:
                raise ReleaseBuildError("artifact_name_invalid")
            source = _artifact_source(input_root, inputs["artifacts"][name], name)
            target = artifacts_dir / name
            shutil.copyfile(source, target)
            records[name] = {
                "sha256": _sha256(target),
                "size_bytes": target.stat().st_size,
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
        release = validate_release(json.loads(manifest.read_text(encoding="utf-8")))
    except Exception as error:
        raise ReleaseBuildError("release_manifest_invalid") from error
    expected_sha = sidecar.read_text(encoding="ascii").strip()
    if expected_sha != _sha256(manifest):
        raise ReleaseBuildError("release_manifest_sha256_mismatch")
    artifacts_dir = destination / ARTIFACT_DIR
    if artifacts_dir.is_symlink() or not artifacts_dir.is_dir():
        raise ReleaseBuildError("release_artifact_directory_invalid")
    if {path.name for path in artifacts_dir.iterdir()} != set(release["artifacts"]):
        raise ReleaseBuildError("release_artifact_set_invalid")
    for name, record in release["artifacts"].items():
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
