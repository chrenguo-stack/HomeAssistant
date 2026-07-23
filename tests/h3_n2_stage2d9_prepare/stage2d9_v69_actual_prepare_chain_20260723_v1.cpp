#include <array>
#include <cstdlib>
#include <iostream>
#include <string>

#include "firmware/esphome_rc/components/greenhouse_pairing_client/secure_pairing_channel.h"
#include "firmware/esphome_rc/components/greenhouse_profile_isolated_acceptance/isolated_acceptance_package.h"
#include "firmware/esphome_rc/components/greenhouse_profile_isolated_device_driver/isolated_device_driver.h"

namespace esphome::greenhouse_pairing_client {

std::string SecurePairingChannel::json_escape(const std::string &value) {
  return value;
}

}  // namespace esphome::greenhouse_pairing_client

namespace {

using namespace esphome::greenhouse_pairing_client;

[[noreturn]] void fail(const char *message) {
  std::cerr << "STAGE2D9_V69_ACTUAL_PREPARE_CHAIN=FAIL reason=" << message
            << '\n';
  std::exit(2);
}

void require(bool condition, const char *message) {
  if (!condition)
    fail(message);
}

class FakePersistence final : public IsolatedDevicePersistencePort {
 public:
  bool configure(const IsolatedDeviceDriverConfig &config,
                 VolatileTestPersistenceKeyProvider *provider) override {
    configured_ = config.valid() && provider != nullptr;
    provider_ = provider;
    return configured_;
  }

  bool inspect_read_only(IsolatedDevicePersistenceSnapshot *snapshot,
                         RamCredentialBundle *active,
                         RamCredentialBundle *candidate) override {
    if (!configured_ || snapshot == nullptr)
      return false;
    if (active != nullptr)
      active->clear();
    if (candidate != nullptr)
      candidate->clear();
    *snapshot = {};
    snapshot->read_only_opened = true;
    snapshot->namespace_missing = !prepared_;
    snapshot->recovery_valid = true;
    snapshot->recovery_status = prepared_ ? "no_active_prepared" : "empty";
    snapshot->active_generation = 0;
    snapshot->candidate_generation = prepared_ ? 1 : 0;
    snapshot->persistent_write_count = write_count_;
    if (prepared_ && candidate != nullptr) {
      clone_bundle_(prepared_bundle_, candidate);
    }
    return true;
  }

  bool prepare_candidate(const RamCredentialBundle &candidate,
                         IsolatedDevicePersistenceSnapshot *snapshot) override {
    prepare_call_count_++;
    if (!configured_ || snapshot == nullptr || provider_ == nullptr ||
        !provider_->loaded() || !candidate.valid()) {
      return false;
    }
    prepared_bundle_.clear();
    clone_bundle_(candidate, &prepared_bundle_);
    prepared_ = true;
    write_count_ = 1;
    *snapshot = {};
    snapshot->read_only_opened = true;
    snapshot->namespace_missing = false;
    snapshot->recovery_valid = true;
    snapshot->recovery_status = "no_active_prepared";
    snapshot->active_generation = 0;
    snapshot->candidate_generation = candidate.credential_generation;
    snapshot->persistent_write_count = write_count_;
    return true;
  }

  bool commit_prepared(IsolatedDevicePersistenceSnapshot *,
                       RamCredentialBundle *) override {
    return false;
  }

  bool cleanup_test_namespace(
      IsolatedDevicePersistenceSnapshot *) override {
    return false;
  }

  void quiesce() override {}

  int prepare_call_count() const { return prepare_call_count_; }

 private:
  static void clone_bundle_(const RamCredentialBundle &source,
                            RamCredentialBundle *target) {
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

  VolatileTestPersistenceKeyProvider *provider_{nullptr};
  RamCredentialBundle prepared_bundle_{};
  uint32_t write_count_{0};
  int prepare_call_count_{0};
  bool configured_{false};
  bool prepared_{false};
};

class RejectingMqtt final : public IsolatedDeviceMqttPort {
 public:
  bool configure(const RamCredentialBundle *, const IsolatedCandidateProfile &,
                 uint32_t, uint32_t) override {
    operation_attempted_ = true;
    return false;
  }
  bool begin_validation(IsolatedDeviceMqttSnapshot *) override {
    operation_attempted_ = true;
    return false;
  }
  bool poll_validation(uint32_t, IsolatedDeviceMqttSnapshot *) override {
    operation_attempted_ = true;
    return false;
  }
  bool begin_activation(IsolatedDeviceMqttSnapshot *) override {
    operation_attempted_ = true;
    return false;
  }
  bool rollback_activation(IsolatedDeviceMqttSnapshot *) override {
    operation_attempted_ = true;
    return false;
  }
  bool promote_candidate(IsolatedDeviceMqttSnapshot *) override {
    operation_attempted_ = true;
    return false;
  }
  void quiesce() override {}

  bool operation_attempted() const { return operation_attempted_; }

 private:
  bool operation_attempted_{false};
};

class AcceptingEvidence final : public IsolatedAcceptanceEvidenceSink {
 public:
  bool write_redacted_json(const std::string &) override { return true; }
};

IsolatedAcceptanceTestConfiguration make_config(const std::string &host) {
  const std::string suffix = "815f0baef097";
  const std::string run_id = "gh-test-run-" + suffix;
  IsolatedAcceptanceTestConfiguration config;
  config.schema = "gh.h3.n2.stage2d7-isolated-test-config/1";
  config.firmware_commit_sha =
      "f39c3c4c621717a61e0b3cef8b4ec88e59ac13aa";
  config.configuration_digest =
      "1111111111111111111111111111111111111111111111111111111111111111";
  config.broker_configuration_digest =
      "2222222222222222222222222222222222222222222222222222222222222222";
  config.test_device_identifier = "gh-test-device-" + suffix;
  config.candidate.schema = "gh.h3.n2.isolated-candidate-profile/1";
  config.candidate.test_run_id = run_id;
  config.candidate.system_id = "gh-test-system-" + suffix;
  config.candidate.node_id = "gh-test-node-" + suffix;
  config.candidate.broker_host = host;
  config.candidate.broker_port = 8883;
  config.candidate.broker_tls_server_name = host;
  config.candidate.ca_pem = "stage2d9-test-ca";
  config.candidate.mqtt_username = "stage2d9-test";
  config.candidate.mqtt_client_id = "gh-test-client-" + run_id;
  config.candidate.mqtt_password =
      "2222222222222222222222222222222222222222222222222222222222222222";
  config.candidate.test_topic_root = "gh-test/" + run_id + "/node";
  config.candidate.credential_generation = 1;
  return config;
}

struct Fixture {
  VolatileTestPersistenceKeyProvider key_provider{};
  FakePersistence persistence{};
  RejectingMqtt mqtt{};
  IsolatedDeviceDriver driver{};
  AcceptingEvidence evidence{};
  IsolatedAcceptancePackage package{};
  IsolatedDeviceAuthorizationBinder binder{};

  void initialize() {
    IsolatedDeviceDriverConfig driver_config;
    driver_config.partition_label = "gh2d8_p2d9";
    driver_config.namespace_name = "gh2d8_s2d9";
    driver_config.validation_timeout_ms = 15000;
    driver_config.activation_timeout_ms = 15000;
    require(driver.configure(driver_config, &persistence, &mqtt, &key_provider),
            "driver configure failed");
    require(package.configure(&driver, &key_provider, &evidence),
            "package configure failed");
    require(binder.configure(&package, &driver), "binder configure failed");
    require(package.inspect_read_only(), "initial read-only inspect failed");
    const auto &snapshot = package.snapshot();
    require(snapshot.phase == IsolatedAcceptancePhase::READ_ONLY,
            "initial phase mismatch");
    require(snapshot.driver.persistence_status == "empty",
            "initial persistence mismatch");
    require(!mqtt.operation_attempted(), "MQTT touched during inspect");

    std::array<uint8_t, 32> key{};
    key.fill(0x5A);
    require(key_provider.load(key), "key load failed");
    key.fill(0);
  }

  void load_and_authorize(IsolatedAcceptanceTestConfiguration config) {
    require(config.valid(), "outer test config invalid");
    require(package.load_test_configuration(std::move(config)),
            "package config load failed");
    const std::string authorization_digest(64, '2');
    require(binder.grant(IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE,
                         0, 1, authorization_digest),
            "mirrored authorization grant failed");
  }
};

void test_corrected_local_host_succeeds() {
  Fixture fixture;
  fixture.initialize();
  fixture.load_and_authorize(make_config("stage2d9.local"));
  require(fixture.package.prepare_candidate(),
          "corrected PREPARE transaction failed");
  const auto &snapshot = fixture.package.snapshot();
  require(snapshot.phase == IsolatedAcceptancePhase::PREPARED,
          "corrected phase not PREPARED");
  require(snapshot.failure == IsolatedAcceptanceFailure::NONE,
          "corrected package failure present");
  require(snapshot.active_generation == 0,
          "corrected active generation changed");
  require(snapshot.candidate_generation == 1,
          "corrected candidate generation mismatch");
  require(snapshot.driver.persistence_status == "no_active_prepared",
          "corrected persistence status mismatch");
  require(snapshot.driver.persistent_write_count == 1,
          "corrected write count mismatch");
  require(snapshot.write_authorization_consumed,
          "corrected authorization not consumed");
  require(!snapshot.write_authorization_armed,
          "corrected authorization remained armed");
  require(fixture.persistence.prepare_call_count() == 1,
          "corrected persistence PREPARE count mismatch");
  require(!fixture.mqtt.operation_attempted(),
          "MQTT touched during corrected PREPARE");
}

void test_frozen_invalid_host_fails_before_persistence() {
  Fixture fixture;
  fixture.initialize();
  fixture.load_and_authorize(make_config("stage2d9.invalid"));
  require(!fixture.package.prepare_candidate(),
          "frozen invalid-host PREPARE unexpectedly passed");
  const auto &snapshot = fixture.package.snapshot();
  require(snapshot.phase == IsolatedAcceptancePhase::FAILED,
          "invalid-host package did not fail");
  require(snapshot.failure == IsolatedAcceptanceFailure::PREPARE_FAILED,
          "invalid-host package failure mismatch");
  require(fixture.driver.failure() ==
              IsolatedDeviceDriverFailure::INVALID_CONFIGURATION,
          "invalid-host driver failure mismatch");
  require(fixture.persistence.prepare_call_count() == 0,
          "invalid-host reached persistence PREPARE");
  require(!fixture.mqtt.operation_attempted(),
          "MQTT touched during invalid-host PREPARE");
}

}  // namespace

int main() {
  test_frozen_invalid_host_fails_before_persistence();
  test_corrected_local_host_succeeds();
  std::cout << "STAGE2D9_V69_ACTUAL_PREPARE_INVALID_HOST_REJECTED=true\n";
  std::cout << "STAGE2D9_V69_ACTUAL_PREPARE_LOCAL_HOST_PASSED=true\n";
  std::cout << "STAGE2D9_V69_ACTUAL_PREPARE_MQTT_UNTOUCHED=true\n";
  std::cout << "STAGE2D9_V69_ACTUAL_PREPARE_CHAIN=PASS\n";
  return 0;
}
