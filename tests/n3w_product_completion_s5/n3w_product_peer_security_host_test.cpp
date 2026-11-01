#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>

#include "esphome/components/greenhouse_n3w_product_runtime/n3w_product_peer_security.h"

using esphome::greenhouse_n3w_core::LinkKey;
using esphome::greenhouse_n3w_product_runtime::ProductPeerGrant;
using esphome::greenhouse_n3w_product_runtime::ProductPeerKey;
using esphome::greenhouse_n3w_product_runtime::ProductPeerNonce;
using esphome::greenhouse_n3w_product_runtime::ProductPeerProof;
using esphome::greenhouse_n3w_product_runtime::ProductPeerRequest;
using esphome::greenhouse_n3w_product_runtime::ProductPeerRole;
using esphome::greenhouse_n3w_product_runtime::ProductPeerSecurity;

namespace {

template <std::size_t N>
std::array<uint8_t, N> from_hex(const std::string &hex) {
  assert(hex.size() == N * 2);
  std::array<uint8_t, N> output{};
  for (std::size_t index = 0; index < N; ++index) {
    output[index] = static_cast<uint8_t>(
        std::stoul(hex.substr(index * 2, 2), nullptr, 16));
  }
  return output;
}

void assert_equal(const ProductPeerKey &actual, const ProductPeerKey &expected) {
  assert(actual == expected);
}

}  // namespace

int main() {
  const ProductPeerKey child_private = from_hex<32>(
      "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20");
  const ProductPeerKey relay_private = from_hex<32>(
      "2122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f40");
  const ProductPeerKey expected_child_public = from_hex<32>(
      "07a37cbc142093c8b755dc1b10e86cb426374ad16aa853ed0bdfc0b2b86d1c7c");
  const ProductPeerKey expected_relay_public = from_hex<32>(
      "5869aff450549732cbaaed5e5df9b30a6da31cb0e5742bad5ad4a1a768f1a67b");
  const ProductPeerKey child_application_key = from_hex<32>(
      "8182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9fa0");
  const ProductPeerKey relay_application_key = from_hex<32>(
      "a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebfc0");
  const ProductPeerNonce child_nonce = from_hex<32>(
      "4142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f60");
  const ProductPeerNonce relay_nonce = from_hex<32>(
      "6162636465666768696a6b6c6d6e6f707172737475767778797a7b7c7d7e7f80");

  ProductPeerKey child_public{};
  ProductPeerKey relay_public{};
  assert(ProductPeerSecurity::x25519_public_key(child_private, &child_public));
  assert(ProductPeerSecurity::x25519_public_key(relay_private, &relay_public));
  assert_equal(child_public, expected_child_public);
  assert_equal(relay_public, expected_relay_public);

  ProductPeerKey child_auth{};
  ProductPeerKey relay_auth{};
  assert(ProductPeerSecurity::derive_relay_auth_key(
      child_application_key, "system001", "node_child01", 1, 1, &child_auth));
  assert(ProductPeerSecurity::derive_relay_auth_key(
      relay_application_key, "system001", "node_relay01", 2, 3, &relay_auth));
  assert_equal(
      child_auth,
      from_hex<32>("ae5c57299e4915e934e7a84d19158b033542fa0418751e5262036c088aea5bd0"));
  assert_equal(
      relay_auth,
      from_hex<32>("af1c7d570a32112cf2221b366fa8eebd4290de97958c0637c188f7c20c2b8bf0"));

  ProductPeerRequest request;
  request.system_id = "system001";
  request.session_id = "s5-session-0001";
  request.requested_at_ms = 1786689000000ULL;
  request.child.node_id = "node_child01";
  request.child.credential_generation = 1;
  request.child.key_epoch = 1;
  request.child.ephemeral_public_key = child_public;
  request.child.nonce = child_nonce;
  request.relay.node_id = "node_relay01";
  request.relay.credential_generation = 2;
  request.relay.key_epoch = 3;
  request.relay.ephemeral_public_key = relay_public;
  request.relay.nonce = relay_nonce;
  request.relay_health.observed_at_ms = 1786688999000ULL;
  request.relay_health.relay_capable = true;
  request.relay_health.low_battery = false;
  request.relay_health.overloaded = false;

  ProductPeerProof child_proof{};
  ProductPeerProof relay_proof{};
  assert(ProductPeerSecurity::build_endpoint_proof(
      request, ProductPeerRole::CHILD, child_auth, &child_proof));
  assert(ProductPeerSecurity::build_endpoint_proof(
      request, ProductPeerRole::RELAY, relay_auth, &relay_proof));
  assert(child_proof == from_hex<32>(
      "01d10498afbfe1c88a50992e614ec1b4c43ef6d715fdb6b1dc7fc1784f653db8"));
  assert(relay_proof == from_hex<32>(
      "7cd74be1126de0087da8dad7e2dce68510913c324dd93f0d07d0892a97706801"));

  ProductPeerGrant child_grant;
  child_grant.role = ProductPeerRole::CHILD;
  child_grant.authorization_id = "11111111-2222-3333-4444-555555555555";
  child_grant.system_id = "system001";
  child_grant.session_id = "s5-session-0001";
  child_grant.child_node_id = "node_child01";
  child_grant.relay_node_id = "node_relay01";
  child_grant.child_credential_generation = 1;
  child_grant.relay_credential_generation = 2;
  child_grant.child_key_epoch = 1;
  child_grant.relay_key_epoch = 3;
  child_grant.child_ephemeral_public_key = child_public;
  child_grant.relay_ephemeral_public_key = relay_public;
  child_grant.child_nonce = child_nonce;
  child_grant.relay_nonce = relay_nonce;
  child_grant.issued_at_ms = 1786689000100ULL;
  child_grant.expires_at_ms = 1786689030000ULL;
  child_grant.authorization_epoch = 7;
  child_grant.grant_mac = from_hex<32>(
      "49263fe315de3a170592be8b56cb0183c62d6a721ee12f961bc30f8faf280cc8");

  ProductPeerGrant relay_grant = child_grant;
  relay_grant.role = ProductPeerRole::RELAY;
  relay_grant.grant_mac = from_hex<32>(
      "d4172a3446782ffd863155900224f14fb48a9741eed2cc286a027d711c055f04");

  assert(ProductPeerSecurity::verify_endpoint_grant(
      child_grant, child_auth, 1786689000200ULL));
  assert(ProductPeerSecurity::verify_endpoint_grant(
      relay_grant, relay_auth, 1786689000200ULL));
  assert(!ProductPeerSecurity::verify_endpoint_grant(
      child_grant, relay_auth, 1786689000200ULL));
  assert(!ProductPeerSecurity::verify_endpoint_grant(
      relay_grant, child_auth, 1786689000200ULL));
  assert(!ProductPeerSecurity::verify_endpoint_grant(
      child_grant, child_auth, child_grant.expires_at_ms));

  LinkKey child_lmk{};
  LinkKey relay_lmk{};
  assert(ProductPeerSecurity::derive_pair_lmk(
      child_private, relay_public, child_grant, &child_lmk));
  assert(ProductPeerSecurity::derive_pair_lmk(
      relay_private, child_public, relay_grant, &relay_lmk));
  const LinkKey expected_lmk =
      from_hex<16>("aaebd482e2dec5346c9d11b00ad9c3fb");
  assert(child_lmk == expected_lmk);
  assert(relay_lmk == expected_lmk);

  std::cout << "S5_PRODUCT_PEER_SECURITY_VECTOR=PASS\n";
  return 0;
}
