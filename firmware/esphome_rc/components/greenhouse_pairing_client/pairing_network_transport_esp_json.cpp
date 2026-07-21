#include "pairing_network_transport.h"

#ifdef USE_ESP32

#include <algorithm>
#include <cmath>
#include <cstring>
#include <memory>
#include <set>

#include "cJSON.h"

namespace esphome::greenhouse_pairing_client {

namespace {

void wipe_bytes(char *value) {
  if (value == nullptr)
    return;
  volatile unsigned char *cursor =
      reinterpret_cast<volatile unsigned char *>(value);
  size_t remaining = std::strlen(value);
  while (remaining-- > 0)
    *cursor++ = 0;
}

void wipe_json_tree(cJSON *value) {
  if (value == nullptr)
    return;
  for (cJSON *child = value->child; child != nullptr; child = child->next)
    wipe_json_tree(child);
  if (value->valuestring != nullptr && (value->type & cJSON_IsReference) == 0)
    wipe_bytes(value->valuestring);
  if (value->string != nullptr && (value->type & cJSON_StringIsConst) == 0)
    wipe_bytes(value->string);
}

struct JsonDeleter {
  void operator()(cJSON *value) const {
    if (value == nullptr)
      return;
    wipe_json_tree(value);
    cJSON_Delete(value);
  }
};
using JsonPtr = std::unique_ptr<cJSON, JsonDeleter>;

bool exact_object(const cJSON *object, const std::set<std::string> &fields) {
  if (!cJSON_IsObject(object) || static_cast<size_t>(cJSON_GetArraySize(object)) != fields.size())
    return false;
  std::set<std::string> observed;
  for (const cJSON *item = object->child; item != nullptr; item = item->next) {
    if (item->string == nullptr || fields.count(item->string) == 0 ||
        !observed.insert(item->string).second)
      return false;
  }
  return observed == fields;
}

bool json_string(const cJSON *object, const char *name, std::string *output,
                 size_t maximum = 16384) {
  if (object == nullptr || name == nullptr || output == nullptr)
    return false;
  const cJSON *item = cJSON_GetObjectItemCaseSensitive(object, name);
  if (!cJSON_IsString(item) || item->valuestring == nullptr)
    return false;
  const size_t length = std::strlen(item->valuestring);
  if (length == 0 || length > maximum)
    return false;
  std::fill(output->begin(), output->end(), '\0');
  output->assign(item->valuestring, length);
  return true;
}

bool json_uint32(const cJSON *object, const char *name, uint32_t *output,
                 bool allow_zero = true) {
  if (object == nullptr || name == nullptr || output == nullptr)
    return false;
  const cJSON *item = cJSON_GetObjectItemCaseSensitive(object, name);
  if (!cJSON_IsNumber(item) || !std::isfinite(item->valuedouble) || item->valuedouble < 0 ||
      item->valuedouble > 4294967295.0 || std::floor(item->valuedouble) != item->valuedouble ||
      (!allow_zero && item->valuedouble == 0))
    return false;
  *output = static_cast<uint32_t>(item->valuedouble);
  return true;
}

bool json_uint64(const cJSON *object, const char *name, uint64_t *output) {
  if (object == nullptr || name == nullptr || output == nullptr)
    return false;
  const cJSON *item = cJSON_GetObjectItemCaseSensitive(object, name);
  constexpr double MAX_EXACT_JSON_INTEGER = 9007199254740991.0;
  if (!cJSON_IsNumber(item) || !std::isfinite(item->valuedouble) || item->valuedouble < 0 ||
      item->valuedouble > MAX_EXACT_JSON_INTEGER ||
      std::floor(item->valuedouble) != item->valuedouble)
    return false;
  *output = static_cast<uint64_t>(item->valuedouble);
  return true;
}

bool contains_escaped_nul(const std::string &body) {
  if (body.find('\0') != std::string::npos)
    return true;
  std::string lowered = body;
  std::transform(lowered.begin(), lowered.end(), lowered.begin(), [](unsigned char value) {
    return static_cast<char>(std::tolower(value));
  });
  const bool found = lowered.find("\\u0000") != std::string::npos;
  std::fill(lowered.begin(), lowered.end(), '\0');
  return found;
}

JsonPtr parse_json_object(const std::string &body, const std::set<std::string> &fields) {
  if (body.empty() || contains_escaped_nul(body))
    return {};
  const char *parse_end = nullptr;
  JsonPtr document(cJSON_ParseWithLengthOpts(body.c_str(), body.size() + 1,
                                              &parse_end, true));
  if (!document || parse_end == nullptr || !exact_object(document.get(), fields))
    return {};
  return document;
}

}  // namespace

bool PairingNetworkTransport::parse_discovery_response_(const std::string &body,
                                                         PairingClientCore *core,
                                                         uint32_t now_ms) const {
  JsonPtr document = parse_json_object(body, {"schema", "request_id", "nonce", "candidate"});
  if (!document || core == nullptr)
    return false;
  std::string schema;
  std::string request_id;
  std::string nonce;
  if (!json_string(document.get(), "schema", &schema, 64) || schema != DISCOVERY_RESPONSE_SCHEMA ||
      !json_string(document.get(), "request_id", &request_id, 64) ||
      !json_string(document.get(), "nonce", &nonce, 64) || request_id != core->request_id() ||
      nonce != core->nonce())
    return false;
  const cJSON *item = cJSON_GetObjectItemCaseSensitive(document.get(), "candidate");
  if (!exact_object(item, {"schema", "manager_id", "system_id", "host", "scheme", "port",
                           "pairing_path", "protocol", "priority", "ttl_s"}))
    return false;
  ManagerCandidate candidate;
  uint32_t port = 0;
  uint32_t priority = 0;
  uint32_t ttl_s = 0;
  if (!json_string(item, "schema", &candidate.schema, 64) ||
      !json_string(item, "manager_id", &candidate.manager_id, 128) ||
      !json_string(item, "system_id", &candidate.system_id, 128) ||
      !json_string(item, "host", &candidate.host, 253) ||
      !json_string(item, "scheme", &candidate.scheme, 8) ||
      !json_uint32(item, "port", &port, false) || port > 65535 ||
      !json_string(item, "pairing_path", &candidate.pairing_path, 256) ||
      !PairingTransportCore::validate_pairing_path(candidate.pairing_path) ||
      !json_string(item, "protocol", &candidate.protocol, 64) ||
      !json_uint32(item, "priority", &priority) || priority > 65535 ||
      !json_uint32(item, "ttl_s", &ttl_s, false) || ttl_s > 65535)
    return false;
  candidate.port = static_cast<uint16_t>(port);
  candidate.priority = static_cast<uint16_t>(priority);
  candidate.ttl_s = static_cast<uint16_t>(ttl_s);
  return core->observe_candidate(request_id, nonce, candidate, now_ms);
}

bool PairingNetworkTransport::parse_offer_(const std::string &body,
                                            SecureOfferDocument *offer) const {
  JsonPtr document = parse_json_object(
      body, {"schema", "session_id", "hardware_id", "pairing_id", "manager_nonce",
             "manager_public_key", "cipher_suite", "expires_at", "max_proof_attempts"});
  if (!document || offer == nullptr)
    return false;
  SecureOfferDocument candidate;
  uint32_t attempts = 0;
  if (!json_string(document.get(), "schema", &candidate.schema, 64) ||
      !json_string(document.get(), "session_id", &candidate.session_id, 64) ||
      !json_string(document.get(), "hardware_id", &candidate.hardware_id, 128) ||
      !json_string(document.get(), "pairing_id", &candidate.pairing_id, 64) ||
      !json_string(document.get(), "manager_nonce", &candidate.manager_nonce, 64) ||
      !json_string(document.get(), "manager_public_key", &candidate.manager_public_key, 64) ||
      !json_string(document.get(), "cipher_suite", &candidate.cipher_suite, 128) ||
      !json_string(document.get(), "expires_at", &candidate.expires_at, 64) ||
      !json_uint32(document.get(), "max_proof_attempts", &attempts, false) || attempts > 16)
    return false;
  candidate.max_proof_attempts = static_cast<uint8_t>(attempts);
  if (!SecurePairingChannel::validate_offer(candidate))
    return false;
  *offer = std::move(candidate);
  return true;
}

bool PairingNetworkTransport::parse_secure_status_(const std::string &body,
                                                    const std::string &session_id,
                                                    const std::string &expected_state,
                                                    uint32_t expected_generation) const {
  JsonPtr document = parse_json_object(body, {"schema", "session_id", "state", "expires_at",
                                               "proof_attempts", "credential_generation"});
  if (!document)
    return false;
  std::string schema;
  std::string returned_session;
  std::string state;
  std::string expires_at;
  uint32_t proof_attempts = 0;
  if (!json_string(document.get(), "schema", &schema, 64) || schema != "gh.pair.secure-status/1" ||
      !json_string(document.get(), "session_id", &returned_session, 64) ||
      returned_session != session_id || !json_string(document.get(), "state", &state, 64) ||
      state != expected_state || !json_string(document.get(), "expires_at", &expires_at, 64) ||
      !json_uint32(document.get(), "proof_attempts", &proof_attempts))
    return false;
  const cJSON *generation =
      cJSON_GetObjectItemCaseSensitive(document.get(), "credential_generation");
  if (expected_generation == 0)
    return cJSON_IsNull(generation);
  uint32_t actual_generation = 0;
  return json_uint32(document.get(), "credential_generation", &actual_generation, false) &&
         actual_generation == expected_generation;
}

bool PairingNetworkTransport::parse_envelope_(const std::string &body,
                                               SecureEnvelopeDocument *envelope) const {
  JsonPtr document = parse_json_object(
      body, {"schema", "session_id", "direction", "sequence", "content_type", "nonce", "ciphertext"});
  if (!document || envelope == nullptr)
    return false;
  SecureEnvelopeDocument candidate;
  if (!json_string(document.get(), "schema", &candidate.schema, 64) ||
      !json_string(document.get(), "session_id", &candidate.session_id, 64) ||
      !json_string(document.get(), "direction", &candidate.direction, 32) ||
      !json_uint64(document.get(), "sequence", &candidate.sequence) ||
      !json_string(document.get(), "content_type", &candidate.content_type, 128) ||
      !json_string(document.get(), "nonce", &candidate.nonce, 64) ||
      !json_string(document.get(), "ciphertext", &candidate.ciphertext,
                   this->options_.limits.response_max_bytes))
    return false;
  if (!SecurePairingChannel::validate_envelope_shape(candidate))
    return false;
  *envelope = std::move(candidate);
  return true;
}

bool PairingNetworkTransport::parse_credentials_(const std::string &plaintext,
                                                  RamCredentialBundle *credentials) const {
  JsonPtr document = parse_json_object(
      plaintext, {"schema", "system_id", "node_id", "broker_host", "broker_port",
                  "broker_tls_server_name", "ca_pem", "mqtt_username", "mqtt_client_id",
                  "credential_generation", "mqtt_password"});
  if (!document || credentials == nullptr)
    return false;
  RamCredentialBundle candidate;
  uint32_t port = 0;
  if (!json_string(document.get(), "schema", &candidate.schema, 64) ||
      !json_string(document.get(), "system_id", &candidate.system_id, 128) ||
      !json_string(document.get(), "node_id", &candidate.node_id, 128) ||
      !json_string(document.get(), "broker_host", &candidate.broker_host, 253) ||
      !json_uint32(document.get(), "broker_port", &port, false) || port > 65535 ||
      !json_string(document.get(), "broker_tls_server_name", &candidate.broker_tls_server_name, 253) ||
      !json_string(document.get(), "ca_pem", &candidate.ca_pem, 8192) ||
      !json_string(document.get(), "mqtt_username", &candidate.mqtt_username, 128) ||
      !json_string(document.get(), "mqtt_client_id", &candidate.mqtt_client_id, 128) ||
      !json_uint32(document.get(), "credential_generation", &candidate.credential_generation, false) ||
      !json_string(document.get(), "mqtt_password", &candidate.mqtt_password, 512))
    return false;
  candidate.broker_port = static_cast<uint16_t>(port);
  if (!candidate.valid()) {
    candidate.clear();
    return false;
  }
  *credentials = std::move(candidate);
  return true;
}

}  // namespace esphome::greenhouse_pairing_client

#endif
