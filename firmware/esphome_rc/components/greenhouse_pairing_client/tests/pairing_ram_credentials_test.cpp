#include <cassert>
#include <iostream>

#include "pairing_ram_credentials.h"

using namespace esphome::greenhouse_pairing_client;

int main() {
  RamCredentialBundle bundle{
      .schema = "gh.pair.credentials/1",
      .system_id = "greenhouse",
      .node_id = "gh-n1-stage2c2",
      .broker_host = "broker.local",
      .broker_port = 8883,
      .broker_tls_server_name = "broker.local",
      .ca_pem = "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n",
      .mqtt_username = "ghn_stage2c2",
      .mqtt_client_id = "gh-n1-stage2c2",
      .credential_generation = 7,
      .mqtt_password = "ram-only-password",
  };
  assert(bundle.valid());
  assert(bundle.present());
  assert(bundle.delivery_ack_json() ==
         "{\"credential_generation\":7,\"node_id\":\"gh-n1-stage2c2\","
         "\"schema\":\"gh.pair.delivery-ack/1\",\"stored\":true}");
  bundle.clear();
  assert(!bundle.present());
  assert(!bundle.valid());
  std::cout << "stage2c2 RAM credential tests passed\n";
}
