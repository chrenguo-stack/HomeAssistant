import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"


def test_direct_recovery_liveness_policy_behavior(tmp_path: Path) -> None:
    header = CORE / "n3w_direct_recovery_policy.h"
    source = CORE / "n3w_direct_recovery_policy.cpp"
    assert header.exists(), "missing production Direct recovery policy header"
    assert source.exists(), "missing production Direct recovery policy source"

    compiler = shutil.which("g++")
    assert compiler is not None

    test_source = (
        ROOT
        / "tests/n3w_phase4/n3w_direct_recovery_liveness_host_test.cpp"
    )
    executable = tmp_path / "n3w-direct-recovery-liveness-host-test"

    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(CORE),
            str(source),
            str(test_source),
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)
