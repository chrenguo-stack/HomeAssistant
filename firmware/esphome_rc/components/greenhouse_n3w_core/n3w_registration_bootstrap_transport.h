#pragma once

#include <cstdint>
#include <string>

namespace esphome::greenhouse_n3w_core {

enum class RegistrationBootstrapTransportError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  CONNECT_FAILED,
  TLS_FAILED,
  PIN_MISMATCH,
  IO_FAILED,
  RESPONSE_TOO_LARGE,
  PROTOCOL_FAILED,
};

struct RegistrationBootstrapHttpResponse {
  int status_code{0};
  std::string body{};

  void clear();
};

class Esp32RegistrationBootstrapTransport {
 public:
  bool post_json(
      const std::string &host,
      uint16_t port,
      const std::string &leaf_sha256,
      const std::string &path,
      const std::string &request_json,
      RegistrationBootstrapHttpResponse *response,
      RegistrationBootstrapTransportError *error);
};

}  // namespace esphome::greenhouse_n3w_core
