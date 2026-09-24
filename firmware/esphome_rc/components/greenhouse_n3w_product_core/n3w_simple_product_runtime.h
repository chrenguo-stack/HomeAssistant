#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "n3w_compact_telemetry.h"
#include "n3w_esp32_simple_nvs.h"
#include "n3w_radio.h"
#include "n3w_simple_runtime.h"

namespace esphome::greenhouse_n3w_core {

enum class SimpleProductError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  NOT_READY,
  RADIO_FAILED,
  MQTT_FAILED,
  CRYPTO_FAILED,
  PACKET_REJECTED,
  STATE_REJECTED,
};

enum class TelemetryPathAccounting : uint8_t {
  RECORD_PATH_RESULT = 0,
  TRANSPORT_ONLY,
};

struct TelemetryAdmissionPlan {
  bool record_direct_unavailable{false};
  TelemetryPathAccounting front_accounting{
      TelemetryPathAccounting::RECORD_PATH_RESULT};
};

TelemetryAdmissionPlan plan_business_telemetry_admission(
    LocalPathState path_state,
    bool direct_mqtt_available);

bool gateway_selection_local_fault_requires_restore(
    SimpleProductError result,
    bool selection_busy_before,
    bool selection_busy_after);

enum class SimpleProductStartMode : uint8_t {
  DIRECT = 0,
  DISCOVERY,
};

enum class DiscoveryScanStage : uint8_t {
  HINT = 0,
  FAST,
  FULL,
};

enum class DiscoveryRejectReason : uint8_t {
  NONE = 0,
  STATE_NOT_DISCOVERY = 1,
  PENDING_CHALLENGE = 2,
  PACKET_INVALID = 3,
  TRUST_GENERATION_MISMATCH = 4,
  SELF_RELAY = 5,
  CHANNEL_MISMATCH = 6,
  IDENTITY_CONFLICT = 7,
  RSSI_INVALID = 8,
  SELECTION_FROZEN = 9,
  CANDIDATE_CAPACITY = 10,
};

struct DirectRecoveryCommitResult {
  SimpleProductError error{SimpleProductError::NONE};
  uint64_t completed_at_ms{0};
  bool committed{false};
};

struct SimpleProductPolicy {
  LocalPathPolicy path{};
  std::vector<uint8_t> allowed_channels{1, 6, 11};
  uint32_t scan_dwell_ms{250};
  uint32_t fast_search_budget_ms{6500};
  uint32_t full_scan_dwell_ms{2250};
  uint32_t full_scan_schedule_margin_ms{2000};
  uint32_t full_handshake_max_ms{24000};
  uint32_t full_scan_total_max_ms{60000};
  uint32_t challenge_timeout_ms{1500};
  uint32_t relay_advertisement_interval_ms{2000};
  uint32_t candidate_window_ms{6500};
  uint32_t gateway_selection_transaction_max_ms{30000};
  std::size_t max_gateway_candidates{8};
  std::size_t max_relay_children{8};

  bool valid() const;
};

class SimpleProductClock {
 public:
  virtual ~SimpleProductClock() = default;
  virtual uint64_t now_ms() const = 0;
};

class SimpleProductRandom {
 public:
  virtual ~SimpleProductRandom() = default;
  virtual bool fill(uint8_t *data, std::size_t size) = 0;
};

class SimpleProductPort {
 public:
  virtual ~SimpleProductPort() = default;
  virtual bool set_radio_channel(uint8_t channel) = 0;
  virtual bool current_legal_channels(std::vector<uint8_t> *channels) = 0;
  virtual bool broadcast_control(const uint8_t *data, std::size_t size) = 0;
  virtual bool broadcast_control_on_channel(
      uint8_t channel,
      const uint8_t *data,
      std::size_t size,
      uint32_t wait_time_ms) {
    (void) channel;
    (void) wait_time_ms;
    return broadcast_control(data, size);
  }
  virtual bool install_encrypted_peer(
      const MacAddress &peer_mac,
      const LinkKey &lmk,
      uint8_t channel) = 0;
  virtual bool remove_peer(const MacAddress &peer_mac) = 0;
  virtual bool send_encrypted_peer(
      const MacAddress &peer_mac,
      const uint8_t *data,
      std::size_t size) = 0;
  virtual uint8_t last_channel_observed() const { return 0; }
  virtual int32_t last_channel_error_raw() const { return 0; }
  virtual uint8_t last_broadcast_send_error_code() const { return 0; }
  virtual int32_t last_broadcast_send_error_raw() const { return 0; }
  virtual bool publish_direct(const std::string &topic, const std::string &payload) = 0;
  virtual bool publish_relay(const std::string &topic, const std::string &payload) = 0;
};

struct SimpleProductRelayPeer {
  std::string node_id;
  MacAddress mac{};
  LinkKey lmk{};
  uint8_t channel{0};

  bool valid() const;
};

class SimpleProductDiagnosticSink {
 public:
  virtual ~SimpleProductDiagnosticSink() = default;
  virtual void on_runtime_start(uint8_t mode, uint8_t path_state) = 0;
  virtual void on_scan_attempt(uint8_t requested, uint64_t now_ms) = 0;
  virtual void on_scan_result(
      uint8_t requested,
      bool success,
      uint8_t observed,
      int32_t raw_error,
      uint64_t now_ms) = 0;
  virtual void on_direct_path_result(bool success, uint64_t now_ms) {
    (void) success;
    (void) now_ms;
  }
  virtual void on_discovery_enter(uint64_t now_ms) {
    (void) now_ms;
  }
  virtual void on_discovery_rx(bool accepted, uint64_t now_ms) = 0;
  virtual void on_discovery_rejected(
      DiscoveryRejectReason reason,
      uint8_t packet_channel,
      uint8_t rx_channel,
      uint64_t now_ms) {
    (void) reason;
    (void) packet_channel;
    (void) rx_channel;
    (void) now_ms;
  }
  virtual void on_challenge_tx(bool success, uint64_t now_ms) = 0;
  virtual void on_challenge_submit_result(
      bool attempted,
      bool success,
      uint8_t driver_error,
      int32_t raw_error,
      uint64_t now_ms) {
    (void) attempted;
    (void) success;
    (void) driver_error;
    (void) raw_error;
    (void) now_ms;
  }
  virtual void on_challenge_rx(bool verified, uint64_t now_ms) = 0;
  virtual void on_accept_tx(bool success, uint64_t now_ms) = 0;
  virtual void on_accept_rx(bool verified, uint64_t now_ms) = 0;
  virtual void on_relay_active(uint64_t now_ms) = 0;
  virtual void on_relay_telemetry(bool success, uint64_t now_ms) = 0;
  virtual void on_relay_advertisement(bool submitted, uint64_t now_ms) = 0;
  virtual void on_broadcast_completion(bool success, uint64_t now_ms) = 0;
  // Send callbacks run from the Wi-Fi task. Implementations must only enqueue
  // atomic state here; durable persistence belongs to the normal loop.
  virtual void on_unicast_completion(bool success, uint64_t now_ms) {
    (void) success;
    (void) now_ms;
  }
  virtual void on_compact_rx(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_state_rejected(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_child_binding_failure(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_decode(bool success, uint64_t now_ms) {
    (void) success;
    (void) now_ms;
  }
  virtual void on_compact_wrap_failure(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_forward_attempt(uint64_t now_ms) { (void) now_ms; }
  virtual void on_compact_forward_submit(bool success, uint64_t now_ms) {
    (void) success;
    (void) now_ms;
  }
};

class SimpleProductRuntime {
 public:
  SimpleProductRuntime(
      SimpleProductPort *port,
      SimpleProductClock *clock,
      SimpleProductRandom *random,
      SimpleProductPolicy policy = {});

  SimpleProductError start(
      const ProvisionedPeerStateV2 &state,
      const MacAddress &local_mac,
      uint8_t direct_channel,
      SimpleProductStartMode start_mode = SimpleProductStartMode::DIRECT);
  void stop();
  SimpleProductError tick();

  SimpleProductError note_direct_result(bool success);
  SimpleProductError note_direct_recovery_probe(bool success);
  DirectRecoveryCommitResult commit_direct_recovery_before(
      uint64_t absolute_deadline_ms);
  SimpleProductError note_relay_delivery_result(
      const MacAddress &destination,
      bool success);
  // Reinstalls the channel and encrypted peer after a bounded Direct recovery
  // probe temporarily handed the single radio back to ESPHome Wi-Fi.
  SimpleProductError rebind_radio_state();
  SimpleProductError reset_to_discovery_after_radio_fault();
  bool update_direct_channel_hint(uint8_t channel);
  SimpleProductError send_telemetry(
      const std::string &telemetry_json,
      const std::string &boot_id,
      uint32_t seq,
      TelemetryPathAccounting accounting =
          TelemetryPathAccounting::RECORD_PATH_RESULT);

  SimpleProductError on_radio_receive(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size,
      uint8_t channel,
      int16_t rssi_dbm);

  void set_relay_capable(bool value) { relay_capable_ = value; }
  void set_diagnostic_sink(SimpleProductDiagnosticSink *sink) {
    diagnostic_sink_ = sink;
  }
  bool started() const { return started_; }
  LocalPathState path_state() const { return path_.state(); }
  uint8_t direct_channel_hint() const { return direct_channel_; }
  uint8_t working_channel() const;
  const std::optional<SimpleProductRelayPeer> &active_relay() const {
    return active_relay_;
  }
  bool challenge_pending() const { return pending_challenge_.has_value(); }
  bool gateway_selection_busy() const {
    return full_scan_in_progress_ ||
           gateway_selection_epoch_.has_value() ||
           pending_challenge_.has_value();
  }
  bool discovery_radio_ready() const { return discovery_radio_ready_; }
  DiscoveryScanStage discovery_scan_stage() const {
    return discovery_scan_stage_;
  }
  uint8_t cached_gateway_channel() const { return cached_gateway_channel_; }
  std::size_t legal_channel_count() const { return legal_channels_.size(); }
  std::size_t relay_child_count() const { return relay_children_.size(); }
  const ProvisionedPeerStateV2 &provisioned_state() const { return state_; }

 private:
  friend struct SimpleProductRelayPeer;

  struct PendingChallenge {
    std::string relay_node_id;
    MacAddress relay_mac{};
    HandshakeNonce challenge_nonce{};
    uint8_t channel{0};
    uint64_t expires_at_ms{0};
  };

  struct RelayCandidate {
    std::string relay_node_id;
    MacAddress mac{};
    uint8_t channel{0};
    int64_t rssi_sum{0};
    uint32_t rssi_sample_count{0};
    uint64_t first_seen_ms{0};
    uint64_t last_seen_ms{0};
    bool attempted{false};
  };

  struct GatewaySelectionEpoch {
    std::vector<RelayCandidate> candidates{};
    uint64_t deadline_ms{0};
    uint64_t transaction_deadline_ms{0};
    bool frozen{false};
    bool full_scan_collection{false};
  };

  SimpleProductError begin_discovery_();
  SimpleProductError refresh_legal_channels_();
  SimpleProductError start_fast_scan_(uint64_t now_ms, bool preserve_selection);
  SimpleProductError start_full_scan_(uint64_t now_ms, bool preserve_selection);
  SimpleProductError finish_full_scan_(uint64_t now_ms);
  SimpleProductError set_scan_channel_(
      uint8_t channel,
      uint32_t dwell_ms,
      uint64_t now_ms);
  bool legal_channel_(uint8_t channel) const;
  bool fast_channel_(uint8_t channel) const;
  SimpleProductError leave_relay_for_discovery_();
  SimpleProductError restore_direct_();
  SimpleProductError handle_discovery_(
      const MacAddress &source,
      const SimpleRelayDiscovery &packet,
      uint8_t channel,
      int16_t rssi_dbm);
  void clear_gateway_selection_();
  SimpleProductError add_or_update_gateway_candidate_(
      const MacAddress &source,
      const SimpleRelayDiscovery &packet,
      uint8_t channel,
      int16_t rssi_dbm,
      uint64_t now_ms);
  SimpleProductError attempt_next_gateway_candidate_();
  SimpleProductError start_challenge_for_candidate_(
      const RelayCandidate &candidate);
  SimpleProductError select_next_gateway_candidate_(
      std::size_t *candidate_index) const;
  RelayCandidate *find_gateway_candidate_by_node_(
      const std::string &relay_node_id);
  RelayCandidate *find_gateway_candidate_by_mac_(const MacAddress &mac);
  static bool valid_discovery_rssi_(int16_t rssi_dbm);
  SimpleProductError handle_challenge_(
      const MacAddress &source,
      const SimplePeerChallenge &packet,
      uint8_t channel);
  SimpleProductError handle_accept_(
      const MacAddress &source,
      const SimplePeerAccept &packet,
      uint8_t channel);
  SimpleProductError handle_compact_(
      const MacAddress &source,
      const uint8_t *data,
      std::size_t size);
  SimpleProductError maybe_advertise_relay_(uint64_t now_ms);
  SimpleProductError maybe_advance_scan_(uint64_t now_ms);
  SimpleProductRelayPeer *find_relay_child_(const MacAddress &mac);
  bool fill_nonce_(HandshakeNonce *nonce);
  static bool valid_unicast_mac_(const MacAddress &mac);
  static LinkKey as_link_key_(const SimpleLmk &lmk);

  SimpleProductPort *port_{nullptr};
  SimpleProductClock *clock_{nullptr};
  SimpleProductRandom *random_{nullptr};
  SimpleProductPolicy policy_{};
  LocalPathController path_;
  ChannelScanPlan scan_{};
  ProvisionedPeerStateV2 state_{};
  SystemPeerCredentialV2 peer_credential_{};
  ApplicationKeyState application_key_{};
  PeerEndpointV2 local_endpoint_{};
  HandshakeNonce local_boot_nonce_{};
  uint8_t direct_channel_{0};
  uint8_t cached_gateway_channel_{0};
  DiscoveryScanStage discovery_scan_stage_{DiscoveryScanStage::HINT};
  std::vector<uint8_t> legal_channels_{};
  uint64_t next_scan_switch_ms_{0};
  uint64_t fast_search_deadline_ms_{0};
  uint64_t full_scan_started_ms_{0};
  uint64_t full_scan_hard_deadline_ms_{0};
  uint64_t full_scan_total_deadline_ms_{0};
  uint64_t next_advertisement_ms_{0};
  bool full_scan_in_progress_{false};
  bool discovery_radio_ready_{false};
  bool started_{false};
  bool relay_capable_{true};
  std::optional<PendingChallenge> pending_challenge_{};
  std::optional<GatewaySelectionEpoch> gateway_selection_epoch_{};
  std::optional<SimpleProductRelayPeer> active_relay_{};
  std::vector<SimpleProductRelayPeer> relay_children_{};
  SimpleProductDiagnosticSink *diagnostic_sink_{nullptr};
};

}  // namespace esphome::greenhouse_n3w_core
