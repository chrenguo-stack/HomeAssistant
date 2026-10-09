from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import cold_snapshot as snapshot
import controlled_window as window
import systemd_recovery_unit as unit

UNIT_NAME = unit.UNIT_NAME
UNIT_DEST = Path("/run/systemd/system") / UNIT_NAME
SCRIPTS = (
    "cold_snapshot.py",
    "controlled_window.py",
    "emergency_resume.py",
    "systemd_recovery_unit.py",
    "business_snapshot.py",
    "one_shot_operator.py",
)
STOP_WINDOW_MAX_SECONDS = 390


class GateError(RuntimeError):
    pass


def check(ok: bool, label: str) -> None:
    if not ok:
        raise GateError(label)


def invoke(args: tuple[str, ...], *, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)


def checked(args: tuple[str, ...], label: str, *, timeout: int = 20) -> None:
    result = invoke(args, timeout=timeout)
    check(result.returncode == 0, label)


def verify_archive(directory: Path) -> None:
    items = ("old-manager-image.tar", "old-manager-image.tar.sha256")
    for name in items:
        path = directory / name
        check(
            path.is_file() and not path.is_symlink()
            and stat.S_IMODE(path.stat().st_mode) == 0o600,
            "OLD_IMAGE_PRIVATE_ARCHIVE_NOT_READY",
        )
    checked(
        ("sha256sum", "-c", "--status", str(directory / items[1])),
        "OLD_IMAGE_PRIVATE_SHA256_INVALID",
        timeout=35,
    )


def verify_stage(directory: Path) -> Path:
    stage = directory / unit.STAGE_DIR
    check(stage.is_dir() and not stage.is_symlink(), "EXECUTOR_STAGE_MISSING")
    check(stat.S_IMODE(stage.stat().st_mode) == 0o700, "EXECUTOR_STAGE_NOT_PRIVATE")
    for name in SCRIPTS:
        file = stage / name
        check(
            file.is_file() and not file.is_symlink()
            and stat.S_IMODE(file.stat().st_mode) == 0o600,
            "EXECUTOR_SCRIPT_INVALID",
        )
    return stage


def manager_process_opener_owner(pid: int, manager_root: int) -> bool:
    visited: set[int] = set()
    for _ in range(128):
        if pid == manager_root:
            return True
        if pid <= 1 or pid in visited:
            return False
        visited.add(pid)
        try:
            lines = (Path("/proc") / str(pid) / "status").read_text().splitlines()
        except OSError as err:
            raise GateError("PROCESS_IDENTITY_RACE_OR_UNREADABLE") from err
        parent = [x for x in lines if x.startswith("PPid:")]
        check(len(parent) == 1, "PROCESS_PARENT_UNAVAILABLE")
        matches = re.findall(r"\d+", parent[0])
        check(len(matches) == 1, "PROCESS_PARENT_UNEXPECTED")
        pid = int(matches[0])
    raise GateError("PROCESS_ANCESTRY_TOO_DEEP")


def check_db_openers_owned_by_old_manager(current: dict[str, Any], sources: dict[str, Path]) -> None:
    root_pid = int(current["State"]["Pid"])
    check(root_pid > 1, "OLD_MANAGER_HOST_PID_INVALID")
    for label, name in snapshot.DATABASES:
        db = sources[snapshot.RW[label]] / name
        check(db.is_file() and not db.is_symlink(), "PRODUCTION_DB_MISSING")
        candidates = (
            db, Path(str(db) + "-wal"), Path(str(db) + "-shm"),
        )
        for candidate in candidates:
            if candidate != db and not candidate.exists():
                continue
            check(candidate.is_file() and not candidate.is_symlink(), "DB_SIDECAR_TYPE_CHANGED")
            report = invoke(("fuser", str(candidate)), timeout=12)
            check(report.returncode in (0, 1), "FUSER_RESULT_UNCERTAIN")
            pids = report.stdout.split()
            check(
                (report.returncode == 0 and bool(pids))
                or (report.returncode == 1 and not pids),
                "FUSER_PID_COUNT_INCONSISTENT",
            )
            for text in pids:
                check(text.isdecimal(), "FUSER_OUTPUT_NOT_PID")
                check(
                    manager_process_opener_owner(int(text), root_pid),
                    "OTHER_HOST_PROCESS_DB_OPENER_BLOCKED",
                )


def check_non_mutating_preflight(directory: Path) -> str:
    manager, broker = window.get_private_origin(directory)
    window.check_old_running(manager, broker)
    live_manager = snapshot.inspect(window.MANAGER)
    snapshot.require(
        snapshot.inspect(window.BROKER).get("State", {}).get("StartedAt")
        == broker.get("State", {}).get("StartedAt"),
        "BROKER_STARTED_AT_CHANGED",
    )
    snapshot.require(
        snapshot.inspect(window.BROKER).get("RestartCount")
        == broker.get("RestartCount"),
        "BROKER_RESTART_COUNT_CHANGED",
    )
    verify_archive(directory)
    stage = verify_stage(directory)
    check(
        not any((directory / label).exists() for label in (
            "cold-snapshot", "isolated-restoration",
            "cold-snapshot-manifest-private.json",
            "p4-business-restore-evidence-private.json",
        )),
        "COLD_BACKUP_PRIVATE_DESTINATION_ALREADY_EXISTS",
    )
    check(shutil.which("systemctl") is not None, "SYSTEMCTL_NOT_FOUND")
    check(shutil.which("systemd-analyze") is not None, "SYSTEMD_ANALYZE_NOT_FOUND")
    checked(("systemctl", "is-active", "--quiet", "docker.service"), "DOCKER_SYSTEMD_NOT_ACTIVE")
    check(not UNIT_DEST.exists() and not UNIT_DEST.is_symlink(), "ONE_SHOT_SERVICE_ALREADY_INSTALLED")
    existing = invoke(("systemctl", "show", UNIT_NAME, "--property=LoadState", "--value"))
    check(existing.returncode == 0 and existing.stdout.strip() == "not-found", "ONE_SHOT_UNIT_NAME_COLLISION")
    sources = snapshot.mount_sources(live_manager)
    check_db_openers_owned_by_old_manager(live_manager, sources)
    total_bytes = 0
    for mount in snapshot.RW.values():
        for file in sources[mount].rglob("*"):
            if file.is_symlink():
                raise GateError("PRODUCTION_SOURCE_SYMLINK_NOT_SUPPORTED")
            if file.is_file():
                total_bytes += file.stat().st_size
            elif not file.is_dir():
                raise GateError("PRODUCTION_SOURCE_SPECIAL_FILE_NOT_SUPPORTED")
    check(
        shutil.disk_usage(directory).free > 3 * total_bytes + 64 * 1024 * 1024,
        "BACKUP_DISK_SPACE_NOT_SUFFICIENT",
    )
    content = unit.render_unit(directory, stage, Path(sys.executable).resolve())
    check(
        not (directory / "one-shot-service-verify-private.log").exists(),
        "ONE_SHOT_VERIFY_LOG_ALREADY_EXISTS",
    )
    private_template = directory / "one-shot-service-verify-private.service"
    check(not private_template.exists(), "ONE_SHOT_TEMPLATE_ALREADY_EXISTS")
    with private_template.open("x") as handle:
        handle.write(content)
    private_template.chmod(0o600)
    private_log = directory / "one-shot-service-verify-private.log"
    with private_log.open("x") as output:
        verification = subprocess.run(
            ("systemd-analyze", "verify", str(private_template)),
            stdout=output, stderr=output, timeout=20, check=False,
        )
    private_log.chmod(0o600)
    check(verification.returncode == 0, "SYSTEMD_UNIT_STATIC_VERIFICATION_FAILED")
    return content


def install_one_shot_unit(content: str) -> None:
    check(not UNIT_DEST.exists() and not UNIT_DEST.is_symlink(), "ONE_SHOT_UNIT_COLLISION")
    fd = os.open(UNIT_DEST, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(content)
        checked(("systemctl", "daemon-reload"), "SYSTEMD_RELOAD_FAILED")
    except BaseException:
        if UNIT_DEST.exists():
            UNIT_DEST.unlink()
        raise


def one_shot_status() -> dict[str, str]:
    p = invoke((
        "systemctl", "show", UNIT_NAME,
        "--property=LoadState,ActiveState,Result,ExecMainStartTimestampMonotonic",
    ), timeout=12)
    check(p.returncode == 0, "ONE_SHOT_STATUS_UNAVAILABLE")
    values = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)
    return values


def wait_for_completed_unit(now=time.monotonic, sleep=time.sleep) -> None:
    deadline = now() + STOP_WINDOW_MAX_SECONDS
    started = False
    while now() < deadline:
        status = one_shot_status()
        check(status.get("LoadState") == "loaded", "ONE_SHOT_UNIT_NO_LONGER_LOADED")
        stamp = status.get("ExecMainStartTimestampMonotonic", "0")
        if stamp.isdecimal() and int(stamp) > 0:
            started = True
        state = status.get("ActiveState")
        if started and state in ("failed", "inactive"):
            check(status.get("Result") == "success" and state == "inactive", "ONE_SHOT_UNIT_FAILED")
            return
        sleep(2)
    raise GateError("ONE_SHOT_WAIT_LIMIT_REACHED_CHECK_SYSTEMD_RECOVERY")


def verify_old_manager_and_report(private: Path) -> None:
    origin, broker = window.get_private_origin(private)
    window.check_old_running(origin, broker)
    actual = snapshot.inspect(window.MANAGER)
    observed = snapshot.inspect(window.BROKER)
    check(actual.get("Id") == origin.get("Id"), "OLD_MANAGER_CONTAINER_REPLACED")
    check(observed.get("State", {}).get("StartedAt") == broker.get("State", {}).get("StartedAt"), "BROKER_RESTARTED")
    check(observed.get("RestartCount") == broker.get("RestartCount"), "BROKER_RESTARTED")
    check((private / "p4-business-restore-evidence-private.json").is_file(), "BUSINESS_EVIDENCE_MISSING")
    check((private / "cold-snapshot-manifest-private.json").is_file(), "COLD_SNAPSHOT_MANIFEST_MISSING")
    print("ONE_SHOT_THREE_DATABASE_COLD_BACKUP=PASS")
    print("ONE_SHOT_ISOLATED_RESTORE_AND_BUSINESS_STATE=PASS")
    print("ORIGINAL_MANAGER_RESTARTED=PASS")
    print("BROKER_UNCHANGED=PASS")
    print("P4_CANDIDATE_MANAGER_DEPLOYED=false")


def remove_completed_service() -> None:
    status = one_shot_status()
    check(status.get("ActiveState") == "inactive" and status.get("Result") == "success", "UNIT_NOT_SAFE_TO_REMOVE")
    UNIT_DEST.unlink()
    checked(("systemctl", "daemon-reload"), "UNIT_CLEANUP_RELOAD_FAILED")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "execute", "status"))
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--permit-manager-stop", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    private = snapshot.private_root(args.private_root)
    lock = private / ".p4-one-shot-operator-lock"
    with lock.open("a+") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise GateError("ANOTHER_P4_OPERATOR_RUNNING") from exc
        if args.phase == "status":
            status = one_shot_status()
            print("P4_SYSTEMD_UNIT_STATE=" + str(status.get("ActiveState", "unknown")))
            print("P4_SYSTEMD_UNIT_RESULT=" + str(status.get("Result", "unknown")))
            return
        check(
            args.phase == "preflight" or args.permit_manager_stop,
            "LIVE_MANAGER_STOP_NOT_AUTHORIZED",
        )
        content = check_non_mutating_preflight(private)
        print("SINGLE_ENTRY_PRECHECKS=PASS")
        if args.phase == "preflight":
            print("MANAGER_STOP_NOT_EXECUTED=true")
            print("COLD_BACKUP_NOT_STARTED=true")
            return
        install_one_shot_unit(content)
        checked(("systemctl", "start", "--no-block", UNIT_NAME), "SUPERVISED_COLD_BACKUP_START_FAILED")
        print("SUPERVISED_COLD_BACKUP_JOB_SUBMITTED=true")
        wait_for_completed_unit()
        verify_old_manager_and_report(private)
        remove_completed_service()
        print("ONE_SHOT_MANAGER_COLD_BACKUP_AND_OLD_RESTORE=PASS")


if __name__ == "__main__":
    try:
        main()
    except (
        GateError, snapshot.Stop, window.WindowStop, OSError, ValueError,
        subprocess.TimeoutExpired, subprocess.CalledProcessError, KeyError,
    ) as error:
        code = str(error) if isinstance(error, (GateError, snapshot.Stop, window.WindowStop)) else type(error).__name__
        print("P4_ONE_SHOT_OPERATOR=STOP:" + code, file=sys.stderr)
        print("LIVE_MANAGER_RECOVERY_STATUS=CHECK_SYSTEMD_AND_ORIGINAL_CONTAINER", file=sys.stderr)
        raise SystemExit(1)
