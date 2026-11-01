#include <cassert>
#include <iostream>
#include <type_traits>
#include <utility>

#include "pairing_ram_credentials.h"

using namespace esphome::greenhouse_pairing_client;

namespace {

RamCredentialBundle make_bundle() {
  RamCredentialBundle bundle;
  bundle.schema = "gh.pair.credentials/1";
  bundle.system_id = "greenhouse";
  bundle.node_id = "gh-n1-stage2c2";
  bundle.broker_host = "broker.local";
  bundle.broker_port = 8883;
  bundle.broker_tls_server_name = "broker.local";
  bundle.ca_pem = "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n";
  bundle.mqtt_username = "ghn_stage2c2";
  bundle.mqtt_client_id = "gh-n1-stage2c2";
  bundle.credential_generation = 7;
  bundle.mqtt_password = "ram-only-password";
  return bundle;
}

}  // namespace

int main() {
  static_assert(!std::is_copy_constructible_v<RamCredentialBundle>);
  static_assert(!std::is_copy_assignable_v<RamCredentialBundle>);
  static_assert(std::is_move_constructible_v<RamCredentialBundle>);
  static_assert(std::is_move_assignable_v<RamCredentialBundle>);

  RamCredentialBundle source = make_bundle();
  assert(source.valid());
  assert(source.present());
  assert(source.delivery_ack_json() ==
         "{\"credential_generation\":7,\"node_id\":\"gh-n1-stage2c2\","
         "\"schema\":\"gh.pair.delivery-ack/1\",\"stored\":true}");

  RamCredentialBundle moved(std::move(source));
  assert(moved.valid());
  assert(!source.present());
  assert(source.mqtt_password.empty());
  assert(source.ca_pem.empty());

  RamCredentialBundle assigned;
  assigned = std::move(moved);
  assert(assigned.valid());
  assert(!moved.present());
  assert(moved.mqtt_password.empty());
  assert(moved.ca_pem.empty());

  assigned.clear();
  assert(!assigned.present());
  assert(!assigned.valid());
  std::cout << "stage2c2 RAM credential tests passed\n";
}
