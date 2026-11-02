#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from collections.abc import Sequence
from pathlib import Path

SCHEMA = "gh.n3w-t1-clean-reference-r2b-package/1"
PRODUCT_SOURCE_HEAD = "24382caae4a1f5d459297f86e8d18f10a848ca64"
R2A_CONTROL_HEAD = "abeb6c31147bcf249361dcec7e9536eaed6106a6"
EXECUTOR = "tools/n3w_t1_clean_reference_r2b.py"


class R2BPackageError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_package(
    repo_root: Path,
    destination: Path,
    control_plane_head: str,
) -> dict[str, object]:
    if re.fullmatch(r"[0-9a-f]{40}", control_plane_head) is None:
        raise R2BPackageError("control_plane_head_invalid")
    if destination.exists() or destination.is_symlink():
        raise R2BPackageError("destination_exists")
    source = repo_root / EXECUTOR
    if source.is_symlink() or not source.is_file():
        raise R2BPackageError("executor_source_invalid")
    destination.mkdir(parents=True, mode=0o700)
    try:
        target = destination / EXECUTOR
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        os.chmod(target, 0o755)
        record = {
            "path": EXECUTOR,
            "sha256": _sha256(target),
            "size": target.stat().st_size,
            "mode": 0o755,
        }
        manifest = {
            "schema": SCHEMA,
            "product_source_head": PRODUCT_SOURCE_HEAD,
            "r2a_control_head": R2A_CONTROL_HEAD,
            "control_plane_head": control_plane_head,
            "files": [record],
            "reboot_executed": False,
            "t1_access": False,
            "board_access": False,
        }
        manifest_path = destination / "package-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "product_source_head": PRODUCT_SOURCE_HEAD,
            "r2a_control_head": R2A_CONTROL_HEAD,
            "control_plane_head": control_plane_head,
            "file_count": 1,
            "package_manifest_sha256": _sha256(manifest_path),
            "reboot_executed": False,
            "t1_access": False,
            "board_access": False,
        }
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--control-plane-head", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = build_package(
            Path(os.path.abspath(args.repo_root)),
            Path(os.path.abspath(args.destination)),
            args.control_plane_head,
        )
    except (R2BPackageError, OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:300],
                    "reboot_executed": False,
                    "t1_access": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
