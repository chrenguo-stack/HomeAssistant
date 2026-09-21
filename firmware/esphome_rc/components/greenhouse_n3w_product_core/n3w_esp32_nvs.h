#pragma once

#include "n3w_core.h"

#ifdef USE_ESP32

#include <string>
#include <utility>

namespace esphome::greenhouse_n3w_core {

class NvsBootSessionStore final : public BootSessionStore {
 public:
  explicit NvsBootSessionStore(
      std::string namespace_name = "gh_n3w",
      std::string key_name = "boot_state")
      : namespace_name_(std::move(namespace_name)),
        key_name_(std::move(key_name)) {}

  StoreStatus load(uint64_t *last_session) override;
  StoreStatus save(uint64_t last_session) override;

 protected:
  std::string namespace_name_;
  std::string key_name_;
};

}  // namespace esphome::greenhouse_n3w_core

#endif  // USE_ESP32
