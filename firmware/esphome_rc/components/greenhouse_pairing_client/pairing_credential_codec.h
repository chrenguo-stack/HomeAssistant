#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "pairing_ram_credentials.h"

namespace esphome::greenhouse_pairing_client {

class PairingCredentialCodec {
 public:
  static bool encode(const RamCredentialBundle &credentials,
                     std::vector<uint8_t> *output);
  static bool decode(const std::vector<uint8_t> &input,
                     RamCredentialBundle *credentials);
  static void zeroize(std::vector<uint8_t> *value);

 private:
  static constexpr uint16_t SCHEMA_VERSION = 1;
};

}  // namespace esphome::greenhouse_pairing_client
