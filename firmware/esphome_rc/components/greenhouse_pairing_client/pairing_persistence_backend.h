#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#ifdef USE_ESP32
#include "nvs.h"
#endif

namespace esphome::greenhouse_pairing_client {

static constexpr size_t PERSISTENCE_MAX_BLOB_BYTES = 16384;

enum class PersistenceReadResult : uint8_t {
  OK = 0,
  NOT_FOUND = 1,
  ERROR = 2,
};

class PairingPersistenceBackend {
 public:
  virtual ~PairingPersistenceBackend() = default;

  virtual PersistenceReadResult read_blob(const char *key,
                                          std::vector<uint8_t> *value) = 0;
  virtual bool write_blob(const char *key, const uint8_t *value,
                          size_t length) = 0;
  virtual bool erase_key(const char *key) = 0;
  virtual bool commit() = 0;
};

#ifdef USE_ESP32
class EspIdfNvsPersistenceBackend final : public PairingPersistenceBackend {
 public:
  EspIdfNvsPersistenceBackend(const std::string &partition_label,
                              const std::string &namespace_name);
  ~EspIdfNvsPersistenceBackend() override;

  EspIdfNvsPersistenceBackend(const EspIdfNvsPersistenceBackend &) = delete;
  EspIdfNvsPersistenceBackend &operator=(
      const EspIdfNvsPersistenceBackend &) = delete;

  bool open();
  bool opened() const { return this->opened_; }

  PersistenceReadResult read_blob(const char *key,
                                  std::vector<uint8_t> *value) override;
  bool write_blob(const char *key, const uint8_t *value,
                  size_t length) override;
  bool erase_key(const char *key) override;
  bool commit() override;

 private:
  std::string partition_label_;
  std::string namespace_name_;
  nvs_handle_t handle_{0};
  bool opened_{false};
};
#endif

}  // namespace esphome::greenhouse_pairing_client
