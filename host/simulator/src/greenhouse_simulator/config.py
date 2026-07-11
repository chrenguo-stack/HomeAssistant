from __future__ import annotations

import os
import re
from dataclasses import dataclass

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_HARDWARE_ID_RE = re.compile(r"^ghw-[a-z0-9]+-[0-9a-f]{12}$")


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


def _positive_float(name: str, default: str) -> float:
    value = float(os.getenv(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _non_negative_int(name: str, default: str) -> int:
    value = int(os.getenv(name, default))
    if value < 0:
        raise ValueError(f"{name} must be zero or greater")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    system_id: str
    node_id: str
    mqtt_host: str = "mosquitto"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    publish_interval_s: float = 10.0
    initial_delay_s: float = 2.0
    publish_count: int = 0
    duplicate_every: int = 0
    invalid_every: int = 0
    log_level: str = "INFO"
    pairing_hello_enabled: bool = False
    hardware_id: str = "ghw-sim-000000000001"
    pairing_epoch: int = 1

    @classmethod
    def from_env(cls) -> Settings:
        settings = cls(
            system_id=os.getenv("GH_SYSTEM_ID", "devsystem"),
            node_id=os.getenv("GH_NODE_ID", "node_01HZX7AQ5FJ3"),
            mqtt_host=os.getenv("GH_MQTT_HOST", "mosquitto"),
            mqtt_port=int(os.getenv("GH_MQTT_PORT", "1883")),
            mqtt_username=os.getenv("GH_MQTT_USERNAME") or None,
            mqtt_password=os.getenv("GH_MQTT_PASSWORD") or None,
            publish_interval_s=_positive_float("GH_SIM_INTERVAL_S", "10"),
            initial_delay_s=float(os.getenv("GH_SIM_INITIAL_DELAY_S", "2")),
            publish_count=_non_negative_int("GH_SIM_COUNT", "0"),
            duplicate_every=_non_negative_int("GH_SIM_DUPLICATE_EVERY", "0"),
            invalid_every=_non_negative_int("GH_SIM_INVALID_EVERY", "0"),
            log_level=os.getenv("GH_LOG_LEVEL", "INFO").upper(),
            pairing_hello_enabled=_env_bool("GH_SIM_PAIRING_HELLO", False),
            hardware_id=os.getenv("GH_HARDWARE_ID", "ghw-sim-000000000001"),
            pairing_epoch=int(os.getenv("GH_PAIRING_EPOCH", "1")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not _ID_RE.fullmatch(self.system_id):
            raise ValueError("GH_SYSTEM_ID must match [A-Za-z0-9_-]{8,64}")
        if not _ID_RE.fullmatch(self.node_id):
            raise ValueError("GH_NODE_ID must match [A-Za-z0-9_-]{8,64}")
        if not self.mqtt_host.strip():
            raise ValueError("GH_MQTT_HOST cannot be empty")
        if not 1 <= self.mqtt_port <= 65535:
            raise ValueError("GH_MQTT_PORT must be between 1 and 65535")
        if self.initial_delay_s < 0:
            raise ValueError("GH_SIM_INITIAL_DELAY_S must be zero or greater")
        if bool(self.mqtt_username) != bool(self.mqtt_password):
            raise ValueError("GH_MQTT_USERNAME and GH_MQTT_PASSWORD must be configured together")
        if self.pairing_hello_enabled and not _HARDWARE_ID_RE.fullmatch(self.hardware_id):
            raise ValueError("GH_HARDWARE_ID must match ghw-<platform>-<12 lowercase hex>")
        if not 1 <= self.pairing_epoch <= 4294967295:
            raise ValueError("GH_PAIRING_EPOCH must be between 1 and 4294967295")
