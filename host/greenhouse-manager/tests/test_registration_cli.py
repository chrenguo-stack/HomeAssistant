from __future__ import annotations

import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from greenhouse_manager.registration import RegistrationRegistry
from greenhouse_manager.registration_cli import main

HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"


def hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 3,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "simulator-M2.1c",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": 120345,
    }


def database(tmp_path: Path) -> Path:
    path = tmp_path / "registration.sqlite3"
    with RegistrationRegistry(path) as registry:
        registry.observe_hello(hello(), now=datetime.now(UTC))
    return path


def run_cli(path: Path, *args: str) -> tuple[int, object, str]:
    stdout = StringIO()
    stderr = StringIO()
    code = main(["--db", str(path), *args], stdout=stdout, stderr=stderr)
    document = json.loads(stdout.getvalue()) if stdout.getvalue() else None
    return code, document, stderr.getvalue()


def test_lists_pending_registration_without_nonce(tmp_path: Path) -> None:
    code, document, error = run_cli(database(tmp_path), "list")

    assert code == 0
    assert error == ""
    assert document[0]["hardware_id"] == HARDWARE_ID
    assert document[0]["state"] == "pending"
    assert "node_nonce" not in document[0]


def test_approve_is_explicitly_not_credential_issuance(tmp_path: Path) -> None:
    path = database(tmp_path)

    code, document, error = run_cli(
        path, "approve", HARDWARE_ID, PAIRING_ID, "--node-id", "gh-n1-a9f2f8"
    )

    assert code == 0
    assert error == ""
    assert document["result"] == "operator_approved"
    assert document["credential_issued"] is False
    assert document["registration"]["node_id"] == "gh-n1-a9f2f8"


def test_lists_secret_free_audit_events(tmp_path: Path) -> None:
    path = database(tmp_path)
    run_cli(path, "reject", HARDWARE_ID, PAIRING_ID, "--reason", "user_rejected")

    code, document, error = run_cli(path, "events", "--hardware-id", HARDWARE_ID)

    assert code == 0
    assert error == ""
    assert [event["event"] for event in document] == ["operator_rejected", "hello_created"]
    serialized = json.dumps(document)
    assert "node_nonce" not in serialized
    assert "pairing_pop" not in serialized


def test_missing_database_fails_without_creating_it(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"

    code, document, error = run_cli(path, "list")

    assert code == 2
    assert document is None
    assert "does not exist" in error
    assert not path.exists()
