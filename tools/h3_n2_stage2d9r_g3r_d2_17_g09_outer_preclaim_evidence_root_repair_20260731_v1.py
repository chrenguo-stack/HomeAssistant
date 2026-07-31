#!/usr/bin/env python3
"""Host-only repair for G09 outer preclaim validation ordering.

The physical decision driver must not call the configured D2-11 core before
``prepare_payload_handoff`` binds the prepare, delivery and terminalization
roots. This module validates the same authorization closure using the frozen
base validator plus the D2-17 execution-identity contract, without calling
``configure_core``. The inherited executor still performs its normal
prepare-payload-handoff -> configure-core ordering.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


class OuterPreclaimRepairError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise OuterPreclaimRepairError(code)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def verify_self_binding(value: dict[str, Any], field: str, expected: str) -> None:
    embedded = value.get(field)
    core = dict(value)
    core.pop(field, None)
    require(embedded == expected, field.upper() + "_EXPECTED_DRIFT")
    require(canonical_sha256(core) == expected, field.upper() + "_SEMANTIC_DRIFT")


def validate_outer_preclaim_without_unbound_configure(
    *,
    d2_11: Any,
    d2_17_contract: Any,
    authorization_path: Path,
    authorization: dict[str, Any],
    request: dict[str, Any],
    identity: dict[str, Any],
    package_root: Path,
    python_path: Path,
    openssl_path: Path,
    esptool_path: Path,
    mosquitto_path: Path,
    now: datetime | None,
    home: Path,
    private_metadata_validator: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    """Validate the outer preclaim closure without calling ``configure_core``."""
    base_validate = getattr(d2_11, "_BASE_VALIDATE_AUTHORIZATION", None)
    core = getattr(d2_11, "core", None)
    require(callable(base_validate), "D2_11_BASE_VALIDATOR_MISSING")
    require(core is not None, "D2_11_CORE_MISSING")
    require(
        callable(getattr(d2_17_contract, "validate_execution_identity", None)),
        "D2_17_IDENTITY_VALIDATOR_MISSING",
    )
    require(
        callable(getattr(d2_17_contract, "validate_authorization_contract", None)),
        "D2_17_AUTHORIZATION_VALIDATOR_MISSING",
    )

    d2_17_contract.validate_execution_identity(
        identity,
        package_root,
        request=request,
        controller_path=Path(core.__file__),
        python_path=python_path,
        openssl_path=openssl_path,
        esptool_path=esptool_path,
        mosquitto_path=mosquitto_path,
    )
    d2_17_contract.validate_authorization_contract(
        authorization,
        request,
        identity,
        now=now,
    )
    validator = private_metadata_validator
    if validator is None:
        validator = getattr(core, "validate_private_metadata", None)
    require(callable(validator), "PRIVATE_METADATA_VALIDATOR_MISSING")
    validator(home)
    validated = base_validate(
        authorization_path,
        package_root=package_root,
        python_path=python_path,
        openssl_path=openssl_path,
        esptool_path=esptool_path,
        mosquitto_path=mosquitto_path,
        now=now,
    )
    require(isinstance(validated, dict), "BASE_AUTHORIZATION_RESULT_INVALID")
    return {
        "status": "PASS",
        "configured_core_called": False,
        "base_authorization_validator_executed": True,
        "d2_17_execution_identity_contract_executed": True,
        "d2_17_authorization_contract_executed": True,
        "private_metadata_validator_executed": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "physical_nvs_operation": False,
    }
