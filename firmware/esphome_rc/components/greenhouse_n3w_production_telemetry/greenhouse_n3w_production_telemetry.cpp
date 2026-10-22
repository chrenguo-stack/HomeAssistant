#include "greenhouse_n3w_production_telemetry.h"

#include <cmath>
#include <cstdint>
#include <string>

#include "esphome/components/json/json_util.h"
#include "esphome/core/log.h"

namespace esphome::greenhouse_n3w_production_telemetry {
namespace {

static const char *const TAG = "n3w_product_telemetry";

bool usable(sensor::Sensor *value) {
  return value != nullptr && value->has_state() && std::isfinite(value->state);
}

void add_measurement(
    JsonObject measurements,
    JsonObject quality,
    const char *key,
    sensor::Sensor *value,
    const char *missing_quality) {
  if (usable(value)) {
    measurements[key] = value->state;
    return;
  }
  quality[key] = missing_quality;
}

}  // namespace

void GreenhouseN3wProductionTelemetry::update() {
  if (core_ == nullptr || !core_->runtime_ready()) return;

  std::string boot_id;
  uint32_t seq = 0;
  if (!core_->take_telemetry_identity(&boot_id, &seq)) return;

  const uint64_t uptime_ms = static_cast<uint64_t>(millis());
  const bool startup_warming = uptime_ms < 120000ULL;
  const char *normal_missing = startup_warming ? "warming" : "fault";
  const char *soil_missing = startup_warming ? "warming" : "stale";

  const std::string telemetry = json::build_json([&](JsonObject root) {
    root["schema"] = "gh.telemetry/1";
    root["node_id"] = core_->node_id();
    root["boot_id"] = boot_id;
    root["seq"] = seq;
    root["uptime_ms"] = uptime_ms;
    root["cap_hash"] = cap_hash_;
    root["fw_version"] = fw_version_;

    JsonObject measurements = root["measurements"].to<JsonObject>();
    JsonObject quality = root["quality"].to<JsonObject>();

    add_measurement(
        measurements, quality, "air_temperature_c", air_temperature_,
        normal_missing);
    add_measurement(
        measurements, quality, "air_humidity_pct", air_humidity_,
        normal_missing);
    add_measurement(measurements, quality, "co2_ppm", co2_, normal_missing);
    add_measurement(
        measurements, quality, "illuminance_lx", illuminance_,
        normal_missing);
    add_measurement(
        measurements, quality, "soil_temperature_c", soil_temperature_,
        soil_missing);
    add_measurement(
        measurements, quality, "soil_moisture_pct", soil_moisture_,
        soil_missing);
    add_measurement(
        measurements, quality, "soil_ec_us_cm", soil_ec_, soil_missing);
    add_measurement(measurements, quality, "vpd_kpa", vpd_, normal_missing);
    add_measurement(
        measurements, quality, "dew_point_c", dew_point_, normal_missing);
    add_measurement(
        measurements, quality, "absolute_humidity_g_m3", absolute_humidity_,
        normal_missing);
    add_measurement(
        measurements, quality, "ppfd_umol_m2_s", ppfd_, normal_missing);
    add_measurement(
        measurements, quality, "dli_today_mol_m2_d", dli_today_,
        normal_missing);
    add_measurement(
        measurements, quality, "dli_yesterday_mol_m2_d", dli_yesterday_,
        normal_missing);

    const bool battery_present = usable(battery_voltage_) &&
                                 battery_voltage_->state > 0.5f;
    if (battery_present) {
      measurements["battery_v"] = battery_voltage_->state;
      if (usable(battery_level_)) {
        measurements["battery_pct"] = battery_level_->state;
      } else {
        quality["battery_pct"] = normal_missing;
      }
    } else {
      quality["battery_v"] = "not_present";
      quality["battery_pct"] = "not_present";
    }

    JsonObject power = root["power"].to<JsonObject>();
    if (main_power_ != nullptr && main_power_->has_state()) {
      power["source"] = main_power_->state ? "main" : "battery";
    } else {
      power["source"] = "unknown";
    }
    power["low"] =
        low_battery_ != nullptr && low_battery_->has_state()
            ? low_battery_->state
            : false;

    if (battery_present) {
      power["battery_v"] = battery_voltage_->state;
      if (usable(battery_level_)) {
        power["battery_pct"] = battery_level_->state;
      } else {
        power["battery_pct"] = nullptr;
      }
    } else {
      power["battery_v"] = nullptr;
      power["battery_pct"] = nullptr;
    }
  });

  if (telemetry.empty() ||
      telemetry.size() > greenhouse_n3w_core::kMaxCiphertextBytes) {
    ESP_LOGE(
        TAG,
        "Production telemetry rejected before transport seq=%u bytes=%u limit=%u",
        static_cast<unsigned>(seq),
        static_cast<unsigned>(telemetry.size()),
        static_cast<unsigned>(greenhouse_n3w_core::kMaxCiphertextBytes));
    return;
  }

  const auto disposition =
      core_->submit_telemetry_json(telemetry, boot_id, seq);
  if (disposition == greenhouse_n3w_core::TelemetrySubmitDisposition::REJECTED) {
    ESP_LOGW(
        TAG,
        "Production telemetry rejected by N3-W runtime seq=%u bytes=%u",
        static_cast<unsigned>(seq),
        static_cast<unsigned>(telemetry.size()));
  }
}

}  // namespace esphome::greenhouse_n3w_production_telemetry
