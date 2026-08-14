#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "esphome/components/greenhouse_n3w_core/n3w_radio.h"
#include "n3w_product_peer_security.h"

namespace esphome::greenhouse_n3w_product_runtime {

constexpr uint8_t kProductPeerHandshakeWireVersion = 1;
constexpr std::size_t kProductPeerHandshakeMaxNodeIdBytes = 64;

enum class ProductPeerHandshakeType : uint8_t {
  CHILD_AUTH_INIT = 2,
  RELAY_CHALLENGE = 3,
  CHILD_PROOF = 4,
  CHILD_GRANT = 5,
};

struct ProductChildAuthInit {
  uint64_t session_token{0};
  std::string child_node_id;
  std::string target_relay_node_id;
  uint32_t child_credential_generation{0};
  uint32_t child_key_epoch{0};
  ProductPeerKey child_ephemeral_public_key{};
  ProductPeerNonce child_nonce{};

  bool valid() const;
};

struct ProductRelayChallenge {
  uint64_t session_token{0};
  greenhouse_n3w_core::MacAddress target_child_mac{};
  std::string relay_node_id;
  uint32_t relay_credential_generation{0};
  uint32_t relay_key_epoch{0};
  ProductPeerKey relay_ephemeral_public_key{};
  ProductPeerNonce relay_nonce{};
  uint64_t requested_at_ms{0};
  ProductRelayHealth relay_health{};

  bool valid() const;
};

struct ProductChildProofPacket {
  uint64_t session_token{0};
  greenhouse_n3w_core::MacAddress target_relay_mac{};
  ProductPeerProof child_proof{};

  bool valid() const;
};

struct ProductChildGrantPacket {
  uint64_t session_token{0};
  greenhouse_n3w_core::MacAddress target_child_mac{};
  std::array<uint8_t, 16> authorization_uuid{};
  uint64_t issued_at_ms{0};
  uint64_t expires_at_ms{0};
  uint32_t authorization_epoch{0};
  ProductPeerProof child_grant_mac{};

  bool valid() const;
  std::string authorization_id() const;
};

bool encode_child_auth_init(
    const ProductChildAuthInit &packet,
    std::vector<uint8_t> *encoded);
bool decode_child_auth_init(
    const uint8_t *data,
    std::size_t size,
    ProductChildAuthInit *packet);

bool encode_relay_challenge(
    const ProductRelayChallenge &packet,
    std::vector<uint8_t> *encoded);
bool decode_relay_challenge(
    const uint8_t *data,
    std::size_t size,
    ProductRelayChallenge *packet);

bool encode_child_proof_packet(
    const ProductChildProofPacket &packet,
    std::vector<uint8_t> *encoded);
bool decode_child_proof_packet(
    const uint8_t *data,
    std::size_t size,
    ProductChildProofPacket *packet);

bool encode_child_grant_packet(
    const ProductChildGrantPacket &packet,
    std::vector<uint8_t> *encoded);
bool decode_child_grant_packet(
    const uint8_t *data,
    std::size_t size,
    ProductChildGrantPacket *packet);

bool parse_authorization_uuid(
    const std::string &authorization_id,
    std::array<uint8_t, 16> *uuid_bytes);
std::string product_session_id(uint64_t session_token);

}  // namespace esphome::greenhouse_n3w_product_runtime
