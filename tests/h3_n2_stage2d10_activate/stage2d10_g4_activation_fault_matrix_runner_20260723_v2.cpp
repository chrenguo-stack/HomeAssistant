#define main stage2d10_g4_embedded_v1_main
#include "stage2d10_g4_activation_fault_matrix_20260723_v1.cpp"
#undef main

namespace {

void test_post_reboot_read_only_verification_fresh_process() {
  Fixture activation;
  activation.configure();
  activation.validate();
  activation.grant();
  assert(activation.coordinator.activate(&activation.snapshot));

  activation.coordinator.quiesce_for_reboot();

  // EspIdfIsolatedPersistencePort::configure() resets process-local audit
  // counters and marker-observation flags without changing persisted state.
  // The fake port is reused to retain persistent state, so reset only those
  // process-local audit fields before constructing the fresh verifier.
  activation.persistence.write_count = 0;
  activation.persistence.marker_committed = false;
  activation.persistence.configured = false;

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
  test_post_reboot_read_only_verification_fresh_process();
  std::cout << "stage2d10_g4_activation_fault_matrix=pass\n";
  return 0;
}
