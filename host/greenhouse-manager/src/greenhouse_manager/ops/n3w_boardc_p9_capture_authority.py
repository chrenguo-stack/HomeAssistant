"""Board-C P9 durable hardware authority and capture boundary."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_HARDWARE_ID = re.compile(r"ghw-c6-([0-9a-f]{12})\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_USB_ID = re.compile(r"[0-9a-f]{12}\Z")


class AuthorityError(ValueError):
    """A secret-safe authority preparation failure."""


def _normalize_usb_identity(value: str) -> str:
    normalized = re.sub(r"[-:\s]", "", value).lower()
    if _USB_ID.fullmatch(normalized) is None:
        raise AuthorityError("USB_IDENTITY_FORMAT_INVALID")
    return normalized


@dataclass(frozen=True)
class BoardCP9CaptureAuthority:
    """Single source-owned authority used by USB and capture boundaries."""

    durable_hardware_id: str
    claim_pairing_id_sha256: str
    usb_serial_identity: str

    @property
    def normalized_durable_usb_identity(self) -> str:
        match = _HARDWARE_ID.fullmatch(self.durable_hardware_id)
        if match is None:
            raise AuthorityError("DURABLE_HARDWARE_ID_FORMAT_INVALID")
        return match.group(1)

    @property
    def capture_expected_hardware_id(self) -> str:
        """The only capture hardware value; it is the durable identity."""
        return self.durable_hardware_id

    def validate_usb_continuity(self) -> None:
        if _normalize_usb_identity(self.usb_serial_identity) != (
            self.normalized_durable_usb_identity
        ):
            raise AuthorityError("DURABLE_USB_IDENTITY_MISMATCH")


def prepare_boardc_p9_authority(
    durable_hardware_id: str,
    claim_pairing_id_sha256: str,
    usb_serial_identity: str,
) -> BoardCP9CaptureAuthority:
    """Prepare immutable authority without opening serial."""
    if _HARDWARE_ID.fullmatch(durable_hardware_id) is None:
        raise AuthorityError("DURABLE_HARDWARE_ID_FORMAT_INVALID")
    if _SHA256.fullmatch(claim_pairing_id_sha256) is None:
        raise AuthorityError("PAIRING_HASH_FORMAT_INVALID")
    authority = BoardCP9CaptureAuthority(
        durable_hardware_id=durable_hardware_id,
        claim_pairing_id_sha256=claim_pairing_id_sha256,
        usb_serial_identity=_normalize_usb_identity(usb_serial_identity),
    )
    authority.validate_usb_continuity()
    return authority


def invoke_capture_with_authority(
    authority: BoardCP9CaptureAuthority,
    capture_callable: Callable[..., Any],
    *,
    port: str,
    output: str,
    ack_live_serial_open_risk: bool,
) -> Any:
    """Pass only source-owned identity values to the low-level primitive."""
    authority.validate_usb_continuity()
    return capture_callable(
        port=port,
        output=output,
        expected_hardware_id=authority.capture_expected_hardware_id,
        expected_pairing_id_sha256=authority.claim_pairing_id_sha256,
        ack_live_serial_open_risk=ack_live_serial_open_risk,
    )


def public_authority_fingerprint(authority: BoardCP9CaptureAuthority) -> str:
    """Return a safe diagnostic fingerprint without exposing raw identities."""
    material = (
        authority.durable_hardware_id
        + authority.claim_pairing_id_sha256
        + authority.usb_serial_identity
    ).encode("ascii")
    return hashlib.sha256(material).hexdigest()
