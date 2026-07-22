#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <utility>

#include "isolated_acceptance_package.h"

using namespace esphome::greenhouse_pairing_client;

namespace {

constexpr const char *kFirmwareSha =
    "1111111111111111111111111111111111111111";
constexpr const char *kConfigDigest =
    "2222222222222222222222222222222222222222222222222222222222222222";
constexpr const char *kBrokerDigest =
    "3333333333333333333333333333333333333333333333333333333333333333";
constexpr const char *kPrepareAuthorization =
    "4444444444444444444444444444444444444444444444444444444444444444";
constexpr const char *kActivateAuthorization =
    "5555555555555555555555555555555555555555555555555555555555555555";
constexpr const char *kCleanupAuthorization =
    "6666666666666666666666666666666666666666666666666666666666666666";
constexpr const char *kBrokerHost = "isolated-broker.test.invalid";
constexpr const char *kBrokerPassword = "stage2d7-secret-password";
constexpr const char *kCaPem = "-----BEGIN CERTIFICATE-----TEST-ONLY-----END CERTIFICATE-----";

class MemoryEvidenceSink final : public IsolatedAcceptanceEvidenceSink {
 public:
  bool write_redacted_json(const std::string &json) override {
    calls++;
    if (!ok)
      return false;
    last_json = json;
    return true;
  }

  bool ok{true};
  int calls{0};
  std::string last_json;
};

class FakeIsolatedAcceptanceDriver final : public IsolatedAcceptanceDriver {
 public:
  bool inspect_read_only(IsolatedAcceptanceDriverSnapshot *snapshot) override {
    inspect_calls++;
    if (snapshot == nullptr || !inspect_ok)
      return false;
    snapshot_.read_only_observed = true;
    snapshot_.active_session_live = false;
    snapshot_.candidate_session_live = false;
    snapshot_.probe_session_live = false;
    snapshot_.persistence_status =
        snapshot_.active_generation == 0 ? "empty" : "active";
    snapshot_.controller_phase = "recovered_offline";
    *snapshot = snapshot_;
    return true;
  }

  bool prepare_candidate(const IsolatedCandidateProfile &candidate,
                         IsolatedAcceptanceDriverSnapshot *snapshot) override {
    prepare_calls++;
    if (snapshot == nullptr || !prepare_ok || !candidate.valid())
      return false;
    snapshot_.persistent_write_count++;
    snapshot_.candidate_generation = generation_drift_on_prepare
                                         ? candidate.credential_generation + 1
                                         : candidate.credential_generation;
    snapshot_.persistence_status =
        snapshot_.active_generation == 0 ? "no_active_prepared"
                                         : "active_with_prepared";
    snapshot_.controller_phase = "prepared";
    *snapshot = snapshot_;
    return true;
  }

  bool begin_validation(IsolatedAcceptanceDriverSnapshot *snapshot) override {
    begin_validation_calls++;
    if (snapshot == nullptr || !begin_validation_ok)
      return false;
    snapshot_.probe_session_live = true;
    snapshot_.validation_complete = false;
    snapshot_.validation_success = false;
    snapshot_.controller_phase = "validating";
    *snapshot = snapshot_;
    return true;
  }

  bool poll_validation(uint32_t elapsed_ms,
                       IsolatedAcceptanceDriverSnapshot *snapshot) override {
    poll_validation_calls++;
    if (snapshot == nullptr || elapsed_ms == 0 || !poll_validation_ok)
      return false;
    if (validation_finishes_on_poll && poll_validation_calls >= 2) {
      snapshot_.probe_session_live = false;
      snapshot_.validation_complete = true;
      snapshot_.validation_success = validation_success;
      snapshot_.controller_phase = validation_success ? "verified" : "failed";
      if (!validation_success) {
        snapshot_.failure_injection_point = "candidate_validation";
        snapshot_.rollback_result = "active_unchanged";
        snapshot_.rollback_completed = true;
      }
    }
    *snapshot = snapshot_;
    return true;
  }

  bool activate(ProfileLifecycleMutationAuthorizer *authorizer,
                IsolatedAcceptanceDriverSnapshot *snapshot) override {
    activate_calls++;
    if (snapshot == nullptr || !activate_ok)
      return false;

    bool authorized = false;
    if (skip_authorizer_call) {
      authorized = true;
    } else if (authorizer != nullptr) {
      const uint32_t candidate = generation_drift_on_activate
                                     ? snapshot_.candidate_generation + 1
                                     : snapshot_.candidate_generation;
      authorized = authorizer->authorize(
          ProfileLifecycleMutationOperation::COMMIT_PREPARED_PROFILE,
          snapshot_.active_generation, candidate);
    }
    if (!authorized) {
      snapshot_.failure_injection_point = "mutation_authorization";
      snapshot_.rollback_result = "old_active_retained";
      snapshot_.rollback_completed = true;
      *snapshot = snapshot_;
      return false;
    }

    snapshot_.active_session_live = false;
    snapshot_.candidate_session_live = true;
    snapshot_.persistent_write_count++;
    snapshot_.marker_last_observed = marker_last_observed;
    snapshot_.activation_complete = true;
    snapshot_.activation_success = true;
    snapshot_.active_generation = snapshot_.candidate_generation;
    snapshot_.candidate_generation = 0;
    snapshot_.candidate_session_live = false;
    snapshot_.active_session_live = true;
    snapshot_.persistence_status = "active";
    snapshot_.controller_phase = "activated";
    *snapshot = snapshot_;
    return true;
  }

  bool cleanup_test_state(IsolatedAcceptanceDriverSnapshot *snapshot) override {
    cleanup_calls++;
    if (snapshot == nullptr || !cleanup_ok)
      return false;
    snapshot_.persistent_write_count++;
    snapshot_.active_session_live = false;
    snapshot_.candidate_session_live = false;
    snapshot_.probe_session_live = false;
    snapshot_.candidate_generation = 0;
    snapshot_.cleanup_confirmed = true;
    snapshot_.controller_phase = "cleaned";
    snapshot_.persistence_status = cleanup_removes_active ? "empty" : "active";
    if (cleanup_removes_active)
      snapshot_.active_generation = 0;
    *snapshot = snapshot_;
    return true;
  }

  void quiesce_for_reboot() override {
    quiesce_calls++;
    snapshot_.active_session_live = false;
    snapshot_.candidate_session_live = false;
    snapshot_.probe_session_live = false;
    snapshot_.reboot_required = true;
    snapshot_.controller_phase = "reboot_required";
  }

  void set_active_generation(uint32_t generation) {
    snapshot_.active_generation = generation;
    snapshot_.candidate_generation = 0;
    snapshot_.persistence_status = generation == 0 ? "empty" : "active";
  }

  bool inspect_ok{true};
  bool prepare_ok{true};
  bool begin_validation_ok{true};
  bool poll_validation_ok{true};
  bool validation_finishes_on_poll{true};
  bool validation_success{true};
  bool activate_ok{true};
  bool cleanup_ok{true};
  bool generation_drift_on_prepare{false};
  bool generation_drift_on_activate{false};
  bool skip_authorizer_call{false};
  bool marker_last_observed{true};
  bool cleanup_removes_active{true};
  int inspect_calls{0};
  int prepare_calls{0};
  int begin_validation_calls{0};
  int poll_validation_calls{0};
  int activate_calls{0};
  int cleanup_calls{0};
  int quiesce_calls{0};

 private:
  IsolatedAcceptanceDriverSnapshot snapshot_{};
};

IsolatedAcceptanceTestConfiguration make_configuration(
    uint32_t candidate_generation = 2) {
  IsolatedAcceptanceTestConfiguration config;
  config.schema = "gh.h3.n2.stage2d7-isolated-test-config/1";
  config.firmware_commit_sha = kFirmwareSha;
  config.configuration_digest = kConfigDigest;
  config.broker_configuration_digest = kBrokerDigest;
  config.test_device_identifier = "gh-test-device-001";
  config.candidate.schema = "gh.h3.n2.isolated-candidate-profile/1";
  config.candidate.test_run_id = "gh-test-run-20260721-v55";
  config.candidate.system_id = "gh-test-system-001";
  config.candidate.node_id = "gh-test-node-001";
  config.candidate.broker_host = kBrokerHost;
  config.candidate.broker_port = 18884;
  config.candidate.broker_tls_server_name = "broker.test.invalid";
  config.candidate.ca_pem = kCaPem;
  config.candidate.mqtt_username = "gh-test-user-001";
  config.candidate.mqtt_client_id =
      "gh-test-client-gh-test-run-20260721-v55";
  config.candidate.mqtt_password = kBrokerPassword;
  config.candidate.test_topic_root =
      "gh-test/gh-test-run-20260721-v55/node-001";
  config.candidate.credential_generation = candidate_generation;
  return config;
}

std::array<uint8_t, 32> make_test_key() {
  std::array<uint8_t, 32> key{};
  for (size_t index = 0; index < key.size(); index++)
    key[index] = static_cast<uint8_t>(index + 1U);
  return key;
}

void reach_verified(IsolatedAcceptancePackage *package,
                    FakeIsolatedAcceptanceDriver *driver,
                    VolatileTestPersistenceKeyProvider *key_provider,
                    uint32_t active_generation = 1,
                    uint32_t candidate_generation = 2) {
  assert(package != nullptr);
  assert(driver != nullptr);
  assert(key_provider != nullptr);
  driver->set_active_generation(active_generation);
  assert(package->inspect_read_only());
  assert(key_provider->load(make_test_key()));
  assert(package->load_test_configuration(
      make_configuration(candidate_generation)));
  assert(package->grant_write_authorization(
      IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE,
      active_generation, candidate_generation, kPrepareAuthorization));
  assert(package->prepare_candidate());
  assert(package->begin_validation());
  assert(package->poll_validation(100));
  assert(package->poll_validation(100));
  assert(package->snapshot().phase == IsolatedAcceptancePhase::VERIFIED);
}

void test_default_offline_and_key_required() {
  FakeIsolatedAcceptanceDriver driver;
  MemoryEvidenceSink sink;
  VolatileTestPersistenceKeyProvider key_provider;
  IsolatedAcceptancePackage package;
  assert(package.configure(&driver, &key_provider, &sink));
  driver.set_active_generation(1);
  assert(package.inspect_read_only());
  assert(driver.prepare_calls == 0);
  assert(driver.activate_calls == 0);
  assert(package.snapshot().driver.persistent_write_count == 0);
  assert(!package.load_test_configuration(make_configuration()));
  assert(package.snapshot().failure ==
         IsolatedAcceptanceFailure::TEST_KEY_REQUIRED);
  assert(package.snapshot().phase == IsolatedAcceptancePhase::READ_ONLY);
}

void test_key_provider_is_volatile_and_has_no_default() {
  VolatileTestPersistenceKeyProvider key_provider;
  std::array<uint8_t, 32> output{};
  assert(!key_provider.loaded());
  assert(!key_provider.derive_key(CredentialSlot::A, 1, &output));
  std::array<uint8_t, 32> zero{};
  assert(!key_provider.load(zero));
  assert(key_provider.load(make_test_key()));
  assert(key_provider.derive_key(CredentialSlot::A, 1, &output));
  assert(output != make_test_key());
  key_provider.destroy();
  assert(!key_provider.loaded());
  assert(!key_provider.derive_key(CredentialSlot::A, 1, &output));
}

void test_successful_reversible_flow_and_redacted_evidence() {
  FakeIsolatedAcceptanceDriver driver;
  MemoryEvidenceSink sink;
  VolatileTestPersistenceKeyProvider key_provider;
  IsolatedAcceptancePackage package;
  assert(package.configure(&driver, &key_provider, &sink));
  driver.set_active_generation(1);
  assert(package.inspect_read_only());
  assert(key_provider.load(make_test_key()));
  assert(package.load_test_configuration(make_configuration()));

  assert(!package.prepare_candidate());
  assert(package.snapshot().failure ==
         IsolatedAcceptanceFailure::AUTHORIZATION_NOT_ARMED);
  assert(package.snapshot().phase ==
         IsolatedAcceptancePhase::CONFIG_LOADED);
  assert(!package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE, 0, 2,
      kPrepareAuthorization));
  assert(package.snapshot().failure ==
         IsolatedAcceptanceFailure::GENERATION_MISMATCH);
  assert(package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE, 1, 2,
      kPrepareAuthorization));
  assert(package.prepare_candidate());
  assert(package.snapshot().write_authorization_consumed);
  assert(driver.prepare_calls == 1);

  assert(package.begin_validation());
  assert(package.poll_validation(100));
  assert(package.snapshot().phase == IsolatedAcceptancePhase::VALIDATING);
  assert(package.poll_validation(100));
  assert(package.snapshot().phase == IsolatedAcceptancePhase::VERIFIED);

  assert(!package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      "not-a-digest"));
  assert(package.snapshot().phase == IsolatedAcceptancePhase::VERIFIED);
  assert(package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(package.activate());
  assert(package.snapshot().phase == IsolatedAcceptancePhase::ACTIVATED);
  assert(package.snapshot().active_generation == 2);
  assert(package.snapshot().candidate_generation == 0);
  assert(package.snapshot().driver.marker_last_observed);

  sink.ok = false;
  assert(!package.export_evidence());
  assert(package.snapshot().phase == IsolatedAcceptancePhase::ACTIVATED);
  sink.ok = true;
  assert(package.export_evidence());
  assert(sink.last_json.find(kFirmwareSha) != std::string::npos);
  assert(sink.last_json.find(kConfigDigest) != std::string::npos);
  assert(sink.last_json.find("\"marker_last_observed\":true") !=
         std::string::npos);
  assert(sink.last_json.find(kBrokerHost) == std::string::npos);
  assert(sink.last_json.find(kBrokerPassword) == std::string::npos);
  assert(sink.last_json.find(kCaPem) == std::string::npos);
  assert(sink.last_json.find(kPrepareAuthorization) == std::string::npos);
  assert(sink.last_json.find(kActivateAuthorization) == std::string::npos);

  assert(!package.cleanup_test_state());
  assert(package.snapshot().failure ==
         IsolatedAcceptanceFailure::AUTHORIZATION_NOT_ARMED);
  assert(package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE, 2, 0,
      kCleanupAuthorization));
  assert(package.cleanup_test_state());
  assert(package.snapshot().phase == IsolatedAcceptancePhase::CLEANED);
  assert(package.snapshot().cleanup_confirmed);
  assert(!key_provider.loaded());
  assert(package.export_evidence());
  assert(sink.last_json.find("\"cleanup_confirmed\":true") !=
         std::string::npos);
}

void test_one_shot_authorization_and_reboot_clearing() {
  OneShotGenerationAuthorization authorization;
  assert(authorization.arm(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(authorization.authorize(
      ProfileLifecycleMutationOperation::COMMIT_PREPARED_PROFILE, 1, 2));
  assert(!authorization.authorize(
      ProfileLifecycleMutationOperation::COMMIT_PREPARED_PROFILE, 1, 2));

  FakeIsolatedAcceptanceDriver driver;
  MemoryEvidenceSink sink;
  VolatileTestPersistenceKeyProvider key_provider;
  IsolatedAcceptancePackage package;
  assert(package.configure(&driver, &key_provider, &sink));
  reach_verified(&package, &driver, &key_provider);
  assert(package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  package.quiesce_for_reboot();
  assert(package.snapshot().phase ==
         IsolatedAcceptancePhase::REBOOT_REQUIRED);
  assert(!package.snapshot().write_authorization_armed);
  assert(!key_provider.loaded());
}

void test_generation_drift_fails_closed() {
  FakeIsolatedAcceptanceDriver driver;
  MemoryEvidenceSink sink;
  VolatileTestPersistenceKeyProvider key_provider;
  IsolatedAcceptancePackage package;
  assert(package.configure(&driver, &key_provider, &sink));
  reach_verified(&package, &driver, &key_provider);
  driver.generation_drift_on_activate = true;
  assert(package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(!package.activate());
  assert(package.snapshot().phase ==
         IsolatedAcceptancePhase::REBOOT_REQUIRED);
  assert(package.snapshot().failure ==
         IsolatedAcceptanceFailure::AUTHORIZATION_NOT_CONSUMED);
  assert(driver.quiesce_calls >= 1);
  assert(!key_provider.loaded());
}

void test_driver_cannot_bypass_authorizer() {
  FakeIsolatedAcceptanceDriver driver;
  MemoryEvidenceSink sink;
  VolatileTestPersistenceKeyProvider key_provider;
  IsolatedAcceptancePackage package;
  assert(package.configure(&driver, &key_provider, &sink));
  reach_verified(&package, &driver, &key_provider);
  driver.skip_authorizer_call = true;
  assert(package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(!package.activate());
  assert(package.snapshot().phase ==
         IsolatedAcceptancePhase::REBOOT_REQUIRED);
  assert(package.snapshot().failure ==
         IsolatedAcceptanceFailure::AUTHORIZATION_NOT_CONSUMED);
}

void test_validation_failure_can_be_evidenced_and_cleaned() {
  FakeIsolatedAcceptanceDriver driver;
  MemoryEvidenceSink sink;
  VolatileTestPersistenceKeyProvider key_provider;
  IsolatedAcceptancePackage package;
  assert(package.configure(&driver, &key_provider, &sink));
  driver.set_active_generation(1);
  assert(package.inspect_read_only());
  assert(key_provider.load(make_test_key()));
  assert(package.load_test_configuration(make_configuration()));
  assert(package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE, 1, 2,
      kPrepareAuthorization));
  assert(package.prepare_candidate());
  driver.validation_success = false;
  assert(package.begin_validation());
  assert(package.poll_validation(100));
  assert(!package.poll_validation(100));
  assert(package.snapshot().phase == IsolatedAcceptancePhase::FAILED);
  assert(package.export_evidence());
  assert(sink.last_json.find("candidate_validation") != std::string::npos);
  assert(sink.last_json.find("active_unchanged") != std::string::npos);
  assert(package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE, 1, 2,
      kCleanupAuthorization));
  assert(package.cleanup_test_state());
}

void test_marker_last_missing_requires_reboot() {
  FakeIsolatedAcceptanceDriver driver;
  MemoryEvidenceSink sink;
  VolatileTestPersistenceKeyProvider key_provider;
  IsolatedAcceptancePackage package;
  assert(package.configure(&driver, &key_provider, &sink));
  reach_verified(&package, &driver, &key_provider);
  driver.marker_last_observed = false;
  assert(package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(!package.activate());
  assert(package.snapshot().phase ==
         IsolatedAcceptancePhase::REBOOT_REQUIRED);
  assert(package.snapshot().failure ==
         IsolatedAcceptanceFailure::ACTIVATION_FAILED);
}

}  // namespace

int main() {
  test_default_offline_and_key_required();
  test_key_provider_is_volatile_and_has_no_default();
  test_successful_reversible_flow_and_redacted_evidence();
  test_one_shot_authorization_and_reboot_clearing();
  test_generation_drift_fails_closed();
  test_driver_cannot_bypass_authorizer();
  test_validation_failure_can_be_evidenced_and_cleaned();
  test_marker_last_missing_requires_reboot();
  std::cout << "stage2d7_isolated_acceptance_fault_matrix=pass\n";
  return 0;
}
