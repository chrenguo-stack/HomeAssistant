from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_DISCOVERY_PREFIX_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HISTORY_DB_ROLE_PARTS = ("manager", "manager-state.sqlite3")


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


def _read_private_secret(name: str, raw_path: str) -> str:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{name} must reference a regular non-symlink file")
    if path.stat().st_mode & 0o077:
        raise ValueError(f"{name} must not be accessible by group or other")
    try:
        value = path.read_text(encoding="utf-8").rstrip("\r\n")
    except UnicodeError as error:
        raise ValueError(f"{name} must contain UTF-8 text") from error
    if not value or "\n" in value or "\r" in value or "\x00" in value:
        raise ValueError(f"{name} must contain exactly one non-empty secret")
    return value


def _mqtt_password_from_env() -> str | None:
    inline = os.getenv("GH_MQTT_PASSWORD") or None
    password_file = os.getenv("GH_MQTT_PASSWORD_FILE") or None
    if inline and password_file:
        raise ValueError(
            "GH_MQTT_PASSWORD and GH_MQTT_PASSWORD_FILE are mutually exclusive"
        )
    if password_file:
        return _read_private_secret("GH_MQTT_PASSWORD_FILE", password_file)
    return inline


def _n3w_provisioning_password_from_env() -> str | None:
    password_file = (
        os.getenv(
            "GH_N3W_PROVISIONING_PASSWORD_FILE"
        )
        or None
    )

    if password_file is None:
        return None

    return _read_private_secret(
        "GH_N3W_PROVISIONING_PASSWORD_FILE",
        password_file,
    )


def _path_contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


@dataclass(frozen=True, slots=True)
class Settings:
    system_id: str
    mqtt_host: str = "mosquitto"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_tls: bool = False
    mqtt_ca_file: str | None = None
    mqtt_client_id: str = "greenhouse-manager"
    stale_after_s: int = 180
    dedup_capacity: int = 4096
    log_level: str = "INFO"
    ha_discovery_enabled: bool = True
    ha_discovery_prefix: str = "homeassistant"
    ha_device_name_prefix: str = "温室监测节点"
    pairing_intake_enabled: bool = False
    pairing_db_path: str = "/var/lib/greenhouse-manager/registration.sqlite3"
    pairing_pending_ttl_s: int = 120
    history_replay_enabled: bool = False
    history_db_path: str = (
        "/var/lib/greenhouse-manager/manager/manager-state.sqlite3"
    )
    history_retention_days: int = 7
    history_max_future_skew_s: int = 300
    history_max_records_per_page: int = 256
    history_max_payload_bytes: int = 262_144
    history_max_records: int = 250_000
    history_max_db_bytes: int = 268_435_456
    history_queue_capacity: int = 64
    history_max_pages_per_minute: int = 60
    history_rate_state_capacity: int = 1_024
    history_rate_state_ttl_s: int = 3_600
    history_prune_interval_s: int = 300
    n3w_runtime_enabled: bool = False
    n3w_replay_db_path: str = "/var/lib/greenhouse-manager/n3w/replay.sqlite3"
    n3w_relay_authorization_db_path: str = (
        "/var/lib/greenhouse-manager/n3w/relay-authorization.sqlite3"
    )
    n3w_relay_key_dir: str = "/var/lib/greenhouse-manager/n3w/relay-keys"
    n3w_product_pairing_enabled: bool = False
    n3w_pairing_manager_id: str = "manager-disabled"
    n3w_pairing_bind_host: str = "0.0.0.0"
    n3w_pairing_advertised_host: str = "greenhouse-manager.local"
    n3w_pairing_http_port: int = 47112
    n3w_pairing_udp_port: int = 47111

    n3w_provisioning_username: str | None = None
    n3w_provisioning_password: str | None = None
    n3w_provisioning_client_id: str | None = None

    n3w_node_broker_host: str = "mqtt.greenhouse.local"
    n3w_node_broker_port: int = 8883
    n3w_node_broker_tls_server_name: str = "mqtt.greenhouse.local"
    n3w_node_broker_ca_file: str | None = None

    n3w_peer_trust_db_path: str = (
        "/var/lib/greenhouse-manager/n3w/system-peer-trust.sqlite3"
    )
    n3w_credential_lifecycle_db_path: str = (
        "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3"
    )
    n3w_pairing_socket_path: str = "/run/greenhouse-manager/pairing.sock"

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls(
            system_id=os.getenv("GH_SYSTEM_ID", "dev"),
            mqtt_host=os.getenv("GH_MQTT_HOST", "mosquitto"),
            mqtt_port=int(os.getenv("GH_MQTT_PORT", "1883")),
            mqtt_username=os.getenv("GH_MQTT_USERNAME") or None,
            mqtt_password=_mqtt_password_from_env(),
            mqtt_tls=_env_bool("GH_MQTT_TLS", False),
            mqtt_ca_file=os.getenv("GH_MQTT_CA_FILE") or None,
            mqtt_client_id=os.getenv("GH_MQTT_CLIENT_ID", "greenhouse-manager"),
            stale_after_s=int(os.getenv("GH_STALE_AFTER_S", "180")),
            dedup_capacity=int(os.getenv("GH_DEDUP_CAPACITY", "4096")),
            log_level=os.getenv("GH_LOG_LEVEL", "INFO").upper(),
            ha_discovery_enabled=_env_bool("GH_HA_DISCOVERY_ENABLED", True),
            ha_discovery_prefix=os.getenv("GH_HA_DISCOVERY_PREFIX", "homeassistant"),
            ha_device_name_prefix=os.getenv("GH_HA_DEVICE_NAME_PREFIX", "温室监测节点"),
            pairing_intake_enabled=_env_bool("GH_PAIRING_INTAKE_ENABLED", False),
            pairing_db_path=os.getenv(
                "GH_PAIRING_DB_PATH", "/var/lib/greenhouse-manager/registration.sqlite3"
            ),
            pairing_pending_ttl_s=int(os.getenv("GH_PAIRING_PENDING_TTL_S", "120")),
            history_replay_enabled=_env_bool("GH_HISTORY_REPLAY_ENABLED", False),
            history_db_path=os.getenv(
                "GH_HISTORY_DB_PATH",
                "/var/lib/greenhouse-manager/manager/manager-state.sqlite3",
            ),
            history_retention_days=int(os.getenv("GH_HISTORY_RETENTION_DAYS", "7")),
            history_max_future_skew_s=int(
                os.getenv("GH_HISTORY_MAX_FUTURE_SKEW_S", "300")
            ),
            history_max_records_per_page=int(
                os.getenv("GH_HISTORY_MAX_RECORDS_PER_PAGE", "256")
            ),
            history_max_payload_bytes=int(
                os.getenv("GH_HISTORY_MAX_PAYLOAD_BYTES", "262144")
            ),
            history_max_records=int(os.getenv("GH_HISTORY_MAX_RECORDS", "250000")),
            history_max_db_bytes=int(
                os.getenv("GH_HISTORY_MAX_DB_BYTES", "268435456")
            ),
            history_queue_capacity=int(
                os.getenv("GH_HISTORY_QUEUE_CAPACITY", "64")
            ),
            history_max_pages_per_minute=int(
                os.getenv("GH_HISTORY_MAX_PAGES_PER_MINUTE", "60")
            ),
            history_rate_state_capacity=int(
                os.getenv("GH_HISTORY_RATE_STATE_CAPACITY", "1024")
            ),
            history_rate_state_ttl_s=int(
                os.getenv("GH_HISTORY_RATE_STATE_TTL_S", "3600")
            ),
            history_prune_interval_s=int(
                os.getenv("GH_HISTORY_PRUNE_INTERVAL_S", "300")
            ),
            n3w_runtime_enabled=_env_bool("GH_N3W_RUNTIME_ENABLED", False),
            n3w_replay_db_path=os.getenv(
                "GH_N3W_REPLAY_DB_PATH",
                "/var/lib/greenhouse-manager/n3w/replay.sqlite3",
            ),
            n3w_relay_authorization_db_path=os.getenv(
                "GH_N3W_RELAY_AUTHORIZATION_DB_PATH",
                "/var/lib/greenhouse-manager/n3w/relay-authorization.sqlite3",
            ),
            n3w_relay_key_dir=os.getenv(
                "GH_N3W_RELAY_KEY_DIR",
                "/var/lib/greenhouse-manager/n3w/relay-keys",
            ),
            n3w_product_pairing_enabled=_env_bool(
                "GH_N3W_PRODUCT_PAIRING_ENABLED",
                False,
            ),
            n3w_pairing_manager_id=os.getenv(
                "GH_N3W_PAIRING_MANAGER_ID",
                "manager-disabled",
            ),
            n3w_pairing_bind_host=os.getenv(
                "GH_N3W_PAIRING_BIND_HOST",
                "0.0.0.0",
            ),
            n3w_pairing_advertised_host=os.getenv(
                "GH_N3W_PAIRING_ADVERTISED_HOST",
                "greenhouse-manager.local",
            ),
            n3w_pairing_http_port=int(
                os.getenv(
                    "GH_N3W_PAIRING_HTTP_PORT",
                    "47112",
                )
            ),
            n3w_pairing_udp_port=int(
                os.getenv(
                    "GH_N3W_PAIRING_UDP_PORT",
                    "47111",
                )
            ),
            n3w_provisioning_username=(
                os.getenv(
                    "GH_N3W_PROVISIONING_USERNAME"
                )
                or None
            ),
            n3w_provisioning_password=(
                _n3w_provisioning_password_from_env()
            ),
            n3w_provisioning_client_id=(
                os.getenv(
                    "GH_N3W_PROVISIONING_CLIENT_ID"
                )
                or None
            ),
            n3w_node_broker_host=os.getenv(
                "GH_N3W_NODE_BROKER_HOST",
                "mqtt.greenhouse.local",
            ),
            n3w_node_broker_port=int(
                os.getenv(
                    "GH_N3W_NODE_BROKER_PORT",
                    "8883",
                )
            ),
            n3w_node_broker_tls_server_name=os.getenv(
                "GH_N3W_NODE_BROKER_TLS_SERVER_NAME",
                "mqtt.greenhouse.local",
            ),
            n3w_node_broker_ca_file=(
                os.getenv(
                    "GH_N3W_NODE_BROKER_CA_FILE"
                )
                or None
            ),
            n3w_peer_trust_db_path=os.getenv(
                "GH_N3W_PEER_TRUST_DB_PATH",
                (
                    "/var/lib/greenhouse-manager/"
                    "n3w/system-peer-trust.sqlite3"
                ),
            ),
            n3w_credential_lifecycle_db_path=os.getenv(
                "GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH",
                (
                    "/var/lib/greenhouse-manager/"
                    "n3w/credential-lifecycle.sqlite3"
                ),
            ),
            n3w_pairing_socket_path=os.getenv(
                "GH_N3W_PAIRING_SOCKET_PATH",
                "/run/greenhouse-manager/pairing.sock",
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not _ID_RE.fullmatch(self.system_id):
            raise ValueError("GH_SYSTEM_ID must match [A-Za-z0-9_-]{3,64}")
        if not self.mqtt_host.strip():
            raise ValueError("GH_MQTT_HOST cannot be empty")
        if not 1 <= self.mqtt_port <= 65535:
            raise ValueError("GH_MQTT_PORT must be between 1 and 65535")
        if self.stale_after_s < 30:
            raise ValueError("GH_STALE_AFTER_S must be at least 30 seconds")
        if self.dedup_capacity < 128:
            raise ValueError("GH_DEDUP_CAPACITY must be at least 128")
        if bool(self.mqtt_username) != bool(self.mqtt_password):
            raise ValueError(
                "GH_MQTT_USERNAME and the configured MQTT password must be set together"
            )
        if self.mqtt_tls and not self.mqtt_ca_file:
            raise ValueError("GH_MQTT_CA_FILE is required when GH_MQTT_TLS=true")
        if not _DISCOVERY_PREFIX_RE.fullmatch(self.ha_discovery_prefix):
            raise ValueError("GH_HA_DISCOVERY_PREFIX must match [A-Za-z0-9_-]{1,64}")
        if not self.ha_device_name_prefix.strip():
            raise ValueError("GH_HA_DEVICE_NAME_PREFIX cannot be empty")
        if self.pairing_intake_enabled and not self.pairing_db_path.strip():
            raise ValueError(
                "GH_PAIRING_DB_PATH cannot be empty when pairing intake is enabled"
            )
        if not 30 <= self.pairing_pending_ttl_s <= 600:
            raise ValueError("GH_PAIRING_PENDING_TTL_S must be between 30 and 600 seconds")
        if self.history_replay_enabled:
            history_path = Path(self.history_db_path).expanduser()
            if not self.history_db_path.strip():
                raise ValueError(
                    "GH_HISTORY_DB_PATH cannot be empty when history replay is enabled"
                )
            if not history_path.is_absolute():
                raise ValueError(
                    "GH_HISTORY_DB_PATH must be absolute when history replay is enabled"
                )
            if history_path.parts[-2:] != _HISTORY_DB_ROLE_PARTS:
                raise ValueError(
                    "GH_HISTORY_DB_PATH must target the portable "
                    "manager/manager-state.sqlite3 role"
                )
            if _path_contains_symlink(history_path):
                raise ValueError(
                    "GH_HISTORY_DB_PATH and its ancestors must not be symlinks"
                )
        if not 1 <= self.history_retention_days <= 30:
            raise ValueError("GH_HISTORY_RETENTION_DAYS must be between 1 and 30")
        if not 0 <= self.history_max_future_skew_s <= 86_400:
            raise ValueError("GH_HISTORY_MAX_FUTURE_SKEW_S must be between 0 and 86400")
        if not 1 <= self.history_max_records_per_page <= 256:
            raise ValueError(
                "GH_HISTORY_MAX_RECORDS_PER_PAGE must be between 1 and 256"
            )
        if not 4_096 <= self.history_max_payload_bytes <= 1_048_576:
            raise ValueError(
                "GH_HISTORY_MAX_PAYLOAD_BYTES must be between 4096 and 1048576"
            )
        if not 1_024 <= self.history_max_records <= 2_000_000:
            raise ValueError("GH_HISTORY_MAX_RECORDS must be between 1024 and 2000000")
        if not 1_048_576 <= self.history_max_db_bytes <= 2_147_483_648:
            raise ValueError(
                "GH_HISTORY_MAX_DB_BYTES must be between 1048576 and 2147483648"
            )
        if not 1 <= self.history_queue_capacity <= 1_024:
            raise ValueError("GH_HISTORY_QUEUE_CAPACITY must be between 1 and 1024")
        if not 1 <= self.history_max_pages_per_minute <= 600:
            raise ValueError(
                "GH_HISTORY_MAX_PAGES_PER_MINUTE must be between 1 and 600"
            )
        if not 1 <= self.history_rate_state_capacity <= 65_536:
            raise ValueError(
                "GH_HISTORY_RATE_STATE_CAPACITY must be between 1 and 65536"
            )
        if not 1 <= self.history_rate_state_ttl_s <= 86_400:
            raise ValueError(
                "GH_HISTORY_RATE_STATE_TTL_S must be between 1 and 86400"
            )
        if not 30 <= self.history_prune_interval_s <= 86_400:
            raise ValueError(
                "GH_HISTORY_PRUNE_INTERVAL_S must be between 30 and 86400"
            )
        if self.n3w_product_pairing_enabled:
            if not self.n3w_runtime_enabled:
                raise ValueError(
                    "GH_N3W_PRODUCT_PAIRING_ENABLED "
                    "requires GH_N3W_RUNTIME_ENABLED"
                )

            if (
                _ID_RE.fullmatch(
                    self.n3w_pairing_manager_id
                )
                is None
            ):
                raise ValueError(
                    "GH_N3W_PAIRING_MANAGER_ID must "
                    "match [A-Za-z0-9_-]{3,64}"
                )

            if self.n3w_pairing_bind_host not in {
                "0.0.0.0",
                "127.0.0.1",
            }:
                raise ValueError(
                    "GH_N3W_PAIRING_BIND_HOST must be "
                    "0.0.0.0 or 127.0.0.1"
                )

            if (
                not self.n3w_pairing_advertised_host
                or any(
                    character.isspace()
                    for character
                    in self.n3w_pairing_advertised_host
                )
            ):
                raise ValueError(
                    "GH_N3W_PAIRING_ADVERTISED_HOST "
                    "must be non-empty"
                )

            for name, port in (
                (
                    "GH_N3W_PAIRING_HTTP_PORT",
                    self.n3w_pairing_http_port,
                ),
                (
                    "GH_N3W_PAIRING_UDP_PORT",
                    self.n3w_pairing_udp_port,
                ),
                (
                    "GH_N3W_NODE_BROKER_PORT",
                    self.n3w_node_broker_port,
                ),
            ):
                if not 1 <= port <= 65535:
                    raise ValueError(
                        f"{name} must be between "
                        "1 and 65535"
                    )

            provisioning = (
                self.n3w_provisioning_username,
                self.n3w_provisioning_password,
                self.n3w_provisioning_client_id,
            )

            if not all(provisioning):
                raise ValueError(
                    "N3-W provisioning identity is "
                    "incomplete"
                )

            if (
                not self.n3w_node_broker_host
                or any(
                    character.isspace()
                    for character
                    in self.n3w_node_broker_host
                )
            ):
                raise ValueError(
                    "GH_N3W_NODE_BROKER_HOST "
                    "must be non-empty"
                )

            if (
                not self.n3w_node_broker_tls_server_name
                or any(
                    character.isspace()
                    for character
                    in self.n3w_node_broker_tls_server_name
                )
            ):
                raise ValueError(
                    "GH_N3W_NODE_BROKER_TLS_SERVER_NAME "
                    "must be non-empty"
                )

            if not self.n3w_node_broker_ca_file:
                raise ValueError(
                    "GH_N3W_NODE_BROKER_CA_FILE "
                    "is required"
                )

            ca_path = Path(
                self.n3w_node_broker_ca_file
            ).expanduser()

            if (
                not ca_path.is_absolute()
                or ca_path.is_symlink()
                or not ca_path.is_file()
            ):
                raise ValueError(
                    "GH_N3W_NODE_BROKER_CA_FILE must "
                    "reference an absolute regular "
                    "non-symlink file"
                )

            if ca_path.stat().st_size > 64 * 1024:
                raise ValueError(
                    "GH_N3W_NODE_BROKER_CA_FILE "
                    "exceeds 64 KiB"
                )

            try:
                ca_pem = ca_path.read_text(
                    encoding="utf-8"
                )
            except UnicodeError as error:
                raise ValueError(
                    "GH_N3W_NODE_BROKER_CA_FILE must "
                    "contain UTF-8 PEM"
                ) from error

            if (
                "-----BEGIN CERTIFICATE-----"
                not in ca_pem
                or "-----END CERTIFICATE-----"
                not in ca_pem
                or "\x00" in ca_pem
            ):
                raise ValueError(
                    "GH_N3W_NODE_BROKER_CA_FILE must "
                    "contain a PEM certificate"
                )

            product_private_paths = {
                "GH_N3W_PEER_TRUST_DB_PATH":
                    self.n3w_peer_trust_db_path,
                "GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH":
                    self.n3w_credential_lifecycle_db_path,
                "GH_N3W_PAIRING_SOCKET_PATH":
                    self.n3w_pairing_socket_path,
            }

            normalized_product_paths = {}

            for name, raw_path in (
                product_private_paths.items()
            ):
                if not raw_path.strip():
                    raise ValueError(
                        f"{name} cannot be empty"
                    )

                private_path = Path(
                    raw_path
                ).expanduser()

                if not private_path.is_absolute():
                    raise ValueError(
                        f"{name} must be absolute"
                    )

                if _path_contains_symlink(
                    private_path
                ):
                    raise ValueError(
                        f"{name} and its ancestors "
                        "must not be symlinks"
                    )

                normalized_product_paths[
                    name
                ] = private_path

            product_databases = {
                Path(
                    self.pairing_db_path
                ).expanduser(),
                Path(
                    self.n3w_replay_db_path
                ).expanduser(),
                Path(
                    self.n3w_relay_authorization_db_path
                ).expanduser(),
                normalized_product_paths[
                    "GH_N3W_PEER_TRUST_DB_PATH"
                ],
                normalized_product_paths[
                    (
                        "GH_N3W_CREDENTIAL_"
                        "LIFECYCLE_DB_PATH"
                    )
                ],
            }

            if len(product_databases) != 5:
                raise ValueError(
                    "N3-W product databases must differ"
                )


        if self.n3w_runtime_enabled:
            configured_paths = {
                "GH_PAIRING_DB_PATH": self.pairing_db_path,
                "GH_N3W_REPLAY_DB_PATH": self.n3w_replay_db_path,
                "GH_N3W_RELAY_AUTHORIZATION_DB_PATH": (
                    self.n3w_relay_authorization_db_path
                ),
                "GH_N3W_RELAY_KEY_DIR": self.n3w_relay_key_dir,
            }
            normalized: dict[str, Path] = {}
            for name, raw_path in configured_paths.items():
                if not raw_path.strip():
                    raise ValueError(f"{name} cannot be empty when N3-W runtime is enabled")
                path = Path(raw_path).expanduser()
                if not path.is_absolute():
                    raise ValueError(f"{name} must be absolute when N3-W runtime is enabled")
                normalized[name] = path
            database_paths = {
                normalized["GH_PAIRING_DB_PATH"],
                normalized["GH_N3W_REPLAY_DB_PATH"],
                normalized["GH_N3W_RELAY_AUTHORIZATION_DB_PATH"],
            }
            if len(database_paths) != 3:
                raise ValueError("N3-W registration, replay, and authorization databases must differ")
            if normalized["GH_N3W_RELAY_KEY_DIR"] in database_paths:
                raise ValueError("GH_N3W_RELAY_KEY_DIR must not be a database path")
