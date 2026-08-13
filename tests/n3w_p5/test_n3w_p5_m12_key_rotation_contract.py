from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[2]
MANAGER_SRC = ROOT / "host/greenhouse-manager/src"
sys.path.insert(0, str(MANAGER_SRC))

from greenhouse_manager.ops.n3w_relay_authorization_admin import (
    RelayAuthorizationAdmin,
)
from greenhouse_manager.runtime.ingest import TelemetryProcessor
from greenhouse_manager.runtime.n3w_ingress_router import N3wManagerIngressRouter
from greenhouse_manager.runtime.n3w_path_lease import (
    N3wPathLeaseCoordinator,
    PathLeasePolicy,
)
from greenhouse_manager.runtime.n3w_relay_authorization import (
    SqliteRelayAuthorizationProvider,
)
from greenhouse_manager.runtime.n3w_relay_ingress import (
    N3wRelayIngressCore,
    RelayEnvelope,
    build_aad,
    derive_nonce,
)
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

PLAN = ROOT / "docs/decisions/n3w-p5-m12-key-rotation-host-only-plan.json"
MATRIX = ROOT / "docs/decisions/n3w-p5-two-board-isolated-e2e-execution-plan.json"
COMPOSE = ROOT / "infra/compose/n3w-p5-two-board-isolated/docker-compose.yml"
LAB_ADMIN = ROOT / "infra/compose/n3w-p5-two-board-isolated/lab_admin.py"
CHILD_YAML = ROOT / "firmware/esphome_rc/board_lab/n3w_p5_two_board/child.yml"
P5_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.cpp"
WORKFLOW = ROOT / ".github/workflows/n3w-p5-m12-key-rotation-host-only-ci.yml"

SYSTEM_ID = "n3wp5lab"
NODE_ID = "n3wp5_child01"
GATEWAY_ID = "n3wp5_relay01"
BOOT_ID = "boot_0000000000000001"
KEY_1 = bytes.fromhex("11" * 32)
KEY_2 = bytes.fromhex("22" * 32)
KEY_UNKNOWN = bytes.fromhex("33" * 32)
RELAY_TOPIC = f"gh/v1/{SYSTEM_ID}/ingress/gateway/{GATEWAY_ID}/{NODE_ID}/frame"
NOW = datetime(2026, 8, 13, 3, 0, tzinfo=UTC)
POLICY = PathLeasePolicy(
    stability_window_s=5,
    minimum_distinct_frames=2,
    lease_ttl_s=30,
    old_path_grace_s=5,
)


def _telemetry(seq: int) -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": BOOT_ID,
        "seq": seq,
        "uptime_ms": seq * 5000,
        "cap_hash": "cap_hash_m12",
        "measurements": {"air_temperature_c": 24.5},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "main", "low": False},
    }


def _relay_payload(*, key_epoch: int, key: bytes, seq: int) -> bytes:
    document = _telemetry(seq)
    nonce = derive_nonce(BOOT_ID, seq)
    envelope = RelayEnvelope(
        schema="gh.relay/1",
        transport="esp_now",
        gateway_id=GATEWAY_ID,
        node_id=NODE_ID,
        hop_count=1,
        key_epoch=key_epoch,
        boot_id=BOOT_ID,
        seq=seq,
        nonce=nonce,
        ciphertext=b"placeholder",
        tag=b"0" * 16,
    )
    sealed = AESGCM(key).encrypt(
        nonce,
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode(),
        build_aad(envelope),
    )
    outer = {
        "schema": "gh.relay/1",
        "transport": "esp_now",
        "gateway_id": GATEWAY_ID,
        "node_id": NODE_ID,
        "hop_count": 1,
        "key_epoch": key_epoch,
        "boot_id": BOOT_ID,
        "seq": seq,
        "nonce_b64": base64.b64encode(nonce).decode(),
        "ciphertext_b64": base64.b64encode(sealed[:-16]).decode(),
        "tag_b64": base64.b64encode(sealed[-16:]).decode(),
    }
    return json.dumps(outer, separators=(",", ":")).encode()


def _path_state(database: Path) -> dict[str, object]:
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        row = connection.execute(
            "SELECT * FROM n3w_path_leases WHERE node_id=?", (NODE_ID,)
        ).fetchone()
        assert row is not None
        replay = connection.execute(
            "SELECT highest_session_hex FROM n3w_replay_state WHERE node_id=?",
            (NODE_ID,),
        ).fetchone()
        assert replay is not None
        return {
            "active_transport": row["active_transport"],
            "active_gateway_id": row["active_gateway_id"],
            "candidate_transport": row["candidate_transport"],
            "candidate_gateway_id": row["candidate_gateway_id"],
            "canonical_boot_session_hex": row["canonical_boot_session_hex"],
            "canonical_seq": row["canonical_seq"],
            "revision": row["revision"],
            "highest_session_hex": replay["highest_session_hex"],
        }
    finally:
        connection.close()


def _key_states(database: Path) -> dict[int, tuple[str, int]]:
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    try:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        return {
            int(epoch): (str(state), int(enabled))
            for epoch, state, enabled in connection.execute(
                "SELECT key_epoch,state,enabled FROM n3w_relay_key_epochs "
                "WHERE node_id=? ORDER BY key_epoch",
                (NODE_ID,),
            )
        }
    finally:
        connection.close()


def _make_runtime(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    ReplayRegistry,
    RelayAuthorizationAdmin,
    SqliteRelayAuthorizationProvider,
    N3wManagerIngressRouter,
]:
    authorization_database = tmp_path / "relay-authorization.sqlite3"
    key_dir = tmp_path / "relay-keys"
    replay_database = tmp_path / "replay.sqlite3"
    admin = RelayAuthorizationAdmin(
        authorization_database,
        key_dir,
        node_state=lambda _node_id: "active",
    )
    admin.grant(gateway_id=GATEWAY_ID, node_id=NODE_ID)
    assert admin.stage_key(node_id=NODE_ID, key_material=KEY_1)["key_epoch"] == 1
    admin.activate_key(node_id=NODE_ID, key_epoch=1)
    assert admin.stage_key(node_id=NODE_ID, key_material=KEY_2)["key_epoch"] == 2

    provider = SqliteRelayAuthorizationProvider(authorization_database, key_dir)
    replay = ReplayRegistry(replay_database)
    relay_core = N3wRelayIngressCore(
        system_id=SYSTEM_ID,
        authorization=provider,
        replay_registry=replay,
    )
    path = N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=POLICY,
        ingress_allowed=lambda _node_id: True,
    )
    router = N3wManagerIngressRouter(
        processor=TelemetryProcessor(system_id=SYSTEM_ID),
        replay_registry=replay,
        relay_core=relay_core,
        path_lease=path,
    )
    return authorization_database, replay_database, replay, admin, provider, router


def test_m12_plan_is_host_only_and_live_rotation_is_separately_gated() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    assert document["status"] == "host_only_contract_ready_live_execution_prohibited"
    assert document["base"] == {
        "repository": "chrenguo-stack/HomeAssistant",
        "branch": "main",
        "commit_sha": "b4f07a5fd836124ae2fbdb2f01e28402481b15e7",
        "tree_sha": "252d1b0955d55606afec52fb552b43df4e326e7d",
    }
    expected_matrix = {
        "id": "M12",
        "name": "key_rotation",
        "action": "activate epoch2 then Child KEY 2",
        "expect": "epoch2 accepted; canonical continuous; epoch1 grace semantics observable",
    }
    assert document["matrix_contract"] == expected_matrix
    assert expected_matrix in matrix["matrix"]
    assert document["development_authorization"]["consumed"] is True
    assert document["development_authorization"]["replay_allowed"] is False
    assert document["future_live_preflight"]["authorized_now"] is False
    assert document["future_live_transaction"]["authorized_now"] is False
    assert document["future_live_transaction"]["maximum_rotate_invocations"] == 1
    assert document["future_live_transaction"]["maximum_child_key_2_publishes"] == 1
    assert document["future_live_transaction"]["automatic_retry"] is False
    assert document["next_gate"]["m12_live_allowed"] is False
    assert document["next_gate"]["m13_allowed"] is False


def test_m12_real_aead_rotation_preserves_path_replay_and_canonical_stream(
    tmp_path: Path,
) -> None:
    auth_db, replay_db, replay, admin, provider, router = _make_runtime(tmp_path)
    try:
        assert _key_states(auth_db) == {1: ("ACTIVE", 1), 2: ("STAGED", 0)}
        epoch1_active = router.process_relay(
            RELAY_TOPIC,
            _relay_payload(key_epoch=1, key=KEY_1, seq=1),
            received_at=NOW,
        )
        assert epoch1_active.status == "accepted"
        before_activation = _path_state(replay_db)
        assert before_activation["canonical_seq"] == 1

        activated = admin.activate_key(node_id=NODE_ID, key_epoch=2)
        assert activated == {
            "schema": "gh.n3w-relay-authorization-admin-result/1",
            "status": "passed",
            "operation": "activate_key",
            "node_id": NODE_ID,
            "gateway_id": None,
            "key_epoch": 2,
            "recovery_pending": False,
            "secret_values_included": False,
        }
        assert _key_states(auth_db) == {1: ("GRACE", 1), 2: ("ACTIVE", 1)}
        assert _path_state(replay_db) == before_activation
        assert (
            provider.resolve_key(gateway_id=GATEWAY_ID, node_id=NODE_ID, key_epoch=1)
            == KEY_1
        )
        assert (
            provider.resolve_key(gateway_id=GATEWAY_ID, node_id=NODE_ID, key_epoch=2)
            == KEY_2
        )

        epoch1_grace = router.process_relay(
            RELAY_TOPIC,
            _relay_payload(key_epoch=1, key=KEY_1, seq=2),
            received_at=NOW + timedelta(seconds=5),
        )
        epoch2_active = router.process_relay(
            RELAY_TOPIC,
            _relay_payload(key_epoch=2, key=KEY_2, seq=3),
            received_at=NOW + timedelta(seconds=10),
        )
        assert epoch1_grace.status == epoch2_active.status == "accepted"

        final = _path_state(replay_db)
        assert final["active_transport"] == "relay"
        assert final["active_gateway_id"] == GATEWAY_ID
        assert final["candidate_transport"] is None
        assert final["candidate_gateway_id"] is None
        assert final["canonical_boot_session_hex"] == "0000000000000001"
        assert final["highest_session_hex"] == "0000000000000001"
        assert final["canonical_seq"] == 3
        assert int(final["revision"]) == int(before_activation["revision"]) + 2
    finally:
        provider.close()
        admin.close()
        replay.close()


def test_m12_epoch_change_cannot_bypass_replay_and_rejections_do_not_consume(
    tmp_path: Path,
) -> None:
    auth_db, _replay_db, replay, admin, provider, router = _make_runtime(tmp_path)
    try:
        admin.activate_key(node_id=NODE_ID, key_epoch=2)
        assert (
            router.process_relay(
                RELAY_TOPIC,
                _relay_payload(key_epoch=1, key=KEY_1, seq=1),
                received_at=NOW,
            ).status
            == "accepted"
        )
        cross_epoch = router.process_relay(
            RELAY_TOPIC,
            _relay_payload(key_epoch=2, key=KEY_2, seq=1),
            received_at=NOW,
        )
        assert cross_epoch.status == "duplicate"
        assert cross_epoch.code == "duplicate_node_boot_seq"

        unknown = router.process_relay(
            RELAY_TOPIC,
            _relay_payload(key_epoch=3, key=KEY_UNKNOWN, seq=2),
            received_at=NOW + timedelta(seconds=5),
        )
        assert unknown.status == "rejected"
        assert unknown.code == "key_epoch_rejected"
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=2).status == "ready"
        assert (
            router.process_relay(
                RELAY_TOPIC,
                _relay_payload(key_epoch=2, key=KEY_2, seq=2),
                received_at=NOW + timedelta(seconds=5),
            ).status
            == "accepted"
        )

        admin.revoke_key(node_id=NODE_ID, key_epoch=1)
        assert _key_states(auth_db) == {1: ("REVOKED", 0), 2: ("ACTIVE", 1)}
        revoked = router.process_relay(
            RELAY_TOPIC,
            _relay_payload(key_epoch=1, key=KEY_1, seq=3),
            received_at=NOW + timedelta(seconds=10),
        )
        assert revoked.status == "rejected"
        assert revoked.code == "key_epoch_rejected"
        assert replay.inspect(node_id=NODE_ID, boot_id=BOOT_ID, seq=3).status == "ready"
        assert (
            router.process_relay(
                RELAY_TOPIC,
                _relay_payload(key_epoch=2, key=KEY_2, seq=3),
                received_at=NOW + timedelta(seconds=10),
            ).status
            == "accepted"
        )
    finally:
        provider.close()
        admin.close()
        replay.close()


def test_m12_child_key_2_changes_epoch_only_and_keeps_frame_binding() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    child_yaml = CHILD_YAML.read_text(encoding="utf-8")
    start = source.index('} else if (is_child_ && command == "KEY 2") {')
    end = source.index("} else if", start + 1)
    branch = source[start:end]

    assert "selected_key_epoch_ = 2;" in branch
    assert "Lab command: KEY epoch 2" in branch
    for forbidden in (
        "esp_restart",
        "desired_path_",
        "invalidate_relay_auth_",
        "relay_authenticated_",
        "boot_",
        "seq",
        "RESEND",
        "REORDER",
        "driver_",
    ):
        assert forbidden not in branch

    assert "return selected_key_epoch_ == 2 ? &key_epoch2_ : &key_epoch1_;" in source
    assert "header.key_epoch = selected_key_epoch_;" in source
    assert "build_relay_frame(header, *active_key_(), telemetry" in source
    assert "Relay must not receive Child application key material" in source
    assert "gh/p5/${p5_system_id}/control/${p5_node_id}" in child_yaml
    assert "handle_lab_command(x);" in child_yaml


def test_m12_lab_admin_wiring_and_secret_free_audit_contract() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    source = LAB_ADMIN.read_text(encoding="utf-8")
    service = compose.split("\n  lab-admin:\n", maxsplit=1)[1].split(
        "\nvolumes:\n", maxsplit=1
    )[0]

    assert 'profiles: ["admin"]' in service
    assert 'entrypoint: ["python", "/lab_admin.py"]' in service
    assert "- manager-state:/state" in service
    assert "GH_P5_APP_KEY_EPOCH1_HEX" in compose
    assert "GH_P5_APP_KEY_EPOCH2_HEX" in compose
    assert "admin.activate_key(node_id=NODE_ID, key_epoch=2)" in source
    assert '"rotate": command_rotate' in source

    document = json.loads(PLAN.read_text(encoding="utf-8"))
    assert document["evidence_contract"]["secret_values_included"] is False
    assert document["future_live_transaction"]["automatic_rollback"] is False
    assert document["future_live_transaction"]["automatic_epoch1_revoke"] is False


def test_m12_change_set_contains_no_live_executor_or_secret_material() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    expected = {
        ".github/workflows/n3w-p5-m12-key-rotation-host-only-ci.yml",
        "docs/decisions/n3w-p5-m12-key-rotation-host-only-plan.json",
        "tests/n3w_p5/test_n3w_p5_m12_key_rotation_contract.py",
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
    assert b"GH_P5_APP_KEY_EPOCH1_" + b"HEX=" not in combined
    assert b"GH_P5_APP_KEY_EPOCH2_" + b"HEX=" not in combined
    assert hashlib.sha256(combined).hexdigest()
