#include "n3w_radio.h"

#include <algorithm>
#include <cstring>

#include <mbedtls/md.h>

namespace esphome::greenhouse_n3w_core {
namespace {

constexpr uint8_t kMagic0 = 'G';
constexpr uint8_t kMagic1 = 'H';
constexpr uint8_t kLinkVersion = 1;
constexpr std::size_t kPrefixBytes = 4;
constexpr std::size_t kDataHeaderBytes = 54;

void append_u16(std::vector<uint8_t> *out, uint16_t value) {
  out->push_back(static_cast<uint8_t>((value >> 8U) & 0xffU));
  out->push_back(static_cast<uint8_t>(value & 0xffU));
}

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

bool read_u16(const uint8_t *data, std::size_t size, std::size_t *offset, uint16_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr || *offset + 2 > size) {
    return false;
  }
  *value = static_cast<uint16_t>(data[*offset]) << 8U;
  *value |= static_cast<uint16_t>(data[*offset + 1]);
  *offset += 2;
  return true;
}

bool read_u32(const uint8_t *data, std::size_t size, std::size_t *offset, uint32_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr || *offset + 4 > size) {
    return false;
  }
  uint32_t parsed = 0;
  for (int i = 0; i < 4; ++i) {
    parsed = (parsed << 8U) | data[*offset + i];
  }
  *value = parsed;
  *offset += 4;
  return true;
}

bool read_u64(const uint8_t *data, std::size_t size, std::size_t *offset, uint64_t *value) {
  if (data == nullptr || offset == nullptr || value == nullptr || *offset + 8 > size) {
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
  if (data == nullptr || offset == nullptr || value == nullptr || *offset >= size) {
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

bool constant_time_equal(const uint8_t *left, const uint8_t *right, std::size_t size) {
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
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
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
  const RadioError err = hmac16(key, encoded->data(), encoded->size(), &auth);
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
  if (!constant_time_equal(expected.data(), data + signed_size, expected.size())) {
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
         (preferred_channel == 0 || valid_radio_channel(preferred_channel));
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
      !valid_identity(expected_gateway_id) || size > kEspNowDatagramLimit) {
    return RadioError::INVALID_ARGUMENT;
  }
  RadioError err = verify_auth(binding.lmk, data, size, kPrefixBytes + 8 + 2);
  if (err != RadioError::NONE) {
    return err;
  }
  const std::size_t signed_size = size - kControlAuthBytes;
  std::size_t offset = 0;
  err = validate_prefix(data, signed_size, LinkPacketType::PROBE, &offset);
  if (err != RadioError::NONE) {
    return err;
  }
  if (!read_u64(data, signed_size, &offset, &packet->challenge) ||
      !read_identity(data, signed_size, &offset, &packet->gateway_id) ||
      !read_identity(data, signed_size, &offset, &packet->node_id) ||
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
  if (encoded == nullptr || !link_key_nonzero(lmk) || challenge == 0) {
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
  RadioError err = verify_auth(lmk, data, size, kPrefixBytes + 8 + 1);
  if (err != RadioError::NONE) {
    return err;
  }
  const std::size_t signed_size = size - kControlAuthBytes;
  std::size_t offset = 0;
  err = validate_prefix(data, signed_size, LinkPacketType::PROBE_ACK, &offset);
  if (err != RadioError::NONE) {
    return err;
  }
  if (!read_u64(data, signed_size, &offset, &packet->challenge) ||
      offset >= signed_size) {
    return RadioError::PACKET_TRUNCATED;
  }
  const uint8_t accepted = data[offset++];
  if ((accepted != 0 && accepted != 1) || offset != signed_size ||
      packet->challenge == 0) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  packet->accepted = accepted == 1;
  return RadioError::NONE;
}

RadioError encode_authenticated_receipt_ack(
    const LinkKey &lmk,
    uint64_t boot_session,
    uint32_t seq,
    ReceiptStatus status,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || !link_key_nonzero(lmk) || boot_session == 0 ||
      (status != ReceiptStatus::ACCEPTED_FOR_FORWARDING &&
       status != ReceiptStatus::REJECTED)) {
    return RadioError::INVALID_ARGUMENT;
  }
  encoded->clear();
  append_prefix(encoded, LinkPacketType::RECEIPT_ACK);
  append_u64(encoded, boot_session);
  append_u32(encoded, seq);
  encoded->push_back(static_cast<uint8_t>(status));
  return append_auth(lmk, encoded);
}

RadioError decode_authenticated_receipt_ack(
    const uint8_t *data,
    std::size_t size,
    const LinkKey &lmk,
    ReceiptAckPacket *packet) {
  if (packet == nullptr || !link_key_nonzero(lmk) ||
      size > kEspNowDatagramLimit) {
    return RadioError::INVALID_ARGUMENT;
  }
  RadioError err = verify_auth(lmk, data, size, kPrefixBytes + 8 + 4 + 1);
  if (err != RadioError::NONE) {
    return err;
  }
  const std::size_t signed_size = size - kControlAuthBytes;
  std::size_t offset = 0;
  err = validate_prefix(data, signed_size, LinkPacketType::RECEIPT_ACK, &offset);
  if (err != RadioError::NONE) {
    return err;
  }
  uint8_t status = 0;
  if (!read_u64(data, signed_size, &offset, &packet->boot_session) ||
      !read_u32(data, signed_size, &offset, &packet->seq) ||
      offset >= signed_size) {
    return RadioError::PACKET_TRUNCATED;
  }
  status = data[offset++];
  if (offset != signed_size || packet->boot_session == 0 || status > 1) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  packet->status = static_cast<ReceiptStatus>(status);
  return RadioError::NONE;
}

RadioError encode_data_fragment(
    const DataFragment &fragment,
    std::vector<uint8_t> *encoded) {
  if (encoded == nullptr || fragment.boot_session == 0 ||
      fragment.total_ciphertext == 0 ||
      fragment.total_ciphertext > kMaxCiphertextBytes ||
      fragment.fragment_count == 0 ||
      fragment.fragment_count > kMaxDataFragments ||
      fragment.fragment_index >= fragment.fragment_count ||
      fragment.payload.empty() ||
      fragment.payload.size() > kDataFragmentPayloadBytes ||
      fragment.offset !=
          static_cast<uint16_t>(fragment.fragment_index * kDataFragmentPayloadBytes) ||
      static_cast<std::size_t>(fragment.offset) + fragment.payload.size() >
          fragment.total_ciphertext) {
    return RadioError::INVALID_ARGUMENT;
  }
  const uint8_t expected_count = static_cast<uint8_t>(
      (fragment.total_ciphertext + kDataFragmentPayloadBytes - 1) /
      kDataFragmentPayloadBytes);
  if (fragment.fragment_count != expected_count) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  const std::size_t expected_payload = std::min<std::size_t>(
      kDataFragmentPayloadBytes,
      fragment.total_ciphertext - fragment.offset);
  if (fragment.payload.size() != expected_payload) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }

  encoded->clear();
  append_prefix(encoded, LinkPacketType::DATA_FRAGMENT);
  append_u64(encoded, fragment.boot_session);
  append_u32(encoded, fragment.seq);
  append_u32(encoded, fragment.key_epoch);
  append_u16(encoded, fragment.total_ciphertext);
  encoded->push_back(fragment.fragment_index);
  encoded->push_back(fragment.fragment_count);
  append_u16(encoded, fragment.offset);
  encoded->insert(encoded->end(), fragment.nonce.begin(), fragment.nonce.end());
  encoded->insert(encoded->end(), fragment.tag.begin(), fragment.tag.end());
  encoded->insert(encoded->end(), fragment.payload.begin(), fragment.payload.end());
  if (encoded->size() > kEspNowDatagramLimit) {
    encoded->clear();
    return RadioError::PACKET_TOO_LARGE;
  }
  return RadioError::NONE;
}

RadioError decode_data_fragment(
    const uint8_t *data,
    std::size_t size,
    DataFragment *fragment) {
  if (fragment == nullptr || data == nullptr || size > kEspNowDatagramLimit) {
    return RadioError::INVALID_ARGUMENT;
  }
  if (size <= kDataHeaderBytes) {
    return RadioError::PACKET_TRUNCATED;
  }
  std::size_t offset = 0;
  RadioError err = validate_prefix(data, size, LinkPacketType::DATA_FRAGMENT, &offset);
  if (err != RadioError::NONE) {
    return err;
  }
  if (!read_u64(data, size, &offset, &fragment->boot_session) ||
      !read_u32(data, size, &offset, &fragment->seq) ||
      !read_u32(data, size, &offset, &fragment->key_epoch) ||
      !read_u16(data, size, &offset, &fragment->total_ciphertext)) {
    return RadioError::PACKET_TRUNCATED;
  }
  if (offset + 2 > size) {
    return RadioError::PACKET_TRUNCATED;
  }
  fragment->fragment_index = data[offset++];
  fragment->fragment_count = data[offset++];
  if (!read_u16(data, size, &offset, &fragment->offset) ||
      offset + kNonceBytes + kTagBytes > size) {
    return RadioError::PACKET_TRUNCATED;
  }
  std::copy_n(data + offset, kNonceBytes, fragment->nonce.begin());
  offset += kNonceBytes;
  std::copy_n(data + offset, kTagBytes, fragment->tag.begin());
  offset += kTagBytes;
  fragment->payload.assign(data + offset, data + size);

  if (fragment->boot_session == 0 || fragment->total_ciphertext == 0 ||
      fragment->total_ciphertext > kMaxCiphertextBytes ||
      fragment->fragment_count == 0 ||
      fragment->fragment_count > kMaxDataFragments ||
      fragment->fragment_index >= fragment->fragment_count ||
      fragment->payload.empty() ||
      fragment->payload.size() > kDataFragmentPayloadBytes ||
      fragment->offset != static_cast<uint16_t>(
          fragment->fragment_index * kDataFragmentPayloadBytes)) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  const uint8_t expected_count = static_cast<uint8_t>(
      (fragment->total_ciphertext + kDataFragmentPayloadBytes - 1) /
      kDataFragmentPayloadBytes);
  if (fragment->fragment_count != expected_count ||
      fragment->offset >= fragment->total_ciphertext) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  const std::size_t expected_payload = std::min<std::size_t>(
      kDataFragmentPayloadBytes,
      fragment->total_ciphertext - fragment->offset);
  if (fragment->payload.size() != expected_payload ||
      static_cast<std::size_t>(fragment->offset) + fragment->payload.size() >
          fragment->total_ciphertext) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  return RadioError::NONE;
}

RadioError fragment_relay_frame(
    const RelayFrame &frame,
    std::vector<std::vector<uint8_t>> *datagrams) {
  if (datagrams == nullptr || frame.header.schema != "gh.relay/1" ||
      frame.header.transport != "esp_now" || frame.header.hop_count != 1 ||
      !valid_identity(frame.header.gateway_id) ||
      !valid_identity(frame.header.node_id) || frame.header.key_epoch == 0 ||
      frame.ciphertext.empty() || frame.ciphertext.size() > kMaxCiphertextBytes) {
    return RadioError::INVALID_ARGUMENT;
  }
  uint64_t boot_session = 0;
  if (!parse_boot_id(frame.header.boot_id, &boot_session)) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  std::array<uint8_t, kNonceBytes> expected_nonce{};
  if (derive_nonce(frame.header.boot_id, frame.header.seq, &expected_nonce) !=
          CoreError::NONE ||
      !constant_time_equal(
          expected_nonce.data(), frame.nonce.data(), expected_nonce.size())) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }

  const uint8_t count = static_cast<uint8_t>(
      (frame.ciphertext.size() + kDataFragmentPayloadBytes - 1) /
      kDataFragmentPayloadBytes);
  datagrams->clear();
  datagrams->reserve(count);
  for (uint8_t index = 0; index < count; ++index) {
    const std::size_t offset = index * kDataFragmentPayloadBytes;
    const std::size_t length = std::min<std::size_t>(
        kDataFragmentPayloadBytes, frame.ciphertext.size() - offset);
    DataFragment fragment;
    fragment.boot_session = boot_session;
    fragment.seq = frame.header.seq;
    fragment.key_epoch = frame.header.key_epoch;
    fragment.total_ciphertext = static_cast<uint16_t>(frame.ciphertext.size());
    fragment.fragment_index = index;
    fragment.fragment_count = count;
    fragment.offset = static_cast<uint16_t>(offset);
    fragment.nonce = frame.nonce;
    fragment.tag = frame.tag;
    fragment.payload.assign(
        frame.ciphertext.begin() + static_cast<std::ptrdiff_t>(offset),
        frame.ciphertext.begin() + static_cast<std::ptrdiff_t>(offset + length));
    std::vector<uint8_t> encoded;
    const RadioError err = encode_data_fragment(fragment, &encoded);
    if (err != RadioError::NONE) {
      datagrams->clear();
      return err;
    }
    datagrams->push_back(std::move(encoded));
  }
  return RadioError::NONE;
}

void RelayReassembler::reset() {
  active_ = false;
  boot_session_ = 0;
  seq_ = 0;
  key_epoch_ = 0;
  total_ciphertext_ = 0;
  fragment_count_ = 0;
  nonce_.fill(0);
  tag_.fill(0);
  ciphertext_.clear();
  received_.clear();
}

RadioError RelayReassembler::accept(
    const uint8_t *data,
    std::size_t size,
    const std::string &gateway_id,
    const std::string &node_id,
    RelayFrame *frame,
    bool *complete) {
  if (frame == nullptr || complete == nullptr || !valid_identity(gateway_id) ||
      !valid_identity(node_id)) {
    return RadioError::INVALID_ARGUMENT;
  }
  *complete = false;
  DataFragment fragment;
  RadioError err = decode_data_fragment(data, size, &fragment);
  if (err != RadioError::NONE) {
    return err;
  }

  if (!active_) {
    active_ = true;
    boot_session_ = fragment.boot_session;
    seq_ = fragment.seq;
    key_epoch_ = fragment.key_epoch;
    total_ciphertext_ = fragment.total_ciphertext;
    fragment_count_ = fragment.fragment_count;
    nonce_ = fragment.nonce;
    tag_ = fragment.tag;
    ciphertext_.assign(total_ciphertext_, 0);
    received_.assign(fragment_count_, false);
  } else if (boot_session_ != fragment.boot_session || seq_ != fragment.seq) {
    return RadioError::REASSEMBLY_BUSY;
  } else if (key_epoch_ != fragment.key_epoch ||
             total_ciphertext_ != fragment.total_ciphertext ||
             fragment_count_ != fragment.fragment_count ||
             !constant_time_equal(nonce_.data(), fragment.nonce.data(), nonce_.size()) ||
             !constant_time_equal(tag_.data(), fragment.tag.data(), tag_.size())) {
    return RadioError::FRAGMENT_CONFLICT;
  }

  const std::size_t index = fragment.fragment_index;
  if (received_[index]) {
    if (!std::equal(
            fragment.payload.begin(),
            fragment.payload.end(),
            ciphertext_.begin() + fragment.offset)) {
      return RadioError::FRAGMENT_CONFLICT;
    }
    return RadioError::DUPLICATE_FRAGMENT;
  }
  std::copy(
      fragment.payload.begin(),
      fragment.payload.end(),
      ciphertext_.begin() + fragment.offset);
  received_[index] = true;
  if (!std::all_of(received_.begin(), received_.end(), [](bool value) { return value; })) {
    return RadioError::NONE;
  }

  frame->header = RelayHeader{};
  frame->header.gateway_id = gateway_id;
  frame->header.node_id = node_id;
  frame->header.key_epoch = key_epoch_;
  frame->header.boot_id = format_boot_id(boot_session_);
  frame->header.seq = seq_;
  frame->nonce = nonce_;
  frame->tag = tag_;
  frame->ciphertext = ciphertext_;
  *complete = true;
  reset();
  return RadioError::NONE;
}

RadioError RelayIngressController::accept_fragment(
    const uint8_t *data,
    std::size_t size,
    const std::string &gateway_id,
    const std::string &node_id,
    ReceiptAckPacket *receipt,
    bool *receipt_ready) {
  if (sink_ == nullptr || receipt == nullptr || receipt_ready == nullptr) {
    return RadioError::INVALID_ARGUMENT;
  }
  *receipt_ready = false;
  RelayFrame frame;
  bool complete = false;
  const RadioError err = reassembler_.accept(
      data, size, gateway_id, node_id, &frame, &complete);
  if (err != RadioError::NONE && err != RadioError::DUPLICATE_FRAGMENT) {
    return err;
  }
  if (!complete) {
    return err;
  }
  uint64_t boot_session = 0;
  if (!parse_boot_id(frame.header.boot_id, &boot_session)) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  receipt->boot_session = boot_session;
  receipt->seq = frame.header.seq;
  const bool accepted = sink_->accept_for_forwarding(frame);
  receipt->status = accepted ? ReceiptStatus::ACCEPTED_FOR_FORWARDING
                             : ReceiptStatus::REJECTED;
  *receipt_ready = accepted;
  return RadioError::NONE;
}

RadioError ChannelScanPlan::configure(
    uint8_t last_direct_channel,
    const std::vector<uint8_t> &allowed_channels) {
  channels_.clear();
  index_ = 0;
  auto append_unique = [this](uint8_t channel) {
    if (std::find(channels_.begin(), channels_.end(), channel) == channels_.end()) {
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

bool RetryPolicy::valid() const {
  return initial_delay_ms > 0 && max_delay_ms >= initial_delay_ms &&
         max_attempts > 0;
}

uint64_t ChildRelayCache::saturating_add_(uint64_t left, uint64_t right) {
  if (right > std::numeric_limits<uint64_t>::max() - left) {
    return std::numeric_limits<uint64_t>::max();
  }
  return left + right;
}

CachedRelayFrame *ChildRelayCache::find_(uint64_t boot_session, uint32_t seq) {
  for (auto &entry : entries_) {
    if (entry.boot_session == boot_session && entry.seq == seq) {
      return &entry;
    }
  }
  return nullptr;
}

RadioError ChildRelayCache::enqueue(const RelayFrame &frame, uint64_t now_ms) {
  if (capacity_ == 0 || !policy_.valid()) {
    return RadioError::INVALID_ARGUMENT;
  }
  uint64_t boot_session = 0;
  if (!parse_boot_id(frame.header.boot_id, &boot_session)) {
    return RadioError::PACKET_FORMAT_REJECTED;
  }
  if (find_(boot_session, frame.header.seq) != nullptr) {
    return RadioError::DUPLICATE_FRAGMENT;
  }
  if (entries_.size() >= capacity_) {
    return RadioError::CACHE_FULL;
  }
  CachedRelayFrame cached;
  cached.boot_session = boot_session;
  cached.seq = frame.header.seq;
  cached.next_due_ms = now_ms;
  const RadioError err = fragment_relay_frame(frame, &cached.datagrams);
  if (err != RadioError::NONE) {
    return err;
  }
  entries_.push_back(std::move(cached));
  return RadioError::NONE;
}

const CachedRelayFrame *ChildRelayCache::next_due(uint64_t now_ms) const {
  const CachedRelayFrame *best = nullptr;
  for (const auto &entry : entries_) {
    if (entry.exhausted || entry.next_due_ms > now_ms) {
      continue;
    }
    if (best == nullptr || entry.next_due_ms < best->next_due_ms) {
      best = &entry;
    }
  }
  return best;
}

RadioError ChildRelayCache::note_attempt(
    uint64_t boot_session,
    uint32_t seq,
    uint64_t now_ms) {
  CachedRelayFrame *entry = find_(boot_session, seq);
  if (entry == nullptr) {
    return RadioError::CACHE_NOT_FOUND;
  }
  if (entry->exhausted) {
    return RadioError::RETRY_EXHAUSTED;
  }
  ++entry->attempts;
  if (entry->attempts >= policy_.max_attempts) {
    entry->exhausted = true;
    entry->next_due_ms = std::numeric_limits<uint64_t>::max();
    return RadioError::RETRY_EXHAUSTED;
  }
  uint64_t delay = policy_.initial_delay_ms;
  for (uint8_t i = 1; i < entry->attempts; ++i) {
    if (delay >= policy_.max_delay_ms / 2U) {
      delay = policy_.max_delay_ms;
      break;
    }
    delay *= 2U;
  }
  delay = std::min<uint64_t>(delay, policy_.max_delay_ms);
  entry->next_due_ms = saturating_add_(now_ms, delay);
  return RadioError::NONE;
}

bool ChildRelayCache::acknowledge(const ReceiptAckPacket &ack) {
  if (ack.status != ReceiptStatus::ACCEPTED_FOR_FORWARDING || ack.boot_session == 0) {
    return false;
  }
  for (auto it = entries_.begin(); it != entries_.end(); ++it) {
    if (it->boot_session == ack.boot_session && it->seq == ack.seq) {
      entries_.erase(it);
      return true;
    }
  }
  return false;
}

bool LocalPathPolicy::valid() const {
  return direct_failures_to_discovery > 0 &&
         direct_recoveries_to_direct > 0 && relay_failures_to_discovery > 0;
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
