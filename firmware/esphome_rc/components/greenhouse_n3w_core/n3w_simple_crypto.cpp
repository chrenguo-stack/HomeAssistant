#include "n3w_simple_crypto.h"

#include <algorithm>
#include <cstring>

#include "mbedtls/gcm.h"
#include "mbedtls/hkdf.h"
#include "mbedtls/md.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr char kBootstrapDomain[] = "gh.pair.simple-bootstrap/1";
constexpr char kPairDomain[] = "gh.n3w.peer-pair/1";
constexpr char kProofDomain[] = "gh.n3w.long-lived-peer-proof/1";
constexpr char kLmkDomain[] = "gh.n3w.long-lived-peer-lmk/1";

bool valid_simple_id(const std::string &value) {
  if (value.size() < 3 || value.size() > 64) return false;
  const auto alpha_num = [](char ch) {
    return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
           (ch >= '0' && ch <= '9');
  };
  if (!alpha_num(value.front())) return false;
  return std::all_of(value.begin() + 1, value.end(), [&](char ch) {
    return alpha_num(ch) || ch == '_' || ch == '-';
  });
}

bool valid_pairing_id(const std::string &value) {
  if (value.size() < 8 || value.size() > 128) return false;
  return std::all_of(value.begin(), value.end(), [](char ch) {
    return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') ||
           (ch >= '0' && ch <= '9') || ch == '.' || ch == '_' ||
           ch == ':' || ch == '-';
  });
}


char hex_digit(uint8_t value) {
  return value < 10 ? static_cast<char>('0' + value)
                    : static_cast<char>('a' + (value - 10));
}

template<std::size_t N>
std::string hex_encode(const std::array<uint8_t, N> &value) {
  std::string output(N * 2U, '0');
  for (std::size_t i = 0; i < N; ++i) {
    output[i * 2U] = hex_digit(static_cast<uint8_t>(value[i] >> 4U));
    output[i * 2U + 1U] = hex_digit(static_cast<uint8_t>(value[i] & 0x0fU));
  }
  return output;
}

void append_ascii(std::vector<uint8_t> *out, const char *value) {
  out->insert(out->end(), value, value + std::strlen(value));
}

void append_string(std::vector<uint8_t> *out, const std::string &value) {
  out->insert(out->end(), value.begin(), value.end());
}

void append_separator(std::vector<uint8_t> *out) { out->push_back(0); }

void append_field(std::vector<uint8_t> *out, const std::string &value) {
  append_separator(out);
  append_string(out, value);
}

void append_marker(std::vector<uint8_t> *out, const char *value) {
  append_separator(out);
  append_ascii(out, value);
  append_separator(out);
}

SimpleCryptoError sha256(
    const uint8_t *data,
    std::size_t size,
    std::array<uint8_t, 32> *digest) {
  if (digest == nullptr || (data == nullptr && size != 0)) {
    return SimpleCryptoError::INVALID_ARGUMENT;
  }
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr || mbedtls_md(info, data, size, digest->data()) != 0) {
    digest->fill(0);
    return SimpleCryptoError::HASH_FAILED;
  }
  return SimpleCryptoError::NONE;
}

SimpleCryptoError hmac_sha256(
    const uint8_t *key,
    std::size_t key_size,
    const uint8_t *data,
    std::size_t size,
    PeerProof *digest) {
  if (digest == nullptr || key == nullptr || key_size == 0 ||
      (data == nullptr && size != 0)) {
    return SimpleCryptoError::INVALID_ARGUMENT;
  }
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr ||
      mbedtls_md_hmac(info, key, key_size, data, size, digest->data()) != 0) {
    digest->fill(0);
    return SimpleCryptoError::HMAC_FAILED;
  }
  return SimpleCryptoError::NONE;
}

bool constant_time_equal(const uint8_t *left, const uint8_t *right, std::size_t size) {
  if (left == nullptr || right == nullptr) return false;
  uint8_t diff = 0;
  for (std::size_t i = 0; i < size; ++i) diff |= left[i] ^ right[i];
  return diff == 0;
}

std::vector<uint8_t> pairing_proof_message(
    const SimplePairingTranscript &transcript,
    PairingRole role) {
  std::vector<uint8_t> message;
  append_ascii(&message, kBootstrapDomain);
  append_marker(&message, "proof");
  append_ascii(&message, role == PairingRole::NODE ? "node" : "manager");
  append_separator(&message);
  const std::vector<uint8_t> encoded = transcript.encode();
  message.insert(message.end(), encoded.begin(), encoded.end());
  return message;
}

std::vector<uint8_t> canonical_pair_binding(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &first,
    const PeerEndpointV2 &second) {
  const PeerEndpointV2 *left = &first;
  const PeerEndpointV2 *right = &second;
  if (right->node_id < left->node_id ||
      (right->node_id == left->node_id && right->mac < left->mac)) {
    std::swap(left, right);
  }
  std::vector<uint8_t> binding;
  append_ascii(&binding, kPairDomain);
  append_field(&binding, credential.system_id);
  append_field(&binding, std::to_string(credential.generation));
  append_field(&binding, left->node_id);
  append_field(&binding, hex_encode(left->mac));
  append_field(&binding, right->node_id);
  append_field(&binding, hex_encode(right->mac));
  return binding;
}

std::vector<uint8_t> peer_proof_message(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &prover,
    const PeerEndpointV2 &verifier,
    const HandshakeNonce &prover_boot_nonce,
    const HandshakeNonce &challenge_nonce) {
  std::vector<uint8_t> message;
  append_ascii(&message, kProofDomain);
  append_field(&message, credential.system_id);
  append_field(&message, std::to_string(credential.generation));
  append_field(&message, prover.node_id);
  append_field(&message, hex_encode(prover.mac));
  append_field(&message, verifier.node_id);
  append_field(&message, hex_encode(verifier.mac));
  append_field(&message, hex_encode(prover_boot_nonce));
  append_field(&message, hex_encode(challenge_nonce));
  return message;
}

bool distinct_endpoints(const PeerEndpointV2 &first, const PeerEndpointV2 &second) {
  return first.node_id != second.node_id && first.mac != second.mac;
}

uint8_t nibble(char ch) {
  if (ch >= '0' && ch <= '9') return static_cast<uint8_t>(ch - '0');
  if (ch >= 'a' && ch <= 'f') return static_cast<uint8_t>(10 + ch - 'a');
  return static_cast<uint8_t>(10 + ch - 'A');
}

template<std::size_t N>
bool decode_hex(const char *text, std::array<uint8_t, N> *output) {
  if (text == nullptr || output == nullptr || std::strlen(text) != N * 2U) return false;
  for (std::size_t i = 0; i < N; ++i) {
    const char high = text[i * 2U];
    const char low = text[i * 2U + 1U];
    const auto valid = [](char ch) {
      return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') ||
             (ch >= 'A' && ch <= 'F');
    };
    if (!valid(high) || !valid(low)) return false;
    (*output)[i] = static_cast<uint8_t>((nibble(high) << 4U) | nibble(low));
  }
  return true;
}

}  // namespace

bool SimplePairingTranscript::valid() const {
  return valid_pairing_id(pairing_id) && valid_simple_id(hardware_id) &&
         valid_simple_id(manager_id) && node_nonce != manager_nonce;
}

std::vector<uint8_t> SimplePairingTranscript::encode() const {
  if (!valid()) return {};
  std::vector<uint8_t> encoded;
  append_ascii(&encoded, kBootstrapDomain);
  append_field(&encoded, pairing_id);
  append_field(&encoded, hardware_id);
  append_field(&encoded, manager_id);
  append_field(&encoded, hex_encode(node_nonce));
  append_field(&encoded, hex_encode(manager_nonce));
  return encoded;
}

bool valid_simple_identity_v2(const std::string &value) {
  return valid_simple_id(value);
}

bool PeerEndpointV2::valid() const {
  return valid_simple_id(node_id);
}

bool SystemPeerCredentialV2::valid() const {
  return valid_simple_id(system_id) && generation > 0;
}

void SystemPeerCredentialV2::clear() {
  std::fill(key.begin(), key.end(), 0);
  system_id.clear();
  generation = 0;
}

SimpleCryptoError build_setup_proof(
    const SetupSecret &setup_secret,
    const SimplePairingTranscript &transcript,
    PairingRole role,
    PeerProof *proof) {
  if (proof == nullptr || !transcript.valid() ||
      (role != PairingRole::NODE && role != PairingRole::MANAGER)) {
    return SimpleCryptoError::INVALID_ARGUMENT;
  }
  const std::vector<uint8_t> message = pairing_proof_message(transcript, role);
  return hmac_sha256(
      setup_secret.data(), setup_secret.size(), message.data(), message.size(), proof);
}

SimpleCryptoError derive_bootstrap_key(
    const SetupSecret &setup_secret,
    const SimplePairingTranscript &transcript,
    std::array<uint8_t, 32> *bootstrap_key) {
  if (bootstrap_key == nullptr || !transcript.valid()) {
    return SimpleCryptoError::INVALID_ARGUMENT;
  }
  const std::vector<uint8_t> encoded = transcript.encode();
  std::vector<uint8_t> salt_input;
  append_ascii(&salt_input, kBootstrapDomain);
  append_marker(&salt_input, "salt");
  salt_input.insert(salt_input.end(), encoded.begin(), encoded.end());
  std::array<uint8_t, 32> salt{};
  SimpleCryptoError error = sha256(salt_input.data(), salt_input.size(), &salt);
  if (error != SimpleCryptoError::NONE) return error;

  std::vector<uint8_t> info;
  append_ascii(&info, kBootstrapDomain);
  append_marker(&info, "key");
  info.insert(info.end(), encoded.begin(), encoded.end());
  const mbedtls_md_info_t *md = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (md == nullptr ||
      mbedtls_hkdf(
          md,
          salt.data(), salt.size(),
          setup_secret.data(), setup_secret.size(),
          info.data(), info.size(),
          bootstrap_key->data(), bootstrap_key->size()) != 0) {
    bootstrap_key->fill(0);
    return SimpleCryptoError::HKDF_FAILED;
  }
  return SimpleCryptoError::NONE;
}

SimpleCryptoError decrypt_simple_credential_bundle(
    const std::array<uint8_t, 32> &bootstrap_key,
    const SimplePairingTranscript &transcript,
    const SimpleAeadNonce &nonce,
    const std::vector<uint8_t> &ciphertext_and_tag,
    std::vector<uint8_t> *plaintext) {
  if (plaintext == nullptr || !transcript.valid() || ciphertext_and_tag.size() < 16U) {
    return SimpleCryptoError::INVALID_ARGUMENT;
  }
  const std::vector<uint8_t> aad = transcript.encode();
  const std::size_t ciphertext_size = ciphertext_and_tag.size() - 16U;
  plaintext->assign(ciphertext_size, 0);

  mbedtls_gcm_context context;
  mbedtls_gcm_init(&context);
  int rc = mbedtls_gcm_setkey(
      &context,
      MBEDTLS_CIPHER_ID_AES,
      bootstrap_key.data(),
      static_cast<unsigned int>(bootstrap_key.size() * 8U));
  if (rc == 0) {
    rc = mbedtls_gcm_auth_decrypt(
        &context,
        ciphertext_size,
        nonce.data(), nonce.size(),
        aad.data(), aad.size(),
        ciphertext_and_tag.data() + ciphertext_size, 16U,
        ciphertext_and_tag.data(),
        plaintext->data());
  }
  mbedtls_gcm_free(&context);
  if (rc != 0) {
    std::fill(plaintext->begin(), plaintext->end(), 0);
    plaintext->clear();
    return SimpleCryptoError::AEAD_FAILED;
  }
  return SimpleCryptoError::NONE;
}

SimpleCryptoError build_peer_proof_v2(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &prover,
    const PeerEndpointV2 &verifier,
    const HandshakeNonce &prover_boot_nonce,
    const HandshakeNonce &challenge_nonce,
    PeerProof *proof) {
  if (proof == nullptr || !credential.valid() || !prover.valid() ||
      !verifier.valid() || !distinct_endpoints(prover, verifier)) {
    return SimpleCryptoError::INVALID_ARGUMENT;
  }
  const std::vector<uint8_t> message = peer_proof_message(
      credential, prover, verifier, prover_boot_nonce, challenge_nonce);
  return hmac_sha256(
      credential.key.data(), credential.key.size(),
      message.data(), message.size(), proof);
}

bool verify_peer_proof_v2(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &prover,
    const PeerEndpointV2 &verifier,
    const HandshakeNonce &prover_boot_nonce,
    const HandshakeNonce &challenge_nonce,
    const PeerProof &proof) {
  PeerProof expected{};
  if (build_peer_proof_v2(
          credential, prover, verifier, prover_boot_nonce, challenge_nonce,
          &expected) != SimpleCryptoError::NONE) {
    return false;
  }
  return constant_time_equal(expected.data(), proof.data(), proof.size());
}

SimpleCryptoError derive_pair_lmk_v2(
    const SystemPeerCredentialV2 &credential,
    const PeerEndpointV2 &first,
    const PeerEndpointV2 &second,
    SimpleLmk *lmk) {
  if (lmk == nullptr || !credential.valid() || !first.valid() ||
      !second.valid() || !distinct_endpoints(first, second)) {
    return SimpleCryptoError::INVALID_ARGUMENT;
  }
  const std::vector<uint8_t> binding = canonical_pair_binding(credential, first, second);
  std::vector<uint8_t> salt_input;
  append_ascii(&salt_input, kLmkDomain);
  append_marker(&salt_input, "salt");
  salt_input.insert(salt_input.end(), binding.begin(), binding.end());
  std::array<uint8_t, 32> salt{};
  SimpleCryptoError error = sha256(salt_input.data(), salt_input.size(), &salt);
  if (error != SimpleCryptoError::NONE) return error;

  std::vector<uint8_t> info;
  append_ascii(&info, kLmkDomain);
  append_marker(&info, "derive");
  info.insert(info.end(), binding.begin(), binding.end());
  const mbedtls_md_info_t *md = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (md == nullptr ||
      mbedtls_hkdf(
          md,
          salt.data(), salt.size(),
          credential.key.data(), credential.key.size(),
          info.data(), info.size(),
          lmk->data(), lmk->size()) != 0) {
    lmk->fill(0);
    return SimpleCryptoError::HKDF_FAILED;
  }
  return SimpleCryptoError::NONE;
}


}  // namespace esphome::greenhouse_n3w_core
