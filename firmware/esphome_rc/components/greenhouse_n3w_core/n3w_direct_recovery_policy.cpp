#include "n3w_direct_recovery_policy.h"

#include <limits>

namespace esphome::greenhouse_n3w_core {

uint64_t DirectRecoveryAttempt::add_budget_(
    uint64_t now_ms,
    uint32_t budget_ms) const {
  const uint64_t budget = static_cast<uint64_t>(budget_ms);
  if (now_ms > std::numeric_limits<uint64_t>::max() - budget) {
    return std::numeric_limits<uint64_t>::max();
  }
  return now_ms + budget;
}

DirectRecoveryAction DirectRecoveryAttempt::failure_action_() const {
  return mode_ == DirectRecoveryMode::HEALTHY_RELAY
             ? DirectRecoveryAction::RESTORE_HEALTHY_RELAY
             : DirectRecoveryAction::RETURN_TO_RELAY_SEARCH;
}

DirectRecoveryDecision DirectRecoveryAttempt::decision_(
    DirectRecoveryAction action) const {
  return DirectRecoveryDecision{
      phase_,
      action,
      phase_ == DirectRecoveryPhase::SUCCEEDED ||
          phase_ == DirectRecoveryPhase::FAILED,
      terminal_reason_,
      confirm_success_count_,
      phase_deadline_ms_,
      absolute_deadline_ms_,
  };
}

DirectRecoveryDecision DirectRecoveryAttempt::fail_(
    DirectRecoveryTerminalReason reason) {
  phase_ = DirectRecoveryPhase::FAILED;
  terminal_reason_ = reason;
  restore_requested_ = false;
  return decision_(failure_action_());
}

void DirectRecoveryAttempt::enter_phase_(
    DirectRecoveryPhase phase,
    uint64_t now_ms,
    uint32_t budget_ms) {
  phase_ = phase;
  phase_deadline_ms_ = add_budget_(now_ms, budget_ms);
}

DirectRecoveryDecision DirectRecoveryAttempt::begin(
    DirectRecoveryMode mode,
    uint64_t now_ms) {
  mode_ = mode;
  terminal_reason_ = DirectRecoveryTerminalReason::NONE;
  confirm_success_count_ = 0;
  restore_requested_ = false;
  const uint32_t absolute_budget =
      mode == DirectRecoveryMode::HEALTHY_RELAY
          ? config_.healthy_relay_absolute_budget_ms
          : config_.no_relay_absolute_budget_ms;
  absolute_deadline_ms_ = add_budget_(now_ms, absolute_budget);
  enter_phase_(
      DirectRecoveryPhase::WIFI_RECOVERY,
      now_ms,
      config_.wifi_phase_budget_ms);
  return decision_(DirectRecoveryAction::CONTINUE_DIRECT);
}

DirectRecoveryDecision DirectRecoveryAttempt::observe(
    const DirectRecoveryObservation &observation) {
  if (!active()) {
    if (restore_requested_) {
      return decision_(
          DirectRecoveryAction::REQUEST_CONCRETE_DIRECT_RESTORE);
    }
    return decision_(DirectRecoveryAction::NONE);
  }

  const uint64_t now = observation.now_ms;

  if (phase_ == DirectRecoveryPhase::WIFI_RECOVERY &&
      observation.wifi_ready) {
    enter_phase_(
        DirectRecoveryPhase::MQTT_RECOVERY,
        now,
        config_.mqtt_phase_budget_ms);
  }

  if (phase_ == DirectRecoveryPhase::MQTT_RECOVERY) {
    if (!observation.wifi_ready) {
      confirm_success_count_ = 0;
      enter_phase_(
          DirectRecoveryPhase::WIFI_RECOVERY,
          now,
          config_.wifi_phase_budget_ms);
    } else if (observation.mqtt_ready) {
      confirm_success_count_ = 0;
      enter_phase_(
          DirectRecoveryPhase::DIRECT_CONFIRM,
          now,
          config_.confirm_phase_budget_ms);
    }
  }

  if (phase_ == DirectRecoveryPhase::DIRECT_CONFIRM) {
    if (!observation.wifi_ready) {
      confirm_success_count_ = 0;
      enter_phase_(
          DirectRecoveryPhase::WIFI_RECOVERY,
          now,
          config_.wifi_phase_budget_ms);
    } else if (!observation.mqtt_ready) {
      confirm_success_count_ = 0;
      enter_phase_(
          DirectRecoveryPhase::MQTT_RECOVERY,
          now,
          config_.mqtt_phase_budget_ms);
    } else if (observation.direct_check_success) {
      if (confirm_success_count_ < std::numeric_limits<uint8_t>::max()) {
        ++confirm_success_count_;
      }
      if (confirm_success_count_ >= config_.confirm_successes_required) {
        restore_requested_ = true;
        return decision_(
            DirectRecoveryAction::REQUEST_CONCRETE_DIRECT_RESTORE);
      }
    } else {
      confirm_success_count_ = 0;
    }
  }

  if (now >= phase_deadline_ms_) {
    switch (phase_) {
      case DirectRecoveryPhase::WIFI_RECOVERY:
        return fail_(DirectRecoveryTerminalReason::WIFI_TIMEOUT);
      case DirectRecoveryPhase::MQTT_RECOVERY:
        return fail_(DirectRecoveryTerminalReason::MQTT_TIMEOUT);
      case DirectRecoveryPhase::DIRECT_CONFIRM:
        return fail_(DirectRecoveryTerminalReason::CONFIRM_TIMEOUT);
      default:
        break;
    }
  }

  if (now >= absolute_deadline_ms_) {
    return fail_(DirectRecoveryTerminalReason::ABSOLUTE_TIMEOUT);
  }

  return decision_(DirectRecoveryAction::CONTINUE_DIRECT);
}

DirectRecoveryDecision DirectRecoveryAttempt::on_concrete_direct_restore(
    bool success,
    uint64_t) {
  if (!restore_requested_) {
    return decision_(DirectRecoveryAction::NONE);
  }
  restore_requested_ = false;
  if (!success) {
    return fail_(
        DirectRecoveryTerminalReason::CONCRETE_RESTORE_FAILED);
  }
  phase_ = DirectRecoveryPhase::SUCCEEDED;
  terminal_reason_ = DirectRecoveryTerminalReason::SUCCEEDED;
  return decision_(DirectRecoveryAction::COMMIT_DIRECT);
}

bool DirectRecoveryAttempt::active() const {
  return phase_ == DirectRecoveryPhase::WIFI_RECOVERY ||
         phase_ == DirectRecoveryPhase::MQTT_RECOVERY ||
         phase_ == DirectRecoveryPhase::DIRECT_CONFIRM;
}

void DirectApHintPolicy::observe(
    uint64_t now_ms,
    bool explicitly_locked) {
  last_seen_ms_ = now_ms;
  misses_ = 0;
  scan_errors_ = 0;
  explicitly_locked_ = explicitly_locked;
  active_ = true;
}

bool DirectApHintPolicy::age_expired_(uint64_t now_ms) const {
  return active_ &&
         now_ms >= last_seen_ms_ &&
         now_ms - last_seen_ms_ >= config_.max_age_ms;
}

void DirectApHintPolicy::disable_internal_hint_() {
  active_ = false;
}

DirectApHintDecision DirectApHintPolicy::decision_(
    bool use_internal_hint,
    bool allow_configured_full_direct,
    bool restore_failure) const {
  return DirectApHintDecision{
      use_internal_hint,
      allow_configured_full_direct,
      explicitly_locked_,
      restore_failure,
      misses_,
      scan_errors_,
  };
}

DirectApHintDecision DirectApHintPolicy::assess(
    uint64_t now_ms,
    DirectApScanResult result) {
  if (result == DirectApScanResult::RESTORE_FAILED) {
    return decision_(active_, false, true);
  }

  if (result == DirectApScanResult::FOUND) {
    last_seen_ms_ = now_ms;
    misses_ = 0;
    scan_errors_ = 0;
    active_ = true;
    return decision_(true, false, false);
  }

  if (!active_) {
    return decision_(false, true, false);
  }

  if (result == DirectApScanResult::NOT_FOUND) {
    if (misses_ < std::numeric_limits<uint8_t>::max()) {
      ++misses_;
    }
    scan_errors_ = 0;
  } else if (result == DirectApScanResult::ERROR) {
    if (scan_errors_ < std::numeric_limits<uint8_t>::max()) {
      ++scan_errors_;
    }
  }

  const bool miss_limit =
      config_.miss_limit != 0U &&
      misses_ >= config_.miss_limit;
  const bool error_limit =
      config_.scan_error_limit != 0U &&
      scan_errors_ >= config_.scan_error_limit;
  if (age_expired_(now_ms) || miss_limit || error_limit) {
    disable_internal_hint_();
    return decision_(false, true, false);
  }

  return decision_(true, false, false);
}

void DirectApHintPolicy::clear() {
  last_seen_ms_ = 0;
  misses_ = 0;
  scan_errors_ = 0;
  explicitly_locked_ = false;
  active_ = false;
}

}
