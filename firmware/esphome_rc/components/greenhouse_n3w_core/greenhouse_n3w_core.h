#pragma once

#include "esphome/core/component.h"

#include "n3w_compact_telemetry.h"
#include "n3w_core.h"
#include "n3w_esp32_nvs.h"
#include "n3w_esp32_simple_nvs.h"
#include "n3w_phase4_physical_harness.h"
#include "n3w_simple_crypto.h"
#include "n3w_simple_runtime.h"

namespace esphome::greenhouse_n3w_core {

class GreenhouseN3wCore : public Component {
 public:
  void set_phase4_source_harness_enabled(bool enabled) {
    phase4_source_harness_enabled_ = enabled;
  }

  Phase4PhysicalHarness *phase4_harness() { return &phase4_harness_; }

  // Source-only preparation is deliberately I/O-free. It binds the real NVS,
  // local-path, compact-frame and ESP-NOW driver adapters into one generic
  // firmware target without initializing Wi-Fi/ESP-NOW or touching NVS.
  void setup() override {
    if (phase4_source_harness_enabled_) {
      phase4_source_harness_ready_ = phase4_harness_.prepare_source_only();
    }
  }

  void loop() override {}

  bool phase4_source_harness_ready() const {
    return phase4_source_harness_ready_;
  }

 protected:
  bool phase4_source_harness_enabled_{false};
  bool phase4_source_harness_ready_{false};
  Phase4PhysicalHarness phase4_harness_{};
};

}  // namespace esphome::greenhouse_n3w_core
