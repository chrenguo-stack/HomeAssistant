#pragma once

#include <cstdint>
#include <limits>
#include <string>

#ifdef USE_MQTT
#include "esphome/components/mqtt/mqtt_client.h"
#endif
#ifdef USE_WIFI
#include "esphome/components/wifi/wifi_component.h"
#endif
#include "esphome/core/log.h"

#include "n3w_compact_telemetry.h"
#include "n3w_core.h"
#include "n3w_esp32_nvs.h"
#include "n3w_esp32_pairing_nvs.h"
#include "n3w_esp32_runtime_nvs.h"
#include "n3w_esp32_simple_nvs.h"
#include "n3w_first_pair_boot_policy.h"
#include "n3w_simple_crypto.h"
#include "n3w_simple_pairing_client.h"
#include "n3w_simple_product_component.h"
#include "n3w_simple_product_runtime.h"
#include "n3w_simple_runtime.h"

namespace esphome::greenhouse_n3w_core {

class GreenhouseN3wCore : public SimpleProductComponent {
 public:
  void set_product_runtime_enabled(bool enabled) {
    product_runtime_enabled_ = enabled;
    set_activation_enabled(enabled);
  }

  void setup() override {
    if (!product_runtime_enabled_) {
      SimpleProductComponent::setup();
      return;
    }

    const StartupProductIdentityState startup_identity =
        classify_startup_product_identity_();
    if (startup_identity == StartupProductIdentityState::INVALID_OR_PARTIAL) {
      ESP_LOGE(
          "n3w_boot_session",
          "Startup product identity state is partial, corrupt, or contradictory");
      mark_failed();
      return;
    }

    if (startup_identity == StartupProductIdentityState::PROVEN_FRESH) {
      const CoreError floor_result =
          prepare_initial_boot_floor(
              &boot_session_manager_, &boot_session_store_);
      if (floor_result != CoreError::NONE) {
        ESP_LOGE(
            "n3w_boot_session",
            "Initial boot-session floor preparation failed code=%u",
            static_cast<unsigned>(floor_result));
        mark_failed();
        return;
      }
    }

    SimpleProductComponent::setup();
  }

  void loop() override {
    SimpleProductComponent::loop();
    advance_direct_mqtt_broker_relocation_();
  }

  // Recovery-only surface for a legacy provisioned identity whose durable boot
  // counter is missing. Formal recovery is inseparable from a higher pairing
  // generation so the old application-key epoch cannot be reused. The helper is
  // inert unless normal product runtime execution is disabled.
  //
  // LEGACY_MIGRATION_ONLY / ENGINEERING_MIGRATION_ONLY / BOARD_LAB_ONLY.
  // Normal product runtime and Final Product Acceptance must not call this.
  // The historical sequence is restart-safe: pairing_epoch is materialized first and acts
  // as the recovery marker; a retry may then resume floor persistence and old
  // credential removal without lowering either durable generation.
  bool provision_boot_session_repair_recovery(
      uint64_t floor,
      uint32_t pairing_epoch) {
    if (floor == 0 || pairing_epoch < 2 || product_runtime_enabled_ ||
        runtime_ready() || boot_session_manager_.ready()) {
      ESP_LOGE(
          "n3w_boot_recovery",
          "Boot-session repair recovery precondition rejected");
      return false;
    }

    PendingPairingAckV2 pending;
    const SimpleNvsStatus ack_status = ack_store_.load(&pending);
    if (ack_status != SimpleNvsStatus::MISSING) {
      ESP_LOGE(
          "n3w_boot_recovery",
          "Repair recovery requires no pending pairing acknowledgement status=%u",
          static_cast<unsigned>(ack_status));
      return false;
    }

    uint64_t existing_floor = 0;
    const StoreStatus floor_status = boot_session_store_.load(&existing_floor);
    const bool floor_missing = floor_status == StoreStatus::MISSING;
    const bool floor_exact =
        floor_status == StoreStatus::OK && existing_floor == floor;
    if (!floor_missing && !floor_exact) {
      ESP_LOGE(
          "n3w_boot_recovery",
          "Repair recovery boot floor state rejected status=%u",
          static_cast<unsigned>(floor_status));
      return false;
    }

    uint32_t existing_pairing_epoch = 0;
    const SimpleNvsStatus pairing_epoch_status =
        recovery_pairing_epoch_store_.load(&existing_pairing_epoch);
    const bool pairing_epoch_missing =
        pairing_epoch_status == SimpleNvsStatus::MISSING;
    const bool pairing_epoch_exact =
        pairing_epoch_status == SimpleNvsStatus::OK &&
        existing_pairing_epoch == pairing_epoch;
    if (!pairing_epoch_missing && !pairing_epoch_exact) {
      ESP_LOGE(
          "n3w_boot_recovery",
          "Repair recovery pairing epoch state rejected status=%u",
          static_cast<unsigned>(pairing_epoch_status));
      return false;
    }

    ProvisionedPeerStateV2 peer;
    ProvisionedBrokerStateV2 broker;
    const SimpleNvsStatus peer_status = peer_store_.load(&peer);
    const SimpleNvsStatus broker_status = broker_store_.load(&broker);
    const bool peer_present =
        peer_status == SimpleNvsStatus::OK && peer.valid();
    const bool broker_present =
        broker_status == SimpleNvsStatus::OK && broker.valid();
    const bool peer_missing = peer_status == SimpleNvsStatus::MISSING;
    const bool broker_missing = broker_status == SimpleNvsStatus::MISSING;

    if ((!peer_present && !peer_missing) ||
        (!broker_present && !broker_missing)) {
      peer.clear();
      broker.clear();
      ESP_LOGE("n3w_boot_recovery", "Repair recovery credential state invalid");
      return false;
    }

    if (pairing_epoch_missing) {
      // First entry must prove an intact legacy provisioned identity. A missing
      // or partially erased credential set without the durable recovery marker
      // is ambiguous and therefore fails closed.
      if (!floor_missing || !peer_present || !broker_present ||
          peer.system_id != broker.system_id || peer.node_id != broker.node_id ||
          broker.credential_generation == 0 ||
          pairing_epoch <= broker.credential_generation ||
          pairing_epoch - broker.credential_generation != 1) {
        peer.clear();
        broker.clear();
        ESP_LOGE(
            "n3w_boot_recovery",
            "Repair recovery legacy identity binding rejected");
        return false;
      }
    } else if (peer_present && broker_present &&
               (peer.system_id != broker.system_id ||
                peer.node_id != broker.node_id)) {
      peer.clear();
      broker.clear();
      ESP_LOGE(
          "n3w_boot_recovery",
          "Repair recovery resumed credential binding rejected");
      return false;
    }

    peer.clear();
    broker.clear();

    if (pairing_epoch_missing &&
        recovery_pairing_epoch_store_.save(pairing_epoch) !=
            SimpleNvsStatus::OK) {
      ESP_LOGE("n3w_boot_recovery", "Repair pairing epoch persistence failed");
      return false;
    }

    uint32_t verified_pairing_epoch = 0;
    if (recovery_pairing_epoch_store_.load(&verified_pairing_epoch) !=
            SimpleNvsStatus::OK ||
        verified_pairing_epoch != pairing_epoch) {
      ESP_LOGE("n3w_boot_recovery", "Repair pairing epoch verification failed");
      return false;
    }

    if (floor_missing) {
      const CoreError floor_result =
          boot_session_manager_.provision_recovery_floor(
              &boot_session_store_, floor);
      if (floor_result != CoreError::NONE) {
        ESP_LOGE(
            "n3w_boot_recovery",
            "Boot-session recovery floor persistence failed code=%u",
            static_cast<unsigned>(floor_result));
        return false;
      }
    }

    uint64_t verified_floor = 0;
    if (boot_session_store_.load(&verified_floor) != StoreStatus::OK ||
        verified_floor != floor) {
      ESP_LOGE(
          "n3w_boot_recovery",
          "Boot-session recovery floor verification failed");
      return false;
    }

    if (broker_store_.erase() != SimpleNvsStatus::OK ||
        peer_store_.erase() != SimpleNvsStatus::OK) {
      ESP_LOGE(
          "n3w_boot_recovery",
          "Legacy credential removal failed; recovery remains resumable");
      return false;
    }

    ProvisionedPeerStateV2 verify_peer;
    ProvisionedBrokerStateV2 verify_broker;
    const bool credentials_removed =
        peer_store_.load(&verify_peer) == SimpleNvsStatus::MISSING &&
        broker_store_.load(&verify_broker) == SimpleNvsStatus::MISSING;
    verify_peer.clear();
    verify_broker.clear();
    if (!credentials_removed) {
      ESP_LOGE("n3w_boot_recovery", "Legacy credential removal verification failed");
      return false;
    }

    ESP_LOGI(
        "n3w_boot_recovery",
        "Boot-session repair floor and pairing epoch persisted; old credentials removed");
    return true;
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
  bool direct_wifi_connected_() const {
#ifdef USE_WIFI
    return wifi::global_wifi_component != nullptr &&
           wifi::global_wifi_component->is_connected();
#else
    return false;
#endif
  }

  bool direct_mqtt_connected_() const {
#ifdef USE_MQTT
    return mqtt::global_mqtt_client != nullptr &&
           mqtt::global_mqtt_client->is_connected();
#else
    return false;
#endif
  }

  uint64_t direct_broker_deadline_(uint64_t base, uint64_t delta) const {
    if (base > std::numeric_limits<uint64_t>::max() - delta) {
      return std::numeric_limits<uint64_t>::max();
    }
    return base + delta;
  }

  void reset_direct_broker_relocation_(bool rollback) {
    if (rollback) {
      rollback_broker_candidate_();
    } else {
      broker_discovery_session_.reset();
    }
    reset_broker_relocation_attempt_();
    direct_broker_relocation_owned_ = false;
  }

  bool start_next_direct_broker_candidate_() {
    const uint64_t now = now_ms();
    if (broker_discovery_completed_ms_ == 0U) return false;

    const uint64_t shared_deadline = direct_broker_deadline_(
        broker_discovery_completed_ms_,
        static_cast<uint64_t>(kBrokerRelocationCandidateBudgetMs) +
            kBrokerRelocationCleanupReserveMs);
    const uint64_t deadline = broker_relocation_candidate_deadline(
        now, shared_deadline, shared_deadline, 0U);
    if (deadline == 0U) return false;

    std::string current_ipv4;
    std::string current_mask;
    if (!current_wifi_ipv4_(&current_ipv4, &current_mask) ||
        current_ipv4 != broker_discovery_local_ipv4_ ||
        current_mask != broker_discovery_subnet_mask_) {
      broker_relocation_target_index_ = broker_relocation_targets_.size();
      ESP_LOGW(
          "n3w_broker_relocation",
          "N3-W standalone Broker relocation network changed after discovery");
      return false;
    }

    while (broker_relocation_target_index_ < broker_relocation_targets_.size()) {
      const SimpleBrokerRecoveryTarget target =
          broker_relocation_targets_[broker_relocation_target_index_++];
      if (target.host.empty() || target.host == stable_runtime_broker_host_ ||
          target.ttl_s == 0U) {
        continue;
      }
      const uint64_t ttl_ms = static_cast<uint64_t>(target.ttl_s) * 1000U;
      if (now < broker_discovery_completed_ms_ ||
          now - broker_discovery_completed_ms_ >= ttl_ms) {
        continue;
      }
      if (!retarget_runtime_broker_(target.host, true)) {
        broker_relocation_target_index_ = broker_relocation_targets_.size();
        rollback_broker_candidate_();
        ESP_LOGW(
            "n3w_broker_relocation",
            "N3-W standalone Broker candidate reconnect setup failed; stable Broker restored");
        return false;
      }
      pending_broker_candidate_host_ = target.host;
      broker_candidate_active_ = true;
      broker_candidate_verified_ = false;
      broker_candidate_started_ms_ = now;
      broker_candidate_deadline_ms_ = deadline;
      ESP_LOGI(
          "n3w_broker_relocation",
          "N3-W standalone Direct Broker candidate attempt started");
      return true;
    }
    return false;
  }

  void advance_direct_mqtt_broker_relocation_() {
    if (!product_runtime_enabled_ || !runtime_ready() || safe_reboot_requested_ ||
        direct_recovery_attempt_.phase() != DirectRecoveryPhase::IDLE) {
      direct_mqtt_failure_started_ms_ = 0;
      if (direct_broker_relocation_owned_) {
        reset_direct_broker_relocation_(true);
      }
      return;
    }

    const bool direct_path = runtime_.path_state() == LocalPathState::DIRECT;
    const bool wifi_ready = direct_wifi_connected_();
    const bool mqtt_ready = direct_mqtt_connected_();

    if (!direct_path || !wifi_ready) {
      direct_mqtt_failure_started_ms_ = 0;
      if (direct_broker_relocation_owned_) {
        reset_direct_broker_relocation_(true);
      }
      return;
    }

    if (mqtt_ready) {
      direct_mqtt_failure_started_ms_ = 0;
      if (direct_broker_relocation_owned_) {
        if (broker_candidate_active_ &&
            !pending_broker_candidate_host_.empty()) {
          broker_candidate_verified_ = true;
          stable_runtime_broker_host_ = pending_broker_candidate_host_;
          ESP_LOGI(
              "n3w_broker_relocation",
              "N3-W standalone Direct Broker candidate promoted for this boot");
        }
        reset_direct_broker_relocation_(false);
      }
      return;
    }

    const uint64_t now = now_ms();
    if (direct_mqtt_failure_started_ms_ == 0U) {
      direct_mqtt_failure_started_ms_ = now;
      return;
    }

    if (!broker_relocation_trigger_due(direct_mqtt_failure_started_ms_, now)) {
      return;
    }

    if (!direct_broker_relocation_owned_) {
      if (broker_discovery_ever_started_ &&
          (now < last_broker_discovery_started_ms_ ||
           now - last_broker_discovery_started_ms_ <
               kBrokerRelocationDiscoveryMinIntervalMs)) {
        return;
      }
      reset_broker_relocation_attempt_();
      direct_broker_relocation_owned_ = true;
      if (!start_broker_discovery_()) {
        direct_broker_relocation_owned_ = false;
      }
      return;
    }

    if (broker_candidate_active_) {
#ifdef USE_MQTT
      if (mqtt::global_mqtt_client != nullptr) {
        (void) mqtt::global_mqtt_client->n3w_runtime_request_reconnect();
      }
#endif
      if (broker_candidate_deadline_ms_ != 0U &&
          now >= broker_candidate_deadline_ms_) {
        broker_candidate_active_ = false;
        broker_candidate_verified_ = false;
        broker_candidate_started_ms_ = 0;
        broker_candidate_deadline_ms_ = 0;
        pending_broker_candidate_host_.clear();
        if (!start_next_direct_broker_candidate_()) {
          rollback_broker_candidate_();
          reset_direct_broker_relocation_(false);
        }
      }
      return;
    }

    if (broker_discovery_session_.active()) {
      const Esp32ManagerDiscoverySessionStatus status =
          broker_discovery_session_.poll(now);
      if (status == Esp32ManagerDiscoverySessionStatus::IN_PROGRESS) return;
      if (status == Esp32ManagerDiscoverySessionStatus::COMPLETE &&
          finish_broker_discovery_() &&
          start_next_direct_broker_candidate_()) {
        return;
      }
      reset_direct_broker_relocation_(false);
      return;
    }

    reset_direct_broker_relocation_(false);
  }

  static StartupIdentityRecordState startup_identity_record_state_(
      SimpleNvsStatus status,
      bool valid) {
    if (status == SimpleNvsStatus::MISSING) {
      return StartupIdentityRecordState::MISSING;
    }
    if (status == SimpleNvsStatus::OK && valid) {
      return StartupIdentityRecordState::VALID;
    }
    return StartupIdentityRecordState::INVALID;
  }

  StartupProductIdentityState classify_startup_product_identity_() {
    ProvisionedPeerStateV2 peer;
    ProvisionedBrokerStateV2 broker;
    PendingPairingAckV2 pending;

    const SimpleNvsStatus peer_status = peer_store_.load(&peer);
    const SimpleNvsStatus broker_status = broker_store_.load(&broker);
    const SimpleNvsStatus ack_status = ack_store_.load(&pending);

    const bool peer_valid =
        peer_status == SimpleNvsStatus::OK && peer.valid();
    const bool broker_valid =
        broker_status == SimpleNvsStatus::OK && broker.valid();
    const bool ack_valid =
        ack_status == SimpleNvsStatus::OK && pending.valid();
    const bool peer_broker_match =
        peer_valid && broker_valid && peer.system_id == broker.system_id &&
        peer.node_id == broker.node_id;

    const StartupProductIdentityState state = classify_startup_product_identity(
        startup_identity_record_state_(peer_status, peer_valid),
        startup_identity_record_state_(broker_status, broker_valid),
        peer_broker_match,
        startup_identity_record_state_(ack_status, ack_valid));

    peer.clear();
    broker.clear();
    pending.clear();
    return state;
  }

  bool begin_boot_session_if_needed_() {
    if (boot_session_manager_.ready()) return true;

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

  bool product_runtime_enabled_{false};
  bool direct_broker_relocation_owned_{false};
  uint64_t direct_mqtt_failure_started_ms_{0};
  NvsBootSessionStore boot_session_store_{};
  BootSessionManager boot_session_manager_{};
  NvsPairingEpochStore recovery_pairing_epoch_store_{};
};

}  // namespace esphome::greenhouse_n3w_core
