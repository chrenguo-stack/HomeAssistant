#include "secure_pairing_channel.h"
#include "stage2c2_vectors_generated.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>

using namespace esphome::greenhouse_pairing_client;

namespace {

uint8_t hex_value(char value) {
  if (value >= '0' && value <= '9')
    return static_cast<uint8_t>(value - '0');
  if (value >= 'a' && value <= 'f')
    return static_cast<uint8_t>(value - 'a' + 10);
  if (value >= 'A' && value <= 'F')
    return static_cast<uint8_t>(value - 'A' + 10);
  assert(false);
  return 0;
}

std::array<uint8_t, 32> bytes32(const char *hex) {
  std::string value(hex);
  assert(value.size() == 64);
  std::array<uint8_t, 32> output{};
  for (size_t index = 0; index < output.size(); index++)
    output[index] = static_cast<uint8_t>((hex_value(value[index * 2]) << 4U) |
                                         hex_value(value[index * 2 + 1]));
  return output;
}

std::array<uint8_t, 32> b64_32(const char *text) {
  std::array<uint8_t, 32> output{};
  assert(SecurePairingChannel::decode_base64url_32(text, &output));
  return output;
}

SecureOfferDocument offer() {
  return SecureOfferDocument{
      .schema = SECURE_OFFER_SCHEMA,
      .session_id = stage2c2_vectors::session_id,
      .hardware_id = stage2c2_vectors::hardware_id,
      .pairing_id = stage2c2_vectors::pairing_id,
      .manager_nonce = stage2c2_vectors::manager_nonce,
      .manager_public_key = stage2c2_vectors::manager_public_key,
      .cipher_suite = stage2c2_vectors::cipher_suite,
      .expires_at = "2026-07-21T01:00:00Z",
      .max_proof_attempts = 3,
  };
}

SecureEnvelopeDocument credentials_envelope() {
  return SecureEnvelopeDocument{
      .schema = ENVELOPE_SCHEMA,
      .session_id = stage2c2_vectors::session_id,
      .direction = MANAGER_TO_NODE_DIRECTION,
      .sequence = 0,
      .content_type = CREDENTIALS_CONTENT_TYPE,
      .nonce = stage2c2_vectors::credentials_nonce,
      .ciphertext = stage2c2_vectors::credentials_ciphertext,
  };
}

}  // namespace

int main() {
  SecurePairingChannel channel;
  assert(channel.establish_for_test(offer(), stage2c2_vectors::pairing_secret,
                                    bytes32(stage2c2_vectors::node_private_key_hex),
                                    b64_32(stage2c2_vectors::node_nonce)));
  assert(channel.node_public_key() == stage2c2_vectors::node_public_key);
  assert(channel.node_nonce() == stage2c2_vectors::node_nonce);
  assert(channel.secure_proof() == stage2c2_vectors::secure_proof);
  assert(channel.build_establish_request_json().find(stage2c2_vectors::secure_proof) !=
         std::string::npos);

  auto wrong_direction = credentials_envelope();
  wrong_direction.direction = NODE_TO_MANAGER_DIRECTION;
  std::string plaintext;
  assert(!channel.decrypt(wrong_direction, CREDENTIALS_CONTENT_TYPE, &plaintext));
  assert(channel.snapshot().receive_sequence == 0);

  auto tampered = credentials_envelope();
  tampered.ciphertext.back() = tampered.ciphertext.back() == 'A' ? 'B' : 'A';
  assert(!channel.decrypt(tampered, CREDENTIALS_CONTENT_TYPE, &plaintext));
  assert(channel.snapshot().receive_sequence == 0);

  auto credentials = credentials_envelope();
  assert(channel.decrypt(credentials, CREDENTIALS_CONTENT_TYPE, &plaintext));
  assert(plaintext == stage2c2_vectors::credentials_plaintext);
  assert(channel.snapshot().receive_sequence == 1);
  assert(!channel.decrypt(credentials, CREDENTIALS_CONTENT_TYPE, &plaintext));
  assert(channel.snapshot().receive_sequence == 1);

  SecureEnvelopeDocument ack;
  assert(channel.encrypt(stage2c2_vectors::ack_plaintext, ACK_CONTENT_TYPE, &ack));
  assert(ack.schema == ENVELOPE_SCHEMA);
  assert(ack.session_id == stage2c2_vectors::session_id);
  assert(ack.direction == NODE_TO_MANAGER_DIRECTION);
  assert(ack.sequence == 0);
  assert(ack.nonce == stage2c2_vectors::ack_nonce);
  assert(ack.ciphertext == stage2c2_vectors::ack_ciphertext);
  assert(channel.snapshot().send_sequence == 1);

  channel.clear();
  assert(!channel.snapshot().established);
  assert(channel.node_public_key().empty());
  assert(channel.secure_proof().empty());
  std::cout << "stage2c2 secure channel vectors passed\n";
  return 0;
}
