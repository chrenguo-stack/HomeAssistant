import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
PROD_COMPONENT = (
    ROOT / "firmware/esphome_rc/components/greenhouse_n3w_production_telemetry"
)
RC2 = ROOT / "firmware/esphome_rc/f1_0_rc2"
PROD_TARGET = RC2 / "f1_0_rc2_n3w_production.yml"
PROD_PACKAGE = RC2 / "packages/n3w_production.yml"
LAB_TARGET = ROOT / "firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_production_target_is_independent_from_phase4_lab_target() -> None:
    production = text(PROD_TARGET)
    package = text(PROD_PACKAGE)
    lab = text(LAB_TARGET)

    assert "greenhouse_n3w_production_telemetry" in production
    assert "n3w_transport: !include packages/n3w_production.yml" in production
    assert "product_runtime: true" in package

    for forbidden in (
        "phase4_source_harness:",
        "phase4_lab_diagnostics:",
        "phase4_product_runtime:",
        "PHASE4_PAIRING_QR_PAYLOAD",
        "PHASE4_LAB_TELEMETRY",
        "phase4_lab",
        "n3w_l",
        "n3w_r",
        "n3w_u",
        "wdt_breadcrumb",
    ):
        assert forbidden not in production
        assert forbidden not in package

    # The already validated PR #437 lab target stays intact and independently
    # opt-in to the engineering fixture.
    assert "phase4_source_harness: true" in lab
    assert "phase4_product_runtime: true" in lab
    assert "phase4_lab_diagnostics: true" in lab
    assert "PHASE4_PAIRING_QR_PAYLOAD" in lab
    assert "PHASE4_LAB_TELEMETRY" in lab


def test_phase4_lab_code_is_compile_time_opt_in() -> None:
    init = text(CORE / "__init__.py")
    core_header = text(CORE / "greenhouse_n3w_core.h")
    diagnostic_header = text(CORE / "n3w_lab_diagnostics.h")
    diagnostic_source = text(CORE / "n3w_lab_diagnostics.cpp")
    harness_source = text(CORE / "n3w_phase4_physical_harness.cpp")
    breadcrumb_source = text(CORE / "n3w_rtc_breadcrumb.cpp")
    driver = text(CORE / "n3w_espnow_driver.cpp")

    gate = "GREENHOUSE_N3W_ENABLE_PHASE4_LAB"
    assert f'LAB_BUILD_FLAG = "{gate}"' in init
    assert "if lab_enabled:" in init
    assert 'CONF_PRODUCT_RUNTIME = "product_runtime"' in init

    for source in (
        core_header,
        diagnostic_header,
        diagnostic_source,
        harness_source,
        breadcrumb_source,
        driver,
    ):
        assert gate in source

    assert "Production build stub" in diagnostic_header
    assert "diagnostic receive count=" in driver
    assert "Lab-only observation" in driver


def test_production_bridge_uses_real_product_entities_and_n3w_runtime() -> None:
    package = text(PROD_PACKAGE)
    source = text(
        PROD_COMPONENT / "greenhouse_n3w_production_telemetry.cpp"
    )

    for entity_id in (
        "air_temp",
        "air_humidity",
        "scd30_co2",
        "illuminance",
        "soil_temperature",
        "soil_moisture",
        "soil_ec",
        "vpd",
        "dew_point",
        "absolute_humidity",
        "ppfd",
        "dli_today_sensor",
        "dli_yesterday_sensor",
        "battery_voltage",
        "battery_level",
        "main_power",
        "low_battery_status",
    ):
        assert entity_id in package

    assert "take_telemetry_identity" in source
    assert "submit_telemetry_json" in source
    assert '"gh.telemetry/1"' in source
    assert "mqtt::global_mqtt_client->publish" not in source
    assert "phase4" not in source.lower()
    assert "synthetic" not in source.lower()


def test_production_payload_shape_has_compact_worst_case_budget() -> None:
    # Mirror the production bridge's compact rule: valid values are carried in
    # measurements without redundant quality='ok'; missing values are omitted
    # from measurements and receive one quality marker instead.
    keys = (
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
    )
    payload = {
        "schema": "gh.telemetry/1",
        "node_id": "node_" + "f" * 32,
        "boot_id": "boot_" + "f" * 16,
        "seq": 0xFFFFFFFF,
        "uptime_ms": 0xFFFFFFFF,
        "cap_hash": "n3w-prod-v1",
        "fw_version": "F1.0-RC2-N3W-PROD-0.1",
        "measurements": {},
        "quality": {key: "not_present" for key in keys},
        "power": {
            "source": "battery",
            "low": True,
            "battery_v": None,
            "battery_pct": None,
        },
    }
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    assert len(encoded) < 1024
