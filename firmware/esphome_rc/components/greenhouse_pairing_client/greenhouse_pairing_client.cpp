#include "greenhouse_pairing_client.h"

#include <algorithm>
#include <array>
#include <cstdio>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "mbedtls/md.h"

#ifdef USE_ESP32
#include "esp_random.h"
#endif

namespace esphome::greenhouse_pairing_client {

namespace {

void secure_clear(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

}  // namespace

static const char *const TAG = "greenhouse_pairing_client";

GreenhousePairingClient::~GreenhousePairingClient() {
  this->network_.clear();
  this->ram_credentials_.clear();
  this->clear_pairing_secret_();
}

void GreenhousePairingClient::setup() {
  if (!PairingClientCore::valid_base64url_32(this->pairing_secret_) ||
      !this->core_.configure(this->hardware_id_, this->pairing_id_, this->max_candidates_,
                            this->candidate_ttl_cap_s_) ||
      (this->network_options_.enabled &&
       (!PairingTransportCore::validate_limits(this->network_options_.limits) ||
        (this->network_options_.udp_enabled &&
         !PairingTransportCore::validate_udp_target(this->network_options_.udp_target))))) {
    ESP_LOGE(TAG, "Pairing client configuration rejected");
    this->mark_failed();
    return;
  }
  this->network_.set_options(this->network_options_);
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
                "Greenhouse Pairing Client:\n"
                "  Hardware identity configured: %s\n"
                "  Pairing ID configured: %s\n"
                "  Pairing secret present: %s\n"
                "  Pairing state: %s\n"
                "  Last error: %s\n"
                "  Candidate count: %u\n"
                "  Explicit selection required: %s\n"
                "  Candidate selected: %s\n"
                "  Credential generation: %" PRIu32 "\n"
                "  Network transport enabled: %s\n"
                "  mDNS browse enabled: %s\n"
                "  UDP fallback enabled: %s\n"
                "  Secure channel: X25519/HKDF-SHA256/ChaCha20-Poly1305\n"
                "  Credential persistence: RAM ONLY\n"
                "  Formal MQTT profile switch: NO\n"
                "  Production RC2 YAML modified: NO\n"
                "  Secret values included: NO",
                YESNO(!this->hardware_id_.empty()), YESNO(!this->pairing_id_.empty()),
                YESNO(!this->pairing_secret_.empty()), this->core_.state_name(), this->core_.error_name(),
                static_cast<unsigned>(snapshot.candidate_count), YESNO(snapshot.selection_required),
                YESNO(snapshot.candidate_selected), snapshot.credential_generation,
                YESNO(this->network_options_.enabled), YESNO(this->network_options_.mdns_enabled),
                YESNO(this->network_options_.udp_enabled));
}

float GreenhousePairingClient::get_setup_priority() const { return setup_priority::DATA; }

bool GreenhousePairingClient::start_discovery(const std::string &request_id,
                                              const std::string &nonce) {
  if (this->is_failed())
    return false;
  return this->core_.start_discovery(request_id, nonce, millis());
}

bool GreenhousePairingClient::start_random_discovery() {
  std::string request_id;
  std::string nonce;
  return random_discovery_context_(&request_id, &nonce) && this->start_discovery(request_id, nonce);
}

bool GreenhousePairingClient::observe_candidate(const std::string &manager_id,
                                                 const std::string &system_id,
                                                 const std::string &host,
                                                 const std::string &scheme, uint16_t port,
                                                 const std::string &pairing_path,
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
  return PairingTransportCore::validate_pairing_path(pairing_path) &&
         this->core_.observe_candidate(this->core_.request_id(), this->core_.nonce(), candidate,
                                       millis());
}

bool GreenhousePairingClient::discover_network() {
  if (this->is_failed() || !this->network_options_.enabled)
    return false;
  const std::string query = this->build_discovery_request_json();
  if (query.empty())
    return false;
  const PairingNetworkResult result = this->network_.discover(&this->core_, query, millis());
  return result == PairingNetworkResult::SUCCESS ||
         result == PairingNetworkResult::SELECTION_REQUIRED;
}

bool GreenhousePairingClient::complete_network_pairing() {
  if (this->is_failed() || !this->network_options_.enabled ||
      this->core_.snapshot().state != PairingClientState::CLAIM_READY)
    return false;
  std::string claim = this->build_claim_request_json();
  if (claim.empty())
    return false;
  RamCredentialBundle staged;
  const PairingNetworkResult result =
      this->network_.complete_pairing(&this->core_, &this->pairing_secret_, claim, &staged);
  secure_clear(&claim);
  if (result != PairingNetworkResult::SUCCESS) {
    staged.clear();
    return false;
  }
  this->ram_credentials_.clear();
  this->ram_credentials_ = std::move(staged);
  this->clear_pairing_secret_();
  return true;
}

bool GreenhousePairingClient::run_network_pairing_once() {
  if (this->core_.snapshot().state == PairingClientState::UNBOUND &&
      !this->start_random_discovery())
    return false;
  if (this->core_.snapshot().state == PairingClientState::DISCOVERING &&
      !this->discover_network())
    return false;
  if (this->selection_required())
    return false;
  return this->complete_network_pairing();
}

bool GreenhousePairingClient::select_candidate(size_t index) {
  return this->core_.select_candidate(index);
}

bool GreenhousePairingClient::mark_claim_sent() { return this->core_.mark_claim_sent(); }

bool GreenhousePairingClient::accept_secure_offer_for_test(
    const std::string &session_id, const std::string &manager_nonce,
    const std::string &manager_public_key, const std::string &cipher_suite) {
  return this->core_.accept_secure_offer(session_id, manager_nonce, manager_public_key,
                                         cipher_suite);
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

void GreenhousePairingClient::reset_unbound() {
  this->network_.clear();
  this->ram_credentials_.clear();
  this->core_.reset_unbound();
}

std::string GreenhousePairingClient::build_discovery_request_json() const {
  const auto snapshot = this->core_.snapshot();
  if (snapshot.state != PairingClientState::DISCOVERING &&
      snapshot.state != PairingClientState::CLAIM_READY &&
      snapshot.state != PairingClientState::SELECTION_REQUIRED)
    return {};
  return std::string("{\"hardware_id\":\"") + json_escape_(this->core_.hardware_id()) +
         "\",\"nonce\":\"" + json_escape_(this->core_.nonce()) +
         "\",\"protocols\":[\"" + SECURE_PAIRING_PROTOCOL + "\"],\"request_id\":\"" +
         json_escape_(this->core_.request_id()) + "\",\"schema\":\"" +
         DISCOVERY_QUERY_SCHEMA + "\"}";
}

std::string GreenhousePairingClient::build_claim_request_json() const {
  const auto *candidate = this->core_.selected_candidate();
  if (candidate == nullptr || this->core_.snapshot().state != PairingClientState::CLAIM_READY)
    return {};
  std::string proof;
  if (!this->claim_proof_(&proof))
    return {};
  std::string request = std::string("{\"claim_proof\":\"") + json_escape_(proof) +
                        "\",\"hardware_id\":\"" + json_escape_(this->core_.hardware_id()) +
                        "\",\"manager_id\":\"" + json_escape_(candidate->manager_id) +
                        "\",\"pairing_id\":\"" + json_escape_(this->core_.pairing_id()) +
                        "\",\"schema\":\"" + CLAIM_SCHEMA + "\"}";
  secure_clear(&proof);
  return request;
}

std::string GreenhousePairingClient::json_escape_(const std::string &value) {
  return SecurePairingChannel::json_escape(value);
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

bool GreenhousePairingClient::decode_pairing_secret_(const std::string &value,
                                                     uint8_t output[32]) {
  if (output == nullptr)
    return false;
  std::array<uint8_t, 32> decoded{};
  const bool success = SecurePairingChannel::decode_base64url_32(value, &decoded);
  if (success)
    std::copy(decoded.begin(), decoded.end(), output);
  std::fill(decoded.begin(), decoded.end(), 0);
  return success;
}

bool GreenhousePairingClient::encode_base64url_(const uint8_t *data, size_t length,
                                                std::string *output) {
  return SecurePairingChannel::encode_base64url(data, length, output);
}

bool GreenhousePairingClient::random_discovery_context_(std::string *request_id,
                                                        std::string *nonce) {
  if (request_id == nullptr || nonce == nullptr)
    return false;
#ifdef USE_ESP32
  std::array<uint8_t, 16> uuid{};
  std::array<uint8_t, 32> nonce_bytes{};
  esp_fill_random(uuid.data(), uuid.size());
  esp_fill_random(nonce_bytes.data(), nonce_bytes.size());
  uuid[6] = static_cast<uint8_t>((uuid[6] & 0x0FU) | 0x40U);
  uuid[8] = static_cast<uint8_t>((uuid[8] & 0x3FU) | 0x80U);
  char text[37]{};
  const int written = snprintf(
      text, sizeof(text),
      "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      uuid[0], uuid[1], uuid[2], uuid[3], uuid[4], uuid[5], uuid[6], uuid[7], uuid[8],
      uuid[9], uuid[10], uuid[11], uuid[12], uuid[13], uuid[14], uuid[15]);
  const bool success = written == 36 &&
                       encode_base64url_(nonce_bytes.data(), nonce_bytes.size(), nonce);
  if (success)
    *request_id = text;
  std::fill(uuid.begin(), uuid.end(), 0);
  std::fill(nonce_bytes.begin(), nonce_bytes.end(), 0);
  std::fill(std::begin(text), std::end(text), '\0');
  return success;
#else
  return false;
#endif
}

void GreenhousePairingClient::clear_pairing_secret_() { secure_clear(&this->pairing_secret_); }

}  // namespace esphome::greenhouse_pairing_client
