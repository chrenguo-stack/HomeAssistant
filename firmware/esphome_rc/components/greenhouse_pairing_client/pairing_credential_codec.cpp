#include "pairing_credential_codec.h"

#include <algorithm>
#include <array>
#include <limits>
#include <string>

namespace esphome::greenhouse_pairing_client {
namespace {

constexpr std::array<uint8_t, 4> PAYLOAD_MAGIC = {'G', 'H', 'C', '1'};
constexpr uint16_t LEGACY_FIELD_COUNT = 9;
constexpr uint16_t PRODUCT_FIELD_COUNT = 10;

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

void wipe_string(std::string *value) {
  if (value == nullptr)
    return;
  std::fill(value->begin(), value->end(), '\0');
  value->clear();
  value->shrink_to_fit();
}

void wipe_fields(std::array<std::string, PRODUCT_FIELD_COUNT> *fields) {
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

  const bool product = bundle.has_n3w_credentials();
  const uint16_t version = product
                               ? PERSISTED_CREDENTIAL_PAYLOAD_VERSION_PRODUCT
                               : PERSISTED_CREDENTIAL_PAYLOAD_VERSION_LEGACY;
  const uint16_t field_count = product ? PRODUCT_FIELD_COUNT : LEGACY_FIELD_COUNT;

  output->reserve(96 + bundle.ca_pem.size() + bundle.mqtt_password.size() +
                  bundle.n3w_application_key.size());
  output->insert(output->end(), PAYLOAD_MAGIC.begin(), PAYLOAD_MAGIC.end());
  put_u16(output, version);
  put_u16(output, field_count);
  put_u32(output, bundle.credential_generation);
  put_u16(output, bundle.broker_port);
  if (product)
    put_u32(output, bundle.n3w_key_epoch);

  const std::array<const std::string *, PRODUCT_FIELD_COUNT> fields = {
      &bundle.schema,
      &bundle.system_id,
      &bundle.node_id,
      &bundle.broker_host,
      &bundle.broker_tls_server_name,
      &bundle.ca_pem,
      &bundle.mqtt_username,
      &bundle.mqtt_client_id,
      &bundle.mqtt_password,
      &bundle.n3w_application_key,
  };
  for (uint16_t index = 0; index < field_count; ++index) {
    if (!put_string(output, *fields[index])) {
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
      !take_u16(input, &offset, &broker_port))
    return false;

  const bool legacy =
      version == PERSISTED_CREDENTIAL_PAYLOAD_VERSION_LEGACY &&
      field_count == LEGACY_FIELD_COUNT;
  const bool product =
      version == PERSISTED_CREDENTIAL_PAYLOAD_VERSION_PRODUCT &&
      field_count == PRODUCT_FIELD_COUNT;
  if (!legacy && !product)
    return false;

  uint32_t n3w_key_epoch = 0;
  if (product && !take_u32(input, &offset, &n3w_key_epoch))
    return false;

  std::array<std::string, PRODUCT_FIELD_COUNT> fields;
  const std::array<size_t, PRODUCT_FIELD_COUNT> maximums = {
      64, 128, 128, 253, 253, 8192, 128, 128, 512, 64};
  bool success = true;
  for (uint16_t index = 0; index < field_count; ++index) {
    if (!take_string(input, &offset, maximums[index], &fields[index])) {
      success = false;
      break;
    }
  }
  success = success && offset == input.size();
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
  if (product) {
    output->n3w_key_epoch = n3w_key_epoch;
    output->n3w_application_key = fields[9];
  }
  wipe_fields(&fields);
  if (!output->valid() || (product && !output->has_n3w_credentials())) {
    output->clear();
    return false;
  }
  return true;
}

}  // namespace esphome::greenhouse_pairing_client
