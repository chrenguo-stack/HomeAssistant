#include "pairing_transport_core.h"

#include <cassert>
#include <iostream>

using namespace esphome::greenhouse_pairing_client;

int main() {
  PairingTransportLimits limits;
  assert(PairingTransportCore::validate_limits(limits));
  assert(PairingTransportCore::retry_delay_ms(limits, 0) == 250);
  assert(PairingTransportCore::retry_delay_ms(limits, 1) == 500);
  assert(PairingTransportCore::retry_delay_ms(limits, 2) == 1000);
  assert(PairingTransportCore::retry_delay_ms(limits, 3) == 0);

  assert(PairingTransportCore::validate_udp_datagram_size(1));
  assert(PairingTransportCore::validate_udp_datagram_size(1400));
  assert(!PairingTransportCore::validate_udp_datagram_size(0));
  assert(!PairingTransportCore::validate_udp_datagram_size(1401));
  assert(PairingTransportCore::validate_udp_target("255.255.255.255"));
  assert(PairingTransportCore::validate_udp_target("192.168.1.20"));
  assert(PairingTransportCore::validate_udp_target("169.254.10.20"));
  assert(!PairingTransportCore::validate_udp_target("0.0.0.0"));
  assert(!PairingTransportCore::validate_udp_target("8.8.8.8"));
  assert(!PairingTransportCore::validate_udp_target("manager.local"));

  assert(PairingTransportCore::validate_http_response(
      {.status_code = 200, .content_type = "application/json", .body_size = 16384,
       .redirect_observed = false}));
  assert(!PairingTransportCore::validate_http_response(
      {.status_code = 302, .content_type = "application/json", .body_size = 0,
       .redirect_observed = true}));
  assert(!PairingTransportCore::validate_http_response(
      {.status_code = 200, .content_type = "text/plain", .body_size = 12,
       .redirect_observed = false}));

  uint16_t small = 0;
  uint32_t large = 0;
  assert(PairingTransportCore::parse_uint16("47111", &small) && small == 47111);
  assert(!PairingTransportCore::parse_uint16("65536", &small));
  assert(PairingTransportCore::parse_uint32("3600", &large) && large == 3600);
  assert(!PairingTransportCore::parse_uint32("3x", &large));

  assert(PairingTransportCore::validate_pairing_path("/v1/pairing"));
  assert(PairingTransportCore::validate_pairing_path("/v1/pairing/"));
  assert(!PairingTransportCore::validate_pairing_path("/v1//pairing"));
  assert(!PairingTransportCore::validate_pairing_path("/v1/../pairing"));
  assert(!PairingTransportCore::validate_pairing_path("/v1/pairing?next=/claim"));
  assert(!PairingTransportCore::validate_pairing_path("/v1/%2e%2e/pairing"));

  const std::string base = PairingTransportCore::build_base_url(
      "http", "manager.local", 47110, "/v1/pairing/");
  assert(base == "http://manager.local:47110/v1/pairing");
  assert(PairingTransportCore::build_session_url(
             base, "11111111-2222-4333-8444-555555555555", "credentials") ==
         "http://manager.local:47110/v1/pairing/sessions/11111111-2222-4333-8444-555555555555/credentials");
  assert(PairingTransportCore::build_base_url("ftp", "manager.local", 47110,
                                               "/v1/pairing")
             .empty());
  assert(PairingTransportCore::build_base_url("http", "manager.local", 47110,
                                               "/v1/../pairing")
             .empty());

  std::cout << "stage2c2 transport core tests passed\n";
  return 0;
}
