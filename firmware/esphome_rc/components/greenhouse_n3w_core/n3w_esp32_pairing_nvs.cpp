#include "n3w_esp32_pairing_nvs.h"

#include <algorithm>
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
}  // namespace

bool PendingPairingAckV2::valid() const {
  return valid_text(manager_host, 253) && manager_port > 0 &&
         valid_text(pairing_path, 255) && pairing_path.front() == '/' &&
         valid_text(session_id, 64) &&
         std::any_of(
             delivery_digest.begin(), delivery_digest.end(),
             [](uint8_t value) { return value != 0; });
}

void PendingPairingAckV2::clear() {
  manager_host.clear();
  manager_port = 0;
  pairing_path.clear();
  session_id.clear();
  delivery_digest.fill(0);
}

#ifdef USE_ESP32
namespace {

constexpr uint32_t kAckMagic = 0x4E334132U;  // N3A2
constexpr uint16_t kAckVersion = 1U;
constexpr std::size_t kHostCapacity = 254U;
constexpr std::size_t kPathCapacity = 256U;
constexpr std::size_t kSessionCapacity = 65U;

struct PersistedPendingAck {
  uint32_t magic;
  uint16_t version;
  uint16_t manager_port;
  char manager_host[kHostCapacity];
  char pairing_path[kPathCapacity];
  char session_id[kSessionCapacity];
  uint8_t delivery_digest[32];
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

bool write_check(PersistedPendingAck *record) {
  if (record == nullptr) return false;
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return info != nullptr &&
         mbedtls_md(
             info,
             reinterpret_cast<const uint8_t *>(record),
             offsetof(PersistedPendingAck, check),
             record->check) == 0;
}

bool valid_check(const PersistedPendingAck &record) {
  PersistedPendingAck copy = record;
  if (!write_check(&copy)) return false;
  uint8_t diff = 0;
  for (std::size_t i = 0; i < sizeof(record.check); ++i) {
    diff |= copy.check[i] ^ record.check[i];
  }
  return diff == 0;
}

SimpleNvsStatus read_record(
    const std::string &namespace_name,
    const std::string &key_name,
    PersistedPendingAck *record) {
  nvs_handle_t handle = 0;
  const esp_err_t opened = nvs_open(namespace_name.c_str(), NVS_READONLY, &handle);
  if (opened == ESP_ERR_NVS_NOT_FOUND || opened == ESP_ERR_NVS_NOT_INITIALIZED ||
      opened == ESP_ERR_NVS_INVALID_STATE) {
    return SimpleNvsStatus::MISSING;
  }
  if (opened != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  std::size_t size = sizeof(*record);
  const esp_err_t error = nvs_get_blob(handle, key_name.c_str(), record, &size);
  nvs_close(handle);
  if (error == ESP_ERR_NVS_NOT_FOUND) return SimpleNvsStatus::MISSING;
  if (error != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  return size == sizeof(*record) ? SimpleNvsStatus::OK : SimpleNvsStatus::CORRUPT;
}

SimpleNvsStatus write_record(
    const std::string &namespace_name,
    const std::string &key_name,
    const PersistedPendingAck &record) {
  nvs_handle_t handle = 0;
  esp_err_t error = nvs_open(namespace_name.c_str(), NVS_READWRITE, &handle);
  if (error != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  error = nvs_set_blob(handle, key_name.c_str(), &record, sizeof(record));
  if (error == ESP_OK) error = nvs_commit(handle);
  nvs_close(handle);
  return error == ESP_OK ? SimpleNvsStatus::OK : SimpleNvsStatus::IO_ERROR;
}

}  // namespace

SimpleNvsStatus NvsPendingPairingAckStoreV2::load(PendingPairingAckV2 *state) {
  if (state == nullptr || namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  PersistedPendingAck record{};
  const SimpleNvsStatus status = read_record(namespace_name_, key_name_, &record);
  if (status != SimpleNvsStatus::OK) return status;
  if (record.magic != kAckMagic || record.version != kAckVersion ||
      !valid_check(record) || !terminated(record.manager_host) ||
      !terminated(record.pairing_path) || !terminated(record.session_id)) {
    return SimpleNvsStatus::CORRUPT;
  }
  PendingPairingAckV2 candidate;
  candidate.manager_host = record.manager_host;
  candidate.manager_port = record.manager_port;
  candidate.pairing_path = record.pairing_path;
  candidate.session_id = record.session_id;
  std::copy(
      std::begin(record.delivery_digest),
      std::end(record.delivery_digest),
      candidate.delivery_digest.begin());
  if (!candidate.valid()) {
    candidate.clear();
    return SimpleNvsStatus::CORRUPT;
  }
  *state = std::move(candidate);
  return SimpleNvsStatus::OK;
}

SimpleNvsStatus NvsPendingPairingAckStoreV2::save(const PendingPairingAckV2 &state) {
  if (!state.valid() || namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  PersistedPendingAck record{};
  record.magic = kAckMagic;
  record.version = kAckVersion;
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

SimpleNvsStatus NvsPendingPairingAckStoreV2::erase() {
  if (namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  nvs_handle_t handle = 0;
  esp_err_t error = nvs_open(namespace_name_.c_str(), NVS_READWRITE, &handle);
  if (error != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  error = nvs_erase_key(handle, key_name_.c_str());
  if (error == ESP_ERR_NVS_NOT_FOUND) error = ESP_OK;
  if (error == ESP_OK) error = nvs_commit(handle);
  nvs_close(handle);
  return error == ESP_OK ? SimpleNvsStatus::OK : SimpleNvsStatus::IO_ERROR;
}
#endif  // USE_ESP32

}  // namespace esphome::greenhouse_n3w_core
