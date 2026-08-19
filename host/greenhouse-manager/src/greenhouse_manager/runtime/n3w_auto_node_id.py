from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime

from .registration import RegistrationConflict, RegistrationRecord, RegistrationRegistry

_RANDOM_BYTES = 16


class AutomaticNodeIdExhausted(RegistrationConflict):
    """Raised when bounded collision retries cannot allocate a fresh NODE_ID."""


class AutomaticNodeIdApprover:
    """Approve registration without requiring an operator-supplied NODE_ID.

    The generated identifier is opaque. Existing active assignments are preserved,
    while every historical lease state (including RETIRED) remains reserved.
    """

    def __init__(
        self,
        registry: RegistrationRegistry,
        *,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
        max_attempts: int = 16,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.registry = registry
        self.random_bytes = random_bytes
        self.max_attempts = max_attempts

    def approve(
        self,
        hardware_id: str,
        pairing_id: str,
        *,
        logical_location_id: str | None = None,
        now: datetime | None = None,
    ) -> RegistrationRecord:
        current = self.registry.get(hardware_id)
        if current.node_id is not None:
            return self.registry.approve(
                hardware_id,
                pairing_id,
                logical_location_id=logical_location_id,
                now=now,
            )

        for _ in range(self.max_attempts):
            candidate = self._candidate()
            if self.registry.node_id_lease_state(candidate) is not None:
                continue
            try:
                return self.registry.approve(
                    hardware_id,
                    pairing_id,
                    node_id=candidate,
                    logical_location_id=logical_location_id,
                    now=now,
                )
            except RegistrationConflict as error:
                if "already assigned" not in str(error):
                    raise
        raise AutomaticNodeIdExhausted("automatic node_id allocation exhausted")

    def _candidate(self) -> str:
        material = self.random_bytes(_RANDOM_BYTES)
        if not isinstance(material, bytes) or len(material) != _RANDOM_BYTES:
            raise AutomaticNodeIdExhausted("automatic node_id generator returned invalid length")
        return f"node_{material.hex()}"
