#include "n3w_compact_telemetry.h"

#include <algorithm>
#include <cstring>

#include "mbedtls/base64.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint8_t kMagic[] = {'N', '3', 'W', '2'};

void append_u32(std::vector<uint8_t> *out, uint32_t value) {
  for (int shift = 24; shift >= 0; shift -= 8) {
    out->push_back(static_cast<uint8_t>((value >> shift) & 0xffU));
  }
}

void append_u64(std::vector<uint8_t> *out, uint64_t value) {
  for (int shift = 56; shift >= 0; shift -= 8) {
    out->push_back(static_cast<uint8_t>((value >> shift) & 0xffU));
  }
}

bool read_u32(const uint8_t *data, std::size_t size, std::size_t *offset, uint32_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr || *offset + 4U > size) {
    return false;
  }
  uint32_t parsed = 0;
  for (std::size_t i = 0; i < 4U; ++i) parsed = (parsed << 8U) | data[*offset + i];
  *offset += 4U;
  *value = parsed;
  return true;
}

bool read_u64(const uint8_t *data, std::size_t size, std::size_t *offset, uint64_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr || *offset + 8U > size) {
    return false;
  }
  uint64_t parsed = 0;
  for (std::size_t i = 0; i < 8U; ++i) parsed = (parsed << 8U) | data[*offset + i];
  *offset += 8U;
  *value = parsed;
  return true;
}

uint8_t nibble(char ch) {
  if (ch >= '0' && ch <= '9') return static_cast<uint8_t>(ch - '0');
  if (ch >= 'a' && ch <= 'f') return static_cast<uint8_t>(10 + ch - 'a');
  return static_cast<uint8_t>(10 + ch - 'A');
}

bool decode_hex_vector(const char *text, std::vector<uint8_t> *output) {
  if (text == nullptr || output == nullptr) return false;
  const std::size_t length = std::strlen(text);
  if (length == 0 || (length % 2U) != 0) return false;
  output->assign(length / 2U, 0);
  const auto valid = [](char ch) {
    return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') ||
           (ch >= 'A' && ch <= 'F');
  };
  for (std::size_t i = 0; i < output->size(); ++i) {
    const char high = text[i * 2U];
    const char low = text[i * 2U + 1U];
    if (!valid(high) || !valid(low)) return false;
    (*output)[i] = static_cast<uint8_t>((nibble(high) << 4U) | nibble(low));
  }
  return true;
}

}  // namespace

std::string CompactTelemetryFrameV2::boot_id() const {
  return format_boot_id(boot_session);
}

bool CompactTelemetryFrameV2::valid() const {
  return boot_session > 0 && key_epoch > 0 &&
         nonce.size() == kNonceBytes && tag.size() == kTagBytes &&
         !ciphertext.empty() && ciphertext.size() <= kMaxCiphertextBytes &&
         kCompactTelemetryHeaderBytes + ciphertext.size() <= kEspNowV2PayloadLimit;
}

CompactTelemetryError build_compact_aad_v2(
    const std::string &system_id,
    const std::string &node_id,
    uint32_t key_epoch,
    const std::string &boot_id,
    uint32_t seq,
    std::string *aad) {
  if (aad == nullptr || !valid_simple_identity_v2(system_id) || !valid_simple_identity_v2(node_id) ||
      key_epoch == 0) {
    return CompactTelemetryError::INVALID_ARGUMENT;
  }
  uint64_t boot_session = 0;
  if (!parse_boot_id(boot_id, &boot_session)) {
    return CompactTelemetryError::INVALID_ARGUMENT;
  }
  (void) boot_session;
  // Python Manager json.dumps(..., separators=(",", ":"), sort_keys=True)
  // sorts these keys exactly: boot_id,key_epoch,node_id,schema,seq,system_id.
  *aad =
      "{\"boot_id\":\"" + boot_id +
      "\",\"key_epoch\":" + std::to_string(key_epoch) +
      ",\"node_id\":\"" + node_id +
      "\",\"schema\":\"gh.relay/2\"" +
      ",\"seq\":" + std::to_string(seq) +
      ",\"system_id\":\"" + system_id + "\"}";
  return CompactTelemetryError::NONE;
}

CompactTelemetryError encrypt_compact_telemetry_v2(
    const std::string &system_id,
    const std::string &node_id,
    uint32_t key_epoch,
    const std::string &boot_id,
    uint32_t seq,
    const ApplicationKeyState &key_state,
    const std::string &telemetry_json,
    CompactTelemetryFrameV2 *frame) {
  if (frame == nullptr || telemetry_json.empty() ||
      telemetry_json.size() > kMaxCiphertextBytes ||
      !key_state.valid_for_encrypt() || key_state.key_epoch != key_epoch) {
    return CompactTelemetryError::INVALID_ARGUMENT;
  }
  uint64_t boot_session = 0;
  if (!parse_boot_id(boot_id, &boot_session)) return CompactTelemetryError::INVALID_ARGUMENT;
  std::array<uint8_t, kNonceBytes> nonce{};
  if (derive_nonce(boot_id, seq, &nonce) != CoreError::NONE) {
    return CompactTelemetryError::CRYPTO_FAILED;
  }
  std::string aad;
  if (build_compact_aad_v2(system_id, node_id, key_epoch, boot_id, seq, &aad) !=
      CompactTelemetryError::NONE) {
    return CompactTelemetryError::INVALID_ARGUMENT;
  }
  std::vector<uint8_t> ciphertext;
  std::array<uint8_t, kTagBytes> tag{};
  if (aes256gcm_encrypt(
          key_state, nonce, telemetry_json, aad, &ciphertext, &tag) != CoreError::NONE) {
    return CompactTelemetryError::CRYPTO_FAILED;
  }
  CompactTelemetryFrameV2 candidate{
      boot_session,
      seq,
      key_epoch,
      nonce,
      tag,
      std::move(ciphertext),
  };
  if (!candidate.valid()) return CompactTelemetryError::FRAME_TOO_LARGE;
  *frame = std::move(candidate);
  return CompactTelemetryError::NONE;
}

CompactTelemetryError decrypt_compact_telemetry_v2(
    const std::string &system_id,
    const std::string &node_id,
    const ApplicationKeyState &key_state,
    const CompactTelemetryFrameV2 &frame,
    std::string *telemetry_json) {
  if (telemetry_json == nullptr || !frame.valid() ||
      !key_state.valid_for_encrypt() || key_state.key_epoch != frame.key_epoch) {
    return CompactTelemetryError::INVALID_ARGUMENT;
  }
  const std::string boot_id = frame.boot_id();
  std::array<uint8_t, kNonceBytes> expected_nonce{};
  if (derive_nonce(boot_id, frame.seq, &expected_nonce) != CoreError::NONE ||
      expected_nonce != frame.nonce) {
    return CompactTelemetryError::CRYPTO_FAILED;
  }
  std::string aad;
  if (build_compact_aad_v2(
          system_id, node_id, frame.key_epoch, boot_id, frame.seq, &aad) !=
      CompactTelemetryError::NONE) {
    return CompactTelemetryError::INVALID_ARGUMENT;
  }
  if (aes256gcm_decrypt(
          key_state, frame.nonce, frame.ciphertext, frame.tag, aad,
          telemetry_json) != CoreError::NONE) {
    return CompactTelemetryError::CRYPTO_FAILED;
  }
  return CompactTelemetryError::NONE;
}

CompactTelemetryError encode_compact_telemetry_frame_v2(
    const CompactTelemetryFrameV2 &frame,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !frame.valid()) return CompactTelemetryError::INVALID_ARGUMENT;
  encoded->clear();
  encoded->reserve(kCompactTelemetryHeaderBytes + frame.ciphertext.size());
  encoded->insert(encoded->end(), std::begin(kMagic), std::end(kMagic));
  append_u64(encoded, frame.boot_session);
  append_u32(encoded, frame.seq);
  append_u32(encoded, frame.key_epoch);
  encoded->insert(encoded->end(), frame.nonce.begin(), frame.nonce.end());
  encoded->insert(encoded->end(), frame.tag.begin(), frame.tag.end());
  encoded->insert(encoded->end(), frame.ciphertext.begin(), frame.ciphertext.end());
  return encoded->size() <= kEspNowV2PayloadLimit
             ? CompactTelemetryError::NONE
             : CompactTelemetryError::FRAME_TOO_LARGE;
}

CompactTelemetryError decode_compact_telemetry_frame_v2(
    const uint8_t *data,
    std::size_t size,
    CompactTelemetryFrameV2 *frame) {
  if (data == nullptr || frame == nullptr) return CompactTelemetryError::INVALID_ARGUMENT;
  if (size <= kCompactTelemetryHeaderBytes) return CompactTelemetryError::FRAME_TRUNCATED;
  if (size > kEspNowV2PayloadLimit ||
      !std::equal(std::begin(kMagic), std::end(kMagic), data)) {
    return CompactTelemetryError::FRAME_FORMAT_REJECTED;
  }
  std::size_t offset = sizeof(kMagic);
  CompactTelemetryFrameV2 candidate;
  if (!read_u64(data, size, &offset, &candidate.boot_session) ||
      !read_u32(data, size, &offset, &candidate.seq) ||
      !read_u32(data, size, &offset, &candidate.key_epoch) ||
      offset + kNonceBytes + kTagBytes >= size) {
    return CompactTelemetryError::FRAME_TRUNCATED;
  }
  std::copy_n(data + offset, kNonceBytes, candidate.nonce.begin());
  offset += kNonceBytes;
  std::copy_n(data + offset, kTagBytes, candidate.tag.begin());
  offset += kTagBytes;
  candidate.ciphertext.assign(data + offset, data + size);
  if (!candidate.valid()) return CompactTelemetryError::FRAME_FORMAT_REJECTED;
  *frame = std::move(candidate);
  return CompactTelemetryError::NONE;
}

CompactTelemetryError wrap_compact_relay_mqtt_v2(
    const std::vector<uint8_t> &encoded_frame,
    std::string *payload_json) {
  if (payload_json == nullptr || encoded_frame.empty()) {
    return CompactTelemetryError::INVALID_ARGUMENT;
  }
  CompactTelemetryFrameV2 decoded;
  if (decode_compact_telemetry_frame_v2(
          encoded_frame.data(), encoded_frame.size(), &decoded) !=
      CompactTelemetryError::NONE) {
    return CompactTelemetryError::FRAME_FORMAT_REJECTED;
  }
  const std::size_t capacity = ((encoded_frame.size() + 2U) / 3U) * 4U + 1U;
  std::vector<unsigned char> base64(capacity, 0);
  std::size_t written = 0;
  if (mbedtls_base64_encode(
          base64.data(), base64.size(), &written,
          encoded_frame.data(), encoded_frame.size()) != 0) {
    return CompactTelemetryError::FRAME_FORMAT_REJECTED;
  }
  payload_json->assign("{\"frame_b64\":\"");
  payload_json->append(reinterpret_cast<const char *>(base64.data()), written);
  payload_json->append("\",\"schema\":\"gh.relay/2\"}");
  return CompactTelemetryError::NONE;
}


}  // namespace esphome::greenhouse_n3w_core
