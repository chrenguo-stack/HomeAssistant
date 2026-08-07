from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from greenhouse_manager.ops.registration_cli import _parser, main
from greenhouse_manager.runtime.n3w_path_lease import N3wPathLeaseCoordinator, PathLeasePolicy, PathOwner
from greenhouse_manager.runtime.n3w_relay_authorization import REVOKED_GATEWAY_SENTINEL
from greenhouse_manager.runtime.registration import RegistrationRegistry
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
LOGICAL_LOCATION_ID = "greenhouse-bed-01"
N3W_NODE_ID = "node_01hzx7aq5fj3"
N3W_ACTIVE_NODE_ID = "gh-n1-a9f2f8"
N3W_BOOT_ID = "boot_0000000000000001"
N3W_GATEWAY_ID = "gateway_01hzx7aq5fj3"
N3W_KEY_FILE = "node_01hzx7aq5fj3-epoch-1.key"
N3W_KEY = bytes(range(32))


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


def active_database(tmp_path: Path) -> Path:
    path = database(tmp_path)
    with RegistrationRegistry(path) as registry:
        registry.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id=N3W_ACTIVE_NODE_ID,
            logical_location_id=LOGICAL_LOCATION_ID,
        )
    return path


def run_cli(path: Path, *args: str) -> tuple[int, object, str]:
    stdout = StringIO()
    stderr = StringIO()
    code = main(["--db", str(path), *args], stdout=stdout, stderr=stderr)
    document = json.loads(stdout.getvalue()) if stdout.getvalue() else None
    return code, document, stderr.getvalue()


def relay_authorization_store(tmp_path: Path) -> tuple[Path, Path]:
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    os.chmod(key_dir, 0o700)
    key_path = key_dir / N3W_KEY_FILE
    key_path.write_bytes(N3W_KEY)
    os.chmod(key_path, 0o600)

    path = tmp_path / "relay-authorization.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE n3w_relay_meta (schema_version INTEGER NOT NULL);
            CREATE TABLE n3w_relay_nodes (
                node_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL
            );
            CREATE TABLE n3w_relay_gateway_nodes (
                gateway_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                PRIMARY KEY (gateway_id, node_id)
            );
            CREATE TABLE n3w_relay_key_epochs (
                node_id TEXT NOT NULL,
                key_epoch INTEGER NOT NULL,
                key_file TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                PRIMARY KEY (node_id, key_epoch)
            );
            """
        )
        connection.execute("INSERT INTO n3w_relay_meta VALUES (1)")
        connection.execute(
            "INSERT INTO n3w_relay_nodes VALUES (?, 1)",
            (N3W_NODE_ID,),
        )
        connection.execute(
            "INSERT INTO n3w_relay_gateway_nodes VALUES (?, ?, 1)",
            (N3W_GATEWAY_ID, N3W_NODE_ID),
        )
        connection.execute(
            "INSERT INTO n3w_relay_key_epochs VALUES (?, 1, ?, 1)",
            (N3W_NODE_ID, N3W_KEY_FILE),
        )
    os.chmod(path, 0o600)
    return path, key_dir


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
        path,
        "approve",
        HARDWARE_ID,
        PAIRING_ID,
        "--node-id",
        "gh-n1-a9f2f8",
        "--logical-location-id",
        LOGICAL_LOCATION_ID,
    )

    assert code == 0
    assert error == ""
    assert document["result"] == "operator_approved"
    assert document["credential_issued"] is False
    assert document["registration"]["node_id"] == "gh-n1-a9f2f8"
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


def test_cli_does_not_expose_node_id_reuse_flags() -> None:
    help_text = _parser().format_help()
    assert "--reuse-retired-node-id" not in help_text
    assert "--private-identity-bound" not in help_text


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


def test_n3w_relay_authz_audit_is_secret_free_and_registration_independent(
    tmp_path: Path,
) -> None:
    authz_db, key_dir = relay_authorization_store(tmp_path)
    unused_registration = tmp_path / "registration-does-not-exist.sqlite3"

    code, document, error = run_cli(
        unused_registration,
        "n3w-relay-authz-audit",
        "--authz-db",
        str(authz_db),
        "--key-dir",
        str(key_dir),
    )

    assert code == 0
    assert error == ""
    assert document["schema"] == "gh.n3w-relay-authorization-audit/1"
    assert document["status"] == "passed"
    assert document["active_node_count"] == 1
    assert document["enabled_gateway_grant_count"] == 1
    assert document["enabled_key_epoch_count"] == 1
    assert document["secret_values_included"] is False
    assert document["mutated"] is False
    serialized = json.dumps(document)
    assert N3W_KEY_FILE not in serialized
    assert N3W_KEY.hex() not in serialized
    assert not unused_registration.exists()


def test_n3w_relay_authz_audit_missing_store_fails_without_creating_it(
    tmp_path: Path,
) -> None:
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    os.chmod(key_dir, 0o700)
    missing = tmp_path / "missing-authz.sqlite3"

    code, document, error = run_cli(
        tmp_path / "unused-registration.sqlite3",
        "n3w-relay-authz-audit",
        "--authz-db",
        str(missing),
        "--key-dir",
        str(key_dir),
    )

    assert code == 3
    assert document is None
    assert "authorization_store_permissions_invalid" in error
    assert not missing.exists()


def test_n3w_relay_authz_init_is_registration_independent(tmp_path: Path) -> None:
    authz_db = tmp_path / "authz.sqlite3"
    key_dir = tmp_path / "app-keys"
    registration = tmp_path / "missing-registration.sqlite3"

    code, document, error = run_cli(
        registration,
        "n3w-relay-authz-init",
        "--authz-db",
        str(authz_db),
        "--key-dir",
        str(key_dir),
    )

    assert code == 0
    assert error == ""
    assert document["schema_version"] == 2
    assert document["secret_values_included"] is False
    assert authz_db.exists()
    assert key_dir.is_dir()
    assert not registration.exists()


def test_n3w_relay_lifecycle_cli_requires_active_registration_and_never_prints_key(
    tmp_path: Path,
) -> None:
    registration = active_database(tmp_path)
    authz_db = tmp_path / "authz.sqlite3"
    key_dir = tmp_path / "app-keys"
    key_input = tmp_path / "key-input.bin"
    key_input.write_bytes(N3W_KEY)
    os.chmod(key_input, 0o600)

    assert (
        run_cli(
            registration,
            "n3w-relay-authz-init",
            "--authz-db",
            str(authz_db),
            "--key-dir",
            str(key_dir),
        )[0]
        == 0
    )
    code, grant, error = run_cli(
        registration,
        "n3w-relay-authz-grant",
        "--authz-db",
        str(authz_db),
        "--key-dir",
        str(key_dir),
        "--gateway-id",
        N3W_GATEWAY_ID,
        "--node-id",
        N3W_ACTIVE_NODE_ID,
    )
    assert code == 0
    assert error == ""
    assert grant["secret_values_included"] is False

    code, staged, error = run_cli(
        registration,
        "n3w-relay-key-stage",
        "--authz-db",
        str(authz_db),
        "--key-dir",
        str(key_dir),
        "--node-id",
        N3W_ACTIVE_NODE_ID,
        "--key-input",
        str(key_input),
    )
    assert code == 0
    assert error == ""
    assert staged["key_epoch"] == 1
    assert N3W_KEY.hex() not in json.dumps(staged)
    assert str(key_input) not in json.dumps(staged)

    code, activated, error = run_cli(
        registration,
        "n3w-relay-key-activate",
        "--authz-db",
        str(authz_db),
        "--key-dir",
        str(key_dir),
        "--node-id",
        N3W_ACTIVE_NODE_ID,
        "--key-epoch",
        "1",
    )
    assert code == 0
    assert error == ""
    assert activated["status"] == "passed"

    code, audit, error = run_cli(
        tmp_path / "unused-registration.sqlite3",
        "n3w-relay-authz-audit",
        "--authz-db",
        str(authz_db),
        "--key-dir",
        str(key_dir),
    )
    assert code == 0
    assert error == ""
    assert audit["enabled_key_epoch_count"] == 1
    assert audit["schema_version"] == 2


def test_n3w_relay_grant_rejects_pending_or_unassigned_node(tmp_path: Path) -> None:
    registration = database(tmp_path)
    authz_db = tmp_path / "authz.sqlite3"
    key_dir = tmp_path / "app-keys"
    assert (
        run_cli(
            registration,
            "n3w-relay-authz-init",
            "--authz-db",
            str(authz_db),
            "--key-dir",
            str(key_dir),
        )[0]
        == 0
    )

    code, document, error = run_cli(
        registration,
        "n3w-relay-authz-grant",
        "--authz-db",
        str(authz_db),
        "--key-dir",
        str(key_dir),
        "--gateway-id",
        N3W_GATEWAY_ID,
        "--node-id",
        N3W_ACTIVE_NODE_ID,
    )
    assert code == 3
    assert document is None
    assert "node_id_not_active" in error


def test_n3w_relay_revoke_cli_invalidates_matching_path_owner(tmp_path: Path) -> None:
    registration = active_database(tmp_path)
    authz_db = tmp_path / "authz.sqlite3"
    key_dir = tmp_path / "app-keys"
    replay_db = tmp_path / "replay.sqlite3"
    key_input = tmp_path / "key-input.bin"
    key_input.write_bytes(N3W_KEY)
    os.chmod(key_input, 0o600)

    for command in (
        (
            "n3w-relay-authz-init",
            "--authz-db",
            str(authz_db),
            "--key-dir",
            str(key_dir),
        ),
        (
            "n3w-relay-authz-grant",
            "--authz-db",
            str(authz_db),
            "--key-dir",
            str(key_dir),
            "--gateway-id",
            N3W_GATEWAY_ID,
            "--node-id",
            N3W_ACTIVE_NODE_ID,
        ),
        (
            "n3w-relay-key-stage",
            "--authz-db",
            str(authz_db),
            "--key-dir",
            str(key_dir),
            "--node-id",
            N3W_ACTIVE_NODE_ID,
            "--key-input",
            str(key_input),
        ),
        (
            "n3w-relay-key-activate",
            "--authz-db",
            str(authz_db),
            "--key-dir",
            str(key_dir),
            "--node-id",
            N3W_ACTIVE_NODE_ID,
            "--key-epoch",
            "1",
        ),
    ):
        assert run_cli(registration, *command)[0] == 0

    with ReplayRegistry(replay_db) as replay:
        path = N3wPathLeaseCoordinator(
            replay_registry=replay,
            policy=PathLeasePolicy(
                stability_window_s=0,
                minimum_distinct_frames=2,
                lease_ttl_s=10,
                old_path_grace_s=1,
            ),
            ingress_allowed=lambda _node_id: True,
        )
        assert (
            path.process(
                node_id=N3W_ACTIVE_NODE_ID,
                boot_id=N3W_BOOT_ID,
                seq=1,
                owner=PathOwner("relay", N3W_GATEWAY_ID),
                now=datetime.now(UTC),
            ).status
            == "accepted"
        )

    code, document, error = run_cli(
        registration,
        "n3w-relay-authz-revoke-grant",
        "--authz-db",
        str(authz_db),
        "--key-dir",
        str(key_dir),
        "--gateway-id",
        N3W_GATEWAY_ID,
        "--node-id",
        N3W_ACTIVE_NODE_ID,
        "--replay-db",
        str(replay_db),
    )
    assert code == 0
    assert error == ""
    assert document["recovery_pending"] is False
    with sqlite3.connect(replay_db) as connection:
        row = connection.execute(
            "SELECT active_gateway_id,lease_expires_at FROM n3w_path_leases WHERE node_id=?",
            (N3W_ACTIVE_NODE_ID,),
        ).fetchone()
    assert row == (REVOKED_GATEWAY_SENTINEL, "1970-01-01T00:00:00.000Z")


def test_n3w_key_input_requires_private_regular_file(tmp_path: Path) -> None:
    registration = active_database(tmp_path)
    authz_db = tmp_path / "authz.sqlite3"
    key_dir = tmp_path / "app-keys"
    key_input = tmp_path / "key-input.bin"
    key_input.write_bytes(N3W_KEY)
    os.chmod(key_input, 0o644)
    assert (
        run_cli(
            registration,
            "n3w-relay-authz-init",
            "--authz-db",
            str(authz_db),
            "--key-dir",
            str(key_dir),
        )[0]
        == 0
    )

    code, document, error = run_cli(
        registration,
        "n3w-relay-key-stage",
        "--authz-db",
        str(authz_db),
        "--key-dir",
        str(key_dir),
        "--node-id",
        N3W_ACTIVE_NODE_ID,
        "--key-input",
        str(key_input),
    )
    assert code == 3
    assert document is None
    assert "key_input_permissions_invalid" in error
    assert N3W_KEY.hex() not in error
