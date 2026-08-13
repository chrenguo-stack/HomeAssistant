from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANAGER_SRC = ROOT / "host/greenhouse-manager/src"
sys.path.insert(0, str(MANAGER_SRC))

from greenhouse_manager.ops.n3w_relay_authorization_admin import (
    RelayAuthorizationAdmin,
    RelayAuthorizationAdminError,
    ReplayPathLeaseInvalidator,
)
from greenhouse_manager.runtime.n3w_path_lease import (
    N3wPathLeaseCoordinator,
    PathLeasePolicy,
    PathOwner,
)
from greenhouse_manager.runtime.n3w_relay_authorization import (
    REVOKED_GATEWAY_SENTINEL,
    SqliteRelayAuthorizationProvider,
)
from greenhouse_manager.runtime.n3w_relay_ingress import RelayIngressRejected
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

PLAN = ROOT / "docs/decisions/n3w-p5-m11-authorization-regrant-host-only-plan.json"
COMPOSE = ROOT / "infra/compose/n3w-p5-two-board-isolated/docker-compose.yml"
LAB_ADMIN = ROOT / "infra/compose/n3w-p5-two-board-isolated/lab_admin.py"
WORKFLOW = ROOT / ".github/workflows/n3w-p5-m11-authorization-regrant-host-only-ci.yml"

NODE_ID = "n3wp5_child01"
GATEWAY_ID = "n3wp5_relay01"
BOOT_ID = "boot_0000000000000001"
KEY = bytes.fromhex("22" * 32)
NOW = datetime(2026, 8, 13, 2, 0, tzinfo=UTC)
RELAY = PathOwner("relay", GATEWAY_ID)
POLICY = PathLeasePolicy(
    stability_window_s=5,
    minimum_distinct_frames=2,
    lease_ttl_s=30,
    old_path_grace_s=5,
)


def _path_state(database: Path) -> dict[str, object]:
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        row = connection.execute(
            "SELECT * FROM n3w_path_leases WHERE node_id=?", (NODE_ID,)
        ).fetchone()
        assert row is not None
        return {
            "active_transport": row["active_transport"],
            "active_gateway_id": row["active_gateway_id"],
            "lease_expires_at": row["lease_expires_at"],
            "candidate_transport": row["candidate_transport"],
            "candidate_gateway_id": row["candidate_gateway_id"],
            "candidate_since": row["candidate_since"],
            "candidate_last_boot_id": row["candidate_last_boot_id"],
            "candidate_last_seq": row["candidate_last_seq"],
            "candidate_distinct_count": row["candidate_distinct_count"],
            "previous_transport": row["previous_transport"],
            "previous_gateway_id": row["previous_gateway_id"],
            "old_grace_until": row["old_grace_until"],
            "canonical_boot_session_hex": row["canonical_boot_session_hex"],
            "canonical_seq": row["canonical_seq"],
            "revision": row["revision"],
        }
    finally:
        connection.close()


def _create_revoked_state(
    tmp_path: Path,
) -> tuple[
    Path, Path, Path, ReplayRegistry, N3wPathLeaseCoordinator, RelayAuthorizationAdmin
]:
    replay_database = tmp_path / "replay.sqlite3"
    authorization_database = tmp_path / "relay-authorization.sqlite3"
    key_dir = tmp_path / "relay-keys"
    replay = ReplayRegistry(replay_database)
    path = N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=POLICY,
        ingress_allowed=lambda _node_id: True,
    )
    assert (
        path.process(
            node_id=NODE_ID,
            boot_id=BOOT_ID,
            seq=1,
            owner=RELAY,
            now=NOW,
        ).status
        == "accepted"
    )
    admin = RelayAuthorizationAdmin(
        authorization_database,
        key_dir,
        node_state=lambda _node_id: "active",
        path_invalidator=ReplayPathLeaseInvalidator(replay),
    )
    admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
    staged = admin.stage_key(node_id=NODE_ID, key_material=KEY)
    admin.activate_key(node_id=NODE_ID, key_epoch=int(staged["key_epoch"]))
    result = admin.revoke_grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
    assert result["recovery_pending"] is False
    return authorization_database, key_dir, replay_database, replay, path, admin


def test_m11_plan_is_host_only_and_live_execution_is_separately_gated() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))

    assert document["status"] == "host_only_contract_ready_live_execution_prohibited"
    assert document["base"] == {
        "repository": "chrenguo-stack/HomeAssistant",
        "branch": "main",
        "commit_sha": "681f13d1deee92388fed312453623d338489946a",
        "tree_sha": "685e0afd0d84728f39ada67b55fba4f7205e11b0",
    }
    assert document["matrix_contract"] == {
        "id": "M11",
        "name": "authorization_regrant",
        "action": "lab admin grant",
        "expect": "Relay must re-enter through normal stability path",
    }
    assert document["development_authorization"]["consumed"] is True
    assert document["development_authorization"]["replay_allowed"] is False
    assert document["regrant_contract"]["minimum_distinct_frames"] == 2
    assert document["regrant_contract"]["stability_window_s"] == 5
    assert document["future_live_preflight"]["authorized_now"] is False
    assert document["future_live_transaction"]["authorized_now"] is False
    assert document["future_live_transaction"]["maximum_grant_attempts"] == 1
    assert document["future_live_transaction"]["automatic_retry"] is False
    assert document["next_gate"]["m11_live_allowed"] is False
    assert document["next_gate"]["m12_allowed"] is False


def test_m11_regrant_requires_production_stability_and_preserves_candidate_tuples(
    tmp_path: Path,
) -> None:
    auth_db, key_dir, replay_db, replay, path, admin = _create_revoked_state(tmp_path)
    provider = SqliteRelayAuthorizationProvider(auth_db, key_dir)
    try:
        revoked = _path_state(replay_db)
        assert revoked["active_gateway_id"] == REVOKED_GATEWAY_SENTINEL
        assert revoked["lease_expires_at"] == "1970-01-01T00:00:00.000Z"
        assert revoked["candidate_transport"] is None
        with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
            provider.resolve_key(gateway_id=GATEWAY_ID, node_id=NODE_ID, key_epoch=1)

        grant = admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
        assert grant["status"] == "passed"
        assert grant["operation"] == "grant"
        assert grant["recovery_pending"] is False
        assert grant["secret_values_included"] is False
        assert (
            provider.resolve_key(gateway_id=GATEWAY_ID, node_id=NODE_ID, key_epoch=1)
            == KEY
        )
        assert _path_state(replay_db) == revoked

        first = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_ID,
            seq=2,
            owner=RELAY,
            now=NOW + timedelta(seconds=1),
        )
        after_first = _path_state(replay_db)
        assert first.code == "path_candidate_pending"
        assert first.candidate_distinct_count == 1
        assert after_first["active_gateway_id"] == REVOKED_GATEWAY_SENTINEL
        assert after_first["candidate_gateway_id"] == GATEWAY_ID
        assert after_first["candidate_distinct_count"] == 1
        assert after_first["canonical_seq"] == revoked["canonical_seq"]
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=2).status == (
            "ready"
        )

        second = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_ID,
            seq=3,
            owner=RELAY,
            now=NOW + timedelta(seconds=4),
        )
        after_second = _path_state(replay_db)
        assert second.code == "path_candidate_pending"
        assert second.candidate_distinct_count == 2
        assert after_second["active_gateway_id"] == REVOKED_GATEWAY_SENTINEL
        assert after_second["candidate_distinct_count"] == 2
        assert after_second["canonical_seq"] == revoked["canonical_seq"]
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=3).status == (
            "ready"
        )

        switched = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_ID,
            seq=4,
            owner=RELAY,
            now=NOW + timedelta(seconds=6),
        )
        final = _path_state(replay_db)
        assert switched.status == "accepted"
        assert switched.switched is True
        assert switched.active_owner == RELAY
        assert final["active_transport"] == "relay"
        assert final["active_gateway_id"] == GATEWAY_ID
        assert final["candidate_transport"] is None
        assert final["candidate_gateway_id"] is None
        assert final["previous_transport"] == "relay"
        assert final["previous_gateway_id"] == REVOKED_GATEWAY_SENTINEL
        assert final["canonical_boot_session_hex"] == "0000000000000001"
        assert final["canonical_seq"] == 4
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=2).status == (
            "ready"
        )
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=3).status == (
            "ready"
        )
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=4).status == (
            "duplicate"
        )
    finally:
        provider.close()
        admin.close()
        replay.close()


def test_m11_pending_revoke_cleanup_blocks_regrant(tmp_path: Path) -> None:
    authorization_db = tmp_path / "relay-authorization.sqlite3"
    key_dir = tmp_path / "relay-keys"
    admin = RelayAuthorizationAdmin(
        authorization_db,
        key_dir,
        node_state=lambda _node_id: "active",
    )
    try:
        admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
        result = admin.revoke_grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
        assert result["recovery_pending"] is True
        with pytest.raises(
            RelayAuthorizationAdminError, match="grant_recovery_pending"
        ):
            admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
    finally:
        admin.close()


def test_m11_lab_admin_compose_and_production_policy_wiring() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    lab_admin_service = compose.split("\n  lab-admin:\n", maxsplit=1)[1].split(
        "\nvolumes:\n", maxsplit=1
    )[0]
    source = LAB_ADMIN.read_text(encoding="utf-8")

    assert 'profiles: ["admin"]' in lab_admin_service
    assert 'entrypoint: ["python", "/lab_admin.py"]' in lab_admin_service
    assert "- manager-state:/state" in lab_admin_service
    assert 'GH_N3W_PATH_STABILITY_WINDOW_S: "5"' in compose
    assert 'GH_N3W_PATH_MINIMUM_DISTINCT_FRAMES: "2"' in compose
    assert 'GH_N3W_PATH_LEASE_TTL_S: "30"' in compose
    assert 'GH_N3W_PATH_OLD_GRACE_S: "5"' in compose
    assert "admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)" in source
    assert '"grant": command_grant' in source


def test_m11_change_set_contains_no_live_executor_or_secret_material() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    expected = {
        ".github/workflows/n3w-p5-m11-authorization-regrant-host-only-ci.yml",
        "docs/decisions/n3w-p5-m11-authorization-regrant-host-only-plan.json",
        "tests/n3w_p5/test_n3w_p5_m11_authorization_regrant_contract.py",
    }
    assert set(document["change_scope"]["allowed"]) == expected

    forbidden_workflow_tokens = (
        "docker --context",
        "docker compose",
        "mosquitto_pub",
        "mosquitto_sub",
        "esphome run",
        "esptool",
        "/dev/cu.",
        "/dev/tty",
        "192.168.68.",
    )
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert all(token not in workflow for token in forbidden_workflow_tokens)

    combined = PLAN.read_bytes() + WORKFLOW.read_bytes() + Path(__file__).read_bytes()
    assert b"BEGIN " + b"PRIVATE KEY" not in combined
    assert b"GH_MQTT_" + b"PASSWORD=" not in combined
    assert hashlib.sha256(combined).hexdigest()
