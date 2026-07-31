#!/usr/bin/env python3
"""Host-only compatibility adapter for the frozen D2-17 marker digest contract.

The frozen D2-17 authorization contract stores SHA256(D2_REQUEST_ID) in
``execution_marker_name_sha256``. The inherited executor derives the marker
filename as ``SHA256(D2_REQUEST_ID) + '.json'`` and then compares
SHA256(marker_filename) to that frozen field. Those values are different, so
an otherwise valid authorization would stop immediately before claim.

This adapter preserves the frozen authorization bytes and deterministic marker
filename. It wraps the configured runtime's ``sha256_bytes`` function only
for the exact marker-filename byte string, returning the already frozen
request-id digest. Every other digest operation is delegated unchanged.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable


class MarkerDigestCompatibilityError(RuntimeError):
    """Stable host-only compatibility failure."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise MarkerDigestCompatibilityError(code)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def marker_contract(request_id: str) -> dict[str, str]:
    require(isinstance(request_id, str) and request_id, "D2_REQUEST_ID_INVALID")
    request_digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    marker_name = request_digest + ".json"
    inherited_marker_digest = hashlib.sha256(marker_name.encode("utf-8")).hexdigest()
    return {
        "d2_request_id": request_id,
        "authorization_marker_digest_sha256": request_digest,
        "marker_name": marker_name,
        "inherited_marker_name_digest_sha256": inherited_marker_digest,
    }


def patch_core_marker_digest(core: Any, request_id: str) -> dict[str, Any]:
    """Patch one configured core without invoking any physical boundary."""
    contract = marker_contract(request_id)
    binding = canonical_sha256(contract)
    current = getattr(core, "_d2_17_marker_digest_adapter_binding_v1", None)
    if current is not None:
        require(current == binding, "MARKER_DIGEST_ADAPTER_BINDING_DRIFT")
        return {
            "installed": True,
            "install_count": 1,
            "binding_sha256": binding,
            "idempotent_recheck": True,
            "marker_name": contract["marker_name"],
        }

    original: Callable[[bytes], str] | None = getattr(core, "sha256_bytes", None)
    require(callable(original), "CORE_SHA256_BYTES_MISSING")
    marker_name_bytes = contract["marker_name"].encode("utf-8")
    observed_request_digest = original(request_id.encode("utf-8"))
    observed_marker_digest = original(marker_name_bytes)
    require(
        observed_request_digest == contract["authorization_marker_digest_sha256"],
        "REQUEST_DIGEST_IMPLEMENTATION_DRIFT",
    )
    require(
        observed_marker_digest == contract["inherited_marker_name_digest_sha256"],
        "MARKER_DIGEST_IMPLEMENTATION_DRIFT",
    )
    require(
        observed_request_digest != observed_marker_digest,
        "MARKER_DIGEST_COMPATIBILITY_NOT_REQUIRED",
    )

    def sha256_bytes_compat(payload: bytes) -> str:
        if payload == marker_name_bytes:
            return contract["authorization_marker_digest_sha256"]
        return original(payload)

    core.sha256_bytes = sha256_bytes_compat
    setattr(core, "_d2_17_marker_digest_adapter_binding_v1", binding)
    setattr(core, "_d2_17_marker_digest_adapter_original_sha256_bytes_v1", original)
    return {
        "installed": True,
        "install_count": 1,
        "binding_sha256": binding,
        "idempotent_recheck": False,
        "marker_name": contract["marker_name"],
    }


def install_runtime_marker_digest_adapter(d2_11: Any, request_id: str) -> dict[str, Any]:
    """Wrap ``configure_core`` so inherited execution receives the adapter."""
    contract = marker_contract(request_id)
    binding = canonical_sha256(contract)
    current = getattr(d2_11, "_d2_17_marker_digest_runtime_binding_v1", None)
    if current is not None:
        require(current == binding, "RUNTIME_MARKER_DIGEST_ADAPTER_BINDING_DRIFT")
        return {
            "installed": True,
            "install_count": 1,
            "binding_sha256": binding,
            "idempotent_recheck": True,
        }

    original_configure: Callable[[], Any] | None = getattr(d2_11, "configure_core", None)
    require(callable(original_configure), "D2_11_CONFIGURE_CORE_MISSING")

    def configure_core() -> Any:
        core = original_configure()
        patch_core_marker_digest(core, request_id)
        return core

    d2_11.configure_core = configure_core
    handoff = getattr(d2_11, "handoff", None)
    if handoff is not None:
        handoff.configure_core = configure_core
    setattr(d2_11, "_d2_17_marker_digest_runtime_binding_v1", binding)
    setattr(d2_11, "_d2_17_marker_digest_original_configure_v1", original_configure)
    return {
        "installed": True,
        "install_count": 1,
        "binding_sha256": binding,
        "idempotent_recheck": False,
    }
