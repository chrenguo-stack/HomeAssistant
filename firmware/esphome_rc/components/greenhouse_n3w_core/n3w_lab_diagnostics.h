#pragma once

#include <atomic>
#include <cstdint>

#include "n3w_simple_product_runtime.h"

namespace esphome::greenhouse_n3w_core {

class N3wLabDiagnostics final : public SimpleProductDiagnosticSink {
 public:
  static constexpr uint32_t kMagic = 0x4e335744U;
  static constexpr uint16_t kSchemaVersion = 5U;
  static constexpr char kNamespace[] = "gh_n3w_diag";
  static constexpr char kKey[] = "snapshot";

#pragma pack(push, 1)
  struct Snapshot {
    uint32_t magic{kMagic};
    uint16_t schema_version{kSchemaVersion};
    uint16_t size{sizeof(Snapshot)};
    uint64_t boot_session{0};
    uint64_t snapshot_uptime_ms{0};
    uint8_t runtime_start_mode{0};
    uint8_t path_state{0};
    uint8_t current_channel{0};
    uint8_t direct_channel_hint{0};
    uint8_t last_requested_channel{0};
    uint8_t last_observed_channel{0};
    uint8_t reserved[1]{0};
    uint32_t scan_attempts{0};
    uint32_t scan_successes{0};
    uint32_t scan_failures{0};
    uint32_t channel_set_attempts{0};
    uint32_t channel_set_successes{0};
    uint32_t channel_set_failures{0};
    uint32_t channel_attempts[3]{0, 0, 0};
    uint32_t channel_successes[3]{0, 0, 0};
    uint32_t channel_failures[3]{0, 0, 0};
    int32_t last_driver_error_raw{0};
    uint32_t discovery_rx{0};
    uint32_t discovery_rejected{0};
    uint32_t challenge_tx{0};
    uint32_t challenge_tx_success{0};
    uint32_t challenge_rx{0};
    uint32_t challenge_verify{0};
    uint32_t accept_tx{0};
    uint32_t accept_tx_success{0};
    uint32_t accept_rx{0};
    uint32_t accept_verify{0};
    uint32_t peer_install_attempts{0};
    uint32_t peer_install_success{0};
    uint32_t relay_active_count{0};
    uint32_t relay_telemetry_attempts{0};
    uint32_t relay_telemetry_success{0};
    uint32_t rx_dropped{0};
    uint32_t relay_advertisement_attempts{0};
    uint32_t relay_advertisement_submit_success{0};
    uint32_t relay_advertisement_submit_failure{0};
    uint32_t broadcast_completion_count{0};
    uint32_t broadcast_completion_success{0};
    uint32_t broadcast_completion_failure{0};
    uint32_t discovery_reject_state{0};
    uint32_t discovery_reject_pending{0};
    uint32_t discovery_reject_packet_invalid{0};
    uint32_t discovery_reject_trust_generation{0};
    uint32_t discovery_reject_self{0};
    uint32_t discovery_reject_channel_mismatch{0};
    uint8_t last_discovery_rejection_reason{0};
    uint8_t last_discovery_packet_channel{0};
    uint8_t last_discovery_rx_channel{0};
    // v5 fields are appended so the v4 binary prefix remains unchanged.
    uint32_t unicast_completion_count{0};
    uint32_t unicast_completion_success{0};
    uint32_t unicast_completion_failure{0};
    uint32_t compact_rx_count{0};
    uint32_t compact_state_reject_count{0};
    uint32_t compact_child_binding_failure{0};
    uint32_t compact_decode_success{0};
    uint32_t compact_decode_failure{0};
    uint32_t compact_wrap_failure{0};
    uint32_t compact_forward_attempts{0};
    uint32_t compact_forward_submit_success{0};
    uint32_t compact_forward_submit_failure{0};
  };
#pragma pack(pop)

  void set_enabled(bool enabled) { enabled_ = enabled; }
  bool enabled() const { return enabled_; }
  void begin_boot_session();
  void bind_boot_session(uint64_t session, uint64_t uptime_ms);
  bool boot_session_bound() const { return boot_session_bound_; }
  uint32_t persist_count() const { return persist_count_; }
  const Snapshot &snapshot() const { return snapshot_; }

  void note_channel_set_result(
      uint8_t requested,
      bool success,
      uint8_t observed,
      int32_t raw_error,
      uint64_t now_ms);
  void note_channel_result(
      uint8_t requested,
      bool success,
      uint8_t observed,
      int32_t raw_error,
      uint64_t now_ms);
  void observe_runtime(
      uint8_t path_state,
      uint8_t current_channel,
      uint8_t direct_channel_hint,
      uint32_t relay_children,
      bool relay_active,
      uint64_t now_ms);
  void note_peer_install(bool success, uint64_t now_ms);
  void note_rx_dropped(uint64_t now_ms);
  void note_relay_telemetry(bool success, uint64_t now_ms);
  void emit_summary(uint64_t now_ms);

  // SimpleProductDiagnosticSink.
  void on_runtime_start(uint8_t mode, uint8_t path_state) override;
  void on_scan_attempt(uint8_t requested, uint64_t now_ms) override;
  void on_scan_result(
      uint8_t requested,
      bool success,
      uint8_t observed,
      int32_t raw_error,
      uint64_t now_ms) override;
  void on_discovery_rx(bool accepted, uint64_t now_ms) override;
  void on_discovery_rejected(
      DiscoveryRejectReason reason,
      uint8_t packet_channel,
      uint8_t rx_channel,
      uint64_t now_ms) override;
  void on_challenge_tx(bool success, uint64_t now_ms) override;
  void on_challenge_rx(bool verified, uint64_t now_ms) override;
  void on_accept_tx(bool success, uint64_t now_ms) override;
  void on_accept_rx(bool verified, uint64_t now_ms) override;
  void on_relay_active(uint64_t now_ms) override;
  void on_relay_telemetry(bool success, uint64_t now_ms) override;
  void on_relay_advertisement(bool submitted, uint64_t now_ms) override;
  void on_broadcast_completion(bool success, uint64_t now_ms) override;
  void on_unicast_completion(bool success, uint64_t now_ms) override;
  void on_compact_rx(uint64_t now_ms) override;
  void on_compact_state_rejected(uint64_t now_ms) override;
  void on_compact_child_binding_failure(uint64_t now_ms) override;
  void on_compact_decode(bool success, uint64_t now_ms) override;
  void on_compact_wrap_failure(uint64_t now_ms) override;
  void on_compact_forward_attempt(uint64_t now_ms) override;
  void on_compact_forward_submit(bool success, uint64_t now_ms) override;

 private:
  void persist_(uint64_t now_ms, bool force);
  void mark_(uint64_t now_ms, bool force);
  void drain_broadcast_completions_(uint64_t now_ms);
  void drain_unicast_completions_(uint64_t now_ms);
  static int channel_slot_(uint8_t channel);

  bool enabled_{false};
  bool boot_session_started_{false};
  bool boot_session_bound_{false};
  bool dirty_{false};
  uint64_t last_persist_ms_{0};
  uint64_t next_summary_ms_{0};
  uint32_t persist_count_{0};
  uint32_t relay_children_{0};
  bool relay_active_{false};
  std::atomic<uint32_t> pending_broadcast_success_{0};
  std::atomic<uint32_t> pending_broadcast_failure_{0};
  std::atomic<uint32_t> pending_unicast_success_{0};
  std::atomic<uint32_t> pending_unicast_failure_{0};
  Snapshot snapshot_{};
};

static_assert(sizeof(N3wLabDiagnostics::Snapshot) < 512U);

}  // namespace esphome::greenhouse_n3w_core
