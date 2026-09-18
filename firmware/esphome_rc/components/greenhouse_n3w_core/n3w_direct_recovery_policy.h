#pragma once

#include <cstdint>

namespace esphome::greenhouse_n3w_core {

enum class DirectRecoveryMode : uint8_t {
  NO_RELAY = 0,
  HEALTHY_RELAY,
};

enum class DirectRecoveryPhase : uint8_t {
  IDLE = 0,
  WIFI_RECOVERY,
  MQTT_RECOVERY,
  DIRECT_CONFIRM,
  SUCCEEDED,
  FAILED,
};

enum class DirectRecoveryAction : uint8_t {
  NONE = 0,
  CONTINUE_DIRECT,
  REQUEST_CONCRETE_DIRECT_RESTORE,
  COMMIT_DIRECT,
  RETURN_TO_RELAY_SEARCH,
  RESTORE_HEALTHY_RELAY,
};

enum class DirectRecoveryTerminalReason : uint8_t {
  NONE = 0,
  SUCCEEDED,
  WIFI_TIMEOUT,
  MQTT_TIMEOUT,
  CONFIRM_TIMEOUT,
  ABSOLUTE_TIMEOUT,
  CONCRETE_RESTORE_FAILED,
};

struct DirectRecoveryConfig {
  uint32_t wifi_phase_budget_ms{20000};
  uint32_t mqtt_phase_budget_ms{25000};
  uint32_t confirm_phase_budget_ms{5000};
  uint32_t no_relay_absolute_budget_ms{50000};
  uint32_t healthy_relay_absolute_budget_ms{30000};
  uint8_t confirm_successes_required{2};
};

struct DirectRecoveryObservation {
  uint64_t now_ms{0};
  bool wifi_ready{false};
  bool mqtt_ready{false};
  bool direct_check_success{false};
};

struct DirectRecoveryDecision {
  DirectRecoveryPhase phase{DirectRecoveryPhase::IDLE};
  DirectRecoveryAction action{DirectRecoveryAction::NONE};
  bool terminal{false};
  DirectRecoveryTerminalReason terminal_reason{
      DirectRecoveryTerminalReason::NONE};
  uint8_t confirm_success_count{0};
  uint64_t phase_deadline_ms{0};
  uint64_t absolute_deadline_ms{0};
};

class DirectRecoveryAttempt {
 public:
  explicit DirectRecoveryAttempt(const DirectRecoveryConfig &config)
      : config_(config) {}

  DirectRecoveryDecision begin(
      DirectRecoveryMode mode,
      uint64_t now_ms);
  DirectRecoveryDecision observe(
      const DirectRecoveryObservation &observation);
  DirectRecoveryDecision on_concrete_direct_restore(
      bool success,
      uint64_t now_ms);

  bool active() const;
  DirectRecoveryMode mode() const { return mode_; }
  DirectRecoveryPhase phase() const { return phase_; }

 private:
  uint64_t add_budget_(uint64_t now_ms, uint32_t budget_ms) const;
  DirectRecoveryAction failure_action_() const;
  DirectRecoveryDecision decision_(DirectRecoveryAction action) const;
  DirectRecoveryDecision fail_(
      DirectRecoveryTerminalReason reason);
  void enter_phase_(
      DirectRecoveryPhase phase,
      uint64_t now_ms,
      uint32_t budget_ms);

  DirectRecoveryConfig config_{};
  DirectRecoveryMode mode_{DirectRecoveryMode::NO_RELAY};
  DirectRecoveryPhase phase_{DirectRecoveryPhase::IDLE};
  DirectRecoveryTerminalReason terminal_reason_{
      DirectRecoveryTerminalReason::NONE};
  uint64_t phase_deadline_ms_{0};
  uint64_t absolute_deadline_ms_{0};
  uint8_t confirm_success_count_{0};
  bool restore_requested_{false};
};

enum class DirectApScanResult : uint8_t {
  FOUND = 0,
  NOT_FOUND,
  ERROR,
  RESTORE_FAILED,
};

struct DirectApHintConfig {
  uint64_t max_age_ms{300000};
  uint8_t miss_limit{2};
  uint8_t scan_error_limit{3};
};

struct DirectApHintDecision {
  bool use_internal_hint{false};
  bool allow_configured_full_direct{true};
  bool explicit_bssid_lock_preserved{false};
  bool restore_failure{false};
  uint8_t misses{0};
  uint8_t scan_errors{0};
};

class DirectApHintPolicy {
 public:
  explicit DirectApHintPolicy(const DirectApHintConfig &config)
      : config_(config) {}

  void observe(uint64_t now_ms, bool explicitly_locked);
  DirectApHintDecision assess(
      uint64_t now_ms,
      DirectApScanResult result);
  void clear();

  uint8_t misses() const { return misses_; }
  uint8_t scan_errors() const { return scan_errors_; }
  uint64_t last_seen_ms() const { return last_seen_ms_; }
  bool explicitly_locked() const { return explicitly_locked_; }
  bool active() const { return active_; }

 private:
  DirectApHintDecision decision_(
      bool use_internal_hint,
      bool allow_configured_full_direct,
      bool restore_failure) const;
  bool age_expired_(uint64_t now_ms) const;
  void disable_internal_hint_();

  DirectApHintConfig config_{};
  uint64_t last_seen_ms_{0};
  uint8_t misses_{0};
  uint8_t scan_errors_{0};
  bool explicitly_locked_{false};
  bool active_{false};
};

}
