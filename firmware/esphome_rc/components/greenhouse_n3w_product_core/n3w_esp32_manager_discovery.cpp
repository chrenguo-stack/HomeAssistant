#include "n3w_esp32_manager_discovery.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>

#include "esphome/core/hal.h"
#include "esp_random.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint16_t kDiscoveryPort = 47111;
constexpr uint32_t kDiscoveryCollectWindowMs = 1000;
constexpr std::size_t kDiscoveryDatagramMaxBytes = 1400;

}

bool Esp32ManagerDiscoveryNetwork::collect_manager_discovery(
    const std::string &request_json,
    std::size_t max_datagrams,
    std::vector<SimpleDiscoveryDatagram> *datagrams) {
  if (request_json.empty() || datagrams == nullptr || max_datagrams == 0U) return false;
  datagrams->clear();
  const std::size_t limit =
      std::min(max_datagrams, kManagerDiscoveryMaxParsedDatagrams);

  const int fd = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  if (fd < 0) return false;

  int broadcast = 1;
  bool ok = ::setsockopt(
                fd,
                SOL_SOCKET,
                SO_BROADCAST,
                &broadcast,
                sizeof(broadcast)) == 0;

  sockaddr_in target{};
  target.sin_family = AF_INET;
  target.sin_port = htons(kDiscoveryPort);
  target.sin_addr.s_addr = htonl(INADDR_BROADCAST);
  if (ok) {
    ok = ::sendto(
             fd,
             request_json.data(),
             request_json.size(),
             0,
             reinterpret_cast<sockaddr *>(&target),
             sizeof(target)) ==
         static_cast<ssize_t>(request_json.size());
  }

  const uint32_t started_ms = millis();
  while (ok && datagrams->size() < limit) {
    const uint32_t elapsed_ms = millis() - started_ms;
    if (elapsed_ms >= kDiscoveryCollectWindowMs) break;
    const uint32_t remaining_ms = kDiscoveryCollectWindowMs - elapsed_ms;

    fd_set read_set;
    FD_ZERO(&read_set);
    FD_SET(fd, &read_set);
    timeval timeout{};
    timeout.tv_sec = static_cast<long>(remaining_ms / 1000U);
    timeout.tv_usec = static_cast<long>((remaining_ms % 1000U) * 1000U);
    const int ready = ::select(fd + 1, &read_set, nullptr, nullptr, &timeout);
    if (ready <= 0) break;

    std::array<char, kDiscoveryDatagramMaxBytes + 1U> buffer{};
    sockaddr_in source{};
    socklen_t source_size = sizeof(source);
    const ssize_t received = ::recvfrom(
        fd,
        buffer.data(),
        kDiscoveryDatagramMaxBytes,
        0,
        reinterpret_cast<sockaddr *>(&source),
        &source_size);
    if (received <= 0 || source.sin_family != AF_INET) continue;

    std::array<char, INET_ADDRSTRLEN> source_text{};
    if (::inet_ntop(
            AF_INET,
            &source.sin_addr,
            source_text.data(),
            source_text.size()) == nullptr) {
      continue;
    }

    datagrams->push_back(SimpleDiscoveryDatagram{
        std::string(buffer.data(), static_cast<std::size_t>(received)),
        std::string(source_text.data()),
    });
  }

  ::close(fd);
  return ok && !datagrams->empty();
}

bool Esp32ManagerDiscoveryRandom::fill_discovery_random(
    uint8_t *data,
    std::size_t size) {
  if (data == nullptr || size == 0U) return false;
  esp_fill_random(data, size);
  return std::any_of(
      data,
      data + size,
      [](uint8_t value) { return value != 0U; });
}

}
