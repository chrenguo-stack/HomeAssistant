#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

#include "pairing_persistence_contract.h"

namespace esphome::greenhouse_pairing_client {

static constexpr uint16_t PERSISTENCE_ENVELOPE_SCHEMA_VERSION = 1;
static constexpr size_t PERSISTENCE_NONCE_BYTES = 12;
static constexpr size_t PERSISTENCE_DIGEST_BYTES = 32;
static constexpr size_t PERSISTENCE_TAG_BYTES = 16;
static constexpr size_t PERSISTENCE_MAX_PLAINTEXT_BYTES = 12288;

struct PersistenceEnvelopeMetadata {
  CredentialSlot slot{CredentialSlot::NONE};
  CredentialRecordState state{CredentialRecordState::INVALID};
  uint32_t generation{0};
  uint32_t plaintext_size{0};
  std::array<uint8_t, PERSISTENCE_DIGEST_BYTES> digest{};
};

class PersistenceKeyProvider {
 public:
  virtual ~PersistenceKeyProvider() = default;
  virtual bool derive_key(CredentialSlot slot, uint32_t generation,
                          std::array<uint8_t, 32> *key) = 0;
};

class FixedPersistenceKeyProvider final : public PersistenceKeyProvider {
 public:
  explicit FixedPersistenceKeyProvider(const std::array<uint8_t, 32> &key);
  ~FixedPersistenceKeyProvider() override;

  FixedPersistenceKeyProvider(const FixedPersistenceKeyProvider &) = delete;
  FixedPersistenceKeyProvider &operator=(
      const FixedPersistenceKeyProvider &) = delete;

  bool derive_key(CredentialSlot slot, uint32_t generation,
                  std::array<uint8_t, 32> *key) override;

 private:
  std::array<uint8_t, 32> key_{};
};

#ifdef USE_ESP32
class EfuseHmacPersistenceKeyProvider final : public PersistenceKeyProvider {
 public:
  explicit EfuseHmacPersistenceKeyProvider(uint8_t key_id) : key_id_(key_id) {}

  bool derive_key(CredentialSlot slot, uint32_t generation,
                  std::array<uint8_t, 32> *key) override;

 private:
  uint8_t key_id_{0};
};
#endif

class PairingPersistenceCrypto {
 public:
  explicit PairingPersistenceCrypto(PersistenceKeyProvider *key_provider)
      : key_provider_(key_provider) {}

  bool seal(CredentialSlot slot, CredentialRecordState state,
            uint32_t generation, const std::vector<uint8_t> &plaintext,
            std::vector<uint8_t> *envelope);
  bool open(const std::vector<uint8_t> &envelope,
            PersistenceEnvelopeMetadata *metadata,
            std::vector<uint8_t> *plaintext);

  static bool inspect(const std::vector<uint8_t> &envelope,
                      PersistenceEnvelopeMetadata *metadata);
  static void zeroize(void *data, size_t length);

 private:
  static bool random_bytes_(uint8_t *output, size_t length);
  static bool sha256_(const uint8_t *data, size_t length,
                      std::array<uint8_t, 32> *digest);
  static bool aead_encrypt_(const std::array<uint8_t, 32> &key,
                            const std::array<uint8_t, 12> &nonce,
                            const uint8_t *aad, size_t aad_length,
                            const std::vector<uint8_t> &plaintext,
                            std::vector<uint8_t> *ciphertext);
  static bool aead_decrypt_(const std::array<uint8_t, 32> &key,
                            const std::array<uint8_t, 12> &nonce,
                            const uint8_t *aad, size_t aad_length,
                            const uint8_t *ciphertext,
                            size_t ciphertext_length,
                            std::vector<uint8_t> *plaintext);
  static bool constant_time_equal_(const uint8_t *left, const uint8_t *right,
                                   size_t length);

  PersistenceKeyProvider *key_provider_{nullptr};
};

}  // namespace esphome::greenhouse_pairing_client
