from __future__ import annotations

from greenhouse_manager.ha_discovery import HomeAssistantDiscovery

NODE_ID = "gh-n1-a9f2f8"


def canonical_telemetry(*, firmware_version: str = "F1.0-RC2-N1.0.1") -> dict[str, object]:
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": "boot_5BA5BC5150E96A38",
        "seq": 8,
        "uptime_ms": 480000,
        "received_at": "2026-07-10T16:27:46.860Z",
        "cap_hash": "sha256:3e19f73d5c27a84b",
        "fw_version": firmware_version,
        "measurements": {
            "air_temperature_c": 27.4,
            "air_humidity_pct": 68.2,
            "co2_ppm": 684,
            "illuminance_lx": 18250,
            "soil_moisture_pct": None,
        },
        "quality": {
            "air_temperature_c": "ok",
            "air_humidity_pct": "ok",
            "co2_ppm": "ok",
            "illuminance_lx": "ok",
            "soil_moisture_pct": "not_present",
        },
        "power": {
            "source": "main",
            "battery_v": None,
            "battery_pct": None,
            "low": False,
        },
    }


def test_builds_device_and_connectivity_discovery() -> None:
    discovery = HomeAssistantDiscovery(system_id="greenhouse")

    messages = discovery.messages_for_telemetry(canonical_telemetry())

    assert len(messages) == 2
    device_message, connectivity_message = messages

    assert device_message.topic == f"homeassistant/device/{NODE_ID}/config"
    assert device_message.qos == 1
    assert device_message.retain is True
    assert device_message.payload["state_topic"] == (
        f"gh/v1/greenhouse/state/{NODE_ID}/telemetry"
    )
    assert device_message.payload["availability"][0]["topic"] == (
        f"gh/v1/greenhouse/state/{NODE_ID}/availability"
    )
    assert device_message.payload["origin"]["name"] == "greenhouse-manager"
    assert device_message.payload["device"]["serial_number"] == NODE_ID
    assert device_message.payload["device"]["sw_version"] == "F1.0-RC2-N1.0.1"

    components = device_message.payload["components"]
    assert set(components) == {
        "air_temperature_c",
        "air_humidity_pct",
        "co2_ppm",
        "illuminance_lx",
        "firmware_version",
        "node_id",
    }
    assert components["air_temperature_c"]["device_class"] == "temperature"
    assert components["air_temperature_c"]["unit_of_measurement"] == "°C"
    assert components["co2_ppm"]["device_class"] == "carbon_dioxide"
    assert components["illuminance_lx"]["device_class"] == "illuminance"

    assert connectivity_message.topic == (
        f"homeassistant/binary_sensor/{NODE_ID}_connectivity/config"
    )
    assert connectivity_message.payload["state_topic"] == (
        f"gh/v1/greenhouse/state/{NODE_ID}/availability"
    )
    assert connectivity_message.payload["payload_on"] == "online"
    assert connectivity_message.payload["payload_off"] == "unavailable"


def test_does_not_republish_unchanged_discovery() -> None:
    discovery = HomeAssistantDiscovery(system_id="greenhouse")
    document = canonical_telemetry()

    first = discovery.messages_for_telemetry(document)
    second = discovery.messages_for_telemetry(document)

    assert len(first) == 2
    assert second == ()


def test_republishes_when_firmware_version_changes() -> None:
    discovery = HomeAssistantDiscovery(system_id="greenhouse")
    discovery.messages_for_telemetry(canonical_telemetry())

    changed = discovery.messages_for_telemetry(
        canonical_telemetry(firmware_version="F1.0-RC2-N1.0.2")
    )

    assert len(changed) == 2
    assert changed[0].payload["device"]["sw_version"] == "F1.0-RC2-N1.0.2"


def test_discovery_can_be_disabled() -> None:
    discovery = HomeAssistantDiscovery(system_id="greenhouse", enabled=False)

    assert discovery.messages_for_telemetry(canonical_telemetry()) == ()
