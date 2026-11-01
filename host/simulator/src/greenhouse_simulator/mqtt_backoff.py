from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0, 60.0)


class MqttFailureKind(StrEnum):
    CREDENTIAL_REJECTED = "credential_rejected"
    NETWORK_UNAVAILABLE = "network_unavailable"


@dataclass(frozen=True, slots=True)
class RetryDecision:
    delay_s: float
    failure_count: int
    local_sampling_enabled: bool = True
    pairing_auto_open: bool = False


class CredentialRetryBackoff:
    """Bound credential retry cadence without coupling MQTT to local sensing."""

    def __init__(
        self,
        *,
        random_unit: Callable[[], float],
        jitter_ratio: float = 0.2,
    ) -> None:
        if not 0 <= jitter_ratio <= 0.5:
            raise ValueError("jitter_ratio must be between 0 and 0.5")
        self.random_unit = random_unit
        self.jitter_ratio = jitter_ratio
        self.failure_count = 0

    def credential_rejected(self) -> RetryDecision:
        self.failure_count += 1
        index = min(self.failure_count - 1, len(BACKOFF_SECONDS) - 1)
        base = BACKOFF_SECONDS[index]
        random_value = self.random_unit()
        if not 0 <= random_value <= 1:
            raise ValueError("random_unit must return a value between 0 and 1")
        multiplier = 1 - self.jitter_ratio + (2 * self.jitter_ratio * random_value)
        return RetryDecision(
            delay_s=max(1.0, base * multiplier),
            failure_count=self.failure_count,
        )

    def connected(self) -> None:
        self.failure_count = 0

    def network_unavailable(self) -> RetryDecision:
        """Network faults do not consume the credential rejection counter."""
        return RetryDecision(delay_s=1.0, failure_count=self.failure_count)
