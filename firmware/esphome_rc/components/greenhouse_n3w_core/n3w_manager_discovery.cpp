#include "n3w_manager_discovery.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <utility>
#include <vector>

#include "esphome/components/json/json_util.h"
#include "mbedtls/base64.h"

#include "n3w_simple_crypto.h"

namespace esphome::greenhouse_n3w_core {
namespace {

std::string base64url_encode(const uint8_t *data, std::size_t size) {
  if (data == nullptr || size == 0U) return {};
  std::vector<uint8_t> encoded(((size + 2U) / 3U) * 4U + 1U, 0);
  std::size_t written = 0;
  if (mbedtls_base64_encode(
          encoded.data(), encoded.size(), &written, data, size) != 0) {
    return {};
  }
  std::string output(reinterpret_cast<const char *>(encoded.data()), written);
  for (char &ch : output) {
    if (ch == '+') ch = '-';
    if (ch == '/') ch = '_';
  }
  while (!output.empty() && output.back() == '=') output.pop_back();
  return output;
}

template<std::size_t N>
std::string base64url_encode(const std::array<uint8_t, N> &data) {
  return base64url_encode(data.data(), data.size());
}

template<std::size_t N>
bool any_nonzero(const std::array<uint8_t, N> &value) {
  return std::any_of(value.begin(), value.end(), [](uint8_t byte) { return byte != 0U; });
}

std::string uuid_from_random(const std::array<uint8_t, 16> &random) {
  std::array<uint8_t, 16> value = random;
  value[6] = static_cast<uint8_t>((value[6] & 0x0fU) | 0x40U);
  value[8] = static_cast<uint8_t>((value[8] & 0x3fU) | 0x80U);
  char output[37]{};
  std::snprintf(
      output,
      sizeof(output),
      "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      value[0], value[1], value[2], value[3],
      value[4], value[5], value[6], value[7],
      value[8], value[9], value[10], value[11], value[12], value[13], value[14], value[15]);
  return output;
}

bool read_string(JsonObjectConst object, const char *key, std::string *value) {
  if (value == nullptr || !object[key].is<const char *>()) return false;
  const char *raw = object[key].as<const char *>();
  if (raw == nullptr || raw[0] == '\0') return false;
  *value = raw;
  return true;
}

}  // namespace

bool SimpleManagerCandidateV2::valid() const {
  return valid_simple_identity_v2(manager_id) && valid_simple_identity_v2(system_id) &&
         !host.empty() && host.size() <= 253U && port > 0U &&
         !pairing_path.empty() && pairing_path.size() <= 255U &&
         pairing_path.front() == '/';
}

bool SimpleManagerDiscovery::fill_(uint8_t *data, std::size_t size) {
  if (data == nullptr || size == 0U || random_ == nullptr ||
      !random_->fill_discovery_random(data, size)) {
    return false;
  }
  return std::any_of(data, data + size, [](uint8_t value) { return value != 0U; });
}

SimpleManagerDiscoveryError SimpleManagerDiscovery::discover(
    const std::string &hardware_id,
    const SimpleDiscoveryFilterContext &context,
    std::vector<SimpleManagerCandidateV2> *candidates) {
  if (network_ == nullptr || random_ == nullptr || candidates == nullptr ||
      context.expected_system_id.empty() || context.local_ipv4.empty() ||
      context.subnet_mask.empty()) {
    return SimpleManagerDiscoveryError::NOT_READY;
  }
  candidates->clear();

  std::array<uint8_t, 16> request_random{};
  std::array<uint8_t, 32> nonce_random{};
  if (!fill_(request_random.data(), request_random.size()) ||
      !fill_(nonce_random.data(), nonce_random.size())) {
    return SimpleManagerDiscoveryError::IO_FAILED;
  }

  std::string request_id;
  std::string nonce_text;
  std::string request_json;
  if (!build_simple_discovery_query(
          hardware_id,
          request_random,
          nonce_random,
          &request_id,
          &nonce_text,
          &request_json)) {
    return SimpleManagerDiscoveryError::IO_FAILED;
  }

  std::vector<SimpleDiscoveryDatagram> datagrams;
  if (!network_->collect_manager_discovery(
          request_json,
          kManagerDiscoveryMaxParsedDatagrams,
          &datagrams)) {
    return SimpleManagerDiscoveryError::DISCOVERY_FAILED;
  }
  *candidates = parse_filter_simple_discovery_datagrams(
      datagrams,
      request_id,
      nonce_text,
      context);
  return candidates->empty()
             ? SimpleManagerDiscoveryError::DISCOVERY_FAILED
             : SimpleManagerDiscoveryError::NONE;
}

bool build_simple_discovery_query(
    const std::string &hardware_id,
    const std::array<uint8_t, 16> &request_random,
    const std::array<uint8_t, 32> &nonce_random,
    std::string *request_id,
    std::string *nonce_text,
    std::string *request_json) {
  if (request_id == nullptr || nonce_text == nullptr || request_json == nullptr ||
      !valid_simple_identity_v2(hardware_id) || !any_nonzero(request_random) ||
      !any_nonzero(nonce_random)) {
    return false;
  }

  *request_id = uuid_from_random(request_random);
  *nonce_text = base64url_encode(nonce_random);
  if (request_id->empty() || nonce_text->empty()) return false;

  *request_json = json::build_json([&](JsonObject root) {
    root["schema"] = "gh.discovery.query/1";
    root["request_id"] = *request_id;
    root["nonce"] = *nonce_text;
    root["hardware_id"] = hardware_id;
    JsonArray protocols = root["protocols"].to<JsonArray>();
    protocols.add(kSimplePairingProtocol);
  });
  return !request_json->empty();
}

bool parse_simple_discovery_response(
    const std::string &response_json,
    const std::string &request_id,
    const std::string &nonce_text,
    SimpleManagerCandidateV2 *candidate) {
  if (candidate == nullptr || response_json.empty() || request_id.empty() || nonce_text.empty()) {
    return false;
  }

  JsonDocument document = json::parse_json(response_json);
  JsonObjectConst root = document.as<JsonObjectConst>();
  if (root.isNull() || std::string(root["schema"] | "") != "gh.discovery.response/1" ||
      std::string(root["request_id"] | "") != request_id ||
      std::string(root["nonce"] | "") != nonce_text ||
      !root["candidate"].is<JsonObjectConst>()) {
    return false;
  }

  JsonObjectConst value = root["candidate"].as<JsonObjectConst>();
  std::string schema;
  std::string protocol;
  std::string scheme;
  SimpleManagerCandidateV2 parsed;
  if (!read_string(value, "schema", &schema) || schema != "gh.manager.candidate/1" ||
      !read_string(value, "protocol", &protocol) || protocol != kSimplePairingProtocol ||
      !read_string(value, "scheme", &scheme) || scheme != "http" ||
      !read_string(value, "manager_id", &parsed.manager_id) ||
      !read_string(value, "system_id", &parsed.system_id) ||
      !read_string(value, "host", &parsed.host) ||
      !read_string(value, "pairing_path", &parsed.pairing_path) ||
      !value["port"].is<uint16_t>()) {
    return false;
  }
  parsed.port = value["port"].as<uint16_t>();
  if (!parsed.valid()) return false;
  *candidate = std::move(parsed);
  return true;
}

std::vector<SimpleManagerCandidateV2> parse_filter_simple_discovery_datagrams(
    const std::vector<SimpleDiscoveryDatagram> &datagrams,
    const std::string &request_id,
    const std::string &nonce_text,
    const SimpleDiscoveryFilterContext &context,
    std::size_t *parsed_datagrams) {
  const std::size_t count =
      std::min(datagrams.size(), kManagerDiscoveryMaxParsedDatagrams);
  if (parsed_datagrams != nullptr) *parsed_datagrams = count;

  std::vector<SimpleManagerCandidateV2> candidates;
  std::vector<std::string> source_ipv4s;
  candidates.reserve(count);
  source_ipv4s.reserve(count);
  for (std::size_t index = 0; index < count; ++index) {
    SimpleManagerCandidateV2 candidate;
    if (!parse_simple_discovery_response(
            datagrams[index].response_json,
            request_id,
            nonce_text,
            &candidate)) {
      continue;
    }
    candidates.push_back(std::move(candidate));
    source_ipv4s.push_back(datagrams[index].source_ipv4);
  }
  return filter_simple_discovery_candidates(candidates, source_ipv4s, context);
}

}  // namespace esphome::greenhouse_n3w_core
