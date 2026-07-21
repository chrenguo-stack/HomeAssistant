#include "secure_pairing_channel.h"

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>

#include "pairing_client_core.h"

#ifdef USE_ESP32
#include "esp_random.h"
#include "mbedtls/base64.h"
#include "mbedtls/chachapoly.h"
#include "mbedtls/md.h"
#include "psa/crypto.h"
#else
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/rand.h>
#endif

namespace esphome::greenhouse_pairing_client {

namespace {

constexpr size_t CHACHA_TAG_SIZE = 16;

bool constant_time_equal(const uint8_t *left, const uint8_t *right, size_t length) {
  if (left == nullptr || right == nullptr)
    return false;
  uint8_t difference = 0;
  for (size_t index = 0; index < length; index++)
    difference |= left[index] ^ right[index];
  return difference == 0;
}

std::vector<uint8_t> concat(const char *prefix, const std::array<uint8_t, 32> &digest) {
  std::vector<uint8_t> output;
  const size_t prefix_length = std::strlen(prefix);
  output.reserve(prefix_length + 1 + digest.size());
  output.insert(output.end(), prefix, prefix + prefix_length);
  output.push_back(0);
  output.insert(output.end(), digest.begin(), digest.end());
  return output;
}

}  // namespace

SecurePairingChannel::~SecurePairingChannel() { this->clear(); }

bool SecurePairingChannel::establish(const SecureOfferDocument &offer,
                                     const std::string &pairing_secret) {
  std::array<uint8_t, 32> private_key{};
  std::array<uint8_t, 32> nonce{};
  if (!random_bytes_(private_key.data(), private_key.size()) ||
      !random_bytes_(nonce.data(), nonce.size())) {
    zeroize_(private_key.data(), private_key.size());
    zeroize_(nonce.data(), nonce.size());
    return false;
  }
  private_key[0] &= 248U;
  private_key[31] &= 127U;
  private_key[31] |= 64U;
  const bool result = this->establish_impl_(offer, pairing_secret, private_key, nonce);
  zeroize_(private_key.data(), private_key.size());
  zeroize_(nonce.data(), nonce.size());
  return result;
}

bool SecurePairingChannel::establish_for_test(
    const SecureOfferDocument &offer, const std::string &pairing_secret,
    const std::array<uint8_t, 32> &node_private_key,
    const std::array<uint8_t, 32> &node_nonce) {
  return this->establish_impl_(offer, pairing_secret, node_private_key, node_nonce);
}

bool SecurePairingChannel::establish_impl_(
    const SecureOfferDocument &offer, const std::string &pairing_secret,
    const std::array<uint8_t, 32> &node_private_key,
    const std::array<uint8_t, 32> &node_nonce) {
  this->clear();
  if (!validate_offer(offer))
    return false;

  std::array<uint8_t, 32> secret{};
  std::array<uint8_t, 32> manager_public_key{};
  std::array<uint8_t, 32> node_public_key{};
  std::array<uint8_t, 32> shared_secret{};
  std::array<uint8_t, 32> proof_digest{};
  std::array<uint8_t, 32> transcript_digest{};
  std::array<uint8_t, 32> salt{};
  std::array<uint8_t, 64> material{};

  bool success = decode_base64url_32(pairing_secret, &secret) &&
                 decode_base64url_32(offer.manager_public_key, &manager_public_key) &&
                 x25519_(node_private_key, manager_public_key, &node_public_key, &shared_secret);
  if (!success)
    goto cleanup;

  success = encode_base64url(node_nonce.data(), node_nonce.size(), &this->node_nonce_) &&
            encode_base64url(node_public_key.data(), node_public_key.size(),
                             &this->node_public_key_);
  if (!success)
    goto cleanup;

  {
    const std::string transcript =
        secure_proof_transcript(offer, this->node_nonce_, this->node_public_key_);
    if (transcript.empty()) {
      success = false;
      goto cleanup;
    }
    success = hmac_sha256_(secret.data(), secret.size(),
                           reinterpret_cast<const uint8_t *>(transcript.data()), transcript.size(),
                           &proof_digest) &&
              encode_base64url(proof_digest.data(), proof_digest.size(), &this->secure_proof_) &&
              sha256_(reinterpret_cast<const uint8_t *>(transcript.data()), transcript.size(),
                      &transcript_digest);
    if (!success)
      goto cleanup;

    const auto salt_input = concat("gh.pair.secure-salt/1", transcript_digest);
    success = hmac_sha256_(secret.data(), secret.size(), salt_input.data(), salt_input.size(),
                           &salt);
    if (!success)
      goto cleanup;

    const auto info = concat("gh.pair.secure-keys/1", transcript_digest);
    success = hkdf_sha256_64_(shared_secret, salt, info, &material);
    if (!success)
      goto cleanup;
  }

  std::copy_n(material.begin(), 32, this->manager_to_node_key_.begin());
  std::copy_n(material.begin() + 32, 32, this->node_to_manager_key_.begin());
  this->session_id_ = offer.session_id;
  this->send_sequence_ = 0;
  this->receive_sequence_ = 0;
  this->established_ = true;

cleanup:
  zeroize_(secret.data(), secret.size());
  zeroize_(manager_public_key.data(), manager_public_key.size());
  zeroize_(node_public_key.data(), node_public_key.size());
  zeroize_(shared_secret.data(), shared_secret.size());
  zeroize_(proof_digest.data(), proof_digest.size());
  zeroize_(transcript_digest.data(), transcript_digest.size());
  zeroize_(salt.data(), salt.size());
  zeroize_(material.data(), material.size());
  if (!success)
    this->clear();
  return success;
}

bool SecurePairingChannel::decrypt(const SecureEnvelopeDocument &envelope,
                                   const std::string &expected_content_type,
                                   std::string *plaintext) {
  if (!this->established_ || plaintext == nullptr ||
      !validate_envelope_shape(envelope) || envelope.session_id != this->session_id_ ||
      envelope.direction != MANAGER_TO_NODE_DIRECTION ||
      envelope.content_type != expected_content_type ||
      envelope.sequence != this->receive_sequence_)
    return false;

  bool nonce_valid = false;
  const auto expected_nonce = envelope_nonce(envelope.direction, envelope.sequence, &nonce_valid);
  std::vector<uint8_t> supplied_nonce;
  std::vector<uint8_t> ciphertext;
  if (!nonce_valid || !decode_base64url(envelope.nonce, &supplied_nonce) ||
      supplied_nonce.size() != expected_nonce.size() ||
      !constant_time_equal(supplied_nonce.data(), expected_nonce.data(), expected_nonce.size()) ||
      !decode_base64url(envelope.ciphertext, &ciphertext))
    return false;

  const std::string aad = envelope_aad(envelope.session_id, envelope.direction,
                                       envelope.sequence, envelope.content_type);
  if (!aead_decrypt_(this->manager_to_node_key_, expected_nonce, aad, ciphertext, plaintext))
    return false;
  this->receive_sequence_++;
  return true;
}

bool SecurePairingChannel::encrypt(const std::string &plaintext,
                                   const std::string &content_type,
                                   SecureEnvelopeDocument *envelope) {
  if (!this->established_ || envelope == nullptr || content_type.empty() ||
      this->send_sequence_ == std::numeric_limits<uint64_t>::max())
    return false;
  bool nonce_valid = false;
  const auto nonce = envelope_nonce(NODE_TO_MANAGER_DIRECTION, this->send_sequence_, &nonce_valid);
  if (!nonce_valid)
    return false;
  const std::string aad = envelope_aad(this->session_id_, NODE_TO_MANAGER_DIRECTION,
                                       this->send_sequence_, content_type);
  std::vector<uint8_t> ciphertext;
  if (!aead_encrypt_(this->node_to_manager_key_, nonce, aad, plaintext, &ciphertext))
    return false;

  SecureEnvelopeDocument candidate{
      .schema = ENVELOPE_SCHEMA,
      .session_id = this->session_id_,
      .direction = NODE_TO_MANAGER_DIRECTION,
      .sequence = this->send_sequence_,
      .content_type = content_type,
      .nonce = {},
      .ciphertext = {},
  };
  if (!encode_base64url(nonce.data(), nonce.size(), &candidate.nonce) ||
      !encode_base64url(ciphertext.data(), ciphertext.size(), &candidate.ciphertext))
    return false;
  *envelope = std::move(candidate);
  this->send_sequence_++;
  return true;
}

std::string SecurePairingChannel::build_establish_request_json() const {
  if (!this->established_ || this->node_nonce_.empty() || this->node_public_key_.empty() ||
      this->secure_proof_.empty())
    return {};
  return std::string("{\"node_nonce\":\"") + json_escape(this->node_nonce_) +
         "\",\"node_public_key\":\"" + json_escape(this->node_public_key_) +
         "\",\"proof\":\"" + json_escape(this->secure_proof_) +
         "\",\"schema\":\"" + ESTABLISH_SCHEMA + "\"}";
}

SecurePairingMaterialSnapshot SecurePairingChannel::snapshot() const {
  return SecurePairingMaterialSnapshot{
      .established = this->established_,
      .send_sequence = this->send_sequence_,
      .receive_sequence = this->receive_sequence_,
      .node_nonce = this->node_nonce_,
      .node_public_key = this->node_public_key_,
      .secure_proof = this->secure_proof_,
  };
}

void SecurePairingChannel::clear() {
  zeroize_(this->manager_to_node_key_.data(), this->manager_to_node_key_.size());
  zeroize_(this->node_to_manager_key_.data(), this->node_to_manager_key_.size());
  std::fill(this->node_nonce_.begin(), this->node_nonce_.end(), '\0');
  std::fill(this->node_public_key_.begin(), this->node_public_key_.end(), '\0');
  std::fill(this->secure_proof_.begin(), this->secure_proof_.end(), '\0');
  this->node_nonce_.clear();
  this->node_public_key_.clear();
  this->secure_proof_.clear();
  this->session_id_.clear();
  this->send_sequence_ = 0;
  this->receive_sequence_ = 0;
  this->established_ = false;
}

bool SecurePairingChannel::validate_offer(const SecureOfferDocument &offer) {
  return offer.schema == SECURE_OFFER_SCHEMA &&
         PairingClientCore::valid_request_id(offer.session_id) &&
         PairingClientCore::valid_identifier(offer.hardware_id) &&
         PairingClientCore::valid_request_id(offer.pairing_id) &&
         PairingClientCore::valid_base64url_32(offer.manager_nonce) &&
         PairingClientCore::valid_base64url_32(offer.manager_public_key) &&
         offer.cipher_suite == SECURE_CIPHER_SUITE && !offer.expires_at.empty() &&
         offer.max_proof_attempts >= 1 && offer.max_proof_attempts <= 16;
}

bool SecurePairingChannel::validate_envelope_shape(const SecureEnvelopeDocument &envelope) {
  return envelope.schema == ENVELOPE_SCHEMA &&
         PairingClientCore::valid_request_id(envelope.session_id) &&
         (envelope.direction == MANAGER_TO_NODE_DIRECTION ||
          envelope.direction == NODE_TO_MANAGER_DIRECTION) &&
         !envelope.content_type.empty() && !envelope.nonce.empty() &&
         !envelope.ciphertext.empty();
}

std::string SecurePairingChannel::secure_proof_transcript(
    const SecureOfferDocument &offer, const std::string &node_nonce,
    const std::string &node_public_key) {
  if (!validate_offer(offer) || !PairingClientCore::valid_base64url_32(node_nonce) ||
      !PairingClientCore::valid_base64url_32(node_public_key))
    return {};
  return std::string("gh.pair.secure-proof/1\n") + offer.session_id + "\n" +
         offer.hardware_id + "\n" + offer.pairing_id + "\n" + node_nonce + "\n" +
         offer.manager_nonce + "\n" + offer.manager_public_key + "\n" + node_public_key +
         "\n" + offer.cipher_suite;
}

std::string SecurePairingChannel::envelope_aad(const std::string &session_id,
                                               const std::string &direction,
                                               uint64_t sequence,
                                               const std::string &content_type) {
  return std::string("{\"content_type\":\"") + json_escape(content_type) +
         "\",\"direction\":\"" + json_escape(direction) +
         "\",\"schema\":\"gh.pair.envelope/1\",\"sequence\":" +
         std::to_string(sequence) + ",\"session_id\":\"" + json_escape(session_id) +
         "\"}";
}

std::array<uint8_t, 12> SecurePairingChannel::envelope_nonce(const std::string &direction,
                                                              uint64_t sequence,
                                                              bool *valid) {
  std::array<uint8_t, 12> nonce{};
  uint32_t prefix = 0;
  if (direction == MANAGER_TO_NODE_DIRECTION)
    prefix = 1;
  else if (direction == NODE_TO_MANAGER_DIRECTION)
    prefix = 2;
  else {
    if (valid != nullptr)
      *valid = false;
    return nonce;
  }
  nonce[0] = static_cast<uint8_t>(prefix >> 24U);
  nonce[1] = static_cast<uint8_t>(prefix >> 16U);
  nonce[2] = static_cast<uint8_t>(prefix >> 8U);
  nonce[3] = static_cast<uint8_t>(prefix);
  for (size_t index = 0; index < 8; index++)
    nonce[4 + index] = static_cast<uint8_t>(sequence >> (56U - 8U * index));
  if (valid != nullptr)
    *valid = true;
  return nonce;
}

}  // namespace esphome::greenhouse_pairing_client
