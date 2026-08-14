#include "n3w_product_peer_handshake_wire.h"

#include <algorithm>
#include <array>
#include <cstdio>

namespace esphome::greenhouse_n3w_product_runtime {
namespace {

constexpr uint8_t kMagic0 = 'G';
constexpr uint8_t kMagic1 = 'P';
constexpr std::size_t kHeaderBytes = 4;

void put_u32(std::vector<uint8_t> *output, uint32_t value) {
  output->push_back(static_cast<uint8_t>((value >> 24U) & 0xffU));
  output->push_back(static_cast<uint8_t>((value >> 16U) & 0xffU));
  output->push_back(static_cast<uint8_t>((value >> 8U) & 0xffU));
  output->push_back(static_cast<uint8_t>(value & 0xffU));
}

void put_u64(std::vector<uint8_t> *output, uint64_t value) {
  for (int shift = 56; shift >= 0; shift -= 8)
    output->push_back(static_cast<uint8_t>((value >> shift) & 0xffU));
}

bool take_u32(
    const uint8_t *data,
    std::size_t size,
    std::size_t *offset,
    uint32_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr ||
      *offset > size || size - *offset < 4) {
    return false;
  }
  *value = (static_cast<uint32_t>(data[*offset]) << 24U) |
           (static_cast<uint32_t>(data[*offset + 1]) << 16U) |
           (static_cast<uint32_t>(data[*offset + 2]) << 8U) |
           static_cast<uint32_t>(data[*offset + 3]);
  *offset += 4;
  return true;
}

bool take_u64(
    const uint8_t *data,
    std::size_t size,
    std::size_t *offset,
    uint64_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr ||
      *offset > size || size - *offset < 8) {
    return false;
  }
  uint64_t parsed = 0;
  for (int index = 0; index < 8; ++index)
    parsed = (parsed << 8U) | data[*offset + static_cast<std::size_t>(index)];
  *value = parsed;
  *offset += 8;
  return true;
}

template <std::size_t N>
void put_array(std::vector<uint8_t> *output, const std::array<uint8_t, N> &value) {
  output->insert(output->end(), value.begin(), value.end());
}

template <std::size_t N>
bool take_array(
    const uint8_t *data,
    std::size_t size,
    std::size_t *offset,
    std::array<uint8_t, N> *value) {
  if (data == nullptr || offset == nullptr || value == nullptr ||
      *offset > size || size - *offset < N) {
    return false;
  }
  std::copy_n(data + *offset, N, value->begin());
  *offset += N;
  return true;
}

bool put_id(std::vector<uint8_t> *output, const std::string &value) {
  if (output == nullptr || value.empty() || value.size() > kProductPeerHandshakeMaxNodeIdBytes)
    return false;
  output->push_back(static_cast<uint8_t>(value.size()));
  output->insert(output->end(), value.begin(), value.end());
  return true;
}

bool take_id(
    const uint8_t *data,
    std::size_t size,
    std::size_t *offset,
    std::string *value) {
  if (data == nullptr || offset == nullptr || value == nullptr || *offset >= size)
    return false;
  const std::size_t length = data[(*offset)++];
  if (length == 0 || length > kProductPeerHandshakeMaxNodeIdBytes ||
      *offset > size || size - *offset < length) {
    return false;
  }
  value->assign(reinterpret_cast<const char *>(data + *offset), length);
  *offset += length;
  return ProductPeerSecurity::valid_identifier_(*value);
}

bool valid_unicast_mac(const greenhouse_n3w_core::MacAddress &mac) {
  uint8_t aggregate = 0;
  for (uint8_t value : mac)
    aggregate |= value;
  return aggregate != 0 && (mac[0] & 0x01U) == 0;
}

bool valid_header(
    const uint8_t *data,
    std::size_t size,
    ProductPeerHandshakeType type) {
  return data != nullptr && size >= kHeaderBytes &&
         size <= greenhouse_n3w_core::kEspNowDatagramLimit && data[0] == kMagic0 &&
         data[1] == kMagic1 && data[2] == kProductPeerHandshakeWireVersion &&
         data[3] == static_cast<uint8_t>(type);
}

void begin_packet(ProductPeerHandshakeType type, std::vector<uint8_t> *output) {
  output->clear();
  output->push_back(kMagic0);
  output->push_back(kMagic1);
  output->push_back(kProductPeerHandshakeWireVersion);
  output->push_back(static_cast<uint8_t>(type));
}

bool finish_packet(const std::vector<uint8_t> &output) {
  return !output.empty() && output.size() <= greenhouse_n3w_core::kEspNowDatagramLimit;
}

int hex_nibble(char value) {
  if (value >= '0' && value <= '9') return value - '0';
  if (value >= 'a' && value <= 'f') return 10 + value - 'a';
  if (value >= 'A' && value <= 'F') return 10 + value - 'A';
  return -1;
}

}  // namespace

bool ProductChildAuthInit::valid() const {
  return session_token != 0 && ProductPeerSecurity::valid_identifier_(child_node_id) &&
         child_node_id.size() <= kProductPeerHandshakeMaxNodeIdBytes &&
         ProductPeerSecurity::valid_identifier_(target_relay_node_id) &&
         target_relay_node_id.size() <= kProductPeerHandshakeMaxNodeIdBytes &&
         child_node_id != target_relay_node_id && child_credential_generation > 0 &&
         child_key_epoch > 0 &&
         ProductPeerSecurity::nonzero_(child_ephemeral_public_key.data(), child_ephemeral_public_key.size()) &&
         ProductPeerSecurity::nonzero_(child_nonce.data(), child_nonce.size());
}

bool ProductRelayChallenge::valid() const {
  return session_token != 0 && valid_unicast_mac(target_child_mac) &&
         ProductPeerSecurity::valid_identifier_(relay_node_id) &&
         relay_node_id.size() <= kProductPeerHandshakeMaxNodeIdBytes &&
         relay_credential_generation > 0 && relay_key_epoch > 0 && requested_at_ms > 0 &&
         relay_health.observed_at_ms > 0 &&
         ProductPeerSecurity::nonzero_(relay_ephemeral_public_key.data(), relay_ephemeral_public_key.size()) &&
         ProductPeerSecurity::nonzero_(relay_nonce.data(), relay_nonce.size());
}

bool ProductChildProofPacket::valid() const {
  return session_token != 0 && valid_unicast_mac(target_relay_mac) &&
         ProductPeerSecurity::nonzero_(child_proof.data(), child_proof.size());
}

bool ProductChildGrantPacket::valid() const {
  return session_token != 0 && valid_unicast_mac(target_child_mac) &&
         ProductPeerSecurity::nonzero_(authorization_uuid.data(), authorization_uuid.size()) &&
         issued_at_ms > 0 && issued_at_ms < expires_at_ms && authorization_epoch > 0 &&
         ProductPeerSecurity::nonzero_(child_grant_mac.data(), child_grant_mac.size());
}

std::string ProductChildGrantPacket::authorization_id() const {
  if (!ProductPeerSecurity::nonzero_(authorization_uuid.data(), authorization_uuid.size()))
    return {};
  char buffer[37]{};
  std::snprintf(
      buffer,
      sizeof(buffer),
      "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      authorization_uuid[0], authorization_uuid[1], authorization_uuid[2], authorization_uuid[3],
      authorization_uuid[4], authorization_uuid[5], authorization_uuid[6], authorization_uuid[7],
      authorization_uuid[8], authorization_uuid[9], authorization_uuid[10], authorization_uuid[11],
      authorization_uuid[12], authorization_uuid[13], authorization_uuid[14], authorization_uuid[15]);
  return std::string(buffer);
}

bool parse_authorization_uuid(
    const std::string &authorization_id,
    std::array<uint8_t, 16> *uuid_bytes) {
  if (uuid_bytes == nullptr || authorization_id.size() != 36 || authorization_id[8] != '-' ||
      authorization_id[13] != '-' || authorization_id[18] != '-' || authorization_id[23] != '-') {
    return false;
  }
  std::array<uint8_t, 16> parsed{};
  std::size_t source = 0;
  for (std::size_t index = 0; index < parsed.size(); ++index) {
    while (source < authorization_id.size() && authorization_id[source] == '-') ++source;
    if (source + 1 >= authorization_id.size()) return false;
    const int high = hex_nibble(authorization_id[source]);
    const int low = hex_nibble(authorization_id[source + 1]);
    if (high < 0 || low < 0) return false;
    parsed[index] = static_cast<uint8_t>((high << 4) | low);
    source += 2;
  }
  while (source < authorization_id.size() && authorization_id[source] == '-') ++source;
  if (source != authorization_id.size() ||
      !ProductPeerSecurity::nonzero_(parsed.data(), parsed.size())) {
    return false;
  }
  *uuid_bytes = parsed;
  return true;
}

std::string product_session_id(uint64_t session_token) {
  if (session_token == 0) return {};
  char buffer[20]{};
  std::snprintf(buffer, sizeof(buffer), "s5-%016llx", static_cast<unsigned long long>(session_token));
  return std::string(buffer);
}

bool encode_child_auth_init(
    const ProductChildAuthInit &packet,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !packet.valid()) return false;
  begin_packet(ProductPeerHandshakeType::CHILD_AUTH_INIT, encoded);
  put_u64(encoded, packet.session_token);
  put_u32(encoded, packet.child_credential_generation);
  put_u32(encoded, packet.child_key_epoch);
  put_array(encoded, packet.child_ephemeral_public_key);
  put_array(encoded, packet.child_nonce);
  if (!put_id(encoded, packet.child_node_id) || !put_id(encoded, packet.target_relay_node_id) ||
      !finish_packet(*encoded)) {
    encoded->clear();
    return false;
  }
  return true;
}

bool decode_child_auth_init(
    const uint8_t *data,
    std::size_t size,
    ProductChildAuthInit *packet) {
  if (packet == nullptr || !valid_header(data, size, ProductPeerHandshakeType::CHILD_AUTH_INIT))
    return false;
  ProductChildAuthInit parsed;
  std::size_t offset = kHeaderBytes;
  if (!take_u64(data, size, &offset, &parsed.session_token) ||
      !take_u32(data, size, &offset, &parsed.child_credential_generation) ||
      !take_u32(data, size, &offset, &parsed.child_key_epoch) ||
      !take_array(data, size, &offset, &parsed.child_ephemeral_public_key) ||
      !take_array(data, size, &offset, &parsed.child_nonce) ||
      !take_id(data, size, &offset, &parsed.child_node_id) ||
      !take_id(data, size, &offset, &parsed.target_relay_node_id) || offset != size ||
      !parsed.valid()) {
    return false;
  }
  *packet = parsed;
  return true;
}

bool encode_relay_challenge(
    const ProductRelayChallenge &packet,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !packet.valid()) return false;
  begin_packet(ProductPeerHandshakeType::RELAY_CHALLENGE, encoded);
  put_u64(encoded, packet.session_token);
  put_array(encoded, packet.target_child_mac);
  put_u32(encoded, packet.relay_credential_generation);
  put_u32(encoded, packet.relay_key_epoch);
  put_array(encoded, packet.relay_ephemeral_public_key);
  put_array(encoded, packet.relay_nonce);
  put_u64(encoded, packet.requested_at_ms);
  put_u64(encoded, packet.relay_health.observed_at_ms);
  uint8_t flags = 0;
  if (packet.relay_health.relay_capable) flags |= 0x01U;
  if (packet.relay_health.low_battery) flags |= 0x02U;
  if (packet.relay_health.overloaded) flags |= 0x04U;
  encoded->push_back(flags);
  if (!put_id(encoded, packet.relay_node_id) || !finish_packet(*encoded)) {
    encoded->clear();
    return false;
  }
  return true;
}

bool decode_relay_challenge(
    const uint8_t *data,
    std::size_t size,
    ProductRelayChallenge *packet) {
  if (packet == nullptr || !valid_header(data, size, ProductPeerHandshakeType::RELAY_CHALLENGE))
    return false;
  ProductRelayChallenge parsed;
  std::size_t offset = kHeaderBytes;
  if (!take_u64(data, size, &offset, &parsed.session_token) ||
      !take_array(data, size, &offset, &parsed.target_child_mac) ||
      !take_u32(data, size, &offset, &parsed.relay_credential_generation) ||
      !take_u32(data, size, &offset, &parsed.relay_key_epoch) ||
      !take_array(data, size, &offset, &parsed.relay_ephemeral_public_key) ||
      !take_array(data, size, &offset, &parsed.relay_nonce) ||
      !take_u64(data, size, &offset, &parsed.requested_at_ms) ||
      !take_u64(data, size, &offset, &parsed.relay_health.observed_at_ms) || offset >= size) {
    return false;
  }
  const uint8_t flags = data[offset++];
  if ((flags & 0xf8U) != 0) return false;
  parsed.relay_health.relay_capable = (flags & 0x01U) != 0;
  parsed.relay_health.low_battery = (flags & 0x02U) != 0;
  parsed.relay_health.overloaded = (flags & 0x04U) != 0;
  if (!take_id(data, size, &offset, &parsed.relay_node_id) || offset != size || !parsed.valid())
    return false;
  *packet = parsed;
  return true;
}

bool encode_child_proof_packet(
    const ProductChildProofPacket &packet,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !packet.valid()) return false;
  begin_packet(ProductPeerHandshakeType::CHILD_PROOF, encoded);
  put_u64(encoded, packet.session_token);
  put_array(encoded, packet.target_relay_mac);
  put_array(encoded, packet.child_proof);
  return finish_packet(*encoded);
}

bool decode_child_proof_packet(
    const uint8_t *data,
    std::size_t size,
    ProductChildProofPacket *packet) {
  if (packet == nullptr || !valid_header(data, size, ProductPeerHandshakeType::CHILD_PROOF))
    return false;
  ProductChildProofPacket parsed;
  std::size_t offset = kHeaderBytes;
  if (!take_u64(data, size, &offset, &parsed.session_token) ||
      !take_array(data, size, &offset, &parsed.target_relay_mac) ||
      !take_array(data, size, &offset, &parsed.child_proof) || offset != size || !parsed.valid()) {
    return false;
  }
  *packet = parsed;
  return true;
}

bool encode_child_grant_packet(
    const ProductChildGrantPacket &packet,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !packet.valid()) return false;
  begin_packet(ProductPeerHandshakeType::CHILD_GRANT, encoded);
  put_u64(encoded, packet.session_token);
  put_array(encoded, packet.target_child_mac);
  put_array(encoded, packet.authorization_uuid);
  put_u64(encoded, packet.issued_at_ms);
  put_u64(encoded, packet.expires_at_ms);
  put_u32(encoded, packet.authorization_epoch);
  put_array(encoded, packet.child_grant_mac);
  return finish_packet(*encoded);
}

bool decode_child_grant_packet(
    const uint8_t *data,
    std::size_t size,
    ProductChildGrantPacket *packet) {
  if (packet == nullptr || !valid_header(data, size, ProductPeerHandshakeType::CHILD_GRANT))
    return false;
  ProductChildGrantPacket parsed;
  std::size_t offset = kHeaderBytes;
  if (!take_u64(data, size, &offset, &parsed.session_token) ||
      !take_array(data, size, &offset, &parsed.target_child_mac) ||
      !take_array(data, size, &offset, &parsed.authorization_uuid) ||
      !take_u64(data, size, &offset, &parsed.issued_at_ms) ||
      !take_u64(data, size, &offset, &parsed.expires_at_ms) ||
      !take_u32(data, size, &offset, &parsed.authorization_epoch) ||
      !take_array(data, size, &offset, &parsed.child_grant_mac) || offset != size || !parsed.valid()) {
    return false;
  }
  *packet = parsed;
  return true;
}

}  // namespace esphome::greenhouse_n3w_product_runtime
