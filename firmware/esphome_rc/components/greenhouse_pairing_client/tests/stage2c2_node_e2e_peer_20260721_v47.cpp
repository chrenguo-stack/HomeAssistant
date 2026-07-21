#include <array>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

#include <openssl/evp.h>
#include <openssl/hmac.h>

#include "pairing_ram_credentials.h"
#include "pairing_network_transport.h"
#include "secure_pairing_channel.h"

using namespace esphome::greenhouse_pairing_client;

namespace {

std::vector<std::string> split_tabs(const std::string &line) {
  std::vector<std::string> fields;
  size_t start = 0;
  while (true) {
    const size_t stop = line.find('\t', start);
    fields.push_back(line.substr(start, stop == std::string::npos ? stop : stop - start));
    if (stop == std::string::npos)
      break;
    start = stop + 1;
  }
  return fields;
}

bool decode_hex4(const std::string &text, size_t offset, char *output) {
  if (output == nullptr || offset + 4 > text.size())
    return false;
  unsigned value = 0;
  for (size_t index = 0; index < 4; index++) {
    const char c = text[offset + index];
    value <<= 4;
    if (c >= '0' && c <= '9')
      value |= static_cast<unsigned>(c - '0');
    else if (c >= 'a' && c <= 'f')
      value |= static_cast<unsigned>(c - 'a' + 10);
    else if (c >= 'A' && c <= 'F')
      value |= static_cast<unsigned>(c - 'A' + 10);
    else
      return false;
  }
  if (value > 0x7f)
    return false;
  *output = static_cast<char>(value);
  return true;
}

std::optional<std::string> json_string(const std::string &json, const std::string &key) {
  const std::string marker = "\"" + key + "\":";
  size_t position = json.find(marker);
  if (position == std::string::npos)
    return std::nullopt;
  position += marker.size();
  if (position >= json.size() || json[position] != '"')
    return std::nullopt;
  position++;
  std::string output;
  while (position < json.size()) {
    const char value = json[position++];
    if (value == '"')
      return output;
    if (value != '\\') {
      if (static_cast<unsigned char>(value) < 0x20)
        return std::nullopt;
      output += value;
      continue;
    }
    if (position >= json.size())
      return std::nullopt;
    const char escape = json[position++];
    switch (escape) {
      case '"': output += '"'; break;
      case '\\': output += '\\'; break;
      case '/': output += '/'; break;
      case 'b': output += '\b'; break;
      case 'f': output += '\f'; break;
      case 'n': output += '\n'; break;
      case 'r': output += '\r'; break;
      case 't': output += '\t'; break;
      case 'u': {
        char decoded = 0;
        if (!decode_hex4(json, position, &decoded))
          return std::nullopt;
        position += 4;
        output += decoded;
        break;
      }
      default:
        return std::nullopt;
    }
  }
  return std::nullopt;
}

std::optional<uint32_t> json_uint32(const std::string &json, const std::string &key) {
  const std::string marker = "\"" + key + "\":";
  size_t position = json.find(marker);
  if (position == std::string::npos)
    return std::nullopt;
  position += marker.size();
  if (position >= json.size() || !std::isdigit(static_cast<unsigned char>(json[position])))
    return std::nullopt;
  uint64_t value = 0;
  while (position < json.size() && std::isdigit(static_cast<unsigned char>(json[position]))) {
    value = value * 10 + static_cast<unsigned>(json[position++] - '0');
    if (value > UINT32_MAX)
      return std::nullopt;
  }
  return static_cast<uint32_t>(value);
}

bool parse_credentials(const std::string &json, RamCredentialBundle *output) {
  if (output == nullptr)
    return false;
  auto schema = json_string(json, "schema");
  auto system_id = json_string(json, "system_id");
  auto node_id = json_string(json, "node_id");
  auto broker_host = json_string(json, "broker_host");
  auto broker_port = json_uint32(json, "broker_port");
  auto broker_tls_server_name = json_string(json, "broker_tls_server_name");
  auto ca_pem = json_string(json, "ca_pem");
  auto mqtt_username = json_string(json, "mqtt_username");
  auto mqtt_client_id = json_string(json, "mqtt_client_id");
  auto generation = json_uint32(json, "credential_generation");
  auto mqtt_password = json_string(json, "mqtt_password");
  if (!schema || !system_id || !node_id || !broker_host || !broker_port ||
      *broker_port > UINT16_MAX || !broker_tls_server_name || !ca_pem || !mqtt_username ||
      !mqtt_client_id || !generation || !mqtt_password)
    return false;
  RamCredentialBundle candidate{
      .schema = *schema,
      .system_id = *system_id,
      .node_id = *node_id,
      .broker_host = *broker_host,
      .broker_port = static_cast<uint16_t>(*broker_port),
      .broker_tls_server_name = *broker_tls_server_name,
      .ca_pem = *ca_pem,
      .mqtt_username = *mqtt_username,
      .mqtt_client_id = *mqtt_client_id,
      .credential_generation = *generation,
      .mqtt_password = *mqtt_password,
  };
  if (!candidate.valid()) {
    candidate.clear();
    return false;
  }
  *output = std::move(candidate);
  return true;
}

std::string claim_proof(const std::string &pairing_secret, const std::string &manager_id,
                        const std::string &hardware_id, const std::string &pairing_id) {
  std::array<uint8_t, 32> secret{};
  if (!SecurePairingChannel::decode_base64url_32(pairing_secret, &secret))
    return {};
  const std::string transcript = "gh.pair.claim/1\n" + manager_id + "\n" + hardware_id +
                                 "\n" + pairing_id;
  std::array<uint8_t, 32> digest{};
  unsigned int written = 0;
  const bool success = HMAC(EVP_sha256(), secret.data(), static_cast<int>(secret.size()),
                            reinterpret_cast<const unsigned char *>(transcript.data()),
                            transcript.size(), digest.data(), &written) != nullptr &&
                       written == digest.size();
  std::fill(secret.begin(), secret.end(), 0);
  std::string output;
  if (!success || !SecurePairingChannel::encode_base64url(digest.data(), digest.size(), &output))
    output.clear();
  std::fill(digest.begin(), digest.end(), 0);
  return output;
}

}  // namespace

int main() {
  std::string pairing_secret;
  std::string hardware_id;
  std::string pairing_id;
  SecurePairingChannel channel;
  RamCredentialBundle credentials;

  std::string line;
  while (std::getline(std::cin, line)) {
    const auto fields = split_tabs(line);
    if (fields.empty())
      return 2;
    if (fields[0] == "INIT" && fields.size() == 5) {
      const std::string &manager_id = fields[1];
      hardware_id = fields[2];
      pairing_id = fields[3];
      pairing_secret = fields[4];
      const std::string proof = claim_proof(pairing_secret, manager_id, hardware_id, pairing_id);
      if (proof.empty())
        return 3;
      std::cout << "CLAIM\t{\"claim_proof\":\"" << proof
                << "\",\"hardware_id\":\"" << hardware_id
                << "\",\"manager_id\":\"" << manager_id
                << "\",\"pairing_id\":\"" << pairing_id
                << "\",\"schema\":\"gh.pair.claim/1\"}" << std::endl;
      continue;
    }
    if (fields[0] == "OFFER" && fields.size() == 10) {
      SecureOfferDocument offer{
          .schema = fields[1],
          .session_id = fields[2],
          .hardware_id = fields[3],
          .pairing_id = fields[4],
          .manager_nonce = fields[5],
          .manager_public_key = fields[6],
          .cipher_suite = fields[7],
          .expires_at = fields[8],
          .max_proof_attempts = static_cast<uint8_t>(std::stoul(fields[9])),
      };
      if (offer.hardware_id != hardware_id || offer.pairing_id != pairing_id ||
          !channel.establish(offer, pairing_secret))
        return 4;
      std::fill(pairing_secret.begin(), pairing_secret.end(), '\0');
      pairing_secret.clear();
      std::cout << "ESTABLISH\t" << channel.build_establish_request_json() << std::endl;
      continue;
    }
    if (fields[0] == "CREDENTIALS" && fields.size() == 8) {
      SecureEnvelopeDocument envelope{
          .schema = fields[1],
          .session_id = fields[2],
          .direction = fields[3],
          .sequence = std::stoull(fields[4]),
          .content_type = fields[5],
          .nonce = fields[6],
          .ciphertext = fields[7],
      };
      std::string plaintext;
      if (!channel.decrypt(envelope, CREDENTIALS_CONTENT_TYPE, &plaintext) ||
          !parse_credentials(plaintext, &credentials))
        return 5;
      std::fill(plaintext.begin(), plaintext.end(), '\0');
      plaintext.clear();
      SecureEnvelopeDocument ack;
      if (!channel.encrypt(credentials.delivery_ack_json(), ACK_CONTENT_TYPE, &ack))
        return 6;
      std::cout << "ACK\t" << PairingNetworkTransport::envelope_json(ack) << std::endl;
      continue;
    }
    if (fields[0] == "COMMIT" && fields.size() == 3) {
      const uint32_t generation = static_cast<uint32_t>(std::stoul(fields[2]));
      if (!credentials.valid() || credentials.node_id != fields[1] ||
          credentials.credential_generation != generation || !pairing_secret.empty())
        return 7;
      std::cout << "COMMITTED\t" << credentials.node_id << "\t"
                << credentials.credential_generation << "\tRAM_ONLY" << std::endl;
      credentials.clear();
      channel.clear();
      continue;
    }
    return 8;
  }
  return 0;
}
