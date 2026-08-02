from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager.bootstrap.anonymous_closure import (
    ANONYMOUS_CLOSURE_SCHEMA,
    AnonymousClosureError,
    validate_anonymous_closure_policy,
)
from greenhouse_manager.bootstrap.identity_guard import (
    CLAIM_CONFIRMATION,
    RELEASE_CONFIRMATION,
    IdentityConflictError,
    claim_identity,
    release_identity,
)
from greenhouse_manager.bootstrap.portable_restore import (
    CREATE_CONFIRMATION,
    RESTORE_CONFIRMATION,
    REQUIRED_ROLES,
    ROLE_BROKER_DYNAMIC_SECURITY,
    ROLE_BROKER_PERSISTENCE,
    ROLE_MANAGER_CREDENTIAL_STATE,
    ROLE_MANAGER_IDENTITY,
    ROLE_MANAGER_REGISTRATION_STATE,
    ROLE_MANAGER_RETIREMENT_OUTBOX,
    ROLE_SYSTEM_CA_CERTIFICATE,
    ROLE_SYSTEM_CA_PRIVATE_KEY,
    ROLE_SYSTEM_IDENTITY,
    ROLE_SYSTEM_ROOT_KEY,
    PortableRestoreError,
    create_portable_backup,
    restore_portable_backup,
    verify_portable_backup,
)
from greenhouse_manager.bootstrap.system_init import (
    INITIALIZATION_CONFIRMATION,
    MANAGER_IDENTITY_NAME,
    SYSTEM_CA_CERTIFICATE_NAME,
    SYSTEM_CA_PRIVATE_KEY_NAME,
    SYSTEM_IDENTITY_NAME,
    SYSTEM_ROOT_KEY_NAME,
    InitializationError,
    initialize_system,
    verify_initialization,
)

NOW = datetime(2026, 8, 2, 8, 0, tzinfo=UTC)
PASSPHRASE = "correct horse battery staple"


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def _private_file(path: Path, payload: bytes) -> None:
    _private_directory(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def _backup_source(tmp_path: Path) -> tuple[Path, dict[str, str], str]:
    source = tmp_path / "source"
    _private_directory(source)
    report = initialize_system(
        source,
        enable=True,
        confirmation=INITIALIZATION_CONFIRMATION,
        now=NOW,
    )
    _private_file(source / "manager" / "registration.sqlite3", b"manager-state")
    _private_file(source / "broker" / "dynamic-security.json", b'{"clients":[]}\n')
    _private_file(source / "broker" / "mosquitto.db", b"broker-persistence")
    inventory = {
        ROLE_SYSTEM_IDENTITY: SYSTEM_IDENTITY_NAME,
        ROLE_SYSTEM_ROOT_KEY: SYSTEM_ROOT_KEY_NAME,
        ROLE_SYSTEM_CA_CERTIFICATE: SYSTEM_CA_CERTIFICATE_NAME,
        ROLE_SYSTEM_CA_PRIVATE_KEY: SYSTEM_CA_PRIVATE_KEY_NAME,
        ROLE_MANAGER_IDENTITY: MANAGER_IDENTITY_NAME,
        ROLE_MANAGER_REGISTRATION_STATE: "manager/registration.sqlite3",
        ROLE_MANAGER_CREDENTIAL_STATE: "manager/registration.sqlite3",
        ROLE_MANAGER_RETIREMENT_OUTBOX: "manager/registration.sqlite3",
        ROLE_BROKER_DYNAMIC_SECURITY: "broker/dynamic-security.json",
        ROLE_BROKER_PERSISTENCE: "broker/mosquitto.db",
    }
    assert set(inventory) == REQUIRED_ROLES
    return source, inventory, report.system_id


def _policy(system_id: str) -> dict[str, object]:
    return {
        "schema": ANONYMOUS_CLOSURE_SCHEMA,
        "system_id": system_id,
        "anonymous_enabled": False,
        "live_apply_enabled": False,
        "clients": [
            {
                "system_id": system_id,
                "role": "manager",
                "client_id": "manager-client",
                "username": "manager-user",
                "credential_generation": 1,
                "publish": ["homeassistant/#", "gh/canonical/#"],
                "subscribe": ["gh/ingress/#"],
            },
            {
                "system_id": system_id,
                "role": "home_assistant",
                "client_id": "ha-client",
                "username": "ha-user",
                "credential_generation": 1,
                "publish": ["homeassistant/status"],
                "subscribe": ["homeassistant/#", "gh/canonical/#"],
            },
            {
                "system_id": system_id,
                "role": "node",
                "client_id": "node-client",
                "username": "node-user",
                "credential_generation": 1,
                "publish": ["gh/ingress/node-1/telemetry"],
                "subscribe": ["gh/control/node-1/#"],
            },
        ],
        "probes": [
            {
                "client_id": "node-client",
                "action": "publish",
                "topic": "gh/ingress/node-1/telemetry",
                "expected": True,
            },
            {
                "client_id": "manager-client",
                "action": "subscribe",
                "topic": "gh/ingress/node-1/telemetry",
                "expected": True,
            },
            {
                "client_id": None,
                "action": "publish",
                "topic": "gh/ingress/node-1/telemetry",
                "expected": False,
            },
            {
                "client_id": None,
                "action": "subscribe",
                "topic": "homeassistant/#",
                "expected": False,
            },
        ],
    }


def test_initialize_is_marker_last_idempotent_and_unique(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _private_directory(tmp_path)

    first = initialize_system(
        first_root,
        enable=True,
        confirmation=INITIALIZATION_CONFIRMATION,
        now=NOW,
    )
    repeated = initialize_system(first_root)
    second = initialize_system(
        second_root,
        enable=True,
        confirmation=INITIALIZATION_CONFIRMATION,
        now=NOW,
    )

    assert first.created is True
    assert repeated.created is False
    assert repeated.system_id == first.system_id
    assert repeated.manager_id == first.manager_id
    assert second.system_id != first.system_id
    assert second.manager_id != first.manager_id
    assert (first_root / "INITIALIZED.json").stat().st_mode & 0o777 == 0o600
    assert first.production_services_modified is False
    assert first.network_operation is False
    assert first.subprocess_operation is False


def test_initialize_rejects_partial_or_tampered_state(tmp_path: Path) -> None:
    partial = tmp_path / "partial"
    _private_directory(partial)
    _private_file(partial / SYSTEM_ROOT_KEY_NAME, b"x" * 32)
    with pytest.raises(InitializationError, match="partial"):
        initialize_system(
            partial,
            enable=True,
            confirmation=INITIALIZATION_CONFIRMATION,
            now=NOW,
        )

    complete = tmp_path / "complete"
    initialize_system(
        complete,
        enable=True,
        confirmation=INITIALIZATION_CONFIRMATION,
        now=NOW,
    )
    (complete / SYSTEM_ROOT_KEY_NAME).write_bytes(b"tampered")
    (complete / SYSTEM_ROOT_KEY_NAME).chmod(0o600)
    with pytest.raises(InitializationError, match="digest drift|size drift"):
        verify_initialization(complete)


def test_portable_backup_round_trip_and_host_identity_conflict(tmp_path: Path) -> None:
    _private_directory(tmp_path)
    source, inventory, system_id = _backup_source(tmp_path)
    archive = tmp_path / "portable.ghpr"

    created = create_portable_backup(
        source,
        inventory,
        archive,
        passphrase=PASSPHRASE,
        enable=True,
        confirmation=CREATE_CONFIRMATION,
        now=NOW,
    )
    verified = verify_portable_backup(archive, passphrase=PASSPHRASE)
    restored_root = tmp_path / "restored"
    restored = restore_portable_backup(
        archive,
        restored_root,
        passphrase=PASSPHRASE,
        expected_system_id=system_id,
        enable=True,
        confirmation=RESTORE_CONFIRMATION,
    )

    assert created.encrypted is True
    assert created.portable_off_host is True
    assert created.role_count == len(REQUIRED_ROLES)
    assert verified.envelope_sha256 == created.envelope_sha256
    assert restored.system_id == system_id
    assert restored.activation_enabled is False
    assert (restored_root / "RESTORE_COMPLETE.json").is_file()
    assert (restored_root / "manager" / "registration.sqlite3").read_bytes() == b"manager-state"

    registry = tmp_path / "registry"
    claim_identity(
        registry,
        system_id=system_id,
        host_instance_id="host-a",
        enable=True,
        confirmation=CLAIM_CONFIRMATION,
        now=NOW,
    )
    with pytest.raises(IdentityConflictError, match="another host"):
        claim_identity(
            registry,
            system_id=system_id,
            host_instance_id="host-b",
            enable=True,
            confirmation=CLAIM_CONFIRMATION,
            now=NOW,
        )
    release_identity(
        registry,
        system_id=system_id,
        host_instance_id="host-a",
        enable=True,
        confirmation=RELEASE_CONFIRMATION,
    )
    successor = claim_identity(
        registry,
        system_id=system_id,
        host_instance_id="host-b",
        enable=True,
        confirmation=CLAIM_CONFIRMATION,
        now=NOW,
    )
    assert successor.claimed is True
    assert successor.host_instance_id == "host-b"


def test_portable_backup_fails_closed_on_wrong_passphrase_tamper_and_inventory(
    tmp_path: Path,
) -> None:
    _private_directory(tmp_path)
    source, inventory, _system_id = _backup_source(tmp_path)
    archive = tmp_path / "portable.ghpr"
    create_portable_backup(
        source,
        inventory,
        archive,
        passphrase=PASSPHRASE,
        enable=True,
        confirmation=CREATE_CONFIRMATION,
        now=NOW,
    )

    with pytest.raises(PortableRestoreError, match="authentication failed"):
        verify_portable_backup(archive, passphrase="wrong passphrase 123")

    payload = bytearray(archive.read_bytes())
    payload[-1] ^= 1
    archive.write_bytes(payload)
    archive.chmod(0o600)
    with pytest.raises(PortableRestoreError, match="ciphertext digest drift"):
        verify_portable_backup(archive, passphrase=PASSPHRASE)

    incomplete = dict(inventory)
    del incomplete[ROLE_MANAGER_RETIREMENT_OUTBOX]
    with pytest.raises(PortableRestoreError, match="role inventory mismatch"):
        create_portable_backup(
            source,
            incomplete,
            tmp_path / "incomplete.ghpr",
            passphrase=PASSPHRASE,
            enable=True,
            confirmation=CREATE_CONFIRMATION,
            now=NOW,
        )


def test_anonymous_closure_isolated_policy_regression(tmp_path: Path) -> None:
    _private_directory(tmp_path)
    source, _inventory, system_id = _backup_source(tmp_path)
    assert source.is_dir()
    report = validate_anonymous_closure_policy(_policy(system_id))
    assert report.all_required_clients_authenticated is True
    assert report.legacy_anonymous_publish_allowed is False
    assert report.legacy_anonymous_subscribe_allowed is False
    assert report.live_apply_enabled is False
    assert report.production_services_modified is False
    assert report.network_operation is False

    unsafe = _policy(system_id)
    unsafe["clients"][0]["password"] = "must-not-appear"  # type: ignore[index]
    with pytest.raises(AnonymousClosureError, match="secret-bearing"):
        validate_anonymous_closure_policy(unsafe)


def test_mutating_operations_are_default_disabled(tmp_path: Path) -> None:
    _private_directory(tmp_path)
    with pytest.raises(InitializationError, match="disabled"):
        initialize_system(tmp_path / "system")
    source, inventory, system_id = _backup_source(tmp_path)
    with pytest.raises(PortableRestoreError, match="disabled"):
        create_portable_backup(
            source,
            inventory,
            tmp_path / "disabled.ghpr",
            passphrase=PASSPHRASE,
        )
    with pytest.raises(IdentityConflictError, match="disabled"):
        claim_identity(
            tmp_path / "registry",
            system_id=system_id,
            host_instance_id="host-a",
        )
