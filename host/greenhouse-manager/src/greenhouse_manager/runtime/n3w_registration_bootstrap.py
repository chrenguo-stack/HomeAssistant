from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .n3w_trusted_product_lan import (
    TrustedProductLanState,
    load_trusted_product_lan,
)

CONFIRM_SCHEMA = "gh.registration.confirm/1"


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
    normalized: dict[str, str] = {}
    for name in _REQUIRED_FIELDS - {"schema"}:
        value = document.get(name)
        if not isinstance(value, str) or not value or len(value) > 256:
            raise RegistrationBootstrapRejected("identity_invalid")
        normalized[name] = value
    return normalized


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
