from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANAGER_SRC = ROOT / "host/greenhouse-manager/src"
sys.path.insert(0, str(MANAGER_SRC))

from greenhouse_manager.runtime.n3w_path_lease import (
    N3wPathLeaseCoordinator,
    PathLeasePolicy,
    PathOwner,
)
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

PLAN = ROOT / "docs/decisions/n3w-p5-m09-manager-restart-host-only-plan.json"
COMPOSE = ROOT / "infra/compose/n3w-p5-two-board-isolated/docker-compose.yml"
MQTT_SERVICE = (
    ROOT / "host/greenhouse-manager/src/greenhouse_manager/runtime/mqtt_service.py"
)
WORKFLOW = ROOT / ".github/workflows/n3w-p5-m09-manager-restart-host-only-ci.yml"

NODE_ID = "n3wp5_child01"
GATEWAY_ID = "n3wp5_relay01"
BOOT_1 = "boot_0000000000000001"
RELAY = PathOwner("relay", GATEWAY_ID)
DIRECT = PathOwner("direct")
NOW = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)
POLICY = PathLeasePolicy(
    stability_window_s=5,
    minimum_distinct_frames=2,
    lease_ttl_s=30,
    old_path_grace_s=5,
)


def _coordinator(database: Path) -> tuple[ReplayRegistry, N3wPathLeaseCoordinator]:
    replay = ReplayRegistry(database)
    path = N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=POLICY,
        ingress_allowed=lambda _node_id: True,
    )
    return replay, path


def _state(database: Path) -> dict[str, object]:
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        replay = connection.execute(
            "SELECT node_id, highest_session_hex FROM n3w_replay_state"
        ).fetchone()
        path = connection.execute("SELECT * FROM n3w_path_leases").fetchone()
        assert replay is not None and path is not None
        return {
            "highest_session_hex": replay["highest_session_hex"],
            "active_transport": path["active_transport"],
            "active_gateway_id": path["active_gateway_id"],
            "candidate_transport": path["candidate_transport"],
            "candidate_gateway_id": path["candidate_gateway_id"],
            "candidate_last_boot_id": path["candidate_last_boot_id"],
            "candidate_last_seq": path["candidate_last_seq"],
            "candidate_distinct_count": path["candidate_distinct_count"],
            "canonical_boot_session_hex": path["canonical_boot_session_hex"],
            "canonical_seq": path["canonical_seq"],
            "revision": path["revision"],
        }
    finally:
        connection.close()


def test_m09_plan_is_host_only_and_live_execution_is_separately_gated() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))

    assert document["status"] == "host_only_contract_ready_live_execution_prohibited"
    assert document["base"] == {
        "repository": "chrenguo-stack/HomeAssistant",
        "branch": "main",
        "commit_sha": "ffd9d00c0107e4893166c05939183dc702a30f83",
        "tree_sha": "b058be3142b04fe27db0c345469370ce85a48b46",
    }
    assert document["matrix_contract"] == {
        "id": "M09",
        "name": "manager_restart",
        "action": "restart isolated manager container only",
        "expect": "path lease and replay/high-water restore",
    }
    assert document["development_authorization"]["consumed"] is True
    assert document["development_authorization"]["replay_allowed"] is False
    assert document["future_live_preflight"]["authorized_now"] is False
    assert document["future_live_transaction"]["authorized_now"] is False
    assert document["future_live_transaction"]["maximum_restart_attempts"] == 1
    assert document["future_live_transaction"]["automatic_retry"] is False
    assert document["next_gate"]["m09_live_allowed"] is False
    assert document["evidence_contract"]["secret_values_included"] is False


def test_m09_manager_restart_preserves_active_path_replay_and_cursor(
    tmp_path: Path,
) -> None:
    database = tmp_path / "replay.sqlite3"
    replay, path = _coordinator(database)
    try:
        accepted = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=41,
            owner=RELAY,
            now=NOW,
        )
        assert accepted.status == "accepted"
        before = _state(database)
    finally:
        replay.close()

    reopened_replay, reopened_path = _coordinator(database)
    try:
        after_reopen = _state(database)
        duplicate = reopened_path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=41,
            owner=RELAY,
            now=NOW + timedelta(seconds=1),
        )
        advanced = reopened_path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=42,
            owner=RELAY,
            now=NOW + timedelta(seconds=2),
        )
        final = _state(database)
    finally:
        reopened_replay.close()

    assert after_reopen == before
    assert duplicate.status == "duplicate"
    assert advanced.status == "accepted"
    assert final["highest_session_hex"] == "0000000000000001"
    assert final["active_transport"] == "relay"
    assert final["active_gateway_id"] == GATEWAY_ID
    assert final["candidate_transport"] is None
    assert final["canonical_boot_session_hex"] == "0000000000000001"
    assert final["canonical_seq"] == 42
    assert final["revision"] == int(before["revision"]) + 1


def test_m09_manager_restart_preserves_candidate_without_consuming_tuple(
    tmp_path: Path,
) -> None:
    database = tmp_path / "replay.sqlite3"
    replay, path = _coordinator(database)
    try:
        path.process(node_id=NODE_ID, boot_id=BOOT_1, seq=1, owner=RELAY, now=NOW)
        pending = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=2,
            owner=DIRECT,
            now=NOW + timedelta(seconds=1),
        )
        assert pending.code == "path_candidate_pending"
        before = _state(database)
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=2).status == "ready"
    finally:
        replay.close()

    reopened_replay, reopened_path = _coordinator(database)
    try:
        after_reopen = _state(database)
        assert after_reopen == before
        assert (
            reopened_replay.inspect(node_id=NODE_ID, boot_id=BOOT_1, seq=2).status
            == "ready"
        )
        switched = reopened_path.process(
            node_id=NODE_ID,
            boot_id=BOOT_1,
            seq=3,
            owner=DIRECT,
            now=NOW + timedelta(seconds=6),
        )
    finally:
        reopened_replay.close()

    assert switched.status == "accepted"
    assert switched.switched is True
    assert switched.active_owner == DIRECT


def test_m09_compose_and_retained_restore_wiring_are_persistent() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    manager = compose.split("\n  manager:\n", maxsplit=1)[1].split(
        "\n  lab-admin:\n", maxsplit=1
    )[0]
    mqtt_service = MQTT_SERVICE.read_text(encoding="utf-8")

    assert "GH_N3W_REPLAY_DB_PATH: /state/n3w/replay.sqlite3" in manager
    assert (
        "GH_N3W_RELAY_AUTHORIZATION_DB_PATH: /state/n3w/relay-authorization.sqlite3"
        in manager
    )
    assert "- manager-state:/state" in manager
    assert "canonical_telemetry_subscription(self.settings.system_id)" in mqtt_service
    assert (
        "self.processor.restore_canonical(message.topic, message.payload)"
        in mqtt_service
    )


def test_m09_change_set_contains_no_live_executor_or_secret_material() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    expected = {
        ".github/workflows/n3w-p5-m09-manager-restart-host-only-ci.yml",
        "docs/decisions/n3w-p5-m09-manager-restart-host-only-plan.json",
        "tests/n3w_p5/test_n3w_p5_m09_manager_restart_contract.py",
    }
    assert set(document["change_scope"]["allowed"]) == expected

    forbidden_workflow_tokens = (
        "docker --context",
        "mosquitto_pub",
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
