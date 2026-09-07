#include "n3w_lab_diagnostics.h"

#include <cstring>

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
  dirty_ = true;
  last_persist_ms_ = 0;
  next_summary_ms_ = 0;
  relay_children_ = 0;
  relay_active_ = false;
  persist_(0, true);
}

void N3wLabDiagnostics::mark_(uint64_t now_ms, bool force) {
  if (!enabled_ || !boot_session_started_) return;
  dirty_ = true;
  persist_(now_ms, force);
}

void N3wLabDiagnostics::persist_(uint64_t now_ms, bool force) {
  if (!enabled_ || !boot_session_started_ || !dirty_ ||
      (!force && now_ms - last_persist_ms_ < kPersistIntervalMs)) {
    return;
  }
#ifdef USE_ESP32
  nvs_handle_t handle = 0;
  if (nvs_open(kNamespace, NVS_READWRITE, &handle) != ESP_OK) return;
  const esp_err_t result = nvs_set_blob(handle, kKey, &snapshot_, sizeof(snapshot_)) == ESP_OK
                               ? nvs_commit(handle)
                               : ESP_FAIL;
  nvs_close(handle);
  if (result != ESP_OK) return;
#endif
  last_persist_ms_ = now_ms;
  dirty_ = false;
}

void N3wLabDiagnostics::note_channel_result(
    uint8_t requested,
    bool success,
    uint8_t observed,
    int32_t raw_error,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  snapshot_.current_channel = observed != 0U ? observed : requested;
  snapshot_.last_requested_channel = requested;
  snapshot_.last_observed_channel = observed;
  snapshot_.last_driver_error_raw = raw_error;
  ++snapshot_.scan_attempts;
  const int slot = channel_slot_(requested);
  if (slot >= 0) {
    ++snapshot_.channel_attempts[slot];
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
  mark_(now_ms, !success);
}

void N3wLabDiagnostics::observe_runtime(
    uint8_t path_state,
    uint8_t current_channel,
    uint32_t relay_children,
    bool relay_active,
    uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  const bool changed = snapshot_.path_state != path_state ||
                       snapshot_.current_channel != current_channel ||
                       relay_children_ != relay_children ||
                       relay_active_ != relay_active;
  snapshot_.path_state = path_state;
  snapshot_.current_channel = current_channel;
  relay_children_ = relay_children;
  relay_active_ = relay_active;
  if (changed) mark_(now_ms, true);
}

void N3wLabDiagnostics::note_peer_install(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.peer_install_attempts;
  if (success) ++snapshot_.peer_install_success;
  mark_(now_ms, !success);
}

void N3wLabDiagnostics::note_rx_dropped(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.rx_dropped;
  mark_(now_ms, true);
}

void N3wLabDiagnostics::note_relay_telemetry(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.relay_telemetry_attempts;
  if (success) ++snapshot_.relay_telemetry_success;
  mark_(now_ms, !success);
}

void N3wLabDiagnostics::emit_summary(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_ || now_ms < next_summary_ms_) return;
  next_summary_ms_ = now_ms + kSummaryIntervalMs;
  ESP_LOGI(
      TAG,
      "N3W_DIAG_DISCOVERY schema=%u path=%u current_channel=%u attempts=%u success=%u fail=%u discovery_rx=%u challenge_rx=%u accept_tx=%u relay_children=%u relay_active_count=%u",
      static_cast<unsigned>(snapshot_.schema_version),
      static_cast<unsigned>(snapshot_.path_state),
      static_cast<unsigned>(snapshot_.current_channel),
      static_cast<unsigned>(snapshot_.scan_attempts),
      static_cast<unsigned>(snapshot_.scan_successes),
      static_cast<unsigned>(snapshot_.scan_failures),
      static_cast<unsigned>(snapshot_.discovery_rx),
      static_cast<unsigned>(snapshot_.challenge_rx),
      static_cast<unsigned>(snapshot_.accept_tx),
      static_cast<unsigned>(relay_children_),
      static_cast<unsigned>(snapshot_.relay_active_count));
}

void N3wLabDiagnostics::on_runtime_start(uint8_t mode, uint8_t path_state) {
  if (!enabled_ || !boot_session_started_) return;
  snapshot_.runtime_start_mode = mode;
  snapshot_.path_state = path_state;
  mark_(0, true);
}

void N3wLabDiagnostics::on_discovery_rx(bool accepted, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.discovery_rx;
  if (!accepted) ++snapshot_.discovery_rejected;
  mark_(now_ms, !accepted);
}

void N3wLabDiagnostics::on_challenge_tx(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.challenge_tx;
  if (success) ++snapshot_.challenge_tx_success;
  mark_(now_ms, !success);
}

void N3wLabDiagnostics::on_challenge_rx(bool verified, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.challenge_rx;
  if (verified) ++snapshot_.challenge_verify;
  mark_(now_ms, !verified);
}

void N3wLabDiagnostics::on_accept_tx(bool success, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.accept_tx;
  if (success) ++snapshot_.accept_tx_success;
  mark_(now_ms, !success);
}

void N3wLabDiagnostics::on_accept_rx(bool verified, uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.accept_rx;
  if (verified) ++snapshot_.accept_verify;
  mark_(now_ms, !verified);
}

void N3wLabDiagnostics::on_relay_active(uint64_t now_ms) {
  if (!enabled_ || !boot_session_started_) return;
  ++snapshot_.relay_active_count;
  relay_active_ = true;
  mark_(now_ms, true);
}

void N3wLabDiagnostics::on_relay_telemetry(bool success, uint64_t now_ms) {
  note_relay_telemetry(success, now_ms);
}

}  // namespace esphome::greenhouse_n3w_core
