from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from greenhouse_manager.runtime.n3w_dynamic_pairing_window import (
    DEFAULT_WINDOW_SECONDS,
    close_dynamic_pairing_window_over_socket,
    dynamic_pairing_window_status_over_socket,
    open_dynamic_pairing_window_over_socket,
    recover_expired_first_registration_over_socket,
)
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


def _default_control_socket_path() -> str:
    return (
        os.getenv(
            "GH_N3W_PAIRING_CONTROL_SOCKET_PATH"
        )
        or "/run/greenhouse-manager/pairing-control.sock"
    )


def _authorization_arguments(
    command: argparse.ArgumentParser,
) -> None:
    command.add_argument(
        "--socket",
        default=_default_socket_path(),
    )
    command.add_argument(
        "--hardware-id",
        required=True,
    )
    command.add_argument(
        "--pairing-id",
        required=True,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="greenhouse-manager-pairing"
    )
    commands = root.add_subparsers(
        dest="command",
        required=True,
    )

    import_command = commands.add_parser(
        "import",
        help="import a Setup Secret over local IPC",
    )
    import_command.add_argument(
        "--socket",
        default=_default_socket_path(),
    )
    import_command.add_argument(
        "--hardware-id",
        required=True,
    )
    import_command.add_argument(
        "--pairing-id",
        required=True,
    )
    import_command.add_argument(
        "--setup-secret-stdin",
        action="store_true",
        required=True,
        help="read one base64url Setup Secret line from stdin",
    )

    repair_command = commands.add_parser(
        "authorize-repair",
        help=(
            "authorize one bounded ordinary repair "
            "transaction over local IPC"
        ),
    )
    _authorization_arguments(
        repair_command
    )

    recovery_command = commands.add_parser(
        "authorize-credential-recovery",
        help=(
            "authorize one bounded existing-identity "
            "MQTT credential recovery transaction "
            "over local IPC"
        ),
    )
    _authorization_arguments(
        recovery_command
    )

    window_open = commands.add_parser(
        "window-open",
        help=(
            "open one bounded Manager-owned pairing "
            "window over local IPC"
        ),
    )
    window_open.add_argument(
        "--control-socket",
        default=_default_control_socket_path(),
    )
    window_open.add_argument(
        "--peer-ip",
        required=True,
    )
    window_open.add_argument(
        "--window-seconds",
        type=int,
        default=DEFAULT_WINDOW_SECONDS,
    )

    window_status = commands.add_parser(
        "window-status",
        help=(
            "read Manager-owned pairing-window state "
            "over local IPC"
        ),
    )
    window_status.add_argument(
        "--control-socket",
        default=_default_control_socket_path(),
    )

    window_close = commands.add_parser(
        "window-close",
        help=(
            "close the Manager-owned pairing window "
            "over local IPC"
        ),
    )
    window_close.add_argument(
        "--control-socket",
        default=_default_control_socket_path(),
    )

    expired_first_recovery = commands.add_parser(
        "recover-expired-first",
        help=(
            "release one expired never-approved "
            "first-registration pointer"
        ),
    )
    expired_first_recovery.add_argument(
        "--control-socket",
        default=_default_control_socket_path(),
    )
    expired_first_recovery.add_argument(
        "--hardware-id-sha256",
        required=True,
    )
    expired_first_recovery.add_argument(
        "--pairing-id-sha256",
        required=True,
    )

    return root


def main(
    argv: Sequence[str] | None = None,
) -> int:
    root = parser()
    args = root.parse_args(argv)

    if args.command == "authorize-repair":
        result = authorize_repair_over_socket(
            args.socket,
            hardware_id=args.hardware_id,
            pairing_id=args.pairing_id,
        )
    elif (
        args.command
        == "authorize-credential-recovery"
    ):
        result = (
            authorize_credential_recovery_over_socket(
                args.socket,
                hardware_id=args.hardware_id,
                pairing_id=args.pairing_id,
            )
        )
    elif args.command == "window-open":
        result = (
            open_dynamic_pairing_window_over_socket(
                args.control_socket,
                peer_ip=args.peer_ip,
                window_seconds=args.window_seconds,
            )
        )
    elif args.command == "window-status":
        result = (
            dynamic_pairing_window_status_over_socket(
                args.control_socket
            )
        )
    elif args.command == "window-close":
        result = (
            close_dynamic_pairing_window_over_socket(
                args.control_socket
            )
        )
    elif args.command == "recover-expired-first":
        result = (
            recover_expired_first_registration_over_socket(
                args.control_socket,
                hardware_id_sha256=(
                    args.hardware_id_sha256
                ),
                pairing_id_sha256=(
                    args.pairing_id_sha256
                ),
            )
        )
    else:
        setup_secret = (
            sys.stdin.readline(256).strip()
        )
        if not setup_secret:
            root.error(
                "Setup Secret stdin is empty"
            )
        result = import_setup_secret_over_socket(
            args.socket,
            hardware_id=args.hardware_id,
            pairing_id=args.pairing_id,
            setup_secret=setup_secret,
        )

    print(
        json.dumps(
            result,
            sort_keys=True,
        )
    )
    return (
        0
        if result.get("accepted") is True
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
