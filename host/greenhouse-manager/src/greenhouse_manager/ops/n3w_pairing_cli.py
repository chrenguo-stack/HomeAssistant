from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from greenhouse_manager.runtime.n3w_pairing_local_ipc import (
    import_setup_secret_over_socket,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="greenhouse-manager-pairing")
    commands = root.add_subparsers(dest="command", required=True)
    import_command = commands.add_parser("import", help="import a Setup Secret over local IPC")
    import_command.add_argument("--socket", default="/run/greenhouse-manager/pairing.sock")
    import_command.add_argument("--hardware-id", required=True)
    import_command.add_argument("--pairing-id", required=True)
    import_command.add_argument(
        "--setup-secret-stdin",
        action="store_true",
        required=True,
        help="read one base64url Setup Secret line from stdin",
    )
    return root


def main(argv: Sequence[str] | None = None) -> int:
    root = parser()
    args = root.parse_args(argv)
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
