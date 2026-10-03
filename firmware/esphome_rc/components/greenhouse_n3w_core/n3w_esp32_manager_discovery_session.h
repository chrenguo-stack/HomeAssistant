#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "n3w_manager_discovery.h"

namespace esphome::greenhouse_n3w_core {

enum class Esp32ManagerDiscoverySessionStatus : uint8_t {
  IDLE = 0,
  IN_PROGRESS,
  COMPLETE,
  FAILED,
};

class Esp32ManagerDiscoverySession {
 public:
  ~Esp32ManagerDiscoverySession();

  bool begin(const std::string &request_json, uint64_t now_ms);
  Esp32ManagerDiscoverySessionStatus poll(uint64_t now_ms);
  void reset();

  bool active() const {
    return status_ == Esp32ManagerDiscoverySessionStatus::IN_PROGRESS;
  }
  Esp32ManagerDiscoverySessionStatus status() const { return status_; }
  const std::vector<SimpleDiscoveryDatagram> &datagrams() const {
    return datagrams_;
  }

 private:
  void close_socket_();

  int fd_{-1};
  uint64_t started_ms_{0};
  Esp32ManagerDiscoverySessionStatus status_{
      Esp32ManagerDiscoverySessionStatus::IDLE};
  std::vector<SimpleDiscoveryDatagram> datagrams_{};
};

}
