from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import sys
from pathlib import Path

import cold_snapshot as snapshot
import fresh_manager_deploy as deploy

SYSTEMD_START_TIMEOUT_SECONDS = 420
SYSTEMD_STOP_POST_TIMEOUT_SECONDS = 120

UNIT_NAME = "n3w-p4-fresh-manager-r4-deploy.service"
UNIT_DEST = Path("/run/systemd/system") / UNIT_NAME
STAGE_DIR = "p4-fresh-manager-deploy-r4"
PROTECTED_SCRIPTS = (
    "cold_snapshot.py",
    "business_snapshot.py",
    "controlled_window.py",
    "cutover_contract.py",
    "fresh_state_contract.py",
    "fresh_manager_deploy.py",
    "fresh_manager_recovery.py",
    "fresh_manager_operator.py",
    "fresh_manager_systemd_unit.py",
    "r3_forensic_seal.py",
    "r4_shadow_stable_fingerprint.py",
)
SAFE_ABSOLUTE = re.compile(r"^/[A-Za-z0-9_./+-]+$")


def check_source(private: Path, stage: Path, python: Path) -> None:
    snapshot.private_root(str(private))
    snapshot.require(
        stage == private / STAGE_DIR
        and stage.is_dir()
        and not stage.is_symlink()
        and stat.S_IMODE(stage.stat().st_mode) == 0o700,
        "FRESH_DEPLOY_STAGE_INVALID",
    )
    for name in PROTECTED_SCRIPTS:
        file = stage / name
        snapshot.require(
            file.is_file()
            and not file.is_symlink()
            and stat.S_IMODE(file.stat().st_mode) == 0o600,
            "FRESH_DEPLOY_SCRIPT_MISSING_OR_INSECURE",
        )
    snapshot.require(
        python.is_absolute()
        and python.is_file()
        and os.access(python, os.X_OK),
        "PYTHON_EXECUTABLE_INVALID",
    )
    for value in (str(private), str(stage), str(python)):
        snapshot.require(
            SAFE_ABSOLUTE.fullmatch(value) is not None,
            "UNSAFE_SYSTEMD_EXECUTION_PATH",
        )


def render_unit(private: Path, stage: Path, python: Path) -> str:
    check_source(private, stage, python)
    return (
        "[Unit]\n"
        "Description=N3W P4 fresh Manager one-shot deploy with fail-closed rollback\n"
        "Requires=docker.service\n"
        "After=docker.service\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "User=root\n"
        "Group=root\n"
        f"TimeoutStartSec={SYSTEMD_START_TIMEOUT_SECONDS}\n"
        f"TimeoutStopSec={SYSTEMD_STOP_POST_TIMEOUT_SECONDS}\n"
        "KillMode=control-group\n"
        "SendSIGKILL=yes\n"
        "Restart=no\n"
        "UMask=0077\n"
        f"ExecStart={python} -B {stage / 'fresh_manager_deploy.py'} execute "
        f"--private-root {private} "
        f"--authorization-id {deploy.AUTHORIZATION_ID} "
        "--permit-live-manager-replacement --systemd-supervised\n"
        f"ExecStopPost={python} -B {stage / 'fresh_manager_recovery.py'} "
        f"--private-root {private} --systemd-stop-post\n"
        "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight",))
    parser.add_argument("--private-root", required=True)
    args = parser.parse_args()
    private = snapshot.private_root(args.private_root)
    stage = private / STAGE_DIR
    python = Path(sys.executable).resolve()
    text = render_unit(private, stage, python)
    print("FRESH_MANAGER_SYSTEMD_TEMPLATE=PASS")
    print("UNIT_CONTENT_SHA256=" + hashlib.sha256(text.encode()).hexdigest())
    print("SYSTEMD_UNIT_INSTALLED=false")
    print("MANAGER_REPLACEMENT_EXECUTED=false")


if __name__ == "__main__":
    try:
        main()
    except (snapshot.Stop, OSError, ValueError) as error:
        code = str(error) if isinstance(error, snapshot.Stop) else type(error).__name__
        print("FRESH_MANAGER_SYSTEMD_TEMPLATE=STOP:" + code, file=sys.stderr)
        raise SystemExit(1)
