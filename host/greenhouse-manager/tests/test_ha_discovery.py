from __future__ import annotations

from greenhouse_manager.ha_discovery import HomeAssistantDiscovery

NODE_ID = "gh-n1-a9f2f8"


def canonical_telemetry(*, firmware_version: str = "F1.0-RC2-N1.0.1") -> dict[str, object]:
    measurements = {
        "air_temperature_c": 27.4,
        "air_humidity_pct": 68.2,
        "co2_ppm": 684,
        "illuminance_lx": 18250,
        "soil_temperature_c": None,
        "soil_moisture_pct": None,
        "soil_ec_us_cm": None,
        "vpd_kpa": 1.18,
        "dew_point_c": 21.0,
        "absolute_humidity_g_m3": 17.9,
        "ppfd_umol_m2_s": 337.6,
        "dli_today_mol_m2_d": 5.42,
        "dli_yesterday_mol_m2_d": 12.81,
        "battery_v": None,
        "battery_pct": None,
    }
    quality = {
        key: ("not_present" if key.startswith("soil_") or key.startswith("battery_") else "ok")
        for key in measurements
    }
    return {
        "schema": "gh.telemetry/1",
        "node_id": NODE_ID,
        "boot_id": "boot_5BA5BC5150E96A38",
        "seq": 8,
        "uptime_ms": 480000,
        "received_at": "2026-07-10T16:27:46.860Z",
        "cap_hash": "sha256:3e19f73d5c27a84b",
        "fw_version": firmware_version,
        "measurements": measurements,
        "quality": quality,
        "power": {
            "source": "main",
            "battery_v": None,
            "battery_pct": None,
            "low": False,
        },
    }


def test_builds_full_device_and_connectivity_discovery() -> None:
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
        "soil_temperature_c",
        "soil_moisture_pct",
        "soil_ec_us_cm",
        "vpd_kpa",
        "dew_point_c",
        "absolute_humidity_g_m3",
        "ppfd_umol_m2_s",
        "dli_today_mol_m2_d",
        "dli_yesterday_mol_m2_d",
        "battery_v",
        "battery_pct",
        "firmware_version",
        "node_id",
        "power_source",
        "low_battery",
    }
    assert components["air_temperature_c"]["device_class"] == "temperature"
    assert components["co2_ppm"]["device_class"] == "carbon_dioxide"
    assert components["soil_moisture_pct"]["device_class"] == "moisture"
    assert components["soil_ec_us_cm"]["device_class"] == "conductivity"
    assert components["absolute_humidity_g_m3"]["device_class"] == "absolute_humidity"
    assert components["vpd_kpa"]["device_class"] == "pressure"
    assert components["battery_v"]["device_class"] == "voltage"
    assert components["battery_pct"]["device_class"] == "battery"
    assert components["battery_pct"]["entity_category"] == "diagnostic"
    assert components["dli_today_mol_m2_d"]["state_class"] == "total_increasing"
    assert "state_class" not in components["dli_yesterday_mol_m2_d"]
    assert components["low_battery"]["p"] == "binary_sensor"
    assert components["low_battery"]["payload_on"] == "ON"
    assert components["power_source"]["value_template"] == "{{ value_json.power.source }}"

    assert connectivity_message.topic == (
        f"homeassistant/binary_sensor/{NODE_ID}_connectivity/config"
    )
    assert connectivity_message.payload["state_topic"] == (
        f"gh/v1/greenhouse/state/{NODE_ID}/availability"
    )
    assert connectivity_message.payload["payload_on"] == "online"
    assert connectivity_message.payload["payload_off"] == "unavailable"


def test_only_exposes_measurements_present_in_payload() -> None:
    discovery = HomeAssistantDiscovery(system_id="greenhouse")
    document = canonical_telemetry()
    document["measurements"] = {"air_temperature_c": 25.0}

    messages = discovery.messages_for_telemetry(document)
    components = messages[0].payload["components"]

    assert "air_temperature_c" in components
    assert "air_humidity_pct" not in components
    assert "firmware_version" in components
    assert "power_source" in components


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
