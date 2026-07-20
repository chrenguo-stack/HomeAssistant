#include "pairing_client_core.h"

#include <algorithm>
#include <cctype>
#include <limits>

namespace esphome::greenhouse_pairing_client {

namespace {

constexpr size_t INVALID_INDEX = std::numeric_limits<size_t>::max();
constexpr const char *CIPHER_SUITE = "X25519-HKDF-SHA256-CHACHA20-POLY1305";

bool is_ascii_safe_identifier_char(char value) {
  const auto byte = static_cast<unsigned char>(value);
  return std::isalnum(byte) != 0 || value == '.' || value == '_' || value == ':' || value == '-';
}

bool is_hex(char value) {
  const auto byte = static_cast<unsigned char>(value);
  return std::isdigit(byte) != 0 || (value >= 'a' && value <= 'f') || (value >= 'A' && value <= 'F');
}

bool ends_with(const std::string &value, const std::string &suffix) {
  return value.size() >= suffix.size() && value.compare(value.size() - suffix.size(), suffix.size(), suffix) == 0;
}

bool parse_ipv4(const std::string &value, uint32_t *address) {
  if (address == nullptr)
    return false;
  uint32_t result = 0;
  size_t start = 0;
  for (int part = 0; part < 4; part++) {
    const size_t end = value.find('.', start);
    if ((part < 3 && end == std::string::npos) || (part == 3 && end != std::string::npos))
      return false;
    const size_t stop = end == std::string::npos ? value.size() : end;
    if (stop == start || stop - start > 3)
      return false;
    uint32_t octet = 0;
    for (size_t index = start; index < stop; index++) {
      const auto byte = static_cast<unsigned char>(value[index]);
      if (std::isdigit(byte) == 0)
        return false;
      octet = octet * 10U + static_cast<uint32_t>(value[index] - '0');
    }
    if (octet > 255U)
      return false;
    result = (result << 8U) | octet;
    start = stop + 1U;
  }
  *address = result;
  return true;
}

bool is_local_ipv4(uint32_t address) {
  const uint8_t first = static_cast<uint8_t>(address >> 24U);
  const uint8_t second = static_cast<uint8_t>(address >> 16U);
  return first == 127U || first == 10U || (first == 172U && second >= 16U && second <= 31U) ||
         (first == 192U && second == 168U) || (first == 169U && second == 254U);
}

uint32_t ttl_to_ms(uint16_t ttl_s, uint16_t cap_s) {
  const uint32_t effective = std::min<uint32_t>(ttl_s, cap_s);
  return effective * 1000U;
}

}  // namespace

bool PairingClientCore::configure(const std::string &hardware_id, const std::string &pairing_id,
                                  size_t max_candidates, uint16_t candidate_ttl_cap_s) {
  if (!valid_identifier(hardware_id) || !valid_request_id(pairing_id) || max_candidates < 1 ||
      max_candidates > 16 || candidate_ttl_cap_s < 1 || candidate_ttl_cap_s > 3600) {
    this->set_error_(PairingClientError::INVALID_CONFIGURATION);
    this->set_state_(PairingClientState::TERMINAL_FAILURE);
    return false;
  }
  this->hardware_id_ = hardware_id;
  this->pairing_id_ = pairing_id;
  this->max_candidates_ = max_candidates;
  this->candidate_ttl_cap_s_ = candidate_ttl_cap_s;
  this->reset_unbound();
  return true;
}

bool PairingClientCore::start_discovery(const std::string &request_id, const std::string &nonce, uint32_t now_ms) {
  if (this->state_ == PairingClientState::COMMITTED || !valid_request_id(request_id) ||
      !valid_base64url_32(nonce) || this->hardware_id_.empty() || this->pairing_id_.empty()) {
    this->set_error_(PairingClientError::INVALID_DISCOVERY_CONTEXT);
    return false;
  }
  this->request_id_ = request_id;
  this->nonce_ = nonce;
  this->discovery_started_at_ms_ = now_ms;
  this->candidates_.clear();
  this->selected_index_ = INVALID_INDEX;
  this->session_id_.clear();
  this->manager_nonce_.clear();
  this->manager_public_key_.clear();
  this->node_id_.clear();
  this->credential_generation_ = 0;
  this->set_error_(PairingClientError::NONE);
  this->set_state_(PairingClientState::DISCOVERING);
  return true;
}

bool PairingClientCore::observe_candidate(const std::string &request_id, const std::string &nonce,
                                          const ManagerCandidate &candidate, uint32_t now_ms) {
  if (this->state_ != PairingClientState::DISCOVERING && this->state_ != PairingClientState::CANDIDATE_READY &&
      this->state_ != PairingClientState::SELECTION_REQUIRED && this->state_ != PairingClientState::CLAIM_READY) {
    this->set_error_(PairingClientError::INVALID_STATE_TRANSITION);
    return false;
  }
  if (request_id != this->request_id_ || nonce != this->nonce_) {
    this->set_error_(PairingClientError::INVALID_DISCOVERY_CONTEXT);
    return false;
  }
  if (!valid_candidate(candidate)) {
    this->set_error_(PairingClientError::INVALID_CANDIDATE);
    return false;
  }

  this->prune_candidates(now_ms);
  for (auto &observation : this->candidates_) {
    if (same_candidate(observation.candidate, candidate)) {
      observation.candidate = candidate;
      observation.observed_at_ms = now_ms;
      this->resolve_selection_state_();
      this->set_error_(PairingClientError::NONE);
      return true;
    }
  }
  if (this->candidates_.size() >= this->max_candidates_) {
    this->set_error_(PairingClientError::CANDIDATE_CAPACITY_REACHED);
    return false;
  }
  this->candidates_.push_back(CandidateObservation{.candidate = candidate, .observed_at_ms = now_ms});
  this->resolve_selection_state_();
  this->set_error_(PairingClientError::NONE);
  return true;
}

void PairingClientCore::prune_candidates(uint32_t now_ms) {
  if (this->state_ == PairingClientState::CLAIM_SENT ||
      this->state_ == PairingClientState::SECURE_OFFER_RECEIVED ||
      this->state_ == PairingClientState::CHANNEL_ESTABLISHED ||
      this->state_ == PairingClientState::CREDENTIALS_STAGED || this->state_ == PairingClientState::COMMITTED)
    return;

  ManagerCandidate selected;
  const bool had_selection = this->selected_index_valid_();
  if (had_selection)
    selected = this->candidates_[this->selected_index_].candidate;

  this->candidates_.erase(
      std::remove_if(this->candidates_.begin(), this->candidates_.end(), [this, now_ms](const auto &observation) {
        const uint32_t elapsed = now_ms - observation.observed_at_ms;
        return elapsed >= ttl_to_ms(observation.candidate.ttl_s, this->candidate_ttl_cap_s_);
      }),
      this->candidates_.end());

  this->selected_index_ = INVALID_INDEX;
  if (had_selection) {
    for (size_t index = 0; index < this->candidates_.size(); index++) {
      if (same_candidate(this->candidates_[index].candidate, selected)) {
        this->selected_index_ = index;
        break;
      }
    }
  }
  this->resolve_selection_state_();
}

bool PairingClientCore::select_candidate(size_t index) {
  if (this->state_ != PairingClientState::SELECTION_REQUIRED && this->state_ != PairingClientState::CANDIDATE_READY &&
      this->state_ != PairingClientState::CLAIM_READY) {
    this->set_error_(PairingClientError::INVALID_STATE_TRANSITION);
    return false;
  }
  if (index >= this->candidates_.size()) {
    this->set_error_(PairingClientError::CANDIDATE_NOT_AVAILABLE);
    return false;
  }
  this->selected_index_ = index;
  this->set_error_(PairingClientError::NONE);
  this->set_state_(PairingClientState::CLAIM_READY);
  return true;
}

bool PairingClientCore::mark_claim_sent() {
  if (this->state_ != PairingClientState::CLAIM_READY || !this->selected_index_valid_()) {
    this->set_error_(this->candidates_.size() > 1 ? PairingClientError::CANDIDATE_SELECTION_REQUIRED
                                                 : PairingClientError::INVALID_STATE_TRANSITION);
    return false;
  }
  this->set_error_(PairingClientError::NONE);
  this->set_state_(PairingClientState::CLAIM_SENT);
  return true;
}

bool PairingClientCore::accept_secure_offer(const std::string &session_id, const std::string &manager_nonce,
                                            const std::string &manager_public_key,
                                            const std::string &cipher_suite) {
  if (this->state_ != PairingClientState::CLAIM_SENT || !valid_request_id(session_id) ||
      !valid_base64url_32(manager_nonce) || !valid_base64url_32(manager_public_key) || cipher_suite != CIPHER_SUITE) {
    this->set_error_(PairingClientError::SECURE_OFFER_REJECTED);
    return false;
  }
  this->session_id_ = session_id;
  this->manager_nonce_ = manager_nonce;
  this->manager_public_key_ = manager_public_key;
  this->set_error_(PairingClientError::NONE);
  this->set_state_(PairingClientState::SECURE_OFFER_RECEIVED);
  return true;
}

bool PairingClientCore::mark_channel_established() {
  if (this->state_ != PairingClientState::SECURE_OFFER_RECEIVED) {
    this->set_error_(PairingClientError::INVALID_STATE_TRANSITION);
    return false;
  }
  this->set_error_(PairingClientError::NONE);
  this->set_state_(PairingClientState::CHANNEL_ESTABLISHED);
  return true;
}

bool PairingClientCore::stage_credentials(const std::string &node_id, uint32_t credential_generation) {
  if (this->state_ != PairingClientState::CHANNEL_ESTABLISHED || !valid_identifier(node_id) ||
      credential_generation == 0) {
    this->set_error_(PairingClientError::CREDENTIALS_REJECTED);
    return false;
  }
  this->node_id_ = node_id;
  this->credential_generation_ = credential_generation;
  this->set_error_(PairingClientError::NONE);
  this->set_state_(PairingClientState::CREDENTIALS_STAGED);
  return true;
}

bool PairingClientCore::commit_credentials() {
  if (this->state_ != PairingClientState::CREDENTIALS_STAGED || this->node_id_.empty() ||
      this->credential_generation_ == 0) {
    this->set_error_(PairingClientError::INVALID_STATE_TRANSITION);
    return false;
  }
  this->set_error_(PairingClientError::NONE);
  this->set_state_(PairingClientState::COMMITTED);
  return true;
}

void PairingClientCore::fail(PairingClientError error, bool recoverable) {
  this->set_error_(error == PairingClientError::NONE ? PairingClientError::TRANSPORT_FAILED : error);
  this->set_state_(recoverable ? PairingClientState::RECOVERABLE_FAILURE : PairingClientState::TERMINAL_FAILURE);
}

void PairingClientCore::reset_unbound() {
  this->request_id_.clear();
  this->nonce_.clear();
  this->discovery_started_at_ms_ = 0;
  this->candidates_.clear();
  this->selected_index_ = INVALID_INDEX;
  this->session_id_.clear();
  this->manager_nonce_.clear();
  this->manager_public_key_.clear();
  this->node_id_.clear();
  this->credential_generation_ = 0;
  this->set_error_(PairingClientError::NONE);
  this->set_state_(PairingClientState::UNBOUND);
}

PairingClientSnapshot PairingClientCore::snapshot() const {
  return PairingClientSnapshot{
      .state = this->state_,
      .error = this->error_,
      .candidate_count = this->candidates_.size(),
      .selection_required = this->state_ == PairingClientState::SELECTION_REQUIRED,
      .candidate_selected = this->selected_index_valid_(),
      .secure_offer_present = !this->session_id_.empty(),
      .credentials_staged = this->state_ == PairingClientState::CREDENTIALS_STAGED ||
                            this->state_ == PairingClientState::COMMITTED,
      .committed = this->state_ == PairingClientState::COMMITTED,
      .credential_generation = this->credential_generation_,
  };
}

const ManagerCandidate *PairingClientCore::selected_candidate() const {
  return this->selected_index_valid_() ? &this->candidates_[this->selected_index_].candidate : nullptr;
}

const char *PairingClientCore::state_name() const {
  switch (this->state_) {
    case PairingClientState::UNBOUND:
      return "unbound";
    case PairingClientState::DISCOVERING:
      return "discovering";
    case PairingClientState::CANDIDATE_READY:
      return "candidate_ready";
    case PairingClientState::SELECTION_REQUIRED:
      return "selection_required";
    case PairingClientState::CLAIM_READY:
      return "claim_ready";
    case PairingClientState::CLAIM_SENT:
      return "claim_sent";
    case PairingClientState::SECURE_OFFER_RECEIVED:
      return "secure_offer_received";
    case PairingClientState::CHANNEL_ESTABLISHED:
      return "channel_established";
    case PairingClientState::CREDENTIALS_STAGED:
      return "credentials_staged";
    case PairingClientState::COMMITTED:
      return "committed";
    case PairingClientState::RECOVERABLE_FAILURE:
      return "recoverable_failure";
    case PairingClientState::TERMINAL_FAILURE:
      return "terminal_failure";
  }
  return "unknown";
}

const char *PairingClientCore::error_name() const {
  switch (this->error_) {
    case PairingClientError::NONE:
      return "none";
    case PairingClientError::INVALID_CONFIGURATION:
      return "invalid_configuration";
    case PairingClientError::INVALID_DISCOVERY_CONTEXT:
      return "invalid_discovery_context";
    case PairingClientError::INVALID_CANDIDATE:
      return "invalid_candidate";
    case PairingClientError::CANDIDATE_CAPACITY_REACHED:
      return "candidate_capacity_reached";
    case PairingClientError::CANDIDATE_SELECTION_REQUIRED:
      return "candidate_selection_required";
    case PairingClientError::CANDIDATE_NOT_AVAILABLE:
      return "candidate_not_available";
    case PairingClientError::INVALID_STATE_TRANSITION:
      return "invalid_state_transition";
    case PairingClientError::SECURE_OFFER_REJECTED:
      return "secure_offer_rejected";
    case PairingClientError::CREDENTIALS_REJECTED:
      return "credentials_rejected";
    case PairingClientError::STORAGE_FAILED:
      return "storage_failed";
    case PairingClientError::TRANSPORT_FAILED:
      return "transport_failed";
  }
  return "unknown";
}

bool PairingClientCore::valid_candidate(const ManagerCandidate &candidate) {
  if (candidate.schema != MANAGER_CANDIDATE_SCHEMA || !valid_identifier(candidate.manager_id) ||
      !valid_identifier(candidate.system_id) || !valid_local_host(candidate.host) ||
      (candidate.scheme != "http" && candidate.scheme != "https") || candidate.port == 0 ||
      candidate.pairing_path.empty() || candidate.pairing_path.front() != '/' ||
      candidate.pairing_path.size() > 256 || candidate.pairing_path.rfind("//", 0) == 0 ||
      candidate.protocol != SECURE_PAIRING_PROTOCOL || candidate.ttl_s < 1 || candidate.ttl_s > 3600)
    return false;
  return std::all_of(candidate.pairing_path.begin(), candidate.pairing_path.end(), [](char value) {
    const auto byte = static_cast<unsigned char>(value);
    return byte >= 0x21U && byte <= 0x7EU && value != '"' && value != '\\';
  });
}

bool PairingClientCore::valid_identifier(const std::string &value) {
  return !value.empty() && value.size() <= 128 &&
         std::all_of(value.begin(), value.end(), [](char character) { return is_ascii_safe_identifier_char(character); });
}

bool PairingClientCore::valid_request_id(const std::string &value) {
  if (value.size() != 36)
    return false;
  static constexpr size_t HYPHENS[] = {8, 13, 18, 23};
  for (size_t index = 0; index < value.size(); index++) {
    const bool hyphen = std::find(std::begin(HYPHENS), std::end(HYPHENS), index) != std::end(HYPHENS);
    if (hyphen ? value[index] != '-' : !is_hex(value[index]))
      return false;
  }
  return true;
}

bool PairingClientCore::valid_base64url_32(const std::string &value) {
  return value.size() == 43 && std::all_of(value.begin(), value.end(), [](char character) {
           const auto byte = static_cast<unsigned char>(character);
           return std::isalnum(byte) != 0 || character == '-' || character == '_';
         });
}

bool PairingClientCore::valid_local_host(const std::string &value) {
  if (value.empty() || value.size() > 253 ||
      std::any_of(value.begin(), value.end(), [](char character) { return std::isspace(static_cast<unsigned char>(character)); }))
    return false;
  std::string normalized = value;
  if (!normalized.empty() && normalized.back() == '.')
    normalized.pop_back();
  uint32_t address = 0;
  if (parse_ipv4(normalized, &address))
    return is_local_ipv4(address);
  if (!ends_with(normalized, ".local") || normalized.size() < 7)
    return false;
  size_t start = 0;
  while (start < normalized.size()) {
    const size_t stop = normalized.find('.', start);
    const size_t end = stop == std::string::npos ? normalized.size() : stop;
    if (end == start || end - start > 63 || normalized[start] == '-' || normalized[end - 1] == '-')
      return false;
    for (size_t index = start; index < end; index++) {
      const auto byte = static_cast<unsigned char>(normalized[index]);
      if (std::isalnum(byte) == 0 && normalized[index] != '-')
        return false;
    }
    start = end + 1;
  }
  return true;
}

bool PairingClientCore::same_candidate(const ManagerCandidate &left, const ManagerCandidate &right) {
  return left.manager_id == right.manager_id && left.system_id == right.system_id && left.host == right.host &&
         left.scheme == right.scheme && left.port == right.port && left.pairing_path == right.pairing_path &&
         left.protocol == right.protocol;
}

std::string PairingClientCore::build_claim_transcript(const std::string &manager_id,
                                                      const std::string &hardware_id,
                                                      const std::string &pairing_id) {
  if (!valid_identifier(manager_id) || !valid_identifier(hardware_id) || !valid_request_id(pairing_id))
    return {};
  return std::string(CLAIM_SCHEMA) + "\n" + manager_id + "\n" + hardware_id + "\n" + pairing_id;
}

void PairingClientCore::set_state_(PairingClientState state) { this->state_ = state; }

void PairingClientCore::set_error_(PairingClientError error) { this->error_ = error; }

void PairingClientCore::resolve_selection_state_() {
  if (this->candidates_.empty()) {
    this->selected_index_ = INVALID_INDEX;
    this->set_state_(PairingClientState::DISCOVERING);
    return;
  }
  if (this->candidates_.size() == 1) {
    this->selected_index_ = 0;
    this->set_state_(PairingClientState::CLAIM_READY);
    return;
  }
  if (this->selected_index_valid_()) {
    this->set_state_(PairingClientState::CLAIM_READY);
    return;
  }
  this->selected_index_ = INVALID_INDEX;
  this->set_state_(PairingClientState::SELECTION_REQUIRED);
}

bool PairingClientCore::selected_index_valid_() const {
  return this->selected_index_ != INVALID_INDEX && this->selected_index_ < this->candidates_.size();
}

}  // namespace esphome::greenhouse_pairing_client
