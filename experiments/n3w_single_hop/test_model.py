from __future__ import annotations

import base64
import json
import unittest

from experiments.n3w_single_hop.model import (
    N3wIngressModel,
    ReplayRegistry,
    derive_nonce,
)

SYSTEM = "system_001"
GATEWAY = "gateway_001"
NODE = "node_001"
BOOT = "boot_0000000000000001"
TOPIC = f"gh/v1/{SYSTEM}/ingress/gateway/{GATEWAY}/{NODE}/frame"


def telemetry(*, node: str = NODE, boot: str = BOOT, seq: int = 1) -> bytes:
    return json.dumps(
        {
            "schema": "gh.telemetry/1",
            "node_id": node,
            "boot_id": boot,
            "seq": seq,
            "uptime_ms": 1000,
            "cap_hash": "synthetic",
            "measurements": {},
            "quality": {},
            "power": {"source": "test"},
        }
    ).encode()


def envelope(
    *,
    gateway: str = GATEWAY,
    node: str = NODE,
    boot: str = BOOT,
    seq: int = 1,
    hop: int = 1,
    epoch: int = 7,
) -> bytes:
    return json.dumps(
        {
            "schema": "gh.relay/1",
            "transport": "esp_now",
            "gateway_id": gateway,
            "node_id": node,
            "hop_count": hop,
            "key_epoch": epoch,
            "boot_id": boot,
            "seq": seq,
            "nonce_b64": base64.b64encode(derive_nonce(node, boot, seq)).decode(),
            "ciphertext_b64": base64.b64encode(b"synthetic-ciphertext").decode(),
            "tag_b64": base64.b64encode(b"t" * 16).decode(),
        }
    ).encode()


class N3wIngressModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ReplayRegistry()
        self.model = N3wIngressModel(
            system_id=SYSTEM,
            active_nodes={NODE},
            gateway_nodes={GATEWAY: {NODE}},
            key_epochs={NODE: {7}},
            replay_registry=self.registry,
        )

    def decrypt(self, nonce: bytes, ciphertext: bytes, tag: bytes, aad: bytes) -> bytes:
        self.assertEqual(len(nonce), 12)
        self.assertEqual(nonce, (1).to_bytes(8, "big") + (1).to_bytes(4, "big"))
        self.assertEqual(ciphertext, b"synthetic-ciphertext")
        self.assertEqual(tag, b"t" * 16)
        self.assertIn(b'"hop_count":1', aad)
        return telemetry()

    def test_accepts_one_hop_and_restores_original_node_ingress(self) -> None:
        result = self.model.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(result.status, "accepted")
        self.assertEqual(result.node_id, NODE)
        self.assertEqual(
            result.ingress_topic, f"gh/v1/{SYSTEM}/ingress/node/{NODE}/telemetry"
        )

    def test_rejects_non_single_hop_and_unauthorized_gateway(self) -> None:
        self.assertEqual(
            self.model.process(TOPIC, envelope(hop=2), decrypt=self.decrypt).code,
            "not_single_hop",
        )
        other = TOPIC.replace(GATEWAY, "gateway_002")
        self.assertEqual(
            self.model.process(
                other, envelope(gateway="gateway_002"), decrypt=self.decrypt
            ).code,
            "gateway_node_unauthorized",
        )

    def test_rejects_nonce_epoch_and_inner_binding(self) -> None:
        document = json.loads(envelope())
        document["nonce_b64"] = base64.b64encode(b"n" * 12).decode()
        self.assertEqual(
            self.model.process(TOPIC, json.dumps(document), decrypt=self.decrypt).code,
            "nonce_mismatch",
        )
        self.assertEqual(
            self.model.process(TOPIC, envelope(epoch=8), decrypt=self.decrypt).code,
            "key_epoch_rejected",
        )

        def wrong_inner(*_: bytes) -> bytes:
            return telemetry(node="node_002")

        self.assertEqual(
            self.model.process(TOPIC, envelope(), decrypt=wrong_inner).code,
            "inner_binding_mismatch",
        )

    def test_rejects_aead_failure_and_manager_owned_field(self) -> None:
        def failed(*_: bytes) -> bytes:
            raise ValueError("synthetic authentication failure")

        self.assertEqual(
            self.model.process(TOPIC, envelope(), decrypt=failed).code,
            "aead_or_plaintext_rejected",
        )

        def owned(*_: bytes) -> bytes:
            document = json.loads(telemetry())
            document["received_at"] = "2026-08-06T00:00:00Z"
            return json.dumps(document).encode()

        self.assertEqual(
            self.model.process(TOPIC, envelope(), decrypt=owned).code,
            "manager_owned_field_present",
        )
        self.assertEqual(
            self.model.process(TOPIC, b" " * 4097, decrypt=self.decrypt).code,
            "payload_size_rejected",
        )

    def test_unifies_direct_and_relay_dedup(self) -> None:
        self.model.observe_direct(node_id=NODE, boot_id=BOOT, seq=1)
        result = self.model.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(
            (result.status, result.code), ("duplicate", "duplicate_node_boot_seq")
        )

    def test_persists_replay_state_across_manager_restart(self) -> None:
        first = self.model.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(first.status, "accepted")
        restarted = N3wIngressModel(
            system_id=SYSTEM,
            active_nodes={NODE},
            gateway_nodes={GATEWAY: {NODE}},
            key_epochs={NODE: {7}},
            replay_registry=self.registry,
        )
        replay = restarted.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(
            (replay.status, replay.code), ("duplicate", "duplicate_node_boot_seq")
        )

    def test_rejects_boot_session_rollback(self) -> None:
        newer_boot = "boot_0000000000000002"

        def newer_plaintext(*_: bytes) -> bytes:
            return telemetry(boot=newer_boot)

        accepted = self.model.process(
            TOPIC, envelope(boot=newer_boot), decrypt=newer_plaintext
        )
        self.assertEqual(accepted.status, "accepted")
        called = False

        def rollback_plaintext(*_: bytes) -> bytes:
            nonlocal called
            called = True
            return telemetry()

        rollback = self.model.process(TOPIC, envelope(), decrypt=rollback_plaintext)
        self.assertEqual(
            (rollback.status, rollback.code), ("rejected", "stale_boot_session")
        )
        self.assertFalse(called)

        rotated = N3wIngressModel(
            system_id=SYSTEM,
            active_nodes={NODE},
            gateway_nodes={GATEWAY: {NODE}},
            key_epochs={NODE: {7, 8}},
            replay_registry=self.registry,
        )
        rollback = rotated.process(TOPIC, envelope(epoch=8), decrypt=rollback_plaintext)
        self.assertEqual(rollback.code, "stale_boot_session")
        self.assertFalse(called)

    def test_fails_closed_before_decrypt_when_registry_is_unavailable(self) -> None:
        self.registry.available = False
        called = False

        def decrypt(*_: bytes) -> bytes:
            nonlocal called
            called = True
            return telemetry()

        result = self.model.process(TOPIC, envelope(), decrypt=decrypt)
        self.assertEqual(result.code, "replay_registry_unavailable")
        self.assertFalse(called)

    def test_rejects_noncanonical_boot_session(self) -> None:
        document = json.loads(envelope())
        document["boot_id"] = "boot_001"
        result = self.model.process(TOPIC, json.dumps(document), decrypt=self.decrypt)
        self.assertEqual(result.code, "boot_session_invalid")

        document["boot_id"] = "boot_0000000000000000"
        result = self.model.process(TOPIC, json.dumps(document), decrypt=self.decrypt)
        self.assertEqual(result.code, "boot_session_invalid")

    def test_rejects_retired_node_before_decrypt(self) -> None:
        model = N3wIngressModel(
            system_id=SYSTEM,
            active_nodes=set(),
            gateway_nodes={GATEWAY: {NODE}},
            key_epochs={NODE: {7}},
            replay_registry=ReplayRegistry(),
        )
        called = False

        def decrypt(*_: bytes) -> bytes:
            nonlocal called
            called = True
            return telemetry()

        result = model.process(TOPIC, envelope(), decrypt=decrypt)
        self.assertEqual(result.code, "node_not_active")
        self.assertFalse(called)


if __name__ == "__main__":
    unittest.main()
