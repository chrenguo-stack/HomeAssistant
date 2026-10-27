#include "n3w_registration_discovery.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstring>
#include <cstdio>
#include <limits>
#include <string>
#include <vector>

#include "esphome/components/json/json_util.h"
#include "lwip/inet.h"
#include "lwip/ip_addr.h"
#include "mdns.h"

#include "n3w_esp32_manager_discovery.h"
#include "n3w_manager_discovery.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint32_t kRegistrationMdnsTimeoutMs = 1500;
constexpr std::size_t kRegistrationMdnsMaxResults = 8;
constexpr uint8_t kRegistrationUdpAttempts = 3;
constexpr std::size_t kRegistrationQueryPaddedBytes = 1400;

bool safe_registration_id(const std::string &value) {
  if (value.empty() || value.size() > 128U) return false;
  const auto alpha_num = [](char ch) {
    return (ch >= 'a' && ch <= 'z') ||
           (ch >= 'A' && ch <= 'Z') ||
           (ch >= '0' && ch <= '9');
  };
  if (!alpha_num(value.front())) return false;
  return std::all_of(value.begin() + 1, value.end(), [&](char ch) {
    return alpha_num(ch) || ch == '.' || ch == '_' || ch == ':' || ch == '-';
  });
}

bool lowercase_sha256(const std::string &value) {
  return value.size() == 64U &&
         std::all_of(value.begin(), value.end(), [](char ch) {
           return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
         });
}

bool parse_ipv4_host_order(const std::string &text, uint32_t *value) {
  if (value == nullptr || text.empty()) return false;
  in_addr parsed{};
  if (::inet_pton(AF_INET, text.c_str(), &parsed) != 1) return false;
  *value = ntohl(parsed.s_addr);
  return true;
}

bool valid_subnet_mask(uint32_t mask) {
  if (mask == 0U) return false;
  const uint32_t inverse = ~mask;
  return (inverse & (inverse + 1U)) == 0U;
}

bool valid_unicast_ipv4(uint32_t address) {
  const uint8_t first = static_cast<uint8_t>(address >> 24U);
  return first != 0U && first != 127U && first < 224U &&
         address != 0xffffffffU;
}

bool candidate_host_allowed(
    const std::string &candidate_host,
    const std::string &source_ipv4,
    const std::string &local_ipv4,
    const std::string &subnet_mask,
    bool require_source_match) {
  uint32_t candidate = 0;
  uint32_t source = 0;
  uint32_t local = 0;
  uint32_t mask = 0;
  if (!parse_ipv4_host_order(candidate_host, &candidate) ||
      !parse_ipv4_host_order(local_ipv4, &local) ||
      !parse_ipv4_host_order(subnet_mask, &mask) ||
      !valid_subnet_mask(mask) ||
      !valid_unicast_ipv4(candidate) ||
      !valid_unicast_ipv4(local) ||
      candidate == local ||
      (candidate & mask) != (local & mask)) {
    return false;
  }

  const uint32_t host_mask = ~mask;
  const uint32_t network = local & mask;
  const uint32_t broadcast = network | host_mask;
  if (candidate == network || candidate == broadcast) return false;

  if (!require_source_match) return true;
  if (!parse_ipv4_host_order(source_ipv4, &source) ||
      !valid_unicast_ipv4(source)) {
    return false;
  }
  return source == candidate;
}

bool read_string(JsonObjectConst object, const char *key, std::string *value) {
  if (value == nullptr || !object[key].is<const char *>()) return false;
  const char *raw = object[key].as<const char *>();
  if (raw == nullptr || raw[0] == '\0') return false;
  *value = raw;
  return true;
}

bool parse_candidate_object(
    JsonObjectConst value,
    uint64_t observed_ms,
    RegistrationCandidateV1 *candidate) {
  if (candidate == nullptr || value.isNull() || value.size() != 12U) {
    return false;
  }

  std::string schema;
  std::string scheme;
  std::string protocol;
  RegistrationCandidateV1 parsed;
  if (!read_string(value, "schema", &schema) ||
      schema != kRegistrationCandidateSchema ||
      !read_string(value, "manager_id", &parsed.manager_id) ||
      !read_string(value, "system_id", &parsed.system_id) ||
      !read_string(value, "system_id_hint", &parsed.system_id_hint) ||
      !read_string(value, "host", &parsed.host) ||
      !read_string(
          value, "bootstrap_tls_sha256", &parsed.bootstrap_tls_sha256) ||
      !read_string(value, "bootstrap_scheme", &scheme) ||
      scheme != "https" ||
      !read_string(value, "bootstrap_path", &parsed.bootstrap_path) ||
      !read_string(value, "protocol", &protocol) ||
      protocol != kRegistrationDiscoveryProtocol ||
      !value["bootstrap_port"].is<uint16_t>() ||
      !value["ttl_s"].is<uint16_t>() ||
      !value["busy"].is<bool>()) {
    return false;
  }

  parsed.bootstrap_port = value["bootstrap_port"].as<uint16_t>();
  parsed.ttl_s = value["ttl_s"].as<uint16_t>();
  parsed.busy = value["busy"].as<bool>();
  parsed.observed_ms = observed_ms;
  if (!parsed.valid()) return false;
  *candidate = std::move(parsed);
  return true;
}

const char *txt_value(const mdns_result_t *result, const char *key) {
  if (result == nullptr || key == nullptr) return nullptr;
  for (std::size_t index = 0; index < result->txt_count; ++index) {
    const mdns_txt_item_t &item = result->txt[index];
    if (item.key != nullptr && std::strcmp(item.key, key) == 0) {
      return item.value;
    }
  }
  return nullptr;
}

bool exact_registration_mdns_txt(const mdns_result_t *result) {
  static constexpr std::array<const char *, 10> required = {
      "schema",
      "manager_id",
      "system_id",
      "system_id_hint",
      "bootstrap_scheme",
      "bootstrap_path",
      "bootstrap_tls_sha256",
      "protocol",
      "ttl_s",
      "busy",
  };
  if (result == nullptr || result->txt_count != required.size()) return false;
  for (const char *key : required) {
    if (txt_value(result, key) == nullptr) return false;
  }
  for (std::size_t index = 0; index < result->txt_count; ++index) {
    bool known = false;
    for (const char *key : required) {
      known = known ||
              (result->txt[index].key != nullptr &&
               std::strcmp(result->txt[index].key, key) == 0);
    }
    if (!known) return false;
  }
  return true;
}

bool parse_decimal_uint16(const char *text, uint16_t *value) {
  if (text == nullptr || value == nullptr || text[0] == '\0') return false;
  uint32_t parsed = 0;
  for (const char *cursor = text; *cursor != '\0'; ++cursor) {
    if (*cursor < '0' || *cursor > '9') return false;
    parsed = parsed * 10U + static_cast<uint32_t>(*cursor - '0');
    if (parsed > std::numeric_limits<uint16_t>::max()) return false;
  }
  *value = static_cast<uint16_t>(parsed);
  return true;
}

bool first_mdns_ipv4(const mdns_result_t *result, std::string *host) {
  if (result == nullptr || host == nullptr) return false;
  for (mdns_ip_addr_t *address = result->addr;
       address != nullptr;
       address = address->next) {
    if (address->addr.type != IPADDR_TYPE_V4) continue;
    std::array<char, INET_ADDRSTRLEN> text{};
    in_addr raw{};
    raw.s_addr = address->addr.u_addr.ip4.addr;
    if (::inet_ntop(AF_INET, &raw, text.data(), text.size()) == nullptr) {
      continue;
    }
    *host = text.data();
    return true;
  }
  return false;
}

bool candidate_from_mdns(
    const mdns_result_t *result,
    const std::string &local_ipv4,
    const std::string &subnet_mask,
    uint64_t observed_ms,
    RegistrationCandidateV1 *candidate) {
  if (candidate == nullptr || result == nullptr ||
      result->port != kRegistrationBootstrapPort ||
      !exact_registration_mdns_txt(result)) {
    return false;
  }

  RegistrationCandidateV1 parsed;
  if (!first_mdns_ipv4(result, &parsed.host)) return false;

  const char *schema = txt_value(result, "schema");
  const char *manager_id = txt_value(result, "manager_id");
  const char *system_id = txt_value(result, "system_id");
  const char *system_id_hint = txt_value(result, "system_id_hint");
  const char *scheme = txt_value(result, "bootstrap_scheme");
  const char *path = txt_value(result, "bootstrap_path");
  const char *fingerprint = txt_value(result, "bootstrap_tls_sha256");
  const char *protocol = txt_value(result, "protocol");
  const char *ttl_text = txt_value(result, "ttl_s");
  const char *busy_text = txt_value(result, "busy");
  if (schema == nullptr || manager_id == nullptr || system_id == nullptr ||
      system_id_hint == nullptr || scheme == nullptr || path == nullptr ||
      fingerprint == nullptr || protocol == nullptr || ttl_text == nullptr ||
      busy_text == nullptr ||
      std::strcmp(schema, kRegistrationCandidateSchema) != 0 ||
      std::strcmp(scheme, "https") != 0 ||
      std::strcmp(path, "/v1/registration/confirm") != 0 ||
      std::strcmp(protocol, kRegistrationDiscoveryProtocol) != 0 ||
      (std::strcmp(busy_text, "0") != 0 &&
       std::strcmp(busy_text, "1") != 0)) {
    return false;
  }

  parsed.manager_id = manager_id;
  parsed.system_id = system_id;
  parsed.system_id_hint = system_id_hint;
  parsed.bootstrap_tls_sha256 = fingerprint;
  parsed.bootstrap_port = result->port;
  parsed.bootstrap_path = path;
  parsed.busy = std::strcmp(busy_text, "1") == 0;
  parsed.observed_ms = observed_ms;
  if (!parse_decimal_uint16(ttl_text, &parsed.ttl_s) ||
      !parsed.valid() ||
      !candidate_host_allowed(
          parsed.host,
          {},
          local_ipv4,
          subnet_mask,
          false)) {
    return false;
  }

  *candidate = std::move(parsed);
  return true;
}

}  // namespace

bool RegistrationCandidateV1::valid() const {
  return safe_registration_id(manager_id) &&
         safe_registration_id(system_id) &&
         !system_id_hint.empty() &&
         system_id_hint.size() <= 32U &&
         !host.empty() &&
         lowercase_sha256(bootstrap_tls_sha256) &&
         bootstrap_port == kRegistrationBootstrapPort &&
         bootstrap_path == "/v1/registration/confirm" &&
         ttl_s == kRegistrationCandidateTtlSeconds &&
         observed_ms > 0U;
}

bool RegistrationCandidateV1::expired(uint64_t now_ms) const {
  if (!valid() || now_ms < observed_ms) return true;
  return now_ms - observed_ms >=
         static_cast<uint64_t>(ttl_s) * 1000ULL;
}

bool parse_registration_discovery_response(
    const std::string &response_json,
    const std::string &request_id,
    const std::string &nonce_text,
    const std::string &source_ipv4,
    const std::string &local_ipv4,
    const std::string &subnet_mask,
    uint64_t observed_ms,
    RegistrationCandidateV1 *candidate) {
  if (candidate == nullptr || response_json.empty() ||
      request_id.empty() || nonce_text.empty() ||
      source_ipv4.empty() || local_ipv4.empty() || subnet_mask.empty()) {
    return false;
  }

  JsonDocument document = json::parse_json(response_json);
  JsonObjectConst root = document.as<JsonObjectConst>();
  if (root.isNull() || root.size() != 4U ||
      std::string(root["schema"] | "") !=
          kRegistrationDiscoveryResponseSchema ||
      std::string(root["request_id"] | "") != request_id ||
      std::string(root["nonce"] | "") != nonce_text ||
      !root["candidate"].is<JsonObjectConst>()) {
    return false;
  }

  RegistrationCandidateV1 parsed;
  if (!parse_candidate_object(
          root["candidate"].as<JsonObjectConst>(),
          observed_ms,
          &parsed) ||
      !candidate_host_allowed(
          parsed.host,
          source_ipv4,
          local_ipv4,
          subnet_mask,
          true)) {
    return false;
  }

  *candidate = std::move(parsed);
  return true;
}

void RegistrationDiscovery::append_candidate_(
    const RegistrationCandidateV1 &candidate,
    std::vector<RegistrationCandidateV1> *candidates) {
  if (candidates == nullptr || !candidate.valid() ||
      candidates->size() >= kRegistrationDiscoveryMaxCandidates) {
    return;
  }
  const bool duplicate = std::any_of(
      candidates->begin(),
      candidates->end(),
      [&](const RegistrationCandidateV1 &existing) {
        return existing.manager_id == candidate.manager_id &&
               existing.system_id == candidate.system_id &&
               existing.host == candidate.host &&
               existing.bootstrap_port == candidate.bootstrap_port;
      });
  if (!duplicate) candidates->push_back(candidate);
}

void RegistrationDiscovery::collect_mdns_(
    const std::string &local_ipv4,
    const std::string &subnet_mask,
    uint64_t observed_ms,
    std::vector<RegistrationCandidateV1> *candidates) {
  if (candidates == nullptr ||
      candidates->size() >= kRegistrationDiscoveryMaxCandidates) {
    return;
  }

  mdns_result_t *results = nullptr;
  const esp_err_t status = mdns_query_ptr(
      "_greenhouse-reg",
      "_tcp",
      kRegistrationMdnsTimeoutMs,
      kRegistrationMdnsMaxResults,
      &results);
  if (status != ESP_OK || results == nullptr) {
    if (results != nullptr) mdns_query_results_free(results);
    return;
  }

  for (mdns_result_t *result = results;
       result != nullptr &&
       candidates->size() < kRegistrationDiscoveryMaxCandidates;
       result = result->next) {
    RegistrationCandidateV1 candidate;
    if (candidate_from_mdns(
            result,
            local_ipv4,
            subnet_mask,
            observed_ms,
            &candidate)) {
      append_candidate_(candidate, candidates);
    }
  }
  mdns_query_results_free(results);
}

void RegistrationDiscovery::collect_udp_(
    const std::string &request_json,
    const std::string &request_id,
    const std::string &nonce_text,
    const std::string &local_ipv4,
    const std::string &subnet_mask,
    uint64_t observed_ms,
    std::vector<RegistrationCandidateV1> *candidates) {
  if (candidates == nullptr ||
      candidates->size() >= kRegistrationDiscoveryMaxCandidates) {
    return;
  }

  Esp32ManagerDiscoveryNetwork network;
  for (uint8_t attempt = 0;
       attempt < kRegistrationUdpAttempts &&
       candidates->size() < kRegistrationDiscoveryMaxCandidates;
       ++attempt) {
    std::vector<SimpleDiscoveryDatagram> datagrams;
    if (!network.collect_manager_discovery(
            request_json,
            kManagerDiscoveryMaxParsedDatagrams,
            &datagrams)) {
      continue;
    }
    for (const SimpleDiscoveryDatagram &datagram : datagrams) {
      RegistrationCandidateV1 candidate;
      if (parse_registration_discovery_response(
              datagram.response_json,
              request_id,
              nonce_text,
              datagram.source_ipv4,
              local_ipv4,
              subnet_mask,
              observed_ms,
              &candidate)) {
        append_candidate_(candidate, candidates);
      }
      if (candidates->size() >= kRegistrationDiscoveryMaxCandidates) break;
    }
  }
}

bool RegistrationDiscovery::discover(
    const std::string &hardware_id,
    const std::string &local_ipv4,
    const std::string &subnet_mask,
    uint64_t now_ms,
    std::vector<RegistrationCandidateV1> *candidates) {
  if (candidates == nullptr || hardware_id.empty() ||
      local_ipv4.empty() || subnet_mask.empty() || now_ms == 0U) {
    return false;
  }
  candidates->clear();

  std::array<uint8_t, 16> request_random{};
  std::array<uint8_t, 32> nonce_random{};
  Esp32ManagerDiscoveryRandom random;
  if (!random.fill_discovery_random(
          request_random.data(), request_random.size()) ||
      !random.fill_discovery_random(
          nonce_random.data(), nonce_random.size())) {
    return false;
  }

  std::string request_id;
  std::string nonce_text;
  std::string request_json;
  if (!build_discovery_query_for_protocol(
          hardware_id,
          kRegistrationDiscoveryProtocol,
          request_random,
          nonce_random,
          &request_id,
          &nonce_text,
          &request_json)) {
    return false;
  }

  if (request_json.size() < kRegistrationQueryPaddedBytes) {
    request_json.append(
        kRegistrationQueryPaddedBytes - request_json.size(), ' ');
  }
  if (request_json.size() != kRegistrationQueryPaddedBytes) return false;

  collect_mdns_(
      local_ipv4,
      subnet_mask,
      now_ms,
      candidates);
  if (candidates->empty()) {
    collect_udp_(
        request_json,
        request_id,
        nonce_text,
        local_ipv4,
        subnet_mask,
        now_ms,
        candidates);
  }
  return true;
}

}  // namespace esphome::greenhouse_n3w_core
