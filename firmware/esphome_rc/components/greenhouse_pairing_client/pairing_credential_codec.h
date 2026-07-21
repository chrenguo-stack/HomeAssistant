#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "pairing_ram_credentials.h"

namespace esphome::greenhouse_pairing_client {

static constexpr uint16_t PERSISTED_CREDENTIAL_PAYLOAD_VERSION = 1;
static constexpr size_t PERSISTED_CREDENTIAL_MAX_BYTES = 12288;

class PairingCredentialCodec {
 public:
  static bool encode(const RamCredentialBundle &bundle,
                     std::vector<uint8_t> *output);
  static bool decode(const std::vector<uint8_t> &input,
                     RamCredentialBundle *output);
};

}  // namespace esphome::greenhouse_pairing_client
