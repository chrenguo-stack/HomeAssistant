#define main stage2d10_g4_embedded_activation_matrix_main
#include "stage2d10_g4_activation_fault_matrix_20260723_v1.cpp"
#undef main

#include "stage2d10_g4_execution_controller.h"

namespace {

class FakeWifiPort final : public Stage2D10G4WifiPort {
 public:
  bool configure_private(const std::string &ssid,
                         const std::string &password,
                         const std::string &profile_digest,
                         uint32_t timeout_ms,
                         Stage2D10G4WifiSnapshot *snapshot) override {
    configure_calls++;
    if (!configure_ok || snapshot == nullptr || ssid.empty() ||
        password.size() < 8 || profile_digest.size() != 64 ||
        timeout_ms < 1000) {
      return false;
    }
    retained_ssid = ssid;
    retained_password = password;
    configured = true;
    snapshot->configured = true;
    return true;
  }

  bool begin(Stage2D10G4WifiSnapshot *snapshot) override {
    begin_calls++;
    if (!configured || !begin_ok || snapshot == nullptr)
      return false;
    started = true;
    snapshot->configured = true;
    snapshot->start_attempted = true;
    return true;
  }

  bool poll(uint32_t elapsed_ms,
            Stage2D10G4WifiSnapshot *snapshot) override {
    poll_calls++;
    if (!started || !poll_ok || elapsed_ms == 0 || snapshot == nullptr)
      return false;
    total_elapsed += elapsed_ms;
    snapshot->configured = true;
    snapshot->start_attempted = true;
    snapshot->elapsed_ms = total_elapsed;
    if (terminal_failure) {
      snapshot->terminal = true;
      snapshot->connected = false;
      snapshot->failure = Stage2D10G4WifiFailure::AUTHENTICATION_FAILED;
      return true;
    }
    if (poll_calls >= polls_to_connect) {
      connected = true;
      snapshot->connected = true;
      snapshot->terminal = false;
      snapshot->failure = Stage2D10G4WifiFailure::NONE;
    }
    return true;
  }

  void quiesce_and_destroy() override {
    quiesce_calls++;
    connected = false;
    started = false;
    configured = false;
    std::fill(retained_ssid.begin(), retained_ssid.end(), '\0');
    std::fill(retained_password.begin(), retained_password.end(), '\0');
    retained_ssid.clear();
    retained_password.clear();
  }

  bool configure_ok{true};
  bool begin_ok{true};
  bool poll_ok{true};
  bool terminal_failure{false};
  bool configured{false};
  bool started{false};
  bool connected{false};
  int polls_to_connect{2};
  int configure_calls{0};
  int begin_calls{0};
  int poll_calls{0};
  int quiesce_calls{0};
  uint32_t total_elapsed{0};
  std::string retained_ssid{};
  std::string retained_password{};
};

Stage2D10G4ExecutionConfig make_execution_config(
    const IsolatedCandidateProfile &candidate) {
  Stage2D10G4ExecutionConfig config;
  config.expected_candidate = candidate;
  assert(Stage2D10G4ExecutionController::candidate_digest(
      candidate, &config.expected_candidate_digest));
  config.expected_broker_configuration_digest = std::string(64, '5');
  config.wifi_timeout_ms = 20000;
  return config;
}

Stage2D10G4CommandEnvelope make_activate_envelope(
    const Stage2D10G4ExecutionConfig &config) {
  Stage2D10G4CommandEnvelope command;
  command.action = Stage2D10G4CommandAction::ACTIVATE_PROFILE;
  command.run_suffix = "a1b2c3d4e5f6";
  command.authorization_digest = kAuthorizationDigest;
  command.candidate_digest = config.expected_candidate_digest;
  command.wifi_ssid = "gh-stage2d10-test";
  command.wifi_password = "stage2d10-private-password";
  assert(Stage2D10G4CommandCodec::wifi_profile_digest(
      command.wifi_ssid, command.wifi_password,
      &command.wifi_profile_digest));
  command.broker_configuration_digest =
      config.expected_broker_configuration_digest;
  command.raw_command_sha256 = std::string(64, '9');
  return command;
}

Stage2D10G4CommandEnvelope make_verify_envelope(
    const Stage2D10G4ExecutionConfig &config) {
  Stage2D10G4CommandEnvelope command;
  command.action = Stage2D10G4CommandAction::VERIFY_ACTIVE_READ_ONLY;
  command.run_suffix = "a1b2c3d4e5f6";
  command.active_digest = config.expected_candidate_digest;
  command.raw_command_sha256 = std::string(64, '8');
  return command;
}

struct ExecutionFixture {
  Fixture activation;
  FakeWifiPort wifi;
  Stage2D10G4ExecutionController controller;
  Stage2D10G4ExecutionSnapshot snapshot;
  Stage2D10G4ExecutionConfig config{make_execution_config(activation.candidate)};

  void configure() {
    activation.configure();
    assert(controller.configure(config, &activation.coordinator, &wifi));
  }

  void bind_activate() {
    Stage2D10G4CommandEnvelope command = make_activate_envelope(config);
    assert(controller.bind_command(&command, &snapshot));
    assert(command.action == Stage2D10G4CommandAction::NONE);
  }

  void start_activation() {
    configure();
    bind_activate();
    assert(controller.begin_activate(&snapshot));
  }

  void complete_activation() {
    start_activation();
    assert(controller.poll(100, &snapshot));
    assert(controller.poll(100, &snapshot));
    assert(controller.poll(100, &snapshot));
    assert(controller.poll(100, &snapshot));
    assert(snapshot.phase ==
           Stage2D10G4ExecutionPhase::ACTIVATED_RESTART_REQUIRED);
  }
};

void test_execution_config_and_digest_binding() {
  ExecutionFixture fixture;
  fixture.activation.configure();
  Stage2D10G4ExecutionConfig invalid = fixture.config;
  invalid.expected_candidate_digest = std::string(64, '0');
  assert(fixture.controller.configure(
      invalid, &fixture.activation.coordinator, &fixture.wifi));

  Stage2D10G4CommandEnvelope command = make_activate_envelope(fixture.config);
  assert(!fixture.controller.bind_command(&command, &fixture.snapshot));
  assert(fixture.controller.failure() ==
         Stage2D10G4ExecutionFailure::CANDIDATE_DIGEST_MISMATCH);
  assert(fixture.wifi.configure_calls == 0);
  assert(fixture.activation.persistence.inspect_calls == 0);
  assert(fixture.activation.persistence.commit_calls == 0);
}

void test_broker_digest_binding() {
  ExecutionFixture fixture;
  fixture.configure();
  Stage2D10G4CommandEnvelope command = make_activate_envelope(fixture.config);
  command.broker_configuration_digest = std::string(64, '7');
  assert(!fixture.controller.bind_command(&command, &fixture.snapshot));
  assert(fixture.controller.failure() ==
         Stage2D10G4ExecutionFailure::BROKER_DIGEST_MISMATCH);
  assert(fixture.wifi.configure_calls == 0);
  assert(fixture.activation.persistence.commit_calls == 0);
}

void test_wifi_failures_are_pre_mqtt_and_prewrite() {
  ExecutionFixture configure_failure;
  configure_failure.wifi.configure_ok = false;
  configure_failure.configure();
  configure_failure.bind_activate();
  assert(!configure_failure.controller.begin_activate(
      &configure_failure.snapshot));
  assert(!configure_failure.snapshot.mqtt_operation_attempted);
  assert(configure_failure.activation.persistence.inspect_calls == 0);
  assert(configure_failure.activation.persistence.commit_calls == 0);

  ExecutionFixture terminal_failure;
  terminal_failure.wifi.terminal_failure = true;
  terminal_failure.start_activation();
  assert(!terminal_failure.controller.poll(100, &terminal_failure.snapshot));
  assert(terminal_failure.controller.failure() ==
         Stage2D10G4ExecutionFailure::WIFI_FAILED);
  assert(!terminal_failure.snapshot.mqtt_operation_attempted);
  assert(terminal_failure.activation.persistence.inspect_calls == 0);
  assert(terminal_failure.activation.persistence.commit_calls == 0);
}

void test_activate_happy_path_and_secret_destruction() {
  ExecutionFixture fixture;
  fixture.complete_activation();
  assert(fixture.snapshot.failure == Stage2D10G4ExecutionFailure::NONE);
  assert(fixture.snapshot.command_consumed);
  assert(fixture.snapshot.candidate_digest_match);
  assert(fixture.snapshot.broker_digest_match);
  assert(fixture.snapshot.wifi_operation_attempted);
  assert(fixture.snapshot.mqtt_operation_attempted);
  assert(fixture.snapshot.activation_attempted);
  assert(fixture.snapshot.activation_succeeded);
  assert(fixture.snapshot.automatic_restart_required);
  assert(!fixture.snapshot.cleanup_operation_attempted);
  assert(fixture.snapshot.coordinator.active_generation == 1);
  assert(fixture.snapshot.coordinator.candidate_generation == 0);
  assert(fixture.snapshot.coordinator.marker_last_observed);
  assert(fixture.activation.persistence.prepare_calls == 0);
  assert(fixture.activation.persistence.cleanup_calls == 0);
  assert(fixture.wifi.retained_ssid.empty());
  assert(fixture.wifi.retained_password.empty());
  assert(fixture.wifi.quiesce_calls >= 1);
}

void test_validation_and_activation_failures_do_not_retry() {
  ExecutionFixture validation_failure;
  validation_failure.activation.mqtt.validation_ok = false;
  validation_failure.start_activation();
  assert(validation_failure.controller.poll(
      100, &validation_failure.snapshot));
  assert(validation_failure.controller.poll(
      100, &validation_failure.snapshot));
  assert(validation_failure.controller.poll(
      100, &validation_failure.snapshot));
  assert(!validation_failure.controller.poll(
      100, &validation_failure.snapshot));
  assert(validation_failure.controller.failure() ==
         Stage2D10G4ExecutionFailure::VALIDATION_FAILED);
  assert(validation_failure.activation.persistence.commit_calls == 0);
  assert(!validation_failure.snapshot.activation_attempted);

  ExecutionFixture activation_failure;
  activation_failure.activation.persistence.commit_ok = false;
  activation_failure.start_activation();
  assert(activation_failure.controller.poll(100, &activation_failure.snapshot));
  assert(activation_failure.controller.poll(100, &activation_failure.snapshot));
  assert(activation_failure.controller.poll(100, &activation_failure.snapshot));
  assert(!activation_failure.controller.poll(100, &activation_failure.snapshot));
  assert(activation_failure.controller.failure() ==
         Stage2D10G4ExecutionFailure::ACTIVATION_FAILED);
  assert(activation_failure.activation.persistence.commit_calls == 1);
  assert(!activation_failure.snapshot.activation_succeeded);
}

void test_post_restart_verify_is_read_only_and_network_silent() {
  ExecutionFixture activation;
  activation.complete_activation();
  activation.controller.quiesce();

  activation.activation.persistence.write_count = 0;
  activation.activation.persistence.marker_committed = false;
  activation.activation.persistence.configured = false;

  FakeMqttPort verify_mqtt;
  VolatileTestPersistenceKeyProvider verify_key;
  OneShotGenerationAuthorization verify_package_authorization;
  MirroredGenerationWriteAuthorization verify_mirrored_authorization;
  Stage2D10G4ActivationCoordinator verifier;
  assert(verifier.configure(
      make_config(), &activation.activation.persistence, &verify_mqtt,
      &verify_key, &verify_package_authorization,
      &verify_mirrored_authorization));
  assert(verify_key.load(make_key()));

  FakeWifiPort verify_wifi;
  Stage2D10G4ExecutionController verify_controller;
  Stage2D10G4ExecutionSnapshot verified;
  assert(verify_controller.configure(
      activation.config, &verifier, &verify_wifi));
  Stage2D10G4CommandEnvelope command =
      make_verify_envelope(activation.config);
  assert(verify_controller.bind_command(&command, &verified));
  assert(verify_controller.verify_active_read_only(&verified));
  assert(verified.phase ==
         Stage2D10G4ExecutionPhase::VERIFIED_AFTER_RESTART);
  assert(verified.read_only_verify_attempted);
  assert(verified.read_only_verify_succeeded);
  assert(!verified.wifi_operation_attempted);
  assert(!verified.mqtt_operation_attempted);
  assert(!verified.activation_attempted);
  assert(!verified.cleanup_operation_attempted);
  assert(verified.coordinator.active_generation == 1);
  assert(verified.coordinator.candidate_generation == 0);
  assert(verified.coordinator.persistent_write_count == 0);
  assert(verify_wifi.configure_calls == 0);
  assert(verify_mqtt.configure_calls == 0);
}

}  // namespace

int main() {
  test_execution_config_and_digest_binding();
  test_broker_digest_binding();
  test_wifi_failures_are_pre_mqtt_and_prewrite();
  test_activate_happy_path_and_secret_destruction();
  test_validation_and_activation_failures_do_not_retry();
  test_post_restart_verify_is_read_only_and_network_silent();
  std::cout << "stage2d10_g4_execution_controller_fault_matrix=pass\n";
  return 0;
}
