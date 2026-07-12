from __future__ import annotations

import subprocess
from pathlib import Path


def _script() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "run_t1_broker_identity_activation_decision_packet.sh"
    )


def test_shell_script_has_valid_syntax() -> None:
    completed = subprocess.run(
        ["bash", "-n", str(_script())],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_help_is_non_mutating_and_documents_four_inputs() -> None:
    completed = subprocess.run(
        ["bash", str(_script()), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "HANDOFF_DIRECTORY" in completed.stdout
    assert "STAGE_DIRECTORY" in completed.stdout
    assert "EXPECTED_RETAINED_TOPIC" in completed.stdout
    assert "OUTPUT_DIRECTORY" in completed.stdout
    assert "does not create" in completed.stdout
    assert "restart services" in completed.stdout


def test_packet_uses_authorization_request_only() -> None:
    content = _script().read_text(encoding="utf-8")
    assert "activation_readiness_authorization.py\" \\\n  request" in content
    assert "AUTHORIZATION_CREATED=false" in content
    assert "OPERATOR_DECISION_REQUIRED=true" in content
    assert "--confirmation" not in content
    assert " authorization.py\" \\\n  create" not in content


def test_packet_contains_no_live_mutation_command() -> None:
    content = _script().read_text(encoding="utf-8")
    forbidden = (
        "docker restart",
        "docker exec",
        "docker cp",
        "docker create",
        "docker start",
        "docker stop",
        "docker rm",
        "docker compose",
        "systemctl",
        "ssh ",
        "--execute",
        "--apply",
        "--live",
    )
    for token in forbidden:
        assert token not in content
    assert "docker inspect" in content
    assert 'cmp -s "$BEFORE" "$AFTER"' in content
    assert "CURRENT_SERVICES_MODIFIED=false" in content
    assert "PRODUCTION_DRIVER_INSTALLED=false" in content
    assert "EXECUTION_ENABLED=false" in content
