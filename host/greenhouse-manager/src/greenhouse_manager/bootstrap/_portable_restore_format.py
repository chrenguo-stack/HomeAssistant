from __future__ import annotations

import base64
import io
import json
import struct
import tarfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
except ImportError:  # pragma: no cover - exercised only in incomplete installations.
    InvalidTag = None
    AESGCM = None
    Scrypt = None

from greenhouse_manager.bootstrap.system_init import (
    MANAGER_IDENTITY_NAME,
    SYSTEM_CA_CERTIFICATE_NAME,
    SYSTEM_CA_PRIVATE_KEY_NAME,
    SYSTEM_IDENTITY_NAME,
    SYSTEM_ROOT_KEY_NAME,
    InitializationError,
    _absolute_path,
    _canonical_json,
    _sha256_bytes,
)

ENVELOPE_SCHEMA = "gh.h0h1.portable-backup-envelope/1"
MANIFEST_SCHEMA = "gh.h0h1.portable-restore-manifest/1"
RESTORE_SCHEMA = "gh.h0h1.portable-restore-result/1"
MAGIC = b"GHPR1\x00"
CREATE_CONFIRMATION = "CREATE-PORTABLE-GREENHOUSE-BACKUP"
RESTORE_CONFIRMATION = "RESTORE-PORTABLE-GREENHOUSE-BACKUP"
RESTORE_MARKER = "RESTORE_COMPLETE.json"

ROLE_SYSTEM_IDENTITY = "system_identity"
ROLE_SYSTEM_ROOT_KEY = "system_root_key"
ROLE_SYSTEM_CA_CERTIFICATE = "system_ca_certificate"
ROLE_SYSTEM_CA_PRIVATE_KEY = "system_ca_private_key"
ROLE_MANAGER_IDENTITY = "manager_identity"
ROLE_MANAGER_REGISTRATION_STATE = "manager_registration_state"
ROLE_MANAGER_CREDENTIAL_STATE = "manager_credential_lifecycle_state"
ROLE_MANAGER_RETIREMENT_OUTBOX = "manager_retirement_outbox_state"
ROLE_BROKER_DYNAMIC_SECURITY = "broker_dynamic_security_state"
ROLE_BROKER_PERSISTENCE = "broker_persistence_state"

REQUIRED_ROLES = frozenset(
    {
        ROLE_SYSTEM_IDENTITY,
        ROLE_SYSTEM_ROOT_KEY,
        ROLE_SYSTEM_CA_CERTIFICATE,
        ROLE_SYSTEM_CA_PRIVATE_KEY,
        ROLE_MANAGER_IDENTITY,
        ROLE_MANAGER_REGISTRATION_STATE,
        ROLE_MANAGER_CREDENTIAL_STATE,
        ROLE_MANAGER_RETIREMENT_OUTBOX,
        ROLE_BROKER_DYNAMIC_SECURITY,
        ROLE_BROKER_PERSISTENCE,
    }
)

IDENTITY_DEFAULT_PATHS = {
    ROLE_SYSTEM_IDENTITY: SYSTEM_IDENTITY_NAME,
    ROLE_SYSTEM_ROOT_KEY: SYSTEM_ROOT_KEY_NAME,
    ROLE_SYSTEM_CA_CERTIFICATE: SYSTEM_CA_CERTIFICATE_NAME,
    ROLE_SYSTEM_CA_PRIVATE_KEY: SYSTEM_CA_PRIVATE_KEY_NAME,
    ROLE_MANAGER_IDENTITY: MANAGER_IDENTITY_NAME,
}

AAD_FIELDS = (
    "schema",
    "created_at",
    "system_id",
    "manager_id",
    "salt",
    "nonce",
    "kdf",
    "manifest_sha256",
    "plaintext_sha256",
    "portable_off_host",
    "restore_target_absent_required",
    "live_apply_enabled",
)


class PortableRestoreError(InitializationError):
    pass


@dataclass(frozen=True)
class PortableBackupReport:
    schema: str
    system_id: str
    manager_id: str
    manifest_sha256: str
    envelope_sha256: str
    file_count: int
    role_count: int
    encrypted: bool
    portable_off_host: bool
    live_apply_enabled: bool
    production_services_modified: bool
    network_operation: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortableRestoreReport:
    schema: str
    system_id: str
    manager_id: str
    manifest_sha256: str
    envelope_sha256: str
    file_count: int
    restored: bool
    activation_enabled: bool
    production_services_modified: bool
    network_operation: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_crypto() -> None:
    if AESGCM is None or Scrypt is None:
        raise PortableRestoreError(
            "cryptography is required; install greenhouse-manager with the bootstrap extra"
        )


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError) as error:
        raise PortableRestoreError("portable backup base64 field is invalid") from error


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or value == "."
        or ".." in path.parts
        or "\\" in value
    ):
        raise PortableRestoreError(f"unsafe inventory path: {value}")
    return path.as_posix()


def _read_json_bytes(value: bytes, *, name: str) -> dict[str, Any]:
    try:
        document = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PortableRestoreError(f"invalid JSON component: {name}") from error
    if not isinstance(document, dict):
        raise PortableRestoreError(f"invalid JSON object: {name}")
    return document


def _source_file(root: Path, relative: str) -> tuple[Path, bytes, int]:
    path = _absolute_path(
        root.joinpath(*PurePosixPath(relative).parts),
        error_type=PortableRestoreError,
        label=f"portable backup inventory member {relative}",
    )
    try:
        path.relative_to(root)
    except ValueError as error:
        raise PortableRestoreError(f"inventory member escapes source root: {relative}") from error
    if not path.is_file():
        raise PortableRestoreError(f"inventory member is not a regular file: {relative}")
    mode = path.stat().st_mode & 0o777
    if mode != 0o600:
        raise PortableRestoreError(f"inventory member mode must be 0600: {relative}")
    return path, path.read_bytes(), mode


def _normalize_inventory(inventory: Mapping[str, str]) -> dict[str, str]:
    if set(inventory) != REQUIRED_ROLES:
        missing = sorted(REQUIRED_ROLES - set(inventory))
        extra = sorted(set(inventory) - REQUIRED_ROLES)
        raise PortableRestoreError(
            f"portable backup role inventory mismatch: missing={missing}, extra={extra}"
        )
    return {role: _safe_relative(str(inventory[role])) for role in sorted(inventory)}


def _build_payload(
    source_root: Path,
    inventory: Mapping[str, str],
    *,
    observed_at: datetime,
) -> tuple[bytes, dict[str, Any]]:
    normalized = _normalize_inventory(inventory)
    unique_paths = sorted(set(normalized.values()))
    role_by_path: dict[str, list[str]] = {path: [] for path in unique_paths}
    for role, relative in normalized.items():
        role_by_path[relative].append(role)

    members: dict[str, tuple[bytes, int]] = {}
    records: list[dict[str, Any]] = []
    for relative in unique_paths:
        _path, payload, mode = _source_file(source_root, relative)
        members[relative] = (payload, mode)
        records.append(
            {
                "path": relative,
                "roles": sorted(role_by_path[relative]),
                "size": len(payload),
                "mode": mode,
                "sha256": _sha256_bytes(payload),
            }
        )

    system_identity_path = normalized[ROLE_SYSTEM_IDENTITY]
    manager_identity_path = normalized[ROLE_MANAGER_IDENTITY]
    system_identity = _read_json_bytes(
        members[system_identity_path][0],
        name=ROLE_SYSTEM_IDENTITY,
    )
    manager_identity = _read_json_bytes(
        members[manager_identity_path][0],
        name=ROLE_MANAGER_IDENTITY,
    )
    system_id = system_identity.get("system_id")
    manager_id = manager_identity.get("manager_id")
    if not isinstance(system_id, str) or not system_id:
        raise PortableRestoreError("system identity is missing system_id")
    if not isinstance(manager_id, str) or not manager_id:
        raise PortableRestoreError("manager identity is missing manager_id")
    if manager_identity.get("system_id") != system_id:
        raise PortableRestoreError("manager identity is bound to another system")

    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "created_at": observed_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "system_id": system_id,
        "manager_id": manager_id,
        "portable_off_host": True,
        "encrypted": True,
        "complete_pairing_state": True,
        "restore_target_absent_required": True,
        "live_apply_enabled": False,
        "production_services_modified": False,
        "network_operation": False,
        "roles": normalized,
        "files": records,
    }
    manifest_bytes = _canonical_json(manifest) + b"\n"

    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        manifest_info = tarfile.TarInfo("manifest.json")
        manifest_info.size = len(manifest_bytes)
        manifest_info.mode = 0o600
        manifest_info.mtime = 0
        manifest_info.uid = 0
        manifest_info.gid = 0
        manifest_info.uname = ""
        manifest_info.gname = ""
        archive.addfile(manifest_info, io.BytesIO(manifest_bytes))
        for relative in unique_paths:
            payload, _source_mode = members[relative]
            info = tarfile.TarInfo(relative)
            info.size = len(payload)
            info.mode = 0o600
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(payload))
    return stream.getvalue(), manifest


def _derive_key(passphrase: str, salt: bytes, kdf: Mapping[str, int]) -> bytes:
    _require_crypto()
    if len(passphrase) < 12:
        raise PortableRestoreError("portable backup passphrase must contain at least 12 characters")
    derivation = Scrypt(
        salt=salt,
        length=32,
        n=int(kdf["n"]),
        r=int(kdf["r"]),
        p=int(kdf["p"]),
    )
    return derivation.derive(passphrase.encode("utf-8"))


def _aad_from_header(header: Mapping[str, Any]) -> bytes:
    try:
        aad = {field: header[field] for field in AAD_FIELDS}
    except KeyError as error:
        raise PortableRestoreError("portable backup header is incomplete") from error
    return _canonical_json(aad)


def _encode_envelope(header: Mapping[str, Any], ciphertext: bytes) -> bytes:
    header_bytes = _canonical_json(header)
    return MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes + ciphertext


def _decode_envelope(value: bytes) -> tuple[dict[str, Any], bytes]:
    if not value.startswith(MAGIC) or len(value) < len(MAGIC) + 4:
        raise PortableRestoreError("portable backup magic is invalid")
    offset = len(MAGIC)
    header_length = struct.unpack(">I", value[offset : offset + 4])[0]
    offset += 4
    if header_length <= 0 or header_length > 1024 * 1024:
        raise PortableRestoreError("portable backup header length is invalid")
    end = offset + header_length
    if end >= len(value):
        raise PortableRestoreError("portable backup is truncated")
    try:
        header = json.loads(value[offset:end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PortableRestoreError("portable backup header is invalid") from error
    if not isinstance(header, dict) or header.get("schema") != ENVELOPE_SCHEMA:
        raise PortableRestoreError("portable backup envelope schema is unsupported")
    ciphertext = value[end:]
    if _sha256_bytes(ciphertext) != header.get("ciphertext_sha256"):
        raise PortableRestoreError("portable backup ciphertext digest drift")
    return header, ciphertext


