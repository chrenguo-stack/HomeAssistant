#!/usr/bin/env python3
"""Host-only runtime adapter for the D2-17 G07 preclaim identity TypeError.

The frozen D2-11 runtime validator accepts ``package_root`` as its third
contract argument. After the D2-17 contract is rebound across the complete
successor chain, that third argument is instead ``identity``. This adapter
replaces only the configured runtime authorization validator so the already
validated execution identity is supplied to the D2-17 contract.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


class IdentityAdapterRepairError(RuntimeError):
    """Stable host-only adapter failure."""


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise IdentityAdapterRepairError(code)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def identity_binding(identity: dict[str, Any]) -> str:
    """Return a stable, secret-free binding for the supplied identity object."""
    _require(isinstance(identity, dict), "EXECUTION_IDENTITY_TYPE_INVALID")
    supplied = identity.get("execution_identity_sha256")
    _require(
        isinstance(supplied, str) and len(supplied) == 64,
        "EXECUTION_IDENTITY_BINDING_INVALID",
    )
    return supplied


def install_runtime_identity_adapter(
    d2_11: Any,
    d2_17_contract: Any,
    identity: dict[str, Any],
) -> dict[str, Any]:
    """Install one identity-aware runtime authorization adapter.

    ``d2_11`` must be the exact module returned by D2-17
    ``bind_complete_chain``. The function is host-only and performs no board,
    serial, esptool, network, Broker, Flash/NVS, PREPARE, VERIFY or recovery
    operation.
    """
    binding = identity_binding(identity)
    current = getattr(d2_11, "_d2_17_identity_adapter_binding_v1", None)
    if current is not None:
        _require(current == binding, "RUNTIME_IDENTITY_ADAPTER_BINDING_DRIFT")
        return {
            "installed": True,
            "install_count": 1,
            "execution_identity_sha256": binding,
            "idempotent_recheck": True,
        }

    original_configure: Callable[[], Any] = getattr(d2_11, "configure_core", None)
    base_validate: Callable[..., dict[str, Any]] = getattr(
        d2_11, "_BASE_VALIDATE_AUTHORIZATION", None
    )
    _require(callable(original_configure), "D2_11_CONFIGURE_CORE_MISSING")
    _require(callable(base_validate), "D2_11_BASE_VALIDATOR_MISSING")
    _require(
        callable(getattr(d2_17_contract, "validate_authorization_contract", None)),
        "D2_17_AUTHORIZATION_CONTRACT_MISSING",
    )

    def configure_core() -> Any:
        core = original_configure()

        def validate_authorization(*args: Any, **kwargs: Any) -> dict[str, Any]:
            value = base_validate(*args, **kwargs)
            request = getattr(d2_11, "_BOUND_PHYSICAL_REQUEST", None)
            _require(isinstance(request, dict), "PHYSICAL_REQUEST_NOT_BOUND")
            d2_17_contract.validate_authorization_contract(
                value,
                request,
                identity,
                now=kwargs.get("now"),
            )
            return value

        core.validate_authorization = validate_authorization
        return core

    d2_11.configure_core = configure_core
    handoff = getattr(d2_11, "handoff", None)
    if handoff is not None:
        handoff.configure_core = configure_core
    setattr(d2_11, "_d2_17_identity_adapter_binding_v1", binding)
    setattr(d2_11, "_d2_17_identity_adapter_original_configure_v1", original_configure)
    return {
        "installed": True,
        "install_count": 1,
        "execution_identity_sha256": binding,
        "idempotent_recheck": False,
    }
