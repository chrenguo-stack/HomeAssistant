from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager.runtime.config import Settings
from greenhouse_manager.runtime.ingest import TelemetryProcessor
from greenhouse_manager.runtime.n3w_runtime_wiring import (
    N3wRuntimeWiringError,
    build_n3w_runtime_wiring,
    require_n3w_registration_store,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

SYSTEM_ID = "system_001"
NODE_ID = "node_0001"
GATEWAY_ID = "gateway_001"
HARDWARE_ID = "ghw-c6-98a316a9f2f8"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
KEY = bytes(range(32))
KEY_FILE = f"{NODE_ID}-epoch-1.key"
NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def hello() -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": PAIRING_ID,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE_ID,
        "model": "greenhouse-wifi-c6",
        "fw_version": "F1.0-RC2-N2.0",
        "node_nonce": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        "capabilities": ["mqtt-runtime-credentials"],
        "sent_at_ms": 120345,
    }


def create_registration(path: Path) -> None:
    with RegistrationRegistry(path) as registry:
        registry.observe_hello(hello(), now=NOW)
        registry.approve(
            HARDWARE_ID,
            PAIRING_ID,
            node_id=NODE_ID,
            now=NOW,
        )


def create_replay(path: Path) -> None:
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    with ReplayRegistry(path):
        pass
    os.chmod(path, 0o600)


def create_authorization(database: Path, key_dir: Path) -> None:
    key_dir.mkdir(mode=0o700)
    key_path = key_dir / KEY_FILE
    key_path.write_bytes(KEY)
    os.chmod(key_path, 0o600)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE n3w_relay_meta (schema_version INTEGER NOT NULL);
            CREATE TABLE n3w_relay_nodes (
                node_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL CHECK (active IN (0,1))
            );
            CREATE TABLE n3w_relay_gateway_nodes (
                gateway_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
                PRIMARY KEY (gateway_id,node_id)
            );
            CREATE TABLE n3w_relay_key_epochs (
                node_id TEXT NOT NULL,
                key_epoch INTEGER NOT NULL CHECK (key_epoch >= 1),
                key_file TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
                state TEXT NOT NULL CHECK (state IN ('STAGED','ACTIVE','GRACE','REVOKED')),
                key_sha256 TEXT,
                PRIMARY KEY (node_id,key_epoch)
            );
            CREATE TABLE n3w_relay_operations (
                operation_key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                node_id TEXT NOT NULL,
                gateway_id TEXT,
                key_epoch INTEGER,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute("INSERT INTO n3w_relay_meta VALUES (2)")
        connection.execute(
            "INSERT INTO n3w_relay_nodes VALUES (?, 1)",
            (NODE_ID,),
        )
        connection.execute(
            "INSERT INTO n3w_relay_gateway_nodes VALUES (?, ?, 1)",
            (GATEWAY_ID, NODE_ID),
        )
        connection.execute(
            """
            INSERT INTO n3w_relay_key_epochs
                (node_id,key_epoch,key_file,enabled,state,key_sha256)
            VALUES (?,1,?,1,'ACTIVE',?)
            """,
            (NODE_ID, KEY_FILE, hashlib.sha256(KEY).hexdigest()),
        )
    os.chmod(database, 0o600)


def state(tmp_path: Path) -> tuple[Settings, Path, Path, Path, Path]:
    registration = tmp_path / "registration.sqlite3"
    replay = tmp_path / "replay.sqlite3"
    authorization = tmp_path / "relay-authorization.sqlite3"
    key_dir = tmp_path / "relay-keys"
    create_registration(registration)
    create_replay(replay)
    create_authorization(authorization, key_dir)
    settings = Settings(
        system_id=SYSTEM_ID,
        pairing_db_path=str(registration),
        n3w_runtime_enabled=True,
        n3w_replay_db_path=str(replay),
        n3w_relay_authorization_db_path=str(authorization),
        n3w_relay_key_dir=str(key_dir),
        n3w_path_stability_window_s=0,
        n3w_path_minimum_distinct_frames=1,
        n3w_path_lease_ttl_s=1,
        n3w_path_old_grace_s=0,
    )
    settings.validate()
    return settings, registration, replay, authorization, key_dir


def test_builds_one_shared_production_shaped_runtime_and_audits_secret_free(
    tmp_path: Path,
) -> None:
    settings, registration_path, _replay, _authorization, _keys = state(tmp_path)
    registration = RegistrationRegistry(registration_path)
    processor = TelemetryProcessor(system_id=SYSTEM_ID)
    try:
        wiring = build_n3w_runtime_wiring(
            settings=settings,
            processor=processor,
            registration_registry=registration,
        )
        audit = wiring.audit()

        assert wiring.router.processor is processor
        assert wiring.router.replay_registry is wiring.replay_registry
        assert wiring.relay_core.replay_registry is wiring.replay_registry
        assert wiring.path_lease.replay_registry is wiring.replay_registry
        assert wiring.relay_subscription == (
            f"gh/v1/{SYSTEM_ID}/ingress/gateway/+/+/frame"
        )
        assert wiring.is_relay_topic(
            f"gh/v1/{SYSTEM_ID}/ingress/gateway/{GATEWAY_ID}/{NODE_ID}/frame"
        )
        assert not wiring.is_relay_topic(
            f"gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/telemetry"
        )
        assert audit["status"] == "passed"
        assert audit["secret_values_included"] is False
        assert audit["mutated"] is False
        assert KEY.hex() not in json.dumps(audit)
        wiring.close()
        wiring.close()
    finally:
        registration.close()


def test_requires_preexisting_registration_and_private_replay_store(
    tmp_path: Path,
) -> None:
    missing_registration = tmp_path / "missing-registration.sqlite3"
    with pytest.raises(
        N3wRuntimeWiringError,
        match="n3w_registration_store_unavailable",
    ):
        require_n3w_registration_store(str(missing_registration))
    assert not missing_registration.exists()

    settings, registration_path, replay, _authorization, _keys = state(tmp_path)
    registration = RegistrationRegistry(registration_path)
    try:
        os.chmod(replay, 0o644)
        with pytest.raises(
            N3wRuntimeWiringError,
            match="n3w_replay_store_unavailable",
        ):
            build_n3w_runtime_wiring(
                settings=settings,
                processor=TelemetryProcessor(system_id=SYSTEM_ID),
                registration_registry=registration,
            )
    finally:
        registration.close()


def test_missing_replay_store_is_not_created_by_runtime_wiring(tmp_path: Path) -> None:
    settings, registration_path, replay, _authorization, _keys = state(tmp_path)
    replay.unlink()
    registration = RegistrationRegistry(registration_path)
    try:
        with pytest.raises(
            N3wRuntimeWiringError,
            match="n3w_replay_store_unavailable",
        ):
            build_n3w_runtime_wiring(
                settings=settings,
                processor=TelemetryProcessor(system_id=SYSTEM_ID),
                registration_registry=registration,
            )
        assert not replay.exists()
    finally:
        registration.close()


def test_authorization_failure_closes_partially_open_runtime(tmp_path: Path) -> None:
    settings, registration_path, _replay, authorization, _keys = state(tmp_path)
    os.chmod(authorization, 0o644)
    registration = RegistrationRegistry(registration_path)
    try:
        with pytest.raises(
            N3wRuntimeWiringError,
            match="n3w_runtime_wiring_unavailable",
        ):
            build_n3w_runtime_wiring(
                settings=settings,
                processor=TelemetryProcessor(system_id=SYSTEM_ID),
                registration_registry=registration,
            )
    finally:
        registration.close()


def test_builder_rejects_disabled_runtime(tmp_path: Path) -> None:
    settings, registration_path, _replay, _authorization, _keys = state(tmp_path)
    registration = RegistrationRegistry(registration_path)
    try:
        with pytest.raises(N3wRuntimeWiringError, match="n3w_runtime_not_enabled"):
            build_n3w_runtime_wiring(
                settings=replace(settings, n3w_runtime_enabled=False),
                processor=TelemetryProcessor(system_id=SYSTEM_ID),
                registration_registry=registration,
            )
    finally:
        registration.close()
