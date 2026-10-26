from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from .n3w_trusted_product_lan import (
    TrustedProductLanState,
    load_trusted_product_lan,
)

CONFIRM_SCHEMA = "gh.registration.confirm/1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HARDWARE_ID = re.compile(r"^ghw-[a-z0-9]+-[0-9a-f]{12}$")
_SETUP_SECRET = re.compile(r"^[A-Za-z0-9_-]{43}$")


class RegistrationBootstrapRejected(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BootstrapSkeletonResult:
    status: str
    reason: str
    transaction_started: bool = False

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": "gh.registration.confirm-result/1",
            "accepted": False,
            "status": self.status,
            "reason": self.reason,
            "transaction_started": self.transaction_started,
        }


_REQUIRED_FIELDS = {
    "schema",
    "manager_id",
    "system_id",
    "hardware_id",
    "pairing_id",
    "setup_secret",
}


def validate_bootstrap_source(
    source_ip: str,
    *,
    state_loader: Callable[[], TrustedProductLanState] = load_trusted_product_lan,
) -> None:
    state = state_loader()
    if not state.available:
        raise RegistrationBootstrapRejected("trusted_product_lan_unavailable")
    if not state.authorizes(source_ip):
        raise RegistrationBootstrapRejected("source_not_trusted_product_lan")


def validate_confirm_document(document: Any) -> dict[str, str]:
    if not isinstance(document, dict) or set(document) != _REQUIRED_FIELDS:
        raise RegistrationBootstrapRejected("identity_invalid")
    if document.get("schema") != CONFIRM_SCHEMA:
        raise RegistrationBootstrapRejected("identity_invalid")
    manager_id = document.get("manager_id")
    system_id = document.get("system_id")
    hardware_id = document.get("hardware_id")
    pairing_id = document.get("pairing_id")
    setup_secret = document.get("setup_secret")
    if (
        not isinstance(manager_id, str)
        or _SAFE_ID.fullmatch(manager_id) is None
        or not isinstance(system_id, str)
        or _SAFE_ID.fullmatch(system_id) is None
        or not isinstance(hardware_id, str)
        or _HARDWARE_ID.fullmatch(hardware_id) is None
        or not isinstance(pairing_id, str)
        or not isinstance(setup_secret, str)
        or _SETUP_SECRET.fullmatch(setup_secret) is None
    ):
        raise RegistrationBootstrapRejected("identity_invalid")
    try:
        parsed_pairing = uuid.UUID(pairing_id)
    except ValueError as error:
        raise RegistrationBootstrapRejected("identity_invalid") from error
    if str(parsed_pairing) != pairing_id.lower():
        raise RegistrationBootstrapRejected("identity_invalid")
    return {
        "manager_id": manager_id,
        "system_id": system_id,
        "hardware_id": hardware_id,
        "pairing_id": pairing_id,
        "setup_secret": setup_secret,
    }


def evaluate_confirm_skeleton(
    document: Any,
    *,
    source_ip: str,
    expected_manager_id: str,
    expected_system_id: str,
    state_loader: Callable[[], TrustedProductLanState] = load_trusted_product_lan,
) -> BootstrapSkeletonResult:
    validate_bootstrap_source(source_ip, state_loader=state_loader)
    request = validate_confirm_document(document)
    if request["manager_id"] != expected_manager_id:
        raise RegistrationBootstrapRejected("manager_mismatch")
    if request["system_id"] != expected_system_id:
        raise RegistrationBootstrapRejected("system_mismatch")
    return BootstrapSkeletonResult(
        status="unavailable",
        reason="first_registration_transaction_not_implemented",
    )
