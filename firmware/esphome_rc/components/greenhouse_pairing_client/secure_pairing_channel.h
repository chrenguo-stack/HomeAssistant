#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace esphome::greenhouse_pairing_client {

static constexpr const char *SECURE_CIPHER_SUITE =
    "X25519-HKDF-SHA256-CHACHA20-POLY1305";
static constexpr const char *SECURE_OFFER_SCHEMA = "gh.pair.secure-offer/1";
static constexpr const char *ESTABLISH_SCHEMA = "gh.pair.establish/1";
static constexpr const char *ENVELOPE_SCHEMA = "gh.pair.envelope/1";
static constexpr const char *CREDENTIALS_CONTENT_TYPE = "gh.pair.credentials/1";
static constexpr const char *ACK_CONTENT_TYPE = "gh.pair.delivery-ack/1";
static constexpr const char *MANAGER_TO_NODE_DIRECTION = "manager_to_node";
static constexpr const char *NODE_TO_MANAGER_DIRECTION = "node_to_manager";

struct SecureOfferDocument {
  std::string schema;
  std::string session_id;
  std::string hardware_id;
  std::string pairing_id;
  std::string manager_nonce;
  std::string manager_public_key;
  std::string cipher_suite;
  std::string expires_at;
  uint8_t max_proof_attempts{0};
};

struct SecureEnvelopeDocument {
  std::string schema;
  std::string session_id;
  std::string direction;
  uint64_t sequence{0};
  std::string content_type;
  std::string nonce;
  std::string ciphertext;
};

struct SecurePairingMaterialSnapshot {
  bool established{false};
  uint64_t send_sequence{0};
  uint64_t receive_sequence{0};
  std::string node_nonce;
  std::string node_public_key;
  std::string secure_proof;
};

class SecurePairingChannel {
 public:
  SecurePairingChannel() = default;
  ~SecurePairingChannel();

  SecurePairingChannel(const SecurePairingChannel &) = delete;
  SecurePairingChannel &operator=(const SecurePairingChannel &) = delete;

  bool establish(const SecureOfferDocument &offer, const std::string &pairing_secret);
  bool establish_for_test(const SecureOfferDocument &offer, const std::string &pairing_secret,
                          const std::array<uint8_t, 32> &node_private_key,
                          const std::array<uint8_t, 32> &node_nonce);

  bool decrypt(const SecureEnvelopeDocument &envelope, const std::string &expected_content_type,
               std::string *plaintext);
  bool encrypt(const std::string &plaintext, const std::string &content_type,
               SecureEnvelopeDocument *envelope);

  std::string build_establish_request_json() const;
  SecurePairingMaterialSnapshot snapshot() const;
  void clear();

  const std::string &session_id() const { return this->session_id_; }
  const std::string &node_nonce() const { return this->node_nonce_; }
  const std::string &node_public_key() const { return this->node_public_key_; }
  const std::string &secure_proof() const { return this->secure_proof_; }

  static bool validate_offer(const SecureOfferDocument &offer);
  static bool validate_envelope_shape(const SecureEnvelopeDocument &envelope);
  static std::string secure_proof_transcript(const SecureOfferDocument &offer,
                                             const std::string &node_nonce,
                                             const std::string &node_public_key);
  static std::string envelope_aad(const std::string &session_id, const std::string &direction,
                                  uint64_t sequence, const std::string &content_type);
  static std::array<uint8_t, 12> envelope_nonce(const std::string &direction, uint64_t sequence,
                                                 bool *valid = nullptr);
  static std::string json_escape(const std::string &value);
  static bool encode_base64url(const uint8_t *data, size_t length, std::string *output);
  static bool decode_base64url(const std::string &value, std::vector<uint8_t> *output);
  static bool decode_base64url_32(const std::string &value, std::array<uint8_t, 32> *output);

 protected:
  bool establish_impl_(const SecureOfferDocument &offer, const std::string &pairing_secret,
                       const std::array<uint8_t, 32> &node_private_key,
                       const std::array<uint8_t, 32> &node_nonce);

  static bool random_bytes_(uint8_t *output, size_t length);
  static bool x25519_(const std::array<uint8_t, 32> &private_key,
                      const std::array<uint8_t, 32> &peer_public_key,
                      std::array<uint8_t, 32> *public_key,
                      std::array<uint8_t, 32> *shared_secret);
  static bool sha256_(const uint8_t *data, size_t length, std::array<uint8_t, 32> *digest);
  static bool hmac_sha256_(const uint8_t *key, size_t key_length, const uint8_t *data,
                           size_t data_length, std::array<uint8_t, 32> *digest);
  static bool hkdf_sha256_64_(const std::array<uint8_t, 32> &shared_secret,
                              const std::array<uint8_t, 32> &salt,
                              const std::vector<uint8_t> &info,
                              std::array<uint8_t, 64> *material);
  static bool aead_encrypt_(const std::array<uint8_t, 32> &key,
                            const std::array<uint8_t, 12> &nonce, const std::string &aad,
                            const std::string &plaintext, std::vector<uint8_t> *ciphertext);
  static bool aead_decrypt_(const std::array<uint8_t, 32> &key,
                            const std::array<uint8_t, 12> &nonce, const std::string &aad,
                            const std::vector<uint8_t> &ciphertext, std::string *plaintext);
  static void zeroize_(void *data, size_t length);

  bool established_{false};
  std::string session_id_;
  std::string node_nonce_;
  std::string node_public_key_;
  std::string secure_proof_;
  std::array<uint8_t, 32> manager_to_node_key_{};
  std::array<uint8_t, 32> node_to_manager_key_{};
  uint64_t send_sequence_{0};
  uint64_t receive_sequence_{0};
};

}  // namespace esphome::greenhouse_pairing_client
