from __future__ import annotations

import io
import json
import os
from pathlib import Path

from greenhouse_manager.bootstrap.cli import main as init_main
from greenhouse_manager.bootstrap.identity_guard import (
    CLAIM_CONFIRMATION,
    RELEASE_CONFIRMATION,
)
from greenhouse_manager.bootstrap.identity_guard_cli import main as guard_main
from greenhouse_manager.bootstrap.portable_restore import (
    CREATE_CONFIRMATION,
    RESTORE_CONFIRMATION,
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
)
from greenhouse_manager.bootstrap.portable_restore_cli import main as portable_main
from greenhouse_manager.bootstrap.system_init import (
    INITIALIZATION_CONFIRMATION,
    MANAGER_IDENTITY_NAME,
    SYSTEM_CA_CERTIFICATE_NAME,
    SYSTEM_CA_PRIVATE_KEY_NAME,
    SYSTEM_IDENTITY_NAME,
    SYSTEM_ROOT_KEY_NAME,
)


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def _private_file(path: Path, payload: bytes) -> None:
    _private_directory(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)


def _inventory() -> dict[str, str]:
    return {
        ROLE_SYSTEM_IDENTITY: SYSTEM_IDENTITY_NAME,
        ROLE_SYSTEM_ROOT_KEY: SYSTEM_ROOT_KEY_NAME,
        ROLE_SYSTEM_CA_CERTIFICATE: SYSTEM_CA_CERTIFICATE_NAME,
        ROLE_SYSTEM_CA_PRIVATE_KEY: SYSTEM_CA_PRIVATE_KEY_NAME,
        ROLE_MANAGER_IDENTITY: MANAGER_IDENTITY_NAME,
        ROLE_MANAGER_REGISTRATION_STATE: "manager/state.sqlite3",
        ROLE_MANAGER_CREDENTIAL_STATE: "manager/state.sqlite3",
        ROLE_MANAGER_RETIREMENT_OUTBOX: "manager/state.sqlite3",
        ROLE_BROKER_DYNAMIC_SECURITY: "broker/dynamic-security.json",
        ROLE_BROKER_PERSISTENCE: "broker/mosquitto.db",
    }


def test_cli_chain_initializes_backs_up_restores_and_guards_identity(
    tmp_path: Path,
) -> None:
    _private_directory(tmp_path)
    system_root = tmp_path / "system"
    output = io.StringIO()
    errors = io.StringIO()
    assert (
        init_main(
            [
                "initialize",
                "--root",
                str(system_root),
                "--enable-initialization",
                "--confirm",
                INITIALIZATION_CONFIRMATION,
            ],
            output=output,
            error_output=errors,
        )
        == 0
    )
    initialized = json.loads(output.getvalue())
    assert initialized["status"] == "PASS"
    assert initialized["created"] is True
    assert "system_root_key" not in initialized
    assert errors.getvalue() == ""

    _private_file(system_root / "manager" / "state.sqlite3", b"manager")
    _private_file(system_root / "broker" / "dynamic-security.json", b"dynsec")
    _private_file(system_root / "broker" / "mosquitto.db", b"broker")

    passphrase_file = tmp_path / "passphrase"
    inventory_file = tmp_path / "inventory.json"
    _private_file(passphrase_file, b"local-only passphrase 12345\n")
    _private_file(
        inventory_file,
        json.dumps(_inventory(), sort_keys=True).encode("utf-8") + b"\n",
    )
    archive = tmp_path / "system.ghpr"
    output = io.StringIO()
    assert (
        portable_main(
            [
                "create",
                "--source-root",
                str(system_root),
                "--inventory-file",
                str(inventory_file),
                "--output",
                str(archive),
                "--passphrase-file",
                str(passphrase_file),
                "--enable-create",
                "--confirm",
                CREATE_CONFIRMATION,
            ],
            output=output,
            error_output=io.StringIO(),
        )
        == 0
    )
    created = json.loads(output.getvalue())
    assert created["encrypted"] is True
    assert "passphrase" not in output.getvalue().lower()

    restored_root = tmp_path / "restored"
    output = io.StringIO()
    assert (
        portable_main(
            [
                "restore",
                "--archive",
                str(archive),
                "--target-root",
                str(restored_root),
                "--passphrase-file",
                str(passphrase_file),
                "--expected-system-id",
                initialized["system_id"],
                "--enable-restore",
                "--confirm",
                RESTORE_CONFIRMATION,
            ],
            output=output,
            error_output=io.StringIO(),
        )
        == 0
    )
    restored = json.loads(output.getvalue())
    assert restored["activation_enabled"] is False

    registry = tmp_path / "registry"
    output = io.StringIO()
    assert (
        guard_main(
            [
                "claim",
                "--registry-root",
                str(registry),
                "--system-id",
                initialized["system_id"],
                "--host-instance-id",
                "host-a",
                "--enable",
                "--confirm",
                CLAIM_CONFIRMATION,
            ],
            output=output,
            error_output=io.StringIO(),
        )
        == 0
    )
    assert json.loads(output.getvalue())["claimed"] is True

    output = io.StringIO()
    assert (
        guard_main(
            [
                "release",
                "--registry-root",
                str(registry),
                "--system-id",
                initialized["system_id"],
                "--host-instance-id",
                "host-a",
                "--enable",
                "--confirm",
                RELEASE_CONFIRMATION,
            ],
            output=output,
            error_output=io.StringIO(),
        )
        == 0
    )
    assert json.loads(output.getvalue())["claimed"] is False
