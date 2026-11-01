#include "pairing_persistence_backend.h"

#include <algorithm>

#ifdef USE_ESP32
#include "esp_err.h"
#include "nvs.h"
#endif

namespace esphome::greenhouse_pairing_client {

#ifdef USE_ESP32
EspIdfNvsPersistenceBackend::EspIdfNvsPersistenceBackend(
    const std::string &partition_label, const std::string &namespace_name)
    : partition_label_(partition_label), namespace_name_(namespace_name) {}

EspIdfNvsPersistenceBackend::~EspIdfNvsPersistenceBackend() {
  if (this->opened_)
    nvs_close(this->handle_);
  this->handle_ = 0;
  this->opened_ = false;
  this->writable_ = false;
  this->namespace_missing_ = false;
  this->poisoned_ = false;
}

bool EspIdfNvsPersistenceBackend::open(PersistenceOpenMode mode) {
  if (this->opened_ || this->namespace_name_.empty() ||
      this->namespace_name_.size() > 15 ||
      this->partition_label_.size() > 15)
    return false;

  this->namespace_missing_ = false;
  this->poisoned_ = false;
  const nvs_open_mode_t open_mode =
      mode == PersistenceOpenMode::READ_ONLY ? NVS_READONLY : NVS_READWRITE;
  esp_err_t status = ESP_FAIL;
  if (this->partition_label_.empty() || this->partition_label_ == "nvs") {
    status = nvs_open(this->namespace_name_.c_str(), open_mode,
                      &this->handle_);
  } else {
    status = nvs_open_from_partition(this->partition_label_.c_str(),
                                     this->namespace_name_.c_str(),
                                     open_mode, &this->handle_);
  }
  this->opened_ = status == ESP_OK;
  this->writable_ = this->opened_ && mode == PersistenceOpenMode::READ_WRITE;
  this->namespace_missing_ =
      !this->opened_ && mode == PersistenceOpenMode::READ_ONLY &&
      status == ESP_ERR_NVS_NOT_FOUND;
  if (!this->opened_) {
    this->handle_ = 0;
    this->writable_ = false;
  }
  return this->opened_;
}

PersistenceReadResult EspIdfNvsPersistenceBackend::read_blob(
    const char *key, std::vector<uint8_t> *value) {
  if (!this->healthy() || key == nullptr || value == nullptr)
    return PersistenceReadResult::ERROR;
  std::fill(value->begin(), value->end(), 0);
  value->clear();

  size_t length = 0;
  esp_err_t status = nvs_get_blob(this->handle_, key, nullptr, &length);
  if (status == ESP_ERR_NVS_NOT_FOUND)
    return PersistenceReadResult::NOT_FOUND;
  if (status != ESP_OK || length == 0 || length > PERSISTENCE_MAX_BLOB_BYTES)
    return PersistenceReadResult::ERROR;

  value->assign(length, 0);
  status = nvs_get_blob(this->handle_, key, value->data(), &length);
  if (status != ESP_OK || length != value->size()) {
    std::fill(value->begin(), value->end(), 0);
    value->clear();
    return PersistenceReadResult::ERROR;
  }
  return PersistenceReadResult::OK;
}

bool EspIdfNvsPersistenceBackend::write_blob(const char *key,
                                             const uint8_t *value,
                                             size_t length) {
  if (!this->writable() || key == nullptr || value == nullptr || length == 0 ||
      length > PERSISTENCE_MAX_BLOB_BYTES)
    return false;
  if (nvs_set_blob(this->handle_, key, value, length) == ESP_OK)
    return true;
  this->poisoned_ = true;
  return false;
}

bool EspIdfNvsPersistenceBackend::erase_key(const char *key) {
  if (!this->writable() || key == nullptr)
    return false;
  const esp_err_t status = nvs_erase_key(this->handle_, key);
  if (status == ESP_OK || status == ESP_ERR_NVS_NOT_FOUND)
    return true;
  this->poisoned_ = true;
  return false;
}

bool EspIdfNvsPersistenceBackend::commit() {
  if (!this->writable())
    return false;
  if (nvs_commit(this->handle_) == ESP_OK)
    return true;
  this->poisoned_ = true;
  return false;
}
#endif

}  // namespace esphome::greenhouse_pairing_client
