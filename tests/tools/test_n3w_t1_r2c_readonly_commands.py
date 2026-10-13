from __future__ import annotations

import pytest
from n3w_t1_r2c_readonly_commands import (
    ReadonlyCommandError,
    build_contract_argv,
    run_contract_command,
)


def test_fixed_contract_commands_have_exact_argv() -> None:
    assert build_contract_argv("C1_SYSTEMD") == ("systemd", "--version")
    assert build_contract_argv("C1_ARCH") == ("uname", "-m")
    assert build_contract_argv("C2_PYTHON") == ("python3", "-B", "--version")
    assert build_contract_argv("C5_MACHINE_ID_MOUNT") == (
        "findmnt",
        "--noheadings",
        "--mountpoint",
        "/etc/machine-id",
        "--output",
        "TARGET,FSTYPE,OPTIONS",
    )
    assert build_contract_argv("C6_LISTEN") == ("ss", "-H", "-ltn")


def test_dpkg_commands_require_preapproved_dynamic_values() -> None:
    assert build_contract_argv(
        "C3_OWNER",
        value="/etc/os-release",
        approved_paths={"/etc/os-release"},
    ) == ("dpkg-query", "-S", "/etc/os-release")
    assert build_contract_argv(
        "C3_LIST",
        value="systemd",
        approved_packages={"systemd"},
    ) == ("dpkg-query", "-L", "systemd")
    with pytest.raises(ReadonlyCommandError, match="unapproved_path"):
        build_contract_argv(
            "C3_OWNER",
            value="/etc/passwd",
            approved_paths={"/etc/os-release"},
        )
    with pytest.raises(ReadonlyCommandError, match="invalid_package"):
        build_contract_argv(
            "C3_LIST",
            value="systemd;id",
            approved_packages={"systemd;id"},
        )


def test_systemctl_requires_approved_unit_and_single_argv_value() -> None:
    argv = build_contract_argv(
        "C4_UNIT",
        value="ssh.service",
        approved_units={"ssh.service"},
    )
    assert argv[:4] == ("systemctl", "--no-pager", "show", "ssh.service")
    assert len(argv) == 5
    assert argv[4].startswith("--property=Id,Names,LoadState,")
    with pytest.raises(ReadonlyCommandError, match="unapproved_unit"):
        build_contract_argv(
            "C4_UNIT",
            value="network-online.target",
            approved_units={"ssh.service"},
        )
    with pytest.raises(ReadonlyCommandError, match="invalid_unit"):
        build_contract_argv(
            "C4_UNIT",
            value="ssh.service;id",
            approved_units={"ssh.service;id"},
        )


def test_unknown_or_extra_dynamic_command_input_fails_closed() -> None:
    with pytest.raises(ReadonlyCommandError, match="unknown_command_id"):
        build_contract_argv("C99_UNKNOWN", value="x")
    with pytest.raises(ReadonlyCommandError, match="unexpected_dynamic_value"):
        build_contract_argv("C1_ARCH", value="x")


def test_bounded_runner_executes_allowlisted_arch_query() -> None:
    result = run_contract_command("C1_ARCH")
    assert result.returncode == 0
    assert result.argv == ("uname", "-m")
    assert result.stdout.strip()
    assert result.stderr == b""


def test_bounded_runner_enforces_output_and_timeout_parameters() -> None:
    with pytest.raises(ReadonlyCommandError, match="command_output_limit"):
        run_contract_command("C1_ARCH", output_limit=1)
    with pytest.raises(ReadonlyCommandError, match="invalid_timeout"):
        run_contract_command("C1_ARCH", timeout_seconds=0)
