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

}  // namespace

FixedPersistenceKeyProvider::FixedPersistenceKeyProvider(
    const std::array<uint8_t, 32> &key)
    : key_(key) {}

FixedPersistenceKeyProvider::~FixedPersistenceKeyProvider() {
  PairingPersistenceCrypto::zeroize(this->key_.data(), this->key_.size());
}

bool FixedPersistenceKeyProvider::derive_key(
    CredentialSlot slot, uint32_t generation, std::array<uint8_t, 32> *key) {
  if (key == nullptr || !valid_slot(slot) || generation == 0)
    return false;
  *key = this->key_;
  return true;
}

#ifdef USE_ESP32
bool EfuseHmacPersistenceKeyProvider::derive_key(
    CredentialSlot slot, uint32_t generation, std::array<uint8_t, 32> *key) {
  if (key == nullptr || !valid_slot(slot) || generation == 0 ||
      this->key_id_ > 5)
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
    PairingPersistenceCrypto::zeroize(key->data(), key->size());
    return false;
  }
  return true;
}
#endif

bool PairingPersistenceCrypto::seal(
    CredentialSlot slot, CredentialRecordState state, uint32_t generation,
    const std::vector<uint8_t> &plaintext, std::vector<uint8_t> *envelope) {
  if (this->key_provider_ == nullptr || envelope == nullptr ||
      !valid_slot(slot) || !valid_state(state) || generation == 0 ||
      plaintext.empty() ||
      plaintext.size() > PERSISTENCE_MAX_PLAINTEXT_BYTES)
    return false;

  std::fill(envelope->begin(), envelope->end(), 0);
  envelope->clear();

  std::array<uint8_t, 32> key{};
  std::array<uint8_t, 12> nonce{};
  std::array<uint8_t, 32> digest{};
  if (!this->key_provider_->derive_key(slot, generation, &key) ||
      !random_bytes_(nonce.data(), nonce.size()) ||
      !sha256_(plaintext.data(), plaintext.size(), &digest)) {
    zeroize(key.data(), key.size());
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
    zeroize(key.data(), key.size());
    zeroize(nonce.data(), nonce.size());
    zeroize(digest.data(), digest.size());
    zeroize(header.data(), header.size());
    return false;
  }

  std::vector<uint8_t> ciphertext;
  const bool success =
      aead_encrypt_(key, nonce, header.data(), header.size(), plaintext,
                    &ciphertext) &&
      ciphertext.size() == plaintext.size() + PERSISTENCE_TAG_BYTES;
  if (success) {
    envelope->reserve(header.size() + ciphertext.size());
    envelope->insert(envelope->end(), header.begin(), header.end());
    envelope->insert(envelope->end(), ciphertext.begin(), ciphertext.end());
  }

  zeroize(key.data(), key.size());
  zeroize(nonce.data(), nonce.size());
  zeroize(digest.data(), digest.size());
  zeroize(header.data(), header.size());
  zeroize(ciphertext.data(), ciphertext.size());
  if (!success) {
    zeroize(envelope->data(), envelope->size());
    envelope->clear();
  }
  return success;
}

bool PairingPersistenceCrypto::inspect(
    const std::vector<uint8_t> &envelope,
    PersistenceEnvelopeMetadata *metadata) {
  if (metadata == nullptr ||
      envelope.size() < HEADER_BYTES + PERSISTENCE_TAG_BYTES ||
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
          HEADER_BYTES + parsed.plaintext_size + PERSISTENCE_TAG_BYTES)
    return false;
  *metadata = parsed;
  return true;
}

bool PairingPersistenceCrypto::open(
    const std::vector<uint8_t> &envelope,
    PersistenceEnvelopeMetadata *metadata,
    std::vector<uint8_t> *plaintext) {
  if (this->key_provider_ == nullptr || metadata == nullptr ||
      plaintext == nullptr)
    return false;
  std::fill(plaintext->begin(), plaintext->end(), 0);
  plaintext->clear();

  PersistenceEnvelopeMetadata parsed{};
  if (!inspect(envelope, &parsed))
    return false;

  std::array<uint8_t, 32> key{};
  std::array<uint8_t, 12> nonce{};
  std::copy_n(envelope.data() + 48, nonce.size(), nonce.begin());
  if (!this->key_provider_->derive_key(parsed.slot, parsed.generation, &key)) {
    zeroize(nonce.data(), nonce.size());
    return false;
  }

  const uint8_t *ciphertext = envelope.data() + HEADER_BYTES;
  const size_t ciphertext_length = envelope.size() - HEADER_BYTES;
  bool success = aead_decrypt_(
      key, nonce, envelope.data(), HEADER_BYTES, ciphertext,
      ciphertext_length, plaintext);
  std::array<uint8_t, 32> digest{};
  if (success)
    success = sha256_(plaintext->data(), plaintext->size(), &digest) &&
              constant_time_equal_(digest.data(), parsed.digest.data(),
                                   digest.size());

  zeroize(key.data(), key.size());
  zeroize(nonce.data(), nonce.size());
  zeroize(digest.data(), digest.size());
  if (!success) {
    zeroize(plaintext->data(), plaintext->size());
    plaintext->clear();
    return false;
  }
  *metadata = parsed;
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

bool PairingPersistenceCrypto::sha256_(
    const uint8_t *data, size_t length, std::array<uint8_t, 32> *digest) {
  if (data == nullptr || length == 0 || digest == nullptr)
    return false;
#ifdef USE_ESP32
  const mbedtls_md_info_t *info =
      mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return info != nullptr &&
         mbedtls_md(info, data, length, digest->data()) == 0;
#else
  unsigned int written = 0;
  return EVP_Digest(data, length, digest->data(), &written, EVP_sha256(),
                    nullptr) == 1 &&
         written == digest->size();
#endif
}

bool PairingPersistenceCrypto::aead_encrypt_(
    const std::array<uint8_t, 32> &key,
    const std::array<uint8_t, 12> &nonce, const uint8_t *aad,
    size_t aad_length, const std::vector<uint8_t> &plaintext,
    std::vector<uint8_t> *ciphertext) {
  if (aad == nullptr || plaintext.empty() || ciphertext == nullptr)
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
    zeroize(ciphertext->data(), ciphertext->size());
    ciphertext->clear();
    return false;
  }
  return true;
#else
  EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
  if (context == nullptr) {
    zeroize(ciphertext->data(), ciphertext->size());
    ciphertext->clear();
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
    zeroize(ciphertext->data(), ciphertext->size());
    ciphertext->clear();
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
  if (aad == nullptr || ciphertext == nullptr || plaintext == nullptr ||
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
    zeroize(plaintext->data(), plaintext->size());
    plaintext->clear();
    return false;
  }
  return true;
#else
  EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
  if (context == nullptr) {
    zeroize(plaintext->data(), plaintext->size());
    plaintext->clear();
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
    zeroize(plaintext->data(), plaintext->size());
    plaintext->clear();
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
