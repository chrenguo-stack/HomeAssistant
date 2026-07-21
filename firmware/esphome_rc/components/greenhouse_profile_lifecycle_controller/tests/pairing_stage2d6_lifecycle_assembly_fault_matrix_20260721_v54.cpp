#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "profile_lifecycle_controller.h"

using namespace esphome::greenhouse_pairing_client;

class FakeProductionMqttSession final : public ProductionMqttSession {
 public:
  bool configure(CandidateMqttProfile profile,
                 CandidateMqttProbeExchange exchange,
                 bool require_round_trip) override {
    configure_calls++;
    if (!configure_ok || live_ || !profile.valid() ||
        (require_round_trip && !exchange.valid())) {
      profile.clear();
      exchange.clear();
      return false;
    }
    profile_ = std::move(profile);
    exchange_ = std::move(exchange);
    require_round_trip_ = require_round_trip;
    configured_ = true;
    terminal_failure_ = false;
    failure_ = ProductionMqttSessionFailure::NONE;
    return true;
  }

  bool start() override {
    start_calls++;
    if (!configured_ || !start_ok)
      return false;
    live_ = true;
    started_ = true;
    return true;
  }

  bool poll(ProductionMqttSessionObservation *observation) override {
    poll_calls++;
    if (!poll_ok || observation == nullptr)
      return false;
    observation->client_created = configured_;
    observation->started = started_;
    observation->connected = connected_;
    observation->authenticated = authenticated_;
    observation->subscribe_ready = subscribe_ready_;
    observation->round_trip = round_trip_;
    observation->terminal_failure = terminal_failure_;
    observation->failure = failure_;
    return true;
  }

  bool wait_connected(uint32_t timeout_ms) override {
    wait_connected_calls++;
    if (!live_ || timeout_ms < 1000 || !wait_connected_ok)
      return false;
    connected_ = true;
    authenticated_ = true;
    return true;
  }

  bool wait_round_trip(uint32_t timeout_ms) override {
    wait_round_trip_calls++;
    if (!live_ || !require_round_trip_ || timeout_ms < 1000 ||
        !wait_round_trip_ok)
      return false;
    connected_ = true;
    authenticated_ = true;
    subscribe_ready_ = true;
    round_trip_ = true;
    return true;
  }

  bool stop() override {
    stop_calls++;
    if (!stop_ok)
      return false;
    live_ = false;
    started_ = false;
    connected_ = false;
    authenticated_ = false;
    subscribe_ready_ = false;
    return true;
  }

  void destroy() override {
    destroy_calls++;
    live_ = false;
    started_ = false;
    connected_ = false;
    authenticated_ = false;
    subscribe_ready_ = false;
    round_trip_ = false;
    configured_ = false;
    require_round_trip_ = false;
    terminal_failure_ = false;
    failure_ = ProductionMqttSessionFailure::NONE;
    profile_.clear();
    exchange_.clear();
  }

  bool live() const override { return live_; }
  uint32_t generation() const override {
    return profile_.credential_generation;
  }

  void set_poll_success() {
    connected_ = true;
    authenticated_ = true;
    subscribe_ready_ = true;
    round_trip_ = true;
  }

  void set_poll_failure(ProductionMqttSessionFailure failure) {
    terminal_failure_ = true;
    failure_ = failure;
  }

  bool configure_ok{true};
  bool start_ok{true};
  bool poll_ok{true};
  bool wait_connected_ok{true};
  bool wait_round_trip_ok{true};
  bool stop_ok{true};
  int configure_calls{0};
  int start_calls{0};
  int poll_calls{0};
  int wait_connected_calls{0};
  int wait_round_trip_calls{0};
  int stop_calls{0};
  int destroy_calls{0};

 private:
  CandidateMqttProfile profile_{};
  CandidateMqttProbeExchange exchange_{};
  bool configured_{false};
  bool require_round_trip_{false};
  bool live_{false};
  bool started_{false};
  bool connected_{false};
  bool authenticated_{false};
  bool subscribe_ready_{false};
  bool round_trip_{false};
  bool terminal_failure_{false};
  ProductionMqttSessionFailure failure_{ProductionMqttSessionFailure::NONE};
};

class FixedNonceSource final : public ActivationNonceSource {
 public:
  bool next_nonce_hex(std::string *nonce_hex) override {
    calls++;
    if (!ok || nonce_hex == nullptr)
      return false;
    *nonce_hex = calls % 2 == 0
                     ? "ffeeddccbbaa99887766554433221100"
                     : "00112233445566778899aabbccddeeff";
    return true;
  }

  bool ok{true};
  int calls{0};
};

class FixedMutationAuthorizer final
    : public ProfileLifecycleMutationAuthorizer {
 public:
  bool authorize(ProfileLifecycleMutationOperation operation,
                 uint32_t active_generation,
                 uint32_t candidate_generation) override {
    calls++;
    last_operation = operation;
    last_active_generation = active_generation;
    last_candidate_generation = candidate_generation;
    return allow;
  }

  bool allow{false};
  int calls{0};
  ProfileLifecycleMutationOperation last_operation{
      ProfileLifecycleMutationOperation::COMMIT_PREPARED_PROFILE};
  uint32_t last_active_generation{0};
  uint32_t last_candidate_generation{0};
};

class MemoryBackend final : public PairingPersistenceBackend {
 public:
  struct Pending {
    bool erase{false};
    std::vector<uint8_t> value;
  };

  PersistenceReadResult read_blob(const char *key,
                                  std::vector<uint8_t> *value) override {
    read_calls++;
    if (fail_reads || key == nullptr || value == nullptr)
      return PersistenceReadResult::ERROR;
    auto pending = pending_.find(key);
    if (pending != pending_.end()) {
      if (pending->second.erase)
        return PersistenceReadResult::NOT_FOUND;
      *value = pending->second.value;
      return PersistenceReadResult::OK;
    }
    auto durable = durable_.find(key);
    if (durable == durable_.end())
      return PersistenceReadResult::NOT_FOUND;
    *value = durable->second;
    return PersistenceReadResult::OK;
  }

  bool write_blob(const char *key, const uint8_t *value,
                  size_t length) override {
    write_calls++;
    if (fail_writes || key == nullptr || value == nullptr || length == 0)
      return false;
    pending_[key] =
        Pending{false, std::vector<uint8_t>(value, value + length)};
    return true;
  }

  bool erase_key(const char *key) override {
    erase_calls++;
    if (fail_writes || key == nullptr)
      return false;
    pending_[key] = Pending{true, {}};
    return true;
  }

  bool commit() override {
    commit_calls++;
    if (fail_commits)
      return false;
    for (const auto &[key, pending] : pending_) {
      if (pending.erase)
        durable_.erase(key);
      else
        durable_[key] = pending.value;
    }
    pending_.clear();
    return true;
  }

  bool fail_reads{false};
  bool fail_writes{false};
  bool fail_commits{false};
  int read_calls{0};
  int write_calls{0};
  int erase_calls{0};
  int commit_calls{0};

 private:
  std::map<std::string, std::vector<uint8_t>> durable_;
  std::map<std::string, Pending> pending_;
};

std::array<uint8_t, 32> make_key() {
  std::array<uint8_t, 32> key{};
  for (size_t index = 0; index < key.size(); index++)
    key[index] = static_cast<uint8_t>(index + 1);
  return key;
}

RamCredentialBundle make_credentials(uint32_t generation) {
  RamCredentialBundle bundle;
  bundle.schema = "gh.pair.credentials/1";
  bundle.system_id = "greenhouse";
  bundle.node_id = "node-" + std::to_string(generation);
  bundle.broker_host = "broker.local";
  bundle.broker_port = 8883;
  bundle.broker_tls_server_name = bundle.broker_host;
  bundle.ca_pem =
      "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n";
  bundle.mqtt_username = "node_user_" + std::to_string(generation);
  bundle.mqtt_client_id = "node_client_" + std::to_string(generation);
  bundle.credential_generation = generation;
  bundle.mqtt_password = "test-value-" + std::to_string(generation);
  assert(bundle.valid());
  return bundle;
}

struct ControllerRig {
  ControllerRig() : key(make_key()), key_provider(key) {
    assert(persistence.configure(&backend, &key_provider));
    assert(probe_transport.configure(&probe_session));
    assert(runtime.configure(&active_session, &activation_session, &nonce));
    assert(controller.configure(persistence.store(), &probe_transport, &runtime,
                                &nonce));
  }

  PairingPersistentStore *store() { return persistence.store(); }

  void prepare(uint32_t generation) {
    RamCredentialBundle credentials = make_credentials(generation);
    assert(store()->prepare(credentials));
  }

  void commit_prepared() { assert(store()->commit_prepared()); }

  PersistentRecoverySnapshot recover() {
    PersistentRecoverySnapshot snapshot{};
    assert(store()->recover(&snapshot));
    return snapshot;
  }

  MemoryBackend backend;
  std::array<uint8_t, 32> key;
  FixedPersistenceKeyProvider key_provider;
  ProductionPersistenceAdapter persistence;
  FakeProductionMqttSession probe_session;
  FakeProductionMqttSession active_session;
  FakeProductionMqttSession activation_session;
  FixedNonceSource nonce;
  ProductionCandidateMqttTransport probe_transport;
  ProductionProfileLifecycleRuntime runtime;
  ProductionProfileLifecycleController controller;
};

void verify_probe(ControllerRig *rig) {
  assert(rig != nullptr);
  assert(rig->controller.begin_prepared_validation());
  assert(rig->controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::VALIDATING);
  assert(!rig->controller.begin_prepared_validation());
  assert(!rig->controller.recover_startup());
  rig->probe_session.set_poll_success();
  assert(rig->controller.poll_validation(100));
  assert(rig->controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::VERIFIED);
  assert(!rig->probe_transport.live());
}

void test_empty_startup_is_read_only() {
  ControllerRig rig;
  const int commits_before = rig.backend.commit_calls;
  assert(rig.controller.recover_startup());
  const auto &snapshot = rig.controller.snapshot();
  assert(snapshot.phase == ProfileLifecycleControllerPhase::RECOVERED);
  assert(snapshot.startup_disposition == StartupRecoveryDisposition::UNPAIRED);
  assert(snapshot.active_generation == 0);
  assert(snapshot.candidate_generation == 0);
  assert(!snapshot.active_runtime_live);
  assert(!snapshot.candidate_runtime_live);
  assert(!snapshot.prepared_present);
  assert(rig.backend.commit_calls == commits_before);
  assert(rig.active_session.start_calls == 0);
  assert(rig.activation_session.start_calls == 0);
  assert(rig.probe_session.start_calls == 0);
}

void test_active_start_is_explicit() {
  ControllerRig rig;
  rig.prepare(1);
  rig.commit_prepared();
  const int commits_before = rig.backend.commit_calls;
  assert(rig.controller.recover_startup());
  assert(rig.controller.snapshot().startup_disposition ==
         StartupRecoveryDisposition::ACTIVE_READY);
  assert(rig.controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::RECOVERED);
  assert(!rig.controller.snapshot().active_runtime_live);
  assert(rig.active_session.start_calls == 0);
  assert(rig.backend.commit_calls == commits_before);

  assert(rig.controller.start_recovered_active());
  assert(rig.controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::ACTIVE_LIVE);
  assert(rig.controller.snapshot().active_runtime_live);
  assert(rig.runtime.active_generation() == 1);
  assert(rig.backend.commit_calls == commits_before);
}

void test_first_enrollment_authorization_gate() {
  ControllerRig rig;
  rig.prepare(1);
  assert(rig.controller.recover_startup());
  assert(rig.controller.snapshot().startup_disposition ==
         StartupRecoveryDisposition::PREPARED_FIRST_ENROLLMENT);
  assert(!rig.controller.start_recovered_active());
  verify_probe(&rig);

  FixedMutationAuthorizer authorizer;
  assert(!rig.controller.activate(&authorizer));
  assert(authorizer.calls == 1);
  assert(authorizer.last_active_generation == 0);
  assert(authorizer.last_candidate_generation == 1);
  assert(rig.controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::VERIFIED);
  assert(rig.controller.snapshot().failure ==
         ProfileLifecycleControllerFailure::MUTATION_NOT_AUTHORIZED);
  assert(rig.recover().status == PersistentRecoveryStatus::NO_ACTIVE_PREPARED);

  authorizer.allow = true;
  assert(rig.controller.activate(&authorizer));
  assert(rig.controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::ACTIVATED);
  assert(rig.controller.snapshot().persistence_committed);
  assert(rig.controller.snapshot().promotion_finalized);
  assert(rig.controller.snapshot().active_generation == 1);
  assert(rig.controller.snapshot().active_runtime_live);
  assert(!rig.controller.snapshot().candidate_runtime_live);
  const PersistentRecoverySnapshot recovery = rig.recover();
  assert(recovery.status == PersistentRecoveryStatus::ACTIVE);
  assert(recovery.active_generation == 1);
}

void test_rotation_validation_failure_preserves_active() {
  ControllerRig rig;
  rig.prepare(1);
  rig.commit_prepared();
  rig.prepare(2);
  assert(rig.controller.recover_startup());
  assert(rig.controller.snapshot().startup_disposition ==
         StartupRecoveryDisposition::ACTIVE_WITH_PREPARED);
  assert(!rig.controller.begin_prepared_validation());
  assert(rig.controller.snapshot().failure ==
         ProfileLifecycleControllerFailure::ACTIVE_START_REQUIRED);
  assert(rig.controller.start_recovered_active());
  assert(rig.controller.begin_prepared_validation());
  rig.probe_session.set_poll_failure(
      ProductionMqttSessionFailure::AUTHENTICATION_FAILED);
  assert(!rig.controller.poll_validation(100));
  assert(rig.controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::FAILED);
  assert(rig.controller.snapshot().active_runtime_live);
  assert(!rig.controller.snapshot().candidate_runtime_live);
  const PersistentRecoverySnapshot recovery = rig.recover();
  assert(recovery.status == PersistentRecoveryStatus::ACTIVE_WITH_PREPARED);
  assert(recovery.active_generation == 1);
  assert(recovery.candidate_generation == 2);
}

void test_rotation_activation_failure_rolls_back() {
  ControllerRig rig;
  rig.prepare(1);
  rig.commit_prepared();
  rig.prepare(2);
  assert(rig.controller.recover_startup());
  assert(rig.controller.start_recovered_active());
  verify_probe(&rig);

  rig.activation_session.start_ok = false;
  FixedMutationAuthorizer authorizer;
  authorizer.allow = true;
  assert(!rig.controller.activate(&authorizer));
  assert(rig.controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::ROLLED_BACK);
  assert(rig.controller.snapshot().active_runtime_live);
  assert(!rig.controller.snapshot().candidate_runtime_live);
  assert(!rig.controller.snapshot().persistence_committed);
  const PersistentRecoverySnapshot recovery = rig.recover();
  assert(recovery.status == PersistentRecoveryStatus::ACTIVE_WITH_PREPARED);
  assert(recovery.active_generation == 1);
  assert(recovery.candidate_generation == 2);
}

void test_two_rotations_reuse_promoted_active() {
  ControllerRig rig;
  rig.prepare(1);
  assert(rig.controller.recover_startup());
  verify_probe(&rig);
  FixedMutationAuthorizer authorizer;
  authorizer.allow = true;
  assert(rig.controller.activate(&authorizer));
  assert(rig.runtime.active_generation() == 1);

  assert(rig.controller.reset_transaction());
  rig.prepare(2);
  assert(rig.controller.recover_startup());
  assert(rig.controller.snapshot().startup_disposition ==
         StartupRecoveryDisposition::ACTIVE_WITH_PREPARED);
  assert(rig.controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::ACTIVE_LIVE);
  assert(rig.controller.start_recovered_active());
  verify_probe(&rig);
  assert(rig.controller.activate(&authorizer));
  assert(rig.runtime.active_generation() == 2);
  assert(rig.controller.snapshot().active_generation == 2);
  assert(rig.controller.snapshot().active_runtime_live);
  assert(!rig.controller.snapshot().candidate_runtime_live);
}

void test_stale_committed_slot_requires_maintenance_without_cleanup() {
  ControllerRig rig;
  rig.prepare(1);
  rig.commit_prepared();
  rig.prepare(2);
  rig.commit_prepared();
  const int commits_before = rig.backend.commit_calls;
  assert(rig.controller.recover_startup());
  assert(rig.controller.snapshot().startup_disposition ==
         StartupRecoveryDisposition::ACTIVE_WITH_MAINTENANCE_PENDING);
  assert(rig.controller.snapshot().maintenance_pending);
  assert(!rig.controller.snapshot().prepared_present);
  assert(rig.backend.commit_calls == commits_before);
  assert(rig.controller.start_recovered_active());
  assert(rig.runtime.active_generation() == 2);
  assert(!rig.controller.begin_prepared_validation());
  assert(rig.backend.commit_calls == commits_before);
}

void test_storage_error_quiesces_and_requires_reboot() {
  ControllerRig rig;
  rig.backend.fail_reads = true;
  assert(!rig.controller.recover_startup());
  assert(rig.controller.snapshot().phase ==
         ProfileLifecycleControllerPhase::REBOOT_REQUIRED);
  assert(rig.controller.snapshot().reboot_required);
  assert(!rig.controller.snapshot().active_runtime_live);
  assert(!rig.controller.snapshot().candidate_runtime_live);
  assert(!rig.controller.snapshot().probe_client_live);
  assert(!rig.controller.reset_transaction());
}

int main() {
  test_empty_startup_is_read_only();
  test_active_start_is_explicit();
  test_first_enrollment_authorization_gate();
  test_rotation_validation_failure_preserves_active();
  test_rotation_activation_failure_rolls_back();
  test_two_rotations_reuse_promoted_active();
  test_stale_committed_slot_requires_maintenance_without_cleanup();
  test_storage_error_quiesces_and_requires_reboot();
  std::cout << "Stage 2D-6 lifecycle assembly fault matrix passed\n";
  return 0;
}
