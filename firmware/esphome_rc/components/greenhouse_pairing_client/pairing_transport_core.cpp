#include "pairing_transport_core.h"

#include <algorithm>
#include <cctype>
#include <limits>

#include "pairing_client_core.h"

namespace esphome::greenhouse_pairing_client {

bool PairingTransportCore::validate_limits(const PairingTransportLimits &limits) {
  return limits.udp_port != 0 && limits.udp_attempts >= 1 &&
         limits.udp_attempts <= UDP_DISCOVERY_MAX_ATTEMPTS &&
         limits.udp_initial_backoff_ms >= 50 && limits.udp_initial_backoff_ms <= 5000 &&
         limits.mdns_timeout_ms >= 100 && limits.mdns_timeout_ms <= 5000 &&
         limits.http_timeout_ms >= 250 && limits.http_timeout_ms <= HTTP_TIMEOUT_MAX_MS &&
         limits.response_max_bytes >= 1024 && limits.response_max_bytes <= HTTP_RESPONSE_MAX_BYTES;
}

uint32_t PairingTransportCore::retry_delay_ms(const PairingTransportLimits &limits,
                                              uint8_t attempt_index) {
  if (!validate_limits(limits) || attempt_index >= limits.udp_attempts)
    return 0;
  const uint8_t exponent = std::min<uint8_t>(attempt_index, 6);
  const uint64_t delay = static_cast<uint64_t>(limits.udp_initial_backoff_ms) << exponent;
  return static_cast<uint32_t>(std::min<uint64_t>(delay, 30000));
}

bool PairingTransportCore::validate_udp_datagram_size(size_t payload_size) {
  return payload_size > 0 && payload_size <= UDP_DISCOVERY_MAX_DATAGRAM;
}

bool PairingTransportCore::validate_http_response(const HttpResponseMetadata &metadata) {
  return metadata.status_code == 200 && metadata.content_type == "application/json" &&
         metadata.body_size <= HTTP_RESPONSE_MAX_BYTES && !metadata.redirect_observed;
}

bool PairingTransportCore::parse_uint16(const std::string &value, uint16_t *output) {
  uint32_t parsed = 0;
  if (!parse_uint32(value, &parsed) || parsed > std::numeric_limits<uint16_t>::max() ||
      output == nullptr)
    return false;
  *output = static_cast<uint16_t>(parsed);
  return true;
}

bool PairingTransportCore::parse_uint32(const std::string &value, uint32_t *output) {
  if (output == nullptr || value.empty() || value.size() > 10 ||
      !std::all_of(value.begin(), value.end(), [](char character) {
        return std::isdigit(static_cast<unsigned char>(character)) != 0;
      }))
    return false;
  uint64_t parsed = 0;
  for (const char character : value) {
    parsed = parsed * 10U + static_cast<uint64_t>(character - '0');
    if (parsed > std::numeric_limits<uint32_t>::max())
      return false;
  }
  *output = static_cast<uint32_t>(parsed);
  return true;
}

std::string PairingTransportCore::build_base_url(const std::string &scheme,
                                                 const std::string &host, uint16_t port,
                                                 const std::string &pairing_path) {
  if ((scheme != "http" && scheme != "https") ||
      !PairingClientCore::valid_local_host(host) || port == 0 || pairing_path.empty() ||
      pairing_path.front() != '/' || pairing_path.size() > 256 ||
      pairing_path.rfind("//", 0) == 0)
    return {};
  std::string normalized = pairing_path;
  while (normalized.size() > 1 && normalized.back() == '/')
    normalized.pop_back();
  return scheme + "://" + host + ":" + std::to_string(port) + normalized;
}

std::string PairingTransportCore::build_session_url(const std::string &base_url,
                                                    const std::string &session_id,
                                                    const std::string &action) {
  if (base_url.empty() || !PairingClientCore::valid_request_id(session_id) ||
      (action != "establish" && action != "credentials" && action != "ack" &&
       action != "abort" && action != "status"))
    return {};
  return base_url + "/sessions/" + session_id + "/" + action;
}

}  // namespace esphome::greenhouse_pairing_client
