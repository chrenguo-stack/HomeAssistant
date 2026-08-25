from __future__ import annotations

import argparse
import json
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
    import_command.add_argument("--setup-secret", required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = import_setup_secret_over_socket(
        args.socket,
        hardware_id=args.hardware_id,
        pairing_id=args.pairing_id,
        setup_secret=args.setup_secret,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("accepted") is True else 2
