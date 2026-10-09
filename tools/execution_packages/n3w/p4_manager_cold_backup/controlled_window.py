from __future__ import annotations

import argparse
import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import cold_snapshot as snapshot

MANAGER = "greenhouse-manager"
BROKER = "n3wfc4-broker-1"
WINDOW_TIMEOUT_SECONDS = 150
STOP_TIMEOUT_SECONDS = 30
START_TIMEOUT_SECONDS = 30


class WindowStop(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise WindowStop(code)


def run_docker(*args: str, timeout: int = 30) -> None:
    process = subprocess.run(
        ("docker", *args),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
    )
    require(process.returncode == 0, "DOCKER_SERVICE_ACTION_FAILED")


def get_private_origin(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    require(os.geteuid() == 0, "REQUIRES_ROOT")
    require(
        directory.is_dir()
        and not directory.is_symlink()
        and stat.S_IMODE(directory.stat().st_mode) == 0o700,
        "PRIVATE_ROOT_INVALID",
    )
    files = (
        directory / "manager-inspect-private.json",
        directory / "broker-inspect-private.json",
    )
    for file in files:
        require(
            file.is_file()
            and not file.is_symlink()
            and stat.S_IMODE(file.stat().st_mode) == 0o600,
            "PRIVATE_INSPECT_INVALID",
        )
    manager = json.loads(files[0].read_text())[0]
    broker = json.loads(files[1].read_text())[0]
    require(isinstance(manager, dict) and isinstance(broker, dict), "PRIVATE_INSPECT_FORMAT_INVALID")
    return manager, broker


def check_old_running(origin: dict[str, Any], broker_origin: dict[str, Any]) -> None:
    snapshot.validate_runtime(origin, broker_origin, "preflight")
    current = snapshot.inspect(MANAGER)
    require(current["HostConfig"]["RestartPolicy"]["Name"] == "unless-stopped", "UNEXPECTED_RESTART_POLICY")
    require(current["HostConfig"]["NetworkMode"] == "host", "UNEXPECTED_MANAGER_NETWORK_MODE")
    require(current["State"]["Running"] is True, "ORIGINAL_MANAGER_NOT_RUNNING")


def check_old_stopped(origin: dict[str, Any], broker_origin: dict[str, Any]) -> None:
    snapshot.validate_runtime(origin, broker_origin, "capture")


def resume_original_manager(origin: dict[str, Any], broker_origin: dict[str, Any]) -> None:
    current = snapshot.inspect(MANAGER)
    require(current.get("Id") == origin.get("Id"), "OLD_MANAGER_ID_MISMATCH")
    if not current.get("State", {}).get("Running"):
        run_docker("start", MANAGER, timeout=START_TIMEOUT_SECONDS)
    deadline = time.monotonic() + 45
    consecutive_running = 0
    while time.monotonic() < deadline:
        current = snapshot.inspect(MANAGER)
        if current.get("Id") == origin.get("Id") and current.get("State", {}).get("Running") is True:
            consecutive_running += 1
            if consecutive_running >= 3:
                snapshot.validate_runtime(origin, broker_origin, "preflight")
                broker = snapshot.inspect(BROKER)
                require(
                    broker.get("State", {}).get("StartedAt")
                    == broker_origin.get("State", {}).get("StartedAt"),
                    "BROKER_STARTED_AT_CHANGED",
                )
                require(
                    broker.get("RestartCount") == broker_origin.get("RestartCount"),
                    "BROKER_RESTART_COUNT_CHANGED",
                )
                return
        else:
            consecutive_running = 0
        time.sleep(1)
    raise WindowStop("OLD_MANAGER_RESTART_NOT_STABLE")


def run_window(
    directory: Path,
    *,
    allow_stop: bool,
    capture: Callable[[Path], None],
    stop_action: Callable[[], None],
    resume: Callable[[], None],
    now: Callable[[], float] = time.monotonic,
) -> None:
    require(allow_stop, "STOP_WINDOW_NOT_AUTHORIZED")
    origin, broker_origin = get_private_origin(directory)
    check_old_running(origin, broker_origin)
    require(
        not (directory / "cold-snapshot").exists()
        and not (directory / "isolated-restoration").exists()
        and not (directory / "cold-snapshot-manifest-private.json").exists(),
        "PRIVATE_BACKUP_ALREADY_EXISTS",
    )
    started = now()
    stop_attempted = False
    failure: BaseException | None = None
    try:
        stop_attempted = True
        stop_action()
        check_old_stopped(origin, broker_origin)
        capture(directory)
        require(now() - started <= WINDOW_TIMEOUT_SECONDS, "MANAGER_STOP_WINDOW_TIMEOUT")
    except BaseException as error:
        failure = error
    finally:
        if stop_attempted:
            try:
                resume()
            except BaseException as recovery_error:
                print("OLD_MANAGER_RECOVERY=FAILED_STOP_MANUAL", file=sys.stderr)
                raise WindowStop("OLD_MANAGER_RECOVERY_FAILED") from recovery_error
    if failure is not None:
        raise WindowStop("COLD_BACKUP_OR_STOP_FAILED_OLD_MANAGER_RESUMED") from failure
    print("ORIGINAL_MANAGER_RETURNED_RUNNING=PASS")
    print("BROKER_NOT_RESTARTED_BY_EXECUTOR=true")
    print("COLD_SNAPSHOT_AND_RESTORE=PASS")


def interrupt(_signum: int, _frame: Any) -> None:
    raise WindowStop("INTERRUPTED_RECOVER_OLD_MANAGER")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "execute"))
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--permit-manager-stop", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    directory = snapshot.private_root(args.private_root)
    manager, broker = get_private_origin(directory)
    check_old_running(manager, broker)
    if args.phase == "preflight":
        print("ORIGINAL_MANAGER_STOP_RECOVERY_PREFLIGHT=PASS")
        print("BROKER_PERSISTENCE_PREFLIGHT=PASS")
        print("MANAGER_STOP_NOT_EXECUTED=true")
        return
    require(args.permit_manager_stop, "EXPLICIT_MANAGER_STOP_AUTHORIZATION_REQUIRED")
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupt)

    def capture(value: Path) -> None:
        sources = snapshot.validate_runtime(manager, broker, "capture")
        snapshot.capture(sources, value)
        snapshot.validate_runtime(manager, broker, "capture")

    run_window(
        directory,
        allow_stop=True,
        capture=capture,
        stop_action=lambda: run_docker(
            "stop", "--time", str(STOP_TIMEOUT_SECONDS), MANAGER,
            timeout=STOP_TIMEOUT_SECONDS + 10,
        ),
        resume=lambda: resume_original_manager(manager, broker),
    )


if __name__ == "__main__":
    try:
        main()
    except (snapshot.Stop, WindowStop, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        code = str(error) if isinstance(error, (snapshot.Stop, WindowStop)) else type(error).__name__
        print(f"P4_CONTROLLED_BACKUP=STOP:{code}", file=sys.stderr)
        raise SystemExit(1)
