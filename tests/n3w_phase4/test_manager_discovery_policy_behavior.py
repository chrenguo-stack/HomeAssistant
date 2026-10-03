import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"


def test_manager_discovery_policy_behavior(tmp_path: Path) -> None:
    header = CORE / "n3w_manager_discovery.h"
    source = CORE / "n3w_manager_discovery_policy.cpp"
    assert header.exists()
    assert source.exists()

    compiler = shutil.which("g++")
    assert compiler is not None

    test_source = ROOT / "tests/n3w_phase4/n3w_manager_discovery_policy_host_test.cpp"
    executable = tmp_path / "n3w-manager-discovery-policy-host-test"

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
