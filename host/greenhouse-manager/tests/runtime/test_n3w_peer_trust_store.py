from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.runtime.n3w_peer_trust_store import (
    PeerTrustStoreConflict,
    SystemPeerTrustStore,
)

SYSTEM_ID = "gh-system-01"
FIRST_KEY = bytes(range(32))
SECOND_KEY = bytes(range(32, 64))
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


class FixedKeys:
    def __init__(self, *values: bytes) -> None:
        self.values = list(values)

    def __call__(self, size: int) -> bytes:
        assert size == 32
        return self.values.pop(0)


def test_get_or_create_is_stable_across_reopen(tmp_path) -> None:
    database = tmp_path / "peer-trust.sqlite3"
    with SystemPeerTrustStore(database, random_bytes=FixedKeys(FIRST_KEY)) as store:
        first = store.get_or_create(SYSTEM_ID, now=NOW)
        again = store.get_or_create(SYSTEM_ID, now=NOW + timedelta(seconds=5))
        snapshot = store.snapshot(SYSTEM_ID)

    with SystemPeerTrustStore(database, random_bytes=FixedKeys()) as reopened:
        persisted = reopened.get(SYSTEM_ID)

    assert first == again == persisted
    assert first.generation == 1
    assert first.key == FIRST_KEY
    assert snapshot.generation == 1
    assert snapshot.created_at == NOW
    assert snapshot.updated_at == NOW


def test_explicit_rotation_advances_generation_and_normal_reads_do_not(tmp_path) -> None:
    database = tmp_path / "peer-trust.sqlite3"
    with SystemPeerTrustStore(
        database,
        random_bytes=FixedKeys(FIRST_KEY, SECOND_KEY),
    ) as store:
        first = store.get_or_create(SYSTEM_ID, now=NOW)
        assert store.get(SYSTEM_ID) == first
        rotated = store.rotate(SYSTEM_ID, now=NOW + timedelta(hours=1))
        assert store.get(SYSTEM_ID) == rotated

    assert first.generation == 1
    assert rotated.generation == 2
    assert rotated.key == SECOND_KEY
    assert rotated.key != first.key


def test_rotate_requires_initialized_system_and_secrets_are_redacted(tmp_path) -> None:
    with SystemPeerTrustStore(
        tmp_path / "peer-trust.sqlite3",
        random_bytes=FixedKeys(FIRST_KEY),
    ) as store:
        with pytest.raises(PeerTrustStoreConflict, match="not initialized"):
            store.rotate(SYSTEM_ID, now=NOW)
        credential = store.get_or_create(SYSTEM_ID, now=NOW)
        snapshot = store.snapshot(SYSTEM_ID)
        audit = store.audit()

    assert FIRST_KEY.hex() not in repr(credential)
    assert FIRST_KEY.hex() not in repr(snapshot)
    assert "<redacted>" in repr(credential)
    assert audit["secret_values_included"] is False
    assert audit["normal_get_rotates"] is False


def test_invalid_key_generator_fails_closed(tmp_path) -> None:
    with (
        SystemPeerTrustStore(
            tmp_path / "peer-trust.sqlite3",
            random_bytes=lambda _: b"short",
        ) as store,
        pytest.raises(PeerTrustStoreConflict, match="invalid length"),
    ):
        store.get_or_create(SYSTEM_ID, now=NOW)

    with (
        SystemPeerTrustStore(
            tmp_path / "peer-trust-zero.sqlite3",
            random_bytes=lambda _: b"\x00" * 32,
        ) as store,
        pytest.raises(PeerTrustStoreConflict, match="all-zero"),
    ):
        store.get_or_create(SYSTEM_ID, now=NOW)
