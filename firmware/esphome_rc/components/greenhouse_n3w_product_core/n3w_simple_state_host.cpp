#include "n3w_esp32_simple_nvs.h"

#ifndef USE_ESP32

#include <algorithm>

namespace esphome::greenhouse_n3w_core {

namespace {
template<typename Container>
bool any_nonzero(const Container &value) {
  return std::any_of(value.begin(), value.end(), [](uint8_t byte) { return byte != 0; });
}
}  // namespace

bool ProvisionedPeerStateV2::valid() const {
  return valid_simple_identity_v2(system_id) && valid_simple_identity_v2(node_id) &&
         peer_trust_generation > 0 && n3w_key_epoch > 0 &&
         any_nonzero(system_peer_key) && any_nonzero(n3w_application_key);
}

void ProvisionedPeerStateV2::clear() {
  system_id.clear();
  node_id.clear();
  peer_trust_generation = 0;
  std::fill(system_peer_key.begin(), system_peer_key.end(), 0);
  n3w_key_epoch = 0;
  std::fill(n3w_application_key.begin(), n3w_application_key.end(), 0);
}

}  // namespace esphome::greenhouse_n3w_core

#endif
