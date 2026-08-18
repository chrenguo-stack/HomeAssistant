#include "n3w_radio.h"

#ifndef GREENHOUSE_N3W_ENABLE_LEGACY_RADIO

#include <algorithm>
#include <limits>

#include <mbedtls/md.h>

#include "n3w_core.h"

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint8_t kMagic0 = 'G';
constexpr uint8_t kMagic1 = 'H';
constexpr uint8_t kLinkVersion = 1;
constexpr std::size_t kPrefixBytes = 4;

void append_u64(std::vector<uint8_t> *out, uint64_t value) {
  for (int shift = 56; shift >= 0; shift -= 8) {
    out->push_back(static_cast<uint8_t>((value >> shift) & 0xffU));
  }
}

bool read_u64(
    const uint8_t *data,
    std::size_t size,
    std::size_t *offset,
    uint64_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr ||
      *offset + 8 > size) {
    return false;
  }
  uint64_t parsed = 0;
  for (int i = 0; i < 8; ++i) {
    parsed = (parsed << 8U) | data[*offset + i];
  }
  *value = parsed;
  *offset += 8;
  return true;
}

void append_prefix(std::vector<uint8_t> *out, LinkPacketType type) {
  out->push_back(kMagic0);
  out->push_back(kMagic1);
  out->push_back(kLinkVersion);
  out->push_back(static_cast<uint8_t>(type));
}

RadioError validate_prefix(
    const uint8_t *data,
    std::size_t size,
    LinkPacketType expected,
    std::size_t *offset) {
  if (data == nullptr || offset == nullptr || size < kPrefixBytes) {
    return RadioError::PACKET_TRUNCATED;
  }
  if (data[0] != kMagic0 || data[1] != kMagic1 || data[2] != kLinkVersion) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  if (data[3] != static_cast<uint8_t>(expected)) {
    return RadioError::PACKET_TYPE_REJECTED;
  }
  *offset = kPrefixBytes;
  return RadioError::NONE;
}

bool append_identity(std::vector<uint8_t> *out, const std::string &value) {
  if (!valid_identity(value) || value.size() > 255) {
    return false;
  }
  out->push_back(static_cast<uint8_t>(value.size()));
  out->insert(out->end(), value.begin(), value.end());
  return true;
}

bool read_identity(
    const uint8_t *data,
    std::size_t size,
    std::size_t *offset,
    std::string *value) {
  if (data == nullptr || offset == nullptr || value == nullptr ||
      *offset >= size) {
    return false;
  }
  const std::size_t length = data[(*offset)++];
  if (length == 0 || *offset + length > size) {
    return false;
  }
  value->assign(reinterpret_cast<const char *>(data + *offset), length);
  *offset += length;
  return valid_identity(*value);
}

bool constant_time_equal(
    const uint8_t *left,
    const uint8_t *right,
    std::size_t size) {
  if (left == nullptr || right == nullptr) {
    return false;
  }
  uint8_t diff = 0;
  for (std::size_t i = 0; i < size; ++i) {
    diff |= left[i] ^ right[i];
  }
  return diff == 0;
}

RadioError hmac16(
    const LinkKey &key,
    const uint8_t *data,
    std::size_t size,
    std::array<uint8_t, kControlAuthBytes> *auth) {
  if (auth == nullptr || (data == nullptr && size != 0)) {
    return RadioError::INVALID_ARGUMENT;
  }
  const mbedtls_md_info_t *info =
      mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr) {
    return RadioError::AUTH_FAILED;
  }
  static constexpr char kControlContext[] = "gh.n3w-control-v1";
  std::array<uint8_t, 32> control_key{};
  int rc = mbedtls_md_hmac(
      info,
      key.data(),
      key.size(),
      reinterpret_cast<const uint8_t *>(kControlContext),
      sizeof(kControlContext) - 1,
      control_key.data());
  if (rc != 0) {
    return RadioError::AUTH_FAILED;
  }
  std::array<uint8_t, 32> full{};
  rc = mbedtls_md_hmac(
      info,
      control_key.data(),
      control_key.size(),
      data,
      size,
      full.data());
  if (rc != 0) {
    return RadioError::AUTH_FAILED;
  }
  std::copy_n(full.begin(), auth->size(), auth->begin());
  return RadioError::NONE;
}

RadioError append_auth(const LinkKey &key, std::vector<uint8_t> *encoded) {
  if (encoded == nullptr) {
    return RadioError::INVALID_ARGUMENT;
  }
  std::array<uint8_t, kControlAuthBytes> auth{};
  const RadioError err =
      hmac16(key, encoded->data(), encoded->size(), &auth);
  if (err != RadioError::NONE) {
    return err;
  }
  encoded->insert(encoded->end(), auth.begin(), auth.end());
  if (encoded->size() > kEspNowDatagramLimit) {
    return RadioError::PACKET_TOO_LARGE;
  }
  return RadioError::NONE;
}

RadioError verify_auth(
    const LinkKey &key,
    const uint8_t *data,
    std::size_t size,
    std::size_t minimum_without_auth) {
  if (data == nullptr || size < minimum_without_auth + kControlAuthBytes) {
    return RadioError::PACKET_TRUNCATED;
  }
  const std::size_t signed_size = size - kControlAuthBytes;
  std::array<uint8_t, kControlAuthBytes> expected{};
  const RadioError err = hmac16(key, data, signed_size, &expected);
  if (err != RadioError::NONE) {
    return err;
  }
  if (!constant_time_equal(
          expected.data(), data + signed_size, expected.size())) {
    return RadioError::AUTH_FAILED;
  }
  return RadioError::NONE;
}

bool link_key_nonzero(const LinkKey &key) {
  uint8_t aggregate = 0;
  for (uint8_t value : key) {
    aggregate |= value;
  }
  return aggregate != 0;
}

bool valid_unicast_mac(const MacAddress &mac) {
  uint8_t aggregate = 0;
  for (uint8_t value : mac) {
    aggregate |= value;
  }
  return aggregate != 0 && (mac[0] & 0x01U) == 0;
}

}  // namespace

bool valid_radio_channel(uint8_t channel) {
  return channel >= 1 && channel <= 14;
}

bool same_mac(const MacAddress &left, const MacAddress &right) {
  return constant_time_equal(left.data(), right.data(), left.size());
}

bool RelayPeerBinding::valid() const {
  return valid_identity(gateway_id) && valid_unicast_mac(peer_mac) &&
         link_key_nonzero(lmk) &&
         (preferred_channel == 0 ||
          valid_radio_channel(preferred_channel));
}

bool ChildPeerBinding::valid() const {
  return valid_identity(node_id) && valid_unicast_mac(peer_mac) &&
         link_key_nonzero(lmk);
}

RadioError encode_discovery_advertisement(
    const DiscoveryAdvertisement &packet,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !valid_identity(packet.gateway_id) ||
      !valid_radio_channel(packet.channel)) {
    return RadioError::INVALID_ARGUMENT;
  }
  encoded->clear();
  append_prefix(encoded, LinkPacketType::DISCOVERY_ADVERTISEMENT);
  encoded->push_back(packet.channel);
  if (!append_identity(encoded, packet.gateway_id)) {
    encoded->clear();
    return RadioError::INVALID_ARGUMENT;
  }
  if (encoded->size() > kEspNowDatagramLimit) {
    encoded->clear();
    return RadioError::PACKET_TOO_LARGE;
  }
  return RadioError::NONE;
}

RadioError decode_discovery_advertisement(
    const uint8_t *data,
    std::size_t size,
    DiscoveryAdvertisement *packet) {
  if (packet == nullptr || size > kEspNowDatagramLimit) {
    return RadioError::INVALID_ARGUMENT;
  }
  std::size_t offset = 0;
  RadioError err = validate_prefix(
      data, size, LinkPacketType::DISCOVERY_ADVERTISEMENT, &offset);
  if (err != RadioError::NONE) {
    return err;
  }
  if (offset >= size) {
    return RadioError::PACKET_TRUNCATED;
  }
  packet->channel = data[offset++];
  if (!valid_radio_channel(packet->channel) ||
      !read_identity(data, size, &offset, &packet->gateway_id) ||
      offset != size) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  return RadioError::NONE;
}

bool discovery_matches_binding(
    const RelayPeerBinding &binding,
    const MacAddress &source_mac,
    const DiscoveryAdvertisement &packet) {
  if (!binding.valid() || !valid_radio_channel(packet.channel)) {
    return false;
  }
  if (packet.gateway_id != binding.gateway_id ||
      !same_mac(binding.peer_mac, source_mac)) {
    return false;
  }
  return binding.preferred_channel == 0 ||
         binding.preferred_channel == packet.channel;
}

RadioError encode_authenticated_probe(
    const RelayPeerBinding &binding,
    const std::string &node_id,
    uint64_t challenge,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !binding.valid() || !valid_identity(node_id) ||
      challenge == 0) {
    return RadioError::INVALID_ARGUMENT;
  }
  encoded->clear();
  append_prefix(encoded, LinkPacketType::PROBE);
  append_u64(encoded, challenge);
  if (!append_identity(encoded, binding.gateway_id) ||
      !append_identity(encoded, node_id)) {
    encoded->clear();
    return RadioError::INVALID_ARGUMENT;
  }
  return append_auth(binding.lmk, encoded);
}

RadioError decode_authenticated_probe(
    const uint8_t *data,
    std::size_t size,
    const std::string &expected_gateway_id,
    const ChildPeerBinding &binding,
    ProbePacket *packet) {
  if (packet == nullptr || !binding.valid() ||
      !valid_identity(expected_gateway_id) ||
      size > kEspNowDatagramLimit) {
    return RadioError::INVALID_ARGUMENT;
  }
  RadioError err =
      verify_auth(binding.lmk, data, size, kPrefixBytes + 8 + 2);
  if (err != RadioError::NONE) {
    return err;
  }
  const std::size_t signed_size = size - kControlAuthBytes;
  std::size_t offset = 0;
  err = validate_prefix(
      data, signed_size, LinkPacketType::PROBE, &offset);
  if (err != RadioError::NONE) {
    return err;
  }
  if (!read_u64(data, signed_size, &offset, &packet->challenge) ||
      !read_identity(
          data, signed_size, &offset, &packet->gateway_id) ||
      !read_identity(
          data, signed_size, &offset, &packet->node_id) ||
      offset != signed_size || packet->challenge == 0) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  if (packet->gateway_id != expected_gateway_id ||
      packet->node_id != binding.node_id) {
    return RadioError::BINDING_MISMATCH;
  }
  return RadioError::NONE;
}

RadioError encode_authenticated_probe_ack(
    const LinkKey &lmk,
    uint64_t challenge,
    bool accepted,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !link_key_nonzero(lmk) ||
      challenge == 0) {
    return RadioError::INVALID_ARGUMENT;
  }
  encoded->clear();
  append_prefix(encoded, LinkPacketType::PROBE_ACK);
  append_u64(encoded, challenge);
  encoded->push_back(accepted ? 1 : 0);
  return append_auth(lmk, encoded);
}

RadioError decode_authenticated_probe_ack(
    const uint8_t *data,
    std::size_t size,
    const LinkKey &lmk,
    ProbeAckPacket *packet) {
  if (packet == nullptr || !link_key_nonzero(lmk) ||
      size > kEspNowDatagramLimit) {
    return RadioError::INVALID_ARGUMENT;
  }
  RadioError err =
      verify_auth(lmk, data, size, kPrefixBytes + 8 + 1);
  if (err != RadioError::NONE) {
    return err;
  }
  const std::size_t signed_size = size - kControlAuthBytes;
  std::size_t offset = 0;
  err = validate_prefix(
      data, signed_size, LinkPacketType::PROBE_ACK, &offset);
  if (err != RadioError::NONE) {
    return err;
  }
  if (!read_u64(
          data, signed_size, &offset, &packet->challenge) ||
      offset >= signed_size) {
    return RadioError::PACKET_TRUNCATED;
  }
  const uint8_t accepted = data[offset++];
  if ((accepted != 0 && accepted != 1) ||
      offset != signed_size || packet->challenge == 0) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  packet->accepted = accepted == 1;
  return RadioError::NONE;
}

RadioError ChannelScanPlan::configure(
    uint8_t last_direct_channel,
    const std::vector<uint8_t> &allowed_channels) {
  channels_.clear();
  index_ = 0;
  auto append_unique = [this](uint8_t channel) {
    if (std::find(
            channels_.begin(), channels_.end(), channel) ==
        channels_.end()) {
      channels_.push_back(channel);
    }
  };
  if (last_direct_channel != 0) {
    if (!valid_radio_channel(last_direct_channel)) {
      return RadioError::CHANNEL_REJECTED;
    }
    append_unique(last_direct_channel);
  }
  for (uint8_t channel : allowed_channels) {
    if (!valid_radio_channel(channel)) {
      channels_.clear();
      return RadioError::CHANNEL_REJECTED;
    }
    append_unique(channel);
  }
  if (channels_.empty()) {
    return RadioError::INVALID_ARGUMENT;
  }
  return RadioError::NONE;
}

uint8_t ChannelScanPlan::current() const {
  if (channels_.empty()) {
    return 0;
  }
  return channels_[index_];
}

uint8_t ChannelScanPlan::advance() {
  if (channels_.empty()) {
    return 0;
  }
  index_ = (index_ + 1) % channels_.size();
  return channels_[index_];
}

bool LocalPathPolicy::valid() const {
  return direct_failures_to_discovery > 0 &&
         direct_recoveries_to_direct > 0 &&
         relay_failures_to_discovery > 0;
}

RadioError LocalPathController::note_direct_result(bool success) {
  if (!policy_.valid() || state_ != LocalPathState::DIRECT) {
    return RadioError::INVALID_ARGUMENT;
  }
  if (success) {
    direct_failures_ = 0;
    return RadioError::NONE;
  }
  if (direct_failures_ < std::numeric_limits<uint8_t>::max()) {
    ++direct_failures_;
  }
  if (direct_failures_ >= policy_.direct_failures_to_discovery) {
    state_ = LocalPathState::DISCOVERY;
    direct_failures_ = 0;
  }
  return RadioError::NONE;
}

RadioError LocalPathController::note_authenticated_relay_ready(bool ready) {
  if (!policy_.valid() || state_ != LocalPathState::DISCOVERY) {
    return RadioError::INVALID_ARGUMENT;
  }
  if (ready) {
    state_ = LocalPathState::RELAY_ACTIVE;
    relay_failures_ = 0;
    direct_recoveries_ = 0;
  }
  return RadioError::NONE;
}

RadioError LocalPathController::note_relay_result(bool success) {
  if (!policy_.valid() || state_ != LocalPathState::RELAY_ACTIVE) {
    return RadioError::INVALID_ARGUMENT;
  }
  if (success) {
    relay_failures_ = 0;
    return RadioError::NONE;
  }
  if (relay_failures_ < std::numeric_limits<uint8_t>::max()) {
    ++relay_failures_;
  }
  if (relay_failures_ >= policy_.relay_failures_to_discovery) {
    state_ = LocalPathState::DISCOVERY;
    relay_failures_ = 0;
    direct_recoveries_ = 0;
  }
  return RadioError::NONE;
}

RadioError LocalPathController::note_direct_recovery_probe(bool success) {
  if (!policy_.valid() ||
      (state_ != LocalPathState::RELAY_ACTIVE &&
       state_ != LocalPathState::DISCOVERY)) {
    return RadioError::INVALID_ARGUMENT;
  }
  if (!success) {
    direct_recoveries_ = 0;
    return RadioError::NONE;
  }
  if (direct_recoveries_ < std::numeric_limits<uint8_t>::max()) {
    ++direct_recoveries_;
  }
  if (direct_recoveries_ >= policy_.direct_recoveries_to_direct) {
    state_ = LocalPathState::DIRECT;
    direct_recoveries_ = 0;
    relay_failures_ = 0;
  }
  return RadioError::NONE;
}

}  // namespace esphome::greenhouse_n3w_core

#endif  // GREENHOUSE_N3W_ENABLE_LEGACY_RADIO
