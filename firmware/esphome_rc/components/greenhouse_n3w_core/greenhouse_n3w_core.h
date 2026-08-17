#pragma once

#include "n3w_compact_telemetry.h"
#include "n3w_core.h"
#include "n3w_esp32_nvs.h"
#include "n3w_esp32_pairing_nvs.h"
#include "n3w_esp32_runtime_nvs.h"
#include "n3w_esp32_simple_nvs.h"
#include "n3w_phase4_physical_harness.h"
#include "n3w_simple_crypto.h"
#include "n3w_simple_pairing_client.h"
#include "n3w_simple_product_component.h"
#include "n3w_simple_product_runtime.h"
#include "n3w_simple_runtime.h"

namespace esphome::greenhouse_n3w_core {

class GreenhouseN3wCore : public SimpleProductComponent {
 public:
  void set_phase4_source_harness_enabled(bool enabled) {
    phase4_source_harness_enabled_ = enabled;
  }

  void set_phase4_product_runtime_enabled(bool enabled) {
    set_activation_enabled(enabled);
  }

  Phase4PhysicalHarness *phase4_harness() { return &phase4_harness_; }

  void setup() override {
    if (phase4_source_harness_enabled_) {
      phase4_source_harness_ready_ = phase4_harness_.prepare_source_only();
    }
    SimpleProductComponent::setup();
  }

  void loop() override {
    SimpleProductComponent::loop();
  }

  bool phase4_source_harness_ready() const {
    return phase4_source_harness_ready_;
  }

 protected:
  bool phase4_source_harness_enabled_{false};
  bool phase4_source_harness_ready_{false};
  Phase4PhysicalHarness phase4_harness_{};
};

}  // namespace esphome::greenhouse_n3w_core
