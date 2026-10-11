from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import secrets
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from greenhouse_manager.ops.t1_clean_service_credential_bundle import (
    create_clean_service_credential_bundle,
    verify_clean_service_credential_bundle,
)
from greenhouse_manager.runtime.dynsec_api import DynsecProvisioner, DynsecTransport
from greenhouse_manager.runtime.service_identity_plan import (
    ServiceCredentials,
    ServiceIdentityPlan,
    build_service_identity_plan,
)

SCHEMA = "gh.n3w.t1-fresh-broker-bootstrap/1"
DEFAULT_SERVER_NAME = "mqtt.greenhouse.local"
DEFAULT_COMPATIBILITY_DNS = ("armbian",)
CA_VALIDITY_DAYS = 3650
SERVER_VALIDITY_DAYS = 825
ADMIN_USERNAME = "admin"
SERVICE_NAMES = ("provisioning", "manager", "homeassistant")


class FreshBrokerBootstrapError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FreshBrokerBootstrapReport:
    schema: str
    system_id: str
    server_name: str
    san_dns: tuple[str, ...]
    san_ip: tuple[str, ...]
    ca_sha256: str
    server_sha256: str
    service_count: int
    node_credential_count: int
    dynsec_admin_secret_created: bool
    broker_transport_ca_separate_from_system_ca: bool
    secret_values_included: bool
    production_service_start: bool
    network_operation: bool
    board_access: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _private_directory(path: Path) -> None:
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    if path.is_symlink() or path.stat().st_mode & 0o777 != 0o700:
        raise FreshBrokerBootstrapError("private_directory_invalid")


def _write_private(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(path, 0o600)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _certificate_fingerprint(certificate: x509.Certificate) -> str:
    return certificate.fingerprint(hashes.SHA256()).hex()


def _generate_tls(
    *,
    system_id: str,
    server_name: str,
    compatibility_dns: tuple[str, ...],
    now: datetime,
) -> tuple[bytes, bytes, bytes, bytes, tuple[str, ...], tuple[str, ...]]:
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Greenhouse N3-W"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"Greenhouse Broker CA {system_id}"),
        ]
    )
    ca_certificate = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=CA_VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
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
        .sign(ca_key, hashes.SHA256())
    )

    server_key = ec.generate_private_key(ec.SECP256R1())
    server_subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Greenhouse N3-W"),
            x509.NameAttribute(NameOID.COMMON_NAME, server_name),
        ]
    )
    dns_names = tuple(dict.fromkeys((server_name, *compatibility_dns)))
    ip_names = ("127.0.0.1",)
    san = x509.SubjectAlternativeName(
        [
            *(x509.DNSName(name) for name in dns_names),
            *(x509.IPAddress(ipaddress.ip_address(value)) for value in ip_names),
        ]
    )
    server_certificate = (
        x509.CertificateBuilder()
        .subject_name(server_subject)
        .issuer_name(ca_certificate.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=SERVER_VALIDITY_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=True,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .add_extension(san, critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    return (
        ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        ca_certificate.public_bytes(serialization.Encoding.PEM),
        server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        server_certificate.public_bytes(serialization.Encoding.PEM),
        dns_names,
        ip_names,
    )


def _load_certificate(path: Path) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(path.read_bytes())
    except (OSError, ValueError) as error:
        raise FreshBrokerBootstrapError("certificate_invalid") from error


def _load_private_key(path: Path):
    try:
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as error:
        raise FreshBrokerBootstrapError("private_key_invalid") from error


def _verify_tls(root: Path, *, server_name: str) -> dict[str, Any]:
    tls = root / "tls"
    for name in ("ca.key", "ca.pem", "server.key", "server.pem"):
        path = tls / name
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_mode & 0o777 != 0o600
        ):
            raise FreshBrokerBootstrapError("tls_inventory_invalid")

    ca = _load_certificate(tls / "ca.pem")
    server = _load_certificate(tls / "server.pem")
    ca_key = _load_private_key(tls / "ca.key")
    server_key = _load_private_key(tls / "server.key")

    if ca.subject != ca.issuer:
        raise FreshBrokerBootstrapError("ca_not_self_issued")
    if ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is not True:
        raise FreshBrokerBootstrapError("ca_constraints_invalid")
    if server.issuer != ca.subject:
        raise FreshBrokerBootstrapError("server_issuer_invalid")
    if server.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is not False:
        raise FreshBrokerBootstrapError("server_constraints_invalid")

    ca.public_key().verify(
        server.signature,
        server.tbs_certificate_bytes,
        ec.ECDSA(server.signature_hash_algorithm),
    )

    ca_public = ca.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    ca_key_public = ca_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    server_public = server.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    server_key_public = server_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if not secrets.compare_digest(ca_public, ca_key_public):
        raise FreshBrokerBootstrapError("ca_key_mismatch")
    if not secrets.compare_digest(server_public, server_key_public):
        raise FreshBrokerBootstrapError("server_key_mismatch")

    san = server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    dns_names = tuple(san.get_values_for_type(x509.DNSName))
    ip_names = tuple(str(value) for value in san.get_values_for_type(x509.IPAddress))
    if server_name not in dns_names or "127.0.0.1" not in ip_names:
        raise FreshBrokerBootstrapError("server_san_invalid")
    eku = server.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    if ExtendedKeyUsageOID.SERVER_AUTH not in eku:
        raise FreshBrokerBootstrapError("server_auth_missing")

    return {
        "ca_sha256": _certificate_fingerprint(ca),
        "server_sha256": _certificate_fingerprint(server),
        "san_dns": dns_names,
        "san_ip": ip_names,
    }


def create_fresh_broker_materials(
    destination: str | Path,
    *,
    system_id: str,
    server_name: str = DEFAULT_SERVER_NAME,
    compatibility_dns: tuple[str, ...] = DEFAULT_COMPATIBILITY_DNS,
    now: datetime | None = None,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> FreshBrokerBootstrapReport:
    requested = Path(destination).expanduser()
    if requested.exists() or requested.is_symlink():
        raise FreshBrokerBootstrapError("destination_already_exists")
    if not requested.parent.is_dir() or _contains_symlink(requested.parent):
        raise FreshBrokerBootstrapError("destination_parent_invalid")

    observed = (now or datetime.now(UTC)).astimezone(UTC)
    root = requested.parent.resolve() / requested.name
    created = False
    try:
        _private_directory(root)
        created = True
        _private_directory(root / "tls")
        _private_directory(root / "private")

        ca_key, ca_cert, server_key, server_cert, dns_names, ip_names = _generate_tls(
            system_id=system_id,
            server_name=server_name,
            compatibility_dns=compatibility_dns,
            now=observed,
        )
        for name, payload in (
            ("ca.key", ca_key),
            ("ca.pem", ca_cert),
            ("server.key", server_key),
            ("server.pem", server_cert),
        ):
            _write_private(root / "tls" / name, payload)

        admin_password = base64.urlsafe_b64encode(random_bytes(32)).rstrip(b"=")
        _write_private(root / "private" / "dynsec-admin-password", admin_password + b"\n")

        create_clean_service_credential_bundle(
            root / "service-credentials",
            system_id=system_id,
            generation=1,
            random_bytes=random_bytes,
        )

        tls_report = _verify_tls(root, server_name=server_name)
        manifest = {
            "schema": SCHEMA,
            "system_id": system_id,
            "server_name": server_name,
            "san_dns": list(dns_names),
            "san_ip": list(ip_names),
            "ca_sha256": tls_report["ca_sha256"],
            "server_sha256": tls_report["server_sha256"],
            "service_count": 3,
            "service_names": list(SERVICE_NAMES),
            "node_credential_count": 0,
            "node_precreation_forbidden": True,
            "dynsec_admin_username": ADMIN_USERNAME,
            "dynsec_admin_password_path": "private/dynsec-admin-password",
            "dynsec_admin_runtime_use_forbidden": True,
            "broker_transport_ca_separate_from_system_ca": True,
            "secret_values_included": False,
            "production_service_start": False,
            "network_operation": False,
            "board_access": False,
        }
        _write_private(root / "manifest.json", _canonical_json(manifest) + b"\n")
        return verify_fresh_broker_materials(root)
    except Exception:
        if created:
            shutil.rmtree(root, ignore_errors=True)
        raise


def verify_fresh_broker_materials(
    directory: str | Path,
) -> FreshBrokerBootstrapReport:
    requested = Path(directory).expanduser()
    if _contains_symlink(requested):
        raise FreshBrokerBootstrapError("root_unsafe")
    root = requested.resolve()
    if not root.is_dir() or root.stat().st_mode & 0o777 != 0o700:
        raise FreshBrokerBootstrapError("root_unsafe")

    top_level = {path.name for path in root.iterdir()}
    if top_level != {"tls", "private", "service-credentials", "manifest.json"}:
        raise FreshBrokerBootstrapError("top_level_inventory_invalid")
    for name in ("tls", "private", "service-credentials"):
        child = root / name
        if child.is_symlink() or not child.is_dir() or child.stat().st_mode & 0o777 != 0o700:
            raise FreshBrokerBootstrapError("private_directory_invalid")

    admin = root / "private" / "dynsec-admin-password"
    if (
        not admin.is_file()
        or admin.is_symlink()
        or admin.stat().st_mode & 0o777 != 0o600
        or not admin.read_text(encoding="utf-8").strip()
    ):
        raise FreshBrokerBootstrapError("dynsec_admin_secret_invalid")

    service_manifest = verify_clean_service_credential_bundle(root / "service-credentials")
    manifest_path = root / "manifest.json"
    if (
        not manifest_path.is_file()
        or manifest_path.is_symlink()
        or manifest_path.stat().st_mode & 0o777 != 0o600
    ):
        raise FreshBrokerBootstrapError("manifest_invalid")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FreshBrokerBootstrapError("manifest_invalid") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != SCHEMA
        or manifest.get("service_count") != 3
        or manifest.get("service_names") != list(SERVICE_NAMES)
        or manifest.get("node_credential_count") != 0
        or manifest.get("node_precreation_forbidden") is not True
        or manifest.get("dynsec_admin_runtime_use_forbidden") is not True
        or manifest.get("broker_transport_ca_separate_from_system_ca") is not True
        or manifest.get("secret_values_included") is not False
        or manifest.get("production_service_start") is not False
        or manifest.get("network_operation") is not False
        or manifest.get("board_access") is not False
        or service_manifest.get("system_id") != manifest.get("system_id")
    ):
        raise FreshBrokerBootstrapError("manifest_contract_invalid")

    server_name = manifest.get("server_name")
    if not isinstance(server_name, str) or not server_name:
        raise FreshBrokerBootstrapError("server_name_invalid")
    tls_report = _verify_tls(root, server_name=server_name)
    if (
        manifest.get("ca_sha256") != tls_report["ca_sha256"]
        or manifest.get("server_sha256") != tls_report["server_sha256"]
        or manifest.get("san_dns") != list(tls_report["san_dns"])
        or manifest.get("san_ip") != list(tls_report["san_ip"])
    ):
        raise FreshBrokerBootstrapError("tls_manifest_binding_invalid")

    return FreshBrokerBootstrapReport(
        schema=SCHEMA,
        system_id=str(manifest["system_id"]),
        server_name=server_name,
        san_dns=tuple(tls_report["san_dns"]),
        san_ip=tuple(tls_report["san_ip"]),
        ca_sha256=str(tls_report["ca_sha256"]),
        server_sha256=str(tls_report["server_sha256"]),
        service_count=3,
        node_credential_count=0,
        dynsec_admin_secret_created=True,
        broker_transport_ca_separate_from_system_ca=True,
        secret_values_included=False,
        production_service_start=False,
        network_operation=False,
        board_access=False,
    )


def _service_materials(
    credential_root: Path,
    *,
    system_id: str,
) -> tuple[dict[str, ServiceIdentityPlan], dict[str, ServiceCredentials]]:
    manifest = verify_clean_service_credential_bundle(credential_root)
    if manifest.get("system_id") != system_id:
        raise FreshBrokerBootstrapError("service_system_id_mismatch")
    plans: dict[str, ServiceIdentityPlan] = {}
    credentials: dict[str, ServiceCredentials] = {}
    for service in SERVICE_NAMES:
        plan = build_service_identity_plan(
            system_id=system_id,
            service=service,  # type: ignore[arg-type]
            generation=1,
        )
        identity_path = credential_root / service / "identity.json"
        try:
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise FreshBrokerBootstrapError("service_identity_invalid") from error
        if (
            not isinstance(identity, dict)
            or identity.get("service") != service
            or identity.get("system_id") != system_id
            or identity.get("generation") != 1
            or identity.get("username") != plan.username
            or identity.get("client_id") != plan.client_id
            or identity.get("role_name") != plan.role_name
        ):
            raise FreshBrokerBootstrapError("service_identity_binding_invalid")
        password = (credential_root / service / "password").read_text(
            encoding="utf-8"
        ).rstrip("\r\n")
        if not password:
            raise FreshBrokerBootstrapError("service_password_missing")
        plans[service] = plan
        credentials[service] = ServiceCredentials(
            username=plan.username,
            client_id=plan.client_id,
            generation=plan.generation,
            password=password,
        )
    return plans, credentials


def provision_fresh_service_identities(
    transport: DynsecTransport,
    credential_root: str | Path,
    *,
    system_id: str,
) -> dict[str, object]:
    plans, credentials = _service_materials(
        Path(credential_root).expanduser().resolve(),
        system_id=system_id,
    )
    provisioner = DynsecProvisioner(transport)
    provisioner.apply_baseline(plans["manager"])
    for service in SERVICE_NAMES:
        provisioner.provision(plans[service], credentials[service])
    return {
        "schema": "gh.n3w.t1-fresh-dynsec-service-bootstrap/1",
        "system_id": system_id,
        "service_count": 3,
        "service_usernames": [plans[name].username for name in SERVICE_NAMES],
        "service_client_ids": [plans[name].client_id for name in SERVICE_NAMES],
        "service_roles": [plans[name].role_name for name in SERVICE_NAMES],
        "node_credential_count": 0,
        "default_acl_applied": True,
        "secret_values_included": False,
        "production_service_start": False,
        "board_access": False,
    }


def audit_fresh_dynsec_document(
    path: str | Path,
    *,
    system_id: str,
) -> dict[str, object]:
    source = Path(path).expanduser()
    if (
        not source.is_file()
        or source.is_symlink()
        or source.stat().st_mode & 0o777 != 0o600
    ):
        raise FreshBrokerBootstrapError("dynsec_document_unsafe")
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FreshBrokerBootstrapError("dynsec_document_invalid") from error
    if not isinstance(document, dict):
        raise FreshBrokerBootstrapError("dynsec_document_invalid")

    defaults = document.get("defaultACLAccess")
    expected_defaults = {
        "publishClientSend": False,
        "publishClientReceive": False,
        "subscribe": False,
        "unsubscribe": True,
    }
    if defaults != expected_defaults:
        raise FreshBrokerBootstrapError("dynsec_default_acl_invalid")

    clients = document.get("clients")
    roles = document.get("roles")
    if not isinstance(clients, list) or not isinstance(roles, list):
        raise FreshBrokerBootstrapError("dynsec_inventory_invalid")
    usernames = {
        item.get("username")
        for item in clients
        if isinstance(item, dict) and isinstance(item.get("username"), str)
    }
    role_names = {
        item.get("rolename")
        for item in roles
        if isinstance(item, dict) and isinstance(item.get("rolename"), str)
    }
    plans = {
        service: build_service_identity_plan(
            system_id=system_id,
            service=service,  # type: ignore[arg-type]
            generation=1,
        )
        for service in SERVICE_NAMES
    }
    required_users = {plan.username for plan in plans.values()}
    required_roles = {plan.role_name for plan in plans.values()}
    if ADMIN_USERNAME not in usernames or not required_users <= usernames:
        raise FreshBrokerBootstrapError("dynsec_service_clients_missing")
    if not required_roles <= role_names:
        raise FreshBrokerBootstrapError("dynsec_service_roles_missing")
    if any(
        username.startswith("ghn_")
        for username in usernames
        if isinstance(username, str)
    ):
        raise FreshBrokerBootstrapError("dynsec_node_client_precreated")
    if any(
        role.startswith(f"gh-node-{system_id}-")
        for role in role_names
        if isinstance(role, str)
    ):
        raise FreshBrokerBootstrapError("dynsec_node_role_precreated")

    return {
        "schema": "gh.n3w.t1-fresh-dynsec-audit/1",
        "status": "PASS",
        "default_acl_exact": True,
        "service_client_count": 3,
        "service_role_count": 3,
        "node_client_count": 0,
        "node_role_count": 0,
        "admin_runtime_use_forbidden": True,
        "secret_values_included": False,
    }
