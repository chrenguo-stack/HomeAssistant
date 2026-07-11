from __future__ import annotations

import base64
import re
import secrets
import uuid
from typing import Callable

HARDWARE_ID_PATTERN = re.compile(r"^ghw-[a-z0-9]+-[0-9a-f]{12}$")


def build_pairing_hello(
    *,
    hardware_id: str,
    pairing_epoch: int,
    model: str = "greenhouse-wifi-c6",
    fw_version: str = "simulator-M2.1a",
    sent_at_ms: int = 0,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    new_uuid: Callable[[], uuid.UUID] = uuid.uuid4,
) -> dict[str, object]:
    """Build simulator input for the manager's untrusted hello boundary."""
    if HARDWARE_ID_PATTERN.fullmatch(hardware_id) is None:
        raise ValueError("invalid hardware_id")
    if pairing_epoch < 1:
        raise ValueError("pairing_epoch must be positive")
    if sent_at_ms < 0:
        raise ValueError("sent_at_ms must not be negative")

    nonce = base64.urlsafe_b64encode(random_bytes(32)).rstrip(b"=").decode("ascii")
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": str(new_uuid()),
        "pairing_epoch": pairing_epoch,
        "hardware_id": hardware_id,
        "model": model,
        "fw_version": fw_version,
        "node_nonce": nonce,
        "capabilities": ["mqtt-runtime-credentials", "lcd-pairing-qr"],
        "sent_at_ms": sent_at_ms,
    }
