#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

#include "esphome/components/greenhouse_pairing_client/pairing_credential_codec.h"
#include "esphome/components/greenhouse_pairing_client/pairing_ram_credentials.h"

using esphome::greenhouse_pairing_client::PairingCredentialCodec;
using esphome::greenhouse_pairing_client::RamCredentialBundle;

namespace {

RamCredentialBundle make_bundle(bool product) {
  RamCredentialBundle bundle;
  bundle.schema = "gh.pair.credentials/1";
  bundle.system_id = "system001";
  bundle.node_id = "node_child01";
  bundle.broker_host = "broker.local";
  bundle.broker_port = 8883;
  bundle.broker_tls_server_name = "broker.local";
  bundle.ca_pem = "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n";
  bundle.mqtt_username = "node_child01";
  bundle.mqtt_client_id = "node_child01";
  bundle.credential_generation = 7;
  bundle.mqtt_password = "node-only-mqtt-password";
  if (product) {
    bundle.n3w_key_epoch = 9;
    bundle.n3w_application_key =
        "gYKDhIWGh4iJiouMjY6PkJGSk5SVlpeYmZqbnJ2en6A";
  }
  return bundle;
}

uint16_t persisted_version(const std::vector<uint8_t> &encoded) {
  assert(encoded.size() >= 6);
  return static_cast<uint16_t>(
      (static_cast<uint16_t>(encoded[4]) << 8U) |
      static_cast<uint16_t>(encoded[5]));
}

}  // namespace

int main() {
  RamCredentialBundle legacy = make_bundle(false);
  assert(legacy.valid());
  assert(!legacy.has_n3w_credentials());
  std::vector<uint8_t> legacy_encoded;
  assert(PairingCredentialCodec::encode(legacy, &legacy_encoded));
  assert(persisted_version(legacy_encoded) == 1);
  RamCredentialBundle legacy_decoded;
  assert(PairingCredentialCodec::decode(legacy_encoded, &legacy_decoded));
  assert(legacy_decoded.valid());
  assert(!legacy_decoded.has_n3w_credentials());
  assert(legacy_decoded.node_id == legacy.node_id);

  RamCredentialBundle product = make_bundle(true);
  assert(product.valid());
  assert(product.has_n3w_credentials());
  std::vector<uint8_t> product_encoded;
  assert(PairingCredentialCodec::encode(product, &product_encoded));
  assert(persisted_version(product_encoded) == 2);
  RamCredentialBundle product_decoded;
  assert(PairingCredentialCodec::decode(product_encoded, &product_decoded));
  assert(product_decoded.valid());
  assert(product_decoded.has_n3w_credentials());
  assert(product_decoded.n3w_key_epoch == 9);
  assert(product_decoded.n3w_application_key == product.n3w_application_key);

  RamCredentialBundle partial = make_bundle(false);
  partial.n3w_key_epoch = 9;
  assert(!partial.valid());
  partial.clear();
  assert(!partial.present());
  assert(partial.n3w_application_key.empty());
  assert(partial.n3w_key_epoch == 0);

  std::vector<uint8_t> corrupt = product_encoded;
  assert(corrupt.size() > 16);
  corrupt[12] = 0;
  corrupt[13] = 0;
  corrupt[14] = 0;
  corrupt[15] = 0;
  RamCredentialBundle rejected;
  assert(!PairingCredentialCodec::decode(corrupt, &rejected));
  assert(!rejected.present());

  std::cout << "S5_PRODUCT_CREDENTIAL_PERSISTENCE=PASS\n";
  return 0;
}
