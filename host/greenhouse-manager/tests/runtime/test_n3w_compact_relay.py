import base64
import json

from greenhouse_manager.runtime.n3w_compact_relay import (
    ESPNOW_V2_PAYLOAD_LIMIT,
    MAX_CIPHERTEXT_BYTES,
    CompactRelayIngressCore,
    StaticNodeApplicationKeyProvider,
    build_aad,
    decode_single_frame,
    encrypt_compact_telemetry,
    single_frame_wire_bytes,
    wrap_relay_frame,
)

SYSTEM_ID = "gh-system-01"
NODE_ID = "node_child01"
BOOT_ID = "boot_0000000000000001"
KEY = bytes(range(32))


def telemetry(seq: int) -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": BOOT_ID,
        "seq": seq,
        "uptime_ms": 1234,
        "cap_hash": "cap_hash_001",
        "measurements": {"air_temperature_c": 24.5},
        "quality": {"air_temperature_c": "ok"},
        "power": {"source": "main", "low": False},
    }


def encoded_relay(seq: int = 42) -> bytes:
    plaintext = json.dumps(telemetry(seq), separators=(",", ":"), sort_keys=True).encode()
    frame = encrypt_compact_telemetry(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        key_epoch=1,
        boot_id=BOOT_ID,
        seq=seq,
        key=KEY,
        plaintext=plaintext,
    )
    return wrap_relay_frame(frame)


def test_current_max_payload_fits_one_espnow_v2_frame() -> None:
    assert single_frame_wire_bytes(MAX_CIPHERTEXT_BYTES) == 1072
    assert single_frame_wire_bytes(MAX_CIPHERTEXT_BYTES) <= ESPNOW_V2_PAYLOAD_LIMIT


def test_same_encrypted_child_frame_is_gateway_independent() -> None:
    core = CompactRelayIngressCore(
        system_id=SYSTEM_ID,
        keys=StaticNodeApplicationKeyProvider({(NODE_ID, 1): KEY}),
    )
    payload = encoded_relay()
    gateway_a = core.prepare(
        f"gh/v1/{SYSTEM_ID}/ingress/gateway/node_relay01/{NODE_ID}/frame",
        payload,
    )
    gateway_b = core.prepare(
        f"gh/v1/{SYSTEM_ID}/ingress/gateway/node_relay02/{NODE_ID}/frame",
        payload,
    )

    assert gateway_a.status == "ready"
    assert gateway_b.status == "ready"
    assert gateway_a.telemetry == gateway_b.telemetry == telemetry(42)
    assert gateway_a.gateway_id == "node_relay01"
    assert gateway_b.gateway_id == "node_relay02"
    aad = build_aad(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        key_epoch=1,
        boot_id=BOOT_ID,
        seq=42,
    )
    assert b"gateway" not in aad


def test_tamper_or_wrong_node_fails_closed() -> None:
    core = CompactRelayIngressCore(
        system_id=SYSTEM_ID,
        keys=StaticNodeApplicationKeyProvider({(NODE_ID, 1): KEY, ("node_other01", 1): KEY}),
    )
    document = json.loads(encoded_relay())
    frame = bytearray(base64.b64decode(document["frame_b64"]))
    frame[-1] ^= 1
    document["frame_b64"] = base64.b64encode(frame).decode()
    tampered = json.dumps(document, separators=(",", ":"), sort_keys=True)

    rejected = core.prepare(
        f"gh/v1/{SYSTEM_ID}/ingress/gateway/node_relay01/{NODE_ID}/frame",
        tampered,
    )
    wrong_node = core.prepare(
        f"gh/v1/{SYSTEM_ID}/ingress/gateway/node_relay01/node_other01/frame",
        encoded_relay(),
    )

    assert rejected.status == "rejected"
    assert rejected.code == "aead_or_plaintext_rejected"
    assert wrong_node.status == "rejected"
    assert wrong_node.code == "aead_or_plaintext_rejected"


def test_single_frame_codec_has_no_fragment_fields() -> None:
    plaintext = json.dumps(telemetry(42), separators=(",", ":"), sort_keys=True).encode()
    encoded = encrypt_compact_telemetry(
        system_id=SYSTEM_ID,
        node_id=NODE_ID,
        key_epoch=1,
        boot_id=BOOT_ID,
        seq=42,
        key=KEY,
        plaintext=plaintext,
    )
    frame = decode_single_frame(encoded)

    assert frame.boot_id == BOOT_ID
    assert frame.seq == 42
    assert frame.key_epoch == 1
    assert len(encoded) == 48 + len(plaintext)
    assert not hasattr(frame, "fragment_index")
    assert not hasattr(frame, "fragment_count")
    assert not hasattr(frame, "offset")
