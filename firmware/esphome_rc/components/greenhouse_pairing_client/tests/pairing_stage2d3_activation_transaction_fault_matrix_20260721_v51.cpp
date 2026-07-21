#include <cassert>
#include <iostream>
#include <string>
#include <vector>

#include "pairing_profile_activation_coordinator.h"

using namespace esphome::greenhouse_pairing_client;

namespace {

struct FakeRuntime final : ProfileActivationRuntime {
  explicit FakeRuntime(bool old_live, std::vector<std::string> *trace)
      : old_live(old_live), trace(trace) {}

  bool stop_old_active() override {
    this->record("stop_old");
    if (!this->stop_old_ok)
      return false;
    this->old_live = false;
    return true;
  }

  bool start_candidate() override {
    this->record("start_candidate");
    if (!this->start_candidate_ok)
      return false;
    this->candidate_live = true;
    return true;
  }

  bool confirm_candidate_round_trip() override {
    this->record("confirm_candidate");
    return this->confirm_ok;
  }

  bool stop_candidate() override {
    this->record("stop_candidate");
    if (!this->stop_candidate_ok)
      return false;
    this->candidate_live = false;
    return true;
  }

  bool restore_old_active() override {
    this->record("restore_old");
    if (!this->restore_old_ok)
      return false;
    this->old_live = true;
    return true;
  }

  void quiesce_all() override {
    this->record("quiesce_all");
    this->old_live = false;
    this->candidate_live = false;
    this->quiesced = true;
  }

  void clear_candidate_material() override {
    this->record("clear_material");
    this->material_cleared = true;
  }

  bool old_active_live() const override { return this->old_live; }
  bool candidate_active_live() const override { return this->candidate_live; }

  void record(const std::string &value) {
    if (this->trace != nullptr)
      this->trace->push_back(value);
  }

  bool old_live{false};
  bool candidate_live{false};
  bool stop_old_ok{true};
  bool start_candidate_ok{true};
  bool confirm_ok{true};
  bool stop_candidate_ok{true};
  bool restore_old_ok{true};
  bool quiesced{false};
  bool material_cleared{false};
  std::vector<std::string> *trace{nullptr};
};

struct FakePersistence final : ProfileActivationPersistence {
  explicit FakePersistence(std::vector<std::string> *trace) : trace(trace) {}

  bool prepared_matches(uint32_t active_generation,
                        uint32_t candidate_generation) const override {
    if (this->trace != nullptr)
      this->trace->push_back("prepared_matches");
    return this->prepared_ok && active_generation == this->expected_active &&
           candidate_generation == this->expected_candidate;
  }

  ProfileActivationCommitResult commit_verified_candidate() override {
    if (this->trace != nullptr)
      this->trace->push_back("commit");
    return this->commit_result;
  }

  bool prepared_ok{true};
  uint32_t expected_active{10};
  uint32_t expected_candidate{11};
  ProfileActivationCommitResult commit_result{
      ProfileActivationCommitResult::COMMITTED};
  std::vector<std::string> *trace{nullptr};
};

VerifiedCandidateEvidence evidence(uint32_t active = 10,
                                   uint32_t candidate = 11) {
  return {
      .active_generation = active,
      .candidate_generation = candidate,
      .candidate_verified = true,
      .candidate_probe_client_destroyed = true,
      .active_profile_unchanged = true,
  };
}

void expect_trace(const std::vector<std::string> &actual,
                  const std::vector<std::string> &expected) {
  assert(actual == expected);
}

void test_invalid_evidence() {
  ProfileActivationCoordinator coordinator;
  assert(coordinator.configure(10));

  auto invalid = evidence();
  invalid.candidate_verified = false;
  assert(!coordinator.arm(invalid));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::FAILED);
  assert(coordinator.snapshot().failure ==
         ProfileActivationFailure::INVALID_EVIDENCE);
  assert(coordinator.reset());

  invalid = evidence(9, 11);
  assert(!coordinator.arm(invalid));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::FAILED);
}

void test_prepared_mismatch() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(true, &trace);
  FakePersistence persistence(&trace);
  persistence.prepared_ok = false;

  assert(coordinator.configure(10));
  assert(coordinator.arm(evidence()));
  assert(!coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::FAILED);
  assert(coordinator.snapshot().failure ==
         ProfileActivationFailure::PREPARED_MISMATCH);
  assert(runtime.old_live && !runtime.candidate_live);
  assert(runtime.material_cleared);
  expect_trace(trace, {"prepared_matches", "clear_material"});
}

void test_stop_old_failure_preserves_old() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(true, &trace);
  FakePersistence persistence(&trace);
  runtime.stop_old_ok = false;

  assert(coordinator.configure(10));
  assert(coordinator.arm(evidence()));
  assert(!coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::FAILED);
  assert(coordinator.snapshot().failure ==
         ProfileActivationFailure::STOP_OLD_FAILED);
  assert(runtime.old_live && !runtime.candidate_live && !runtime.quiesced);
  expect_trace(trace,
               {"prepared_matches", "stop_old", "clear_material"});
}

void test_start_failure_rolls_back() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(true, &trace);
  FakePersistence persistence(&trace);
  runtime.start_candidate_ok = false;

  assert(coordinator.configure(10));
  assert(coordinator.arm(evidence()));
  assert(!coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::ROLLED_BACK);
  assert(coordinator.snapshot().failure ==
         ProfileActivationFailure::START_CANDIDATE_FAILED);
  assert(runtime.old_live && !runtime.candidate_live);
  expect_trace(trace, {"prepared_matches", "stop_old", "start_candidate",
                       "restore_old", "clear_material"});
}

void test_confirmation_failure_rolls_back() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(true, &trace);
  FakePersistence persistence(&trace);
  runtime.confirm_ok = false;

  assert(coordinator.configure(10));
  assert(coordinator.arm(evidence()));
  assert(!coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::ROLLED_BACK);
  assert(coordinator.snapshot().failure ==
         ProfileActivationFailure::CONFIRM_CANDIDATE_FAILED);
  assert(runtime.old_live && !runtime.candidate_live);
  expect_trace(trace,
               {"prepared_matches", "stop_old", "start_candidate",
                "confirm_candidate", "stop_candidate", "restore_old",
                "clear_material"});
}

void test_persistence_rejection_rolls_back_marker_last() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(true, &trace);
  FakePersistence persistence(&trace);
  persistence.commit_result =
      ProfileActivationCommitResult::OLD_ACTIVE_PRESERVED;

  assert(coordinator.configure(10));
  assert(coordinator.arm(evidence()));
  assert(!coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::ROLLED_BACK);
  assert(coordinator.snapshot().active_generation == 10);
  assert(!coordinator.snapshot().persistence_committed);
  assert(runtime.old_live && !runtime.candidate_live);
  expect_trace(trace,
               {"prepared_matches", "stop_old", "start_candidate",
                "confirm_candidate", "commit", "stop_candidate",
                "restore_old", "clear_material"});
}

void test_indeterminate_commit_requires_reboot() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(true, &trace);
  FakePersistence persistence(&trace);
  persistence.commit_result =
      ProfileActivationCommitResult::INDETERMINATE_REBOOT_REQUIRED;

  assert(coordinator.configure(10));
  assert(coordinator.arm(evidence()));
  assert(!coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase ==
         ProfileActivationPhase::REBOOT_REQUIRED);
  assert(coordinator.snapshot().failure ==
         ProfileActivationFailure::PERSISTENCE_INDETERMINATE);
  assert(coordinator.snapshot().reboot_required);
  assert(runtime.quiesced && !runtime.old_live && !runtime.candidate_live);
  expect_trace(trace,
               {"prepared_matches", "stop_old", "start_candidate",
                "confirm_candidate", "commit", "quiesce_all",
                "clear_material"});
}

void test_restore_failure_requires_reboot() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(true, &trace);
  FakePersistence persistence(&trace);
  runtime.confirm_ok = false;
  runtime.restore_old_ok = false;

  assert(coordinator.configure(10));
  assert(coordinator.arm(evidence()));
  assert(!coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase ==
         ProfileActivationPhase::REBOOT_REQUIRED);
  assert(coordinator.snapshot().failure ==
         ProfileActivationFailure::RESTORE_OLD_FAILED);
  assert(runtime.quiesced);
  expect_trace(trace,
               {"prepared_matches", "stop_old", "start_candidate",
                "confirm_candidate", "stop_candidate", "restore_old",
                "quiesce_all", "clear_material"});
}

void test_success_commits_after_round_trip() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(true, &trace);
  FakePersistence persistence(&trace);

  assert(coordinator.configure(10));
  assert(coordinator.arm(evidence()));
  assert(coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::ACTIVATED);
  assert(coordinator.snapshot().active_generation == 11);
  assert(coordinator.snapshot().candidate_generation == 0);
  assert(coordinator.snapshot().persistence_committed);
  assert(!coordinator.snapshot().reboot_required);
  assert(!runtime.old_live && runtime.candidate_live);
  assert(runtime.material_cleared);
  expect_trace(trace,
               {"prepared_matches", "stop_old", "start_candidate",
                "confirm_candidate", "commit", "clear_material"});
  assert(coordinator.reset());
  assert(coordinator.snapshot().phase == ProfileActivationPhase::IDLE);
  assert(coordinator.snapshot().active_generation == 11);
}

void test_first_enrollment() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(false, &trace);
  FakePersistence persistence(&trace);
  persistence.expected_active = 0;
  persistence.expected_candidate = 1;

  assert(coordinator.configure(0));
  assert(coordinator.arm(evidence(0, 1)));
  assert(coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::ACTIVATED);
  assert(coordinator.snapshot().active_generation == 1);
  assert(runtime.candidate_live && !runtime.old_live);
  expect_trace(trace, {"prepared_matches", "start_candidate",
                       "confirm_candidate", "commit", "clear_material"});
}

void test_first_enrollment_persistence_rejection() {
  std::vector<std::string> trace;
  ProfileActivationCoordinator coordinator;
  FakeRuntime runtime(false, &trace);
  FakePersistence persistence(&trace);
  persistence.expected_active = 0;
  persistence.expected_candidate = 1;
  persistence.commit_result =
      ProfileActivationCommitResult::OLD_ACTIVE_PRESERVED;

  assert(coordinator.configure(0));
  assert(coordinator.arm(evidence(0, 1)));
  assert(!coordinator.execute(&runtime, &persistence));
  assert(coordinator.snapshot().phase == ProfileActivationPhase::FAILED);
  assert(coordinator.snapshot().active_generation == 0);
  assert(!runtime.old_live && !runtime.candidate_live);
  expect_trace(trace, {"prepared_matches", "start_candidate",
                       "confirm_candidate", "commit", "stop_candidate",
                       "clear_material"});
}

}  // namespace

int main() {
  test_invalid_evidence();
  test_prepared_mismatch();
  test_stop_old_failure_preserves_old();
  test_start_failure_rolls_back();
  test_confirmation_failure_rolls_back();
  test_persistence_rejection_rolls_back_marker_last();
  test_indeterminate_commit_requires_reboot();
  test_restore_failure_requires_reboot();
  test_success_commits_after_round_trip();
  test_first_enrollment();
  test_first_enrollment_persistence_rejection();
  std::cout << "stage2d3 activation transaction fault matrix passed\n";
  return 0;
}
