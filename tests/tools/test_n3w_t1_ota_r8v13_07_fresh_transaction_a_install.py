from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_FRESH_TRANSACTION_A_INSTALL_TO_TERMINAL_20261124_01.sh"
)


def test_retired_shell_executor_cannot_execute_install_path() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "RETIRED_EXECUTOR=" in text
    assert "DO_NOT_EXECUTE_RETIRED_GATE=true" in text
    assert "N3W_T1_R8V13_07_THIN_REENTRY_AWARE_INSTALL_TO_TERMINAL_20261124_01.py" in text
    assert "exit 64" in text
    assert "--maintenance-submit-approved-release" not in text
    assert "--issue-install-authority" not in text
    assert "--resume-pending" not in text
