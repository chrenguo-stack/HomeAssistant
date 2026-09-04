#pragma once

#include <cstdint>
#include <string>

#include "esphome/core/log.h"

#ifdef USE_MQTT
#include "esphome/components/mqtt/mqtt_client.h"
#endif
#ifdef USE_WIFI
#include "esphome/components/wifi/wifi_component.h"
#endif
#ifdef USE_ESP32
#include "esp_system.h"
#include "esp_wifi.h"
#endif

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
    phase4_product_runtime_enabled_ = enabled;
    set_activation_enabled(enabled);
  }

  Phase4PhysicalHarness *phase4_harness() { return &phase4_harness_; }

  void setup() override {
#ifdef USE_ESP32
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_BOOT reset_reason=%d idf=%s",
        static_cast<int>(esp_reset_reason()),
        esp_get_idf_version());
#endif
    fresh_identity_candidate_ = !persisted_runtime_state_present_();
    if (phase4_source_harness_enabled_) {
      phase4_source_harness_ready_ = phase4_harness_.prepare_source_only();
    }
    SimpleProductComponent::setup();
    diag_log_state_(true);
  }

  void loop() override {
    SimpleProductComponent::loop();
    diag_log_state_(false);
  }

  bool phase4_source_harness_ready() const {
    return phase4_source_harness_ready_;
  }

  void on_espnow_receive_with_metadata(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) override {
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_ESPNOW_RX kind=%s src=%02x:%02x:%02x:%02x:%02x:%02x size=%u channel=%u rssi=%d path=%u",
        diag_frame_kind_(data, size),
        static_cast<unsigned>(source[0]),
        static_cast<unsigned>(source[1]),
        static_cast<unsigned>(source[2]),
        static_cast<unsigned>(source[3]),
        static_cast<unsigned>(source[4]),
        static_cast<unsigned>(source[5]),
        static_cast<unsigned>(size),
        static_cast<unsigned>(metadata.channel),
        static_cast<int>(metadata.rssi_dbm),
        diag_path_value_());
    SimpleProductComponent::on_espnow_receive_with_metadata(
        source, data, size, metadata);
  }

  void on_espnow_send_result(
      const MacAddress &destination,
      bool success) override {
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_ESPNOW_TX_DONE dst=%02x:%02x:%02x:%02x:%02x:%02x success=%s path=%u",
        static_cast<unsigned>(destination[0]),
        static_cast<unsigned>(destination[1]),
        static_cast<unsigned>(destination[2]),
        static_cast<unsigned>(destination[3]),
        static_cast<unsigned>(destination[4]),
        static_cast<unsigned>(destination[5]),
        success ? "true" : "false",
        diag_path_value_());
    SimpleProductComponent::on_espnow_send_result(destination, success);
  }

  bool set_radio_channel(uint8_t channel) override {
    uint8_t before_channel = 0;
    uint8_t after_channel = 0;
    const int before_rc = diag_read_channel_(&before_channel);
    const bool wifi_before = diag_wifi_connected_();
    const bool accepted = SimpleProductComponent::set_radio_channel(channel);
    const int after_rc = diag_read_channel_(&after_channel);

    ++diag_channel_attempts_;
    if (!accepted) ++diag_channel_failures_;
    const uint64_t now = now_ms();
    const bool log_failure =
        !accepted &&
        (diag_channel_failures_ <= 8 ||
         now - diag_last_channel_failure_log_ms_ >= 250);
    if (accepted || log_failure) {
      if (!accepted) diag_last_channel_failure_log_ms_ = now;
      ESP_LOGI(
          "n3w_diag",
          "N3W_DIAG_CHANNEL request=%u wifi_connected=%s accepted=%s before_rc=%d before=%u after_rc=%d after=%u attempts=%u failures=%u path=%u",
          static_cast<unsigned>(channel),
          wifi_before ? "true" : "false",
          accepted ? "true" : "false",
          before_rc,
          static_cast<unsigned>(before_channel),
          after_rc,
          static_cast<unsigned>(after_channel),
          static_cast<unsigned>(diag_channel_attempts_),
          static_cast<unsigned>(diag_channel_failures_),
          diag_path_value_());
    }
    return accepted;
  }

  bool broadcast_control(
      const uint8_t *data,
      std::size_t size) override {
    const char *kind = diag_frame_kind_(data, size);
    const bool accepted = SimpleProductComponent::broadcast_control(data, size);
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_ESPNOW_TX_SUBMIT kind=%s mode=broadcast size=%u accepted=%s path=%u",
        kind,
        static_cast<unsigned>(size),
        accepted ? "true" : "false",
        diag_path_value_());
    return accepted;
  }

  bool send_encrypted_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) override {
    const bool accepted =
        SimpleProductComponent::send_encrypted_peer(peer_mac, data, size);
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_ESPNOW_TX_SUBMIT kind=compact mode=unicast dst=%02x:%02x:%02x:%02x:%02x:%02x size=%u accepted=%s path=%u",
        static_cast<unsigned>(peer_mac[0]),
        static_cast<unsigned>(peer_mac[1]),
        static_cast<unsigned>(peer_mac[2]),
        static_cast<unsigned>(peer_mac[3]),
        static_cast<unsigned>(peer_mac[4]),
        static_cast<unsigned>(peer_mac[5]),
        static_cast<unsigned>(size),
        accepted ? "true" : "false",
        diag_path_value_());
    return accepted;
  }

  bool publish_direct(
      const std::string &topic,
      const std::string &payload) override {
    const bool accepted = SimpleProductComponent::publish_direct(topic, payload);
    ESP_LOGI(
        "n3w_diag",
        "N3W_DIAG_DIRECT_PUBLISH accepted=%s wifi_connected=%s mqtt_connected=%s path=%u",
        accepted ? "true" : "false",
        diag_wifi_connected_() ? "true" : "false",
        diag_mqtt_connected_() ? "true" : "false",
        diag_path_value_());
    return accepted;
  }

  // Recovery-only surface for a legacy provisioned identity whose durable boot
  // counter is missing. Formal recovery is inseparable from a higher pairing
  // generation so the old application-key epoch cannot be reused. The helper is
  // inert unless product/runtime harness execution is disabled.
  //
  // LEGACY_MIGRATION_ONLY / ENGINEERING_MIGRATION_ONLY / BOARD_LAB_ONLY.
  // Normal product runtime and Final Product Acceptance must not call this.
  // The historical sequence is restart-safe: pairing_epoch is materialized first and acts
  // as the recovery marker; a retry may then resume floor persistence and old
  // credential removal without lowering either durable generation.
  bool provision_boot_session_repair_recovery(
      uint64_t floor,
      uint32_t pairing_epoch) {
    if (floor == 0 || pairing_epoch < 2 || phase4_product_runtime_enabled_ ||
        phase4_source_harness_enabled_ || runtime_ready() ||
        boot_session_manager_.ready()) {
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
  static bool diag_wifi_connected_() {
#ifdef USE_WIFI
    return wifi::global_wifi_component != nullptr &&
           wifi::global_wifi_component->is_connected();
#else
    return false;
#endif
  }

  static bool diag_mqtt_connected_() {
#ifdef USE_MQTT
    return mqtt::global_mqtt_client != nullptr &&
           mqtt::global_mqtt_client->is_connected();
#else
    return false;
#endif
  }

  static int diag_read_channel_(uint8_t *channel) {
    if (channel == nullptr) return -1;
    *channel = 0;
#ifdef USE_ESP32
    wifi_second_chan_t secondary = WIFI_SECOND_CHAN_NONE;
    return static_cast<int>(esp_wifi_get_channel(channel, &secondary));
#else
    return -1;
#endif
  }

  static const char *diag_frame_kind_(
      const uint8_t *data,
      std::size_t size) {
    if (data == nullptr || size == 0) return "invalid";
    SimpleRelayDiscovery discovery;
    if (decode_simple_relay_discovery(data, size, &discovery) ==
        SimpleRuntimeError::NONE) {
      return "relay_discovery";
    }
    SimplePeerChallenge challenge;
    if (decode_simple_peer_challenge(data, size, &challenge) ==
        SimpleRuntimeError::NONE) {
      return "peer_challenge";
    }
    SimplePeerAccept accept;
    if (decode_simple_peer_accept(data, size, &accept) ==
        SimpleRuntimeError::NONE) {
      return "peer_accept";
    }
    CompactTelemetryFrameV2 compact;
    if (decode_compact_telemetry_frame_v2(data, size, &compact) ==
        CompactTelemetryError::NONE) {
      return "compact";
    }
    return "unknown";
  }

  unsigned diag_path_value_() const {
    return runtime_ready()
               ? static_cast<unsigned>(path_state())
               : 255U;
  }

  void diag_log_state_(bool force) {
    const uint64_t now = now_ms();
    const bool wifi_connected = diag_wifi_connected_();
    const bool mqtt_connected = diag_mqtt_connected_();
    const unsigned path = diag_path_value_();
    uint8_t channel = 0;
    const int channel_rc = diag_read_channel_(&channel);
    const bool changed =
        !diag_state_initialized_ || wifi_connected != diag_last_wifi_connected_ ||
        mqtt_connected != diag_last_mqtt_connected_ ||
        path != diag_last_path_ || channel != diag_last_channel_ ||
        channel_rc != diag_last_channel_rc_;
    if (force || changed || now - diag_last_state_log_ms_ >= 5000) {
      ESP_LOGI(
          "n3w_diag",
          "N3W_DIAG_STATE wifi_connected=%s mqtt_connected=%s runtime_ready=%s path=%u channel_rc=%d channel=%u uptime_ms=%llu boot_reset_reason=%d idf=%s rx_dropped=%u channel_attempts=%u channel_failures=%u",
          wifi_connected ? "true" : "false",
          mqtt_connected ? "true" : "false",
          runtime_ready() ? "true" : "false",
          path,
          channel_rc,
          static_cast<unsigned>(channel),
          static_cast<unsigned long long>(now),
#ifdef USE_ESP32
          static_cast<int>(esp_reset_reason()),
          esp_get_idf_version(),
#else
          -1,
          "non-esp32",
#endif
          static_cast<unsigned>(rx_dropped_.load(std::memory_order_relaxed)),
          static_cast<unsigned>(diag_channel_attempts_),
          static_cast<unsigned>(diag_channel_failures_));
      diag_last_state_log_ms_ = now;
    }
    diag_state_initialized_ = true;
    diag_last_wifi_connected_ = wifi_connected;
    diag_last_mqtt_connected_ = mqtt_connected;
    diag_last_path_ = path;
    diag_last_channel_ = channel;
    diag_last_channel_rc_ = channel_rc;
  }

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

  bool diag_state_initialized_{false};
  bool diag_last_wifi_connected_{false};
  bool diag_last_mqtt_connected_{false};
  unsigned diag_last_path_{255U};
  uint8_t diag_last_channel_{0};
  int diag_last_channel_rc_{-1};
  uint32_t diag_channel_attempts_{0};
  uint32_t diag_channel_failures_{0};
  uint64_t diag_last_state_log_ms_{0};
  uint64_t diag_last_channel_failure_log_ms_{0};
  bool phase4_source_harness_enabled_{false};
  bool phase4_source_harness_ready_{false};
  bool phase4_product_runtime_enabled_{false};
  bool fresh_identity_candidate_{false};
  Phase4PhysicalHarness phase4_harness_{};
  NvsBootSessionStore boot_session_store_{};
  BootSessionManager boot_session_manager_{};
  NvsPairingEpochStore recovery_pairing_epoch_store_{};
};

}  // namespace esphome::greenhouse_n3w_core
