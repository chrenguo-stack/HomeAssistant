#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace esphome::greenhouse_n3w_core {

inline constexpr char kRegistrationDiscoveryProtocol[] =
    "gh.n3w.first-registration/1";
inline constexpr char kRegistrationCandidateSchema[] =
    "gh.registration.candidate/1";
inline constexpr char kRegistrationDiscoveryResponseSchema[] =
    "gh.registration.discovery-result/1";
inline constexpr std::size_t kRegistrationDiscoveryMaxCandidates = 4;
inline constexpr uint16_t kRegistrationBootstrapPort = 47110;
inline constexpr uint16_t kRegistrationCandidateTtlSeconds = 30;

struct RegistrationCandidateV1 {
  std::string manager_id;
  std::string system_id;
  std::string system_id_hint;
  std::string host;
  std::string bootstrap_tls_sha256;
  bool busy{false};
  uint16_t bootstrap_port{kRegistrationBootstrapPort};
  std::string bootstrap_path{"/v1/registration/confirm"};
  uint16_t ttl_s{kRegistrationCandidateTtlSeconds};
  uint64_t observed_ms{0};

  bool valid() const;
  bool expired(uint64_t now_ms) const;
};

bool parse_registration_discovery_response(
    const std::string &response_json,
    const std::string &request_id,
    const std::string &nonce_text,
    const std::string &source_ipv4,
    const std::string &local_ipv4,
    const std::string &subnet_mask,
    uint64_t observed_ms,
    RegistrationCandidateV1 *candidate);

class RegistrationDiscovery {
 public:
  bool discover(
      const std::string &hardware_id,
      const std::string &local_ipv4,
      const std::string &subnet_mask,
      uint64_t now_ms,
      std::vector<RegistrationCandidateV1> *candidates);

 private:
  void collect_mdns_(
      const std::string &local_ipv4,
      const std::string &subnet_mask,
      uint64_t observed_ms,
      std::vector<RegistrationCandidateV1> *candidates);
  void collect_udp_(
      const std::string &request_json,
      const std::string &request_id,
      const std::string &nonce_text,
      const std::string &local_ipv4,
      const std::string &subnet_mask,
      uint64_t observed_ms,
      std::vector<RegistrationCandidateV1> *candidates);
  static void append_candidate_(
      const RegistrationCandidateV1 &candidate,
      std::vector<RegistrationCandidateV1> *candidates);
};

}  // namespace esphome::greenhouse_n3w_core
