#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

#include "pairing_persistence_crypto.h"

using namespace esphome::greenhouse_pairing_client;

namespace {

bool all_zero(const std::array<uint8_t, 32> &value) {
  return std::all_of(value.begin(), value.end(),
                     [](uint8_t byte) { return byte == 0; });
}

bool metadata_empty(const PersistenceEnvelopeMetadata &metadata) {
  return metadata.slot == CredentialSlot::NONE &&
         metadata.state == CredentialRecordState::INVALID &&
         metadata.generation == 0 && metadata.plaintext_size == 0 &&
         all_zero(metadata.digest);
}

}  // namespace

int main() {
  std::array<uint8_t, 32> root{};
  for (size_t index = 0; index < root.size(); index++)
    root[index] = static_cast<uint8_t>(index + 1);
  FixedPersistenceKeyProvider provider(root);
  PairingPersistenceCrypto crypto(&provider);

  std::array<uint8_t, 32> stale_key{};
  stale_key.fill(0xa5);
  assert(!provider.derive_key(CredentialSlot::NONE, 1, &stale_key));
  assert(all_zero(stale_key));
  stale_key.fill(0x5a);
  assert(!provider.derive_key(CredentialSlot::A, 0, &stale_key));
  assert(all_zero(stale_key));

  std::vector<uint8_t> stale_envelope = {1, 2, 3, 4};
  const std::vector<uint8_t> plaintext = {'o', 'k'};
  assert(!crypto.seal(CredentialSlot::NONE,
                      CredentialRecordState::PREPARED, 1, plaintext,
                      &stale_envelope));
  assert(stale_envelope.empty());
  stale_envelope = {5, 6, 7};
  assert(!crypto.seal(CredentialSlot::A,
                      CredentialRecordState::PREPARED, 0, plaintext,
                      &stale_envelope));
  assert(stale_envelope.empty());

  PersistenceEnvelopeMetadata metadata{};
  metadata.slot = CredentialSlot::B;
  metadata.state = CredentialRecordState::COMMITTED;
  metadata.generation = 99;
  metadata.plaintext_size = 99;
  metadata.digest.fill(0x7f);
  assert(!PairingPersistenceCrypto::inspect({1, 2, 3}, &metadata));
  assert(metadata_empty(metadata));

  std::vector<uint8_t> opened_plaintext = {9, 9, 9};
  metadata.slot = CredentialSlot::B;
  metadata.state = CredentialRecordState::COMMITTED;
  metadata.generation = 88;
  metadata.plaintext_size = 88;
  metadata.digest.fill(0x6e);
  assert(!crypto.open({1, 2, 3}, &metadata, &opened_plaintext));
  assert(metadata_empty(metadata));
  assert(opened_plaintext.empty());

  std::vector<uint8_t> valid_envelope;
  assert(crypto.seal(CredentialSlot::A,
                     CredentialRecordState::PREPARED, 1, plaintext,
                     &valid_envelope));
  assert(crypto.open(valid_envelope, &metadata, &opened_plaintext));
  assert(metadata.slot == CredentialSlot::A);
  assert(metadata.state == CredentialRecordState::PREPARED);
  assert(metadata.generation == 1);
  assert(opened_plaintext == plaintext);

  valid_envelope.back() ^= 0x01;
  metadata.slot = CredentialSlot::B;
  metadata.state = CredentialRecordState::COMMITTED;
  metadata.generation = 77;
  metadata.plaintext_size = 77;
  metadata.digest.fill(0x4d);
  opened_plaintext = {8, 8, 8};
  assert(!crypto.open(valid_envelope, &metadata, &opened_plaintext));
  assert(metadata_empty(metadata));
  assert(opened_plaintext.empty());

  std::cout << "stage2d1 persistence crypto output safety passed\n";
  return 0;
}
