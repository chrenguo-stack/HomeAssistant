#pragma once

#include <cstdint>
#include <limits>

namespace esphome::greenhouse_n3w_core {

struct RecoveryExitPolicy {
  static constexpr uint8_t kDirectApHintMissLimit = 2;
  static constexpr uint64_t kDirectApHintMaxAgeMs = 300000ULL;
  static constexpr uint32_t kPendingUnicastCompletionTimeoutMs = 2000U;
  static constexpr uint8_t kRelayRestoreMaxAttempts = 10U;
  static constexpr uint32_t kRelayRestoreMaxElapsedMs = 30000U;
};

class DirectApHintLease {
 public:
  void observe(uint64_t now_ms, bool explicitly_locked) {
    last_seen_ms_ = now_ms;
    misses_ = 0;
    explicitly_locked_ = explicitly_locked;
  }

  void note_found(uint64_t now_ms) {
    last_seen_ms_ = now_ms;
    misses_ = 0;
  }

  bool note_not_found(uint64_t now_ms) {
    if (misses_ < std::numeric_limits<uint8_t>::max()) {
      ++misses_;
    }
    if (explicitly_locked_) {
      return false;
    }
    const bool miss_limit =
        misses_ >= RecoveryExitPolicy::kDirectApHintMissLimit;
    const bool age_limit =
        last_seen_ms_ != 0U &&
        now_ms >= last_seen_ms_ &&
        now_ms - last_seen_ms_ >= RecoveryExitPolicy::kDirectApHintMaxAgeMs;
    return miss_limit || age_limit;
  }

  void clear() {
    last_seen_ms_ = 0;
    misses_ = 0;
    explicitly_locked_ = false;
  }

  uint8_t misses() const { return misses_; }
  uint64_t last_seen_ms() const { return last_seen_ms_; }
  bool explicitly_locked() const { return explicitly_locked_; }

 private:
  uint64_t last_seen_ms_{0};
  uint8_t misses_{0};
  bool explicitly_locked_{false};
};

class PendingUnicastDeadline {
 public:
  void on_submit(uint64_t now_ms) {
    if (!active_) {
      active_ = true;
      started_ms_ = now_ms;
    }
  }

  void on_drained() {
    active_ = false;
    started_ms_ = 0;
  }

  bool timed_out(uint64_t now_ms) const {
    return active_ &&
           now_ms >= started_ms_ &&
           now_ms - started_ms_ >=
               RecoveryExitPolicy::kPendingUnicastCompletionTimeoutMs;
  }

  bool active() const { return active_; }
  uint64_t started_ms() const { return started_ms_; }

 private:
  uint64_t started_ms_{0};
  bool active_{false};
};

class RelayRestoreBudget {
 public:
  void start(uint64_t now_ms) {
    active_ = true;
    started_ms_ = now_ms;
    attempts_ = 0;
  }

  void note_failure() {
    if (attempts_ < std::numeric_limits<uint8_t>::max()) {
      ++attempts_;
    }
  }

  bool exhausted(uint64_t now_ms) const {
    if (!active_) return false;
    if (attempts_ >= RecoveryExitPolicy::kRelayRestoreMaxAttempts) {
      return true;
    }
    return now_ms >= started_ms_ &&
           now_ms - started_ms_ >=
               RecoveryExitPolicy::kRelayRestoreMaxElapsedMs;
  }

  void clear() {
    active_ = false;
    started_ms_ = 0;
    attempts_ = 0;
  }

  uint8_t attempts() const { return attempts_; }
  uint64_t started_ms() const { return started_ms_; }
  bool active() const { return active_; }

 private:
  uint64_t started_ms_{0};
  uint8_t attempts_{0};
  bool active_{false};
};


struct EspNowTeardownDecision {
  bool confirmed{false};
  bool keep_espnow_started{false};
};

inline EspNowTeardownDecision assess_espnow_teardown(
    bool espnow_stopped,
    bool wifi_stopped,
    bool callbacks_idle) {
  return EspNowTeardownDecision{
      espnow_stopped && wifi_stopped && callbacks_idle,
      !espnow_stopped,
  };
}

enum class CallbackQuiesceAction : uint8_t {
  PROCEED = 0,
  WAIT,
  REBOOT,
};

inline CallbackQuiesceAction callback_quiesce_action(
    bool callbacks_idle,
    bool teardown_confirmed,
    const RelayRestoreBudget &budget,
    uint64_t now_ms) {
  if (!teardown_confirmed) {
    return CallbackQuiesceAction::REBOOT;
  }
  if (callbacks_idle) {
    return CallbackQuiesceAction::PROCEED;
  }
  return budget.exhausted(now_ms)
             ? CallbackQuiesceAction::REBOOT
             : CallbackQuiesceAction::WAIT;
}

}  // namespace esphome::greenhouse_n3w_core
