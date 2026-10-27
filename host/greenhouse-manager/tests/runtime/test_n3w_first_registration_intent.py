from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.runtime.n3w_first_registration_intent import (
    FirstRegistrationIntent,
    FirstRegistrationIntentError,
    FirstRegistrationIntentStore,
)

NOW = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-00000000000a"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
SECRET = bytes(range(32))


def prepared() -> FirstRegistrationIntent:
    return FirstRegistrationIntent.prepare(
        hardware_id=HARDWARE_ID,
        pairing_id=PAIRING_ID,
        source_ip="192.0.2.44",
        manager_id="manager_lab_01",
        system_id="greenhouse",
        setup_secret=SECRET,
        opened_at=NOW,
        expires_at=NOW + timedelta(seconds=1800),
    )


def test_intent_is_inactive_until_durable_authority_activates_it() -> None:
    intent = prepared()

    assert intent.active is False
    with pytest.raises(
        FirstRegistrationIntentError,
        match="secret_unavailable",
    ):
        intent.setup_secret_bytes()

    store = FirstRegistrationIntentStore()
    store.activate(intent)

    assert intent.active is True
    assert intent.setup_secret_bytes() == SECRET
    assert intent.remaining_seconds(now=NOW + timedelta(seconds=1700)) == 100
    assert "setup_secret=<redacted>" in repr(intent)
    assert SECRET.hex() not in repr(intent)


def test_intent_store_allows_only_one_active_transaction() -> None:
    store = FirstRegistrationIntentStore()
    first = prepared()
    store.activate(first)

    second = FirstRegistrationIntent.prepare(
        hardware_id="ghw-c6-00000000000b",
        pairing_id="7e0a9e6d-5b62-4de8-9d90-f1a8dd5774c9",
        source_ip="192.0.2.45",
        manager_id="manager_lab_01",
        system_id="greenhouse",
        setup_secret=bytes(reversed(range(32))),
        opened_at=NOW,
        expires_at=NOW + timedelta(seconds=1800),
    )

    with pytest.raises(
        FirstRegistrationIntentError,
        match="already_active",
    ):
        store.activate(second)

    assert (
        store.exact(
            hardware_id=HARDWARE_ID,
            pairing_id=PAIRING_ID,
            source_ip="192.0.2.44",
            manager_id="manager_lab_01",
            system_id="greenhouse",
        )
        is first
    )


def test_close_active_zeroizes_and_invalidates_secret() -> None:
    store = FirstRegistrationIntentStore()
    intent = prepared()
    store.activate(intent)

    store.close_active()

    assert store.current() is None
    assert intent.active is False
    assert intent.consumed is True
    with pytest.raises(
        FirstRegistrationIntentError,
        match="secret_unavailable",
    ):
        intent.setup_secret_bytes()
