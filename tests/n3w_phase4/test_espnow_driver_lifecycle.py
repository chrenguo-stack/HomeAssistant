import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
STUBS = ROOT / "tests/n3w_phase4/espnow_driver_host_stubs"


def test_real_espnow_driver_partial_init_lifecycle(tmp_path: Path) -> None:
    compiler = shutil.which("g++")
    assert compiler is not None
    executable = tmp_path / "n3w-espnow-driver-lifecycle-host-test"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DUSE_ESP32",
            "-I",
            str(STUBS),
            "-I",
            str(CORE),
            str(CORE / "n3w_espnow_driver.cpp"),
            str(ROOT / "tests/n3w_phase4/n3w_espnow_driver_lifecycle_host_test.cpp"),
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)
