#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Sequence

SCHEMA = "gh.n3w-broker-certificate-lifecycle/1"
EXPECTED_ACTIVATION_UNIT = "n3wfc4-broker-activation.service"
SERVER_CERT_VALIDITY_DAYS = 825
SERVER_CERT_WARNING_DAYS = 90
SERVER_CERT_RENEW_DAYS = 60
SERVER_CERT_CRITICAL_DAYS = 30
CA_WARNING_DAYS = 730
CA_CRITICAL_DAYS = 365
CA_SIGNING_SAFETY_MARGIN_DAYS = 90
DEFAULT_PROBE_HOST = "127.0.0.1"
DEFAULT_PROBE_PORT = 8883
_COMMAND_TIMEOUT_SECONDS = 20
_DNS_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


class LifecycleError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class CertificateInfo:
    not_before: datetime
    not_after: datetime
    fingerprint: str
    serial: str
    subject: str
    issuer: str
    san_dns: tuple[str, ...]
    is_ca: bool
    server_auth: bool


@dataclass(frozen=True, slots=True)
class LifecycleConfig:
    server_cert: Path
    ca_cert: Path
    server_name: str
    status_file: Path
    allowed_roots: tuple[Path, ...]
    system_ca: Path | None = None
    server_key: Path | None = None
    ca_key: Path | None = None
    activation_unit: str = EXPECTED_ACTIVATION_UNIT
    probe_host: str = DEFAULT_PROBE_HOST
    probe_port: int = DEFAULT_PROBE_PORT
    server_validity_days: int = SERVER_CERT_VALIDITY_DAYS
    server_warning_days: int = SERVER_CERT_WARNING_DAYS
    server_renew_days: int = SERVER_CERT_RENEW_DAYS
    server_critical_days: int = SERVER_CERT_CRITICAL_DAYS
    ca_warning_days: int = CA_WARNING_DAYS
    ca_critical_days: int = CA_CRITICAL_DAYS
    ca_signing_safety_margin_days: int = CA_SIGNING_SAFETY_MARGIN_DAYS


def _run(argv: Sequence[str], *, timeout: int = _COMMAND_TIMEOUT_SECONDS) -> str:
    try:
        result = subprocess.run(
            list(argv),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LifecycleError("subprocess_unavailable") from error
    if result.returncode != 0:
        raise LifecycleError("subprocess_failed")
    return result.stdout


def _absolute_without_symlink(value: str | Path, *, must_exist: bool) -> Path:
    path = Path(os.path.abspath(os.fspath(Path(value).expanduser())))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise LifecycleError("path_contains_symlink")
        if not current.exists():
            if must_exist:
                raise LifecycleError("path_missing")
            break
    return path


def _normalize_roots(values: Sequence[str | Path]) -> tuple[Path, ...]:
    roots: list[Path] = []
    for value in values:
        root = _absolute_without_symlink(value, must_exist=True)
        if not root.is_dir():
            raise LifecycleError("allowed_root_not_directory")
        roots.append(root)
    if not roots:
        raise LifecycleError("allowed_root_missing")
    return tuple(roots)


def _under_allowed_root(path: Path, roots: Sequence[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _validated_file(
    value: str | Path,
    roots: Sequence[Path],
    *,
    private: bool = False,
) -> Path:
    path = _absolute_without_symlink(value, must_exist=True)
    if not _under_allowed_root(path, roots):
        raise LifecycleError("path_outside_allowed_root")
    if not path.is_file() or path.is_symlink():
        raise LifecycleError("file_not_regular")
    if private and path.stat().st_mode & 0o077:
        raise LifecycleError("private_key_permissions_unsafe")
    return path


def _validate_dns_name(value: str) -> str:
    name = value.strip().rstrip(".")
    if not name or len(name) > 253 or "/" in name or "\x00" in name:
        raise LifecycleError("server_name_invalid")
    labels = name.rstrip(".").split(".")
    if any(not _DNS_LABEL.fullmatch(label) for label in labels):
        raise LifecycleError("server_name_invalid")
    try:
        socket.inet_pton(socket.AF_INET, name)
    except OSError:
        pass
    else:
        raise LifecycleError("server_name_ip_literal_forbidden")
    try:
        socket.inet_pton(socket.AF_INET6, name)
    except OSError:
        pass
    else:
        raise LifecycleError("server_name_ip_literal_forbidden")
    return name


def _parse_openssl_time(value: str) -> datetime:
    normalized = " ".join(value.strip().split())
    try:
        parsed = datetime.strptime(normalized, "%b %d %H:%M:%S %Y %Z")
    except ValueError as error:
        raise LifecycleError("certificate_time_invalid") from error
    return parsed.replace(tzinfo=UTC)


def _field(output: str, prefix: str) -> str:
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise LifecycleError("certificate_field_missing")


def _certificate_info(path: Path) -> CertificateInfo:
    summary = _run(
        (
            "openssl",
            "x509",
            "-in",
            str(path),
            "-noout",
            "-startdate",
            "-enddate",
            "-fingerprint",
            "-sha256",
            "-serial",
            "-subject",
            "-issuer",
        )
    )
    san = _run(
        (
            "openssl",
            "x509",
            "-in",
            str(path),
            "-noout",
            "-ext",
            "subjectAltName",
        )
    )
    basic = _run(
        (
            "openssl",
            "x509",
            "-in",
            str(path),
            "-noout",
            "-ext",
            "basicConstraints",
        )
    )
    try:
        eku = _run(
            (
                "openssl",
                "x509",
                "-in",
                str(path),
                "-noout",
                "-ext",
                "extendedKeyUsage",
            )
        )
    except LifecycleError:
        eku = ""
    fingerprint = _field(summary, "sha256 Fingerprint=").replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise LifecycleError("certificate_fingerprint_invalid")
    san_dns = tuple(
        match.group(1).rstrip(".")
        for match in re.finditer(r"DNS:([^,\s]+)", san)
    )
    return CertificateInfo(
        not_before=_parse_openssl_time(_field(summary, "notBefore=")),
        not_after=_parse_openssl_time(_field(summary, "notAfter=")),
        fingerprint=fingerprint,
        serial=_field(summary, "serial="),
        subject=_field(summary, "subject="),
        issuer=_field(summary, "issuer="),
        san_dns=san_dns,
        is_ca="CA:TRUE" in basic,
        server_auth=(
            "TLS Web Server Authentication" in eku
            or "serverAuth" in eku
        ),
    )


def _verify_certificate(
    certificate: Path,
    ca_certificate: Path,
    server_name: str,
    *,
    no_check_time: bool,
) -> None:
    argv = [
        "openssl",
        "verify",
        "-CAfile",
        str(ca_certificate),
        "-verify_hostname",
        server_name,
    ]
    if no_check_time:
        argv.append("-no_check_time")
    argv.append(str(certificate))
    _run(argv)


def _certificate_public_key(path: Path) -> bytes:
    return _run(
        (
            "openssl",
            "x509",
            "-in",
            str(path),
            "-noout",
            "-pubkey",
        )
    ).encode("ascii")


def _private_public_key(path: Path) -> bytes:
    return _run(
        (
            "openssl",
            "pkey",
            "-in",
            str(path),
            "-pubout",
        )
    ).encode("ascii")


def _keys_match(certificate: Path, private_key: Path) -> bool:
    return secrets.compare_digest(
        _certificate_public_key(certificate),
        _private_public_key(private_key),
    )


def _remaining_seconds(info: CertificateInfo, now: datetime) -> int:
    return int((info.not_after - now).total_seconds())


def _server_state(info: CertificateInfo, now: datetime, config: LifecycleConfig) -> str:
    remaining = _remaining_seconds(info, now)
    if remaining <= 0:
        return "EXPIRED"
    if remaining <= config.server_critical_days * 86400:
        return "CRITICAL"
    if remaining <= config.server_renew_days * 86400:
        return "RENEW_DUE"
    if remaining <= config.server_warning_days * 86400:
        return "WARNING"
    return "HEALTHY"


def _ca_state(info: CertificateInfo, now: datetime, config: LifecycleConfig) -> str:
    remaining = _remaining_seconds(info, now)
    if remaining <= 0:
        return "EXPIRED"
    if remaining <= config.ca_critical_days * 86400:
        return "CRITICAL"
    if remaining <= config.ca_warning_days * 86400:
        return "WARNING"
    return "HEALTHY"


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _inspect(
    config: LifecycleConfig,
    *,
    now: datetime,
) -> tuple[CertificateInfo, CertificateInfo, CertificateInfo | None]:
    server_cert = _validated_file(config.server_cert, config.allowed_roots)
    ca_cert = _validated_file(config.ca_cert, config.allowed_roots)
    server = _certificate_info(server_cert)
    ca = _certificate_info(ca_cert)
    if server.is_ca:
        raise LifecycleError("server_certificate_is_ca")
    if not ca.is_ca:
        raise LifecycleError("signing_certificate_not_ca")
    if config.server_name.rstrip(".") not in server.san_dns:
        raise LifecycleError("server_certificate_san_mismatch")
    _verify_certificate(
        server_cert,
        ca_cert,
        config.server_name,
        no_check_time=True,
    )
    if server.not_after > now:
        _verify_certificate(
            server_cert,
            ca_cert,
            config.server_name,
            no_check_time=False,
        )
    system_ca = None
    if config.system_ca is not None:
        system_path = _validated_file(config.system_ca, config.allowed_roots)
        system_ca = _certificate_info(system_path)
        if not system_ca.is_ca:
            raise LifecycleError("system_certificate_not_ca")
    return server, ca, system_ca


def _base_status(
    config: LifecycleConfig,
    *,
    now: datetime,
    server: CertificateInfo,
    ca: CertificateInfo,
    system_ca: CertificateInfo | None,
) -> dict[str, object]:
    document: dict[str, object] = {
        "schema": SCHEMA,
        "checked_at": _iso(now),
        "server_not_after": _iso(server.not_after),
        "server_remaining_seconds": _remaining_seconds(server, now),
        "server_state": _server_state(server, now, config),
        "server_sha256_fingerprint": server.fingerprint,
        "ca_not_after": _iso(ca.not_after),
        "ca_remaining_seconds": _remaining_seconds(ca, now),
        "ca_state": _ca_state(ca, now, config),
        "ca_sha256_fingerprint": ca.fingerprint,
        "system_ca_not_after": None,
        "system_ca_remaining_seconds": None,
        "system_ca_state": None,
        "system_ca_sha256_fingerprint": None,
        "action": "audit",
        "result": "ok",
        "renewal_attempted": False,
        "rollback_attempted": False,
    }
    if system_ca is not None:
        document.update(
            {
                "system_ca_not_after": _iso(system_ca.not_after),
                "system_ca_remaining_seconds": _remaining_seconds(system_ca, now),
                "system_ca_state": _ca_state(system_ca, now, config),
                "system_ca_sha256_fingerprint": system_ca.fingerprint,
            }
        )
    return document


def _status_parent(path: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    parent = absolute.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    parent = _absolute_without_symlink(parent, must_exist=True)
    if parent.stat().st_mode & 0o077:
        raise LifecycleError("status_directory_permissions_unsafe")
    if absolute.exists() and absolute.is_symlink():
        raise LifecycleError("status_path_symlink_forbidden")
    return parent


def _atomic_write_status(path: Path, document: dict[str, object]) -> None:
    parent = _status_parent(path)
    absolute = parent / Path(path).name
    payload = (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")
    temporary = parent / f".{absolute.name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, absolute)
        directory = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _write_failure_status(
    path: Path,
    *,
    now: datetime,
    code: str,
) -> None:
    document: dict[str, object] = {
        "schema": SCHEMA,
        "checked_at": _iso(now),
        "server_not_after": None,
        "server_remaining_seconds": None,
        "server_state": "INVALID",
        "server_sha256_fingerprint": None,
        "ca_not_after": None,
        "ca_remaining_seconds": None,
        "ca_state": "INVALID",
        "ca_sha256_fingerprint": None,
        "system_ca_not_after": None,
        "system_ca_remaining_seconds": None,
        "system_ca_state": None,
        "system_ca_sha256_fingerprint": None,
        "action": "none",
        "result": code,
        "renewal_attempted": False,
        "rollback_attempted": False,
    }
    _atomic_write_status(path, document)


def _unit_is_active(unit: str) -> bool:
    if unit != EXPECTED_ACTIVATION_UNIT:
        raise LifecycleError("activation_unit_invalid")
    try:
        result = subprocess.run(
            ("systemctl", "is-active", "--quiet", unit),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            timeout=_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LifecycleError("systemctl_unavailable") from error
    return result.returncode == 0


def _restart_activation(unit: str) -> None:
    if unit != EXPECTED_ACTIVATION_UNIT:
        raise LifecycleError("activation_unit_invalid")
    _run(("systemctl", "restart", unit), timeout=120)
    if not _unit_is_active(unit):
        raise LifecycleError("activation_unit_not_active")


def _probe_unverified(
    host: str,
    port: int,
    server_name: str,
    *,
    timeout: float = 10.0,
) -> str:
    context = ssl._create_unverified_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=server_name) as wrapped:
                der = wrapped.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as error:
        raise LifecycleError("tls_probe_failed") from error
    if not der:
        raise LifecycleError("tls_peer_certificate_missing")
    return hashlib.sha256(der).hexdigest()


def _probe_verified(
    host: str,
    port: int,
    server_name: str,
    ca_certificate: Path,
    *,
    timeout: float = 10.0,
) -> str:
    try:
        context = ssl.create_default_context(cafile=str(ca_certificate))
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=server_name) as wrapped:
                der = wrapped.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as error:
        raise LifecycleError("tls_verified_probe_failed") from error
    if not der:
        raise LifecycleError("tls_peer_certificate_missing")
    return hashlib.sha256(der).hexdigest()


def _require_prechange_endpoint(
    config: LifecycleConfig,
    server: CertificateInfo,
    *,
    now: datetime,
) -> None:
    if not _unit_is_active(config.activation_unit):
        raise LifecycleError("activation_unit_not_active")
    observed = _probe_unverified(
        config.probe_host,
        config.probe_port,
        config.server_name,
    )
    if observed != server.fingerprint:
        raise LifecycleError("running_certificate_fingerprint_mismatch")
    if server.not_after > now:
        verified = _probe_verified(
            config.probe_host,
            config.probe_port,
            config.server_name,
            config.ca_cert,
        )
        if verified != server.fingerprint:
            raise LifecycleError("running_verified_certificate_mismatch")


def _write_private_text(path: Path, value: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _generate_candidate(
    config: LifecycleConfig,
    workspace: Path,
) -> Path:
    if config.server_key is None or config.ca_key is None:
        raise LifecycleError("renewal_private_key_missing")
    request = workspace / "server.csr"
    request_config = workspace / "request.cnf"
    extension_config = workspace / "extensions.cnf"
    candidate = workspace / "server.pem"
    _write_private_text(
        request_config,
        "\n".join(
            (
                "[req]",
                "prompt=no",
                "distinguished_name=dn",
                "req_extensions=req_ext",
                "[dn]",
                "O=Greenhouse FC4",
                f"CN={config.server_name}",
                "[req_ext]",
                "subjectAltName=@alt_names",
                "[alt_names]",
                f"DNS.1={config.server_name}",
                "",
            )
        ),
    )
    _write_private_text(
        extension_config,
        "\n".join(
            (
                "[server_ext]",
                "basicConstraints=critical,CA:FALSE",
                "extendedKeyUsage=serverAuth",
                f"subjectAltName=DNS:{config.server_name}",
                "subjectKeyIdentifier=hash",
                "authorityKeyIdentifier=keyid,issuer",
                "",
            )
        ),
    )
    _run(
        (
            "openssl",
            "req",
            "-new",
            "-key",
            str(config.server_key),
            "-config",
            str(request_config),
            "-out",
            str(request),
        )
    )
    serial = secrets.randbits(159) | 1
    _run(
        (
            "openssl",
            "x509",
            "-req",
            "-in",
            str(request),
            "-CA",
            str(config.ca_cert),
            "-CAkey",
            str(config.ca_key),
            "-set_serial",
            f"0x{serial:x}",
            "-days",
            str(config.server_validity_days),
            "-sha256",
            "-extfile",
            str(extension_config),
            "-extensions",
            "server_ext",
            "-out",
            str(candidate),
        )
    )
    os.chmod(candidate, 0o600)
    return candidate


def _validate_candidate(
    config: LifecycleConfig,
    candidate: Path,
    *,
    now: datetime,
) -> CertificateInfo:
    if config.server_key is None:
        raise LifecycleError("server_private_key_missing")
    info = _certificate_info(candidate)
    if info.is_ca:
        raise LifecycleError("candidate_is_ca")
    if config.server_name.rstrip(".") not in info.san_dns:
        raise LifecycleError("candidate_san_mismatch")
    if not info.server_auth:
        raise LifecycleError("candidate_server_auth_missing")
    _verify_certificate(
        candidate,
        config.ca_cert,
        config.server_name,
        no_check_time=False,
    )
    if not _keys_match(candidate, config.server_key):
        raise LifecycleError("candidate_server_key_mismatch")
    if info.not_before > now + timedelta(minutes=10):
        raise LifecycleError("candidate_not_yet_valid")
    maximum = timedelta(days=config.server_validity_days, minutes=10)
    if info.not_after - info.not_before > maximum:
        raise LifecycleError("candidate_validity_exceeds_policy")
    return info


def _prepare_workspace(server_cert: Path) -> Path:
    workspace = Path(
        tempfile.mkdtemp(
            prefix=".n3w-certificate-lifecycle.",
            dir=server_cert.parent,
        )
    )
    os.chmod(workspace, 0o700)
    return workspace


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _prepare_candidate_for_replace(
    candidate: Path,
    original_stat: os.stat_result,
) -> None:
    mode = stat.S_IMODE(original_stat.st_mode)
    os.chmod(candidate, mode)
    candidate_stat = candidate.stat()
    if (
        candidate_stat.st_uid != original_stat.st_uid
        or candidate_stat.st_gid != original_stat.st_gid
    ):
        os.chown(candidate, original_stat.st_uid, original_stat.st_gid)
    with candidate.open("rb") as stream:
        os.fsync(stream.fileno())


def _restore_bytes(
    active: Path,
    payload: bytes,
    original_stat: os.stat_result,
) -> None:
    temporary = active.parent / f".{active.name}.rollback.{secrets.token_hex(8)}"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        stat.S_IMODE(original_stat.st_mode),
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_stat = temporary.stat()
        if (
            temporary_stat.st_uid != original_stat.st_uid
            or temporary_stat.st_gid != original_stat.st_gid
        ):
            os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
        os.replace(temporary, active)
        _fsync_directory(active.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _cleanup_workspace(workspace: Path) -> None:
    shutil.rmtree(workspace, ignore_errors=True)


def _renewal_required(state: str) -> bool:
    return state in {"RENEW_DUE", "CRITICAL", "EXPIRED"}


def audit(
    config: LifecycleConfig,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, object], int]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    server, ca, system_ca = _inspect(config, now=current)
    status_doc = _base_status(
        config,
        now=current,
        server=server,
        ca=ca,
        system_ca=system_ca,
    )
    if any(
        status_doc.get(key) in {"WARNING", "CRITICAL", "EXPIRED"}
        for key in ("server_state", "ca_state", "system_ca_state")
    ):
        status_doc["result"] = "monitoring_warning"
    return status_doc, 0


def auto_renew(
    config: LifecycleConfig,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, object], int]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    server, ca, system_ca = _inspect(config, now=current)
    status_doc = _base_status(
        config,
        now=current,
        server=server,
        ca=ca,
        system_ca=system_ca,
    )
    server_state = str(status_doc["server_state"])
    if not _renewal_required(server_state):
        if any(
            status_doc.get(key) in {"WARNING", "CRITICAL", "EXPIRED"}
            for key in ("server_state", "ca_state", "system_ca_state")
        ):
            status_doc["result"] = "monitoring_warning"
        return status_doc, 0

    status_doc["action"] = "renew_server_certificate"
    minimum_ca_seconds = (
        config.server_validity_days + config.ca_signing_safety_margin_days
    ) * 86400
    if _remaining_seconds(ca, current) < minimum_ca_seconds:
        status_doc["ca_state"] = "CA_ROLLOVER_REQUIRED"
        status_doc["result"] = "ca_rollover_required"
        return status_doc, 2

    if config.server_key is None or config.ca_key is None:
        status_doc["result"] = "renewal_private_key_missing"
        return status_doc, 2

    server_key = _validated_file(
        config.server_key,
        config.allowed_roots,
        private=True,
    )
    ca_key = _validated_file(
        config.ca_key,
        config.allowed_roots,
        private=True,
    )
    if not _keys_match(config.server_cert, server_key):
        raise LifecycleError("server_private_key_mismatch")
    if not _keys_match(config.ca_cert, ca_key):
        raise LifecycleError("ca_private_key_mismatch")
    _require_prechange_endpoint(config, server, now=current)

    status_doc["renewal_attempted"] = True
    original_bytes = config.server_cert.read_bytes()
    original_stat = config.server_cert.stat()
    workspace = _prepare_workspace(config.server_cert)
    replaced = False
    try:
        candidate = _generate_candidate(config, workspace)
        candidate_info = _validate_candidate(
            config,
            candidate,
            now=current,
        )
        rollback_copy = workspace / "server.previous.pem"
        descriptor = os.open(
            rollback_copy,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(original_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        _prepare_candidate_for_replace(
            candidate,
            original_stat,
        )
        os.replace(candidate, config.server_cert)
        replaced = True
        _fsync_directory(config.server_cert.parent)
        _restart_activation(config.activation_unit)
        observed = _probe_verified(
            config.probe_host,
            config.probe_port,
            config.server_name,
            config.ca_cert,
        )
        if observed != candidate_info.fingerprint:
            raise LifecycleError("postrenew_certificate_fingerprint_mismatch")
        active_info = _certificate_info(config.server_cert)
        if (
            active_info.fingerprint != candidate_info.fingerprint
            or active_info.not_after != candidate_info.not_after
        ):
            raise LifecycleError("postrenew_active_certificate_mismatch")
        status_doc.update(
            {
                "server_not_after": _iso(active_info.not_after),
                "server_remaining_seconds": _remaining_seconds(active_info, current),
                "server_state": _server_state(active_info, current, config),
                "server_sha256_fingerprint": active_info.fingerprint,
                "result": "renewed",
            }
        )
        _cleanup_workspace(workspace)
        return status_doc, 0
    except Exception as error:
        failure_code = (
            error.code
            if isinstance(error, LifecycleError)
            else "renewal_internal_failure"
        )
        if not replaced:
            _cleanup_workspace(workspace)
            status_doc["result"] = failure_code
            return status_doc, 2
        status_doc["rollback_attempted"] = True
        try:
            _restore_bytes(
                config.server_cert,
                original_bytes,
                original_stat,
            )
            _restart_activation(config.activation_unit)
            observed = _probe_unverified(
                config.probe_host,
                config.probe_port,
                config.server_name,
            )
            if observed != server.fingerprint:
                raise LifecycleError("rollback_certificate_fingerprint_mismatch")
            if server.not_after > current:
                verified = _probe_verified(
                    config.probe_host,
                    config.probe_port,
                    config.server_name,
                    config.ca_cert,
                )
                if verified != server.fingerprint:
                    raise LifecycleError("rollback_verified_certificate_mismatch")
                status_doc["result"] = "renewal_failed_rolled_back"
            else:
                status_doc["result"] = "renewal_failed_rolled_back_expired"
            _cleanup_workspace(workspace)
            return status_doc, 2
        except Exception:
            status_doc["result"] = "rollback_unproven"
            return status_doc, 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("audit", "auto-renew"))
    parser.add_argument("--server-cert", required=True)
    parser.add_argument("--server-key")
    parser.add_argument("--ca-cert", required=True)
    parser.add_argument("--ca-key")
    parser.add_argument("--system-ca")
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--status-file", required=True)
    parser.add_argument("--allowed-root", action="append", required=True)
    parser.add_argument(
        "--activation-unit",
        default=EXPECTED_ACTIVATION_UNIT,
    )
    parser.add_argument("--probe-host", default=DEFAULT_PROBE_HOST)
    parser.add_argument("--probe-port", type=int, default=DEFAULT_PROBE_PORT)
    return parser


def _config_from_args(args: argparse.Namespace) -> LifecycleConfig:
    roots = _normalize_roots(args.allowed_root)
    server_name = _validate_dns_name(args.server_name)
    if not 1 <= args.probe_port <= 65535:
        raise LifecycleError("probe_port_invalid")
    try:
        probe = socket.inet_pton(socket.AF_INET, args.probe_host)
    except OSError as error:
        raise LifecycleError("probe_host_must_be_ipv4_loopback") from error
    if not probe or not args.probe_host.startswith("127."):
        raise LifecycleError("probe_host_must_be_ipv4_loopback")
    if args.activation_unit != EXPECTED_ACTIVATION_UNIT:
        raise LifecycleError("activation_unit_invalid")
    return LifecycleConfig(
        server_cert=_validated_file(args.server_cert, roots),
        server_key=(
            Path(os.path.abspath(os.path.expanduser(args.server_key)))
            if args.server_key
            else None
        ),
        ca_cert=_validated_file(args.ca_cert, roots),
        ca_key=(
            Path(os.path.abspath(os.path.expanduser(args.ca_key)))
            if args.ca_key
            else None
        ),
        system_ca=(
            _validated_file(args.system_ca, roots)
            if args.system_ca
            else None
        ),
        server_name=server_name,
        status_file=Path(os.path.abspath(os.path.expanduser(args.status_file))),
        allowed_roots=roots,
        activation_unit=args.activation_unit,
        probe_host=args.probe_host,
        probe_port=args.probe_port,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    now = datetime.now(UTC)
    status_path = Path(os.path.abspath(os.path.expanduser(args.status_file)))
    try:
        config = _config_from_args(args)
        parent = _status_parent(config.status_file)
        lock_path = parent / ".certificate-lifecycle.lock"
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "r+") as lock_stream:
            try:
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise LifecycleError("lifecycle_lock_busy")
            if args.mode == "audit":
                document, code = audit(config, now=now)
            else:
                document, code = auto_renew(config, now=now)
            _atomic_write_status(config.status_file, document)
            print(json.dumps(document, sort_keys=True, separators=(",", ":")))
            return code
    except LifecycleError as error:
        try:
            _write_failure_status(status_path, now=now, code=error.code)
        except Exception:
            pass
        document = {
            "schema": SCHEMA,
            "checked_at": _iso(now),
            "result": error.code,
            "server_state": "INVALID",
            "ca_state": "INVALID",
            "renewal_attempted": False,
            "rollback_attempted": False,
        }
        print(json.dumps(document, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
