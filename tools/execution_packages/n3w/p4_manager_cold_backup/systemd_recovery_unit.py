from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import sys
from pathlib import Path

import cold_snapshot as snapshot

UNIT_NAME = "n3w-p4-manager-cold-backup.service"
STAGE_DIR = "p4-reviewed-controlled-backup-r4"
PROTECTED_SCRIPTS = ("cold_snapshot.py", "controlled_window.py", "emergency_resume.py")
SAFE_ABSOLUTE = re.compile(r"^/[A-Za-z0-9_./+-]+$")


def check_source(private: Path, stage: Path, python: Path) -> None:
    snapshot.private_root(str(private))
    snapshot.require(
        stage == private / STAGE_DIR and stage.is_dir() and not stage.is_symlink(),
        "STAGE_DIR_INVALID",
    )
    snapshot.require(
        stat.S_IMODE(stage.stat().st_mode) == 0o700,
        "STAGE_DIR_MODE_INVALID",
    )
    for name in PROTECTED_SCRIPTS:
        file = stage / name
        snapshot.require(
            file.is_file()
            and not file.is_symlink()
            and stat.S_IMODE(file.stat().st_mode) == 0o600,
            "PROTECTED_SCRIPT_MISSING_OR_INSECURE",
        )
    snapshot.require(
        python.is_absolute() and python.is_file() and os.access(python, os.X_OK),
        "PYTHON_EXECUTABLE_INVALID",
    )
    for value in (str(private), str(stage), str(python)):
        snapshot.require(SAFE_ABSOLUTE.fullmatch(value) is not None, "UNSAFE_UNIT_PATH")


def render_unit(private: Path, stage: Path, python: Path) -> str:
    check_source(private, stage, python)
    return (
        "[Unit]\n"
        "Description=N3W P4 original Manager cold snapshot with independent recovery\n"
        "Requires=docker.service\n"
        "After=docker.service\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "User=root\n"
        "Group=root\n"
        "TimeoutStartSec=240\n"
        "TimeoutStopSec=90\n"
        "KillMode=control-group\n"
        "SendSIGKILL=yes\n"
        "Restart=no\n"
        "UMask=0077\n"
        f"ExecStart={python} -B {stage / 'controlled_window.py'} execute --private-root {private} --permit-manager-stop\n"
        f"ExecStopPost={python} -B {stage / 'emergency_resume.py'} --private-root {private}\n"
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
    assert "ExecStopPost=" in text
    assert "ExecStart=" in text
    print("T1_SYSTEMD_SERVICE_RECOVERY_TEMPLATE=PASS")
    print("UNIT_CONTENT_SHA256=" + hashlib.sha256(text.encode()).hexdigest())
    print("T1_SYSTEMD_SERVICE_INSTALLED=false")
    print("MANAGER_STOP_NOT_EXECUTED=true")


if __name__ == "__main__":
    try:
        main()
    except (snapshot.Stop, OSError, ValueError) as error:
        code = str(error) if isinstance(error, snapshot.Stop) else type(error).__name__
        print(f"P4_SYSTEMD_UNIT=STOP:{code}", file=sys.stderr)
        raise SystemExit(1)
