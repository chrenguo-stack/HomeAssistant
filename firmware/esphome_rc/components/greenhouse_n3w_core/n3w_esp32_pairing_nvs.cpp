#include "n3w_esp32_pairing_nvs.h"

#include <algorithm>
#include <iterator>
#include <utility>

#ifdef USE_ESP32
#include <cstddef>
#include <cstring>

#include "mbedtls/md.h"
#include "nvs.h"
#endif

namespace esphome::greenhouse_n3w_core {

namespace {

bool valid_text(const std::string &value, std::size_t maximum) {
  return !value.empty() && value.size() <= maximum &&
         std::none_of(value.begin(), value.end(), [](char ch) { return ch == '\0'; });
}

bool lowercase_sha256(const std::string &value) {
  return value.size() == 64U &&
         std::all_of(value.begin(), value.end(), [](char ch) {
           return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
         });
}

bool common_ack_valid(const PendingPairingAckV2 &state) {
  return valid_text(state.manager_host, 253U) && state.manager_port > 0U &&
         valid_text(state.pairing_path, 255U) &&
         state.pairing_path.front() == '/' &&
         valid_text(state.session_id, 64U) &&
         std::any_of(
             state.delivery_digest.begin(), state.delivery_digest.end(),
             [](uint8_t value) { return value != 0U; });
}

}  // namespace

bool PendingPairingAckV2::valid() const {
  if (!common_ack_valid(*this)) return false;
  if (legacy()) {
    return state == PendingPairingAckState::ACK_PENDING;
  }
  if (format_version != kPendingPairingAckCurrentVersion ||
      (state != PendingPairingAckState::ACK_PENDING &&
       state != PendingPairingAckState::TERMINAL_CLEANUP)) {
    return false;
  }
  return valid_text(pairing_id, 64U) && valid_text(manager_id, 128U) &&
         valid_text(system_id, 128U) && valid_text(bootstrap_host, 253U) &&
         bootstrap_port == 47110U && lowercase_sha256(bootstrap_tls_sha256);
}

bool PendingPairingAckV2::recovery_capable() const {
  return format_version == kPendingPairingAckCurrentVersion && valid();
}

void PendingPairingAckV2::clear() {
  format_version = kPendingPairingAckCurrentVersion;
  state = PendingPairingAckState::ACK_PENDING;
  manager_host.clear();
  manager_port = 0;
  pairing_path.clear();
  session_id.clear();
  delivery_digest.fill(0);
  pairing_id.clear();
  manager_id.clear();
  system_id.clear();
  bootstrap_host.clear();
  bootstrap_port = 0;
  bootstrap_tls_sha256.clear();
}

#ifdef USE_ESP32
namespace {

constexpr uint32_t kAckMagic = 0x4E334132U;  // N3A2
constexpr std::size_t kHostCapacity = 254U;
constexpr std::size_t kPathCapacity = 256U;
constexpr std::size_t kSessionCapacity = 65U;
constexpr std::size_t kPairingIdCapacity = 65U;
constexpr std::size_t kIdentityCapacity = 129U;
constexpr std::size_t kFingerprintCapacity = 65U;

struct PersistedPendingAckV1 {
  uint32_t magic;
  uint16_t version;
  uint16_t manager_port;
  char manager_host[kHostCapacity];
  char pairing_path[kPathCapacity];
  char session_id[kSessionCapacity];
  uint8_t delivery_digest[32];
  uint8_t check[32];
};

struct PersistedPendingAckV2 {
  uint32_t magic;
  uint16_t version;
  uint8_t state;
  uint8_t reserved;
  uint16_t manager_port;
  uint16_t bootstrap_port;
  char manager_host[kHostCapacity];
  char pairing_path[kPathCapacity];
  char session_id[kSessionCapacity];
  uint8_t delivery_digest[32];
  char pairing_id[kPairingIdCapacity];
  char manager_id[kIdentityCapacity];
  char system_id[kIdentityCapacity];
  char bootstrap_host[kHostCapacity];
  char bootstrap_tls_sha256[kFingerprintCapacity];
  uint8_t check[32];
};

template<std::size_t N>
bool copy_text(const std::string &source, char (&destination)[N]) {
  if (source.empty() || source.size() >= N) return false;
  std::memset(destination, 0, N);
  std::memcpy(destination, source.data(), source.size());
  return true;
}

template<std::size_t N>
bool terminated(const char (&value)[N]) {
  return std::memchr(value, '\0', N) != nullptr;
}

bool sha256_record(
    const void *record,
    std::size_t check_offset,
    uint8_t *output) {
  if (record == nullptr || output == nullptr || check_offset == 0U) return false;
  const mbedtls_md_info_t *info =
      mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return info != nullptr &&
         mbedtls_md(
             info,
             static_cast<const uint8_t *>(record),
             check_offset,
             output) == 0;
}

bool write_check(PersistedPendingAckV1 *record) {
  return record != nullptr &&
         sha256_record(
             record,
             offsetof(PersistedPendingAckV1, check),
             record->check);
}

bool write_check(PersistedPendingAckV2 *record) {
  return record != nullptr &&
         sha256_record(
             record,
             offsetof(PersistedPendingAckV2, check),
             record->check);
}

bool valid_check(const PersistedPendingAckV1 &record) {
  std::array<uint8_t, 32> expected{};
  if (!sha256_record(
          &record,
          offsetof(PersistedPendingAckV1, check),
          expected.data())) {
    return false;
  }
  uint8_t diff = 0;
  for (std::size_t index = 0; index < expected.size(); ++index) {
    diff = static_cast<uint8_t>(diff | (expected[index] ^ record.check[index]));
  }
  return diff == 0U;
}

bool valid_check(const PersistedPendingAckV2 &record) {
  std::array<uint8_t, 32> expected{};
  if (!sha256_record(
          &record,
          offsetof(PersistedPendingAckV2, check),
          expected.data())) {
    return false;
  }
  uint8_t diff = 0;
  for (std::size_t index = 0; index < expected.size(); ++index) {
    diff = static_cast<uint8_t>(diff | (expected[index] ^ record.check[index]));
  }
  return diff == 0U;
}

SimpleNvsStatus blob_size(
    const std::string &namespace_name,
    const std::string &key_name,
    std::size_t *size) {
  if (size == nullptr) return SimpleNvsStatus::INVALID_ARGUMENT;
  nvs_handle_t handle = 0;
  const esp_err_t opened =
      nvs_open(namespace_name.c_str(), NVS_READONLY, &handle);
  if (opened == ESP_ERR_NVS_NOT_FOUND ||
      opened == ESP_ERR_NVS_NOT_INITIALIZED ||
      opened == ESP_ERR_NVS_INVALID_STATE) {
    return SimpleNvsStatus::MISSING;
  }
  if (opened != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  *size = 0U;
  const esp_err_t error =
      nvs_get_blob(handle, key_name.c_str(), nullptr, size);
  nvs_close(handle);
  if (error == ESP_ERR_NVS_NOT_FOUND) return SimpleNvsStatus::MISSING;
  return error == ESP_OK ? SimpleNvsStatus::OK : SimpleNvsStatus::IO_ERROR;
}

template<typename Record>
SimpleNvsStatus read_record(
    const std::string &namespace_name,
    const std::string &key_name,
    Record *record) {
  if (record == nullptr) return SimpleNvsStatus::INVALID_ARGUMENT;
  nvs_handle_t handle = 0;
  const esp_err_t opened =
      nvs_open(namespace_name.c_str(), NVS_READONLY, &handle);
  if (opened != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  std::size_t size = sizeof(*record);
  const esp_err_t error =
      nvs_get_blob(handle, key_name.c_str(), record, &size);
  nvs_close(handle);
  if (error == ESP_ERR_NVS_NOT_FOUND) return SimpleNvsStatus::MISSING;
  if (error != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  return size == sizeof(*record)
             ? SimpleNvsStatus::OK
             : SimpleNvsStatus::CORRUPT;
}

template<typename Record>
SimpleNvsStatus write_record(
    const std::string &namespace_name,
    const std::string &key_name,
    const Record &record) {
  nvs_handle_t handle = 0;
  esp_err_t error =
      nvs_open(namespace_name.c_str(), NVS_READWRITE, &handle);
  if (error != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  error = nvs_set_blob(
      handle, key_name.c_str(), &record, sizeof(record));
  if (error == ESP_OK) error = nvs_commit(handle);
  nvs_close(handle);
  return error == ESP_OK ? SimpleNvsStatus::OK : SimpleNvsStatus::IO_ERROR;
}

bool load_common(
    const char *manager_host,
    uint16_t manager_port,
    const char *pairing_path,
    const char *session_id,
    const uint8_t *delivery_digest,
    PendingPairingAckV2 *candidate) {
  if (manager_host == nullptr || pairing_path == nullptr ||
      session_id == nullptr || delivery_digest == nullptr ||
      candidate == nullptr) {
    return false;
  }
  candidate->manager_host = manager_host;
  candidate->manager_port = manager_port;
  candidate->pairing_path = pairing_path;
  candidate->session_id = session_id;
  std::copy_n(
      delivery_digest,
      candidate->delivery_digest.size(),
      candidate->delivery_digest.begin());
  return true;
}

}  // namespace

SimpleNvsStatus NvsPendingPairingAckStoreV2::load(
    PendingPairingAckV2 *state) {
  if (state == nullptr || namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }

  std::size_t size = 0U;
  const SimpleNvsStatus size_status =
      blob_size(namespace_name_, key_name_, &size);
  if (size_status != SimpleNvsStatus::OK) return size_status;

  PendingPairingAckV2 candidate;
  if (size == sizeof(PersistedPendingAckV1)) {
    PersistedPendingAckV1 record{};
    const SimpleNvsStatus status =
        read_record(namespace_name_, key_name_, &record);
    if (status != SimpleNvsStatus::OK) return status;
    if (record.magic != kAckMagic ||
        record.version != kPendingPairingAckLegacyVersion ||
        !valid_check(record) || !terminated(record.manager_host) ||
        !terminated(record.pairing_path) || !terminated(record.session_id)) {
      return SimpleNvsStatus::CORRUPT;
    }
    candidate.format_version = kPendingPairingAckLegacyVersion;
    candidate.state = PendingPairingAckState::ACK_PENDING;
    if (!load_common(
            record.manager_host,
            record.manager_port,
            record.pairing_path,
            record.session_id,
            record.delivery_digest,
            &candidate) ||
        !candidate.valid()) {
      candidate.clear();
      return SimpleNvsStatus::CORRUPT;
    }
    *state = std::move(candidate);
    return SimpleNvsStatus::OK;
  }

  if (size != sizeof(PersistedPendingAckV2)) {
    return SimpleNvsStatus::CORRUPT;
  }

  PersistedPendingAckV2 record{};
  const SimpleNvsStatus status =
      read_record(namespace_name_, key_name_, &record);
  if (status != SimpleNvsStatus::OK) return status;
  if (record.magic != kAckMagic ||
      record.version != kPendingPairingAckCurrentVersion ||
      !valid_check(record) || !terminated(record.manager_host) ||
      !terminated(record.pairing_path) || !terminated(record.session_id) ||
      !terminated(record.pairing_id) || !terminated(record.manager_id) ||
      !terminated(record.system_id) || !terminated(record.bootstrap_host) ||
      !terminated(record.bootstrap_tls_sha256)) {
    return SimpleNvsStatus::CORRUPT;
  }

  candidate.format_version = kPendingPairingAckCurrentVersion;
  candidate.state =
      static_cast<PendingPairingAckState>(record.state);
  if (!load_common(
          record.manager_host,
          record.manager_port,
          record.pairing_path,
          record.session_id,
          record.delivery_digest,
          &candidate)) {
    return SimpleNvsStatus::CORRUPT;
  }
  candidate.pairing_id = record.pairing_id;
  candidate.manager_id = record.manager_id;
  candidate.system_id = record.system_id;
  candidate.bootstrap_host = record.bootstrap_host;
  candidate.bootstrap_port = record.bootstrap_port;
  candidate.bootstrap_tls_sha256 = record.bootstrap_tls_sha256;
  if (!candidate.valid()) {
    candidate.clear();
    return SimpleNvsStatus::CORRUPT;
  }
  *state = std::move(candidate);
  return SimpleNvsStatus::OK;
}

SimpleNvsStatus NvsPendingPairingAckStoreV2::save(
    const PendingPairingAckV2 &state) {
  if (!state.valid() || namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }

  // Legacy source paths remain readable/writable for non-product compatibility.
  // The R6 selected-candidate path always supplies recovery identity and writes
  // the version-2 branch below.
  if (state.legacy()) {
    PersistedPendingAckV1 record{};
    record.magic = kAckMagic;
    record.version = kPendingPairingAckLegacyVersion;
    record.manager_port = state.manager_port;
    if (!copy_text(state.manager_host, record.manager_host) ||
        !copy_text(state.pairing_path, record.pairing_path) ||
        !copy_text(state.session_id, record.session_id)) {
      return SimpleNvsStatus::INVALID_ARGUMENT;
    }
    std::copy(
        state.delivery_digest.begin(),
        state.delivery_digest.end(),
        std::begin(record.delivery_digest));
    if (!write_check(&record)) return SimpleNvsStatus::IO_ERROR;
    return write_record(namespace_name_, key_name_, record);
  }

  if (!state.recovery_capable()) return SimpleNvsStatus::INVALID_ARGUMENT;
  PersistedPendingAckV2 record{};
  record.magic = kAckMagic;
  record.version = kPendingPairingAckCurrentVersion;
  record.state = static_cast<uint8_t>(state.state);
  record.manager_port = state.manager_port;
  record.bootstrap_port = state.bootstrap_port;
  if (!copy_text(state.manager_host, record.manager_host) ||
      !copy_text(state.pairing_path, record.pairing_path) ||
      !copy_text(state.session_id, record.session_id) ||
      !copy_text(state.pairing_id, record.pairing_id) ||
      !copy_text(state.manager_id, record.manager_id) ||
      !copy_text(state.system_id, record.system_id) ||
      !copy_text(state.bootstrap_host, record.bootstrap_host) ||
      !copy_text(
          state.bootstrap_tls_sha256,
          record.bootstrap_tls_sha256)) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  std::copy(
      state.delivery_digest.begin(),
      state.delivery_digest.end(),
      std::begin(record.delivery_digest));
  if (!write_check(&record)) return SimpleNvsStatus::IO_ERROR;
  return write_record(namespace_name_, key_name_, record);
}

SimpleNvsStatus NvsPendingPairingAckStoreV2::erase() {
  if (namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  nvs_handle_t handle = 0;
  esp_err_t error =
      nvs_open(namespace_name_.c_str(), NVS_READWRITE, &handle);
  if (error != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  error = nvs_erase_key(handle, key_name_.c_str());
  if (error == ESP_ERR_NVS_NOT_FOUND) error = ESP_OK;
  if (error == ESP_OK) error = nvs_commit(handle);
  nvs_close(handle);
  return error == ESP_OK ? SimpleNvsStatus::OK : SimpleNvsStatus::IO_ERROR;
}
#endif  // USE_ESP32

}  // namespace esphome::greenhouse_n3w_core
