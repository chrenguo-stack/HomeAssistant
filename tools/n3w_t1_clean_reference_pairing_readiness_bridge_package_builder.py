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

SCHEMA = "gh.n3w-t1-clean-reference-pairing-readiness-bridge-package/1"

PRODUCT_SOURCE_HEAD = "24382caae4a1f5d459297f86e8d18f10a848ca64"
R2A_CONTROL_HEAD = "abeb6c31147bcf249361dcec7e9536eaed6106a6"
R2B_CONTROL_HEAD = "e15c64ac8f0f5f482a6c8538072031734002a559"
R3_OBSERVER_CONTROL_HEAD = "da9124fe18774cdb5822f9eb3afee40120cfb04f"
R2_REFERENCE_SHA256 = "89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747"

FILES = {
    "tools/n3w_t1_clean_reference_pairing_readiness_bridge.py": 0o755,
    "tools/n3w_t1_clean_reference_observer.py": 0o755,
}


class PackageError(RuntimeError):
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
        raise PackageError("control_plane_head_invalid")
    if destination.exists() or destination.is_symlink():
        raise PackageError("destination_exists")

    destination.mkdir(parents=True, mode=0o700)
    records: list[dict[str, object]] = []
    try:
        for relative, mode in FILES.items():
            source = repo_root / relative
            if source.is_symlink() or not source.is_file():
                raise PackageError(f"source_invalid:{relative}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            os.chmod(target, mode)
            records.append(
                {
                    "path": relative,
                    "sha256": _sha256(target),
                    "size": target.stat().st_size,
                    "mode": mode,
                }
            )

        manifest = {
            "schema": SCHEMA,
            "product_source_head": PRODUCT_SOURCE_HEAD,
            "r2a_control_head": R2A_CONTROL_HEAD,
            "r2b_control_head": R2B_CONTROL_HEAD,
            "r3_observer_control_head": R3_OBSERVER_CONTROL_HEAD,
            "r2_reference_sha256": R2_REFERENCE_SHA256,
            "control_plane_head": control_plane_head,
            "files": sorted(records, key=lambda item: str(item["path"])),
            "t1_access": False,
            "t1_mutation": False,
            "network_mutation": False,
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
            "r2b_control_head": R2B_CONTROL_HEAD,
            "r3_observer_control_head": R3_OBSERVER_CONTROL_HEAD,
            "r2_reference_sha256": R2_REFERENCE_SHA256,
            "control_plane_head": control_plane_head,
            "file_count": len(records),
            "package_manifest_sha256": _sha256(manifest_path),
            "t1_access": False,
            "t1_mutation": False,
            "network_mutation": False,
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
    except (PackageError, OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "reason": str(error)[:300],
                    "t1_access": False,
                    "t1_mutation": False,
                    "network_mutation": False,
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
