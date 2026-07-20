from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

FROZEN_PAIRING_HTTP_PORT = 47110
FROZEN_PAIRING_UDP_PORT = 47111
ISOLATED_DEPLOYMENT_MODE = "isolated-lab"

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_DNS_LABEL_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
)
_LOCAL_IPV4_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def _require_absolute_file(name: str, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{name} must reference a regular non-symlink file")
    return path


def _read_ca_pem(path: Path) -> str:
    if path.stat().st_size > 64 * 1024:
        raise ValueError("GH_PAIRING_BROKER_CA_FILE exceeds 64 KiB")
    try:
        value = path.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise ValueError(
            "GH_PAIRING_BROKER_CA_FILE must contain UTF-8 PEM"
        ) from error
    if (
        "-----BEGIN CERTIFICATE-----" not in value
        or "-----END CERTIFICATE-----" not in value
        or "\x00" in value
    ):
        raise ValueError(
            "GH_PAIRING_BROKER_CA_FILE must contain a PEM certificate"
        )
    return value


def _is_local_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return (
        address.version == 4
        and not address.is_unspecified
        and any(address in network for network in _LOCAL_IPV4_NETWORKS)
    )


def _valid_local_hostname(value: str) -> bool:
    if not value or not value.isascii() or any(
        character.isspace() for character in value
    ):
        return False
    candidate = value[:-1] if value.endswith(".") else value
    labels = candidate.split(".")
    return (
        candidate.endswith(".local")
        and len(labels) >= 2
        and all(_DNS_LABEL_RE.fullmatch(label) for label in labels)
    )


@dataclass(frozen=True, slots=True)
class PairingRuntimeSettings:
    enabled: bool = False
    deployment_mode: str = "disabled"
    system_id: str = "dev"
    manager_id: str = "manager-disabled"
    bind_host: str = "127.0.0.1"
    http_port: int = FROZEN_PAIRING_HTTP_PORT
    udp_port: int = FROZEN_PAIRING_UDP_PORT
    advertised_host: str = "greenhouse-manager.local"
    advertised_ipv4: str = "127.0.0.1"
    mdns_instance_name: str = "greenhouse-manager"
    pairing_path: str = "/v1/pairing"
    priority: int = 100
    candidate_ttl_s: int = 30
    registration_db_path: str = (
        "/var/lib/greenhouse-manager/registration.sqlite3"
    )
    registration_pending_ttl_s: int = 120
    session_ttl_s: int = 120
    max_proof_attempts: int = 3
    broker_host: str = "mqtt.greenhouse.local"
    broker_port: int = 8883
    broker_tls_server_name: str = "mqtt.greenhouse.local"
    broker_ca_file: str | None = None
    expiry_poll_s: float = 1.0

    @classmethod
    def from_env(cls) -> PairingRuntimeSettings:
        enabled = _env_bool("GH_PAIRING_SERVICE_ENABLED", False)
        settings = cls(
            enabled=enabled,
            deployment_mode=os.getenv(
                "GH_PAIRING_DEPLOYMENT_MODE",
                "disabled",
            ),
            system_id=os.getenv("GH_SYSTEM_ID", "dev"),
            manager_id=os.getenv(
                "GH_PAIRING_MANAGER_ID",
                "manager-disabled",
            ),
            bind_host=os.getenv("GH_PAIRING_BIND_HOST", "127.0.0.1"),
            http_port=_env_int(
                "GH_PAIRING_HTTP_PORT",
                FROZEN_PAIRING_HTTP_PORT,
            ),
            udp_port=_env_int(
                "GH_PAIRING_UDP_PORT",
                FROZEN_PAIRING_UDP_PORT,
            ),
            advertised_host=os.getenv(
                "GH_PAIRING_ADVERTISED_HOST",
                "greenhouse-manager.local",
            ),
            advertised_ipv4=os.getenv(
                "GH_PAIRING_ADVERTISED_IPV4",
                "127.0.0.1",
            ),
            mdns_instance_name=os.getenv(
                "GH_PAIRING_MDNS_INSTANCE",
                "greenhouse-manager",
            ),
            pairing_path=os.getenv(
                "GH_PAIRING_PATH",
                "/v1/pairing",
            ),
            priority=_env_int("GH_PAIRING_PRIORITY", 100),
            candidate_ttl_s=_env_int("GH_PAIRING_CANDIDATE_TTL_S", 30),
            registration_db_path=os.getenv(
                "GH_PAIRING_DB_PATH",
                "/var/lib/greenhouse-manager/registration.sqlite3",
            ),
            registration_pending_ttl_s=_env_int(
                "GH_PAIRING_PENDING_TTL_S",
                120,
            ),
            session_ttl_s=_env_int(
                "GH_PAIRING_SESSION_TTL_S",
                120,
            ),
            max_proof_attempts=_env_int(
                "GH_PAIRING_MAX_PROOF_ATTEMPTS",
                3,
            ),
            broker_host=os.getenv(
                "GH_PAIRING_BROKER_HOST",
                "mqtt.greenhouse.local",
            ),
            broker_port=_env_int("GH_PAIRING_BROKER_PORT", 8883),
            broker_tls_server_name=os.getenv(
                "GH_PAIRING_BROKER_TLS_SERVER_NAME",
                "mqtt.greenhouse.local",
            ),
            broker_ca_file=os.getenv(
                "GH_PAIRING_BROKER_CA_FILE"
            ) or None,
            expiry_poll_s=float(
                os.getenv("GH_PAIRING_EXPIRY_POLL_S", "1.0")
            ),
        )
        settings.validate(enforce_deployment_contract=True)
        return settings

    def validate(self, *, enforce_deployment_contract: bool) -> None:
        if not self.enabled:
            return
        if self.deployment_mode != ISOLATED_DEPLOYMENT_MODE:
            raise ValueError(
                "GH_PAIRING_DEPLOYMENT_MODE must be isolated-lab "
                "when the pairing service is enabled"
            )
        if not _ID_RE.fullmatch(self.system_id):
            raise ValueError(
                "GH_SYSTEM_ID must match [A-Za-z0-9_-]{3,64}"
            )
        if not _ID_RE.fullmatch(self.manager_id):
            raise ValueError(
                "GH_PAIRING_MANAGER_ID must match "
                "[A-Za-z0-9_-]{3,64}"
            )
        if self.bind_host not in {"127.0.0.1", "0.0.0.0"}:
            raise ValueError(
                "GH_PAIRING_BIND_HOST must be 127.0.0.1 or 0.0.0.0"
            )
        if enforce_deployment_contract and (
            self.http_port != FROZEN_PAIRING_HTTP_PORT
            or self.udp_port != FROZEN_PAIRING_UDP_PORT
        ):
            raise ValueError(
                "pairing service ports are frozen at "
                f"{FROZEN_PAIRING_HTTP_PORT}/tcp and "
                f"{FROZEN_PAIRING_UDP_PORT}/udp"
            )
        for name, port in (
            ("GH_PAIRING_HTTP_PORT", self.http_port),
            ("GH_PAIRING_UDP_PORT", self.udp_port),
            ("GH_PAIRING_BROKER_PORT", self.broker_port),
        ):
            if not 0 <= port <= 65535:
                raise ValueError(f"{name} must be between 0 and 65535")
            if name == "GH_PAIRING_BROKER_PORT" and port == 0:
                raise ValueError(
                    "GH_PAIRING_BROKER_PORT must be between 1 and 65535"
                )
        if not _valid_local_hostname(self.advertised_host):
            raise ValueError(
                "GH_PAIRING_ADVERTISED_HOST must be a .local hostname"
            )
        if not _is_local_ipv4(self.advertised_ipv4):
            raise ValueError(
                "GH_PAIRING_ADVERTISED_IPV4 must be a local IPv4 address"
            )
        if _DNS_LABEL_RE.fullmatch(self.mdns_instance_name) is None:
            raise ValueError(
                "GH_PAIRING_MDNS_INSTANCE must be a DNS label"
            )
        if self.pairing_path != "/v1/pairing":
            raise ValueError(
                "GH_PAIRING_PATH is frozen at /v1/pairing"
            )
        if not 0 <= self.priority <= 65535:
            raise ValueError(
                "GH_PAIRING_PRIORITY must be between 0 and 65535"
            )
        if not 1 <= self.candidate_ttl_s <= 3600:
            raise ValueError(
                "GH_PAIRING_CANDIDATE_TTL_S must be between 1 and 3600"
            )
        database = Path(self.registration_db_path).expanduser()
        if not database.is_absolute():
            raise ValueError("GH_PAIRING_DB_PATH must be an absolute path")
        if not 30 <= self.registration_pending_ttl_s <= 600:
            raise ValueError(
                "GH_PAIRING_PENDING_TTL_S must be between 30 and 600"
            )
        if not 30 <= self.session_ttl_s <= 600:
            raise ValueError(
                "GH_PAIRING_SESSION_TTL_S must be between 30 and 600"
            )
        if not 1 <= self.max_proof_attempts <= 5:
            raise ValueError(
                "GH_PAIRING_MAX_PROOF_ATTEMPTS must be between 1 and 5"
            )
        if (
            not self.broker_host
            or any(character.isspace() for character in self.broker_host)
        ):
            raise ValueError(
                "GH_PAIRING_BROKER_HOST must be a non-empty hostname"
            )
        if (
            not self.broker_tls_server_name
            or any(
                character.isspace()
                for character in self.broker_tls_server_name
            )
        ):
            raise ValueError(
                "GH_PAIRING_BROKER_TLS_SERVER_NAME must be non-empty"
            )
        if self.broker_ca_file is None:
            raise ValueError(
                "GH_PAIRING_BROKER_CA_FILE is required when enabled"
            )
        _read_ca_pem(
            _require_absolute_file(
                "GH_PAIRING_BROKER_CA_FILE",
                self.broker_ca_file,
            )
        )
        if not 0.1 <= self.expiry_poll_s <= 30:
            raise ValueError(
                "GH_PAIRING_EXPIRY_POLL_S must be between 0.1 and 30"
            )

    def read_broker_ca_pem(self) -> str:
        if self.broker_ca_file is None:
            raise ValueError("pairing Broker CA file is not configured")
        return _read_ca_pem(
            _require_absolute_file(
                "GH_PAIRING_BROKER_CA_FILE",
                self.broker_ca_file,
            )
        )

    def report(self) -> dict[str, object]:
        return {
            "schema": "gh.pair.runtime-config/1",
            "configuration_valid": True,
            "pairing_service_enabled": self.enabled,
            "deployment_mode": self.deployment_mode,
            "network_attempted": False,
            "listener_count": 2 if self.enabled else 0,
            "listeners": (
                [
                    {
                        "transport": "tcp",
                        "port": self.http_port,
                        "purpose": "pairing_http",
                    },
                    {
                        "transport": "udp",
                        "port": self.udp_port,
                        "purpose": "pairing_discovery",
                    },
                ]
                if self.enabled
                else []
            ),
            "mdns_enabled": self.enabled,
            "default_manager_runtime_modified": False,
            "secret_values_included": False,
            "ca_file_configured": bool(self.broker_ca_file),
        }

    def public_document(self) -> Mapping[str, object]:
        document = asdict(self)
        document.pop("broker_ca_file")
        return document
