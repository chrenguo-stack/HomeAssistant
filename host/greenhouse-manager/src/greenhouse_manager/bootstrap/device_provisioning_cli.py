from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, TextIO

from greenhouse_manager.bootstrap.device_firstboot import (
    PROVISIONING_CONFIRMATION,
    DeviceFirstbootError,
)

SCHEMA = "gh.n3w.t1-device-provisioning-cli/1"


class DeviceProvisioningController(Protocol):
    def inspect(
        self,
        transaction_root: Path,
        candidate_root: Path,
        *,
        release_id: str,
    ) -> Mapping[str, object]: ...

    def start(
        self,
        transaction_root: Path,
        candidate_root: Path,
        *,
        release_id: str,
        confirmation: str,
    ) -> Mapping[str, object]: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="n3w-t1-provision")
    parser.add_argument("--transaction-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")
    start = subparsers.add_parser("start")
    start.add_argument("--confirm", required=True)
    return parser


def _emit(destination: TextIO, document: Mapping[str, object]) -> None:
    destination.write(
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    controller: DeviceProvisioningController | None = None,
    output: TextIO | None = None,
    error_output: TextIO | None = None,
) -> int:
    destination = output or sys.stdout
    errors = error_output or sys.stderr
    args = _parser().parse_args(argv)

    if controller is None:
        _emit(
            errors,
            {
                "schema": SCHEMA,
                "status": "FAIL",
                "error_code": "host_adapter_required",
                "production_service_start": False,
            },
        )
        return 2

    if args.command == "start" and args.confirm != PROVISIONING_CONFIRMATION:
        _emit(
            errors,
            {
                "schema": SCHEMA,
                "status": "FAIL",
                "error_code": "provisioning_confirmation_invalid",
                "confirmation_required": PROVISIONING_CONFIRMATION,
                "production_service_start": False,
            },
        )
        return 2

    try:
        if args.command == "status":
            report = controller.inspect(
                args.transaction_root,
                args.candidate_root,
                release_id=args.release_id,
            )
        else:
            report = controller.start(
                args.transaction_root,
                args.candidate_root,
                release_id=args.release_id,
                confirmation=args.confirm,
            )
    except (DeviceFirstbootError, OSError, ValueError) as error:
        _emit(
            errors,
            {
                "schema": SCHEMA,
                "status": "FAIL",
                "error_code": str(error) or type(error).__name__,
                "production_service_start": False,
            },
        )
        return 2

    _emit(
        destination,
        {
            "schema": SCHEMA,
            **report,
            "production_service_start": False,
        },
    )
    return 0
