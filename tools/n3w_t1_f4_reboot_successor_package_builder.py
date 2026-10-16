from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SCHEMA = "gh.n3w-t1-f4-reboot-successor-control-package/1"
MANIFEST_NAME = "reboot-successor-manifest.json"
FILES = (
    "tools/n3w_t1_f4_certificate_runtime_guard.py",
    "tools/n3w_t1_f4_reboot_authority.py",
    "tools/n3w_t1_f4_reboot_verify.py",
    (
        "infra/n3w-t1/f4/reboot-successor/"
        "n3wfc4-broker-certificate-lifecycle.service.d/"
        "10-runtime-status-evolution.conf"
    ),
)


class PackageBuildError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_package(
    repository: Path,
    destination: Path,
    *,
    source_head: str,
) -> dict[str, object]:
    repository = repository.resolve()
    if destination.exists() or destination.is_symlink():
        raise PackageBuildError("destination_already_exists")
    if (
        len(source_head) != 40
        or any(character not in "0123456789abcdef" for character in source_head)
    ):
        raise PackageBuildError("source_head_invalid")

    destination.mkdir(parents=True, mode=0o700)
    records: list[dict[str, object]] = []
    try:
        for relative in FILES:
            source = repository / relative
            if source.is_symlink() or not source.is_file():
                raise PackageBuildError(f"source_invalid:{relative}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            records.append(
                {
                    "path": relative,
                    "sha256": _sha256(target),
                    "size": target.stat().st_size,
                }
            )

        manifest = {
            "schema": SCHEMA,
            "source_head": source_head,
            "files": records,
            "secret_values_included": False,
            "live_runtime_mutation": False,
            "reboot_executed": False,
            "board_access": False,
        }
        manifest_path = destination / MANIFEST_NAME
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )
        return {
            "status": "PASS",
            "source_head": source_head,
            "manifest_sha256": _sha256(manifest_path),
            "file_count": len(records),
            "secret_values_included": False,
            "live_runtime_mutation": False,
            "reboot_executed": False,
            "board_access": False,
        }
    except (OSError, PackageBuildError):
        shutil.rmtree(destination, ignore_errors=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = build_package(
            args.repository,
            args.destination,
            source_head=args.source_head,
        )
    except (OSError, PackageBuildError) as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": str(error)[:300],
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
