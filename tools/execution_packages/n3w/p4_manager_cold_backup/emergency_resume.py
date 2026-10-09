from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cold_snapshot as snapshot
import controlled_window as window


def recover_original(private_root: Path) -> None:
    directory = snapshot.private_root(str(private_root))
    manager, broker = window.get_private_origin(directory)
    original_id = manager.get("Id")
    current = snapshot.inspect(window.MANAGER)
    window.require(current.get("Id") == original_id, "ORIGINAL_CONTAINER_ID_MISMATCH")
    window.require(
        current.get("Image") == manager.get("Image"),
        "ORIGINAL_CONTAINER_IMAGE_MISMATCH",
    )
    for field in ("Config", "HostConfig"):
        window.require(
            current.get(field) == manager.get(field),
            "ORIGINAL_CONTAINER_CONFIG_MISMATCH",
        )
    window.resume_original_manager(manager, broker)
    print("ORIGINAL_MANAGER_RESCUE_VERIFIED=PASS")
    print("BROKER_RESTART_REQUESTED=false")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", required=True)
    args = parser.parse_args()
    recover_original(Path(args.private_root))


if __name__ == "__main__":
    try:
        main()
    except (snapshot.Stop, window.WindowStop, OSError, ValueError, KeyError) as error:
        code = str(error) if isinstance(error, (snapshot.Stop, window.WindowStop)) else type(error).__name__
        print("ORIGINAL_MANAGER_RESCUE=FAILED_STOP_MANUAL:" + code, file=sys.stderr)
        raise SystemExit(1)
