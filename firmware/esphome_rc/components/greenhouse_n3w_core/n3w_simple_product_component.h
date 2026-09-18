#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>

#include "esphome/core/component.h"

#include "n3w_esp32_pairing_nvs.h"
#include "n3w_esp32_runtime_nvs.h"
#include "n3w_espnow_driver.h"
#include "n3w_lab_diagnostics.h"
#include "n3w_simple_pairing_client.h"
#include "n3w_simple_product_runtime.h"

namespace esphome::greenhouse_n3w_core {

enum class TelemetrySubmitDisposition : uint8_t {
  REJECTED = 0,
  SUBMITTED,
  BUFFERED,
};

const char *telemetry_submit_disposition_name(
    TelemetrySubmitDisposition disposition);

class SimpleProductComponent : public Component,
                               public EspNowEventSink,
                               public SimpleProductPort,
                               public SimpleProductClock,
                               public SimpleProductRandom,
                               public SimplePairingClientNetwork,
                               public SimplePairingClientRandom {
  enum class RadioOwnership : uint8_t {
    DIRECT_WIFI = 0,
    RELAY_ESPNOW,
    DIRECT_PROBE,
    RELAY_RESTORE,
  };

 public:
  SimpleProductComponent();

  void set_activation_enabled(bool enabled) { activation_enabled_ = enabled; }
  void set_lab_diagnostics_enabled(bool enabled) {
    diagnostics_.set_enabled(enabled);
    runtime_.set_diagnostic_sink(enabled ? &diagnostics_ : nullptr);
  }
  void setup() override;
  void loop() override;
  float get_setup_priority() const override;

  TelemetrySubmitDisposition submit_telemetry_json(
      const std::string &telemetry_json,
      const std::string &boot_id,
      uint32_t seq);
  bool send_telemetry_json(
      const std::string &telemetry_json,
      const std::string &boot_id,
      uint32_t seq);

  bool provisioned() const { return pairing_client_.provisioned(); }
  bool runtime_ready() const { return runtime_ready_; }
  LocalPathState path_state() const { return runtime_.path_state(); }
  const N3wLabDiagnostics::LatencySnapshot &latency_diagnostics() const {
    return diagnostics_.latency_snapshot();
  }
  const std::string &hardware_id() const { return pairing_client_.hardware_id(); }
  const std::string &pairing_id() const { return pairing_client_.pairing_id(); }
  const std::string &node_id() const { return peer_state_.node_id; }
  std::string pairing_qr_payload() const { return pairing_client_.pairing_qr_payload(); }

  // EspNowEventSink. Receive and unicast-send completion work is copied into
  // bounded SPSC rings and processed from loop(), never from the high-priority
  // Wi-Fi callback.
  void on_espnow_receive(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size) override;
  void on_espnow_receive_with_metadata(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      const EspNowReceiveMetadata &metadata) override;
  void on_espnow_send_result(
      const MacAddress &destination,
      bool success) override;

  // SimpleProductPort.
  bool set_radio_channel(uint8_t channel) override;
  bool broadcast_control(const uint8_t *data, std::size_t size) override;
  bool broadcast_control_on_channel(
      uint8_t channel,
      const uint8_t *data,
      std::size_t size,
      uint32_t wait_time_ms) override {
    return radio_ownership_ == RadioOwnership::RELAY_ESPNOW &&
           radio_.send_broadcast_on_channel(
               channel, data, size, wait_time_ms) == DriverError::NONE;
  }
  bool install_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) override;
  bool remove_peer(const MacAddress &peer_mac) override;
  bool send_encrypted_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) override;
  uint8_t last_channel_observed() const override { return last_channel_observed_; }
  int32_t last_channel_error_raw() const override { return last_channel_error_raw_; }
  uint8_t last_broadcast_send_error_code() const override {
    return static_cast<uint8_t>(radio_.last_broadcast_send_error());
  }
  int32_t last_broadcast_send_error_raw() const override {
    return radio_.last_broadcast_send_error_raw();
  }
  bool publish_direct(const std::string &topic, const std::string &payload) override;
  bool publish_relay(const std::string &topic, const std::string &payload) override;

  // Clocks/randomness.
  uint64_t now_ms() const override;
  bool fill(uint8_t *data, std::size_t size) override;
  bool fill_pairing_random(uint8_t *data, std::size_t size) override;

  // Simplified bootstrap network.
  bool discover_manager(
      const std::string &request_json,
      std::string *response_json) override;
  bool post_json(
      const SimpleManagerCandidateV2 &candidate,
      const std::string &path,
      const std::string &request_json,
      int *status_code,
      std::string *response_json) override;
  bool post_json(
      const PendingPairingAckV2 &pending,
      const std::string &path,
      const std::string &request_json,
      int *status_code,
      std::string *response_json) override;

 protected:
  struct RxSlot {
    MacAddress source{};
    uint16_t size{0};
    uint8_t channel{0};
    std::array<uint8_t, kEspNowPhysicalDatagramLimit> data{};
  };

  struct TxCompletionSlot {
    MacAddress destination{};
    bool success{false};
  };

  enum class DirectPresenceProbeResult : uint8_t {
    FOUND = 0,
    NOT_FOUND,
    ERROR,
    RESTORE_FAILED,
  };

  struct BufferedTelemetry {
    std::string telemetry_json;
    std::string boot_id;
    uint32_t seq{0};
    uint8_t attempts{0};
  };

  bool read_local_mac_();
  bool load_runtime_state_();
  bool configure_mqtt_();
  bool start_runtime_if_ready_();
  bool derive_pmk_(LinkKey *pmk) const;
  void drain_send_completions_();
  void drain_radio_();
  void advance_pairing_();
  void advance_recovery_();
  bool claim_relay_radio_();
  bool begin_direct_probe_();
  bool prepare_direct_probe_radio_();
  void refresh_direct_ap_hint_();
  DirectPresenceProbeResult probe_direct_ap_presence_();
  void schedule_recovery_probe_(bool increase_backoff);
  void begin_relay_restore_();
  void advance_relay_restore_();
  bool restore_relay_radio_();
  bool enqueue_telemetry_(
      const std::string &telemetry_json,
      const std::string &boot_id,
      uint32_t seq);
  void flush_telemetry_queue_();
  bool http_post_(
      const std::string &host,
      uint16_t port,
      const std::string &path,
      const std::string &request_json,
      int *status_code,
      std::string *response_json);

  void begin_lab_diagnostic_boot_session_() {
    diagnostics_.begin_boot_session();
  }

  void bind_lab_diagnostic_boot_session_(uint64_t session, uint64_t uptime_ms) {
    diagnostics_.bind_boot_session(session, uptime_ms);
  }

  static constexpr std::size_t kRxRingSlots = 4;
  static constexpr std::size_t kTxCompletionRingSlots = 8;
  static constexpr uint32_t kPairingRetryMs = 5000;
  static constexpr uint32_t kRecoveryProbeMs = 2000;
  static constexpr uint32_t kRecoveryProbeWindowMs = 15000;
  static constexpr uint32_t kRecoveryProbeIntervalMs = 60000;
  static constexpr uint32_t kRecoveryProbeBackoffMaxMs = 480000;
  static constexpr uint32_t kDirectPresenceProbeQuietGuardMs = 500;
  static constexpr uint16_t kDirectPresenceProbePassiveMs = 120;
  static constexpr uint32_t kPendingUnicastDrainRetryMs = 25;
  static constexpr uint32_t kRelayRestoreRetryFastMs = 1000;
  static constexpr uint32_t kRelayRestoreRetrySlowMs = 5000;
  static constexpr uint8_t kRelayRestoreFastAttempts = 5;
  static constexpr std::size_t kTelemetryQueueCapacity = 8;
  static constexpr uint32_t kTelemetryFlushSpacingMs = 100;
  static constexpr uint32_t kTelemetryRetrySpacingMs = 500;
  static constexpr uint8_t kTelemetryMaxSendAttempts = 3;
  static constexpr uint32_t kInitialDirectGraceMs = 15000;
  static constexpr uint16_t kDiscoveryPort = 47111;

  bool activation_enabled_{false};
  bool runtime_state_loaded_{false};
  bool mqtt_configured_{false};
  bool runtime_ready_{false};
  bool radio_attempted_{false};
  bool runtime_start_grace_started_{false};
  uint64_t next_pairing_attempt_ms_{0};
  uint64_t next_recovery_probe_ms_{0};
  uint64_t direct_probe_deadline_ms_{0};
  uint64_t next_relay_restore_attempt_ms_{0};
  uint64_t next_telemetry_flush_ms_{0};
  uint64_t last_relay_telemetry_ms_{0};
  uint64_t last_radio_attempt_ms_{0};
  uint64_t runtime_start_grace_started_ms_{0};
  uint32_t recovery_probe_backoff_ms_{kRecoveryProbeIntervalMs};
  uint32_t telemetry_queue_dropped_{0};
  uint8_t relay_restore_attempts_{0};
  MacAddress local_mac_{};
  MacAddress direct_ap_bssid_{};
  bool direct_ap_bssid_valid_{false};
  uint8_t direct_ap_channel_{0};
  ProvisionedPeerStateV2 peer_state_{};
  ProvisionedBrokerStateV2 broker_state_{};
  EspNowDriver radio_{};
  RadioOwnership radio_ownership_{RadioOwnership::DIRECT_WIFI};
  uint8_t last_channel_observed_{0};
  int32_t last_channel_error_raw_{0};
  N3wLabDiagnostics diagnostics_{};
  SimpleProductRuntime runtime_;
  NvsSetupSecretStore setup_secret_store_{};
  NvsProvisionedPeerStoreV2 peer_store_{};
  NvsProvisionedBrokerStoreV2 broker_store_{};
  NvsPendingPairingAckStoreV2 ack_store_{};
  SimplePairingClient pairing_client_;
  std::deque<BufferedTelemetry> telemetry_queue_{};
  std::array<TxCompletionSlot, kTxCompletionRingSlots> tx_completion_ring_{};
  std::atomic<uint8_t> tx_completion_write_{0};
  std::atomic<uint8_t> tx_completion_read_{0};
  std::atomic<uint32_t> tx_completion_dropped_{0};
  std::array<RxSlot, kRxRingSlots> rx_ring_{};
  std::atomic<uint8_t> rx_write_{0};
  std::atomic<uint8_t> rx_read_{0};
  std::atomic<uint32_t> rx_dropped_{0};
};

}  // namespace esphome::greenhouse_n3w_core
