#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <utility>

#include "stage2d10_g4_activation_coordinator.h"

using namespace esphome::greenhouse_pairing_client;

namespace {

constexpr const char *kAuthorizationDigest =
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

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

RamCredentialBundle make_bundle(uint32_t generation = 1) {
  RamCredentialBundle bundle;
  bundle.schema = "gh.pair.credentials/1";
  bundle.system_id = "gh-test-system-stage2d10";
  bundle.node_id = "gh-test-node-stage2d10";
  bundle.broker_host = "broker.stage2d10.local";
  bundle.broker_port = 8883;
  bundle.broker_tls_server_name = "broker.stage2d10.local";
  bundle.ca_pem =
      "-----BEGIN CERTIFICATE-----\nSTAGE2D10\n-----END CERTIFICATE-----";
  bundle.mqtt_username = "gh-test-user-stage2d10";
  bundle.mqtt_client_id = "gh-test-client-gh-test-run-stage2d10-v1";
  bundle.credential_generation = generation;
  bundle.mqtt_password = "stage2d10-test-password";
  return bundle;
}

IsolatedCandidateProfile make_candidate(uint32_t generation = 1) {
  IsolatedCandidateProfile candidate;
  candidate.schema = "gh.h3.n2.isolated-candidate-profile/1";
  candidate.test_run_id = "gh-test-run-stage2d10-v1";
  candidate.system_id = "gh-test-system-stage2d10";
  candidate.node_id = "gh-test-node-stage2d10";
  candidate.broker_host = "broker.stage2d10.local";
  candidate.broker_port = 8883;
  candidate.broker_tls_server_name = "broker.stage2d10.local";
  candidate.ca_pem =
      "-----BEGIN CERTIFICATE-----\nSTAGE2D10\n-----END CERTIFICATE-----";
  candidate.mqtt_username = "gh-test-user-stage2d10";
  candidate.mqtt_client_id =
      "gh-test-client-gh-test-run-stage2d10-v1";
  candidate.mqtt_password = "stage2d10-test-password";
  candidate.test_topic_root =
      "gh-test/gh-test-run-stage2d10-v1/node";
  candidate.credential_generation = generation;
  return candidate;
}

std::array<uint8_t, 32> make_key() {
  std::array<uint8_t, 32> key{};
  for (size_t index = 0; index < key.size(); index++)
    key[index] = static_cast<uint8_t>(index + 17U);
  return key;
}

Stage2D10G4Config make_config() {
  Stage2D10G4Config config;
  config.partition_label = "gh2d8_p2d10";
  config.namespace_name = "gh2d8_s2d10";
  config.validation_timeout_ms = 15000;
  config.activation_timeout_ms = 15000;
  config.expected_active_generation = 0;
  config.expected_candidate_generation = 1;
  return config;
}

class FakePersistencePort final : public IsolatedDevicePersistencePort {
 public:
  bool configure(const IsolatedDeviceDriverConfig &config,
                 VolatileTestPersistenceKeyProvider *provider) override {
    configure_calls++;
    configured = configure_ok && config.valid() && provider != nullptr;
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
    if (active != nullptr) {
      active->clear();
      if (active_generation != 0) {
        RamCredentialBundle value = active_bundle.valid()
                                        ? make_copy(active_bundle)
                                        : make_bundle(active_generation);
        clone_bundle(value, active);
        value.clear();
      }
    }
    if (candidate != nullptr) {
      candidate->clear();
      if (candidate_generation != 0) {
        RamCredentialBundle value = candidate_bundle.valid()
                                        ? make_copy(candidate_bundle)
                                        : make_bundle(candidate_generation);
        clone_bundle(value, candidate);
        value.clear();
      }
    }
    return true;
  }

  bool prepare_candidate(const RamCredentialBundle &,
                         IsolatedDevicePersistenceSnapshot *) override {
    prepare_calls++;
    return false;
  }

  bool commit_prepared(IsolatedDevicePersistenceSnapshot *snapshot,
                       RamCredentialBundle *new_active) override {
    commit_calls++;
    if (!configured || snapshot == nullptr || new_active == nullptr ||
        candidate_generation == 0)
      return false;

    if (!commit_ok) {
      write_count += failed_commit_write_increments;
      marker_committed = marker_committed_on_failure;
      if (marker_committed) {
        active_generation = candidate_generation;
        candidate_generation = 0;
        recovery_status = "active";
        active_bundle.clear();
        clone_bundle(candidate_bundle, &active_bundle);
      }
      *snapshot = make_snapshot();
      snapshot->marker_last_observed = false;
      return false;
    }

    write_count += successful_commit_write_increments;
    active_generation = candidate_generation;
    candidate_generation = 0;
    recovery_status = "active";
    marker_committed = true;
    active_bundle.clear();
    if (return_mismatched_active) {
      active_bundle = make_bundle(active_generation);
      active_bundle.node_id = "gh-test-node-mismatch";
    } else {
      clone_bundle(candidate_bundle, &active_bundle);
    }
    clone_bundle(active_bundle, new_active);
    *snapshot = make_snapshot();
    return true;
  }

  bool cleanup_test_namespace(
      IsolatedDevicePersistenceSnapshot *) override {
    cleanup_calls++;
    return false;
  }

  void quiesce() override { quiesce_calls++; }

  IsolatedDevicePersistenceSnapshot make_snapshot() const {
    IsolatedDevicePersistenceSnapshot snapshot;
    snapshot.read_only_opened = true;
    snapshot.recovery_valid = recovery_valid;
    snapshot.recovery_status = recovery_status;
    snapshot.active_generation = active_generation;
    snapshot.candidate_generation = candidate_generation;
    snapshot.marker_committed = marker_committed;
    snapshot.marker_last_observed = marker_committed && marker_last;
    snapshot.persistent_write_count = write_count;
    snapshot.reboot_required = reboot_required;
    return snapshot;
  }

  static RamCredentialBundle make_copy(const RamCredentialBundle &source) {
    RamCredentialBundle copy;
    clone_bundle(source, &copy);
    return copy;
  }

  bool configure_ok{true};
  bool inspect_ok{true};
  bool commit_ok{true};
  bool recovery_valid{true};
  bool marker_committed{false};
  bool marker_committed_on_failure{false};
  bool marker_last{true};
  bool reboot_required{false};
  bool drift_write_count_on_inspect{false};
  bool return_mismatched_active{false};
  bool configured{false};
  uint32_t active_generation{0};
  uint32_t candidate_generation{1};
  uint32_t write_count{0};
  uint32_t successful_commit_write_increments{2};
  uint32_t failed_commit_write_increments{0};
  std::string recovery_status{"no_active_prepared"};
  RamCredentialBundle candidate_bundle{make_bundle(1)};
  RamCredentialBundle active_bundle{};
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
    if (!configure_ok || !candidate.valid() ||
        validation_timeout_ms < 1000 || activation_timeout_ms < 1000)
      return false;
    has_active = active != nullptr && active->valid();
    configured = true;
    return true;
  }

  bool begin_validation(IsolatedDeviceMqttSnapshot *snapshot) override {
    begin_validation_calls++;
    if (!configured || snapshot == nullptr || !begin_validation_ok)
      return false;
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
    probe_live = false;
    active_live = has_active;
    rollback_complete = !has_active || active_live;
    rollback_result = rollback_complete ? "no_active_prepared_retained"
                                        : "authority_unavailable";
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
    snapshot.reboot_required = reboot_required;
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
  bool reboot_required{false};
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
  OneShotGenerationAuthorization package_authorization;
  MirroredGenerationWriteAuthorization mirrored_authorization;
  Stage2D10G4ActivationCoordinator coordinator;
  Stage2D10G4Snapshot snapshot;
  IsolatedCandidateProfile candidate{make_candidate()};

  void configure(bool load_key = true) {
    assert(coordinator.configure(make_config(), &persistence, &mqtt,
                                 &key_provider, &package_authorization,
                                 &mirrored_authorization));
    if (load_key)
      assert(key_provider.load(make_key()));
  }

  void recover() {
    assert(coordinator.recover_prepared_read_only(candidate, &snapshot));
    assert(snapshot.phase == Stage2D10G4Phase::RECOVERED_PREPARED);
  }

  void validate() {
    recover();
    assert(coordinator.begin_validation(&snapshot));
    assert(coordinator.poll_validation(100, &snapshot));
    assert(coordinator.poll_validation(100, &snapshot));
    assert(snapshot.phase == Stage2D10G4Phase::VERIFIED);
  }

  void grant() {
    assert(coordinator.grant_activation_authorization(
        kAuthorizationDigest, &snapshot));
  }
};

void test_config_and_default_off_boundary() {
  Fixture fixture;
  Stage2D10G4Config invalid = make_config();
  invalid.partition_label = "nvs";
  assert(!invalid.valid());
  assert(!fixture.coordinator.configure(
      invalid, &fixture.persistence, &fixture.mqtt, &fixture.key_provider,
      &fixture.package_authorization, &fixture.mirrored_authorization));
  assert(fixture.mqtt.configure_calls == 0);
  assert(fixture.persistence.inspect_calls == 0);
  assert(fixture.persistence.prepare_calls == 0);
  assert(fixture.persistence.commit_calls == 0);
}

void test_recover_prepared_is_read_only_and_network_silent() {
  Fixture fixture;
  fixture.configure();
  fixture.recover();
  assert(fixture.persistence.inspect_calls == 1);
  assert(fixture.persistence.write_count == 0);
  assert(fixture.persistence.prepare_calls == 0);
  assert(fixture.mqtt.configure_calls == 1);
  assert(fixture.mqtt.begin_validation_calls == 0);
  assert(fixture.snapshot.active_generation == 0);
  assert(fixture.snapshot.candidate_generation == 1);
  assert(fixture.snapshot.persistence_status == "no_active_prepared");
  assert(fixture.snapshot.recovered_candidate_match);
  assert(!fixture.snapshot.active_session_live);
  assert(!fixture.snapshot.candidate_session_live);
  assert(!fixture.snapshot.probe_session_live);
}

void test_recover_requires_key() {
  Fixture fixture;
  fixture.configure(false);
  assert(!fixture.coordinator.recover_prepared_read_only(
      fixture.candidate, &fixture.snapshot));
  assert(fixture.coordinator.phase() == Stage2D10G4Phase::COLD);
  assert(fixture.coordinator.failure() ==
         Stage2D10G4Failure::TEST_KEY_REQUIRED);
  assert(fixture.persistence.inspect_calls == 0);
}

void test_recover_rejects_wrong_state_and_generation() {
  Fixture wrong_status;
  wrong_status.persistence.recovery_status = "active_with_prepared";
  wrong_status.configure();
  assert(!wrong_status.coordinator.recover_prepared_read_only(
      wrong_status.candidate, &wrong_status.snapshot));
  assert(wrong_status.coordinator.phase() == Stage2D10G4Phase::FAILED);

  Fixture wrong_generation;
  wrong_generation.persistence.candidate_generation = 2;
  wrong_generation.persistence.candidate_bundle = make_bundle(2);
  wrong_generation.configure();
  assert(!wrong_generation.coordinator.recover_prepared_read_only(
      wrong_generation.candidate, &wrong_generation.snapshot));
  assert(wrong_generation.coordinator.failure() ==
         Stage2D10G4Failure::RECOVERED_STATE_MISMATCH);
}

void test_recover_rejects_candidate_mismatch_and_write_drift() {
  Fixture mismatch;
  mismatch.persistence.candidate_bundle.node_id = "gh-test-node-other";
  mismatch.configure();
  assert(!mismatch.coordinator.recover_prepared_read_only(
      mismatch.candidate, &mismatch.snapshot));
  assert(mismatch.coordinator.failure() ==
         Stage2D10G4Failure::RECOVERED_CANDIDATE_MISMATCH);
  assert(mismatch.mqtt.configure_calls == 0);

  Fixture drift;
  drift.persistence.drift_write_count_on_inspect = true;
  drift.configure();
  assert(!drift.coordinator.recover_prepared_read_only(
      drift.candidate, &drift.snapshot));
  assert(drift.coordinator.failure() ==
         Stage2D10G4Failure::READ_ONLY_WRITE_DRIFT);
}

void test_validation_success_and_failure() {
  Fixture success;
  success.configure();
  success.validate();
  assert(success.persistence.write_count == 0);
  assert(success.mqtt.begin_validation_calls == 1);
  assert(success.snapshot.validation_complete);
  assert(success.snapshot.validation_success);
  assert(!success.snapshot.probe_session_live);

  Fixture failure;
  failure.mqtt.validation_ok = false;
  failure.configure();
  failure.recover();
  assert(failure.coordinator.begin_validation(&failure.snapshot));
  assert(failure.coordinator.poll_validation(100, &failure.snapshot));
  assert(!failure.coordinator.poll_validation(100, &failure.snapshot));
  assert(failure.coordinator.phase() == Stage2D10G4Phase::FAILED);
  assert(failure.persistence.active_generation == 0);
  assert(failure.persistence.candidate_generation == 1);
  assert(failure.persistence.commit_calls == 0);
  assert(!failure.key_provider.loaded());
}

void test_activation_requires_fresh_authorization() {
  Fixture fixture;
  fixture.configure();
  fixture.validate();
  assert(!fixture.coordinator.activate(&fixture.snapshot));
  assert(fixture.coordinator.phase() == Stage2D10G4Phase::VERIFIED);
  assert(fixture.coordinator.failure() ==
         Stage2D10G4Failure::AUTHORIZATION_NOT_ARMED);
  assert(fixture.persistence.commit_calls == 0);
}

void test_stale_package_authorization_is_rejected() {
  Fixture fixture;
  fixture.configure();
  fixture.validate();
  fixture.grant();
  assert(fixture.package_authorization.arm(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kAuthorizationDigest));
  assert(!fixture.coordinator.activate(&fixture.snapshot));
  assert(fixture.coordinator.phase() == Stage2D10G4Phase::VERIFIED);
  assert(fixture.coordinator.failure() ==
         Stage2D10G4Failure::AUTHORIZATION_MISMATCH);
  assert(fixture.persistence.commit_calls == 0);
}

void test_one_layer_consumption_is_terminal() {
  Fixture fixture;
  fixture.configure();
  fixture.validate();
  fixture.grant();
  assert(fixture.mirrored_authorization.arm(
      IsolatedAcceptanceWriteOperation::ACTIVATE_PROFILE, 1, 2,
      kAuthorizationDigest));
  assert(!fixture.coordinator.activate(&fixture.snapshot));
  assert(fixture.coordinator.phase() ==
         Stage2D10G4Phase::REBOOT_REQUIRED);
  assert(fixture.coordinator.failure() ==
         Stage2D10G4Failure::AUTHORITY_AMBIGUOUS);
  assert(fixture.snapshot.package_authorization_consumed);
  assert(fixture.persistence.commit_calls == 0);
}

void test_activation_start_failure_rolls_back_prepared() {
  Fixture fixture;
  fixture.mqtt.begin_activation_ok = false;
  fixture.configure();
  fixture.validate();
  fixture.grant();
  assert(!fixture.coordinator.activate(&fixture.snapshot));
  assert(fixture.coordinator.phase() == Stage2D10G4Phase::FAILED);
  assert(fixture.coordinator.failure() ==
         Stage2D10G4Failure::ACTIVATION_START_FAILED);
  assert(fixture.mqtt.rollback_calls == 1);
  assert(fixture.persistence.commit_calls == 0);
  assert(fixture.persistence.active_generation == 0);
  assert(fixture.persistence.candidate_generation == 1);
}

void test_clear_commit_failure_rolls_back_prepared() {
  Fixture fixture;
  fixture.persistence.commit_ok = false;
  fixture.configure();
  fixture.validate();
  fixture.grant();
  assert(!fixture.coordinator.activate(&fixture.snapshot));
  assert(fixture.coordinator.phase() == Stage2D10G4Phase::FAILED);
  assert(fixture.coordinator.failure() ==
         Stage2D10G4Failure::PERSISTENCE_COMMIT_FAILED);
  assert(fixture.mqtt.rollback_calls == 1);
  assert(fixture.persistence.active_generation == 0);
  assert(fixture.persistence.candidate_generation == 1);
}

void test_marker_ambiguity_and_marker_last_failure_are_terminal() {
  Fixture ambiguous;
  ambiguous.persistence.commit_ok = false;
  ambiguous.persistence.marker_committed_on_failure = true;
  ambiguous.configure();
  ambiguous.validate();
  ambiguous.grant();
  assert(!ambiguous.coordinator.activate(&ambiguous.snapshot));
  assert(ambiguous.coordinator.phase() ==
         Stage2D10G4Phase::REBOOT_REQUIRED);
  assert(ambiguous.coordinator.failure() ==
         Stage2D10G4Failure::AUTHORITY_AMBIGUOUS);

  Fixture marker_last;
  marker_last.persistence.marker_last = false;
  marker_last.configure();
  marker_last.validate();
  marker_last.grant();
  assert(!marker_last.coordinator.activate(&marker_last.snapshot));
  assert(marker_last.coordinator.phase() ==
         Stage2D10G4Phase::REBOOT_REQUIRED);
  assert(marker_last.coordinator.failure() ==
         Stage2D10G4Failure::MARKER_LAST_NOT_PROVEN);
}

void test_active_recovery_mismatch_and_promotion_failure_are_terminal() {
  Fixture mismatch;
  mismatch.persistence.return_mismatched_active = true;
  mismatch.configure();
  mismatch.validate();
  mismatch.grant();
  assert(!mismatch.coordinator.activate(&mismatch.snapshot));
  assert(mismatch.coordinator.phase() ==
         Stage2D10G4Phase::REBOOT_REQUIRED);
  assert(mismatch.coordinator.failure() ==
         Stage2D10G4Failure::ACTIVE_RECOVERY_MISMATCH);

  Fixture promotion;
  promotion.mqtt.promote_ok = false;
  promotion.configure();
  promotion.validate();
  promotion.grant();
  assert(!promotion.coordinator.activate(&promotion.snapshot));
  assert(promotion.coordinator.phase() ==
         Stage2D10G4Phase::REBOOT_REQUIRED);
  assert(promotion.coordinator.failure() ==
         Stage2D10G4Failure::PROMOTION_FAILED);
  assert(promotion.persistence.active_generation == 1);
  assert(promotion.persistence.candidate_generation == 0);
}

void test_success_and_authorization_non_replay() {
  Fixture fixture;
  fixture.configure();
  fixture.validate();
  fixture.grant();
  assert(fixture.coordinator.activate(&fixture.snapshot));
  assert(fixture.snapshot.phase == Stage2D10G4Phase::ACTIVATED);
  assert(fixture.snapshot.failure == Stage2D10G4Failure::NONE);
  assert(fixture.snapshot.active_generation == 1);
  assert(fixture.snapshot.candidate_generation == 0);
  assert(fixture.snapshot.persistence_status == "active");
  assert(fixture.snapshot.marker_committed);
  assert(fixture.snapshot.marker_last_observed);
  assert(fixture.snapshot.promotion_complete);
  assert(fixture.snapshot.active_session_live);
  assert(!fixture.snapshot.candidate_session_live);
  assert(!fixture.snapshot.probe_session_live);
  assert(fixture.snapshot.package_authorization_consumed);
  assert(!fixture.snapshot.package_authorization_armed);
  assert(!fixture.snapshot.mirrored_authorization_armed);
  assert(fixture.persistence.prepare_calls == 0);
  assert(fixture.persistence.cleanup_calls == 0);

  assert(!fixture.coordinator.activate(&fixture.snapshot));
  assert(fixture.coordinator.failure() == Stage2D10G4Failure::INVALID_STATE);
  assert(fixture.persistence.commit_calls == 1);
}

void test_post_reboot_read_only_verification() {
  Fixture activation;
  activation.configure();
  activation.validate();
  activation.grant();
  assert(activation.coordinator.activate(&activation.snapshot));

  FakeMqttPort verify_mqtt;
  VolatileTestPersistenceKeyProvider verify_key;
  OneShotGenerationAuthorization verify_package_authorization;
  MirroredGenerationWriteAuthorization verify_mirrored_authorization;
  Stage2D10G4ActivationCoordinator verifier;
  Stage2D10G4Snapshot verified;

  assert(verifier.configure(
      make_config(), &activation.persistence, &verify_mqtt, &verify_key,
      &verify_package_authorization, &verify_mirrored_authorization));
  assert(verify_key.load(make_key()));
  IsolatedCandidateProfile expected = make_candidate();
  assert(verifier.verify_active_read_only(expected, &verified));
  assert(verified.phase == Stage2D10G4Phase::VERIFIED_AFTER_REBOOT);
  assert(verified.active_generation == 1);
  assert(verified.candidate_generation == 0);
  assert(verified.persistence_status == "active");
  assert(verified.persistent_write_count == 0);
  assert(verify_mqtt.configure_calls == 0);
  assert(verify_mqtt.begin_validation_calls == 0);
  assert(!verified.active_session_live);
  assert(!verified.candidate_session_live);
  assert(!verified.probe_session_live);
  assert(!verified.package_authorization_armed);
  assert(!verified.package_authorization_consumed);
  assert(!verified.mirrored_authorization_armed);
}

}  // namespace

int main() {
  test_config_and_default_off_boundary();
  test_recover_prepared_is_read_only_and_network_silent();
  test_recover_requires_key();
  test_recover_rejects_wrong_state_and_generation();
  test_recover_rejects_candidate_mismatch_and_write_drift();
  test_validation_success_and_failure();
  test_activation_requires_fresh_authorization();
  test_stale_package_authorization_is_rejected();
  test_one_layer_consumption_is_terminal();
  test_activation_start_failure_rolls_back_prepared();
  test_clear_commit_failure_rolls_back_prepared();
  test_marker_ambiguity_and_marker_last_failure_are_terminal();
  test_active_recovery_mismatch_and_promotion_failure_are_terminal();
  test_success_and_authorization_non_replay();
  test_post_reboot_read_only_verification();
  std::cout << "stage2d10_g4_activation_fault_matrix=pass\n";
  return 0;
}
