#include "pairing_persistence_crypto.h"

#include <algorithm>
#include <array>
#include <cstring>

#ifdef USE_ESP32
#include "esp_err.h"
#include "esp_hmac.h"
#include "esp_random.h"
#include "mbedtls/chachapoly.h"
#include "mbedtls/md.h"
#else
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/rand.h>
#endif

namespace esphome::greenhouse_pairing_client {

namespace {

constexpr std::array<uint8_t, 4> ENVELOPE_MAGIC = {'G', 'H', 'P', '1'};
constexpr size_t HEADER_BYTES = 60;

void put_u16(std::vector<uint8_t> *output, uint16_t value) {
  output->push_back(static_cast<uint8_t>((value >> 8) & 0xffU));
  output->push_back(static_cast<uint8_t>(value & 0xffU));
}

void put_u32(std::vector<uint8_t> *output, uint32_t value) {
  output->push_back(static_cast<uint8_t>((value >> 24) & 0xffU));
  output->push_back(static_cast<uint8_t>((value >> 16) & 0xffU));
  output->push_back(static_cast<uint8_t>((value >> 8) & 0xffU));
  output->push_back(static_cast<uint8_t>(value & 0xffU));
}

uint16_t read_u16(const uint8_t *data) {
  return static_cast<uint16_t>(
      (static_cast<uint16_t>(data[0]) << 8) |
      static_cast<uint16_t>(data[1]));
}

uint32_t read_u32(const uint8_t *data) {
  return (static_cast<uint32_t>(data[0]) << 24) |
         (static_cast<uint32_t>(data[1]) << 16) |
         (static_cast<uint32_t>(data[2]) << 8) |
         static_cast<uint32_t>(data[3]);
}

bool valid_slot(CredentialSlot slot) {
  return slot == CredentialSlot::A || slot == CredentialSlot::B;
}

bool valid_state(CredentialRecordState state) {
  return state == CredentialRecordState::PREPARED ||
         state == CredentialRecordState::COMMITTED;
}

void clear_bytes(std::vector<uint8_t> *value) {
  if (value == nullptr)
    return;
  PairingPersistenceCrypto::zeroize(value->data(), value->size());
  value->clear();
  value->shrink_to_fit();
}

void clear_metadata(PersistenceEnvelopeMetadata *metadata) {
  if (metadata == nullptr)
    return;
  PairingPersistenceCrypto::zeroize(metadata->digest.data(),
                                    metadata->digest.size());
  *metadata = {};
}

void clear_key(std::array<uint8_t, 32> *key) {
  if (key != nullptr)
    PairingPersistenceCrypto::zeroize(key->data(), key->size());
}

}  // namespace

FixedPersistenceKeyProvider::FixedPersistenceKeyProvider(
    const std::array<uint8_t, 32> &key)
    : key_(key) {}

FixedPersistenceKeyProvider::~FixedPersistenceKeyProvider() {
  PairingPersistenceCrypto::zeroize(this->key_.data(), this->key_.size());
}

bool FixedPersistenceKeyProvider::derive_key(
    CredentialSlot slot, uint32_t generation, std::array<uint8_t, 32> *key) {
  if (key == nullptr)
    return false;
  clear_key(key);
  if (!valid_slot(slot) || generation == 0)
    return false;
  *key = this->key_;
  return true;
}

#ifdef USE_ESP32
bool EfuseHmacPersistenceKeyProvider::derive_key(
    CredentialSlot slot, uint32_t generation, std::array<uint8_t, 32> *key) {
  if (key == nullptr)
    return false;
  clear_key(key);
  if (!valid_slot(slot) || generation == 0 || this->key_id_ > 5)
    return false;

  std::array<uint8_t, 24> context{};
  constexpr std::array<uint8_t, 15> DOMAIN = {
      'g', 'h', '-', 'p', 'e', 'r', 's', 'i',
      's', 't', '-', 'v', '1', 0, 0};
  std::copy(DOMAIN.begin(), DOMAIN.end(), context.begin());
  context[16] = static_cast<uint8_t>(slot);
  context[17] = static_cast<uint8_t>((generation >> 24) & 0xffU);
  context[18] = static_cast<uint8_t>((generation >> 16) & 0xffU);
  context[19] = static_cast<uint8_t>((generation >> 8) & 0xffU);
  context[20] = static_cast<uint8_t>(generation & 0xffU);

  const esp_err_t status = esp_hmac_calculate(
      static_cast<hmac_key_id_t>(this->key_id_), context.data(),
      context.size(), key->data());
  PairingPersistenceCrypto::zeroize(context.data(), context.size());
  if (status != ESP_OK) {
    clear_key(key);
    return false;
  }
  return true;
}
#endif

bool PairingPersistenceCrypto::seal(
    CredentialSlot slot, CredentialRecordState state, uint32_t generation,
    const std::vector<uint8_t> &plaintext, std::vector<uint8_t> *envelope) {
  if (envelope == nullptr)
    return false;
  clear_bytes(envelope);
  if (this->key_provider_ == nullptr || !valid_slot(slot) ||
      !valid_state(state) || generation == 0 || plaintext.empty() ||
      plaintext.size() > PERSISTENCE_MAX_PLAINTEXT_BYTES)
    return false;

  std::array<uint8_t, 32> record_key{};
  std::array<uint8_t, 32> encryption_key{};
  std::array<uint8_t, 32> digest_key{};
  std::array<uint8_t, 12> nonce{};
  std::array<uint8_t, 32> digest{};
  if (!this->key_provider_->derive_key(slot, generation, &record_key) ||
      !derive_subkey_(record_key, "gh-persist-encryption-v1", &encryption_key) ||
      !derive_subkey_(record_key, "gh-persist-digest-v1", &digest_key) ||
      !random_bytes_(nonce.data(), nonce.size()) ||
      !hmac_sha256_(digest_key.data(), digest_key.size(), plaintext.data(),
                    plaintext.size(), &digest)) {
    zeroize(record_key.data(), record_key.size());
    zeroize(encryption_key.data(), encryption_key.size());
    zeroize(digest_key.data(), digest_key.size());
    zeroize(nonce.data(), nonce.size());
    zeroize(digest.data(), digest.size());
    return false;
  }

  std::vector<uint8_t> header;
  header.reserve(HEADER_BYTES);
  header.insert(header.end(), ENVELOPE_MAGIC.begin(), ENVELOPE_MAGIC.end());
  put_u16(&header, PERSISTENCE_ENVELOPE_SCHEMA_VERSION);
  header.push_back(static_cast<uint8_t>(slot));
  header.push_back(static_cast<uint8_t>(state));
  put_u32(&header, generation);
  put_u32(&header, static_cast<uint32_t>(plaintext.size()));
  header.insert(header.end(), digest.begin(), digest.end());
  header.insert(header.end(), nonce.begin(), nonce.end());
  if (header.size() != HEADER_BYTES) {
    zeroize(record_key.data(), record_key.size());
    zeroize(encryption_key.data(), encryption_key.size());
    zeroize(digest_key.data(), digest_key.size());
    zeroize(nonce.data(), nonce.size());
    zeroize(digest.data(), digest.size());
    clear_bytes(&header);
    return false;
  }

  std::vector<uint8_t> ciphertext;
  const bool success =
      aead_encrypt_(encryption_key, nonce, header.data(), header.size(),
                    plaintext, &ciphertext) &&
      ciphertext.size() == plaintext.size() + PERSISTENCE_TAG_BYTES;
  if (success) {
    envelope->reserve(header.size() + ciphertext.size());
    envelope->insert(envelope->end(), header.begin(), header.end());
    envelope->insert(envelope->end(), ciphertext.begin(), ciphertext.end());
  }

  zeroize(record_key.data(), record_key.size());
  zeroize(encryption_key.data(), encryption_key.size());
  zeroize(digest_key.data(), digest_key.size());
  zeroize(nonce.data(), nonce.size());
  zeroize(digest.data(), digest.size());
  clear_bytes(&header);
  clear_bytes(&ciphertext);
  if (!success)
    clear_bytes(envelope);
  return success;
}

bool PairingPersistenceCrypto::inspect(
    const std::vector<uint8_t> &envelope,
    PersistenceEnvelopeMetadata *metadata) {
  if (metadata == nullptr)
    return false;
  clear_metadata(metadata);
  if (envelope.size() < HEADER_BYTES + PERSISTENCE_TAG_BYTES ||
      !std::equal(ENVELOPE_MAGIC.begin(), ENVELOPE_MAGIC.end(),
                  envelope.begin()) ||
      read_u16(envelope.data() + 4) !=
          PERSISTENCE_ENVELOPE_SCHEMA_VERSION)
    return false;

  PersistenceEnvelopeMetadata parsed{};
  parsed.slot = static_cast<CredentialSlot>(envelope[6]);
  parsed.state = static_cast<CredentialRecordState>(envelope[7]);
  parsed.generation = read_u32(envelope.data() + 8);
  parsed.plaintext_size = read_u32(envelope.data() + 12);
  std::copy_n(envelope.data() + 16, parsed.digest.size(),
              parsed.digest.begin());

  if (!valid_slot(parsed.slot) || !valid_state(parsed.state) ||
      parsed.generation == 0 || parsed.plaintext_size == 0 ||
      parsed.plaintext_size > PERSISTENCE_MAX_PLAINTEXT_BYTES ||
      envelope.size() !=
          HEADER_BYTES + parsed.plaintext_size + PERSISTENCE_TAG_BYTES) {
    zeroize(parsed.digest.data(), parsed.digest.size());
    return false;
  }
  *metadata = parsed;
  zeroize(parsed.digest.data(), parsed.digest.size());
  return true;
}

bool PairingPersistenceCrypto::open(
    const std::vector<uint8_t> &envelope,
    PersistenceEnvelopeMetadata *metadata,
    std::vector<uint8_t> *plaintext) {
  if (metadata != nullptr)
    clear_metadata(metadata);
  if (plaintext != nullptr)
    clear_bytes(plaintext);
  if (this->key_provider_ == nullptr || metadata == nullptr ||
      plaintext == nullptr)
    return false;

  PersistenceEnvelopeMetadata parsed{};
  if (!inspect(envelope, &parsed))
    return false;

  std::array<uint8_t, 32> record_key{};
  std::array<uint8_t, 32> encryption_key{};
  std::array<uint8_t, 32> digest_key{};
  std::array<uint8_t, 12> nonce{};
  std::copy_n(envelope.data() + 48, nonce.size(), nonce.begin());
  if (!this->key_provider_->derive_key(parsed.slot, parsed.generation,
                                       &record_key) ||
      !derive_subkey_(record_key, "gh-persist-encryption-v1", &encryption_key) ||
      !derive_subkey_(record_key, "gh-persist-digest-v1", &digest_key)) {
    zeroize(record_key.data(), record_key.size());
    zeroize(encryption_key.data(), encryption_key.size());
    zeroize(digest_key.data(), digest_key.size());
    zeroize(nonce.data(), nonce.size());
    zeroize(parsed.digest.data(), parsed.digest.size());
    return false;
  }

  const uint8_t *ciphertext = envelope.data() + HEADER_BYTES;
  const size_t ciphertext_length = envelope.size() - HEADER_BYTES;
  bool success = aead_decrypt_(
      encryption_key, nonce, envelope.data(), HEADER_BYTES, ciphertext,
      ciphertext_length, plaintext);
  std::array<uint8_t, 32> digest{};
  if (success)
    success = hmac_sha256_(digest_key.data(), digest_key.size(),
                           plaintext->data(), plaintext->size(), &digest) &&
              constant_time_equal_(digest.data(), parsed.digest.data(),
                                   digest.size());

  zeroize(record_key.data(), record_key.size());
  zeroize(encryption_key.data(), encryption_key.size());
  zeroize(digest_key.data(), digest_key.size());
  zeroize(nonce.data(), nonce.size());
  zeroize(digest.data(), digest.size());
  if (!success) {
    clear_bytes(plaintext);
    zeroize(parsed.digest.data(), parsed.digest.size());
    return false;
  }
  *metadata = parsed;
  zeroize(parsed.digest.data(), parsed.digest.size());
  return true;
}

bool PairingPersistenceCrypto::random_bytes_(uint8_t *output, size_t length) {
  if (output == nullptr || length == 0)
    return false;
#ifdef USE_ESP32
  esp_fill_random(output, length);
  return true;
#else
  return RAND_bytes(output, static_cast<int>(length)) == 1;
#endif
}

bool PairingPersistenceCrypto::hmac_sha256_(
    const uint8_t *key, size_t key_length, const uint8_t *data,
    size_t data_length, std::array<uint8_t, 32> *digest) {
  if (digest == nullptr)
    return false;
  clear_key(digest);
  if (key == nullptr || key_length == 0 || data == nullptr ||
      data_length == 0)
    return false;
#ifdef USE_ESP32
  const mbedtls_md_info_t *info =
      mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  const bool success =
      info != nullptr &&
      mbedtls_md_hmac(info, key, key_length, data, data_length,
                      digest->data()) == 0;
#else
  unsigned int written = 0;
  const bool success =
      HMAC(EVP_sha256(), key, static_cast<int>(key_length), data,
           data_length, digest->data(), &written) != nullptr &&
      written == digest->size();
#endif
  if (!success)
    clear_key(digest);
  return success;
}

bool PairingPersistenceCrypto::derive_subkey_(
    const std::array<uint8_t, 32> &record_key, const char *label,
    std::array<uint8_t, 32> *subkey) {
  if (subkey == nullptr)
    return false;
  clear_key(subkey);
  if (label == nullptr)
    return false;
  const size_t label_length = std::strlen(label);
  return label_length > 0 &&
         hmac_sha256_(record_key.data(), record_key.size(),
                      reinterpret_cast<const uint8_t *>(label), label_length,
                      subkey);
}

bool PairingPersistenceCrypto::aead_encrypt_(
    const std::array<uint8_t, 32> &key,
    const std::array<uint8_t, 12> &nonce, const uint8_t *aad,
    size_t aad_length, const std::vector<uint8_t> &plaintext,
    std::vector<uint8_t> *ciphertext) {
  if (ciphertext == nullptr)
    return false;
  clear_bytes(ciphertext);
  if (aad == nullptr || plaintext.empty())
    return false;
  ciphertext->assign(plaintext.size() + PERSISTENCE_TAG_BYTES, 0);
#ifdef USE_ESP32
  mbedtls_chachapoly_context context;
  mbedtls_chachapoly_init(&context);
  int result = mbedtls_chachapoly_setkey(&context, key.data());
  if (result == 0)
    result = mbedtls_chachapoly_encrypt_and_tag(
        &context, plaintext.size(), nonce.data(), aad, aad_length,
        plaintext.data(), ciphertext->data(),
        ciphertext->data() + plaintext.size());
  mbedtls_chachapoly_free(&context);
  if (result != 0) {
    clear_bytes(ciphertext);
    return false;
  }
  return true;
#else
  EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
  if (context == nullptr) {
    clear_bytes(ciphertext);
    return false;
  }
  int written = 0;
  int total = 0;
  bool success =
      EVP_EncryptInit_ex(context, EVP_chacha20_poly1305(), nullptr, nullptr,
                         nullptr) == 1 &&
      EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_SET_IVLEN, nonce.size(),
                          nullptr) == 1 &&
      EVP_EncryptInit_ex(context, nullptr, nullptr, key.data(),
                         nonce.data()) == 1 &&
      EVP_EncryptUpdate(context, nullptr, &written, aad,
                        static_cast<int>(aad_length)) == 1 &&
      EVP_EncryptUpdate(context, ciphertext->data(), &written,
                        plaintext.data(),
                        static_cast<int>(plaintext.size())) == 1;
  if (success)
    total = written;
  if (success)
    success = EVP_EncryptFinal_ex(context, ciphertext->data() + total,
                                  &written) == 1;
  if (success)
    total += written;
  if (success)
    success = EVP_CIPHER_CTX_ctrl(
                  context, EVP_CTRL_AEAD_GET_TAG, PERSISTENCE_TAG_BYTES,
                  ciphertext->data() + plaintext.size()) == 1;
  EVP_CIPHER_CTX_free(context);
  if (!success || static_cast<size_t>(total) != plaintext.size()) {
    clear_bytes(ciphertext);
    return false;
  }
  return true;
#endif
}

bool PairingPersistenceCrypto::aead_decrypt_(
    const std::array<uint8_t, 32> &key,
    const std::array<uint8_t, 12> &nonce, const uint8_t *aad,
    size_t aad_length, const uint8_t *ciphertext,
    size_t ciphertext_length, std::vector<uint8_t> *plaintext) {
  if (plaintext == nullptr)
    return false;
  clear_bytes(plaintext);
  if (aad == nullptr || ciphertext == nullptr ||
      ciphertext_length <= PERSISTENCE_TAG_BYTES)
    return false;
  const size_t body_length = ciphertext_length - PERSISTENCE_TAG_BYTES;
  plaintext->assign(body_length, 0);
#ifdef USE_ESP32
  mbedtls_chachapoly_context context;
  mbedtls_chachapoly_init(&context);
  int result = mbedtls_chachapoly_setkey(&context, key.data());
  if (result == 0)
    result = mbedtls_chachapoly_auth_decrypt(
        &context, body_length, nonce.data(), aad, aad_length,
        ciphertext + body_length, ciphertext, plaintext->data());
  mbedtls_chachapoly_free(&context);
  if (result != 0) {
    clear_bytes(plaintext);
    return false;
  }
  return true;
#else
  EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
  if (context == nullptr) {
    clear_bytes(plaintext);
    return false;
  }
  int written = 0;
  int total = 0;
  bool success =
      EVP_DecryptInit_ex(context, EVP_chacha20_poly1305(), nullptr, nullptr,
                         nullptr) == 1 &&
      EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_SET_IVLEN, nonce.size(),
                          nullptr) == 1 &&
      EVP_DecryptInit_ex(context, nullptr, nullptr, key.data(),
                         nonce.data()) == 1 &&
      EVP_DecryptUpdate(context, nullptr, &written, aad,
                        static_cast<int>(aad_length)) == 1 &&
      EVP_DecryptUpdate(context, plaintext->data(), &written, ciphertext,
                        static_cast<int>(body_length)) == 1;
  if (success)
    total = written;
  if (success)
    success = EVP_CIPHER_CTX_ctrl(
                  context, EVP_CTRL_AEAD_SET_TAG, PERSISTENCE_TAG_BYTES,
                  const_cast<uint8_t *>(ciphertext + body_length)) == 1;
  if (success)
    success = EVP_DecryptFinal_ex(context, plaintext->data() + total,
                                  &written) == 1;
  if (success)
    total += written;
  EVP_CIPHER_CTX_free(context);
  if (!success || static_cast<size_t>(total) != body_length) {
    clear_bytes(plaintext);
    return false;
  }
  return true;
#endif
}

bool PairingPersistenceCrypto::constant_time_equal_(
    const uint8_t *left, const uint8_t *right, size_t length) {
  if (left == nullptr || right == nullptr)
    return false;
  uint8_t difference = 0;
  for (size_t index = 0; index < length; index++)
    difference |= left[index] ^ right[index];
  return difference == 0;
}

void PairingPersistenceCrypto::zeroize(void *data, size_t length) {
  if (data == nullptr)
    return;
  volatile uint8_t *pointer = static_cast<volatile uint8_t *>(data);
  while (length-- > 0)
    *pointer++ = 0;
}

}  // namespace esphome::greenhouse_pairing_client
