#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>

#include "esphome/components/greenhouse_n3w_core/n3w_core.h"
#include "esphome/components/greenhouse_n3w_s5_private_runtime/n3w_product_s5_private_telemetry_stimulus.h"

using namespace esphome::greenhouse_n3w_core;
using namespace esphome::greenhouse_n3w_s5_private_runtime;

namespace {

std::array<uint8_t, kApplicationKeyBytes> test_key() {
  std::array<uint8_t, kApplicationKeyBytes> key{};
  for (std::size_t i = 0; i < key.size(); ++i)
    key[i] = static_cast<uint8_t>(0x80 + i);
  return key;
}

ApplicationKeyState key_state(
    const std::array<uint8_t, kApplicationKeyBytes> &key) {
  ApplicationKeyState state;
  state.lifecycle = KeyLifecycle::ACTIVE;
  state.key_epoch = 3;
  state.key = key;
  return state;
}

}  // namespace

int main() {
  const auto key = test_key();

  ProductS5PrivateTelemetryStimulus stimulus;
  assert(stimulus.configure("node_child01", 3, key, 7, 0));
  assert(stimulus.configured());
  assert(stimulus.application_key_resident());
  assert(!stimulus.prepared());
  assert(!stimulus.submitted());

  assert(
      stimulus.prepare("node_relay01", 1234) ==
      ProductS5PrivateTelemetryStimulusError::NONE);
  assert(stimulus.prepared());
  assert(!stimulus.submitted());
  assert(!stimulus.application_key_resident());
  assert(stimulus.prepared_gateway_id() == "node_relay01");

  const RelayFrame *frame = stimulus.prepared_frame();
  assert(frame != nullptr);
  assert(frame->header.schema == "gh.relay/1");
  assert(frame->header.transport == "esp_now");
  assert(frame->header.gateway_id == "node_relay01");
  assert(frame->header.node_id == "node_child01");
  assert(frame->header.key_epoch == 3);
  assert(frame->header.boot_id == "boot_0000000000000007");
  assert(frame->header.seq == 0);

  std::string aad;
  assert(build_aad(frame->header, &aad) == CoreError::NONE);
  std::string plaintext;
  const auto state = key_state(key);
  assert(
      aes256gcm_decrypt(
          state,
          frame->nonce,
          frame->ciphertext,
          frame->tag,
          aad,
          &plaintext) == CoreError::NONE);
  assert(plaintext.find("\"schema\":\"gh.telemetry/1\"") != std::string::npos);
  assert(plaintext.find("\"node_id\":\"node_child01\"") != std::string::npos);
  assert(plaintext.find("\"boot_id\":\"boot_0000000000000007\"") != std::string::npos);
  assert(plaintext.find("\"seq\":0") != std::string::npos);
  assert(plaintext.find("\"air_temperature_c\":24.5") != std::string::npos);
  assert(plaintext.find("\"exactly_once\":true") != std::string::npos);

  assert(
      stimulus.prepare("node_relay01", 1235) ==
      ProductS5PrivateTelemetryStimulusError::ALREADY_PREPARED);

  assert(stimulus.mark_submitted());
  assert(!stimulus.prepared());
  assert(stimulus.prepared_frame() == nullptr);
  assert(stimulus.submitted());
  assert(
      stimulus.prepare("node_relay01", 1236) ==
      ProductS5PrivateTelemetryStimulusError::ALREADY_SUBMITTED);
  assert(!stimulus.mark_submitted());

  ProductS5PrivateTelemetryStimulus invalid;
  std::array<uint8_t, kApplicationKeyBytes> zero_key{};
  assert(!invalid.configure("node_child01", 3, zero_key, 7, 0));
  assert(!invalid.configure("short", 3, key, 7, 0));

  std::cout << "S5_R7_PRIVATE_TELEMETRY_STIMULUS_EXACTLY_ONCE=PASS\n";
  return 0;
}
