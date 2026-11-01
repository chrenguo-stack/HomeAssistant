#include "secure_pairing_channel.h"

#include <algorithm>
#include <array>
#include <cstring>
#include <vector>

#ifdef USE_ESP32
#include "esp_random.h"
#include "mbedtls/chachapoly.h"
#include "mbedtls/md.h"
#include "psa/crypto.h"
#else
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/rand.h>
#endif

namespace esphome::greenhouse_pairing_client {

namespace {
constexpr size_t CHACHA_TAG_SIZE = 16;
}

bool SecurePairingChannel::random_bytes_(uint8_t *output, size_t length) {
  if (output == nullptr || length == 0)
    return false;
#ifdef USE_ESP32
  esp_fill_random(output, length);
  return true;
#else
  return RAND_bytes(output, static_cast<int>(length)) == 1;
#endif
}

bool SecurePairingChannel::x25519_(const std::array<uint8_t, 32> &private_key,
                                   const std::array<uint8_t, 32> &peer_public_key,
                                   std::array<uint8_t, 32> *public_key,
                                   std::array<uint8_t, 32> *shared_secret) {
  if (public_key == nullptr || shared_secret == nullptr)
    return false;
#ifdef USE_ESP32
  if (psa_crypto_init() != PSA_SUCCESS)
    return false;
  psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
  psa_set_key_type(&attributes, PSA_KEY_TYPE_ECC_KEY_PAIR(PSA_ECC_FAMILY_MONTGOMERY));
  psa_set_key_bits(&attributes, 255);
  psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_DERIVE | PSA_KEY_USAGE_EXPORT);
  psa_set_key_algorithm(&attributes, PSA_ALG_ECDH);
  psa_key_id_t key_id = 0;
  psa_status_t status = psa_import_key(&attributes, private_key.data(), private_key.size(), &key_id);
  psa_reset_key_attributes(&attributes);
  if (status != PSA_SUCCESS)
    return false;
  size_t public_length = 0;
  size_t shared_length = 0;
  status = psa_export_public_key(key_id, public_key->data(), public_key->size(), &public_length);
  if (status == PSA_SUCCESS)
    status = psa_raw_key_agreement(PSA_ALG_ECDH, key_id, peer_public_key.data(),
                                   peer_public_key.size(), shared_secret->data(),
                                   shared_secret->size(), &shared_length);
  const psa_status_t destroy_status = psa_destroy_key(key_id);
  return status == PSA_SUCCESS && destroy_status == PSA_SUCCESS &&
         public_length == public_key->size() && shared_length == shared_secret->size();
#else
  EVP_PKEY *private_pkey = EVP_PKEY_new_raw_private_key(EVP_PKEY_X25519, nullptr,
                                                        private_key.data(), private_key.size());
  EVP_PKEY *peer_pkey = EVP_PKEY_new_raw_public_key(EVP_PKEY_X25519, nullptr,
                                                    peer_public_key.data(), peer_public_key.size());
  if (private_pkey == nullptr || peer_pkey == nullptr) {
    EVP_PKEY_free(private_pkey);
    EVP_PKEY_free(peer_pkey);
    return false;
  }
  size_t public_length = public_key->size();
  size_t shared_length = shared_secret->size();
  EVP_PKEY_CTX *context = EVP_PKEY_CTX_new(private_pkey, nullptr);
  bool success = EVP_PKEY_get_raw_public_key(private_pkey, public_key->data(), &public_length) == 1 &&
                 context != nullptr && EVP_PKEY_derive_init(context) == 1 &&
                 EVP_PKEY_derive_set_peer(context, peer_pkey) == 1 &&
                 EVP_PKEY_derive(context, shared_secret->data(), &shared_length) == 1 &&
                 public_length == public_key->size() && shared_length == shared_secret->size();
  EVP_PKEY_CTX_free(context);
  EVP_PKEY_free(private_pkey);
  EVP_PKEY_free(peer_pkey);
  return success;
#endif
}

bool SecurePairingChannel::sha256_(const uint8_t *data, size_t length,
                                   std::array<uint8_t, 32> *digest) {
  if (data == nullptr || digest == nullptr)
    return false;
#ifdef USE_ESP32
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return info != nullptr && mbedtls_md(info, data, length, digest->data()) == 0;
#else
  unsigned int written = 0;
  return EVP_Digest(data, length, digest->data(), &written, EVP_sha256(), nullptr) == 1 &&
         written == digest->size();
#endif
}

bool SecurePairingChannel::hmac_sha256_(const uint8_t *key, size_t key_length,
                                        const uint8_t *data, size_t data_length,
                                        std::array<uint8_t, 32> *digest) {
  if (key == nullptr || data == nullptr || digest == nullptr)
    return false;
#ifdef USE_ESP32
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return info != nullptr &&
         mbedtls_md_hmac(info, key, key_length, data, data_length, digest->data()) == 0;
#else
  unsigned int written = 0;
  return HMAC(EVP_sha256(), key, static_cast<int>(key_length), data, data_length,
              digest->data(), &written) != nullptr &&
         written == digest->size();
#endif
}

bool SecurePairingChannel::hkdf_sha256_64_(
    const std::array<uint8_t, 32> &shared_secret, const std::array<uint8_t, 32> &salt,
    const std::vector<uint8_t> &info, std::array<uint8_t, 64> *material) {
  if (material == nullptr)
    return false;
  std::array<uint8_t, 32> prk{};
  std::array<uint8_t, 32> first{};
  std::array<uint8_t, 32> second{};
  std::vector<uint8_t> first_input;
  std::vector<uint8_t> second_input;

  bool success = hmac_sha256_(salt.data(), salt.size(), shared_secret.data(),
                              shared_secret.size(), &prk);
  if (success) {
    first_input = info;
    first_input.push_back(1);
    success = hmac_sha256_(prk.data(), prk.size(), first_input.data(), first_input.size(), &first);
  }
  if (success) {
    second_input.reserve(first.size() + info.size() + 1);
    second_input.insert(second_input.end(), first.begin(), first.end());
    second_input.insert(second_input.end(), info.begin(), info.end());
    second_input.push_back(2);
    success = hmac_sha256_(prk.data(), prk.size(), second_input.data(), second_input.size(), &second);
  }
  if (success) {
    std::copy(first.begin(), first.end(), material->begin());
    std::copy(second.begin(), second.end(), material->begin() + 32);
  }
  zeroize_(first_input.data(), first_input.size());
  zeroize_(second_input.data(), second_input.size());
  zeroize_(prk.data(), prk.size());
  zeroize_(first.data(), first.size());
  zeroize_(second.data(), second.size());
  return success;
}

bool SecurePairingChannel::aead_encrypt_(const std::array<uint8_t, 32> &key,
                                         const std::array<uint8_t, 12> &nonce,
                                         const std::string &aad,
                                         const std::string &plaintext,
                                         std::vector<uint8_t> *ciphertext) {
  if (ciphertext == nullptr)
    return false;
  ciphertext->assign(plaintext.size() + CHACHA_TAG_SIZE, 0);
#ifdef USE_ESP32
  mbedtls_chachapoly_context context;
  mbedtls_chachapoly_init(&context);
  int result = mbedtls_chachapoly_setkey(&context, key.data());
  if (result == 0)
    result = mbedtls_chachapoly_encrypt_and_tag(
        &context, plaintext.size(), nonce.data(),
        reinterpret_cast<const unsigned char *>(aad.data()), aad.size(),
        reinterpret_cast<const unsigned char *>(plaintext.data()), ciphertext->data(),
        ciphertext->data() + plaintext.size());
  mbedtls_chachapoly_free(&context);
  if (result != 0) {
    zeroize_(ciphertext->data(), ciphertext->size());
    ciphertext->clear();
    return false;
  }
  return true;
#else
  EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
  if (context == nullptr) {
    zeroize_(ciphertext->data(), ciphertext->size());
    ciphertext->clear();
    return false;
  }
  int output_length = 0;
  int total = 0;
  bool success = EVP_EncryptInit_ex(context, EVP_chacha20_poly1305(), nullptr, nullptr, nullptr) == 1 &&
                 EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_SET_IVLEN, nonce.size(), nullptr) == 1 &&
                 EVP_EncryptInit_ex(context, nullptr, nullptr, key.data(), nonce.data()) == 1 &&
                 EVP_EncryptUpdate(context, nullptr, &output_length,
                                   reinterpret_cast<const unsigned char *>(aad.data()),
                                   static_cast<int>(aad.size())) == 1 &&
                 EVP_EncryptUpdate(context, ciphertext->data(), &output_length,
                                   reinterpret_cast<const unsigned char *>(plaintext.data()),
                                   static_cast<int>(plaintext.size())) == 1;
  if (success)
    total = output_length;
  if (success)
    success = EVP_EncryptFinal_ex(context, ciphertext->data() + total, &output_length) == 1;
  if (success)
    total += output_length;
  if (success)
    success = EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_GET_TAG, CHACHA_TAG_SIZE,
                                  ciphertext->data() + plaintext.size()) == 1;
  EVP_CIPHER_CTX_free(context);
  if (!success || static_cast<size_t>(total) != plaintext.size()) {
    zeroize_(ciphertext->data(), ciphertext->size());
    ciphertext->clear();
    return false;
  }
  return true;
#endif
}

bool SecurePairingChannel::aead_decrypt_(const std::array<uint8_t, 32> &key,
                                         const std::array<uint8_t, 12> &nonce,
                                         const std::string &aad,
                                         const std::vector<uint8_t> &ciphertext,
                                         std::string *plaintext) {
  if (plaintext == nullptr || ciphertext.size() < CHACHA_TAG_SIZE)
    return false;
  const size_t body_size = ciphertext.size() - CHACHA_TAG_SIZE;
  std::vector<uint8_t> output(body_size, 0);
#ifdef USE_ESP32
  mbedtls_chachapoly_context context;
  mbedtls_chachapoly_init(&context);
  int result = mbedtls_chachapoly_setkey(&context, key.data());
  if (result == 0)
    result = mbedtls_chachapoly_auth_decrypt(
        &context, body_size, nonce.data(),
        reinterpret_cast<const unsigned char *>(aad.data()), aad.size(),
        ciphertext.data() + body_size, ciphertext.data(), output.data());
  mbedtls_chachapoly_free(&context);
  if (result != 0) {
    zeroize_(output.data(), output.size());
    return false;
  }
#else
  EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
  if (context == nullptr) {
    zeroize_(output.data(), output.size());
    return false;
  }
  int output_length = 0;
  int total = 0;
  bool success = EVP_DecryptInit_ex(context, EVP_chacha20_poly1305(), nullptr, nullptr, nullptr) == 1 &&
                 EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_SET_IVLEN, nonce.size(), nullptr) == 1 &&
                 EVP_DecryptInit_ex(context, nullptr, nullptr, key.data(), nonce.data()) == 1 &&
                 EVP_DecryptUpdate(context, nullptr, &output_length,
                                   reinterpret_cast<const unsigned char *>(aad.data()),
                                   static_cast<int>(aad.size())) == 1 &&
                 EVP_DecryptUpdate(context, output.data(), &output_length, ciphertext.data(),
                                   static_cast<int>(body_size)) == 1;
  if (success)
    total = output_length;
  if (success)
    success = EVP_CIPHER_CTX_ctrl(context, EVP_CTRL_AEAD_SET_TAG, CHACHA_TAG_SIZE,
                                  const_cast<uint8_t *>(ciphertext.data() + body_size)) == 1;
  if (success)
    success = EVP_DecryptFinal_ex(context, output.data() + total, &output_length) == 1;
  if (success)
    total += output_length;
  EVP_CIPHER_CTX_free(context);
  if (!success || static_cast<size_t>(total) != body_size) {
    zeroize_(output.data(), output.size());
    return false;
  }
#endif
  plaintext->assign(reinterpret_cast<const char *>(output.data()), output.size());
  zeroize_(output.data(), output.size());
  return true;
}

void SecurePairingChannel::zeroize_(void *data, size_t length) {
  if (data == nullptr)
    return;
  volatile uint8_t *pointer = static_cast<volatile uint8_t *>(data);
  while (length-- > 0)
    *pointer++ = 0;
}

}  // namespace esphome::greenhouse_pairing_client
