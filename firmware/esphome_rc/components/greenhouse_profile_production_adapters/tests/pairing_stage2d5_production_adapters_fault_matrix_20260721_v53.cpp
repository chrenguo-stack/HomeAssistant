#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "profile_production_adapters.h"

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
    failure_ = ProductionMqttSessionFailure::NONE;
    terminal_failure_ = false;
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
    *nonce_hex = "00112233445566778899aabbccddeeff";
    return true;
  }

  bool ok{true};
  int calls{0};
};

class MemoryBackend final : public PairingPersistenceBackend {
 public:
  struct Pending {
    bool erase{false};
    std::vector<uint8_t> value;
  };

  PersistenceReadResult read_blob(const char *key,
                                  std::vector<uint8_t> *value) override {
    if (key == nullptr || value == nullptr)
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
    if (key == nullptr || value == nullptr || length == 0)
      return false;
    pending_[key] = Pending{false,
                            std::vector<uint8_t>(value, value + length)};
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

 private:
  std::map<std::string, std::vector<uint8_t>> durable_;
  std::map<std::string, Pending> pending_;
};

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

CandidateMqttProfile make_profile(uint32_t generation) {
  const RamCredentialBundle credentials = make_credentials(generation);
  CandidateMqttProfile profile;
  profile.system_id = credentials.system_id;
  profile.node_id = credentials.node_id;
  profile.broker_host = credentials.broker_host;
  profile.broker_port = credentials.broker_port;
  profile.broker_tls_server_name = credentials.broker_tls_server_name;
  profile.ca_pem = credentials.ca_pem;
  profile.mqtt_username = credentials.mqtt_username;
  profile.mqtt_client_id = credentials.mqtt_client_id;
  profile.credential_generation = credentials.credential_generation;
  profile.mqtt_password = credentials.mqtt_password;
  assert(profile.valid());
  return profile;
}

CandidateMqttProbeExchange make_exchange(uint32_t generation) {
  CandidateMqttProbeExchange exchange;
  exchange.publish_topic = "gh/v1/greenhouse/ingress/node/node-" +
                           std::to_string(generation) + "/telemetry";
  exchange.subscribe_topic = "gh/v1/greenhouse/out/node/node-" +
                             std::to_string(generation) + "/confirm";
  exchange.request_payload = "request";
  exchange.expected_payload = "accepted";
  assert(exchange.valid());
  return exchange;
}

void test_candidate_transport_success() {
  FakeProductionMqttSession session;
  ProductionCandidateMqttTransport transport;
  assert(transport.configure(&session));
  CandidateMqttProfile profile = make_profile(2);
  CandidateMqttProbeExchange exchange = make_exchange(2);
  assert(transport.create(profile, exchange));
  assert(transport.start());
  session.set_poll_success();
  CandidateMqttTransportObservation observation{};
  assert(transport.poll(&observation));
  assert(observation.client_created);
  assert(observation.connected);
  assert(observation.authenticated);
  assert(observation.subscribe_ready);
  assert(observation.telemetry_round_trip);
  assert(!observation.terminal_failure);
  transport.destroy();
  assert(!transport.live());
}

void test_candidate_transport_failure_mapping() {
  FakeProductionMqttSession session;
  ProductionCandidateMqttTransport transport;
  assert(transport.configure(&session));
  CandidateMqttProfile profile = make_profile(2);
  CandidateMqttProbeExchange exchange = make_exchange(2);
  assert(transport.create(profile, exchange));
  assert(transport.start());
  session.set_poll_failure(
      ProductionMqttSessionFailure::AUTHENTICATION_FAILED);
  CandidateMqttTransportObservation observation{};
  assert(transport.poll(&observation));
  assert(observation.terminal_failure);
  assert(observation.failure ==
         CandidateMqttProbeFailure::AUTHENTICATION_FAILED);
  transport.destroy();
}

void test_rotation_and_promotion() {
  FakeProductionMqttSession active_session;
  FakeProductionMqttSession candidate_session;
  FixedNonceSource nonce;
  ProductionProfileLifecycleRuntime runtime;
  assert(runtime.configure(&active_session, &candidate_session, &nonce));

  RamCredentialBundle active = make_credentials(1);
  RamCredentialBundle candidate = make_credentials(2);
  assert(runtime.bind_active_profile(active));
  assert(runtime.old_active_live());
  assert(runtime.stage_recovered_profiles(&active, candidate));
  assert(runtime.staged_generations_match(1, 2));
  assert(runtime.stop_old_active());
  assert(!runtime.old_active_live());
  assert(runtime.start_candidate());
  assert(runtime.candidate_active_live());
  assert(runtime.confirm_candidate_round_trip());

  runtime.clear_candidate_material();
  assert(runtime.promotion_pending());
  assert(!runtime.old_active_live());
  assert(runtime.candidate_active_live());
  assert(runtime.active_generation() == 2);
  assert(runtime.candidate_generation() == 0);
  assert(runtime.finalize_activation_promotion());
  assert(runtime.old_active_live());
  assert(!runtime.candidate_active_live());
  assert(!runtime.promotion_pending());

  RamCredentialBundle next = make_credentials(3);
  assert(runtime.stage_recovered_profiles(&candidate, next));
  assert(runtime.staged_generations_match(2, 3));
  assert(runtime.stop_old_active());
  assert(runtime.start_candidate());
  assert(runtime.confirm_candidate_round_trip());
  assert(runtime.stop_candidate());
  assert(runtime.restore_old_active());
  runtime.clear_candidate_material();
  assert(!runtime.promotion_pending());
  assert(runtime.old_active_live());
  assert(!runtime.candidate_active_live());
}

void test_first_enrollment() {
  FakeProductionMqttSession active_session;
  FakeProductionMqttSession candidate_session;
  FixedNonceSource nonce;
  ProductionProfileLifecycleRuntime runtime;
  assert(runtime.configure(&active_session, &candidate_session, &nonce));
  RamCredentialBundle candidate = make_credentials(1);
  assert(runtime.stage_recovered_profiles(nullptr, candidate));
  assert(runtime.staged_generations_match(0, 1));
  assert(runtime.stop_old_active());
  assert(runtime.start_candidate());
  assert(runtime.confirm_candidate_round_trip());
  runtime.clear_candidate_material();
  assert(runtime.promotion_pending());
  assert(runtime.finalize_activation_promotion());
  assert(runtime.old_active_live());
  assert(runtime.active_generation() == 1);
}

void test_runtime_fail_closed() {
  FakeProductionMqttSession active_session;
  FakeProductionMqttSession candidate_session;
  FixedNonceSource nonce;
  ProductionProfileLifecycleRuntime runtime;
  assert(runtime.configure(&active_session, &candidate_session, &nonce));
  RamCredentialBundle active = make_credentials(2);
  RamCredentialBundle stale = make_credentials(2);
  assert(runtime.bind_active_profile(active));
  assert(!runtime.stage_recovered_profiles(&active, stale));

  RamCredentialBundle candidate = make_credentials(3);
  assert(runtime.stage_recovered_profiles(&active, candidate));
  assert(runtime.stop_old_active());
  candidate_session.start_ok = false;
  assert(!runtime.start_candidate());
  assert(!runtime.candidate_active_live());
  assert(runtime.restore_old_active());
  runtime.clear_candidate_material();

  FakeProductionMqttSession same;
  ProductionProfileLifecycleRuntime invalid;
  assert(!invalid.configure(&same, &same, &nonce));
}

void test_persistence_composition() {
  MemoryBackend backend;
  std::array<uint8_t, 32> key{};
  for (size_t index = 0; index < key.size(); index++)
    key[index] = static_cast<uint8_t>(index + 1);
  FixedPersistenceKeyProvider key_provider(key);
  ProductionPersistenceAdapter adapter;
  assert(adapter.configure(&backend, &key_provider));
  assert(adapter.ready());
  assert(adapter.store() != nullptr);

  RamCredentialBundle candidate = make_credentials(1);
  assert(adapter.store()->prepare(candidate));
  PersistentRecoverySnapshot recovery{};
  RamCredentialBundle recovered_candidate;
  assert(adapter.store()->recover(&recovery, nullptr, &recovered_candidate));
  assert(recovery.status == PersistentRecoveryStatus::NO_ACTIVE_PREPARED);
  assert(recovery.candidate_generation == 1);
  assert(recovered_candidate.valid());
  adapter.reset();
  assert(!adapter.ready());
}

int main() {
  test_candidate_transport_success();
  test_candidate_transport_failure_mapping();
  test_rotation_and_promotion();
  test_first_enrollment();
  test_runtime_fail_closed();
  test_persistence_composition();
  std::cout << "Stage 2D-5 production adapter fault matrix passed\n";
  return 0;
}
