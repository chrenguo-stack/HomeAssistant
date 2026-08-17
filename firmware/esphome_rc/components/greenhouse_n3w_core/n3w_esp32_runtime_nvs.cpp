#include "n3w_esp32_runtime_nvs.h"

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
bool valid_runtime_text(const std::string &value, std::size_t maximum) {
  return !value.empty() && value.size() <= maximum &&
         std::none_of(value.begin(), value.end(), [](char ch) { return ch == '\0'; });
}
}  // namespace

bool ProvisionedBrokerStateV2::valid() const {
  return valid_simple_identity_v2(system_id) && valid_simple_identity_v2(node_id) &&
         valid_runtime_text(broker_host, 253) && broker_port > 0 &&
         valid_runtime_text(broker_tls_server_name, 253) &&
         valid_runtime_text(ca_pem, 4096) &&
         ca_pem.find("-----BEGIN CERTIFICATE-----") != std::string::npos &&
         valid_runtime_text(mqtt_username, 128) &&
         valid_runtime_text(mqtt_password, 256) &&
         valid_runtime_text(mqtt_client_id, 128) && credential_generation > 0;
}

void ProvisionedBrokerStateV2::clear() {
  system_id.clear();
  node_id.clear();
  broker_host.clear();
  broker_port = 0;
  broker_tls_server_name.clear();
  ca_pem.clear();
  mqtt_username.clear();
  std::fill(mqtt_password.begin(), mqtt_password.end(), '\0');
  mqtt_password.clear();
  mqtt_client_id.clear();
  credential_generation = 0;
}

#ifdef USE_ESP32
namespace {

constexpr uint32_t kBrokerMagic = 0x4E334232U;  // N3B2
constexpr uint16_t kRecordVersion = 1U;
constexpr std::size_t kIdCapacity = 65U;
constexpr std::size_t kHostCapacity = 254U;
constexpr std::size_t kCaCapacity = 4097U;
constexpr std::size_t kUsernameCapacity = 129U;
constexpr std::size_t kPasswordCapacity = 257U;
constexpr std::size_t kClientIdCapacity = 129U;

struct PersistedBrokerState {
  uint32_t magic;
  uint16_t version;
  uint16_t broker_port;
  uint32_t credential_generation;
  char system_id[kIdCapacity];
  char node_id[kIdCapacity];
  char broker_host[kHostCapacity];
  char broker_tls_server_name[kHostCapacity];
  char ca_pem[kCaCapacity];
  char mqtt_username[kUsernameCapacity];
  char mqtt_password[kPasswordCapacity];
  char mqtt_client_id[kClientIdCapacity];
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

bool write_check(PersistedBrokerState *record) {
  if (record == nullptr) return false;
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return info != nullptr &&
         mbedtls_md(
             info,
             reinterpret_cast<const uint8_t *>(record),
             offsetof(PersistedBrokerState, check),
             record->check) == 0;
}

bool valid_check(const PersistedBrokerState &record) {
  PersistedBrokerState copy = record;
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
    PersistedBrokerState *record) {
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
    const PersistedBrokerState &record) {
  nvs_handle_t handle = 0;
  esp_err_t error = nvs_open(namespace_name.c_str(), NVS_READWRITE, &handle);
  if (error != ESP_OK) return SimpleNvsStatus::IO_ERROR;
  error = nvs_set_blob(handle, key_name.c_str(), &record, sizeof(record));
  if (error == ESP_OK) error = nvs_commit(handle);
  nvs_close(handle);
  return error == ESP_OK ? SimpleNvsStatus::OK : SimpleNvsStatus::IO_ERROR;
}

}  // namespace

SimpleNvsStatus NvsProvisionedBrokerStoreV2::load(ProvisionedBrokerStateV2 *state) {
  if (state == nullptr || namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  PersistedBrokerState record{};
  const SimpleNvsStatus status = read_record(namespace_name_, key_name_, &record);
  if (status != SimpleNvsStatus::OK) return status;
  if (record.magic != kBrokerMagic || record.version != kRecordVersion ||
      !valid_check(record) || !terminated(record.system_id) ||
      !terminated(record.node_id) || !terminated(record.broker_host) ||
      !terminated(record.broker_tls_server_name) || !terminated(record.ca_pem) ||
      !terminated(record.mqtt_username) || !terminated(record.mqtt_password) ||
      !terminated(record.mqtt_client_id)) {
    return SimpleNvsStatus::CORRUPT;
  }
  ProvisionedBrokerStateV2 candidate;
  candidate.system_id = record.system_id;
  candidate.node_id = record.node_id;
  candidate.broker_host = record.broker_host;
  candidate.broker_port = record.broker_port;
  candidate.broker_tls_server_name = record.broker_tls_server_name;
  candidate.ca_pem = record.ca_pem;
  candidate.mqtt_username = record.mqtt_username;
  candidate.mqtt_password = record.mqtt_password;
  candidate.mqtt_client_id = record.mqtt_client_id;
  candidate.credential_generation = record.credential_generation;
  if (!candidate.valid()) {
    candidate.clear();
    return SimpleNvsStatus::CORRUPT;
  }
  *state = std::move(candidate);
  return SimpleNvsStatus::OK;
}

SimpleNvsStatus NvsProvisionedBrokerStoreV2::save(const ProvisionedBrokerStateV2 &state) {
  if (!state.valid() || namespace_name_.empty() || key_name_.empty()) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  PersistedBrokerState record{};
  record.magic = kBrokerMagic;
  record.version = kRecordVersion;
  record.broker_port = state.broker_port;
  record.credential_generation = state.credential_generation;
  if (!copy_text(state.system_id, record.system_id) ||
      !copy_text(state.node_id, record.node_id) ||
      !copy_text(state.broker_host, record.broker_host) ||
      !copy_text(state.broker_tls_server_name, record.broker_tls_server_name) ||
      !copy_text(state.ca_pem, record.ca_pem) ||
      !copy_text(state.mqtt_username, record.mqtt_username) ||
      !copy_text(state.mqtt_password, record.mqtt_password) ||
      !copy_text(state.mqtt_client_id, record.mqtt_client_id) ||
      !write_check(&record)) {
    return SimpleNvsStatus::INVALID_ARGUMENT;
  }
  return write_record(namespace_name_, key_name_, record);
}

SimpleNvsStatus NvsProvisionedBrokerStoreV2::erase() {
  if (namespace_name_.empty() || key_name_.empty()) return SimpleNvsStatus::INVALID_ARGUMENT;
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
