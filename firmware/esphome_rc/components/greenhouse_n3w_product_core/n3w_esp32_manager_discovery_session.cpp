#include "n3w_esp32_manager_discovery_session.h"

#include <array>
#include <cerrno>
#include <limits>

#include "lwip/inet.h"
#include "lwip/sockets.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint16_t kDiscoveryPort = 47111;
constexpr uint64_t kDiscoveryCollectWindowMs = 1000;
constexpr std::size_t kDiscoveryDatagramMaxBytes = 1400;
constexpr std::size_t kDiscoveryPollDatagramLimit = 2;

}

Esp32ManagerDiscoverySession::~Esp32ManagerDiscoverySession() {
  reset();
}

void Esp32ManagerDiscoverySession::close_socket_() {
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
}

void Esp32ManagerDiscoverySession::reset() {
  close_socket_();
  started_ms_ = 0;
  status_ = Esp32ManagerDiscoverySessionStatus::IDLE;
  datagrams_.clear();
}

bool Esp32ManagerDiscoverySession::begin(
    const std::string &request_json,
    uint64_t now_ms) {
  reset();
  if (request_json.empty()) return false;

  fd_ = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  if (fd_ < 0) {
    status_ = Esp32ManagerDiscoverySessionStatus::FAILED;
    return false;
  }

  int broadcast = 1;
  if (::setsockopt(
fd_,
SOL_SOCKET,
SO_BROADCAST,
&broadcast,
sizeof(broadcast)) != 0) {
    close_socket_();
    status_ = Esp32ManagerDiscoverySessionStatus::FAILED;
    return false;
  }

  sockaddr_in target{};
  target.sin_family = AF_INET;
  target.sin_port = htons(kDiscoveryPort);
  target.sin_addr.s_addr = htonl(INADDR_BROADCAST);
  const ssize_t sent = ::sendto(
      fd_,
      request_json.data(),
      request_json.size(),
      0,
      reinterpret_cast<sockaddr *>(&target),
      sizeof(target));
  if (sent != static_cast<ssize_t>(request_json.size())) {
    close_socket_();
    status_ = Esp32ManagerDiscoverySessionStatus::FAILED;
    return false;
  }

  started_ms_ = now_ms;
  status_ = Esp32ManagerDiscoverySessionStatus::IN_PROGRESS;
  return true;
}

Esp32ManagerDiscoverySessionStatus Esp32ManagerDiscoverySession::poll(
    uint64_t now_ms) {
  if (status_ != Esp32ManagerDiscoverySessionStatus::IN_PROGRESS) {
    return status_;
  }

  for (std::size_t count = 0;
       count < kDiscoveryPollDatagramLimit &&
       datagrams_.size() < kManagerDiscoveryMaxParsedDatagrams;
       ++count) {
    std::array<char, kDiscoveryDatagramMaxBytes + 1U> buffer{};
    sockaddr_in source{};
    socklen_t source_size = sizeof(source);
    const ssize_t received = ::recvfrom(
        fd_,
        buffer.data(),
        kDiscoveryDatagramMaxBytes,
        MSG_DONTWAIT,
        reinterpret_cast<sockaddr *>(&source),
        &source_size);
    if (received < 0) {
      if (errno == EAGAIN || errno == EWOULDBLOCK) break;
      close_socket_();
      status_ = Esp32ManagerDiscoverySessionStatus::FAILED;
      return status_;
    }
    if (received == 0) break;
    if (source.sin_family != AF_INET) continue;

    std::array<char, INET_ADDRSTRLEN> source_text{};
    if (::inet_ntop(
  AF_INET,
  &source.sin_addr,
  source_text.data(),
  source_text.size()) == nullptr) {
      continue;
    }
    datagrams_.push_back(SimpleDiscoveryDatagram{
        std::string(buffer.data(), static_cast<std::size_t>(received)),
        std::string(source_text.data()),
    });
  }

  const uint64_t elapsed_ms =
      now_ms >= started_ms_
? now_ms - started_ms_
: std::numeric_limits<uint64_t>::max();
  if (datagrams_.size() >= kManagerDiscoveryMaxParsedDatagrams ||
      elapsed_ms >= kDiscoveryCollectWindowMs) {
    close_socket_();
    status_ = Esp32ManagerDiscoverySessionStatus::COMPLETE;
  }
  return status_;
}

}
