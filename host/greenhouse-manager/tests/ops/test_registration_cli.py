from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from greenhouse_manager.ops.registration_cli import _parser, main
from greenhouse_manager.runtime.registration import RegistrationRegistry
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
LOGICAL_LOCATION_ID = "greenhouse-bed-01"
N3W_NODE_ID = "node_01hzx7aq5fj3"
N3W_BOOT_ID = "boot_0000000000000001"


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


def test_approve_uses_manager_assigned_node_id_and_does_not_issue_credentials(
    tmp_path: Path,
) -> None:
    path = database(tmp_path)

    code, document, error = run_cli(
        path,
        "approve",
        HARDWARE_ID,
        PAIRING_ID,
        "--logical-location-id",
        LOGICAL_LOCATION_ID,
    )

    assert code == 0
    assert error == ""
    assert document["result"] == "operator_approved"
    assert document["credential_issued"] is False
    assert document["node_id_assignment"] == "manager_automatic"
    assert re.fullmatch(r"node_[0-9a-f]{32}", document["registration"]["node_id"])
    assert document["registration"]["logical_location_id"] == LOGICAL_LOCATION_ID


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


def test_cli_does_not_expose_retired_node_id_admin_flags() -> None:
    parser = _parser()
    root_help = parser.format_help()
    command_action = next(action for action in parser._actions if action.dest == "command")
    approve_help = command_action.choices["approve"].format_help()

    assert "--node-id" not in approve_help
    assert "--reuse-retired-node-id" not in root_help
    assert "--private-identity-bound" not in root_help


def test_n3w_replay_audit_uses_existing_registration_cli_entrypoint(tmp_path: Path) -> None:
    replay_path = tmp_path / "n3w-replay.sqlite3"
    missing_registration_path = tmp_path / "registration-does-not-exist.sqlite3"
    with ReplayRegistry(replay_path):
        pass

    code, document, error = run_cli(
        missing_registration_path,
        "n3w-replay-audit",
        "--replay-db",
        str(replay_path),
    )

    assert code == 0
    assert error == ""
    assert document["schema"] == "gh.n3w-replay-registry-audit/1"
    assert document["status"] == "passed"
    assert document["node_count"] == 0
    assert replay_path.exists()
    assert not missing_registration_path.exists()


def test_n3w_replay_audit_missing_db_fails_without_creating_it(tmp_path: Path) -> None:
    replay_path = tmp_path / "missing-replay.sqlite3"

    code, document, error = run_cli(
        tmp_path / "unused-registration.sqlite3",
        "n3w-replay-audit",
        "--replay-db",
        str(replay_path),
    )

    assert code == 3
    assert document is None
    assert "replay_registry_unavailable" in error
    assert not replay_path.exists()


def test_n3w_replay_inspect_is_read_only(tmp_path: Path) -> None:
    replay_path = tmp_path / "n3w-replay.sqlite3"
    with ReplayRegistry(replay_path) as registry:
        registry.commit(node_id=N3W_NODE_ID, boot_id=N3W_BOOT_ID, seq=1)

    code, document, error = run_cli(
        tmp_path / "unused-registration.sqlite3",
        "n3w-replay-inspect",
        "--replay-db",
        str(replay_path),
        "--node-id",
        N3W_NODE_ID,
        "--boot-id",
        N3W_BOOT_ID,
        "--seq",
        "2",
    )

    assert code == 0
    assert error == ""
    assert document["status"] == "ready"
    assert document["highest_session_hex"] == "0000000000000001"
    assert document["mutated"] is False

    with ReplayRegistry(replay_path) as registry:
        assert (
            registry.inspect(
                node_id=N3W_NODE_ID,
                boot_id=N3W_BOOT_ID,
                seq=2,
            ).status
            == "ready"
        )


def test_n3w_replay_inspect_rejects_invalid_boot_session(tmp_path: Path) -> None:
    replay_path = tmp_path / "n3w-replay.sqlite3"
    with ReplayRegistry(replay_path):
        pass

    code, document, error = run_cli(
        tmp_path / "unused-registration.sqlite3",
        "n3w-replay-inspect",
        "--replay-db",
        str(replay_path),
        "--node-id",
        N3W_NODE_ID,
        "--boot-id",
        "boot_0000000000000000",
        "--seq",
        "1",
    )

    assert code == 3
    assert document is None
    assert "boot_session_invalid" in error
