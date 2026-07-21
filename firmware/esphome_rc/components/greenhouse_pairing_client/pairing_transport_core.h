#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace esphome::greenhouse_pairing_client {

static constexpr size_t UDP_DISCOVERY_MAX_DATAGRAM = 1400;
static constexpr size_t HTTP_RESPONSE_MAX_BYTES = 16 * 1024;
static constexpr uint32_t HTTP_TIMEOUT_MAX_MS = 5000;
static constexpr uint8_t UDP_DISCOVERY_MAX_ATTEMPTS = 5;

struct PairingTransportLimits {
  uint16_t udp_port{47111};
  uint8_t udp_attempts{3};
  uint32_t udp_initial_backoff_ms{250};
  uint32_t mdns_timeout_ms{1000};
  uint32_t http_timeout_ms{5000};
  size_t response_max_bytes{HTTP_RESPONSE_MAX_BYTES};
};

struct HttpResponseMetadata {
  int status_code{0};
  std::string content_type;
  size_t body_size{0};
  bool redirect_observed{false};
};

class PairingTransportCore {
 public:
  static bool validate_limits(const PairingTransportLimits &limits);
  static uint32_t retry_delay_ms(const PairingTransportLimits &limits, uint8_t attempt_index);
  static bool validate_udp_datagram_size(size_t payload_size);
  static bool validate_http_response(const HttpResponseMetadata &metadata);
  static bool parse_uint16(const std::string &value, uint16_t *output);
  static bool parse_uint32(const std::string &value, uint32_t *output);
  static std::string build_base_url(const std::string &scheme, const std::string &host,
                                    uint16_t port, const std::string &pairing_path);
  static std::string build_session_url(const std::string &base_url,
                                       const std::string &session_id,
                                       const std::string &action);
};

}  // namespace esphome::greenhouse_pairing_client
