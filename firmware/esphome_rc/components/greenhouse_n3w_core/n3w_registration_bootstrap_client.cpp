#include "n3w_registration_bootstrap_client.h"

#include <algorithm>
#include <cstddef>
#include <string>

#include "esphome/components/json/json_util.h"
#include "lwip/inet.h"

namespace esphome::greenhouse_n3w_core {
namespace {

bool required_string(JsonObjectConst root, const char *name, std::string *out) {
  if (!root[name].is<const char *>()) return false;
  const char *raw = root[name].as<const char *>();
  if (raw == nullptr || raw[0] == '\0') return false;
  *out = raw;
  return true;
}

bool ipv4_literal(const std::string &host) {
  if (host.empty() || host.size() > 15U) return false;
  in_addr parsed{};
  return inet_pton(AF_INET, host.c_str(), &parsed) == 1 &&
         parsed.s_addr != INADDR_ANY &&
         parsed.s_addr != INADDR_BROADCAST;
}

bool base64url_32_text(const std::string &text) {
  if (text.size() != 43U) return false;
  return std::all_of(text.begin(), text.end(), [](char value) {
    return (value >= 'A' && value <= 'Z') ||
           (value >= 'a' && value <= 'z') ||
           (value >= '0' && value <= '9') ||
           value == '-' || value == '_';
  });
}

}  // namespace

bool build_registration_confirm_request(
    const RegistrationCandidateV1 &selected,
    const std::string &hardware_id,
    const std::string &pairing_id,
    const std::string &setup_secret_base64url,
    std::string *request_json) {
  if (request_json == nullptr || !selected.valid() ||
      !base64url_32_text(setup_secret_base64url) ||
      hardware_id.empty() || pairing_id.empty()) {
    return false;
  }
  *request_json = json::build_json([&](JsonObject root) {
    root["schema"] = "gh.registration.confirm/1";
    root["manager_id"] = selected.manager_id;
    root["system_id"] = selected.system_id;
    root["hardware_id"] = hardware_id;
    root["pairing_id"] = pairing_id;
    root["setup_secret"] = setup_secret_base64url;
  });
  return !request_json->empty() && request_json->size() <= 2048U;
}

bool parse_registration_confirm_result(
    const std::string &response_json,
    const RegistrationCandidateV1 &selected,
    RegistrationConfirmResult *result) {
  if (result == nullptr) return false;
  *result = RegistrationConfirmResult{};
  if (!selected.valid() || response_json.size() > 4096U) return false;
  JsonDocument parsed = json::parse_json(response_json);
  JsonObjectConst root = parsed.as<JsonObjectConst>();
  if (root.isNull()) return false;
  std::string schema;
  std::string status;
  if (!required_string(root, "schema", &schema) ||
      schema != "gh.registration.confirm-result/1" ||
      !required_string(root, "status", &status) ||
      !root["accepted"].is<bool>()) return false;

  if (!root["accepted"].as<bool>()) {
    std::string reason;
    if (status != "rejected" ||
        !required_string(root, "reason", &reason)) return false;
    result->reason = reason;
    if (reason == "expired" || reason == "replay_detected") {
      std::string disposition;
      if (!required_string(root, "transaction_disposition", &disposition) ||
          disposition != "terminal") return false;
      result->disposition = RegistrationConfirmDisposition::RENEW_PAIRING_ID;
      return true;
    }
    result->disposition = RegistrationConfirmDisposition::RETRY_SAME_PAIRING_ID;
    return true;
  }

  std::string manager_id;
  std::string system_id;
  std::string host;
  std::string pairing_path;
  if (status != "accepted" ||
      !required_string(root, "manager_id", &manager_id) ||
      manager_id != selected.manager_id ||
      !required_string(root, "system_id", &system_id) ||
      system_id != selected.system_id ||
      !required_string(root, "pairing_host", &host) ||
      !ipv4_literal(host) ||
      !required_string(root, "pairing_path", &pairing_path) ||
      pairing_path != "/v2/pairing" ||
      !root["pairing_port"].is<uint16_t>() ||
      root["pairing_port"].as<uint16_t>() != 47112U ||
      !root["expires_in_seconds"].is<uint16_t>()) return false;
  const uint16_t remaining = root["expires_in_seconds"].as<uint16_t>();
  if (remaining == 0 || remaining > 1800U) return false;

  result->pairing_target.manager_id = manager_id;
  result->pairing_target.system_id = system_id;
  result->pairing_target.host = host;
  result->pairing_target.port = 47112;
  result->pairing_target.pairing_path = pairing_path;
  result->pairing_target.ttl_s = remaining;
  result->remaining_seconds = remaining;
  result->disposition = RegistrationConfirmDisposition::ACCEPTED;
  return true;
}

}  // namespace esphome::greenhouse_n3w_core
