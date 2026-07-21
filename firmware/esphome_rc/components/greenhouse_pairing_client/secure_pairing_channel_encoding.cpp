#include "secure_pairing_channel.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdio>

#include "pairing_client_core.h"

#ifdef USE_ESP32
#include "mbedtls/base64.h"
#else
#include <openssl/evp.h>
#endif

namespace esphome::greenhouse_pairing_client {

std::string SecurePairingChannel::json_escape(const std::string &value) {
  std::string escaped;
  escaped.reserve(value.size() + 8);
  static constexpr char HEX[] = "0123456789abcdef";
  for (const char character : value) {
    const auto byte = static_cast<unsigned char>(character);
    switch (character) {
      case '\\':
        escaped += "\\\\";
        break;
      case '"':
        escaped += "\\\"";
        break;
      case '\b':
        escaped += "\\b";
        break;
      case '\f':
        escaped += "\\f";
        break;
      case '\n':
        escaped += "\\n";
        break;
      case '\r':
        escaped += "\\r";
        break;
      case '\t':
        escaped += "\\t";
        break;
      default:
        if (byte < 0x20U) {
          escaped += "\\u00";
          escaped += HEX[(byte >> 4U) & 0x0FU];
          escaped += HEX[byte & 0x0FU];
        } else {
          escaped += character;
        }
    }
  }
  return escaped;
}

bool SecurePairingChannel::encode_base64url(const uint8_t *data, size_t length,
                                            std::string *output) {
  if (output == nullptr)
    return false;
  zeroize_(output->data(), output->size());
  output->clear();
  if (data == nullptr)
    return false;

  std::vector<unsigned char> encoded(4 * ((length + 2) / 3) + 1, 0);
#ifdef USE_ESP32
  size_t written = 0;
  const bool success =
      mbedtls_base64_encode(encoded.data(), encoded.size(), &written, data, length) == 0;
#else
  const int encoded_length = EVP_EncodeBlock(encoded.data(), data, static_cast<int>(length));
  const bool success = encoded_length >= 0;
  const size_t written = success ? static_cast<size_t>(encoded_length) : 0;
#endif
  if (!success) {
    zeroize_(encoded.data(), encoded.size());
    return false;
  }

  std::string value(reinterpret_cast<const char *>(encoded.data()), written);
  zeroize_(encoded.data(), encoded.size());
  while (!value.empty() && value.back() == '=')
    value.pop_back();
  for (char &character : value) {
    if (character == '+')
      character = '-';
    else if (character == '/')
      character = '_';
  }
  *output = value;
  zeroize_(value.data(), value.size());
  value.clear();
  return true;
}

bool SecurePairingChannel::decode_base64url(const std::string &value,
                                            std::vector<uint8_t> *output) {
  if (output == nullptr)
    return false;
  zeroize_(output->data(), output->size());
  output->clear();
  if (value.empty() || value.size() % 4 == 1)
    return false;
  for (const char character : value) {
    if (!(std::isalnum(static_cast<unsigned char>(character)) || character == '-' ||
          character == '_'))
      return false;
  }

  std::string normalized = value;
  for (char &character : normalized) {
    if (character == '-')
      character = '+';
    else if (character == '_')
      character = '/';
  }
  while (normalized.size() % 4 != 0)
    normalized.push_back('=');
  std::vector<uint8_t> decoded((normalized.size() / 4) * 3 + 1, 0);
#ifdef USE_ESP32
  size_t written = 0;
  const bool success =
      mbedtls_base64_decode(decoded.data(), decoded.size(), &written,
                            reinterpret_cast<const unsigned char *>(normalized.data()),
                            normalized.size()) == 0;
#else
  const int decoded_length =
      EVP_DecodeBlock(decoded.data(),
                      reinterpret_cast<const unsigned char *>(normalized.data()),
                      static_cast<int>(normalized.size()));
  bool success = decoded_length >= 0;
  size_t written = success ? static_cast<size_t>(decoded_length) : 0;
  if (success && !normalized.empty() && normalized.back() == '=')
    written--;
  if (success && normalized.size() > 1 && normalized[normalized.size() - 2] == '=')
    written--;
#endif
  zeroize_(normalized.data(), normalized.size());
  normalized.clear();
  if (!success) {
    zeroize_(decoded.data(), decoded.size());
    return false;
  }
  decoded.resize(written);

  std::string canonical;
  const bool canonical_valid = encode_base64url(decoded.data(), decoded.size(), &canonical) &&
                               canonical == value;
  zeroize_(canonical.data(), canonical.size());
  canonical.clear();
  if (!canonical_valid) {
    zeroize_(decoded.data(), decoded.size());
    decoded.clear();
    return false;
  }

  *output = std::move(decoded);
  return true;
}

bool SecurePairingChannel::decode_base64url_32(const std::string &value,
                                               std::array<uint8_t, 32> *output) {
  if (output == nullptr || !PairingClientCore::valid_base64url_32(value))
    return false;
  std::vector<uint8_t> decoded;
  if (!decode_base64url(value, &decoded) || decoded.size() != output->size()) {
    zeroize_(decoded.data(), decoded.size());
    return false;
  }
  std::copy(decoded.begin(), decoded.end(), output->begin());
  zeroize_(decoded.data(), decoded.size());
  return true;
}

}  // namespace esphome::greenhouse_pairing_client
