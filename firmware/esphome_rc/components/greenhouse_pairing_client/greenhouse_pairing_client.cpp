#include "greenhouse_pairing_client.h"

#include <array>
#include <cstdio>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "mbedtls/base64.h"
#include "mbedtls/md.h"

namespace esphome::greenhouse_pairing_client {

static const char *const TAG = "greenhouse_pairing_client";

void GreenhousePairingClient::setup() {
  if (!PairingClientCore::valid_base64url_32(this->pairing_secret_) ||
      !this->core_.configure(this->hardware_id_, this->pairing_id_, this->max_candidates_,
                            this->candidate_ttl_cap_s_)) {
    ESP_LOGE(TAG, "Pairing client configuration rejected");
    this->mark_failed();
    return;
  }
  this->last_prune_ms_ = millis();
}

void GreenhousePairingClient::loop() {
  if (this->is_failed())
    return;
  const uint32_t now = millis();
  if (now - this->last_prune_ms_ < 1000U)
    return;
  this->last_prune_ms_ = now;
  this->core_.prune_candidates(now);
}

void GreenhousePairingClient::dump_config() {
  const auto snapshot = this->core_.snapshot();
  ESP_LOGCONFIG(TAG,
                "Greenhouse Pairing Client Core:\n"
                "  Hardware identity configured: %s\n"
                "  Pairing ID configured: %s\n"
                "  Pairing secret present: %s\n"
                "  Pairing state: %s\n"
                "  Last error: %s\n"
                "  Candidate count: %u\n"
                "  Explicit selection required: %s\n"
                "  Candidate selected: %s\n"
                "  Credential generation: %" PRIu32 "\n"
                "  Network transport enabled: NO\n"
                "  Secret values included: NO",
                YESNO(!this->hardware_id_.empty()), YESNO(!this->pairing_id_.empty()),
                YESNO(!this->pairing_secret_.empty()), this->core_.state_name(), this->core_.error_name(),
                static_cast<unsigned>(snapshot.candidate_count), YESNO(snapshot.selection_required),
                YESNO(snapshot.candidate_selected), snapshot.credential_generation);
}

float GreenhousePairingClient::get_setup_priority() const { return setup_priority::DATA; }

bool GreenhousePairingClient::start_discovery(const std::string &request_id, const std::string &nonce) {
  if (this->is_failed())
    return false;
  return this->core_.start_discovery(request_id, nonce, millis());
}

bool GreenhousePairingClient::observe_candidate(const std::string &manager_id, const std::string &system_id,
                                                const std::string &host, const std::string &scheme,
                                                uint16_t port, const std::string &pairing_path,
                                                uint16_t priority, uint16_t ttl_s) {
  if (this->is_failed())
    return false;
  const ManagerCandidate candidate{
      .schema = MANAGER_CANDIDATE_SCHEMA,
      .manager_id = manager_id,
      .system_id = system_id,
      .host = host,
      .scheme = scheme,
      .port = port,
      .pairing_path = pairing_path,
      .protocol = SECURE_PAIRING_PROTOCOL,
      .priority = priority,
      .ttl_s = ttl_s,
  };
  return this->core_.observe_candidate(this->core_.request_id(), this->core_.nonce(), candidate, millis());
}

bool GreenhousePairingClient::select_candidate(size_t index) { return this->core_.select_candidate(index); }

bool GreenhousePairingClient::mark_claim_sent() { return this->core_.mark_claim_sent(); }

bool GreenhousePairingClient::accept_secure_offer_for_test(const std::string &session_id,
                                                           const std::string &manager_nonce,
                                                           const std::string &manager_public_key,
                                                           const std::string &cipher_suite) {
  return this->core_.accept_secure_offer(session_id, manager_nonce, manager_public_key, cipher_suite);
}

bool GreenhousePairingClient::mark_channel_established_for_test() {
  return this->core_.mark_channel_established();
}

bool GreenhousePairingClient::stage_credentials_for_test(const std::string &node_id,
                                                         uint32_t credential_generation) {
  return this->core_.stage_credentials(node_id, credential_generation);
}

bool GreenhousePairingClient::commit_credentials_for_test() {
  if (!this->core_.commit_credentials())
    return false;
  this->clear_pairing_secret_();
  return true;
}

void GreenhousePairingClient::reset_unbound() { this->core_.reset_unbound(); }

std::string GreenhousePairingClient::build_discovery_request_json() const {
  const auto snapshot = this->core_.snapshot();
  if (snapshot.state != PairingClientState::DISCOVERING && snapshot.state != PairingClientState::CLAIM_READY &&
      snapshot.state != PairingClientState::SELECTION_REQUIRED)
    return {};
  return std::string("{\"hardware_id\":\"") + json_escape_(this->core_.hardware_id()) +
         "\",\"nonce\":\"" + json_escape_(this->core_.nonce()) +
         "\",\"protocols\":[\"" + SECURE_PAIRING_PROTOCOL + "\"],\"request_id\":\"" +
         json_escape_(this->core_.request_id()) + "\",\"schema\":\"" + DISCOVERY_QUERY_SCHEMA + "\"}";
}

std::string GreenhousePairingClient::build_claim_request_json() const {
  const auto *candidate = this->core_.selected_candidate();
  if (candidate == nullptr || this->core_.snapshot().state != PairingClientState::CLAIM_READY)
    return {};
  std::string proof;
  if (!this->claim_proof_(&proof))
    return {};
  return std::string("{\"claim_proof\":\"") + json_escape_(proof) + "\",\"hardware_id\":\"" +
         json_escape_(this->core_.hardware_id()) + "\",\"manager_id\":\"" +
         json_escape_(candidate->manager_id) + "\",\"pairing_id\":\"" +
         json_escape_(this->core_.pairing_id()) + "\",\"schema\":\"" + CLAIM_SCHEMA + "\"}";
}

std::string GreenhousePairingClient::json_escape_(const std::string &value) {
  std::string escaped;
  escaped.reserve(value.size() + 8);
  for (const auto character : value) {
    const auto byte = static_cast<unsigned char>(character);
    switch (character) {
      case '\\':
        escaped += "\\\\";
        break;
      case '"':
        escaped += "\\\"";
        break;
      case '\b':
        escaped += "\\b";
        break;
      case '\f':
        escaped += "\\f";
        break;
      case '\n':
        escaped += "\\n";
        break;
      case '\r':
        escaped += "\\r";
        break;
      case '\t':
        escaped += "\\t";
        break;
      default:
        if (byte < 0x20U) {
          char encoded[7];
          snprintf(encoded, sizeof(encoded), "\\u%04x", byte);
          escaped += encoded;
        } else {
          escaped += character;
        }
    }
  }
  return escaped;
}

bool GreenhousePairingClient::claim_proof_(std::string *output) const {
  if (output == nullptr || this->pairing_secret_.empty())
    return false;
  const auto *candidate = this->core_.selected_candidate();
  if (candidate == nullptr)
    return false;
  const std::string transcript = PairingClientCore::build_claim_transcript(
      candidate->manager_id, this->core_.hardware_id(), this->core_.pairing_id());
  if (transcript.empty())
    return false;

  std::array<uint8_t, 32> secret{};
  std::array<uint8_t, 32> digest{};
  bool success = false;
  if (decode_pairing_secret_(this->pairing_secret_, secret.data())) {
    const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    if (info != nullptr &&
        mbedtls_md_hmac(info, secret.data(), secret.size(),
                        reinterpret_cast<const unsigned char *>(transcript.data()), transcript.size(),
                        digest.data()) == 0)
      success = encode_base64url_(digest.data(), digest.size(), output);
  }
  std::fill(secret.begin(), secret.end(), 0);
  std::fill(digest.begin(), digest.end(), 0);
  return success;
}

bool GreenhousePairingClient::decode_pairing_secret_(const std::string &value, uint8_t output[32]) {
  if (output == nullptr || !PairingClientCore::valid_base64url_32(value))
    return false;
  std::string normalized = value;
  for (auto &character : normalized) {
    if (character == '-')
      character = '+';
    else if (character == '_')
      character = '/';
  }
  normalized.push_back('=');
  size_t written = 0;
  return mbedtls_base64_decode(output, 32, &written,
                               reinterpret_cast<const unsigned char *>(normalized.data()), normalized.size()) == 0 &&
         written == 32;
}

bool GreenhousePairingClient::encode_base64url_(const uint8_t *data, size_t length, std::string *output) {
  if (data == nullptr || output == nullptr)
    return false;
  std::array<unsigned char, 96> encoded{};
  size_t written = 0;
  if (mbedtls_base64_encode(encoded.data(), encoded.size(), &written, data, length) != 0)
    return false;
  std::string value(reinterpret_cast<const char *>(encoded.data()), written);
  while (!value.empty() && value.back() == '=')
    value.pop_back();
  for (auto &character : value) {
    if (character == '+')
      character = '-';
    else if (character == '/')
      character = '_';
  }
  *output = value;
  return true;
}

void GreenhousePairingClient::clear_pairing_secret_() {
  std::fill(this->pairing_secret_.begin(), this->pairing_secret_.end(), '\0');
  this->pairing_secret_.clear();
  this->pairing_secret_.shrink_to_fit();
}

}  // namespace esphome::greenhouse_pairing_client
