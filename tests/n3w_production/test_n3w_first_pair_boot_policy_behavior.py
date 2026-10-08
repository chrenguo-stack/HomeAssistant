import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_core"


def test_first_pair_boot_policy_behavior(tmp_path: Path) -> None:
    header = CORE / "n3w_first_pair_boot_policy.h"
    source = CORE / "n3w_core.cpp"
    assert header.exists(), "missing first-pair boot policy header"
    assert source.exists(), "missing product-core n3w_core.cpp"

    compiler = shutil.which("g++")
    assert compiler is not None

    test_source = (
        ROOT
        / "tests/n3w_production/n3w_first_pair_boot_policy_host_test.cpp"
    )
    executable = tmp_path / "n3w-first-pair-boot-policy-host-test"

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
            "-lmbedcrypto",
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)
