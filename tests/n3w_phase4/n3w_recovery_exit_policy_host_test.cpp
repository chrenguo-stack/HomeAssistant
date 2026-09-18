#include <cassert>
#include <cstdint>

#include "n3w_recovery_exit_policy.h"

using namespace esphome::greenhouse_n3w_core;

int main() {
  {
    DirectApHintLease hint;
    hint.observe(1000, false);
    assert(!hint.note_not_found(61000));
    assert(hint.misses() == 1);
    assert(hint.note_not_found(181000));
    assert(hint.misses() == RecoveryExitPolicy::kDirectApHintMissLimit);
  }

  {
    DirectApHintLease locked;
    locked.observe(1000, true);
    for (uint8_t i = 0; i < 8; ++i) {
      assert(!locked.note_not_found(600000 + static_cast<uint64_t>(i) * 60000));
    }
    assert(locked.explicitly_locked());
  }

  {
    DirectApHintLease aged;
    aged.observe(1000, false);
    assert(aged.note_not_found(
        1000 + RecoveryExitPolicy::kDirectApHintMaxAgeMs));
  }

  {
    PendingUnicastDeadline pending;
    pending.on_submit(1000);
    assert(pending.active());
    assert(!pending.timed_out(
        1000 + RecoveryExitPolicy::kPendingUnicastCompletionTimeoutMs - 1));
    assert(pending.timed_out(
        1000 + RecoveryExitPolicy::kPendingUnicastCompletionTimeoutMs));
    pending.on_drained();
    assert(!pending.active());
    assert(!pending.timed_out(100000));

    // A stale/late completion after teardown is represented by another drain;
    // it must not resurrect the old deadline or poison a new send session.
    pending.on_drained();
    pending.on_submit(200000);
    assert(pending.active());
    assert(pending.started_ms() == 200000);
  }

  {
    RelayRestoreBudget budget;
    budget.start(1000);
    for (uint8_t i = 1; i < RecoveryExitPolicy::kRelayRestoreMaxAttempts; ++i) {
      budget.note_failure();
      assert(!budget.exhausted(1000 + static_cast<uint64_t>(i) * 1000));
    }
    budget.note_failure();
    assert(budget.exhausted(11000));
  }

  {
    RelayRestoreBudget elapsed;
    elapsed.start(5000);
    elapsed.note_failure();
    assert(!elapsed.exhausted(
        5000 + RecoveryExitPolicy::kRelayRestoreMaxElapsedMs - 1));
    assert(elapsed.exhausted(
        5000 + RecoveryExitPolicy::kRelayRestoreMaxElapsedMs));
  }

  {
    RelayRestoreBudget quiesce;
    quiesce.start(1000);
    assert(callback_quiesce_action(true, true, quiesce, 1000) ==
           CallbackQuiesceAction::PROCEED);
    assert(callback_quiesce_action(false, true, quiesce, 2000) ==
           CallbackQuiesceAction::WAIT);
    assert(callback_quiesce_action(
               false,
               true,
               quiesce,
               1000 + RecoveryExitPolicy::kRelayRestoreMaxElapsedMs) ==
           CallbackQuiesceAction::REBOOT);
    assert(callback_quiesce_action(true, false, quiesce, 2000) ==
           CallbackQuiesceAction::REBOOT);
  }

  {
    const EspNowTeardownDecision clean =
        assess_espnow_teardown(true, true, true);
    assert(clean.confirmed);
    assert(!clean.keep_espnow_started);

    const EspNowTeardownDecision deinit_failed =
        assess_espnow_teardown(false, true, true);
    assert(!deinit_failed.confirmed);
    assert(deinit_failed.keep_espnow_started);

    const EspNowTeardownDecision callback_busy =
        assess_espnow_teardown(true, true, false);
    assert(!callback_busy.confirmed);
    assert(!callback_busy.keep_espnow_started);

    const EspNowTeardownDecision wifi_stop_failed =
        assess_espnow_teardown(true, false, true);
    assert(!wifi_stop_failed.confirmed);
    assert(!wifi_stop_failed.keep_espnow_started);
  }

  return 0;
}
