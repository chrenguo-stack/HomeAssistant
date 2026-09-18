#include <cassert>
#include <cstdint>
#include <initializer_list>

#include "n3w_direct_recovery_policy.h"

using namespace esphome::greenhouse_n3w_core;

namespace {

DirectRecoveryConfig base_config() {
  DirectRecoveryConfig config;
  config.wifi_phase_budget_ms = 20000;
  config.mqtt_phase_budget_ms = 25000;
  config.confirm_phase_budget_ms = 5000;
  config.no_relay_absolute_budget_ms = 50000;
  config.healthy_relay_absolute_budget_ms = 30000;
  config.confirm_successes_required = 2;
  return config;
}

DirectRecoveryDecision observe(
    DirectRecoveryAttempt &attempt,
    uint64_t now_ms,
    bool wifi_ready,
    bool mqtt_ready,
    bool direct_check_success) {
  return attempt.observe(DirectRecoveryObservation{
      now_ms,
      wifi_ready,
      mqtt_ready,
      direct_check_success,
  });
}

void complete_success(
    DirectRecoveryAttempt &attempt,
    uint64_t mqtt_ready_ms) {
  auto decision = observe(attempt, 0, true, false, false);
  assert(decision.phase == DirectRecoveryPhase::MQTT_RECOVERY);
  assert(decision.action == DirectRecoveryAction::CONTINUE_DIRECT);

  decision = observe(attempt, mqtt_ready_ms, true, true, false);
  assert(decision.phase == DirectRecoveryPhase::DIRECT_CONFIRM);
  assert(decision.action == DirectRecoveryAction::CONTINUE_DIRECT);

  decision = observe(attempt, mqtt_ready_ms + 2000, true, true, true);
  assert(decision.phase == DirectRecoveryPhase::DIRECT_CONFIRM);
  assert(decision.confirm_success_count == 1);
  assert(decision.action == DirectRecoveryAction::CONTINUE_DIRECT);

  decision = observe(attempt, mqtt_ready_ms + 4000, true, true, true);
  assert(decision.action ==
         DirectRecoveryAction::REQUEST_CONCRETE_DIRECT_RESTORE);
  assert(!decision.terminal);

  decision =
      attempt.on_concrete_direct_restore(true, mqtt_ready_ms + 4000);
  assert(decision.action == DirectRecoveryAction::COMMIT_DIRECT);
  assert(decision.phase == DirectRecoveryPhase::SUCCEEDED);
  assert(decision.terminal);
  assert(decision.terminal_reason ==
         DirectRecoveryTerminalReason::SUCCEEDED);
}

void drl_01_no_relay_mqtt_ready_at_12s_succeeds() {
  DirectRecoveryAttempt attempt(base_config());
  auto begin = attempt.begin(DirectRecoveryMode::NO_RELAY, 0);
  assert(begin.action == DirectRecoveryAction::CONTINUE_DIRECT);
  complete_success(attempt, 12000);
}

void drl_02_no_relay_mqtt_ready_at_13s_succeeds() {
  DirectRecoveryAttempt attempt(base_config());
  auto begin = attempt.begin(DirectRecoveryMode::NO_RELAY, 0);
  assert(begin.action == DirectRecoveryAction::CONTINUE_DIRECT);
  complete_success(attempt, 13000);
}

void drl_03_no_relay_mqtt_ready_at_20s_succeeds() {
  DirectRecoveryAttempt attempt(base_config());
  auto begin = attempt.begin(DirectRecoveryMode::NO_RELAY, 0);
  assert(begin.action == DirectRecoveryAction::CONTINUE_DIRECT);
  complete_success(attempt, 20000);
}

void drl_04_progress_at_mqtt_deadline_wins_before_timeout() {
  DirectRecoveryConfig config = base_config();
  config.mqtt_phase_budget_ms = 20000;
  DirectRecoveryAttempt attempt(config);
  auto decision = attempt.begin(DirectRecoveryMode::NO_RELAY, 0);
  assert(decision.action == DirectRecoveryAction::CONTINUE_DIRECT);

  decision = observe(attempt, 0, true, false, false);
  assert(decision.phase == DirectRecoveryPhase::MQTT_RECOVERY);

  decision = observe(attempt, 20000, true, true, false);
  assert(decision.phase == DirectRecoveryPhase::DIRECT_CONFIRM);
  assert(!decision.terminal);
}

void drl_05_confirm_loss_resets_confirmation_not_absolute_deadline() {
  DirectRecoveryAttempt attempt(base_config());
  auto decision = attempt.begin(DirectRecoveryMode::NO_RELAY, 1000);
  const uint64_t absolute_deadline = decision.absolute_deadline_ms;

  decision = observe(attempt, 1000, true, false, false);
  assert(decision.phase == DirectRecoveryPhase::MQTT_RECOVERY);

  decision = observe(attempt, 2000, true, true, false);
  assert(decision.phase == DirectRecoveryPhase::DIRECT_CONFIRM);

  decision = observe(attempt, 4000, true, true, true);
  assert(decision.confirm_success_count == 1);

  decision = observe(attempt, 5000, true, false, false);
  assert(decision.phase == DirectRecoveryPhase::MQTT_RECOVERY);
  assert(decision.confirm_success_count == 0);
  assert(decision.absolute_deadline_ms == absolute_deadline);

  decision = observe(attempt, 6000, true, true, false);
  assert(decision.phase == DirectRecoveryPhase::DIRECT_CONFIRM);
  assert(decision.absolute_deadline_ms == absolute_deadline);
}

void drl_06_oscillation_cannot_extend_absolute_deadline() {
  DirectRecoveryAttempt attempt(base_config());
  auto decision = attempt.begin(DirectRecoveryMode::NO_RELAY, 0);
  const uint64_t absolute_deadline = decision.absolute_deadline_ms;

  decision = observe(attempt, 10000, true, false, false);
  assert(!decision.terminal);
  decision = observe(attempt, 20000, false, false, false);
  assert(!decision.terminal);
  decision = observe(attempt, 30000, true, false, false);
  assert(!decision.terminal);
  decision = observe(attempt, 40000, false, false, false);
  assert(!decision.terminal);

  decision = observe(attempt, absolute_deadline, false, false, false);
  assert(decision.terminal);
  assert(decision.terminal_reason ==
         DirectRecoveryTerminalReason::ABSOLUTE_TIMEOUT);
  assert(decision.action ==
         DirectRecoveryAction::RETURN_TO_RELAY_SEARCH);
}

void drl_07_no_relay_attempt_is_not_self_interrupted() {
  DirectRecoveryAttempt attempt(base_config());
  auto decision = attempt.begin(DirectRecoveryMode::NO_RELAY, 0);
  assert(decision.action == DirectRecoveryAction::CONTINUE_DIRECT);

  for (uint64_t now : {5000ULL, 10000ULL, 15000ULL, 20000ULL}) {
    decision = observe(attempt, now, true, false, false);
    assert(!decision.terminal);
    assert(decision.action == DirectRecoveryAction::CONTINUE_DIRECT);
  }
}

void drl_08_healthy_relay_attempt_is_bounded_and_returns_to_relay() {
  DirectRecoveryAttempt attempt(base_config());
  auto decision = attempt.begin(DirectRecoveryMode::HEALTHY_RELAY, 0);
  assert(decision.action == DirectRecoveryAction::CONTINUE_DIRECT);

  decision = observe(attempt, 20000, false, false, false);
  assert(decision.terminal);
  assert(decision.action ==
         DirectRecoveryAction::RESTORE_HEALTHY_RELAY);
}

void drl_09_hint_expires_by_wall_clock_even_on_scan_error() {
  DirectApHintConfig config;
  config.max_age_ms = 300000;
  config.miss_limit = 2;
  config.scan_error_limit = 3;

  DirectApHintPolicy hint(config);
  hint.observe(0, false);

  const auto decision =
      hint.assess(300000, DirectApScanResult::ERROR);

  assert(!decision.use_internal_hint);
  assert(decision.allow_configured_full_direct);
  assert(!decision.explicit_bssid_lock_preserved);
  assert(!decision.restore_failure);
}

void drl_10_repeated_scan_error_has_bounded_exit() {
  DirectApHintConfig config;
  config.max_age_ms = 300000;
  config.miss_limit = 2;
  config.scan_error_limit = 3;

  DirectApHintPolicy hint(config);
  hint.observe(0, false);

  auto decision = hint.assess(1000, DirectApScanResult::ERROR);
  assert(decision.use_internal_hint);
  assert(!decision.allow_configured_full_direct);

  decision = hint.assess(2000, DirectApScanResult::ERROR);
  assert(decision.use_internal_hint);
  assert(!decision.allow_configured_full_direct);

  decision = hint.assess(3000, DirectApScanResult::ERROR);
  assert(!decision.use_internal_hint);
  assert(decision.allow_configured_full_direct);
}

void drl_11_explicit_bssid_constraint_is_preserved() {
  DirectApHintConfig config;
  config.max_age_ms = 300000;
  config.miss_limit = 2;
  config.scan_error_limit = 3;

  DirectApHintPolicy hint(config);
  hint.observe(0, true);

  const auto decision =
      hint.assess(300000, DirectApScanResult::ERROR);

  assert(!decision.use_internal_hint);
  assert(decision.allow_configured_full_direct);
  assert(decision.explicit_bssid_lock_preserved);
}

void drl_12_concrete_restore_precedes_logical_direct_commit() {
  DirectRecoveryAttempt attempt(base_config());
  auto decision = attempt.begin(DirectRecoveryMode::NO_RELAY, 0);
  assert(decision.action == DirectRecoveryAction::CONTINUE_DIRECT);

  decision = observe(attempt, 0, true, false, false);
  assert(decision.phase == DirectRecoveryPhase::MQTT_RECOVERY);

  decision = observe(attempt, 1000, true, true, false);
  assert(decision.phase == DirectRecoveryPhase::DIRECT_CONFIRM);

  decision = observe(attempt, 3000, true, true, true);
  assert(decision.confirm_success_count == 1);

  decision = observe(attempt, 5000, true, true, true);
  assert(decision.action ==
         DirectRecoveryAction::REQUEST_CONCRETE_DIRECT_RESTORE);
  assert(decision.phase == DirectRecoveryPhase::DIRECT_CONFIRM);
  assert(!decision.terminal);

  decision = attempt.on_concrete_direct_restore(true, 5000);
  assert(decision.action == DirectRecoveryAction::COMMIT_DIRECT);
  assert(decision.phase == DirectRecoveryPhase::SUCCEEDED);
  assert(decision.terminal);
}

}

int main() {
  drl_01_no_relay_mqtt_ready_at_12s_succeeds();
  drl_02_no_relay_mqtt_ready_at_13s_succeeds();
  drl_03_no_relay_mqtt_ready_at_20s_succeeds();
  drl_04_progress_at_mqtt_deadline_wins_before_timeout();
  drl_05_confirm_loss_resets_confirmation_not_absolute_deadline();
  drl_06_oscillation_cannot_extend_absolute_deadline();
  drl_07_no_relay_attempt_is_not_self_interrupted();
  drl_08_healthy_relay_attempt_is_bounded_and_returns_to_relay();
  drl_09_hint_expires_by_wall_clock_even_on_scan_error();
  drl_10_repeated_scan_error_has_bounded_exit();
  drl_11_explicit_bssid_constraint_is_preserved();
  drl_12_concrete_restore_precedes_logical_direct_commit();
  return 0;
}
