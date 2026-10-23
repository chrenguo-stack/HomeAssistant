#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "n3w_manager_discovery.h"

namespace esphome::greenhouse_n3w_core {

class Esp32ManagerDiscoveryNetwork : public SimpleManagerDiscoveryNetwork {
 public:
  bool collect_manager_discovery(
      const std::string &request_json,
      std::size_t max_datagrams,
      std::vector<SimpleDiscoveryDatagram> *datagrams) override;
};

class Esp32ManagerDiscoveryRandom : public SimpleManagerDiscoveryRandom {
 public:
  bool fill_discovery_random(uint8_t *data, std::size_t size) override;
};

}
