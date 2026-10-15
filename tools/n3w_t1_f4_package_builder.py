from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

SCHEMA = "gh.n3w-t1-f4-activation-package/1"
MANIFEST_NAME = "f4-package-manifest.json"


class PackageBuildError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_f4_host(repository: Path) -> ModuleType:
    source = repository / "tools/n3w_t1_f4_activation_host.py"
    if source.is_symlink() or not source.is_file():
        raise PackageBuildError("f4_host_source_invalid")
    specification = importlib.util.spec_from_file_location(
        "n3w_f4_package_contract",
        source,
    )
    if specification is None or specification.loader is None:
        raise PackageBuildError("f4_host_import_invalid")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _copy_file(source: Path, target: Path) -> dict[str, object]:
    if source.is_symlink() or not source.is_file():
        raise PackageBuildError(f"package_source_invalid:{source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return {
        "sha256": _sha256(target),
        "size": target.stat().st_size,
    }


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

    host = _load_f4_host(repository)
    expected = tuple(sorted(str(path) for path in host.INSTALL_MAP))
    destination.mkdir(parents=True, mode=0o700)

    records: list[dict[str, object]] = []
    try:
        for relative in expected:
            source = repository / relative
            target = destination / relative
            binding = _copy_file(source, target)
            records.append(
                {
                    "path": relative,
                    "sha256": binding["sha256"],
                    "size": binding["size"],
                }
            )

        manifest = {
            "schema": SCHEMA,
            "source_head": source_head,
            "files": records,
            "secret_values_included": False,
            "production_service_start": False,
            "board_access": False,
        }
        manifest_path = destination / MANIFEST_NAME
        manifest_path.write_text(
            json.dumps(
                manifest,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "status": "PASS",
            "source_head": source_head,
            "file_count": len(records),
            "manifest_sha256": _sha256(manifest_path),
            "secret_values_included": False,
            "production_service_start": False,
            "board_access": False,
        }
    except (OSError, PackageBuildError, RuntimeError, ValueError):
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
    except (OSError, PackageBuildError, RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": str(error)[:300],
                    "production_service_start": False,
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
