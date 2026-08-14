#include "n3w_product_peer_security.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <string>
#include <vector>

#include "mbedtls/md.h"

#ifdef USE_ESP32
#include "esp_random.h"
#include "psa/crypto.h"
#else
#include <openssl/evp.h>
#include <openssl/rand.h>
#endif

namespace esphome::greenhouse_n3w_product_runtime {
namespace {

constexpr char kAuthKeyInfo[] = "gh.n3w-product/relay-auth-key/1";
constexpr char kProofDomain[] = "gh.n3w-product/peer-proof/1";
constexpr char kGrantDomain[] = "gh.n3w-product/peer-grant/1";
constexpr char kLmkDomain[] = "gh.n3w-product/espnow-lmk/1";
constexpr char kRequestDomain[] = "gh.n3w-product.peer-request/1";
constexpr char kGrantBindingDomain[] = "gh.n3w-product.peer-grant-binding/1";
constexpr char kBase64Alphabet[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

const char *role_name(ProductPeerRole role) {
  return role == ProductPeerRole::CHILD ? "child" : "relay";
}

void append_field(std::string *output, const std::string &value) {
  if (!output->empty()) output->push_back('\n');
  output->append(value);
}

void append_u32(std::string *output, uint32_t value) {
  append_field(output, std::to_string(value));
}

void append_u64(std::string *output, uint64_t value) {
  append_field(output, std::to_string(value));
}

bool grant_binding_shape_valid(const ProductPeerGrant &grant) {
  return ProductPeerSecurity::valid_session_id_(grant.authorization_id) &&
         ProductPeerSecurity::valid_identifier_(grant.system_id) &&
         ProductPeerSecurity::valid_session_id_(grant.session_id) &&
         ProductPeerSecurity::valid_identifier_(grant.child_node_id) &&
         ProductPeerSecurity::valid_identifier_(grant.relay_node_id) &&
         grant.child_node_id != grant.relay_node_id &&
         grant.child_credential_generation > 0 &&
         grant.relay_credential_generation > 0 && grant.child_key_epoch > 0 &&
         grant.relay_key_epoch > 0 && grant.issued_at_ms < grant.expires_at_ms &&
         grant.authorization_epoch > 0 &&
         ProductPeerSecurity::nonzero_(grant.child_ephemeral_public_key.data(),
                                       grant.child_ephemeral_public_key.size()) &&
         ProductPeerSecurity::nonzero_(grant.relay_ephemeral_public_key.data(),
                                       grant.relay_ephemeral_public_key.size()) &&
         ProductPeerSecurity::nonzero_(grant.child_nonce.data(), grant.child_nonce.size()) &&
         ProductPeerSecurity::nonzero_(grant.relay_nonce.data(), grant.relay_nonce.size());
}

}  // namespace

bool ProductPeerEndpoint::valid_shape(bool require_proof) const {
  return ProductPeerSecurity::valid_identifier_(node_id) && credential_generation > 0 &&
         key_epoch > 0 &&
         ProductPeerSecurity::nonzero_(ephemeral_public_key.data(), ephemeral_public_key.size()) &&
         ProductPeerSecurity::nonzero_(nonce.data(), nonce.size()) &&
         (!require_proof || ProductPeerSecurity::nonzero_(proof.data(), proof.size()));
}

bool ProductPeerRequest::valid_shape(bool require_proofs) const {
  return ProductPeerSecurity::valid_identifier_(system_id) &&
         ProductPeerSecurity::valid_session_id_(session_id) && child.node_id != relay.node_id &&
         child.valid_shape(require_proofs) && relay.valid_shape(require_proofs);
}

bool ProductPeerGrant::valid_shape() const {
  return grant_binding_shape_valid(*this) &&
         ProductPeerSecurity::nonzero_(grant_mac.data(), grant_mac.size());
}

bool ProductPeerSecurity::valid_identifier_(const std::string &value) {
  if (value.size() < 3 || value.size() > 64) return false;
  return std::all_of(value.begin(), value.end(), [](unsigned char value) {
    return std::isalnum(value) != 0 || value == '_' || value == '-';
  });
}

bool ProductPeerSecurity::valid_session_id_(const std::string &value) {
  if (value.size() < 8 || value.size() > 128) return false;
  return std::all_of(value.begin(), value.end(), [](unsigned char value) {
    return std::isalnum(value) != 0 || value == '.' || value == '_' || value == ':' || value == '-';
  });
}

bool ProductPeerSecurity::nonzero_(const uint8_t *data, std::size_t length) {
  if (data == nullptr || length == 0) return false;
  uint8_t aggregate = 0;
  for (std::size_t index = 0; index < length; ++index) aggregate |= data[index];
  return aggregate != 0;
}

bool ProductPeerSecurity::random_private_key(ProductPeerKey *private_key) {
  if (private_key == nullptr) return false;
#ifdef USE_ESP32
  esp_fill_random(private_key->data(), private_key->size());
  return nonzero_(private_key->data(), private_key->size());
#else
  return RAND_bytes(private_key->data(), static_cast<int>(private_key->size())) == 1 &&
         nonzero_(private_key->data(), private_key->size());
#endif
}

bool ProductPeerSecurity::x25519_public_key(
    const ProductPeerKey &private_key,
    ProductPeerKey *public_key) {
  if (public_key == nullptr || !nonzero_(private_key.data(), private_key.size())) return false;
#ifdef USE_ESP32
  if (psa_crypto_init() != PSA_SUCCESS) return false;
  psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
  psa_set_key_type(&attributes, PSA_KEY_TYPE_ECC_KEY_PAIR(PSA_ECC_FAMILY_MONTGOMERY));
  psa_set_key_bits(&attributes, 255);
  psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_DERIVE | PSA_KEY_USAGE_EXPORT);
  psa_set_key_algorithm(&attributes, PSA_ALG_ECDH);
  psa_key_id_t key_id = 0;
  psa_status_t status =
      psa_import_key(&attributes, private_key.data(), private_key.size(), &key_id);
  psa_reset_key_attributes(&attributes);
  if (status != PSA_SUCCESS) return false;
  std::size_t public_length = 0;
  status = psa_export_public_key(key_id, public_key->data(), public_key->size(), &public_length);
  const psa_status_t destroy_status = psa_destroy_key(key_id);
  return status == PSA_SUCCESS && destroy_status == PSA_SUCCESS &&
         public_length == public_key->size() && nonzero_(public_key->data(), public_key->size());
#else
  EVP_PKEY *key = EVP_PKEY_new_raw_private_key(
      EVP_PKEY_X25519, nullptr, private_key.data(), private_key.size());
  if (key == nullptr) return false;
  std::size_t output_length = public_key->size();
  const bool success =
      EVP_PKEY_get_raw_public_key(key, public_key->data(), &output_length) == 1 &&
      output_length == public_key->size() && nonzero_(public_key->data(), public_key->size());
  EVP_PKEY_free(key);
  return success;
#endif
}

bool ProductPeerSecurity::x25519_shared_secret(
    const ProductPeerKey &private_key,
    const ProductPeerKey &peer_public_key,
    ProductPeerKey *shared_secret) {
  if (shared_secret == nullptr || !nonzero_(private_key.data(), private_key.size()) ||
      !nonzero_(peer_public_key.data(), peer_public_key.size())) {
    return false;
  }
#ifdef USE_ESP32
  if (psa_crypto_init() != PSA_SUCCESS) return false;
  psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
  psa_set_key_type(&attributes, PSA_KEY_TYPE_ECC_KEY_PAIR(PSA_ECC_FAMILY_MONTGOMERY));
  psa_set_key_bits(&attributes, 255);
  psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_DERIVE);
  psa_set_key_algorithm(&attributes, PSA_ALG_ECDH);
  psa_key_id_t key_id = 0;
  psa_status_t status =
      psa_import_key(&attributes, private_key.data(), private_key.size(), &key_id);
  psa_reset_key_attributes(&attributes);
  if (status != PSA_SUCCESS) return false;
  std::size_t shared_length = 0;
  status = psa_raw_key_agreement(
      PSA_ALG_ECDH, key_id, peer_public_key.data(), peer_public_key.size(), shared_secret->data(),
      shared_secret->size(), &shared_length);
  const psa_status_t destroy_status = psa_destroy_key(key_id);
  if (status != PSA_SUCCESS || destroy_status != PSA_SUCCESS ||
      shared_length != shared_secret->size() || !nonzero_(shared_secret->data(), shared_secret->size())) {
    zeroize_(shared_secret->data(), shared_secret->size());
    return false;
  }
  return true;
#else
  EVP_PKEY *private_pkey = EVP_PKEY_new_raw_private_key(
      EVP_PKEY_X25519, nullptr, private_key.data(), private_key.size());
  EVP_PKEY *peer_pkey = EVP_PKEY_new_raw_public_key(
      EVP_PKEY_X25519, nullptr, peer_public_key.data(), peer_public_key.size());
  if (private_pkey == nullptr || peer_pkey == nullptr) {
    EVP_PKEY_free(private_pkey);
    EVP_PKEY_free(peer_pkey);
    return false;
  }
  EVP_PKEY_CTX *context = EVP_PKEY_CTX_new(private_pkey, nullptr);
  std::size_t shared_length = shared_secret->size();
  const bool success = context != nullptr && EVP_PKEY_derive_init(context) == 1 &&
                       EVP_PKEY_derive_set_peer(context, peer_pkey) == 1 &&
                       EVP_PKEY_derive(context, shared_secret->data(), &shared_length) == 1 &&
                       shared_length == shared_secret->size() &&
                       nonzero_(shared_secret->data(), shared_secret->size());
  EVP_PKEY_CTX_free(context);
  EVP_PKEY_free(private_pkey);
  EVP_PKEY_free(peer_pkey);
  if (!success) zeroize_(shared_secret->data(), shared_secret->size());
  return success;
#endif
}

bool ProductPeerSecurity::sha256_(
    const uint8_t *data,
    std::size_t length,
    ProductPeerKey *digest) {
  if (data == nullptr || length == 0 || digest == nullptr) return false;
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return info != nullptr && mbedtls_md(info, data, length, digest->data()) == 0;
}

bool ProductPeerSecurity::hmac_sha256_(
    const uint8_t *key,
    std::size_t key_length,
    const uint8_t *data,
    std::size_t data_length,
    ProductPeerProof *digest) {
  if (key == nullptr || key_length == 0 || data == nullptr || data_length == 0 || digest == nullptr) {
    return false;
  }
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return info != nullptr &&
         mbedtls_md_hmac(info, key, key_length, data, data_length, digest->data()) == 0;
}

bool ProductPeerSecurity::hkdf_sha256_(
    const uint8_t *ikm,
    std::size_t ikm_length,
    const uint8_t *salt,
    std::size_t salt_length,
    const uint8_t *info,
    std::size_t info_length,
    uint8_t *output,
    std::size_t output_length) {
  if (ikm == nullptr || ikm_length == 0 || info == nullptr || info_length == 0 ||
      output == nullptr || output_length == 0 || output_length > 32) {
    return false;
  }
  ProductPeerProof prk{};
  ProductPeerProof block{};
  std::array<uint8_t, 32> zero_salt{};
  const uint8_t *effective_salt = salt_length == 0 ? zero_salt.data() : salt;
  const std::size_t effective_salt_length = salt_length == 0 ? zero_salt.size() : salt_length;
  if (effective_salt == nullptr ||
      !hmac_sha256_(effective_salt, effective_salt_length, ikm, ikm_length, &prk)) {
    return false;
  }
  std::vector<uint8_t> expand_input;
  expand_input.reserve(info_length + 1);
  expand_input.insert(expand_input.end(), info, info + info_length);
  expand_input.push_back(1);
  const bool success = hmac_sha256_(
      prk.data(), prk.size(), expand_input.data(), expand_input.size(), &block);
  if (success) std::copy_n(block.begin(), output_length, output);
  zeroize_(expand_input.data(), expand_input.size());
  zeroize_(prk.data(), prk.size());
  zeroize_(block.data(), block.size());
  return success;
}

bool ProductPeerSecurity::constant_time_equal_(
    const uint8_t *left,
    const uint8_t *right,
    std::size_t length) {
  if (left == nullptr || right == nullptr || length == 0) return false;
  uint8_t difference = 0;
  for (std::size_t index = 0; index < length; ++index) difference |= left[index] ^ right[index];
  return difference == 0;
}

void ProductPeerSecurity::zeroize_(void *data, std::size_t length) {
  if (data == nullptr) return;
  volatile uint8_t *cursor = static_cast<volatile uint8_t *>(data);
  while (length-- > 0) *cursor++ = 0;
}

bool ProductPeerSecurity::encode_base64url(
    const uint8_t *data,
    std::size_t length,
    std::string *output) {
  if (data == nullptr || length == 0 || output == nullptr) return false;
  output->clear();
  output->reserve((length * 4 + 2) / 3);
  std::size_t index = 0;
  while (index + 3 <= length) {
    const uint32_t value = (static_cast<uint32_t>(data[index]) << 16U) |
                           (static_cast<uint32_t>(data[index + 1]) << 8U) |
                           static_cast<uint32_t>(data[index + 2]);
    output->push_back(kBase64Alphabet[(value >> 18U) & 0x3fU]);
    output->push_back(kBase64Alphabet[(value >> 12U) & 0x3fU]);
    output->push_back(kBase64Alphabet[(value >> 6U) & 0x3fU]);
    output->push_back(kBase64Alphabet[value & 0x3fU]);
    index += 3;
  }
  const std::size_t remaining = length - index;
  if (remaining == 1) {
    const uint32_t value = static_cast<uint32_t>(data[index]) << 16U;
    output->push_back(kBase64Alphabet[(value >> 18U) & 0x3fU]);
    output->push_back(kBase64Alphabet[(value >> 12U) & 0x3fU]);
  } else if (remaining == 2) {
    const uint32_t value = (static_cast<uint32_t>(data[index]) << 16U) |
                           (static_cast<uint32_t>(data[index + 1]) << 8U);
    output->push_back(kBase64Alphabet[(value >> 18U) & 0x3fU]);
    output->push_back(kBase64Alphabet[(value >> 12U) & 0x3fU]);
    output->push_back(kBase64Alphabet[(value >> 6U) & 0x3fU]);
  }
  return !output->empty();
}

bool ProductPeerSecurity::request_core(
    const ProductPeerRequest &request,
    std::string *output) {
  if (output == nullptr || !request.valid_shape(false)) return false;
  std::string child_public;
  std::string child_nonce;
  std::string relay_public;
  std::string relay_nonce;
  if (!encode_base64url(request.child.ephemeral_public_key.data(),
                        request.child.ephemeral_public_key.size(), &child_public) ||
      !encode_base64url(request.child.nonce.data(), request.child.nonce.size(), &child_nonce) ||
      !encode_base64url(request.relay.ephemeral_public_key.data(),
                        request.relay.ephemeral_public_key.size(), &relay_public) ||
      !encode_base64url(request.relay.nonce.data(), request.relay.nonce.size(), &relay_nonce)) {
    return false;
  }
  output->clear();
  append_field(output, kRequestDomain);
  append_field(output, request.system_id);
  append_field(output, request.session_id);
  append_u64(output, request.requested_at_ms);
  append_field(output, request.child.node_id);
  append_u32(output, request.child.credential_generation);
  append_u32(output, request.child.key_epoch);
  append_field(output, child_public);
  append_field(output, child_nonce);
  append_field(output, request.relay.node_id);
  append_u32(output, request.relay.credential_generation);
  append_u32(output, request.relay.key_epoch);
  append_field(output, relay_public);
  append_field(output, relay_nonce);
  append_u64(output, request.relay_health.observed_at_ms);
  append_field(output, request.relay_health.relay_capable ? "1" : "0");
  append_field(output, request.relay_health.low_battery ? "1" : "0");
  append_field(output, request.relay_health.overloaded ? "1" : "0");
  return true;
}

bool ProductPeerSecurity::grant_binding(
    const ProductPeerGrant &grant,
    std::string *output) {
  if (output == nullptr || !grant_binding_shape_valid(grant)) return false;
  std::string child_public;
  std::string relay_public;
  std::string child_nonce;
  std::string relay_nonce;
  if (!encode_base64url(grant.child_ephemeral_public_key.data(),
                        grant.child_ephemeral_public_key.size(), &child_public) ||
      !encode_base64url(grant.relay_ephemeral_public_key.data(),
                        grant.relay_ephemeral_public_key.size(), &relay_public) ||
      !encode_base64url(grant.child_nonce.data(), grant.child_nonce.size(), &child_nonce) ||
      !encode_base64url(grant.relay_nonce.data(), grant.relay_nonce.size(), &relay_nonce)) {
    return false;
  }
  output->clear();
  append_field(output, kGrantBindingDomain);
  append_field(output, grant.authorization_id);
  append_field(output, grant.system_id);
  append_field(output, grant.session_id);
  append_field(output, grant.child_node_id);
  append_field(output, grant.relay_node_id);
  append_u32(output, grant.child_credential_generation);
  append_u32(output, grant.relay_credential_generation);
  append_u32(output, grant.child_key_epoch);
  append_u32(output, grant.relay_key_epoch);
  append_field(output, child_public);
  append_field(output, relay_public);
  append_field(output, child_nonce);
  append_field(output, relay_nonce);
  append_u64(output, grant.issued_at_ms);
  append_u64(output, grant.expires_at_ms);
  append_u32(output, grant.authorization_epoch);
  return true;
}

bool ProductPeerSecurity::derive_relay_auth_key(
    const ProductPeerKey &application_key,
    const std::string &system_id,
    const std::string &node_id,
    uint32_t credential_generation,
    uint32_t key_epoch,
    ProductPeerKey *relay_auth_key) {
  if (relay_auth_key == nullptr || !nonzero_(application_key.data(), application_key.size()) ||
      !valid_identifier_(system_id) || !valid_identifier_(node_id) || credential_generation == 0 ||
      key_epoch == 0) {
    return false;
  }
  std::string info(kAuthKeyInfo);
  info.push_back('\0');
  info.append(system_id);
  info.push_back('\0');
  info.append(node_id);
  info.push_back('\0');
  info.append(std::to_string(credential_generation));
  info.push_back('\0');
  info.append(std::to_string(key_epoch));
  return hkdf_sha256_(
      application_key.data(), application_key.size(), nullptr, 0,
      reinterpret_cast<const uint8_t *>(info.data()), info.size(), relay_auth_key->data(),
      relay_auth_key->size());
}

bool ProductPeerSecurity::build_endpoint_proof(
    const ProductPeerRequest &request,
    ProductPeerRole role,
    const ProductPeerKey &relay_auth_key,
    ProductPeerProof *proof) {
  if (proof == nullptr || !nonzero_(relay_auth_key.data(), relay_auth_key.size())) return false;
  std::string core;
  if (!request_core(request, &core)) return false;
  std::string message(kProofDomain);
  message.push_back('\0');
  message.append(role_name(role));
  message.push_back('\0');
  message.append(core);
  return hmac_sha256_(
      relay_auth_key.data(), relay_auth_key.size(),
      reinterpret_cast<const uint8_t *>(message.data()), message.size(), proof);
}

bool ProductPeerSecurity::verify_endpoint_grant(
    const ProductPeerGrant &grant,
    const ProductPeerKey &relay_auth_key,
    uint64_t now_ms) {
  if (!grant.valid_shape() || !nonzero_(relay_auth_key.data(), relay_auth_key.size()) ||
      now_ms < grant.issued_at_ms || now_ms >= grant.expires_at_ms) {
    return false;
  }
  std::string binding;
  if (!grant_binding(grant, &binding)) return false;
  std::string message(kGrantDomain);
  message.push_back('\0');
  message.append(role_name(grant.role));
  message.push_back('\0');
  message.append(binding);
  ProductPeerProof expected{};
  const bool built = hmac_sha256_(
      relay_auth_key.data(), relay_auth_key.size(),
      reinterpret_cast<const uint8_t *>(message.data()), message.size(), &expected);
  const bool matches =
      built && constant_time_equal_(expected.data(), grant.grant_mac.data(), expected.size());
  zeroize_(expected.data(), expected.size());
  return matches;
}

bool ProductPeerSecurity::derive_pair_lmk(
    const ProductPeerKey &local_private_key,
    const ProductPeerKey &peer_public_key,
    const ProductPeerGrant &grant,
    LinkKey *lmk) {
  if (lmk == nullptr) return false;
  std::string binding;
  if (!grant_binding(grant, &binding)) return false;
  ProductPeerKey shared{};
  ProductPeerKey salt{};
  std::string salt_input(kLmkDomain);
  salt_input.append("\0salt\0", 6);
  salt_input.append(binding);
  if (!x25519_shared_secret(local_private_key, peer_public_key, &shared) ||
      !sha256_(reinterpret_cast<const uint8_t *>(salt_input.data()), salt_input.size(), &salt)) {
    zeroize_(shared.data(), shared.size());
    zeroize_(salt.data(), salt.size());
    return false;
  }
  std::string info(kLmkDomain);
  info.append("\0derive\0", 8);
  info.append(binding);
  const bool success = hkdf_sha256_(
      shared.data(), shared.size(), salt.data(), salt.size(),
      reinterpret_cast<const uint8_t *>(info.data()), info.size(), lmk->data(), lmk->size());
  zeroize_(shared.data(), shared.size());
  zeroize_(salt.data(), salt.size());
  if (!success || !nonzero_(lmk->data(), lmk->size())) {
    zeroize_(lmk->data(), lmk->size());
    return false;
  }
  return true;
}

}  // namespace esphome::greenhouse_n3w_product_runtime
