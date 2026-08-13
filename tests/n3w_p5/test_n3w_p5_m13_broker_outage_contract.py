from __future__ import annotations

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

PLAN = ROOT / "docs/decisions/n3w-p5-m13-broker-outage-host-only-plan.json"
MATRIX = ROOT / "docs/decisions/n3w-p5-two-board-isolated-e2e-execution-plan.json"
P5_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.cpp"
P5_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_p5_lab/n3w_p5_lab.h"
RADIO_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.cpp"
RADIO_H = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_radio.h"
LIVENESS_HOST_TEST = ROOT / "tests/n3w_p5/n3w_p5_liveness_host_test.cpp"

NODE_ID = "n3wp5_child01"
GATEWAY_ID = "n3wp5_relay01"
BOOT_ID = "boot_0000000000000001"
RELAY = PathOwner("relay", GATEWAY_ID)
NOW = datetime(2026, 8, 13, 4, 0, tzinfo=UTC)
POLICY = PathLeasePolicy(
    stability_window_s=0,
    minimum_distinct_frames=1,
    lease_ttl_s=30,
    old_path_grace_s=0,
)


def _function_body(text: str, signature: str, next_signature: str) -> str:
    start = text.index(signature)
    return text[start : text.index(next_signature, start)]


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
            "candidate_transport": row["candidate_transport"],
            "candidate_gateway_id": row["candidate_gateway_id"],
            "canonical_boot_session_hex": row["canonical_boot_session_hex"],
            "canonical_seq": row["canonical_seq"],
            "revision": row["revision"],
        }
    finally:
        connection.close()


def test_m13_plan_is_exactly_host_only_and_live_outage_is_separately_gated() -> None:
    document = json.loads(PLAN.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    expected_matrix = {
        "id": "M13",
        "name": "broker_outage",
        "action": "stop isolated broker, wait through retry window, restore broker",
        "expect": (
            "no false positive ReceiptAck; bounded retry; recovery without duplicate "
            "canonical"
        ),
    }
    assert document["status"] == "host_only_contract_ready_live_execution_prohibited"
    assert document["base"] == {
        "repository": "chrenguo-stack/HomeAssistant",
        "branch": "main",
        "commit_sha": "6bc4bd403d3913daf28017eea82dfab391265908",
        "tree_sha": "54112010e5ec034c7954147fe38d9669f7b42463",
    }
    assert document["matrix_contract"] == expected_matrix
    assert expected_matrix in matrix["matrix"]
    assert document["m12_dependency"]["classification"] == "PASS"
    assert document["development_authorization"]["consumed"] is True
    assert document["development_authorization"]["replay_allowed"] is False
    assert document["change_scope"]["manager_product_runtime_change"] is False
    assert document["change_scope"]["compose_change"] is False
    assert document["change_scope"]["firmware_change"] is False
    assert document["future_live_preflight"]["authorized_now"] is False
    assert document["future_live_transaction"]["authorized_now"] is False
    assert document["future_live_transaction"]["automatic_retry"] is False
    assert document["next_gate"]["m13_live_allowed"] is False
    assert document["next_gate"]["m14_allowed"] is False


def test_disconnected_or_failed_mqtt_publish_cannot_claim_forward_acceptance() -> None:
    p5 = P5_CPP.read_text(encoding="utf-8")
    radio = RADIO_CPP.read_text(encoding="utf-8")
    forward = _function_body(
        p5,
        "bool GreenhouseN3wP5Lab::accept_for_forwarding",
        "void GreenhouseN3wP5Lab::invalidate_relay_auth_",
    )
    ingress = _function_body(
        radio,
        "RadioError RelayIngressController::accept_fragment",
        "RadioError ChannelScanPlan::configure",
    )

    connected = forward.index("!mqtt::global_mqtt_client->is_connected()")
    publish = forward.index("global_mqtt_client->publish")
    assert connected < publish
    assert "return false" in forward[:publish]
    assert "return mqtt::global_mqtt_client->publish" in forward

    sink = ingress.index("sink_->accept_for_forwarding(frame)")
    status = ingress.index("ReceiptStatus::ACCEPTED_FOR_FORWARDING", sink)
    rejected = ingress.index("ReceiptStatus::REJECTED", status)
    assert sink < status < rejected
    assert "*receipt_ready = accepted" in ingress


def test_rejected_receipt_retains_exact_tuple_and_retry_window_is_bounded() -> None:
    header = P5_H.read_text(encoding="utf-8")
    radio_header = RADIO_H.read_text(encoding="utf-8")
    radio = RADIO_CPP.read_text(encoding="utf-8")
    host_test = LIVENESS_HOST_TEST.read_text(encoding="utf-8")

    assert "ChildRelayCache cache_{4, RetryPolicy{500, 8000, 5}};" in header
    policy = _function_body(
        radio, "bool RetryPolicy::valid()", "uint64_t ChildRelayCache"
    )
    attempt = _function_body(
        radio,
        "RadioError ChildRelayCache::note_attempt",
        "bool ChildRelayCache::acknowledge",
    )
    acknowledge = _function_body(
        radio,
        "bool ChildRelayCache::acknowledge",
        "bool LocalPathPolicy::valid",
    )
    cache = _function_body(
        radio_header,
        "class ChildRelayCache",
        "enum class LocalPathState",
    )

    assert "initial_delay_ms > 0" in policy
    assert "max_delay_ms >= initial_delay_ms" in policy
    assert "max_attempts > 0" in policy
    assert "++entry->attempts" in attempt
    assert "entry->attempts >= policy_.max_attempts" in attempt
    assert "delay *= 2U" in attempt
    assert "std::min<uint64_t>(delay, policy_.max_delay_ms)" in attempt
    assert "ack.status != ReceiptStatus::ACCEPTED_FOR_FORWARDING" in acknowledge
    assert "it->boot_session == ack.boot_session && it->seq == ack.seq" in acknowledge
    assert "bool discard(uint64_t boot_session, uint32_t seq)" in cache

    assert "test_rejected_forwarding_has_exact_rejected_receipt_identity" in host_test
    assert "test_rejected_receipt_does_not_claim_forward_success" in host_test
    assert "cache.size() == 1" in host_test
    assert [0, 500, 1500, 3500, 7500] == [
        0,
        500,
        500 + 1000,
        500 + 1000 + 2000,
        500 + 1000 + 2000 + 4000,
    ]


def test_retry_exhaustion_discards_exact_tuple_and_requires_fresh_probe() -> None:
    source = P5_CPP.read_text(encoding="utf-8")
    flush = _function_body(
        source,
        "void GreenhouseN3wP5Lab::flush_relay_cache_",
        "bool GreenhouseN3wP5Lab::send_datagrams_",
    )
    probe = _function_body(
        source,
        "void GreenhouseN3wP5Lab::process_relay_packet_",
        "bool GreenhouseN3wP5Lab::accept_for_forwarding",
    )

    note = flush.index("cache_.note_attempt(session, seq, now)")
    exhausted = flush.index("RadioError::RETRY_EXHAUSTED")
    discard = flush.index("cache_.discard(session, seq)")
    invalidate = flush.index('invalidate_relay_auth_("receipt_ack_retry_exhausted")')
    assert note < exhausted < discard < invalidate

    decode = probe.index("decode_authenticated_probe(")
    reset = probe.index("relay_ingress_.reset()", decode)
    establish = probe.index("relay_probe_established_since_boot_ = true", reset)
    gate = probe.index("if (!relay_probe_established_since_boot_)", establish)
    reassembly = probe.index("relay_ingress_.accept_fragment", gate)
    assert decode < reset < establish < gate < reassembly


def test_recovery_and_delayed_duplicate_create_only_one_canonical_commit(
    tmp_path: Path,
) -> None:
    database = tmp_path / "replay.sqlite3"
    replay = ReplayRegistry(database)
    path = N3wPathLeaseCoordinator(
        replay_registry=replay,
        policy=POLICY,
        ingress_allowed=lambda _node_id: True,
    )
    try:
        before_outage = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_ID,
            seq=100,
            owner=RELAY,
            now=NOW,
        )
        assert before_outage.status == "accepted"
        frozen_during_outage = _path_state(database)

        recovered = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_ID,
            seq=101,
            owner=RELAY,
            now=NOW + timedelta(seconds=10),
        )
        after_recovery = _path_state(database)
        duplicate = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_ID,
            seq=101,
            owner=RELAY,
            now=NOW + timedelta(seconds=11),
        )
        after_duplicate = _path_state(database)
        continued = path.process(
            node_id=NODE_ID,
            boot_id=BOOT_ID,
            seq=102,
            owner=RELAY,
            now=NOW + timedelta(seconds=12),
        )
        final = _path_state(database)
    finally:
        replay.close()

    assert frozen_during_outage["canonical_seq"] == 100
    assert recovered.status == "accepted"
    assert after_recovery["canonical_seq"] == 101
    assert duplicate.status == "duplicate"
    assert after_duplicate == after_recovery
    assert continued.status == "accepted"
    assert final["canonical_seq"] == 102
    assert final["revision"] > after_duplicate["revision"]
    assert final["canonical_boot_session_hex"] == "0000000000000001"
    assert final["active_transport"] == "relay"
    assert final["active_gateway_id"] == GATEWAY_ID
    assert final["candidate_transport"] is None
    assert final["candidate_gateway_id"] is None


def test_host_only_scope_contains_no_live_execution_tokens() -> None:
    changed = [PLAN]
    forbidden = (
        "docker stop",
        "docker start",
        "docker restart",
        "mosquitto_pub",
        "esphome run",
        "esptool",
        "/dev/cu.",
        "/dev/tty",
        "192.168.68.",
    )
    for path in changed:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
