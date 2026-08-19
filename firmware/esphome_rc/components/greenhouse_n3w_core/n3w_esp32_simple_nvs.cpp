#include "n3w_esp32_simple_nvs.h"

#ifdef USE_ESP32

#include <algorithm>
#include <cstddef>
#include <cstring>
#include <iterator>

#include "esp_random.h"
#include "mbedtls/md.h"
#include "nvs.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint32_t kSetupMagic = 0x4E335332U;  // N3S2
constexpr uint32_t kPeerMagic = 0x4E335032U;   // N3P2
constexpr uint16_t kRecordVersion = 1U;
constexpr std::size_t kIdCapacity = 65U;

struct PersistedSetupSecret {
  uint32_t magic;
  uint16_t version;
  uint16_t reserved;
  uint8_t secret[kSetupSecretBytes];
  uint8_t check[32];
};

struct PersistedPeerState {
  uint32_t magic;
  uint16_t version;
  uint16_t reserved;
  char system_id[kIdCapacity];
  char node_id[kIdCapacity];
  uint64_t peer_trust_generation;
  uint8_t system_peer_key[kSystemPeerKeyBytes];
  uint32_t n3w_key_epoch;
  uint8_t n3w_application_key[kApplicationKeyBytes];
  uint8_t check[32];
};

template<typename Record>
bool write_check(Record *record) {
  if (record == nullptr) return false;
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr) return false;
  return mbedtls_md(
             info,
             reinterpret_cast<const uint8_t *>(record),
             offsetof(Record, check),
             record->check) == 0;
}

template<typename Record>
bool valid_check(const Record &record) {
  Record copy = record;
  if (!write_check(&copy)) return false;
  uint8_t diff = 0;
  for (std::size_t i = 0; i < sizeof(record.check); ++i) {
    diff |= copy.check[i] ^ record.check[i];
  }
  return diff == 0;
}

bool nonzero(const uint8_t *data, std::size_t size) {
  if (data == nullptr) return false;
  uint8_t aggregate = 0;
  for (std::size_t i = 0; i < size; ++i) aggregate |= data[i];
  return aggregate != 0;
}

SimpleNvsStatus map_read_error(esp_err_t error) {
  if (error == ESP_ERR_NVS_NOT_FOUND || error == ESP_ERR_NVS_NOT_INITIALIZED ||
      error == ESP_ERR_NVS_INVALID_STATE) {
    return SimpleNvsStatus::MISSING;
  }
  return SimpleNvsStatus::IO_ERROR;
}

SimpleNvsStatus read_blob(
    const std::string &namespace_name,
    const std::string &key_name,
    void *record,
    std::size_t expected_size) {
  if (namespace_name.empty() || key_name.empty() || record == nullptr || expected_size == 0) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  nvs_handle_t handle = 0;
  esp_err_t error = nvs_open(namespace_name.c_str(), NVS_READONLY, &handle);
  if (error != ESP_OK) return map_read_error(error);
  std::size_t length = expected_size;
  error = nvs_get_blob(handle, key_name.c_str(), record, &length);
  nvs_close(handle);
  if (error != ESP_OK) return map_read_error(error);
  return length == expected_size ? SimpleNvsStatus::OK : SimpleNvsStatus::CORRUPT;
}

SimpleNvsStatus write_blob(
    const std::string &namespace_name,
    const std::string &key_name,
    const void *record,
    std::size_t size) {
  if (namespace_name.empty() || key_name.empty() || record == nullptr || size == 0) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  nvs_handle_t handle = 0;
  esp_err_t error = nvs_open(namespace_name.c_str(), NVS_READWRITE, &handle);
  if (error != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  error = nvs_set_blob(handle, key_name.c_str(), record, size);
  if (error == ESP_OK) error = nvs_commit(handle);
  nvs_close(handle);
  return error == ESP_OK ? SimpleNvsStatus::OK : SimpleNvsStatus::IO_ERROR;
}

SimpleNvsStatus erase_key(
    const std::string &namespace_name,
    const std::string &key_name) {
  if (namespace_name.empty() || key_name.empty()) return SimpleNvsStatus::INVALID_ARGUMENT;
  nvs_handle_t handle = 0;
  esp_err_t error = nvs_open(namespace_name.c_str(), NVS_READWRITE, &handle);
  if (error != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  error = nvs_erase_key(handle, key_name.c_str());
  if (error == ESP_ERR_NVS_NOT_FOUND) error = ESP_OK;
  if (error == ESP_OK) error = nvs_commit(handle);
  nvs_close(handle);
  return error == ESP_OK ? SimpleNvsStatus::OK : SimpleNvsStatus::IO_ERROR;
}

bool copy_id(const std::string &source, char *destination) {
  if (!valid_simple_identity_v2(source) || destination == nullptr || source.size() >= kIdCapacity) return false;
  std::memset(destination, 0, kIdCapacity);
  std::memcpy(destination, source.data(), source.size());
  return true;
}

bool terminated_id(const char *value) {
  if (value == nullptr) return false;
  return std::memchr(value, '\0', kIdCapacity) != nullptr;
}

}  // namespace

bool ProvisionedPeerStateV2::valid() const {
  return valid_simple_identity_v2(system_id) && valid_simple_identity_v2(node_id) &&
         peer_trust_generation > 0 && n3w_key_epoch > 0 &&
         nonzero(system_peer_key.data(), system_peer_key.size()) &&
         nonzero(n3w_application_key.data(), n3w_application_key.size());
}

void ProvisionedPeerStateV2::clear() {
  system_id.clear();
  node_id.clear();
  peer_trust_generation = 0;
  std::fill(system_peer_key.begin(), system_peer_key.end(), 0);
  n3w_key_epoch = 0;
  std::fill(n3w_application_key.begin(), n3w_application_key.end(), 0);
}

SimpleNvsStatus NvsSetupSecretStore::load_or_create(SetupSecret *secret) {
  if (secret == nullptr || namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  PersistedSetupSecret record{};
  SimpleNvsStatus status = read_blob(namespace_name_, key_name_, &record, sizeof(record));
  if (status == SimpleNvsStatus::OK) {
    if (record.magic != kSetupMagic || record.version != kRecordVersion ||
        record.reserved != 0 || !valid_check(record) ||
        !nonzero(record.secret, sizeof(record.secret))) {
      return SimpleNvsStatus::CORRUPT;
    }
    std::copy_n(record.secret, secret->size(), secret->begin());
    return SimpleNvsStatus::OK;
  }
  if (status != SimpleNvsStatus::MISSING) return status;

  record.magic = kSetupMagic;
  record.version = kRecordVersion;
  record.reserved = 0;
  esp_fill_random(record.secret, sizeof(record.secret));
  if (!nonzero(record.secret, sizeof(record.secret)) || !write_check(&record)) {
    std::fill(std::begin(record.secret), std::end(record.secret), 0);
    return SimpleNvsStatus::IO_ERROR;
  }
  status = write_blob(namespace_name_, key_name_, &record, sizeof(record));
  if (status != SimpleNvsStatus::OK) {
    std::fill(std::begin(record.secret), std::end(record.secret), 0);
    return status;
  }
  std::copy_n(record.secret, secret->size(), secret->begin());
  std::fill(std::begin(record.secret), std::end(record.secret), 0);
  return SimpleNvsStatus::CREATED;
}

SimpleNvsStatus NvsSetupSecretStore::erase() {
  return erase_key(namespace_name_, key_name_);
}

SimpleNvsStatus NvsProvisionedPeerStoreV2::load(ProvisionedPeerStateV2 *state) {
  if (state == nullptr || namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  PersistedPeerState record{};
  SimpleNvsStatus status = read_blob(namespace_name_, key_name_, &record, sizeof(record));
  if (status != SimpleNvsStatus::OK) return status;
  if (record.magic != kPeerMagic || record.version != kRecordVersion ||
      record.reserved != 0 || !terminated_id(record.system_id) ||
      !terminated_id(record.node_id) || !valid_check(record)) {
    return SimpleNvsStatus::CORRUPT;
  }
  ProvisionedPeerStateV2 candidate;
  candidate.system_id = record.system_id;
  candidate.node_id = record.node_id;
  candidate.peer_trust_generation = record.peer_trust_generation;
  std::copy_n(record.system_peer_key, candidate.system_peer_key.size(), candidate.system_peer_key.begin());
  candidate.n3w_key_epoch = record.n3w_key_epoch;
  std::copy_n(
      record.n3w_application_key,
      candidate.n3w_application_key.size(),
      candidate.n3w_application_key.begin());
  if (!candidate.valid()) {
    candidate.clear();
    return SimpleNvsStatus::CORRUPT;
  }
  *state = std::move(candidate);
  return SimpleNvsStatus::OK;
}

SimpleNvsStatus NvsProvisionedPeerStoreV2::save(const ProvisionedPeerStateV2 &state) {
  if (!state.valid() || namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  PersistedPeerState record{};
  record.magic = kPeerMagic;
  record.version = kRecordVersion;
  record.reserved = 0;
  if (!copy_id(state.system_id, record.system_id) || !copy_id(state.node_id, record.node_id)) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  record.peer_trust_generation = state.peer_trust_generation;
  std::copy(state.system_peer_key.begin(), state.system_peer_key.end(), record.system_peer_key);
  record.n3w_key_epoch = state.n3w_key_epoch;
  std::copy(
      state.n3w_application_key.begin(),
      state.n3w_application_key.end(),
      record.n3w_application_key);
  if (!write_check(&record)) return SimpleNvsStatus::IO_ERROR;
  return write_blob(namespace_name_, key_name_, &record, sizeof(record));
}

SimpleNvsStatus NvsProvisionedPeerStoreV2::erase() {
  return erase_key(namespace_name_, key_name_);
}

}  // namespace esphome::greenhouse_n3w_core

#endif  // USE_ESP32
