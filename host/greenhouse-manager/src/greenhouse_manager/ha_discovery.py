from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .ingest import PublishMessage
from .topics import availability_topic, canonical_telemetry_topic


def _manager_version() -> str:
    try:
        return version("greenhouse-manager")
    except PackageNotFoundError:
        return "development"


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _measurement_sensor(
    *,
    node_id: str,
    key: str,
    name: str,
    device_class: str | None = None,
    unit: str | None = None,
) -> dict[str, Any]:
    component: dict[str, Any] = {
        "p": "sensor",
        "name": name,
        "unique_id": f"{node_id}_{key}",
        "state_class": "measurement",
        "value_template": f"{{{{ value_json.measurements.{key} }}}}",
    }
    if device_class:
        component["device_class"] = device_class
    if unit:
        component["unit_of_measurement"] = unit
    return component


@dataclass(slots=True)
class HomeAssistantDiscovery:
    system_id: str
    prefix: str = "homeassistant"
    device_name_prefix: str = "温室监测节点"
    enabled: bool = True
    _published_hashes: dict[str, str] = field(default_factory=dict, init=False)

    def _device_discovery_topic(self, node_id: str) -> str:
        return f"{self.prefix}/device/{node_id}/config"

    def _connectivity_discovery_topic(self, node_id: str) -> str:
        return f"{self.prefix}/binary_sensor/{node_id}_connectivity/config"

    def _device_info(self, node_id: str, firmware_version: str) -> dict[str, Any]:
        suffix = node_id.rsplit("-", 1)[-1]
        return {
            "identifiers": [f"gh_{self.system_id}_{node_id}"],
            "name": f"{self.device_name_prefix} {suffix}",
            "manufacturer": "Greenhouse Monitoring System",
            "model": "ESP32-C6-WROOM-1 Monitoring Node",
            "serial_number": node_id,
            "sw_version": firmware_version,
        }

    @staticmethod
    def _origin() -> dict[str, str]:
        return {
            "name": "greenhouse-manager",
            "sw_version": _manager_version(),
        }

    def _device_payload(self, document: dict[str, Any]) -> dict[str, Any]:
        node_id = str(document["node_id"])
        firmware_version = str(document.get("fw_version") or "unknown")
        measurements = document.get("measurements")
        if not isinstance(measurements, dict):
            measurements = {}

        definitions = {
            "air_temperature_c": ("空气温度", "temperature", "°C"),
            "air_humidity_pct": ("空气湿度", "humidity", "%"),
            "co2_ppm": ("二氧化碳", "carbon_dioxide", "ppm"),
            "illuminance_lx": ("光照度", "illuminance", "lx"),
        }
        components: dict[str, dict[str, Any]] = {}
        for key, (name, device_class, unit) in definitions.items():
            if key not in measurements:
                continue
            components[key] = _measurement_sensor(
                node_id=node_id,
                key=key,
                name=name,
                device_class=device_class,
                unit=unit,
            )

        components["firmware_version"] = {
            "p": "sensor",
            "name": "固件版本",
            "unique_id": f"{node_id}_firmware_version",
            "entity_category": "diagnostic",
            "icon": "mdi:chip",
            "value_template": "{{ value_json.fw_version }}",
        }
        components["node_id"] = {
            "p": "sensor",
            "name": "节点标识",
            "unique_id": f"{node_id}_node_id",
            "entity_category": "diagnostic",
            "icon": "mdi:identifier",
            "value_template": "{{ value_json.node_id }}",
        }

        return {
            "device": self._device_info(node_id, firmware_version),
            "origin": self._origin(),
            "components": components,
            "state_topic": canonical_telemetry_topic(self.system_id, node_id),
            "availability": [
                {
                    "topic": availability_topic(self.system_id, node_id),
                    "value_template": "{{ value_json.state }}",
                    "payload_available": "online",
                    "payload_not_available": "unavailable",
                }
            ],
            "qos": 1,
        }

    def _connectivity_payload(self, document: dict[str, Any]) -> dict[str, Any]:
        node_id = str(document["node_id"])
        firmware_version = str(document.get("fw_version") or "unknown")
        return {
            "device": self._device_info(node_id, firmware_version),
            "origin": self._origin(),
            "name": "连接状态",
            "unique_id": f"{node_id}_connectivity",
            "device_class": "connectivity",
            "entity_category": "diagnostic",
            "state_topic": availability_topic(self.system_id, node_id),
            "value_template": "{{ value_json.state }}",
            "payload_on": "online",
            "payload_off": "unavailable",
            "qos": 1,
        }

    def messages_for_telemetry(self, document: dict[str, Any]) -> tuple[PublishMessage, ...]:
        if not self.enabled:
            return ()

        node_id = str(document["node_id"])
        candidates = (
            (self._device_discovery_topic(node_id), self._device_payload(document)),
            (self._connectivity_discovery_topic(node_id), self._connectivity_payload(document)),
        )

        messages: list[PublishMessage] = []
        for topic, payload in candidates:
            digest = _payload_hash(payload)
            if self._published_hashes.get(topic) == digest:
                continue
            self._published_hashes[topic] = digest
            messages.append(PublishMessage(topic=topic, payload=payload, qos=1, retain=True))
        return tuple(messages)
