from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

from greenhouse_manager.ops.n3w_relay_authorization_admin import (
    RelayAuthorizationAdmin,
    ReplayPathLeaseInvalidator,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

STATE = Path(os.environ.get("GH_P5_STATE_ROOT", "/state"))
REGISTRATION = STATE / "registration.sqlite3"
REPLAY = STATE / "n3w" / "replay.sqlite3"
AUTH = STATE / "n3w" / "relay-authorization.sqlite3"
KEY_DIR = STATE / "n3w" / "relay-keys"
NODE_ID = os.environ.get("GH_P5_NODE_ID", "n3wp5_child01")
GATEWAY_ID = os.environ.get("GH_P5_GATEWAY_ID", "n3wp5_relay01")


def _key(name: str) -> bytes:
    value = os.environ.get(name, "")
    if len(value) != 64:
        raise SystemExit(f"{name} must contain exactly 32 bytes as lowercase hex")
    try:
        result = bytes.fromhex(value)
    except ValueError as exc:
        raise SystemExit(f"{name} is not valid hex") from exc
    if len(result) != 32 or not any(result):
        raise SystemExit(f"{name} must be a nonzero 32-byte key")
    return result


def _prepare_paths() -> None:
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    (STATE / "n3w").mkdir(mode=0o700, exist_ok=True)
    KEY_DIR.mkdir(mode=0o700, exist_ok=True)
    os.chmod(STATE, 0o700)
    os.chmod(STATE / "n3w", 0o700)
    os.chmod(KEY_DIR, 0o700)
    if not REPLAY.exists():
        REPLAY.touch(mode=0o600)
    os.chmod(REPLAY, 0o600)


def _ensure_registration(registry: RegistrationRegistry) -> None:
    try:
        existing = registry.list_current()
    except Exception as exc:
        raise SystemExit("registration store unavailable") from exc
    if existing:
        if len(existing) != 1 or existing[0].node_id != NODE_ID:
            raise SystemExit(
                "isolated registration store is not the expected one-node state"
            )
        return
    now = datetime.now(UTC)
    hello = {
        "schema": "gh.pair.hello/1",
        "pairing_id": "00000000-0000-4000-8000-000000000005",
        "pairing_epoch": 1,
        "hardware_id": "ghw-n3wp5-001122334455",
        "model": "n3wp5lab",
        "fw_version": "N3W-P5-LAB",
        "node_nonce": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "capabilities": ["p5-lab"],
        "sent_at_ms": 0,
    }
    observed = registry.observe_hello(hello, now=now)
    if observed.status != "created":
        raise SystemExit(f"unexpected registration bootstrap status: {observed.status}")
    registry.approve(
        hello["hardware_id"],
        hello["pairing_id"],
        node_id=NODE_ID,
        logical_location_id="n3wp5_lab_location",
        now=now,
    )


def _open_admin() -> tuple[
    RegistrationRegistry, ReplayRegistry, RelayAuthorizationAdmin
]:
    _prepare_paths()
    registry = RegistrationRegistry(REGISTRATION, pending_ttl_s=120)
    replay = ReplayRegistry(REPLAY)
    admin = RelayAuthorizationAdmin(
        AUTH,
        KEY_DIR,
        node_state=registry.node_id_lease_state,
        path_invalidator=ReplayPathLeaseInvalidator(replay),
    )
    return registry, replay, admin


def command_init() -> None:
    registry, replay, admin = _open_admin()
    try:
        _ensure_registration(registry)
        audit = admin.audit()
        if audit["active_key_epoch_count"] or audit["staged_key_epoch_count"]:
            raise SystemExit(
                "refusing to overwrite non-empty P5 authorization/key state"
            )
        admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
        first = admin.stage_key(
            node_id=NODE_ID, key_material=_key("GH_P5_APP_KEY_EPOCH1_HEX")
        )
        if first["key_epoch"] != 1:
            raise SystemExit("unexpected first P5 key epoch")
        admin.activate_key(node_id=NODE_ID, key_epoch=1)
        second = admin.stage_key(
            node_id=NODE_ID, key_material=_key("GH_P5_APP_KEY_EPOCH2_HEX")
        )
        if second["key_epoch"] != 2:
            raise SystemExit("unexpected second P5 key epoch")
        print(admin.audit())
    finally:
        admin.close()
        replay.close()
        registry.close()


def command_rotate() -> None:
    registry, replay, admin = _open_admin()
    try:
        admin.activate_key(node_id=NODE_ID, key_epoch=2)
        print(admin.audit())
    finally:
        admin.close()
        replay.close()
        registry.close()


def command_revoke_grant() -> None:
    registry, replay, admin = _open_admin()
    try:
        print(admin.revoke_grant(gateway_id=GATEWAY_ID, node_id=NODE_ID))
    finally:
        admin.close()
        replay.close()
        registry.close()


def command_grant() -> None:
    registry, replay, admin = _open_admin()
    try:
        print(admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID))
    finally:
        admin.close()
        replay.close()
        registry.close()


def command_audit() -> None:
    registry, replay, admin = _open_admin()
    try:
        print(
            {
                "authorization": admin.audit(),
                "registration_count": len(registry.list_current()),
            }
        )
    finally:
        admin.close()
        replay.close()
        registry.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["init", "rotate", "revoke-grant", "grant", "audit"]
    )
    args = parser.parse_args()
    {
        "init": command_init,
        "rotate": command_rotate,
        "revoke-grant": command_revoke_grant,
        "grant": command_grant,
        "audit": command_audit,
    }[args.command]()


if __name__ == "__main__":
    main()
