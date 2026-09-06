from pathlib import Path
import shutil
import subprocess


def test_shared_c_operation_decisions_execute_in_minimal_harness() -> None:
    cc = shutil.which("cc")
    assert cc is not None, "a C compiler is required for the diagnostic C harness"
    root = Path(__file__).parents[2]
    source_dir = root / "diagnostics/n3w_r1r4_usb_console_evidence/main"
    harness = Path(__file__).parent / "c_harness/test_operation_completion_harness.c"
    output = Path(__file__).parent / "c_harness/operation_completion_harness"
    try:
        subprocess.run(
            [cc, "-std=c11", "-Wall", "-Werror", "-I", str(source_dir), str(harness), "-o", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run([str(output)], check=True, capture_output=True, text=True)
    finally:
        output.unlink(missing_ok=True)
