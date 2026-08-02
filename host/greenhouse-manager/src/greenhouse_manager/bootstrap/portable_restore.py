from __future__ import annotations

import io
import os
import secrets
import tarfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from greenhouse_manager.bootstrap._portable_restore_format import (
    AESGCM,
    CREATE_CONFIRMATION,
    ENVELOPE_SCHEMA,
    InvalidTag,
    MANIFEST_SCHEMA,
    REQUIRED_ROLES,
    RESTORE_CONFIRMATION,
    RESTORE_MARKER,
    RESTORE_SCHEMA,
    ROLE_BROKER_DYNAMIC_SECURITY,
    ROLE_BROKER_PERSISTENCE,
    ROLE_MANAGER_CREDENTIAL_STATE,
    ROLE_MANAGER_IDENTITY,
    ROLE_MANAGER_REGISTRATION_STATE,
    ROLE_MANAGER_RETIREMENT_OUTBOX,
    ROLE_SYSTEM_CA_CERTIFICATE,
    ROLE_SYSTEM_CA_PRIVATE_KEY,
    ROLE_SYSTEM_IDENTITY,
    ROLE_SYSTEM_ROOT_KEY,
    PortableBackupReport,
    PortableRestoreError,
    PortableRestoreReport,
    _aad_from_header,
    _b64,
    _build_payload,
    _canonical_json,
    _decode_envelope,
    _derive_key,
    _encode_envelope,
    _private_directory,
    _read_json_bytes,
    _require_crypto,
    _safe_relative,
    _sha256_bytes,
    _unb64,
    _write_atomic,
)


def create_portable_backup(
    source_root: str | Path,
    inventory: Mapping[str, str],
    output_path: str | Path,
    *,
    passphrase: str,
    enable: bool = False,
    confirmation: str | None = None,
    now: datetime | None = None,
) -> PortableBackupReport:
    _require_crypto()
    if not enable:
        raise PortableRestoreError("portable backup creation is disabled")
    if confirmation != CREATE_CONFIRMATION:
        raise PortableRestoreError("portable backup creation confirmation does not match")
    root = Path(source_root).expanduser().resolve()
    if root.is_symlink() or not root.is_dir():
        raise PortableRestoreError("portable backup source root must be a real directory")
    destination = Path(output_path).expanduser().resolve()
    _private_directory(destination.parent)
    if destination.exists() or destination.is_symlink():
        raise PortableRestoreError("portable backup destination already exists")

    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    plaintext, manifest = _build_payload(root, inventory, observed_at=observed_at)
    manifest_bytes = _canonical_json(manifest) + b"\n"
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    kdf = {"name": "scrypt", "n": 16384, "r": 8, "p": 1}
    header: dict[str, Any] = {
        "schema": ENVELOPE_SCHEMA,
        "created_at": manifest["created_at"],
        "system_id": manifest["system_id"],
        "manager_id": manifest["manager_id"],
        "salt": _b64(salt),
        "nonce": _b64(nonce),
        "kdf": kdf,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "plaintext_sha256": _sha256_bytes(plaintext),
        "portable_off_host": True,
        "restore_target_absent_required": True,
        "live_apply_enabled": False,
    }
    aad = _aad_from_header(header)
    key = _derive_key(passphrase, salt, kdf)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    header["ciphertext_sha256"] = _sha256_bytes(ciphertext)
    envelope = _encode_envelope(header, ciphertext)
    _write_atomic(destination, envelope)

    return PortableBackupReport(
        schema=ENVELOPE_SCHEMA,
        system_id=str(manifest["system_id"]),
        manager_id=str(manifest["manager_id"]),
        manifest_sha256=str(header["manifest_sha256"]),
        envelope_sha256=_sha256_bytes(envelope),
        file_count=len(manifest["files"]),
        role_count=len(manifest["roles"]),
        encrypted=True,
        portable_off_host=True,
        live_apply_enabled=False,
        production_services_modified=False,
        network_operation=False,
    )


def _decrypt_envelope(
    path: Path,
    passphrase: str,
) -> tuple[dict[str, Any], bytes, str]:
    _require_crypto()
    if path.is_symlink() or not path.is_file():
        raise PortableRestoreError("portable backup must be a regular file")
    if path.stat().st_mode & 0o077:
        raise PortableRestoreError("portable backup permissions are not private")
    envelope = path.read_bytes()
    header, ciphertext = _decode_envelope(envelope)
    kdf = header.get("kdf")
    if (
        not isinstance(kdf, dict)
        or kdf.get("name") != "scrypt"
        or kdf.get("n") != 16384
        or kdf.get("r") != 8
        or kdf.get("p") != 1
    ):
        raise PortableRestoreError("portable backup KDF contract is unsupported")
    salt = _unb64(str(header.get("salt", "")))
    nonce = _unb64(str(header.get("nonce", "")))
    if len(salt) != 16 or len(nonce) != 12:
        raise PortableRestoreError("portable backup cryptographic parameters are invalid")
    key = _derive_key(passphrase, salt, kdf)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, _aad_from_header(header))
    except Exception as error:
        if InvalidTag is not None and isinstance(error, InvalidTag):
            raise PortableRestoreError("portable backup authentication failed") from error
        raise
    if _sha256_bytes(plaintext) != header.get("plaintext_sha256"):
        raise PortableRestoreError("portable backup plaintext digest drift")
    return header, plaintext, _sha256_bytes(envelope)


def _verify_payload(
    header: Mapping[str, Any],
    plaintext: bytes,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:") as archive:
        members = archive.getmembers()
        if not members or members[0].name != "manifest.json":
            raise PortableRestoreError("portable backup manifest is missing")
        names: list[str] = []
        payloads: dict[str, bytes] = {}
        for member in members:
            name = _safe_relative(member.name)
            if name in names:
                raise PortableRestoreError("portable backup contains duplicate members")
            names.append(name)
            if not member.isfile() or member.issym() or member.islnk():
                raise PortableRestoreError("portable backup contains a non-regular member")
            stream = archive.extractfile(member)
            if stream is None:
                raise PortableRestoreError(f"portable backup member cannot be read: {name}")
            payloads[name] = stream.read()

    manifest_payload = payloads.pop("manifest.json")
    if _sha256_bytes(manifest_payload) != header.get("manifest_sha256"):
        raise PortableRestoreError("portable backup manifest digest drift")
    manifest = _read_json_bytes(manifest_payload, name="manifest")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise PortableRestoreError("portable backup manifest schema is unsupported")
    if manifest.get("system_id") != header.get("system_id"):
        raise PortableRestoreError("portable backup system identity binding drift")
    if manifest.get("manager_id") != header.get("manager_id"):
        raise PortableRestoreError("portable backup manager identity binding drift")
    roles = manifest.get("roles")
    if not isinstance(roles, dict) or set(roles) != REQUIRED_ROLES:
        raise PortableRestoreError("portable backup role inventory is incomplete")
    expected_names = {_safe_relative(str(value)) for value in roles.values()}
    if set(payloads) != expected_names:
        raise PortableRestoreError("portable backup member inventory mismatch")

    records = manifest.get("files")
    if not isinstance(records, list):
        raise PortableRestoreError("portable backup file records are invalid")
    by_path = {
        record.get("path"): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }
    if set(by_path) != expected_names:
        raise PortableRestoreError("portable backup file record inventory mismatch")
    for name, payload in payloads.items():
        record = by_path[name]
        if record.get("mode") != 0o600:
            raise PortableRestoreError(f"portable backup member mode is invalid: {name}")
        if record.get("size") != len(payload):
            raise PortableRestoreError(f"portable backup member size drift: {name}")
        if record.get("sha256") != _sha256_bytes(payload):
            raise PortableRestoreError(f"portable backup member digest drift: {name}")
        expected_roles = sorted(role for role, path in roles.items() if path == name)
        if record.get("roles") != expected_roles:
            raise PortableRestoreError(f"portable backup role binding drift: {name}")
    return manifest, payloads


def verify_portable_backup(
    path: str | Path,
    *,
    passphrase: str,
) -> PortableBackupReport:
    archive_path = Path(path).expanduser().resolve()
    header, plaintext, envelope_sha256 = _decrypt_envelope(archive_path, passphrase)
    manifest, _payloads = _verify_payload(header, plaintext)
    return PortableBackupReport(
        schema=ENVELOPE_SCHEMA,
        system_id=str(manifest["system_id"]),
        manager_id=str(manifest["manager_id"]),
        manifest_sha256=str(header["manifest_sha256"]),
        envelope_sha256=envelope_sha256,
        file_count=len(manifest["files"]),
        role_count=len(manifest["roles"]),
        encrypted=True,
        portable_off_host=True,
        live_apply_enabled=False,
        production_services_modified=False,
        network_operation=False,
    )


def restore_portable_backup(
    path: str | Path,
    target_root: str | Path,
    *,
    passphrase: str,
    expected_system_id: str | None = None,
    enable: bool = False,
    confirmation: str | None = None,
) -> PortableRestoreReport:
    if not enable:
        raise PortableRestoreError("portable restore is disabled")
    if confirmation != RESTORE_CONFIRMATION:
        raise PortableRestoreError("portable restore confirmation does not match")
    archive_path = Path(path).expanduser().resolve()
    header, plaintext, envelope_sha256 = _decrypt_envelope(archive_path, passphrase)
    manifest, payloads = _verify_payload(header, plaintext)
    system_id = str(manifest["system_id"])
    if expected_system_id is not None and system_id != expected_system_id:
        raise PortableRestoreError("portable restore expected system identity does not match")

    target = Path(target_root).expanduser().resolve()
    if target.exists() or target.is_symlink():
        raise PortableRestoreError("portable restore target must be absent")
    parent = target.parent
    _private_directory(parent)
    staging = parent / f".{target.name}.restore-{secrets.token_hex(8)}"
    staging.mkdir(mode=0o700)
    try:
        for relative in sorted(payloads):
            destination = staging.joinpath(*PurePosixPath(relative).parts)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if destination.parent.stat().st_mode & 0o077:
                raise PortableRestoreError("portable restore directory permissions are unsafe")
            _write_atomic(destination, payloads[relative])
        marker = {
            "schema": RESTORE_SCHEMA,
            "system_id": system_id,
            "manager_id": manifest["manager_id"],
            "manifest_sha256": header["manifest_sha256"],
            "envelope_sha256": envelope_sha256,
            "file_count": len(payloads),
            "activation_enabled": False,
            "production_services_modified": False,
            "network_operation": False,
            "identity_claim_required_before_activation": True,
        }
        _write_atomic(staging / RESTORE_MARKER, _canonical_json(marker) + b"\n")
        os.replace(staging, target)
        parent_descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except Exception:
        if staging.exists():
            for candidate in sorted(staging.rglob("*"), reverse=True):
                if candidate.is_file():
                    candidate.unlink(missing_ok=True)
                elif candidate.is_dir():
                    candidate.rmdir()
            staging.rmdir()
        raise

    return PortableRestoreReport(
        schema=RESTORE_SCHEMA,
        system_id=system_id,
        manager_id=str(manifest["manager_id"]),
        manifest_sha256=str(header["manifest_sha256"]),
        envelope_sha256=envelope_sha256,
        file_count=len(payloads),
        restored=True,
        activation_enabled=False,
        production_services_modified=False,
        network_operation=False,
    )
