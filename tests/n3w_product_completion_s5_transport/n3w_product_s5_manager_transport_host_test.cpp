#include <cassert>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "esphome/components/greenhouse_n3w_s5_manager_transport/n3w_product_s5_manager_transport.h"

using namespace esphome::greenhouse_n3w_s5_manager_transport;
using namespace esphome::greenhouse_n3w_product_runtime;
using esphome::greenhouse_n3w_core::RelayFrame;

namespace {

std::string read_file(const char *path) {
  std::ifstream input(path, std::ios::binary);
  assert(input.good());
  std::ostringstream output;
  output << input.rdbuf();
  return output.str();
}

ProductPeerKey from_hex(const std::string &hex) {
  assert(hex.size() == 64);
  ProductPeerKey output{};
  auto nibble = [](char ch) -> uint8_t {
    if (ch >= '0' && ch <= '9') return static_cast<uint8_t>(ch - '0');
    if (ch >= 'a' && ch <= 'f')
      return static_cast<uint8_t>(10 + ch - 'a');
    assert(false);
    return 0;
  };
  for (std::size_t index = 0; index < output.size(); ++index) {
    output[index] = static_cast<uint8_t>(
        (nibble(hex[index * 2]) << 4U) |
        nibble(hex[index * 2 + 1]));
  }
  return output;
}

class FakeClock final : public ProductRuntimeClock {
 public:
  uint64_t now_ms() const override { return now; }
  uint64_t now{1000};
};

struct Published {
  std::string topic;
  std::string payload;
  uint8_t qos{0};
  bool retain{false};
};

class FakeBus final : public ProductS5MessageBusPort {
 public:
  bool begin(
      const std::string &value,
      ProductS5MessageBusSink *value_sink) override {
    if (started || value.empty() || value_sink == nullptr) return false;
    started = true;
    subscription = value;
    sink = value_sink;
    return true;
  }

  bool connected() override { return started && is_connected; }

  bool publish_message(
      const std::string &topic,
      const std::string &payload,
      uint8_t qos,
      bool retain) override {
    if (!connected()) return false;
    published.push_back(Published{topic, payload, qos, retain});
    return true;
  }

  void deliver(
      const std::string &topic,
      const std::string &payload) {
    assert(sink != nullptr);
    sink->on_s5_message(topic, payload);
  }

  bool started{false};
  bool is_connected{true};
  std::string subscription;
  ProductS5MessageBusSink *sink{nullptr};
  std::vector<Published> published;
};

class FakeAuthorizationSink final
    : public ProductS5ManagerAuthorizationSink {
 public:
  bool queue_s5_manager_authorization(
      const ProductPeerGrant &child,
      const ProductPeerGrant &relay) override {
    ++calls;
    child_grant = child;
    relay_grant = relay;
    return accept;
  }

  bool accept{true};
  unsigned calls{0};
  ProductPeerGrant child_grant{};
  ProductPeerGrant relay_grant{};
};

ProductPeerRequest fixed_request() {
  ProductPeerRequest request;
  request.system_id = "system001";
  request.session_id = "s5-session-0001";
  request.requested_at_ms = 1786689000000ULL;
  request.child.node_id = "node_child01";
  request.child.credential_generation = 1;
  request.child.key_epoch = 1;
  request.child.ephemeral_public_key = from_hex(
      "07a37cbc142093c8b755dc1b10e86cb426374ad16aa853ed0bdfc0b2b86d1c7c");
  request.child.nonce = from_hex(
      "4142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f60");
  request.child.proof = from_hex(
      "01d10498afbfe1c88a50992e614ec1b4c43ef6d715fdb6b1dc7fc1784f653db8");
  request.relay.node_id = "node_relay01";
  request.relay.credential_generation = 2;
  request.relay.key_epoch = 3;
  request.relay.ephemeral_public_key = from_hex(
      "5869aff450549732cbaaed5e5df9b30a6da31cb0e5742bad5ad4a1a768f1a67b");
  request.relay.nonce = from_hex(
      "6162636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f80");
  request.relay.proof = from_hex(
      "7cd74be1126de0087da8dad7e2dce68510913c324dd93f0d07d0892a97706801");
  request.relay_health.observed_at_ms = 1786688999000ULL;
  request.relay_health.relay_capable = true;
  request.relay_health.low_battery = false;
  request.relay_health.overloaded = false;
  assert(request.valid_shape(true));
  return request;
}

}  // namespace

int main(int argc, char **argv) {
  assert(argc == 3);
  const std::string manager_request = read_file(argv[1]);
  const std::string manager_response = read_file(argv[2]);

  ProductPeerRequest request = fixed_request();
  std::string encoded_request;
  assert(encode_peer_authorization_request_json(
      request, &encoded_request));
  assert(encoded_request == manager_request);

  ProductPeerGrant decoded_child;
  ProductPeerGrant decoded_relay;
  assert(decode_peer_authorization_response_json(
      manager_response, &decoded_child, &decoded_relay));
  assert(decoded_child.role == ProductPeerRole::CHILD);
  assert(decoded_relay.role == ProductPeerRole::RELAY);
  assert(decoded_child.authorization_id ==
         "11111111-2222-3333-4444-555555555555");
  assert(decoded_relay.authorization_id ==
         decoded_child.authorization_id);

  FakeClock clock;
  FakeBus bus;
  FakeAuthorizationSink authorization_sink;
  ProductS5IsolatedManagerTransport transport(
      "system001",
      "node_relay01",
      &clock,
      &bus,
      &authorization_sink);
  assert(transport.start());
  assert(bus.subscription ==
         "gh/v1/system001/out/node/node_relay01/relay-peer-auth/+");

  uint64_t authority_now = 0;
  assert(!transport.authority_now_ms(&authority_now));
  assert(bus.published.size() == 1);
  assert(bus.published.back().topic ==
         "gh/v1/system001/ingress/node/node_relay01/"
         "relay-peer-auth/time-request");
  assert(bus.published.back().qos == 1);
  assert(!bus.published.back().retain);

  std::string time_nonce;
  assert(decode_peer_authority_time_request_json(
      bus.published.back().payload, &time_nonce));
  std::string time_response;
  assert(encode_peer_authority_time_response_json(
      time_nonce, request.requested_at_ms, &time_response));
  bus.deliver(
      "gh/v1/system001/out/node/node_relay01/relay-peer-auth/time",
      time_response);
  assert(transport.authority_now_ms(&authority_now));
  assert(authority_now == request.requested_at_ms);

  assert(transport.submit_peer_authorization(request));
  assert(transport.authorization_pending());
  assert(bus.published.back().topic ==
         "gh/v1/system001/ingress/node/node_relay01/"
         "relay-peer-auth/request");
  assert(bus.published.back().payload == manager_request);
  assert(bus.published.back().qos == 1);
  assert(!bus.published.back().retain);

  bus.deliver(
      "gh/v1/system001/out/node/node_relay01/"
      "relay-peer-auth/s5-session-0001",
      manager_response);
  assert(authorization_sink.calls == 1);
  assert(!transport.authorization_pending());
  assert(authorization_sink.child_grant.authorization_id ==
         decoded_child.authorization_id);
  assert(authorization_sink.relay_grant.grant_mac ==
         decoded_relay.grant_mac);

  // A duplicate response is not delivered after the request has been consumed.
  bus.deliver(
      "gh/v1/system001/out/node/node_relay01/"
      "relay-peer-auth/s5-session-0001",
      manager_response);
  assert(authorization_sink.calls == 1);

  RelayFrame frame;
  frame.header.gateway_id = "node_relay01";
  frame.header.node_id = "node_child01";
  frame.header.key_epoch = 3;
  frame.header.boot_id = "boot_0000000000000001";
  frame.header.seq = 42;
  frame.ciphertext = {1, 2, 3, 4};
  frame.tag[0] = 1;
  assert(transport.accept_for_forwarding(frame));
  assert(bus.published.back().topic ==
         "gh/v1/system001/ingress/gateway/node_relay01/"
         "node_child01/frame");
  std::string expected_relay_payload;
  assert(
      esphome::greenhouse_n3w_core::serialize_relay_frame_json(
          frame, &expected_relay_payload) ==
      esphome::greenhouse_n3w_core::CoreError::NONE);
  assert(bus.published.back().payload == expected_relay_payload);
  assert(bus.published.back().qos == 1);
  assert(!bus.published.back().retain);

  // Manager epoch expires independently of endpoint monotonic uptime.
  clock.now = 32001;
  assert(!transport.authority_now_ms(&authority_now));

  return 0;
}
