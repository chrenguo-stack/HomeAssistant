#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <utility>

#include "isolated_device_driver.h"

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

void clone_bundle(const RamCredentialBundle &source,
                  RamCredentialBundle *target) {
  assert(target != nullptr);
  target->clear();
  target->schema = source.schema;
  target->system_id = source.system_id;
  target->node_id = source.node_id;
  target->broker_host = source.broker_host;
  target->broker_port = source.broker_port;
  target->broker_tls_server_name = source.broker_tls_server_name;
  target->ca_pem = source.ca_pem;
  target->mqtt_username = source.mqtt_username;
  target->mqtt_client_id = source.mqtt_client_id;
  target->credential_generation = source.credential_generation;
  target->mqtt_password = source.mqtt_password;
}

RamCredentialBundle make_bundle(uint32_t generation) {
  RamCredentialBundle bundle;
  bundle.schema = "gh.pair.credentials/1";
  bundle.system_id = "gh-test-system-001";
  bundle.node_id = "gh-test-node-001";
  bundle.broker_host = "broker.test.local";
  bundle.broker_port = 8884;
  bundle.broker_tls_server_name = "broker.test.local";
  bundle.ca_pem =
      "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----";
  bundle.mqtt_username = "gh-test-user-001";
  bundle.mqtt_client_id = "gh-test-client-001";
  bundle.credential_generation = generation;
  bundle.mqtt_password = "test-only-password";
  return bundle;
}

IsolatedAcceptanceTestConfiguration make_configuration(
    uint32_t candidate_generation = 2) {
  IsolatedAcceptanceTestConfiguration config;
  config.schema = "gh.h3.n2.stage2d7-isolated-test-config/1";
  config.firmware_commit_sha = kFirmwareSha;
  config.configuration_digest = kConfigDigest;
  config.broker_configuration_digest = kBrokerDigest;
  config.test_device_identifier = "gh-test-device-001";
  config.candidate.schema = "gh.h3.n2.isolated-candidate-profile/1";
  config.candidate.test_run_id = "gh-test-run-20260721-v56";
  config.candidate.system_id = "gh-test-system-001";
  config.candidate.node_id = "gh-test-node-001";
  config.candidate.broker_host = "broker.test.local";
  config.candidate.broker_port = 8884;
  config.candidate.broker_tls_server_name = "broker.test.local";
  config.candidate.ca_pem =
      "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----";
  config.candidate.mqtt_username = "gh-test-user-001";
  config.candidate.mqtt_client_id =
      "gh-test-client-gh-test-run-20260721-v56";
  config.candidate.mqtt_password = "test-only-password";
  config.candidate.test_topic_root =
      "gh-test/gh-test-run-20260721-v56/node-001";
  config.candidate.credential_generation = candidate_generation;
  return config;
}

std::array<uint8_t, 32> make_key() {
  std::array<uint8_t, 32> key{};
  for (size_t index = 0; index < key.size(); index++)
    key[index] = static_cast<uint8_t>(index + 1U);
  return key;
}

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

class FakePersistencePort final : public IsolatedDevicePersistencePort {
 public:
  bool configure(const IsolatedDeviceDriverConfig &config,
                 VolatileTestPersistenceKeyProvider *provider) override {
    configure_calls++;
    configured = config.valid() && provider != nullptr && configure_ok;
    return configured;
  }

  bool inspect_read_only(IsolatedDevicePersistenceSnapshot *snapshot,
                         RamCredentialBundle *active,
                         RamCredentialBundle *candidate) override {
    inspect_calls++;
    if (!configured || snapshot == nullptr || !inspect_ok)
      return false;
    if (drift_write_count_on_inspect)
      write_count++;
    *snapshot = make_snapshot();
    snapshot->read_only_opened = true;
    snapshot->recovery_valid = true;
    if (active != nullptr) {
      active->clear();
      if (active_generation != 0) {
        RamCredentialBundle value = make_bundle(active_generation);
        clone_bundle(value, active);
      }
    }
    if (candidate != nullptr) {
      candidate->clear();
      if (candidate_generation != 0) {
        RamCredentialBundle value = make_bundle(candidate_generation);
        clone_bundle(value, candidate);
      }
    }
    return true;
  }

  bool prepare_candidate(const RamCredentialBundle &candidate,
                         IsolatedDevicePersistenceSnapshot *snapshot) override {
    prepare_calls++;
    if (!configured || snapshot == nullptr || !prepare_ok ||
        !candidate.valid())
      return false;
    candidate_generation = candidate.credential_generation;
    write_count++;
    recovery_status = active_generation == 0 ? "no_active_prepared"
                                             : "active_with_prepared";
    *snapshot = make_snapshot();
    return true;
  }

  bool commit_prepared(IsolatedDevicePersistenceSnapshot *snapshot,
                       RamCredentialBundle *new_active) override {
    commit_calls++;
    if (!configured || snapshot == nullptr || new_active == nullptr ||
        candidate_generation == 0)
      return false;
    write_count += commit_write_increments;
    if (!commit_ok) {
      if (marker_committed_on_failure) {
        active_generation = candidate_generation;
        candidate_generation = 0;
        recovery_status = "active";
      }
      *snapshot = make_snapshot();
      snapshot->marker_committed = marker_committed_on_failure;
      snapshot->marker_last_observed = false;
      return false;
    }
    active_generation = candidate_generation;
    candidate_generation = 0;
    recovery_status = "active";
    RamCredentialBundle value = make_bundle(active_generation);
    clone_bundle(value, new_active);
    *snapshot = make_snapshot();
    snapshot->marker_committed = true;
    snapshot->marker_last_observed = marker_last;
    return true;
  }

  bool cleanup_test_namespace(
      IsolatedDevicePersistenceSnapshot *snapshot) override {
    cleanup_calls++;
    if (!configured || snapshot == nullptr || !cleanup_ok)
      return false;
    active_generation = 0;
    candidate_generation = 0;
    recovery_status = "empty";
    write_count++;
    *snapshot = make_snapshot();
    snapshot->cleanup_confirmed = true;
    return true;
  }

  void quiesce() override { quiesce_calls++; }

  IsolatedDevicePersistenceSnapshot make_snapshot() const {
    IsolatedDevicePersistenceSnapshot snapshot;
    snapshot.read_only_opened = true;
    snapshot.recovery_valid = true;
    snapshot.recovery_status = recovery_status;
    snapshot.active_generation = active_generation;
    snapshot.candidate_generation = candidate_generation;
    snapshot.marker_committed = active_generation != 0;
    snapshot.marker_last_observed = marker_last && active_generation != 0;
    snapshot.persistent_write_count = write_count;
    return snapshot;
  }

  bool configure_ok{true};
  bool inspect_ok{true};
  bool prepare_ok{true};
  bool commit_ok{true};
  bool cleanup_ok{true};
  bool marker_last{true};
  bool marker_committed_on_failure{false};
  bool drift_write_count_on_inspect{false};
  bool configured{false};
  uint32_t active_generation{1};
  uint32_t candidate_generation{0};
  uint32_t write_count{0};
  uint32_t commit_write_increments{2};
  std::string recovery_status{"active"};
  int configure_calls{0};
  int inspect_calls{0};
  int prepare_calls{0};
  int commit_calls{0};
  int cleanup_calls{0};
  int quiesce_calls{0};
};

class FakeMqttPort final : public IsolatedDeviceMqttPort {
 public:
  bool configure(const RamCredentialBundle *active,
                 const IsolatedCandidateProfile &candidate,
                 uint32_t validation_timeout_ms,
                 uint32_t activation_timeout_ms) override {
    configure_calls++;
    if (!configure_ok || !candidate.valid() || validation_timeout_ms < 1000 ||
        activation_timeout_ms < 1000)
      return false;
    has_active = active != nullptr && active->valid();
    configured = true;
    return true;
  }

  bool begin_validation(IsolatedDeviceMqttSnapshot *snapshot) override {
    begin_validation_calls++;
    if (!configured || snapshot == nullptr || !begin_validation_ok)
      return false;
    active_live = has_active;
    probe_live = true;
    *snapshot = make_snapshot();
    return true;
  }

  bool poll_validation(uint32_t elapsed_ms,
                       IsolatedDeviceMqttSnapshot *snapshot) override {
    poll_calls++;
    if (!configured || snapshot == nullptr || elapsed_ms == 0 || !poll_ok)
      return false;
    if (poll_calls >= polls_to_complete) {
      validation_complete = true;
      validation_success = validation_ok;
      probe_live = false;
      if (!validation_ok)
        failure_point = "validation_injected";
    }
    *snapshot = make_snapshot();
    return true;
  }

  bool begin_activation(IsolatedDeviceMqttSnapshot *snapshot) override {
    begin_activation_calls++;
    if (!configured || !validation_complete || !validation_success ||
        snapshot == nullptr || !begin_activation_ok)
      return false;
    candidate_live = true;
    *snapshot = make_snapshot();
    return true;
  }

  bool rollback_activation(IsolatedDeviceMqttSnapshot *snapshot) override {
    rollback_calls++;
    if (snapshot == nullptr || !rollback_ok)
      return false;
    candidate_live = false;
    rollback_complete = !has_active || active_live;
    rollback_result = rollback_complete ? "old_active_retained"
                                        : "old_active_unavailable";
    *snapshot = make_snapshot();
    return rollback_complete;
  }

  bool promote_candidate(IsolatedDeviceMqttSnapshot *snapshot) override {
    promote_calls++;
    if (snapshot == nullptr || !promote_ok || !candidate_live)
      return false;
    active_live = true;
    candidate_live = false;
    promotion_complete = true;
    *snapshot = make_snapshot();
    return true;
  }

  void quiesce() override {
    quiesce_calls++;
    active_live = false;
    candidate_live = false;
    probe_live = false;
  }

  IsolatedDeviceMqttSnapshot make_snapshot() const {
    IsolatedDeviceMqttSnapshot snapshot;
    snapshot.configured = configured;
    snapshot.validation_complete = validation_complete;
    snapshot.validation_success = validation_success;
    snapshot.active_session_live = active_live;
    snapshot.candidate_session_live = candidate_live;
    snapshot.probe_session_live = probe_live;
    snapshot.rollback_completed = rollback_complete;
    snapshot.promotion_complete = promotion_complete;
    snapshot.failure_point = failure_point;
    snapshot.rollback_result = rollback_result;
    return snapshot;
  }

  bool configure_ok{true};
  bool begin_validation_ok{true};
  bool poll_ok{true};
  bool validation_ok{true};
  bool begin_activation_ok{true};
  bool rollback_ok{true};
  bool promote_ok{true};
  bool configured{false};
  bool has_active{false};
  bool active_live{false};
  bool candidate_live{false};
  bool probe_live{false};
  bool validation_complete{false};
  bool validation_success{false};
  bool rollback_complete{false};
  bool promotion_complete{false};
  int polls_to_complete{2};
  int configure_calls{0};
  int begin_validation_calls{0};
  int poll_calls{0};
  int begin_activation_calls{0};
  int rollback_calls{0};
  int promote_calls{0};
  int quiesce_calls{0};
  std::string failure_point{"none"};
  std::string rollback_result{"not_applicable"};
};

struct Fixture {
  FakePersistencePort persistence;
  FakeMqttPort mqtt;
  VolatileTestPersistenceKeyProvider key_provider;
  IsolatedDeviceDriver driver;
  MemoryEvidenceSink sink;
  IsolatedAcceptancePackage package;
  IsolatedDeviceAuthorizationBinder binder;

  void configure(uint32_t active_generation = 1) {
    persistence.active_generation = active_generation;
    persistence.recovery_status = active_generation == 0 ? "empty" : "active";
    IsolatedDeviceDriverConfig driver_config;
    driver_config.partition_label = "gh2d8_test";
    driver_config.namespace_name = "gh2d8_state";
    assert(driver.configure(driver_config, &persistence, &mqtt, &key_provider));
    assert(package.configure(&driver, &key_provider, &sink));
    assert(binder.configure(&package, &driver));
    assert(key_provider.load(make_key()));
    assert(package.inspect_read_only());
  }

  void prepare(uint32_t candidate_generation = 2) {
    assert(package.load_test_configuration(
        make_configuration(candidate_generation)));
    assert(binder.grant(IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE,
                        package.snapshot().active_generation,
                        candidate_generation, kPrepareAuthorization));
    assert(package.prepare_candidate());
  }

  void verify(uint32_t candidate_generation = 2) {
    prepare(candidate_generation);
    assert(package.begin_validation());
    assert(package.poll_validation(100));
    assert(package.poll_validation(100));
    assert(package.snapshot().phase == IsolatedAcceptancePhase::VERIFIED);
  }
};

void test_default_off_and_storage_boundary() {
  IsolatedDeviceDriverConfig invalid;
  invalid.partition_label = "nvs";
  invalid.namespace_name = "production";
  assert(!invalid.valid());

  Fixture fixture;
  fixture.configure();
  assert(fixture.persistence.inspect_calls == 1);
  assert(fixture.mqtt.configure_calls == 0);
  assert(fixture.persistence.write_count == 0);
  assert(!fixture.package.snapshot().driver.active_session_live);
  assert(!fixture.package.snapshot().driver.candidate_session_live);
  assert(!fixture.package.snapshot().driver.probe_session_live);
}

void test_driver_requires_mirrored_prepare_grant() {
  Fixture fixture;
  fixture.configure();
  assert(fixture.package.load_test_configuration(make_configuration()));
  assert(fixture.package.grant_write_authorization(
      IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE, 1, 2,
      kPrepareAuthorization));
  assert(!fixture.package.prepare_candidate());
  assert(fixture.persistence.prepare_calls == 0);
  assert(fixture.driver.failure() ==
         IsolatedDeviceDriverFailure::WRITE_AUTHORIZATION_NOT_ARMED);
}

void test_complete_reversible_flow() {
  Fixture fixture;
  fixture.configure();
  fixture.verify();
  assert(fixture.binder.grant(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(fixture.package.activate());
  assert(fixture.package.snapshot().phase == IsolatedAcceptancePhase::ACTIVATED);
  assert(fixture.package.snapshot().active_generation == 2);
  assert(fixture.package.snapshot().driver.marker_last_observed);
  assert(fixture.package.export_evidence());
  assert(fixture.sink.last_json.find("broker.test.local") == std::string::npos);
  assert(fixture.sink.last_json.find("test-only-password") == std::string::npos);
  assert(fixture.sink.last_json.find(kActivateAuthorization) ==
         std::string::npos);
  assert(fixture.binder.grant(
      IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE, 2, 0,
      kCleanupAuthorization));
  assert(fixture.package.cleanup_test_state());
  assert(fixture.package.snapshot().phase == IsolatedAcceptancePhase::CLEANED);
  assert(!fixture.key_provider.loaded());
  assert(fixture.persistence.recovery_status == "empty");
  assert(!fixture.package.snapshot().driver.active_session_live);
}

void test_stale_generation_grant_is_rejected_by_both_layers() {
  Fixture fixture;
  fixture.configure();
  assert(fixture.package.load_test_configuration(make_configuration()));
  assert(!fixture.binder.grant(
      IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE, 0, 2,
      kPrepareAuthorization));
  assert(fixture.persistence.prepare_calls == 0);
  assert(!fixture.package.prepare_candidate());
}

void test_validation_failure_keeps_active_authority() {
  Fixture fixture;
  fixture.configure();
  fixture.mqtt.validation_ok = false;
  fixture.prepare();
  assert(fixture.package.begin_validation());
  assert(fixture.package.poll_validation(100));
  assert(!fixture.package.poll_validation(100));
  assert(fixture.package.snapshot().phase == IsolatedAcceptancePhase::FAILED);
  assert(fixture.persistence.active_generation == 1);
  assert(fixture.persistence.candidate_generation == 2);
  assert(fixture.mqtt.active_live);
  assert(!fixture.mqtt.probe_live);
}

void test_commit_failure_rolls_back_without_authority_change() {
  Fixture fixture;
  fixture.configure();
  fixture.verify();
  fixture.persistence.commit_ok = false;
  assert(fixture.binder.grant(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(!fixture.package.activate());
  assert(fixture.package.snapshot().phase == IsolatedAcceptancePhase::FAILED);
  assert(!fixture.package.snapshot().reboot_required);
  assert(fixture.mqtt.rollback_calls == 1);
  assert(fixture.persistence.active_generation == 1);
  assert(fixture.persistence.candidate_generation == 2);
}

void test_marker_commit_failure_is_terminal() {
  Fixture fixture;
  fixture.configure();
  fixture.verify();
  fixture.persistence.commit_ok = false;
  fixture.persistence.marker_committed_on_failure = true;
  assert(fixture.binder.grant(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(!fixture.package.activate());
  assert(fixture.package.snapshot().phase ==
         IsolatedAcceptancePhase::REBOOT_REQUIRED);
  assert(fixture.package.snapshot().reboot_required);
  assert(fixture.mqtt.quiesce_calls > 0);
}

void test_missing_marker_last_proof_is_terminal() {
  Fixture fixture;
  fixture.configure();
  fixture.verify();
  fixture.persistence.marker_last = false;
  assert(fixture.binder.grant(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(!fixture.package.activate());
  assert(fixture.package.snapshot().phase ==
         IsolatedAcceptancePhase::REBOOT_REQUIRED);
  assert(fixture.driver.failure() ==
         IsolatedDeviceDriverFailure::MARKER_LAST_NOT_PROVEN);
}

void test_promotion_failure_after_marker_is_terminal() {
  Fixture fixture;
  fixture.configure();
  fixture.verify();
  fixture.mqtt.promote_ok = false;
  assert(fixture.binder.grant(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kActivateAuthorization));
  assert(!fixture.package.activate());
  assert(fixture.package.snapshot().phase ==
         IsolatedAcceptancePhase::REBOOT_REQUIRED);
  assert(fixture.persistence.active_generation == 2);
}

void test_read_only_write_drift_fails_closed() {
  Fixture fixture;
  fixture.persistence.drift_write_count_on_inspect = true;
  IsolatedDeviceDriverConfig config;
  config.partition_label = "gh2d8_test";
  config.namespace_name = "gh2d8_state";
  assert(fixture.driver.configure(config, &fixture.persistence, &fixture.mqtt,
                                  &fixture.key_provider));
  assert(fixture.package.configure(&fixture.driver, &fixture.key_provider,
                                   &fixture.sink));
  assert(fixture.key_provider.load(make_key()));
  assert(!fixture.package.inspect_read_only());
  assert(fixture.package.snapshot().phase == IsolatedAcceptancePhase::FAILED);
  assert(fixture.mqtt.configure_calls == 0);
}

void test_cleanup_failure_preserves_evidence_and_key() {
  Fixture fixture;
  fixture.configure();
  fixture.verify();
  assert(fixture.package.export_evidence());
  fixture.persistence.cleanup_ok = false;
  assert(fixture.binder.grant(
      IsolatedAcceptanceWriteOperation::CLEANUP_TEST_STATE, 1, 2,
      kCleanupAuthorization));
  assert(!fixture.package.cleanup_test_state());
  assert(fixture.package.snapshot().phase == IsolatedAcceptancePhase::FAILED);
  assert(fixture.key_provider.loaded());
}

}  // namespace

int main() {
  test_default_off_and_storage_boundary();
  test_driver_requires_mirrored_prepare_grant();
  test_complete_reversible_flow();
  test_stale_generation_grant_is_rejected_by_both_layers();
  test_validation_failure_keeps_active_authority();
  test_commit_failure_rolls_back_without_authority_change();
  test_marker_commit_failure_is_terminal();
  test_missing_marker_last_proof_is_terminal();
  test_promotion_failure_after_marker_is_terminal();
  test_read_only_write_drift_fails_closed();
  test_cleanup_failure_preserves_evidence_and_key();
  std::cout << "stage2d8_isolated_device_driver_fault_matrix=pass\n";
  return 0;
}
