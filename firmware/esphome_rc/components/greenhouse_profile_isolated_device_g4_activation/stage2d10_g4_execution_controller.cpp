#include "stage2d10_g4_execution_controller.h"

#include <algorithm>
#include <sstream>
#include <utility>

namespace esphome::greenhouse_pairing_client {
namespace {

bool lower_hex_64(const std::string &value) {
  return value.size() == 64 &&
         std::all_of(value.begin(), value.end(), [](unsigned char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

void secure_clear(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

}  // namespace

bool Stage2D10G4ExecutionConfig::valid() const {
  return this->expected_candidate.valid() &&
         this->expected_candidate.credential_generation == 1 &&
         lower_hex_64(this->expected_candidate_digest) &&
         lower_hex_64(this->expected_broker_configuration_digest) &&
         this->wifi_timeout_ms >= 1000 && this->wifi_timeout_ms <= 120000;
}

void Stage2D10G4ExecutionConfig::clear() {
  this->expected_candidate.clear();
  secure_clear(&this->expected_candidate_digest);
  secure_clear(&this->expected_broker_configuration_digest);
  this->wifi_timeout_ms = 0;
}

bool Stage2D10G4ExecutionController::configure(
    const Stage2D10G4ExecutionConfig &config,
    Stage2D10G4ActivationCoordinator *coordinator,
    Stage2D10G4WifiPort *wifi_port) {
  this->quiesce();
  if (!config.valid() || coordinator == nullptr || wifi_port == nullptr) {
    this->phase_ = Stage2D10G4ExecutionPhase::FAILED;
    this->failure_ = Stage2D10G4ExecutionFailure::INVALID_CONFIGURATION;
    return false;
  }

  this->config_.expected_candidate = config.expected_candidate;
  this->config_.expected_candidate_digest = config.expected_candidate_digest;
  this->config_.expected_broker_configuration_digest =
      config.expected_broker_configuration_digest;
  this->config_.wifi_timeout_ms = config.wifi_timeout_ms;
  this->coordinator_ = coordinator;
  this->wifi_port_ = wifi_port;
  this->configured_ = true;
  this->phase_ = Stage2D10G4ExecutionPhase::LOCKED;
  this->failure_ = Stage2D10G4ExecutionFailure::NONE;
  return true;
}

bool Stage2D10G4ExecutionController::bind_command(
    Stage2D10G4CommandEnvelope *command,
    Stage2D10G4ExecutionSnapshot *snapshot) {
  if (!this->configured_ || this->phase_ != Stage2D10G4ExecutionPhase::LOCKED ||
      command == nullptr || command->action == Stage2D10G4CommandAction::NONE ||
      this->command_bound_) {
    return this->fail_(Stage2D10G4ExecutionFailure::INVALID_STATE,
                       snapshot);
  }

  this->candidate_digest_match_ = false;
  this->broker_digest_match_ = false;
  if (command->action == Stage2D10G4CommandAction::ACTIVATE_PROFILE) {
    this->candidate_digest_match_ = constant_equal_(
        command->candidate_digest, this->config_.expected_candidate_digest);
    this->broker_digest_match_ = constant_equal_(
        command->broker_configuration_digest,
        this->config_.expected_broker_configuration_digest);
    if (!this->candidate_digest_match_) {
      return this->fail_(
          Stage2D10G4ExecutionFailure::CANDIDATE_DIGEST_MISMATCH,
          snapshot);
    }
    if (!this->broker_digest_match_) {
      return this->fail_(Stage2D10G4ExecutionFailure::BROKER_DIGEST_MISMATCH,
                         snapshot);
    }
  } else if (command->action ==
             Stage2D10G4CommandAction::VERIFY_ACTIVE_READ_ONLY) {
    this->candidate_digest_match_ = constant_equal_(
        command->active_digest, this->config_.expected_candidate_digest);
    this->broker_digest_match_ = true;
    if (!this->candidate_digest_match_) {
      return this->fail_(Stage2D10G4ExecutionFailure::ACTIVE_DIGEST_MISMATCH,
                         snapshot);
    }
  } else {
    return this->fail_(Stage2D10G4ExecutionFailure::ACTION_MISMATCH,
                       snapshot);
  }

  this->command_.clear();
  this->command_ = std::move(*command);
  command->clear();
  this->command_bound_ = true;
  this->command_consumed_ = false;
  this->failure_ = Stage2D10G4ExecutionFailure::NONE;
  this->phase_ = Stage2D10G4ExecutionPhase::COMMAND_BOUND;
  this->refresh_(snapshot);
  return true;
}

bool Stage2D10G4ExecutionController::begin_activate(
    Stage2D10G4ExecutionSnapshot *snapshot) {
  if (!this->configured_ || !this->command_bound_ ||
      this->phase_ != Stage2D10G4ExecutionPhase::COMMAND_BOUND ||
      this->command_.action != Stage2D10G4CommandAction::ACTIVATE_PROFILE ||
      this->wifi_port_ == nullptr) {
    return this->fail_(Stage2D10G4ExecutionFailure::ACTION_MISMATCH,
                       snapshot);
  }

  this->wifi_snapshot_ = {};
  if (!this->wifi_port_->configure_private(
          this->command_.wifi_ssid, this->command_.wifi_password,
          this->command_.wifi_profile_digest, this->config_.wifi_timeout_ms,
          &this->wifi_snapshot_)) {
    secure_clear(&this->command_.wifi_ssid);
    secure_clear(&this->command_.wifi_password);
    return this->fail_(
        Stage2D10G4ExecutionFailure::WIFI_CONFIGURATION_FAILED, snapshot);
  }
  secure_clear(&this->command_.wifi_ssid);
  secure_clear(&this->command_.wifi_password);

  this->wifi_operation_attempted_ = true;
  if (!this->wifi_port_->begin(&this->wifi_snapshot_)) {
    return this->fail_(Stage2D10G4ExecutionFailure::WIFI_START_FAILED,
                       snapshot);
  }
  this->command_consumed_ = true;
  this->failure_ = Stage2D10G4ExecutionFailure::NONE;
  this->phase_ = Stage2D10G4ExecutionPhase::WIFI_CONNECTING;
  this->refresh_(snapshot);
  return true;
}

bool Stage2D10G4ExecutionController::poll(
    uint32_t elapsed_ms, Stage2D10G4ExecutionSnapshot *snapshot) {
  if (!this->configured_ || elapsed_ms == 0 || snapshot == nullptr) {
    return this->fail_(Stage2D10G4ExecutionFailure::INVALID_STATE,
                       snapshot);
  }

  if (this->phase_ == Stage2D10G4ExecutionPhase::WIFI_CONNECTING) {
    if (!this->wifi_port_->poll(elapsed_ms, &this->wifi_snapshot_)) {
      return this->fail_(Stage2D10G4ExecutionFailure::WIFI_FAILED,
                         snapshot);
    }
    if (this->wifi_snapshot_.terminal && !this->wifi_snapshot_.connected) {
      return this->fail_(Stage2D10G4ExecutionFailure::WIFI_FAILED,
                         snapshot);
    }
    if (!this->wifi_snapshot_.connected) {
      this->refresh_(snapshot);
      return true;
    }

    if (!this->coordinator_->recover_prepared_read_only(
            this->config_.expected_candidate, &this->coordinator_snapshot_)) {
      return this->fail_(
          Stage2D10G4ExecutionFailure::RECOVER_PREPARED_FAILED, snapshot,
          this->coordinator_snapshot_.reboot_required);
    }
    this->mqtt_operation_attempted_ = true;
    if (!this->coordinator_->begin_validation(
            &this->coordinator_snapshot_)) {
      return this->fail_(
          Stage2D10G4ExecutionFailure::VALIDATION_START_FAILED, snapshot,
          this->coordinator_snapshot_.reboot_required);
    }
    this->phase_ = Stage2D10G4ExecutionPhase::VALIDATING;
    this->refresh_(snapshot);
    return true;
  }

  if (this->phase_ == Stage2D10G4ExecutionPhase::VALIDATING) {
    if (!this->coordinator_->poll_validation(
            elapsed_ms, &this->coordinator_snapshot_)) {
      return this->fail_(Stage2D10G4ExecutionFailure::VALIDATION_FAILED,
                         snapshot,
                         this->coordinator_snapshot_.reboot_required);
    }
    if (this->coordinator_snapshot_.phase != Stage2D10G4Phase::VERIFIED) {
      this->refresh_(snapshot);
      return true;
    }

    if (!this->coordinator_->grant_activation_authorization(
            this->command_.authorization_digest,
            &this->coordinator_snapshot_)) {
      return this->fail_(
          Stage2D10G4ExecutionFailure::ACTIVATION_AUTHORIZATION_FAILED,
          snapshot, this->coordinator_snapshot_.reboot_required);
    }

    this->activation_attempted_ = true;
    this->phase_ = Stage2D10G4ExecutionPhase::ACTIVATING;
    if (!this->coordinator_->activate(&this->coordinator_snapshot_)) {
      return this->fail_(Stage2D10G4ExecutionFailure::ACTIVATION_FAILED,
                         snapshot,
                         this->coordinator_snapshot_.reboot_required);
    }

    this->activation_succeeded_ = true;
    this->automatic_restart_required_ = true;
    if (this->wifi_port_ != nullptr)
      this->wifi_port_->quiesce_and_destroy();
    this->wifi_snapshot_.connected = false;
    this->wifi_snapshot_.credentials_destroyed = true;
    this->clear_command_();
    this->failure_ = Stage2D10G4ExecutionFailure::NONE;
    this->phase_ =
        Stage2D10G4ExecutionPhase::ACTIVATED_RESTART_REQUIRED;
    this->refresh_(snapshot);
    return true;
  }

  return this->fail_(Stage2D10G4ExecutionFailure::INVALID_STATE,
                     snapshot);
}

bool Stage2D10G4ExecutionController::verify_active_read_only(
    Stage2D10G4ExecutionSnapshot *snapshot) {
  if (!this->configured_ || !this->command_bound_ ||
      this->phase_ != Stage2D10G4ExecutionPhase::COMMAND_BOUND ||
      this->command_.action !=
          Stage2D10G4CommandAction::VERIFY_ACTIVE_READ_ONLY) {
    return this->fail_(Stage2D10G4ExecutionFailure::ACTION_MISMATCH,
                       snapshot);
  }

  this->read_only_verify_attempted_ = true;
  this->command_consumed_ = true;
  this->phase_ = Stage2D10G4ExecutionPhase::VERIFYING_READ_ONLY;
  if (!this->coordinator_->verify_active_read_only(
          this->config_.expected_candidate, &this->coordinator_snapshot_)) {
    return this->fail_(Stage2D10G4ExecutionFailure::READ_ONLY_VERIFY_FAILED,
                       snapshot,
                       this->coordinator_snapshot_.reboot_required);
  }

  this->read_only_verify_succeeded_ = true;
  this->automatic_restart_required_ = false;
  this->clear_command_();
  this->failure_ = Stage2D10G4ExecutionFailure::NONE;
  this->phase_ = Stage2D10G4ExecutionPhase::VERIFIED_AFTER_RESTART;
  this->refresh_(snapshot);
  return true;
}

void Stage2D10G4ExecutionController::quiesce() {
  if (this->wifi_port_ != nullptr)
    this->wifi_port_->quiesce_and_destroy();
  if (this->coordinator_ != nullptr)
    this->coordinator_->quiesce_for_reboot();
  this->clear_command_();
  this->config_.clear();
  this->coordinator_ = nullptr;
  this->wifi_port_ = nullptr;
  this->wifi_snapshot_ = {};
  this->coordinator_snapshot_ = {};
  this->phase_ = Stage2D10G4ExecutionPhase::LOCKED;
  this->failure_ = Stage2D10G4ExecutionFailure::NONE;
  this->configured_ = false;
  this->command_bound_ = false;
  this->command_consumed_ = false;
  this->candidate_digest_match_ = false;
  this->broker_digest_match_ = false;
  this->wifi_operation_attempted_ = false;
  this->mqtt_operation_attempted_ = false;
  this->activation_attempted_ = false;
  this->activation_succeeded_ = false;
  this->read_only_verify_attempted_ = false;
  this->read_only_verify_succeeded_ = false;
  this->automatic_restart_required_ = false;
}

bool Stage2D10G4ExecutionController::candidate_digest(
    const IsolatedCandidateProfile &candidate, std::string *digest) {
  if (digest == nullptr || !candidate.valid())
    return false;
  std::ostringstream material;
  material << CREDENTIALS_CONTENT_TYPE << '\n'
           << candidate.system_id << '\n'
           << candidate.node_id << '\n'
           << candidate.broker_host << '\n'
           << candidate.broker_port << '\n'
           << candidate.broker_tls_server_name << '\n'
           << candidate.ca_pem << '\n'
           << candidate.mqtt_username << '\n'
           << candidate.mqtt_client_id << '\n'
           << candidate.credential_generation << '\n'
           << candidate.mqtt_password;
  std::string canonical = material.str();
  const bool success =
      Stage2D10G4CommandCodec::command_sha256(canonical, digest);
  secure_clear(&canonical);
  return success;
}

const char *Stage2D10G4ExecutionController::phase_name(
    Stage2D10G4ExecutionPhase phase) {
  switch (phase) {
    case Stage2D10G4ExecutionPhase::LOCKED:
      return "locked";
    case Stage2D10G4ExecutionPhase::COMMAND_BOUND:
      return "command_bound";
    case Stage2D10G4ExecutionPhase::WIFI_CONNECTING:
      return "wifi_connecting";
    case Stage2D10G4ExecutionPhase::VALIDATING:
      return "validating";
    case Stage2D10G4ExecutionPhase::ACTIVATING:
      return "activating";
    case Stage2D10G4ExecutionPhase::ACTIVATED_RESTART_REQUIRED:
      return "activated_restart_required";
    case Stage2D10G4ExecutionPhase::VERIFYING_READ_ONLY:
      return "verifying_read_only";
    case Stage2D10G4ExecutionPhase::VERIFIED_AFTER_RESTART:
      return "verified_after_restart";
    case Stage2D10G4ExecutionPhase::FAILED:
      return "failed";
    case Stage2D10G4ExecutionPhase::REBOOT_REQUIRED:
      return "reboot_required";
  }
  return "unknown";
}

const char *Stage2D10G4ExecutionController::failure_name(
    Stage2D10G4ExecutionFailure failure) {
  switch (failure) {
    case Stage2D10G4ExecutionFailure::NONE:
      return "none";
    case Stage2D10G4ExecutionFailure::INVALID_CONFIGURATION:
      return "invalid_configuration";
    case Stage2D10G4ExecutionFailure::INVALID_STATE:
      return "invalid_state";
    case Stage2D10G4ExecutionFailure::ACTION_MISMATCH:
      return "action_mismatch";
    case Stage2D10G4ExecutionFailure::CANDIDATE_DIGEST_MISMATCH:
      return "candidate_digest_mismatch";
    case Stage2D10G4ExecutionFailure::BROKER_DIGEST_MISMATCH:
      return "broker_digest_mismatch";
    case Stage2D10G4ExecutionFailure::WIFI_CONFIGURATION_FAILED:
      return "wifi_configuration_failed";
    case Stage2D10G4ExecutionFailure::WIFI_START_FAILED:
      return "wifi_start_failed";
    case Stage2D10G4ExecutionFailure::WIFI_FAILED:
      return "wifi_failed";
    case Stage2D10G4ExecutionFailure::RECOVER_PREPARED_FAILED:
      return "recover_prepared_failed";
    case Stage2D10G4ExecutionFailure::VALIDATION_START_FAILED:
      return "validation_start_failed";
    case Stage2D10G4ExecutionFailure::VALIDATION_FAILED:
      return "validation_failed";
    case Stage2D10G4ExecutionFailure::ACTIVATION_AUTHORIZATION_FAILED:
      return "activation_authorization_failed";
    case Stage2D10G4ExecutionFailure::ACTIVATION_FAILED:
      return "activation_failed";
    case Stage2D10G4ExecutionFailure::ACTIVE_DIGEST_MISMATCH:
      return "active_digest_mismatch";
    case Stage2D10G4ExecutionFailure::READ_ONLY_VERIFY_FAILED:
      return "read_only_verify_failed";
  }
  return "unknown";
}

bool Stage2D10G4ExecutionController::fail_(
    Stage2D10G4ExecutionFailure failure,
    Stage2D10G4ExecutionSnapshot *snapshot, bool reboot_required) {
  this->failure_ = failure;
  this->automatic_restart_required_ = reboot_required;
  this->phase_ = reboot_required ? Stage2D10G4ExecutionPhase::REBOOT_REQUIRED
                                 : Stage2D10G4ExecutionPhase::FAILED;
  if (this->wifi_port_ != nullptr)
    this->wifi_port_->quiesce_and_destroy();
  if (this->coordinator_ != nullptr)
    this->coordinator_->quiesce_for_reboot();
  this->wifi_snapshot_.connected = false;
  this->wifi_snapshot_.credentials_destroyed = true;
  this->clear_command_();
  this->refresh_(snapshot);
  return false;
}

void Stage2D10G4ExecutionController::refresh_(
    Stage2D10G4ExecutionSnapshot *snapshot) const {
  if (snapshot == nullptr)
    return;
  snapshot->phase = this->phase_;
  snapshot->failure = this->failure_;
  snapshot->wifi = this->wifi_snapshot_;
  snapshot->coordinator = this->coordinator_snapshot_;
  snapshot->command_bound = this->command_bound_;
  snapshot->command_consumed = this->command_consumed_;
  snapshot->candidate_digest_match = this->candidate_digest_match_;
  snapshot->broker_digest_match = this->broker_digest_match_;
  snapshot->wifi_operation_attempted = this->wifi_operation_attempted_;
  snapshot->mqtt_operation_attempted = this->mqtt_operation_attempted_;
  snapshot->activation_attempted = this->activation_attempted_;
  snapshot->activation_succeeded = this->activation_succeeded_;
  snapshot->read_only_verify_attempted =
      this->read_only_verify_attempted_;
  snapshot->read_only_verify_succeeded =
      this->read_only_verify_succeeded_;
  snapshot->automatic_restart_required =
      this->automatic_restart_required_;
  snapshot->cleanup_operation_attempted = false;
}

void Stage2D10G4ExecutionController::clear_command_() {
  this->command_.clear();
  this->command_bound_ = false;
}

bool Stage2D10G4ExecutionController::constant_equal_(
    const std::string &left, const std::string &right) {
  if (left.size() != right.size())
    return false;
  uint8_t difference = 0;
  for (size_t index = 0; index < left.size(); index++)
    difference |= static_cast<uint8_t>(left[index] ^ right[index]);
  return difference == 0;
}

}  // namespace esphome::greenhouse_pairing_client
