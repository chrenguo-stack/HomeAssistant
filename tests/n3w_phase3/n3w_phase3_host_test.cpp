#include <algorithm>
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

#include "n3w_compact_telemetry.h"
#include "n3w_radio.h"
#include "n3w_simple_crypto.h"
#include "n3w_simple_runtime.h"

using namespace esphome::greenhouse_n3w_core;

namespace {

uint8_t nibble(char ch) {
  if (ch >= '0' && ch <= '9') return static_cast<uint8_t>(ch - '0');
  if (ch >= 'a' && ch <= 'f') return static_cast<uint8_t>(10 + ch - 'a');
  return static_cast<uint8_t>(10 + ch - 'A');
}

template<std::size_t N>
std::array<uint8_t, N> hex_array(const char *text) {
  assert(text != nullptr);
  assert(std::strlen(text) == N * 2U);
  std::array<uint8_t, N> output{};
  for (std::size_t i = 0; i < N; ++i) {
    output[i] = static_cast<uint8_t>(
        (nibble(text[i * 2U]) << 4U) | nibble(text[i * 2U + 1U]));
  }
  return output;
}

std::vector<uint8_t> hex_vector(const char *text) {
  assert(text != nullptr);
  const std::size_t length = std::strlen(text);
  assert(length % 2U == 0);
  std::vector<uint8_t> output(length / 2U, 0);
  for (std::size_t i = 0; i < output.size(); ++i) {
    output[i] = static_cast<uint8_t>(
        (nibble(text[i * 2U]) << 4U) | nibble(text[i * 2U + 1U]));
  }
  return output;
}

void test_pairing_cross_language_vectors() {
  SetupSecret setup_secret{};
  for (std::size_t i = 0; i < setup_secret.size(); ++i) {
    setup_secret[i] = static_cast<uint8_t>(i);
  }
  SimplePairingTranscript transcript{
      "pairing-0001",
      "ghw-c6-98a316a9f2f8",
      "manager-01",
      hex_array<16>("000102030405060708090a0b0c0d0e0f"),
      hex_array<16>("101112131415161718191a1b1c1d1e1f"),
  };
  assert(transcript.valid());

  std::array<uint8_t, 32> bootstrap{};
  assert(derive_bootstrap_key(setup_secret, transcript, &bootstrap) ==
         SimpleCryptoError::NONE);
  assert(bootstrap == hex_array<32>(
      "245cd6779140823149f1f338418155b6159515074f44c847cbefa779148b6442"));

  PeerProof node_proof{};
  PeerProof manager_proof{};
  assert(build_setup_proof(
             setup_secret, transcript, PairingRole::NODE, &node_proof) ==
         SimpleCryptoError::NONE);
  assert(build_setup_proof(
             setup_secret, transcript, PairingRole::MANAGER, &manager_proof) ==
         SimpleCryptoError::NONE);
  assert(node_proof == hex_array<32>(
      "5ee6550d20a489b5d60901158f63728a37a8faaf81c927d100dd2a20e0ea39fa"));
  assert(manager_proof == hex_array<32>(
      "8d070768337a1f279fc667c8b8e7f1dac2a917a002d99931ed78b72af30c89b4"));

  const SimpleAeadNonce aead_nonce = hex_array<12>("202122232425262728292a2b");
  const std::vector<uint8_t> encrypted = hex_vector(
      "ce6b1a415414bc949bb884cc78231ecd6ed87b83cb3e8d6a52ad4fe3d1708dc"
      "3d576fbe76e645fe0f1ebb5b05b4b9c83369cac871d430d709a3f46e297a370");
  std::vector<uint8_t> plaintext;
  assert(decrypt_simple_credential_bundle(
             bootstrap, transcript, aead_nonce, encrypted, &plaintext) ==
         SimpleCryptoError::NONE);
  const std::string expected =
      "{\"mqtt\":\"credential\",\"peer_trust_generation\":7}";
  assert(std::string(plaintext.begin(), plaintext.end()) == expected);
}

void test_peer_trust_cross_language_vectors() {
  SystemPeerCredentialV2 credential{"gh-system-01", 7, {}};
  for (std::size_t i = 0; i < credential.key.size(); ++i) {
    credential.key[i] = static_cast<uint8_t>(i);
  }
  const PeerEndpointV2 child{
      "gh-child-01", hex_array<6>("001122334455")};
  const PeerEndpointV2 relay{
      "gh-relay-01", hex_array<6>("aabbccddeeff")};
  const HandshakeNonce boot_nonce =
      hex_array<16>("101112131415161718191a1b1c1d1e1f");
  const HandshakeNonce challenge =
      hex_array<16>("202122232425262728292a2b2c2d2e2f");

  PeerProof proof{};
  assert(build_peer_proof_v2(
             credential, child, relay, boot_nonce, challenge, &proof) ==
         SimpleCryptoError::NONE);
  assert(proof == hex_array<32>(
      "c7b3b00fe36e493467ca53a84af37bb5fddb5a3d582901a2e82d0e72569fb199"));
  assert(verify_peer_proof_v2(
      credential, child, relay, boot_nonce, challenge, proof));

  SimpleLmk lmk{};
  SimpleLmk reverse{};
  assert(derive_pair_lmk_v2(credential, child, relay, &lmk) ==
         SimpleCryptoError::NONE);
  assert(derive_pair_lmk_v2(credential, relay, child, &reverse) ==
         SimpleCryptoError::NONE);
  assert(lmk == reverse);
  assert(lmk == hex_array<16>("fbfe0c8ee9d28f9b13738efd57aed3f2"));

  HandshakeNonce changed_challenge = challenge;
  changed_challenge[0] ^= 1U;
  assert(!verify_peer_proof_v2(
      credential, child, relay, boot_nonce, changed_challenge, proof));
}

void test_compact_telemetry_cross_language_vector() {
  ApplicationKeyState key_state;
  key_state.lifecycle = KeyLifecycle::ACTIVE;
  key_state.key_epoch = 1;
  for (std::size_t i = 0; i < key_state.key.size(); ++i) {
    key_state.key[i] = static_cast<uint8_t>(i);
  }
  const std::string telemetry =
      "{\"boot_id\":\"boot_0000000000000001\",\"cap_hash\":\"cap_hash_001\","
      "\"measurements\":{\"air_temperature_c\":24.5},\"node_id\":\"node_child01\","
      "\"power\":{\"low\":false,\"source\":\"main\"},\"quality\":{\"air_temperature_c\":\"ok\"},"
      "\"schema\":\"gh.telemetry/1\",\"seq\":42,\"uptime_ms\":1234}";

  std::string aad;
  assert(build_compact_aad_v2(
             "gh-system-01", "node_child01", 1,
             "boot_0000000000000001", 42, &aad) ==
         CompactTelemetryError::NONE);
  assert(aad ==
      "{\"boot_id\":\"boot_0000000000000001\",\"key_epoch\":1,"
      "\"node_id\":\"node_child01\",\"schema\":\"gh.relay/2\",\"seq\":42,"
      "\"system_id\":\"gh-system-01\"}");
  assert(aad.find("gateway") == std::string::npos);

  CompactTelemetryFrameV2 frame;
  assert(encrypt_compact_telemetry_v2(
             "gh-system-01", "node_child01", 1,
             "boot_0000000000000001", 42, key_state, telemetry, &frame) ==
         CompactTelemetryError::NONE);
  std::vector<uint8_t> encoded;
  assert(encode_compact_telemetry_frame_v2(frame, &encoded) ==
         CompactTelemetryError::NONE);
  assert(encoded.size() == 303U);
  assert(kCompactTelemetryMaxWireBytes == 1072U);
  assert(kCompactTelemetryMaxWireBytes <= kEspNowV2PayloadLimit);

  const std::vector<uint8_t> expected = hex_vector(
      "4e33573200000000000000010000002a0000000100000000000000010000002a"
      "69816be0202be3f6e274262cfcc9d0417efc372f8f6b5494b164d9d0e504b2e7"
      "7dcb3d6c648a6cf35c06f0374c29df8deb31c2f9a1c485d856c8d0ddca52cc42"
      "10658bdfee9b53762422f3d79c5c817e4561431b5d10b5225bf1fbe1d852112f"
      "728c74328ea86d2fededad01ef5fc925a36eaae8ad2a7923c1289dfddb4e2bd9e"
      "0a4f3c9a07a989cf6ba7b1f227cf48bb5ef5f9275afedc677340c49a6d50355d"
      "a20fff1694692ec060c83851fa1ac158e0dfb0f34d1aec0521eb3657ddce5c20a"
      "78e1940e26c7915dbd3b46ab00801d0d7775172345e23e7d85097bf3d22bc884"
      "39533b47789f8c98bef7d8b7a73cf1d0a236e1092b5b4e0f97fdb67992efc654"
      "77e5d7925209749da09820b904da");
  assert(encoded == expected);

  CompactTelemetryFrameV2 decoded;
  assert(decode_compact_telemetry_frame_v2(
             encoded.data(), encoded.size(), &decoded) ==
         CompactTelemetryError::NONE);
  std::string decrypted;
  assert(decrypt_compact_telemetry_v2(
             "gh-system-01", "node_child01", key_state, decoded, &decrypted) ==
         CompactTelemetryError::NONE);
  assert(decrypted == telemetry);

  std::string wrapper;
  assert(wrap_compact_relay_mqtt_v2(encoded, &wrapper) ==
         CompactTelemetryError::NONE);
  assert(wrapper.rfind("{\"frame_b64\":\"", 0) == 0);
  assert(wrapper.find("\",\"schema\":\"gh.relay/2\"}") != std::string::npos);
}

void test_simple_peer_handshake_and_local_fallback() {
  SystemPeerCredentialV2 credential{"gh-system-01", 9, {}};
  for (std::size_t i = 0; i < credential.key.size(); ++i) {
    credential.key[i] = static_cast<uint8_t>(0x80U + i);
  }
  const PeerEndpointV2 child{
      "node_child01", hex_array<6>("001122334455")};
  const PeerEndpointV2 relay{
      "node_relay01", hex_array<6>("02aabbccddee")};
  const HandshakeNonce child_boot =
      hex_array<16>("0102030405060708090a0b0c0d0e0f10");
  const HandshakeNonce relay_boot =
      hex_array<16>("1112131415161718191a1b1c1d1e1f20");
  const HandshakeNonce challenge =
      hex_array<16>("2122232425262728292a2b2c2d2e2f30");

  SimpleRelayDiscovery discovery{credential.generation, 6, relay.node_id};
  std::vector<uint8_t> wire;
  assert(encode_simple_relay_discovery(discovery, &wire) == SimpleRuntimeError::NONE);
  SimpleRelayDiscovery parsed_discovery;
  assert(decode_simple_relay_discovery(wire.data(), wire.size(), &parsed_discovery) ==
         SimpleRuntimeError::NONE);
  assert(parsed_discovery.relay_node_id == relay.node_id);

  SimplePeerChallenge challenge_packet;
  assert(build_simple_peer_challenge(
             credential, child, relay, child_boot, challenge,
             &challenge_packet) == SimpleRuntimeError::NONE);
  assert(encode_simple_peer_challenge(challenge_packet, &wire) ==
         SimpleRuntimeError::NONE);
  SimplePeerChallenge parsed_challenge;
  assert(decode_simple_peer_challenge(wire.data(), wire.size(), &parsed_challenge) ==
         SimpleRuntimeError::NONE);
  SimpleLmk relay_lmk{};
  assert(verify_simple_peer_challenge(
             credential, child.mac, relay, parsed_challenge, &relay_lmk) ==
         SimpleRuntimeError::NONE);

  SimplePeerAccept accept_packet;
  assert(build_simple_peer_accept(
             credential, relay, child, relay_boot, challenge,
             &accept_packet) == SimpleRuntimeError::NONE);
  assert(encode_simple_peer_accept(accept_packet, &wire) == SimpleRuntimeError::NONE);
  SimplePeerAccept parsed_accept;
  assert(decode_simple_peer_accept(wire.data(), wire.size(), &parsed_accept) ==
         SimpleRuntimeError::NONE);
  SimpleLmk child_lmk{};
  assert(verify_simple_peer_accept(
             credential, relay.mac, child, parsed_accept, &child_lmk) ==
         SimpleRuntimeError::NONE);
  assert(child_lmk == relay_lmk);

  SimplePeerAccept old_generation = parsed_accept;
  old_generation.peer_trust_generation -= 1U;
  assert(verify_simple_peer_accept(
             credential, relay.mac, child, old_generation, &child_lmk) ==
         SimpleRuntimeError::GENERATION_MISMATCH);

  LocalPathController path(LocalPathPolicy{3, 2, 2});
  assert(path.state() == LocalPathState::DIRECT);
  assert(path.note_direct_result(false) == RadioError::NONE);
  assert(path.note_direct_result(false) == RadioError::NONE);
  assert(path.note_direct_result(false) == RadioError::NONE);
  assert(path.state() == LocalPathState::DISCOVERY);
  assert(path.note_authenticated_relay_ready(true) == RadioError::NONE);
  assert(path.state() == LocalPathState::RELAY_ACTIVE);
  assert(path.note_direct_recovery_probe(true) == RadioError::NONE);
  assert(path.note_direct_recovery_probe(true) == RadioError::NONE);
  assert(path.state() == LocalPathState::DIRECT);
}

}  // namespace

int main() {
  test_pairing_cross_language_vectors();
  test_peer_trust_cross_language_vectors();
  test_compact_telemetry_cross_language_vector();
  test_simple_peer_handshake_and_local_fallback();
  std::cout << "PHASE3_CROSS_LANGUAGE_HOST_TEST=PASS\n";
  return 0;
}
