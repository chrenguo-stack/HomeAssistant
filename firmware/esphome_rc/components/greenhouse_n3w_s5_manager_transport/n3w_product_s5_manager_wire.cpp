#include "n3w_product_s5_manager_wire.h"

#include <algorithm>
#include <cctype>
#include <limits>

#include "mbedtls/base64.h"

namespace esphome::greenhouse_n3w_s5_manager_transport {

using greenhouse_n3w_product_runtime::ProductPeerGrant;
using greenhouse_n3w_product_runtime::ProductPeerKey;
using greenhouse_n3w_product_runtime::ProductPeerRequest;
using greenhouse_n3w_product_runtime::ProductPeerRole;
using greenhouse_n3w_product_runtime::ProductPeerSecurity;
namespace {

bool unique_field_position(
    const std::string &json,
    const std::string &key,
    std::size_t *position) {
  if (position == nullptr) return false;
  const std::string needle = "\"" + key + "\":";
  const std::size_t first = json.find(needle);
  if (first == std::string::npos ||
      json.find(needle, first + needle.size()) != std::string::npos) {
    return false;
  }
  *position = first + needle.size();
  return true;
}

bool extract_string(
    const std::string &json,
    const std::string &key,
    std::string *value) {
  if (value == nullptr) return false;
  std::size_t position = 0;
  if (!unique_field_position(json, key, &position) ||
      position >= json.size() || json[position] != '"') {
    return false;
  }
  const std::size_t end = json.find('"', position + 1U);
  if (end == std::string::npos) return false;
  *value = json.substr(position + 1U, end - position - 1U);
  return true;
}

bool extract_uint64(
    const std::string &json,
    const std::string &key,
    uint64_t *value) {
  if (value == nullptr) return false;
  std::size_t position = 0;
  if (!unique_field_position(json, key, &position) ||
      position >= json.size() ||
      !std::isdigit(static_cast<unsigned char>(json[position]))) {
    return false;
  }
  uint64_t parsed = 0;
  while (position < json.size() &&
         std::isdigit(static_cast<unsigned char>(json[position]))) {
    const uint8_t digit = static_cast<uint8_t>(json[position] - '0');
    if (parsed > (std::numeric_limits<uint64_t>::max() - digit) / 10U) {
      return false;
    }
    parsed = parsed * 10U + digit;
    ++position;
  }
  if (position >= json.size() ||
      (json[position] != ',' && json[position] != '}')) {
    return false;
  }
  *value = parsed;
  return true;
}

bool extract_uint32(
    const std::string &json,
    const std::string &key,
    uint32_t *value) {
  if (value == nullptr) return false;
  uint64_t parsed = 0;
  if (!extract_uint64(json, key, &parsed) ||
      parsed > std::numeric_limits<uint32_t>::max()) {
    return false;
  }
  *value = static_cast<uint32_t>(parsed);
  return true;
}

bool extract_bool(
    const std::string &json,
    const std::string &key,
    bool *value) {
  if (value == nullptr) return false;
  std::size_t position = 0;
  if (!unique_field_position(json, key, &position)) return false;
  if (json.compare(position, 4, "true") == 0) {
    *value = true;
    return true;
  }
  if (json.compare(position, 5, "false") == 0) {
    *value = false;
    return true;
  }
  return false;
}

bool extract_flat_object(
    const std::string &json,
    const std::string &key,
    std::string *object) {
  if (object == nullptr) return false;
  std::size_t position = 0;
  if (!unique_field_position(json, key, &position) ||
      position >= json.size() || json[position] != '{') {
    return false;
  }
  const std::size_t end = json.find('}', position + 1U);
  if (end == std::string::npos) return false;
  *object = json.substr(position, end - position + 1U);
  return true;
}

bool decode_base64url_32(
    const std::string &encoded,
    ProductPeerKey *value) {
  if (value == nullptr || encoded.empty() ||
      encoded.find('=') != std::string::npos) {
    return false;
  }
  std::string normalized = encoded;
  for (char &ch : normalized) {
    if (ch == '-') ch = '+';
    else if (ch == '_') ch = '/';
    else if (!std::isalnum(static_cast<unsigned char>(ch)) &&
             ch != '+' && ch != '/') {
      return false;
    }
  }
  while ((normalized.size() % 4U) != 0U) normalized.push_back('=');
  std::size_t written = 0;
  ProductPeerKey decoded{};
  const int result = mbedtls_base64_decode(
      decoded.data(), decoded.size(), &written,
      reinterpret_cast<const unsigned char *>(normalized.data()),
      normalized.size());
  if (result != 0 || written != decoded.size()) return false;
  *value = decoded;
  return true;
}

bool decode_grant(
    const std::string &json,
    ProductPeerRole expected_role,
    ProductPeerGrant *grant) {
  if (grant == nullptr) return false;
  ProductPeerGrant candidate;
  std::string role;
  if (!extract_string(json, "role", &role) ||
      !extract_string(json, "authorization_id", &candidate.authorization_id) ||
      !extract_string(json, "system_id", &candidate.system_id) ||
      !extract_string(json, "session_id", &candidate.session_id) ||
      !extract_string(json, "child_node_id", &candidate.child_node_id) ||
      !extract_string(json, "relay_node_id", &candidate.relay_node_id) ||
      !extract_uint32(
          json, "child_credential_generation",
          &candidate.child_credential_generation) ||
      !extract_uint32(
          json, "relay_credential_generation",
          &candidate.relay_credential_generation) ||
      !extract_uint32(json, "child_key_epoch", &candidate.child_key_epoch) ||
      !extract_uint32(json, "relay_key_epoch", &candidate.relay_key_epoch) ||
      !extract_uint64(json, "issued_at_ms", &candidate.issued_at_ms) ||
      !extract_uint64(json, "expires_at_ms", &candidate.expires_at_ms) ||
      !extract_uint32(
          json, "authorization_epoch", &candidate.authorization_epoch)) {
    return false;
  }

  std::string child_public;
  std::string relay_public;
  std::string child_nonce;
  std::string relay_nonce;
  std::string grant_mac;
  if (!extract_string(
          json, "child_ephemeral_public_key", &child_public) ||
      !extract_string(
          json, "relay_ephemeral_public_key", &relay_public) ||
      !extract_string(json, "child_nonce", &child_nonce) ||
      !extract_string(json, "relay_nonce", &relay_nonce) ||
      !extract_string(json, "grant_mac", &grant_mac) ||
      !decode_base64url_32(
          child_public, &candidate.child_ephemeral_public_key) ||
      !decode_base64url_32(
          relay_public, &candidate.relay_ephemeral_public_key) ||
      !decode_base64url_32(child_nonce, &candidate.child_nonce) ||
      !decode_base64url_32(relay_nonce, &candidate.relay_nonce) ||
      !decode_base64url_32(grant_mac, &candidate.grant_mac)) {
    return false;
  }

  if (role == "child") candidate.role = ProductPeerRole::CHILD;
  else if (role == "relay") candidate.role = ProductPeerRole::RELAY;
  else return false;

  if (candidate.role != expected_role || !candidate.valid_shape()) return false;
  *grant = candidate;
  return true;
}

bool b64(
    const uint8_t *data,
    std::size_t size,
    std::string *output) {
  return ProductPeerSecurity::encode_base64url(data, size, output);
}

std::string bool_text(bool value) {
  return value ? "true" : "false";
}

}  // namespace

bool valid_product_transport_nonce(const std::string &nonce) {
  if (nonce.size() < 3U || nonce.size() > 96U) return false;
  return std::all_of(
      nonce.begin(), nonce.end(), [](char ch) {
        const unsigned char value = static_cast<unsigned char>(ch);
        return std::isalnum(value) || ch == '_' || ch == '-';
      });
}

std::string product_peer_authorization_request_topic(
    const std::string &system_id,
    const std::string &relay_node_id) {
  if (!ProductPeerSecurity::valid_identifier_(system_id) ||
      !ProductPeerSecurity::valid_identifier_(relay_node_id)) {
    return {};
  }
  return "gh/v1/" + system_id + "/ingress/node/" + relay_node_id +
         "/relay-peer-auth/request";
}

std::string product_peer_authorization_response_topic(
    const std::string &system_id,
    const std::string &relay_node_id,
    const std::string &session_id) {
  if (!ProductPeerSecurity::valid_identifier_(system_id) ||
      !ProductPeerSecurity::valid_identifier_(relay_node_id) ||
      !ProductPeerSecurity::valid_session_id_(session_id)) {
    return {};
  }
  return "gh/v1/" + system_id + "/out/node/" + relay_node_id +
         "/relay-peer-auth/" + session_id;
}

std::string product_peer_authorization_response_subscription(
    const std::string &system_id,
    const std::string &relay_node_id) {
  if (!ProductPeerSecurity::valid_identifier_(system_id) ||
      !ProductPeerSecurity::valid_identifier_(relay_node_id)) {
    return {};
  }
  return "gh/v1/" + system_id + "/out/node/" + relay_node_id +
         "/relay-peer-auth/+";
}

std::string product_peer_authority_time_request_topic(
    const std::string &system_id,
    const std::string &relay_node_id) {
  if (!ProductPeerSecurity::valid_identifier_(system_id) ||
      !ProductPeerSecurity::valid_identifier_(relay_node_id)) {
    return {};
  }
  return "gh/v1/" + system_id + "/ingress/node/" + relay_node_id +
         "/relay-peer-auth/time-request";
}

std::string product_peer_authority_time_response_topic(
    const std::string &system_id,
    const std::string &relay_node_id) {
  if (!ProductPeerSecurity::valid_identifier_(system_id) ||
      !ProductPeerSecurity::valid_identifier_(relay_node_id)) {
    return {};
  }
  return "gh/v1/" + system_id + "/out/node/" + relay_node_id +
         "/relay-peer-auth/time";
}

std::string product_relay_ingress_topic(
    const std::string &system_id,
    const std::string &relay_node_id,
    const std::string &child_node_id) {
  if (!ProductPeerSecurity::valid_identifier_(system_id) ||
      !ProductPeerSecurity::valid_identifier_(relay_node_id) ||
      !ProductPeerSecurity::valid_identifier_(child_node_id)) {
    return {};
  }
  return "gh/v1/" + system_id + "/ingress/gateway/" + relay_node_id +
         "/" + child_node_id + "/frame";
}

bool encode_peer_authorization_request_json(
    const ProductPeerRequest &request,
    std::string *json) {
  if (json == nullptr || !request.valid_shape(true)) return false;
  std::string child_public;
  std::string child_nonce;
  std::string child_proof;
  std::string relay_public;
  std::string relay_nonce;
  std::string relay_proof;
  if (!b64(
          request.child.ephemeral_public_key.data(),
          request.child.ephemeral_public_key.size(), &child_public) ||
      !b64(
          request.child.nonce.data(), request.child.nonce.size(),
          &child_nonce) ||
      !b64(
          request.child.proof.data(), request.child.proof.size(),
          &child_proof) ||
      !b64(
          request.relay.ephemeral_public_key.data(),
          request.relay.ephemeral_public_key.size(), &relay_public) ||
      !b64(
          request.relay.nonce.data(), request.relay.nonce.size(),
          &relay_nonce) ||
      !b64(
          request.relay.proof.data(), request.relay.proof.size(),
          &relay_proof)) {
    return false;
  }

  // Keep byte ordering identical to Python's
  // json.dumps(..., sort_keys=True, separators=(",", ":")).
  *json =
      "{\"child\":{\"credential_generation\":" +
      std::to_string(request.child.credential_generation) +
      ",\"ephemeral_public_key\":\"" + child_public +
      "\",\"key_epoch\":" + std::to_string(request.child.key_epoch) +
      ",\"node_id\":\"" + request.child.node_id +
      "\",\"nonce\":\"" + child_nonce +
      "\",\"proof\":\"" + child_proof +
      "\"},\"relay\":{\"credential_generation\":" +
      std::to_string(request.relay.credential_generation) +
      ",\"ephemeral_public_key\":\"" + relay_public +
      "\",\"key_epoch\":" + std::to_string(request.relay.key_epoch) +
      ",\"node_id\":\"" + request.relay.node_id +
      "\",\"nonce\":\"" + relay_nonce +
      "\",\"proof\":\"" + relay_proof +
      "\"},\"relay_health\":{\"low_battery\":" +
      bool_text(request.relay_health.low_battery) +
      ",\"observed_at_ms\":" +
      std::to_string(request.relay_health.observed_at_ms) +
      ",\"overloaded\":" + bool_text(request.relay_health.overloaded) +
      ",\"relay_capable\":" +
      bool_text(request.relay_health.relay_capable) +
      "},\"requested_at_ms\":" + std::to_string(request.requested_at_ms) +
      ",\"schema\":\"" + kProductPeerAuthorizationRequestSchema +
      "\",\"session_id\":\"" + request.session_id +
      "\",\"system_id\":\"" + request.system_id + "\"}";
  return true;
}

bool decode_peer_authorization_response_json(
    const std::string &json,
    ProductPeerGrant *child_grant,
    ProductPeerGrant *relay_grant) {
  if (child_grant == nullptr || relay_grant == nullptr ||
      json.empty() || json.size() > 8192U) {
    return false;
  }
  std::string schema;
  std::string child_object;
  std::string relay_object;
  if (!extract_string(json, "schema", &schema) ||
      schema != kProductPeerAuthorizationResponseSchema ||
      !extract_flat_object(json, "child_grant", &child_object) ||
      !extract_flat_object(json, "relay_grant", &relay_object)) {
    return false;
  }
  ProductPeerGrant child;
  ProductPeerGrant relay;
  if (!decode_grant(child_object, ProductPeerRole::CHILD, &child) ||
      !decode_grant(relay_object, ProductPeerRole::RELAY, &relay) ||
      child.authorization_id != relay.authorization_id ||
      child.system_id != relay.system_id ||
      child.session_id != relay.session_id ||
      child.child_node_id != relay.child_node_id ||
      child.relay_node_id != relay.relay_node_id ||
      child.issued_at_ms != relay.issued_at_ms ||
      child.expires_at_ms != relay.expires_at_ms ||
      child.authorization_epoch != relay.authorization_epoch) {
    return false;
  }
  *child_grant = child;
  *relay_grant = relay;
  return true;
}

bool encode_peer_authority_time_request_json(
    const std::string &nonce,
    std::string *json) {
  if (json == nullptr || !valid_product_transport_nonce(nonce)) return false;
  *json = "{\"nonce\":\"" + nonce + "\",\"schema\":\"" +
          kProductPeerAuthorityTimeRequestSchema + "\"}";
  return true;
}

bool decode_peer_authority_time_request_json(
    const std::string &json,
    std::string *nonce) {
  if (nonce == nullptr || json.size() > 512U) return false;
  std::string schema;
  std::string parsed_nonce;
  if (!extract_string(json, "nonce", &parsed_nonce) ||
      !extract_string(json, "schema", &schema) ||
      schema != kProductPeerAuthorityTimeRequestSchema ||
      !valid_product_transport_nonce(parsed_nonce)) {
    return false;
  }
  *nonce = parsed_nonce;
  return true;
}

bool encode_peer_authority_time_response_json(
    const std::string &nonce,
    uint64_t authority_now_ms,
    std::string *json) {
  if (json == nullptr || authority_now_ms == 0 ||
      !valid_product_transport_nonce(nonce)) {
    return false;
  }
  *json =
      "{\"authority_now_ms\":" + std::to_string(authority_now_ms) +
      ",\"nonce\":\"" + nonce + "\",\"schema\":\"" +
      kProductPeerAuthorityTimeResponseSchema + "\"}";
  return true;
}

bool decode_peer_authority_time_response_json(
    const std::string &json,
    std::string *nonce,
    uint64_t *authority_now_ms) {
  if (nonce == nullptr || authority_now_ms == nullptr ||
      json.size() > 512U) {
    return false;
  }
  std::string schema;
  std::string parsed_nonce;
  uint64_t parsed_time = 0;
  if (!extract_uint64(json, "authority_now_ms", &parsed_time) ||
      parsed_time == 0 ||
      !extract_string(json, "nonce", &parsed_nonce) ||
      !extract_string(json, "schema", &schema) ||
      schema != kProductPeerAuthorityTimeResponseSchema ||
      !valid_product_transport_nonce(parsed_nonce)) {
    return false;
  }
  *nonce = parsed_nonce;
  *authority_now_ms = parsed_time;
  return true;
}

}  // namespace esphome::greenhouse_n3w_s5_manager_transport
