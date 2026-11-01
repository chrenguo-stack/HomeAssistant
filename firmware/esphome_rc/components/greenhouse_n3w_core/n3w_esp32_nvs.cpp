#include "n3w_esp32_nvs.h"

#ifdef USE_ESP32

#include <cstddef>
#include <cstdint>

#include "nvs.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint32_t kMagic = 0x4E335742U;  // "N3WB"
constexpr uint16_t kVersion = 1U;
constexpr uint64_t kSessionMask = 0xA59D3C7E62F148B5ULL;

struct PersistedBootState {
  uint32_t magic;
  uint16_t version;
  uint16_t reserved;
  uint64_t last_session;
  uint64_t session_check;
};

bool valid_record(const PersistedBootState &record) {
  return record.magic == kMagic &&
         record.version == kVersion &&
         record.reserved == 0 &&
         record.session_check == (record.last_session ^ kSessionMask);
}

StoreStatus map_open_error(esp_err_t error) {
  if (error == ESP_ERR_NVS_NOT_FOUND ||
      error == ESP_ERR_NVS_NOT_INITIALIZED ||
      error == ESP_ERR_NVS_INVALID_STATE)
    return StoreStatus::MISSING;
  return StoreStatus::IO_ERROR;
}

}  // namespace

StoreStatus NvsBootSessionStore::load(uint64_t *last_session) {
  if (last_session == nullptr || this->namespace_name_.empty() ||
      this->key_name_.empty())
    return StoreStatus::IO_ERROR;

  nvs_handle_t handle = 0;
  esp_err_t error =
      nvs_open(this->namespace_name_.c_str(), NVS_READONLY, &handle);
  if (error != ESP_OK)
    return map_open_error(error);

  PersistedBootState record{};
  std::size_t length = sizeof(record);
  error = nvs_get_blob(
      handle, this->key_name_.c_str(), &record, &length);
  nvs_close(handle);

  if (error == ESP_ERR_NVS_NOT_FOUND)
    return StoreStatus::MISSING;
  if (error != ESP_OK)
    return StoreStatus::IO_ERROR;
  if (length != sizeof(record) || !valid_record(record))
    return StoreStatus::CORRUPT;

  *last_session = record.last_session;
  return StoreStatus::OK;
}

StoreStatus NvsBootSessionStore::save(uint64_t last_session) {
  if (this->namespace_name_.empty() || this->key_name_.empty())
    return StoreStatus::IO_ERROR;

  PersistedBootState record{
      kMagic,
      kVersion,
      0,
      last_session,
      last_session ^ kSessionMask,
  };

  nvs_handle_t handle = 0;
  esp_err_t error =
      nvs_open(this->namespace_name_.c_str(), NVS_READWRITE, &handle);
  if (error != ESP_OK)
    return StoreStatus::IO_ERROR;

  error = nvs_set_blob(
      handle, this->key_name_.c_str(), &record, sizeof(record));
  if (error == ESP_OK)
    error = nvs_commit(handle);
  nvs_close(handle);
  return error == ESP_OK ? StoreStatus::OK : StoreStatus::IO_ERROR;
}

}  // namespace esphome::greenhouse_n3w_core

#endif  // USE_ESP32
