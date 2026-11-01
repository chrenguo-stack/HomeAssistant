from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from greenhouse_manager.bootstrap.anonymous_closure import (
    ANONYMOUS_CLOSURE_SCHEMA,
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
    initialize_system,
)

SCHEMA = "gh.h0h1.host-only-harness/1"
PASSPHRASE = "host-only deterministic non-production passphrase"


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


def run_harness() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="gh-h0h1-host-only-") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        host_a = root / "host-a"
        host_c = root / "host-c"
        first = initialize_system(
            host_a,
            enable=True,
            confirmation=INITIALIZATION_CONFIRMATION,
        )
        independent = initialize_system(
            host_c,
            enable=True,
            confirmation=INITIALIZATION_CONFIRMATION,
        )
        _private_file(host_a / "manager" / "state.sqlite3", b"synthetic-manager-state")
        _private_file(
            host_a / "broker" / "dynamic-security.json",
            b'{"schema":"synthetic","clients":[]}\n',
        )
        _private_file(host_a / "broker" / "mosquitto.db", b"synthetic-broker-state")

        archive = root / "portable.ghpr"
        created = create_portable_backup(
            host_a,
            _inventory(),
            archive,
            passphrase=PASSPHRASE,
            enable=True,
            confirmation=CREATE_CONFIRMATION,
        )
        verified = verify_portable_backup(archive, passphrase=PASSPHRASE)
        restored_root = root / "host-b"
        restored = restore_portable_backup(
            archive,
            restored_root,
            passphrase=PASSPHRASE,
            expected_system_id=first.system_id,
            enable=True,
            confirmation=RESTORE_CONFIRMATION,
        )

        registry = root / "identity-registry"
        claim_identity(
            registry,
            system_id=first.system_id,
            host_instance_id="host-a",
            enable=True,
            confirmation=CLAIM_CONFIRMATION,
        )
        conflict_detected = False
        try:
            claim_identity(
                registry,
                system_id=first.system_id,
                host_instance_id="host-b",
                enable=True,
                confirmation=CLAIM_CONFIRMATION,
            )
        except IdentityConflictError:
            conflict_detected = True
        if not conflict_detected:
            raise RuntimeError("synthetic identity conflict was not detected")
        release_identity(
            registry,
            system_id=first.system_id,
            host_instance_id="host-a",
            enable=True,
            confirmation=RELEASE_CONFIRMATION,
        )
        successor_claim = claim_identity(
            registry,
            system_id=first.system_id,
            host_instance_id="host-b",
            enable=True,
            confirmation=CLAIM_CONFIRMATION,
        )
        closure = validate_anonymous_closure_policy(_policy(first.system_id))

        return {
            "schema": SCHEMA,
            "status": "PASS",
            "source_system_id_fingerprint": hashlib.sha256(
                first.system_id.encode("utf-8")
            ).hexdigest()[:16],
            "independent_initializations_distinct": (
                independent.system_id != first.system_id
                and independent.manager_id != first.manager_id
            ),
            "portable_backup_encrypted": created.encrypted,
            "portable_backup_verified": (
                verified.envelope_sha256 == created.envelope_sha256
            ),
            "portable_restore_round_trip": (
                restored.system_id == first.system_id
                and restored.activation_enabled is False
            ),
            "identity_conflict_detected": conflict_detected,
            "successor_identity_claimed_after_release": (
                successor_claim.claimed
                and successor_claim.host_instance_id == "host-b"
            ),
            "anonymous_publish_denied": (
                closure.legacy_anonymous_publish_allowed is False
            ),
            "anonymous_subscribe_denied": (
                closure.legacy_anonymous_subscribe_allowed is False
            ),
            "all_required_clients_authenticated": (
                closure.all_required_clients_authenticated
            ),
            "production_services_modified": False,
            "network_operation": False,
            "subprocess_operation": False,
            "t1_operation": False,
            "board_operation": False,
            "live_apply_enabled": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_harness()
    payload = json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
