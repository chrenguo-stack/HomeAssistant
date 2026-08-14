#pragma once

#include <cstdint>
#include <string>

#include "esphome/components/greenhouse_n3w_product_runtime/n3w_product_peer_security.h"

namespace esphome::greenhouse_n3w_s5_manager_transport {

using greenhouse_n3w_product_runtime::ProductPeerGrant;
using greenhouse_n3w_product_runtime::ProductPeerRequest;
using greenhouse_n3w_product_runtime::ProductPeerSecurity;

constexpr char kProductPeerAuthorizationRequestSchema[] =
    "gh.n3w-product.peer-auth-request/1";
constexpr char kProductPeerAuthorizationResponseSchema[] =
    "gh.n3w-product.peer-auth-response/1";
constexpr char kProductPeerAuthorityTimeRequestSchema[] =
    "gh.n3w-product.peer-auth-time-request/1";
constexpr char kProductPeerAuthorityTimeResponseSchema[] =
    "gh.n3w-product.peer-auth-time-response/1";

std::string product_peer_authorization_request_topic(
    const std::string &system_id,
    const std::string &relay_node_id);
std::string product_peer_authorization_response_topic(
    const std::string &system_id,
    const std::string &relay_node_id,
    const std::string &session_id);
std::string product_peer_authorization_response_subscription(
    const std::string &system_id,
    const std::string &relay_node_id);
std::string product_peer_authority_time_request_topic(
    const std::string &system_id,
    const std::string &relay_node_id);
std::string product_peer_authority_time_response_topic(
    const std::string &system_id,
    const std::string &relay_node_id);
std::string product_relay_ingress_topic(
    const std::string &system_id,
    const std::string &relay_node_id,
    const std::string &child_node_id);

bool encode_peer_authorization_request_json(
    const ProductPeerRequest &request,
    std::string *json);
bool decode_peer_authorization_response_json(
    const std::string &json,
    ProductPeerGrant *child_grant,
    ProductPeerGrant *relay_grant);

bool encode_peer_authority_time_request_json(
    const std::string &nonce,
    std::string *json);
bool decode_peer_authority_time_request_json(
    const std::string &json,
    std::string *nonce);
bool encode_peer_authority_time_response_json(
    const std::string &nonce,
    uint64_t authority_now_ms,
    std::string *json);
bool decode_peer_authority_time_response_json(
    const std::string &json,
    std::string *nonce,
    uint64_t *authority_now_ms);

bool valid_product_transport_nonce(const std::string &nonce);

}  // namespace esphome::greenhouse_n3w_s5_manager_transport
