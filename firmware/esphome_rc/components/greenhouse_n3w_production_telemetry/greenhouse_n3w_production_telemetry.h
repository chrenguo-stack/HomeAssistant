#pragma once

#include <string>

#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/greenhouse_n3w_core/greenhouse_n3w_core.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/core/component.h"

namespace esphome::greenhouse_n3w_production_telemetry {

class GreenhouseN3wProductionTelemetry : public PollingComponent {
 public:
  void set_core(greenhouse_n3w_core::GreenhouseN3wCore *value) { core_ = value; }
  void set_cap_hash(const std::string &value) { cap_hash_ = value; }
  void set_fw_version(const std::string &value) { fw_version_ = value; }

  void set_air_temperature(sensor::Sensor *value) { air_temperature_ = value; }
  void set_air_humidity(sensor::Sensor *value) { air_humidity_ = value; }
  void set_co2(sensor::Sensor *value) { co2_ = value; }
  void set_illuminance(sensor::Sensor *value) { illuminance_ = value; }
  void set_soil_temperature(sensor::Sensor *value) { soil_temperature_ = value; }
  void set_soil_moisture(sensor::Sensor *value) { soil_moisture_ = value; }
  void set_soil_ec(sensor::Sensor *value) { soil_ec_ = value; }
  void set_vpd(sensor::Sensor *value) { vpd_ = value; }
  void set_dew_point(sensor::Sensor *value) { dew_point_ = value; }
  void set_absolute_humidity(sensor::Sensor *value) { absolute_humidity_ = value; }
  void set_ppfd(sensor::Sensor *value) { ppfd_ = value; }
  void set_dli_today(sensor::Sensor *value) { dli_today_ = value; }
  void set_dli_yesterday(sensor::Sensor *value) { dli_yesterday_ = value; }
  void set_battery_voltage(sensor::Sensor *value) { battery_voltage_ = value; }
  void set_battery_level(sensor::Sensor *value) { battery_level_ = value; }
  void set_main_power(binary_sensor::BinarySensor *value) { main_power_ = value; }
  void set_low_battery(binary_sensor::BinarySensor *value) { low_battery_ = value; }

  void update() override;

 private:
  greenhouse_n3w_core::GreenhouseN3wCore *core_{nullptr};
  std::string cap_hash_;
  std::string fw_version_;

  sensor::Sensor *air_temperature_{nullptr};
  sensor::Sensor *air_humidity_{nullptr};
  sensor::Sensor *co2_{nullptr};
  sensor::Sensor *illuminance_{nullptr};
  sensor::Sensor *soil_temperature_{nullptr};
  sensor::Sensor *soil_moisture_{nullptr};
  sensor::Sensor *soil_ec_{nullptr};
  sensor::Sensor *vpd_{nullptr};
  sensor::Sensor *dew_point_{nullptr};
  sensor::Sensor *absolute_humidity_{nullptr};
  sensor::Sensor *ppfd_{nullptr};
  sensor::Sensor *dli_today_{nullptr};
  sensor::Sensor *dli_yesterday_{nullptr};
  sensor::Sensor *battery_voltage_{nullptr};
  sensor::Sensor *battery_level_{nullptr};
  binary_sensor::BinarySensor *main_power_{nullptr};
  binary_sensor::BinarySensor *low_battery_{nullptr};
};

}  // namespace esphome::greenhouse_n3w_production_telemetry
