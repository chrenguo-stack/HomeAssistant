from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from greenhouse_manager.bootstrap.system_init import (
    InitializationError,
    _canonical_json,
    _private_directory,
    _write_atomic,
)

IDENTITY_GUARD_SCHEMA = "gh.h0h1.system-identity-guard/1"
CLAIM_CONFIRMATION = "CLAIM-GREENHOUSE-SYSTEM-IDENTITY"
RELEASE_CONFIRMATION = "RELEASE-GREENHOUSE-SYSTEM-IDENTITY"


class IdentityConflictError(InitializationError):
    pass


@dataclass(frozen=True)
class IdentityGuardReport:
    schema: str
    system_id: str
    host_instance_id: str | None
    claimed: bool
    changed: bool
    conflict_detected: bool
    production_services_modified: bool
    network_operation: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _empty_registry() -> dict[str, Any]:
    return {
        "schema": IDENTITY_GUARD_SCHEMA,
        "claims": {},
        "production_services_modified": False,
        "network_operation": False,
    }


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_registry()
    if path.is_symlink() or not path.is_file():
        raise IdentityConflictError("identity registry must be a regular file")
    if path.stat().st_mode & 0o777 != 0o600:
        raise IdentityConflictError("identity registry mode drift")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise IdentityConflictError("identity registry is invalid") from error
    if not isinstance(document, dict) or document.get("schema") != IDENTITY_GUARD_SCHEMA:
        raise IdentityConflictError("identity registry schema is unsupported")
    claims = document.get("claims")
    if not isinstance(claims, dict):
        raise IdentityConflictError("identity registry claims are invalid")
    return document


def inspect_identity(
    registry_root: str | Path,
    system_id: str,
) -> IdentityGuardReport:
    root = Path(registry_root).expanduser().resolve()
    _private_directory(root)
    document = _load_registry(root / "identity-claims.json")
    claim = document["claims"].get(system_id)
    if claim is not None and not isinstance(claim, dict):
        raise IdentityConflictError("identity claim is invalid")
    return IdentityGuardReport(
        schema=IDENTITY_GUARD_SCHEMA,
        system_id=system_id,
        host_instance_id=(str(claim["host_instance_id"]) if claim else None),
        claimed=claim is not None,
        changed=False,
        conflict_detected=False,
        production_services_modified=False,
        network_operation=False,
    )


def claim_identity(
    registry_root: str | Path,
    *,
    system_id: str,
    host_instance_id: str,
    enable: bool = False,
    confirmation: str | None = None,
    now: datetime | None = None,
) -> IdentityGuardReport:
    if not system_id or not host_instance_id:
        raise ValueError("system_id and host_instance_id must not be empty")
    root = Path(registry_root).expanduser().resolve()
    _private_directory(root)
    path = root / "identity-claims.json"
    document = _load_registry(path)
    existing = document["claims"].get(system_id)
    if existing is not None:
        existing_host = str(existing["host_instance_id"])
        if existing_host != host_instance_id:
            raise IdentityConflictError(
                "system identity is already active on another host instance"
            )
        return IdentityGuardReport(
            schema=IDENTITY_GUARD_SCHEMA,
            system_id=system_id,
            host_instance_id=host_instance_id,
            claimed=True,
            changed=False,
            conflict_detected=False,
            production_services_modified=False,
            network_operation=False,
        )
    if not enable:
        raise IdentityConflictError("identity claim is disabled")
    if confirmation != CLAIM_CONFIRMATION:
        raise IdentityConflictError("identity claim confirmation does not match")

    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    document["claims"][system_id] = {
        "host_instance_id": host_instance_id,
        "claimed_at": observed_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    _write_atomic(path, _canonical_json(document) + b"\n")
    return IdentityGuardReport(
        schema=IDENTITY_GUARD_SCHEMA,
        system_id=system_id,
        host_instance_id=host_instance_id,
        claimed=True,
        changed=True,
        conflict_detected=False,
        production_services_modified=False,
        network_operation=False,
    )


def release_identity(
    registry_root: str | Path,
    *,
    system_id: str,
    host_instance_id: str,
    enable: bool = False,
    confirmation: str | None = None,
) -> IdentityGuardReport:
    root = Path(registry_root).expanduser().resolve()
    _private_directory(root)
    path = root / "identity-claims.json"
    document = _load_registry(path)
    existing = document["claims"].get(system_id)
    if existing is None:
        return IdentityGuardReport(
            schema=IDENTITY_GUARD_SCHEMA,
            system_id=system_id,
            host_instance_id=None,
            claimed=False,
            changed=False,
            conflict_detected=False,
            production_services_modified=False,
            network_operation=False,
        )
    if str(existing["host_instance_id"]) != host_instance_id:
        raise IdentityConflictError("identity release host binding does not match")
    if not enable:
        raise IdentityConflictError("identity release is disabled")
    if confirmation != RELEASE_CONFIRMATION:
        raise IdentityConflictError("identity release confirmation does not match")
    del document["claims"][system_id]
    _write_atomic(path, _canonical_json(document) + b"\n")
    return IdentityGuardReport(
        schema=IDENTITY_GUARD_SCHEMA,
        system_id=system_id,
        host_instance_id=None,
        claimed=False,
        changed=True,
        conflict_detected=False,
        production_services_modified=False,
        network_operation=False,
    )
