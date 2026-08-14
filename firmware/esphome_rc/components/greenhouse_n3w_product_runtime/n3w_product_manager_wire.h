#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

#include "n3w_product_peer_security.h"

namespace esphome::greenhouse_n3w_product_runtime {

class ProductManagerPeerAuthorizationCodec {
 public:
  static std::string request_topic(
      const std::string &system_id,
      const std::string &relay_node_id);
  static std::string response_topic(
      const std::string &system_id,
      const std::string &relay_node_id,
      const std::string &session_id);

  static bool encode_request(
      const ProductPeerRequest &request,
      std::string *payload);
  static bool decode_response(
      const std::string &payload,
      const ProductPeerRequest &expected_request,
      ProductPeerGrant *child_grant,
      ProductPeerGrant *relay_grant);

 private:
  static bool decode_base64url32_(
      const std::string &value,
      ProductPeerKey *output);
};

}  // namespace esphome::greenhouse_n3w_product_runtime
