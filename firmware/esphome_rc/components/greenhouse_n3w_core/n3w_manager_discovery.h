#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace esphome::greenhouse_n3w_core {

inline constexpr char kSimplePairingProtocol[] = "gh-n3w-simple-pairing/1";
inline constexpr std::size_t kManagerDiscoveryMaxParsedDatagrams = 8;
inline constexpr std::size_t kManagerDiscoveryMaxRetainedCandidates = 3;
inline constexpr std::size_t kManagerDiscoveryMaxAttemptCandidates = 2;
inline constexpr uint16_t kManagerDiscoveryMaxCandidateTtlSeconds = 120;

enum class SimpleManagerDiscoveryError : uint8_t {
  NONE = 0,
  NOT_READY,
  IO_FAILED,
  DISCOVERY_FAILED,
};

struct SimpleManagerCandidateV2 {
  std::string manager_id;
  std::string system_id;
  std::string host;
  uint16_t port{0};
  std::string pairing_path;
  uint16_t ttl_s{0};

  bool valid() const;
};

struct SimpleDiscoveryDatagram {
  std::string response_json;
  std::string source_ipv4;
};

struct SimpleDiscoveryFilterContext {
  std::string expected_system_id;
  std::string local_ipv4;
  std::string subnet_mask;
};

struct SimpleBrokerRecoveryTarget {
  std::string host;
  uint16_t port{0};
  uint16_t ttl_s{0};
};

class SimpleManagerDiscoveryNetwork {
 public:
  virtual ~SimpleManagerDiscoveryNetwork() = default;
  virtual bool collect_manager_discovery(
      const std::string &request_json,
      std::size_t max_datagrams,
      std::vector<SimpleDiscoveryDatagram> *datagrams) = 0;
};

class SimpleManagerDiscoveryRandom {
 public:
  virtual ~SimpleManagerDiscoveryRandom() = default;
  virtual bool fill_discovery_random(uint8_t *data, std::size_t size) = 0;
};

class SimpleManagerDiscovery {
 public:
  SimpleManagerDiscovery(
      SimpleManagerDiscoveryNetwork *network,
      SimpleManagerDiscoveryRandom *random)
      : network_(network), random_(random) {}

  SimpleManagerDiscoveryError discover(
      const std::string &hardware_id,
      const SimpleDiscoveryFilterContext &context,
      std::vector<SimpleManagerCandidateV2> *candidates);

 private:
  bool fill_(uint8_t *data, std::size_t size);

  SimpleManagerDiscoveryNetwork *network_{nullptr};
  SimpleManagerDiscoveryRandom *random_{nullptr};
};

bool build_simple_discovery_query(
    const std::string &hardware_id,
    const std::array<uint8_t, 16> &request_random,
    const std::array<uint8_t, 32> &nonce_random,
    std::string *request_id,
    std::string *nonce_text,
    std::string *request_json);

bool parse_simple_discovery_response(
    const std::string &response_json,
    const std::string &request_id,
    const std::string &nonce_text,
    SimpleManagerCandidateV2 *candidate);

bool simple_discovery_candidate_allowed(
    const SimpleManagerCandidateV2 &candidate,
    const std::string &source_ipv4,
    const SimpleDiscoveryFilterContext &context);

std::vector<SimpleManagerCandidateV2> filter_simple_discovery_candidates(
    const std::vector<SimpleManagerCandidateV2> &candidates,
    const std::vector<std::string> &source_ipv4s,
    const SimpleDiscoveryFilterContext &context);

std::vector<SimpleManagerCandidateV2> parse_filter_simple_discovery_datagrams(
    const std::vector<SimpleDiscoveryDatagram> &datagrams,
    const std::string &request_id,
    const std::string &nonce_text,
    const SimpleDiscoveryFilterContext &context,
    std::size_t *parsed_datagrams = nullptr);

std::vector<SimpleBrokerRecoveryTarget> make_simple_broker_recovery_targets(
    const std::vector<SimpleManagerCandidateV2> &candidates,
    uint16_t durable_broker_port);

}
