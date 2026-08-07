from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from greenhouse_manager.runtime.n3w_relay_ingress import (
    N3wRelayIngressCore,
    PackagedTelemetryValidator,
    RelayEnvelope,
    StaticRelayAuthorizationProvider,
    build_aad,
    derive_nonce,
    parse_relay_envelope,
)
from greenhouse_manager.runtime.replay_registry import ReplayRegistry

SYSTEM_ID = "system_001"
GATEWAY_ID = "gateway_001"
NODE_ID = "node_0001"
OTHER_NODE_ID = "node_0002"
BOOT_1 = "boot_0000000000000001"
BOOT_2 = "boot_0000000000000002"
KEY_EPOCH = 1
KEY = bytes(range(32))
TOPIC = f"gh/v1/{SYSTEM_ID}/ingress/gateway/{GATEWAY_ID}/{NODE_ID}/frame"


def telemetry(*, node_id: str = NODE_ID, boot_id: str = BOOT_1, seq: int = 1) -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": node_id,
        "boot_id": boot_id,
        "seq": seq,
        "uptime_ms": 1234,
        "cap_hash": "cap_hash_001",
        "measurements": {"air_temperature_c": 24.5},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "main", "low": False},
    }


def authorization() -> StaticRelayAuthorizationProvider:
    return StaticRelayAuthorizationProvider(
        active_nodes=frozenset({NODE_ID}),
        gateway_nodes={GATEWAY_ID: frozenset({NODE_ID})},
        keys={(NODE_ID, KEY_EPOCH): KEY},
    )


def make_core(database: Path, *, auth: StaticRelayAuthorizationProvider | None = None) -> N3wRelayIngressCore:
    return N3wRelayIngressCore(
        system_id=SYSTEM_ID,
        authorization=auth or authorization(),
        replay_registry=ReplayRegistry(database),
    )


def relay_payload(
    document: dict[str, object],
    *,
    gateway_id: str = GATEWAY_ID,
    node_id: str = NODE_ID,
    boot_id: str = BOOT_1,
    seq: int = 1,
    key_epoch: int = KEY_EPOCH,
    key: bytes = KEY,
    hop_count: int = 1,
    nonce: bytes | None = None,
    aad_mutator: dict[str, object] | None = None,
) -> bytes:
    actual_nonce = nonce or derive_nonce(boot_id, seq)
    aad_envelope = RelayEnvelope(
        schema="gh.relay/1",
        transport="esp_now",
        gateway_id=gateway_id,
        node_id=node_id,
        hop_count=hop_count,
        key_epoch=key_epoch,
        boot_id=boot_id,
        seq=seq,
        nonce=actual_nonce,
        ciphertext=b"placeholder",
        tag=b"0" * 16,
    )
    aad_document = json.loads(build_aad(aad_envelope))
    if aad_mutator:
        aad_document.update(aad_mutator)
    aad = json.dumps(aad_document, separators=(",", ":"), sort_keys=True).encode()
    sealed = AESGCM(key).encrypt(
        actual_nonce,
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode(),
        aad,
    )
    ciphertext, tag = sealed[:-16], sealed[-16:]
    outer = {
        "schema": "gh.relay/1",
        "transport": "esp_now",
        "gateway_id": gateway_id,
        "node_id": node_id,
        "hop_count": hop_count,
        "key_epoch": key_epoch,
        "boot_id": boot_id,
        "seq": seq,
        "nonce_b64": base64.b64encode(actual_nonce).decode(),
        "ciphertext_b64": base64.b64encode(ciphertext).decode(),
        "tag_b64": base64.b64encode(tag).decode(),
    }
    return json.dumps(outer, separators=(",", ":")).encode()


def test_accepts_valid_relay_and_returns_existing_direct_ingress_handoff(tmp_path: Path) -> None:
    core = make_core(tmp_path / "replay.sqlite3")
    try:
        result = core.process(TOPIC, relay_payload(telemetry()))
        assert result.status == "accepted"
        assert result.code is None
        assert result.node_id == NODE_ID
        assert result.ingress_topic == f"gh/v1/{SYSTEM_ID}/ingress/node/{NODE_ID}/telemetry"
        assert result.telemetry == telemetry()
    finally:
        core.replay_registry.close()


def test_same_relay_tuple_is_duplicate_after_valid_aead_and_validation(tmp_path: Path) -> None:
    core = make_core(tmp_path / "replay.sqlite3")
    payload = relay_payload(telemetry())
    try:
        assert core.process(TOPIC, payload).status == "accepted"
        duplicate = core.process(TOPIC, payload)
        assert duplicate.status == "duplicate"
        assert duplicate.code == "duplicate_node_boot_seq"
    finally:
        core.replay_registry.close()


def test_direct_then_relay_and_relay_then_direct_share_persistent_replay_state(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    core = make_core(database)
    try:
        assert core.commit_validated_direct_tuple(node_id=NODE_ID, boot_id=BOOT_1, seq=1).status == "accepted"
        relay_duplicate = core.process(TOPIC, relay_payload(telemetry()))
        assert relay_duplicate.status == "duplicate"
        assert relay_duplicate.code == "duplicate_node_boot_seq"

        relay_second = core.process(
            TOPIC,
            relay_payload(telemetry(boot_id=BOOT_1, seq=2), seq=2),
        )
        assert relay_second.status == "accepted"
        direct_duplicate = core.commit_validated_direct_tuple(node_id=NODE_ID, boot_id=BOOT_1, seq=2)
        assert direct_duplicate.status == "duplicate"
    finally:
        core.replay_registry.close()


def test_replay_state_survives_manager_core_restart(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"
    core = make_core(database)
    payload = relay_payload(telemetry())
    assert core.process(TOPIC, payload).status == "accepted"
    core.replay_registry.close()

    reopened = make_core(database)
    try:
        assert reopened.process(TOPIC, payload).status == "duplicate"
    finally:
        reopened.replay_registry.close()


def test_higher_boot_session_advances_and_lower_session_is_rejected_before_decrypt(tmp_path: Path) -> None:
    core = make_core(tmp_path / "replay.sqlite3")
    try:
        higher = relay_payload(telemetry(boot_id=BOOT_2, seq=0), boot_id=BOOT_2, seq=0)
        assert core.process(TOPIC, higher).status == "accepted"

        stale_payload = relay_payload(telemetry(boot_id=BOOT_1, seq=99), boot_id=BOOT_1, seq=99)
        stale = core.process(TOPIC, stale_payload)
        assert stale.status == "rejected"
        assert stale.code == "stale_boot_session"
    finally:
        core.replay_registry.close()


def test_topic_and_outer_identity_binding_fail_closed(tmp_path: Path) -> None:
    core = make_core(tmp_path / "replay.sqlite3")
    try:
        wrong_system = TOPIC.replace(SYSTEM_ID, "system_999", 1)
        assert core.process(wrong_system, relay_payload(telemetry())).code == "system_binding_mismatch"

        wrong_topic_node = TOPIC.replace(NODE_ID, OTHER_NODE_ID, 1)
        assert core.process(wrong_topic_node, relay_payload(telemetry())).code == "outer_binding_mismatch"
    finally:
        core.replay_registry.close()


def test_gateway_node_authorization_node_state_and_key_epoch_fail_closed(tmp_path: Path) -> None:
    database = tmp_path / "replay.sqlite3"

    inactive = StaticRelayAuthorizationProvider(
        active_nodes=frozenset(),
        gateway_nodes={GATEWAY_ID: frozenset({NODE_ID})},
        keys={(NODE_ID, KEY_EPOCH): KEY},
    )
    core = make_core(database, auth=inactive)
    assert core.process(TOPIC, relay_payload(telemetry())).code == "node_not_active"
    core.replay_registry.close()

    unauthorized = StaticRelayAuthorizationProvider(
        active_nodes=frozenset({NODE_ID}),
        gateway_nodes={GATEWAY_ID: frozenset()},
        keys={(NODE_ID, KEY_EPOCH): KEY},
    )
    core = make_core(database, auth=unauthorized)
    assert core.process(TOPIC, relay_payload(telemetry())).code == "gateway_node_unauthorized"
    core.replay_registry.close()

    missing_epoch = StaticRelayAuthorizationProvider(
        active_nodes=frozenset({NODE_ID}),
        gateway_nodes={GATEWAY_ID: frozenset({NODE_ID})},
        keys={},
    )
    core = make_core(database, auth=missing_epoch)
    assert core.process(TOPIC, relay_payload(telemetry())).code == "key_epoch_rejected"
    core.replay_registry.close()


def test_nonce_mismatch_rejected_without_consuming_replay_tuple(tmp_path: Path) -> None:
    core = make_core(tmp_path / "replay.sqlite3")
    wrong_nonce = b"\xff" * 12
    try:
        rejected = core.process(
            TOPIC,
            relay_payload(telemetry(), nonce=wrong_nonce),
        )
        assert rejected.status == "rejected"
        assert rejected.code == "nonce_mismatch"

        corrected = core.process(TOPIC, relay_payload(telemetry()))
        assert corrected.status == "accepted"
    finally:
        core.replay_registry.close()


def test_aad_or_ciphertext_tamper_fails_aead_without_consuming_tuple(tmp_path: Path) -> None:
    core = make_core(tmp_path / "replay.sqlite3")
    try:
        aad_mismatch = relay_payload(
            telemetry(),
            aad_mutator={"gateway_id": "gateway_999"},
        )
        rejected = core.process(TOPIC, aad_mismatch)
        assert rejected.code == "aead_or_plaintext_rejected"

        corrected = core.process(TOPIC, relay_payload(telemetry()))
        assert corrected.status == "accepted"
    finally:
        core.replay_registry.close()


def test_inner_binding_and_complete_telemetry_validation_do_not_consume_tuple(tmp_path: Path) -> None:
    core = make_core(tmp_path / "replay.sqlite3")
    try:
        mismatched = telemetry(node_id=OTHER_NODE_ID)
        binding = core.process(TOPIC, relay_payload(mismatched))
        assert binding.code == "inner_binding_mismatch"

        invalid = telemetry()
        invalid.pop("power")
        validation = core.process(TOPIC, relay_payload(invalid))
        assert validation.code == "telemetry_validation_rejected"

        manager_owned = telemetry()
        manager_owned["received_at"] = "2026-08-07T00:00:00Z"
        owned = core.process(TOPIC, relay_payload(manager_owned))
        assert owned.code == "manager_owned_field_present"

        corrected = core.process(TOPIC, relay_payload(telemetry()))
        assert corrected.status == "accepted"
    finally:
        core.replay_registry.close()


def test_registry_unavailable_fails_closed_before_aead(tmp_path: Path) -> None:
    core = make_core(tmp_path / "replay.sqlite3")
    core.replay_registry.close()

    result = core.process(TOPIC, relay_payload(telemetry()))
    assert result.status == "rejected"
    assert result.code == "replay_registry_unavailable"


def test_payload_size_single_hop_and_ciphertext_bounds_fail_closed(tmp_path: Path) -> None:
    core = make_core(tmp_path / "replay.sqlite3")
    try:
        oversized = b"{" + b"x" * 4096
        assert core.process(TOPIC, oversized).code == "payload_size_rejected"

        multi_hop = relay_payload(telemetry(), hop_count=2)
        assert core.process(TOPIC, multi_hop).code == "not_single_hop"

        outer = json.loads(relay_payload(telemetry()))
        outer["ciphertext_b64"] = base64.b64encode(b"").decode()
        empty_ciphertext = json.dumps(outer).encode()
        assert core.process(TOPIC, empty_ciphertext).code == "ciphertext_size_rejected"
    finally:
        core.replay_registry.close()


def test_envelope_rejects_zero_boot_out_of_range_seq_and_bad_base64() -> None:
    outer = json.loads(relay_payload(telemetry()))

    outer["boot_id"] = "boot_0000000000000000"
    with pytest.raises(ValueError, match="boot_session_invalid"):
        parse_relay_envelope(json.dumps(outer))

    outer = json.loads(relay_payload(telemetry()))
    outer["seq"] = 2**32
    with pytest.raises(ValueError, match="sequence_out_of_range"):
        parse_relay_envelope(json.dumps(outer))

    outer = json.loads(relay_payload(telemetry()))
    outer["nonce_b64"] = "***"
    with pytest.raises(ValueError, match="nonce_invalid"):
        parse_relay_envelope(json.dumps(outer))


def test_nonce_and_aad_are_deterministic_contract_bindings() -> None:
    nonce = derive_nonce("boot_0102030405060708", 0x0A0B0C0D)
    assert nonce == bytes.fromhex("01020304050607080a0b0c0d")

    envelope = parse_relay_envelope(relay_payload(telemetry()))
    aad = json.loads(build_aad(envelope))
    assert aad == {
        "schema": "gh.relay/1",
        "transport": "esp_now",
        "gateway_id": GATEWAY_ID,
        "node_id": NODE_ID,
        "hop_count": 1,
        "key_epoch": KEY_EPOCH,
        "boot_id": BOOT_1,
        "seq": 1,
    }


def test_packaged_validator_matches_existing_telemetry_schema_without_tightening_global_boot_id() -> None:
    validator = PackagedTelemetryValidator()
    legacy = telemetry(boot_id="boot_legacy_01")
    validator.validate(legacy)

    with pytest.raises(ValueError, match="manager_owned_field_present"):
        legacy["received_at"] = "2026-08-07T00:00:00Z"
        validator.validate(legacy)
