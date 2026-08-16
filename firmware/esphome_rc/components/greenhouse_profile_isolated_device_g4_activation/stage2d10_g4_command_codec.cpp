#include "stage2d10_g4_command_codec.h"

#include <algorithm>
#include <array>
#include <vector>

#ifdef USE_ESP32
#include "mbedtls/sha256.h"
#ifndef mbedtls_sha256_ret
#define mbedtls_sha256_ret mbedtls_sha256
#endif
#else
#include <openssl/evp.h>
#endif

#include "../greenhouse_pairing_client/secure_pairing_channel.h"

namespace esphome::greenhouse_pairing_client {
namespace {

void secure_clear(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

bool contains_nul(const std::string &value) {
  return std::find(value.begin(), value.end(), '\0') != value.end();
}

}  // namespace

void Stage2D10G4CommandEnvelope::clear() {
  this->action = Stage2D10G4CommandAction::NONE;
  secure_clear(&this->run_suffix);
  this->unlock_token.fill(0);
  this->persistence_key.fill(0);
  secure_clear(&this->authorization_digest);
  secure_clear(&this->candidate_digest);
  secure_clear(&this->active_digest);
  secure_clear(&this->wifi_ssid);
  secure_clear(&this->wifi_password);
  secure_clear(&this->wifi_profile_digest);
  secure_clear(&this->broker_configuration_digest);
  secure_clear(&this->raw_command_sha256);
}

bool Stage2D10G4CommandCodec::parse(
    const std::string &line, const std::string &expected_unlock_digest,
    Stage2D10G4CommandEnvelope *envelope,
    Stage2D10G4CommandFailure *failure) {
  if (envelope == nullptr || failure == nullptr)
    return false;
  envelope->clear();
  *failure = Stage2D10G4CommandFailure::NONE;

  if (line.empty()) {
    fail_(Stage2D10G4CommandFailure::EMPTY, failure);
    return false;
  }
  if (line.size() > MAX_COMMAND_LENGTH) {
    fail_(Stage2D10G4CommandFailure::LENGTH, failure);
    return false;
  }
  if (line.front() == ' ' || line.back() == ' ' ||
      line.find("  ") != std::string::npos ||
      line.find_first_of("\t\r\n") != std::string::npos) {
    fail_(Stage2D10G4CommandFailure::WHITESPACE, failure);
    return false;
  }
  if (!valid_lower_hex_(expected_unlock_digest, 64)) {
    fail_(Stage2D10G4CommandFailure::UNLOCK_DIGEST, failure);
    return false;
  }

  std::array<std::string, 10> fields{};
  size_t field_count = 0;
  if (!split_exact_(line, &fields, &field_count)) {
    fail_(Stage2D10G4CommandFailure::FIELD_COUNT, failure);
    return false;
  }

  bool parsed = false;
  if (fields[0] == ACTIVATE_SCHEMA) {
    parsed = parse_activate_(line, fields.data(), field_count,
                             expected_unlock_digest, envelope, failure);
  } else if (fields[0] == VERIFY_SCHEMA) {
    parsed = parse_verify_(line, fields.data(), field_count,
                           expected_unlock_digest, envelope, failure);
  } else {
    fail_(Stage2D10G4CommandFailure::SCHEMA, failure);
  }

  if (!parsed)
    envelope->clear();
  for (auto &field : fields)
    secure_clear(&field);
  return parsed;
}

bool Stage2D10G4CommandCodec::wifi_profile_digest(
    const std::string &ssid, const std::string &password,
    std::string *digest) {
  if (digest == nullptr || ssid.empty() || ssid.size() > 32 ||
      password.size() < 8 || password.size() > 63 || contains_nul(ssid) ||
      contains_nul(password)) {
    return false;
  }

  static constexpr char PREFIX[] = "gh.stage2d10.wifi/1";
  std::vector<uint8_t> payload;
  payload.reserve(sizeof(PREFIX) - 1 + 1 + ssid.size() + 1 +
                  password.size());
  payload.insert(payload.end(), PREFIX, PREFIX + sizeof(PREFIX) - 1);
  payload.push_back(0);
  payload.insert(payload.end(), ssid.begin(), ssid.end());
  payload.push_back(0);
  payload.insert(payload.end(), password.begin(), password.end());

  std::array<uint8_t, 32> output{};
  const bool success = sha256_(payload.data(), payload.size(), &output);
  std::fill(payload.begin(), payload.end(), 0);
  payload.clear();
  if (!success)
    return false;
  *digest = hex_(output);
  output.fill(0);
  return true;
}

bool Stage2D10G4CommandCodec::command_sha256(const std::string &line,
                                             std::string *digest) {
  if (digest == nullptr || line.empty())
    return false;
  std::array<uint8_t, 32> output{};
  if (!sha256_(reinterpret_cast<const uint8_t *>(line.data()), line.size(),
               &output)) {
    return false;
  }
  *digest = hex_(output);
  output.fill(0);
  return true;
}

const char *Stage2D10G4CommandCodec::action_name(
    Stage2D10G4CommandAction action) {
  switch (action) {
    case Stage2D10G4CommandAction::NONE:
      return "none";
    case Stage2D10G4CommandAction::ACTIVATE_PROFILE:
      return "activate_profile";
    case Stage2D10G4CommandAction::VERIFY_ACTIVE_READ_ONLY:
      return "verify_active_read_only";
  }
  return "unknown";
}

const char *Stage2D10G4CommandCodec::failure_name(
    Stage2D10G4CommandFailure failure) {
  switch (failure) {
    case Stage2D10G4CommandFailure::NONE:
      return "none";
    case Stage2D10G4CommandFailure::EMPTY:
      return "empty";
    case Stage2D10G4CommandFailure::LENGTH:
      return "length";
    case Stage2D10G4CommandFailure::WHITESPACE:
      return "whitespace";
    case Stage2D10G4CommandFailure::SCHEMA:
      return "schema";
    case Stage2D10G4CommandFailure::FIELD_COUNT:
      return "field_count";
    case Stage2D10G4CommandFailure::RUN_SUFFIX:
      return "run_suffix";
    case Stage2D10G4CommandFailure::HEX_SHAPE:
      return "hex_shape";
    case Stage2D10G4CommandFailure::UNLOCK_DIGEST:
      return "unlock_digest";
    case Stage2D10G4CommandFailure::BASE64URL:
      return "base64url";
    case Stage2D10G4CommandFailure::WIFI_LENGTH:
      return "wifi_length";
    case Stage2D10G4CommandFailure::WIFI_DIGEST:
      return "wifi_digest";
    case Stage2D10G4CommandFailure::VERIFY_MODE:
      return "verify_mode";
  }
  return "unknown";
}

bool Stage2D10G4CommandCodec::parse_activate_(
    const std::string &line, const std::string *fields, size_t field_count,
    const std::string &expected_unlock_digest,
    Stage2D10G4CommandEnvelope *envelope,
    Stage2D10G4CommandFailure *failure) {
  if (field_count != 10) {
    fail_(Stage2D10G4CommandFailure::FIELD_COUNT, failure);
    return false;
  }
  if (!valid_run_suffix_(fields[1])) {
    fail_(Stage2D10G4CommandFailure::RUN_SUFFIX, failure);
    return false;
  }
  for (size_t index : {size_t{2}, size_t{3}, size_t{4}, size_t{5},
                       size_t{8}, size_t{9}}) {
    if (!valid_lower_hex_(fields[index], 64)) {
      fail_(Stage2D10G4CommandFailure::HEX_SHAPE, failure);
      return false;
    }
  }

  std::array<uint8_t, 32> unlock{};
  std::array<uint8_t, 32> persistence_key{};
  if (!decode_hex_32_(fields[2], &unlock) ||
      !decode_hex_32_(fields[3], &persistence_key)) {
    fail_(Stage2D10G4CommandFailure::HEX_SHAPE, failure);
    return false;
  }
  std::array<uint8_t, 32> observed_unlock_digest{};
  if (!sha256_(unlock.data(), unlock.size(), &observed_unlock_digest) ||
      !constant_equal_(hex_(observed_unlock_digest),
                       expected_unlock_digest)) {
    unlock.fill(0);
    persistence_key.fill(0);
    observed_unlock_digest.fill(0);
    fail_(Stage2D10G4CommandFailure::UNLOCK_DIGEST, failure);
    return false;
  }
  observed_unlock_digest.fill(0);

  std::vector<uint8_t> ssid_bytes;
  std::vector<uint8_t> password_bytes;
  if (!SecurePairingChannel::decode_base64url(fields[6], &ssid_bytes) ||
      !SecurePairingChannel::decode_base64url(fields[7], &password_bytes)) {
    unlock.fill(0);
    persistence_key.fill(0);
    std::fill(ssid_bytes.begin(), ssid_bytes.end(), 0);
    std::fill(password_bytes.begin(), password_bytes.end(), 0);
    fail_(Stage2D10G4CommandFailure::BASE64URL, failure);
    return false;
  }
  std::string ssid(ssid_bytes.begin(), ssid_bytes.end());
  std::string password(password_bytes.begin(), password_bytes.end());
  std::fill(ssid_bytes.begin(), ssid_bytes.end(), 0);
  std::fill(password_bytes.begin(), password_bytes.end(), 0);
  ssid_bytes.clear();
  password_bytes.clear();
  if (ssid.empty() || ssid.size() > 32 || password.size() < 8 ||
      password.size() > 63 || contains_nul(ssid) || contains_nul(password)) {
    unlock.fill(0);
    persistence_key.fill(0);
    secure_clear(&ssid);
    secure_clear(&password);
    fail_(Stage2D10G4CommandFailure::WIFI_LENGTH, failure);
    return false;
  }

  std::string observed_wifi_digest;
  if (!wifi_profile_digest(ssid, password, &observed_wifi_digest) ||
      !constant_equal_(observed_wifi_digest, fields[8])) {
    unlock.fill(0);
    persistence_key.fill(0);
    secure_clear(&ssid);
    secure_clear(&password);
    secure_clear(&observed_wifi_digest);
    fail_(Stage2D10G4CommandFailure::WIFI_DIGEST, failure);
    return false;
  }
  secure_clear(&observed_wifi_digest);

  std::string raw_digest;
  if (!command_sha256(line, &raw_digest)) {
    unlock.fill(0);
    persistence_key.fill(0);
    secure_clear(&ssid);
    secure_clear(&password);
    fail_(Stage2D10G4CommandFailure::HEX_SHAPE, failure);
    return false;
  }

  envelope->action = Stage2D10G4CommandAction::ACTIVATE_PROFILE;
  envelope->run_suffix = fields[1];
  envelope->unlock_token = unlock;
  envelope->persistence_key = persistence_key;
  envelope->authorization_digest = fields[4];
  envelope->candidate_digest = fields[5];
  envelope->wifi_ssid = std::move(ssid);
  envelope->wifi_password = std::move(password);
  envelope->wifi_profile_digest = fields[8];
  envelope->broker_configuration_digest = fields[9];
  envelope->raw_command_sha256 = std::move(raw_digest);
  unlock.fill(0);
  persistence_key.fill(0);
  *failure = Stage2D10G4CommandFailure::NONE;
  return true;
}

bool Stage2D10G4CommandCodec::parse_verify_(
    const std::string &line, const std::string *fields, size_t field_count,
    const std::string &expected_unlock_digest,
    Stage2D10G4CommandEnvelope *envelope,
    Stage2D10G4CommandFailure *failure) {
  if (field_count != 6) {
    fail_(Stage2D10G4CommandFailure::FIELD_COUNT, failure);
    return false;
  }
  if (!valid_run_suffix_(fields[1])) {
    fail_(Stage2D10G4CommandFailure::RUN_SUFFIX, failure);
    return false;
  }
  for (size_t index : {size_t{2}, size_t{3}, size_t{4}}) {
    if (!valid_lower_hex_(fields[index], 64)) {
      fail_(Stage2D10G4CommandFailure::HEX_SHAPE, failure);
      return false;
    }
  }
  if (fields[5] != "READ_ONLY") {
    fail_(Stage2D10G4CommandFailure::VERIFY_MODE, failure);
    return false;
  }

  std::array<uint8_t, 32> unlock{};
  std::array<uint8_t, 32> persistence_key{};
  if (!decode_hex_32_(fields[2], &unlock) ||
      !decode_hex_32_(fields[3], &persistence_key)) {
    fail_(Stage2D10G4CommandFailure::HEX_SHAPE, failure);
    return false;
  }
  std::array<uint8_t, 32> observed_unlock_digest{};
  if (!sha256_(unlock.data(), unlock.size(), &observed_unlock_digest) ||
      !constant_equal_(hex_(observed_unlock_digest),
                       expected_unlock_digest)) {
    unlock.fill(0);
    persistence_key.fill(0);
    observed_unlock_digest.fill(0);
    fail_(Stage2D10G4CommandFailure::UNLOCK_DIGEST, failure);
    return false;
  }
  observed_unlock_digest.fill(0);

  std::string raw_digest;
  if (!command_sha256(line, &raw_digest)) {
    unlock.fill(0);
    persistence_key.fill(0);
    fail_(Stage2D10G4CommandFailure::HEX_SHAPE, failure);
    return false;
  }

  envelope->action = Stage2D10G4CommandAction::VERIFY_ACTIVE_READ_ONLY;
  envelope->run_suffix = fields[1];
  envelope->unlock_token = unlock;
  envelope->persistence_key = persistence_key;
  envelope->active_digest = fields[4];
  envelope->raw_command_sha256 = std::move(raw_digest);
  unlock.fill(0);
  persistence_key.fill(0);
  *failure = Stage2D10G4CommandFailure::NONE;
  return true;
}

bool Stage2D10G4CommandCodec::split_exact_(
    const std::string &line, std::array<std::string, 10> *fields,
    size_t *field_count) {
  if (fields == nullptr || field_count == nullptr)
    return false;
  *field_count = 0;
  size_t start = 0;
  while (start <= line.size()) {
    if (*field_count >= fields->size())
      return false;
    const size_t delimiter = line.find(' ', start);
    const size_t end = delimiter == std::string::npos ? line.size() : delimiter;
    if (end == start)
      return false;
    (*fields)[(*field_count)++] = line.substr(start, end - start);
    if (delimiter == std::string::npos)
      break;
    start = delimiter + 1;
  }
  return *field_count > 0;
}

bool Stage2D10G4CommandCodec::valid_lower_hex_(
    const std::string &value, size_t length) {
  return value.size() == length &&
         std::all_of(value.begin(), value.end(), [](unsigned char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

bool Stage2D10G4CommandCodec::valid_run_suffix_(
    const std::string &value) {
  return value.size() == 12 &&
         std::all_of(value.begin(), value.end(), [](unsigned char character) {
           return (character >= '0' && character <= '9') ||
                  (character >= 'a' && character <= 'f');
         });
}

bool Stage2D10G4CommandCodec::decode_hex_32_(
    const std::string &value, std::array<uint8_t, 32> *output) {
  if (output == nullptr || !valid_lower_hex_(value, 64))
    return false;
  output->fill(0);
  const auto decode = [](char character) -> uint8_t {
    return character <= '9' ? static_cast<uint8_t>(character - '0')
                            : static_cast<uint8_t>(character - 'a' + 10);
  };
  for (size_t index = 0; index < output->size(); index++) {
    (*output)[index] = static_cast<uint8_t>(
        (decode(value[index * 2]) << 4U) | decode(value[index * 2 + 1]));
  }
  return true;
}

bool Stage2D10G4CommandCodec::sha256_(
    const uint8_t *data, size_t length, std::array<uint8_t, 32> *digest) {
  if (data == nullptr || digest == nullptr)
    return false;
  digest->fill(0);
#ifdef USE_ESP32
  return mbedtls_sha256_ret(data, length, digest->data(), 0) == 0;
#else
  EVP_MD_CTX *context = EVP_MD_CTX_new();
  if (context == nullptr)
    return false;
  unsigned int written = 0;
  const bool success =
      EVP_DigestInit_ex(context, EVP_sha256(), nullptr) == 1 &&
      EVP_DigestUpdate(context, data, length) == 1 &&
      EVP_DigestFinal_ex(context, digest->data(), &written) == 1 &&
      written == digest->size();
  EVP_MD_CTX_free(context);
  if (!success)
    digest->fill(0);
  return success;
#endif
}

std::string Stage2D10G4CommandCodec::hex_(
    const std::array<uint8_t, 32> &value) {
  static constexpr char HEX[] = "0123456789abcdef";
  std::string output(value.size() * 2, '0');
  for (size_t index = 0; index < value.size(); index++) {
    output[index * 2] = HEX[(value[index] >> 4U) & 0x0FU];
    output[index * 2 + 1] = HEX[value[index] & 0x0FU];
  }
  return output;
}

bool Stage2D10G4CommandCodec::constant_equal_(
    const std::string &left, const std::string &right) {
  if (left.size() != right.size())
    return false;
  uint8_t difference = 0;
  for (size_t index = 0; index < left.size(); index++)
    difference |= static_cast<uint8_t>(left[index] ^ right[index]);
  return difference == 0;
}

void Stage2D10G4CommandCodec::fail_(Stage2D10G4CommandFailure value,
                                    Stage2D10G4CommandFailure *failure) {
  if (failure != nullptr)
    *failure = value;
}

}  // namespace esphome::greenhouse_pairing_client
