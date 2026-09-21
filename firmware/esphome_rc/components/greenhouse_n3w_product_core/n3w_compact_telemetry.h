#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "n3w_core.h"
#include "n3w_simple_crypto.h"

namespace esphome::greenhouse_n3w_core {

constexpr std::size_t kEspNowV2PayloadLimit = 1470;
constexpr std::size_t kCompactTelemetryHeaderBytes = 48;
constexpr std::size_t kCompactTelemetryMaxWireBytes =
    kCompactTelemetryHeaderBytes + kMaxCiphertextBytes;

static_assert(kCompactTelemetryMaxWireBytes <= kEspNowV2PayloadLimit,
              "N3-W compact telemetry must fit one ESP-NOW v2 frame");

enum class CompactTelemetryError : uint8_t {
  NONE = 0,
  INVALID_ARGUMENT,
  FRAME_TOO_LARGE,
  FRAME_TRUNCATED,
  FRAME_FORMAT_REJECTED,
  CRYPTO_FAILED,
};

struct CompactTelemetryFrameV2 {
  uint64_t boot_session{0};
  uint32_t seq{0};
  uint32_t key_epoch{0};
  std::array<uint8_t, kNonceBytes> nonce{};
  std::array<uint8_t, kTagBytes> tag{};
  std::vector<uint8_t> ciphertext;

  std::string boot_id() const;
  bool valid() const;
};

CompactTelemetryError build_compact_aad_v2(
    const std::string &system_id,
    const std::string &node_id,
    uint32_t key_epoch,
    const std::string &boot_id,
    uint32_t seq,
    std::string *aad);

CompactTelemetryError encrypt_compact_telemetry_v2(
    const std::string &system_id,
    const std::string &node_id,
    uint32_t key_epoch,
    const std::string &boot_id,
    uint32_t seq,
    const ApplicationKeyState &key_state,
    const std::string &telemetry_json,
    CompactTelemetryFrameV2 *frame);

CompactTelemetryError decrypt_compact_telemetry_v2(
    const std::string &system_id,
    const std::string &node_id,
    const ApplicationKeyState &key_state,
    const CompactTelemetryFrameV2 &frame,
    std::string *telemetry_json);

CompactTelemetryError encode_compact_telemetry_frame_v2(
    const CompactTelemetryFrameV2 &frame,
    std::vector<uint8_t> *encoded);

CompactTelemetryError decode_compact_telemetry_frame_v2(
    const uint8_t *data,
    std::size_t size,
    CompactTelemetryFrameV2 *frame);

CompactTelemetryError wrap_compact_relay_mqtt_v2(
    const std::vector<uint8_t> &encoded_frame,
    std::string *payload_json);


}  // namespace esphome::greenhouse_n3w_core
