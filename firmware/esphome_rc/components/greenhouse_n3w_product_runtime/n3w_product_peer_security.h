#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

#include "esphome/components/greenhouse_n3w_core/n3w_radio.h"

namespace esphome::greenhouse_n3w_product_runtime {

constexpr std::size_t kProductPeerKeyBytes = 32;
constexpr std::size_t kProductPeerNonceBytes = 32;
constexpr std::size_t kProductPeerProofBytes = 32;

using ProductPeerKey = std::array<uint8_t, kProductPeerKeyBytes>;
using ProductPeerNonce = std::array<uint8_t, kProductPeerNonceBytes>;
using ProductPeerProof = std::array<uint8_t, kProductPeerProofBytes>;
using greenhouse_n3w_core::LinkKey;

enum class ProductPeerRole : uint8_t {
  CHILD = 0,
  RELAY = 1,
};

struct ProductPeerEndpoint {
  std::string node_id;
  uint32_t credential_generation{0};
  uint32_t key_epoch{0};
  ProductPeerKey ephemeral_public_key{};
  ProductPeerNonce nonce{};
  ProductPeerProof proof{};

  bool valid_shape(bool require_proof = true) const;
};

struct ProductRelayHealth {
  uint64_t observed_at_ms{0};
  bool relay_capable{false};
  bool low_battery{false};
  bool overloaded{false};
};

struct ProductPeerRequest {
  std::string system_id;
  std::string session_id;
  uint64_t requested_at_ms{0};
  ProductPeerEndpoint child{};
  ProductPeerEndpoint relay{};
  ProductRelayHealth relay_health{};

  bool valid_shape(bool require_proofs = true) const;
};

struct ProductPeerGrant {
  ProductPeerRole role{ProductPeerRole::CHILD};
  std::string authorization_id;
  std::string system_id;
  std::string session_id;
  std::string child_node_id;
  std::string relay_node_id;
  uint32_t child_credential_generation{0};
  uint32_t relay_credential_generation{0};
  uint32_t child_key_epoch{0};
  uint32_t relay_key_epoch{0};
  ProductPeerKey child_ephemeral_public_key{};
  ProductPeerKey relay_ephemeral_public_key{};
  ProductPeerNonce child_nonce{};
  ProductPeerNonce relay_nonce{};
  uint64_t issued_at_ms{0};
  uint64_t expires_at_ms{0};
  uint32_t authorization_epoch{0};
  ProductPeerProof grant_mac{};

  bool valid_shape() const;
};

class ProductPeerSecurity {
 public:
  static bool random_private_key(ProductPeerKey *private_key);
  static bool x25519_public_key(
      const ProductPeerKey &private_key,
      ProductPeerKey *public_key);
  static bool x25519_shared_secret(
      const ProductPeerKey &private_key,
      const ProductPeerKey &peer_public_key,
      ProductPeerKey *shared_secret);

  static bool derive_relay_auth_key(
      const ProductPeerKey &application_key,
      const std::string &system_id,
      const std::string &node_id,
      uint32_t credential_generation,
      uint32_t key_epoch,
      ProductPeerKey *relay_auth_key);

  static bool build_endpoint_proof(
      const ProductPeerRequest &request,
      ProductPeerRole role,
      const ProductPeerKey &relay_auth_key,
      ProductPeerProof *proof);

  static bool verify_endpoint_grant(
      const ProductPeerGrant &grant,
      const ProductPeerKey &relay_auth_key,
      uint64_t now_ms);

  static bool derive_pair_lmk(
      const ProductPeerKey &local_private_key,
      const ProductPeerKey &peer_public_key,
      const ProductPeerGrant &grant,
      LinkKey *lmk);

  static bool request_core(const ProductPeerRequest &request, std::string *output);
  static bool grant_binding(const ProductPeerGrant &grant, std::string *output);
  static bool encode_base64url(const uint8_t *data, std::size_t length, std::string *output);

 private:
  static bool valid_identifier_(const std::string &value);
  static bool valid_session_id_(const std::string &value);
  static bool nonzero_(const uint8_t *data, std::size_t length);
  static bool sha256_(const uint8_t *data, std::size_t length, ProductPeerKey *digest);
  static bool hmac_sha256_(
      const uint8_t *key,
      std::size_t key_length,
      const uint8_t *data,
      std::size_t data_length,
      ProductPeerProof *digest);
  static bool hkdf_sha256_(
      const uint8_t *ikm,
      std::size_t ikm_length,
      const uint8_t *salt,
      std::size_t salt_length,
      const uint8_t *info,
      std::size_t info_length,
      uint8_t *output,
      std::size_t output_length);
  static bool constant_time_equal_(
      const uint8_t *left,
      const uint8_t *right,
      std::size_t length);
  static void zeroize_(void *data, std::size_t length);
};

}  // namespace esphome::greenhouse_n3w_product_runtime
