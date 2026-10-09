from __future__ import annotations

import argparse
import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import cold_snapshot as snapshot
import controlled_window as window
import cutover_contract as contract
import fresh_manager_deploy as deploy


class RecoveryStop(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RecoveryStop(code)


def load_state(private: Path) -> dict[str, Any] | None:
    path = private / deploy.STATE_FILE
    if not path.exists():
        return None
    require(
        path.is_file()
        and not path.is_symlink()
        and stat.S_IMODE(path.stat().st_mode) == 0o600,
        "TRANSACTION_STATE_INVALID",
    )
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RecoveryStop("TRANSACTION_STATE_UNREADABLE") from error
    require(
        isinstance(value, dict)
        and value.get("schema") == "gh.n3w.p4.fresh-manager-deploy/1",
        "TRANSACTION_STATE_SCHEMA_INVALID",
    )
    return value


def _run_docker(*args: str, timeout: int = 30) -> None:
    result = deploy.invoke(("docker", *args), timeout=timeout)
    require(result.returncode == 0, "ROLLBACK_DOCKER_ACTION_FAILED")


def _inspect_if_exists(name: str) -> dict[str, Any] | None:
    if not deploy.container_exists(name):
        return None
    return deploy.docker_json("container", name)


def _write_rollback_state(private: Path, state: dict[str, Any], result: str) -> None:
    state = dict(state)
    state["rollback_result"] = result
    state["rollback_phase"] = "ORIGINAL_MANAGER_RESTORED"
    deploy._atomic_json(private / deploy.STATE_FILE, state)


def recover_original(private: Path) -> None:
    origin, broker_origin = window.get_private_origin(private)
    state = load_state(private)
    if state is None:
        window.check_old_running(origin, broker_origin)
        print("FRESH_MANAGER_RECOVERY=NOT_REQUIRED_TRANSACTION_NOT_STARTED")
        return
    if state.get("committed") is True:
        current = deploy.docker_json("container", contract.MANAGER_NAME)
        require(
            current.get("Id") == state.get("candidate_id")
            and current.get("Image") == state.get("candidate_image_id")
            and current.get("State", {}).get("Running") is True,
            "COMMITTED_CANDIDATE_IDENTITY_DRIFT",
        )
        deploy.broker_unchanged(
            broker_origin,
            deploy.docker_json("container", contract.BROKER_NAME),
        )
        print("FRESH_MANAGER_RECOVERY=NOT_REQUIRED_COMMITTED")
        return

    old_id = state.get("old_manager_id")
    candidate_image = state.get("candidate_image_id")
    candidate_id = state.get("candidate_id")
    require(old_id == origin.get("Id"), "ROLLBACK_OLD_MANAGER_AUTHORITY_MISMATCH")
    require(candidate_image and isinstance(candidate_image, str), "ROLLBACK_CANDIDATE_IMAGE_UNBOUND")

    current = _inspect_if_exists(contract.MANAGER_NAME)
    parked = _inspect_if_exists(deploy.PARKED_NAME)

    if current is not None and current.get("Id") != old_id:
        require(current.get("Image") == candidate_image, "ROLLBACK_CANDIDATE_IMAGE_MISMATCH")
        if candidate_id is not None:
            require(current.get("Id") == candidate_id, "ROLLBACK_CANDIDATE_ID_MISMATCH")
        require(
            parked is not None and parked.get("Id") == old_id,
            "ROLLBACK_PARKED_OLD_MANAGER_MISSING",
        )
        if current.get("State", {}).get("Running") is True:
            _run_docker(
                "stop",
                "--time",
                str(deploy.STOP_TIMEOUT_SECONDS),
                contract.MANAGER_NAME,
                timeout=deploy.STOP_TIMEOUT_SECONDS + 15,
            )
            current = deploy.docker_json("container", contract.MANAGER_NAME)
            require(current.get("State", {}).get("Running") is False,
                    "ROLLBACK_CANDIDATE_STOP_FAILED")
        require(not deploy.container_exists(deploy.FAILED_NAME), "ROLLBACK_FAILED_NAME_COLLISION")
        _run_docker("rename", contract.MANAGER_NAME, deploy.FAILED_NAME)
        require(not deploy.container_exists(contract.MANAGER_NAME),
                "ROLLBACK_CANDIDATE_NAME_NOT_RELEASED")
        current = None

    if current is not None:
        require(current.get("Id") == old_id, "ROLLBACK_MANAGER_NAME_WRONG_ID")
    else:
        parked = _inspect_if_exists(deploy.PARKED_NAME)
        require(parked is not None and parked.get("Id") == old_id,
                "ROLLBACK_PARKED_OLD_MANAGER_MISSING")
        require(parked.get("State", {}).get("Running") is False,
                "ROLLBACK_PARKED_OLD_MANAGER_RUNNING")
        _run_docker("rename", deploy.PARKED_NAME, contract.MANAGER_NAME)
        restored = deploy.docker_json("container", contract.MANAGER_NAME)
        require(restored.get("Id") == old_id, "ROLLBACK_RENAME_OLD_MANAGER_ID_MISMATCH")

    try:
        window.resume_original_manager(origin, broker_origin)
    except (snapshot.Stop, window.WindowStop, OSError, KeyError) as error:
        raise RecoveryStop("OLD_MANAGER_RESTART_FAILED") from error
    deploy.broker_unchanged(
        broker_origin,
        deploy.docker_json("container", contract.BROKER_NAME),
    )
    _write_rollback_state(private, state, "PASS")
    print("ORIGINAL_MANAGER_ROLLBACK=PASS")
    print("BROKER_UNCHANGED=PASS")
    print("FAILED_FRESH_STATE_PRESERVED_PRIVATE=true")
    print("AUTO_RETRY=false")


def supervised_stop_post(private: Path) -> None:
    state = load_state(private)
    if state is None or state.get("committed") is not True:
        recover_original(private)
        return
    try:
        recover_original(private)
        return
    except (RecoveryStop, deploy.DeployStop, contract.CutoverStop, snapshot.Stop,
            window.WindowStop, OSError, ValueError, KeyError):
        interrupted = dict(state)
        interrupted["committed"] = False
        interrupted["supervised_post_commit_verification_failed"] = True
        deploy._atomic_json(private / deploy.STATE_FILE, interrupted)
    recover_original(private)
    raise RecoveryStop("POST_COMMIT_SUPERVISOR_VERIFICATION_FAILED_ROLLED_BACK")


def rollback_after_operator_final_check_failure(private: Path) -> None:
    state = load_state(private)
    require(state is not None and state.get("committed") is True,
            "FINAL_CHECK_ROLLBACK_STATE_NOT_COMMITTED")
    state = dict(state)
    state["committed"] = False
    state["operator_final_check_failed"] = True
    deploy._atomic_json(private / deploy.STATE_FILE, state)
    recover_original(private)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--systemd-stop-post", action="store_true")
    args = parser.parse_args()
    private = snapshot.private_root(args.private_root)
    if args.systemd_stop_post:
        supervised_stop_post(private)
    else:
        recover_original(private)


if __name__ == "__main__":
    try:
        main()
    except (
        RecoveryStop,
        deploy.DeployStop,
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
            (RecoveryStop, deploy.DeployStop, snapshot.Stop, window.WindowStop, contract.CutoverStop),
        ):
            code = str(error)
        else:
            code = type(error).__name__
        print("FRESH_MANAGER_RECOVERY=FAILED_STOP_MANUAL:" + code, file=sys.stderr)
        raise SystemExit(1)
