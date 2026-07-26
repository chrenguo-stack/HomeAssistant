from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from .node_mqtt_board_lab_common import NodeMqttBoardLabError, _canonical_json
from .private_mosquitto_builder import (
    build_private_mosquitto,
    plan_private_mosquitto,
    private_mosquitto_manifest_path,
    verify_private_mosquitto,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and verify the frozen project-private Mosquitto board-lab toolchain"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan")
    plan.add_argument("--cache-root", type=Path, required=True)
    plan.add_argument("--cmake-bin", default="cmake")
    plan.add_argument("--openssl-root", type=Path)

    build = subparsers.add_parser("build")
    build.add_argument("--cache-root", type=Path, required=True)
    build.add_argument("--confirmation", required=True)
    build.add_argument("--source-archive", type=Path)
    build.add_argument("--cmake-bin", default="cmake")
    build.add_argument("--openssl-root", type=Path)
    build.add_argument("--jobs", type=int, default=2)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", type=Path)
    verify.add_argument("--cache-root", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            report = plan_private_mosquitto(
                args.cache_root,
                cmake_bin=args.cmake_bin,
                openssl_root=args.openssl_root,
            )
        elif args.command == "build":
            report = build_private_mosquitto(
                args.cache_root,
                confirmation=args.confirmation,
                source_archive=args.source_archive,
                cmake_bin=args.cmake_bin,
                openssl_root=args.openssl_root,
                jobs=args.jobs,
            )
        elif args.command == "verify":
            if (args.manifest is None) == (args.cache_root is None):
                raise NodeMqttBoardLabError(
                    "verify requires exactly one of --manifest or --cache-root"
                )
            manifest = (
                args.manifest
                if args.manifest is not None
                else private_mosquitto_manifest_path(args.cache_root)
            )
            report = verify_private_mosquitto(manifest)
        else:
            raise NodeMqttBoardLabError("unsupported private Mosquitto command")
    except (
        NodeMqttBoardLabError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
        ValueError,
        RuntimeError,
    ) as error:
        print(f"Private Mosquitto operation failed: {error}", file=sys.stderr)
        return 2
    print(_canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
