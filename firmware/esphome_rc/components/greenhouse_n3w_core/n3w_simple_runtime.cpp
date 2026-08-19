#include "n3w_simple_runtime.h"

#include <algorithm>

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint8_t kMagic[] = {'N', '3', 'P', '2'};
constexpr std::size_t kPrefixBytes = 5;

bool nonzero(const uint8_t *data, std::size_t size) {
  if (data == nullptr) return false;
  uint8_t aggregate = 0;
  for (std::size_t i = 0; i < size; ++i) aggregate |= data[i];
  return aggregate != 0;
}

void append_u64(std::vector<uint8_t> *out, uint64_t value) {
  for (int shift = 56; shift >= 0; shift -= 8) {
    out->push_back(static_cast<uint8_t>((value >> shift) & 0xffU));
  }
}

bool read_u64(const uint8_t *data, std::size_t size, std::size_t *offset, uint64_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr || *offset + 8U > size) {
    return false;
  }
  uint64_t parsed = 0;
  for (std::size_t i = 0; i < 8U; ++i) parsed = (parsed << 8U) | data[*offset + i];
  *offset += 8U;
  *value = parsed;
  return true;
}

bool append_identity(std::vector<uint8_t> *out, const std::string &value) {
  if (!valid_simple_identity_v2(value) || value.size() > 255U) return false;
  out->push_back(static_cast<uint8_t>(value.size()));
  out->insert(out->end(), value.begin(), value.end());
  return true;
}

bool read_identity(
    const uint8_t *data,
    std::size_t size,
    std::size_t *offset,
    std::string *value) {
  if (data == nullptr || offset == nullptr || value == nullptr || *offset >= size) return false;
  const std::size_t length = data[(*offset)++];
  if (length == 0 || *offset + length > size) return false;
  value->assign(reinterpret_cast<const char *>(data + *offset), length);
  *offset += length;
  return valid_simple_identity_v2(*value);
}

void append_prefix(std::vector<uint8_t> *out, SimplePeerPacketType type) {
  out->insert(out->end(), std::begin(kMagic), std::end(kMagic));
  out->push_back(static_cast<uint8_t>(type));
}

SimpleRuntimeError parse_prefix(
    const uint8_t *data,
    std::size_t size,
    SimplePeerPacketType expected,
    std::size_t *offset) {
  if (data == nullptr || offset == nullptr || size < kPrefixBytes) {
    return SimpleRuntimeError::PACKET_TRUNCATED;
  }
  if (!std::equal(std::begin(kMagic), std::end(kMagic), data) ||
      data[4] != static_cast<uint8_t>(expected)) {
    return SimpleRuntimeError::PACKET_REJECTED;
  }
  *offset = kPrefixBytes;
  return SimpleRuntimeError::NONE;
}

bool valid_peer_mac(const PeerMac &mac) {
  return nonzero(mac.data(), mac.size()) && (mac[0] & 0x01U) == 0;
}

bool challenge_shape_valid(const SimplePeerChallenge &packet) {
  return packet.peer_trust_generation > 0 && valid_simple_identity_v2(packet.child_node_id) &&
         valid_simple_identity_v2(packet.relay_node_id) && packet.child_node_id != packet.relay_node_id;
}

bool accept_shape_valid(const SimplePeerAccept &packet) {
  return packet.peer_trust_generation > 0 && valid_simple_identity_v2(packet.relay_node_id) &&
         valid_simple_identity_v2(packet.child_node_id) && packet.relay_node_id != packet.child_node_id;
}

}  // namespace

bool SimpleRelayDiscovery::valid() const {
  return peer_trust_generation > 0 && valid_radio_channel(channel) &&
         valid_simple_identity_v2(relay_node_id);
}

SimpleRuntimeError encode_simple_relay_discovery(
    const SimpleRelayDiscovery &packet,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !packet.valid()) return SimpleRuntimeError::INVALID_ARGUMENT;
  encoded->clear();
  append_prefix(encoded, SimplePeerPacketType::DISCOVERY);
  append_u64(encoded, packet.peer_trust_generation);
  encoded->push_back(packet.channel);
  if (!append_identity(encoded, packet.relay_node_id)) {
    encoded->clear();
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  return encoded->size() <= kSimplePeerControlMaxBytes
             ? SimpleRuntimeError::NONE
             : SimpleRuntimeError::PACKET_TOO_LARGE;
}

SimpleRuntimeError decode_simple_relay_discovery(
    const uint8_t *data,
    std::size_t size,
    SimpleRelayDiscovery *packet) {
  if (packet == nullptr || size > kSimplePeerControlMaxBytes) {
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  std::size_t offset = 0;
  SimpleRuntimeError error = parse_prefix(data, size, SimplePeerPacketType::DISCOVERY, &offset);
  if (error != SimpleRuntimeError::NONE) return error;
  SimpleRelayDiscovery candidate;
  if (!read_u64(data, size, &offset, &candidate.peer_trust_generation) || offset >= size) {
    return SimpleRuntimeError::PACKET_TRUNCATED;
  }
  candidate.channel = data[offset++];
  if (!read_identity(data, size, &offset, &candidate.relay_node_id) ||
      offset != size || !candidate.valid()) {
    return SimpleRuntimeError::PACKET_REJECTED;
  }
  *packet = std::move(candidate);
  return SimpleRuntimeError::NONE;
}

SimpleRuntimeError build_simple_peer_challenge(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &child,
    const PeerEndpointV2 &relay,
    const HandshakeNonce &child_boot_nonce,
    const HandshakeNonce &challenge_nonce,
    SimplePeerChallenge *packet) {
  if (packet == nullptr || !credential.valid() || !child.valid() || !relay.valid()) {
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  SimplePeerChallenge candidate;
  candidate.peer_trust_generation = credential.generation;
  candidate.child_node_id = child.node_id;
  candidate.relay_node_id = relay.node_id;
  candidate.child_boot_nonce = child_boot_nonce;
  candidate.challenge_nonce = challenge_nonce;
  if (build_peer_proof_v2(
          credential, child, relay, child_boot_nonce, challenge_nonce,
          &candidate.proof) != SimpleCryptoError::NONE) {
    return SimpleRuntimeError::CRYPTO_FAILED;
  }
  *packet = std::move(candidate);
  return SimpleRuntimeError::NONE;
}

SimpleRuntimeError encode_simple_peer_challenge(
    const SimplePeerChallenge &packet,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !challenge_shape_valid(packet)) {
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  encoded->clear();
  append_prefix(encoded, SimplePeerPacketType::CHALLENGE);
  append_u64(encoded, packet.peer_trust_generation);
  if (!append_identity(encoded, packet.child_node_id) ||
      !append_identity(encoded, packet.relay_node_id)) {
    encoded->clear();
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  encoded->insert(encoded->end(), packet.child_boot_nonce.begin(), packet.child_boot_nonce.end());
  encoded->insert(encoded->end(), packet.challenge_nonce.begin(), packet.challenge_nonce.end());
  encoded->insert(encoded->end(), packet.proof.begin(), packet.proof.end());
  return encoded->size() <= kSimplePeerControlMaxBytes
             ? SimpleRuntimeError::NONE
             : SimpleRuntimeError::PACKET_TOO_LARGE;
}

SimpleRuntimeError decode_simple_peer_challenge(
    const uint8_t *data,
    std::size_t size,
    SimplePeerChallenge *packet) {
  if (packet == nullptr || size > kSimplePeerControlMaxBytes) {
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  std::size_t offset = 0;
  SimpleRuntimeError error = parse_prefix(data, size, SimplePeerPacketType::CHALLENGE, &offset);
  if (error != SimpleRuntimeError::NONE) return error;
  SimplePeerChallenge candidate;
  if (!read_u64(data, size, &offset, &candidate.peer_trust_generation) ||
      !read_identity(data, size, &offset, &candidate.child_node_id) ||
      !read_identity(data, size, &offset, &candidate.relay_node_id) ||
      offset + candidate.child_boot_nonce.size() + candidate.challenge_nonce.size() +
              candidate.proof.size() != size) {
    return SimpleRuntimeError::PACKET_TRUNCATED;
  }
  std::copy_n(data + offset, candidate.child_boot_nonce.size(), candidate.child_boot_nonce.begin());
  offset += candidate.child_boot_nonce.size();
  std::copy_n(data + offset, candidate.challenge_nonce.size(), candidate.challenge_nonce.begin());
  offset += candidate.challenge_nonce.size();
  std::copy_n(data + offset, candidate.proof.size(), candidate.proof.begin());
  offset += candidate.proof.size();
  if (offset != size || !challenge_shape_valid(candidate)) return SimpleRuntimeError::PACKET_REJECTED;
  *packet = std::move(candidate);
  return SimpleRuntimeError::NONE;
}

SimpleRuntimeError verify_simple_peer_challenge(
    const SystemPeerCredentialV2 &credential,
    const PeerMac &source_child_mac,
    const PeerEndpointV2 &local_relay,
    const SimplePeerChallenge &packet,
    SimpleLmk *pair_lmk) {
  if (pair_lmk == nullptr || !credential.valid() || !local_relay.valid() ||
      !valid_peer_mac(source_child_mac) || !challenge_shape_valid(packet)) {
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  if (packet.peer_trust_generation != credential.generation) {
    return SimpleRuntimeError::GENERATION_MISMATCH;
  }
  if (packet.relay_node_id != local_relay.node_id) {
    return SimpleRuntimeError::BINDING_MISMATCH;
  }
  PeerEndpointV2 child{packet.child_node_id, source_child_mac};
  if (!child.valid() || !verify_peer_proof_v2(
          credential, child, local_relay, packet.child_boot_nonce,
          packet.challenge_nonce, packet.proof)) {
    return SimpleRuntimeError::AUTH_FAILED;
  }
  return derive_pair_lmk_v2(credential, child, local_relay, pair_lmk) ==
                 SimpleCryptoError::NONE
             ? SimpleRuntimeError::NONE
             : SimpleRuntimeError::CRYPTO_FAILED;
}

SimpleRuntimeError build_simple_peer_accept(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &relay,
    const PeerEndpointV2 &child,
    const HandshakeNonce &relay_boot_nonce,
    const HandshakeNonce &challenge_nonce,
    SimplePeerAccept *packet) {
  if (packet == nullptr || !credential.valid() || !relay.valid() || !child.valid()) {
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  SimplePeerAccept candidate;
  candidate.peer_trust_generation = credential.generation;
  candidate.relay_node_id = relay.node_id;
  candidate.child_node_id = child.node_id;
  candidate.relay_boot_nonce = relay_boot_nonce;
  candidate.challenge_nonce = challenge_nonce;
  if (build_peer_proof_v2(
          credential, relay, child, relay_boot_nonce, challenge_nonce,
          &candidate.proof) != SimpleCryptoError::NONE) {
    return SimpleRuntimeError::CRYPTO_FAILED;
  }
  *packet = std::move(candidate);
  return SimpleRuntimeError::NONE;
}

SimpleRuntimeError encode_simple_peer_accept(
    const SimplePeerAccept &packet,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !accept_shape_valid(packet)) return SimpleRuntimeError::INVALID_ARGUMENT;
  encoded->clear();
  append_prefix(encoded, SimplePeerPacketType::ACCEPT);
  append_u64(encoded, packet.peer_trust_generation);
  if (!append_identity(encoded, packet.relay_node_id) ||
      !append_identity(encoded, packet.child_node_id)) {
    encoded->clear();
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  encoded->insert(encoded->end(), packet.relay_boot_nonce.begin(), packet.relay_boot_nonce.end());
  encoded->insert(encoded->end(), packet.challenge_nonce.begin(), packet.challenge_nonce.end());
  encoded->insert(encoded->end(), packet.proof.begin(), packet.proof.end());
  return encoded->size() <= kSimplePeerControlMaxBytes
             ? SimpleRuntimeError::NONE
             : SimpleRuntimeError::PACKET_TOO_LARGE;
}

SimpleRuntimeError decode_simple_peer_accept(
    const uint8_t *data,
    std::size_t size,
    SimplePeerAccept *packet) {
  if (packet == nullptr || size > kSimplePeerControlMaxBytes) return SimpleRuntimeError::INVALID_ARGUMENT;
  std::size_t offset = 0;
  SimpleRuntimeError error = parse_prefix(data, size, SimplePeerPacketType::ACCEPT, &offset);
  if (error != SimpleRuntimeError::NONE) return error;
  SimplePeerAccept candidate;
  if (!read_u64(data, size, &offset, &candidate.peer_trust_generation) ||
      !read_identity(data, size, &offset, &candidate.relay_node_id) ||
      !read_identity(data, size, &offset, &candidate.child_node_id) ||
      offset + candidate.relay_boot_nonce.size() + candidate.challenge_nonce.size() +
              candidate.proof.size() != size) {
    return SimpleRuntimeError::PACKET_TRUNCATED;
  }
  std::copy_n(data + offset, candidate.relay_boot_nonce.size(), candidate.relay_boot_nonce.begin());
  offset += candidate.relay_boot_nonce.size();
  std::copy_n(data + offset, candidate.challenge_nonce.size(), candidate.challenge_nonce.begin());
  offset += candidate.challenge_nonce.size();
  std::copy_n(data + offset, candidate.proof.size(), candidate.proof.begin());
  offset += candidate.proof.size();
  if (offset != size || !accept_shape_valid(candidate)) return SimpleRuntimeError::PACKET_REJECTED;
  *packet = std::move(candidate);
  return SimpleRuntimeError::NONE;
}

SimpleRuntimeError verify_simple_peer_accept(
    const SystemPeerCredentialV2 &credential,
    const PeerMac &source_relay_mac,
    const PeerEndpointV2 &local_child,
    const SimplePeerAccept &packet,
    SimpleLmk *pair_lmk) {
  if (pair_lmk == nullptr || !credential.valid() || !local_child.valid() ||
      !valid_peer_mac(source_relay_mac) || !accept_shape_valid(packet)) {
    return SimpleRuntimeError::INVALID_ARGUMENT;
  }
  if (packet.peer_trust_generation != credential.generation) {
    return SimpleRuntimeError::GENERATION_MISMATCH;
  }
  if (packet.child_node_id != local_child.node_id) {
    return SimpleRuntimeError::BINDING_MISMATCH;
  }
  PeerEndpointV2 relay{packet.relay_node_id, source_relay_mac};
  if (!relay.valid() || !verify_peer_proof_v2(
          credential, relay, local_child, packet.relay_boot_nonce,
          packet.challenge_nonce, packet.proof)) {
    return SimpleRuntimeError::AUTH_FAILED;
  }
  return derive_pair_lmk_v2(credential, relay, local_child, pair_lmk) ==
                 SimpleCryptoError::NONE
             ? SimpleRuntimeError::NONE
             : SimpleRuntimeError::CRYPTO_FAILED;
}


}  // namespace esphome::greenhouse_n3w_core
