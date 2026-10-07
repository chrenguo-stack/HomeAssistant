from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence

from greenhouse_manager.runtime.n3w_pairing_local_ipc import (
    authorize_credential_recovery_over_socket,
    authorize_repair_over_socket,
    import_setup_secret_over_socket,
)

PAIRING_PAYLOAD_RE = re.compile(
    r"GHN3W2:"
    r"([A-Za-z0-9._-]{1,128}):"
    r"([A-Za-z0-9._-]{1,128}):"
    r"([A-Za-z0-9_-]{1,128})"
)
MAX_PAIRING_PAYLOAD_CHARS = 512


class PairingPayloadError(ValueError):
    pass


def _parse_pairing_payload(value: str) -> tuple[str, str, str]:
    if not value or len(value) > MAX_PAIRING_PAYLOAD_CHARS:
        raise PairingPayloadError("pairing_payload_invalid")
    match = PAIRING_PAYLOAD_RE.fullmatch(value)
    if match is None:
        raise PairingPayloadError("pairing_payload_invalid")
    return match.group(1), match.group(2), match.group(3)


def _read_pairing_payload_stdin() -> str:
    raw = sys.stdin.read(MAX_PAIRING_PAYLOAD_CHARS + 1)
    if len(raw) > MAX_PAIRING_PAYLOAD_CHARS:
        raise PairingPayloadError("pairing_payload_too_large")
    value = raw.rstrip("\r\n")
    if "\n" in value or "\r" in value:
        raise PairingPayloadError("pairing_payload_multiple_lines")
    return value


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

    payload_command = commands.add_parser(
        "import-payload",
        help="import one complete GHN3W2 pairing payload over local IPC",
    )
    payload_command.add_argument("--socket", default=_default_socket_path())
    payload_command.add_argument(
        "--payload-stdin",
        action="store_true",
        required=True,
        help="read one complete GHN3W2 payload from stdin",
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
    elif args.command == "import-payload":
        try:
            hardware_id, pairing_id, setup_secret = _parse_pairing_payload(
                _read_pairing_payload_stdin()
            )
        except PairingPayloadError:
            root.error("Pairing payload stdin is invalid")
        result = import_setup_secret_over_socket(
            args.socket,
            hardware_id=hardware_id,
            pairing_id=pairing_id,
            setup_secret=setup_secret,
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
