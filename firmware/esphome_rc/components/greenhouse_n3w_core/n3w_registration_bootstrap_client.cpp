#include "n3w_registration_bootstrap_client.h"

#include <algorithm>
#include <limits>
#include <utility>

#include "esphome/components/json/json_util.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint64_t kRegistrationDeadlineSafetyMs = 1000ULL;

bool valid_text(const std::string &value, std::size_t maximum) {
  return !value.empty() && value.size() <= maximum &&
         std::none_of(value.begin(), value.end(), [](char ch) { return ch == '\0'; });
}

bool lowercase_sha256(const std::string &value) {
  return value.size() == 64U &&
         std::all_of(value.begin(), value.end(), [](char ch) {
           return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
         });
}

bool read_string(JsonObjectConst object, const char *key, std::string *value) {
  if (value == nullptr || !object[key].is<const char *>()) return false;
  const char *raw = object[key].as<const char *>();
  if (raw == nullptr || raw[0] == '\0') return false;
  *value = raw;
  return true;
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

bool pairing_host_allowed(
    const std::string &pairing_host,
    const std::string &local_ipv4,
    const std::string &subnet_mask) {
  uint32_t host = 0;
  uint32_t local = 0;
  uint32_t mask = 0;
  if (!parse_ipv4_host_order(pairing_host, &host) ||
      !parse_ipv4_host_order(local_ipv4, &local) ||
      !parse_ipv4_host_order(subnet_mask, &mask) ||
      !valid_subnet_mask(mask) || !valid_unicast_ipv4(host) ||
      !valid_unicast_ipv4(local) || host == local ||
      (host & mask) != (local & mask)) {
    return false;
  }
  const uint32_t network = local & mask;
  const uint32_t broadcast = network | ~mask;
  return host != network && host != broadcast;
}

bool parse_confirm_rejection(
    JsonObjectConst root,
    RegistrationBootstrapConfirmResult *result) {
  if (result == nullptr || root.isNull()) return false;
  std::string schema;
  std::string status;
  std::string reason;
  if (!read_string(root, "schema", &schema) ||
      schema != kRegistrationConfirmResultSchema ||
      !root["accepted"].is<bool>() || root["accepted"].as<bool>() ||
      !read_string(root, "status", &status) ||
      !read_string(root, "reason", &reason)) {
    return false;
  }

  if (root.size() == 5U) {
    std::string disposition;
    if (!read_string(root, "transaction_disposition", &disposition) ||
        disposition != "terminal" || status != "rejected" ||
        (reason != "expired" && reason != "replay_detected")) {
      return false;
    }
    result->action = RegistrationBootstrapConfirmAction::TERMINAL;
    result->reason = std::move(reason);
    return true;
  }

  if (root.size() != 4U ||
      (status != "rejected" && status != "unavailable")) {
    return false;
  }
  result->action = RegistrationBootstrapConfirmAction::RETRY;
  result->reason = std::move(reason);
  return true;
}

}  // namespace

bool RegistrationBootstrapRecoveryBinding::valid() const {
  return valid_text(pairing_id, 64U) && valid_text(manager_id, 128U) &&
         valid_text(system_id, 128U) && valid_text(bootstrap_host, 253U) &&
         bootstrap_port == kRegistrationBootstrapPort &&
         lowercase_sha256(bootstrap_tls_sha256);
}

bool build_registration_confirm_request(
    const RegistrationCandidateV1 &selected,
    const std::string &hardware_id,
    const std::string &pairing_id,
    const std::string &setup_secret_base64url,
    std::string *request_json) {
  if (request_json == nullptr || !selected.valid() ||
      !valid_text(hardware_id, 64U) || !valid_text(pairing_id, 64U) ||
      setup_secret_base64url.size() != 43U) {
    return false;
  }
  *request_json = json::build_json([&](JsonObject root) {
    root["schema"] = kRegistrationConfirmSchema;
    root["manager_id"] = selected.manager_id;
    root["system_id"] = selected.system_id;
    root["hardware_id"] = hardware_id;
    root["pairing_id"] = pairing_id;
    root["setup_secret"] = setup_secret_base64url;
  });
  return !request_json->empty();
}

bool parse_registration_confirm_response(
    int http_status,
    const std::string &response_json,
    const RegistrationCandidateV1 &selected,
    const std::string &pairing_id,
    const std::string &local_ipv4,
    const std::string &subnet_mask,
    uint64_t received_ms,
    RegistrationBootstrapConfirmResult *result) {
  if (result == nullptr || !selected.valid() || pairing_id.empty() ||
      response_json.empty() || received_ms == 0U) {
    return false;
  }

  RegistrationBootstrapConfirmResult parsed;
  JsonDocument document = json::parse_json(response_json);
  JsonObjectConst root = document.as<JsonObjectConst>();
  if (root.isNull()) return false;

  if (http_status != 200) {
    if (!parse_confirm_rejection(root, &parsed)) return false;
    *result = std::move(parsed);
    return true;
  }

  std::string schema;
  std::string status;
  std::string manager_id;
  std::string system_id;
  std::string pairing_host;
  std::string pairing_path;
  if (root.size() != 9U || !read_string(root, "schema", &schema) ||
      schema != kRegistrationConfirmResultSchema ||
      !root["accepted"].is<bool>() || !root["accepted"].as<bool>() ||
      !read_string(root, "status", &status) || status != "accepted" ||
      !read_string(root, "manager_id", &manager_id) ||
      manager_id != selected.manager_id ||
      !read_string(root, "system_id", &system_id) ||
      system_id != selected.system_id ||
      !read_string(root, "pairing_host", &pairing_host) ||
      !root["pairing_port"].is<uint16_t>() ||
      root["pairing_port"].as<uint16_t>() != kRegistrationPairingPort ||
      !read_string(root, "pairing_path", &pairing_path) ||
      pairing_path != kRegistrationPairingPath ||
      !root["expires_in_seconds"].is<uint16_t>()) {
    return false;
  }

  const uint16_t expires = root["expires_in_seconds"].as<uint16_t>();
  if (expires == 0U || expires > kRegistrationTransactionMaxSeconds ||
      !pairing_host_allowed(pairing_host, local_ipv4, subnet_mask)) {
    return false;
  }
  const uint64_t delta_ms = static_cast<uint64_t>(expires) * 1000ULL;
  // Manager returns ceil(remaining seconds). Subtract one second locally so
  // the node never treats rounding slack as additional transaction lifetime.
  const uint64_t safe_delta_ms =
      delta_ms > kRegistrationDeadlineSafetyMs
          ? delta_ms - kRegistrationDeadlineSafetyMs
          : 0U;
  if (received_ms >
      std::numeric_limits<uint64_t>::max() - safe_delta_ms) {
    return false;
  }

  parsed.action = RegistrationBootstrapConfirmAction::ACCEPTED;
  parsed.transaction_deadline_ms = received_ms + safe_delta_ms;
  parsed.pairing_target.manager_id = selected.manager_id;
  parsed.pairing_target.system_id = selected.system_id;
  parsed.pairing_target.host = pairing_host;
  parsed.pairing_target.port = kRegistrationPairingPort;
  parsed.pairing_target.pairing_path = kRegistrationPairingPath;
  parsed.pairing_target.ttl_s = expires;
  if (!parsed.pairing_target.valid()) return false;

  parsed.recovery.pairing_id = pairing_id;
  parsed.recovery.manager_id = selected.manager_id;
  parsed.recovery.system_id = selected.system_id;
  parsed.recovery.bootstrap_host = selected.host;
  parsed.recovery.bootstrap_port = selected.bootstrap_port;
  parsed.recovery.bootstrap_tls_sha256 = selected.bootstrap_tls_sha256;
  if (!parsed.recovery.valid()) return false;

  *result = std::move(parsed);
  return true;
}

bool build_registration_status_request(
    const RegistrationBootstrapRecoveryBinding &binding,
    const std::string &hardware_id,
    const std::string &delivery_digest_base64url,
    std::string *request_json) {
  if (request_json == nullptr || !binding.valid() ||
      !valid_text(hardware_id, 64U) ||
      delivery_digest_base64url.size() != 43U) {
    return false;
  }
  *request_json = json::build_json([&](JsonObject root) {
    root["schema"] = kRegistrationStatusSchema;
    root["manager_id"] = binding.manager_id;
    root["system_id"] = binding.system_id;
    root["hardware_id"] = hardware_id;
    root["pairing_id"] = binding.pairing_id;
    root["delivery_digest"] = delivery_digest_base64url;
  });
  return !request_json->empty();
}

bool parse_registration_status_response(
    int http_status,
    const std::string &response_json,
    RegistrationBootstrapStatusResult *result) {
  if (result == nullptr || http_status != 200 || response_json.empty()) {
    return false;
  }
  JsonDocument document = json::parse_json(response_json);
  JsonObjectConst root = document.as<JsonObjectConst>();
  std::string schema;
  std::string status;
  std::string disposition;
  if (root.isNull() || !read_string(root, "schema", &schema) ||
      schema != kRegistrationStatusResultSchema ||
      !read_string(root, "status", &status) ||
      !read_string(root, "transaction_disposition", &disposition)) {
    return false;
  }

  RegistrationBootstrapStatusResult parsed;
  if (root.size() == 3U && status == "committed" &&
      disposition == "committed") {
    parsed.action = RegistrationBootstrapStatusAction::COMMITTED;
    *result = std::move(parsed);
    return true;
  }
  if (root.size() == 3U &&
      (status == "pending" || status == "unknown") &&
      disposition == "wait") {
    parsed.action = RegistrationBootstrapStatusAction::WAIT;
    *result = std::move(parsed);
    return true;
  }
  if (root.size() != 4U || status != "rejected" ||
      disposition != "terminal" ||
      !read_string(root, "reason", &parsed.reason) ||
      (parsed.reason != "expired" &&
       parsed.reason != "replay_detected")) {
    return false;
  }
  parsed.action = RegistrationBootstrapStatusAction::TERMINAL;
  *result = std::move(parsed);
  return true;
}

bool registration_bootstrap_host_allowed(
    const std::string &host,
    const std::string &local_ipv4,
    const std::string &subnet_mask) {
  return pairing_host_allowed(host, local_ipv4, subnet_mask);
}

bool registration_relocation_matches(
    const RegistrationCandidateV1 &candidate,
    const RegistrationBootstrapRecoveryBinding &binding) {
  return candidate.valid() && binding.valid() &&
         candidate.manager_id == binding.manager_id &&
         candidate.system_id == binding.system_id &&
         candidate.bootstrap_tls_sha256 == binding.bootstrap_tls_sha256 &&
         candidate.bootstrap_port == binding.bootstrap_port &&
         candidate.bootstrap_path == "/v1/registration/confirm";
}

}  // namespace esphome::greenhouse_n3w_core
