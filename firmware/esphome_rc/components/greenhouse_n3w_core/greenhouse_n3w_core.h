#pragma once

#include "esphome/core/component.h"

#include "n3w_core.h"
#include "n3w_esp32_nvs.h"

namespace esphome::greenhouse_n3w_core {

class GreenhouseN3wCore : public Component {
 public:
  // P4a is deliberately inert at runtime. The component exists so the exact
  // ESP32-C6/ESP-IDF toolchain compiles the production crypto/session sources.
  // P4b must separately authorize radio and transport wiring.
  void setup() override {}
  void loop() override {}
};

}  // namespace esphome::greenhouse_n3w_core
