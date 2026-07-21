#include "pairing_network_transport.h"

#include <algorithm>
#include <utility>

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

PairingNetworkTransport::~PairingNetworkTransport() { this->clear(); }

PairingNetworkResult PairingNetworkTransport::discover(PairingClientCore *core,
                                                        const std::string &query_json,
                                                        uint32_t now_ms) {
  if (!this->options_.enabled)
    return this->set_result_(PairingNetworkResult::DISABLED);
  if (core == nullptr || !PairingTransportCore::validate_limits(this->options_.limits) ||
      (!this->options_.mdns_enabled && !this->options_.udp_enabled) ||
      (this->options_.udp_enabled &&
       !PairingTransportCore::validate_udp_target(this->options_.udp_target)) ||
      !PairingTransportCore::validate_udp_datagram_size(query_json.size()))
    return this->set_result_(PairingNetworkResult::INVALID_CONFIGURATION);
#ifdef USE_ESP32
  bool observed = false;
  if (this->options_.mdns_enabled)
    observed = this->browse_mdns_(core, now_ms);
  if (!observed && this->options_.udp_enabled)
    observed = this->discover_udp_(core, query_json, now_ms);
  if (!observed)
    return this->set_result_(PairingNetworkResult::DISCOVERY_FAILED);
  if (core->snapshot().selection_required)
    return this->set_result_(PairingNetworkResult::SELECTION_REQUIRED);
  return this->set_result_(PairingNetworkResult::SUCCESS);
#else
  (void) query_json;
  (void) now_ms;
  return this->set_result_(PairingNetworkResult::DISCOVERY_FAILED);
#endif
}

PairingNetworkResult PairingNetworkTransport::complete_pairing(
    PairingClientCore *core, std::string *pairing_secret, const std::string &claim_json,
    RamCredentialBundle *credentials) {
  this->channel_.clear();
  if (credentials != nullptr)
    credentials->clear();
  if (!this->options_.enabled)
    return this->set_result_(PairingNetworkResult::DISABLED);
  if (core == nullptr || pairing_secret == nullptr || pairing_secret->empty() ||
      credentials == nullptr || claim_json.empty() ||
      !PairingTransportCore::validate_limits(this->options_.limits))
    return this->set_result_(PairingNetworkResult::INVALID_CONFIGURATION);
  const ManagerCandidate *candidate = core->selected_candidate();
  if (candidate == nullptr)
    return this->set_result_(core->snapshot().selection_required
                                 ? PairingNetworkResult::SELECTION_REQUIRED
                                 : PairingNetworkResult::DISCOVERY_FAILED);
  // Bootstrap is intentionally restricted to the Stage 2B-2 local HTTP profile.
  // HTTPS will be enabled only when a trusted bootstrap CA is available.
  if (candidate->scheme != "http")
    return this->set_result_(PairingNetworkResult::UNSUPPORTED_SCHEME);

#ifdef USE_ESP32
  const std::string base_url = PairingTransportCore::build_base_url(
      candidate->scheme, candidate->host, candidate->port, candidate->pairing_path);
  if (base_url.empty())
    return this->set_result_(PairingNetworkResult::INVALID_CONFIGURATION);

  HttpResponse response;
  if (!this->post_json_(base_url + "/claim", claim_json, &response)) {
    core->fail(PairingClientError::TRANSPORT_FAILED, true);
    return this->set_result_(PairingNetworkResult::CLAIM_FAILED);
  }
  SecureOfferDocument offer;
  if (!this->parse_offer_(response.body, &offer) || offer.hardware_id != core->hardware_id() ||
      offer.pairing_id != core->pairing_id() || !core->mark_claim_sent() ||
      !core->accept_secure_offer(offer.session_id, offer.manager_nonce, offer.manager_public_key,
                                 offer.cipher_suite)) {
    core->fail(PairingClientError::SECURE_OFFER_REJECTED, false);
    return this->set_result_(PairingNetworkResult::SECURE_OFFER_REJECTED);
  }

  if (!this->channel_.establish(offer, *pairing_secret)) {
    core->fail(PairingClientError::SECURE_OFFER_REJECTED, false);
    return this->set_result_(PairingNetworkResult::CHANNEL_FAILED);
  }
  const std::string establish_url =
      PairingTransportCore::build_session_url(base_url, offer.session_id, "establish");
  std::string establish_request = this->channel_.build_establish_request_json();
  const bool establish_posted = !establish_url.empty() && !establish_request.empty() &&
                                this->post_json_(establish_url, establish_request, &response);
  secure_clear(&establish_request);
  if (!establish_posted ||
      !this->parse_secure_status_(response.body, offer.session_id, "channel_established") ||
      !core->mark_channel_established()) {
    this->channel_.clear();
    core->fail(PairingClientError::TRANSPORT_FAILED, false);
    return this->set_result_(PairingNetworkResult::CHANNEL_FAILED);
  }
  // Retain the QR bootstrap secret until the Manager confirms channel
  // establishment. A lost establish response must not destroy the only local
  // recovery material before the caller can reset or abort the session.
  secure_clear(pairing_secret);

  const std::string credentials_url =
      PairingTransportCore::build_session_url(base_url, offer.session_id, "credentials");
  if (credentials_url.empty() ||
      !this->post_json_(credentials_url,
                        "{\"schema\":\"gh.pair.credentials-request/1\"}", &response)) {
    this->channel_.clear();
    core->fail(PairingClientError::TRANSPORT_FAILED, false);
    return this->set_result_(PairingNetworkResult::CREDENTIALS_FAILED);
  }
  SecureEnvelopeDocument encrypted_credentials;
  std::string plaintext;
  RamCredentialBundle staged;
  if (!this->parse_envelope_(response.body, &encrypted_credentials) ||
      !this->channel_.decrypt(encrypted_credentials, CREDENTIALS_CONTENT_TYPE, &plaintext) ||
      !this->parse_credentials_(plaintext, &staged) || !staged.valid() ||
      !core->stage_credentials(staged.node_id, staged.credential_generation)) {
    secure_clear(&plaintext);
    staged.clear();
    this->channel_.clear();
    core->fail(PairingClientError::CREDENTIALS_REJECTED, false);
    return this->set_result_(PairingNetworkResult::CREDENTIALS_FAILED);
  }
  secure_clear(&plaintext);

  SecureEnvelopeDocument ack;
  std::string ack_plaintext = staged.delivery_ack_json();
  const std::string ack_url =
      PairingTransportCore::build_session_url(base_url, offer.session_id, "ack");
  const bool ack_encrypted = !ack_url.empty() && !ack_plaintext.empty() &&
                             this->channel_.encrypt(ack_plaintext, ACK_CONTENT_TYPE, &ack);
  secure_clear(&ack_plaintext);
  std::string ack_document = ack_encrypted ? envelope_json(ack) : std::string{};
  const bool ack_posted = ack_encrypted && !ack_document.empty() &&
                          this->post_json_(ack_url, ack_document, &response);
  secure_clear(&ack_document);
  if (!ack_posted ||
      !this->parse_secure_status_(response.body, offer.session_id, "consumed",
                                  staged.credential_generation) ||
      !core->commit_credentials()) {
    staged.clear();
    this->channel_.clear();
    core->fail(PairingClientError::TRANSPORT_FAILED, false);
    return this->set_result_(PairingNetworkResult::ACK_FAILED);
  }

  *credentials = std::move(staged);
  this->channel_.clear();
  return this->set_result_(PairingNetworkResult::SUCCESS);
#else
  (void) pairing_secret;
  (void) claim_json;
  return this->set_result_(PairingNetworkResult::CHANNEL_FAILED);
#endif
}

void PairingNetworkTransport::clear() { this->channel_.clear(); }

const char *PairingNetworkTransport::last_result_name() const {
  switch (this->last_result_) {
    case PairingNetworkResult::SUCCESS:
      return "success";
    case PairingNetworkResult::DISABLED:
      return "disabled";
    case PairingNetworkResult::INVALID_CONFIGURATION:
      return "invalid_configuration";
    case PairingNetworkResult::DISCOVERY_FAILED:
      return "discovery_failed";
    case PairingNetworkResult::SELECTION_REQUIRED:
      return "selection_required";
    case PairingNetworkResult::CLAIM_FAILED:
      return "claim_failed";
    case PairingNetworkResult::SECURE_OFFER_REJECTED:
      return "secure_offer_rejected";
    case PairingNetworkResult::CHANNEL_FAILED:
      return "channel_failed";
    case PairingNetworkResult::CREDENTIALS_FAILED:
      return "credentials_failed";
    case PairingNetworkResult::ACK_FAILED:
      return "ack_failed";
    case PairingNetworkResult::UNSUPPORTED_SCHEME:
      return "unsupported_scheme";
  }
  return "unknown";
}

std::string PairingNetworkTransport::envelope_json(const SecureEnvelopeDocument &envelope) {
  if (!SecurePairingChannel::validate_envelope_shape(envelope))
    return {};
  return std::string("{\"ciphertext\":\"") +
         SecurePairingChannel::json_escape(envelope.ciphertext) +
         "\",\"content_type\":\"" + SecurePairingChannel::json_escape(envelope.content_type) +
         "\",\"direction\":\"" + SecurePairingChannel::json_escape(envelope.direction) +
         "\",\"nonce\":\"" + SecurePairingChannel::json_escape(envelope.nonce) +
         "\",\"schema\":\"gh.pair.envelope/1\",\"sequence\":" +
         std::to_string(envelope.sequence) + ",\"session_id\":\"" +
         SecurePairingChannel::json_escape(envelope.session_id) + "\"}";
}

PairingNetworkResult PairingNetworkTransport::set_result_(PairingNetworkResult result) {
  this->last_result_ = result;
  return result;
}

}  // namespace esphome::greenhouse_pairing_client
