#pragma once

#include "esphome/core/component.h"

#include "n3w_compact_telemetry.h"
#include "n3w_core.h"
#include "n3w_esp32_nvs.h"
#include "n3w_esp32_simple_nvs.h"
#include "n3w_simple_crypto.h"
#include "n3w_simple_runtime.h"

namespace esphome::greenhouse_n3w_core {

class GreenhouseN3wCore : public Component {
 public:
  // Phase 3 still keeps this generic component inert by default. All new
  // bootstrap, peer-trust, compact-frame and NVS primitives are compiled and
  // linked without factory secrets or a fixed Child/Relay role. Phase 4 must
  // separately authorize physical radio/pairing execution.
  void setup() override {}
  void loop() override {}
};

}  // namespace esphome::greenhouse_n3w_core
