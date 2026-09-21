#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace esphome::greenhouse_n3w_core {

constexpr std::size_t kApplicationKeyBytes = 32;
constexpr std::size_t kNonceBytes = 12;
constexpr std::size_t kTagBytes = 16;
constexpr std::size_t kMaxCiphertextBytes = 1024;

enum class CoreError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  BOOT_SESSION_INVALID,
  KEY_STATE_INVALID,
  PLAINTEXT_SIZE_REJECTED,
  AEAD_ENCRYPT_FAILED,
  AEAD_DECRYPT_FAILED,
  STORE_MISSING,
  STORE_CORRUPT,
  STORE_IO_ERROR,
  SESSION_ROLLBACK,
  SESSION_EXHAUSTED,
  DURABILITY_VERIFY_FAILED,
  NOT_READY,
  SEQUENCE_EXHAUSTED,
};

enum class StoreStatus : uint8_t {
  OK = 0,
  MISSING,
  CORRUPT,
  IO_ERROR,
};

enum class KeyLifecycle : uint8_t {
  EMPTY = 0,
  STAGED,
  ACTIVE,
  GRACE,
  REVOKED,
};

struct RelayHeader {
  std::string schema{"gh.relay/1"};
  std::string transport{"esp_now"};
  std::string gateway_id;
  std::string node_id;
  uint8_t hop_count{1};
  uint32_t key_epoch{0};
  std::string boot_id;
  uint32_t seq{0};
};

struct RelayFrame {
  RelayHeader header;
  std::array<uint8_t, kNonceBytes> nonce{};
  std::vector<uint8_t> ciphertext;
  std::array<uint8_t, kTagBytes> tag{};
};

struct ApplicationKeyState {
  KeyLifecycle lifecycle{KeyLifecycle::EMPTY};
  uint32_t key_epoch{0};
  std::array<uint8_t, kApplicationKeyBytes> key{};
  uint64_t session_floor{0};

  bool valid_for_encrypt() const;
  void clear();
};

class ApplicationKeyStore {
 public:
  virtual ~ApplicationKeyStore() = default;
  virtual StoreStatus load(ApplicationKeyState *state) = 0;
  virtual StoreStatus save(const ApplicationKeyState &state) = 0;
};

class BootSessionStore {
 public:
  virtual ~BootSessionStore() = default;
  virtual StoreStatus load(uint64_t *last_session) = 0;
  virtual StoreStatus save(uint64_t last_session) = 0;
};

class SequenceCounter {
 public:
  explicit SequenceCounter(uint32_t first = 0) : next_(first) {}

  CoreError take(uint32_t *seq);
  bool exhausted() const { return exhausted_; }

 protected:
  uint32_t next_{0};
  bool exhausted_{false};
};

class BootSessionManager {
 public:
  CoreError provision_recovery_floor(BootSessionStore *store, uint64_t floor);
  CoreError begin(BootSessionStore *store, uint64_t minimum_session_floor);
  CoreError take_sequence(uint32_t *seq);

  bool ready() const { return ready_; }
  uint64_t session() const { return session_; }
  std::string boot_id() const;

 protected:
  static CoreError map_store_status_(StoreStatus status);

  uint64_t session_{0};
  bool ready_{false};
  SequenceCounter sequence_{};
};

bool valid_identity(const std::string &value);
bool parse_boot_id(const std::string &boot_id, uint64_t *session);
std::string format_boot_id(uint64_t session);

CoreError derive_nonce(
    const std::string &boot_id,
    uint32_t seq,
    std::array<uint8_t, kNonceBytes> *nonce);

CoreError build_aad(const RelayHeader &header, std::string *aad);

CoreError aes256gcm_encrypt(
    const ApplicationKeyState &key_state,
    const std::array<uint8_t, kNonceBytes> &nonce,
    const std::string &plaintext,
    const std::string &aad,
    std::vector<uint8_t> *ciphertext,
    std::array<uint8_t, kTagBytes> *tag);

CoreError aes256gcm_decrypt(
    const ApplicationKeyState &key_state,
    const std::array<uint8_t, kNonceBytes> &nonce,
    const std::vector<uint8_t> &ciphertext,
    const std::array<uint8_t, kTagBytes> &tag,
    const std::string &aad,
    std::string *plaintext);

CoreError build_relay_frame(
    const RelayHeader &header,
    const ApplicationKeyState &key_state,
    const std::string &telemetry_json,
    RelayFrame *frame);

CoreError serialize_relay_frame_json(
    const RelayFrame &frame,
    std::string *json);

}  // namespace esphome::greenhouse_n3w_core
