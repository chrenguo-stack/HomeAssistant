from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

from .registration import HelloValidationError, RegistrationRegistry

PAIRING_HELLO_SUBSCRIPTION = "gh/bootstrap/v1/node/+/hello"
_PAIRING_HELLO_TOPIC = re.compile(
    r"^gh/bootstrap/v1/node/(?P<hardware_id>ghw-[a-z0-9]+-[0-9a-f]{12})/hello$"
)
_MAX_HELLO_BYTES = 4096


@dataclass(frozen=True, slots=True)
class PairingIntakeResult:
    status: str
    hardware_id: str | None = None
    pairing_id: str | None = None
    state: str | None = None
    reason: str | None = None


class PairingHelloProcessor:
    """Validate and persist untrusted bootstrap hello messages without replying."""

    def __init__(self, registry: RegistrationRegistry) -> None:
        self.registry = registry

    def process(
        self,
        topic: str,
        payload: bytes | str,
        *,
        received_at: datetime | None = None,
    ) -> PairingIntakeResult:
        match = _PAIRING_HELLO_TOPIC.fullmatch(topic)
        if match is None:
            return PairingIntakeResult("rejected", reason="invalid_topic")
        hardware_id = match.group("hardware_id")

        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
        if len(raw) > _MAX_HELLO_BYTES:
            return PairingIntakeResult("rejected", hardware_id=hardware_id, reason="payload_too_large")
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return PairingIntakeResult("rejected", hardware_id=hardware_id, reason="invalid_json")
        if not isinstance(document, dict):
            return PairingIntakeResult("rejected", hardware_id=hardware_id, reason="invalid_hello")
        if document.get("hardware_id") != hardware_id:
            return PairingIntakeResult(
                "rejected", hardware_id=hardware_id, reason="topic_hardware_mismatch"
            )

        try:
            observed = self.registry.observe_hello(document, now=received_at)
        except HelloValidationError:
            return PairingIntakeResult("rejected", hardware_id=hardware_id, reason="invalid_hello")

        return PairingIntakeResult(
            observed.status,
            hardware_id=observed.record.hardware_id,
            pairing_id=observed.record.pairing_id,
            state=observed.record.state,
            reason=observed.reason,
        )

    def expire_pending(self, *, now: datetime | None = None) -> int:
        return self.registry.expire_pending(now=now)


def redacted_hardware_id(hardware_id: str | None) -> str:
    return hardware_id[-6:] if hardware_id else "unknown"


def redacted_pairing_id(pairing_id: str | None) -> str:
    return pairing_id[:8] if pairing_id else "unknown"
