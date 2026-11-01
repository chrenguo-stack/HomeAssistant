from __future__ import annotations

import subprocess
from pathlib import Path


def _script() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "run_t1_broker_identity_production_activation_packet.sh"
    )


def _execute_cli() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "run_t1_broker_identity_production_activation_execute.py"
    )


def test_shell_script_has_valid_syntax() -> None:
    completed = subprocess.run(
        ["bash", "-n", str(_script())],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_help_explicitly_describes_live_scope() -> None:
    completed = subprocess.run(
        ["bash", str(_script()), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    for name in (
        "PREPARATION_ARTIFACT_DIRECTORY",
        "RUNTIME_ARTIFACT_DIRECTORY",
        "HANDOFF_DIRECTORY",
        "EXPECTED_RETAINED_TOPIC",
        "EXECUTION_CONFIRMATION",
        "TRANSACTION_DIRECTORY",
    ):
        assert name in completed.stdout
    assert "live operation" in completed.stdout
    assert "Mosquitto is restarted" in completed.stdout
    assert "anonymous compatibility remains enabled" in completed.stdout


def test_packet_has_explicit_double_opt_in_and_no_homeassistant_write() -> None:
    content = _script().read_text(encoding="utf-8")
    assert "--execution-confirmation \"$CONFIRMATION\"" in content
    assert "--enable-production-execution" in content
    assert "production_activation_execute.py" in content
    assert "HOMEASSISTANT_RECONFIGURED=false" in content
    assert "NODE_CREDENTIALS_DELIVERED=false" in content
    assert "PRESERVE_ANONYMOUS=true" in content
    assert "ANONYMOUS_CLOSURE_ENABLED=false" in content
    assert "docker inspect mosquitto greenhouse-manager homeassistant" in content

    forbidden = (
        "docker exec",
        "docker cp",
        "docker create",
        "docker start",
        "docker stop",
        "docker rm",
        "docker compose",
        "systemctl",
        "ssh ",
        ".storage",
    )
    for token in forbidden:
        assert token not in content


def test_execute_cli_requires_explicit_enable_flag() -> None:
    completed = subprocess.run(
        ["python3", str(_execute_cli()), "--help"],
        cwd=_execute_cli().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--execution-confirmation" in completed.stdout
    assert "--enable-production-execution" in completed.stdout
    assert "--expected-retained-topic" in completed.stdout


def test_execute_cli_without_arguments_cannot_run() -> None:
    completed = subprocess.run(
        ["python3", str(_execute_cli())],
        cwd=_execute_cli().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "authorization_file" in completed.stderr
