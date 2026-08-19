#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "n3w_radio.h"
#include "n3w_simple_crypto.h"

namespace esphome::greenhouse_n3w_core {

constexpr std::size_t kSimplePeerControlMaxBytes = 240;

enum class SimplePeerPacketType : uint8_t {
  DISCOVERY = 1,
  CHALLENGE = 2,
  ACCEPT = 3,
};

enum class SimpleRuntimeError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  PACKET_TOO_LARGE,
  PACKET_TRUNCATED,
  PACKET_REJECTED,
  AUTH_FAILED,
  GENERATION_MISMATCH,
  BINDING_MISMATCH,
  CRYPTO_FAILED,
};

struct SimpleRelayDiscovery {
  uint64_t peer_trust_generation{0};
  uint8_t channel{0};
  std::string relay_node_id;

  bool valid() const;
};

struct SimplePeerChallenge {
  uint64_t peer_trust_generation{0};
  std::string child_node_id;
  std::string relay_node_id;
  HandshakeNonce child_boot_nonce{};
  HandshakeNonce challenge_nonce{};
  PeerProof proof{};
};

struct SimplePeerAccept {
  uint64_t peer_trust_generation{0};
  std::string relay_node_id;
  std::string child_node_id;
  HandshakeNonce relay_boot_nonce{};
  HandshakeNonce challenge_nonce{};
  PeerProof proof{};
};

SimpleRuntimeError encode_simple_relay_discovery(
    const SimpleRelayDiscovery &packet,
    std::vector<uint8_t> *encoded);
SimpleRuntimeError decode_simple_relay_discovery(
    const uint8_t *data,
    std::size_t size,
    SimpleRelayDiscovery *packet);

SimpleRuntimeError build_simple_peer_challenge(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &child,
    const PeerEndpointV2 &relay,
    const HandshakeNonce &child_boot_nonce,
    const HandshakeNonce &challenge_nonce,
    SimplePeerChallenge *packet);
SimpleRuntimeError encode_simple_peer_challenge(
    const SimplePeerChallenge &packet,
    std::vector<uint8_t> *encoded);
SimpleRuntimeError decode_simple_peer_challenge(
    const uint8_t *data,
    std::size_t size,
    SimplePeerChallenge *packet);
SimpleRuntimeError verify_simple_peer_challenge(
    const SystemPeerCredentialV2 &credential,
    const PeerMac &source_child_mac,
    const PeerEndpointV2 &local_relay,
    const SimplePeerChallenge &packet,
    SimpleLmk *pair_lmk);

SimpleRuntimeError build_simple_peer_accept(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &relay,
    const PeerEndpointV2 &child,
    const HandshakeNonce &relay_boot_nonce,
    const HandshakeNonce &challenge_nonce,
    SimplePeerAccept *packet);
SimpleRuntimeError encode_simple_peer_accept(
    const SimplePeerAccept &packet,
    std::vector<uint8_t> *encoded);
SimpleRuntimeError decode_simple_peer_accept(
    const uint8_t *data,
    std::size_t size,
    SimplePeerAccept *packet);
SimpleRuntimeError verify_simple_peer_accept(
    const SystemPeerCredentialV2 &credential,
    const PeerMac &source_relay_mac,
    const PeerEndpointV2 &local_child,
    const SimplePeerAccept &packet,
    SimpleLmk *pair_lmk);

// Phase 3 intentionally keeps path state local. Manager is not a path owner.
// The existing three-state LocalPathController provides bounded hysteresis:
// DIRECT -> DISCOVERY -> RELAY_ACTIVE -> DIRECT.

}  // namespace esphome::greenhouse_n3w_core
