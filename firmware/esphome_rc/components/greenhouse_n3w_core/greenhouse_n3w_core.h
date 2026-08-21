#pragma once

#include <cstdint>
#include <string>

#include "esphome/core/log.h"

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
    fresh_identity_candidate_ = !persisted_runtime_state_present_();
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

  // Returns one telemetry identity owned by the product runtime. Sequence values
  // are burned when issued, even if the following transport attempt fails, so a
  // (boot_id, seq) tuple is never reused with different plaintext.
  bool take_telemetry_identity(std::string *boot_id, uint32_t *seq) {
    if (boot_id == nullptr || seq == nullptr || !runtime_ready()) return false;
    if (!begin_boot_session_if_needed_()) return false;

    uint32_t issued_seq = 0;
    const CoreError sequence_result =
        boot_session_manager_.take_sequence(&issued_seq);
    if (sequence_result != CoreError::NONE) {
      ESP_LOGE(
          "n3w_boot_session",
          "Telemetry sequence allocation failed code=%u",
          static_cast<unsigned>(sequence_result));
      mark_failed();
      return false;
    }

    const std::string issued_boot_id = boot_session_manager_.boot_id();
    if (issued_boot_id.empty()) {
      ESP_LOGE("n3w_boot_session", "Boot session identity unavailable");
      mark_failed();
      return false;
    }

    *boot_id = issued_boot_id;
    *seq = issued_seq;
    return true;
  }

 protected:
  bool persisted_runtime_state_present_() {
    ProvisionedPeerStateV2 peer;
    ProvisionedBrokerStateV2 broker;
    const bool present =
        peer_store_.load(&peer) == SimpleNvsStatus::OK &&
        broker_store_.load(&broker) == SimpleNvsStatus::OK && peer.valid() &&
        broker.valid() && peer.system_id == broker.system_id &&
        peer.node_id == broker.node_id;
    peer.clear();
    broker.clear();
    return present;
  }

  bool begin_boot_session_if_needed_() {
    if (boot_session_manager_.ready()) return true;

    uint64_t last_session = 0;
    StoreStatus store_status = boot_session_store_.load(&last_session);
    if (store_status == StoreStatus::MISSING) {
      // Only a device that had no persisted product identity when this process
      // started may establish the initial zero floor. A provisioned identity
      // with a missing counter is a rollback/recovery condition and fails closed.
      if (!fresh_identity_candidate_ || !provisioned()) {
        ESP_LOGE(
            "n3w_boot_session",
            "Provisioned identity has no durable boot-session counter");
        mark_failed();
        return false;
      }
      const CoreError provision_result =
          boot_session_manager_.provision_recovery_floor(
              &boot_session_store_, 0);
      if (provision_result != CoreError::NONE) {
        ESP_LOGE(
            "n3w_boot_session",
            "Initial boot-session floor persistence failed code=%u",
            static_cast<unsigned>(provision_result));
        mark_failed();
        return false;
      }
    } else if (store_status != StoreStatus::OK) {
      ESP_LOGE(
          "n3w_boot_session",
          "Durable boot-session counter unavailable status=%u",
          static_cast<unsigned>(store_status));
      mark_failed();
      return false;
    }

    const CoreError begin_result =
        boot_session_manager_.begin(&boot_session_store_, 0);
    if (begin_result != CoreError::NONE) {
      ESP_LOGE(
          "n3w_boot_session",
          "Boot-session start failed code=%u",
          static_cast<unsigned>(begin_result));
      mark_failed();
      return false;
    }

    return true;
  }

  bool phase4_source_harness_enabled_{false};
  bool phase4_source_harness_ready_{false};
  bool fresh_identity_candidate_{false};
  Phase4PhysicalHarness phase4_harness_{};
  NvsBootSessionStore boot_session_store_{};
  BootSessionManager boot_session_manager_{};
};

}  // namespace esphome::greenhouse_n3w_core
