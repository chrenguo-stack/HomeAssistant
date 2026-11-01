#include "pairing_credential_codec.h"

#include <algorithm>
#include <array>
#include <limits>
#include <string>

#include "pairing_client_core.h"
#include "secure_pairing_channel.h"

namespace esphome::greenhouse_pairing_client {
namespace {

constexpr std::array<uint8_t, 4> PAYLOAD_MAGIC = {'G', 'H', 'C', '1'};
constexpr uint16_t FIELD_COUNT = 9;

void put_u16(std::vector<uint8_t> *output, uint16_t value) {
  output->push_back(static_cast<uint8_t>((value >> 8) & 0xffU));
  output->push_back(static_cast<uint8_t>(value & 0xffU));
}

void put_u32(std::vector<uint8_t> *output, uint32_t value) {
  output->push_back(static_cast<uint8_t>((value >> 24) & 0xffU));
  output->push_back(static_cast<uint8_t>((value >> 16) & 0xffU));
  output->push_back(static_cast<uint8_t>((value >> 8) & 0xffU));
  output->push_back(static_cast<uint8_t>(value & 0xffU));
}

bool take_u16(const std::vector<uint8_t> &input, size_t *offset,
              uint16_t *value) {
  if (offset == nullptr || value == nullptr || *offset > input.size() ||
      input.size() - *offset < 2)
    return false;
  *value = static_cast<uint16_t>(
      (static_cast<uint16_t>(input[*offset]) << 8) |
      static_cast<uint16_t>(input[*offset + 1]));
  *offset += 2;
  return true;
}

bool take_u32(const std::vector<uint8_t> &input, size_t *offset,
              uint32_t *value) {
  if (offset == nullptr || value == nullptr || *offset > input.size() ||
      input.size() - *offset < 4)
    return false;
  *value = (static_cast<uint32_t>(input[*offset]) << 24) |
           (static_cast<uint32_t>(input[*offset + 1]) << 16) |
           (static_cast<uint32_t>(input[*offset + 2]) << 8) |
           static_cast<uint32_t>(input[*offset + 3]);
  *offset += 4;
  return true;
}

bool put_string(std::vector<uint8_t> *output, const std::string &value) {
  if (output == nullptr ||
      value.size() > std::numeric_limits<uint16_t>::max())
    return false;
  put_u16(output, static_cast<uint16_t>(value.size()));
  output->insert(output->end(), value.begin(), value.end());
  return true;
}

bool take_string(const std::vector<uint8_t> &input, size_t *offset,
                 size_t maximum, std::string *value) {
  uint16_t length = 0;
  if (value == nullptr || !take_u16(input, offset, &length) ||
      length > maximum || *offset > input.size() ||
      input.size() - *offset < length)
    return false;
  value->assign(reinterpret_cast<const char *>(input.data() + *offset),
                length);
  *offset += length;
  return value->find('\0') == std::string::npos;
}

bool validate_values(const std::array<std::string, FIELD_COUNT> &fields,
                     uint16_t broker_port, uint32_t generation) {
  return fields[0] == CREDENTIALS_CONTENT_TYPE &&
         PairingClientCore::valid_identifier(fields[1]) &&
         PairingClientCore::valid_identifier(fields[2]) &&
         PairingClientCore::valid_local_host(fields[3]) && broker_port != 0 &&
         PairingClientCore::valid_local_host(fields[4]) &&
         !fields[5].empty() && fields[5].size() <= 8192 &&
         PairingClientCore::valid_identifier(fields[6]) &&
         PairingClientCore::valid_identifier(fields[7]) && generation != 0 &&
         !fields[8].empty() && fields[8].size() <= 512;
}

void wipe_string(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

void wipe_fields(std::array<std::string, FIELD_COUNT> *fields) {
  if (fields == nullptr)
    return;
  for (auto &field : *fields)
    wipe_string(&field);
}

void wipe_vector(std::vector<uint8_t> *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), 0);
  value->clear();
  value->shrink_to_fit();
}

}  // namespace

bool PairingCredentialCodec::encode(const RamCredentialBundle &bundle,
                                    std::vector<uint8_t> *output) {
  if (output == nullptr)
    return false;
  wipe_vector(output);
  if (!bundle.valid())
    return false;

  output->reserve(64 + bundle.ca_pem.size() + bundle.mqtt_password.size());
  output->insert(output->end(), PAYLOAD_MAGIC.begin(), PAYLOAD_MAGIC.end());
  put_u16(output, PERSISTED_CREDENTIAL_PAYLOAD_VERSION);
  put_u16(output, FIELD_COUNT);
  put_u32(output, bundle.credential_generation);
  put_u16(output, bundle.broker_port);

  const std::array<const std::string *, FIELD_COUNT> fields = {
      &bundle.schema,       &bundle.system_id,
      &bundle.node_id,      &bundle.broker_host,
      &bundle.broker_tls_server_name,
      &bundle.ca_pem,       &bundle.mqtt_username,
      &bundle.mqtt_client_id,
      &bundle.mqtt_password,
  };
  for (const std::string *field : fields) {
    if (field == nullptr || !put_string(output, *field)) {
      wipe_vector(output);
      return false;
    }
  }
  if (output->size() > PERSISTED_CREDENTIAL_MAX_BYTES) {
    wipe_vector(output);
    return false;
  }
  return true;
}

bool PairingCredentialCodec::decode(const std::vector<uint8_t> &input,
                                    RamCredentialBundle *output) {
  if (output == nullptr)
    return false;
  output->clear();
  if (input.size() < 32 || input.size() > PERSISTED_CREDENTIAL_MAX_BYTES ||
      !std::equal(PAYLOAD_MAGIC.begin(), PAYLOAD_MAGIC.end(), input.begin()))
    return false;

  size_t offset = PAYLOAD_MAGIC.size();
  uint16_t version = 0;
  uint16_t field_count = 0;
  uint32_t generation = 0;
  uint16_t broker_port = 0;
  if (!take_u16(input, &offset, &version) ||
      !take_u16(input, &offset, &field_count) ||
      !take_u32(input, &offset, &generation) ||
      !take_u16(input, &offset, &broker_port) ||
      version != PERSISTED_CREDENTIAL_PAYLOAD_VERSION ||
      field_count != FIELD_COUNT)
    return false;

  std::array<std::string, FIELD_COUNT> fields;
  const std::array<size_t, FIELD_COUNT> maximums = {
      64, 128, 128, 253, 253, 8192, 128, 128, 512};
  bool success = true;
  for (size_t index = 0; index < fields.size(); index++) {
    if (!take_string(input, &offset, maximums[index], &fields[index])) {
      success = false;
      break;
    }
  }
  success = success && offset == input.size() &&
            validate_values(fields, broker_port, generation);
  if (!success) {
    wipe_fields(&fields);
    return false;
  }

  output->schema = fields[0];
  output->system_id = fields[1];
  output->node_id = fields[2];
  output->broker_host = fields[3];
  output->broker_port = broker_port;
  output->broker_tls_server_name = fields[4];
  output->ca_pem = fields[5];
  output->mqtt_username = fields[6];
  output->mqtt_client_id = fields[7];
  output->credential_generation = generation;
  output->mqtt_password = fields[8];
  wipe_fields(&fields);
  if (!output->valid()) {
    output->clear();
    return false;
  }
  return true;
}

}  // namespace esphome::greenhouse_pairing_client
