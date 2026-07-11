from __future__ import annotations

import os
import re
from dataclasses import dataclass

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_DISCOVERY_PREFIX_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


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

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls(
            system_id=os.getenv("GH_SYSTEM_ID", "dev"),
            mqtt_host=os.getenv("GH_MQTT_HOST", "mosquitto"),
            mqtt_port=int(os.getenv("GH_MQTT_PORT", "1883")),
            mqtt_username=os.getenv("GH_MQTT_USERNAME") or None,
            mqtt_password=os.getenv("GH_MQTT_PASSWORD") or None,
            mqtt_tls=_env_bool("GH_MQTT_TLS", False),
            mqtt_ca_file=os.getenv("GH_MQTT_CA_FILE") or None,
            mqtt_client_id=os.getenv("GH_MQTT_CLIENT_ID", "greenhouse-manager"),
            stale_after_s=int(os.getenv("GH_STALE_AFTER_S", "180")),
            dedup_capacity=int(os.getenv("GH_DEDUP_CAPACITY", "4096")),
            log_level=os.getenv("GH_LOG_LEVEL", "INFO").upper(),
            ha_discovery_enabled=_env_bool("GH_HA_DISCOVERY_ENABLED", True),
            ha_discovery_prefix=os.getenv("GH_HA_DISCOVERY_PREFIX", "homeassistant"),
            ha_device_name_prefix=os.getenv("GH_HA_DEVICE_NAME_PREFIX", "温室监测节点"),
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
            raise ValueError("GH_MQTT_USERNAME and GH_MQTT_PASSWORD must be configured together")
        if self.mqtt_tls and not self.mqtt_ca_file:
            raise ValueError("GH_MQTT_CA_FILE is required when GH_MQTT_TLS=true")
        if not _DISCOVERY_PREFIX_RE.fullmatch(self.ha_discovery_prefix):
            raise ValueError("GH_HA_DISCOVERY_PREFIX must match [A-Za-z0-9_-]{1,64}")
        if not self.ha_device_name_prefix.strip():
            raise ValueError("GH_HA_DEVICE_NAME_PREFIX cannot be empty")
