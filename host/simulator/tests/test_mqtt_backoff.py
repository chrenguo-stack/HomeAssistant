from __future__ import annotations

import pytest

from greenhouse_simulator.mqtt_backoff import (
    BACKOFF_SECONDS,
    CredentialRetryBackoff,
)


def test_credential_rejection_uses_bounded_exponential_schedule() -> None:
    backoff = CredentialRetryBackoff(random_unit=lambda: 0.5)

    decisions = [backoff.credential_rejected() for _ in range(10)]

    assert [decision.delay_s for decision in decisions] == [
        1.0,
        2.0,
        4.0,
        8.0,
        15.0,
        30.0,
        60.0,
        60.0,
        60.0,
        60.0,
    ]
    assert decisions[-1].failure_count == 10


@pytest.mark.parametrize(
    ("random_value", "expected"),
    [(0.0, 12.0), (0.5, 15.0), (1.0, 18.0)],
)
def test_applies_bounded_jitter(random_value: float, expected: float) -> None:
    backoff = CredentialRetryBackoff(
        random_unit=lambda: random_value, jitter_ratio=0.2
    )
    backoff.failure_count = 4

    assert backoff.credential_rejected().delay_s == pytest.approx(expected)


def test_success_resets_schedule() -> None:
    backoff = CredentialRetryBackoff(random_unit=lambda: 0.5)
    for _ in BACKOFF_SECONDS:
        backoff.credential_rejected()

    backoff.connected()

    assert backoff.credential_rejected().delay_s == 1.0
    assert backoff.failure_count == 1


def test_network_fault_does_not_consume_credential_backoff() -> None:
    backoff = CredentialRetryBackoff(random_unit=lambda: 0.5)
    backoff.credential_rejected()

    decision = backoff.network_unavailable()

    assert decision.delay_s == 1.0
    assert decision.failure_count == 1


def test_retry_never_disables_sampling_or_silently_opens_pairing() -> None:
    backoff = CredentialRetryBackoff(random_unit=lambda: 0.0)

    decisions = [backoff.credential_rejected() for _ in range(20)]

    assert all(decision.local_sampling_enabled for decision in decisions)
    assert not any(decision.pairing_auto_open for decision in decisions)


@pytest.mark.parametrize("random_value", [-0.01, 1.01])
def test_rejects_invalid_random_source(random_value: float) -> None:
    backoff = CredentialRetryBackoff(random_unit=lambda: random_value)

    with pytest.raises(ValueError, match="random_unit"):
        backoff.credential_rejected()
