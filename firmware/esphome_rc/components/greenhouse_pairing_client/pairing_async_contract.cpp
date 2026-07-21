#include "pairing_async_contract.h"

namespace esphome::greenhouse_pairing_client {

bool PairingAsyncContract::queue(uint32_t operation_id, const PairingClientSnapshot &client) {
  if (operation_id == 0 || this->snapshot_.active ||
      (!terminal(this->snapshot_.phase) && this->snapshot_.phase != PairingAsyncPhase::IDLE) ||
      operation_id <= this->snapshot_.operation_id)
    return false;
  this->snapshot_.operation_id = operation_id;
  this->snapshot_.phase = PairingAsyncPhase::QUEUED;
  this->snapshot_.outcome = PairingAsyncOutcome::NONE;
  this->snapshot_.active = true;
  this->snapshot_.cancel_requested = false;
  this->copy_client_(client);
  this->bump_();
  return true;
}

bool PairingAsyncContract::begin(const PairingClientSnapshot &client) {
  if (!this->snapshot_.active || this->snapshot_.phase != PairingAsyncPhase::QUEUED)
    return false;
  return this->publish(PairingAsyncPhase::DISCOVERING, client);
}

bool PairingAsyncContract::publish(PairingAsyncPhase phase,
                                   const PairingClientSnapshot &client) {
  if (!this->snapshot_.active || !valid_transition(this->snapshot_.phase, phase))
    return false;
  this->snapshot_.phase = phase;
  this->copy_client_(client);
  this->bump_();
  return true;
}

bool PairingAsyncContract::request_cancel() {
  if (!this->snapshot_.active || terminal(this->snapshot_.phase))
    return false;
  if (!this->snapshot_.cancel_requested) {
    this->snapshot_.cancel_requested = true;
    this->bump_();
  }
  return true;
}

bool PairingAsyncContract::finish(PairingAsyncOutcome outcome,
                                  const PairingClientSnapshot &client) {
  if (!this->snapshot_.active || outcome == PairingAsyncOutcome::NONE ||
      outcome == PairingAsyncOutcome::BUSY)
    return false;

  PairingAsyncPhase phase = PairingAsyncPhase::FAILED;
  if (outcome == PairingAsyncOutcome::SUCCESS)
    phase = PairingAsyncPhase::COMPLETED;
  else if (outcome == PairingAsyncOutcome::CANCELLED)
    phase = PairingAsyncPhase::CANCELLED;
  else if (outcome == PairingAsyncOutcome::SELECTION_REQUIRED)
    phase = PairingAsyncPhase::WAITING_SELECTION;

  if (!valid_transition(this->snapshot_.phase, phase))
    return false;
  this->snapshot_.phase = phase;
  this->snapshot_.outcome = outcome;
  this->snapshot_.active = false;
  this->copy_client_(client);
  this->bump_();
  return true;
}

void PairingAsyncContract::reset(const PairingClientSnapshot &client) {
  const uint32_t operation_id = this->snapshot_.operation_id;
  const uint32_t version = this->snapshot_.state_version == UINT32_MAX
                               ? UINT32_MAX
                               : this->snapshot_.state_version + 1;
  this->snapshot_ = {};
  this->snapshot_.operation_id = operation_id;
  this->snapshot_.state_version = version;
  this->copy_client_(client);
}

bool PairingAsyncContract::terminal(PairingAsyncPhase phase) {
  return phase == PairingAsyncPhase::COMPLETED ||
         phase == PairingAsyncPhase::CANCELLED ||
         phase == PairingAsyncPhase::FAILED ||
         phase == PairingAsyncPhase::WAITING_SELECTION;
}

bool PairingAsyncContract::valid_transition(PairingAsyncPhase from,
                                            PairingAsyncPhase to) {
  if (from == to)
    return true;
  switch (from) {
    case PairingAsyncPhase::IDLE:
    case PairingAsyncPhase::COMPLETED:
    case PairingAsyncPhase::CANCELLED:
    case PairingAsyncPhase::FAILED:
    case PairingAsyncPhase::WAITING_SELECTION:
      return to == PairingAsyncPhase::QUEUED;
    case PairingAsyncPhase::QUEUED:
      return to == PairingAsyncPhase::DISCOVERING ||
             to == PairingAsyncPhase::SECURE_PAIRING ||
             to == PairingAsyncPhase::CANCELLED ||
             to == PairingAsyncPhase::FAILED;
    case PairingAsyncPhase::DISCOVERING:
      return to == PairingAsyncPhase::WAITING_SELECTION ||
             to == PairingAsyncPhase::SECURE_PAIRING ||
             to == PairingAsyncPhase::CANCELLED ||
             to == PairingAsyncPhase::FAILED;
    case PairingAsyncPhase::SECURE_PAIRING:
      return to == PairingAsyncPhase::RAM_STAGED ||
             to == PairingAsyncPhase::CANCELLED ||
             to == PairingAsyncPhase::FAILED;
    case PairingAsyncPhase::RAM_STAGED:
      return to == PairingAsyncPhase::PERSISTENCE_PREPARED ||
             to == PairingAsyncPhase::COMPLETED ||
             to == PairingAsyncPhase::CANCELLED ||
             to == PairingAsyncPhase::FAILED;
    case PairingAsyncPhase::PERSISTENCE_PREPARED:
      return to == PairingAsyncPhase::MQTT_PROBING ||
             to == PairingAsyncPhase::CANCELLED ||
             to == PairingAsyncPhase::FAILED;
    case PairingAsyncPhase::MQTT_PROBING:
      return to == PairingAsyncPhase::COMPLETED ||
             to == PairingAsyncPhase::CANCELLED ||
             to == PairingAsyncPhase::FAILED;
  }
  return false;
}

const char *PairingAsyncContract::phase_name(PairingAsyncPhase phase) {
  switch (phase) {
    case PairingAsyncPhase::IDLE: return "idle";
    case PairingAsyncPhase::QUEUED: return "queued";
    case PairingAsyncPhase::DISCOVERING: return "discovering";
    case PairingAsyncPhase::WAITING_SELECTION: return "waiting_selection";
    case PairingAsyncPhase::SECURE_PAIRING: return "secure_pairing";
    case PairingAsyncPhase::RAM_STAGED: return "ram_staged";
    case PairingAsyncPhase::PERSISTENCE_PREPARED: return "persistence_prepared";
    case PairingAsyncPhase::MQTT_PROBING: return "mqtt_probing";
    case PairingAsyncPhase::COMPLETED: return "completed";
    case PairingAsyncPhase::CANCELLED: return "cancelled";
    case PairingAsyncPhase::FAILED: return "failed";
  }
  return "unknown";
}

const char *PairingAsyncContract::outcome_name(PairingAsyncOutcome outcome) {
  switch (outcome) {
    case PairingAsyncOutcome::NONE: return "none";
    case PairingAsyncOutcome::SUCCESS: return "success";
    case PairingAsyncOutcome::BUSY: return "busy";
    case PairingAsyncOutcome::SELECTION_REQUIRED: return "selection_required";
    case PairingAsyncOutcome::CANCELLED: return "cancelled";
    case PairingAsyncOutcome::INVALID_TRANSITION: return "invalid_transition";
    case PairingAsyncOutcome::DISCOVERY_FAILED: return "discovery_failed";
    case PairingAsyncOutcome::PAIRING_FAILED: return "pairing_failed";
    case PairingAsyncOutcome::PERSISTENCE_FAILED: return "persistence_failed";
    case PairingAsyncOutcome::MQTT_PROBE_FAILED: return "mqtt_probe_failed";
  }
  return "unknown";
}

void PairingAsyncContract::copy_client_(const PairingClientSnapshot &client) {
  this->snapshot_.client_state = client.state;
  this->snapshot_.client_error = client.error;
  this->snapshot_.candidate_count = client.candidate_count;
  this->snapshot_.credential_generation = client.credential_generation;
  this->snapshot_.selection_required = client.selection_required;
  this->snapshot_.credentials_staged = client.credentials_staged;
}

void PairingAsyncContract::bump_() {
  if (this->snapshot_.state_version != UINT32_MAX)
    this->snapshot_.state_version++;
}

}  // namespace esphome::greenhouse_pairing_client
