#include "pairing_mqtt_activation_contract.h"

namespace esphome::greenhouse_pairing_client {

bool MqttActivationContract::configure(uint32_t active_generation) {
  this->snapshot_ = {};
  this->snapshot_.active_generation = active_generation;
  return true;
}

bool MqttActivationContract::stage(uint32_t candidate_generation) {
  if (this->snapshot_.phase != MqttActivationPhase::UNCHANGED &&
      this->snapshot_.phase != MqttActivationPhase::ROLLED_BACK)
    return false;
  if (candidate_generation == 0 ||
      candidate_generation <= this->snapshot_.active_generation)
    return false;
  this->snapshot_.phase = MqttActivationPhase::CANDIDATE_STAGED;
  this->snapshot_.candidate_generation = candidate_generation;
  this->snapshot_.authenticated = false;
  this->snapshot_.subscribe_ready = false;
  this->snapshot_.telemetry_round_trip = false;
  return true;
}

bool MqttActivationContract::begin_probe() {
  if (this->snapshot_.phase != MqttActivationPhase::CANDIDATE_STAGED)
    return false;
  this->snapshot_.phase = MqttActivationPhase::PROBING;
  return true;
}

bool MqttActivationContract::record_probe(bool authenticated,
                                          bool subscribe_ready,
                                          bool telemetry_round_trip) {
  if (this->snapshot_.phase != MqttActivationPhase::PROBING)
    return false;
  this->snapshot_.authenticated = authenticated;
  this->snapshot_.subscribe_ready = subscribe_ready;
  this->snapshot_.telemetry_round_trip = telemetry_round_trip;
  if (authenticated && subscribe_ready && telemetry_round_trip) {
    this->snapshot_.phase = MqttActivationPhase::VERIFIED;
    return true;
  }
  this->snapshot_.phase = MqttActivationPhase::FAILED;
  return false;
}

bool MqttActivationContract::activate() {
  if (this->snapshot_.phase != MqttActivationPhase::VERIFIED ||
      this->snapshot_.candidate_generation == 0 ||
      this->snapshot_.candidate_generation <= this->snapshot_.active_generation)
    return false;
  this->snapshot_.active_generation = this->snapshot_.candidate_generation;
  this->snapshot_.candidate_generation = 0;
  this->snapshot_.phase = MqttActivationPhase::ACTIVATED;
  return true;
}

bool MqttActivationContract::rollback() {
  if (this->snapshot_.phase != MqttActivationPhase::CANDIDATE_STAGED &&
      this->snapshot_.phase != MqttActivationPhase::PROBING &&
      this->snapshot_.phase != MqttActivationPhase::VERIFIED &&
      this->snapshot_.phase != MqttActivationPhase::FAILED)
    return false;
  this->snapshot_.candidate_generation = 0;
  this->snapshot_.authenticated = false;
  this->snapshot_.subscribe_ready = false;
  this->snapshot_.telemetry_round_trip = false;
  this->snapshot_.phase = MqttActivationPhase::ROLLED_BACK;
  return true;
}

const char *MqttActivationContract::phase_name(MqttActivationPhase phase) {
  switch (phase) {
    case MqttActivationPhase::UNCHANGED: return "unchanged";
    case MqttActivationPhase::CANDIDATE_STAGED: return "candidate_staged";
    case MqttActivationPhase::PROBING: return "probing";
    case MqttActivationPhase::VERIFIED: return "verified";
    case MqttActivationPhase::ACTIVATED: return "activated";
    case MqttActivationPhase::ROLLED_BACK: return "rolled_back";
    case MqttActivationPhase::FAILED: return "failed";
  }
  return "unknown";
}

}  // namespace esphome::greenhouse_pairing_client
