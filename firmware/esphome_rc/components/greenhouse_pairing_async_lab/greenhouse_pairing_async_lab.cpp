#include "greenhouse_pairing_async_lab.h"

#include <cstring>

#include "esphome/core/log.h"

namespace esphome::greenhouse_pairing_async_lab {

using greenhouse_pairing_client::PairingAsyncContract;

static const char *const TAG = "greenhouse_pairing_async_lab";

void GreenhousePairingAsyncLab::setup() {
  this->client_.set_network_enabled(true);
  this->client_.setup();
  if (!this->client_.local_operation_healthy() ||
      !this->worker_.start(this, this->worker_stack_size_, this->worker_priority_)) {
    ESP_LOGE(TAG, "Stage 2C-3 async lab setup rejected");
    this->mark_failed();
  }
}

void GreenhousePairingAsyncLab::loop() {
  if (this->is_failed())
    return;
  PairingAsyncSnapshot snapshot;
  if (this->worker_.poll(&snapshot))
    this->async_snapshot_ = snapshot;
  if (!this->worker_.active())
    this->client_.loop();
}

void GreenhousePairingAsyncLab::dump_config() {
  this->client_.dump_config();
  ESP_LOGCONFIG(TAG,
                "Greenhouse Pairing Async Lab:\n"
                "  Worker active: %s\n"
                "  Worker stack bytes: %" PRIu32 "\n"
                "  Worker priority: %u\n"
                "  Async operation ID: %" PRIu32 "\n"
                "  Async phase: %s\n"
                "  Async outcome: %s\n"
                "  Cancellation: cooperative and bounded by current network call\n"
                "  Credential journal: CONTRACT MODEL ONLY\n"
                "  MQTT activation: CONTRACT MODEL ONLY\n"
                "  Automatic pairing at boot: NO\n"
                "  Production persistence or MQTT mutation: NO",
                YESNO(this->worker_.active()), this->worker_stack_size_,
                static_cast<unsigned>(this->worker_priority_),
                this->async_snapshot_.operation_id, this->async_phase_name(),
                this->async_outcome_name());
}

float GreenhousePairingAsyncLab::get_setup_priority() const {
  return setup_priority::DATA;
}

bool GreenhousePairingAsyncLab::request_pairing() {
  if (this->is_failed() || this->next_operation_id_ == UINT32_MAX)
    return false;

  const uint32_t operation_id = this->next_operation_id_;
  const PairingClientSnapshot initial = this->async_client_snapshot();
  if (!this->worker_.request(operation_id))
    return false;

  this->async_snapshot_.operation_id = operation_id;
  if (this->async_snapshot_.state_version != UINT32_MAX)
    this->async_snapshot_.state_version++;
  this->async_snapshot_.phase = PairingAsyncPhase::QUEUED;
  this->async_snapshot_.outcome = PairingAsyncOutcome::NONE;
  this->async_snapshot_.client_state = initial.state;
  this->async_snapshot_.client_error = initial.error;
  this->async_snapshot_.candidate_count = initial.candidate_count;
  this->async_snapshot_.credential_generation = initial.credential_generation;
  this->async_snapshot_.active = true;
  this->async_snapshot_.cancel_requested = false;
  this->async_snapshot_.selection_required = initial.selection_required;
  this->async_snapshot_.credentials_staged = initial.credentials_staged;
  this->next_operation_id_++;
  return true;
}

bool GreenhousePairingAsyncLab::cancel_pairing() {
  return !this->is_failed() && this->worker_.cancel();
}

bool GreenhousePairingAsyncLab::select_candidate(size_t index) {
  return !this->is_failed() && !this->worker_.active() &&
         this->client_.select_candidate(index);
}

void GreenhousePairingAsyncLab::reset_unbound() {
  if (!this->worker_.active())
    this->client_.reset_unbound();
}

const char *GreenhousePairingAsyncLab::state_name() const {
  return this->worker_.active() ? state_to_name_(this->async_snapshot_.client_state)
                                : this->client_.state_name();
}

const char *GreenhousePairingAsyncLab::error_name() const {
  return this->worker_.active() ? error_to_name_(this->async_snapshot_.client_error)
                                : this->client_.error_name();
}

const char *GreenhousePairingAsyncLab::network_result_name() const {
  return this->worker_.active() ? "in_progress" : this->client_.network_result_name();
}

const char *GreenhousePairingAsyncLab::async_phase_name() const {
  return PairingAsyncContract::phase_name(this->async_snapshot_.phase);
}

const char *GreenhousePairingAsyncLab::async_outcome_name() const {
  return PairingAsyncContract::outcome_name(this->async_snapshot_.outcome);
}

PairingAsyncOutcome GreenhousePairingAsyncLab::execute_async_pairing(
    PairingAsyncExecutionContext *context) {
  if (context == nullptr)
    return PairingAsyncOutcome::INVALID_TRANSITION;
  if (context->cancellation_requested())
    return PairingAsyncOutcome::CANCELLED;

  PairingClientSnapshot snapshot = this->async_client_snapshot();
  bool discovery_phase_published = false;
  if (snapshot.state == PairingClientState::UNBOUND) {
    if (!this->client_.start_random_discovery())
      return PairingAsyncOutcome::DISCOVERY_FAILED;
    snapshot = this->async_client_snapshot();
    if (!context->publish(PairingAsyncPhase::DISCOVERING, snapshot))
      return PairingAsyncOutcome::INVALID_TRANSITION;
    discovery_phase_published = true;
  }

  if (snapshot.state == PairingClientState::DISCOVERING) {
    if (!discovery_phase_published &&
        !context->publish(PairingAsyncPhase::DISCOVERING, snapshot))
      return PairingAsyncOutcome::INVALID_TRANSITION;
    if (context->cancellation_requested()) {
      this->client_.reset_unbound();
      return PairingAsyncOutcome::CANCELLED;
    }
    if (!this->client_.discover_network())
      return context->cancellation_requested() ? PairingAsyncOutcome::CANCELLED
                                               : PairingAsyncOutcome::DISCOVERY_FAILED;
    if (context->cancellation_requested()) {
      this->client_.reset_unbound();
      return PairingAsyncOutcome::CANCELLED;
    }
    snapshot = this->async_client_snapshot();
  }

  if (snapshot.state == PairingClientState::SELECTION_REQUIRED)
    return PairingAsyncOutcome::SELECTION_REQUIRED;
  if (snapshot.state != PairingClientState::CLAIM_READY)
    return PairingAsyncOutcome::INVALID_TRANSITION;

  if (!context->publish(PairingAsyncPhase::SECURE_PAIRING, snapshot) ||
      !this->client_.complete_network_pairing())
    return context->cancellation_requested() ? PairingAsyncOutcome::CANCELLED
                                             : PairingAsyncOutcome::PAIRING_FAILED;

  snapshot = this->async_client_snapshot();
  if (!context->publish(PairingAsyncPhase::RAM_STAGED, snapshot))
    return PairingAsyncOutcome::INVALID_TRANSITION;
  return PairingAsyncOutcome::SUCCESS;
}

PairingClientSnapshot GreenhousePairingAsyncLab::async_client_snapshot() const {
  PairingClientSnapshot snapshot{};
  snapshot.state = state_from_name_(this->client_.state_name());
  snapshot.error = error_from_name_(this->client_.error_name());
  snapshot.candidate_count = this->client_.candidate_count();
  snapshot.selection_required = this->client_.selection_required();
  snapshot.candidate_selected = this->client_.candidate_selected();
  snapshot.credentials_staged = this->client_.ram_credentials_present();
  snapshot.committed = snapshot.state == PairingClientState::COMMITTED;
  snapshot.credential_generation = this->client_.credential_generation();
  return snapshot;
}

const char *GreenhousePairingAsyncLab::state_to_name_(PairingClientState value) {
  switch (value) {
    case PairingClientState::UNBOUND: return "unbound";
    case PairingClientState::DISCOVERING: return "discovering";
    case PairingClientState::CANDIDATE_READY: return "candidate_ready";
    case PairingClientState::SELECTION_REQUIRED: return "selection_required";
    case PairingClientState::CLAIM_READY: return "claim_ready";
    case PairingClientState::CLAIM_SENT: return "claim_sent";
    case PairingClientState::SECURE_OFFER_RECEIVED: return "secure_offer_received";
    case PairingClientState::CHANNEL_ESTABLISHED: return "channel_established";
    case PairingClientState::CREDENTIALS_STAGED: return "credentials_staged";
    case PairingClientState::COMMITTED: return "committed";
    case PairingClientState::RECOVERABLE_FAILURE: return "recoverable_failure";
    case PairingClientState::TERMINAL_FAILURE: return "terminal_failure";
  }
  return "terminal_failure";
}

const char *GreenhousePairingAsyncLab::error_to_name_(PairingClientError value) {
  switch (value) {
    case PairingClientError::NONE: return "none";
    case PairingClientError::INVALID_CONFIGURATION: return "invalid_configuration";
    case PairingClientError::INVALID_DISCOVERY_CONTEXT: return "invalid_discovery_context";
    case PairingClientError::INVALID_CANDIDATE: return "invalid_candidate";
    case PairingClientError::CANDIDATE_CAPACITY_REACHED: return "candidate_capacity_reached";
    case PairingClientError::CANDIDATE_SELECTION_REQUIRED: return "candidate_selection_required";
    case PairingClientError::CANDIDATE_NOT_AVAILABLE: return "candidate_not_available";
    case PairingClientError::INVALID_STATE_TRANSITION: return "invalid_state_transition";
    case PairingClientError::SECURE_OFFER_REJECTED: return "secure_offer_rejected";
    case PairingClientError::CREDENTIALS_REJECTED: return "credentials_rejected";
    case PairingClientError::STORAGE_FAILED: return "storage_failed";
    case PairingClientError::TRANSPORT_FAILED: return "transport_failed";
  }
  return "transport_failed";
}

PairingClientState GreenhousePairingAsyncLab::state_from_name_(const char *value) {
  if (value == nullptr)
    return PairingClientState::TERMINAL_FAILURE;
  if (std::strcmp(value, "unbound") == 0) return PairingClientState::UNBOUND;
  if (std::strcmp(value, "discovering") == 0) return PairingClientState::DISCOVERING;
  if (std::strcmp(value, "candidate_ready") == 0) return PairingClientState::CANDIDATE_READY;
  if (std::strcmp(value, "selection_required") == 0) return PairingClientState::SELECTION_REQUIRED;
  if (std::strcmp(value, "claim_ready") == 0) return PairingClientState::CLAIM_READY;
  if (std::strcmp(value, "claim_sent") == 0) return PairingClientState::CLAIM_SENT;
  if (std::strcmp(value, "secure_offer_received") == 0)
    return PairingClientState::SECURE_OFFER_RECEIVED;
  if (std::strcmp(value, "channel_established") == 0)
    return PairingClientState::CHANNEL_ESTABLISHED;
  if (std::strcmp(value, "credentials_staged") == 0)
    return PairingClientState::CREDENTIALS_STAGED;
  if (std::strcmp(value, "committed") == 0) return PairingClientState::COMMITTED;
  if (std::strcmp(value, "recoverable_failure") == 0)
    return PairingClientState::RECOVERABLE_FAILURE;
  return PairingClientState::TERMINAL_FAILURE;
}

PairingClientError GreenhousePairingAsyncLab::error_from_name_(const char *value) {
  if (value == nullptr || std::strcmp(value, "none") == 0)
    return PairingClientError::NONE;
  if (std::strcmp(value, "invalid_configuration") == 0)
    return PairingClientError::INVALID_CONFIGURATION;
  if (std::strcmp(value, "invalid_discovery_context") == 0)
    return PairingClientError::INVALID_DISCOVERY_CONTEXT;
  if (std::strcmp(value, "invalid_candidate") == 0)
    return PairingClientError::INVALID_CANDIDATE;
  if (std::strcmp(value, "candidate_capacity_reached") == 0)
    return PairingClientError::CANDIDATE_CAPACITY_REACHED;
  if (std::strcmp(value, "candidate_selection_required") == 0)
    return PairingClientError::CANDIDATE_SELECTION_REQUIRED;
  if (std::strcmp(value, "candidate_not_available") == 0)
    return PairingClientError::CANDIDATE_NOT_AVAILABLE;
  if (std::strcmp(value, "invalid_state_transition") == 0)
    return PairingClientError::INVALID_STATE_TRANSITION;
  if (std::strcmp(value, "secure_offer_rejected") == 0)
    return PairingClientError::SECURE_OFFER_REJECTED;
  if (std::strcmp(value, "credentials_rejected") == 0)
    return PairingClientError::CREDENTIALS_REJECTED;
  if (std::strcmp(value, "storage_failed") == 0)
    return PairingClientError::STORAGE_FAILED;
  return PairingClientError::TRANSPORT_FAILED;
}

}  // namespace esphome::greenhouse_pairing_async_lab
