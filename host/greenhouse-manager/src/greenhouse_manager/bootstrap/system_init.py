from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
except ImportError:  # pragma: no cover - exercised only in incomplete installations.
    x509 = None
    hashes = None
    serialization = None
    ec = None
    NameOID = None

INITIALIZATION_SCHEMA = "gh.h0h1.system-initialization/1"
IDENTITY_SCHEMA = "gh.h0h1.system-identity/1"
MANAGER_IDENTITY_SCHEMA = "gh.h0h1.manager-identity/1"
INITIALIZATION_CONFIRMATION = "INITIALIZE-NEW-GREENHOUSE-SYSTEM"
MARKER_NAME = "INITIALIZED.json"

SYSTEM_IDENTITY_NAME = "system-identity.json"
SYSTEM_ROOT_KEY_NAME = "system-root.key"
SYSTEM_CA_CERTIFICATE_NAME = "system-ca.pem"
SYSTEM_CA_PRIVATE_KEY_NAME = "system-ca-key.pem"
MANAGER_IDENTITY_NAME = "manager-identity.json"

EXPECTED_FILES = (
    SYSTEM_IDENTITY_NAME,
    SYSTEM_ROOT_KEY_NAME,
    SYSTEM_CA_CERTIFICATE_NAME,
    SYSTEM_CA_PRIVATE_KEY_NAME,
    MANAGER_IDENTITY_NAME,
)


class InitializationError(RuntimeError):
    pass


@dataclass(frozen=True)
class InitializationReport:
    schema: str
    system_id: str
    manager_id: str
    created: bool
    manifest_sha256: str
    system_ca_certificate_sha256: str
    system_root_key_sha256: str
    initialization_enabled: bool
    production_services_modified: bool
    network_operation: bool
    subprocess_operation: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute_path(
    value: str | Path,
    *,
    error_type: type[InitializationError] = InitializationError,
    label: str = "path",
) -> Path:
    path = Path(os.path.abspath(os.fspath(Path(value).expanduser())))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise error_type(f"{label} must not contain symbolic links")
    return path


def _private_directory(
    path: Path,
    *,
    error_type: type[InitializationError] = InitializationError,
    label: str = "initialization root",
) -> None:
    _absolute_path(path, error_type=error_type, label=label)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise error_type(f"{label} must be a directory")
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise error_type(f"{label} must not be accessible by group or other")


def _write_atomic(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        mode,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _generate_ca(
    system_id: str,
    *,
    now: datetime,
) -> tuple[bytes, bytes]:
    if x509 is None or hashes is None or serialization is None or ec is None or NameOID is None:
        raise InitializationError(
            "cryptography is required; install greenhouse-manager with the bootstrap extra"
        )
    private_key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Greenhouse System"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"Greenhouse System CA {system_id}"),
        ]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
    return private_pem, certificate_pem


def _marker_digest(marker: dict[str, Any]) -> str:
    value = dict(marker)
    value.pop("manifest_sha256", None)
    return _sha256_bytes(_canonical_json(value))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InitializationError(f"invalid initialization file: {path.name}") from error
    if not isinstance(value, dict):
        raise InitializationError(f"invalid initialization object: {path.name}")
    return value


def _verify_private_file(path: Path, expected: dict[str, Any]) -> None:
    if path.is_symlink() or not path.is_file():
        raise InitializationError(f"initialization member is not a regular file: {path.name}")
    stat = path.stat()
    mode = stat.st_mode & 0o777
    if mode != 0o600:
        raise InitializationError(f"initialization member mode drift: {path.name}")
    if stat.st_size != expected["size"]:
        raise InitializationError(f"initialization member size drift: {path.name}")
    if _sha256_file(path) != expected["sha256"]:
        raise InitializationError(f"initialization member digest drift: {path.name}")


def verify_initialization(root: str | Path) -> InitializationReport:
    directory = _absolute_path(root, label="initialization root")
    _private_directory(directory)
    marker_path = directory / MARKER_NAME
    if marker_path.is_symlink() or not marker_path.is_file():
        raise InitializationError("initialization marker is missing")
    if marker_path.stat().st_mode & 0o777 != 0o600:
        raise InitializationError("initialization marker mode drift")
    marker = _read_json(marker_path)
    if marker.get("schema") != INITIALIZATION_SCHEMA:
        raise InitializationError("initialization marker schema is unsupported")
    manifest_sha256 = marker.get("manifest_sha256")
    if not isinstance(manifest_sha256, str) or manifest_sha256 != _marker_digest(marker):
        raise InitializationError("initialization marker self-binding is invalid")
    files = marker.get("files")
    if not isinstance(files, dict) or set(files) != set(EXPECTED_FILES):
        raise InitializationError("initialization member inventory is invalid")
    for name in EXPECTED_FILES:
        expected = files[name]
        if not isinstance(expected, dict):
            raise InitializationError(f"initialization member metadata is invalid: {name}")
        _verify_private_file(directory / name, expected)

    identity = _read_json(directory / SYSTEM_IDENTITY_NAME)
    manager_identity = _read_json(directory / MANAGER_IDENTITY_NAME)
    if identity.get("schema") != IDENTITY_SCHEMA:
        raise InitializationError("system identity schema is unsupported")
    if manager_identity.get("schema") != MANAGER_IDENTITY_SCHEMA:
        raise InitializationError("manager identity schema is unsupported")
    if manager_identity.get("system_id") != identity.get("system_id"):
        raise InitializationError("manager identity system binding drift")
    if marker.get("system_id") != identity.get("system_id"):
        raise InitializationError("initialization marker system binding drift")
    if marker.get("manager_id") != manager_identity.get("manager_id"):
        raise InitializationError("initialization marker manager binding drift")

    return InitializationReport(
        schema=INITIALIZATION_SCHEMA,
        system_id=str(identity["system_id"]),
        manager_id=str(manager_identity["manager_id"]),
        created=False,
        manifest_sha256=manifest_sha256,
        system_ca_certificate_sha256=files[SYSTEM_CA_CERTIFICATE_NAME]["sha256"],
        system_root_key_sha256=files[SYSTEM_ROOT_KEY_NAME]["sha256"],
        initialization_enabled=False,
        production_services_modified=False,
        network_operation=False,
        subprocess_operation=False,
    )


def initialize_system(
    root: str | Path,
    *,
    enable: bool = False,
    confirmation: str | None = None,
    now: datetime | None = None,
) -> InitializationReport:
    directory = _absolute_path(root, label="initialization root")
    _private_directory(directory)
    marker_path = directory / MARKER_NAME
    if marker_path.exists():
        return verify_initialization(directory)

    existing = [name for name in EXPECTED_FILES if (directory / name).exists()]
    if existing:
        raise InitializationError("partial initialization state requires recovery")
    if not enable:
        raise InitializationError("initialization is disabled")
    if confirmation != INITIALIZATION_CONFIRMATION:
        raise InitializationError("initialization confirmation does not match")

    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    system_id = f"ghs-{secrets.token_hex(8)}"
    manager_id = f"ghm-{secrets.token_hex(8)}"
    root_key = secrets.token_bytes(32)
    ca_private_key, ca_certificate = _generate_ca(system_id, now=observed_at)

    identity = {
        "schema": IDENTITY_SCHEMA,
        "system_id": system_id,
        "created_at": observed_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "generation": 1,
    }
    manager_identity = {
        "schema": MANAGER_IDENTITY_SCHEMA,
        "system_id": system_id,
        "manager_id": manager_id,
        "created_at": observed_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "generation": 1,
    }
    payloads = {
        SYSTEM_IDENTITY_NAME: _canonical_json(identity) + b"\n",
        SYSTEM_ROOT_KEY_NAME: root_key,
        SYSTEM_CA_CERTIFICATE_NAME: ca_certificate,
        SYSTEM_CA_PRIVATE_KEY_NAME: ca_private_key,
        MANAGER_IDENTITY_NAME: _canonical_json(manager_identity) + b"\n",
    }

    created_paths: list[Path] = []
    try:
        for name in EXPECTED_FILES:
            path = directory / name
            _write_atomic(path, payloads[name])
            created_paths.append(path)

        files: dict[str, dict[str, Any]] = {}
        for name in EXPECTED_FILES:
            path = directory / name
            stat = path.stat()
            files[name] = {
                "sha256": _sha256_file(path),
                "size": stat.st_size,
                "mode": stat.st_mode & 0o777,
            }
        marker: dict[str, Any] = {
            "schema": INITIALIZATION_SCHEMA,
            "system_id": system_id,
            "manager_id": manager_id,
            "created_at": observed_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "generation": 1,
            "files": files,
            "marker_last": True,
            "production_services_modified": False,
            "network_operation": False,
            "subprocess_operation": False,
        }
        marker["manifest_sha256"] = _marker_digest(marker)
        _write_atomic(marker_path, _canonical_json(marker) + b"\n")
    except Exception:
        marker_path.unlink(missing_ok=True)
        for path in reversed(created_paths):
            path.unlink(missing_ok=True)
        raise

    report = verify_initialization(directory)
    return InitializationReport(
        schema=report.schema,
        system_id=report.system_id,
        manager_id=report.manager_id,
        created=True,
        manifest_sha256=report.manifest_sha256,
        system_ca_certificate_sha256=report.system_ca_certificate_sha256,
        system_root_key_sha256=report.system_root_key_sha256,
        initialization_enabled=True,
        production_services_modified=False,
        network_operation=False,
        subprocess_operation=False,
    )
