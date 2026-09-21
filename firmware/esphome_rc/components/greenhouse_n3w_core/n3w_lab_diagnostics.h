#pragma once

#include <atomic>
#include <cstdint>

#include "n3w_simple_product_runtime.h"

namespace esphome::greenhouse_n3w_core {

#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB

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

  // Per-boot Direct -> Relay timing observability.
  // These fields are RAM-only and intentionally do not change the persisted
  // gh_n3w_diag/snapshot schema.
  struct LatencySnapshot {
    uint64_t wifi_down_ms{0};
    uint64_t mqtt_down_ms{0};
    uint64_t direct_fail_first_ms{0};
    uint32_t direct_fail_count{0};
    uint64_t discovery_enter_ms{0};
    uint64_t first_scan_ms{0};
    uint64_t relay_ad_seen_ms{0};
    uint64_t challenge_tx_ms{0};
    uint32_t challenge_submit_failure_count{0};
    uint8_t challenge_submit_first_driver_error{0};
    uint8_t challenge_submit_last_driver_error{0};
    int32_t challenge_submit_first_error_raw{0};
    int32_t challenge_submit_last_error_raw{0};
    uint64_t accept_rx_ms{0};
    uint64_t relay_active_ms{0};
    uint64_t first_relay_tx_ms{0};

    // Lab-only synchronous encrypted-unicast submission evidence. This is kept
    // RAM-only so diagnosing radio channel ownership does not revise or churn
    // the durable NVS diagnostic schema.
    uint32_t unicast_submit_success_count{0};
    uint32_t unicast_submit_failure_count{0};
    uint8_t unicast_submit_first_failure_driver_error{0};
    int32_t unicast_submit_first_failure_error_raw{0};
    uint8_t unicast_submit_first_failure_current_channel{0};
    uint8_t unicast_submit_first_failure_peer_channel{0};
    uint8_t unicast_submit_first_success_current_channel{0};
    uint8_t unicast_submit_first_success_peer_channel{0};

    uint32_t presence_probe_count{0};
    uint32_t presence_probe_found_count{0};
    uint8_t presence_probe_last_result{0xffU};
    uint64_t presence_probe_last_start_ms{0};
    uint32_t presence_probe_last_duration_ms{0};
    uint32_t full_verify_count{0};
    uint64_t full_verify_last_start_ms{0};
    uint8_t full_verify_last_trigger{0};
    uint8_t full_verify_last_terminal_reason{0};
    uint8_t relay_restore_last_cause{0};
    uint8_t relay_restore_last_result{0};
    uint32_t recovery_probe_deferral_count{0};
    uint8_t recovery_probe_last_deferral_reason{0};
    uint64_t next_presence_probe_ms{0};
    uint64_t next_full_verify_ms{0};
    uint8_t full_verify_queue_depth_start{0};
    uint8_t full_verify_queue_depth_end{0};
    uint32_t full_verify_queue_dropped_start{0};
    uint32_t full_verify_queue_dropped_end{0};
    uint32_t full_verify_attempt_failed_dropped_start{0};
    uint32_t full_verify_attempt_failed_dropped_end{0};
  };

  void set_enabled(bool enabled) { enabled_ = enabled; }
  bool enabled() const { return enabled_; }
  void begin_boot_session();
  void bind_boot_session(uint64_t session, uint64_t uptime_ms);
  bool boot_session_bound() const { return boot_session_bound_; }
  uint32_t persist_count() const { return persist_count_; }
  const Snapshot &snapshot() const { return snapshot_; }
  const LatencySnapshot &latency_snapshot() const { return latency_; }

  void observe_connectivity(
      bool wifi_connected,
      bool mqtt_connected,
      uint64_t now_ms);
  // Legacy storage method name; these counters now represent logical Direct
  // path-health observations that participate in failover hysteresis,
  // including a new business sample with no MQTT transport opportunity.
  void note_direct_publish_result(bool success, uint64_t now_ms);
  void note_discovery_enter(uint64_t now_ms);

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
  void note_unicast_submit(
      bool success,
      uint8_t driver_error,
      int32_t raw_error,
      uint8_t current_channel,
      uint8_t peer_channel,
      uint64_t now_ms) {
    (void) now_ms;
    if (!enabled_ || !boot_session_started_) return;

    if (success) {
      if (latency_.unicast_submit_success_count == 0) {
        latency_.unicast_submit_first_success_current_channel = current_channel;
        latency_.unicast_submit_first_success_peer_channel = peer_channel;
      }
      if (latency_.unicast_submit_success_count < 0xffffffffU) {
        ++latency_.unicast_submit_success_count;
      }
      return;
    }

    if (latency_.unicast_submit_failure_count == 0) {
      latency_.unicast_submit_first_failure_driver_error = driver_error;
      latency_.unicast_submit_first_failure_error_raw = raw_error;
      latency_.unicast_submit_first_failure_current_channel = current_channel;
      latency_.unicast_submit_first_failure_peer_channel = peer_channel;
    }
    if (latency_.unicast_submit_failure_count < 0xffffffffU) {
      ++latency_.unicast_submit_failure_count;
    }
  }
  void note_presence_probe(
      uint64_t start_ms,
      uint32_t duration_ms,
      uint8_t result) {
    if (!enabled_ || !boot_session_started_) return;
    if (latency_.presence_probe_count < 0xffffffffU) {
      ++latency_.presence_probe_count;
    }
    if (result == 0U &&
        latency_.presence_probe_found_count < 0xffffffffU) {
      ++latency_.presence_probe_found_count;
    }
    latency_.presence_probe_last_result = result;
    latency_.presence_probe_last_start_ms = start_ms;
    latency_.presence_probe_last_duration_ms = duration_ms;
  }
  void note_full_verify_start(
      uint8_t trigger,
      uint64_t now_ms,
      uint8_t queue_depth,
      uint32_t queue_dropped,
      uint32_t attempt_failed_dropped) {
    if (!enabled_ || !boot_session_started_) return;
    if (latency_.full_verify_count < 0xffffffffU) {
      ++latency_.full_verify_count;
    }
    latency_.full_verify_last_start_ms = now_ms;
    latency_.full_verify_last_trigger = trigger;
    latency_.full_verify_queue_depth_start = queue_depth;
    latency_.full_verify_queue_dropped_start = queue_dropped;
    latency_.full_verify_attempt_failed_dropped_start =
        attempt_failed_dropped;
  }
  void note_full_verify_terminal(
      uint8_t terminal_reason,
      uint8_t queue_depth,
      uint32_t queue_dropped,
      uint32_t attempt_failed_dropped) {
    if (!enabled_ || !boot_session_started_) return;
    latency_.full_verify_last_terminal_reason = terminal_reason;
    latency_.full_verify_queue_depth_end = queue_depth;
    latency_.full_verify_queue_dropped_end = queue_dropped;
    latency_.full_verify_attempt_failed_dropped_end =
        attempt_failed_dropped;
  }
  // Relay restore result: 0=started/none, 1=success, 2=retrying after
  // concrete restore failure, 3=restore budget exhausted.
  void note_relay_restore(uint8_t cause, uint8_t result) {
    if (!enabled_ || !boot_session_started_) return;
    latency_.relay_restore_last_cause = cause;
    latency_.relay_restore_last_result = result;
  }
  void note_recovery_probe_deferral(uint8_t reason) {
    if (!enabled_ || !boot_session_started_) return;
    if (latency_.recovery_probe_deferral_count < 0xffffffffU) {
      ++latency_.recovery_probe_deferral_count;
    }
    latency_.recovery_probe_last_deferral_reason = reason;
  }
  void note_recovery_schedule(
      uint64_t next_presence_ms,
      uint64_t next_full_verify_ms) {
    if (!enabled_ || !boot_session_started_) return;
    latency_.next_presence_probe_ms = next_presence_ms;
    latency_.next_full_verify_ms = next_full_verify_ms;
  }

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
  void on_direct_path_result(bool success, uint64_t now_ms) override {
    note_direct_publish_result(success, now_ms);
  }
  void on_discovery_enter(uint64_t now_ms) override {
    note_discovery_enter(now_ms);
  }
  void on_discovery_rx(bool accepted, uint64_t now_ms) override;
  void on_discovery_rejected(
      DiscoveryRejectReason reason,
      uint8_t packet_channel,
      uint8_t rx_channel,
      uint64_t now_ms) override;
  void on_challenge_tx(bool success, uint64_t now_ms) override;
  void on_challenge_submit_result(
      bool attempted,
      bool success,
      uint8_t driver_error,
      int32_t raw_error,
      uint64_t now_ms) override;
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
  LatencySnapshot latency_{};
  bool wifi_seen_up_{false};
  bool mqtt_seen_up_{false};
  std::atomic<uint32_t> pending_broadcast_success_{0};
  std::atomic<uint32_t> pending_broadcast_failure_{0};
  std::atomic<uint32_t> pending_unicast_success_{0};
  std::atomic<uint32_t> pending_unicast_failure_{0};
  Snapshot snapshot_{};
};

static_assert(sizeof(N3wLabDiagnostics::Snapshot) < 512U);

#else

// Production build stub. The Phase-4 diagnostic implementation is not linked
// unless GREENHOUSE_N3W_ENABLE_PHASE4_LAB is explicitly enabled by a lab target.
class N3wLabDiagnostics {
 public:
  struct LatencySnapshot {};

  void set_enabled(bool) {}
  bool enabled() const { return false; }
  void begin_boot_session() {}
  void bind_boot_session(uint64_t, uint64_t) {}
  const LatencySnapshot &latency_snapshot() const { return latency_; }

  template<typename... Args> void observe_connectivity(Args &&...) {}
  template<typename... Args> void observe_runtime(Args &&...) {}
  template<typename... Args> void emit_summary(Args &&...) {}
  template<typename... Args> void note_recovery_schedule(Args &&...) {}
  template<typename... Args> void note_recovery_probe_deferral(Args &&...) {}
  template<typename... Args> void note_presence_probe(Args &&...) {}
  template<typename... Args> void note_full_verify_terminal(Args &&...) {}
  template<typename... Args> void note_full_verify_start(Args &&...) {}
  template<typename... Args> void note_channel_result(Args &&...) {}
  template<typename... Args> void note_relay_restore(Args &&...) {}
  template<typename... Args> void note_rx_dropped(Args &&...) {}
  template<typename... Args> void on_broadcast_completion(Args &&...) {}
  template<typename... Args> void on_unicast_completion(Args &&...) {}
  template<typename... Args> void note_peer_install(Args &&...) {}
  template<typename... Args> void note_unicast_submit(Args &&...) {}

 private:
  LatencySnapshot latency_{};
};

#endif  // GREENHOUSE_N3W_ENABLE_PHASE4_LAB

}  // namespace esphome::greenhouse_n3w_core
