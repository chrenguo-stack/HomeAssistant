from __future__ import annotations

import ipaddress
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

_HARDWARE_ID = re.compile(r"^ghw-[a-z0-9]+-[0-9a-f]{12}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class FirstRegistrationIntentError(RuntimeError):
    pass


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("first registration timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _canonical_pairing_id(value: str) -> str:
    try:
        parsed = str(uuid.UUID(value))
    except (ValueError, AttributeError) as error:
        raise ValueError("first registration pairing_id invalid") from error
    if parsed != value:
        raise ValueError("first registration pairing_id invalid")
    return value


@dataclass(slots=True, repr=False)
class FirstRegistrationIntent:
    hardware_id: str
    pairing_id: str
    source_ip: str
    manager_id: str
    system_id: str
    opened_at: datetime
    expires_at: datetime
    _setup_secret: bytearray = field(repr=False)
    active: bool = False
    consumed: bool = False

    @classmethod
    def prepare(
        cls,
        *,
        hardware_id: str,
        pairing_id: str,
        source_ip: str,
        manager_id: str,
        system_id: str,
        setup_secret: bytes,
        opened_at: datetime,
        expires_at: datetime,
    ) -> FirstRegistrationIntent:
        if _HARDWARE_ID.fullmatch(hardware_id) is None:
            raise ValueError("first registration hardware_id invalid")
        _canonical_pairing_id(pairing_id)
        for value, label in (
            (manager_id, "manager_id"),
            (system_id, "system_id"),
        ):
            if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
                raise ValueError(f"first registration {label} invalid")
        try:
            address = ipaddress.ip_address(source_ip)
        except ValueError as error:
            raise ValueError("first registration source_ip invalid") from error
        if not isinstance(address, ipaddress.IPv4Address) or address.is_unspecified:
            raise ValueError("first registration source_ip invalid")
        if not isinstance(setup_secret, bytes) or len(setup_secret) != 32:
            raise ValueError("first registration setup_secret invalid")
        opened = _utc(opened_at)
        expires = _utc(expires_at)
        if expires <= opened:
            raise ValueError("first registration deadline invalid")
        return cls(
            hardware_id=hardware_id,
            pairing_id=pairing_id,
            source_ip=str(address),
            manager_id=manager_id,
            system_id=system_id,
            opened_at=opened,
            expires_at=expires,
            _setup_secret=bytearray(setup_secret),
        )

    def matches(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        source_ip: str,
        manager_id: str,
        system_id: str,
    ) -> bool:
        return (
            self.hardware_id == hardware_id
            and self.pairing_id == pairing_id
            and self.source_ip == source_ip
            and self.manager_id == manager_id
            and self.system_id == system_id
            and self.active
            and not self.consumed
        )

    def setup_secret_bytes(self) -> bytes:
        if not self.active or self.consumed or len(self._setup_secret) != 32:
            raise FirstRegistrationIntentError(
                "first_registration_intent_secret_unavailable"
            )
        return bytes(self._setup_secret)

    def remaining_seconds(self, *, now: datetime) -> int:
        observed = _utc(now)
        return max(0, int((self.expires_at - observed).total_seconds()))

    def activate(self) -> None:
        if self.consumed or len(self._setup_secret) != 32:
            raise FirstRegistrationIntentError(
                "first_registration_intent_not_activatable"
            )
        self.active = True

    def close(self) -> None:
        self.active = False
        self.consumed = True
        for index in range(len(self._setup_secret)):
            self._setup_secret[index] = 0
        self._setup_secret.clear()

    def __repr__(self) -> str:
        return (
            "FirstRegistrationIntent("
            f"hardware_id={self.hardware_id!r}, "
            f"pairing_id={self.pairing_id!r}, "
            f"source_ip={self.source_ip!r}, "
            f"manager_id={self.manager_id!r}, "
            f"system_id={self.system_id!r}, "
            f"opened_at={self.opened_at!r}, "
            f"expires_at={self.expires_at!r}, "
            f"active={self.active!r}, consumed={self.consumed!r}, "
            "setup_secret=<redacted>)"
        )


class FirstRegistrationIntentStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active: FirstRegistrationIntent | None = None

    def current(self) -> FirstRegistrationIntent | None:
        with self._lock:
            return self._active

    def activate(self, intent: FirstRegistrationIntent) -> FirstRegistrationIntent:
        with self._lock:
            current = self._active
            if current is intent:
                return current
            if current is not None and current.active and not current.consumed:
                raise FirstRegistrationIntentError(
                    "first_registration_intent_already_active"
                )
            intent.activate()
            self._active = intent
            return intent

    def exact(
        self,
        *,
        hardware_id: str,
        pairing_id: str,
        source_ip: str,
        manager_id: str,
        system_id: str,
    ) -> FirstRegistrationIntent | None:
        with self._lock:
            current = self._active
            if current is None:
                return None
            if not current.matches(
                hardware_id=hardware_id,
                pairing_id=pairing_id,
                source_ip=source_ip,
                manager_id=manager_id,
                system_id=system_id,
            ):
                return None
            return current

    def close_active(self) -> None:
        with self._lock:
            current = self._active
            self._active = None
        if current is not None:
            current.close()
