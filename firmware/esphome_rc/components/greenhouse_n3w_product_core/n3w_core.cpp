#include "n3w_core.h"

#include <algorithm>
#include <cstdio>
#include <limits>
#include <utility>

#include "mbedtls/base64.h"
#include "mbedtls/gcm.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr char kRelaySchema[] = "gh.relay/1";
constexpr char kTransport[] = "esp_now";

bool lower_hex(char value) {
  return (value >= '0' && value <= '9') || (value >= 'a' && value <= 'f');
}

uint8_t hex_value(char value) {
  if (value >= '0' && value <= '9')
    return static_cast<uint8_t>(value - '0');
  return static_cast<uint8_t>(10 + value - 'a');
}

std::string base64_encode(const uint8_t *data, std::size_t length) {
  if (data == nullptr || length == 0)
    return {};
  const std::size_t capacity = ((length + 2U) / 3U) * 4U + 1U;
  std::vector<unsigned char> output(capacity, 0);
  std::size_t written = 0;
  const int rc = mbedtls_base64_encode(
      output.data(), output.size(), &written, data, length);
  if (rc != 0)
    return {};
  return std::string(reinterpret_cast<const char *>(output.data()), written);
}

bool valid_header(const RelayHeader &header) {
  if (header.schema != kRelaySchema || header.transport != kTransport)
    return false;
  if (!valid_identity(header.gateway_id) || !valid_identity(header.node_id))
    return false;
  if (header.hop_count != 1 || header.key_epoch == 0)
    return false;
  uint64_t session = 0;
  return parse_boot_id(header.boot_id, &session);
}

}  // namespace

bool ApplicationKeyState::valid_for_encrypt() const {
  return this->lifecycle == KeyLifecycle::ACTIVE && this->key_epoch > 0;
}

void ApplicationKeyState::clear() {
  std::fill(this->key.begin(), this->key.end(), 0);
  this->lifecycle = KeyLifecycle::EMPTY;
  this->key_epoch = 0;
  this->session_floor = 0;
}

CoreError SequenceCounter::take(uint32_t *seq) {
  if (seq == nullptr)
    return CoreError::INVALID_ARGUMENT;
  if (this->exhausted_)
    return CoreError::SEQUENCE_EXHAUSTED;
  *seq = this->next_;
  if (this->next_ == std::numeric_limits<uint32_t>::max()) {
    this->exhausted_ = true;
  } else {
    ++this->next_;
  }
  return CoreError::NONE;
}

CoreError BootSessionManager::map_store_status_(StoreStatus status) {
  switch (status) {
    case StoreStatus::OK:
      return CoreError::NONE;
    case StoreStatus::MISSING:
      return CoreError::STORE_MISSING;
    case StoreStatus::CORRUPT:
      return CoreError::STORE_CORRUPT;
    case StoreStatus::IO_ERROR:
      return CoreError::STORE_IO_ERROR;
  }
  return CoreError::STORE_IO_ERROR;
}

CoreError BootSessionManager::provision_recovery_floor(
    BootSessionStore *store, uint64_t floor) {
  this->ready_ = false;
  this->session_ = 0;
  this->sequence_ = SequenceCounter{};
  if (store == nullptr)
    return CoreError::INVALID_ARGUMENT;

  StoreStatus saved = store->save(floor);
  if (saved != StoreStatus::OK)
    return map_store_status_(saved);

  uint64_t verified = 0;
  StoreStatus loaded = store->load(&verified);
  if (loaded != StoreStatus::OK)
    return map_store_status_(loaded);
  if (verified != floor)
    return CoreError::DURABILITY_VERIFY_FAILED;
  return CoreError::NONE;
}

CoreError BootSessionManager::begin(
    BootSessionStore *store, uint64_t minimum_session_floor) {
  this->ready_ = false;
  this->session_ = 0;
  this->sequence_ = SequenceCounter{};
  if (store == nullptr)
    return CoreError::INVALID_ARGUMENT;

  uint64_t last_session = 0;
  StoreStatus loaded = store->load(&last_session);
  if (loaded != StoreStatus::OK)
    return map_store_status_(loaded);
  if (last_session < minimum_session_floor)
    return CoreError::SESSION_ROLLBACK;
  if (last_session == std::numeric_limits<uint64_t>::max())
    return CoreError::SESSION_EXHAUSTED;

  const uint64_t next_session = last_session + 1U;
  StoreStatus saved = store->save(next_session);
  if (saved != StoreStatus::OK)
    return map_store_status_(saved);

  uint64_t verified = 0;
  loaded = store->load(&verified);
  if (loaded != StoreStatus::OK)
    return map_store_status_(loaded);
  if (verified != next_session)
    return CoreError::DURABILITY_VERIFY_FAILED;

  this->session_ = next_session;
  this->sequence_ = SequenceCounter{};
  this->ready_ = true;
  return CoreError::NONE;
}

CoreError BootSessionManager::take_sequence(uint32_t *seq) {
  if (!this->ready_)
    return CoreError::NOT_READY;
  return this->sequence_.take(seq);
}

std::string BootSessionManager::boot_id() const {
  if (!this->ready_)
    return {};
  return format_boot_id(this->session_);
}

bool valid_identity(const std::string &value) {
  if (value.size() < 3 || value.size() > 64)
    return false;
  const auto is_first = [](char ch) {
    return (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9');
  };
  const auto is_rest = [&](char ch) {
    return is_first(ch) || ch == '_' || ch == '-';
  };
  if (!is_first(value.front()))
    return false;
  return std::all_of(value.begin() + 1, value.end(), is_rest);
}

bool parse_boot_id(const std::string &boot_id, uint64_t *session) {
  if (session == nullptr || boot_id.size() != 21 ||
      boot_id.compare(0, 5, "boot_") != 0)
    return false;
  uint64_t parsed = 0;
  for (std::size_t index = 5; index < boot_id.size(); ++index) {
    const char ch = boot_id[index];
    if (!lower_hex(ch))
      return false;
    parsed = (parsed << 4U) | hex_value(ch);
  }
  if (parsed == 0)
    return false;
  *session = parsed;
  return true;
}

std::string format_boot_id(uint64_t session) {
  if (session == 0)
    return {};
  char output[22]{};
  std::snprintf(
      output,
      sizeof(output),
      "boot_%016llx",
      static_cast<unsigned long long>(session));
  return std::string(output);
}

CoreError derive_nonce(
    const std::string &boot_id,
    uint32_t seq,
    std::array<uint8_t, kNonceBytes> *nonce) {
  if (nonce == nullptr)
    return CoreError::INVALID_ARGUMENT;
  uint64_t session = 0;
  if (!parse_boot_id(boot_id, &session))
    return CoreError::BOOT_SESSION_INVALID;

  for (int index = 7; index >= 0; --index) {
    (*nonce)[static_cast<std::size_t>(7 - index)] =
        static_cast<uint8_t>((session >> (index * 8U)) & 0xFFU);
  }
  for (int index = 3; index >= 0; --index) {
    (*nonce)[static_cast<std::size_t>(11 - index)] =
        static_cast<uint8_t>((seq >> (index * 8U)) & 0xFFU);
  }
  return CoreError::NONE;
}

CoreError build_aad(const RelayHeader &header, std::string *aad) {
  if (aad == nullptr)
    return CoreError::INVALID_ARGUMENT;
  if (!valid_header(header))
    return CoreError::INVALID_ARGUMENT;

  // Python Manager uses:
  // json.dumps(document, separators=(",", ":"), sort_keys=True)
  // Keep this byte ordering exact: boot_id, gateway_id, hop_count, key_epoch,
  // node_id, schema, seq, transport.
  *aad =
      "{\"boot_id\":\"" + header.boot_id +
      "\",\"gateway_id\":\"" + header.gateway_id +
      "\",\"hop_count\":" + std::to_string(header.hop_count) +
      ",\"key_epoch\":" + std::to_string(header.key_epoch) +
      ",\"node_id\":\"" + header.node_id +
      "\",\"schema\":\"gh.relay/1\"" +
      ",\"seq\":" + std::to_string(header.seq) +
      ",\"transport\":\"esp_now\"}";
  return CoreError::NONE;
}

CoreError aes256gcm_encrypt(
    const ApplicationKeyState &key_state,
    const std::array<uint8_t, kNonceBytes> &nonce,
    const std::string &plaintext,
    const std::string &aad,
    std::vector<uint8_t> *ciphertext,
    std::array<uint8_t, kTagBytes> *tag) {
  if (ciphertext == nullptr || tag == nullptr)
    return CoreError::INVALID_ARGUMENT;
  if (!key_state.valid_for_encrypt())
    return CoreError::KEY_STATE_INVALID;
  if (plaintext.empty() || plaintext.size() > kMaxCiphertextBytes)
    return CoreError::PLAINTEXT_SIZE_REJECTED;

  ciphertext->assign(plaintext.size(), 0);
  tag->fill(0);

  mbedtls_gcm_context context;
  mbedtls_gcm_init(&context);
  int rc = mbedtls_gcm_setkey(
      &context,
      MBEDTLS_CIPHER_ID_AES,
      key_state.key.data(),
      static_cast<unsigned int>(kApplicationKeyBytes * 8U));
  if (rc == 0) {
    rc = mbedtls_gcm_crypt_and_tag(
        &context,
        MBEDTLS_GCM_ENCRYPT,
        plaintext.size(),
        nonce.data(),
        nonce.size(),
        reinterpret_cast<const unsigned char *>(aad.data()),
        aad.size(),
        reinterpret_cast<const unsigned char *>(plaintext.data()),
        ciphertext->data(),
        tag->size(),
        tag->data());
  }
  mbedtls_gcm_free(&context);

  if (rc != 0) {
    std::fill(ciphertext->begin(), ciphertext->end(), 0);
    ciphertext->clear();
    tag->fill(0);
    return CoreError::AEAD_ENCRYPT_FAILED;
  }
  return CoreError::NONE;
}

CoreError aes256gcm_decrypt(
    const ApplicationKeyState &key_state,
    const std::array<uint8_t, kNonceBytes> &nonce,
    const std::vector<uint8_t> &ciphertext,
    const std::array<uint8_t, kTagBytes> &tag,
    const std::string &aad,
    std::string *plaintext) {
  if (plaintext == nullptr)
    return CoreError::INVALID_ARGUMENT;
  if (!key_state.valid_for_encrypt())
    return CoreError::KEY_STATE_INVALID;
  if (ciphertext.empty() || ciphertext.size() > kMaxCiphertextBytes)
    return CoreError::PLAINTEXT_SIZE_REJECTED;

  std::vector<uint8_t> output(ciphertext.size(), 0);
  mbedtls_gcm_context context;
  mbedtls_gcm_init(&context);
  int rc = mbedtls_gcm_setkey(
      &context,
      MBEDTLS_CIPHER_ID_AES,
      key_state.key.data(),
      static_cast<unsigned int>(kApplicationKeyBytes * 8U));
  if (rc == 0) {
    rc = mbedtls_gcm_auth_decrypt(
        &context,
        ciphertext.size(),
        nonce.data(),
        nonce.size(),
        reinterpret_cast<const unsigned char *>(aad.data()),
        aad.size(),
        tag.data(),
        tag.size(),
        ciphertext.data(),
        output.data());
  }
  mbedtls_gcm_free(&context);

  if (rc != 0) {
    std::fill(output.begin(), output.end(), 0);
    plaintext->clear();
    return CoreError::AEAD_DECRYPT_FAILED;
  }
  plaintext->assign(
      reinterpret_cast<const char *>(output.data()), output.size());
  std::fill(output.begin(), output.end(), 0);
  return CoreError::NONE;
}

CoreError build_relay_frame(
    const RelayHeader &header,
    const ApplicationKeyState &key_state,
    const std::string &telemetry_json,
    RelayFrame *frame) {
  if (frame == nullptr)
    return CoreError::INVALID_ARGUMENT;
  if (!key_state.valid_for_encrypt() ||
      key_state.key_epoch != header.key_epoch)
    return CoreError::KEY_STATE_INVALID;

  std::array<uint8_t, kNonceBytes> nonce{};
  CoreError result = derive_nonce(header.boot_id, header.seq, &nonce);
  if (result != CoreError::NONE)
    return result;

  std::string aad;
  result = build_aad(header, &aad);
  if (result != CoreError::NONE)
    return result;

  RelayFrame candidate;
  candidate.header = header;
  candidate.nonce = nonce;
  result = aes256gcm_encrypt(
      key_state,
      candidate.nonce,
      telemetry_json,
      aad,
      &candidate.ciphertext,
      &candidate.tag);
  if (result != CoreError::NONE)
    return result;

  *frame = std::move(candidate);
  return CoreError::NONE;
}

CoreError serialize_relay_frame_json(
    const RelayFrame &frame,
    std::string *json) {
  if (json == nullptr || !valid_header(frame.header) ||
      frame.ciphertext.empty() ||
      frame.ciphertext.size() > kMaxCiphertextBytes)
    return CoreError::INVALID_ARGUMENT;

  const std::string nonce_b64 =
      base64_encode(frame.nonce.data(), frame.nonce.size());
  const std::string ciphertext_b64 =
      base64_encode(frame.ciphertext.data(), frame.ciphertext.size());
  const std::string tag_b64 =
      base64_encode(frame.tag.data(), frame.tag.size());
  if (nonce_b64.empty() || ciphertext_b64.empty() || tag_b64.empty())
    return CoreError::INVALID_ARGUMENT;

  *json =
      "{\"schema\":\"gh.relay/1\",\"transport\":\"esp_now\"" +
      std::string(",\"gateway_id\":\"") + frame.header.gateway_id +
      "\",\"node_id\":\"" + frame.header.node_id +
      "\",\"hop_count\":1" +
      ",\"key_epoch\":" + std::to_string(frame.header.key_epoch) +
      ",\"boot_id\":\"" + frame.header.boot_id +
      "\",\"seq\":" + std::to_string(frame.header.seq) +
      ",\"nonce_b64\":\"" + nonce_b64 +
      "\",\"ciphertext_b64\":\"" + ciphertext_b64 +
      "\",\"tag_b64\":\"" + tag_b64 + "\"}";
  return CoreError::NONE;
}

}  // namespace esphome::greenhouse_n3w_core
