from __future__ import annotations

import base64
import hashlib
import io
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.ops import n3w_p4_pending_readonly, registration_cli
from greenhouse_manager.ops.n3w_p4_pending_readonly import (
    PendingReadonlyError,
    read_pending,
)
from greenhouse_manager.runtime.credential_lifecycle import CredentialLifecycleStore
from greenhouse_manager.runtime.registration import RegistrationRegistry
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

NOW = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
NEW = "ghw-c6-00000000ff00"
PAIR = "c83aeb0d-8f48-4a39-a34b-ea584a588475"


def hello(index: int, pair: str) -> dict:
    return {
        "schema": "gh.pair.hello/1",
        "hardware_id": f"ghw-c6-{index:012x}",
        "pairing_id": pair,
        "pairing_epoch": 1,
        "model": "greenhouse-wifi-c6",
        "fw_version": "phase4-simple",
        "node_nonce": base64.urlsafe_b64encode(bytes([49]) * 32).rstrip(b"=").decode(),
        "capabilities": ["simple-setup-secret"],
        "sent_at_ms": 1,
    }


@pytest.fixture
def dbs(tmp_path):
    reg = tmp_path / "registration.sqlite3"
    cred = tmp_path / "credential.sqlite3"
    replay = tmp_path / "replay.sqlite3"
    with RegistrationRegistry(reg) as registry:
        for i in range(5):
            pair = f"11111111-1111-4111-8111-{i:012x}"
            registry.observe_hello(hello(i, pair), now=NOW)
            registry.approve(f"ghw-c6-{i:012x}", pair, node_id=f"node_{i:04d}", now=NOW)
        registry.observe_hello(
            {
                **hello(0xff00, PAIR),
                "hardware_id": NEW,
            },
            now=NOW,
        )
    with CredentialLifecycleStore(cred):
        pass
    with ReplayRegistry(replay):
        pass
    return reg, cred, replay


def test_readonly_projection_is_six_identity_and_secret_free(dbs):
    result = read_pending(*dbs, now=NOW + timedelta(seconds=1))
    assert result["schema"] == "n3w.p4.terminal-pending-readonly/1"
    assert result["historical_count"] == 5
    assert result["new_count"] == 1
    assert result["hardware_sha256"] == hashlib.sha256(NEW.encode()).hexdigest()
    assert result["pairing_sha256"] == hashlib.sha256(PAIR.encode()).hexdigest()
    assert len(result["historical_hardware_hashes"]) == 5
    assert result["read_only"] is True
    assert result["replay_linkage_clear"] is True
    serialized = json.dumps(result)
    assert NEW not in serialized and PAIR not in serialized
    assert "setup_secret" not in serialized.lower()


def test_cli_does_not_construct_writable_registry_or_change_databases(dbs, monkeypatch):
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in dbs]

    def forbidden(*args, **kwargs):
        raise AssertionError("WRITABLE_REGISTRY_FORBIDDEN")

    monkeypatch.setattr(registration_cli, "RegistrationRegistry", forbidden)
    monkeypatch.setattr(
        registration_cli,
        "read_pending",
        lambda reg, cred, replay: read_pending(
            reg, cred, replay, now=NOW + timedelta(seconds=1)
        ),
    )
    output = io.StringIO()
    error = io.StringIO()
    status = registration_cli.main(
        [
            "--db", str(dbs[0]),
            "p4-pending-readonly",
            "--credential-db", str(dbs[1]),
            "--replay-db", str(dbs[2]),
        ],
        stdout=output,
        stderr=error,
    )
    assert status == 0
    assert json.loads(output.getvalue())["new_count"] == 1
    assert error.getvalue() == ""
    assert before == [(path.read_bytes(), path.stat().st_mtime_ns) for path in dbs]


def test_expired_session_fails_closed(dbs):
    with pytest.raises(PendingReadonlyError):
        read_pending(*dbs, now=NOW + timedelta(seconds=120))


def test_second_pending_fails_closed(dbs):
    with sqlite3.connect(dbs[0]) as connection:
        connection.execute(
            "UPDATE pairing_sessions SET state='pending' WHERE hardware_id=?",
            ("ghw-c6-000000000000",),
        )
    with pytest.raises(PendingReadonlyError):
        read_pending(*dbs, now=NOW)


def test_history_on_new_device_fails_closed(dbs):
    with sqlite3.connect(dbs[0]) as connection:
        connection.execute(
            "INSERT INTO registration_node_history(hardware_id,node_id,assigned_at) VALUES (?,?,?)",
            (NEW, "node_conflict", "2026-10-09T00:00:00Z"),
        )
    with pytest.raises(PendingReadonlyError):
        read_pending(*dbs, now=NOW)


def test_replay_orphan_node_fails_closed(dbs):
    with sqlite3.connect(dbs[2]) as connection:
        connection.execute(
            "INSERT INTO n3w_replay_state(node_id, highest_session_hex) VALUES (?,?)",
            ("node_orphan", "0123456789abcdef"),
        )
    with pytest.raises(PendingReadonlyError):
        read_pending(*dbs, now=NOW)


def test_schema_missing_or_unavailable_fails_closed(dbs, tmp_path):
    with pytest.raises(PendingReadonlyError):
        read_pending(dbs[0], dbs[1], tmp_path / "missing.sqlite3", now=NOW)
    with pytest.raises(PendingReadonlyError):
        read_pending(dbs[0], dbs[0], dbs[2], now=NOW)


def test_extra_identity_fails_closed(dbs):
    with sqlite3.connect(dbs[0]) as connection:
        connection.execute(
            "INSERT INTO registration_events(hardware_id,pairing_id,event,occurred_at) VALUES (?,?,?,?)",
            ("ghw-c6-00000000dd00", PAIR, "hello_created", "2026-10-09T00:00:00Z"),
        )
    with pytest.raises(PendingReadonlyError):
        read_pending(*dbs, now=NOW)


def test_multiple_sessions_on_new_identity_fail_closed(dbs):
    with sqlite3.connect(dbs[0]) as connection:
        connection.execute(
            """
            INSERT INTO pairing_sessions(
                pairing_id,hardware_id,pairing_epoch,model,fw_version,node_nonce,
                capabilities_json,state,first_seen_at,last_seen_at,expires_at
            )
            SELECT ?,hardware_id,pairing_epoch,model,fw_version,node_nonce,
                   capabilities_json,'rejected',first_seen_at,last_seen_at,expires_at
            FROM pairing_sessions WHERE pairing_id=?
            """,
            ("c9555499-8241-4d1a-896e-b61790eb3a5d", PAIR),
        )
    with pytest.raises(PendingReadonlyError):
        read_pending(*dbs, now=NOW)


def test_wal_and_shm_existing_sidecars_are_not_modified_by_readonly_query(dbs):
    with sqlite3.connect(dbs[0]) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute(
            "UPDATE registrations SET pairing_epoch=pairing_epoch WHERE hardware_id=?",
            (NEW,),
        )
        writer.commit()
        wal = type(dbs[0])(str(dbs[0]) + "-wal")
        shm = type(dbs[0])(str(dbs[0]) + "-shm")
        assert wal.is_file() and shm.is_file()
        paths = (*dbs, wal, shm)
        before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
        result = read_pending(*dbs, now=NOW + timedelta(seconds=1))
        assert result["new_count"] == 1
        assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths] == before


def test_missing_shm_with_existing_wal_stops_without_creating_shm(dbs):
    wal = type(dbs[0])(str(dbs[0]) + "-wal")
    shm = type(dbs[0])(str(dbs[0]) + "-shm")
    assert not shm.exists()
    wal.write_bytes(b"synthetic-wal-sidecar-without-index")
    with pytest.raises(PendingReadonlyError):
        read_pending(*dbs, now=NOW)
    assert not shm.exists()
    assert wal.read_bytes() == b"synthetic-wal-sidecar-without-index"


def test_concurrent_wal_writer_state_change_is_rejected(dbs, monkeypatch):
    writer = sqlite3.connect(dbs[0])
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        original = n3w_p4_pending_readonly._projection
        calls = []

        def projection(*connections):
            observed = original(*connections)
            calls.append(observed)
            if len(calls) == 1:
                writer.execute(
                    "INSERT INTO registration_events(hardware_id,pairing_id,event,occurred_at) "
                    "VALUES (?,?,?,?)",
                    (
                        "ghw-c6-000000000000",
                        "11111111-1111-4111-8111-000000000000",
                        "hello_created",
                        NOW.isoformat(),
                    ),
                )
                writer.commit()
            return observed

        monkeypatch.setattr(n3w_p4_pending_readonly, "_projection", projection)
        with pytest.raises(PendingReadonlyError):
            read_pending(*dbs, now=NOW + timedelta(seconds=1))
        assert len(calls) == 1
    finally:
        writer.close()
