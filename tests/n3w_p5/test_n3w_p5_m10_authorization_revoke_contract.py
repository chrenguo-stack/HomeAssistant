from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
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

PLAN = ROOT / "docs/decisions/n3w-p5-m10-authorization-revoke-host-only-plan.json"
COMPOSE = ROOT / "infra/compose/n3w-p5-two-board-isolated/docker-compose.yml"
LAB_ADMIN = ROOT / "infra/compose/n3w-p5-two-board-isolated/lab_admin.py"
WORKFLOW = ROOT / ".github/workflows/n3w-p5-m10-authorization-revoke-host-only-ci.yml"

NODE_ID = "n3wp5_child01"
GATEWAY_ID = "n3wp5_relay01"
BOOT_ID = "boot_0000000000000001"
KEY = bytes.fromhex("11" * 32)
NOW = datetime(2026, 8, 13, 1, 0, tzinfo=UTC)
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
        path = connection.execute(
            "SELECT * FROM n3w_path_leases WHERE node_id=?", (NODE_ID,)
        ).fetchone()
        replay = connection.execute(
            "SELECT highest_session_hex FROM n3w_replay_state WHERE node_id=?",
            (NODE_ID,),
        ).fetchone()
        assert path is not None and replay is not None
        return {
            "active_transport": path["active_transport"],
            "active_gateway_id": path["active_gateway_id"],
            "lease_expires_at": path["lease_expires_at"],
            "candidate_transport": path["candidate_transport"],
            "candidate_gateway_id": path["candidate_gateway_id"],
            "previous_transport": path["previous_transport"],
            "previous_gateway_id": path["previous_gateway_id"],
            "old_grace_until": path["old_grace_until"],
            "canonical_boot_session_hex": path["canonical_boot_session_hex"],
            "canonical_seq": path["canonical_seq"],
            "revision": path["revision"],
            "highest_session_hex": replay["highest_session_hex"],
        }
    finally:
        connection.close()


def _authorization_state(database: Path) -> dict[str, object]:
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        grant = connection.execute(
            """
            SELECT enabled FROM n3w_relay_gateway_nodes
            WHERE gateway_id=? AND node_id=?
            """,
            (GATEWAY_ID, NODE_ID),
        ).fetchone()
        operation = connection.execute(
            """
            SELECT status FROM n3w_relay_operations
            WHERE operation_key=?
            """,
            (f"revoke-grant:{GATEWAY_ID}:{NODE_ID}",),
        ).fetchone()
        return {
            "grant_enabled": None if grant is None else grant["enabled"],
            "operation_status": None if operation is None else operation["status"],
        }
    finally:
        connection.close()


def _create_active_state(
    tmp_path: Path,
) -> tuple[Path, Path, Path, ReplayRegistry, RelayAuthorizationAdmin]:
    replay_database = tmp_path / "replay.sqlite3"
    authorization_database = tmp_path / "relay-authorization.sqlite3"
    key_dir = tmp_path / "relay-keys"
    replay = ReplayRegistry(replay_database)
    path = N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=POLICY,
        ingress_allowed=lambda _node_id: True,
    )
    accepted = path.process(
        node_id=NODE_ID,
        boot_id=BOOT_ID,
        seq=41,
        owner=RELAY,
        now=NOW,
    )
    assert accepted.status == "accepted"
    admin = RelayAuthorizationAdmin(
        authorization_database,
        key_dir,
        node_state=lambda _node_id: "active",
        path_invalidator=ReplayPathLeaseInvalidator(replay),
    )
    admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
    staged = admin.stage_key(node_id=NODE_ID, key_material=KEY)
    admin.activate_key(node_id=NODE_ID, key_epoch=int(staged["key_epoch"]))
    return authorization_database, key_dir, replay_database, replay, admin


def test_m10_plan_is_host_only_and_live_execution_is_separately_gated() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))

    assert document["status"] == "host_only_contract_ready_live_execution_prohibited"
    assert document["base"] == {
        "repository": "chrenguo-stack/HomeAssistant",
        "branch": "main",
        "commit_sha": "a0583eb978c7d5630379d9859a52ce66e4b1b654",
        "tree_sha": "d6bf9e96a666a6d2b45f45fc11262768f2b21922",
    }
    assert document["matrix_contract"] == {
        "id": "M10",
        "name": "authorization_revoke",
        "action": "lab admin revoke-grant",
        "expect": "Relay ingress fail closed and Relay lease invalidated",
    }
    assert document["development_authorization"]["consumed"] is True
    assert document["development_authorization"]["replay_allowed"] is False
    assert document["future_live_preflight"]["authorized_now"] is False
    assert document["future_live_transaction"]["authorized_now"] is False
    assert document["future_live_transaction"]["maximum_revoke_attempts"] == 1
    assert document["future_live_transaction"]["automatic_retry"] is False
    assert document["next_gate"]["m10_live_allowed"] is False
    assert document["next_gate"]["m11_allowed"] is False


def test_m10_revoke_is_immediate_fail_closed_and_invalidates_path(
    tmp_path: Path,
) -> None:
    authorization_db, key_dir, replay_db, replay, admin = _create_active_state(tmp_path)
    provider = SqliteRelayAuthorizationProvider(authorization_db, key_dir)
    try:
        assert (
            provider.resolve_key(gateway_id=GATEWAY_ID, node_id=NODE_ID, key_epoch=1)
            == KEY
        )
        before = _path_state(replay_db)
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=41).status == (
            "duplicate"
        )

        result = admin.revoke_grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)

        assert result["status"] == "passed"
        assert result["operation"] == "revoke_grant"
        assert result["recovery_pending"] is False
        assert result["secret_values_included"] is False
        with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
            provider.resolve_key(gateway_id=GATEWAY_ID, node_id=NODE_ID, key_epoch=1)

        authorization = _authorization_state(authorization_db)
        after = _path_state(replay_db)
        assert authorization == {
            "grant_enabled": 0,
            "operation_status": "DONE",
        }
        assert after["active_transport"] == "relay"
        assert after["active_gateway_id"] == REVOKED_GATEWAY_SENTINEL
        assert after["lease_expires_at"] == "1970-01-01T00:00:00.000Z"
        assert after["candidate_transport"] is None
        assert after["candidate_gateway_id"] is None
        assert after["previous_transport"] == "relay"
        assert after["previous_gateway_id"] == GATEWAY_ID
        assert after["old_grace_until"] == "1970-01-01T00:00:00.000Z"
        assert (
            after["canonical_boot_session_hex"] == before["canonical_boot_session_hex"]
        )
        assert after["canonical_seq"] == before["canonical_seq"]
        assert after["highest_session_hex"] == before["highest_session_hex"]
        assert after["revision"] == int(before["revision"]) + 1
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=41).status == (
            "duplicate"
        )
    finally:
        provider.close()
        admin.close()
        replay.close()


def test_m10_path_cleanup_failure_stays_revoked_and_blocks_regrant(
    tmp_path: Path,
) -> None:
    authorization_db = tmp_path / "relay-authorization.sqlite3"
    key_dir = tmp_path / "relay-keys"

    def fail_path_cleanup(*, node_id: str, gateway_id: str) -> None:
        assert node_id == NODE_ID
        assert gateway_id == GATEWAY_ID
        raise RuntimeError("synthetic_path_cleanup_failure")

    admin = RelayAuthorizationAdmin(
        authorization_db,
        key_dir,
        node_state=lambda _node_id: "active",
        path_invalidator=fail_path_cleanup,
    )
    try:
        admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
        staged = admin.stage_key(node_id=NODE_ID, key_material=KEY)
        admin.activate_key(node_id=NODE_ID, key_epoch=int(staged["key_epoch"]))
        provider = SqliteRelayAuthorizationProvider(authorization_db, key_dir)
        try:
            result = admin.revoke_grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
            assert result["status"] == "passed"
            assert result["recovery_pending"] is True
            assert _authorization_state(authorization_db) == {
                "grant_enabled": 0,
                "operation_status": "AUTH_REVOKED_PATH_PENDING",
            }
            with pytest.raises(RelayIngressRejected, match="gateway_node_unauthorized"):
                provider.resolve_key(
                    gateway_id=GATEWAY_ID, node_id=NODE_ID, key_epoch=1
                )
            with pytest.raises(
                RelayAuthorizationAdminError, match="grant_recovery_pending"
            ):
                admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
        finally:
            provider.close()
    finally:
        admin.close()


def test_m10_lab_admin_and_compose_bind_both_durability_domains() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    lab_admin_service = compose.split("\n  lab-admin:\n", maxsplit=1)[1].split(
        "\nvolumes:\n", maxsplit=1
    )[0]
    source = LAB_ADMIN.read_text(encoding="utf-8")

    assert 'profiles: ["admin"]' in lab_admin_service
    assert 'entrypoint: ["python", "/lab_admin.py"]' in lab_admin_service
    assert "- manager-state:/state" in lab_admin_service
    assert "ReplayRegistry(REPLAY)" in source
    assert "ReplayPathLeaseInvalidator(replay)" in source
    assert "admin.revoke_grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)" in source
    assert '"revoke-grant": command_revoke_grant' in source


def test_m10_change_set_contains_no_live_executor_or_secret_material() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    expected = {
        ".github/workflows/n3w-p5-m10-authorization-revoke-host-only-ci.yml",
        "docs/decisions/n3w-p5-m10-authorization-revoke-host-only-plan.json",
        "tests/n3w_p5/test_n3w_p5_m10_authorization_revoke_contract.py",
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
