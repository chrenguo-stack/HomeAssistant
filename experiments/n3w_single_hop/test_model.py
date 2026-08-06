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
BOOT_2 = "boot_0000000000000002"
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


def validate_telemetry(document: dict[str, object]) -> bool:
    required = {
        "schema",
        "node_id",
        "boot_id",
        "seq",
        "uptime_ms",
        "cap_hash",
        "measurements",
        "quality",
        "power",
    }
    if not required.issubset(document):
        return False
    if document["schema"] != "gh.telemetry/1":
        return False
    if (
        not isinstance(document["uptime_ms"], int)
        or isinstance(document["uptime_ms"], bool)
        or document["uptime_ms"] < 0
    ):
        return False
    structured_fields = ("measurements", "quality", "power")
    return all(isinstance(document[field], dict) for field in structured_fields)


class N3wIngressModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ReplayRegistry()
        self.model = self.build_model(self.registry)

    def build_model(
        self,
        registry: ReplayRegistry,
        *,
        validator=validate_telemetry,
        active_nodes: set[str] | None = None,
        key_epochs: set[int] | None = None,
    ) -> N3wIngressModel:
        return N3wIngressModel(
            system_id=SYSTEM,
            active_nodes={NODE} if active_nodes is None else active_nodes,
            gateway_nodes={GATEWAY: {NODE}},
            key_epochs={NODE: {7} if key_epochs is None else key_epochs},
            replay_registry=registry,
            telemetry_validator=validator,
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

    def test_direct_then_relay_same_tuple_is_duplicate(self) -> None:
        direct = self.model.observe_direct(node_id=NODE, boot_id=BOOT, seq=1)
        self.assertEqual(direct.status, "accepted")
        result = self.model.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(
            (result.status, result.code), ("duplicate", "duplicate_node_boot_seq")
        )

    def test_relay_then_direct_same_tuple_is_duplicate(self) -> None:
        relay = self.model.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(relay.status, "accepted")
        direct = self.model.observe_direct(node_id=NODE, boot_id=BOOT, seq=1)
        self.assertEqual(
            (direct.status, direct.code), ("duplicate", "duplicate_node_boot_seq")
        )

    def test_direct_newer_session_rejects_older_relay_before_decrypt(self) -> None:
        direct = self.model.observe_direct(node_id=NODE, boot_id=BOOT_2, seq=1)
        self.assertEqual(direct.status, "accepted")
        called = False

        def decrypt(*_: bytes) -> bytes:
            nonlocal called
            called = True
            return telemetry()

        relay = self.model.process(TOPIC, envelope(), decrypt=decrypt)
        self.assertEqual((relay.status, relay.code), ("rejected", "stale_boot_session"))
        self.assertFalse(called)

    def test_relay_newer_session_rejects_older_direct(self) -> None:
        def newer_plaintext(*_: bytes) -> bytes:
            return telemetry(boot=BOOT_2)

        relay = self.model.process(
            TOPIC, envelope(boot=BOOT_2), decrypt=newer_plaintext
        )
        self.assertEqual(relay.status, "accepted")
        direct = self.model.observe_direct(node_id=NODE, boot_id=BOOT, seq=1)
        self.assertEqual(
            (direct.status, direct.code), ("rejected", "stale_boot_session")
        )

    def test_restart_preserves_cross_path_high_water_and_duplicate_state(self) -> None:
        direct = self.model.observe_direct(node_id=NODE, boot_id=BOOT_2, seq=9)
        self.assertEqual(direct.status, "accepted")
        restarted = self.build_model(self.registry)

        duplicate = restarted.observe_direct(node_id=NODE, boot_id=BOOT_2, seq=9)
        self.assertEqual(
            (duplicate.status, duplicate.code),
            ("duplicate", "duplicate_node_boot_seq"),
        )

        called = False

        def decrypt(*_: bytes) -> bytes:
            nonlocal called
            called = True
            return telemetry()

        stale = restarted.process(TOPIC, envelope(), decrypt=decrypt)
        self.assertEqual((stale.status, stale.code), ("rejected", "stale_boot_session"))
        self.assertFalse(called)

    def test_persists_replay_state_across_manager_restart(self) -> None:
        first = self.model.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(first.status, "accepted")
        restarted = self.build_model(self.registry)
        replay = restarted.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(
            (replay.status, replay.code), ("duplicate", "duplicate_node_boot_seq")
        )

    def test_rejects_boot_session_rollback(self) -> None:
        def newer_plaintext(*_: bytes) -> bytes:
            return telemetry(boot=BOOT_2)

        accepted = self.model.process(
            TOPIC, envelope(boot=BOOT_2), decrypt=newer_plaintext
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

        rotated = self.build_model(self.registry, key_epochs={7, 8})
        rollback = rotated.process(TOPIC, envelope(epoch=8), decrypt=rollback_plaintext)
        self.assertEqual(rollback.code, "stale_boot_session")
        self.assertFalse(called)

    def test_full_validator_runs_before_replay_commit(self) -> None:
        observed_state: list[tuple[dict[str, int], set[tuple[str, str, int]]]] = []

        def validator(document: dict[str, object]) -> bool:
            observed_state.append(
                (dict(self.registry.highest_session), set(self.registry.seen))
            )
            return validate_telemetry(document)

        model = self.build_model(self.registry, validator=validator)
        result = model.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(result.status, "accepted")
        self.assertEqual(observed_state, [({}, set())])
        self.assertEqual(self.registry.highest_session[NODE], 1)
        self.assertIn((NODE, BOOT, 1), self.registry.seen)

    def test_invalid_telemetry_does_not_consume_replay_tuple(self) -> None:
        def invalid_plaintext(*_: bytes) -> bytes:
            document = json.loads(telemetry())
            del document["measurements"]
            return json.dumps(document).encode()

        result = self.model.process(TOPIC, envelope(), decrypt=invalid_plaintext)
        self.assertEqual(
            (result.status, result.code),
            ("rejected", "telemetry_validation_rejected"),
        )
        self.assertEqual(self.registry.highest_session, {})
        self.assertEqual(self.registry.seen, set())

    def test_validator_exception_does_not_consume_replay_tuple(self) -> None:
        def validator(_: dict[str, object]) -> bool:
            raise RuntimeError("synthetic validator failure")

        model = self.build_model(self.registry, validator=validator)
        result = model.process(TOPIC, envelope(), decrypt=self.decrypt)
        self.assertEqual(result.code, "telemetry_validation_rejected")
        self.assertEqual(self.registry.highest_session, {})
        self.assertEqual(self.registry.seen, set())

    def test_direct_path_validates_boot_and_sequence(self) -> None:
        invalid_boot = self.model.observe_direct(
            node_id=NODE, boot_id="boot_001", seq=1
        )
        invalid_seq = self.model.observe_direct(node_id=NODE, boot_id=BOOT, seq=2**32)
        bool_seq = self.model.observe_direct(node_id=NODE, boot_id=BOOT, seq=True)
        self.assertEqual(invalid_boot.code, "boot_session_invalid")
        self.assertEqual(invalid_seq.code, "sequence_out_of_range")
        self.assertEqual(bool_seq.code, "sequence_out_of_range")
        self.assertEqual(self.registry.highest_session, {})
        self.assertEqual(self.registry.seen, set())

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
        direct = self.model.observe_direct(node_id=NODE, boot_id=BOOT, seq=1)
        self.assertEqual(direct.code, "replay_registry_unavailable")

    def test_rejects_noncanonical_boot_session(self) -> None:
        document = json.loads(envelope())
        document["boot_id"] = "boot_001"
        result = self.model.process(TOPIC, json.dumps(document), decrypt=self.decrypt)
        self.assertEqual(result.code, "boot_session_invalid")

        document["boot_id"] = "boot_0000000000000000"
        result = self.model.process(TOPIC, json.dumps(document), decrypt=self.decrypt)
        self.assertEqual(result.code, "boot_session_invalid")

    def test_rejects_retired_node_before_decrypt(self) -> None:
        model = self.build_model(self.registry, active_nodes=set())
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
