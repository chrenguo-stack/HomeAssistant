#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>

#include "pairing_async_contract.h"
#include "pairing_mqtt_activation_contract.h"
#include "pairing_persistence_contract.h"

using namespace esphome::greenhouse_pairing_client;

namespace {

CredentialSlotRecord empty_record(CredentialSlot slot) {
  return {
      .schema_version = 1,
      .slot = slot,
      .state = CredentialRecordState::EMPTY,
      .generation = 0,
      .payload_digest = {},
  };
}

CredentialSlotRecord prepared_record(CredentialSlot slot, uint32_t generation,
                                     char digest_character = 'a') {
  return {
      .schema_version = 1,
      .slot = slot,
      .state = CredentialRecordState::PREPARED,
      .generation = generation,
      .payload_digest = std::string(64, digest_character),
  };
}

CredentialSlotRecord committed_record(CredentialSlot slot, uint32_t generation,
                                      char digest_character = 'b') {
  return {
      .schema_version = 1,
      .slot = slot,
      .state = CredentialRecordState::COMMITTED,
      .generation = generation,
      .payload_digest = std::string(64, digest_character),
  };
}

void test_async_matrix() {
  PairingClientSnapshot client{};
  PairingAsyncContract contract;

  assert(!contract.queue(0, client));
  assert(contract.queue(1, client));
  assert(!contract.queue(1, client));
  assert(!contract.finish(PairingAsyncOutcome::SUCCESS, client));
  assert(contract.request_cancel());
  assert(contract.finish(PairingAsyncOutcome::CANCELLED, client));
  assert(contract.snapshot().phase == PairingAsyncPhase::CANCELLED);
  assert(contract.snapshot().cancel_requested);

  assert(contract.queue(2, client));
  assert(contract.begin(client));
  client.state = PairingClientState::SELECTION_REQUIRED;
  client.selection_required = true;
  assert(contract.finish(PairingAsyncOutcome::SELECTION_REQUIRED, client));
  assert(contract.snapshot().phase == PairingAsyncPhase::WAITING_SELECTION);

  client.state = PairingClientState::CLAIM_READY;
  client.selection_required = false;
  assert(contract.queue(3, client));
  assert(contract.publish(PairingAsyncPhase::SECURE_PAIRING, client));
  assert(!contract.publish(PairingAsyncPhase::MQTT_PROBING, client));
  client.state = PairingClientState::CREDENTIALS_STAGED;
  client.credentials_staged = true;
  client.credential_generation = 9;
  assert(contract.publish(PairingAsyncPhase::RAM_STAGED, client));
  assert(contract.publish(PairingAsyncPhase::PERSISTENCE_PREPARED, client));
  assert(contract.publish(PairingAsyncPhase::MQTT_PROBING, client));
  assert(contract.finish(PairingAsyncOutcome::SUCCESS, client));
  assert(contract.snapshot().phase == PairingAsyncPhase::COMPLETED);
  assert(contract.snapshot().credential_generation == 9);

  const uint32_t version = contract.snapshot().state_version;
  contract.reset(client);
  assert(contract.snapshot().state_version > version);
  assert(contract.snapshot().operation_id == 3);
  assert(contract.snapshot().phase == PairingAsyncPhase::IDLE);
}

void test_persistence_matrix() {
  CredentialPersistenceContract journal;
  const std::string digest(64, 'a');

  assert(!journal.configure(CredentialSlot::NONE, 1));
  assert(!journal.configure(CredentialSlot::A, 0));
  assert(!journal.configure(static_cast<CredentialSlot>(9), 1));
  assert(journal.configure(CredentialSlot::A, 5));
  assert(!journal.rollback());
  assert(!journal.prepare(5, digest));
  assert(!journal.prepare(6, std::string(63, 'a')));
  assert(!journal.prepare(6, std::string(64, 'A')));
  assert(journal.prepare(6, digest));
  assert(!journal.commit());
  assert(journal.rollback());
  assert(!journal.rollback());
  assert(journal.snapshot().active_slot == CredentialSlot::A);
  assert(journal.snapshot().active_generation == 5);

  assert(journal.prepare(6, digest));
  assert(journal.mark_profile_verified());
  assert(journal.commit());
  assert(journal.snapshot().active_slot == CredentialSlot::B);
  assert(journal.snapshot().active_generation == 6);
  assert(!journal.rollback());
  assert(!journal.prepare(7, digest));

  CredentialJournalSnapshot recovered{};
  const auto empty_a = empty_record(CredentialSlot::A);
  const auto empty_b = empty_record(CredentialSlot::B);
  assert(CredentialPersistenceContract::recover(
      empty_a, empty_b, CredentialSlot::NONE, 0, &recovered));
  assert(recovered.active_slot == CredentialSlot::NONE);

  const auto prepared_a = prepared_record(CredentialSlot::A, 1);
  assert(CredentialPersistenceContract::recover(
      prepared_a, empty_b, CredentialSlot::NONE, 0, &recovered));
  assert(recovered.prepared && recovered.candidate_slot == CredentialSlot::A &&
         recovered.candidate_generation == 1);
  assert(!CredentialPersistenceContract::recover(
      prepared_a, prepared_record(CredentialSlot::B, 2),
      CredentialSlot::NONE, 0, &recovered));
  assert(!CredentialPersistenceContract::recover(
      committed_record(CredentialSlot::A, 1), empty_b,
      CredentialSlot::NONE, 0, &recovered));

  const auto active_a = committed_record(CredentialSlot::A, 5);
  assert(CredentialPersistenceContract::recover(
      active_a, empty_b, CredentialSlot::A, 5, &recovered));
  assert(recovered.active_slot == CredentialSlot::A &&
         recovered.active_generation == 5 && recovered.committed);
  assert(CredentialPersistenceContract::recover(
      active_a, committed_record(CredentialSlot::B, 4),
      CredentialSlot::A, 5, &recovered));
  assert(!CredentialPersistenceContract::recover(
      active_a, committed_record(CredentialSlot::B, 5),
      CredentialSlot::A, 5, &recovered));
  assert(!CredentialPersistenceContract::recover(
      active_a, committed_record(CredentialSlot::B, 6),
      CredentialSlot::A, 5, &recovered));
  assert(CredentialPersistenceContract::recover(
      active_a, prepared_record(CredentialSlot::B, 6),
      CredentialSlot::A, 5, &recovered));
  assert(recovered.prepared && recovered.candidate_generation == 6);
  assert(!CredentialPersistenceContract::recover(
      active_a, prepared_record(CredentialSlot::B, 5),
      CredentialSlot::A, 5, &recovered));
  assert(!CredentialPersistenceContract::recover(
      active_a, prepared_record(CredentialSlot::B, 4),
      CredentialSlot::A, 5, &recovered));

  auto wrong_physical_slot = empty_record(CredentialSlot::A);
  assert(!CredentialPersistenceContract::recover(
      active_a, wrong_physical_slot, CredentialSlot::A, 5, &recovered));
  auto invalid_digest = committed_record(CredentialSlot::B, 6);
  invalid_digest.payload_digest[0] = 'Z';
  assert(!CredentialPersistenceContract::recover(
      active_a, invalid_digest, CredentialSlot::A, 5, &recovered));
  assert(!CredentialPersistenceContract::recover(
      active_a, empty_b, CredentialSlot::A, 4, &recovered));
  assert(!CredentialPersistenceContract::recover(
      active_a, empty_b, static_cast<CredentialSlot>(9), 5, &recovered));
}

void test_mqtt_matrix() {
  for (uint8_t bits = 0; bits < 8; bits++) {
    const bool authenticated = (bits & 0x1U) != 0;
    const bool subscribe_ready = (bits & 0x2U) != 0;
    const bool telemetry_round_trip = (bits & 0x4U) != 0;
    const bool expected = bits == 7;

    MqttActivationContract mqtt;
    assert(mqtt.configure(10));
    assert(!mqtt.rollback());
    assert(!mqtt.stage(10));
    assert(mqtt.stage(11));
    assert(!mqtt.stage(12));
    assert(mqtt.begin_probe());
    assert(mqtt.record_probe(authenticated, subscribe_ready,
                             telemetry_round_trip) == expected);
    if (expected) {
      assert(mqtt.snapshot().phase == MqttActivationPhase::VERIFIED);
      assert(mqtt.activate());
      assert(mqtt.snapshot().phase == MqttActivationPhase::ACTIVATED);
      assert(mqtt.snapshot().active_generation == 11);
      assert(!mqtt.rollback());
      assert(!mqtt.stage(12));
    } else {
      assert(mqtt.snapshot().phase == MqttActivationPhase::FAILED);
      assert(!mqtt.activate());
      assert(mqtt.rollback());
      assert(mqtt.snapshot().active_generation == 10);
      assert(mqtt.snapshot().candidate_generation == 0);
      assert(!mqtt.rollback());
      assert(mqtt.stage(12));
    }
  }
}

}  // namespace

int main() {
  test_async_matrix();
  test_persistence_matrix();
  test_mqtt_matrix();
  std::cout << "stage2c3 fault matrix passed\n";
  return 0;
}
