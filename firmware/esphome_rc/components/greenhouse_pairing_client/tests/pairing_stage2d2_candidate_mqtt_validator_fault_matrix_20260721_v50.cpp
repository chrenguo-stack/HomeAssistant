#include <cassert>
#include <cstdint>
#include <iostream>
#include <utility>
#include <vector>

#include "pairing_candidate_mqtt_validator.h"

using namespace esphome::greenhouse_pairing_client;

namespace {

CandidateMqttProfile valid_profile(uint32_t generation = 2) {
  CandidateMqttProfile profile;
  profile.system_id = "greenhouse";
  profile.node_id = "n_01JABCDEF";
  profile.broker_host = "broker.greenhouse.local";
  profile.broker_port = 8883;
  profile.broker_tls_server_name = profile.broker_host;
  profile.ca_pem =
      "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n";
  profile.mqtt_username = "node-user";
  profile.mqtt_client_id = "node-client";
  profile.credential_generation = generation;
  profile.mqtt_password = "secret-password";
  return profile;
}

struct FakeTransport final : CandidateMqttTransport {
  bool create_result{true};
  bool start_result{true};
  bool poll_result{true};
  bool live_value{false};
  int destroy_count{0};
  std::vector<CandidateMqttTransportObservation> events;
  size_t index{0};
  CandidateMqttProbeExchange captured_exchange{};

  bool create(const CandidateMqttProfile &,
              const CandidateMqttProbeExchange &exchange) override {
    this->captured_exchange.publish_topic = exchange.publish_topic;
    this->captured_exchange.subscribe_topic = exchange.subscribe_topic;
    this->captured_exchange.request_payload = exchange.request_payload;
    this->captured_exchange.expected_payload = exchange.expected_payload;
    this->live_value = this->create_result;
    return this->create_result;
  }

  bool start() override { return this->start_result; }

  bool poll(CandidateMqttTransportObservation *output) override {
    if (!this->poll_result || output == nullptr)
      return false;
    if (this->index < this->events.size())
      *output = this->events[this->index++];
    return true;
  }

  void destroy() override {
    this->live_value = false;
    this->destroy_count++;
    this->captured_exchange.clear();
  }

  bool live() const override { return this->live_value; }
};

CandidateMqttTransportObservation progress(bool authenticated,
                                           bool subscribe_ready,
                                           bool telemetry_round_trip) {
  return {
      .client_created = true,
      .connected = authenticated,
      .authenticated = authenticated,
      .subscribe_ready = subscribe_ready,
      .telemetry_round_trip = telemetry_round_trip,
      .terminal_failure = false,
      .failure = CandidateMqttProbeFailure::NONE,
  };
}

CandidateMqttTransportObservation terminal(CandidateMqttProbeFailure failure,
                                           bool authenticated = false,
                                           bool subscribe_ready = false) {
  return {
      .client_created = true,
      .connected = authenticated,
      .authenticated = authenticated,
      .subscribe_ready = subscribe_ready,
      .telemetry_round_trip = false,
      .terminal_failure = true,
      .failure = failure,
  };
}

void test_success_path_stops_at_verified() {
  CandidateMqttProfileValidator validator;
  FakeTransport transport;
  assert(validator.configure(1, 5000));
  assert(validator.stage(valid_profile(), "0123456789abcdef"));
  assert(validator.snapshot().phase ==
         CandidateMqttProbePhase::CANDIDATE_STAGED);
  assert(validator.begin(&transport));

  assert(transport.captured_exchange.publish_topic ==
         "gh/v1/greenhouse/ingress/node/n_01JABCDEF/telemetry");
  assert(transport.captured_exchange.subscribe_topic ==
         "gh/v1/greenhouse/out/node/n_01JABCDEF/confirm");
  assert(transport.captured_exchange.request_payload.find(
             "gh.telemetry-probe/1") != std::string::npos);
  assert(transport.captured_exchange.expected_payload.find(
             "gh.telemetry-probe-confirm/1") != std::string::npos);

  transport.events = {
      progress(true, false, false),
      progress(true, true, false),
      progress(true, true, true),
  };
  assert(validator.poll(&transport, 100));
  assert(validator.snapshot().phase == CandidateMqttProbePhase::SUBSCRIBING);
  assert(validator.poll(&transport, 200));
  assert(validator.snapshot().phase == CandidateMqttProbePhase::ROUND_TRIP);
  assert(validator.poll(&transport, 300));
  assert(validator.snapshot().phase == CandidateMqttProbePhase::VERIFIED);
  assert(validator.snapshot().active_generation == 1);
  assert(validator.snapshot().candidate_generation == 2);
  assert(validator.snapshot().active_profile_unchanged);
  assert(!validator.snapshot().candidate_client_live);
  assert(!validator.candidate_material_present());
  assert(transport.destroy_count == 1);
  assert(!validator.begin(&transport));
  assert(!validator.cancel(&transport));
}

void test_invalid_inputs_fail_closed() {
  {
    CandidateMqttProfileValidator validator;
    assert(!validator.configure(1, 999));
  }
  {
    CandidateMqttProfileValidator validator;
    assert(validator.configure(2));
    assert(!validator.stage(valid_profile(2), "0123456789abcdef"));
    assert(validator.snapshot().failure ==
           CandidateMqttProbeFailure::GENERATION_REJECTED);
    assert(!validator.candidate_material_present());
  }
  {
    CandidateMqttProfileValidator validator;
    auto profile = valid_profile();
    profile.broker_tls_server_name = "other.greenhouse.local";
    assert(validator.configure(1));
    assert(!validator.stage(std::move(profile), "0123456789abcdef"));
    assert(validator.snapshot().failure ==
           CandidateMqttProbeFailure::INVALID_PROFILE);
  }
  {
    CandidateMqttProfileValidator validator;
    assert(validator.configure(1));
    assert(!validator.stage(valid_profile(), "0123456789ABCDEG"));
    assert(validator.snapshot().failure ==
           CandidateMqttProbeFailure::INVALID_NONCE);
  }
}

void test_transport_creation_and_start_failures() {
  {
    CandidateMqttProfileValidator validator;
    FakeTransport transport;
    transport.create_result = false;
    assert(validator.configure(1));
    assert(validator.stage(valid_profile(), "0123456789abcdef"));
    assert(!validator.begin(&transport));
    assert(validator.snapshot().failure ==
           CandidateMqttProbeFailure::CREATE_FAILED);
    assert(validator.snapshot().active_profile_unchanged);
    assert(!validator.candidate_material_present());
  }
  {
    CandidateMqttProfileValidator validator;
    FakeTransport transport;
    transport.start_result = false;
    assert(validator.configure(1));
    assert(validator.stage(valid_profile(), "0123456789abcdef"));
    assert(!validator.begin(&transport));
    assert(validator.snapshot().failure ==
           CandidateMqttProbeFailure::START_FAILED);
    assert(transport.destroy_count == 1);
  }
}

void test_terminal_transport_failures() {
  const CandidateMqttProbeFailure failures[] = {
      CandidateMqttProbeFailure::AUTHENTICATION_FAILED,
      CandidateMqttProbeFailure::SUBSCRIBE_FAILED,
      CandidateMqttProbeFailure::PUBLISH_FAILED,
      CandidateMqttProbeFailure::ROUND_TRIP_MISMATCH,
      CandidateMqttProbeFailure::TRANSPORT_ERROR,
  };
  for (const auto failure : failures) {
    CandidateMqttProfileValidator validator;
    FakeTransport transport;
    assert(validator.configure(1));
    assert(validator.stage(valid_profile(), "0123456789abcdef"));
    assert(validator.begin(&transport));
    transport.events = {terminal(failure)};
    assert(!validator.poll(&transport, 10));
    assert(validator.snapshot().phase == CandidateMqttProbePhase::FAILED);
    assert(validator.snapshot().failure == failure);
    assert(validator.snapshot().active_generation == 1);
    assert(validator.snapshot().active_profile_unchanged);
    assert(!validator.snapshot().candidate_client_live);
    assert(!validator.candidate_material_present());
    assert(transport.destroy_count == 1);
    assert(validator.reset());
    assert(validator.snapshot().phase == CandidateMqttProbePhase::IDLE);
  }
}

void test_timeout_poll_failure_and_observation_invariants() {
  {
    CandidateMqttProfileValidator validator;
    FakeTransport transport;
    assert(validator.configure(1, 1000));
    assert(validator.stage(valid_profile(), "0123456789abcdef"));
    assert(validator.begin(&transport));
    assert(!validator.poll(&transport, 1001));
    assert(validator.snapshot().failure == CandidateMqttProbeFailure::TIMEOUT);
  }
  {
    CandidateMqttProfileValidator validator;
    FakeTransport transport;
    transport.poll_result = false;
    assert(validator.configure(1));
    assert(validator.stage(valid_profile(), "0123456789abcdef"));
    assert(validator.begin(&transport));
    assert(!validator.poll(&transport, 10));
    assert(validator.snapshot().failure ==
           CandidateMqttProbeFailure::TRANSPORT_ERROR);
  }
  {
    CandidateMqttProfileValidator validator;
    FakeTransport transport;
    assert(validator.configure(1));
    assert(validator.stage(valid_profile(), "0123456789abcdef"));
    assert(validator.begin(&transport));
    transport.events = {progress(false, true, false)};
    assert(!validator.poll(&transport, 10));
    assert(validator.snapshot().failure ==
           CandidateMqttProbeFailure::TRANSPORT_INVARIANT);
  }
  {
    CandidateMqttProfileValidator validator;
    FakeTransport transport;
    assert(validator.configure(1));
    assert(validator.stage(valid_profile(), "0123456789abcdef"));
    assert(validator.begin(&transport));
    transport.events = {progress(true, false, true)};
    assert(!validator.poll(&transport, 10));
    assert(validator.snapshot().failure ==
           CandidateMqttProbeFailure::TRANSPORT_INVARIANT);
  }
}

void test_cancel_destroys_candidate_only() {
  CandidateMqttProfileValidator validator;
  FakeTransport transport;
  assert(validator.configure(1));
  assert(validator.stage(valid_profile(), "0123456789abcdef"));
  assert(validator.begin(&transport));
  assert(validator.cancel(&transport));
  assert(validator.snapshot().phase == CandidateMqttProbePhase::CANCELLED);
  assert(validator.snapshot().failure == CandidateMqttProbeFailure::CANCELLED);
  assert(validator.snapshot().active_profile_unchanged);
  assert(!validator.candidate_material_present());
  assert(!validator.snapshot().candidate_client_live);
  assert(validator.reset());
}

}  // namespace

int main() {
  test_success_path_stops_at_verified();
  test_invalid_inputs_fail_closed();
  test_transport_creation_and_start_failures();
  test_terminal_transport_failures();
  test_timeout_poll_failure_and_observation_invariants();
  test_cancel_destroys_candidate_only();
  std::cout << "stage2d2 candidate MQTT validator fault matrix passed\n";
  return 0;
}
