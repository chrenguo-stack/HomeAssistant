#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

#include "n3w_core.h"

using esphome::greenhouse_n3w_core::ApplicationKeyState;
using esphome::greenhouse_n3w_core::BootSessionManager;
using esphome::greenhouse_n3w_core::BootSessionStore;
using esphome::greenhouse_n3w_core::CoreError;
using esphome::greenhouse_n3w_core::KeyLifecycle;
using esphome::greenhouse_n3w_core::RelayFrame;
using esphome::greenhouse_n3w_core::RelayHeader;
using esphome::greenhouse_n3w_core::SequenceCounter;
using esphome::greenhouse_n3w_core::StoreStatus;
using esphome::greenhouse_n3w_core::aes256gcm_decrypt;
using esphome::greenhouse_n3w_core::build_aad;
using esphome::greenhouse_n3w_core::build_relay_frame;
using esphome::greenhouse_n3w_core::derive_nonce;
using esphome::greenhouse_n3w_core::serialize_relay_frame_json;

namespace {

std::vector<uint8_t> from_hex(const std::string &hex) {
  assert(hex.size() % 2 == 0);
  std::vector<uint8_t> output;
  output.reserve(hex.size() / 2);
  for (std::size_t index = 0; index < hex.size(); index += 2) {
    output.push_back(static_cast<uint8_t>(
        std::stoul(hex.substr(index, 2), nullptr, 16)));
  }
  return output;
}

struct FakeBootStore final : BootSessionStore {
  StoreStatus load_status{StoreStatus::MISSING};
  StoreStatus save_status{StoreStatus::OK};
  uint64_t value{0};
  bool corrupt_readback{false};

  StoreStatus load(uint64_t *last_session) override {
    if (load_status != StoreStatus::OK)
      return load_status;
    *last_session = corrupt_readback ? value + 1U : value;
    return StoreStatus::OK;
  }

  StoreStatus save(uint64_t last_session) override {
    if (save_status != StoreStatus::OK)
      return save_status;
    value = last_session;
    load_status = StoreStatus::OK;
    return StoreStatus::OK;
  }
};

ApplicationKeyState fixed_key() {
  ApplicationKeyState key;
  key.lifecycle = KeyLifecycle::ACTIVE;
  key.key_epoch = 7;
  key.session_floor = 0;
  for (std::size_t index = 0; index < key.key.size(); ++index)
    key.key[index] = static_cast<uint8_t>(index);
  return key;
}

RelayHeader fixed_header() {
  RelayHeader header;
  header.gateway_id = "gateway_001";
  header.node_id = "node_0001";
  header.key_epoch = 7;
  header.boot_id = "boot_0102030405060708";
  header.seq = 0x0A0B0C0DU;
  return header;
}

constexpr char kPlaintext[] =
    "{\"boot_id\":\"boot_0102030405060708\",\"cap_hash\":\"cap_hash_001\"," 
    "\"measurements\":{\"air_temperature_c\":24.5},\"node_id\":\"node_0001\"," 
    "\"power\":{\"low\":false,\"source\":\"main\"},"
    "\"quality\":{\"air_temperature_c\":\"ok\"},"
    "\"schema\":\"gh.telemetry/1\",\"seq\":168496141,\"uptime_ms\":1234}";

constexpr char kExpectedAad[] =
    "{\"boot_id\":\"boot_0102030405060708\",\"gateway_id\":\"gateway_001\"," 
    "\"hop_count\":1,\"key_epoch\":7,\"node_id\":\"node_0001\"," 
    "\"schema\":\"gh.relay/1\",\"seq\":168496141,\"transport\":\"esp_now\"}";

constexpr char kExpectedCiphertextHex[] =
    "3ff9ce942c2a4b94b93396729323ad4aa6b686a5a63825feb724c9a8a74eeab2"
    "5b06877638f0cf31a138aa86e82a03d5df8b9a2acf8277215d9f5d8518814c10"
    "8f319ee107a07cd38c4c5a1744699e7843be9f94c076f06f5ad7888f252714435"
    "37fee66d9392e006b92148bc659369cffe93b3ee0e7e9b4c643359e364de5751e"
    "ce8940a236a441f054adf1218c0f96a3a56ddc4b013d5b3bdf880d8cd38f016c"
    "872665c8458c65a32c62d9b9561b77aec61d5b190738f326a8a4f7a7da365b09"
    "dde1ee97cdc242ab1455275519bd261b6b62689b9c7200945a00574e48e4c8ae1"
    "e731b0e2aa551ccc9e1981ccd2669ec920cc3ec07283347c883c84e6ec2fb710733";

constexpr char kExpectedTagHex[] =
    "11a810b8148c1d8cfeff47f56ef9df34";

void test_crypto_vector() {
  const RelayHeader header = fixed_header();
  const ApplicationKeyState key = fixed_key();

  std::array<uint8_t, 12> nonce{};
  assert(derive_nonce(header.boot_id, header.seq, &nonce) == CoreError::NONE);
  const std::array<uint8_t, 12> expected_nonce{
      0x01, 0x02, 0x03, 0x04, 0x05, 0x06,
      0x07, 0x08, 0x0A, 0x0B, 0x0C, 0x0D};
  assert(nonce == expected_nonce);

  std::string aad;
  assert(build_aad(header, &aad) == CoreError::NONE);
  assert(aad == kExpectedAad);

  RelayFrame frame;
  assert(build_relay_frame(header, key, kPlaintext, &frame) == CoreError::NONE);
  assert(frame.nonce == expected_nonce);
  assert(frame.ciphertext == from_hex(kExpectedCiphertextHex));

  const std::vector<uint8_t> tag = from_hex(kExpectedTagHex);
  assert(std::equal(frame.tag.begin(), frame.tag.end(), tag.begin(), tag.end()));

  std::string recovered;
  assert(aes256gcm_decrypt(
             key, frame.nonce, frame.ciphertext, frame.tag, aad, &recovered) ==
         CoreError::NONE);
  assert(recovered == kPlaintext);

  std::string tampered_aad = aad;
  tampered_aad.replace(
      tampered_aad.find("gateway_001"),
      std::string("gateway_001").size(),
      "gateway_999");
  recovered.clear();
  assert(aes256gcm_decrypt(
             key,
             frame.nonce,
             frame.ciphertext,
             frame.tag,
             tampered_aad,
             &recovered) == CoreError::AEAD_DECRYPT_FAILED);
  assert(recovered.empty());

  ApplicationKeyState wrong_epoch = key;
  wrong_epoch.key_epoch = 8;
  RelayFrame rejected;
  assert(build_relay_frame(
             header, wrong_epoch, kPlaintext, &rejected) ==
         CoreError::KEY_STATE_INVALID);

  std::string outer;
  assert(serialize_relay_frame_json(frame, &outer) == CoreError::NONE);
  assert(outer.find("\"schema\":\"gh.relay/1\"") != std::string::npos);
  assert(outer.find("\"transport\":\"esp_now\"") != std::string::npos);
  assert(outer.find("\"nonce_b64\":\"AQIDBAUGBwgKCwwN\"") != std::string::npos);
  assert(outer.find("\"tag_b64\":\"EagQuBSMHYz+/0f1bvnfNA==\"") !=
         std::string::npos);
}

void test_key_state() {
  ApplicationKeyState key = fixed_key();
  assert(key.valid_for_encrypt());

  key.lifecycle = KeyLifecycle::STAGED;
  assert(!key.valid_for_encrypt());
  key.lifecycle = KeyLifecycle::GRACE;
  assert(!key.valid_for_encrypt());
  key.lifecycle = KeyLifecycle::REVOKED;
  assert(!key.valid_for_encrypt());
  key.lifecycle = KeyLifecycle::ACTIVE;
  key.key_epoch = 0;
  assert(!key.valid_for_encrypt());

  key = fixed_key();
  key.clear();
  assert(!key.valid_for_encrypt());
  for (uint8_t value : key.key)
    assert(value == 0);
}

void test_boot_session_durability_and_rollback() {
  FakeBootStore store;
  BootSessionManager manager;

  assert(manager.begin(&store, 0) == CoreError::STORE_MISSING);
  assert(!manager.ready());

  assert(manager.provision_recovery_floor(&store, 0) == CoreError::NONE);
  assert(manager.begin(&store, 0) == CoreError::NONE);
  assert(manager.ready());
  assert(manager.session() == 1);
  assert(manager.boot_id() == "boot_0000000000000001");

  uint32_t seq = 99;
  assert(manager.take_sequence(&seq) == CoreError::NONE);
  assert(seq == 0);
  assert(manager.take_sequence(&seq) == CoreError::NONE);
  assert(seq == 1);

  BootSessionManager restarted;
  assert(restarted.begin(&store, 0) == CoreError::NONE);
  assert(restarted.session() == 2);
  assert(restarted.boot_id() == "boot_0000000000000002");

  FakeBootStore rollback;
  rollback.load_status = StoreStatus::OK;
  rollback.value = 4;
  BootSessionManager rejected;
  assert(rejected.begin(&rollback, 5) == CoreError::SESSION_ROLLBACK);
  assert(!rejected.ready());

  FakeBootStore corrupt;
  corrupt.load_status = StoreStatus::CORRUPT;
  assert(rejected.begin(&corrupt, 0) == CoreError::STORE_CORRUPT);

  FakeBootStore unavailable;
  unavailable.load_status = StoreStatus::OK;
  unavailable.value = 9;
  unavailable.save_status = StoreStatus::IO_ERROR;
  assert(rejected.begin(&unavailable, 0) == CoreError::STORE_IO_ERROR);

  FakeBootStore exhausted;
  exhausted.load_status = StoreStatus::OK;
  exhausted.value = std::numeric_limits<uint64_t>::max();
  assert(rejected.begin(&exhausted, 0) == CoreError::SESSION_EXHAUSTED);
}

void test_sequence_boundary() {
  SequenceCounter last(std::numeric_limits<uint32_t>::max());
  uint32_t seq = 0;
  assert(last.take(&seq) == CoreError::NONE);
  assert(seq == std::numeric_limits<uint32_t>::max());
  assert(last.exhausted());
  assert(last.take(&seq) == CoreError::SEQUENCE_EXHAUSTED);
}

}  // namespace

int main() {
  test_crypto_vector();
  test_key_state();
  test_boot_session_durability_and_rollback();
  test_sequence_boundary();
  std::cout << "P4A_HOST_CORE_PASS\n";
  return 0;
}
