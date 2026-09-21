#include "n3w_lab_diagnostics.h"

#ifdef GREENHOUSE_N3W_ENABLE_PHASE4_LAB

#include "esphome/core/log.h"

#ifdef USE_ESP32
#include "nvs.h"
#endif

namespace esphome::greenhouse_n3w_core {
namespace {

static const char *const TAG = "gh_n3w_diag";
constexpr uint64_t kPersistIntervalMs = 5000;
constexpr uint64_t kSummaryIntervalMs = 10000;

}  // namespace

int N3wLabDiagnostics::channel_slot_(uint8_t channel) {
  if (channel == 1U) return 0;
  if (channel == 6U) return 1;
  if (channel == 11U) return 2;
  return -1;
}

void N3wLabDiagnostics::begin_boot_session() {
  if (!enabled_) return;
  snapshot_ = Snapshot{};
  snapshot_.size = sizeof(Snapshot);
  boot_session_started_ = true;
  boot_session_bound_ = false;
  dirty_ = true;
  last_persist_ms_ = 0;
  next_summary_ms_ = 0;
  persist_count_ = 0;
  relay_children_ = 0;
  relay_active_ = false;
  latency_ = LatencySnapshot{};
  wifi_seen_up_ = false;
  mqtt_seen_up_ = false;
  pending_broadcast_success_.store(0, std::memory_order_relaxed);
  pending_broadcast_failure_.store(0, std::memory_order_relaxed);
  pending_unicast_success_.store(0, std::memory_order_relaxed);
  pending_unicast_failure_.store(0, std::memory_order_relaxed);
}

void N3wLabDiagnostics::bind_boot_session(uint64_t session, uint64_t uptime_ms) {
  if (!enabled_ || !boot_session_started_ || session == 0) return;
  const bool new_binding = !boot_session_bound_ || snapshot_.boot_session != session;
  boot_session_bound_ = true;
  snapshot_.boot_session = session;
  snapshot_.snapshot_uptime_ms = uptime_ms;
  mark_(uptime_ms, new_binding);
}

void N3wLabDiagnostics::mark_(uint64_t now_ms, bool force) {
  if (!enabled_ || !boot_session_started_) return;
  dirty_ = true;
  if (boot_session_bound_) snapshot_.snapshot_uptime_ms = now_ms;
  persist_(now_ms, force);
}

void N3wLabDiagnostics::persist_(uint64_t now_ms, bool force) {
  if (!enabled_ || !boot_session_started_ || !boot_session_bound_ || !dirty_ ||
      (!force && now_ms - last_persist_ms_ < kPersistIntervalMs)) {
    return;
  }
#ifdef USE_ESP32
  nvs_handle_t handle = 0;
  if (nvs_open(kNamespace, NVS_READWRITE, &handle) != ESP_OK) return;
  const esp_err_t result =
      nvs_set_blob(handle, kKey, &snapshot_, sizeof(snapshot_)) == ESP_OK
          ? nvs_commit(handle)
          : ESP_FAIL;
  nvs_close(handle);
  if (result != ESP_OK) return;
#endif
  last_persist_ms_ = now_ms;
  dirty_ = false;
  ++persist_count_;
}

void N3wLabDiagnostics::observe_connectivity(
    bool wifi_connected,
    bool mqtt_connected,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;

  if (wifi_connected) {
    wifi_seen_up_ = true;
  } else if (wifi_seen_up_ && latency_.wifi_down_ms == 0) {
    latency_.wifi_down_ms = now_ms;
  }

  if (mqtt_connected) {
    mqtt_seen_up_ = true;
  } else if (mqtt_seen_up_ && latency_.mqtt_down_ms == 0) {
    latency_.mqtt_down_ms = now_ms;
  }
}

void N3wLabDiagnostics::note_direct_publish_result(
    bool success,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;

  if (success) {
    latency_.direct_fail_first_ms = 0;
    latency_.direct_fail_count = 0;
    return;
  }

  if (latency_.direct_fail_count == 0) {
    latency_.direct_fail_first_ms = now_ms;
  }
  if (latency_.direct_fail_count < 0xffffffffU) {
    ++latency_.direct_fail_count;
  }
}

void N3wLabDiagnostics::note_discovery_enter(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  if (latency_.discovery_enter_ms == 0) {
    latency_.discovery_enter_ms = now_ms;
  }
}

void N3wLabDiagnostics::note_channel_result(
    uint8_t requested,
    bool success,
    uint8_t observed,
    int32_t raw_error,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  // current_channel is an observation oracle. A failed/unknown readback must
  // remain 0 rather than being replaced by the requested channel.
  snapshot_.current_channel = observed;
  snapshot_.last_requested_channel = requested;
  snapshot_.last_observed_channel = observed;
  snapshot_.last_driver_error_raw = raw_error;
  ++snapshot_.channel_set_attempts;
  if (success) {
    ++snapshot_.channel_set_successes;
  } else {
    ++snapshot_.channel_set_failures;
  }
  mark_(now_ms, false);
}

void N3wLabDiagnostics::note_channel_set_result(
    uint8_t requested,
    bool success,
    uint8_t observed,
    int32_t raw_error,
    uint64_t now_ms) {
  note_channel_result(requested, success, observed, raw_error, now_ms);
}

void N3wLabDiagnostics::on_scan_attempt(uint8_t requested, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  if (latency_.first_scan_ms == 0) latency_.first_scan_ms = now_ms;
  snapshot_.last_requested_channel = requested;
  ++snapshot_.scan_attempts;
  const int slot = channel_slot_(requested);
  if (slot >= 0) ++snapshot_.channel_attempts[slot];
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_scan_result(
    uint8_t requested,
    bool success,
    uint8_t observed,
    int32_t raw_error,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  // current_channel is an observation oracle. A failed/unknown readback must
  // remain 0 rather than being replaced by the requested channel.
  snapshot_.current_channel = observed;
  snapshot_.last_requested_channel = requested;
  snapshot_.last_observed_channel = observed;
  snapshot_.last_driver_error_raw = raw_error;
  const int slot = channel_slot_(requested);
  if (slot >= 0) {
    if (success) {
      ++snapshot_.channel_successes[slot];
    } else {
      ++snapshot_.channel_failures[slot];
    }
  }
  if (success) {
    ++snapshot_.scan_successes;
  } else {
    ++snapshot_.scan_failures;
  }
  mark_(now_ms, false);
}

void N3wLabDiagnostics::observe_runtime(
    uint8_t path_state,
    uint8_t current_channel,
    uint8_t direct_channel_hint,
    uint32_t relay_children,
    bool relay_active,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  // current_channel is reserved for concrete Wi-Fi readback captured by
  // note_channel_result()/on_scan_result(). runtime working_channel is a
  // logical state-machine value and must not overwrite that observation oracle.
  (void) current_channel;
  const bool changed = snapshot_.path_state != path_state ||
                       snapshot_.direct_channel_hint != direct_channel_hint ||
                       relay_children_ != relay_children ||
                       relay_active_ != relay_active;
  snapshot_.path_state = path_state;
  snapshot_.direct_channel_hint = direct_channel_hint;
  relay_children_ = relay_children;
  relay_active_ = relay_active;
  if (changed) mark_(now_ms, false);
}

void N3wLabDiagnostics::note_peer_install(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.peer_install_attempts;
  if (success) ++snapshot_.peer_install_success;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::note_rx_dropped(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.rx_dropped;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::note_relay_telemetry(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  if (success && latency_.first_relay_tx_ms == 0) {
    latency_.first_relay_tx_ms = now_ms;
  }
  ++snapshot_.relay_telemetry_attempts;
  if (success) ++snapshot_.relay_telemetry_success;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::emit_summary(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_ || !boot_session_bound_) {
    return;
  }
  // Broadcast completion callbacks can run from the Wi-Fi task. They only
  // enqueue counters; merge and flush them from the normal component loop.
  drain_broadcast_completions_(now_ms);
  // Unicast completion callbacks use the same atomic-only boundary.
  drain_unicast_completions_(now_ms);
  persist_(now_ms, false);
  if (now_ms < next_summary_ms_) return;
  next_summary_ms_ = now_ms + kSummaryIntervalMs;
  ESP_LOGI(
      TAG,
      "N3W_DIAG_DISCOVERY schema=%u boot_session=%llu snapshot_uptime_ms=%llu path=%u current_channel=%u direct_channel_hint=%u attempts=%u success=%u fail=%u discovery_rx=%u challenge_rx=%u accept_tx=%u relay_children=%u relay_active_count=%u ad_attempts=%u ad_submit_success=%u ad_submit_fail=%u broadcast_done=%u broadcast_done_success=%u unicast_done=%u unicast_done_success=%u compact_rx=%u compact_decode_ok=%u compact_forward_attempts=%u compact_forward_submit_success=%u",
      static_cast<unsigned>(snapshot_.schema_version),
      static_cast<unsigned long long>(snapshot_.boot_session),
      static_cast<unsigned long long>(snapshot_.snapshot_uptime_ms),
      static_cast<unsigned>(snapshot_.path_state),
      static_cast<unsigned>(snapshot_.current_channel),
      static_cast<unsigned>(snapshot_.direct_channel_hint),
      static_cast<unsigned>(snapshot_.scan_attempts),
      static_cast<unsigned>(snapshot_.scan_successes),
      static_cast<unsigned>(snapshot_.scan_failures),
      static_cast<unsigned>(snapshot_.discovery_rx),
      static_cast<unsigned>(snapshot_.challenge_rx),
      static_cast<unsigned>(snapshot_.accept_tx),
      static_cast<unsigned>(relay_children_),
      static_cast<unsigned>(snapshot_.relay_active_count),
      static_cast<unsigned>(snapshot_.relay_advertisement_attempts),
      static_cast<unsigned>(snapshot_.relay_advertisement_submit_success),
      static_cast<unsigned>(snapshot_.relay_advertisement_submit_failure),
      static_cast<unsigned>(snapshot_.broadcast_completion_count),
      static_cast<unsigned>(snapshot_.broadcast_completion_success),
      static_cast<unsigned>(snapshot_.unicast_completion_count),
      static_cast<unsigned>(snapshot_.unicast_completion_success),
      static_cast<unsigned>(snapshot_.compact_rx_count),
      static_cast<unsigned>(snapshot_.compact_decode_success),
      static_cast<unsigned>(snapshot_.compact_forward_attempts),
      static_cast<unsigned>(snapshot_.compact_forward_submit_success));

  ESP_LOGI(
      TAG,
      "N3W_DIAG_RECOVERY presence_count=%u presence_found=%u presence_result=%u presence_last_start_ms=%llu presence_last_duration_ms=%u full_verify_count=%u full_verify_last_start_ms=%llu full_verify_trigger=%u full_verify_terminal=%u restore_cause=%u restore_result=%u deferrals=%u deferral_reason=%u next_presence_ms=%llu next_full_verify_ms=%llu queue_start=%u queue_end=%u queue_drop_start=%u queue_drop_end=%u attempt_drop_start=%u attempt_drop_end=%u",
      static_cast<unsigned>(latency_.presence_probe_count),
      static_cast<unsigned>(latency_.presence_probe_found_count),
      static_cast<unsigned>(latency_.presence_probe_last_result),
      static_cast<unsigned long long>(latency_.presence_probe_last_start_ms),
      static_cast<unsigned>(latency_.presence_probe_last_duration_ms),
      static_cast<unsigned>(latency_.full_verify_count),
      static_cast<unsigned long long>(latency_.full_verify_last_start_ms),
      static_cast<unsigned>(latency_.full_verify_last_trigger),
      static_cast<unsigned>(latency_.full_verify_last_terminal_reason),
      static_cast<unsigned>(latency_.relay_restore_last_cause),
      static_cast<unsigned>(latency_.relay_restore_last_result),
      static_cast<unsigned>(latency_.recovery_probe_deferral_count),
      static_cast<unsigned>(latency_.recovery_probe_last_deferral_reason),
      static_cast<unsigned long long>(latency_.next_presence_probe_ms),
      static_cast<unsigned long long>(latency_.next_full_verify_ms),
      static_cast<unsigned>(latency_.full_verify_queue_depth_start),
      static_cast<unsigned>(latency_.full_verify_queue_depth_end),
      static_cast<unsigned>(latency_.full_verify_queue_dropped_start),
      static_cast<unsigned>(latency_.full_verify_queue_dropped_end),
      static_cast<unsigned>(latency_.full_verify_attempt_failed_dropped_start),
      static_cast<unsigned>(latency_.full_verify_attempt_failed_dropped_end));
}

void N3wLabDiagnostics::drain_broadcast_completions_(uint64_t now_ms) {
  const uint32_t success =
      pending_broadcast_success_.exchange(0, std::memory_order_relaxed);
  const uint32_t failure =
      pending_broadcast_failure_.exchange(0, std::memory_order_relaxed);
  if (success == 0 && failure == 0) return;
  snapshot_.broadcast_completion_count += success + failure;
  snapshot_.broadcast_completion_success += success;
  snapshot_.broadcast_completion_failure += failure;
  snapshot_.snapshot_uptime_ms = now_ms;
  dirty_ = true;
}

void N3wLabDiagnostics::drain_unicast_completions_(uint64_t now_ms) {
  const uint32_t success =
      pending_unicast_success_.exchange(0, std::memory_order_relaxed);
  const uint32_t failure =
      pending_unicast_failure_.exchange(0, std::memory_order_relaxed);
  if (success == 0 && failure == 0) return;
  snapshot_.unicast_completion_count += success + failure;
  snapshot_.unicast_completion_success += success;
  snapshot_.unicast_completion_failure += failure;
  snapshot_.snapshot_uptime_ms = now_ms;
  dirty_ = true;
}

void N3wLabDiagnostics::on_runtime_start(uint8_t mode, uint8_t path_state) {
  if (!enabled_ || !boot_session_started_) return;
  snapshot_.runtime_start_mode = mode;
  snapshot_.path_state = path_state;
  mark_(snapshot_.snapshot_uptime_ms, true);
}

void N3wLabDiagnostics::on_discovery_rejected(
    DiscoveryRejectReason reason,
    uint8_t packet_channel,
    uint8_t rx_channel,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  snapshot_.last_discovery_rejection_reason = static_cast<uint8_t>(reason);
  snapshot_.last_discovery_packet_channel = packet_channel;
  snapshot_.last_discovery_rx_channel = rx_channel;
  switch (reason) {
    case DiscoveryRejectReason::STATE_NOT_DISCOVERY:
      ++snapshot_.discovery_reject_state;
      break;
    case DiscoveryRejectReason::PENDING_CHALLENGE:
      ++snapshot_.discovery_reject_pending;
      break;
    case DiscoveryRejectReason::PACKET_INVALID:
      ++snapshot_.discovery_reject_packet_invalid;
      break;
    case DiscoveryRejectReason::TRUST_GENERATION_MISMATCH:
      ++snapshot_.discovery_reject_trust_generation;
      break;
    case DiscoveryRejectReason::SELF_RELAY:
      ++snapshot_.discovery_reject_self;
      break;
    case DiscoveryRejectReason::CHANNEL_MISMATCH:
      ++snapshot_.discovery_reject_channel_mismatch;
      break;
    case DiscoveryRejectReason::NONE:
      break;
  }
  snapshot_.snapshot_uptime_ms = now_ms;
  dirty_ = true;
}

void N3wLabDiagnostics::on_discovery_rx(bool accepted, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  if (accepted && latency_.relay_ad_seen_ms == 0) {
    latency_.relay_ad_seen_ms = now_ms;
  }
  ++snapshot_.discovery_rx;
  if (!accepted) ++snapshot_.discovery_rejected;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_challenge_tx(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  if (success && latency_.challenge_tx_ms == 0) {
    latency_.challenge_tx_ms = now_ms;
  }
  ++snapshot_.challenge_tx;
  if (success) ++snapshot_.challenge_tx_success;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_challenge_submit_result(
    bool attempted,
    bool success,
    uint8_t driver_error,
    int32_t raw_error,
    uint64_t now_ms) {
  (void) now_ms;
  if (!enabled_ || !boot_session_started_ || !attempted || success) return;
  if (latency_.challenge_submit_failure_count == 0) {
    latency_.challenge_submit_first_driver_error = driver_error;
    latency_.challenge_submit_first_error_raw = raw_error;
  }
  if (latency_.challenge_submit_failure_count < 0xffffffffU) {
    ++latency_.challenge_submit_failure_count;
  }
  latency_.challenge_submit_last_driver_error = driver_error;
  latency_.challenge_submit_last_error_raw = raw_error;
}

void N3wLabDiagnostics::on_challenge_rx(bool verified, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.challenge_rx;
  if (verified) ++snapshot_.challenge_verify;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_accept_tx(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.accept_tx;
  if (success) ++snapshot_.accept_tx_success;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_accept_rx(bool verified, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  if (verified && latency_.accept_rx_ms == 0) {
    latency_.accept_rx_ms = now_ms;
  }
  ++snapshot_.accept_rx;
  if (verified) ++snapshot_.accept_verify;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_relay_active(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  if (latency_.relay_active_ms == 0) {
    latency_.relay_active_ms = now_ms;
  }
  ++snapshot_.relay_active_count;
  relay_active_ = true;
  mark_(now_ms, true);
}

void N3wLabDiagnostics::on_relay_telemetry(bool success, uint64_t now_ms) {
  note_relay_telemetry(success, now_ms);
}

void N3wLabDiagnostics::on_relay_advertisement(
    bool submitted,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.relay_advertisement_attempts;
  if (submitted) {
    ++snapshot_.relay_advertisement_submit_success;
  } else {
    ++snapshot_.relay_advertisement_submit_failure;
  }
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_broadcast_completion(
    bool success,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  (void) now_ms;
  if (success) {
    pending_broadcast_success_.fetch_add(1, std::memory_order_relaxed);
  } else {
    pending_broadcast_failure_.fetch_add(1, std::memory_order_relaxed);
  }
}

void N3wLabDiagnostics::on_unicast_completion(bool success, uint64_t now_ms) {
  // Callback path: atomic increment only. Do not read or persist Snapshot here.
  (void) now_ms;
  if (success) {
    pending_unicast_success_.fetch_add(1, std::memory_order_relaxed);
  } else {
    pending_unicast_failure_.fetch_add(1, std::memory_order_relaxed);
  }
}

void N3wLabDiagnostics::on_compact_rx(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.compact_rx_count;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_compact_state_rejected(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.compact_state_reject_count;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_compact_child_binding_failure(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.compact_child_binding_failure;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_compact_decode(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  if (success) {
    ++snapshot_.compact_decode_success;
  } else {
    ++snapshot_.compact_decode_failure;
  }
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_compact_wrap_failure(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.compact_wrap_failure;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_compact_forward_attempt(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.compact_forward_attempts;
  mark_(now_ms, false);
}

void N3wLabDiagnostics::on_compact_forward_submit(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  if (success) {
    ++snapshot_.compact_forward_submit_success;
  } else {
    ++snapshot_.compact_forward_submit_failure;
  }
  mark_(now_ms, false);
}

}  // namespace esphome::greenhouse_n3w_core

#endif  // GREENHOUSE_N3W_ENABLE_PHASE4_LAB
