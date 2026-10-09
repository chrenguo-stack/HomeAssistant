from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import cold_snapshot as snapshot
import controlled_window as window
import cutover_contract as contract
import fresh_manager_deploy as deploy
import fresh_manager_recovery as recovery
import r3_forensic_seal as r3_seal
import fresh_manager_systemd_unit as unit

WAIT_LIMIT_SECONDS = 430


class OperatorStop(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise OperatorStop(code)


def invoke(args: tuple[str, ...], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def checked(args: tuple[str, ...], code: str, *, timeout: int = 30) -> str:
    result = invoke(args, timeout=timeout)
    require(result.returncode == 0, code)
    return result.stdout


def unit_status() -> dict[str, str]:
    result = invoke((
        "systemctl",
        "show",
        unit.UNIT_NAME,
        "--property=LoadState,ActiveState,SubState,Result,ExecMainStartTimestampMonotonic",
    ), timeout=12)
    require(result.returncode == 0, "SYSTEMD_UNIT_STATUS_UNAVAILABLE")
    return dict(
        line.split("=", 1)
        for line in result.stdout.splitlines()
        if "=" in line
    )


def check_unit_name_available() -> None:
    result = invoke(("systemctl", "show", unit.UNIT_NAME, "--property=LoadState", "--value"), timeout=12)
    require(
        result.returncode == 0 and result.stdout.strip() == "not-found",
        "FRESH_MANAGER_SYSTEMD_UNIT_NAME_COLLISION",
    )
    require(
        not unit.UNIT_DEST.exists() and not unit.UNIT_DEST.is_symlink(),
        "FRESH_MANAGER_SYSTEMD_UNIT_FILE_COLLISION",
    )


def _private_json(path: Path) -> Any:
    require(
        path.is_file()
        and not path.is_symlink()
        and stat.S_IMODE(path.stat().st_mode) == 0o600,
        "PRIVATE_JSON_INVALID",
    )
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise OperatorStop("PRIVATE_JSON_UNREADABLE") from error


def non_mutating_preflight(private: Path) -> str:
    deploy.verify_r5_rollback_authority(private)
    r3_seal.verify_r2(private)
    origin, broker_origin = window.get_private_origin(private)
    window.check_old_running(origin, broker_origin)
    old = deploy.docker_json("container", contract.MANAGER_NAME)
    broker = deploy.docker_json("container", contract.BROKER_NAME)
    image = deploy.docker_json("image", contract.CANDIDATE_TAG)
    require(old.get("Id") == origin.get("Id"), "OLD_MANAGER_NOT_R5_ORIGIN")
    deploy.broker_unchanged(broker_origin, broker)
    contract.validate_source_authority(old, broker, image)
    deploy.validate_create_contract(old)
    require(shutil.which("systemctl") is not None, "SYSTEMCTL_REQUIRED")
    require(shutil.which("systemd-analyze") is not None, "SYSTEMD_ANALYZE_REQUIRED")
    require(shutil.which("docker") is not None, "DOCKER_CLI_REQUIRED")
    require(shutil.which("ss") is not None, "SS_TOOL_REQUIRED")
    checked(("systemctl", "is-active", "--quiet", "docker.service"), "DOCKER_SYSTEMD_NOT_ACTIVE")
    check_unit_name_available()
    for name in (deploy.SHADOW_NAME, deploy.PARKED_NAME, deploy.FAILED_NAME):
        require(not deploy.container_exists(name), "CUTOVER_CONTAINER_NAME_COLLISION")
    require(
        not (private / deploy.STATE_FILE).exists(),
        "TRANSACTION_ALREADY_EXISTS_NO_REPLAY",
    )
    require(
        not (private / deploy.FRESH_BASE).exists(),
        "FRESH_RUNTIME_BASE_ALREADY_EXISTS",
    )
    stage = private / unit.STAGE_DIR
    python = Path(sys.executable).resolve()
    text = unit.render_unit(private, stage, python)
    template = private / "fresh-manager-systemd-verify-private.service"
    log = private / "fresh-manager-systemd-verify-private.log"
    require(
        not template.exists()
        and not template.is_symlink()
        and not log.exists()
        and not log.is_symlink(),
        "SYSTEMD_VERIFY_PRIVATE_FILE_COLLISION",
    )
    try:
        fd = os.open(template, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        with log.open("x") as output:
            verification = subprocess.run(
                ("systemd-analyze", "verify", str(template)),
                stdout=output,
                stderr=output,
                check=False,
                timeout=25,
            )
        log.chmod(0o600)
        require(verification.returncode == 0, "SYSTEMD_UNIT_STATIC_VERIFY_FAILED")
    finally:
        if template.exists():
            template.unlink()
        if log.exists():
            log.unlink()
    return text


def install_unit(text: str) -> None:
    require(
        not unit.UNIT_DEST.exists() and not unit.UNIT_DEST.is_symlink(),
        "SYSTEMD_UNIT_FILE_COLLISION",
    )
    fd = os.open(unit.UNIT_DEST, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        checked(("systemctl", "daemon-reload"), "SYSTEMD_DAEMON_RELOAD_FAILED")
    except BaseException:
        if unit.UNIT_DEST.exists():
            unit.UNIT_DEST.unlink()
        raise


def wait_for_unit(now=time.monotonic, sleep=time.sleep) -> None:
    deadline = now() + WAIT_LIMIT_SECONDS
    started = False
    while now() < deadline:
        status = unit_status()
        require(status.get("LoadState") == "loaded", "SYSTEMD_UNIT_NO_LONGER_LOADED")
        stamp = status.get("ExecMainStartTimestampMonotonic", "0")
        if stamp.isdecimal() and int(stamp) > 0:
            started = True
        state = status.get("ActiveState")
        if started and state in ("inactive", "failed"):
            require(
                state == "inactive" and status.get("Result") == "success",
                "FRESH_MANAGER_SYSTEMD_TRANSACTION_FAILED",
            )
            return
        sleep(2)
    raise OperatorStop("SYSTEMD_TRANSACTION_WAIT_TIMEOUT")


def verify_success(private: Path) -> None:
    state = _private_json(private / deploy.STATE_FILE)
    require(state.get("committed") is True, "TRANSACTION_STATE_NOT_COMMITTED")
    candidate = deploy.docker_json("container", contract.MANAGER_NAME)
    require(
        candidate.get("Id") == state.get("candidate_id")
        and candidate.get("Image") == state.get("candidate_image_id")
        and candidate.get("State", {}).get("Running") is True,
        "COMMITTED_CANDIDATE_RUNTIME_MISMATCH",
    )
    parked = deploy.docker_json("container", deploy.PARKED_NAME)
    require(
        parked.get("Id") == state.get("old_manager_id")
        and parked.get("State", {}).get("Running") is False,
        "PARKED_OLD_MANAGER_RUNTIME_MISMATCH",
    )
    _, broker_origin = window.get_private_origin(private)
    deploy.broker_unchanged(
        broker_origin,
        deploy.docker_json("container", contract.BROKER_NAME),
    )


def remove_success_unit() -> None:
    status = unit_status()
    require(
        status.get("ActiveState") == "inactive"
        and status.get("Result") == "success",
        "SYSTEMD_UNIT_NOT_SAFE_TO_REMOVE",
    )
    unit.UNIT_DEST.unlink()
    checked(("systemctl", "daemon-reload"), "SYSTEMD_CLEANUP_RELOAD_FAILED")


def execute(private: Path) -> None:
    text = non_mutating_preflight(private)
    install_unit(text)
    checked(
        ("systemctl", "start", "--no-block", unit.UNIT_NAME),
        "SYSTEMD_TRANSACTION_START_FAILED",
    )
    print("FRESH_MANAGER_TRANSACTION_SUBMITTED=true")
    wait_for_unit()
    try:
        verify_success(private)
        remove_success_unit()
    except (OperatorStop, deploy.DeployStop, recovery.RecoveryStop,
            snapshot.Stop, window.WindowStop, contract.CutoverStop,
            OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        try:
            recovery.rollback_after_operator_final_check_failure(private)
        except (OperatorStop, deploy.DeployStop, recovery.RecoveryStop,
                snapshot.Stop, window.WindowStop, contract.CutoverStop,
                OSError, ValueError, KeyError, subprocess.TimeoutExpired) as rollback_error:
            raise OperatorStop("FINAL_VERIFICATION_FAILED_ROLLBACK_INCOMPLETE") from rollback_error
        raise OperatorStop("FINAL_VERIFICATION_FAILED_OLD_MANAGER_RESTORED") from error
    print("FRESH_MANAGER_ONE_SHOT_DEPLOYMENT=PASS")
    print("FRESH_MANAGER_PREBOOT_BASELINE=0_0_0_AND_EMPTY_RELAY_KEYS")
    print("BROKER_RESTARTED=false")
    print("OLD_MANAGER_PARKED_FOR_ROLLBACK=true")
    print("BOARD_FIRST_BOOT=false")
    print("SETUP_SECRET_IMPORT=false")


def status(private: Path) -> None:
    state_path = private / deploy.STATE_FILE
    if state_path.exists():
        state = _private_json(state_path)
        print("TRANSACTION_STATE_PRESENT=true")
        print("TRANSACTION_COMMITTED=" + str(bool(state.get("committed"))).lower())
        print("TRANSACTION_PHASE=" + str(state.get("phase", "unknown")))
        print("ROLLBACK_RESULT=" + str(state.get("rollback_result", "none")))
    else:
        print("TRANSACTION_STATE_PRESENT=false")
    result = invoke(("systemctl", "show", unit.UNIT_NAME, "--property=LoadState,ActiveState,Result"))
    if result.returncode == 0:
        values = dict(
            line.split("=", 1)
            for line in result.stdout.splitlines()
            if "=" in line
        )
        print("SYSTEMD_LOAD_STATE=" + values.get("LoadState", "unknown"))
        print("SYSTEMD_ACTIVE_STATE=" + values.get("ActiveState", "unknown"))
        print("SYSTEMD_RESULT=" + values.get("Result", "unknown"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "execute", "status"))
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--authorization-id", default="")
    parser.add_argument("--permit-live-manager-replacement", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    private = snapshot.private_root(args.private_root)
    lock = private / ".p4-fresh-manager-operator-lock"
    with lock.open("a+") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise OperatorStop("ANOTHER_FRESH_MANAGER_OPERATOR_RUNNING") from error
        if args.phase == "status":
            status(private)
            return
        text = non_mutating_preflight(private)
        print("FRESH_MANAGER_PRECHECKS=PASS")
        if args.phase == "preflight":
            print("LIVE_MANAGER_REPLACEMENT_NOT_STARTED=true")
            return
        require(
            args.authorization_id == deploy.AUTHORIZATION_ID,
            "AUTHORIZATION_ID_MISMATCH",
        )
        require(
            args.permit_live_manager_replacement,
            "LIVE_MANAGER_REPLACEMENT_NOT_AUTHORIZED",
        )
        r3_seal.seal_r2(private)
        install_unit(text)
        checked(
            ("systemctl", "start", "--no-block", unit.UNIT_NAME),
            "SYSTEMD_TRANSACTION_START_FAILED",
        )
        print("FRESH_MANAGER_TRANSACTION_SUBMITTED=true")
        wait_for_unit()
        verify_success(private)
        remove_success_unit()
        print("FRESH_MANAGER_ONE_SHOT_DEPLOYMENT=PASS")
        print("FRESH_MANAGER_PREBOOT_BASELINE=0_0_0_AND_EMPTY_RELAY_KEYS")
        print("BROKER_RESTARTED=false")
        print("OLD_MANAGER_PARKED_FOR_ROLLBACK=true")
        print("BOARD_FIRST_BOOT=false")
        print("SETUP_SECRET_IMPORT=false")


if __name__ == "__main__":
    try:
        main()
    except (
        OperatorStop,
        deploy.DeployStop,
        recovery.RecoveryStop,
        snapshot.Stop,
        window.WindowStop,
        contract.CutoverStop,
        OSError,
        ValueError,
        KeyError,
        subprocess.TimeoutExpired,
    ) as error:
        if isinstance(
            error,
            (OperatorStop, deploy.DeployStop, recovery.RecoveryStop, snapshot.Stop, window.WindowStop, contract.CutoverStop),
        ):
            code = str(error)
        else:
            code = type(error).__name__
        print("P4_FRESH_MANAGER_OPERATOR=STOP:" + code, file=sys.stderr)
        print("AUTO_RETRY=false", file=sys.stderr)
        print("CHECK_SYSTEMD_AND_TRANSACTION_STATE=true", file=sys.stderr)
        raise SystemExit(1)
