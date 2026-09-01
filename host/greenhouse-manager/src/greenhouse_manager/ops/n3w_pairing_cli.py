from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from greenhouse_manager.runtime.n3w_pairing_local_ipc import (
    authorize_credential_recovery_over_socket,
    authorize_repair_over_socket,
    import_setup_secret_over_socket,
)


def _default_socket_path() -> str:
    return (
        os.getenv("GH_N3W_PAIRING_SOCKET_PATH")
        or "/run/greenhouse-manager/pairing.sock"
    )


def _authorization_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--socket",
        default=_default_socket_path(),
    )
    command.add_argument("--hardware-id", required=True)
    command.add_argument("--pairing-id", required=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="greenhouse-manager-pairing")
    commands = root.add_subparsers(dest="command", required=True)
    import_command = commands.add_parser(
        "import",
        help="import a Setup Secret over local IPC",
    )
    import_command.add_argument("--socket", default=_default_socket_path())
    import_command.add_argument("--hardware-id", required=True)
    import_command.add_argument("--pairing-id", required=True)
    import_command.add_argument(
        "--setup-secret-stdin",
        action="store_true",
        required=True,
        help="read one base64url Setup Secret line from stdin",
    )

    repair_command = commands.add_parser(
        "authorize-repair",
        help="authorize one bounded ordinary repair transaction over local IPC",
    )
    _authorization_arguments(repair_command)

    recovery_command = commands.add_parser(
        "authorize-credential-recovery",
        help=(
            "authorize one bounded existing-identity MQTT credential recovery "
            "transaction over local IPC"
        ),
    )
    _authorization_arguments(recovery_command)

    return root


def main(argv: Sequence[str] | None = None) -> int:
    root = parser()
    args = root.parse_args(argv)
    if args.command == "authorize-repair":
        result = authorize_repair_over_socket(
            args.socket,
            hardware_id=args.hardware_id,
            pairing_id=args.pairing_id,
        )
    elif args.command == "authorize-credential-recovery":
        result = authorize_credential_recovery_over_socket(
            args.socket,
            hardware_id=args.hardware_id,
            pairing_id=args.pairing_id,
        )
    else:
        setup_secret = sys.stdin.readline(256).strip()
        if not setup_secret:
            root.error("Setup Secret stdin is empty")
        result = import_setup_secret_over_socket(
            args.socket,
            hardware_id=args.hardware_id,
            pairing_id=args.pairing_id,
            setup_secret=setup_secret,
        )

    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("accepted") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
