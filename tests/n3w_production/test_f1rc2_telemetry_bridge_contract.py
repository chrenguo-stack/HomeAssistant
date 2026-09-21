from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml"
BRIDGE = ROOT / "firmware/esphome_rc/f1_0_rc2/packages/n3w_product_telemetry.yml"

EXPECTED_MEASUREMENTS = {
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
}


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_target_attaches_only_the_n3w_bridge() -> None:
    target = text(TARGET)
    assert "n3w_telemetry: !include packages/n3w_product_telemetry.yml" in target
    assert "n3w_telemetry_interval: 60s" in target
    assert 'n3w_cap_hash: "sha256:fed2dec764f4146d"' in target
    assert "mqtt_n1.yml" not in target


def test_bridge_uses_product_owned_identity_and_transport() -> None:
    bridge = text(BRIDGE)
    take = bridge.index("take_telemetry_identity")
    submit = bridge.index("submit_telemetry_json")
    assert take < submit
    assert "mqtt.publish" not in bridge
    assert "n1_boot_id" not in bridge
    assert "n1_seq" not in bridge


def test_bridge_preserves_f1rc2_measurement_vocabulary() -> None:
    bridge = text(BRIDGE)
    for key in EXPECTED_MEASUREMENTS:
        assert f'"{key}"' in bridge
    for quality in ("ok", "warming", "stale", "fault", "not_present"):
        assert f'"{quality}"' in bridge


def test_bridge_has_relay_plaintext_budget_fallback() -> None:
    bridge = text(BRIDGE)
    assert bridge.count("kMaxCiphertextBytes") >= 4
    assert "build_payload(true, true)" in bridge
    assert "build_payload(true, false)" in bridge
    assert "build_payload(false, false)" in bridge
    assert "Telemetry payload rejected before N3-W submit" in bridge
