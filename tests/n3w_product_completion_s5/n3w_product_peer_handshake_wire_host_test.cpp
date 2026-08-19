#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

#include "esphome/components/greenhouse_n3w_product_runtime/n3w_product_peer_handshake_wire.h"

using esphome::greenhouse_n3w_core::MacAddress;
using namespace esphome::greenhouse_n3w_product_runtime;

namespace {

template <std::size_t N>
std::array<uint8_t, N> fill(uint8_t start) {
  std::array<uint8_t, N> output{};
  for (std::size_t index = 0; index < N; ++index)
    output[index] = static_cast<uint8_t>(start + index);
  return output;
}

}  // namespace

int main() {
  const MacAddress child_mac{0x02, 0x11, 0x22, 0x33, 0x44, 0x55};
  const MacAddress relay_mac{0x02, 0xaa, 0xbb, 0xcc, 0xdd, 0xee};

  ProductChildAuthInit init;
  init.session_token = 0x0123456789abcdefULL;
  init.child_node_id = "node_child01";
  init.target_relay_node_id = "node_relay01";
  init.child_credential_generation = 7;
  init.child_key_epoch = 9;
  init.child_ephemeral_public_key = fill<32>(1);
  init.child_nonce = fill<32>(41);
  assert(init.valid());
  std::vector<uint8_t> encoded;
  assert(encode_child_auth_init(init, &encoded));
  assert(encoded.size() <= 240);
  ProductChildAuthInit init_roundtrip;
  assert(decode_child_auth_init(encoded.data(), encoded.size(), &init_roundtrip));
  assert(init_roundtrip.session_token == init.session_token);
  assert(init_roundtrip.child_node_id == init.child_node_id);
  assert(init_roundtrip.target_relay_node_id == init.target_relay_node_id);
  assert(init_roundtrip.child_ephemeral_public_key == init.child_ephemeral_public_key);
  assert(product_session_id(init.session_token) == "s5-0123456789abcdef");
  assert(!decode_child_auth_init(encoded.data(), encoded.size() - 1, &init_roundtrip));

  ProductRelayChallenge challenge;
  challenge.session_token = init.session_token;
  challenge.target_child_mac = child_mac;
  challenge.relay_node_id = "node_relay01";
  challenge.relay_credential_generation = 11;
  challenge.relay_key_epoch = 13;
  challenge.relay_ephemeral_public_key = fill<32>(81);
  challenge.relay_nonce = fill<32>(121);
  challenge.requested_at_ms = 1786689000000ULL;
  challenge.relay_health.observed_at_ms = 1786688999000ULL;
  challenge.relay_health.relay_capable = true;
  challenge.relay_health.low_battery = false;
  challenge.relay_health.overloaded = false;
  assert(challenge.valid());
  assert(encode_relay_challenge(challenge, &encoded));
  assert(encoded.size() <= 240);
  ProductRelayChallenge challenge_roundtrip;
  assert(decode_relay_challenge(encoded.data(), encoded.size(), &challenge_roundtrip));
  assert(challenge_roundtrip.target_child_mac == child_mac);
  assert(challenge_roundtrip.relay_node_id == challenge.relay_node_id);
  assert(challenge_roundtrip.relay_health.relay_capable);

  ProductChildProofPacket proof;
  proof.session_token = init.session_token;
  proof.target_relay_mac = relay_mac;
  proof.child_proof = fill<32>(161);
  assert(proof.valid());
  assert(encode_child_proof_packet(proof, &encoded));
  assert(encoded.size() == 50);
  ProductChildProofPacket proof_roundtrip;
  assert(decode_child_proof_packet(encoded.data(), encoded.size(), &proof_roundtrip));
  assert(proof_roundtrip.target_relay_mac == relay_mac);
  assert(proof_roundtrip.child_proof == proof.child_proof);

  ProductChildGrantPacket grant;
  grant.session_token = init.session_token;
  grant.target_child_mac = child_mac;
  assert(parse_authorization_uuid(
      "11111111-2222-3333-4444-555555555555", &grant.authorization_uuid));
  grant.issued_at_ms = 1786689000100ULL;
  grant.expires_at_ms = 1786689030000ULL;
  grant.authorization_epoch = 17;
  grant.child_grant_mac = fill<32>(193);
  assert(grant.valid());
  assert(grant.authorization_id() == "11111111-2222-3333-4444-555555555555");
  assert(encode_child_grant_packet(grant, &encoded));
  assert(encoded.size() == 86);
  ProductChildGrantPacket grant_roundtrip;
  assert(decode_child_grant_packet(encoded.data(), encoded.size(), &grant_roundtrip));
  assert(grant_roundtrip.authorization_id() == grant.authorization_id());
  assert(grant_roundtrip.child_grant_mac == grant.child_grant_mac);

  std::array<uint8_t, 16> bad_uuid{};
  assert(!parse_authorization_uuid("not-a-uuid", &bad_uuid));

  ProductChildAuthInit maximum = init;
  maximum.child_node_id = std::string(64, 'a');
  maximum.target_relay_node_id = std::string(64, 'b');
  assert(encode_child_auth_init(maximum, &encoded));
  assert(encoded.size() == 214);
  assert(encoded.size() <= 240);

  std::cout << "S5_PRODUCT_PEER_HANDSHAKE_WIRE=PASS\n";
  return 0;
}
