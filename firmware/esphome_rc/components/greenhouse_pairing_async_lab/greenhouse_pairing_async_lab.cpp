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
  if (!this->worker_.request(operation_id))
    return false;
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
  if (snapshot.state == PairingClientState::UNBOUND) {
    if (!context->publish(PairingAsyncPhase::DISCOVERING, snapshot) ||
        !this->client_.start_random_discovery())
      return PairingAsyncOutcome::DISCOVERY_FAILED;
    snapshot = this->async_client_snapshot();
  }

  if (snapshot.state == PairingClientState::DISCOVERING) {
    if (!context->publish(PairingAsyncPhase::DISCOVERING, snapshot) ||
        !this->client_.discover_network())
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
