from __future__ import annotations

import json

import pytest

from greenhouse_simulator.credential_slots import (
    CredentialDeliveryError,
    DeliveryPhase,
    NodeCredentialSlots,
    NodeMqttCredential,
    SlotName,
)


def _credential(generation: int, *, suffix: str = "a") -> NodeMqttCredential:
    return NodeMqttCredential(
        host="broker.internal",
        port=1883,
        client_id=f"gh-node-{suffix}",
        username=f"ghn_node_{suffix}",
        password=f"secret-{suffix}-" + "x" * 32,
        generation=generation,
    )


def _complete_claim(slots: NodeCredentialSlots, credential: NodeMqttCredential) -> None:
    slots.stage(credential)
    assert slots.verify_candidate(
        credential.generation,
        connection_accepted=True,
        observed_client_id=credential.client_id,
    )
    slots.mark_claim_sent(credential.generation)


def test_initial_authenticated_migration_keeps_legacy_until_grace_finishes() -> None:
    slots = NodeCredentialSlots(legacy_fallback_available=True)
    candidate = _credential(1)

    _complete_claim(slots, candidate)
    assert slots.phase is DeliveryPhase.CLAIM_SENT
    assert slots.active_generation is None
    assert slots.pending_generation == 1
    assert slots.legacy_fallback_available is True
    assert slots.local_operation_available is True

    slots.commit(1)

    assert slots.phase is DeliveryPhase.COMMITTED_GRACE
    assert slots.active_generation == 1
    assert slots.pending_generation is None
    assert slots.legacy_fallback_available is True

    slots.finalize_grace(1)

    assert slots.phase is DeliveryPhase.STABLE
    assert slots.active_generation == 1
    assert slots.legacy_fallback_available is False
    assert slots.local_operation_available is True


def test_rotation_retains_old_slot_and_can_roll_back_after_commit() -> None:
    slots = NodeCredentialSlots()
    slots.install_existing_active(_credential(1, suffix="old"))
    candidate = _credential(2, suffix="new")

    _complete_claim(slots, candidate)
    slots.commit(2)

    assert slots.active_generation == 2
    assert slots.rollback_generation == 1
    assert slots.phase is DeliveryPhase.COMMITTED_GRACE

    slots.roll_back("post_commit_connectivity_regression")

    assert slots.phase is DeliveryPhase.STABLE
    assert slots.active_generation == 1
    assert slots.rollback_generation is None
    assert slots.pending_generation is None
    assert slots.local_operation_available is True


def test_candidate_connection_rejection_automatically_clears_pending_slot() -> None:
    slots = NodeCredentialSlots()
    slots.install_existing_active(_credential(3, suffix="old"))
    candidate = _credential(4, suffix="new")
    slots.stage(candidate)

    verified = slots.verify_candidate(
        4,
        connection_accepted=False,
        observed_client_id=candidate.client_id,
    )

    assert verified is False
    assert slots.phase is DeliveryPhase.STABLE
    assert slots.active_generation == 3
    assert slots.pending_generation is None
    assert slots.events[-1].code == "pending_candidate_rolled_back"
    assert slots.events[-1].reason == "candidate_verification_failed"


def test_wrong_client_identity_is_rejected_without_secret_output() -> None:
    slots = NodeCredentialSlots()
    candidate = _credential(1)
    slots.stage(candidate)

    assert not slots.verify_candidate(
        1,
        connection_accepted=True,
        observed_client_id="wrong-client",
    )

    rendered = repr(candidate) + json.dumps(slots.summary(), default=str)
    assert candidate.password not in rendered
    assert candidate.username not in rendered
    assert candidate.client_id not in rendered
    assert candidate.host not in rendered
    assert "<redacted>" in repr(candidate)
    assert slots.summary()["secret_fields_emitted"] is False


def test_boot_before_pointer_commit_rolls_back_to_previous_active() -> None:
    slots = NodeCredentialSlots()
    slots.install_existing_active(_credential(5, suffix="old"))
    candidate = _credential(6, suffix="new")
    _complete_claim(slots, candidate)

    slots.recover_after_boot()

    assert slots.phase is DeliveryPhase.STABLE
    assert slots.active_generation == 5
    assert slots.pending_generation is None
    assert slots.events[-1].reason == "boot_before_commit"


def test_boot_after_atomic_pointer_commit_resumes_grace() -> None:
    slots = NodeCredentialSlots()
    slots.install_existing_active(_credential(7, suffix="old"))
    candidate = _credential(8, suffix="new")
    _complete_claim(slots, candidate)
    slots.commit(8)

    slots.recover_after_boot()

    assert slots.phase is DeliveryPhase.COMMITTED_GRACE
    assert slots.active_generation == 8
    assert slots.rollback_generation == 7
    assert slots.events[-1].code == "grace_resumed_after_boot"


def test_corrupted_committed_slot_rolls_back_during_boot_recovery() -> None:
    slots = NodeCredentialSlots()
    slots.install_existing_active(_credential(9, suffix="old"))
    candidate = _credential(10, suffix="new")
    _complete_claim(slots, candidate)
    slots.commit(10)
    slots.simulate_slot_corruption(SlotName.B)

    slots.recover_after_boot()

    assert slots.phase is DeliveryPhase.STABLE
    assert slots.active_generation == 9
    assert slots.rollback_generation is None
    assert slots.local_operation_available is True
    assert slots.events[-1].code == (
        "invalid_committed_slot_rolled_back_after_boot"
    )


def test_generation_must_increase_and_commit_must_match() -> None:
    slots = NodeCredentialSlots()
    slots.install_existing_active(_credential(4, suffix="old"))

    with pytest.raises(CredentialDeliveryError, match="must increase"):
        slots.stage(_credential(4, suffix="duplicate"))

    candidate = _credential(5, suffix="new")
    _complete_claim(slots, candidate)
    with pytest.raises(CredentialDeliveryError, match="does not match"):
        slots.commit(6)

    assert slots.phase is DeliveryPhase.CLAIM_SENT
    assert slots.active_generation == 4
    assert slots.pending_generation == 5


def test_grace_finalization_erases_old_slot_and_disables_legacy_fallback() -> None:
    slots = NodeCredentialSlots(legacy_fallback_available=True)
    slots.install_existing_active(_credential(11, suffix="old"))
    candidate = _credential(12, suffix="new")
    _complete_claim(slots, candidate)
    slots.commit(12)
    slots.finalize_grace(12)

    assert slots.phase is DeliveryPhase.STABLE
    assert slots.active_generation == 12
    assert slots.rollback_generation is None
    assert slots.legacy_fallback_available is False
    with pytest.raises(CredentialDeliveryError, match="empty slot"):
        slots.simulate_slot_corruption(SlotName.A)


def test_public_summary_and_audit_events_are_secret_free() -> None:
    slots = NodeCredentialSlots()
    credential = _credential(1, suffix="sensitive")
    _complete_claim(slots, credential)
    slots.commit(1)

    serialized = json.dumps(
        {
            "summary": slots.summary(),
            "events": [
                {
                    "code": event.code,
                    "generation": event.generation,
                    "phase": event.phase,
                    "reason": event.reason,
                }
                for event in slots.events
            ],
        },
        default=str,
    )
    for secret in (
        credential.host,
        credential.client_id,
        credential.username,
        credential.password,
    ):
        assert secret not in serialized
