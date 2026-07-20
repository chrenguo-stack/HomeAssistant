from __future__ import annotations

import threading

import pytest

from greenhouse_manager.pairing_secure_transport import (
    MANAGER_TO_NODE,
    NODE_TO_MANAGER,
    SecureChannel,
    SecureEnvelope,
    SecureEnvelopeRejected,
    envelope_nonce,
)

SESSION_ID = "96329311-1c64-4c88-9343-04f5de69698e"


def make_channel() -> SecureChannel:
    return SecureChannel(
        session_id=SESSION_ID,
        send_direction=MANAGER_TO_NODE,
        send_key=bytes([0x44]) * 32,
        receive_direction=NODE_TO_MANAGER,
        receive_key=bytes([0x55]) * 32,
    )


def test_concurrent_encrypt_never_reuses_sequence_or_nonce() -> None:
    channel = make_channel()
    envelopes: list[SecureEnvelope] = []
    failures: list[BaseException] = []
    barrier = threading.Barrier(32)
    result_lock = threading.Lock()

    def worker(index: int) -> None:
        try:
            barrier.wait(timeout=2)
            envelope = channel.encrypt(
                f"message-{index}".encode(),
                content_type="application/test",
            )
            with result_lock:
                envelopes.append(envelope)
        except BaseException as error:
            with result_lock:
                failures.append(error)

    threads = [
        threading.Thread(target=worker, args=(index,))
        for index in range(32)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert not failures
    assert all(not thread.is_alive() for thread in threads)
    assert len(envelopes) == 32
    assert {envelope.sequence for envelope in envelopes} == set(range(32))
    assert len({envelope.nonce for envelope in envelopes}) == 32


def test_secure_channel_rejects_invalid_direction_and_key_size() -> None:
    with pytest.raises(ValueError, match="directions must be complementary"):
        SecureChannel(
            session_id=SESSION_ID,
            send_direction=MANAGER_TO_NODE,
            send_key=bytes(32),
            receive_direction=MANAGER_TO_NODE,
            receive_key=bytes(32),
        )

    with pytest.raises(ValueError, match="keys must be exactly 32 bytes"):
        SecureChannel(
            session_id=SESSION_ID,
            send_direction=MANAGER_TO_NODE,
            send_key=bytes(31),
            receive_direction=NODE_TO_MANAGER,
            receive_key=bytes(32),
        )


def test_nonce_builder_rejects_unknown_direction() -> None:
    with pytest.raises(
        SecureEnvelopeRejected,
        match="direction is invalid",
    ):
        envelope_nonce("unknown", 0)
