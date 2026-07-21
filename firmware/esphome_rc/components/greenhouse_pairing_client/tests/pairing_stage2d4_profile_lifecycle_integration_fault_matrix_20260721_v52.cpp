#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "pairing_profile_lifecycle_integration.h"

using namespace esphome::greenhouse_pairing_client;

class MemoryBackend final : public PairingPersistenceBackend {
 public:
  struct Pending {
    bool erase{false};
    std::vector<uint8_t> value;
  };

  PersistenceReadResult read_blob(const char *key,
                                  std::vector<uint8_t> *value) override {
    if (reads_fail_ || key == nullptr || value == nullptr)
      return PersistenceReadResult::ERROR;
    const auto pending = pending_.find(key);
    if (pending != pending_.end()) {
      if (pending->second.erase)
        return PersistenceReadResult::NOT_FOUND;
      *value = pending->second.value;
      return PersistenceReadResult::OK;
    }
    const auto found = durable_.find(key);
    if (found == durable_.end())
      return PersistenceReadResult::NOT_FOUND;
    *value = found->second;
    return PersistenceReadResult::OK;
  }

  bool write_blob(const char *key, const uint8_t *value,
                  size_t length) override {
    if (key == nullptr || value == nullptr || length == 0)
      return false;
    if (!fail_write_key_.empty() && fail_write_key_ == key) {
      fail_write_key_.clear();
      if (reads_fail_after_write_failure_)
        reads_fail_ = true;
      return false;
    }
    if (std::string(key) == "active" && confirm_flag_ != nullptr &&
        !*confirm_flag_)
      commit_before_confirm_ = true;
    pending_[key] = Pending{false, std::vector<uint8_t>(value, value + length)};
    return true;
  }

  bool erase_key(const char *key) override {
    if (key == nullptr)
      return false;
    pending_[key] = Pending{true, {}};
    return true;
  }

  bool commit() override {
    for (const auto &[key, pending] : pending_) {
      if (pending.erase)
        durable_.erase(key);
      else
        durable_[key] = pending.value;
    }
    pending_.clear();
    return true;
  }

  void fail_next_write_to(const std::string &key,
                          bool fail_following_reads = false) {
    fail_write_key_ = key;
    reads_fail_after_write_failure_ = fail_following_reads;
  }
  void set_confirm_flag(const bool *flag) { confirm_flag_ = flag; }
  bool commit_before_confirm() const { return commit_before_confirm_; }

 private:
  std::map<std::string, std::vector<uint8_t>> durable_;
  std::map<std::string, Pending> pending_;
  std::string fail_write_key_;
  bool reads_fail_after_write_failure_{false};
  bool reads_fail_{false};
  const bool *confirm_flag_{nullptr};
  bool commit_before_confirm_{false};
};

RamCredentialBundle make_credentials(uint32_t generation) {
  RamCredentialBundle bundle;
  bundle.schema = "gh.pair.credentials/1";
  bundle.system_id = "greenhouse";
  bundle.node_id = "node-" + std::to_string(generation);
  bundle.broker_host = "broker.local";
  bundle.broker_port = 8883;
  bundle.broker_tls_server_name = "broker.local";
  bundle.ca_pem =
      "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n";
  bundle.mqtt_username = "node_user_" + std::to_string(generation);
  bundle.mqtt_client_id = "node_client_" + std::to_string(generation);
  bundle.credential_generation = generation;
  bundle.mqtt_password = "test-value-" + std::to_string(generation);
  assert(bundle.valid());
  return bundle;
}

class FakeCandidateTransport final : public CandidateMqttTransport {
 public:
  bool create(const CandidateMqttProfile &profile,
              const CandidateMqttProbeExchange &exchange) override {
    if (fail_create_ || live_ || !profile.valid() || !exchange.valid())
      return false;
    generation_ = profile.credential_generation;
    live_ = true;
    return true;
  }
  bool start() override { return live_ && !fail_start_; }
  bool poll(CandidateMqttTransportObservation *output) override {
    if (!live_ || output == nullptr || observations_.empty())
      return false;
    *output = observations_.front();
    observations_.erase(observations_.begin());
    return true;
  }
  void destroy() override {
    live_ = false;
    destroy_count_++;
  }
  bool live() const override { return live_; }

  void success_sequence() {
    observations_ = {
        {.client_created = true,
         .connected = true,
         .authenticated = true},
        {.client_created = true,
         .connected = true,
         .authenticated = true,
         .subscribe_ready = true},
        {.client_created = true,
         .connected = true,
         .authenticated = true,
         .subscribe_ready = true,
         .telemetry_round_trip = true},
    };
  }
  void authentication_failure() {
    observations_ = {{.client_created = true,
                      .connected = true,
                      .terminal_failure = true,
                      .failure =
                          CandidateMqttProbeFailure::AUTHENTICATION_FAILED}};
  }

  bool fail_create_{false};
  bool fail_start_{false};
  uint32_t generation_{0};
  int destroy_count_{0};

 private:
  bool live_{false};
  std::vector<CandidateMqttTransportObservation> observations_;
};

class FakeLifecycleRuntime final : public ProfileLifecycleRuntime {
 public:
  bool stage_recovered_profiles(
      const RamCredentialBundle *active_credentials,
      const RamCredentialBundle &candidate_credentials) override {
    calls_.push_back("stage");
    if (fail_stage_ || !candidate_credentials.valid())
      return false;
    active_generation_ =
        active_credentials == nullptr ? 0
                                      : active_credentials->credential_generation;
    candidate_generation_ = candidate_credentials.credential_generation;
    old_live_ = active_credentials != nullptr;
    candidate_live_ = false;
    candidate_material_ = true;
    return true;
  }

  bool staged_generations_match(uint32_t active_generation,
                                uint32_t candidate_generation) const override {
    return candidate_material_ && active_generation_ == active_generation &&
           candidate_generation_ == candidate_generation;
  }

  bool stop_old_active() override {
    calls_.push_back("stop_old");
    if (fail_stop_old_)
      return false;
    old_live_ = false;
    return true;
  }
  bool start_candidate() override {
    calls_.push_back("start_candidate");
    if (fail_start_candidate_ || !candidate_material_)
      return false;
    candidate_live_ = true;
    return true;
  }
  bool confirm_candidate_round_trip() override {
    calls_.push_back("confirm_candidate");
    if (fail_confirm_)
      return false;
    confirmed_ = true;
    return true;
  }
  bool stop_candidate() override {
    calls_.push_back("stop_candidate");
    if (fail_stop_candidate_)
      return false;
    candidate_live_ = false;
    return true;
  }
  bool restore_old_active() override {
    calls_.push_back("restore_old");
    if (fail_restore_old_)
      return false;
    old_live_ = active_generation_ != 0;
    return true;
  }
  void quiesce_all() override {
    calls_.push_back("quiesce_all");
    old_live_ = false;
    candidate_live_ = false;
    quiesced_ = true;
  }
  void clear_candidate_material() override {
    calls_.push_back("clear_candidate_material");
    candidate_material_ = false;
    clear_count_++;
  }
  bool old_active_live() const override { return old_live_; }
  bool candidate_active_live() const override { return candidate_live_; }

  bool fail_stage_{false};
  bool fail_stop_old_{false};
  bool fail_start_candidate_{false};
  bool fail_confirm_{false};
  bool fail_stop_candidate_{false};
  bool fail_restore_old_{false};
  bool confirmed_{false};
  bool quiesced_{false};
  int clear_count_{0};
  std::vector<std::string> calls_;

 private:
  uint32_t active_generation_{0};
  uint32_t candidate_generation_{0};
  bool old_live_{false};
  bool candidate_live_{false};
  bool candidate_material_{false};
};

struct Fixture {
  Fixture() : key_provider(key), crypto(&key_provider), store(&backend, &crypto) {
    key.fill(0x4a);
  }

  void prepare_rotation() {
    RamCredentialBundle active = make_credentials(1);
    assert(store.prepare(active));
    assert(store.commit_prepared());
    RamCredentialBundle candidate = make_credentials(2);
    assert(store.prepare(candidate));
  }

  void prepare_first_enrollment() {
    RamCredentialBundle candidate = make_credentials(1);
    assert(store.prepare(candidate));
  }

  std::array<uint8_t, 32> key{};
  MemoryBackend backend;
  FixedPersistenceKeyProvider key_provider;
  PairingPersistenceCrypto crypto;
  PairingPersistentStore store;
  FakeCandidateTransport transport;
  FakeLifecycleRuntime runtime;
  PairingProfileLifecycleIntegration integration;
};

void validate_successfully(Fixture *fixture) {
  fixture->transport.success_sequence();
  assert(fixture->integration.begin_validation("0011223344556677"));
  assert(fixture->integration.poll_validation(100));
  assert(fixture->integration.poll_validation(200));
  assert(fixture->integration.poll_validation(300));
  assert(fixture->integration.snapshot().phase ==
         ProfileLifecyclePhase::VERIFIED);
  assert(!fixture->transport.live());
  assert(fixture->integration.verified_evidence().candidate_verified);
  assert(fixture->integration.verified_evidence()
             .candidate_probe_client_destroyed);
}

void test_rotation_success() {
  Fixture fixture;
  fixture.prepare_rotation();
  fixture.backend.set_confirm_flag(&fixture.runtime.confirmed_);
  assert(fixture.integration.configure(&fixture.store, &fixture.transport,
                                       &fixture.runtime));
  assert(fixture.integration.recover_prepared());
  validate_successfully(&fixture);
  assert(fixture.integration.activate());
  assert(fixture.integration.snapshot().phase ==
         ProfileLifecyclePhase::ACTIVATED);
  assert(fixture.integration.snapshot().active_generation == 2);
  assert(fixture.integration.snapshot().candidate_generation == 0);
  assert(fixture.integration.snapshot().persistence_committed);
  assert(!fixture.backend.commit_before_confirm());
  assert(!fixture.runtime.old_active_live());
  assert(fixture.runtime.candidate_active_live());
  assert(fixture.runtime.clear_count_ == 1);

  PersistentRecoverySnapshot recovery{};
  RamCredentialBundle active;
  assert(fixture.store.recover(&recovery, &active));
  assert(recovery.status == PersistentRecoveryStatus::ACTIVE);
  assert(recovery.active_generation == 2);
  assert(active.valid() && active.credential_generation == 2);
}

void test_first_enrollment_success() {
  Fixture fixture;
  fixture.prepare_first_enrollment();
  fixture.backend.set_confirm_flag(&fixture.runtime.confirmed_);
  assert(fixture.integration.configure(&fixture.store, &fixture.transport,
                                       &fixture.runtime));
  assert(fixture.integration.recover_prepared());
  assert(!fixture.runtime.old_active_live());
  validate_successfully(&fixture);
  assert(fixture.integration.activate());
  assert(fixture.integration.snapshot().active_generation == 1);
  assert(!fixture.backend.commit_before_confirm());
}

void test_validation_failure_preserves_active() {
  Fixture fixture;
  fixture.prepare_rotation();
  assert(fixture.integration.configure(&fixture.store, &fixture.transport,
                                       &fixture.runtime));
  assert(fixture.integration.recover_prepared());
  fixture.transport.authentication_failure();
  assert(fixture.integration.begin_validation("0011223344556677"));
  assert(!fixture.integration.poll_validation(100));
  assert(fixture.integration.snapshot().phase == ProfileLifecyclePhase::FAILED);
  assert(fixture.integration.snapshot().failure ==
         ProfileLifecycleFailure::VALIDATION_FAILED);
  assert(fixture.runtime.old_active_live());
  assert(!fixture.runtime.candidate_active_live());

  PersistentRecoverySnapshot recovery{};
  assert(fixture.store.recover(&recovery));
  assert(recovery.status == PersistentRecoveryStatus::ACTIVE_WITH_PREPARED);
  assert(recovery.active_generation == 1);
  assert(recovery.candidate_generation == 2);
}

void test_commit_rejection_rolls_back() {
  Fixture fixture;
  fixture.prepare_rotation();
  fixture.backend.set_confirm_flag(&fixture.runtime.confirmed_);
  assert(fixture.integration.configure(&fixture.store, &fixture.transport,
                                       &fixture.runtime));
  assert(fixture.integration.recover_prepared());
  validate_successfully(&fixture);
  fixture.backend.fail_next_write_to("active");
  assert(!fixture.integration.activate());
  assert(fixture.integration.snapshot().phase ==
         ProfileLifecyclePhase::ROLLED_BACK);
  assert(fixture.runtime.old_active_live());
  assert(!fixture.runtime.candidate_active_live());
  assert(!fixture.backend.commit_before_confirm());

  PersistentRecoverySnapshot recovery{};
  assert(fixture.store.recover(&recovery));
  assert(recovery.status ==
         PersistentRecoveryStatus::ACTIVE_WITH_COMMITTED_ORPHAN);
  assert(recovery.active_generation == 1);
  assert(recovery.candidate_generation == 2);
}

void test_indeterminate_commit_requires_reboot() {
  Fixture fixture;
  fixture.prepare_rotation();
  fixture.backend.set_confirm_flag(&fixture.runtime.confirmed_);
  assert(fixture.integration.configure(&fixture.store, &fixture.transport,
                                       &fixture.runtime));
  assert(fixture.integration.recover_prepared());
  validate_successfully(&fixture);
  fixture.backend.fail_next_write_to("active", true);
  assert(!fixture.integration.activate());
  assert(fixture.integration.snapshot().phase ==
         ProfileLifecyclePhase::REBOOT_REQUIRED);
  assert(fixture.integration.snapshot().reboot_required);
  assert(fixture.runtime.quiesced_);
  assert(!fixture.runtime.old_active_live());
  assert(!fixture.runtime.candidate_active_live());
}

void test_candidate_confirmation_failure_rolls_back_before_commit() {
  Fixture fixture;
  fixture.prepare_rotation();
  fixture.backend.set_confirm_flag(&fixture.runtime.confirmed_);
  assert(fixture.integration.configure(&fixture.store, &fixture.transport,
                                       &fixture.runtime));
  assert(fixture.integration.recover_prepared());
  validate_successfully(&fixture);
  fixture.runtime.fail_confirm_ = true;
  assert(!fixture.integration.activate());
  assert(fixture.integration.snapshot().phase ==
         ProfileLifecyclePhase::ROLLED_BACK);
  assert(fixture.runtime.old_active_live());
  assert(!fixture.backend.commit_before_confirm());

  PersistentRecoverySnapshot recovery{};
  assert(fixture.store.recover(&recovery));
  assert(recovery.status == PersistentRecoveryStatus::ACTIVE_WITH_PREPARED);
}

void test_runtime_staging_failure_is_closed() {
  Fixture fixture;
  fixture.prepare_rotation();
  fixture.runtime.fail_stage_ = true;
  assert(fixture.integration.configure(&fixture.store, &fixture.transport,
                                       &fixture.runtime));
  assert(!fixture.integration.recover_prepared());
  assert(fixture.integration.snapshot().phase == ProfileLifecyclePhase::FAILED);
  assert(fixture.integration.snapshot().failure ==
         ProfileLifecycleFailure::RUNTIME_STAGE_FAILED);
}

void test_adapter_rejects_generation_drift() {
  Fixture fixture;
  fixture.prepare_rotation();
  PairingPersistentStoreActivationAdapter adapter;
  assert(adapter.configure(&fixture.store, 1, 3));
  assert(!adapter.refresh());
  assert(!adapter.prepared_matches(1, 3));
}

void test_invalid_configuration_and_reset_policy() {
  PairingProfileLifecycleIntegration integration;
  assert(!integration.configure(nullptr, nullptr, nullptr, 500));
  assert(integration.snapshot().failure ==
         ProfileLifecycleFailure::INVALID_CONFIGURATION);
  assert(integration.reset());
  assert(integration.snapshot().phase == ProfileLifecyclePhase::IDLE);
}

int main() {
  test_rotation_success();
  test_first_enrollment_success();
  test_validation_failure_preserves_active();
  test_commit_rejection_rolls_back();
  test_indeterminate_commit_requires_reboot();
  test_candidate_confirmation_failure_rolls_back_before_commit();
  test_runtime_staging_failure_is_closed();
  test_adapter_rejects_generation_drift();
  test_invalid_configuration_and_reset_policy();
  std::cout << "Stage 2D-4 profile lifecycle integration fault matrix passed\n";
  return 0;
}
