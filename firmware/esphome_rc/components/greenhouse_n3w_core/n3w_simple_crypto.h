#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace esphome::greenhouse_n3w_core {

constexpr std::size_t kSetupSecretBytes = 32;
constexpr std::size_t kSystemPeerKeyBytes = 32;
constexpr std::size_t kSimpleHandshakeNonceBytes = 16;
constexpr std::size_t kSimpleAeadNonceBytes = 12;
constexpr std::size_t kSimpleProofBytes = 32;
constexpr std::size_t kSimpleLmkBytes = 16;

using SetupSecret = std::array<uint8_t, kSetupSecretBytes>;
using SystemPeerKey = std::array<uint8_t, kSystemPeerKeyBytes>;
using HandshakeNonce = std::array<uint8_t, kSimpleHandshakeNonceBytes>;
using SimpleAeadNonce = std::array<uint8_t, kSimpleAeadNonceBytes>;
using PeerProof = std::array<uint8_t, kSimpleProofBytes>;
using SimpleLmk = std::array<uint8_t, kSimpleLmkBytes>;
using PeerMac = std::array<uint8_t, 6>;

enum class SimpleCryptoError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  HASH_FAILED,
  HMAC_FAILED,
  HKDF_FAILED,
  AEAD_FAILED,
  AUTH_FAILED,
};

enum class PairingRole : uint8_t {
  NODE = 0,
  MANAGER = 1,
};

struct SimplePairingTranscript {
  std::string pairing_id;
  std::string hardware_id;
  std::string manager_id;
  HandshakeNonce node_nonce{};
  HandshakeNonce manager_nonce{};

  bool valid() const;
  std::vector<uint8_t> encode() const;
};

bool valid_simple_identity_v2(const std::string &value);

struct PeerEndpointV2 {
  std::string node_id;
  PeerMac mac{};

  bool valid() const;
};

struct SystemPeerCredentialV2 {
  std::string system_id;
  uint64_t generation{0};
  SystemPeerKey key{};

  bool valid() const;
  void clear();
};

SimpleCryptoError build_setup_proof(
    const SetupSecret &setup_secret,
    const SimplePairingTranscript &transcript,
    PairingRole role,
    PeerProof *proof);

SimpleCryptoError derive_bootstrap_key(
    const SetupSecret &setup_secret,
    const SimplePairingTranscript &transcript,
    std::array<uint8_t, 32> *bootstrap_key);

SimpleCryptoError decrypt_simple_credential_bundle(
    const std::array<uint8_t, 32> &bootstrap_key,
    const SimplePairingTranscript &transcript,
    const SimpleAeadNonce &nonce,
    const std::vector<uint8_t> &ciphertext_and_tag,
    std::vector<uint8_t> *plaintext);

SimpleCryptoError build_peer_proof_v2(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &prover,
    const PeerEndpointV2 &verifier,
    const HandshakeNonce &prover_boot_nonce,
    const HandshakeNonce &challenge_nonce,
    PeerProof *proof);

bool verify_peer_proof_v2(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &prover,
    const PeerEndpointV2 &verifier,
    const HandshakeNonce &prover_boot_nonce,
    const HandshakeNonce &challenge_nonce,
    const PeerProof &proof);

SimpleCryptoError derive_pair_lmk_v2(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &first,
    const PeerEndpointV2 &second,
    SimpleLmk *lmk);


}  // namespace esphome::greenhouse_n3w_core
