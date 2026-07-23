#include <cstdlib>
#include <iostream>
#include <string>

#include "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_client_core.h"
#include "firmware/esphome_rc/components/greenhouse_pairing_client/pairing_ram_credentials.h"
#include "firmware/esphome_rc/components/greenhouse_pairing_client/secure_pairing_channel.h"

namespace esphome::greenhouse_pairing_client {

// pairing_ram_credentials.cpp references this function from an unrelated JSON
// rendering method. The root-cause test does not exercise that path, so a
// minimal host-only definition keeps the linkage focused on credential
// validation without pulling ESP cryptography dependencies into the test.
std::string SecurePairingChannel::json_escape(const std::string &value) {
  return value;
}

}  // namespace esphome::greenhouse_pairing_client

namespace {

using esphome::greenhouse_pairing_client::CREDENTIALS_CONTENT_TYPE;
using esphome::greenhouse_pairing_client::PairingClientCore;
using esphome::greenhouse_pairing_client::RamCredentialBundle;

[[noreturn]] void fail(const char *message) {
  std::cerr << "STAGE2D9_V68_ROOT_CAUSE_TEST=FAIL reason=" << message << '\n';
  std::exit(2);
}

void require(bool condition, const char *message) {
  if (!condition)
    fail(message);
}

RamCredentialBundle make_bundle(const std::string &host,
                                const std::string &tls_name) {
  RamCredentialBundle bundle;
  bundle.schema = CREDENTIALS_CONTENT_TYPE;
  bundle.system_id = "gh-test-system-815f0baef097";
  bundle.node_id = "gh-test-node-815f0baef097";
  bundle.broker_host = host;
  bundle.broker_port = 8883;
  bundle.broker_tls_server_name = tls_name;
  bundle.ca_pem = "stage2d9-test-ca";
  bundle.mqtt_username = "stage2d9-test";
  bundle.mqtt_client_id = "gh-test-client-gh-test-run-815f0baef097";
  bundle.credential_generation = 1;
  bundle.mqtt_password =
      "e506bc67de2f71fb5c082146d7730e5e110b31a3989249d8a8014c6231031513";
  return bundle;
}

}  // namespace

int main() {
  require(!PairingClientCore::valid_local_host("stage2d9.invalid"),
          "dot-invalid host unexpectedly accepted");
  require(PairingClientCore::valid_local_host("stage2d9.local"),
          "dot-local host unexpectedly rejected");

  RamCredentialBundle frozen_v68 =
      make_bundle("stage2d9.invalid", "stage2d9.invalid");
  require(!frozen_v68.valid(),
          "frozen V68 credential bundle unexpectedly valid");

  RamCredentialBundle corrected =
      make_bundle("stage2d9.local", "stage2d9.local");
  require(corrected.valid(),
          "corrected local-only credential bundle unexpectedly invalid");

  std::cout << "STAGE2D9_V68_INVALID_HOST_REJECTED=true\n";
  std::cout << "STAGE2D9_V69_LOCAL_HOST_ACCEPTED=true\n";
  std::cout << "STAGE2D9_V68_ROOT_CAUSE="
               "candidate_host_contract_mismatch\n";
  std::cout << "STAGE2D9_V68_ROOT_CAUSE_TEST=PASS\n";
  return 0;
}
