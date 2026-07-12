from __future__ import annotations

import subprocess
from pathlib import Path


def _script() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "run_t1_broker_identity_activation_execution_preparation_packet.sh"
    )


def _request_cli() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "run_t1_broker_identity_production_activation_orchestrator.py"
    )


def test_shell_script_has_valid_syntax() -> None:
    completed = subprocess.run(
        ["bash", "-n", str(_script())],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_help_documents_three_inputs_and_non_mutating_boundary() -> None:
    completed = subprocess.run(
        ["bash", str(_script()), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "RUNTIME_ARTIFACT_DIRECTORY" in completed.stdout
    assert "AUTHORIZATION_CONFIRMATION" in completed.stdout
    assert "OUTPUT_DIRECTORY" in completed.stdout
    assert "does not claim or" in completed.stdout
    assert "restart a service" in completed.stdout


def test_packet_creates_bound_materials_but_has_no_live_execution() -> None:
    content = _script().read_text(encoding="utf-8")
    assert "activation_readiness_authorization.py\" \\\n  create" in content
    assert "activation_readiness_transaction_plan.py\" \\\n  build" in content
    assert "production_transaction_adapter_contract.py\" \\\n  \"$TRANSACTION_PLAN\"" in content
    assert "production_activation_orchestrator.py\" \\\n  request" in content
    assert "AUTHORIZATION_CREATED=true" in content
    assert "AUTHORIZATION_CLAIMED=false" in content
    assert "LIVE_ACTIVATION_EXECUTED=false" in content
    assert "CURRENT_SERVICES_MODIFIED=false" in content

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
        " execute ",
        "--enable-production-execution",
    )
    for token in forbidden:
        assert token not in content
    assert "docker inspect" in content
    assert 'cmp -s "$BEFORE" "$AFTER"' in content


def test_orchestrator_cli_exposes_request_only() -> None:
    completed = subprocess.run(
        ["python3", str(_request_cli()), "--help"],
        cwd=_request_cli().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "request" in completed.stdout
    assert "execute" not in completed.stdout
    assert "--apply" not in completed.stdout
    assert "--live" not in completed.stdout
