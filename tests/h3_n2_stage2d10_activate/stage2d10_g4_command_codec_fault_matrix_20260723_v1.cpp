#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>

#include "secure_pairing_channel.h"
#include "stage2d10_g4_command_codec.h"

using namespace esphome::greenhouse_pairing_client;

namespace {

std::string hex_repeat(char value) {
  return std::string(64, value);
}

std::string base64url(const std::string &value) {
  std::string output;
  assert(SecurePairingChannel::encode_base64url(
      reinterpret_cast<const uint8_t *>(value.data()), value.size(),
      &output));
  return output;
}

struct CommandFixture {
  std::string unlock_token{hex_repeat('1')};
  std::string persistence_key{hex_repeat('2')};
  std::string authorization_digest{hex_repeat('3')};
  std::string candidate_digest{hex_repeat('4')};
  std::string broker_digest{hex_repeat('5')};
  std::string active_digest{hex_repeat('6')};
  std::string unlock_digest{};
  std::string ssid{"gh-stage2d10-test"};
  std::string password{"stage2d10-private-password"};
  std::string wifi_digest{};

  CommandFixture() {
    std::array<uint8_t, 32> unlock{};
    for (size_t index = 0; index < unlock.size(); index++)
      unlock[index] = 0x11;
    Stage2D10G4CommandEnvelope temporary;
    const std::string verify_without_digest =
        std::string(Stage2D10G4CommandCodec::VERIFY_SCHEMA) +
        " a1b2c3d4e5f6 " + unlock_token + " " + persistence_key + " " +
        active_digest + " READ_ONLY";
    assert(Stage2D10G4CommandCodec::command_sha256(
        std::string(reinterpret_cast<const char *>(unlock.data()),
                    unlock.size()),
        &unlock_digest));
    assert(Stage2D10G4CommandCodec::wifi_profile_digest(
        ssid, password, &wifi_digest));
    temporary.clear();
    (void) verify_without_digest;
    unlock.fill(0);
  }

  std::string activate() const {
    return std::string(Stage2D10G4CommandCodec::ACTIVATE_SCHEMA) +
           " a1b2c3d4e5f6 " + unlock_token + " " + persistence_key + " " +
           authorization_digest + " " + candidate_digest + " " +
           base64url(ssid) + " " + base64url(password) + " " + wifi_digest +
           " " + broker_digest;
  }

  std::string verify() const {
    return std::string(Stage2D10G4CommandCodec::VERIFY_SCHEMA) +
           " a1b2c3d4e5f6 " + unlock_token + " " + persistence_key + " " +
           active_digest + " READ_ONLY";
  }
};

void test_activate_valid() {
  CommandFixture fixture;
  Stage2D10G4CommandEnvelope envelope;
  Stage2D10G4CommandFailure failure{};
  const std::string raw = fixture.activate();
  assert(Stage2D10G4CommandCodec::parse(
      raw, fixture.unlock_digest, &envelope, &failure));
  assert(failure == Stage2D10G4CommandFailure::NONE);
  assert(envelope.action == Stage2D10G4CommandAction::ACTIVATE_PROFILE);
  assert(envelope.run_suffix == "a1b2c3d4e5f6");
  assert(envelope.authorization_digest == fixture.authorization_digest);
  assert(envelope.candidate_digest == fixture.candidate_digest);
  assert(envelope.wifi_ssid == fixture.ssid);
  assert(envelope.wifi_password == fixture.password);
  assert(envelope.wifi_profile_digest == fixture.wifi_digest);
  assert(envelope.broker_configuration_digest == fixture.broker_digest);
  assert(envelope.raw_command_sha256.size() == 64);
  assert(Stage2D10G4CommandCodec::action_name(envelope.action) ==
         std::string("activate_profile"));
  envelope.clear();
  assert(envelope.action == Stage2D10G4CommandAction::NONE);
  assert(envelope.wifi_ssid.empty());
  assert(envelope.wifi_password.empty());
  assert(std::all_of(envelope.unlock_token.begin(),
                     envelope.unlock_token.end(),
                     [](uint8_t value) { return value == 0; }));
}

void test_verify_valid_and_read_only() {
  CommandFixture fixture;
  Stage2D10G4CommandEnvelope envelope;
  Stage2D10G4CommandFailure failure{};
  assert(Stage2D10G4CommandCodec::parse(
      fixture.verify(), fixture.unlock_digest, &envelope, &failure));
  assert(envelope.action ==
         Stage2D10G4CommandAction::VERIFY_ACTIVE_READ_ONLY);
  assert(envelope.active_digest == fixture.active_digest);
  assert(envelope.authorization_digest.empty());
  assert(envelope.candidate_digest.empty());
  assert(envelope.wifi_ssid.empty());
  assert(envelope.wifi_password.empty());
}

void test_schema_and_field_count_fail_closed() {
  CommandFixture fixture;
  for (const std::string &raw : {
           std::string("GH2D10_PREPARE_V1 x"),
           std::string("GH2D10_CLEANUP_V1 x"),
           fixture.activate() + " extra",
           fixture.verify() + " extra",
           fixture.verify().substr(0, fixture.verify().rfind(' ')),
       }) {
    Stage2D10G4CommandEnvelope envelope;
    Stage2D10G4CommandFailure failure{};
    assert(!Stage2D10G4CommandCodec::parse(
        raw, fixture.unlock_digest, &envelope, &failure));
    assert(envelope.action == Stage2D10G4CommandAction::NONE);
    assert(envelope.wifi_password.empty());
  }
}

void test_whitespace_and_length_fail_closed() {
  CommandFixture fixture;
  const std::string valid = fixture.activate();
  for (const std::string &raw : {
           " " + valid,
           valid + " ",
           valid.substr(0, valid.find(' ')) + "  " +
               valid.substr(valid.find(' ') + 1),
           valid + "\n",
           valid + "\r",
           valid + "\t",
           std::string(Stage2D10G4CommandCodec::MAX_COMMAND_LENGTH + 1, 'a'),
       }) {
    Stage2D10G4CommandEnvelope envelope;
    Stage2D10G4CommandFailure failure{};
    assert(!Stage2D10G4CommandCodec::parse(
        raw, fixture.unlock_digest, &envelope, &failure));
  }
}

void test_unlock_and_hex_binding() {
  CommandFixture fixture;
  for (const std::pair<std::string, std::string> &item : {
           std::make_pair(fixture.activate(), hex_repeat('7')),
           std::make_pair(fixture.verify(), hex_repeat('7')),
           std::make_pair(fixture.activate(), std::string(63, 'a')),
       }) {
    Stage2D10G4CommandEnvelope envelope;
    Stage2D10G4CommandFailure failure{};
    assert(!Stage2D10G4CommandCodec::parse(
        item.first, item.second, &envelope, &failure));
    assert(envelope.action == Stage2D10G4CommandAction::NONE);
  }

  std::string invalid = fixture.activate();
  const size_t token_position = invalid.find(fixture.unlock_token);
  assert(token_position != std::string::npos);
  invalid[token_position] = 'g';
  Stage2D10G4CommandEnvelope envelope;
  Stage2D10G4CommandFailure failure{};
  assert(!Stage2D10G4CommandCodec::parse(
      invalid, fixture.unlock_digest, &envelope, &failure));
  assert(failure == Stage2D10G4CommandFailure::HEX_SHAPE);
}

void test_wifi_base64_length_and_digest_binding() {
  CommandFixture fixture;
  const std::string valid = fixture.activate();

  const std::string encoded_ssid = base64url(fixture.ssid);
  const std::string encoded_password = base64url(fixture.password);

  for (const std::pair<std::string, Stage2D10G4CommandFailure> &item : {
           std::make_pair(
               valid.substr(0, valid.find(encoded_ssid)) + "*invalid*" +
                   valid.substr(valid.find(encoded_ssid) + encoded_ssid.size()),
               Stage2D10G4CommandFailure::BASE64URL),
           std::make_pair(
               valid.substr(0, valid.find(encoded_password)) +
                   base64url("short") +
                   valid.substr(valid.find(encoded_password) +
                                encoded_password.size()),
               Stage2D10G4CommandFailure::WIFI_LENGTH),
       }) {
    Stage2D10G4CommandEnvelope envelope;
    Stage2D10G4CommandFailure failure{};
    assert(!Stage2D10G4CommandCodec::parse(
        item.first, fixture.unlock_digest, &envelope, &failure));
    assert(failure == item.second);
    assert(envelope.wifi_password.empty());
  }

  std::string digest_mismatch = valid;
  const size_t digest_position = digest_mismatch.find(fixture.wifi_digest);
  assert(digest_position != std::string::npos);
  digest_mismatch.replace(digest_position, 64, hex_repeat('8'));
  Stage2D10G4CommandEnvelope envelope;
  Stage2D10G4CommandFailure failure{};
  assert(!Stage2D10G4CommandCodec::parse(
      digest_mismatch, fixture.unlock_digest, &envelope, &failure));
  assert(failure == Stage2D10G4CommandFailure::WIFI_DIGEST);
}

void test_verify_mode_exact() {
  CommandFixture fixture;
  for (const std::string mode : {"WRITE", "read_only", "READONLY"}) {
    std::string raw = fixture.verify();
    raw.replace(raw.rfind("READ_ONLY"), 9, mode);
    Stage2D10G4CommandEnvelope envelope;
    Stage2D10G4CommandFailure failure{};
    assert(!Stage2D10G4CommandCodec::parse(
        raw, fixture.unlock_digest, &envelope, &failure));
    assert(failure == Stage2D10G4CommandFailure::VERIFY_MODE);
  }
}

}  // namespace

int main() {
  test_activate_valid();
  test_verify_valid_and_read_only();
  test_schema_and_field_count_fail_closed();
  test_whitespace_and_length_fail_closed();
  test_unlock_and_hex_binding();
  test_wifi_base64_length_and_digest_binding();
  test_verify_mode_exact();
  std::cout << "stage2d10_g4_command_codec_fault_matrix=pass\n";
  return 0;
}
